

```python
"""Feedback window assembly for bounded verdict history.

Issue #497: Bounded Verdict History in LLD Revision Loop

Assembles a bounded feedback block from verdict history, keeping the latest
verdict verbatim and summarizing all prior verdicts. Enforces a token budget
using tiktoken.
"""

import logging
from dataclasses import dataclass

import tiktoken

from assemblyzero.workflows.requirements.verdict_summarizer import (
    VerdictSummary,
    extract_blocking_issues,
    format_summary_line,
    summarize_verdict,
)

logger = logging.getLogger(__name__)

# Module-level counter for observability
feedback_window_truncation_count: int = 0


@dataclass
class FeedbackWindow:
    """Assembled feedback block ready for prompt insertion."""

    latest_verdict_full: str
    prior_summaries: list[VerdictSummary]
    total_tokens: int
    was_truncated: bool


def count_tokens(text: str, model: str = "cl100k_base") -> int:
    """Count tokens in text using tiktoken.

    Args:
        text: String to count tokens for.
        model: Tiktoken encoding name. Default "cl100k_base".

    Returns:
        Integer token count.
    """
    if not text:
        return 0
    encoding = tiktoken.get_encoding(model)
    return len(encoding.encode(text))


def build_feedback_block(
    verdict_history: list[str],
    token_budget: int = 4000,
) -> FeedbackWindow:
    """Assemble a bounded feedback block from verdict history.

    Algorithm:
    1. If verdict_history is empty, return empty FeedbackWindow.
    2. Reserve the latest verdict verbatim.
    3. Summarize all prior verdicts (with persistence detection).
    4. Assemble: latest verdict + prior summary lines.
    5. If total tokens exceed budget, progressively drop oldest summary lines.
    6. Log warning and increment counter if truncation occurred.

    Args:
        verdict_history: List of verdict strings, ordered oldest-first.
            Index 0 = iteration 1's verdict.
        token_budget: Maximum tokens for the entire feedback block. Default 4000.

    Returns:
        FeedbackWindow dataclass with assembled content and metadata.
    """
    global feedback_window_truncation_count

    if not verdict_history:
        return FeedbackWindow(
            latest_verdict_full="",
            prior_summaries=[],
            total_tokens=0,
            was_truncated=False,
        )

    latest_verdict = verdict_history[-1]
    latest_tokens = count_tokens(latest_verdict)

    # If latest verdict alone exceeds budget, still include it (priority)
    if latest_tokens >= token_budget:
        logger.warning(
            "Latest verdict alone exceeds token budget (%d >= %d)",
            latest_tokens,
            token_budget,
        )
        feedback_window_truncation_count += 1
        return FeedbackWindow(
            latest_verdict_full=latest_verdict,
            prior_summaries=[],
            total_tokens=latest_tokens,
            was_truncated=True,
        )

    remaining_budget = token_budget - latest_tokens

    # Summarize prior verdicts
    prior_verdicts = verdict_history[:-1]
    summaries: list[VerdictSummary] = []
    prev_issues: list[str] | None = None

    for i, verdict in enumerate(prior_verdicts):
        iteration = i + 1
        summary = summarize_verdict(verdict, iteration, prior_issues=prev_issues)
        summaries.append(summary)
        prev_issues = extract_blocking_issues(verdict)

    # Build summary lines and check budget
    summary_lines = [format_summary_line(s) for s in summaries]
    summary_block = "\n".join(summary_lines)
    summary_tokens = count_tokens(summary_block)

    truncated = False
    while summary_tokens > remaining_budget and summary_lines:
        # Drop oldest summary first
        summary_lines.pop(0)
        summaries.pop(0)
        summary_block = "\n".join(summary_lines)
        summary_tokens = count_tokens(summary_block)
        truncated = True

    if truncated:
        logger.warning(
            "Feedback window truncated: dropped oldest summaries to fit budget"
        )
        feedback_window_truncation_count += 1

    total_tokens = latest_tokens + summary_tokens

    return FeedbackWindow(
        latest_verdict_full=latest_verdict,
        prior_summaries=summaries,
        total_tokens=total_tokens,
        was_truncated=truncated,
    )


def render_feedback_markdown(window: FeedbackWindow) -> str:
    """Render a FeedbackWindow as a markdown string for prompt insertion.

    Output format:
        ## Review Feedback (Iteration {N})
        {latest_verdict_full}

        ## Prior Review Summary
        - Iteration 1: BLOCKED — 3 issues (0 persists; 3 new)
        - Iteration 2: BLOCKED — 2 issues (1 persists: "..."; 1 new)

    If no prior summaries exist, the "Prior Review Summary" section is omitted.
    If verdict_history was empty, returns empty string.

    Args:
        window: FeedbackWindow to render.

    Returns:
        Markdown string ready for prompt insertion.
    """
    if not window.latest_verdict_full:
        return ""

    # Determine current iteration number:
    # latest is the Nth verdict where N = len(prior_summaries) + 1
    current_iteration = len(window.prior_summaries) + 1

    parts: list[str] = []
    parts.append(f"## Review Feedback (Iteration {current_iteration})")
    parts.append(window.latest_verdict_full)

    if window.prior_summaries:
        parts.append("")  # blank line separator
        parts.append("## Prior Review Summary")
        for summary in window.prior_summaries:
            parts.append(format_summary_line(summary))

    return "\n".join(parts)
```
