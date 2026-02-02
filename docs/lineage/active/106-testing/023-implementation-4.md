# File: agentos/workflows/parallel/input_sanitizer.py

```python
"""Input validation utilities for path-safe identifiers."""

import re
from pathlib import Path


def sanitize_identifier(identifier: str) -> str:
    """Validate and sanitize an identifier to prevent path traversal.
    
    Args:
        identifier: The identifier to validate
        
    Returns:
        The validated identifier
        
    Raises:
        ValueError: If identifier contains path traversal attempts or absolute paths
    """
    # Check for path traversal patterns
    if '..' in identifier:
        raise ValueError(f"Invalid identifier: contains path traversal (..) - {identifier}")
    
    # Check for absolute paths (Unix and Windows)
    if identifier.startswith('/') or (len(identifier) > 1 and identifier[1] == ':'):
        raise ValueError(f"Invalid identifier: absolute paths not allowed - {identifier}")
    
    # Check for backslash (Windows path separator)
    if '\\' in identifier:
        raise ValueError(f"Invalid identifier: contains backslash (\\) - {identifier}")
    
    # Valid identifier pattern: alphanumeric, dash, underscore
    if not re.match(r'^[a-zA-Z0-9_-]+$', identifier):
        raise ValueError(f"Invalid identifier: must contain only alphanumeric, dash, and underscore - {identifier}")
    
    return identifier
```