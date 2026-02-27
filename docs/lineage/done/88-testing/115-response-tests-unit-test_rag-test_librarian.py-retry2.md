The current file on disk already has the correct fixes from the previous attempt. The timeout on attempt 2 was just a response timeout, not a test failure. The file is correct. Let me output it:

```python
"""Unit tests for LibrarianNode retrieval logic.

Issue #88: The Librarian - Automated Context Retrieval
Tests: T090, T100, T110, T120, T130, T140, T150, T160, T170, T180, T190
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.rag.models import RAGConfig, RetrievedDocument


def _make_doc(
    file_path: str = "docs/adrs/0201.md",
    section: str = "## 2. Decision",
    score: float = 0.85,
    doc_type: str = "adr",
) -> RetrievedDocument:
    """Helper to create a RetrievedDocument for testing."""
    return RetrievedDocument(
        file_path=file_path,
        section=section,
        content_snippet=f"Content from {file_path}",
        score=score,
        doc_type=doc_type,
    )


class TestLibrarianNodeRetrieve:
    """Tests for LibrarianNode.retrieve()."""

    @pytest.mark.rag
    def test_threshold_filtering(self, tmp_path: Path) -> None:
        """T090: LibrarianNode.retrieve filters by threshold (REQ-4)."""
        from assemblyzero.rag.librarian import LibrarianNode

        config = RAGConfig(
            vector_store_path=tmp_path / "store",
            similarity_threshold=0.7,
            top_k_candidates=5,
            top_n_results=3,
        )
        librarian = LibrarianNode(config=config)

        # Mock the embedding provider and vector store
        mock_provider = MagicMock()
        mock_provider.embed_query.return_value = [0.1] * 384
        librarian._embedding_provider = mock_provider

        mock_store = MagicMock()
        mock_store.query.return_value = [
            _make_doc(score=0.90),
            _make_doc(file_path="docs/adrs/0202.md", score=0.75),
            _make_doc(file_path="docs/standards/0001.md", score=0.60),  # Below threshold
            _make_doc(file_path="docs/standards/0002.md", score=0.50),  # Below threshold
        ]
        librarian._vector_store = mock_store

        results = librarian.retrieve("test brief")
        assert all(doc.score >= 0.7 for doc in results)
        assert len(results) == 2  # Only 2 above 0.7

    @pytest.mark.rag
    def test_top_n_limiting(self, tmp_path: Path) -> None:
        """T100: LibrarianNode.retrieve returns max top_n_results (REQ-4)."""
        from assemblyzero.rag.librarian import LibrarianNode

        config = RAGConfig(
            vector_store_path=tmp_path / "store",
            similarity_threshold=0.5,
            top_k_candidates=5,
            top_n_results=3,
        )
        librarian = LibrarianNode(config=config)

        mock_provider = MagicMock()
        mock_provider.embed_query.return_value = [0.1] * 384
        librarian._embedding_provider = mock_provider

        mock_store = MagicMock()
        mock_store.query.return_value = [
            _make_doc(file_path=f"docs/adrs/020{i}.md", score=0.9 - i * 0.05)
            for i in range(5)
        ]
        librarian._vector_store = mock_store

        results = librarian.retrieve("test brief")
        assert len(results) == 3  # top_n_results limits to 3

    @pytest.mark.rag
    def test_threshold_override(self, tmp_path: Path) -> None:
        """LibrarianNode.retrieve respects explicit threshold override."""
        from assemblyzero.rag.librarian import LibrarianNode

        config = RAGConfig(
            vector_store_path=tmp_path / "store",
            similarity_threshold=0.7,
            top_k_candidates=5,
            top_n_results=3,
        )
        librarian = LibrarianNode(config=config)

        mock_provider = MagicMock()
        mock_provider.embed_query.return_value = [0.1] * 384
        librarian._embedding_provider = mock_provider

        mock_store = MagicMock()
        mock_store.query.return_value = [
            _make_doc(score=0.90),
            _make_doc(file_path="docs/adrs/0202.md", score=0.85),
            _make_doc(file_path="docs/standards/0001.md", score=0.60),
        ]
        librarian._vector_store = mock_store

        # Override threshold to 0.8
        results = librarian.retrieve("test brief", threshold=0.8)
        assert all(doc.score >= 0.8 for doc in results)
        assert len(results) == 2

    @pytest.mark.rag
    def test_all_below_threshold_returns_empty(self, tmp_path: Path) -> None:
        """All candidates below threshold returns empty list."""
        from assemblyzero.rag.librarian import LibrarianNode

        config = RAGConfig(
            vector_store_path=tmp_path / "store",
            similarity_threshold=0.9,
            top_k_candidates=5,
            top_n_results=3,
        )
        librarian = LibrarianNode(config=config)

        mock_provider = MagicMock()
        mock_provider.embed_query.return_value = [0.1] * 384
        librarian._embedding_provider = mock_provider

        mock_store = MagicMock()
        mock_store.query.return_value = [
            _make_doc(score=0.60),
            _make_doc(file_path="docs/adrs/0202.md", score=0.50),
        ]
        librarian._vector_store = mock_store

        results = librarian.retrieve("test brief")
        assert results == []


class TestLibrarianNodeAvailability:
    """Tests for LibrarianNode.check_availability()."""

    def test_no_deps(self) -> None:
        """T110: check_availability with no deps (REQ-9)."""
        with patch(
            "assemblyzero.rag.librarian.check_rag_dependencies",
            return_value=(False, "Missing: chromadb"),
        ):
            from assemblyzero.rag.librarian import LibrarianNode

            librarian = LibrarianNode()
            available, status = librarian.check_availability()
            assert available is False
            assert status == "deps_missing"

    @pytest.mark.rag
    def test_no_store(self, tmp_path: Path) -> None:
        """T120: check_availability with no store (REQ-8)."""
        from assemblyzero.rag.librarian import LibrarianNode

        config = RAGConfig(vector_store_path=tmp_path / "nonexistent_store")
        librarian = LibrarianNode(config=config)
        available, status = librarian.check_availability()
        assert available is False
        assert status == "unavailable"

    @pytest.mark.rag
    def test_store_ready(self, tmp_path: Path) -> None:
        """check_availability succeeds with initialized store."""
        from assemblyzero.rag.librarian import LibrarianNode
        from assemblyzero.rag.vector_store import VectorStoreManager

        config = RAGConfig(vector_store_path=tmp_path / "store")
        store = VectorStoreManager(config)
        store.initialize()

        librarian = LibrarianNode(config=config)
        # Inject the already-initialized store so check_availability uses
        # the same FakeClient instance (avoids _client_cache timing issues
        # across module reloads in test teardown).
        librarian._vector_store = store

        available, status = librarian.check_availability()
        assert available is True
        assert "Librarian ready" in status


class TestLibrarianNodeFormat:
    """Tests for LibrarianNode.format_context_for_designer()."""

    def test_format_produces_readable_output(self) -> None:
        """T190: format_context_for_designer produces readable output."""
        from assemblyzero.rag.librarian import LibrarianNode

        librarian = LibrarianNode()
        docs = [
            _make_doc(file_path="docs/adrs/0201.md", score=0.85),
            _make_doc(
                file_path="docs/standards/0005.md",
                section="## 3. Coverage",
                score=0.72,
                doc_type="standard",
            ),
        ]
        formatted = librarian.format_context_for_designer(docs)
        assert "docs/adrs/0201.md" in formatted
        assert "docs/standards/0005.md" in formatted
        assert "0.85" in formatted
        assert "## 2. Decision" in formatted
        assert "Retrieved Context (RAG)" in formatted

    def test_format_empty_documents(self) -> None:
        """Empty document list returns empty string."""
        from assemblyzero.rag.librarian import LibrarianNode

        librarian = LibrarianNode()
        assert librarian.format_context_for_designer([]) == ""

    def test_format_single_document(self) -> None:
        """Single document formats correctly."""
        from assemblyzero.rag.librarian import LibrarianNode

        librarian = LibrarianNode()
        docs = [_make_doc(file_path="docs/adrs/0201.md", score=0.85)]
        formatted = librarian.format_context_for_designer(docs)
        assert "docs/adrs/0201.md" in formatted
        assert "0.85" in formatted
        assert "adr" in formatted
        assert "---" in formatted


class TestLibrarianNode:
    """Tests for librarian_node() LangGraph wrapper.

    These tests patch module-level names in assemblyzero.nodes.librarian.
    The ``create=True`` parameter is required for LibrarianNode because the
    module uses guarded imports (``if "LibrarianNode" not in globals()``)
    and the attribute may not exist after module reloads in test teardown
    (_reset_singletons).  No importlib.reload() is needed because
    librarian_node() resolves names from its module globals at call time,
    so patching the attribute is sufficient.
    """

    def test_deps_missing_graceful(self) -> None:
        """T130: librarian_node sets rag_status='deps_missing' (REQ-9)."""
        from assemblyzero.nodes.librarian import librarian_node

        with patch(
            "assemblyzero.nodes.librarian.check_rag_dependencies",
            return_value=(False, "Missing: chromadb"),
            create=True,
        ):
            state = {
                "issue_brief": "test brief",
                "manual_context_paths": [],
                "retrieved_context": [],
                "rag_status": "",
                "designer_output": "",
            }
            result = librarian_node(state)
            assert result["rag_status"] == "deps_missing"
            assert result["retrieved_context"] == []

    def test_store_unavailable_graceful(self) -> None:
        """T140: librarian_node sets rag_status='unavailable' (REQ-8)."""
        from assemblyzero.nodes.librarian import librarian_node

        mock_instance = MagicMock()
        mock_instance.check_availability.return_value = (False, "unavailable")

        with patch(
            "assemblyzero.nodes.librarian.check_rag_dependencies",
            return_value=(True, "available"),
            create=True,
        ), patch(
            "assemblyzero.nodes.librarian.LibrarianNode",
            return_value=mock_instance,
            create=True,
        ):
            state = {
                "issue_brief": "test brief",
                "manual_context_paths": [],
                "retrieved_context": [],
                "rag_status": "",
                "designer_output": "",
            }
            result = librarian_node(state)
            assert result["rag_status"] == "unavailable"

    def test_no_results_above_threshold(self) -> None:
        """T150: librarian_node sets rag_status='no_results' (REQ-4)."""
        from assemblyzero.nodes.librarian import librarian_node

        mock_instance = MagicMock()
        mock_instance.check_availability.return_value = (True, "ready")
        mock_instance.retrieve.return_value = []  # No results

        with patch(
            "assemblyzero.nodes.librarian.check_rag_dependencies",
            return_value=(True, "available"),
            create=True,
        ), patch(
            "assemblyzero.nodes.librarian.LibrarianNode",
            return_value=mock_instance,
            create=True,
        ):
            state = {
                "issue_brief": "test brief",
                "manual_context_paths": [],
                "retrieved_context": [],
                "rag_status": "",
                "designer_output": "",
            }
            result = librarian_node(state)
            assert result["rag_status"] == "no_results"

    def test_success_with_info_logging(self, caplog: pytest.LogCaptureFixture) -> None:
        """T160: librarian_node success with INFO logging (REQ-14)."""
        from assemblyzero.nodes.librarian import librarian_node

        mock_instance = MagicMock()
        mock_instance.check_availability.return_value = (True, "ready")
        mock_instance.retrieve.return_value = [
            _make_doc(score=0.85),
            _make_doc(file_path="docs/standards/0005.md", score=0.75),
        ]

        with patch(
            "assemblyzero.nodes.librarian.check_rag_dependencies",
            return_value=(True, "available"),
            create=True,
        ), patch(
            "assemblyzero.nodes.librarian.LibrarianNode",
            return_value=mock_instance,
            create=True,
        ):
            state = {
                "issue_brief": "test brief about RAG retrieval",
                "manual_context_paths": [],
                "retrieved_context": [],
                "rag_status": "",
                "designer_output": "",
            }
            with caplog.at_level(logging.INFO):
                result = librarian_node(state)

            assert result["rag_status"] == "success"
            assert len(result["retrieved_context"]) == 2
            assert any(
                "Retrieved 2 documents" in record.message
                for record in caplog.records
            )

    def test_deps_missing_status_from_check_availability(self) -> None:
        """librarian_node handles deps_missing from check_availability."""
        from assemblyzero.nodes.librarian import librarian_node

        mock_instance = MagicMock()
        mock_instance.check_availability.return_value = (False, "deps_missing")

        with patch(
            "assemblyzero.nodes.librarian.check_rag_dependencies",
            return_value=(True, "available"),
            create=True,
        ), patch(
            "assemblyzero.nodes.librarian.LibrarianNode",
            return_value=mock_instance,
            create=True,
        ):
            state = {
                "issue_brief": "test brief",
                "manual_context_paths": [],
                "retrieved_context": [],
                "rag_status": "",
                "designer_output": "",
            }
            result = librarian_node(state)
            assert result["rag_status"] == "deps_missing"

    def test_retrieval_exception_graceful(self) -> None:
        """librarian_node handles retrieval exceptions gracefully."""
        from assemblyzero.nodes.librarian import librarian_node

        mock_instance = MagicMock()
        mock_instance.check_availability.return_value = (True, "ready")
        mock_instance.retrieve.side_effect = RuntimeError("Connection lost")

        with patch(
            "assemblyzero.nodes.librarian.check_rag_dependencies",
            return_value=(True, "available"),
            create=True,
        ), patch(
            "assemblyzero.nodes.librarian.LibrarianNode",
            return_value=mock_instance,
            create=True,
        ):
            state = {
                "issue_brief": "test brief",
                "manual_context_paths": [],
                "retrieved_context": [],
                "rag_status": "",
                "designer_output": "",
            }
            result = librarian_node(state)
            assert result["rag_status"] == "unavailable"
            assert result["retrieved_context"] == []


class TestMergeContexts:
    """Tests for merge_contexts()."""

    def test_dedup_by_file_path(self, tmp_path: Path) -> None:
        """T170: merge_contexts deduplicates by file_path (REQ-7)."""
        from assemblyzero.nodes.librarian import merge_contexts

        # Create a manual file
        manual_file = tmp_path / "standards" / "0005.md"
        manual_file.parent.mkdir(parents=True)
        manual_file.write_text("Manual content")

        rag_results = [
            _make_doc(file_path=str(manual_file), score=0.85),
            _make_doc(file_path="docs/adrs/0201.md", score=0.75),
        ]
        manual_paths = [str(manual_file)]

        merged = merge_contexts(rag_results, manual_paths)
        # Manual version kept, RAG version of same file removed
        file_paths = [m["file_path"] for m in merged]
        assert file_paths.count(str(manual_file)) == 1
        assert len(merged) == 2  # 1 manual + 1 unique RAG

    def test_manual_first(self, tmp_path: Path) -> None:
        """T180: merge_contexts puts manual first (REQ-7)."""
        from assemblyzero.nodes.librarian import merge_contexts

        manual_file = tmp_path / "manual.md"
        manual_file.write_text("Manual content")

        rag_results = [
            _make_doc(file_path="docs/adrs/0201.md", score=0.85),
        ]
        manual_paths = [str(manual_file)]

        merged = merge_contexts(rag_results, manual_paths)
        assert merged[0]["doc_type"] == "manual"
        assert merged[0]["file_path"] == str(manual_file)
        assert merged[1]["file_path"] == "docs/adrs/0201.md"

    def test_no_manual_no_rag(self) -> None:
        """Empty inputs produce empty output."""
        from assemblyzero.nodes.librarian import merge_contexts

        merged = merge_contexts([], [])
        assert merged == []

    def test_manual_score_is_one(self, tmp_path: Path) -> None:
        """Manual context entries have score 1.0."""
        from assemblyzero.nodes.librarian import merge_contexts

        manual_file = tmp_path / "manual.md"
        manual_file.write_text("Manual content")

        merged = merge_contexts([], [str(manual_file)])
        assert len(merged) == 1
        assert merged[0]["score"] == 1.0
        assert merged[0]["doc_type"] == "manual"
        assert merged[0]["section"] == "Full Document"

    def test_manual_file_not_found(self, tmp_path: Path) -> None:
        """Missing manual file is handled gracefully with error content."""
        from assemblyzero.nodes.librarian import merge_contexts

        missing_path = str(tmp_path / "nonexistent.md")
        merged = merge_contexts([], [missing_path])
        assert len(merged) == 1
        assert merged[0]["file_path"] == missing_path
        assert merged[0]["doc_type"] == "manual"

    def test_rag_only(self) -> None:
        """RAG results without manual context work correctly."""
        from assemblyzero.nodes.librarian import merge_contexts

        rag_results = [
            _make_doc(file_path="docs/adrs/0201.md", score=0.85),
            _make_doc(file_path="docs/standards/0005.md", score=0.72),
        ]
        merged = merge_contexts(rag_results, [])
        assert len(merged) == 2
        assert merged[0]["file_path"] == "docs/adrs/0201.md"
        assert merged[1]["file_path"] == "docs/standards/0005.md"


class TestQueryKnowledgeBase:
    """Tests for query_knowledge_base() convenience function."""

    @pytest.mark.rag
    def test_convenience_function(self, tmp_path: Path) -> None:
        """query_knowledge_base delegates to LibrarianNode.retrieve."""
        from assemblyzero.rag.librarian import LibrarianNode, query_knowledge_base

        config = RAGConfig(
            vector_store_path=tmp_path / "store",
            similarity_threshold=0.5,
        )

        with patch.object(LibrarianNode, "retrieve", return_value=[_make_doc()]) as mock_retrieve:
            results = query_knowledge_base("test query", config=config)
            assert len(results) == 1
            mock_retrieve.assert_called_once_with("test query")
```
