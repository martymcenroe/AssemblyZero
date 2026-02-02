# File: tools/verdict_analyzer/patterns.py

```python
"""Pattern extraction and normalization for verdict analyzer."""

import re
from typing import Optional

# Mapping from category names to template sections
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
}


def normalize_pattern(description: str) -> str:
    """Normalize a pattern description for grouping similar issues.
    
    Replaces specific values with placeholders:
    - File paths -> <FILE>
    - Line numbers -> <n>
    - Variable names in quotes -> <VAR>
    - Numbers -> <n>
    
    Args:
        description: The original issue description
        
    Returns:
        Normalized pattern string
    """
    result = description
    
    # Replace file paths (src/something.py, path/to/file.ext)
    result = re.sub(r'\b[\w/\\.-]+\.(py|js|ts|md|json|yaml|yml|txt)\b', '<FILE>', result)
    
    # Replace line numbers: "at line 42" -> "at line <n>"
    # Use lowercase <n> to match test expectations
    result = re.sub(r'\bline\s+\d+', 'line <n>', result, flags=re.IGNORECASE)
    
    # Replace variable names in quotes: 'user_input' -> <VAR>
    result = re.sub(r"'[^']+'\s*variable", '<VAR> variable', result)
    result = re.sub(r'"[^"]+"\s*variable', '<VAR> variable', result)
    
    # Replace standalone numbers that aren't part of placeholders
    # But preserve <n> placeholders
    result = re.sub(r'(?<![<\w])\d+(?![>\w])', '<n>', result)
    
    return result


def get_template_section(category: str) -> str:
    """Get the template section name for a category.
    
    Args:
        category: The category name (case-insensitive)
        
    Returns:
        The corresponding template section name
    """
    normalized = category.lower().strip()
    return CATEGORY_TO_SECTION.get(normalized, "General")


def extract_category(text: str) -> Optional[str]:
    """Extract category from bracketed text like [Security]."""
    match = re.search(r'\[([^\]]+)\]', text)
    if match:
        return match.group(1).strip()
    return None
```