# File: tools/verdict_analyzer/template_updater.py

```python
"""Safe template modification with atomic writes."""

import re
import shutil
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Recommendation:
    """A recommendation for template improvement."""

    type: str  # 'add_guidance', 'add_example', 'add_warning'
    section: str
    content: str
    priority: int = 0  # Higher = more important


def validate_template_path(template_path: Path, allowed_roots: Optional[list[Path]] = None) -> bool:
    """Validate that a template path is safe to modify.

    Args:
        template_path: Path to template file
        allowed_roots: List of allowed root directories (defaults to cwd)

    Returns:
        True if path is valid, False otherwise
    """
    if allowed_roots is None:
        allowed_roots = [Path.cwd()]

    resolved = template_path.resolve()

    # Check for path traversal
    for root in allowed_roots:
        try:
            resolved.relative_to(root.resolve())
            return True
        except ValueError:
            continue

    logger.error(f"Path traversal detected: {template_path} is not under allowed roots")
    return False


def parse_template_sections(content: str) -> dict[str, str]:
    """Parse a template into sections.

    Args:
        content: Template content

    Returns:
        Dictionary mapping section names to content
    """
    sections = {}

    # Split by ## headers
    parts = re.split(r"(?=^## )", content, flags=re.MULTILINE)

    for part in parts:
        if not part.strip():
            continue

        # Extract section name from header
        header_match = re.match(r"^## (.+?)$", part, re.MULTILINE)
        if header_match:
            section_name = header_match.group(1).strip()
            section_content = part[header_match.end() :].strip()
            sections[section_name] = section_content
        elif not sections:
            # Content before first header
            sections["_preamble"] = part.strip()

    return sections


def generate_recommendations(pattern_stats: dict, threshold: int = 3) -> list[Recommendation]:
    """Generate recommendations based on pattern statistics.

    Args:
        pattern_stats: Statistics from database.get_pattern_stats()
        threshold: Minimum count to generate recommendation

    Returns:
        List of recommendations
    """
    from .patterns import CATEGORY_TO_SECTION

    recommendations = []

    by_category = pattern_stats.get("by_category", {})

    for category, count in by_category.items():
        if count >= threshold:
            section = CATEGORY_TO_SECTION.get(category.lower(), "General")

            recommendations.append(
                Recommendation(
                    type="add_guidance",
                    section=section,
                    content=f"Consider adding guidance for {category} issues (found {count} times in verdicts)",
                    priority=count,
                )
            )

    # Sort by priority descending
    recommendations.sort(key=lambda r: -r.priority)

    return recommendations


def atomic_write_with_backup(
    template_path: Path, content: str, create_backup: bool = True
) -> tuple[bool, Optional[Path]]:
    """Write content to template with atomic operation and backup.

    Args:
        template_path: Path to template file
        content: New content to write
        create_backup: Whether to create a .bak file

    Returns:
        Tuple of (success, backup_path or None)
    """
    backup_path = None

    try:
        # Create backup if file exists
        if template_path.exists() and create_backup:
            backup_path = template_path.with_suffix(template_path.suffix + ".bak")
            shutil.copy2(template_path, backup_path)
            logger.info(f"Created backup: {backup_path}")

        # Write to temp file first (atomic)
        temp_path = template_path.with_suffix(template_path.suffix + ".tmp")
        temp_path.write_text(content, encoding="utf-8")

        # Rename (atomic on POSIX, close enough on Windows)
        temp_path.replace(template_path)

        logger.info(f"Updated template: {template_path}")
        return True, backup_path

    except Exception as e:
        logger.error(f"Failed to write template: {e}")
        # Restore from backup if available
        if backup_path and backup_path.exists():
            shutil.copy2(backup_path, template_path)
            logger.info("Restored from backup")
        return False, backup_path


def apply_recommendations_preview(
    template_path: Path, recommendations: list[Recommendation]
) -> str:
    """Generate preview of template with recommendations applied.

    Args:
        template_path: Path to template
        recommendations: Recommendations to apply

    Returns:
        Preview content with recommendations as comments
    """
    content = template_path.read_text(encoding="utf-8")
    sections = parse_template_sections(content)

    # Group recommendations by section
    by_section: dict[str, list[Recommendation]] = {}
    for rec in recommendations:
        by_section.setdefault(rec.section, []).append(rec)

    # Build preview with annotations
    lines = []
    for section_name, section_content in sections.items():
        if section_name != "_preamble":
            lines.append(f"## {section_name}")

        lines.append(section_content)

        # Add recommendations as comments
        if section_name in by_section:
            lines.append("")
            lines.append("<!-- VERDICT ANALYZER RECOMMENDATIONS:")
            for rec in by_section[section_name]:
                lines.append(f"  - [{rec.type}] {rec.content}")
            lines.append("-->")

        lines.append("")

    return "\n".join(lines)
```