

```python
"""Tests for EmbeddingProvider (T060, T070, T080, T120).

Issue #113: Vector Database Infrastructure (RAG Foundation)
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from assemblyzero.rag.embeddings import EmbeddingProvider


@pytest.fixture(scope="session")
def provider() -> EmbeddingProvider:
    """Session-scoped embedding provider to avoid reloading model per test."""
    return EmbeddingProvider()


class TestEmbedQuery:
    """T060: Embedding provider generates local vectors."""

    def test_embed_query_returns_384_floats(
        self, provider: EmbeddingProvider
    ) -> None:
        vector = provider.embed_query("hello world")
        assert isinstance(vector, list)
        assert len(vector) == 384
        assert all(isinstance(v, float) for v in vector)


class TestEmbedTexts:
    """T070: Embedding provider batch encoding."""

    def test_embed_texts_batch(self, provider: EmbeddingProvider) -> None:
        vectors = provider.embed_texts(["a", "b", "c"])
        assert len(vectors) == 3
        for vec in vectors:
            assert len(vec) == 384
            assert all(isinstance(v, float) for v in vec)


class TestLazyLoading:
    """T080: Embedding provider lazy loads model."""

    def test_is_loaded_false_before_use(self) -> None:
        fresh = EmbeddingProvider()
        assert fresh.is_loaded is False

    def test_is_loaded_true_after_use(
        self, provider: EmbeddingProvider
    ) -> None:
        provider.embed_query("trigger load")
        assert provider.is_loaded is True

    def test_dimension_property(self, provider: EmbeddingProvider) -> None:
        assert provider.dimension == 384


class TestMissingDependency:
    """T120: Graceful error on missing sentence-transformers."""

    def test_missing_sentence_transformers_raises(self) -> None:
        fresh = EmbeddingProvider()
        with patch.dict("sys.modules", {"sentence_transformers": None}):
            with pytest.raises(ImportError, match="sentence-transformers"):
                fresh.embed_query("test")
```
