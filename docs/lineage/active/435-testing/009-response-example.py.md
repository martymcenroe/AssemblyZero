```python
"""LLD audit tracking functions.

Issue #435: Provides detect_gemini_review, embed_review_evidence,
load_lld_tracking, and update_lld_status for LLD audit tracking.

Source: assemblyzero/workflows/requirements/audit.py (adapted signatures
per LLD-435 specification for testability).
"""

import json
import re
from pathlib import Path
from typing import Any, Optional

# Valid status values for LLD tracking entries
VALID_STATUSES = {"draft", "reviewed", "approved", "rejected"}

# Marker used to detect Gemini review sections
_GEMINI_REVIEW_MARKER = "### Gemini Review"

# Section heading for embedded review evidence
_EVIDENCE_HEADING = "## Review Evidence"


def detect_gemini_review(lld_content: str) -> bool:
    """Detect whether an LLD contains a Gemini review section.

    Args:
        lld_content: Full text content of an LLD markdown file.

    Returns:
        True if the content contains a '### Gemini Review' section,
        False otherwise (including empty/malformed input).
    """
    if not lld_content:
        return False
    return _GEMINI_REVIEW_MARKER in lld_content


def embed_review_evidence(lld_content: str, evidence: dict[str, Any]) -> str:
    """Embed review evidence into LLD content, returning updated content.

    Adds or updates a '## Review Evidence' section containing a summary
    table and comments list derived from the evidence dict.

    Args:
        lld_content: Original LLD markdown content.
        evidence: Dict with keys: reviewer, verdict, comments, timestamp,
                  and optionally model.

    Returns:
        Updated LLD content string with embedded evidence section.

    Raises:
        ValueError: If evidence is empty or missing required keys.
        ValueError: If lld_content is empty and evidence is empty.
    """
    if not evidence:
        if not lld_content:
            raise ValueError("Both lld_content and evidence are empty")
        return lld_content

    # Validate required keys
    required_keys = {"reviewer", "verdict", "timestamp"}
    missing = required_keys - set(evidence.keys())
    if missing:
        raise ValueError(f"Evidence missing required keys: {missing}")

    # Build the evidence section
    lines: list[str] = []
    lines.append("")
    lines.append(_EVIDENCE_HEADING)
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|-------|-------|")
    lines.append(f"| Reviewer | {evidence['reviewer']} |")
    lines.append(f"| Verdict | {evidence['verdict']} |")

    model: Optional[str] = evidence.get("model")
    if model:
        lines.append(f"| Model | {model} |")

    lines.append(f"| Timestamp | {evidence['timestamp']} |")

    comments: list[str] = evidence.get("comments", [])
    if comments:
        lines.append("")
        lines.append("### Comments")
        for comment in comments:
            lines.append(f"- {comment}")

    lines.append("")
    evidence_block = "\n".join(lines)

    # Idempotency: if evidence section already exists, replace it
    if _EVIDENCE_HEADING in lld_content:
        # Remove the existing evidence section (from heading to next ## or end)
        pattern = re.compile(
            rf"(\n?){re.escape(_EVIDENCE_HEADING)}.*?(?=\n## |\Z)",
            re.DOTALL,
        )
        lld_content = pattern.sub("", lld_content)

    # Append evidence block
    return lld_content.rstrip("\n") + "\n" + evidence_block


def load_lld_tracking(tracking_path: Path) -> dict[str, Any]:
    """Load LLD tracking data from a JSON file.

    Args:
        tracking_path: Path to the tracking JSON file.

    Returns:
        Parsed dict from the JSON file. Returns empty dict if the file
        does not exist, is empty, or contains invalid JSON.
    """
    if not tracking_path.exists():
        return {}

    content = tracking_path.read_text(encoding="utf-8")
    if not content.strip():
        return {}

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return {}

    if not isinstance(data, dict):
        return {}

    return data


def update_lld_status(
    tracking_path: Path,
    issue_id: int,
    status: str,
    **kwargs: Any,
) -> None:
    """Update the status of an LLD entry in the tracking file.

    Creates the file if it doesn't exist. Adds a new entry if the
    issue_id is not already tracked. Merges any extra keyword arguments
    into the entry.

    Args:
        tracking_path: Path to the tracking JSON file.
        issue_id: GitHub issue number.
        status: New status value. Must be one of: draft, reviewed,
                approved, rejected.
        **kwargs: Additional fields to merge into the entry
                  (e.g., gemini_reviewed, review_verdict).

    Raises:
        ValueError: If status is not a recognised value.
    """
    if status not in VALID_STATUSES:
        raise ValueError(
            f"Invalid status {status!r}. Must be one of: {', '.join(sorted(VALID_STATUSES))}"
        )

    # Load existing data (or start fresh)
    if tracking_path.exists():
        content = tracking_path.read_text(encoding="utf-8")
        if content.strip():
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                data = {}
        else:
            data = {}
    else:
        data = {}

    key = str(issue_id)

    # Get or create entry
    entry: dict[str, Any] = data.get(key, {"issue_id": issue_id})
    entry["status"] = status

    # Merge kwargs
    for k, v in kwargs.items():
        entry[k] = v

    data[key] = entry

    # Ensure parent directory exists
    tracking_path.parent.mkdir(parents=True, exist_ok=True)

    # Write back
    tracking_path.write_text(
        json.dumps(data, indent=2) + "\n",
        encoding="utf-8",
    )
```
