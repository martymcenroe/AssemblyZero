Now I have a good understanding of the codebase. Let me create the implementation files. Based on the LLD and test requirements, I need to:

1. Create `agentos/workflows/requirements/parsers/__init__.py` - Module init
2. Create `agentos/workflows/requirements/parsers/verdict_parser.py` - Parse resolutions and suggestions from verdicts
3. Create `agentos/workflows/requirements/parsers/draft_updater.py` - Update draft with parsed verdict content
4. Update the test file with proper implementation

Let me create all the necessary implementation files:

```python
# File: agentos/workflows/requirements/parsers/__init__.py

"""Parsers module for verdict and draft processing.

Issue #257: Review Node Should Update Draft with Resolved Open Questions

This module provides utilities for:
- Parsing resolved questions and Tier 3 suggestions from Gemini verdicts
- Updating LLD drafts with resolutions and suggestions
"""

from agentos.workflows.requirements.parsers.verdict_parser import (
    ResolvedQuestion,
    Tier3Suggestion,
    VerdictParseResult,
    parse_verdict,
)
from agentos.workflows.requirements.parsers.draft_updater import (
    update_draft_with_resolutions,
    update_draft_with_suggestions,
    update_draft,
)

__all__ = [
    "ResolvedQuestion",
    "Tier3Suggestion",
    "VerdictParseResult",
    "parse_verdict",
    "update_draft_with_resolutions",
    "update_draft_with_suggestions",
    "update_draft",
]
```

```python
# File: agentos/workflows/requirements/parsers/verdict_parser.py

"""Verdict parser for extracting resolutions and suggestions.

Issue #257: Review Node Should Update Draft with Resolved Open Questions

Parses Gemini review verdicts to extract:
- Resolved open questions with their resolution text
- Tier 3 suggestions for improvement
"""

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ResolvedQuestion:
    """A resolved open question from a verdict.

    Attributes:
        question_text: The original question text (without checkbox).
        resolution_text: The reviewer's resolution/answer.
        original_line: The full original line from the draft (for matching).
    """

    question_text: str
    resolution_text: str
    original_line: str = ""


@dataclass
class Tier3Suggestion:
    """A Tier 3 suggestion from a verdict.

    Tier 3 suggestions are optional improvements that don't block approval.

    Attributes:
        suggestion_text: The suggestion content.
        section: Optional section the suggestion applies to.
        priority: Priority level if specified (e.g., "low", "medium").
    """

    suggestion_text: str
    section: str = ""
    priority: str = ""


@dataclass
class VerdictParseResult:
    """Result of parsing a verdict.

    Attributes:
        verdict_status: The verdict status (APPROVED, BLOCKED, etc.).
        resolutions: List of resolved questions.
        suggestions: List of Tier 3 suggestions.
        raw_verdict: The original verdict text.
        parse_warnings: Any warnings encountered during parsing.
    """

    verdict_status: str
    resolutions: list[ResolvedQuestion] = field(default_factory=list)
    suggestions: list[Tier3Suggestion] = field(default_factory=list)
    raw_verdict: str = ""
    parse_warnings: list[str] = field(default_factory=list)


def parse_verdict(verdict_content: str) -> VerdictParseResult:
    """Parse a Gemini verdict to extract resolutions and suggestions.

    Args:
        verdict_content: The full verdict text from Gemini.

    Returns:
        VerdictParseResult containing parsed data.
    """
    if not verdict_content:
        return VerdictParseResult(
            verdict_status="BLOCKED",
            raw_verdict="",
            parse_warnings=["Empty verdict content"],
        )

    result = VerdictParseResult(
        verdict_status=_parse_verdict_status(verdict_content),
        raw_verdict=verdict_content,
    )

    # Only extract resolutions for APPROVED verdicts
    if result.verdict_status == "APPROVED":
        result.resolutions = _extract_resolutions(verdict_content)
        result.suggestions = _extract_tier3_suggestions(verdict_content)

    return result


def _parse_verdict_status(verdict_content: str) -> str:
    """Parse verdict status from content.

    Args:
        verdict_content: The verdict text.

    Returns:
        "APPROVED" or "BLOCKED".
    """
    verdict_upper = verdict_content.upper()

    # Check for checked APPROVED checkbox
    if re.search(r"\[X\]\s*\**APPROVED\**", verdict_upper):
        return "APPROVED"
    # Check for checked REVISE checkbox
    if re.search(r"\[X\]\s*\**REVISE\**", verdict_upper):
        return "BLOCKED"
    # Check for checked DISCUSS checkbox
    if re.search(r"\[X\]\s*\**DISCUSS\**", verdict_upper):
        return "BLOCKED"
    # Fallback: Look for explicit keywords
    if "VERDICT: APPROVED" in verdict_upper:
        return "APPROVED"
    if "VERDICT: BLOCKED" in verdict_upper or "VERDICT: REVISE" in verdict_upper:
        return "BLOCKED"

    # Default to BLOCKED
    return "BLOCKED"


def _extract_resolutions(verdict_content: str) -> list[ResolvedQuestion]:
    """Extract resolved questions from verdict.

    Looks for patterns like:
    - [x] ~~Question text~~ **RESOLVED:** Resolution text
    - Q1: Question? **RESOLVED:** Answer
    - Open Questions Resolved section with checkboxes

    Args:
        verdict_content: The verdict text.

    Returns:
        List of ResolvedQuestion objects.
    """
    resolutions = []

    # Pattern 1: [x] ~~question~~ **RESOLVED:** resolution
    # This is the standard format from the LLD review prompt
    pattern1 = re.compile(
        r"^\s*-?\s*\[x\]\s*~~([^~]+)~~\s*\*\*RESOLVED:\*\*\s*(.+?)(?=\n\s*-?\s*\[|\n##|\Z)",
        re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )

    for match in pattern1.finditer(verdict_content):
        question_text = match.group(1).strip()
        resolution_text = match.group(2).strip()
        resolutions.append(
            ResolvedQuestion(
                question_text=question_text,
                resolution_text=resolution_text,
                original_line=f"- [ ] {question_text}",
            )
        )

    # Pattern 2: RESOLVED: answer after a question reference
    # e.g., "Q1: Should we...? RESOLVED: Yes, because..."
    pattern2 = re.compile(
        r"(?:Q\d+|Question\s*\d*):\s*(.+?)\s*\*?\*?RESOLVED:\*?\*?\s*(.+?)(?=\n\s*(?:Q\d+|Question)|\n##|\Z)",
        re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )

    for match in pattern2.finditer(verdict_content):
        question_text = match.group(1).strip().rstrip("?")
        resolution_text = match.group(2).strip()
        # Avoid duplicates
        if not any(r.question_text == question_text for r in resolutions):
            resolutions.append(
                ResolvedQuestion(
                    question_text=question_text,
                    resolution_text=resolution_text,
                    original_line=f"- [ ] {question_text}?",
                )
            )

    # Pattern 3: Open Questions Resolved section
    oq_section = _extract_section(verdict_content, "Open Questions Resolved")
    if oq_section:
        # Look for resolved items in this section
        pattern3 = re.compile(
            r"^\s*-\s*\[x\]\s*(.+?):\s*(.+?)(?=\n\s*-|\Z)",
            re.IGNORECASE | re.MULTILINE | re.DOTALL,
        )
        for match in pattern3.finditer(oq_section):
            question_text = match.group(1).strip()
            resolution_text = match.group(2).strip()
            # Avoid duplicates
            if not any(r.question_text == question_text for r in resolutions):
                resolutions.append(
                    ResolvedQuestion(
                        question_text=question_text,
                        resolution_text=resolution_text,
                        original_line=f"- [ ] {question_text}",
                    )
                )

    return resolutions


def _extract_tier3_suggestions(verdict_content: str) -> list[Tier3Suggestion]:
    """Extract Tier 3 suggestions from verdict.

    Looks for a "Tier 3" section containing suggestions.

    Args:
        verdict_content: The verdict text.

    Returns:
        List of Tier3Suggestion objects.
    """
    suggestions = []

    # Find Tier 3 section
    tier3_section = _extract_section(verdict_content, "Tier 3")
    if not tier3_section:
        # Try alternative header formats
        tier3_section = _extract_section(verdict_content, "Tier 3 Suggestions")
        if not tier3_section:
            tier3_section = _extract_section(
                verdict_content, "Tier 3: Optional Improvements"
            )

    if not tier3_section:
        return suggestions

    # Extract bullet points from the section
    bullet_pattern = re.compile(
        r"^\s*[-*]\s+(.+?)(?=\n\s*[-*]|\n##|\Z)", re.MULTILINE | re.DOTALL
    )

    for match in bullet_pattern.finditer(tier3_section):
        suggestion_text = match.group(1).strip()
        if suggestion_text:
            # Check for section reference in brackets
            section_match = re.search(r"\[([^\]]+)\]", suggestion_text)
            section = section_match.group(1) if section_match else ""

            # Check for priority markers
            priority = ""
            if "low priority" in suggestion_text.lower():
                priority = "low"
            elif "medium priority" in suggestion_text.lower():
                priority = "medium"
            elif "high priority" in suggestion_text.lower():
                priority = "high"

            suggestions.append(
                Tier3Suggestion(
                    suggestion_text=suggestion_text, section=section, priority=priority
                )
            )

    return suggestions


def _extract_section(content: str, header: str) -> str:
    """Extract content under a specific header.

    Args:
        content: Full document content.
        header: Section header to find (without ## prefix).

    Returns:
        Content between the header and the next ## header, or empty string.
    """
    # Try various header formats: ##, ###, ####
    pattern = re.compile(
        rf"^##{{1,4}}\s*{re.escape(header)}\s*\n(.*?)(?=^##|\Z)",
        re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )

    match = pattern.search(content)
    if match:
        return match.group(1).strip()

    return ""
```

```python
# File: agentos/workflows/requirements/parsers/draft_updater.py

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

Now let me update the test file to properly test these implementations:

```python
# File: tests/test_issue_257.py

"""Test file for Issue #257.

Generated by AgentOS TDD Testing Workflow.
Tests for verdict parsing and draft updating functionality.
"""

import logging
import pytest

from agentos.workflows.requirements.parsers.verdict_parser import (
    ResolvedQuestion,
    Tier3Suggestion,
    VerdictParseResult,
    parse_verdict,
)
from agentos.workflows.requirements.parsers.draft_updater import (
    update_draft,
    update_draft_with_resolutions,
    update_draft_with_suggestions,
)


# Test Fixtures
# -------------

@pytest.fixture
def sample_approved_verdict_with_resolutions():
    """Sample APPROVED verdict with resolved open questions."""
    return """
## Verdict

- [x] **APPROVED**
- [ ] REVISE
- [ ] DISCUSS

## Open Questions Resolved

- [x] ~~Should we use strikethrough for original text?~~ **RESOLVED:** Yes, use strikethrough for the original question text and append the resolution.
- [x] ~~Where should Tier 3 suggestions go?~~ **RESOLVED:** Add them to a new "Reviewer Suggestions" section at the end of the draft.

## Tier 3

- Consider adding a backup mechanism before modifying drafts [Section 2.1]
- The idempotency tests could be more comprehensive (low priority)
"""


@pytest.fixture
def sample_approved_verdict_simple():
    """Simple APPROVED verdict without resolutions."""
    return """
## Verdict

VERDICT: APPROVED

No open questions to resolve.
"""


@pytest.fixture
def sample_rejected_verdict():
    """Sample REJECTED/BLOCKED verdict."""
    return """
## Verdict

- [ ] APPROVED
- [x] **REVISE**
- [ ] DISCUSS

## Blocking Issues

1. Missing error handling in the parser
2. No tests for edge cases
"""


@pytest.fixture
def sample_draft_with_open_questions():
    """Sample draft LLD with open questions."""
    return """# LLD-257: Draft Update Feature

## 1. Context & Goal

This feature updates drafts with resolved questions.

### Open Questions

- [ ] Should we use strikethrough for original text?
- [ ] Where should Tier 3 suggestions go?
- [ ] Should we create a backup before modification?

## 2. Proposed Changes

Changes will be made to the review and finalize nodes.

## 3. Test Plan

- Unit tests for parser
- Integration tests for workflow
"""


@pytest.fixture
def sample_draft_no_open_questions():
    """Sample draft with no open questions."""
    return """# LLD-257: Draft Update Feature

## 1. Context & Goal

This feature updates drafts with resolved questions.

### Open Questions

*None at this time.*

## 2. Proposed Changes

Changes will be made to the review and finalize nodes.
"""


@pytest.fixture
def test_client():
    """Test client for API calls."""
    yield None


# Unit Tests
# -----------

def test_id():
    """
    Basic sanity test for imports.
    """
    # Verify imports work
    assert VerdictParseResult is not None
    assert ResolvedQuestion is not None
    assert Tier3Suggestion is not None
    assert parse_verdict is not None


def test_t010(sample_approved_verdict_with_resolutions):
    """
    Parse APPROVED verdict with resolved questions | Returns
    VerdictParseResult with resolutions | RED
    """
    # TDD: Arrange
    verdict = sample_approved_verdict_with_resolutions

    # TDD: Act
    result = parse_verdict(verdict)

    # TDD: Assert
    assert result.verdict_status == "APPROVED"
    assert len(result.resolutions) >= 2
    assert any("strikethrough" in r.question_text.lower() for r in result.resolutions)
    assert any("Tier 3" in r.question_text for r in result.resolutions)


def test_t020(sample_approved_verdict_with_resolutions):
    """
    Parse APPROVED verdict with Tier 3 suggestions | Returns
    VerdictParseResult with suggestions | RED
    """
    # TDD: Arrange
    verdict = sample_approved_verdict_with_resolutions

    # TDD: Act
    result = parse_verdict(verdict)

    # TDD: Assert
    assert result.verdict_status == "APPROVED"
    assert len(result.suggestions) >= 1
    assert any("backup" in s.suggestion_text.lower() for s in result.suggestions)


def test_t030(sample_rejected_verdict):
    """
    Parse REJECTED verdict | Returns VerdictParseResult with empty
    resolutions | RED
    """
    # TDD: Arrange
    verdict = sample_rejected_verdict

    # TDD: Act
    result = parse_verdict(verdict)

    # TDD: Assert
    assert result.verdict_status == "BLOCKED"
    assert len(result.resolutions) == 0


def test_t040(sample_draft_with_open_questions):
    """
    Update draft open questions with resolutions | Checkboxes changed to
    `- [x]` with resolution text | RED
    """
    # TDD: Arrange
    draft = sample_draft_with_open_questions
    resolutions = [
        ResolvedQuestion(
            question_text="Should we use strikethrough for original text?",
            resolution_text="Yes, use strikethrough.",
            original_line="- [ ] Should we use strikethrough for original text?",
        )
    ]

    # TDD: Act
    updated_draft, warnings = update_draft_with_resolutions(draft, resolutions)

    # TDD: Assert
    assert "- [x]" in updated_draft
    assert "**RESOLVED:**" in updated_draft
    assert "Yes, use strikethrough" in updated_draft


def test_t050(sample_draft_with_open_questions):
    """
    Update draft with suggestions (new section) | Reviewer Suggestions
    section appended | RED
    """
    # TDD: Arrange
    draft = sample_draft_with_open_questions
    suggestions = [
        Tier3Suggestion(
            suggestion_text="Consider adding a backup mechanism",
            section="Section 2.1",
            priority="",
        )
    ]

    # TDD: Act
    updated_draft, warnings = update_draft_with_suggestions(draft, suggestions)

    # TDD: Assert
    assert "## Reviewer Suggestions" in updated_draft
    assert "backup mechanism" in updated_draft
    assert "Tier 3 suggestions" in updated_draft


def test_t060(sample_draft_with_open_questions, caplog):
    """
    Handle missing open question in draft | Log warning, continue
    processing | RED
    """
    # TDD: Arrange
    draft = sample_draft_with_open_questions
    resolutions = [
        ResolvedQuestion(
            question_text="This question does not exist in the draft",
            resolution_text="Some resolution",
            original_line="- [ ] This question does not exist",
        )
    ]

    # TDD: Act
    with caplog.at_level(logging.WARNING):
        updated_draft, warnings = update_draft_with_resolutions(draft, resolutions)

    # TDD: Assert
    assert len(warnings) > 0
    assert "not found" in warnings[0].lower()
    # Draft should be unchanged except for the warning
    assert updated_draft == draft


def test_t090(sample_draft_with_open_questions):
    """
    Idempotency: same verdict applied twice | Same result both times |
    RED
    """
    # TDD: Arrange
    draft = sample_draft_with_open_questions
    resolutions = [
        ResolvedQuestion(
            question_text="Should we use strikethrough for original text?",
            resolution_text="Yes, use strikethrough.",
            original_line="- [ ] Should we use strikethrough for original text?",
        )
    ]

    # TDD: Act
    updated_draft1, _ = update_draft_with_resolutions(draft, resolutions)
    updated_draft2, _ = update_draft_with_resolutions(updated_draft1, resolutions)

    # TDD: Assert
    # Second application should produce the same result
    assert updated_draft1 == updated_draft2
    # Should only have one RESOLVED marker
    assert updated_draft1.count("**RESOLVED:**") == 1


def test_010(sample_approved_verdict_with_resolutions):
    """
    Parse approved verdict with resolutions | Auto | Verdict with "Open
    Questions: RESOLVED" | List of ResolvedQuestion | Correct questions
    and resolution text extracted
    """
    # TDD: Arrange
    verdict = sample_approved_verdict_with_resolutions

    # TDD: Act
    result = parse_verdict(verdict)

    # TDD: Assert
    assert result.verdict_status == "APPROVED"
    assert len(result.resolutions) >= 2
    # Check that resolution text was captured
    for res in result.resolutions:
        assert res.resolution_text, f"Resolution should have text: {res.question_text}"


def test_020(sample_approved_verdict_with_resolutions):
    """
    Parse approved verdict with suggestions | Auto | Verdict with "Tier
    3" section | List of Tier3Suggestion | All suggestions captured
    """
    # TDD: Arrange
    verdict = sample_approved_verdict_with_resolutions

    # TDD: Act
    result = parse_verdict(verdict)

    # TDD: Assert
    assert len(result.suggestions) >= 2
    # Check suggestion properties
    for suggestion in result.suggestions:
        assert suggestion.suggestion_text


def test_030(sample_rejected_verdict):
    """
    Parse rejected verdict | Auto | REJECTED verdict | Empty resolutions
    list | No resolutions extracted
    """
    # TDD: Arrange
    verdict = sample_rejected_verdict

    # TDD: Act
    result = parse_verdict(verdict)

    # TDD: Assert
    assert result.verdict_status == "BLOCKED"
    assert result.resolutions == []
    assert result.suggestions == []


def test_040(sample_draft_with_open_questions):
    """
    Update draft checkboxes | Auto | Draft + resolutions | Updated draft
    """
    # TDD: Arrange
    draft = sample_draft_with_open_questions
    resolutions = [
        ResolvedQuestion(
            question_text="Should we use strikethrough for original text",
            resolution_text="Yes",
            original_line="",
        )
    ]

    # TDD: Act
    updated, warnings = update_draft_with_resolutions(draft, resolutions)

    # TDD: Assert
    # Original unchecked box should be replaced
    assert "- [ ] Should we use strikethrough" not in updated
    assert "- [x]" in updated


def test_050(sample_draft_with_open_questions):
    """
    Add suggestions section | Auto | Draft + suggestions | Updated draft
    | New section at end
    """
    # TDD: Arrange
    draft = sample_draft_with_open_questions
    suggestions = [
        Tier3Suggestion(suggestion_text="Add more tests", section="", priority="low")
    ]

    # TDD: Act
    updated, warnings = update_draft_with_suggestions(draft, suggestions)

    # TDD: Assert
    assert "## Reviewer Suggestions" in updated
    assert "Add more tests" in updated
    # Section should be near the end
    suggestions_pos = updated.find("## Reviewer Suggestions")
    assert suggestions_pos > len(updated) // 2


def test_060(sample_draft_with_open_questions, caplog):
    """
    Missing question in draft | Auto | Resolution for non-existent
    question | Warning logged, draft unchanged | No error thrown
    """
    # TDD: Arrange
    draft = sample_draft_with_open_questions
    resolutions = [
        ResolvedQuestion(
            question_text="Nonexistent question that was never in the draft",
            resolution_text="Some answer",
            original_line="",
        )
    ]

    # TDD: Act - should not raise
    updated, warnings = update_draft_with_resolutions(draft, resolutions)

    # TDD: Assert
    assert len(warnings) > 0
    assert draft == updated  # Unchanged


def test_090(sample_draft_with_open_questions):
    """
    Idempotent update | Auto | Apply same verdict twice | Same draft | No
    duplicate markers
    """
    # TDD: Arrange
    draft = sample_draft_with_open_questions
    suggestions = [
        Tier3Suggestion(suggestion_text="Consider caching", section="", priority="")
    ]

    # TDD: Act
    updated1, _ = update_draft_with_suggestions(draft, suggestions)
    updated2, _ = update_draft_with_suggestions(updated1, suggestions)

    # TDD: Assert
    assert updated1 == updated2
    assert updated1.count("## Reviewer Suggestions") == 1


def test_100(sample_draft_no_open_questions):
    """
    Empty Open Questions section | Auto | Verdict resolves nothing |
    Unchanged draft | No modifications
    """
    # TDD: Arrange
    draft = sample_draft_no_open_questions
    resolutions = []  # No resolutions

    # TDD: Act
    updated, warnings = update_draft_with_resolutions(draft, resolutions)

    # TDD: Assert
    assert updated == draft


def test_110():
    """
    Malformed verdict | Auto | Verdict missing expected sections |
    Warning, original draft | Graceful degradation
    """
    # TDD: Arrange
    malformed_verdict = "Just some random text without proper structure"

    # TDD: Act - should not raise
    result = parse_verdict(malformed_verdict)

    # TDD: Assert
    assert result.verdict_status == "BLOCKED"  # Default to safe
    assert result.resolutions == []
    assert result.suggestions == []


# Integration Tests
# -----------------

@pytest.mark.integration
def test_070(
    test_client,
    sample_approved_verdict_with_resolutions,
    sample_draft_with_open_questions,
):
    """
    Review node integration | Auto | State with APPROVED verdict | State
    with updated_draft | Draft contains resolutions
    """
    # TDD: Arrange
    draft = sample_draft_with_open_questions
    verdict = sample_approved_verdict_with_resolutions

    # TDD: Act
    verdict_result = parse_verdict(verdict)
    updated_draft, warnings = update_draft(draft, verdict_result)

    # TDD: Assert
    assert "- [x]" in updated_draft
    assert "**RESOLVED:**" in updated_draft
    # Should also have suggestions section
    assert "## Reviewer Suggestions" in updated_draft


@pytest.mark.integration
def test_080(
    test_client,
    sample_approved_verdict_with_resolutions,
    sample_draft_with_open_questions,
):
    """
    Finalize node integration | Auto | State with updated_draft | Final
    LLD | LLD contains `- [x]`
    """
    # TDD: Arrange
    draft = sample_draft_with_open_questions
    verdict = sample_approved_verdict_with_resolutions

    # TDD: Act
    verdict_result = parse_verdict(verdict)
    final_draft, _ = update_draft(draft, verdict_result)

    # TDD: Assert
    # Final draft should have resolved questions
    assert "- [x]" in final_draft
    # Should have at least one resolved question with resolution text
    assert "**RESOLVED:**" in final_draft


# E2E Tests
# ---------

@pytest.mark.e2e
def test_t070(test_client, sample_approved_verdict_with_resolutions, sample_draft_with_open_questions):
    """
    End-to-end: review node updates draft on approval | State contains
    updated_draft after approval | RED
    """
    # TDD: Arrange
    verdict = sample_approved_verdict_with_resolutions
    draft = sample_draft_with_open_questions

    # TDD: Act - Full flow
    verdict_result = parse_verdict(verdict)
    assert verdict_result.verdict_status == "APPROVED"

    updated_draft, warnings = update_draft(draft, verdict_result)

    # TDD: Assert
    assert updated_draft != draft  # Draft was modified
    assert "- [x]" in updated_draft
    assert "**RESOLVED:**" in updated_draft


@pytest.mark.e2e
def test_t080(test_client, sample_approved_verdict_with_resolutions, sample_draft_with_open_questions):
    """
    End-to-end: finalize uses updated draft | Final LLD contains resolved
    questions | RED
    """
    # TDD: Arrange
    verdict = sample_approved_verdict_with_resolutions
    draft = sample_draft_with_open_questions

    # TDD: Act - Simulate full workflow
    verdict_result = parse_verdict(verdict)
    final_draft, _ = update_draft(draft, verdict_result)

    # TDD: Assert - Final LLD has all resolved content
    assert "- [x]" in final_draft
    # Original unchecked questions for resolved items should be gone
    # (except for the one not resolved: "Should we create a backup")
    resolved_questions = [r.question_text for r in verdict_result.resolutions]
    for q in resolved_questions:
        # The checked version should exist
        assert "- [x]" in final_draft
```

Now I need to update the review.py file to use the new parsers to update the draft after an APPROVED verdict. Let me read the file again and provide the updated version:

```python
# File: agentos/workflows/requirements/nodes/review.py

"""N3: Review node for Requirements Workflow.

Issue #101: Unified Requirements Workflow
Issue #248: Add post-review open questions check
Issue #257: Update draft with resolved open questions after approval

Uses the configured reviewer LLM to review the current draft.
Saves verdict to audit trail and updates verdict history.
"""

import re
from pathlib import Path
from typing import Any

from agentos.core.llm_provider import get_provider
from agentos.workflows.requirements.audit import (
    load_review_prompt,
    next_file_number,
    save_audit_file,
)
from agentos.workflows.requirements.state import RequirementsWorkflowState


def review(state: RequirementsWorkflowState) -> dict[str, Any]:
    """N3: Review draft using configured reviewer.

    Steps:
    1. Load review prompt from agentos_root
    2. Build review content (draft + context)
    3. Call reviewer LLM
    4. Save verdict to audit trail
    5. Update verdict_count and verdict_history
    6. Determine lld_status from verdict
    7. Check for open questions resolution (Issue #248)
    8. Update draft with resolutions if APPROVED (Issue #257)

    Args:
        state: Current workflow state.

    Returns:
        State updates with current_verdict, verdict_count, verdict_history,
        open_questions_status, and updated_draft (if APPROVED).
    """
    workflow_type = state.get("workflow_type", "lld")
    agentos_root = Path(state.get("agentos_root", ""))
    mock_mode = state.get("config_mock_mode", False)
    audit_dir = Path(state.get("audit_dir", ""))
    current_draft = state.get("current_draft", "")
    verdict_history = list(state.get("verdict_history", []))

    verdict_count = state.get("verdict_count", 0) + 1
    print(f"\n[N3] Reviewing draft (review #{verdict_count})...")

    # Use mock provider in mock mode, otherwise use configured reviewer
    if mock_mode:
        reviewer_spec = "mock:review"
    else:
        reviewer_spec = state.get("config_reviewer", "gemini:3-pro-preview")

    # Determine review prompt path based on workflow type
    if workflow_type == "issue":
        prompt_path = Path("docs/skills/0701c-Issue-Review-Prompt.md")
    else:
        prompt_path = Path("docs/skills/0702c-LLD-Review-Prompt.md")

    # Load review prompt
    try:
        review_prompt = load_review_prompt(prompt_path, agentos_root)
    except FileNotFoundError as e:
        return {"error_message": str(e)}

    # Get reviewer provider
    try:
        reviewer = get_provider(reviewer_spec)
    except ValueError as e:
        return {"error_message": f"Invalid reviewer: {e}"}

    # System prompt for reviewing
    system_prompt = """You are a Principal Architect, Systems Engineer, and Test Plan Execution Guru.

Your role is to perform a strict gatekeeper review of design documents before implementation begins.

Key responsibilities:
- Answer any open questions in Section 1 with concrete recommendations
- Evaluate cost, safety, security, and legal concerns
- Verify test coverage meets requirements
- Provide a structured verdict: APPROVED or BLOCKED

Follow the Review Instructions exactly. Be specific about what needs to change for BLOCKED verdicts."""

    # Build review content
    review_content = f"""## Document to Review

{current_draft}

## Review Instructions

{review_prompt}"""

    # Call reviewer
    print(f"    Reviewer: {reviewer_spec}")
    result = reviewer.invoke(system_prompt=system_prompt, content=review_content)

    if not result.success:
        print(f"    ERROR: {result.error_message}")
        return {"error_message": f"Reviewer failed: {result.error_message}"}

    verdict_content = result.response or ""

    # Save to audit trail
    file_num = next_file_number(audit_dir)
    if audit_dir.exists():
        verdict_path = save_audit_file(
            audit_dir, file_num, "verdict.md", verdict_content
        )
    else:
        verdict_path = None

    # Append to verdict history
    verdict_history.append(verdict_content)

    # Determine LLD status from verdict
    lld_status = _parse_verdict_status(verdict_content)

    # Issue #248: Check open questions resolution status
    open_questions_status = _check_open_questions_status(current_draft, verdict_content)

    # Issue #257: Update draft with resolutions if APPROVED
    updated_draft = current_draft
    if lld_status == "APPROVED":
        updated_draft = _update_draft_with_verdict(current_draft, verdict_content)
        if updated_draft != current_draft:
            print("    Draft updated with resolved open questions")

    verdict_lines = len(verdict_content.splitlines()) if verdict_content else 0
    print(f"    Verdict: {lld_status} ({verdict_lines} lines)")
    print(f"    Open Questions: {open_questions_status}")
    if verdict_path:
        print(f"    Saved: {verdict_path.name}")

    return {
        "current_verdict": verdict_content,
        "current_verdict_path": str(verdict_path) if verdict_path else "",
        "verdict_count": verdict_count,
        "verdict_history": verdict_history,
        "file_counter": file_num,
        "lld_status": lld_status,
        "open_questions_status": open_questions_status,
        "current_draft": updated_draft,  # Issue #257: Return updated draft
        "error_message": "",
    }


def _update_draft_with_verdict(draft: str, verdict_content: str) -> str:
    """Update draft with resolutions and suggestions from verdict.

    Issue #257: After APPROVED verdict, update the draft with:
    - Resolved open questions (mark as [x] with resolution text)
    - Tier 3 suggestions (add new section)

    Args:
        draft: Current draft content.
        verdict_content: The APPROVED verdict from reviewer.

    Returns:
        Updated draft content.
    """
    try:
        from agentos.workflows.requirements.parsers.verdict_parser import parse_verdict
        from agentos.workflows.requirements.parsers.draft_updater import update_draft

        verdict_result = parse_verdict(verdict_content)
        updated_draft, warnings = update_draft(draft, verdict_result)

        for warning in warnings:
            print(f"    Warning: {warning}")

        return updated_draft
    except ImportError:
        # Parsers not available (shouldn't happen in production)
        return draft
    except Exception as e:
        print(f"    Warning: Could not update draft with verdict: {e}")
        return draft


def _parse_verdict_status(verdict_content: str) -> str:
    """Parse LLD status from verdict content.

    Args:
        verdict_content: The reviewer's verdict text.

    Returns:
        One of: "APPROVED", "BLOCKED"
    """
    verdict_upper = verdict_content.upper()

    # Check for checked APPROVED checkbox
    if re.search(r"\[X\]\s*\**APPROVED\**", verdict_upper):
        return "APPROVED"
    # Check for checked REVISE checkbox (maps to BLOCKED for workflow purposes)
    elif re.search(r"\[X\]\s*\**REVISE\**", verdict_upper):
        return "BLOCKED"
    # Check for checked DISCUSS checkbox (maps to BLOCKED, needs human)
    elif re.search(r"\[X\]\s*\**DISCUSS\**", verdict_upper):
        return "BLOCKED"
    # Fallback: Look for explicit keywords (legacy/simple responses)
    elif "VERDICT: APPROVED" in verdict_upper:
        return "APPROVED"
    elif "VERDICT: BLOCKED" in verdict_upper or "VERDICT: REVISE" in verdict_upper:
        return "BLOCKED"
    else:
        # Default to BLOCKED if we can't determine status (safe choice)
        return "BLOCKED"


def _check_open_questions_status(draft_content: str, verdict_content: str) -> str:
    """Check whether open questions have been resolved.

    Issue #248: After Gemini review, check if:
    1. Questions were answered (all [x] in verdict's "Open Questions Resolved" section)
    2. Questions marked as HUMAN REQUIRED
    3. Questions remain unanswered

    Args:
        draft_content: The draft that was reviewed.
        verdict_content: Gemini's verdict.

    Returns:
        One of:
        - "RESOLVED": All open questions answered
        - "HUMAN_REQUIRED": One or more questions need human decision
        - "UNANSWERED": Questions exist but weren't answered
        - "NONE": No open questions in the draft
    """
    # Check if draft has open questions
    draft_has_questions = _draft_has_open_questions(draft_content)
    if not draft_has_questions:
        return "NONE"

    # Check for HUMAN REQUIRED in verdict
    if _verdict_has_human_required(verdict_content):
        return "HUMAN_REQUIRED"

    # Check if verdict has "Open Questions Resolved" section with answers
    if _verdict_has_resolved_questions(verdict_content):
        return "RESOLVED"

    # Questions exist but weren't answered
    return "UNANSWERED"


def _draft_has_open_questions(content: str) -> bool:
    """Check if draft has unchecked open questions.

    Args:
        content: Draft content.

    Returns:
        True if unchecked open questions exist.
    """
    if not content:
        return False

    # Extract Open Questions section
    pattern = r"(?:^##?#?\s*Open Questions\s*\n)(.*?)(?=^##|\Z)"
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)

    if not match:
        return False

    open_questions_section = match.group(1)

    # Check for unchecked boxes
    unchecked = re.findall(r"^- \[ \]", open_questions_section, re.MULTILINE)
    return len(unchecked) > 0


def _verdict_has_human_required(verdict_content: str) -> bool:
    """Check if verdict contains HUMAN REQUIRED marker.

    Args:
        verdict_content: The verdict text.

    Returns:
        True if HUMAN REQUIRED is present.
    """
    # Look for HUMAN REQUIRED (case insensitive) in various formats
    patterns = [
        r"HUMAN\s+REQUIRED",
        r"\*\*HUMAN\s+REQUIRED\*\*",
        r"REQUIRES?\s+HUMAN",
        r"NEEDS?\s+HUMAN\s+DECISION",
        r"ESCALATE\s+TO\s+HUMAN",
    ]
    verdict_upper = verdict_content.upper()
    for pattern in patterns:
        if re.search(pattern, verdict_upper):
            return True
    return False


def _verdict_has_resolved_questions(verdict_content: str) -> bool:
    """Check if verdict has resolved open questions.

    Looks for the "Open Questions Resolved" section and checks if
    all items are marked as [x] with RESOLVED.

    Args:
        verdict_content: The verdict text.

    Returns:
        True if questions were resolved.
    """
    # Look for "Open Questions Resolved" section
    pattern = r"(?:##\s*Open Questions Resolved\s*\n)(.*?)(?=^##|\Z)"
    match = re.search(pattern, verdict_content, re.MULTILINE | re.DOTALL)

    if not match:
        # No explicit section - check if "RESOLVED:" appears in verdict
        return "RESOLVED:" in verdict_content.upper()

    resolved_section = match.group(1)

    # Check for resolved markers: [x] followed by ~~question~~ **RESOLVED:
    resolved_count = len(re.findall(r"\[x\].*?RESOLVED:", resolved_section, re.IGNORECASE))

    # Check for any unchecked items still in the section
    unchecked_count = len(re.findall(r"^- \[ \]", resolved_section, re.MULTILINE))

    # If we have resolutions and no unchecked items, questions are resolved
    return resolved_count > 0 and unchecked_count == 0
```

The finalize.py file already handles using the current_draft from state, which will now contain the updated draft after the review node runs. No changes needed there since it reads `current_draft` from state.
