

```python
"""QueryEngine — unified query interface across collections.

Issue #113: Vector Database Infrastructure (RAG Foundation)
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

from assemblyzero.rag.collections import CollectionManager
from assemblyzero.rag.config import RAGConfig
from assemblyzero.rag.errors import CollectionNotFoundError

if TYPE_CHECKING:
    from assemblyzero.rag.embeddings import EmbeddingProvider
    from assemblyzero.rag.store import VectorStore


@dataclass(frozen=True)
class QueryResult:
    """Single result from a vector similarity search.

    Attributes:
        document: The retrieved text chunk.
        metadata: Associated metadata (source file, line range, etc.).
        distance: Distance score (lower = more similar for cosine).
        collection_name: Which collection this came from.
        chunk_id: Unique ID of the chunk.
    """

    document: str
    metadata: dict
    distance: float
    collection_name: str
    chunk_id: str


@dataclass(frozen=True)
class QueryResponse:
    """Aggregated response from a query operation.

    Attributes:
        results: Ranked list of QueryResult objects.
        query_text: The original query text.
        collection_name: The queried collection.
        total_results: Number of results returned.
    """

    results: list[QueryResult]
    query_text: str
    collection_name: str
    total_results: int


def _generate_id(content: str) -> str:
    """Generate a deterministic SHA-256 ID from content.

    Args:
        content: Text content to hash.

    Returns:
        Hex-encoded SHA-256 hash string.
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class QueryEngine:
    """Unified query interface across collections.

    Provides add, query, delete, and get operations with
    automatic embedding generation.
    """

    def __init__(
        self,
        store: VectorStore,
        embedding_provider: EmbeddingProvider,
        config: RAGConfig | None = None,
    ) -> None:
        """Initialize with store and embedding provider.

        Args:
            store: An initialized VectorStore.
            embedding_provider: Provider for generating embeddings.
            config: Optional RAG configuration. Uses defaults if None.
        """
        self._store = store
        self._embedding_provider = embedding_provider
        self._config = config or RAGConfig()
        self._collection_manager = CollectionManager(store)

    def add_documents(
        self,
        collection_name: str,
        documents: list[str],
        metadatas: list[dict] | None = None,
        ids: list[str] | None = None,
    ) -> list[str]:
        """Add documents to a collection with auto-generated embeddings.

        Uses upsert for idempotency — adding the same content twice
        produces the same ID and does not create duplicates.

        Args:
            collection_name: Target collection name (auto-created if missing).
            documents: List of document text strings.
            metadatas: Optional list of metadata dicts (one per document).
            ids: Optional list of document IDs. Auto-generated (SHA-256) if None.

        Returns:
            List of document IDs.
        """
        collection = self._collection_manager.get_or_create_collection(
            collection_name
        )

        doc_ids = ids or [_generate_id(doc) for doc in documents]
        embeddings = self._embedding_provider.embed_texts(documents)

        metas = metadatas or [{} for _ in documents]

        collection.upsert(
            ids=doc_ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metas,
        )

        return doc_ids

    def query(
        self,
        collection_name: str,
        query_text: str,
        n_results: int | None = None,
        where: dict | None = None,
    ) -> QueryResponse:
        """Query a collection with natural language text.

        Args:
            collection_name: Collection to query.
            query_text: Natural language query text.
            n_results: Number of results to return. Defaults to config value.
            where: Optional metadata filter dict.

        Returns:
            QueryResponse with ranked results.

        Raises:
            CollectionNotFoundError: If collection doesn't exist.
        """
        if not self._collection_manager.collection_exists(collection_name):
            raise CollectionNotFoundError(collection_name)

        collection = self._collection_manager.get_collection(collection_name)
        n = n_results or self._config.default_n_results

        # Check if collection is empty
        if collection.count() == 0:
            return QueryResponse(
                results=[],
                query_text=query_text,
                collection_name=collection_name,
                total_results=0,
            )

        # Clamp n_results to collection size to avoid ChromaDB errors
        actual_n = min(n, collection.count())

        query_embedding = self._embedding_provider.embed_query(query_text)

        query_kwargs: dict = {
            "query_embeddings": [query_embedding],
            "n_results": actual_n,
            "include": ["documents", "metadatas", "distances"],
        }
        if where is not None:
            query_kwargs["where"] = where

        raw = collection.query(**query_kwargs)

        results: list[QueryResult] = []
        # ChromaDB returns batched results (list of lists)
        if raw["ids"] and raw["ids"][0]:
            for i, doc_id in enumerate(raw["ids"][0]):
                doc = raw["documents"][0][i] if raw["documents"] else ""
                meta = raw["metadatas"][0][i] if raw["metadatas"] else {}
                dist = raw["distances"][0][i] if raw["distances"] else 0.0
                results.append(
                    QueryResult(
                        document=doc,
                        metadata=meta or {},
                        distance=dist,
                        collection_name=collection_name,
                        chunk_id=doc_id,
                    )
                )

        return QueryResponse(
            results=results,
            query_text=query_text,
            collection_name=collection_name,
            total_results=len(results),
        )

    def delete_documents(
        self,
        collection_name: str,
        ids: list[str],
    ) -> None:
        """Remove documents by ID from a collection.

        Args:
            collection_name: Collection to delete from.
            ids: List of document IDs to remove.

        Raises:
            CollectionNotFoundError: If collection doesn't exist.
        """
        collection = self._collection_manager.get_collection(collection_name)
        collection.delete(ids=ids)

    def get_document(
        self,
        collection_name: str,
        doc_id: str,
    ) -> QueryResult | None:
        """Retrieve a specific document by ID.

        Args:
            collection_name: Collection to search.
            doc_id: Document ID to retrieve.

        Returns:
            QueryResult if found, None otherwise.
        """
        collection = self._collection_manager.get_collection(collection_name)
        raw = collection.get(
            ids=[doc_id],
            include=["documents", "metadatas"],
        )

        if not raw["ids"]:
            return None

        doc = raw["documents"][0] if raw["documents"] else ""
        meta = raw["metadatas"][0] if raw["metadatas"] else {}

        return QueryResult(
            document=doc,
            metadata=meta or {},
            distance=0.0,
            collection_name=collection_name,
            chunk_id=doc_id,
        )
```
