#!/usr/bin/env python3
"""Archive worktree lineage before deletion.

Issue #189: Add pre-worktree-removal cleanup protocol to save audit artifacts.

Usage:
    python tools/archive-worktree-lineage.py --worktree ../AssemblyZero-42 --issue 42

This script:
1. Copies docs/lineage/active/{issue}-*/ to main repo's docs/lineage/archived/
2. Stages the archived files in main
3. Evicts the poetry venv cached for the worktree, so it can be removed
4. Does NOT remove the worktree (user does that after)

It deletes nothing (#3558). It used to clean the worktree's caches first,
with `shutil.rmtree`, and the shell guard reads that token and refused the
whole script to an agent -- so the step CLAUDE.md prescribes before every PR
could not be run as written. The caches are gitignored, and `git worktree
remove`, the last step of the same sequence, deletes every ignored file in
the worktree anyway.
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

            # #3518: an earlier archive of the same lineage is a record too; it
            # is moved aside, stamped, rather than deleted to make room.
            if dest_dir.exists():
                from datetime import datetime

                previous = dest_dir.with_name(
                    f"{dest_dir.name}.prev-{datetime.now().strftime('%Y%m%dT%H%M%S')}"
                )
                dest_dir.rename(previous)
                print(f"  Previous archive moved aside: {previous.name}")
            shutil.copytree(src_dir, dest_dir)

            archived_dirs.append(dest_dir)
            print(f"  Archived: {src_dir.name}")

    return archived_dirs


def is_linked_worktree(path: Path) -> bool:
    """Whether ``path`` is a LINKED worktree, not a repository's main checkout.

    A linked worktree's git dir (``.git/worktrees/<name>``) differs from the
    repository's common dir (``.git``); in the main checkout they are the
    same. Anything git cannot answer for is not a linked worktree.
    """
    def _rev(flag: str) -> Path | None:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--path-format=absolute", flag],
            capture_output=True, text=True,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        return Path(result.stdout.strip()).resolve()

    git_dir, common = _rev("--git-dir"), _rev("--git-common-dir")
    return git_dir is not None and common is not None and git_dir != common


def require_linked_worktree(path: Path) -> None:
    """#3528: refuse before anything is deleted or evicted. The script used
    to accept the main checkout -- run through ``poetry -C <main>``, ``.``
    resolved there -- and emptied its ``__pycache__``, stopping short of
    ``poetry env remove --all`` only because it crashed first."""
    if not is_linked_worktree(path):
        raise SystemExit(
            f"REFUSED: {path} is not a linked git worktree (it is a main "
            "checkout, or not a repository). Nothing was deleted or evicted. "
            "Pass the worktree's own path to --worktree."
        )


def stage_archived(main_repo: Path, issue_number: int) -> None:
    """Stage archived lineage in the main repo without committing.

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
        print(f"  Staged archived lineage for #{issue_number}. Ready to be committed.")
    else:
        print("  No lineage changes to stage")


def evict_poetry_venv(worktree_path: Path) -> None:
    """Evict poetry-cached virtualenvs tied to the worktree path.

    On Windows, poetry creates a cached venv in ~/.cache/pypoetry/virtualenvs/
    whose interpreter references the worktree root. The venv's open file
    handles prevent `git worktree remove` from deleting the on-disk
    directory (Windows "Device or resource busy" / "Permission denied").

    Running `poetry env remove --all` inside the worktree before removal
    evicts the cached venv and releases the locks.

    Args:
        worktree_path: Path to the worktree being cleaned.
    """
    # #3528: `poetry env remove --all` run in a main checkout evicts the venv
    # every worktree test run borrows.
    require_linked_worktree(worktree_path)
    pyproject = worktree_path / "pyproject.toml"
    if not pyproject.exists():
        # Not a poetry project — skip silently.
        return

    print("  Evicting poetry-cached virtualenvs (so the worktree can be removed cleanly)...")
    result = subprocess.run(
        ["poetry", "env", "remove", "--all"],
        cwd=str(worktree_path),
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        # poetry prints one line per env removed; keep it minimal
        output = (result.stdout or "").strip()
        if output:
            # Indent each line under the parent bullet
            for line in output.splitlines():
                print(f"    {line}")
        else:
            print("    No poetry venvs were cached for this worktree.")
    else:
        # Non-fatal — worktree removal may still work, just log and continue.
        err = (result.stderr or result.stdout or "").strip()
        print(f"    WARNING: `poetry env remove --all` returned {result.returncode}: {err[:200]}")
        print("    The worktree may still have locked files when you run `git worktree remove`.")


def main():
    """Main entry point for CLI usage."""
    parser = argparse.ArgumentParser(description="Archive worktree lineage before deletion")
    parser.add_argument("--worktree", required=True, help="Path to worktree")
    parser.add_argument("--issue", required=True, type=int, help="Issue number")
    parser.add_argument("--main-repo", default=".", help="Path to main repo (default: cwd)")
    parser.add_argument("--no-stage", action="store_true", help="Skip git add")
    args = parser.parse_args()

    worktree = Path(args.worktree).resolve()
    main_repo = Path(args.main_repo).resolve()

    # #3528: before any step that deletes, moves or evicts anything.
    require_linked_worktree(worktree)

    print(f"Archiving lineage from {worktree}")

    # Archive lineage
    archived = archive_lineage(worktree, args.issue, main_repo)

    # Stage in repo
    if archived and not args.no_stage:
        stage_archived(main_repo, args.issue)

    # Evict poetry venvs that lock the worktree directory on Windows
    evict_poetry_venv(worktree)

    print("\nDone. You can now remove the worktree:")
    print(f"  git worktree remove {worktree}")


if __name__ == "__main__":
    main()
