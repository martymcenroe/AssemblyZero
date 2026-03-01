"""Auto-fix rules for Ponder Stibbons node.

Issue #307: Mechanical auto-fix rules that correct common LLD formatting
issues without requiring an LLM round-trip.

Each rule is a function that takes (draft, context) and returns
(fixed_draft, list_of_fixes_applied). Rules are deterministic — no LLM calls.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class AutoFix:
    """Record of a single auto-fix applied to a draft."""

    rule: str
    description: str
    section: str


def fix_title_issue_number(
    draft: str, ctx: dict[str, Any]
) -> tuple[str, list[AutoFix]]:
    """Fix incorrect issue number in the H1 title.

    Example: `# 199 - Feature Name` -> `# 99 - Feature Name`
    when issue_number=99.
    """
    issue_number = ctx.get("issue_number")
    if issue_number is None:
        return draft, []

    # Match H1 with a number that doesn't match
    pattern = r"^(#\s+)(\d+)(\s*[-—:])"
    match = re.search(pattern, draft, re.MULTILINE)
    if not match:
        return draft, []

    found_number = int(match.group(2))
    if found_number == issue_number:
        return draft, []

    fixed = re.sub(
        pattern,
        rf"\g<1>{issue_number}\3",
        draft,
        count=1,
        flags=re.MULTILINE,
    )
    return fixed, [
        AutoFix(
            rule="title_issue_number",
            description=f"Fixed title issue number: {found_number} -> {issue_number}",
            section="Title",
        )
    ]


def fix_section_heading_format(
    draft: str, ctx: dict[str, Any]
) -> tuple[str, list[AutoFix]]:
    """Normalize section headings to ## N. format.

    Fixes:
    - `### 11` -> `## 11.`
    - `## 11` -> `## 11.` (missing trailing dot)
    - `### 2.1` -> `## 2.1` (wrong heading level for numbered sections)
    """
    fixes: list[AutoFix] = []

    def _fix_heading(m: re.Match) -> str:
        hashes = m.group(1)
        num = m.group(2)

        needs_fix = False
        new_hashes = hashes

        # Subsection like 2.1 should be ###, top-level like 2 should be ##
        is_subsection = "." in num
        expected_hashes = "###" if is_subsection else "##"

        if hashes != expected_hashes:
            new_hashes = expected_hashes
            needs_fix = True

        # Add trailing dot if missing (only for top-level sections)
        trailing = m.group(3)
        if not is_subsection and not trailing.startswith("."):
            trailing = "." + trailing
            needs_fix = True

        if needs_fix:
            fixes.append(
                AutoFix(
                    rule="section_heading_format",
                    description=f"Normalized heading: '{m.group(0).strip()}' -> '{new_hashes} {num}{trailing}'.strip()",
                    section=num,
                )
            )

        return f"{new_hashes} {num}{trailing}"

    # Match section headings like ## N or ### N.N
    fixed = re.sub(
        r"^(#{2,3})\s+(\d+(?:\.\d+)?)(\.?\s)",
        _fix_heading,
        draft,
        flags=re.MULTILINE,
    )

    return fixed, fixes


def fix_trailing_whitespace(
    draft: str, ctx: dict[str, Any]
) -> tuple[str, list[AutoFix]]:
    """Strip trailing whitespace from all lines."""
    lines = draft.split("\n")
    fixed_count = 0
    for i, line in enumerate(lines):
        stripped = line.rstrip()
        if stripped != line:
            lines[i] = stripped
            fixed_count += 1

    if fixed_count == 0:
        return draft, []

    return "\n".join(lines), [
        AutoFix(
            rule="trailing_whitespace",
            description=f"Stripped trailing whitespace from {fixed_count} lines",
            section="*",
        )
    ]


def fix_missing_blank_before_heading(
    draft: str, ctx: dict[str, Any]
) -> tuple[str, list[AutoFix]]:
    """Insert blank line before headings when missing.

    Markdown best practice: headings should have a blank line before them.
    """
    fixes: list[AutoFix] = []
    lines = draft.split("\n")
    result: list[str] = []

    for i, line in enumerate(lines):
        if i > 0 and line.startswith("#") and result and result[-1].strip():
            result.append("")
            fixes.append(
                AutoFix(
                    rule="blank_before_heading",
                    description=f"Inserted blank line before heading at line {i + 1}",
                    section="*",
                )
            )
        result.append(line)

    if not fixes:
        return draft, []

    return "\n".join(result), fixes


# Registry of all auto-fix rules, applied in order
PONDER_RULES = [
    fix_title_issue_number,
    fix_section_heading_format,
    fix_trailing_whitespace,
    fix_missing_blank_before_heading,
]


def apply_all_rules(
    draft: str, ctx: dict[str, Any]
) -> tuple[str, list[AutoFix]]:
    """Apply all Ponder rules in sequence.

    Args:
        draft: The LLD markdown content.
        ctx: Context dict with keys like 'issue_number'.

    Returns:
        Tuple of (fixed_draft, all_fixes_applied).
    """
    all_fixes: list[AutoFix] = []
    current = draft

    for rule in PONDER_RULES:
        current, fixes = rule(current, ctx)
        all_fixes.extend(fixes)

    return current, all_fixes
