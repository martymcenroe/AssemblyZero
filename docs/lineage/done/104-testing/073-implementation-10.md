# File: tools/verdict_analyzer/template_updater.py

```python
"""Template modification with atomic writes."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from tools.verdict_analyzer.patterns import CATEGORY_TO_SECTION


@dataclass
class Recommendation:
    """A template improvement recommendation."""

    rec_type: str  # "add_section", "add_checklist_item", "add_example"
    section: str
    content: str
    pattern_count: int


def parse_template_sections(content: str) -> dict[str, str]:
    """Parse a template into sections.

    Args:
        content: Template markdown content.

    Returns:
        Dictionary mapping section names to their content.
    """
    if not content:
        return {}

    sections: dict[str, str] = {}

    # Find all headers (## and ###)
    header_pattern = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)
    matches = list(header_pattern.finditer(content))

    if not matches:
        return {}

    for i, match in enumerate(matches):
        section_name = match.group(2).strip()
        start = match.end()

        # Find end (next header or EOF)
        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(content)

        section_content = content[start:end].strip()
        sections[section_name] = section_content

    return sections


def generate_recommendations(
    pattern_stats: dict,
    existing_sections: dict[str, str],
    min_pattern_count: int = 3,
) -> list[Recommendation]:
    """Generate template improvement recommendations.

    Args:
        pattern_stats: Statistics from pattern analysis.
        existing_sections: Existing template sections.
        min_pattern_count: Minimum count to generate recommendation.

    Returns:
        List of Recommendation objects.
    """
    recommendations: list[Recommendation] = []

    categories = pattern_stats.get("categories", {})

    for category, count in categories.items():
        if count < min_pattern_count:
            continue

        section = CATEGORY_TO_SECTION.get(category, "Implementation Notes")

        if section not in existing_sections:
            # Recommend adding new section
            recommendations.append(
                Recommendation(
                    rec_type="add_section",
                    section=section,
                    content=f"Add {section} section to address common {category} issues",
                    pattern_count=count,
                )
            )
        else:
            # Recommend adding checklist item
            recommendations.append(
                Recommendation(
                    rec_type="add_checklist_item",
                    section=section,
                    content=f"Add checklist item for {category} validation",
                    pattern_count=count,
                )
            )

    return recommendations


def atomic_write_template(filepath: Path, content: str) -> Path:
    """Write template content atomically with backup.

    Args:
        filepath: Path to template file.
        content: New content to write.

    Returns:
        Path to backup file.
    """
    # Create backup
    backup_path = filepath.with_suffix(filepath.suffix + ".bak")
    shutil.copy2(filepath, backup_path)

    # Write new content
    filepath.write_text(content, encoding="utf-8")

    return backup_path


def validate_template_path(filepath: Path, base_dir: Path) -> None:
    """Validate template path is within base directory.

    Args:
        filepath: Path to validate.
        base_dir: Base directory path must be within.

    Raises:
        ValueError: If path is outside base directory.
    """
    try:
        filepath.resolve().relative_to(base_dir.resolve())
    except ValueError:
        raise ValueError(
            f"Path traversal detected: {filepath} is not within {base_dir}"
        )


def format_stats(stats: dict) -> str:
    """Format statistics for display.

    Args:
        stats: Statistics dictionary.

    Returns:
        Formatted string.
    """
    lines = [
        f"Total Verdicts: {stats.get('total_verdicts', 0)}",
        f"Total Blocking Issues: {stats.get('total_issues', 0)}",
        "",
        "Decisions:",
    ]

    for decision, count in stats.get("decisions", {}).items():
        lines.append(f"  {decision}: {count}")

    lines.append("")
    lines.append("By Tier:")

    for tier, count in stats.get("tiers", {}).items():
        lines.append(f"  Tier {tier}: {count}")

    lines.append("")
    lines.append("By Category:")

    for category, count in stats.get("categories", {}).items():
        lines.append(f"  {category}: {count}")

    return "\n".join(lines)
```