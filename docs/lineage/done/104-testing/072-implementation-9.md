# File: tools/verdict_analyzer/patterns.py

```python
"""Pattern extraction and normalization."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tools.verdict_analyzer.parser import BlockingIssue

# Mapping from categories to template sections
CATEGORY_TO_SECTION = {
    "security": "Security Considerations",
    "testing": "Testing Strategy",
    "error_handling": "Error Handling",
    "documentation": "Documentation",
    "performance": "Performance Considerations",
    "logging": "Logging & Monitoring",
    "validation": "Input Validation",
    "architecture": "Architecture & Design",
    "general": "Implementation Notes",
    "database": "Data Storage",
    "api": "API Design",
}


def normalize_pattern(description: str) -> str:
    """Normalize a description into a pattern.

    Replaces specific details with placeholders for pattern matching.

    Args:
        description: Raw description from blocking issue.

    Returns:
        Normalized pattern string.
    """
    pattern = description

    # Replace file paths and names with <file>
    # Match patterns like file.py, path/to/file.js, etc.
    pattern = re.sub(r"\b[\w./\\-]+\.(py|js|ts|md|json|yaml|yml|sh|sql)\b", "<file>", pattern)

    # Replace line numbers with <line>
    pattern = re.sub(r"\bline\s*\d+\b", "line <line>", pattern, flags=re.IGNORECASE)

    # Replace absolute paths with <path>
    pattern = re.sub(r"(/[\w./\\-]+|[A-Z]:\\[\w.\\-]+)", "<path>", pattern)

    # Replace numbers (but not tier numbers or single digits in context)
    pattern = re.sub(r"\b\d{2,}\b", "<num>", pattern)

    # Normalize whitespace
    pattern = " ".join(pattern.split())

    return pattern


def map_category_to_section(category: str) -> str:
    """Map a category to its template section.

    Args:
        category: Category name.

    Returns:
        Template section name.
    """
    return CATEGORY_TO_SECTION.get(category, "Implementation Notes")


def extract_patterns_from_issues(issues: list["BlockingIssue"]) -> dict[str, int]:
    """Extract and count patterns from blocking issues.

    Args:
        issues: List of BlockingIssue objects.

    Returns:
        Dictionary mapping normalized patterns to counts.
    """
    if not issues:
        return {}

    pattern_counts: dict[str, int] = {}

    for issue in issues:
        pattern = normalize_pattern(issue.description)
        pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1

    return pattern_counts
```