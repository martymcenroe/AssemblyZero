```python
"""Unit tests for embedding provider abstraction.

Issue #88: The Librarian - Automated Context Retrieval
Tests: T240
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.rag.models import RAGConfig


class TestCreateEmbeddingProvider:
    """Tests for create_embedding_provider()."""

    def test_unknown_provider(self) -> None:
        """Unknown provider raises ValueError."""
        from assemblyzero.rag.embeddings import create_embedding_provider

        config = RAGConfig(embedding_provider="unknown")
        with pytest.raises(ValueError, match="Unknown embedding provider"):
            create_embedding_provider(config)

    def test_openai_not_implemented(self) -> None:
        """OpenAI provider raises NotImplementedError."""
        from assemblyzero.rag.embeddings import create_embedding_provider

        config = RAGConfig(embedding_provider="openai")
        with pytest.raises(NotImplementedError, match="OpenAI"):
            create_embedding_provider(config)

    def test_gemini_not_implemented(self) -> None:
        """Gemini provider raises NotImplementedError."""
        from assemblyzero.rag.embeddings import create_embedding_provider

        config = RAGConfig(embedding_provider="gemini")
        with pytest.raises(NotImplementedError, match="Gemini"):
            create_embedding_provider(config)


@pytest.mark.rag
class TestLocalEmbeddingProvider:
    """Tests for LocalEmbeddingProvider (requires [rag] extra)."""

    def test_embed_query_dimensions(self) -> None:
        """T240: Embedding returns correct dimensions (REQ-2)."""
        from assemblyzero.rag.embeddings import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider(model_name="all-MiniLM-L6-v2")
        embedding = provider.embed_query("test query about governance")
        assert isinstance(embedding, list)
        assert len(embedding) == 384
        assert all(isinstance(v, float) for v in embedding)

    def test_embed_texts_batch(self) -> None:
        """Batch embedding returns correct count and dimensions."""
        from assemblyzero.rag.embeddings import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider(model_name="all-MiniLM-L6-v2")
        texts = ["first text", "second text", "third text"]
        embeddings = provider.embed_texts(texts)
        assert len(embeddings) == 3
        assert all(len(e) == 384 for e in embeddings)

    def test_embed_texts_empty(self) -> None:
        """Empty text list returns empty embeddings list."""
        from assemblyzero.rag.embeddings import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider(model_name="all-MiniLM-L6-v2")
        embeddings = provider.embed_texts([])
        assert embeddings == []

    def test_lazy_model_loading(self) -> None:
        """Model is not loaded until first embed call."""
        from assemblyzero.rag.embeddings import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider(model_name="all-MiniLM-L6-v2")
        assert provider._model is None  # Not yet loaded
        provider.embed_query("trigger load")
        assert provider._model is not None  # Now loaded
```
