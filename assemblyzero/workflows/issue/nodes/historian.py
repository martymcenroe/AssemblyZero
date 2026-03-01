"""N0b: Historian node — RAG history check before drafting.

Issue #91: Check if similar work was already done before drafting a new issue.

Queries the Librarian (RAG) with the brief content and classifies results:
- High (>=0.85): set history_status="high_similarity" — triggers human gate
- Medium (0.5-0.85): set history_context with formatted past-work references
- Low (<0.5): no action, workflow continues normally

Fails open: any RAG error → history_status="unavailable", workflow continues.
"""

from __future__ import annotations

import logging
from typing import Any

from assemblyzero.workflows.issue.state import IssueWorkflowState

logger = logging.getLogger(__name__)

# Similarity thresholds
HIGH_THRESHOLD = 0.85
MEDIUM_THRESHOLD = 0.5


def historian(state: IssueWorkflowState) -> dict[str, Any]:
    """N0b: Query RAG for similar past work.

    Args:
        state: Current workflow state (needs brief_content from N0).

    Returns:
        State updates: history_matches, history_status, history_context.
    """
    brief_content = state.get("brief_content", "")

    if not brief_content:
        logger.info("[Historian] No brief content, skipping")
        return {"history_status": "unavailable", "history_matches": [], "history_context": ""}

    # Fail open: wrap everything in try/except
    try:
        return _query_and_classify(brief_content)
    except Exception as e:
        logger.warning("[Historian] RAG query failed (fail-open): %s", e)
        return {"history_status": "unavailable", "history_matches": [], "history_context": ""}


def _query_and_classify(brief_content: str) -> dict[str, Any]:
    """Query the Librarian and classify results by similarity tier."""
    from assemblyzero.rag.dependencies import check_rag_dependencies
    from assemblyzero.rag.librarian import LibrarianNode

    # Check if RAG is available
    available, msg = check_rag_dependencies()
    if not available:
        logger.info("[Historian] RAG dependencies not available: %s", msg)
        return {"history_status": "unavailable", "history_matches": [], "history_context": ""}

    librarian = LibrarianNode()
    is_ready, status = librarian.check_availability()
    if not is_ready:
        logger.info("[Historian] Librarian not ready: %s", status)
        return {"history_status": "unavailable", "history_matches": [], "history_context": ""}

    # Query with a low threshold to get all candidates, then classify ourselves
    docs = librarian.retrieve(brief_content, threshold=0.0)

    if not docs:
        return {"history_status": "low_similarity", "history_matches": [], "history_context": ""}

    # Serialize matches for state
    matches = [doc.to_dict() for doc in docs]

    # Classify by highest score
    top_score = docs[0].score

    if top_score >= HIGH_THRESHOLD:
        context = _format_history_context(docs)
        print(f"\n  [Historian] HIGH similarity ({top_score:.2f}) — similar past work found!")
        for doc in docs:
            if doc.score >= MEDIUM_THRESHOLD:
                print(f"    - {doc.file_path} ({doc.score:.2f}): {doc.section}")
        return {
            "history_status": "high_similarity",
            "history_matches": matches,
            "history_context": context,
        }

    if top_score >= MEDIUM_THRESHOLD:
        context = _format_history_context(docs)
        print(f"\n  [Historian] Medium similarity ({top_score:.2f}) — related past work found")
        return {
            "history_status": "medium_similarity",
            "history_matches": matches,
            "history_context": context,
        }

    logger.info("[Historian] Low similarity (%s) — no relevant past work", f"{top_score:.2f}")
    return {"history_status": "low_similarity", "history_matches": matches, "history_context": ""}


def _format_history_context(docs) -> str:
    """Format retrieved docs as context for the draft node."""
    lines = ["## Past Work References (from RAG)", ""]
    lines.append("The following past work may be relevant to this issue. "
                 "Reference or link to it where appropriate, and avoid duplicating solved problems.")
    lines.append("")

    for doc in docs:
        if doc.score >= MEDIUM_THRESHOLD:
            lines.append(f"### {doc.file_path} (score: {doc.score:.2f})")
            lines.append(f"**Section:** {doc.section}")
            lines.append(f"**Type:** {doc.doc_type}")
            lines.append("")
            # Truncate long snippets
            snippet = doc.content_snippet
            if len(snippet) > 500:
                snippet = snippet[:500] + "..."
            lines.append(snippet)
            lines.append("")

    return "\n".join(lines)


def handle_historian_decision(decision: str) -> dict[str, Any]:
    """Handle human decision on high-similarity matches.

    Args:
        decision: One of "abort", "link", "ignore".

    Returns:
        State updates based on decision.
    """
    decision = decision.lower().strip()

    if decision == "abort":
        return {
            "historian_decision": "abort",
            "error_message": "HISTORIAN_ABORT: User chose to abort — similar work already exists.",
        }
    elif decision == "link":
        return {
            "historian_decision": "link",
            # history_context is already set; draft will use it
        }
    else:
        # "ignore" or anything else — proceed without context
        return {
            "historian_decision": "ignore",
            "history_context": "",
        }
