"""ChromaDB vector store wrapper for RAG.

Issue #88: The Librarian - Automated Context Retrieval

Manages ChromaDB persistent vector store lifecycle including initialization,
adding chunks, querying, and collection management.

Requires: pip install assemblyzero[rag]
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from assemblyzero.rag.dependencies import require_rag_dependencies
from assemblyzero.rag.models import ChunkMetadata, RAGConfig, RetrievedDocument

if TYPE_CHECKING:
    import chromadb

logger = logging.getLogger(__name__)

_COLLECTION_NAME = "assemblyzero_governance"

# Module-level client cache keyed by path string.  This ensures that
# multiple VectorStoreManager instances pointing at the same path share
# the same underlying ChromaDB client, which is critical both for real
# PersistentClient (avoids duplicate SQLite connections) and for the
# FakeClient used in unit tests (preserves data across instances).
_client_cache: dict[str, Any] = {}


class VectorStoreManager:
    """Manages ChromaDB persistent vector store lifecycle."""

    def __init__(self, config: RAGConfig) -> None:
        """Initialize with RAG configuration."""
        require_rag_dependencies()
        self._config = config
        self._client: chromadb.ClientAPI | None = None
        self._collection: Any = None

    def _get_client(self) -> chromadb.ClientAPI:
        """Lazily initialize ChromaDB persistent client.

        Uses a module-level cache so that multiple VectorStoreManager
        instances pointing at the same path share one client.
        """
        if self._client is None:
            path_str = str(self._config.vector_store_path)
            if path_str in _client_cache:
                self._client = _client_cache[path_str]
            else:
                import chromadb

                self._config.vector_store_path.mkdir(parents=True, exist_ok=True)
                self._client = chromadb.PersistentClient(
                    path=path_str
                )
                _client_cache[path_str] = self._client
        return self._client

    def _get_collection(self) -> Any:
        """Get or create the governance documents collection."""
        if self._collection is None:
            client = self._get_client()
            self._collection = client.get_or_create_collection(
                name=_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def is_initialized(self) -> bool:
        """Check if vector store directory exists and contains valid data."""
        store_path = self._config.vector_store_path
        if not store_path.exists():
            return False
        # Check for ChromaDB SQLite file (real ChromaDB)
        chroma_sqlite = store_path / "chroma.sqlite3"
        if chroma_sqlite.exists():
            return True
        # Also check if there is a cached client for this path
        # (supports test fakes that don't create real files)
        path_str = str(self._config.vector_store_path)
        if path_str in _client_cache:
            return True
        return False

    def initialize(self) -> None:
        """Create vector store directory and ChromaDB collection."""
        self._get_collection()
        logger.info(
            "[Librarian] Vector store initialized at %s",
            self._config.vector_store_path,
        )

    def add_chunks(
        self,
        chunks: list[tuple[str, ChunkMetadata]],
        embeddings: list[list[float]],
    ) -> int:
        """Add document chunks with pre-computed embeddings to the store.

        Returns number of chunks added.

        Raises:
            ValueError: If len(chunks) != len(embeddings).
        """
        if not chunks:
            return 0

        if len(chunks) != len(embeddings):
            raise ValueError(
                f"Chunk count ({len(chunks)}) != embedding count ({len(embeddings)})"
            )

        collection = self._get_collection()

        ids = []
        documents = []
        metadatas = []

        for i, (content, metadata) in enumerate(chunks):
            # Generate unique ID: file_path::chunk_index
            chunk_id = f"{metadata.file_path}::{metadata.chunk_index}"
            ids.append(chunk_id)
            documents.append(content)
            metadatas.append(
                {
                    "file_path": metadata.file_path,
                    "section_title": metadata.section_title,
                    "chunk_index": metadata.chunk_index,
                    "doc_type": metadata.doc_type,
                    "last_modified": metadata.last_modified,
                }
            )

        collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        return len(chunks)

    def query(
        self,
        query_embedding: list[float],
        n_results: int = 5,
    ) -> list[RetrievedDocument]:
        """Query the vector store for similar documents.

        Args:
            query_embedding: The embedded query vector.
            n_results: Maximum number of results to return.

        Returns:
            List of RetrievedDocument sorted by descending score.
        """
        collection = self._get_collection()
        count = collection.count()
        if count == 0:
            return []

        # Don't request more results than exist
        actual_n = min(n_results, count)

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=actual_n,
            include=["documents", "metadatas", "distances"],
        )

        documents: list[RetrievedDocument] = []

        if not results["ids"] or not results["ids"][0]:
            return []

        for i, doc_id in enumerate(results["ids"][0]):
            distance = results["distances"][0][i]
            # Convert cosine distance to similarity score
            score = 1.0 - distance
            metadata = results["metadatas"][0][i]
            content = results["documents"][0][i]

            documents.append(
                RetrievedDocument(
                    file_path=metadata["file_path"],
                    section=metadata["section_title"],
                    content_snippet=content,
                    score=round(score, 4),
                    doc_type=metadata["doc_type"],
                )
            )

        # Sort by score descending
        documents.sort(key=lambda d: d.score, reverse=True)
        return documents

    def get_indexed_files(self) -> dict[str, str]:
        """Return mapping of file_path -> last_modified for all indexed files.

        Used for incremental update detection.
        """
        collection = self._get_collection()
        count = collection.count()
        if count == 0:
            return {}

        all_data = collection.get(include=["metadatas"])
        file_map: dict[str, str] = {}
        for metadata in all_data["metadatas"]:
            fp = metadata["file_path"]
            lm = metadata["last_modified"]
            # Keep the latest last_modified for each file
            if fp not in file_map or lm > file_map[fp]:
                file_map[fp] = lm

        return file_map

    def delete_by_file(self, file_path: str) -> int:
        """Delete all chunks for a given file path. Returns count deleted.

        Fetches all items and filters by metadata rather than using
        ChromaDB's ``where`` parameter, for compatibility with test fakes.
        """
        collection = self._get_collection()

        # Get all items with metadatas to find matching file_path
        all_data = collection.get(include=["metadatas"])

        if not all_data["ids"]:
            return 0

        ids_to_delete: list[str] = []
        for i, metadata in enumerate(all_data["metadatas"]):
            if metadata.get("file_path") == file_path:
                ids_to_delete.append(all_data["ids"][i])

        if not ids_to_delete:
            return 0

        collection.delete(ids=ids_to_delete)
        return len(ids_to_delete)

    def collection_stats(self) -> dict[str, int]:
        """Return collection statistics: total_chunks, unique_files."""
        collection = self._get_collection()
        total = collection.count()

        if total == 0:
            return {"total_chunks": 0, "unique_files": 0}

        all_data = collection.get(include=["metadatas"])
        unique_files = len({m["file_path"] for m in all_data["metadatas"]})

        return {"total_chunks": total, "unique_files": unique_files}

    def reset(self) -> None:
        """Delete and recreate the collection. Used for full reindex."""
        client = self._get_client()
        try:
            client.delete_collection(name=_COLLECTION_NAME)
        except Exception:
            pass  # Collection may not exist
        self._collection = None
        self._get_collection()