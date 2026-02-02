# File: tools/verdict_analyzer/scanner.py

```python
"""Multi-repo verdict discovery."""

import json
import logging
import os
from pathlib import Path
from typing import Optional, Iterator

logger = logging.getLogger(__name__)


def find_registry_path(search_dir: Optional[Path] = None) -> Optional[Path]:
    """Find project-registry.json by searching up from search_dir.

    Args:
        search_dir: Directory to start searching from (defaults to cwd)

    Returns:
        Path to registry file or None if not found
    """
    if search_dir is None:
        search_dir = Path.cwd()

    search_dir = search_dir.resolve()

    # Search up the directory tree
    current = search_dir
    while current != current.parent:
        registry_path = current / "project-registry.json"
        if registry_path.exists():
            logger.debug(f"Found registry at: {registry_path}")
            return registry_path
        current = current.parent

    # Check home directory
    home_registry = Path.home() / "project-registry.json"
    if home_registry.exists():
        return home_registry

    return None


def discover_repos(registry_path: Path) -> list[Path]:
    """Discover repositories from project registry.

    Args:
        registry_path: Path to project-registry.json

    Returns:
        List of repository paths that exist
    """
    try:
        with open(registry_path, "r", encoding="utf-8") as f:
            registry = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to read registry: {e}")
        return []

    repos = []

    # Handle different registry formats
    if isinstance(registry, dict):
        # Format: {"projects": [...]} or {"repos": [...]}
        project_list = registry.get("projects", registry.get("repos", []))
    elif isinstance(registry, list):
        project_list = registry
    else:
        logger.warning(f"Unknown registry format: {type(registry)}")
        return []

    for project in project_list:
        if isinstance(project, str):
            path = Path(project).expanduser()
        elif isinstance(project, dict):
            path = Path(project.get("path", project.get("root", ""))).expanduser()
        else:
            continue

        if path.exists() and path.is_dir():
            repos.append(path.resolve())
        else:
            logger.warning(f"Repository not found: {path}")

    return repos


def scan_for_verdicts(
    repo_path: Path,
    allowed_root: Optional[Path] = None,
    follow_symlinks: bool = False,
) -> Iterator[Path]:
    """Scan a repository for verdict files.

    Args:
        repo_path: Repository root path
        allowed_root: Root path for traversal checking
        follow_symlinks: Whether to follow symlinks

    Yields:
        Paths to verdict markdown files
    """
    if allowed_root is None:
        allowed_root = repo_path

    # Track visited directories to handle symlink loops
    visited: set[str] = set()

    # Common verdict file patterns
    verdict_patterns = [
        "**/verdicts/**/*.md",
        "**/*-verdict.md",
        "**/*_verdict.md",
        "**/governance/**/*.md",
        ".agentos/verdicts/**/*.md",
    ]

    def is_safe_path(path: Path) -> bool:
        """Check if path is safe (no traversal)."""
        try:
            path.resolve().relative_to(allowed_root.resolve())
            return True
        except ValueError:
            logger.warning(f"Path traversal detected: {path}")
            return False

    def safe_iterdir(directory: Path) -> Iterator[Path]:
        """Safely iterate directory contents."""
        try:
            real_path = str(directory.resolve())
            if real_path in visited:
                logger.warning(f"Symlink loop detected at: {directory}")
                return
            visited.add(real_path)

            for entry in directory.iterdir():
                yield entry
        except PermissionError:
            logger.debug(f"Permission denied: {directory}")
        except OSError as e:
            logger.debug(f"Error reading directory {directory}: {e}")

    def scan_directory(directory: Path) -> Iterator[Path]:
        """Recursively scan directory for verdict files."""
        for entry in safe_iterdir(directory):
            # Skip hidden directories except .agentos
            if entry.name.startswith(".") and entry.name != ".agentos":
                continue

            if entry.is_symlink() and not follow_symlinks:
                continue

            if entry.is_dir():
                yield from scan_directory(entry)
            elif entry.is_file() and entry.suffix == ".md":
                # Check if it's a verdict file
                name_lower = entry.name.lower()
                path_str = str(entry).lower()

                if any(
                    pattern in name_lower or pattern in path_str
                    for pattern in ["verdict", "governance"]
                ):
                    if is_safe_path(entry):
                        yield entry

    yield from scan_directory(repo_path)


def validate_verdict_path(verdict_path: Path, repo_root: Path) -> bool:
    """Validate that a verdict path is within the repository.

    Args:
        verdict_path: Path to verdict file
        repo_root: Repository root path

    Returns:
        True if path is valid
    """
    try:
        verdict_path.resolve().relative_to(repo_root.resolve())
        return True
    except ValueError:
        logger.error(f"Path traversal in verdict: {verdict_path}")
        return False
```