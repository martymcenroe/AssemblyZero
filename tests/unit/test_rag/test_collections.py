"""Tests for CollectionManager (T040, T050, T090, T320).

Issue #113: Vector Database Infrastructure (RAG Foundation)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from assemblyzero.rag.collections import (
    COLLECTION_CODEBASE,
    COLLECTION_DOCUMENTATION,
    CollectionManager,
)
from assemblyzero.rag.config import RAGConfig
from assemblyzero.rag.errors import CollectionNotFoundError, RAGError
from assemblyzero.rag.store import VectorStore


@pytest.fixture
def store(tmp_path: Path) -> VectorStore:
    """Create an initialized VectorStore with temp directory."""
    config = RAGConfig(persist_directory=tmp_path / "vector_store")
    s = VectorStore(config)
    s.initialize()
    return s


@pytest.fixture
def cm(store: VectorStore) -> CollectionManager:
    """Create a CollectionManager with initialized store."""
    return CollectionManager(store)


class TestCreateCollections:
    """T040: Create documentation and codebase collections."""

    def test_create_documentation_collection(
        self, cm: CollectionManager
    ) -> None:
        col = cm.create_collection(COLLECTION_DOCUMENTATION)
        assert col is not None
        retrieved = cm.get_collection(COLLECTION_DOCUMENTATION)
        assert retrieved is not None

    def test_create_codebase_collection(
        self, cm: CollectionManager
    ) -> None:
        col = cm.create_collection(COLLECTION_CODEBASE)
        assert col is not None
        retrieved = cm.get_collection(COLLECTION_CODEBASE)
        assert retrieved is not None

    def test_create_both_collections(self, cm: CollectionManager) -> None:
        cm.create_collection(COLLECTION_DOCUMENTATION)
        cm.create_collection(COLLECTION_CODEBASE)
        docs = cm.get_collection(COLLECTION_DOCUMENTATION)
        code = cm.get_collection(COLLECTION_CODEBASE)
        assert docs is not None
        assert code is not None

    def test_create_duplicate_raises(self, cm: CollectionManager) -> None:
        cm.create_collection("test_col")
        with pytest.raises(RAGError, match="already exists"):
            cm.create_collection("test_col")


class TestListCollections:
    """T050: List multiple collections."""

    def test_list_three_collections(self, cm: CollectionManager) -> None:
        cm.create_collection("alpha")
        cm.create_collection("beta")
        cm.create_collection("gamma")
        names = cm.list_collections()
        assert len(names) == 3
        assert set(names) == {"alpha", "beta", "gamma"}


class TestCollectionIsolation:
    """T090: Independent collection queries."""

    def test_add_to_docs_does_not_affect_codebase(
        self, cm: CollectionManager, store: VectorStore
    ) -> None:
        cm.create_collection(COLLECTION_DOCUMENTATION)
        cm.create_collection(COLLECTION_CODEBASE)

        doc_col = cm.get_collection(COLLECTION_DOCUMENTATION)
        doc_col.add(
            ids=["doc1"],
            documents=["A documentation paragraph."],
            metadatas=[{"source": "docs"}],
        )

        code_col = cm.get_collection(COLLECTION_CODEBASE)
        assert code_col.count() == 0
        assert doc_col.count() == 1


class TestCollectionCount:
    """T320: Collection count returns correct count."""

    def test_count_matches_added_documents(
        self, cm: CollectionManager
    ) -> None:
        cm.create_collection("test_count")
        col = cm.get_collection("test_count")
        for i in range(5):
            col.add(
                ids=[f"doc{i}"],
                documents=[f"Document {i} content"],
                metadatas=[{"index": str(i)}],
            )
        assert cm.collection_count("test_count") == 5

    def test_count_nonexistent_raises(self, cm: CollectionManager) -> None:
        with pytest.raises(CollectionNotFoundError):
            cm.collection_count("nonexistent")


class TestCollectionOps:
    """Additional collection operation tests."""

    def test_get_nonexistent_raises(self, cm: CollectionManager) -> None:
        with pytest.raises(CollectionNotFoundError):
            cm.get_collection("nonexistent")

    def test_delete_collection(self, cm: CollectionManager) -> None:
        cm.create_collection("to_delete")
        assert cm.collection_exists("to_delete") is True
        cm.delete_collection("to_delete")
        assert cm.collection_exists("to_delete") is False

    def test_delete_nonexistent_raises(self, cm: CollectionManager) -> None:
        with pytest.raises(CollectionNotFoundError):
            cm.delete_collection("nonexistent")

    def test_get_or_create_creates_new(self, cm: CollectionManager) -> None:
        col = cm.get_or_create_collection("new_col")
        assert col is not None
        assert cm.collection_exists("new_col") is True

    def test_get_or_create_returns_existing(
        self, cm: CollectionManager
    ) -> None:
        cm.create_collection("existing")
        col = cm.get_or_create_collection("existing")
        assert col is not None

    def test_collection_exists_false_for_missing(
        self, cm: CollectionManager
    ) -> None:
        assert cm.collection_exists("no_such_col") is False