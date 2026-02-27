

```python
"""Tests for QueryEngine (T100, T160–T200, T260, T270, T280, T290, T300, T310, T340).

Issue #113: Vector Database Infrastructure (RAG Foundation)
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from assemblyzero.rag import _reset_singletons, get_query_engine, get_store
from assemblyzero.rag.collections import CollectionManager
from assemblyzero.rag.config import RAGConfig
from assemblyzero.rag.embeddings import EmbeddingProvider
from assemblyzero.rag.errors import CollectionNotFoundError
from assemblyzero.rag.query import QueryEngine, QueryResponse, QueryResult
from assemblyzero.rag.store import VectorStore


@pytest.fixture
def config(tmp_path: Path) -> RAGConfig:
    """RAGConfig with temp directory."""
    return RAGConfig(persist_directory=tmp_path / "vector_store")


@pytest.fixture
def store(config: RAGConfig) -> VectorStore:
    """Initialized VectorStore."""
    s = VectorStore(config)
    s.initialize()
    return s


@pytest.fixture(scope="session")
def embedding_provider() -> EmbeddingProvider:
    """Session-scoped embedding provider."""
    return EmbeddingProvider()


@pytest.fixture
def engine(
    store: VectorStore, embedding_provider: EmbeddingProvider, config: RAGConfig
) -> QueryEngine:
    """QueryEngine wired with store and embeddings."""
    return QueryEngine(store, embedding_provider, config)


class TestBothConsumers:
    """T100: Same API serves both consumers."""

    def test_single_engine_serves_both_collections(
        self, engine: QueryEngine
    ) -> None:
        # Add to documentation
        doc_ids = engine.add_documents(
            "documentation",
            ["ChromaDB manages vector storage."],
            [{"source": "docs"}],
        )
        assert len(doc_ids) == 1

        # Add to codebase
        code_ids = engine.add_documents(
            "codebase",
            ["class VectorStore: pass"],
            [{"source": "code"}],
        )
        assert len(code_ids) == 1

        # Query both
        doc_results = engine.query("documentation", "vector storage")
        code_results = engine.query("codebase", "VectorStore class")
        assert doc_results.total_results >= 1
        assert code_results.total_results >= 1


class TestAddDocuments:
    """T160: Add documents via QueryEngine."""

    def test_add_returns_sha256_ids(self, engine: QueryEngine) -> None:
        ids = engine.add_documents(
            "test_add",
            ["Document one", "Document two"],
            [{"key": "val1"}, {"key": "val2"}],
        )
        assert len(ids) == 2
        # SHA-256 hashes are 64 hex chars
        for doc_id in ids:
            assert len(doc_id) == 64
            assert all(c in "0123456789abcdef" for c in doc_id)


class TestQuery:
    """T170: Query returns ranked results."""

    def test_query_ranked_results(self, engine: QueryEngine) -> None:
        engine.add_documents(
            "test_ranked",
            [
                "Python is a programming language.",
                "The weather is sunny today.",
                "Python code uses indentation for blocks.",
            ],
        )
        response = engine.query("test_ranked", "Python programming")
        assert response.total_results >= 1
        assert isinstance(response, QueryResponse)
        assert len(response.results) >= 1
        # Most similar should be about Python
        assert "Python" in response.results[0].document or "python" in response.results[0].document.lower()


class TestDeleteDocuments:
    """T180: Delete documents via QueryEngine."""

    def test_delete_reduces_count(self, engine: QueryEngine) -> None:
        ids = engine.add_documents(
            "test_delete",
            ["doc one", "doc two", "doc three"],
        )
        assert len(ids) == 3
        engine.delete_documents("test_delete", [ids[0]])
        # Verify count decreased
        cm = CollectionManager(engine._store)
        assert cm.collection_count("test_delete") == 2


class TestQueryFilter:
    """T190: Query with metadata filter."""

    def test_where_filter_applied(self, engine: QueryEngine) -> None:
        engine.add_documents(
            "test_filter",
            ["Alpha document content", "Beta document content"],
            [{"category": "alpha"}, {"category": "beta"}],
        )
        response = engine.query(
            "test_filter",
            "document content",
            where={"category": "alpha"},
        )
        assert response.total_results >= 1
        for result in response.results:
            assert result.metadata.get("category") == "alpha"


class TestGetDocument:
    """T200: Get document by ID."""

    def test_get_existing_document(self, engine: QueryEngine) -> None:
        ids = engine.add_documents(
            "test_get",
            ["The specific document to retrieve."],
            [{"tag": "specific"}],
        )
        result = engine.get_document("test_get", ids[0])
        assert result is not None
        assert result.document == "The specific document to retrieve."
        assert result.metadata["tag"] == "specific"
        assert result.chunk_id == ids[0]

    def test_get_nonexistent_returns_none(self, engine: QueryEngine) -> None:
        engine.add_documents("test_get_none", ["placeholder"])
        result = engine.get_document("test_get_none", "nonexistent_id_12345")
        # ChromaDB get() with unknown ID returns empty
        assert result is None


class TestSingleton:
    """T260, T270: Singleton behavior."""

    def test_get_query_engine_singleton(self, tmp_path: Path) -> None:
        config = RAGConfig(persist_directory=tmp_path / "singleton_qe")
        try:
            e1 = get_query_engine(config)
            e2 = get_query_engine(config)
            assert id(e1) == id(e2)
        finally:
            _reset_singletons()

    def test_get_store_singleton(self, tmp_path: Path) -> None:
        config = RAGConfig(persist_directory=tmp_path / "singleton_store")
        try:
            s1 = get_store(config)
            s2 = get_store(config)
            assert id(s1) == id(s2)
        finally:
            _reset_singletons()


class TestDuplicateIdempotent:
    """T300: Duplicate add is idempotent."""

    def test_same_content_produces_same_id(self, engine: QueryEngine) -> None:
        ids1 = engine.add_documents("test_dedup", ["identical content"])
        ids2 = engine.add_documents("test_dedup", ["identical content"])
        assert ids1 == ids2
        cm = CollectionManager(engine._store)
        assert cm.collection_count("test_dedup") == 1


class TestQueryEmpty:
    """T310: Query empty collection returns empty."""

    def test_empty_collection_query(self, engine: QueryEngine) -> None:
        # Create empty collection
        cm = CollectionManager(engine._store)
        cm.get_or_create_collection("empty_col")
        response = engine.query("empty_col", "anything")
        assert response.total_results == 0
        assert response.results == []


class TestQueryNonexistent:
    """T340: Query non-existent collection raises error."""

    def test_query_nonexistent_raises(self, engine: QueryEngine) -> None:
        with pytest.raises(CollectionNotFoundError) as exc_info:
            engine.query("nonexistent_collection", "test query")
        assert exc_info.value.collection_name == "nonexistent_collection"


class TestTypeHints:
    """T280: All public functions have type hints."""

    def test_all_public_methods_have_return_annotations(self) -> None:
        classes = [VectorStore, EmbeddingProvider, CollectionManager, QueryEngine]
        for cls in classes:
            for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
                if name.startswith("_"):
                    continue
                hints = method.__annotations__
                assert "return" in hints, (
                    f"{cls.__name__}.{name}() missing return type hint"
                )


class TestDocstrings:
    """T290: All public functions have docstrings."""

    def test_all_public_methods_have_docstrings(self) -> None:
        classes = [VectorStore, EmbeddingProvider, CollectionManager, QueryEngine]
        for cls in classes:
            for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
                if name.startswith("_"):
                    continue
                assert method.__doc__ is not None and method.__doc__.strip(), (
                    f"{cls.__name__}.{name}() missing docstring"
                )
```
