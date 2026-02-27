```python
"""Unit tests for RAG data models.

Issue #88: The Librarian - Automated Context Retrieval
"""

from __future__ import annotations

from pathlib import Path

from assemblyzero.rag.models import (
    ChunkMetadata,
    IngestionSummary,
    RAGConfig,
    RetrievedDocument,
)


class TestChunkMetadata:
    """Tests for ChunkMetadata dataclass."""

    def test_creation(self) -> None:
        meta = ChunkMetadata(
            file_path="docs/adrs/0201.md",
            section_title="## 2. Decision",
            chunk_index=1,
            doc_type="adr",
            last_modified="2026-02-15T10:30:00+00:00",
        )
        assert meta.file_path == "docs/adrs/0201.md"
        assert meta.section_title == "## 2. Decision"
        assert meta.chunk_index == 1
        assert meta.doc_type == "adr"

    def test_frozen(self) -> None:
        meta = ChunkMetadata(
            file_path="docs/adrs/0201.md",
            section_title="## 2. Decision",
            chunk_index=1,
            doc_type="adr",
            last_modified="2026-02-15T10:30:00+00:00",
        )
        try:
            meta.file_path = "other.md"  # type: ignore[misc]
            assert False, "Should have raised FrozenInstanceError"
        except AttributeError:
            pass  # Expected


class TestRetrievedDocument:
    """Tests for RetrievedDocument dataclass."""

    def test_creation(self) -> None:
        doc = RetrievedDocument(
            file_path="docs/adrs/0201.md",
            section="## 2. Decision",
            content_snippet="We will implement...",
            score=0.85,
            doc_type="adr",
        )
        assert doc.score == 0.85
        assert doc.doc_type == "adr"

    def test_to_dict(self) -> None:
        doc = RetrievedDocument(
            file_path="docs/adrs/0201.md",
            section="## 2. Decision",
            content_snippet="We will implement...",
            score=0.85,
            doc_type="adr",
        )
        d = doc.to_dict()
        assert d == {
            "file_path": "docs/adrs/0201.md",
            "section": "## 2. Decision",
            "content_snippet": "We will implement...",
            "score": 0.85,
            "doc_type": "adr",
        }


class TestRAGConfig:
    """Tests for RAGConfig dataclass."""

    def test_defaults(self) -> None:
        config = RAGConfig()
        assert config.vector_store_path == Path(".assemblyzero/vector_store")
        assert config.embedding_model == "all-MiniLM-L6-v2"
        assert config.similarity_threshold == 0.7
        assert config.top_k_candidates == 5
        assert config.top_n_results == 3
        assert config.chunk_max_tokens == 512
        assert config.embedding_provider == "local"
        assert "docs/adrs" in config.source_directories

    def test_custom_values(self) -> None:
        config = RAGConfig(
            similarity_threshold=0.8,
            top_n_results=5,
        )
        assert config.similarity_threshold == 0.8
        assert config.top_n_results == 5


class TestIngestionSummary:
    """Tests for IngestionSummary dataclass."""

    def test_defaults(self) -> None:
        summary = IngestionSummary()
        assert summary.files_indexed == 0
        assert summary.chunks_created == 0
        assert summary.files_skipped == 0
        assert summary.elapsed_seconds == 0.0
        assert summary.errors == []

    def test_mutable_errors(self) -> None:
        summary = IngestionSummary()
        summary.errors.append("test error")
        assert len(summary.errors) == 1

        # Verify independent instances
        summary2 = IngestionSummary()
        assert len(summary2.errors) == 0
```
