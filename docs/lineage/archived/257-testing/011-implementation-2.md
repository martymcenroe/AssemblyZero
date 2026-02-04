# File: agentos/workflows/requirements/parsers/draft_updater.py

```python
"""Draft updater for applying verdict resolutions and suggestions.

Issue #257: Review Node Should Update Draft with Resolved Open Questions

Updates LLD drafts by:
- Marking open questions as resolved (- [ ] -> - [x])
- Appending resolution text
- Adding Reviewer Suggestions section for Tier 3 items
"""

import logging
import re
from typing import Optional

from agentos.workflows.requirements.parsers.verdict_parser import (
    ResolvedQuestion,
    Tier3Suggestion,
    VerdictParseResult,
)

logger = logging.getLogger(__name__)


def update_draft(
    draft: str, verdict_result: VerdictParseResult
) -> tuple[str, list[str]]:
    """Update draft with all verdict content (resolutions and suggestions).

    This is the main entry point for updating a draft with verdict results.

    Args:
        draft: The original draft content.
        verdict_result: Parsed verdict containing resolutions and suggestions.

    Returns:
        Tuple of (updated_draft, warnings).
    """
    warnings = []

    # Only update for APPROVED verdicts
    if verdict_result.verdict_status != "APPROVED":
        return draft, ["Verdict not APPROVED, draft unchanged"]

    # Apply resolutions
    updated_draft, resolution_warnings = update_draft_with_resolutions(
        draft, verdict_result.resolutions
    )
    warnings.extend(resolution_warnings)

    # Apply suggestions
    if verdict_result.suggestions:
        updated_draft, suggestion_warnings = update_draft_with_suggestions(
            updated_draft, verdict_result.suggestions
        )
        warnings.extend(suggestion_warnings)

    return updated_draft, warnings


def update_draft_with_resolutions(
    draft: str, resolutions: list[ResolvedQuestion]
) -> tuple[str, list[str]]:
    """Update draft open questions with resolutions.

    Changes unchecked checkboxes to checked and appends resolution text:
    - [ ] Question text
    becomes:
    - [x] Question text **RESOLVED:** Resolution text

    Args:
        draft: The original draft content.
        resolutions: List of resolved questions to apply.

    Returns:
        Tuple of (updated_draft, warnings).
    """
    if not resolutions:
        return draft, []

    warnings = []
    updated_draft = draft

    for resolution in resolutions:
        # Try to find and update the question in the draft
        updated, found = _update_single_question(
            updated_draft, resolution.question_text, resolution.resolution_text
        )

        if found:
            updated_draft = updated
        else:
            warning = f"Question not found in draft: {resolution.question_text[:50]}..."
            warnings.append(warning)
            logger.warning(warning)

    return updated_draft, warnings


def _update_single_question(
    draft: str, question_text: str, resolution_text: str
) -> tuple[str, bool]:
    """Update a single open question with its resolution.

    Args:
        draft: Current draft content.
        question_text: The question to find (without checkbox prefix).
        resolution_text: The resolution to add.

    Returns:
        Tuple of (updated_draft, was_found).
    """
    # Normalize question text for matching (remove trailing ?)
    question_normalized = question_text.strip().rstrip("?")

    # Build pattern to match the question (with flexibility for markdown variations)
    # Match: - [ ] Question text (possibly with trailing ?)
    escaped_question = re.escape(question_normalized)

    # Pattern that handles various question formats
    pattern = re.compile(
        rf"^(\s*-\s*)\[ \](\s+{escaped_question}\??)\s*$",
        re.MULTILINE | re.IGNORECASE,
    )

    match = pattern.search(draft)
    if match:
        # Check if already resolved (idempotency)
        full_line = match.group(0)
        if "[x]" in draft[max(0, match.start() - 10) : match.end() + 50].lower():
            # Already resolved, check if resolution text already present
            if "**RESOLVED:**" in draft[match.start() : match.end() + 200]:
                return draft, True  # Already done, no change needed

        # Build replacement: - [x] Question **RESOLVED:** Answer
        prefix = match.group(1)
        question_part = match.group(2).strip()
        replacement = f"{prefix}[x] {question_part} **RESOLVED:** {resolution_text}"

        updated = draft[: match.start()] + replacement + draft[match.end() :]
        return updated, True

    # Try broader match - question might have slightly different formatting
    # Search for just the core question text
    if question_normalized.lower() in draft.lower():
        # Found the text, try to find its line
        lines = draft.split("\n")
        for i, line in enumerate(lines):
            if question_normalized.lower() in line.lower() and "- [ ]" in line:
                # Found it - update this line
                new_line = line.replace("- [ ]", "- [x]")
                if "**RESOLVED:**" not in new_line:
                    new_line = f"{new_line.rstrip()} **RESOLVED:** {resolution_text}"
                lines[i] = new_line
                return "\n".join(lines), True

    return draft, False


def update_draft_with_suggestions(
    draft: str, suggestions: list[Tier3Suggestion]
) -> tuple[str, list[str]]:
    """Add Tier 3 suggestions as a new section to the draft.

    Appends a "## Reviewer Suggestions" section at the end of the draft
    (before any existing footer content).

    Args:
        draft: The original draft content.
        suggestions: List of Tier 3 suggestions to add.

    Returns:
        Tuple of (updated_draft, warnings).
    """
    if not suggestions:
        return draft, []

    warnings = []

    # Check if suggestions section already exists (idempotency)
    if "## Reviewer Suggestions" in draft:
        # Already has suggestions, don't duplicate
        return draft, ["Reviewer Suggestions section already exists"]

    # Build suggestions section
    suggestions_section = "\n\n## Reviewer Suggestions\n\n"
    suggestions_section += "*These are Tier 3 suggestions from the reviewer - optional improvements that don't block approval.*\n\n"

    for suggestion in suggestions:
        section_ref = f" [{suggestion.section}]" if suggestion.section else ""
        priority_ref = f" (Priority: {suggestion.priority})" if suggestion.priority else ""
        suggestions_section += f"- {suggestion.suggestion_text}{section_ref}{priority_ref}\n"

    # Find insertion point - before footer if present, otherwise at end
    # Common footer patterns: ---, Review Evidence, etc.
    footer_patterns = [
        r"\n---\s*\n",  # Horizontal rule
        r"\n## Review Evidence\n",  # Review evidence section
        r"\n<!-- Generated by",  # Comment footer
    ]

    insertion_point = len(draft)
    for pattern in footer_patterns:
        match = re.search(pattern, draft)
        if match and match.start() < insertion_point:
            insertion_point = match.start()

    # Insert suggestions section
    updated_draft = draft[:insertion_point] + suggestions_section + draft[insertion_point:]

    return updated_draft, warnings


def get_updated_draft_from_verdict(
    draft: str, verdict_content: str
) -> tuple[str, list[str]]:
    """Convenience function to parse verdict and update draft in one call.

    Args:
        draft: The original draft content.
        verdict_content: Raw verdict text from Gemini.

    Returns:
        Tuple of (updated_draft, warnings).
    """
    from agentos.workflows.requirements.parsers.verdict_parser import parse_verdict

    verdict_result = parse_verdict(verdict_content)
    return update_draft(draft, verdict_result)
```