

```python
"""VectorStore — ChromaDB lifecycle and persistence management.

Issue #113: Vector Database Infrastructure (RAG Foundation)
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from assemblyzero.rag.config import RAGConfig
from assemblyzero.rag.errors import StoreCorruptedError, StoreNotInitializedError

if TYPE_CHECKING:
    import chromadb


class VectorStore:
    """Manages ChromaDB lifecycle and persistence.

    The store is lazy-initialized: constructing a VectorStore does not
    connect to ChromaDB. Call initialize() to create/open the persistent
    client.
    """

    def __init__(self, config: RAGConfig | None = None) -> None:
        """Initialize with optional config. Does NOT connect yet (lazy init).

        Args:
            config: RAG configuration. Uses defaults if None.
        """
        self._config = config or RAGConfig()
        self._client: chromadb.ClientAPI | None = None

    def initialize(self) -> None:
        """Create or open the persistent ChromaDB client.

        Creates persist_directory if it doesn't exist.

        Raises:
            StoreCorruptedError: If existing store path is a file (not dir).
            ImportError: If chromadb is not installed.
        """
        if self._client is not None:
            return  # Already initialized (idempotent)

        try:
            import chromadb as _chromadb
        except ImportError:
            raise ImportError(
                "chromadb is required for RAG infrastructure. "
                "Install with: pip install chromadb"
            )

        persist_path = self._config.persist_directory

        if persist_path.exists() and not persist_path.is_dir():
            raise StoreCorruptedError(
                f"Store path {persist_path} exists but is not a directory"
            )

        persist_path.mkdir(parents=True, exist_ok=True)

        try:
            self._client = _chromadb.PersistentClient(path=str(persist_path))
        except Exception as exc:
            raise StoreCorruptedError(
                f"Failed to open ChromaDB at {persist_path}: {exc}"
            ) from exc

    @property
    def is_initialized(self) -> bool:
        """Whether the store has been initialized and is ready.

        Returns:
            True if initialize() has been called and client is available.
        """
        return self._client is not None

    def get_client(self) -> chromadb.ClientAPI:
        """Return the underlying ChromaDB client.

        Raises:
            StoreNotInitializedError: If not initialized.

        Returns:
            The ChromaDB client instance.
        """
        if self._client is None:
            raise StoreNotInitializedError(
                "Store not initialized - call initialize() first"
            )
        return self._client

    def reset(self) -> None:
        """Delete all data and reinitialize. DESTRUCTIVE.

        Removes the persist directory and re-creates the store.
        """
        self.close()
        persist_path = self._config.persist_directory
        if persist_path.exists():
            shutil.rmtree(persist_path)
        self.initialize()

    def close(self) -> None:
        """Clean shutdown of the store.

        Sets client to None. Store can be re-initialized after close.
        """
        self._client = None
```
