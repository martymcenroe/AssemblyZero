

```python
"""Verdict summarization for bounded feedback windows.

Issue #497: Bounded Verdict History in LLD Revision Loop

Summarizes prior verdicts into structured one-line summaries with
persistence tracking. Supports both JSON (#494) and text verdict formats.
"""

import json
import logging
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class VerdictSummary:
    """Compressed representation of a single prior verdict."""

    iteration: int
    verdict: str
    issue_count: int
    persisting_issues: list[str]
    new_issues: list[str]


def extract_blocking_issues(verdict_text: str) -> list[str]:
    """Extract blocking issue descriptions from a verdict string.

    Auto-detects format:
    - JSON format (#494): parses ``blocking_issues`` array from JSON
    - Text format (current): regex extracts lines matching ``[BLOCKING]``
      or ``**BLOCKING**`` patterns

    Falls back to text parsing with logger.warning() if JSON detection fails.

    Args:
        verdict_text: Raw verdict string (text or JSON format).

    Returns:
        List of blocking issue description strings. Empty list if no issues
        found or if verdict_text is empty/None.
    """
    if not verdict_text or not verdict_text.strip():
        return []

    stripped = verdict_text.strip()

    # Attempt JSON parsing first
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
            if isinstance(data, dict) and "blocking_issues" in data:
                issues = data["blocking_issues"]
                if isinstance(issues, list):
                    return [
                        item["description"]
                        for item in issues
                        if isinstance(item, dict) and "description" in item
                    ]
            return []
        except (json.JSONDecodeError, KeyError, TypeError):
            logger.warning(
                "Verdict text starts with '{' but failed JSON parsing; "
                "falling back to text extraction"
            )

    # Text format extraction
    # Match patterns like:
    #   - **[BLOCKING]** Description here
    #   - **BLOCKING** Description here
    #   - [BLOCKING] Description here
    pattern = r"-\s*\*{0,2}\[?BLOCKING\]?\*{0,2}\s+(.+)"
    matches = re.findall(pattern, stripped)
    return [m.strip() for m in matches]


def _extract_verdict_status(verdict_text: str) -> str:
    """Extract the verdict status string from a verdict.

    Args:
        verdict_text: Raw verdict text.

    Returns:
        One of "BLOCKED", "APPROVED", or "UNKNOWN".
    """
    if not verdict_text or not verdict_text.strip():
        return "UNKNOWN"

    stripped = verdict_text.strip()

    # Try JSON first
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
            if isinstance(data, dict) and "verdict" in data:
                verdict_val = str(data["verdict"]).upper()
                if verdict_val in ("BLOCKED", "APPROVED"):
                    return verdict_val
                return "UNKNOWN"
        except (json.JSONDecodeError, KeyError, TypeError):
            pass  # Fall through to text parsing

    # Text format: look for "Verdict: BLOCKED" or "Verdict: APPROVED"
    upper = stripped.upper()
    if "APPROVED" in upper:
        return "APPROVED"
    if "BLOCKED" in upper:
        return "BLOCKED"
    return "UNKNOWN"


def identify_persisting_issues(
    current_issues: list[str],
    prior_issues: list[str],
    similarity_threshold: float = 0.8,
) -> tuple[list[str], list[str]]:
    """Classify current issues as persisting or new relative to prior iteration.

    Uses normalized string comparison (lowered, stripped, punctuation-removed)
    to detect when the same issue reappears across iterations.

    Args:
        current_issues: Issues from the current verdict.
        prior_issues: Issues from the immediately preceding verdict.
        similarity_threshold: Minimum ratio for SequenceMatcher to consider
            two issue strings as "the same issue". Default 0.8.

    Returns:
        Tuple of (persisting_issues, new_issues).
    """
    if not current_issues:
        return [], []
    if not prior_issues:
        return [], list(current_issues)

    def _normalize(text: str) -> str:
        """Lowercase, strip, remove punctuation for comparison."""
        cleaned = re.sub(r"[^\w\s]", "", text.lower().strip())
        return cleaned

    persisting: list[str] = []
    new: list[str] = []

    normalized_prior = [_normalize(p) for p in prior_issues]

    for issue in current_issues:
        norm_current = _normalize(issue)
        is_persisting = False
        for norm_prior in normalized_prior:
            ratio = SequenceMatcher(None, norm_current, norm_prior).ratio()
            if ratio >= similarity_threshold:
                is_persisting = True
                break
        if is_persisting:
            persisting.append(issue)
        else:
            new.append(issue)

    return persisting, new


def summarize_verdict(
    verdict_text: str,
    iteration: int,
    prior_issues: Optional[list[str]] = None,
) -> VerdictSummary:
    """Produce a structured summary of a single verdict.

    Args:
        verdict_text: Raw verdict string.
        iteration: 1-based iteration number.
        prior_issues: Blocking issues from the previous iteration
            (for persistence detection). None for iteration 1 (no prior).

    Returns:
        VerdictSummary dataclass.
    """
    verdict_status = _extract_verdict_status(verdict_text)
    current_issues = extract_blocking_issues(verdict_text)
    issue_count = len(current_issues)

    if prior_issues is not None:
        persisting, new = identify_persisting_issues(current_issues, prior_issues)
    else:
        persisting = []
        new = list(current_issues)

    return VerdictSummary(
        iteration=iteration,
        verdict=verdict_status,
        issue_count=issue_count,
        persisting_issues=persisting,
        new_issues=new,
    )


def format_summary_line(summary: VerdictSummary) -> str:
    """Render a VerdictSummary as a single human-readable markdown line.

    Format:
        - Iteration {N}: {VERDICT} — {count} issues ({M} persists: "desc1", "desc2"; {K} new)

    Args:
        summary: VerdictSummary to format.

    Returns:
        Single markdown line string.
    """
    persist_count = len(summary.persisting_issues)
    new_count = len(summary.new_issues)

    if persist_count > 0:
        persist_descs = ", ".join(f'"{desc}"' for desc in summary.persisting_issues)
        persist_part = f"{persist_count} persists: {persist_descs}"
    else:
        persist_part = "0 persists"

    return (
        f"- Iteration {summary.iteration}: {summary.verdict} \u2014 "
        f"{summary.issue_count} issues ({persist_part}; {new_count} new)"
    )
```
