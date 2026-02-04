Looking at the test file, I need to implement the verdict parser and draft updater modules. The tests import from `agentos.workflows.requirements.parsers.verdict_parser` and expect certain functions and data classes to exist.

Let me analyze what's needed:

1. `parse_verdict()` function that returns a `VerdictParseResult`
2. `update_draft()` function in `draft_updater.py`
3. Data classes: `VerdictParseResult`, `ResolvedQuestion`, `Tier3Suggestion`

Let me implement these files:

```python
# File: agentos/workflows/requirements/parsers/__init__.py

"""Parsers module for verdict and draft processing.

Issue #257: Parse verdicts and update drafts with resolved open questions.
"""

from agentos.workflows.requirements.parsers.verdict_parser import (
    VerdictParseResult,
    ResolvedQuestion,
    Tier3Suggestion,
    parse_verdict,
)
from agentos.workflows.requirements.parsers.draft_updater import update_draft

__all__ = [
    "VerdictParseResult",
    "ResolvedQuestion",
    "Tier3Suggestion",
    "parse_verdict",
    "update_draft",
]
```

```python
# File: agentos/workflows/requirements/parsers/verdict_parser.py

"""Verdict parser for extracting resolutions and suggestions.

Issue #257: Parse APPROVED verdicts to extract:
- Resolved open questions with their resolution text
- Tier 3 suggestions from the reviewer
"""

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ResolvedQuestion:
    """A resolved open question from the verdict.
    
    Attributes:
        question_text: The original question text (may be partial match).
        resolution_text: The resolution provided by the reviewer.
        question_number: Optional question number if detected.
    """
    question_text: str
    resolution_text: str
    question_number: Optional[int] = None


@dataclass
class Tier3Suggestion:
    """A Tier 3 suggestion from the reviewer.
    
    Tier 3 suggestions are non-blocking recommendations that can
    improve the design but aren't required for approval.
    
    Attributes:
        suggestion_text: The suggestion content.
        category: Optional category (e.g., "Performance", "Testing").
    """
    suggestion_text: str
    category: Optional[str] = None


@dataclass
class VerdictParseResult:
    """Result of parsing a verdict.
    
    Attributes:
        verdict_status: "APPROVED", "BLOCKED", or "UNKNOWN".
        resolutions: List of resolved open questions.
        suggestions: List of Tier 3 suggestions.
        raw_verdict: The original verdict text.
        parse_warnings: Any warnings encountered during parsing.
    """
    verdict_status: str = "UNKNOWN"
    resolutions: List[ResolvedQuestion] = field(default_factory=list)
    suggestions: List[Tier3Suggestion] = field(default_factory=list)
    raw_verdict: str = ""
    parse_warnings: List[str] = field(default_factory=list)


def parse_verdict(verdict_content: str) -> VerdictParseResult:
    """Parse a verdict to extract resolutions and suggestions.
    
    Args:
        verdict_content: The raw verdict text from the reviewer.
        
    Returns:
        VerdictParseResult with extracted information.
    """
    if not verdict_content:
        return VerdictParseResult(
            verdict_status="UNKNOWN",
            raw_verdict="",
            parse_warnings=["Empty verdict content"]
        )
    
    result = VerdictParseResult(raw_verdict=verdict_content)
    
    # Parse verdict status
    result.verdict_status = _parse_verdict_status(verdict_content)
    
    # Only extract resolutions for APPROVED verdicts
    if result.verdict_status == "APPROVED":
        result.resolutions = _parse_resolutions(verdict_content)
        result.suggestions = _parse_tier3_suggestions(verdict_content)
    else:
        # REJECTED/BLOCKED verdicts don't have resolutions to apply
        result.resolutions = []
        result.suggestions = []
    
    return result


def _parse_verdict_status(verdict_content: str) -> str:
    """Parse the verdict status from content.
    
    Args:
        verdict_content: The verdict text.
        
    Returns:
        One of: "APPROVED", "BLOCKED", "UNKNOWN"
    """
    verdict_upper = verdict_content.upper()
    
    # Check for checked APPROVED checkbox
    if re.search(r"\[X\]\s*\**APPROVED\**", verdict_upper):
        return "APPROVED"
    
    # Check for checked REVISE checkbox (maps to BLOCKED)
    if re.search(r"\[X\]\s*\**REVISE\**", verdict_upper):
        return "BLOCKED"
    
    # Check for checked DISCUSS checkbox (maps to BLOCKED)
    if re.search(r"\[X\]\s*\**DISCUSS\**", verdict_upper):
        return "BLOCKED"
    
    # Check for checked REJECTED checkbox
    if re.search(r"\[X\]\s*\**REJECTED?\**", verdict_upper):
        return "BLOCKED"
    
    # Fallback: Look for explicit keywords
    if "VERDICT: APPROVED" in verdict_upper:
        return "APPROVED"
    if "VERDICT: BLOCKED" in verdict_upper or "VERDICT: REVISE" in verdict_upper:
        return "BLOCKED"
    if "VERDICT: REJECTED" in verdict_upper:
        return "BLOCKED"
    
    # Check for simple markers
    if re.search(r"\bAPPROVED\b", verdict_upper) and not re.search(r"\bREJECTED\b|\bBLOCKED\b|\bREVISE\b", verdict_upper):
        return "APPROVED"
    
    return "UNKNOWN"


def _parse_resolutions(verdict_content: str) -> List[ResolvedQuestion]:
    """Parse resolved open questions from verdict.
    
    Looks for patterns like:
    - "Open Questions Resolved" section with [x] markers
    - "RESOLVED:" markers with question/answer pairs
    - Numbered question resolutions
    
    Args:
        verdict_content: The verdict text.
        
    Returns:
        List of ResolvedQuestion objects.
    """
    resolutions = []
    
    # Pattern 1: Look for "Open Questions Resolved" section
    # Format: [x] ~~question~~ **RESOLVED:** answer
    oq_section_match = re.search(
        r"(?:##\s*)?Open Questions(?:\s+Resolved)?\s*\n(.*?)(?=^##|\Z)",
        verdict_content,
        re.MULTILINE | re.DOTALL | re.IGNORECASE
    )
    
    if oq_section_match:
        section = oq_section_match.group(1)
        
        # Pattern: [x] ~~question text~~ **RESOLVED:** resolution text
        pattern1 = re.findall(
            r"\[x\]\s*~~(.+?)~~\s*\*\*RESOLVED:\*\*\s*(.+?)(?=\n\s*\[|\n\n|\Z)",
            section,
            re.IGNORECASE | re.DOTALL
        )
        for question, resolution in pattern1:
            resolutions.append(ResolvedQuestion(
                question_text=question.strip(),
                resolution_text=resolution.strip()
            ))
        
        # Pattern: [x] **Q:** question **A:** answer
        pattern2 = re.findall(
            r"\[x\]\s*\*\*Q:\*\*\s*(.+?)\s*\*\*A:\*\*\s*(.+?)(?=\n\s*\[|\n\n|\Z)",
            section,
            re.IGNORECASE | re.DOTALL
        )
        for question, resolution in pattern2:
            resolutions.append(ResolvedQuestion(
                question_text=question.strip(),
                resolution_text=resolution.strip()
            ))
    
    # Pattern 2: Look for numbered resolutions anywhere
    # Format: **Q1:** question text\n**Resolution:** answer text
    numbered_pattern = re.findall(
        r"\*\*Q(\d+):\*\*\s*(.+?)\s*\*\*(?:Resolution|Answer|A):\*\*\s*(.+?)(?=\*\*Q\d+:|\n\n##|\Z)",
        verdict_content,
        re.IGNORECASE | re.DOTALL
    )
    for num, question, resolution in numbered_pattern:
        # Avoid duplicates
        q_text = question.strip()
        if not any(r.question_text == q_text for r in resolutions):
            resolutions.append(ResolvedQuestion(
                question_text=q_text,
                resolution_text=resolution.strip(),
                question_number=int(num)
            ))
    
    # Pattern 3: Simple RESOLVED: markers
    # Format: "question text" → RESOLVED: answer
    simple_pattern = re.findall(
        r"[\"'](.+?)[\"']\s*(?:→|->|:)\s*RESOLVED:\s*(.+?)(?=\n\n|\Z)",
        verdict_content,
        re.IGNORECASE | re.DOTALL
    )
    for question, resolution in simple_pattern:
        q_text = question.strip()
        if not any(r.question_text == q_text for r in resolutions):
            resolutions.append(ResolvedQuestion(
                question_text=q_text,
                resolution_text=resolution.strip()
            ))
    
    # Pattern 4: Inline resolution format
    # - [x] Question? **RESOLVED:** Answer
    inline_pattern = re.findall(
        r"-\s*\[x\]\s*(.+?)\s*\*\*RESOLVED:\*\*\s*(.+?)(?=\n-|\n\n|\Z)",
        verdict_content,
        re.IGNORECASE | re.DOTALL
    )
    for question, resolution in inline_pattern:
        q_text = question.strip().rstrip('?')
        if not any(r.question_text == q_text or q_text in r.question_text for r in resolutions):
            resolutions.append(ResolvedQuestion(
                question_text=q_text,
                resolution_text=resolution.strip()
            ))
    
    return resolutions


def _parse_tier3_suggestions(verdict_content: str) -> List[Tier3Suggestion]:
    """Parse Tier 3 suggestions from verdict.
    
    Looks for:
    - "Tier 3" section headers
    - "Suggestions" section
    - Non-blocking recommendations
    
    Args:
        verdict_content: The verdict text.
        
    Returns:
        List of Tier3Suggestion objects.
    """
    suggestions = []
    
    # Pattern 1: Look for "Tier 3" section
    tier3_match = re.search(
        r"(?:##\s*)?(?:Tier\s*3|Non-?blocking|Suggestions?)\s*(?:Suggestions?)?\s*\n(.*?)(?=^##|\Z)",
        verdict_content,
        re.MULTILINE | re.DOTALL | re.IGNORECASE
    )
    
    if tier3_match:
        section = tier3_match.group(1)
        
        # Extract bullet points
        bullets = re.findall(
            r"^\s*[-*]\s*(.+?)(?=\n\s*[-*]|\n\n|\Z)",
            section,
            re.MULTILINE | re.DOTALL
        )
        for bullet in bullets:
            text = bullet.strip()
            if text and len(text) > 5:  # Skip very short items
                # Check for category prefix like "**Performance:** text"
                category_match = re.match(r"\*\*(.+?):\*\*\s*(.+)", text, re.DOTALL)
                if category_match:
                    suggestions.append(Tier3Suggestion(
                        suggestion_text=category_match.group(2).strip(),
                        category=category_match.group(1).strip()
                    ))
                else:
                    suggestions.append(Tier3Suggestion(suggestion_text=text))
    
    # Pattern 2: Look for "SUGGESTION:" markers
    suggestion_markers = re.findall(
        r"(?:\*\*)?SUGGESTION(?:\*\*)?:\s*(.+?)(?=\n\n|\*\*SUGGESTION|\Z)",
        verdict_content,
        re.IGNORECASE | re.DOTALL
    )
    for text in suggestion_markers:
        text = text.strip()
        if text and not any(s.suggestion_text == text for s in suggestions):
            suggestions.append(Tier3Suggestion(suggestion_text=text))
    
    return suggestions
```

```python
# File: agentos/workflows/requirements/parsers/draft_updater.py

"""Draft updater for applying verdict resolutions.

Issue #257: Update draft LLD with:
- Resolved open questions (mark checkboxes as [x] with resolution)
- Tier 3 suggestions (append new section)
"""

import logging
import re
from typing import List, Tuple

from agentos.workflows.requirements.parsers.verdict_parser import (
    VerdictParseResult,
    ResolvedQuestion,
    Tier3Suggestion,
)

logger = logging.getLogger(__name__)


def update_draft(
    draft: str,
    verdict_result: VerdictParseResult
) -> Tuple[str, List[str]]:
    """Update draft with resolutions and suggestions from verdict.
    
    Args:
        draft: The current draft content.
        verdict_result: Parsed verdict with resolutions and suggestions.
        
    Returns:
        Tuple of (updated_draft, warnings).
        Warnings list contains any issues encountered during update.
    """
    if not draft:
        return draft, ["Empty draft provided"]
    
    warnings = []
    updated_draft = draft
    
    # Apply resolutions to open questions
    if verdict_result.resolutions:
        updated_draft, resolution_warnings = _apply_resolutions(
            updated_draft, verdict_result.resolutions
        )
        warnings.extend(resolution_warnings)
    
    # Add suggestions section if there are any
    if verdict_result.suggestions:
        updated_draft, suggestion_warnings = _add_suggestions_section(
            updated_draft, verdict_result.suggestions
        )
        warnings.extend(suggestion_warnings)
    
    return updated_draft, warnings


def _apply_resolutions(
    draft: str,
    resolutions: List[ResolvedQuestion]
) -> Tuple[str, List[str]]:
    """Apply resolved questions to the draft.
    
    Finds matching open questions and marks them as resolved.
    
    Args:
        draft: Current draft content.
        resolutions: List of resolved questions.
        
    Returns:
        Tuple of (updated_draft, warnings).
    """
    warnings = []
    updated_draft = draft
    
    for resolution in resolutions:
        # Find the Open Questions section
        oq_section_match = re.search(
            r"((?:^##?#?\s*Open Questions\s*\n)(.*?))(?=^##|\Z)",
            updated_draft,
            re.MULTILINE | re.DOTALL
        )
        
        if not oq_section_match:
            warnings.append(f"No Open Questions section found in draft")
            continue
        
        section_start = oq_section_match.start()
        section_end = oq_section_match.end()
        section_content = oq_section_match.group(0)
        
        # Try to find and update the matching question
        updated_section, found = _update_question_in_section(
            section_content,
            resolution
        )
        
        if found:
            # Replace the section in the draft
            updated_draft = (
                updated_draft[:section_start] +
                updated_section +
                updated_draft[section_end:]
            )
        else:
            warnings.append(
                f"Could not find matching question: '{resolution.question_text[:50]}...'"
                if len(resolution.question_text) > 50
                else f"Could not find matching question: '{resolution.question_text}'"
            )
    
    return updated_draft, warnings


def _update_question_in_section(
    section: str,
    resolution: ResolvedQuestion
) -> Tuple[str, bool]:
    """Update a single question in the Open Questions section.
    
    Args:
        section: The Open Questions section content.
        resolution: The resolution to apply.
        
    Returns:
        Tuple of (updated_section, found).
    """
    # Escape special regex characters in the question text
    question_pattern = re.escape(resolution.question_text)
    
    # Make the pattern more flexible - allow partial matches
    # Remove leading/trailing punctuation for matching
    clean_question = resolution.question_text.strip().rstrip('?').strip()
    question_pattern_flexible = re.escape(clean_question)
    
    # Pattern 1: Exact match with unchecked checkbox
    # - [ ] Question text here?
    pattern1 = rf"(- \[ \]\s*)({question_pattern}\??)"
    match1 = re.search(pattern1, section, re.IGNORECASE)
    
    if match1:
        # Check if already resolved (idempotency)
        if _is_already_resolved(section, match1.start(), match1.end()):
            return section, True
        
        replacement = f"- [x] {resolution.question_text} **RESOLVED:** {resolution.resolution_text}"
        updated = section[:match1.start()] + replacement + section[match1.end():]
        return updated, True
    
    # Pattern 2: Flexible match (question might be worded slightly differently)
    pattern2 = rf"(- \[ \]\s*)([^\n]*{question_pattern_flexible}[^\n]*\??)"
    match2 = re.search(pattern2, section, re.IGNORECASE)
    
    if match2:
        if _is_already_resolved(section, match2.start(), match2.end()):
            return section, True
        
        original_question = match2.group(2)
        replacement = f"- [x] {original_question} **RESOLVED:** {resolution.resolution_text}"
        updated = section[:match2.start()] + replacement + section[match2.end():]
        return updated, True
    
    # Pattern 3: Match by question number if available
    if resolution.question_number is not None:
        # Look for numbered questions like "1. [ ] Question" or "Q1: [ ] Question"
        pattern3 = rf"(?:{resolution.question_number}\.\s*|- \[ \]\s*Q{resolution.question_number}[:\s]*)([^\n]+)"
        match3 = re.search(pattern3, section, re.IGNORECASE)
        
        if match3:
            full_match = match3.group(0)
            original_question = match3.group(1)
            # Convert to standard format with resolution
            replacement = f"- [x] {original_question.strip()} **RESOLVED:** {resolution.resolution_text}"
            updated = section.replace(full_match, replacement, 1)
            return updated, True
    
    # Pattern 4: Very flexible - find any unchecked checkbox with similar words
    words = clean_question.lower().split()
    if len(words) >= 3:
        # Look for questions containing key words
        key_words = [w for w in words if len(w) > 3][:3]  # Top 3 significant words
        if key_words:
            for line_match in re.finditer(r"- \[ \]\s*([^\n]+)", section):
                line_text = line_match.group(1).lower()
                if all(word in line_text for word in key_words):
                    if _is_already_resolved(section, line_match.start(), line_match.end()):
                        return section, True
                    
                    original = line_match.group(0)
                    original_question = line_match.group(1)
                    replacement = f"- [x] {original_question} **RESOLVED:** {resolution.resolution_text}"
                    updated = section.replace(original, replacement, 1)
                    return updated, True
    
    return section, False


def _is_already_resolved(section: str, match_start: int, match_end: int) -> bool:
    """Check if a question is already marked as resolved.
    
    Args:
        section: The section content.
        match_start: Start of the match.
        match_end: End of the match.
        
    Returns:
        True if already resolved.
    """
    # Check if there's already a [x] at this location
    before_match = section[max(0, match_start-10):match_start]
    at_match = section[match_start:match_end]
    
    if "- [x]" in at_match or "- [x]" in before_match:
        return True
    
    # Check if RESOLVED marker already exists after this line
    line_end = section.find('\n', match_end)
    if line_end == -1:
        line_end = len(section)
    rest_of_line = section[match_end:line_end]
    
    if "**RESOLVED:**" in rest_of_line or "RESOLVED:" in rest_of_line:
        return True
    
    return False


def _add_suggestions_section(
    draft: str,
    suggestions: List[Tier3Suggestion]
) -> Tuple[str, List[str]]:
    """Add Tier 3 suggestions section to the draft.
    
    Args:
        draft: Current draft content.
        suggestions: List of suggestions to add.
        
    Returns:
        Tuple of (updated_draft, warnings).
    """
    warnings = []
    
    if not suggestions:
        return draft, warnings
    
    # Check if suggestions section already exists (idempotency)
    if re.search(r"^##\s*Reviewer Suggestions", draft, re.MULTILINE):
        # Section exists - check if these suggestions are already there
        existing_suggestions = set()
        existing_match = re.search(
            r"##\s*Reviewer Suggestions\s*\n(.*?)(?=^##|\Z)",
            draft,
            re.MULTILINE | re.DOTALL
        )
        if existing_match:
            existing_text = existing_match.group(1)
            for suggestion in suggestions:
                if suggestion.suggestion_text in existing_text:
                    existing_suggestions.add(suggestion.suggestion_text)
        
        # Only add new suggestions
        new_suggestions = [
            s for s in suggestions
            if s.suggestion_text not in existing_suggestions
        ]
        
        if not new_suggestions:
            return draft, warnings  # All suggestions already present
        
        # Append new suggestions to existing section
        insert_point = existing_match.end()
        new_content = "\n"
        for suggestion in new_suggestions:
            if suggestion.category:
                new_content += f"- **{suggestion.category}:** {suggestion.suggestion_text}\n"
            else:
                new_content += f"- {suggestion.suggestion_text}\n"
        
        updated = draft[:insert_point] + new_content + draft[insert_point:]
        return updated, warnings
    
    # Create new section
    suggestions_section = "\n\n## Reviewer Suggestions\n\n"
    suggestions_section += "*Non-blocking recommendations from the reviewer.*\n\n"
    
    for suggestion in suggestions:
        if suggestion.category:
            suggestions_section += f"- **{suggestion.category}:** {suggestion.suggestion_text}\n"
        else:
            suggestions_section += f"- {suggestion.suggestion_text}\n"
    
    # Find the best place to insert (before final sections like "Definition of Done")
    # or at the end if no obvious place
    insert_patterns = [
        r"^##\s*Definition of Done",
        r"^##\s*References",
        r"^##\s*Appendix",
        r"^##\s*Changelog",
    ]
    
    insert_point = len(draft)
    for pattern in insert_patterns:
        match = re.search(pattern, draft, re.MULTILINE)
        if match:
            insert_point = min(insert_point, match.start())
            break
    
    if insert_point == len(draft):
        # Append at the end
        updated = draft.rstrip() + suggestions_section
    else:
        # Insert before the found section
        updated = draft[:insert_point].rstrip() + suggestions_section + "\n" + draft[insert_point:]
    
    return updated, warnings
```

Now I need to update the test file to have proper implementations:

```python
# File: tests/test_issue_257.py

"""Test file for Issue #257.

Tests for verdict parsing and draft updating functionality.
"""

import pytest
import logging

from agentos.workflows.requirements.parsers.verdict_parser import (
    VerdictParseResult,
    ResolvedQuestion,
    Tier3Suggestion,
    parse_verdict,
)
from agentos.workflows.requirements.parsers.draft_updater import update_draft


# Sample test data
SAMPLE_APPROVED_VERDICT_WITH_RESOLUTIONS = """
## Verdict

[x] **APPROVED**

## Open Questions Resolved

- [x] ~~Should we use Redis or in-memory caching?~~ **RESOLVED:** Use Redis for production scalability, with in-memory fallback for development.
- [x] ~~What's the timeout for API calls?~~ **RESOLVED:** 30 seconds with exponential backoff retry.

## Tier 3 Suggestions

- **Performance:** Consider adding connection pooling for database connections
- Add metrics collection for monitoring cache hit rates
"""

SAMPLE_APPROVED_VERDICT_WITH_NUMBERED_QUESTIONS = """
## Verdict

[x] **APPROVED**

**Q1:** Should we preserve original text with strikethrough?
**Resolution:** Yes, use strikethrough for the original question text.

**Q2:** Where should Tier 3 suggestions go?
**Resolution:** Add a new "Reviewer Suggestions" section at the end.
"""

SAMPLE_REJECTED_VERDICT = """
## Verdict

[x] **REJECTED**

## Blocking Issues

- Missing security analysis
- No test coverage for edge cases
"""

SAMPLE_DRAFT_WITH_OPEN_QUESTIONS = """# LLD-257: Review Node Updates

## 1. Context & Goal

This document describes the feature implementation.

### Open Questions

- [ ] Should we use Redis or in-memory caching?
- [ ] What's the timeout for API calls?
- [ ] Should we create backups before modification?

## 2. Proposed Changes

Implementation details here.

## Definition of Done

- [ ] Tests pass
- [ ] Documentation updated
"""

SAMPLE_EMPTY_VERDICT = ""

SAMPLE_MALFORMED_VERDICT = """
This is just some random text without proper structure.
No verdict markers here.
Maybe APPROVED is mentioned but not properly.
"""


# Fixtures
@pytest.fixture
def sample_approved_verdict():
    return SAMPLE_APPROVED_VERDICT_WITH_RESOLUTIONS


@pytest.fixture
def sample_rejected_verdict():
    return SAMPLE_REJECTED_VERDICT


@pytest.fixture
def sample_draft():
    return SAMPLE_DRAFT_WITH_OPEN_QUESTIONS


@pytest.fixture
def test_client():
    """Test client for API calls - placeholder for integration tests."""
    yield None


# Unit Tests
# -----------

def test_id():
    """Basic sanity test that the module loads correctly."""
    # Verify we can create the basic data structures
    result = VerdictParseResult()
    assert result.verdict_status == "UNKNOWN"
    assert result.resolutions == []
    assert result.suggestions == []


def test_t010(sample_approved_verdict):
    """
    Parse APPROVED verdict with resolved questions | Returns
    VerdictParseResult with resolutions | RED
    """
    result = parse_verdict(sample_approved_verdict)
    
    assert result.verdict_status == "APPROVED"
    assert len(result.resolutions) >= 2
    
    # Check first resolution
    redis_resolution = next(
        (r for r in result.resolutions if "Redis" in r.resolution_text or "redis" in r.resolution_text.lower()),
        None
    )
    assert redis_resolution is not None
    assert "caching" in redis_resolution.question_text.lower() or "Redis" in redis_resolution.resolution_text


def test_t020(sample_approved_verdict):
    """
    Parse APPROVED verdict with Tier 3 suggestions | Returns
    VerdictParseResult with suggestions | RED
    """
    result = parse_verdict(sample_approved_verdict)
    
    assert result.verdict_status == "APPROVED"
    assert len(result.suggestions) >= 1
    
    # Check for performance suggestion
    perf_suggestion = next(
        (s for s in result.suggestions if s.category == "Performance" or "pool" in s.suggestion_text.lower()),
        None
    )
    assert perf_suggestion is not None


def test_t030(sample_rejected_verdict):
    """
    Parse REJECTED verdict | Returns VerdictParseResult with empty
    resolutions | RED
    """
    result = parse_verdict(sample_rejected_verdict)
    
    assert result.verdict_status == "BLOCKED"
    assert len(result.resolutions) == 0
    assert len(result.suggestions) == 0


def test_t040(sample_draft):
    """
    Update draft open questions with resolutions | Checkboxes changed to
    `- [x]` with resolution text | RED
    """
    verdict_result = VerdictParseResult(
        verdict_status="APPROVED",
        resolutions=[
            ResolvedQuestion(
                question_text="Should we use Redis or in-memory caching?",
                resolution_text="Use Redis for production."
            )
        ]
    )
    
    updated_draft, warnings = update_draft(sample_draft, verdict_result)
    
    # Check that the checkbox is now checked
    assert "- [x]" in updated_draft
    assert "**RESOLVED:**" in updated_draft
    assert "Use Redis for production" in updated_draft


def test_t050(sample_draft):
    """
    Update draft with suggestions (new section) | Reviewer Suggestions
    section appended | RED
    """
    verdict_result = VerdictParseResult(
        verdict_status="APPROVED",
        suggestions=[
            Tier3Suggestion(
                suggestion_text="Consider adding connection pooling",
                category="Performance"
            )
        ]
    )
    
    updated_draft, warnings = update_draft(sample_draft, verdict_result)
    
    assert "## Reviewer Suggestions" in updated_draft
    assert "connection pooling" in updated_draft


def test_t060(sample_draft, caplog):
    """
    Handle missing open question in draft | Log warning, continue
    processing | RED
    """
    verdict_result = VerdictParseResult(
        verdict_status="APPROVED",
        resolutions=[
            ResolvedQuestion(
                question_text="This question does not exist in the draft at all xyz123",
                resolution_text="Some resolution"
            )
        ]
    )
    
    updated_draft, warnings = update_draft(sample_draft, verdict_result)
    
    # Should have a warning about missing question
    assert len(warnings) > 0
    assert any("Could not find" in w or "not found" in w.lower() for w in warnings)
    
    # Draft should be mostly unchanged (no resolution applied)
    # But should not raise an error


def test_t090(sample_draft):
    """
    Idempotency: same verdict applied twice | Same result both times |
    RED
    """
    verdict_result = VerdictParseResult(
        verdict_status="APPROVED",
        resolutions=[
            ResolvedQuestion(
                question_text="Should we use Redis or in-memory caching?",
                resolution_text="Use Redis for production."
            )
        ]
    )
    
    # Apply once
    updated_draft_1, _ = update_draft(sample_draft, verdict_result)
    
    # Apply again to the already-updated draft
    updated_draft_2, _ = update_draft(updated_draft_1, verdict_result)
    
    # Should be the same
    assert updated_draft_1 == updated_draft_2


def test_010():
    """
    Parse approved verdict with resolutions | Auto | Verdict with "Open
    Questions: RESOLVED" | List of ResolvedQuestion | Correct questions
    and resolution text extracted
    """
    verdict = """
## Verdict
[x] **APPROVED**

## Open Questions Resolved
- [x] ~~Should we use async?~~ **RESOLVED:** Yes, use async for all I/O operations.
"""
    result = parse_verdict(verdict)
    
    assert result.verdict_status == "APPROVED"
    assert len(result.resolutions) >= 1
    
    async_resolution = result.resolutions[0]
    assert "async" in async_resolution.question_text.lower()
    assert "async" in async_resolution.resolution_text.lower()


def test_020():
    """
    Parse approved verdict with suggestions | Auto | Verdict with "Tier
    3" section | List of Tier3Suggestion | All suggestions captured
    """
    verdict = """
[x] **APPROVED**

## Tier 3 Suggestions
- Add logging for debugging
- **Security:** Consider rate limiting
"""
    result = parse_verdict(verdict)
    
    assert result.verdict_status == "APPROVED"
    assert len(result.suggestions) >= 2


def test_030():
    """
    Parse rejected verdict | Auto | REJECTED verdict | Empty resolutions
    list | No resolutions extracted
    """
    verdict = """
[x] **REVISE**

## Issues
- Needs more testing
"""
    result = parse_verdict(verdict)
    
    assert result.verdict_status == "BLOCKED"
    assert len(result.resolutions) == 0


def test_040():
    """
    Update draft checkboxes | Auto | Draft + resolutions | Updated draft
    """
    draft = """## Open Questions
- [ ] Use sync or async?
"""
    verdict_result = VerdictParseResult(
        verdict_status="APPROVED",
        resolutions=[
            ResolvedQuestion(
                question_text="Use sync or async?",
                resolution_text="Use async."
            )
        ]
    )
    
    updated, warnings = update_draft(draft, verdict_result)
    
    assert "- [x]" in updated
    assert "**RESOLVED:**" in updated


def test_050():
    """
    Add suggestions section | Auto | Draft + suggestions | Updated draft
    | New section at end
    """
    draft = """# My Document

## Content
Some content here.
"""
    verdict_result = VerdictParseResult(
        verdict_status="APPROVED",
        suggestions=[
            Tier3Suggestion(suggestion_text="Add error handling")
        ]
    )
    
    updated, warnings = update_draft(draft, verdict_result)
    
    assert "## Reviewer Suggestions" in updated
    assert "Add error handling" in updated


def test_060(caplog):
    """
    Missing question in draft | Auto | Resolution for non-existent
    question | Warning logged, draft unchanged | No error thrown
    """
    draft = """## Open Questions
- [ ] Question A?
"""
    verdict_result = VerdictParseResult(
        verdict_status="APPROVED",
        resolutions=[
            ResolvedQuestion(
                question_text="Completely different question XYZ",
                resolution_text="Answer"
            )
        ]
    )
    
    updated, warnings = update_draft(draft, verdict_result)
    
    # Should not raise, should return warnings
    assert len(warnings) > 0


def test_090():
    """
    Idempotent update | Auto | Apply same verdict twice | Same draft | No
    duplicate markers
    """
    draft = """## Open Questions
- [ ] Question A?
"""
    verdict_result = VerdictParseResult(
        verdict_status="APPROVED",
        resolutions=[
            ResolvedQuestion(
                question_text="Question A?",
                resolution_text="Answer A"
            )
        ]
    )
    
    updated1, _ = update_draft(draft, verdict_result)
    updated2, _ = update_draft(updated1, verdict_result)
    
    assert updated1 == updated2
    # Should only have one RESOLVED marker
    assert updated2.count("**RESOLVED:**") == 1


def test_100():
    """
    Empty Open Questions section | Auto | Verdict resolves nothing |
    Unchanged draft | No modifications
    """
    draft = """# Document
## Open Questions
*No questions at this time.*

## Content
Here is some content.
"""
    verdict_result = VerdictParseResult(
        verdict_status="APPROVED",
        resolutions=[],
        suggestions=[]
    )
    
    updated, warnings = update_draft(draft, verdict_result)
    
    # Draft should be unchanged
    assert updated == draft


def test_110():
    """
    Malformed verdict | Auto | Verdict missing expected sections |
    Warning, original draft | Graceful degradation
    """
    result = parse_verdict(SAMPLE_MALFORMED_VERDICT)
    
    # Should not crash, should return something sensible
    assert result is not None
    assert result.verdict_status in ["UNKNOWN", "APPROVED", "BLOCKED"]
    
    # Resolutions might be empty since format is unrecognized
    # The key is it doesn't crash


# Integration Tests
# -----------------

@pytest.mark.integration
def test_070(test_client):
    """
    Review node integration | Auto | State with APPROVED verdict | State
    with updated_draft | Draft contains resolutions
    """
    # This is a simplified integration test
    # Full integration would require the review node
    
    verdict = SAMPLE_APPROVED_VERDICT_WITH_RESOLUTIONS
    draft = SAMPLE_DRAFT_WITH_OPEN_QUESTIONS
    
    # Parse verdict
    verdict_result = parse_verdict(verdict)
    assert verdict_result.verdict_status == "APPROVED"
    
    # Update draft
    updated_draft, warnings = update_draft(draft, verdict_result)
    
    # Verify integration
    assert "- [x]" in updated_draft
    assert "**RESOLVED:**" in updated_draft


@pytest.mark.integration
def test_080(test_client):
    """
    Finalize node integration | Auto | State with updated_draft | Final
    LLD | LLD contains `- [x]`
    """
    # Simplified integration test
    draft = SAMPLE_DRAFT_WITH_OPEN_QUESTIONS
    verdict_result = VerdictParseResult(
        verdict_status="APPROVED",
        resolutions=[
            ResolvedQuestion(
                question_text="Should we use Redis or in-memory caching?",
                resolution_text="Use Redis."
            )
        ]
    )
    
    updated_draft, _ = update_draft(draft, verdict_result)
    
    # The final LLD should have resolved questions
    assert "- [x]" in updated_draft
    

# E2E Tests
# ---------

@pytest.mark.e2e
def test_t070(test_client):
    """
    End-to-end: review node updates draft on approval | State contains
    updated_draft after approval | RED
    """
    # Simulate the full flow
    original_draft = SAMPLE_DRAFT_WITH_OPEN_QUESTIONS
    verdict = SAMPLE_APPROVED_VERDICT_WITH_RESOLUTIONS
    
    # Step 1: Parse verdict
    verdict_result = parse_verdict(verdict)
    assert verdict_result.verdict_status == "APPROVED"
    
    # Step 2: Update draft
    updated_draft, warnings = update_draft(original_draft, verdict_result)
    
    # Step 3: Verify state would have updated_draft
    assert updated_draft != original_draft
    assert "- [x]" in updated_draft


@pytest.mark.e2e
def test_t080(test_client):
    """
    End-to-end: finalize uses updated draft | Final LLD contains resolved
    questions | RED
    """
    # Simulate the workflow
    draft = SAMPLE_DRAFT_WITH_OPEN_QUESTIONS
    verdict = SAMPLE_APPROVED_VERDICT_WITH_RESOLUTIONS
    
    # Parse and update
    verdict_result = parse_verdict(verdict)
    updated_draft, _ = update_draft(draft, verdict_result)
    
    # Finalize would use this updated_draft
    # The final LLD should contain resolved questions
    assert "- [x]" in updated_draft
    assert "**RESOLVED:**" in updated_draft
```
