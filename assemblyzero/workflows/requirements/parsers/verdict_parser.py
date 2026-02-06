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