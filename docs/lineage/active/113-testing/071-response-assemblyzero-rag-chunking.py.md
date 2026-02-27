

```python
"""TextChunker — document splitting for embedding.

Issue #113: Vector Database Infrastructure (RAG Foundation)
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TextChunk:
    """A chunk of text with provenance metadata.

    Attributes:
        text: The chunk text content.
        metadata: Source metadata (source_file, line range, etc.).
        chunk_index: Position within the source document (0-based).
    """

    text: str
    metadata: dict
    chunk_index: int


class TextChunker:
    """Split documents into chunks suitable for embedding.

    Uses a simple sliding window approach with configurable
    chunk size (in whitespace-delimited tokens) and overlap.
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
    ) -> None:
        """Initialize with chunk size (tokens) and overlap.

        Args:
            chunk_size: Maximum number of tokens per chunk.
            chunk_overlap: Number of overlapping tokens between chunks.

        Raises:
            ValueError: If chunk_overlap >= chunk_size or if either
                value is non-positive (chunk_size) or negative (chunk_overlap).
        """
        if chunk_size <= 0:
            raise ValueError(
                f"chunk_size must be positive, got {chunk_size}"
            )
        if chunk_overlap < 0:
            raise ValueError(
                f"chunk_overlap must be non-negative, got {chunk_overlap}"
            )
        if chunk_overlap >= chunk_size:
            raise ValueError(
                f"chunk_overlap ({chunk_overlap}) must be strictly less "
                f"than chunk_size ({chunk_size}) to ensure forward "
                f"progress in the chunking loop"
            )
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

    def chunk_text(
        self,
        text: str,
        metadata: dict | None = None,
    ) -> list[TextChunk]:
        """Split text into overlapping chunks with metadata propagation.

        Tokenization is whitespace-based (not model-specific).
        Empty text returns empty list.

        Args:
            text: The text to split.
            metadata: Optional metadata to propagate to all chunks.

        Returns:
            List of TextChunk objects. Empty list for empty/whitespace text.
        """
        if not text or not text.strip():
            return []

        meta = metadata if metadata is not None else {}
        tokens = text.split()

        if len(tokens) <= self._chunk_size:
            return [TextChunk(text=text.strip(), metadata=dict(meta), chunk_index=0)]

        chunks: list[TextChunk] = []
        stride = self._chunk_size - self._chunk_overlap
        idx = 0
        chunk_index = 0

        while idx < len(tokens):
            end = min(idx + self._chunk_size, len(tokens))
            chunk_tokens = tokens[idx:end]
            chunk_text = " ".join(chunk_tokens)
            chunks.append(
                TextChunk(
                    text=chunk_text,
                    metadata=dict(meta),
                    chunk_index=chunk_index,
                )
            )
            chunk_index += 1
            idx += stride
            # If next window would start past end, stop
            if idx >= len(tokens):
                break

        return chunks

    def chunk_file(
        self,
        file_path: Path,
        additional_metadata: dict | None = None,
        project_root: Path | None = None,
    ) -> list[TextChunk]:
        """Read file and chunk contents. Adds file path to metadata.

        Validates that file_path exists and resolves to a location
        within project_root (defaults to current working directory).

        Args:
            file_path: Path to the file to chunk.
            additional_metadata: Extra metadata to include in each chunk.
            project_root: Root directory for path traversal validation.
                Defaults to Path.cwd() if None.

        Returns:
            List of TextChunk objects with source_file in metadata.

        Raises:
            FileNotFoundError: If file doesn't exist.
            ValueError: If resolved file_path is outside project_root
                (path traversal protection).
        """
        root = (project_root or Path.cwd()).resolve()
        resolved_path = file_path.resolve()

        # Path traversal check
        try:
            resolved_path.relative_to(root)
        except ValueError:
            raise ValueError(
                f"Path traversal: {resolved_path} is outside {root}"
            )

        if not resolved_path.exists():
            raise FileNotFoundError(f"File not found: {resolved_path}")

        if not resolved_path.is_file():
            raise FileNotFoundError(f"Not a file: {resolved_path}")

        content = resolved_path.read_text(encoding="utf-8")

        meta = additional_metadata.copy() if additional_metadata else {}
        # Store relative path from project root for portability
        try:
            meta["source_file"] = str(resolved_path.relative_to(root))
        except ValueError:
            meta["source_file"] = str(resolved_path)

        return self.chunk_text(content, metadata=meta)
```
