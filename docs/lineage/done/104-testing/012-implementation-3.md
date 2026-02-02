# File: tools/verdict_analyzer/patterns.py

```python
"""Pattern extraction, normalization, and category mapping."""

import re
import logging
from typing import Optional

from .parser import BlockingIssue

logger = logging.getLogger(__name__)

# Mapping from blocking issue categories to template sections
CATEGORY_TO_SECTION = {
    "security": "Security Considerations",
    "error-handling": "Error Handling",
    "error handling": "Error Handling",
    "testing": "Testing Strategy",
    "test coverage": "Testing Strategy",
    "documentation": "Documentation",
    "docs": "Documentation",
    "performance": "Performance Considerations",
    "api-design": "API Design",
    "api design": "API Design",
    "dependencies": "Dependencies",
    "migration": "Migration Strategy",
    "backwards-compatibility": "Migration Strategy",
    "backwards compatibility": "Migration Strategy",
    "implementation": "Implementation Details",
    "architecture": "Architecture",
    "validation": "Input Validation",
    "input validation": "Input Validation",
}


def normalize_pattern(description: str) -> str:
    """Normalize a blocking issue description for pattern matching.

    Removes specific identifiers, normalizes whitespace, and lowercases.

    Args:
        description: Raw description text

    Returns:
        Normalized pattern string
    """
    if not description:
        return ""

    pattern = description.lower()

    # Remove specific file paths
    pattern = re.sub(r"[a-z0-9_/\\]+\.[a-z]+", "<FILE>", pattern)

    # Remove line numbers
    pattern = re.sub(r"line\s*\d+", "line <N>", pattern)
    pattern = re.sub(r":\d+", ":<N>", pattern)

    # Remove specific variable/function names in quotes
    pattern = re.sub(r"['\"`][\w_]+['\"`]", "<NAME>", pattern)

    # Remove specific numbers
    pattern = re.sub(r"\b\d+\b", "<N>", pattern)

    # Normalize whitespace
    pattern = re.sub(r"\s+", " ", pattern).strip()

    return pattern


def extract_category(description: str) -> Optional[str]:
    """Extract category from a description.

    Args:
        description: Issue description

    Returns:
        Category string or None
    """
    desc_lower = description.lower()

    # Check for explicit category markers
    for category in CATEGORY_TO_SECTION.keys():
        if category in desc_lower:
            return category

    # Infer from common patterns
    if any(word in desc_lower for word in ["sql injection", "xss", "csrf", "auth", "password"]):
        return "security"
    if any(word in desc_lower for word in ["try", "except", "catch", "error", "exception"]):
        return "error-handling"
    if any(word in desc_lower for word in ["test", "coverage", "mock", "fixture"]):
        return "testing"
    if any(word in desc_lower for word in ["docstring", "readme", "comment"]):
        return "documentation"

    return None


def get_template_section(category: str) -> str:
    """Get the template section for a category.

    Args:
        category: Issue category

    Returns:
        Template section name
    """
    return CATEGORY_TO_SECTION.get(category.lower(), "General")


def extract_blocking_issues(content: str) -> list[BlockingIssue]:
    """Extract blocking issues from verdict content.

    This is re-exported from parser for convenience.
    """
    from .parser import extract_blocking_issues as _extract

    return _extract(content)
```