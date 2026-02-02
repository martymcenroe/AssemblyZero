# File: tools/verdict_analyzer/template_updater.py

```python
"""Safe template modification with atomic writes."""

from __future__ import annotations

import logging
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from tools.verdict_analyzer.patterns import map_category_to_section

logger = logging.getLogger(__name__)


@dataclass
class Recommendation:
    """A template improvement recommendation."""
    
    rec_type: str  # 'add_section', 'add_checklist_item', 'add_example'
    section: str
    content: str
    reason: str
    pattern_count: int


def validate_template_path(template_path: Path, base_dir: Optional[Path] = None) -> bool:
    """Validate that a template path is safe to write to.
    
    Args:
        template_path: Path to validate
        base_dir: Base directory that template must be within
        
    Returns:
        True if path is valid
        
    Raises:
        ValueError: If path is invalid or attempts traversal
    """
    template_path = template_path.resolve()
    
    # Check for path traversal attempts
    if ".." in str(template_path):
        raise ValueError(f"Path traversal detected in: {template_path}")
    
    # If base_dir provided, ensure template is within it
    if base_dir is not None:
        base_dir = base_dir.resolve()
        try:
            template_path.relative_to(base_dir)
        except ValueError:
            raise ValueError(f"Template path {template_path} is not within {base_dir}")
    
    # Check it's a markdown file
    if template_path.suffix.lower() not in (".md", ".markdown"):
        raise ValueError(f"Template must be a markdown file: {template_path}")
    
    return True


def parse_template_sections(content: str) -> dict[str, str]:
    """Parse a markdown template into sections.
    
    Args:
        content: Template markdown content
        
    Returns:
        Dictionary mapping section headers to content
    """
    sections: dict[str, str] = {}
    
    # Split by headers (## or ###)
    header_pattern = r"^(#{2,3})\s+(.+)$"
    
    lines = content.split("\n")
    current_header = None
    current_content: list[str] = []
    
    for line in lines:
        match = re.match(header_pattern, line)
        if match:
            # Save previous section
            if current_header:
                sections[current_header] = "\n".join(current_content).strip()
            
            current_header = match.group(2).strip()
            current_content = []
        else:
            current_content.append(line)
    
    # Save last section
    if current_header:
        sections[current_header] = "\n".join(current_content).strip()
    
    return sections


def generate_recommendations(
    pattern_stats: dict,
    existing_sections: dict[str, str],
    min_pattern_count: int = 3,
) -> list[Recommendation]:
    """Generate template improvement recommendations.
    
    Args:
        pattern_stats: Statistics from VerdictDatabase.get_pattern_stats()
        existing_sections: Current template sections
        min_pattern_count: Minimum occurrences to recommend
        
    Returns:
        List of recommendations
    """
    recommendations = []
    
    category_counts = pattern_stats.get("categories", {})
    
    for category, count in category_counts.items():
        if count < min_pattern_count:
            continue
        
        section = map_category_to_section(category)
        
        # Check if section exists
        section_exists = any(
            section.lower() in s.lower()
            for s in existing_sections.keys()
        )
        
        if not section_exists:
            recommendations.append(Recommendation(
                rec_type="add_section",
                section=section,
                content=f"## {section}\n\n*Add details about {category} requirements.*\n",
                reason=f"Category '{category}' has {count} blocking issues but no template section",
                pattern_count=count,
            ))
        else:
            # Recommend adding checklist item
            recommendations.append(Recommendation(
                rec_type="add_checklist_item",
                section=section,
                content=f"- [ ] Address {category} considerations",
                reason=f"Category '{category}' frequently causes blocking issues ({count} occurrences)",
                pattern_count=count,
            ))
    
    # Sort by pattern count descending
    recommendations.sort(key=lambda r: r.pattern_count, reverse=True)
    
    return recommendations


def atomic_write_template(
    template_path: Path,
    content: str,
    create_backup: bool = True,
) -> Path:
    """Atomically write content to template with backup.
    
    Args:
        template_path: Path to template file
        content: New content to write
        create_backup: Whether to create .bak file
        
    Returns:
        Path to backup file (or template_path if no backup)
    """
    template_path = Path(template_path)
    backup_path = template_path.with_suffix(template_path.suffix + ".bak")
    
    # Create backup
    if create_backup and template_path.exists():
        shutil.copy2(template_path, backup_path)
        logger.info(f"Created backup: {backup_path}")
    
    # Write to temp file first
    temp_path = template_path.with_suffix(".tmp")
    temp_path.write_text(content, encoding="utf-8")
    
    # Atomic rename
    temp_path.replace(template_path)
    
    logger.info(f"Updated template: {template_path}")
    
    return backup_path if create_backup else template_path


def format_stats(stats: dict) -> str:
    """Format statistics for display.
    
    Args:
        stats: Statistics dictionary from get_pattern_stats()
        
    Returns:
        Formatted string
    """
    lines = [
        "Verdict Analysis Statistics",
        "=" * 40,
        f"Total Verdicts: {stats.get('total_verdicts', 0)}",
        f"Total Blocking Issues: {stats.get('total_issues', 0)}",
        "",
        "Decisions:",
    ]
    
    for decision, count in stats.get("decisions", {}).items():
        lines.append(f"  {decision}: {count}")
    
    lines.extend(["", "Issues by Tier:"])
    for tier, count in sorted(stats.get("tiers", {}).items()):
        lines.append(f"  Tier {tier}: {count}")
    
    lines.extend(["", "Issues by Category:"])
    for category, count in sorted(
        stats.get("categories", {}).items(),
        key=lambda x: x[1],
        reverse=True,
    ):
        lines.append(f"  {category}: {count}")
    
    return "\n".join(lines)
```