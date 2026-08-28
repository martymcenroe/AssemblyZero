"""Section-level revision utilities.

Issue #489: Section-level revision for LLD and Implementation Spec workflows.

Provides utilities to extract markdown sections, identify which sections
are referenced in feedback, and build targeted revision prompts that only
include changed sections + context, reducing token usage by 50-80% on
focused revisions.
"""

import re
from dataclasses import dataclass


@dataclass
class Section:
    """A section extracted from a markdown document.

    Attributes:
        heading: The heading text (without # prefix).
        content: The full content including the heading line.
        level: Heading level (1-6).
    """

    heading: str
    content: str
    level: int


def extract_sections(markdown: str) -> list[Section]:
    """Extract sections from a markdown document.

    Splits on ## and ### headings (levels 2-3). Level 1 headings (#) are
    treated as the document title and included in the first section.

    Args:
        markdown: Raw markdown content.

    Returns:
        List of Section objects in document order.
    """
    if not markdown or not markdown.strip():
        return []

    sections: list[Section] = []
    current_heading = ""
    current_level = 0
    current_lines: list[str] = []

    for line in markdown.split("\n"):
        # Match ## or ### headings (level 2-3)
        heading_match = re.match(r"^(#{2,3})\s+(.+)$", line)

        if heading_match:
            # Flush previous section
            if current_lines:
                sections.append(Section(
                    heading=current_heading,
                    content="\n".join(current_lines),
                    level=current_level,
                ))

            current_heading = heading_match.group(2).strip()
            current_level = len(heading_match.group(1))
            current_lines = [line]
        else:
            current_lines.append(line)

    # Flush last section
    if current_lines:
        sections.append(Section(
            heading=current_heading,
            content="\n".join(current_lines),
            level=current_level,
        ))

    return sections


#: Any ATX heading, with its level. One notion of "heading" for the boundary
#: rule below, so a section's extent is never a second opinion.
_HEADING_RE = re.compile(r"^(#{1,6})[ \t]*(.*)$", re.MULTILINE)


def section_body(markdown: str, title_pattern: re.Pattern) -> str | None:
    """The body of the first heading matching ``title_pattern``, subsections
    included. ``None`` when no heading matches.

    **The boundary is LEVEL-AWARE, and that is the whole point (#2628).** A
    section ends at the next heading of the same or higher level; a deeper
    heading belongs to it.

    The rule this replaces ended Section 3 at the next heading beginning with
    a digit:

        (?=^#{1,3}\\s*\\d|^#{1,3}\\s*[A-Z]|\\Z)

    which was correct until #2607 injection began inserting
    ``### 3.1 Source Decision Table (injected verbatim)`` INSIDE Section 3.
    The lookahead then fired on the injected subheading, so Section 3 captured
    the 62 characters before it -- a blank line and an HTML comment -- and the
    drafter's numbered requirements below the block were invisible. Measured on
    boostgauge's halted draw `run-issue331-152355`: 0 requirements extracted
    from a document that carries 4.

    Level, not first-character, is what separates "the next section" from "a
    subsection of this one", and it is the only rule that stays correct as more
    machine-owned subsections are injected.
    """
    for match in _HEADING_RE.finditer(markdown or ""):
        level = len(match.group(1))
        if not title_pattern.match(match.group(2).strip()):
            continue
        start = match.end()
        for following in _HEADING_RE.finditer(markdown, start):
            if len(following.group(1)) <= level:
                return markdown[start:following.start()]
        return markdown[start:]
    return None


def drafter_authored(markdown: str) -> str:
    """``markdown`` with every machine-owned block removed (#2628).

    Requirement extraction reads what the DRAFTER wrote. #2607's injected block
    is authored by the derivation, is restored verbatim on every revision, and
    its rows are a binding-value reference the requirements cite -- its own
    preamble says so: *"Cite these IDs from the requirements and test-plan
    sections; do not restate their values."*

    Removing it before parsing is not cosmetic. The extractor accumulates
    unnumbered lines as continuation text of the preceding requirement, so a
    numbered item sitting above an injected block would silently swallow the
    whole table into its text.

    Imported lazily: `requirements.table_injection` reaches
    `implementation_spec.assertion_manifest`, which pulls a package whose
    `__init__` imports the spec graph. A module-level import here would build a
    cycle for a three-line call. Same reasoning, and the same shape, as
    `generate_spec._spec_injection` (#2611).
    """
    try:
        from assemblyzero.workflows.requirements.table_injection import (
            strip_injection,
        )
    except ImportError:
        # fail-open: only in shape -- with no stripper available the caller
        # parses the document as it stands, which is the pre-#2628 behaviour.
        # A missing import must never make a valid LLD unreadable.
        return markdown or ""
    return strip_injection(markdown or "")


def identify_changed_sections(
    feedback: str | dict,
    sections: list[Section],
) -> list[str]:
    """Identify which sections are referenced in feedback.

    Supports two feedback formats:
    1. Structured verdict (dict with blocking_issues[].section) from #492
    2. Free-text feedback — matches section headings mentioned in text

    Args:
        feedback: Either a structured verdict dict or free-text feedback string.
        sections: List of sections from the document.

    Returns:
        List of heading names that are referenced in the feedback.
        Empty list if feedback is too generic to map to sections.
    """
    if not feedback or not sections:
        return []

    # Structured verdict (Issue #492 integration)
    if isinstance(feedback, dict):
        return _identify_from_structured(feedback, sections)

    # Free-text feedback
    return _identify_from_freetext(feedback, sections)


def _identify_from_structured(
    verdict: dict,
    sections: list[Section],
) -> list[str]:
    """Extract section references from structured verdict.

    Args:
        verdict: Structured verdict dict with blocking_issues.
        sections: Available sections.

    Returns:
        List of matching heading names.
    """
    referenced: set[str] = set()

    blocking_issues = verdict.get("blocking_issues", [])
    for issue in blocking_issues:
        section_ref = issue.get("section", "")
        if section_ref:
            # Try exact match first
            for section in sections:
                if section.heading.lower() == section_ref.lower():
                    referenced.add(section.heading)
                    break
            else:
                # Try partial match
                for section in sections:
                    if section_ref.lower() in section.heading.lower():
                        referenced.add(section.heading)
                        break

    return list(referenced)


def _identify_from_freetext(
    feedback: str,
    sections: list[Section],
) -> list[str]:
    """Match section headings mentioned in free-text feedback.

    Args:
        feedback: Free-text feedback string.
        sections: Available sections.

    Returns:
        List of matching heading names.
    """
    referenced: list[str] = []
    feedback_lower = feedback.lower()

    for section in sections:
        if not section.heading:
            continue

        heading_lower = section.heading.lower()

        # Skip very short headings that would match too broadly
        if len(heading_lower) < 4:
            continue

        # Check if heading text appears in feedback
        if heading_lower in feedback_lower:
            referenced.append(section.heading)
            continue

        # Check for section number references like "Section 2.1" or "2.1"
        number_match = re.search(r"(\d+(?:\.\d+)*)", section.heading)
        if number_match:
            section_num = number_match.group(1)
            # Look for "section X.Y" or just "X.Y" in feedback
            if re.search(
                rf"(?:section\s+)?{re.escape(section_num)}\b",
                feedback_lower,
            ):
                referenced.append(section.heading)

    return referenced


def build_targeted_prompt(
    sections: list[Section],
    changed_headings: list[str],
    template: str,
    feedback: str,
) -> str:
    """Build a targeted revision prompt with only changed sections in full.

    Includes:
    - Changed sections in full
    - 1 adjacent section before/after each changed section for context
    - Unchanged sections as heading stubs (collapsed)
    - Relevant template portions only

    Falls back to full content if feedback can't be mapped to sections
    (changed_headings is empty).

    Args:
        sections: All sections from the document.
        changed_headings: Headings of sections that need revision.
        template: Full template content.
        feedback: The feedback/review text.

    Returns:
        Targeted revision prompt string.
    """
    if not changed_headings or not sections:
        # Can't target — return None to signal caller should use full prompt
        return ""

    # Build set of indices that should be shown in full
    changed_indices: set[int] = set()
    for i, section in enumerate(sections):
        if section.heading in changed_headings:
            changed_indices.add(i)

    # Add adjacent sections for context
    context_indices: set[int] = set()
    for idx in changed_indices:
        if idx > 0:
            context_indices.add(idx - 1)
        if idx < len(sections) - 1:
            context_indices.add(idx + 1)

    full_indices = changed_indices | context_indices

    # Build the targeted content
    parts: list[str] = []
    parts.append("## Current Draft (targeted sections for revision)\n")
    parts.append(
        "Sections marked [UNCHANGED] are collapsed — preserve them as-is.\n"
        "Focus your revision on the sections shown in full.\n"
    )

    for i, section in enumerate(sections):
        if i in changed_indices:
            parts.append(f"### [REVISE] {section.heading}\n")
            parts.append(section.content)
        elif i in context_indices:
            parts.append(f"### [CONTEXT] {section.heading}\n")
            parts.append(section.content)
        else:
            # Collapsed stub
            level_prefix = "#" * max(section.level, 2)
            if section.heading:
                parts.append(f"{level_prefix} [UNCHANGED] {section.heading}\n")
            # Don't include content for unchanged sections

    # Add feedback
    parts.append(f"\n## Feedback to Address\n\n{feedback}")

    # Extract relevant template sections
    template_sections = extract_sections(template)
    if template_sections and changed_headings:
        relevant_template = _extract_relevant_template(
            template_sections, changed_headings
        )
        if relevant_template:
            parts.append(f"\n## Relevant Template Sections\n\n{relevant_template}")

    return "\n\n".join(parts)


def _extract_relevant_template(
    template_sections: list[Section],
    changed_headings: list[str],
) -> str:
    """Extract template sections relevant to the changed headings.

    Args:
        template_sections: Sections from the template.
        changed_headings: Headings that need revision.

    Returns:
        Relevant template portions as a string.
    """
    relevant: list[str] = []
    changed_lower = {h.lower() for h in changed_headings}

    for section in template_sections:
        heading_lower = section.heading.lower()
        # Check if any changed heading matches this template section
        for changed in changed_lower:
            if changed in heading_lower or heading_lower in changed:
                relevant.append(section.content)
                break

    return "\n\n".join(relevant)
