"""Unit tests for ChromaDB vector store wrapper.

Issue #88: The Librarian - Automated Context Retrieval
Tests: T060, T070, T080, T290
"""

from __future__ import annotations

from pathlib import Path

import pytest

from assemblyzero.rag.models import ChunkMetadata, RAGConfig


@pytest.mark.rag
class TestVectorStoreManager:
    """Tests for VectorStoreManager (requires [rag] extra)."""

    def _make_config(self, tmp_path: Path) -> RAGConfig:
        """Create a RAGConfig pointing to a temp directory."""
        return RAGConfig(vector_store_path=tmp_path / "test_vector_store")

    def test_is_initialized_missing_dir(self, tmp_path: Path) -> None:
        """T060: Vector store not initialized returns False (REQ-1)."""
        from assemblyzero.rag.vector_store import VectorStoreManager

        config = self._make_config(tmp_path)
        manager = VectorStoreManager(config)
        assert manager.is_initialized() is False

    def test_initialize_creates_store(self, tmp_path: Path) -> None:
        """Initialize creates the vector store directory and collection."""
        from assemblyzero.rag.vector_store import VectorStoreManager

        config = self._make_config(tmp_path)
        manager = VectorStoreManager(config)
        manager.initialize()
        assert config.vector_store_path.exists()

    def test_add_and_query_round_trip(self, tmp_path: Path) -> None:
        """T070: Round-trip add chunks then query (REQ-1)."""
        from assemblyzero.rag.vector_store import VectorStoreManager

        config = self._make_config(tmp_path)
        manager = VectorStoreManager(config)
        manager.initialize()

        # Create test chunks with known embeddings
        chunks = [
            (
                "We will implement adversarial audit as a mandatory gate",
                ChunkMetadata(
                    file_path="docs/adrs/0201.md",
                    section_title="## 2. Decision",
                    chunk_index=0,
                    doc_type="adr",
                    last_modified="2026-02-15T10:30:00+00:00",
                ),
            ),
            (
                "All code must have 95% test coverage minimum",
                ChunkMetadata(
                    file_path="docs/standards/0005.md",
                    section_title="## 3. Coverage",
                    chunk_index=0,
                    doc_type="standard",
                    last_modified="2026-02-10T08:00:00+00:00",
                ),
            ),
        ]

        # Use simple embeddings for testing (not real model)
        # Embedding 1: mostly positive
        emb1 = [0.1] * 384
        # Embedding 2: mostly negative
        emb2 = [-0.1] * 384

        manager.add_chunks(chunks, [emb1, emb2])

        # Query with embedding similar to emb1
        results = manager.query(query_embedding=emb1, n_results=2)
        assert len(results) > 0
        assert results[0].file_path == "docs/adrs/0201.md"
        assert results[0].score > 0.5

    def test_query_empty_collection(self, tmp_path: Path) -> None:
        """T080: Query on empty collection returns empty list (REQ-1)."""
        from assemblyzero.rag.vector_store import VectorStoreManager

        config = self._make_config(tmp_path)
        manager = VectorStoreManager(config)
        manager.initialize()

        results = manager.query(query_embedding=[0.0] * 384, n_results=5)
        assert results == []

    def test_add_chunks_length_mismatch(self, tmp_path: Path) -> None:
        """Mismatched chunks/embeddings raises ValueError."""
        from assemblyzero.rag.vector_store import VectorStoreManager

        config = self._make_config(tmp_path)
        manager = VectorStoreManager(config)
        manager.initialize()

        chunks = [
            (
                "content",
                ChunkMetadata(
                    file_path="test.md",
                    section_title="## Test",
                    chunk_index=0,
                    doc_type="adr",
                    last_modified="2026-01-01T00:00:00+00:00",
                ),
            ),
        ]
        with pytest.raises(ValueError, match="Chunk count"):
            manager.add_chunks(chunks, [])

    def test_delete_by_file(self, tmp_path: Path) -> None:
        """delete_by_file removes chunks for specified file."""
        from assemblyzero.rag.vector_store import VectorStoreManager

        config = self._make_config(tmp_path)
        manager = VectorStoreManager(config)
        manager.initialize()

        chunks = [
            (
                "Content A",
                ChunkMetadata(
                    file_path="file_a.md",
                    section_title="## A",
                    chunk_index=0,
                    doc_type="adr",
                    last_modified="2026-01-01T00:00:00+00:00",
                ),
            ),
            (
                "Content B",
                ChunkMetadata(
                    file_path="file_b.md",
                    section_title="## B",
                    chunk_index=0,
                    doc_type="standard",
                    last_modified="2026-01-01T00:00:00+00:00",
                ),
            ),
        ]
        embeddings = [[0.1] * 384, [-0.1] * 384]
        manager.add_chunks(chunks, embeddings)

        deleted = manager.delete_by_file("file_a.md")
        assert deleted == 1

        stats = manager.collection_stats()
        assert stats["total_chunks"] == 1

    def test_collection_stats(self, tmp_path: Path) -> None:
        """collection_stats returns correct counts."""
        from assemblyzero.rag.vector_store import VectorStoreManager

        config = self._make_config(tmp_path)
        manager = VectorStoreManager(config)
        manager.initialize()

        stats = manager.collection_stats()
        assert stats == {"total_chunks": 0, "unique_files": 0}

    def test_get_indexed_files(self, tmp_path: Path) -> None:
        """get_indexed_files returns correct mapping."""
        from assemblyzero.rag.vector_store import VectorStoreManager

        config = self._make_config(tmp_path)
        manager = VectorStoreManager(config)
        manager.initialize()

        chunks = [
            (
                "Content",
                ChunkMetadata(
                    file_path="docs/adrs/0201.md",
                    section_title="## Test",
                    chunk_index=0,
                    doc_type="adr",
                    last_modified="2026-02-15T10:30:00+00:00",
                ),
            ),
        ]
        manager.add_chunks(chunks, [[0.1] * 384])

        files = manager.get_indexed_files()
        assert "docs/adrs/0201.md" in files
        assert files["docs/adrs/0201.md"] == "2026-02-15T10:30:00+00:00"

    def test_persistence_across_instances(self, tmp_path: Path) -> None:
        """T290: Vector store persists between sessions (REQ-13)."""
        from assemblyzero.rag.vector_store import VectorStoreManager

        config = self._make_config(tmp_path)

        # Instance 1: add data
        manager1 = VectorStoreManager(config)
        manager1.initialize()
        chunks = [
            (
                "Persistent content",
                ChunkMetadata(
                    file_path="persist.md",
                    section_title="## Test",
                    chunk_index=0,
                    doc_type="adr",
                    last_modified="2026-01-01T00:00:00+00:00",
                ),
            ),
        ]
        manager1.add_chunks(chunks, [[0.1] * 384])

        # Instance 2: query same data (simulates process restart)
        manager2 = VectorStoreManager(config)
        results = manager2.query(query_embedding=[0.1] * 384, n_results=1)
        assert len(results) == 1
        assert results[0].file_path == "persist.md"

    def test_reset(self, tmp_path: Path) -> None:
        """reset clears all data and recreates collection."""
        from assemblyzero.rag.vector_store import VectorStoreManager

        config = self._make_config(tmp_path)
        manager = VectorStoreManager(config)
        manager.initialize()

        chunks = [
            (
                "Content",
                ChunkMetadata(
                    file_path="test.md",
                    section_title="## Test",
                    chunk_index=0,
                    doc_type="adr",
                    last_modified="2026-01-01T00:00:00+00:00",
                ),
            ),
        ]
        manager.add_chunks(chunks, [[0.1] * 384])
        assert manager.collection_stats()["total_chunks"] == 1

        manager.reset()
        assert manager.collection_stats()["total_chunks"] == 0