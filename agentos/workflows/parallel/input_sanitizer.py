"""Input validation utilities for path-safe identifiers."""

import re
from typing import Pattern


# Pattern for valid identifiers (alphanumeric, dash, underscore)
VALID_IDENTIFIER: Pattern = re.compile(r'^[a-zA-Z0-9_-]+$')


def sanitize_identifier(identifier: str) -> str:
    """Validate and sanitize an identifier for path safety.
    
    Args:
        identifier: Identifier to validate
    
    Returns:
        The identifier if valid
    
    Raises:
        ValueError: If identifier contains invalid characters or path traversal
    """
    # Check for path traversal
    if ".." in identifier:
        raise ValueError(f"Invalid identifier: path traversal not allowed: {identifier}")
    
    # Check for absolute paths
    if identifier.startswith("/") or (len(identifier) > 1 and identifier[1] == ":"):
        raise ValueError(f"Invalid identifier: absolute paths not allowed: {identifier}")
    
    # Check for path separators
    if "/" in identifier or "\\" in identifier:
        raise ValueError(f"Invalid identifier: path separators not allowed: {identifier}")
    
    # Check for invalid characters
    if not VALID_IDENTIFIER.match(identifier):
        raise ValueError(f"Invalid identifier: invalid characters in: {identifier}")
    
    return identifier