"""Tests for TextChunker (T210–T250, T350, T360).

Issue #113: Vector Database Infrastructure (RAG Foundation)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from assemblyzero.rag.chunking import TextChunk, TextChunker


class TestChunkText:
    """T210: Text chunker splits correctly."""

    def test_larger_text_with_overlap(self) -> None:
        """Split 10-token text with chunk_size=4, overlap=1 into 3 chunks.

        Input:
            text = "one two three four five six seven eight nine ten"
            chunk_size = 4, chunk_overlap = 1

        Expected Output:
            4 TextChunk objects (stride=3, last chunk is trailing overlap):
              - TextChunk(text="one two three four", metadata={}, chunk_index=0)
              - TextChunk(text="four five six seven", metadata={}, chunk_index=1)
              - TextChunk(text="seven eight nine ten", metadata={}, chunk_index=2)
              - TextChunk(text="ten", metadata={}, chunk_index=3)
        """
        chunker = TextChunker(chunk_size=4, chunk_overlap=1)
        chunks = chunker.chunk_text(
            "one two three four five six seven eight nine ten"
        )
        assert len(chunks) == 4
        assert chunks[0].text == "one two three four"
        assert chunks[0].chunk_index == 0
        assert chunks[1].text == "four five six seven"
        assert chunks[1].chunk_index == 1
        assert chunks[2].text == "seven eight nine ten"
        assert chunks[2].chunk_index == 2
        assert chunks[3].text == "ten"
        assert chunks[3].chunk_index == 3

    def test_chunk_size_boundary(self) -> None:
        chunker = TextChunker(chunk_size=200, chunk_overlap=50)
        # Generate a ~1000-token text
        tokens = [f"word{i}" for i in range(1000)]
        text = " ".join(tokens)
        chunks = chunker.chunk_text(text)
        # stride = 200 - 50 = 150, ceil(1000/150) ≈ 7 chunks
        assert len(chunks) >= 6
        for chunk in chunks:
            assert len(chunk.text.split()) <= 200


class TestChunkMetadata:
    """T220: Text chunker preserves metadata."""

    def test_metadata_propagated_to_all_chunks(self) -> None:
        chunker = TextChunker(chunk_size=4, chunk_overlap=1)
        meta = {"source": "test.md", "author": "tester"}
        chunks = chunker.chunk_text(
            "one two three four five six seven eight nine ten",
            metadata=meta,
        )
        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk.metadata["source"] == "test.md"
            assert chunk.metadata["author"] == "tester"

    def test_none_metadata_gives_empty_dict(self) -> None:
        """When metadata=None, each chunk should have an empty dict.

        Input:
            text = "hello world foo bar baz"
            metadata = None (default)
            chunk_size = 3, chunk_overlap = 0

        Expected Output:
            2 TextChunk objects, each with metadata == {}
        """
        chunker = TextChunker(chunk_size=3, chunk_overlap=0)
        chunks = chunker.chunk_text("hello world foo bar baz")
        assert len(chunks) == 2
        for chunk in chunks:
            assert chunk.metadata == {}


class TestChunkEmptyText:
    """T230: Text chunker handles empty text."""

    def test_empty_string_returns_empty(self) -> None:
        chunker = TextChunker()
        assert chunker.chunk_text("") == []

    def test_whitespace_only_returns_empty(self) -> None:
        chunker = TextChunker()
        assert chunker.chunk_text("   \n\t  ") == []


class TestChunkShortText:
    """T240: Text chunker handles short text."""

    def test_short_text_single_chunk(self) -> None:
        chunker = TextChunker(chunk_size=512)
        chunks = chunker.chunk_text("short text")
        assert len(chunks) == 1
        assert chunks[0].text == "short text"
        assert chunks[0].chunk_index == 0


class TestChunkFile:
    """T250: Text chunker chunk_file reads from path."""

    def test_chunk_file_reads_content(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.md"
        test_file.write_text("word " * 100, encoding="utf-8")

        chunker = TextChunker(chunk_size=20, chunk_overlap=5)
        chunks = chunker.chunk_file(
            test_file,
            additional_metadata={"section": "test"},
            project_root=tmp_path,
        )
        assert len(chunks) > 1
        for chunk in chunks:
            assert "source_file" in chunk.metadata
            assert chunk.metadata["section"] == "test"

    def test_chunk_file_missing_raises(self, tmp_path: Path) -> None:
        chunker = TextChunker()
        with pytest.raises(FileNotFoundError):
            chunker.chunk_file(
                tmp_path / "nonexistent.md",
                project_root=tmp_path,
            )


class TestChunkOverlapValidation:
    """T350: Chunker rejects invalid overlap settings."""

    def test_overlap_equal_to_size_raises(self) -> None:
        """chunk_overlap == chunk_size should raise ValueError.

        Input: TextChunker(chunk_size=100, chunk_overlap=100)
        Expected: ValueError with message containing 'chunk_overlap (100) must be strictly less than chunk_size (100)'
        """
        with pytest.raises(ValueError, match="chunk_overlap.*100.*must be strictly less.*chunk_size.*100"):
            TextChunker(chunk_size=100, chunk_overlap=100)

    def test_overlap_greater_than_size_raises(self) -> None:
        """chunk_overlap > chunk_size should raise ValueError.

        Input: TextChunker(chunk_size=50, chunk_overlap=100)
        Expected: ValueError with message containing 'chunk_overlap (100) must be strictly less than chunk_size (50)'
        """
        with pytest.raises(ValueError, match="chunk_overlap.*100.*must be strictly less.*chunk_size.*50"):
            TextChunker(chunk_size=50, chunk_overlap=100)

    def test_zero_chunk_size_raises(self) -> None:
        with pytest.raises(ValueError, match="chunk_size must be positive"):
            TextChunker(chunk_size=0, chunk_overlap=0)

    def test_negative_overlap_raises(self) -> None:
        with pytest.raises(ValueError, match="chunk_overlap must be non-negative"):
            TextChunker(chunk_size=100, chunk_overlap=-5)


class TestPathTraversal:
    """T360: chunk_file rejects path outside project root."""

    def test_absolute_path_outside_root_raises(self, tmp_path: Path) -> None:
        # Create a file outside the project root
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()
        outside_file = outside_dir / "evil.txt"
        outside_file.write_text("malicious content")

        project_root = tmp_path / "project"
        project_root.mkdir()

        chunker = TextChunker()
        with pytest.raises(ValueError, match="Path traversal"):
            chunker.chunk_file(outside_file, project_root=project_root)

    def test_relative_traversal_raises(self, tmp_path: Path) -> None:
        # Create project root and an outside file
        project_root = tmp_path / "project"
        project_root.mkdir()
        outside_file = tmp_path / "secret.txt"
        outside_file.write_text("secret data")

        chunker = TextChunker()
        # Use a relative path that traverses up
        traversal_path = project_root / ".." / "secret.txt"
        with pytest.raises(ValueError, match="Path traversal"):
            chunker.chunk_file(traversal_path, project_root=project_root)

    def test_valid_path_within_root_works(self, tmp_path: Path) -> None:
        project_root = tmp_path / "project"
        project_root.mkdir()
        valid_file = project_root / "doc.md"
        valid_file.write_text("valid content here")

        chunker = TextChunker(chunk_size=100)
        chunks = chunker.chunk_file(valid_file, project_root=project_root)
        assert len(chunks) == 1
        assert chunks[0].metadata["source_file"] == "doc.md"