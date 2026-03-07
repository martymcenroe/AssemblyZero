"""LLD section extractor utility.

Issue #642: Extract file-relevant sections from LLD markdown to support
tiered context pruning in retry prompts.
"""

from __future__ import annotations

import logging
import os
import re
from typing import TypedDict

logger = logging.getLogger(__name__)


class ExtractedSection(TypedDict):
    """Result of extracting a single relevant section from an LLD."""

    section_heading: str
    section_body: str
    match_confidence: float


def extract_file_spec_section(
    lld_content: str, target_file: str
) -> ExtractedSection | None:
    """Parse LLD markdown and extract the section most relevant to target_file.

    Strategy:
      1. Split LLD into heading-delimited sections.
      2. Score each section for relevance to target_file.
      3. Return the highest-scoring section if score > 0.0.
      4. Return None if no section matches.

    Args:
        lld_content: Full LLD markdown string.
        target_file: Relative file path (e.g., "assemblyzero/services/alpha_service.py").

    Returns:
        ExtractedSection if a relevant section is found, None otherwise.

    Raises:
        ValueError: If lld_content is empty.
    """
    if not lld_content.strip():
        raise ValueError("lld_content must not be empty")

    sections = _split_lld_into_sections(lld_content)
    if not sections:
        return None

    best_score = 0.0
    best_heading = ""
    best_body = ""

    normalized_target = target_file.replace("\\", "/")

    for heading, body in sections:
        score = _score_section_for_file(body, target_file)
        # Boost score when the exact target path appears in the heading —
        # this distinguishes file-specific sections from summary tables
        # that mention many files. Only exact path match triggers the boost
        # to avoid false positives from stem-only matches.
        if normalized_target in heading:
            score += 0.5
        if score > best_score:
            best_score = score
            best_heading = heading
            best_body = body

    # Cap confidence to [0.0, 1.0]
    best_score = min(best_score, 1.0)

    if best_score == 0.0:
        return None

    return ExtractedSection(
        section_heading=best_heading,
        section_body=best_body,
        match_confidence=best_score,
    )


def _split_lld_into_sections(lld_content: str) -> list[tuple[str, str]]:
    """Split LLD markdown into (heading, body) tuples at ## and ### boundaries.

    Args:
        lld_content: Full LLD markdown.

    Returns:
        List of (heading_text, full_section_text_including_heading) tuples.
    """
    # Split only at ## level to keep ### subsections within their parent
    heading_pattern = re.compile(r"^(#{1,2})\s+(.+)$", re.MULTILINE)
    matches = list(heading_pattern.finditer(lld_content))

    if not matches:
        return [("", lld_content)]

    sections: list[tuple[str, str]] = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(lld_content)
        heading_line = match.group(0).strip()
        section_text = lld_content[start:end]
        sections.append((heading_line, section_text))

    return sections


def _score_section_for_file(section_text: str, target_file: str) -> float:
    """Score how relevant a section is to target_file.

    Scoring rules:
      - Exact path match in section text: 1.0
      - Filename stem match (basename without extension): 0.6
      - Directory name match (parent directory path): 0.3
      - No match: 0.0

    Args:
        section_text: Full text of an LLD section.
        target_file: Target file relative path.

    Returns:
        Float relevance score 0.0–1.0.
    """
    # Normalize path separators
    normalized_target = target_file.replace("\\", "/")

    # Exact path match
    if normalized_target in section_text:
        return 1.0

    # Filename stem match (e.g., "alpha_service" from "alpha_service.py")
    basename = os.path.basename(normalized_target)
    stem = os.path.splitext(basename)[0]
    if stem and stem in section_text:
        return 0.6

    # Directory name match (e.g., "assemblyzero/services" from path)
    parent_dir = os.path.dirname(normalized_target)
    if parent_dir and parent_dir in section_text:
        return 0.3

    return 0.0