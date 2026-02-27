"""RAG configuration dataclass and defaults.

Issue #113: Vector Database Infrastructure (RAG Foundation)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class RAGConfig:
    """Immutable configuration for the RAG infrastructure.

    Attributes:
        persist_directory: Path for ChromaDB persistent storage.
        embedding_model_name: SentenceTransformers model name.
        embedding_dimension: Vector dimension (must match model).
        chunk_size: Maximum tokens per chunk.
        chunk_overlap: Overlap tokens between consecutive chunks.
        default_n_results: Default number of query results.
        distance_metric: ChromaDB distance function.
    """

    persist_directory: Path = field(
        default_factory=lambda: Path(".assemblyzero/vector_store")
    )
    embedding_model_name: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    chunk_size: int = 512
    chunk_overlap: int = 50
    default_n_results: int = 5
    distance_metric: str = "cosine"

    def __post_init__(self) -> None:
        """Validate configuration invariants.

        Raises:
            ValueError: If chunk_overlap >= chunk_size (would cause infinite
                loop in sliding window chunker) or if either value is <= 0.
        """
        if self.chunk_size <= 0:
            raise ValueError(
                f"chunk_size must be positive, got {self.chunk_size}"
            )
        if self.chunk_overlap < 0:
            raise ValueError(
                f"chunk_overlap must be non-negative, got {self.chunk_overlap}"
            )
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                f"chunk_overlap ({self.chunk_overlap}) must be strictly less "
                f"than chunk_size ({self.chunk_size}) to ensure forward "
                f"progress in the chunking loop"
            )