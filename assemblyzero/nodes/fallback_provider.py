"""Fallback provider with pass-through instrumentation.

Issue #774: Tries Claude CLI first, then Anthropic API.
Passes instrumentation to whichever provider fires.
"""

import logging
from typing import TYPE_CHECKING, Optional

from assemblyzero.telemetry.llm_call_record import LLMInputParams

if TYPE_CHECKING:
    from assemblyzero.telemetry.store import CallStore

logger = logging.getLogger(__name__)


def call_with_fallback_instrumentation(
    prompt: str,
    *,
    primary_model: str = "claude:opus",
    fallback_model: str = "claude-sonnet-4-6",
    working_dir: str = ".",
    primary_store: Optional["CallStore"] = None,
    workflow: str = "unknown",
    node: str = "unknown",
    issue_number: Optional[int] = None,
) -> str:
    """Try Claude CLI first, then Anthropic API; passes instrumentation to whichever fires.

    Issue #774: Fallback provider with instrumentation pass-through.
    """
    from assemblyzero.core.claude_client import call_claude_with_instrumentation
    from assemblyzero.nodes.anthropic_provider import call_anthropic_with_instrumentation

    try:
        return call_claude_with_instrumentation(
            prompt,
            model=primary_model,
            working_dir=working_dir,
            store=primary_store,
            workflow=workflow,
            node=node,
            issue_number=issue_number,
        )
    except Exception as primary_err:
        logger.warning(
            "Primary provider (CLI, model=%s) failed: %s. Falling back to Anthropic API.",
            primary_model,
            primary_err,
        )
        return call_anthropic_with_instrumentation(
            prompt,
            model=fallback_model,
            store=primary_store,
            workflow=workflow,
            node=node,
            issue_number=issue_number,
        )