

```python
"""RAG infrastructure for vector-based document retrieval.

Issue #113: Vector Database Infrastructure (RAG Foundation)

Public API:
    - get_store() — singleton VectorStore
    - get_query_engine() — singleton QueryEngine wired with store + embeddings
    - RAGConfig — configuration dataclass
    - TextChunker, TextChunk — document chunking utilities
    - QueryEngine, QueryResult, QueryResponse — query interface
    - VectorStore — store lifecycle management
    - EmbeddingProvider — local embedding generation
    - CollectionManager — collection CRUD
    - Error classes — RAGError hierarchy
"""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from assemblyzero.rag.config import RAGConfig
from assemblyzero.rag.errors import (
    CollectionNotFoundError,
    EmbeddingError,
    RAGError,
    StoreCorruptedError,
    StoreNotInitializedError,
)
from assemblyzero.rag.chunking import TextChunk, TextChunker

if TYPE_CHECKING:
    from assemblyzero.rag.store import VectorStore
    from assemblyzero.rag.embeddings import EmbeddingProvider
    from assemblyzero.rag.collections import CollectionManager
    from assemblyzero.rag.query import QueryEngine, QueryResult, QueryResponse

__all__ = [
    "get_store",
    "get_query_engine",
    "RAGConfig",
    "TextChunker",
    "TextChunk",
    "RAGError",
    "StoreNotInitializedError",
    "CollectionNotFoundError",
    "EmbeddingError",
    "StoreCorruptedError",
]

_lock = threading.Lock()
_store_instance: VectorStore | None = None
_query_engine_instance: QueryEngine | None = None


def get_store(config: RAGConfig | None = None) -> VectorStore:
    """Get or create the singleton VectorStore instance.

    Thread-safe. Returns existing instance if already created.
    Initializes the store on first call.

    Args:
        config: Optional RAG configuration. Uses defaults if None.

    Returns:
        The singleton VectorStore instance, initialized and ready.
    """
    global _store_instance
    if _store_instance is not None:
        return _store_instance
    with _lock:
        if _store_instance is not None:
            return _store_instance
        from assemblyzero.rag.store import VectorStore as _VectorStore

        cfg = config or RAGConfig()
        store = _VectorStore(cfg)
        store.initialize()
        _store_instance = store
        return _store_instance


def get_query_engine(config: RAGConfig | None = None) -> QueryEngine:
    """Get a fully wired QueryEngine with store + embeddings.

    Convenience factory for consumers (#88, #92).
    Initializes store and creates embedding provider on first call.
    Thread-safe singleton.

    Args:
        config: Optional RAG configuration. Uses defaults if None.

    Returns:
        The singleton QueryEngine instance, ready for add/query operations.
    """
    global _query_engine_instance
    if _query_engine_instance is not None:
        return _query_engine_instance
    with _lock:
        if _query_engine_instance is not None:
            return _query_engine_instance
        from assemblyzero.rag.embeddings import EmbeddingProvider as _EmbeddingProvider
        from assemblyzero.rag.query import QueryEngine as _QueryEngine

        cfg = config or RAGConfig()
        store = get_store(cfg)
        provider = _EmbeddingProvider(cfg.embedding_model_name)
        engine = _QueryEngine(store, provider, cfg)
        _query_engine_instance = engine
        return _query_engine_instance


def _reset_singletons() -> None:
    """Reset singleton instances. For testing only.

    Not included in __all__. Tests must call this in try/finally
    to avoid polluting other test runs.
    """
    global _store_instance, _query_engine_instance
    with _lock:
        if _store_instance is not None:
            try:
                _store_instance.close()
            except Exception:
                pass
        _store_instance = None
        _query_engine_instance = None
```
