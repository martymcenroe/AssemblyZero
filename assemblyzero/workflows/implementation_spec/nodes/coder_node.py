"""Coder node: codebase context injection for N3_Coder prompt construction.

Issue #92: Codebase Retrieval System (RAG Injection)

Provides a composable utility that retrieves relevant codebase context
from the RAG vector store and injects it into the code generation prompt.
Designed to be called from whichever workflow node constructs the N3_Coder
system prompt.

Fail-open: if retrieval fails for any reason, the original prompt is
returned unchanged and a warning is logged.
"""

from __future__ import annotations

import logging


logger = logging.getLogger(__name__)


def inject_codebase_context(
    base_prompt: str,
    lld_content: str,
    token_budget: int = 4096,
) -> str:
    """Inject codebase context into N3_Coder's system prompt.

    1. Call retrieve_codebase_context(lld_content)
    2. If context is non-empty, prepend to base_prompt
    3. If retrieval fails (exception), log warning and return base_prompt unchanged

    Args:
        base_prompt: The original system prompt for code generation.
        lld_content: The LLD content to extract keywords from.
        token_budget: Maximum tokens for the codebase context section.

    Returns:
        Modified prompt with codebase context prepended, or original prompt
        on failure or no matches.
    """
    try:
        from assemblyzero.rag.codebase_retrieval import retrieve_codebase_context  # noqa: PLC0415

        context = retrieve_codebase_context(
            lld_content,
            token_budget=token_budget,
        )

        if context["formatted_text"]:
            return context["formatted_text"] + "\n" + base_prompt

    except Exception as exc:
        logger.warning("Codebase retrieval failed: %s", exc)

    return base_prompt
