# File: agentos/workflows/requirements/parsers/verdict_parser.py

```python
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