Now I have the full picture. The conftest expects `_reset_singletons` from `assemblyzero.rag`. Let me write the fixed `__init__.py`:

```python
"""RAG (Retrieval-Augmented Generation) subsystem for AssemblyZero.

Issue #88: The Librarian - Automated Context Retrieval

This module provides optional RAG capabilities for augmenting LLD design
with relevant governance documents. All heavy dependencies (chromadb,
sentence-transformers) are optional and loaded conditionally.

Install RAG dependencies: pip install assemblyzero[rag]
"""

from assemblyzero.rag.models import (
    ChunkMetadata,
    IngestionSummary,
    RAGConfig,
    RetrievedDocument,
)
from assemblyzero.rag.dependencies import check_rag_dependencies, require_rag_dependencies


def _reset_singletons() -> None:
    """Reset any cached singleton state in RAG submodules.

    Called by test fixtures (tests/unit/test_rag/conftest.py) after each
    test to prevent cross-test contamination when modules are reloaded.
    """
    import importlib
    import sys

    # Reload submodules that may hold cached state from mocked imports
    for mod_name in [
        "assemblyzero.rag.dependencies",
        "assemblyzero.rag.chunker",
        "assemblyzero.rag.embeddings",
        "assemblyzero.rag.vector_store",
        "assemblyzero.rag.librarian",
        "assemblyzero.nodes.librarian",
    ]:
        if mod_name in sys.modules:
            try:
                importlib.reload(sys.modules[mod_name])
            except Exception:
                pass


__all__ = [
    "ChunkMetadata",
    "IngestionSummary",
    "RAGConfig",
    "RetrievedDocument",
    "check_rag_dependencies",
    "require_rag_dependencies",
    "_reset_singletons",
]
```
