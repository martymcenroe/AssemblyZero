# File: tools/verdict_analyzer/template_updater.py

```python
"""Template updater module for verdict analyzer.

Handles parsing and updating LLD/issue templates based on verdict patterns.
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class Recommendation:
    """A recommendation for template improvement."""
    type: str
    section: str
    content: str
    priority: int = 0


def parse_template_sections(content: str) -> Dict[str, str]:
    """Parse a markdown template into sections.
    
    Args:
        content: The template markdown content
        
    Returns:
        Dictionary mapping section names to content
    """
    sections = {}
    
    # Split by ## headings
    pattern = r'^##\s+(.+?)$'
    matches = list(re.finditer(pattern, content, re.MULTILINE))
    
    for i, match in enumerate(matches):
        section_name = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        section_content = content[start:end].strip()
        sections[section_name] = section_content
    
    # Also capture the header/intro before first section
    if matches:
        intro = content[:matches[0].start()].strip()
        if intro:
            sections["_intro"] = intro
    
    return sections


def generate_recommendations(pattern_stats: Dict, threshold: int = 3) -> List[Recommendation]:
    """Generate template improvement recommendations from pattern stats.
    
    Args:
        pattern_stats: Statistics from VerdictDatabase.get_pattern_stats()
        threshold: Minimum count for a category to generate a recommendation
        
    Returns:
        List of Recommendation objects
    """
    from .patterns import CATEGORY_TO_SECTION
    
    recommendations = []
    
    by_category = pattern_stats.get("by_category", {})
    
    for category, count in by_category.items():
        if count >= threshold:
            section = CATEGORY_TO_SECTION.get(category.lower(), "General")
            
            rec = Recommendation(
                type="add_guidance",
                section=section,
                content=f"Consider adding guidance for {category} issues (found {count} times)",
                priority=count,
            )
            recommendations.append(rec)
    
    # Sort by priority (highest first)
    recommendations.sort(key=lambda r: r.priority, reverse=True)
    
    return recommendations


def apply_recommendations_preview(template_path: Path, recommendations: List[Recommendation]) -> str:
    """Generate a preview of recommendations without modifying files.
    
    Args:
        template_path: Path to the template file
        recommendations: List of recommendations to preview
        
    Returns:
        Preview string showing proposed changes
    """
    lines = [
        "=" * 60,
        "VERDICT ANALYZER RECOMMENDATIONS",
        "=" * 60,
        f"Template: {template_path}",
        "",
        "Proposed improvements:",
        "",
    ]
    
    for i, rec in enumerate(recommendations, 1):
        lines.append(f"{i}. [{rec.type}] Section: {rec.section}")
        lines.append(f"   {rec.content}")
        lines.append("")
    
    lines.append("-" * 60)
    lines.append("Run with --apply to make changes")
    
    return "\n".join(lines)


def atomic_write_with_backup(file_path: Path, content: str) -> Tuple[bool, Optional[Path]]:
    """Write content to file with atomic backup.
    
    Args:
        file_path: Path to the file to write
        content: New content to write
        
    Returns:
        Tuple of (success, backup_path)
    """
    file_path = Path(file_path)
    backup_path = file_path.with_suffix(file_path.suffix + '.bak')
    
    try:
        # Create backup of existing file
        if file_path.exists():
            original_content = file_path.read_text(encoding='utf-8')
            backup_path.write_text(original_content, encoding='utf-8')
        
        # Write new content
        file_path.write_text(content, encoding='utf-8')
        
        return True, backup_path
    except Exception as e:
        logger.error(f"Failed to write file {file_path}: {e}")
        return False, None


def validate_template_path(path: Path, allowed_roots: List[Path]) -> bool:
    """Validate that a template path is within allowed directories.
    
    Args:
        path: Path to validate
        allowed_roots: List of allowed root directories
        
    Returns:
        True if path is valid, False otherwise
    """
    path = Path(path).resolve()
    
    for root in allowed_roots:
        root = Path(root).resolve()
        try:
            path.relative_to(root)
            return True
        except ValueError:
            continue
    
    logger.warning(f"Path {path} is not within allowed roots")
    return False
```