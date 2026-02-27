

```python
"""EmbeddingProvider — local embedding generation using SentenceTransformers.

Issue #113: Vector Database Infrastructure (RAG Foundation)
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from assemblyzero.rag.errors import EmbeddingError

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


class EmbeddingProvider:
    """Local embedding generation using SentenceTransformers.

    The model is loaded lazily on first use to avoid startup cost.
    Uses all-MiniLM-L6-v2 by default (384 dimensions, ~80MB).
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        """Initialize with model name. Model loaded lazily on first use.

        Args:
            model_name: SentenceTransformers model identifier.
        """
        self._model_name = model_name
        self._model: SentenceTransformer | None = None
        self._dimension: int | None = None

    def _load_model(self) -> None:
        """Load the SentenceTransformer model into memory.

        Raises:
            ImportError: If sentence-transformers is not installed.
            EmbeddingError: If model loading fails.
        """
        if self._model is not None:
            return

        try:
            from sentence_transformers import SentenceTransformer as _ST
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for RAG infrastructure. "
                "Install with: pip install sentence-transformers"
            )

        try:
            self._model = _ST(self._model_name)
            # Determine dimension from a test encoding
            test_embedding = self._model.encode(["test"], convert_to_numpy=True)
            self._dimension = int(test_embedding.shape[1])
        except Exception as exc:
            self._model = None
            self._dimension = None
            raise EmbeddingError(
                f"Failed to load model '{self._model_name}': {exc}"
            ) from exc

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of float vectors, one per input text.

        Raises:
            ImportError: If sentence-transformers is not installed.
            EmbeddingError: On model failure.
        """
        self._load_model()
        assert self._model is not None  # guaranteed by _load_model

        try:
            embeddings = self._model.encode(texts, convert_to_numpy=True)
            return [vec.tolist() for vec in embeddings]
        except Exception as exc:
            raise EmbeddingError(
                f"Failed to encode texts: {exc}"
            ) from exc

    def embed_query(self, query: str) -> list[float]:
        """Generate embedding for a single query string.

        Convenience wrapper around embed_texts.

        Args:
            query: Query text to embed.

        Returns:
            Float vector for the query.
        """
        results = self.embed_texts([query])
        return results[0]

    @property
    def dimension(self) -> int:
        """Return the embedding dimension for the loaded model.

        Loads the model if not already loaded.

        Returns:
            Integer dimension of embedding vectors.
        """
        if self._dimension is None:
            self._load_model()
        assert self._dimension is not None
        return self._dimension

    @property
    def is_loaded(self) -> bool:
        """Whether the model has been loaded into memory.

        Returns:
            True if model is loaded and ready for encoding.
        """
        return self._model is not None
```
