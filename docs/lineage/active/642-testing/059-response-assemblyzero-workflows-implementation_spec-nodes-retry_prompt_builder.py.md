```python
"""Retry prompt builder with tiered context pruning.

Issue #642: Implement tiered context pruning in build_retry_prompt() so that
retry 1 sends the full LLD while retry 2+ sends only the relevant LLD file
spec section, the error message, and a truncated previous-attempt snippet.
"""

from __future__ import annotations

import logging
from typing import TypedDict

import tiktoken

from assemblyzero.utils.lld_section_extractor import (
    _split_lld_into_sections,
    extract_file_spec_section,
)

logger = logging.getLogger(__name__)

# Module-level constants
SNIPPET_MAX_LINES: int = 60
"""Maximum lines retained from previous attempt snippet (tail)."""

TIER_BOUNDARY: int = 2
"""retry_count >= this value triggers Tier 2 pruning."""

# Prompt template fragments
_SYSTEM_PREAMBLE_TIER1: str = (
    "You are retrying code generation for a file that previously failed.\n"
    "Below is the full design specification and the error from the previous attempt.\n"
    "Generate a corrected implementation.\n"
)

_SYSTEM_PREAMBLE_TIER2: str = (
    "You are implementing a fix for a previous failed attempt.\n"
    "Below is only the relevant specification section for the target file,\n"
    "the error from the previous attempt, and the last portion of your\n"
    "previous output. Generate a corrected implementation.\n"
)

_SPEC_SECTION_HEADER: str = "\n## Relevant Specification\n\n"
_FULL_LLD_HEADER: str = "\n## Full LLD Context\n\n"
_TARGET_FILE_HEADER: str = "\n## Target File\n"
_ERROR_HEADER: str = "\n## Error from Previous Attempt\n"
_PREVIOUS_ATTEMPT_HEADER: str = "\n## Previous Attempt (last {n} lines)\n"


class RetryContext(TypedDict):
    """All information needed to build a retry prompt at any tier."""

    lld_content: str
    target_file: str
    error_message: str
    retry_count: int
    previous_attempt_snippet: str | None
    completed_files: list[str]


class PrunedRetryPrompt(TypedDict):
    """Output of build_retry_prompt() — the assembled prompt and metadata."""

    prompt_text: str
    tier: int
    estimated_tokens: int
    context_sections_included: list[str]


def build_retry_prompt(ctx: RetryContext) -> PrunedRetryPrompt:
    """Build a retry prompt applying tiered context pruning.

    Tier 1 (retry_count == 1): Full LLD + target file spec + error.
    Tier 2 (retry_count >= 2): Relevant file spec section only + error
      + truncated previous attempt snippet.

    Args:
        ctx: RetryContext containing LLD, target file, error, and retry metadata.

    Returns:
        PrunedRetryPrompt with assembled prompt text, tier used, and token estimate.

    Raises:
        ValueError: If retry_count < 1, lld_content is empty, target_file is empty,
            or error_message is empty.
    """
    if ctx["retry_count"] < 1:
        raise ValueError("retry_count must be >= 1")
    if not ctx["lld_content"].strip():
        raise ValueError("lld_content must not be empty")
    if not ctx["target_file"].strip():
        raise ValueError("target_file must not be empty")
    if not ctx["error_message"].strip():
        raise ValueError("error_message must not be empty")

    if ctx["retry_count"] < TIER_BOUNDARY:
        tier = 1
        prompt_text = _build_tier1_prompt(ctx)
        sections_included = ["full_lld (minus completed_files)", "error_message"]
    else:
        if ctx["previous_attempt_snippet"] is None:
            raise ValueError("Tier 2 requires previous_attempt_snippet")
        tier = 2
        prompt_text = _build_tier2_prompt(ctx)
        # Check if fallback occurred (tier2 falls back to tier1 on extraction failure)
        if _FULL_LLD_HEADER in prompt_text:
            tier = 1
            sections_included = [
                "full_lld (minus completed_files) [fallback]",
                "error_message",
            ]
        else:
            sections_included = [
                f"Section for {ctx['target_file']}",
                "error_message",
                "previous_attempt_snippet (truncated)",
            ]

    estimated_tokens = _estimate_tokens(prompt_text)

    return PrunedRetryPrompt(
        prompt_text=prompt_text,
        tier=tier,
        estimated_tokens=estimated_tokens,
        context_sections_included=sections_included,
    )


def _build_tier1_prompt(ctx: RetryContext) -> str:
    """Assemble full-LLD retry prompt (current behavior, Retry 1).

    Strips sections for completed files. Includes full LLD + target file
    section call-out + error message.

    Args:
        ctx: Full RetryContext.

    Returns:
        Assembled prompt string.
    """
    lld = _strip_completed_sections(ctx["lld_content"], ctx["completed_files"])

    parts: list[str] = [
        _SYSTEM_PREAMBLE_TIER1,
        _FULL_LLD_HEADER,
        lld,
        _TARGET_FILE_HEADER,
        ctx["target_file"],
        _ERROR_HEADER,
        ctx["error_message"],
    ]
    return "".join(parts)


def _build_tier2_prompt(ctx: RetryContext) -> str:
    """Assemble minimal retry prompt (Retry 2+).

    Includes only the relevant file spec section, error, and truncated
    previous attempt snippet. Falls back to tier 1 if section extraction fails.

    Args:
        ctx: Full RetryContext; previous_attempt_snippet must not be None.

    Returns:
        Assembled prompt string.

    Raises:
        ValueError: If previous_attempt_snippet is None.
    """
    if ctx["previous_attempt_snippet"] is None:
        raise ValueError("Tier 2 requires previous_attempt_snippet")

    section = extract_file_spec_section(ctx["lld_content"], ctx["target_file"])
    if section is None:
        logger.warning(
            "Tier 2 section extraction failed; falling back to tier 1 for file=%s",
            ctx["target_file"],
        )
        return _build_tier1_prompt(ctx)

    truncated = _truncate_snippet(ctx["previous_attempt_snippet"])
    snippet_lines = len(truncated.splitlines())

    parts: list[str] = [
        _SYSTEM_PREAMBLE_TIER2,
        _SPEC_SECTION_HEADER,
        section["section_body"],
        _TARGET_FILE_HEADER,
        ctx["target_file"],
        _ERROR_HEADER,
        ctx["error_message"],
        _PREVIOUS_ATTEMPT_HEADER.format(n=snippet_lines),
        truncated,
    ]
    return "".join(parts)


def _truncate_snippet(snippet: str, max_lines: int = SNIPPET_MAX_LINES) -> str:
    """Truncate a previous-attempt snippet to at most max_lines lines.

    Keeps the final max_lines lines (tail) as they are most relevant
    to the failure point.

    Args:
        snippet: Raw previous attempt text.
        max_lines: Maximum number of lines to retain.

    Returns:
        Truncated snippet string with a leading "..." if lines were dropped.
    """
    lines = snippet.splitlines()
    if len(lines) <= max_lines:
        return snippet
    tail = lines[-max_lines:]
    return "...\n" + "\n".join(tail)


def _estimate_tokens(text: str) -> int:
    """Estimate token count of text using tiktoken cl100k_base encoding.

    Args:
        text: String to estimate.

    Returns:
        Integer token count estimate. Returns -1 if encoding fails.
    """
    if not text:
        return 0
    try:
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        logger.warning("tiktoken encoding failed; returning -1 sentinel")
        return -1


def _strip_completed_sections(lld_content: str, completed_files: list[str]) -> str:
    """Remove LLD sections that correspond to already-completed files.

    Args:
        lld_content: Full LLD markdown.
        completed_files: List of file paths already completed.

    Returns:
        LLD content with completed file sections removed.
    """
    if not completed_files:
        return lld_content

    sections = _split_lld_into_sections(lld_content)
    kept_parts: list[str] = []

    for _heading, body in sections:
        # Check if this section is about a completed file
        is_completed = False
        for completed in completed_files:
            normalized = completed.replace("\\", "/")
            if normalized in body:
                is_completed = True
                break
        if not is_completed:
            kept_parts.append(body)

    return "".join(kept_parts)
```
