

```python
"""Unit tests for RAG dependency checking.

Issue #88: The Librarian - Automated Context Retrieval
Tests: T040, T050
"""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest


class TestCheckRagDependencies:
    """Tests for check_rag_dependencies()."""

    def test_missing_chromadb(self) -> None:
        """T040: Dependency checker detects missing chromadb (REQ-9)."""
        with patch.dict(sys.modules, {"chromadb": None}):
            # Force reimport
            import importlib

            from assemblyzero.rag import dependencies

            importlib.reload(dependencies)
            available, message = dependencies.check_rag_dependencies()
            assert available is False
            assert "pip install assemblyzero[rag]" in message

    def test_missing_sentence_transformers(self) -> None:
        """T040: Dependency checker detects missing sentence-transformers (REQ-9)."""
        with patch.dict(sys.modules, {"sentence_transformers": None}):
            import importlib

            from assemblyzero.rag import dependencies

            importlib.reload(dependencies)
            available, message = dependencies.check_rag_dependencies()
            assert available is False
            assert "pip install assemblyzero[rag]" in message

    def test_all_dependencies_available(self) -> None:
        """T050: Dependency checker succeeds with mocked imports (REQ-9)."""
        # Mock both modules as available
        mock_chromadb = type(sys)("chromadb")
        mock_st = type(sys)("sentence_transformers")
        with patch.dict(
            sys.modules,
            {"chromadb": mock_chromadb, "sentence_transformers": mock_st},
        ):
            import importlib

            from assemblyzero.rag import dependencies

            importlib.reload(dependencies)
            available, message = dependencies.check_rag_dependencies()
            assert available is True
            assert "available" in message.lower()


class TestRequireRagDependencies:
    """Tests for require_rag_dependencies()."""

    def test_raises_when_missing(self) -> None:
        """require_rag_dependencies raises ImportError when deps missing."""
        with patch.dict(sys.modules, {"chromadb": None}):
            import importlib

            from assemblyzero.rag import dependencies

            importlib.reload(dependencies)
            with pytest.raises(ImportError, match="pip install assemblyzero"):
                dependencies.require_rag_dependencies()

    def test_succeeds_when_available(self) -> None:
        """require_rag_dependencies succeeds when deps available."""
        mock_chromadb = type(sys)("chromadb")
        mock_st = type(sys)("sentence_transformers")
        with patch.dict(
            sys.modules,
            {"chromadb": mock_chromadb, "sentence_transformers": mock_st},
        ):
            import importlib

            from assemblyzero.rag import dependencies

            importlib.reload(dependencies)
            # Should not raise
            dependencies.require_rag_dependencies()
```
