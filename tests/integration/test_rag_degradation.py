"""Integration test: graceful degradation without deps/store.

Issue #88: The Librarian - Automated Context Retrieval
Tests: T230
"""

from __future__ import annotations

import importlib
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.integration
class TestRagDegradation:
    """Tests for graceful degradation when RAG is unavailable."""

    def test_workflow_continues_without_deps(self) -> None:
        """T230: Integration: workflow degrades without deps (REQ-9)."""
        with patch(
            "assemblyzero.nodes.librarian.check_rag_dependencies",
            return_value=(False, "Missing: chromadb, sentence-transformers"),
        ):
            from assemblyzero.nodes.librarian import librarian_node

            state = {
                "issue_brief": "Test brief for degradation testing",
                "manual_context_paths": ["docs/standards/0005.md"],
                "retrieved_context": [],
                "rag_status": "",
                "designer_output": "",
            }

            result = librarian_node(state)
            assert result["rag_status"] == "deps_missing"
            assert result["retrieved_context"] == []
            # Workflow can continue — no exception raised

    def test_workflow_continues_without_store(self) -> None:
        """Workflow degrades gracefully when vector store is missing."""
        with patch(
            "assemblyzero.nodes.librarian.check_rag_dependencies",
            return_value=(True, "available"),
        ):
            mock_librarian_cls = MagicMock()
            mock_instance = MagicMock()
            mock_instance.check_availability.return_value = (False, "unavailable")
            mock_librarian_cls.return_value = mock_instance

            with patch(
                "assemblyzero.nodes.librarian.LibrarianNode",
                mock_librarian_cls,
            ):
                from assemblyzero.nodes import librarian as lib_mod

                importlib.reload(lib_mod)

                state = {
                    "issue_brief": "Test brief",
                    "manual_context_paths": [],
                    "retrieved_context": [],
                    "rag_status": "",
                    "designer_output": "",
                }

                result = lib_mod.librarian_node(state)
                assert result["rag_status"] == "unavailable"
                assert result["retrieved_context"] == []

    def test_retrieval_exception_does_not_crash_workflow(self) -> None:
        """Workflow degrades gracefully when retrieval raises an exception."""
        with patch(
            "assemblyzero.nodes.librarian.check_rag_dependencies",
            return_value=(True, "available"),
        ):
            mock_librarian_cls = MagicMock()
            mock_instance = MagicMock()
            mock_instance.check_availability.return_value = (True, "ready")
            mock_instance.retrieve.side_effect = RuntimeError("ChromaDB corrupted")
            mock_librarian_cls.return_value = mock_instance

            with patch(
                "assemblyzero.nodes.librarian.LibrarianNode",
                mock_librarian_cls,
            ):
                from assemblyzero.nodes import librarian as lib_mod

                importlib.reload(lib_mod)

                state = {
                    "issue_brief": "Test brief for exception handling",
                    "manual_context_paths": [],
                    "retrieved_context": [],
                    "rag_status": "",
                    "designer_output": "",
                }

                # Should NOT raise — graceful degradation
                result = lib_mod.librarian_node(state)
                assert result["rag_status"] == "unavailable"
                assert result["retrieved_context"] == []

    def test_manual_context_still_works_without_rag(self) -> None:
        """Manual context paths are preserved even when RAG is unavailable."""
        with patch(
            "assemblyzero.nodes.librarian.check_rag_dependencies",
            return_value=(False, "Missing: chromadb"),
        ):
            from assemblyzero.nodes.librarian import librarian_node

            state = {
                "issue_brief": "Test brief",
                "manual_context_paths": [
                    "docs/standards/0005.md",
                    "docs/adrs/0201.md",
                ],
                "retrieved_context": [],
                "rag_status": "",
                "designer_output": "",
            }

            result = librarian_node(state)
            assert result["rag_status"] == "deps_missing"
            assert result["retrieved_context"] == []
            # Downstream nodes can still use manual_context_paths from state
            # (the node only updates retrieved_context and rag_status)
            assert "manual_context_paths" not in result  # Not overwritten

    def test_empty_issue_brief_does_not_crash(self) -> None:
        """Empty issue brief degrades gracefully without crashing."""
        with patch(
            "assemblyzero.nodes.librarian.check_rag_dependencies",
            return_value=(False, "Missing: chromadb"),
        ):
            from assemblyzero.nodes.librarian import librarian_node

            state = {
                "issue_brief": "",
                "manual_context_paths": [],
                "retrieved_context": [],
                "rag_status": "",
                "designer_output": "",
            }

            result = librarian_node(state)
            assert result["rag_status"] == "deps_missing"
            assert result["retrieved_context"] == []