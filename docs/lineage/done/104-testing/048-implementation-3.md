# File: tools/verdict_analyzer/patterns.py

```python
"""Pattern extraction, normalization, and category mapping."""

from __future__ import annotations

import re
from typing import Optional


# Mapping from blocking issue categories to template sections
CATEGORY_TO_SECTION = {
    "security": "Security Considerations",
    "testing": "Testing Strategy",
    "error_handling": "Error Handling",
    "documentation": "Documentation",
    "dependencies": "Dependencies",
    "architecture": "Architecture",
    "performance": "Performance Requirements",
    "validation": "Input Validation",
    "configuration": "Configuration",
    "logging": "Observability",
    "api": "API Design",
    "general": "Implementation Notes",
}


def normalize_pattern(description: str) -> str:
    """Normalize a blocking issue description into a canonical pattern.
    
    This removes variable parts (like specific names, numbers) and
    standardizes phrasing to group similar issues together.
    
    Args:
        description: Raw issue description
        
    Returns:
        Normalized pattern string
    """
    pattern = description.lower().strip()
    
    # Remove quotes and backticks
    pattern = re.sub(r"[`'\"]", "", pattern)
    
    # Normalize whitespace
    pattern = re.sub(r"\s+", " ", pattern)
    
    # Remove specific file paths, keeping just the pattern
    pattern = re.sub(r"[\w/\\]+\.(py|js|ts|json|yaml|yml|md)", "<file>", pattern)
    
    # Normalize numbers
    pattern = re.sub(r"\b\d+\b", "<N>", pattern)
    
    # Normalize identifiers (camelCase, snake_case, etc.)
    pattern = re.sub(r"\b[a-z]+(?:[A-Z][a-z]+)+\b", "<identifier>", pattern)
    pattern = re.sub(r"\b[a-z]+(?:_[a-z]+)+\b", "<identifier>", pattern)
    
    # Normalize URLs
    pattern = re.sub(r"https?://[^\s]+", "<url>", pattern)
    
    # Common phrase normalizations
    normalizations = [
        (r"missing\s+\w+\s+for", "missing <type> for"),
        (r"no\s+\w+\s+handling", "no <type> handling"),
        (r"should\s+(?:have|include|add)", "should include"),
        (r"needs?\s+(?:to\s+)?(?:be\s+)?(?:add|include)", "needs"),
        (r"lacks?\s+", "missing "),
    ]
    
    for old, new in normalizations:
        pattern = re.sub(old, new, pattern)
    
    return pattern.strip()


def map_category_to_section(category: str) -> str:
    """Map a blocking issue category to a template section.
    
    Args:
        category: Issue category
        
    Returns:
        Template section name
    """
    return CATEGORY_TO_SECTION.get(category, CATEGORY_TO_SECTION["general"])


def extract_patterns_from_issues(issues: list, min_occurrences: int = 2) -> dict[str, int]:
    """Extract recurring patterns from blocking issues.
    
    Args:
        issues: List of BlockingIssue objects
        min_occurrences: Minimum times a pattern must occur
        
    Returns:
        Dictionary of pattern -> count
    """
    pattern_counts: dict[str, int] = {}
    
    for issue in issues:
        pattern = normalize_pattern(issue.description)
        pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
    
    # Filter by minimum occurrences
    return {p: c for p, c in pattern_counts.items() if c >= min_occurrences}
```