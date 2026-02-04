# File: agentos/workflows/parallel/input_sanitizer.py

```python
"""Input validation utilities for path-safe identifiers."""

import re
from pathlib import Path


def sanitize_identifier(identifier: str) -> str:
    """Validate and sanitize an identifier to prevent path traversal attacks.
    
    Args:
        identifier: The identifier to validate
        
    Returns:
        The validated identifier
        
    Raises:
        ValueError: If identifier contains path traversal patterns or invalid characters
    """
    # Check for path traversal patterns
    if ".." in identifier:
        raise ValueError(f"Invalid identifier: contains path traversal pattern '..' - {identifier}")
    
    # Check for absolute paths
    if identifier.startswith("/") or (len(identifier) > 1 and identifier[1] == ":"):
        raise ValueError(f"Invalid identifier: absolute paths not allowed - {identifier}")
    
    # Check for path separators
    if "\\" in identifier or "/" in identifier:
        raise ValueError(f"Invalid identifier: path separators not allowed - {identifier}")
    
    # Only allow alphanumeric, dash, underscore
    if not re.match(r'^[a-zA-Z0-9_-]+$', identifier):
        raise ValueError(f"Invalid identifier: contains invalid characters - {identifier}")
    
    return identifier
```