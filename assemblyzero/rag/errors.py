"""Custom exception hierarchy for RAG infrastructure.

Issue #113: Vector Database Infrastructure (RAG Foundation)

All RAG errors inherit from RAGError. Consumers catch RAGError
for unified fallback behavior.
"""
from __future__ import annotations


class RAGError(Exception):
    """Base exception for all RAG infrastructure errors."""

    pass


class StoreNotInitializedError(RAGError):
    """Raised when operations attempted on uninitialized store."""

    pass


class CollectionNotFoundError(RAGError):
    """Raised when referencing a non-existent collection.

    Attributes:
        collection_name: The name of the collection that was not found.
    """

    def __init__(self, collection_name: str) -> None:
        self.collection_name = collection_name
        super().__init__(f"Collection '{collection_name}' not found")


class EmbeddingError(RAGError):
    """Raised when embedding generation fails."""

    pass


class StoreCorruptedError(RAGError):
    """Raised when the persistent store is corrupted or unreadable."""

    pass