# File: tools/verdict_analyzer/patterns.py

```python
"""Pattern extraction, normalization, and category mapping."""

import re
from typing import Optional

# Map categories to template sections
CATEGORY_TO_SECTION = {
    "security": "Security Considerations",
    "error-handling": "Error Handling",
    "error handling": "Error Handling",
    "testing": "Testing Strategy",
    "documentation": "Documentation",
    "performance": "Performance Considerations",
    "api-design": "API Design",
    "api design": "API Design",
    "dependencies": "Dependencies",
    "migration": "Migration Strategy",
    "implementation": "Implementation Details",
}


def normalize_pattern(description: str) -> str:
    """Normalize a description to extract reusable patterns.
    
    Replaces specific values with placeholders to enable pattern matching.
    
    Args:
        description: The raw description text.
        
    Returns:
        Normalized pattern string.
    """
    if not description:
        return ""
    
    result = description
    
    # Replace file paths with <FILE>
    result = re.sub(r'[a-zA-Z0-9_/\\-]+\.(py|js|ts|md|json|yaml|yml)', '<FILE>', result)
    
    # Replace line numbers
    result = re.sub(r'line\s+\d+', 'line <N>', result, flags=re.IGNORECASE)
    result = re.sub(r':\d+', ':<N>', result)
    
    # Replace variable/field names in quotes
    result = re.sub(r"'[a-zA-Z_][a-zA-Z0-9_]*'", "'<VAR>'", result)
    result = re.sub(r'"[a-zA-Z_][a-zA-Z0-9_]*"', '"<VAR>"', result)
    
    # Replace numbers
    result = re.sub(r'\b\d+\b', '<N>', result)
    
    return result


def get_template_section(category: str) -> str:
    """Get the template section for a category.
    
    Args:
        category: Issue category (case-insensitive).
        
    Returns:
        Template section name, or "General" if not mapped.
    """
    normalized = category.lower().strip()
    return CATEGORY_TO_SECTION.get(normalized, "General")


def extract_category(issue_line: str) -> Optional[str]:
    """Extract category from a blocking issue line.
    
    Args:
        issue_line: Line containing [Tier X] - [Category] - Description
        
    Returns:
        Category string if found, None otherwise.
    """
    # Match [Tier X] - [Category] pattern
    match = re.search(r'\[Tier\s*\d+\]\s*-\s*\[([^\]]+)\]', issue_line, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None
```