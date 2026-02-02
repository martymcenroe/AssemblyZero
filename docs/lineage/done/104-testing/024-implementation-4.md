# File: tools/verdict_analyzer/scanner.py

```python
"""Scanner module for verdict analyzer.

Discovers verdict files across multiple repositories.
"""

import json
import logging
from pathlib import Path
from typing import Generator, List, Optional, Set

logger = logging.getLogger(__name__)


def find_registry_path(start_dir: Optional[Path] = None) -> Optional[Path]:
    """Find project-registry.json by searching up from start directory.
    
    Args:
        start_dir: Directory to start searching from (defaults to cwd)
        
    Returns:
        Path to registry file if found, None otherwise
    """
    if start_dir is None:
        start_dir = Path.cwd()
    
    current = Path(start_dir).resolve()
    
    # Search up to root
    while current != current.parent:
        registry_path = current / "project-registry.json"
        if registry_path.exists():
            return registry_path
        current = current.parent
    
    # Check root
    registry_path = current / "project-registry.json"
    if registry_path.exists():
        return registry_path
    
    return None


def discover_repos(registry_path: Path) -> List[Path]:
    """Discover repositories from a project registry.
    
    Args:
        registry_path: Path to project-registry.json
        
    Returns:
        List of repository paths that exist
    """
    repos = []
    
    try:
        content = registry_path.read_text(encoding='utf-8')
        registry = json.loads(content)
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to read registry {registry_path}: {e}")
        return repos
    
    projects = registry.get("projects", [])
    
    for project_path in projects:
        path = Path(project_path).resolve()
        if path.exists() and path.is_dir():
            repos.append(path)
        else:
            logger.warning(f"Repository not found: {project_path}")
    
    return repos


def validate_verdict_path(verdict_path: Path, repo_root: Path) -> bool:
    """Validate that a verdict path is within the repository root.
    
    Args:
        verdict_path: Path to the verdict file
        repo_root: Root directory of the repository
        
    Returns:
        True if path is valid, False otherwise
    """
    try:
        verdict_resolved = Path(verdict_path).resolve()
        repo_resolved = Path(repo_root).resolve()
        verdict_resolved.relative_to(repo_resolved)
        return True
    except ValueError:
        logger.warning(f"Path traversal detected: {verdict_path}")
        return False


def scan_for_verdicts(
    repo_path: Path,
    patterns: Optional[List[str]] = None,
) -> Generator[Path, None, None]:
    """Scan a repository for verdict files.
    
    Args:
        repo_path: Path to the repository root
        patterns: Glob patterns for verdict files (default: *verdict*.md)
        
    Yields:
        Paths to verdict files
    """
    if patterns is None:
        patterns = ["*verdict*.md", "*Verdict*.md"]
    
    repo_path = Path(repo_path).resolve()
    visited: Set[Path] = set()
    
    def scan_dir(directory: Path, depth: int = 0):
        """Recursively scan directory, handling symlinks."""
        if depth > 20:  # Max depth to prevent issues
            return
        
        try:
            resolved = directory.resolve()
        except OSError:
            return
        
        if resolved in visited:
            logger.warning(f"Skipping already visited directory (possible symlink loop): {directory}")
            return
        
        visited.add(resolved)
        
        try:
            for item in directory.iterdir():
                if item.is_symlink():
                    try:
                        target = item.resolve()
                        if target in visited:
                            continue
                    except OSError:
                        continue
                
                if item.is_dir():
                    # Skip hidden and common non-code directories
                    if item.name.startswith('.') or item.name in ('node_modules', '__pycache__', 'venv'):
                        continue
                    yield from scan_dir(item, depth + 1)
                elif item.is_file():
                    for pattern in patterns:
                        if item.match(pattern):
                            if validate_verdict_path(item, repo_path):
                                yield item
                            break
        except PermissionError:
            logger.warning(f"Permission denied: {directory}")
        except OSError as e:
            logger.warning(f"Error scanning {directory}: {e}")
    
    yield from scan_dir(repo_path)
```