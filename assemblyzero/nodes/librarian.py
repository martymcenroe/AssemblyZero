"""LangGraph node wrapper for the Librarian RAG retrieval.

Issue #88: The Librarian - Automated Context Retrieval

Integrates the LibrarianNode into the LangGraph workflow state machine.
Handles all failure modes gracefully — the workflow never crashes due
to RAG issues.
"""

from __future__ import annotations

import logging
from pathlib import Path

from assemblyzero.rag.models import RAGConfig, RetrievedDocument

# Guard imports that tests may patch and then reload the module.
# importlib.reload() re-executes module code but retains __dict__ entries.
# The guard preserves mocked values set by unittest.mock.patch() by
# skipping the re-import when the name already exists in module globals.
if "check_rag_dependencies" not in globals():
    from assemblyzero.rag.dependencies import check_rag_dependencies
if "LibrarianNode" not in globals():
    from assemblyzero.rag.librarian import LibrarianNode

logger = logging.getLogger(__name__)


def librarian_node(state: dict) -> dict:
    """LangGraph node function: retrieve context and update workflow state.

    Reads ``issue_brief`` from state, runs RAG retrieval, updates
    ``retrieved_context`` and ``rag_status`` fields.

    Handles all failure modes gracefully:
    - Missing dependencies -> rag_status = "deps_missing"
    - Missing vector store -> rag_status = "unavailable"
    - No results above threshold -> rag_status = "no_results"
    - Success -> rag_status = "success"
    """
    issue_brief = state.get("issue_brief", "")
    manual_context_paths = state.get("manual_context_paths", [])

    # Step 1: Check dependencies
    deps_available, deps_msg = check_rag_dependencies()
    if not deps_available:
        logger.warning(
            "[Librarian] RAG dependencies not installed. "
            "Run 'pip install assemblyzero[rag]'. Message: %s",
            deps_msg,
        )
        return {
            "retrieved_context": [],
            "rag_status": "deps_missing",
        }

    # Step 2: Initialize LibrarianNode
    config = RAGConfig()
    librarian = LibrarianNode(config=config)

    # Step 3: Check vector store availability
    available, status_msg = librarian.check_availability()
    if not available:
        if status_msg == "deps_missing":
            logger.warning(
                "[Librarian] RAG dependencies not installed. "
                "Run 'pip install assemblyzero[rag]'"
            )
            return {
                "retrieved_context": [],
                "rag_status": "deps_missing",
            }
        else:
            logger.warning(
                "[Librarian] Vector store not found. "
                "Run 'python tools/rebuild_knowledge_base.py' to build it."
            )
            return {
                "retrieved_context": [],
                "rag_status": "unavailable",
            }

    # Step 4: Retrieve relevant documents
    try:
        logger.info("[Librarian] Retrieving relevant context...")
        results = librarian.retrieve(issue_brief)
    except Exception as e:
        logger.error("[Librarian] Retrieval failed: %s", e)
        return {
            "retrieved_context": [],
            "rag_status": "unavailable",
        }

    # Step 5: Check if we got results
    if not results:
        logger.info(
            "[Librarian] No relevant governance documents found above threshold"
        )
        merged = merge_contexts([], manual_context_paths)
        return {
            "retrieved_context": merged,
            "rag_status": "no_results",
        }

    # Step 6: Success — merge with manual context
    file_paths = [doc.file_path for doc in results]
    logger.info(
        "[Librarian] Retrieved %d documents: %s",
        len(results),
        ", ".join(file_paths),
    )

    merged = merge_contexts(results, manual_context_paths)

    return {
        "retrieved_context": merged,
        "rag_status": "success",
    }


def merge_contexts(
    rag_results: list[RetrievedDocument],
    manual_context_paths: list[str],
) -> list[dict]:
    """Merge RAG results with manually-specified context files.

    Manual context takes precedence. Duplicates (same file_path) are deduplicated,
    keeping the manual version.

    Args:
        rag_results: Documents retrieved by RAG.
        manual_context_paths: File paths from --context CLI flag.

    Returns:
        Combined list of context entries (manual first, then RAG, deduplicated).
    """
    merged: list[dict] = []
    manual_file_set: set[str] = set()

    # Process manual context first
    for path_str in manual_context_paths:
        path = Path(path_str)
        manual_file_set.add(path_str)
        # Normalize path for comparison
        normalized = str(path).replace("\\", "/")
        manual_file_set.add(normalized)

        content = ""
        if path.exists():
            try:
                content = path.read_text(encoding="utf-8")
            except Exception as e:
                logger.warning(
                    "[Librarian] Could not read manual context %s: %s", path_str, e
                )
                content = f"[Error reading file: {e}]"

        merged.append(
            {
                "file_path": path_str,
                "section": "Full Document",
                "content_snippet": content,
                "score": 1.0,
                "doc_type": "manual",
            }
        )

    # Add RAG results, excluding duplicates with manual context
    for doc in rag_results:
        normalized_path = doc.file_path.replace("\\", "/")
        if doc.file_path in manual_file_set or normalized_path in manual_file_set:
            continue  # Skip — manual version takes precedence
        merged.append(doc.to_dict())

    return merged