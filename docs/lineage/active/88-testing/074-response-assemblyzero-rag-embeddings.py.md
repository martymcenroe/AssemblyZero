```python
"""Embedding provider abstraction for RAG.

Issue #88: The Librarian - Automated Context Retrieval

Provides a strategy pattern for embedding generation. Default is local
sentence-transformers (all-MiniLM-L6-v2). External API providers
(OpenAI, Gemini) can be added as future extensions.

Requires: pip install assemblyzero[rag]
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from assemblyzero.rag.dependencies import require_rag_dependencies
from assemblyzero.rag.models import RAGConfig

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


class EmbeddingProvider(ABC):
    """Abstract base for embedding generation."""

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of text strings into vector representations."""
        ...

    @abstractmethod
    def embed_query(self, query: str) -> list[float]:
        """Embed a single query string for similarity search."""
        ...


class LocalEmbeddingProvider(EmbeddingProvider):
    """Local embedding using sentence-transformers.

    Default model: all-MiniLM-L6-v2 (384 dimensions, ~80MB).
    Model is loaded lazily on first use.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        """Initialize with model name. Loads model on first use (lazy)."""
        require_rag_dependencies()
        self._model_name = model_name
        self._model: SentenceTransformer | None = None

    def _get_model(self) -> SentenceTransformer:
        """Lazily load the sentence-transformers model."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name)
        return self._model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of text strings into vector representations."""
        if not texts:
            return []
        model = self._get_model()
        embeddings = model.encode(texts, convert_to_numpy=True)
        return [embedding.tolist() for embedding in embeddings]

    def embed_query(self, query: str) -> list[float]:
        """Embed a single query string for similarity search."""
        model = self._get_model()
        # Pass as single-element list and extract first result to guarantee
        # a 1D array regardless of sentence-transformers version behavior.
        embeddings = model.encode([query], convert_to_numpy=True)
        return embeddings[0].tolist()


def create_embedding_provider(config: RAGConfig) -> EmbeddingProvider:
    """Factory: create the appropriate embedding provider based on config.

    Args:
        config: RAG configuration with embedding_provider and embedding_model.

    Returns:
        An initialized EmbeddingProvider instance.

    Raises:
        ValueError: For unknown provider names.
        NotImplementedError: For providers not yet implemented.
    """
    if config.embedding_provider == "local":
        return LocalEmbeddingProvider(model_name=config.embedding_model)
    elif config.embedding_provider == "openai":
        raise NotImplementedError("OpenAI embedding provider not yet implemented")
    elif config.embedding_provider == "gemini":
        raise NotImplementedError("Gemini embedding provider not yet implemented")
    else:
        raise ValueError(f"Unknown embedding provider: {config.embedding_provider}")
```
