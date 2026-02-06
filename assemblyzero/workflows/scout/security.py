"""Security utilities for Scout workflow.

Implements path validation, overwrite protection, and content sanitization.
"""

import os
import re
from datetime import datetime
from pathlib import Path


def validate_read_path(path: str, base_dir: str = ".") -> str:
    """Ensure path is within base_dir and exists.

    Args:
        path: Path to validate.
        base_dir: Base directory (default: current directory).

    Returns:
        Resolved absolute path.

    Raises:
        ValueError: If path is unsafe (contains .. or outside base_dir).
        FileNotFoundError: If path doesn't exist.
    """
    # Check for obvious path traversal attempts
    if ".." in path:
        raise ValueError(f"Path traversal detected: {path}")

    # Resolve paths
    base_path = Path(base_dir).resolve()
    target_path = Path(path)

    # If relative, make it relative to base_dir
    if not target_path.is_absolute():
        target_path = base_path / path

    target_path = target_path.resolve()

    # Ensure target is within base directory
    try:
        target_path.relative_to(base_path)
    except ValueError:
        raise ValueError(f"Path outside allowed directory: {path}")

    # Check existence
    if not target_path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")

    return str(target_path)


def get_safe_write_path(
    filename: str,
    directory: str,
    overwrite: bool = False,
) -> str:
    """Get safe path for writing, with overwrite protection.

    If file exists and overwrite=False, appends timestamp to filename.

    Args:
        filename: Desired filename.
        directory: Target directory.
        overwrite: If True, allow overwriting existing files.

    Returns:
        Safe path for writing.

    Raises:
        ValueError: If path would be outside directory.
    """
    # Validate directory
    dir_path = Path(directory).resolve()

    # Check for path traversal in filename
    if ".." in filename or os.sep in filename:
        raise ValueError(f"Invalid filename: {filename}")

    target_path = dir_path / filename

    # Ensure within directory
    try:
        target_path.resolve().relative_to(dir_path)
    except ValueError:
        raise ValueError(f"Path outside allowed directory: {filename}")

    # Handle existing file
    if target_path.exists() and not overwrite:
        # Append timestamp
        stem = target_path.stem
        suffix = target_path.suffix
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        new_filename = f"{stem}-{timestamp}{suffix}"
        target_path = dir_path / new_filename

    return str(target_path)


def sanitize_external_content(content: str) -> str:
    """Remove potential prompt injection vectors from external text.

    Removes fake XML tags and other injection patterns.

    Args:
        content: External content to sanitize.

    Returns:
        Sanitized content.
    """
    if not content:
        return content

    # Remove fake XML tags that could be used for prompt injection
    # Pattern: <tag>...</tag> or <tag/>
    xml_pattern = re.compile(r"</?[a-zA-Z][a-zA-Z0-9_-]*(?:\s[^>]*)?>")
    sanitized = xml_pattern.sub("", content)

    # Remove potential instruction markers
    instruction_patterns = [
        r"SYSTEM:",
        r"ASSISTANT:",
        r"USER:",
        r"\[INST\]",
        r"\[/INST\]",
        r"<<SYS>>",
        r"<</SYS>>",
    ]
    for pattern in instruction_patterns:
        sanitized = re.sub(pattern, "", sanitized, flags=re.IGNORECASE)

    return sanitized
