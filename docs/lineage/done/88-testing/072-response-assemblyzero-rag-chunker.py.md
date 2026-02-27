```python
"""Markdown document chunker for RAG ingestion.

Issue #88: The Librarian - Automated Context Retrieval

Splits markdown documents on H1/H2 headers to create semantically
meaningful chunks for vector store indexing. Preserves metadata
about source file, section title, and document type.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from assemblyzero.rag.models import ChunkMetadata

# Regex to match H1 (# ) or H2 (## ) headers at line start
_HEADER_PATTERN = re.compile(r"^(#{1,2})\s+(.+)$", re.MULTILINE)

# Approximate tokens per character (conservative estimate for English)
_CHARS_PER_TOKEN = 4


def chunk_markdown_document(
    file_path: Path,
    max_tokens: int = 512,
) -> list[tuple[str, ChunkMetadata]]:
    """Split a markdown document into chunks on H1/H2 headers.

    Args:
        file_path: Path to the markdown file.
        max_tokens: Maximum approximate token count per chunk.

    Returns:
        List of (content_text, metadata) tuples.

    Raises:
        FileNotFoundError: If file_path does not exist.
    """
    content = file_path.read_text(encoding="utf-8")
    if not content.strip():
        return []

    doc_type = detect_doc_type(file_path)
    stat = file_path.stat()
    last_modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()

    sections = split_on_headers(content)
    max_chars = max_tokens * _CHARS_PER_TOKEN

    chunks: list[tuple[str, ChunkMetadata]] = []
    chunk_index = 0

    for section_title, section_content in sections:
        # Combine title and content for the chunk text
        full_text = f"{section_title}\n\n{section_content}".strip()

        if len(full_text) <= max_chars:
            metadata = ChunkMetadata(
                file_path=str(file_path),
                section_title=section_title,
                chunk_index=chunk_index,
                doc_type=doc_type,
                last_modified=last_modified,
            )
            chunks.append((full_text, metadata))
            chunk_index += 1
        else:
            # Split oversized sections on paragraph boundaries
            sub_chunks = _split_on_paragraphs(full_text, max_chars)
            for sub_text in sub_chunks:
                metadata = ChunkMetadata(
                    file_path=str(file_path),
                    section_title=section_title,
                    chunk_index=chunk_index,
                    doc_type=doc_type,
                    last_modified=last_modified,
                )
                chunks.append((sub_text, metadata))
                chunk_index += 1

    return chunks


def detect_doc_type(file_path: Path) -> str:
    """Determine document type from file path.

    Checks directory structure first, then falls back to filename patterns.
    Returns 'adr', 'standard', 'lld', or 'unknown'.
    """
    path_str = str(file_path).replace("\\", "/")

    # Check directory-based patterns first
    if "/adrs/" in path_str or path_str.startswith("docs/adrs/"):
        return "adr"
    elif "/standards/" in path_str or path_str.startswith("docs/standards/"):
        return "standard"
    elif "/LLDs/" in path_str or path_str.startswith("docs/LLDs/"):
        return "lld"

    # Fallback: check filename for doc type indicators
    filename_lower = file_path.name.lower()
    stem_lower = file_path.stem.lower()
    # Check for patterns like "sample_adr", "adr_0201", "adr-0201", "0201-adr"
    if "_adr" in stem_lower or "adr_" in stem_lower or "adr-" in stem_lower or "-adr" in stem_lower or stem_lower == "adr":
        return "adr"
    elif "_standard" in stem_lower or "standard_" in stem_lower or "standard-" in stem_lower or "-standard" in stem_lower or stem_lower == "standard":
        return "standard"
    elif "_lld" in stem_lower or "lld_" in stem_lower or "lld-" in stem_lower or "-lld" in stem_lower or stem_lower == "lld":
        return "lld"

    return "unknown"


def split_on_headers(content: str) -> list[tuple[str, str]]:
    """Split markdown content on H1/H2 headers.

    Returns list of (section_title, section_content) tuples.
    H3+ headers are included in their parent section.
    """
    matches = list(_HEADER_PATTERN.finditer(content))

    if not matches:
        stripped = content.strip()
        if stripped:
            return [("Untitled", stripped)]
        return []

    sections: list[tuple[str, str]] = []

    # Handle content before first header
    first_match_start = matches[0].start()
    pre_header = content[:first_match_start].strip()
    if pre_header:
        sections.append(("Untitled", pre_header))

    for i, match in enumerate(matches):
        title = match.group(0).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        section_content = content[start:end].strip()
        sections.append((title, section_content))

    return sections


def _split_on_paragraphs(text: str, max_chars: int) -> list[str]:
    """Split text on paragraph boundaries (double newlines) to fit max_chars."""
    paragraphs = re.split(r"\n\n+", text)
    chunks: list[str] = []
    current_chunk: list[str] = []
    current_length = 0

    for para in paragraphs:
        para_len = len(para)
        if current_length + para_len + 2 > max_chars and current_chunk:
            chunks.append("\n\n".join(current_chunk))
            current_chunk = [para]
            current_length = para_len
        else:
            current_chunk.append(para)
            current_length += para_len + 2  # +2 for \n\n separator

    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    return chunks
```
