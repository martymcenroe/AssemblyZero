

```python
"""CollectionManager — CRUD for named vector collections.

Issue #113: Vector Database Infrastructure (RAG Foundation)
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from assemblyzero.rag.errors import CollectionNotFoundError, RAGError

if TYPE_CHECKING:
    import chromadb
    from assemblyzero.rag.store import VectorStore

# Well-known collection names
COLLECTION_DOCUMENTATION: str = "documentation"
COLLECTION_CODEBASE: str = "codebase"

KNOWN_COLLECTIONS: frozenset[str] = frozenset({
    COLLECTION_DOCUMENTATION,
    COLLECTION_CODEBASE,
})


class CollectionManager:
    """CRUD operations for named vector collections.

    Wraps ChromaDB collection operations with error handling
    and the project's exception hierarchy.
    """

    def __init__(self, store: VectorStore) -> None:
        """Initialize with a VectorStore instance.

        Args:
            store: An initialized VectorStore.
        """
        self._store = store

    def create_collection(
        self,
        name: str,
        metadata: dict | None = None,
    ) -> chromadb.Collection:
        """Create a new collection.

        Args:
            name: Collection name.
            metadata: Optional collection-level metadata.

        Returns:
            The created ChromaDB Collection.

        Raises:
            RAGError: If collection already exists.
        """
        client = self._store.get_client()
        if self.collection_exists(name):
            raise RAGError(f"Collection '{name}' already exists")
        meta = metadata or {}
        return client.create_collection(name=name, metadata=meta)

    def get_collection(self, name: str) -> chromadb.Collection:
        """Get existing collection by name.

        Args:
            name: Collection name to retrieve.

        Returns:
            The ChromaDB Collection.

        Raises:
            CollectionNotFoundError: If collection does not exist.
        """
        client = self._store.get_client()
        try:
            return client.get_collection(name=name)
        except Exception:
            raise CollectionNotFoundError(name)

    def get_or_create_collection(
        self,
        name: str,
        metadata: dict | None = None,
    ) -> chromadb.Collection:
        """Get existing or create new collection.

        Args:
            name: Collection name.
            metadata: Optional collection-level metadata.

        Returns:
            The ChromaDB Collection (existing or newly created).
        """
        client = self._store.get_client()
        meta = metadata or {}
        return client.get_or_create_collection(name=name, metadata=meta)

    def delete_collection(self, name: str) -> None:
        """Delete a collection by name.

        Args:
            name: Collection name to delete.

        Raises:
            CollectionNotFoundError: If collection does not exist.
        """
        client = self._store.get_client()
        if not self.collection_exists(name):
            raise CollectionNotFoundError(name)
        client.delete_collection(name=name)

    def list_collections(self) -> list[str]:
        """Return names of all existing collections.

        Returns:
            List of collection name strings.
        """
        client = self._store.get_client()
        collections = client.list_collections()
        # ChromaDB may return strings or Collection objects depending on version
        names: list[str] = []
        for col in collections:
            if isinstance(col, str):
                names.append(col)
            else:
                names.append(col.name)
        return names

    def collection_exists(self, name: str) -> bool:
        """Check if a collection exists.

        Args:
            name: Collection name to check.

        Returns:
            True if collection exists, False otherwise.
        """
        return name in self.list_collections()

    def collection_count(self, name: str) -> int:
        """Return number of documents in a collection.

        Args:
            name: Collection name.

        Returns:
            Integer count of documents in the collection.

        Raises:
            CollectionNotFoundError: If collection does not exist.
        """
        col = self.get_collection(name)
        return col.count()
```
