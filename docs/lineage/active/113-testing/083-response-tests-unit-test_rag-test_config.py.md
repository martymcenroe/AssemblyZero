

```python
"""Tests for RAGConfig validation (T330, T350).

Issue #113: Vector Database Infrastructure (RAG Foundation)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from assemblyzero.rag.config import RAGConfig


class TestConfigDefaults:
    """T330: Config defaults match specification."""

    def test_default_persist_directory(self) -> None:
        config = RAGConfig()
        assert config.persist_directory == Path(".assemblyzero/vector_store")

    def test_default_embedding_model(self) -> None:
        config = RAGConfig()
        assert config.embedding_model_name == "all-MiniLM-L6-v2"

    def test_default_embedding_dimension(self) -> None:
        config = RAGConfig()
        assert config.embedding_dimension == 384

    def test_default_chunk_size(self) -> None:
        config = RAGConfig()
        assert config.chunk_size == 512

    def test_default_chunk_overlap(self) -> None:
        config = RAGConfig()
        assert config.chunk_overlap == 50

    def test_default_n_results(self) -> None:
        config = RAGConfig()
        assert config.default_n_results == 5

    def test_default_distance_metric(self) -> None:
        config = RAGConfig()
        assert config.distance_metric == "cosine"

    def test_config_is_frozen(self) -> None:
        config = RAGConfig()
        with pytest.raises(AttributeError):
            config.chunk_size = 1024  # type: ignore[misc]


class TestConfigValidation:
    """T350: Config rejects invalid overlap settings."""

    def test_overlap_equal_to_size_raises(self) -> None:
        """chunk_overlap == chunk_size should raise ValueError.

        Input: RAGConfig(chunk_size=100, chunk_overlap=100)
        Expected: ValueError with message containing 'chunk_overlap (100) must be strictly less than chunk_size (100)'
        """
        with pytest.raises(ValueError, match="chunk_overlap.*100.*must be strictly less.*chunk_size.*100"):
            RAGConfig(chunk_size=100, chunk_overlap=100)

    def test_overlap_greater_than_size_raises(self) -> None:
        """chunk_overlap > chunk_size should raise ValueError.

        Input: RAGConfig(chunk_size=100, chunk_overlap=150)
        Expected: ValueError with message containing 'chunk_overlap (150) must be strictly less than chunk_size (100)'
        """
        with pytest.raises(ValueError, match="chunk_overlap.*150.*must be strictly less.*chunk_size.*100"):
            RAGConfig(chunk_size=100, chunk_overlap=150)

    def test_zero_overlap_is_valid(self) -> None:
        config = RAGConfig(chunk_overlap=0)
        assert config.chunk_overlap == 0

    def test_zero_chunk_size_raises(self) -> None:
        with pytest.raises(ValueError, match="chunk_size must be positive"):
            RAGConfig(chunk_size=0)

    def test_negative_chunk_size_raises(self) -> None:
        with pytest.raises(ValueError, match="chunk_size must be positive"):
            RAGConfig(chunk_size=-10)

    def test_negative_overlap_raises(self) -> None:
        with pytest.raises(ValueError, match="chunk_overlap must be non-negative"):
            RAGConfig(chunk_overlap=-1)

    def test_custom_persist_directory(self) -> None:
        config = RAGConfig(persist_directory=Path("/tmp/custom_store"))
        assert config.persist_directory == Path("/tmp/custom_store")
```
