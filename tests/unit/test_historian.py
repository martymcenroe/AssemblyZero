"""Tests for the Historian node (RAG history check).

Issue #91: The Historian — check for similar past work before drafting.
"""

from __future__ import annotations

from unittest import mock

import pytest

from assemblyzero.rag.models import RetrievedDocument
from assemblyzero.workflows.issue.nodes.historian import (
    HIGH_THRESHOLD,
    MEDIUM_THRESHOLD,
    _format_history_context,
    handle_historian_decision,
    historian,
)


def _make_doc(score: float, path: str = "docs/lineage/done/42-lld/001-brief.md") -> RetrievedDocument:
    """Create a RetrievedDocument with the given score."""
    return RetrievedDocument(
        file_path=path,
        section="Test Section",
        content_snippet="Some past work content",
        score=score,
        doc_type="lineage",
    )


def _make_state(brief: str = "Add caching to API") -> dict:
    """Create a minimal IssueWorkflowState dict."""
    return {"brief_content": brief}


class TestHistorianNode:
    """Tests for the historian() node function."""

    @mock.patch("assemblyzero.rag.dependencies.check_rag_dependencies")
    def test_rag_unavailable_fails_open(self, mock_deps):
        """When RAG deps aren't available, returns unavailable status."""
        mock_deps.return_value = (False, "chromadb not installed")
        result = historian(_make_state())
        assert result["history_status"] == "unavailable"
        assert result["history_matches"] == []
        assert result["history_context"] == ""

    @mock.patch("assemblyzero.rag.dependencies.check_rag_dependencies")
    @mock.patch("assemblyzero.rag.librarian.LibrarianNode")
    def test_librarian_not_ready(self, mock_librarian_cls, mock_deps):
        """When Librarian isn't initialized, returns unavailable."""
        mock_deps.return_value = (True, "ok")
        mock_lib = mock_librarian_cls.return_value
        mock_lib.check_availability.return_value = (False, "no_store")
        result = historian(_make_state())
        assert result["history_status"] == "unavailable"

    @mock.patch("assemblyzero.rag.dependencies.check_rag_dependencies")
    @mock.patch("assemblyzero.rag.librarian.LibrarianNode")
    def test_high_similarity(self, mock_librarian_cls, mock_deps):
        """High similarity (>=0.85) returns high_similarity status."""
        mock_deps.return_value = (True, "ok")
        mock_lib = mock_librarian_cls.return_value
        mock_lib.check_availability.return_value = (True, "ready")
        mock_lib.retrieve.return_value = [_make_doc(0.92), _make_doc(0.60)]

        result = historian(_make_state())

        assert result["history_status"] == "high_similarity"
        assert len(result["history_matches"]) == 2
        assert "Past Work References" in result["history_context"]

    @mock.patch("assemblyzero.rag.dependencies.check_rag_dependencies")
    @mock.patch("assemblyzero.rag.librarian.LibrarianNode")
    def test_medium_similarity(self, mock_librarian_cls, mock_deps):
        """Medium similarity (0.5-0.85) returns medium status with context."""
        mock_deps.return_value = (True, "ok")
        mock_lib = mock_librarian_cls.return_value
        mock_lib.check_availability.return_value = (True, "ready")
        mock_lib.retrieve.return_value = [_make_doc(0.72)]

        result = historian(_make_state())

        assert result["history_status"] == "medium_similarity"
        assert result["history_context"] != ""

    @mock.patch("assemblyzero.rag.dependencies.check_rag_dependencies")
    @mock.patch("assemblyzero.rag.librarian.LibrarianNode")
    def test_low_similarity(self, mock_librarian_cls, mock_deps):
        """Low similarity (<0.5) returns low status with no context."""
        mock_deps.return_value = (True, "ok")
        mock_lib = mock_librarian_cls.return_value
        mock_lib.check_availability.return_value = (True, "ready")
        mock_lib.retrieve.return_value = [_make_doc(0.30)]

        result = historian(_make_state())

        assert result["history_status"] == "low_similarity"
        assert result["history_context"] == ""

    @mock.patch("assemblyzero.rag.dependencies.check_rag_dependencies")
    @mock.patch("assemblyzero.rag.librarian.LibrarianNode")
    def test_no_results(self, mock_librarian_cls, mock_deps):
        """Empty results returns low_similarity."""
        mock_deps.return_value = (True, "ok")
        mock_lib = mock_librarian_cls.return_value
        mock_lib.check_availability.return_value = (True, "ready")
        mock_lib.retrieve.return_value = []

        result = historian(_make_state())

        assert result["history_status"] == "low_similarity"
        assert result["history_matches"] == []

    def test_empty_brief(self):
        """Empty brief content returns unavailable."""
        result = historian({"brief_content": ""})
        assert result["history_status"] == "unavailable"

    @mock.patch("assemblyzero.rag.dependencies.check_rag_dependencies")
    def test_exception_fails_open(self, mock_deps):
        """Any exception during query fails open."""
        mock_deps.side_effect = RuntimeError("unexpected error")
        result = historian(_make_state())
        assert result["history_status"] == "unavailable"


class TestHistorianDecision:
    """Tests for handle_historian_decision()."""

    def test_abort(self):
        result = handle_historian_decision("abort")
        assert result["historian_decision"] == "abort"
        assert "HISTORIAN_ABORT" in result["error_message"]

    def test_link(self):
        result = handle_historian_decision("link")
        assert result["historian_decision"] == "link"
        assert "error_message" not in result

    def test_ignore(self):
        result = handle_historian_decision("ignore")
        assert result["historian_decision"] == "ignore"
        assert result["history_context"] == ""

    def test_case_insensitive(self):
        result = handle_historian_decision("ABORT")
        assert result["historian_decision"] == "abort"


class TestFormatHistoryContext:
    """Tests for _format_history_context()."""

    def test_formats_above_threshold(self):
        docs = [_make_doc(0.90), _make_doc(0.40)]
        context = _format_history_context(docs)
        # Only the 0.90 doc should appear (above MEDIUM_THRESHOLD)
        assert "0.90" in context
        assert "0.40" not in context

    def test_empty_docs(self):
        context = _format_history_context([])
        assert "Past Work References" in context

    def test_truncates_long_snippets(self):
        doc = RetrievedDocument(
            file_path="test.md",
            section="Test",
            content_snippet="x" * 600,
            score=0.80,
            doc_type="lineage",
        )
        context = _format_history_context([doc])
        assert "..." in context
