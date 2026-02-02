# File: tools/verdict_analyzer/scanner.py

```python
"""Multi-repo verdict discovery and scanning."""

import json
import logging
import os
from pathlib import Path
from typing import Iterator, List, Optional, Set

logger = logging.getLogger(__name__)

VERDICT_PATTERNS = [
    "**/verdict*.md",
    "**/*-verdict.md",
    "**/lld-verdict*.md",
    "**/issue-verdict*.md",
]


def find_registry_path(start_dir: Path) -> Optional[Path]:
    """Find project-registry.json by walking up the directory tree.
    
    Args:
        start_dir: Directory to start searching from.
        
    Returns:
        Path to registry file if found, None otherwise.
    """
    current = start_dir.resolve()
    
    # Walk up to root
    while current != current.parent:
        registry = current / "project-registry.json"
        if registry.exists():
            logger.debug(f"Found registry at {registry}")
            return registry
        current = current.parent
    
    # Check root as well
    registry = current / "project-registry.json"
    if registry.exists():
        return registry
    
    return None


def discover_repos(registry_path: Path) -> List[Path]:
    """Discover repositories from a project registry.
    
    Args:
        registry_path: Path to project-registry.json file.
        
    Returns:
        List of valid repository paths.
    """
    if not registry_path.exists():
        logger.warning(f"Registry not found: {registry_path}")
        return []

    try:
        with open(registry_path) as f:
            registry = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Failed to read registry: {e}")
        return []

    projects = registry.get("projects", [])
    repos = []

    for project_path in projects:
        path = Path(project_path).resolve()
        if path.exists() and path.is_dir():
            repos.append(path)
            logger.debug(f"Found repo: {path}")
        else:
            logger.warning(f"Repository not found: {project_path}")

    return repos


def validate_verdict_path(verdict_path: Path, repo_root: Path) -> bool:
    """Validate that a verdict path is within the repo root.
    
    Prevents path traversal attacks.
    
    Args:
        verdict_path: Path to validate.
        repo_root: Repository root directory.
        
    Returns:
        True if path is valid and within repo root.
    """
    try:
        resolved = verdict_path.resolve()
        root_resolved = repo_root.resolve()
        
        # Check if path is relative to repo root
        try:
            resolved.relative_to(root_resolved)
            return True
        except ValueError:
            logger.warning(f"Path traversal attempt: {verdict_path}")
            return False
    except (OSError, ValueError) as e:
        logger.warning(f"Invalid path: {verdict_path}: {e}")
        return False


def scan_for_verdicts(repo_path: Path, max_depth: int = 10) -> Iterator[Path]:
    """Scan a repository for verdict files.
    
    Handles symlink loops by tracking visited directories.
    
    Args:
        repo_path: Repository root path.
        max_depth: Maximum directory depth to scan.
        
    Yields:
        Paths to verdict files.
    """
    visited: Set[Path] = set()
    
    def _scan_dir(dir_path: Path, depth: int) -> Iterator[Path]:
        if depth > max_depth:
            return
        
        try:
            resolved = dir_path.resolve()
        except (OSError, ValueError):
            return
        
        if resolved in visited:
            logger.warning(f"Skipping already visited directory (possible symlink loop): {dir_path}")
            return
        
        visited.add(resolved)
        
        try:
            entries = list(dir_path.iterdir())
        except PermissionError:
            logger.warning(f"Permission denied: {dir_path}")
            return
        except OSError as e:
            logger.warning(f"Error reading directory {dir_path}: {e}")
            return
        
        for entry in entries:
            if entry.name.startswith("."):
                continue  # Skip hidden files/dirs
            
            try:
                if entry.is_symlink():
                    # Resolve symlink and check for loops
                    try:
                        target = entry.resolve()
                        if target in visited:
                            logger.warning(f"Skipping symlink loop: {entry} -> {target}")
                            continue
                    except (OSError, ValueError):
                        continue
                
                if entry.is_dir():
                    yield from _scan_dir(entry, depth + 1)
                elif entry.is_file():
                    # Check if it matches verdict patterns
                    name_lower = entry.name.lower()
                    if "verdict" in name_lower and entry.suffix == ".md":
                        if validate_verdict_path(entry, repo_path):
                            logger.debug(f"Found verdict: {entry}")
                            yield entry
            except (OSError, ValueError) as e:
                logger.warning(f"Error processing {entry}: {e}")
                continue
    
    yield from _scan_dir(repo_path, 0)
```