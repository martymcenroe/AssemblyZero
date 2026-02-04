# File: agentos/workflows/parallel/input_sanitizer.py

```python
"""Input validation utilities for parallel workflows."""

import os
import re
from pathlib import Path
from typing import Union


def sanitize_identifier(identifier: str) -> str:
    """Validate and sanitize an identifier for file system safety.
    
    Args:
        identifier: The identifier to validate (e.g., issue number, LLD ID)
        
    Returns:
        The sanitized identifier
        
    Raises:
        ValueError: If identifier contains path traversal or invalid characters
    """
    if not identifier:
        raise ValueError("Invalid identifier: empty string")
    
    # Check for path traversal attempts
    if ".." in identifier:
        raise ValueError(f"Invalid identifier: contains path traversal (..): {identifier}")
    
    # Check for absolute paths
    if identifier.startswith("/") or identifier.startswith("\\"):
        raise ValueError(f"Invalid identifier: starts with path separator: {identifier}")
    
    # Check for Windows drive letters
    if len(identifier) >= 2 and identifier[1] == ":":
        raise ValueError(f"Invalid identifier: contains drive letter: {identifier}")
    
    # Check for invalid characters (allow alphanumeric, dash, underscore)
    if not re.match(r"^[a-zA-Z0-9_-]+$", identifier):
        raise ValueError(f"Invalid identifier: contains invalid characters: {identifier}")
    
    return identifier


def sanitize_path(path: Union[str, Path], base_dir: Union[str, Path]) -> Path:
    """Validate that a path is within a base directory.
    
    Args:
        path: The path to validate
        base_dir: The base directory that must contain the path
        
    Returns:
        Resolved Path object
        
    Raises:
        ValueError: If path escapes base directory
    """
    base_path = Path(base_dir).resolve()
    target_path = Path(path).resolve()
    
    try:
        target_path.relative_to(base_path)
    except ValueError:
        raise ValueError(f"Invalid path: escapes base directory: {path}")
    
    return target_path


def validate_workflow_id(workflow_id: str) -> str:
    """Validate a workflow identifier.
    
    Args:
        workflow_id: The workflow ID to validate
        
    Returns:
        The validated workflow ID
        
    Raises:
        ValueError: If workflow ID is invalid
    """
    # Workflow IDs should be short and safe
    if len(workflow_id) > 100:
        raise ValueError(f"Invalid workflow ID: too long (max 100 chars): {workflow_id}")
    
    return sanitize_identifier(workflow_id)
```