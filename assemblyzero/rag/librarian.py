"""Core LibrarianNode: embed query, retrieve docs, filter by threshold.

Issue #88: The Librarian - Automated Context Retrieval

The LibrarianNode is the main entry point for RAG retrieval. It embeds
the issue brief, queries the vector store, filters by similarity threshold,
and returns the top-N most relevant governance documents.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from assemblyzero.rag.dependencies import check_rag_dependencies
from assemblyzero.rag.models import RAGConfig, RetrievedDocument

if TYPE_CHECKING:
    from assemblyzero.rag.embeddings import EmbeddingProvider
    from assemblyzero.rag.vector_store import VectorStoreManager

logger = logging.getLogger(__name__)


class LibrarianNode:
    """Core RAG retrieval engine for the Librarian."""

    def __init__(self, config: RAGConfig | None = None) -> None:
        """Initialize with optional config. Uses defaults if None."""
        self._config = config or RAGConfig()
        self._embedding_provider: EmbeddingProvider | None = None
        self._vector_store: VectorStoreManager | None = None

    def _get_embedding_provider(self) -> EmbeddingProvider:
        """Lazily create the embedding provider."""
        if self._embedding_provider is None:
            from assemblyzero.rag.embeddings import create_embedding_provider

            self._embedding_provider = create_embedding_provider(self._config)
        return self._embedding_provider

    def _get_vector_store(self) -> VectorStoreManager:
        """Lazily create the vector store manager."""
        if self._vector_store is None:
            from assemblyzero.rag.vector_store import VectorStoreManager

            self._vector_store = VectorStoreManager(self._config)
        return self._vector_store

    def retrieve(
        self,
        issue_brief: str,
        threshold: float | None = None,
    ) -> list[RetrievedDocument]:
        """Retrieve relevant governance documents for the given brief.

        Args:
            issue_brief: The text of the issue/brief to find context for.
            threshold: Override similarity threshold (uses config default if None).

        Returns:
            Top-N documents scoring above threshold, sorted by score descending.
        """
        actual_threshold = (
            threshold if threshold is not None else self._config.similarity_threshold
        )

        # Embed the issue brief
        provider = self._get_embedding_provider()
        query_embedding = provider.embed_query(issue_brief)

        # Query vector store for candidates
        store = self._get_vector_store()
        candidates = store.query(
            query_embedding=query_embedding,
            n_results=self._config.top_k_candidates,
        )

        # Filter by threshold
        filtered = [doc for doc in candidates if doc.score >= actual_threshold]

        # Return top N
        top_n = filtered[: self._config.top_n_results]

        return top_n

    def check_availability(self) -> tuple[bool, str]:
        """Check if the Librarian can operate (deps installed, store exists).

        Returns:
            Tuple of (available: bool, status_message: str).
        """
        available, msg = check_rag_dependencies()
        if not available:
            return (False, "deps_missing")

        try:
            store = self._get_vector_store()
        except Exception as e:
            logger.warning("[Librarian] Could not create vector store manager: %s", e)
            return (False, "unavailable")

        if not store.is_initialized():
            return (False, "unavailable")

        try:
            stats = store.collection_stats()
            return (
                True,
                f"Librarian ready: {stats['total_chunks']} chunks indexed "
                f"from {stats['unique_files']} files",
            )
        except Exception as e:
            logger.warning("[Librarian] Vector store error: %s", e)
            return (False, "unavailable")

    def format_context_for_designer(
        self,
        documents: list[RetrievedDocument],
    ) -> str:
        """Format retrieved documents into a text block for Designer prompt injection.

        Returns formatted string with file references, section titles, and content.
        """
        if not documents:
            return ""

        parts = ["--- Retrieved Context (RAG) ---\n"]

        for doc in documents:
            parts.append(f"### Source: {doc.file_path}")
            parts.append(f"**Section:** {doc.section}")
            parts.append(f"**Relevance Score:** {doc.score}")
            parts.append(f"**Type:** {doc.doc_type}")
            parts.append("")
            parts.append(doc.content_snippet)
            parts.append("\n---\n")

        return "\n".join(parts)


def query_knowledge_base(
    query: str, config: RAGConfig | None = None
) -> list[RetrievedDocument]:
    """Convenience function for ad-hoc querying (used in testing/debugging).

    Args:
        query: The search query text.
        config: Optional RAG configuration override.

    Returns:
        List of RetrievedDocument results.
    """
    librarian = LibrarianNode(config=config)
    return librarian.retrieve(query)