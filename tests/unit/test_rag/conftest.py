"""Shared fixtures for RAG unit tests.

Provides fake implementations of ChromaDB and SentenceTransformers
so unit tests run without heavy ML dependencies (chromadb requires
C++ build tools, sentence-transformers requires torch).

The fakes implement the subset of APIs used by the RAG module.
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock

import numpy as np
import pytest


class FakeCollection:
    """In-memory fake ChromaDB collection."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._docs: dict[str, dict] = {}

    def add(
        self,
        ids: list[str],
        documents: list[str] | None = None,
        metadatas: list[dict] | None = None,
        embeddings: list | None = None,
    ) -> None:
        for i, doc_id in enumerate(ids):
            self._docs[doc_id] = {
                "document": documents[i] if documents else "",
                "metadata": metadatas[i] if metadatas else {},
                "embedding": embeddings[i] if embeddings else [],
            }

    def upsert(
        self,
        ids: list[str],
        documents: list[str] | None = None,
        metadatas: list[dict] | None = None,
        embeddings: list | None = None,
    ) -> None:
        self.add(ids, documents, metadatas, embeddings)

    def get(
        self,
        ids: list[str] | None = None,
        include: list[str] | None = None,
    ) -> dict:
        if ids:
            found = [i for i in ids if i in self._docs]
            return {
                "ids": found,
                "documents": [self._docs[i]["document"] for i in found],
                "metadatas": [self._docs[i]["metadata"] for i in found],
            }
        all_ids = list(self._docs.keys())
        return {
            "ids": all_ids,
            "documents": [self._docs[i]["document"] for i in all_ids],
            "metadatas": [self._docs[i]["metadata"] for i in all_ids],
        }

    def query(
        self,
        query_embeddings: list | None = None,
        n_results: int = 10,
        include: list[str] | None = None,
        where: dict | None = None,
    ) -> dict:
        all_ids = list(self._docs.keys())
        if where:
            all_ids = [
                i
                for i in all_ids
                if all(
                    self._docs[i]["metadata"].get(k) == v
                    for k, v in where.items()
                )
            ]
        ids = all_ids[:n_results]
        return {
            "ids": [ids],
            "documents": [[self._docs[i]["document"] for i in ids]],
            "metadatas": [[self._docs[i]["metadata"] for i in ids]],
            "distances": [[0.1 * j for j in range(len(ids))]],
        }

    def delete(self, ids: list[str]) -> None:
        for i in ids:
            self._docs.pop(i, None)

    def count(self) -> int:
        return len(self._docs)


class FakeClient:
    """In-memory fake ChromaDB PersistentClient."""

    def __init__(self, path: str | None = None) -> None:
        self._collections: dict[str, FakeCollection] = {}

    def create_collection(
        self, name: str, metadata: dict | None = None
    ) -> FakeCollection:
        col = FakeCollection(name)
        self._collections[name] = col
        return col

    def get_collection(self, name: str) -> FakeCollection:
        if name not in self._collections:
            raise ValueError(f"Collection {name} not found")
        return self._collections[name]

    def get_or_create_collection(
        self, name: str, metadata: dict | None = None
    ) -> FakeCollection:
        if name not in self._collections:
            return self.create_collection(name, metadata)
        return self._collections[name]

    def delete_collection(self, name: str) -> None:
        self._collections.pop(name, None)

    def list_collections(self) -> list[str]:
        return list(self._collections.keys())


class FakeSentenceTransformer:
    """Fake SentenceTransformer that returns random 384-d vectors."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self.model_name = model_name

    def encode(
        self, texts: list[str], convert_to_numpy: bool = False
    ) -> np.ndarray:
        n = len(texts) if isinstance(texts, list) else 1
        return np.random.rand(n, 384).astype(np.float32)


@pytest.fixture(autouse=True)
def mock_chromadb(monkeypatch):
    """Inject fake chromadb module so tests run without C++ build tools."""
    # Clean any stale chromadb sub-modules from previous (real) import attempts
    stale = [k for k in sys.modules if k.startswith("chromadb")]
    for k in stale:
        monkeypatch.delitem(sys.modules, k, raising=False)

    fake_module = MagicMock()
    fake_module.PersistentClient = FakeClient
    # ClientAPI type hint support
    fake_module.ClientAPI = FakeClient
    monkeypatch.setitem(sys.modules, "chromadb", fake_module)
    yield fake_module


@pytest.fixture(autouse=True)
def mock_sentence_transformers(monkeypatch):
    """Inject fake sentence_transformers module so tests run without torch."""
    # Clean stale sub-modules
    stale = [k for k in sys.modules if k.startswith("sentence_transformers")]
    for k in stale:
        monkeypatch.delitem(sys.modules, k, raising=False)

    fake_module = MagicMock()
    fake_module.SentenceTransformer = FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)
    yield fake_module


@pytest.fixture(autouse=True)
def reset_rag_singletons():
    """Reset RAG singletons after each test to prevent cross-contamination."""
    yield
    from assemblyzero.rag import _reset_singletons

    _reset_singletons()
