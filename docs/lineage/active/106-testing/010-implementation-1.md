# File: agentos/workflows/parallel/input_sanitizer.py

```python
"""Input validation utilities for path-safe identifiers."""

import re
from typing import Any


def sanitize_identifier(identifier: Any) -> str:
    """Validate and sanitize an identifier for path-safe usage.
    
    Args:
        identifier: The identifier to validate (typically issue number or LLD ID)
        
    Returns:
        The sanitized identifier as a string
        
    Raises:
        ValueError: If the identifier contains path traversal sequences or is invalid
    """
    # Convert to string
    id_str = str(identifier)
    
    # Check for path traversal attempts
    if ".." in id_str:
        raise ValueError(
            f"Invalid identifier '{id_str}': contains path traversal sequence '..'"
        )
    
    # Check for absolute paths
    if id_str.startswith("/") or (len(id_str) > 1 and id_str[1] == ":"):
        raise ValueError(
            f"Invalid identifier '{id_str}': absolute paths not allowed"
        )
    
    # Check for directory separators
    if "/" in id_str or "\\" in id_str:
        raise ValueError(
            f"Invalid identifier '{id_str}': path separators not allowed"
        )
    
    # Must be alphanumeric with hyphens/underscores only
    if not re.match(r'^[a-zA-Z0-9_-]+$', id_str):
        raise ValueError(
            f"Invalid identifier '{id_str}': must contain only alphanumeric characters, hyphens, or underscores"
        )
    
    return id_str
```