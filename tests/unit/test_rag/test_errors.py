"""Tests for RAG error hierarchy (T130).

Issue #113: Vector Database Infrastructure (RAG Foundation)
"""
from __future__ import annotations

from assemblyzero.rag.errors import (
    CollectionNotFoundError,
    EmbeddingError,
    RAGError,
    StoreCorruptedError,
    StoreNotInitializedError,
)


class TestErrorHierarchy:
    """T130: All error classes inherit from RAGError."""

    def test_rag_error_is_base(self) -> None:
        err = RAGError("test")
        assert isinstance(err, Exception)
        assert isinstance(err, RAGError)
        assert str(err) == "test"

    def test_store_not_initialized_inherits(self) -> None:
        err = StoreNotInitializedError("not init")
        assert isinstance(err, RAGError)
        assert isinstance(err, Exception)

    def test_collection_not_found_inherits(self) -> None:
        err = CollectionNotFoundError("my_collection")
        assert isinstance(err, RAGError)
        assert err.collection_name == "my_collection"
        assert "my_collection" in str(err)

    def test_embedding_error_inherits(self) -> None:
        err = EmbeddingError("embed fail")
        assert isinstance(err, RAGError)

    def test_store_corrupted_inherits(self) -> None:
        err = StoreCorruptedError("corrupted")
        assert isinstance(err, RAGError)

    def test_all_catchable_as_rag_error(self) -> None:
        """Consumers can catch RAGError for unified fallback."""
        errors = [
            RAGError("base"),
            StoreNotInitializedError("not init"),
            CollectionNotFoundError("col"),
            EmbeddingError("embed"),
            StoreCorruptedError("corrupt"),
        ]
        for err in errors:
            assert isinstance(err, RAGError)