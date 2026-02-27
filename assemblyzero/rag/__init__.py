"""RAG (Retrieval-Augmented Generation) subsystem for AssemblyZero.

Issue #113: Vector Database Infrastructure (RAG Foundation)
Issue #88: The Librarian - Automated Context Retrieval

Public API:
    Foundation (#113):
        - get_store() — singleton VectorStore
        - get_query_engine() — singleton QueryEngine wired with store + embeddings
        - RAGConfig (config.py) — configuration dataclass
        - TextChunker, TextChunk — document chunking utilities
        - QueryEngine, QueryResult, QueryResponse — query interface
        - VectorStore — store lifecycle management
        - EmbeddingProvider — local embedding generation
        - CollectionManager — collection CRUD
        - Error classes — RAGError hierarchy

    Librarian (#88):
        - ChunkMetadata, IngestionSummary, RetrievedDocument — models
        - check_rag_dependencies, require_rag_dependencies — dependency checks

Install RAG dependencies: pip install assemblyzero[rag]
"""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING

# Issue #113 exports (foundation)
from assemblyzero.rag.config import RAGConfig
from assemblyzero.rag.errors import (
    CollectionNotFoundError,
    EmbeddingError,
    RAGError,
    StoreCorruptedError,
    StoreNotInitializedError,
)
from assemblyzero.rag.chunking import TextChunk, TextChunker

# Issue #88 exports (librarian)
from assemblyzero.rag.models import (
    ChunkMetadata,
    IngestionSummary,
    RetrievedDocument,
)
from assemblyzero.rag.dependencies import check_rag_dependencies, require_rag_dependencies

if TYPE_CHECKING:
    from assemblyzero.rag.store import VectorStore
    from assemblyzero.rag.embeddings import EmbeddingProvider as _EmbeddingProvider113
    from assemblyzero.rag.collections import CollectionManager
    from assemblyzero.rag.query import QueryEngine, QueryResult, QueryResponse

__all__ = [
    # #113 foundation
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
    # #88 librarian
    "ChunkMetadata",
    "IngestionSummary",
    "RetrievedDocument",
    "check_rag_dependencies",
    "require_rag_dependencies",
    "_reset_singletons",
]

# --- Singleton factories (#113) ---

_lock = threading.RLock()
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
    """Get or create the singleton QueryEngine instance.

    Thread-safe. Automatically creates VectorStore and EmbeddingProvider.

    Args:
        config: Optional RAG configuration. Uses defaults if None.

    Returns:
        The singleton QueryEngine, ready for queries.
    """
    global _query_engine_instance
    if _query_engine_instance is not None:
        return _query_engine_instance
    with _lock:
        if _query_engine_instance is not None:
            return _query_engine_instance
        from assemblyzero.rag.embeddings import LocalEmbeddingProvider as _LEP
        from assemblyzero.rag.query import QueryEngine as _QE

        cfg = config or RAGConfig()
        store = get_store(cfg)
        embedder = _LEP()
        engine = _QE(store, embedder, cfg)
        _query_engine_instance = engine
        return _query_engine_instance


def _reset_singletons() -> None:
    """Reset singleton state for test isolation.

    Called by test fixtures after each test to prevent cross-test
    contamination when modules are reloaded.
    """
    import importlib
    import sys

    global _store_instance, _query_engine_instance
    _store_instance = None
    _query_engine_instance = None

    # Also reload submodules that may hold cached state from mocked imports (#88)
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
