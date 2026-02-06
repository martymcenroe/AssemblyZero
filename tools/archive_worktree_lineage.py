#!/usr/bin/env python3
"""Archive worktree lineage before deletion.

Issue #189: Add pre-worktree-removal cleanup protocol to save audit artifacts.

Usage:
    python tools/archive-worktree-lineage.py --worktree ../AssemblyZero-42 --issue 42

This script:
1. Copies docs/lineage/active/{issue}-*/ to main repo's docs/lineage/archived/
2. Commits the archived files to main
3. Cleans ephemeral files (.coverage, __pycache__)
4. Does NOT remove the worktree (user does that after)
"""

import argparse
import shutil
import subprocess
from pathlib import Path


def archive_lineage(worktree_path: Path, issue_number: int, main_repo: Path) -> list[Path]:
    """Archive lineage from worktree to main repo.

    Args:
        worktree_path: Path to the worktree being removed
        issue_number: Issue number for this worktree
        main_repo: Path to main repository

    Returns:
        List of archived directory paths
    """
    archived_dirs = []

    # Find lineage directories matching this issue
    lineage_active = worktree_path / "docs" / "lineage" / "active"
    if not lineage_active.exists():
        print(f"No lineage directory found at {lineage_active}")
        return archived_dirs

    # Find directories matching issue number (e.g., 42-testing, 42-feature)
    pattern = f"{issue_number}-*"
    for src_dir in lineage_active.glob(pattern):
        if src_dir.is_dir():
            # Destination in main repo
            dest_dir = main_repo / "docs" / "lineage" / "archived" / src_dir.name
            dest_dir.parent.mkdir(parents=True, exist_ok=True)

            # Copy entire directory (overwrite if exists)
            if dest_dir.exists():
                shutil.rmtree(dest_dir)
            shutil.copytree(src_dir, dest_dir)

            archived_dirs.append(dest_dir)
            print(f"  Archived: {src_dir.name}")

    return archived_dirs


def clean_ephemeral(worktree_path: Path) -> None:
    """Remove ephemeral files that shouldn't persist.

    Args:
        worktree_path: Path to the worktree being cleaned
    """
    ephemeral = [".coverage", "__pycache__", ".pytest_cache", ".assemblyzero/audit"]

    for name in ephemeral:
        target = worktree_path / name
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
            print(f"  Cleaned: {name}")


def commit_archived(main_repo: Path, issue_number: int) -> None:
    """Commit archived lineage to main repo.

    Args:
        main_repo: Path to main repository
        issue_number: Issue number for commit message
    """
    subprocess.run(
        ["git", "-C", str(main_repo), "add", "docs/lineage/archived/"],
        check=True,
    )

    result = subprocess.run(
        ["git", "-C", str(main_repo), "diff", "--cached", "--quiet"],
    )

    if result.returncode != 0:  # There are staged changes
        subprocess.run(
            ["git", "-C", str(main_repo), "commit", "-m",
             f"chore: archive workflow lineage for #{issue_number}"],
            check=True,
        )
        print(f"  Committed archived lineage for #{issue_number}")
    else:
        print("  No lineage changes to commit")


def main():
    """Main entry point for CLI usage."""
    parser = argparse.ArgumentParser(description="Archive worktree lineage before deletion")
    parser.add_argument("--worktree", required=True, help="Path to worktree")
    parser.add_argument("--issue", required=True, type=int, help="Issue number")
    parser.add_argument("--main-repo", default=".", help="Path to main repo (default: cwd)")
    parser.add_argument("--no-commit", action="store_true", help="Skip git commit")
    args = parser.parse_args()

    worktree = Path(args.worktree).resolve()
    main_repo = Path(args.main_repo).resolve()

    print(f"Archiving lineage from {worktree}")

    # Archive lineage
    archived = archive_lineage(worktree, args.issue, main_repo)

    # Clean ephemeral files
    clean_ephemeral(worktree)

    # Commit to main
    if archived and not args.no_commit:
        commit_archived(main_repo, args.issue)

    print(f"\nDone. You can now remove the worktree:")
    print(f"  git worktree remove {worktree}")


if __name__ == "__main__":
    main()
