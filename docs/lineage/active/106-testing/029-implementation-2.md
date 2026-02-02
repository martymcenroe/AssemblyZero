# File: agentos/workflows/parallel/input_sanitizer.py

```python
"""Input validation utilities for path-safe identifiers."""

import re
from pathlib import Path


def sanitize_identifier(identifier: str) -> str:
    """Validate and sanitize an identifier to prevent path traversal.
    
    Args:
        identifier: User-provided identifier
        
    Returns:
        Sanitized identifier
        
    Raises:
        ValueError: If identifier contains invalid characters or path traversal
    """
    # Check for path traversal attempts
    if ".." in identifier:
        raise ValueError(f"Invalid identifier: path traversal detected in '{identifier}'")
        
    # Check for absolute paths
    if identifier.startswith("/") or identifier.startswith("\\"):
        raise ValueError(f"Invalid identifier: absolute path not allowed in '{identifier}'")
        
    # Check for Windows drive letters
    if len(identifier) >= 2 and identifier[1] == ":":
        raise ValueError(f"Invalid identifier: drive letter not allowed in '{identifier}'")
        
    # Validate characters (alphanumeric, dash, underscore only)
    if not re.match(r'^[a-zA-Z0-9_-]+$', identifier):
        raise ValueError(f"Invalid identifier: only alphanumeric, dash, and underscore allowed in '{identifier}'")
        
    return identifier


def validate_path_component(component: str) -> bool:
    """Check if a string is a valid path component.
    
    Args:
        component: Path component to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        sanitize_identifier(component)
        return True
    except ValueError:
        return False
```