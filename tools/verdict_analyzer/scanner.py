"""Multi-repo verdict discovery and scanning."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterator

from tools.verdict_analyzer.database import VerdictDatabase
from tools.verdict_analyzer.parser import compute_content_hash, parse_verdict

logger = logging.getLogger(__name__)


def find_registry(start_path: Path) -> Path | None:
    """Find project-registry.json by searching up directory tree.

    Args:
        start_path: Directory to start searching from.

    Returns:
        Path to registry file, or None if not found.
    """
    current = start_path.resolve()

    while current != current.parent:
        registry = current / "project-registry.json"
        if registry.exists():
            return registry
        current = current.parent

    # Check root
    registry = current / "project-registry.json"
    if registry.exists():
        return registry

    return None


def load_registry(registry_path: Path) -> list[Path]:
    """Load repository paths from registry.

    Args:
        registry_path: Path to project-registry.json.

    Returns:
        List of existing repository paths.
    """
    with open(registry_path, encoding="utf-8") as f:
        data = json.load(f)

    repos = []
    for repo_str in data:
        repo_path = Path(repo_str)
        if repo_path.exists():
            repos.append(repo_path)
        else:
            logger.warning(f"Repository not found: {repo_path}")

    return repos


def validate_verdict_path(verdict_path: Path, base_dir: Path) -> bool:
    """Validate verdict path is within base directory and is a verdict file.

    Args:
        verdict_path: Path to validate.
        base_dir: Base directory path must be within.

    Returns:
        True if path is valid verdict file, False otherwise.
    """
    # Must be a verdict file (contains "verdict" in filename)
    if "verdict" not in verdict_path.name.lower():
        return False

    try:
        verdict_path.resolve().relative_to(base_dir.resolve())
        return True
    except ValueError:
        return False


def discover_verdicts(repo_path: Path) -> Iterator[Path]:
    """Discover verdict files in a repository.

    Args:
        repo_path: Path to repository root.

    Yields:
        Paths to verdict markdown files.
    """
    # Look in common verdict locations
    verdict_dirs = [
        repo_path / "docs" / "lineage" / "active",  # AssemblyZero governance workflow
        repo_path / "docs" / "lineage",  # Broader lineage search
        repo_path / "docs" / "verdicts",
        repo_path / "verdicts",
        repo_path / ".verdicts",
    ]

    seen_paths: set[Path] = set()

    for verdict_dir in verdict_dirs:
        if not verdict_dir.exists():
            continue

        try:
            # Use iterdir + recursion to handle symlink loops
            yield from _scan_directory(verdict_dir, seen_paths, repo_path)
        except OSError as e:
            logger.warning(f"Error scanning {verdict_dir}: {e}")


def _scan_directory(
    directory: Path, seen: set[Path], base_dir: Path
) -> Iterator[Path]:
    """Recursively scan directory for verdict files.

    Args:
        directory: Directory to scan.
        seen: Set of already-seen real paths (for loop detection).
        base_dir: Base directory for path validation.

    Yields:
        Paths to verdict markdown files.
    """
    try:
        real_path = directory.resolve()
    except OSError:
        return

    # Check for symlink loops
    if real_path in seen:
        logger.warning(f"Symlink loop detected at {directory}")
        return

    seen.add(real_path)

    try:
        for entry in directory.iterdir():
            if entry.is_file() and entry.suffix == ".md":
                if validate_verdict_path(entry, base_dir):
                    yield entry
            elif entry.is_dir():
                yield from _scan_directory(entry, seen, base_dir)
    except OSError as e:
        logger.warning(f"Error reading directory {directory}: {e}")


def scan_repos(
    registry_path: Path,
    db_path: Path,
    force: bool = False,
) -> int:
    """Scan repositories and update database.

    Args:
        registry_path: Path to project-registry.json.
        db_path: Path to SQLite database.
        force: If True, re-parse all verdicts regardless of hash.

    Returns:
        Number of verdicts processed.
    """
    repos = load_registry(registry_path)
    db = VerdictDatabase(db_path)

    count = 0

    try:
        for repo in repos:
            logger.info(f"Scanning repository: {repo}")

            for verdict_path in discover_verdicts(repo):
                try:
                    content = verdict_path.read_text(encoding="utf-8")
                    content_hash = compute_content_hash(content)

                    if not force and not db.needs_update(str(verdict_path), content_hash):
                        logger.debug(f"Skipping unchanged: {verdict_path}")
                        continue

                    logger.debug(f"Parsing: {verdict_path}")
                    record = parse_verdict(verdict_path)
                    db.upsert_verdict(record)
                    count += 1

                except Exception as e:
                    logger.error(f"Error parsing {verdict_path}: {e}")

    finally:
        db.close()

    return count