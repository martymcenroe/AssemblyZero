# File: tools/verdict_analyzer/scanner.py

```python
"""Multi-repo verdict discovery."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Iterator, Optional

logger = logging.getLogger(__name__)

# Common verdict directory patterns
VERDICT_PATTERNS = [
    "docs/lineage/verdicts",
    "docs/verdicts",
    ".agentos/verdicts",
    "verdicts",
    "governance/verdicts",
]


def find_registry(start_dir: Optional[Path] = None) -> Optional[Path]:
    """Find project-registry.json by searching up from start_dir.
    
    Args:
        start_dir: Directory to start search from (default: cwd)
        
    Returns:
        Path to registry file or None
    """
    if start_dir is None:
        start_dir = Path.cwd()
    
    start_dir = Path(start_dir).resolve()
    
    # Search up the directory tree
    current = start_dir
    while current != current.parent:
        registry_path = current / "project-registry.json"
        if registry_path.exists():
            logger.debug(f"Found registry at: {registry_path}")
            return registry_path
        current = current.parent
    
    # Also check common locations
    common_paths = [
        Path.home() / "Projects" / "project-registry.json",
        Path.home() / "project-registry.json",
        Path("/projects/project-registry.json"),
    ]
    
    for path in common_paths:
        if path.exists():
            logger.debug(f"Found registry at: {path}")
            return path
    
    return None


def load_registry(registry_path: Path) -> list[Path]:
    """Load repository paths from project registry.
    
    Args:
        registry_path: Path to project-registry.json
        
    Returns:
        List of repository paths
    """
    with registry_path.open(encoding="utf-8") as f:
        data = json.load(f)
    
    repos = []
    base_dir = registry_path.parent
    
    # Handle different registry formats
    if isinstance(data, list):
        entries = data
    elif isinstance(data, dict):
        entries = data.get("repositories", data.get("projects", []))
    else:
        return repos
    
    for entry in entries:
        if isinstance(entry, str):
            repo_path = Path(entry)
        elif isinstance(entry, dict):
            repo_path = Path(entry.get("path", entry.get("directory", "")))
        else:
            continue
        
        # Resolve relative paths
        if not repo_path.is_absolute():
            repo_path = base_dir / repo_path
        
        repo_path = repo_path.resolve()
        
        if repo_path.exists():
            repos.append(repo_path)
        else:
            logger.warning(f"Repository not found: {repo_path}")
    
    return repos


def validate_verdict_path(verdict_path: Path, base_dir: Path) -> bool:
    """Validate that a verdict path is within the expected base directory.
    
    Args:
        verdict_path: Path to validate
        base_dir: Expected base directory
        
    Returns:
        True if valid, False otherwise
    """
    try:
        verdict_path = verdict_path.resolve()
        base_dir = base_dir.resolve()
        verdict_path.relative_to(base_dir)
        return True
    except ValueError:
        logger.warning(f"Path traversal attempt detected: {verdict_path}")
        return False


def discover_verdicts(repo_path: Path, max_depth: int = 10) -> Iterator[Path]:
    """Discover verdict files in a repository.
    
    Args:
        repo_path: Path to repository root
        max_depth: Maximum directory depth to search
        
    Yields:
        Paths to verdict markdown files
    """
    repo_path = Path(repo_path).resolve()
    seen_inodes: set[tuple] = set()  # Track visited directories for symlink loop detection
    
    def _get_inode(path: Path) -> tuple:
        """Get inode info for symlink loop detection."""
        try:
            stat = path.stat()
            return (stat.st_dev, stat.st_ino)
        except (OSError, ValueError):
            return (0, id(path))  # Fallback for Windows
    
    def _walk_dir(dir_path: Path, depth: int) -> Iterator[Path]:
        """Recursively walk directory with symlink loop protection."""
        if depth > max_depth:
            logger.debug(f"Max depth reached at: {dir_path}")
            return
        
        # Check for symlink loops
        inode = _get_inode(dir_path)
        if inode in seen_inodes:
            logger.warning(f"Symlink loop detected at: {dir_path}")
            return
        seen_inodes.add(inode)
        
        try:
            for entry in dir_path.iterdir():
                # Validate path is still within repo
                if not validate_verdict_path(entry, repo_path):
                    continue
                
                if entry.is_file() and entry.suffix.lower() == ".md":
                    # Check if it looks like a verdict file
                    if _is_verdict_file(entry):
                        yield entry
                elif entry.is_dir() and not entry.name.startswith("."):
                    yield from _walk_dir(entry, depth + 1)
        except PermissionError:
            logger.warning(f"Permission denied: {dir_path}")
        except OSError as e:
            logger.warning(f"Error reading directory {dir_path}: {e}")
    
    # Check known verdict directories first
    for pattern in VERDICT_PATTERNS:
        verdict_dir = repo_path / pattern
        if verdict_dir.exists() and verdict_dir.is_dir():
            yield from _walk_dir(verdict_dir, 0)
    
    # Also check docs/lineage for verdict files
    lineage_dir = repo_path / "docs" / "lineage"
    if lineage_dir.exists():
        for entry in lineage_dir.iterdir():
            if entry.is_file() and entry.suffix.lower() == ".md":
                if _is_verdict_file(entry):
                    yield entry


def _is_verdict_file(path: Path) -> bool:
    """Check if a file appears to be a verdict file.
    
    Args:
        path: Path to check
        
    Returns:
        True if file looks like a verdict
    """
    name_lower = path.name.lower()
    
    # Check filename patterns
    if any(p in name_lower for p in ["verdict", "governance", "review"]):
        return True
    
    # Read first few lines to check content
    try:
        with path.open(encoding="utf-8") as f:
            header = f.read(500).lower()
        
        verdict_markers = [
            "verdict",
            "approved",
            "blocked",
            "needs_revision",
            "tier 1",
            "tier 2",
            "blocking issue",
        ]
        
        return any(marker in header for marker in verdict_markers)
    except (OSError, UnicodeDecodeError):
        return False


def scan_repos(
    registry_path: Optional[Path] = None,
    repos: Optional[list[Path]] = None,
) -> Iterator[tuple[Path, Path]]:
    """Scan repositories for verdict files.
    
    Args:
        registry_path: Path to project-registry.json (optional)
        repos: Explicit list of repo paths (optional)
        
    Yields:
        Tuples of (repo_path, verdict_path)
    """
    if repos is None:
        repos = []
    
    if registry_path:
        repos.extend(load_registry(registry_path))
    
    if not repos:
        # Default to current directory
        repos = [Path.cwd()]
    
    for repo_path in repos:
        if not repo_path.exists():
            logger.warning(f"Repository not found: {repo_path}")
            continue
        
        logger.info(f"Scanning repository: {repo_path}")
        
        for verdict_path in discover_verdicts(repo_path):
            yield (repo_path, verdict_path)
```