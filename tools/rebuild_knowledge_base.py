#!/usr/bin/env python3
"""CLI tool: ingest docs into ChromaDB vector store.

Issue #88: The Librarian - Automated Context Retrieval

Usage:
    python tools/rebuild_knowledge_base.py                     # Incremental (default)
    python tools/rebuild_knowledge_base.py --full              # Full rebuild
    python tools/rebuild_knowledge_base.py --full --verbose    # Verbose full rebuild
    python tools/rebuild_knowledge_base.py --source-dirs docs/adrs docs/standards
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from assemblyzero.rag.dependencies import check_rag_dependencies
from assemblyzero.rag.models import IngestionSummary, RAGConfig


def main() -> None:
    """CLI entry point for rebuilding the RAG knowledge base."""
    parser = argparse.ArgumentParser(
        description="Rebuild the RAG knowledge base for the Librarian",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        default=False,
        help="Reindex all documents from scratch (default: incremental)",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        default=True,
        help="Only reindex changed/new files (default behavior)",
    )
    parser.add_argument(
        "--source-dirs",
        nargs="+",
        default=None,
        help="Override default source directories",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Show per-file indexing progress",
    )

    args = parser.parse_args()

    # Check dependencies
    available, msg = check_rag_dependencies()
    if not available:
        print(f"[RAG] Error: {msg}", file=sys.stderr)
        sys.exit(1)

    # Build config
    config = RAGConfig()
    if args.source_dirs:
        config.source_directories = args.source_dirs

    # Run appropriate mode
    if args.full:
        print("[RAG] Rebuilding knowledge base (full mode)...")
        summary = run_full_ingestion(config, verbose=args.verbose)
    else:
        print("[RAG] Updating knowledge base (incremental mode)...")
        summary = run_incremental_ingestion(config, verbose=args.verbose)

    # Print summary
    print(
        f"[RAG] Complete: {summary.files_indexed} files indexed, "
        f"{summary.chunks_created} chunks created, "
        f"{summary.files_skipped} files skipped, "
        f"{len(summary.errors)} errors "
        f"({summary.elapsed_seconds:.2f}s)"
    )

    if summary.errors:
        print("[RAG] Errors:")
        for error in summary.errors:
            print(f"  - {error}")

    sys.exit(0)


def discover_documents(source_dirs: list[str]) -> list[Path]:
    """Find all markdown files in the specified source directories."""
    documents: list[Path] = []
    for dir_str in source_dirs:
        dir_path = Path(dir_str)
        if not dir_path.exists():
            continue
        for md_file in sorted(dir_path.rglob("*.md")):
            if md_file.is_file():
                documents.append(md_file)
    return documents


def compute_file_hash(file_path: Path) -> str:
    """Compute MD5 hash of file content for change detection."""
    content = file_path.read_bytes()
    return hashlib.md5(content).hexdigest()


def run_full_ingestion(
    config: RAGConfig,
    verbose: bool = False,
) -> IngestionSummary:
    """Drop and rebuild the entire vector store."""
    from assemblyzero.rag.chunker import chunk_markdown_document
    from assemblyzero.rag.embeddings import create_embedding_provider
    from assemblyzero.rag.vector_store import VectorStoreManager

    start_time = time.time()
    summary = IngestionSummary()

    # Initialize store (reset if exists)
    store = VectorStoreManager(config)
    store.reset()

    # Create embedding provider
    provider = create_embedding_provider(config)

    # Discover and process documents
    source_dirs = config.source_directories
    print(f"[RAG] Discovering documents in: {', '.join(source_dirs)}")
    documents = discover_documents(source_dirs)
    print(f"[RAG] Found {len(documents)} markdown files")

    for doc_path in documents:
        try:
            chunks = chunk_markdown_document(doc_path, max_tokens=config.chunk_max_tokens)
            if not chunks:
                continue

            # Extract texts for batch embedding
            texts = [content for content, _metadata in chunks]
            embeddings = provider.embed_texts(texts)

            # Add to store
            added = store.add_chunks(chunks, embeddings)
            summary.files_indexed += 1
            summary.chunks_created += added

            if verbose:
                print(f"[RAG] Indexed {doc_path} ({added} chunks)")

        except Exception as e:
            summary.errors.append(f"{doc_path}: {e}")
            if verbose:
                print(f"[RAG] Error indexing {doc_path}: {e}")

    summary.elapsed_seconds = time.time() - start_time
    return summary


def run_incremental_ingestion(
    config: RAGConfig,
    verbose: bool = False,
) -> IngestionSummary:
    """Only reindex files that have changed since last ingestion."""
    from assemblyzero.rag.chunker import chunk_markdown_document
    from assemblyzero.rag.embeddings import create_embedding_provider
    from assemblyzero.rag.vector_store import VectorStoreManager

    start_time = time.time()
    summary = IngestionSummary()

    store = VectorStoreManager(config)
    if not store.is_initialized():
        # No existing store — fall back to full ingestion
        print("[RAG] No existing store found. Running full ingestion.")
        return run_full_ingestion(config, verbose=verbose)

    provider = create_embedding_provider(config)

    # Get currently indexed files
    indexed_files = store.get_indexed_files()
    indexed_paths = set(indexed_files.keys())

    # Discover current documents
    documents = discover_documents(config.source_directories)
    current_paths = {str(doc) for doc in documents}

    # Handle deleted files: remove chunks for files no longer in source dirs
    deleted_paths = indexed_paths - current_paths
    for deleted_path in deleted_paths:
        removed = store.delete_by_file(deleted_path)
        if verbose and removed > 0:
            print(f"[RAG] Removed {removed} chunks for deleted file: {deleted_path}")

    for doc_path in documents:
        try:
            doc_path_str = str(doc_path)

            # Check if file has changed by comparing last_modified timestamps
            from datetime import datetime, timezone

            stat = doc_path.stat()
            current_mtime = datetime.fromtimestamp(
                stat.st_mtime, tz=timezone.utc
            ).isoformat()

            if doc_path_str in indexed_files:
                stored_mtime = indexed_files[doc_path_str]
                if current_mtime <= stored_mtime:
                    summary.files_skipped += 1
                    if verbose:
                        print(f"[RAG] Skipping unchanged: {doc_path}")
                    continue

            # File is new or changed — reindex
            # Delete old chunks first (if any)
            store.delete_by_file(doc_path_str)

            chunks = chunk_markdown_document(
                doc_path, max_tokens=config.chunk_max_tokens
            )
            if not chunks:
                continue

            texts = [content for content, _metadata in chunks]
            embeddings = provider.embed_texts(texts)
            added = store.add_chunks(chunks, embeddings)

            summary.files_indexed += 1
            summary.chunks_created += added

            if verbose:
                print(f"[RAG] Indexed {doc_path} ({added} chunks)")

        except Exception as e:
            summary.errors.append(f"{doc_path}: {e}")
            if verbose:
                print(f"[RAG] Error indexing {doc_path}: {e}")

    summary.elapsed_seconds = time.time() - start_time
    return summary


if __name__ == "__main__":
    main()