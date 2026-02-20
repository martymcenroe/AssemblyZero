"""Path security validation for TDD workflow context files.

Issue #289: Prevents directory traversal, secret file exposure,
and oversized file injection into LLM prompts.
"""

import os
import re
from pathlib import Path

# Secret file patterns (case-insensitive)
SECRET_PATTERNS = [
    r"\.env$",
    r"\.env\.",
    r"credentials",
    r"secret",
    r"\.pem$",
    r"\.key$",
    r"\.p12$",
    r"\.pfx$",
    r"\.jks$",
    r"\.keystore$",
    r"id_rsa",
    r"id_ed25519",
    r"\.aws/",
]

# Default size limit: 100KB
DEFAULT_SIZE_LIMIT = 100 * 1024


def is_secret_file(path: str | Path) -> bool:
    """Check if a file path matches known secret file patterns.

    Args:
        path: File path to check.

    Returns:
        True if the file matches a secret pattern.
    """
    path_str = str(path).replace("\\", "/").lower()
    name = Path(path_str).name.lower()

    for pattern in SECRET_PATTERNS:
        if re.search(pattern, name, re.IGNORECASE):
            return True
        if re.search(pattern, path_str, re.IGNORECASE):
            return True

    return False


def check_file_size(path: Path, limit: int = DEFAULT_SIZE_LIMIT) -> tuple[bool, str]:
    """Check if a file exceeds the size limit.

    Args:
        path: Path to the file.
        limit: Maximum allowed size in bytes.

    Returns:
        Tuple of (ok, error_message). ok=True if within limit.
    """
    try:
        size = path.stat().st_size
    except OSError as e:
        return False, f"Cannot stat file: {e}"

    if size > limit:
        return False, (
            f"File too large: {size:,} bytes "
            f"(limit: {limit:,} bytes / {limit // 1024}KB)"
        )

    return True, ""


def validate_context_path(
    path: str | Path,
    project_root: str | Path,
) -> tuple[bool, str]:
    """Validate a context file path for security.

    Checks:
    1. No directory traversal (../)
    2. Resolves within project root
    3. Not a secret file
    4. File exists and is readable
    5. File size within limit

    Args:
        path: File path to validate (absolute or relative to project_root).
        project_root: Project root directory.

    Returns:
        Tuple of (valid, error_message). valid=True if all checks pass.
    """
    path = Path(path)
    project_root = Path(project_root).resolve()

    # Check for traversal sequences in the raw path string
    raw = str(path).replace("\\", "/")
    if ".." in raw.split("/"):
        return False, f"Directory traversal rejected: {path}"

    # Resolve the path (relative to project_root if not absolute)
    if not path.is_absolute():
        resolved = (project_root / path).resolve()
    else:
        resolved = path.resolve()

    # Check resolved path is within project root
    try:
        resolved.relative_to(project_root)
    except ValueError:
        return False, f"Path outside project root: {resolved} (root: {project_root})"

    # Check for symlink escape
    if resolved.is_symlink():
        real = resolved.resolve()
        try:
            real.relative_to(project_root)
        except ValueError:
            return False, f"Symlink escapes project root: {resolved} -> {real}"

    # Check for secret files
    if is_secret_file(resolved):
        return False, f"Secret file rejected: {resolved.name}"

    # Check file exists
    if not resolved.exists():
        return False, f"File not found: {resolved}"

    if not resolved.is_file():
        return False, f"Not a file: {resolved}"

    # Check file size
    ok, size_error = check_file_size(resolved)
    if not ok:
        return False, f"{resolved.name}: {size_error}"

    return True, ""


def load_context_files(
    paths: list[str],
    project_root: str | Path,
) -> tuple[str, list[str]]:
    """Load and concatenate validated context files.

    Args:
        paths: List of file paths to load.
        project_root: Project root for path validation.

    Returns:
        Tuple of (concatenated_content, error_list).
        Content is empty string if all files fail validation.
    """
    project_root = Path(project_root).resolve()
    contents: list[str] = []
    errors: list[str] = []

    for raw_path in paths:
        valid, error = validate_context_path(raw_path, project_root)
        if not valid:
            errors.append(f"[CONTEXT] REJECTED: {raw_path} — {error}")
            continue

        # Resolve path for reading
        path = Path(raw_path)
        if not path.is_absolute():
            path = project_root / path

        path = path.resolve()

        try:
            text = path.read_text(encoding="utf-8")
            contents.append(f"# Context: {path.name}\n\n{text}")
        except Exception as e:
            errors.append(f"[CONTEXT] Read error: {raw_path} — {e}")

    return "\n\n---\n\n".join(contents), errors
