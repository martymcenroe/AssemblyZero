"""Data models for the RAG subsystem.

Issue #88: The Librarian - Automated Context Retrieval

These models have no external dependencies and can be imported
without the [rag] optional extra installed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ChunkMetadata:
    """Metadata attached to each indexed document chunk."""

    file_path: str
    section_title: str
    chunk_index: int
    doc_type: str
    last_modified: str


@dataclass(frozen=True)
class RetrievedDocument:
    """A single document chunk retrieved from the vector store."""

    file_path: str
    section: str
    content_snippet: str
    score: float
    doc_type: str

    def to_dict(self) -> dict:
        """Convert to dictionary for state serialization."""
        return {
            "file_path": self.file_path,
            "section": self.section,
            "content_snippet": self.content_snippet,
            "score": self.score,
            "doc_type": self.doc_type,
        }


@dataclass
class RAGConfig:
    """Configuration for the Librarian RAG system."""

    vector_store_path: Path = field(
        default_factory=lambda: Path(".assemblyzero/vector_store")
    )
    embedding_model: str = "all-MiniLM-L6-v2"
    similarity_threshold: float = 0.7
    top_k_candidates: int = 5
    top_n_results: int = 3
    source_directories: list[str] = field(
        default_factory=lambda: ["docs/adrs", "docs/standards", "docs/LLDs/done", "docs/lineage/done"]
    )
    chunk_max_tokens: int = 512
    embedding_provider: str = "local"


@dataclass
class IngestionSummary:
    """Summary of a knowledge base ingestion run."""

    files_indexed: int = 0
    chunks_created: int = 0
    files_skipped: int = 0
    elapsed_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)