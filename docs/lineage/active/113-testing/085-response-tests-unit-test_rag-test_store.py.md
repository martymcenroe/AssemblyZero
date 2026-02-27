

```python
"""Tests for VectorStore lifecycle (T010, T020, T030, T140, T150, T110).

Issue #113: Vector Database Infrastructure (RAG Foundation)
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.rag.config import RAGConfig
from assemblyzero.rag.errors import StoreCorruptedError, StoreNotInitializedError
from assemblyzero.rag.store import VectorStore


@pytest.fixture
def store_config(tmp_path: Path) -> RAGConfig:
    """Create a RAGConfig with a temporary persist directory."""
    return RAGConfig(persist_directory=tmp_path / "vector_store")


@pytest.fixture
def store(store_config: RAGConfig) -> VectorStore:
    """Create an uninitialized VectorStore."""
    return VectorStore(store_config)


class TestStoreInit:
    """T010: Store initializes with default config."""

    def test_initialize_creates_directory(
        self, store: VectorStore, store_config: RAGConfig
    ) -> None:
        store.initialize()
        assert store.is_initialized is True
        assert store_config.persist_directory.exists()
        assert store_config.persist_directory.is_dir()

    def test_initialize_is_idempotent(self, store: VectorStore) -> None:
        store.initialize()
        client1 = store.get_client()
        store.initialize()  # Second call — no-op
        client2 = store.get_client()
        assert client1 is client2


class TestStoreNotInitialized:
    """T020: Store reports not-initialized before init."""

    def test_is_initialized_false_before_init(self, store: VectorStore) -> None:
        assert store.is_initialized is False

    def test_get_client_raises_before_init(self, store: VectorStore) -> None:
        with pytest.raises(StoreNotInitializedError, match="not initialized"):
            store.get_client()


class TestStoreCorrupted:
    """T030: Store raises on corrupt directory."""

    def test_file_at_persist_path_raises(self, tmp_path: Path) -> None:
        # Create a file where directory should be
        file_path = tmp_path / "vector_store"
        file_path.write_text("not a directory")

        config = RAGConfig(persist_directory=file_path)
        store = VectorStore(config)

        with pytest.raises(StoreCorruptedError, match="not a directory"):
            store.initialize()


class TestStorePersistence:
    """T140: Store persists across reinitialize."""

    def test_data_survives_close_and_reopen(
        self, store_config: RAGConfig
    ) -> None:
        # Open store, create a collection, add data
        store1 = VectorStore(store_config)
        store1.initialize()
        client1 = store1.get_client()
        col = client1.get_or_create_collection("test_persist")
        col.add(
            ids=["doc1"],
            documents=["persistent document"],
            metadatas=[{"key": "value"}],
        )
        assert col.count() == 1
        store1.close()

        # Reopen store, verify data is still there
        store2 = VectorStore(store_config)
        store2.initialize()
        client2 = store2.get_client()
        col2 = client2.get_collection("test_persist")
        assert col2.count() == 1
        result = col2.get(ids=["doc1"])
        assert result["documents"][0] == "persistent document"
        store2.close()


class TestStoreCustomPath:
    """T150: Persist directory created at correct path."""

    def test_custom_persist_directory(self, tmp_path: Path) -> None:
        custom_path = tmp_path / "custom" / "nested" / "store"
        config = RAGConfig(persist_directory=custom_path)
        store = VectorStore(config)
        store.initialize()
        assert custom_path.exists()
        assert custom_path.is_dir()
        store.close()


class TestStoreMissingDependency:
    """T110: Graceful error on missing chromadb."""

    def test_missing_chromadb_raises_import_error(
        self, store_config: RAGConfig
    ) -> None:
        store = VectorStore(store_config)
        with patch.dict("sys.modules", {"chromadb": None}):
            with pytest.raises(ImportError, match="chromadb"):
                store.initialize()


class TestStoreCloseAndReset:
    """Additional lifecycle tests."""

    def test_close_sets_not_initialized(self, store: VectorStore) -> None:
        store.initialize()
        assert store.is_initialized is True
        store.close()
        assert store.is_initialized is False

    def test_reset_clears_data(self, store: VectorStore) -> None:
        store.initialize()
        client = store.get_client()
        client.get_or_create_collection("to_delete")
        store.reset()
        assert store.is_initialized is True
        # After reset, collection should be gone
        client = store.get_client()
        collections = client.list_collections()
        # Handle both string and object returns
        names = [c if isinstance(c, str) else c.name for c in collections]
        assert "to_delete" not in names
```
