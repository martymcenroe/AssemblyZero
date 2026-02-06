"""Draft updater for applying verdict resolutions.

Issue #257: Update draft LLD with:
- Resolved open questions (mark checkboxes as [x] with resolution)
- Tier 3 suggestions (append new section)
"""

import logging
import re
from typing import List, Tuple

from assemblyzero.workflows.requirements.parsers.verdict_parser import (
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