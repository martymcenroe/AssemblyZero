

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

__all__ = [
    "ChunkMetadata",
    "IngestionSummary",
    "RAGConfig",
    "RetrievedDocument",
    "check_rag_dependencies",
    "require_rag_dependencies",
]
```
