

```python
"""Unit tests for markdown document chunker.

Issue #88: The Librarian - Automated Context Retrieval
Tests: T010, T020, T030
"""

from __future__ import annotations

from pathlib import Path

import pytest

from assemblyzero.rag.chunker import (
    chunk_markdown_document,
    detect_doc_type,
    split_on_headers,
)


class TestSplitOnHeaders:
    """Tests for split_on_headers()."""

    def test_split_h1_h2(self) -> None:
        """T010: Chunker splits markdown on H1/H2 headers (REQ-3)."""
        content = (
            "# Title\n\nIntro text\n\n"
            "## Section 1\n\nContent 1\n\n"
            "## Section 2\n\nContent 2"
        )
        sections = split_on_headers(content)
        assert len(sections) == 3
        assert sections[0] == ("# Title", "Intro text")
        assert sections[1] == ("## Section 1", "Content 1")
        assert sections[2] == ("## Section 2", "Content 2")

    def test_no_headers(self) -> None:
        """T030: Chunker handles document with no headers."""
        content = "Just some plain text\nwith multiple lines"
        sections = split_on_headers(content)
        assert len(sections) == 1
        assert sections[0][0] == "Untitled"
        assert "plain text" in sections[0][1]

    def test_empty_content(self) -> None:
        """Empty content returns empty list."""
        sections = split_on_headers("")
        assert sections == []

    def test_whitespace_only(self) -> None:
        """Whitespace-only content returns empty list."""
        sections = split_on_headers("   \n\n   ")
        assert sections == []

    def test_h3_not_split(self) -> None:
        """H3+ headers are included in parent section, not split."""
        content = "## Section\n\n### Subsection\n\nContent"
        sections = split_on_headers(content)
        assert len(sections) == 1
        assert "### Subsection" in sections[0][1]

    def test_content_before_first_header(self) -> None:
        """Content before first header gets 'Untitled' section."""
        content = "Preamble text\n\n# Title\n\nBody"
        sections = split_on_headers(content)
        assert len(sections) == 2
        assert sections[0] == ("Untitled", "Preamble text")
        assert sections[1][0] == "# Title"


class TestDetectDocType:
    """Tests for detect_doc_type()."""

    def test_adr(self) -> None:
        """T020: Chunker detects 'adr' doc type (REQ-3)."""
        assert detect_doc_type(Path("docs/adrs/0201-adversarial.md")) == "adr"

    def test_standard(self) -> None:
        """T020: Chunker detects 'standard' doc type (REQ-3)."""
        assert detect_doc_type(Path("docs/standards/0002-style.md")) == "standard"

    def test_lld(self) -> None:
        """T020: Chunker detects 'lld' doc type (REQ-3)."""
        assert detect_doc_type(Path("docs/LLDs/done/44-feature.md")) == "lld"

    def test_unknown(self) -> None:
        """Unknown path returns 'unknown'."""
        assert detect_doc_type(Path("docs/other/readme.md")) == "unknown"


class TestChunkMarkdownDocument:
    """Tests for chunk_markdown_document()."""

    def test_chunk_fixture_adr(self) -> None:
        """T010: Full chunking of sample ADR fixture (REQ-3)."""
        fixture = Path("tests/fixtures/rag/sample_adr.md")
        if not fixture.exists():
            pytest.skip("Fixture not found")

        chunks = chunk_markdown_document(fixture)
        assert len(chunks) >= 3  # Title + Decision + Consequences sections
        for content, metadata in chunks:
            assert metadata.file_path == str(fixture)
            assert metadata.doc_type == "adr"
            assert metadata.last_modified  # non-empty ISO timestamp
            assert content  # non-empty content

    def test_chunk_nonexistent_file(self) -> None:
        """FileNotFoundError for nonexistent file."""
        with pytest.raises(FileNotFoundError):
            chunk_markdown_document(Path("nonexistent.md"))

    def test_chunk_empty_file(self, tmp_path: Path) -> None:
        """Empty file returns empty list."""
        empty_file = tmp_path / "empty.md"
        empty_file.write_text("")
        chunks = chunk_markdown_document(empty_file)
        assert chunks == []

    def test_chunk_max_tokens_splitting(self, tmp_path: Path) -> None:
        """Oversized sections are split on paragraph boundaries."""
        # Create a file with a very large section
        large_content = "# Title\n\n" + "\n\n".join(
            [f"Paragraph {i} with some content to fill space." for i in range(100)]
        )
        large_file = tmp_path / "large.md"
        large_file.write_text(large_content)

        chunks = chunk_markdown_document(large_file, max_tokens=50)  # Very small limit
        assert len(chunks) > 1  # Should be split into multiple chunks
```
