"""Integration test: end-to-end LLD workflow with RAG.

Issue #88: The Librarian - Automated Context Retrieval
Tests: T200, T210, T220
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.rag.models import RAGConfig


@pytest.mark.integration
@pytest.mark.rag
class TestRagWorkflowIntegration:
    """Integration tests requiring [rag] extra and real ChromaDB."""

    def test_full_ingestion(self, tmp_path: Path) -> None:
        """T200: Full ingestion indexes fixture docs (REQ-10)."""
        from assemblyzero.rag.chunker import chunk_markdown_document
        from assemblyzero.rag.embeddings import create_embedding_provider
        from assemblyzero.rag.vector_store import VectorStoreManager

        config = RAGConfig(
            vector_store_path=tmp_path / "store",
            source_directories=["tests/fixtures/rag"],
        )

        store = VectorStoreManager(config)
        store.initialize()
        provider = create_embedding_provider(config)

        fixtures_dir = Path("tests/fixtures/rag")
        files = list(fixtures_dir.glob("*.md"))
        assert len(files) >= 3, "Expected at least 3 fixture files"

        total_files = 0
        total_chunks = 0
        for md_file in files:
            chunks = chunk_markdown_document(md_file)
            if chunks:
                texts = [c for c, _m in chunks]
                embeddings = provider.embed_texts(texts)
                added = store.add_chunks(chunks, embeddings)
                total_files += 1
                total_chunks += added

        assert total_files >= 3
        assert total_chunks > 0
        stats = store.collection_stats()
        assert stats["total_chunks"] == total_chunks

    def test_incremental_ingestion_skips_unchanged(self, tmp_path: Path) -> None:
        """T210: Incremental ingestion skips unchanged files (REQ-10)."""
        config = RAGConfig(
            vector_store_path=tmp_path / "store",
            source_directories=["tests/fixtures/rag"],
        )

        # First: full ingestion
        from tools.rebuild_knowledge_base import run_full_ingestion, run_incremental_ingestion

        full_summary = run_full_ingestion(config, verbose=False)
        assert full_summary.files_indexed >= 3

        # Second: incremental should skip all
        inc_summary = run_incremental_ingestion(config, verbose=False)
        assert inc_summary.files_skipped >= full_summary.files_indexed
        assert inc_summary.files_indexed == 0

    def test_lld_workflow_graph_execution(self, tmp_path: Path) -> None:
        """T220: Integration: librarian_node in LLD workflow graph."""
        from assemblyzero.rag.chunker import chunk_markdown_document
        from assemblyzero.rag.embeddings import create_embedding_provider
        from assemblyzero.rag.models import RAGConfig
        from assemblyzero.rag.vector_store import VectorStoreManager

        # Build a real vector store with fixture data
        config = RAGConfig(vector_store_path=tmp_path / "store")

        store = VectorStoreManager(config)
        store.initialize()
        provider = create_embedding_provider(config)

        fixtures_dir = Path("tests/fixtures/rag")
        for md_file in fixtures_dir.glob("*.md"):
            chunks = chunk_markdown_document(md_file)
            if chunks:
                texts = [c for c, _m in chunks]
                embeddings = provider.embed_texts(texts)
                store.add_chunks(chunks, embeddings)

        # Now test the librarian_node directly with real store
        from assemblyzero.nodes.librarian import librarian_node

        state = {
            "issue_brief": "Implement automated testing pipeline with code review",
            "manual_context_paths": [],
            "retrieved_context": [],
            "rag_status": "",
            "designer_output": "",
        }

        # Patch RAGConfig to point to our tmp store
        with patch(
            "assemblyzero.nodes.librarian.RAGConfig",
            return_value=config,
        ):
            result = librarian_node(state)

        # Should succeed since we have a real store with data
        assert result["rag_status"] in ("success", "no_results")
        if result["rag_status"] == "success":
            assert len(result["retrieved_context"]) > 0