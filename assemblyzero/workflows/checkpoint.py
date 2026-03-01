"""Checkpoint database path management for AssemblyZero workflows.

This module provides functions to determine the checkpoint database location,
supporting per-repo isolation for safe concurrent workflow execution.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def get_repo_root() -> Path | None:
    """Get the root directory of the current git repository.

    Returns:
        Path to the git repository root, or None if not in a git repo
        or if git is not installed.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
        return None
    except FileNotFoundError:
        # git is not installed
        return None


def get_checkpoint_db_path() -> Path:
    """Determine the checkpoint database path.

    Priority:
    1. ASSEMBLYZERO_WORKFLOW_DB environment variable (if set and non-empty)
    2. Per-repo: {repo_root}/.assemblyzero/issue_workflow.db
    3. Fail closed with descriptive error if outside git repo

    Returns:
        Path to the checkpoint database file.

    Raises:
        SystemExit: If not in a git repo and no env var set (fail closed).
    """
    # Priority 1: Environment variable override
    env_path = os.environ.get("ASSEMBLYZERO_WORKFLOW_DB", "")
    if env_path:  # Non-empty string
        # Expand ~ to home directory
        expanded_path = os.path.expanduser(env_path)
        db_path = Path(expanded_path)
        # Ensure parent directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return db_path

    # Priority 2: Per-repo path
    repo_root = get_repo_root()
    if repo_root is not None:
        assemblyzero_dir = repo_root / ".assemblyzero"
        assemblyzero_dir.mkdir(parents=True, exist_ok=True)
        return assemblyzero_dir / "issue_workflow.db"

    # Priority 3: Fail closed
    print(
        "ERROR: Not in a git repository and ASSEMBLYZERO_WORKFLOW_DB environment "
        "variable is not set.\n"
        "Please either:\n"
        "  1. Run from within a git repository, or\n"
        "  2. Set ASSEMBLYZERO_WORKFLOW_DB to a custom database path",
        file=sys.stderr,
    )
    sys.exit(1)