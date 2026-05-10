#!/usr/bin/env python3
"""Reset spawn state for a speed-run attempt (#1076).

Performs the cleanup needed between attempts:

  1. Closes any open PR for the issue (without merging).
  2. Removes the worktree at `{repo}-{issue}` if it exists.
  3. Deletes the local feature branch (safe-delete).
  4. Deletes `docs/lineage/active/{issue}-*/` directories.
  5. Reopens the issue if it was closed.
  6. Prints "spawn state restored" on success.

Idempotent: safe to run multiple times. Each step is independently
guarded — a missing PR / worktree / branch is not an error.

Usage:

    poetry run python tools/speedrun_reset.py \\
        --repo /c/Users/mcwiz/Projects/boostgauge \\
        --issue 35

    # Reset all known speed-run issues at once:
    poetry run python tools/speedrun_reset.py \\
        --repo /c/Users/mcwiz/Projects/boostgauge \\
        --all-issues

The `--all-issues` mode reads `data/speedrun/run-log.jsonl` and resets
every issue that's appeared in any attempt (covers the full speed-run
arc across multiple takes).
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str], cwd: Path | None = None, check: bool = False):
    """Subprocess wrapper that returns the result and captures both streams."""
    return subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, check=check,
    )


def _gh_repo(repo_root: Path) -> str:
    """Read GitHub remote and extract owner/repo."""
    result = _run(["git", "remote", "get-url", "origin"], cwd=repo_root)
    if result.returncode != 0:
        raise RuntimeError(f"Could not read git remote: {result.stderr}")
    url = result.stdout.strip()
    # https://github.com/owner/repo.git → owner/repo
    if url.startswith("https://github.com/"):
        path = url[len("https://github.com/"):]
    elif url.startswith("git@github.com:"):
        path = url[len("git@github.com:"):]
    else:
        raise RuntimeError(f"Unrecognized remote URL: {url}")
    if path.endswith(".git"):
        path = path[:-4]
    return path


def close_open_prs(repo: str, issue: int) -> int:
    """Close any open PR that closes this issue. Returns count closed."""
    # Find PRs that reference the issue in body.
    result = _run([
        "gh", "pr", "list",
        "--repo", repo,
        "--state", "open",
        "--search", f"Closes #{issue}",
        "--json", "number,title",
    ])
    if result.returncode != 0:
        print(f"  WARNING: gh pr list failed: {result.stderr.strip()}")
        return 0
    try:
        prs = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return 0
    closed = 0
    for pr in prs:
        n = pr["number"]
        r = _run(["gh", "pr", "close", str(n), "--repo", repo])
        if r.returncode == 0:
            print(f"  Closed PR #{n}: {pr['title']}")
            closed += 1
        else:
            print(f"  WARNING: could not close PR #{n}: {r.stderr.strip()}")
    return closed


def remove_worktree(repo_root: Path, issue: int) -> bool:
    """Remove worktree at `{repo}-{issue}` if it exists."""
    parent = repo_root.parent
    worktree_path = parent / f"{repo_root.name}-{issue}"
    if not worktree_path.exists():
        return False
    result = _run(
        ["git", "worktree", "remove", str(worktree_path)],
        cwd=repo_root,
    )
    if result.returncode == 0:
        print(f"  Removed worktree: {worktree_path}")
        return True
    # Worktree might exist but be unregistered in git's view. Try direct rmdir.
    try:
        shutil.rmtree(worktree_path)
        print(f"  Removed worktree directory: {worktree_path}")
        return True
    except OSError as e:
        print(f"  WARNING: could not remove worktree {worktree_path}: {e}")
        return False


def delete_local_branches(repo_root: Path, issue: int) -> int:
    """Delete local branches matching `{issue}-*` pattern. Returns count deleted."""
    result = _run(
        ["git", "branch", "--list", f"{issue}-*"],
        cwd=repo_root,
    )
    if result.returncode != 0:
        return 0
    branches = [
        line.strip().lstrip("* ").strip()
        for line in result.stdout.splitlines()
        if line.strip()
    ]
    deleted = 0
    for branch in branches:
        if not branch:
            continue
        # Try safe-delete first; never use -D
        r = _run(["git", "branch", "-d", branch], cwd=repo_root)
        if r.returncode == 0:
            print(f"  Deleted local branch: {branch}")
            deleted += 1
        else:
            # Branch wasn't merged. For speed-run reset, that's expected
            # (we're discarding work). Use -d still — the user can decide
            # if they want -D themselves. We don't auto-escalate.
            print(
                f"  Skipped branch {branch} (not merged; "
                f"reset with `git branch -D {branch}` if intentional)"
            )
    return deleted


def delete_lineage_dirs(repo_root: Path, issue: int) -> int:
    """Delete docs/lineage/active/{issue}-* directories. Returns count deleted."""
    lineage_active = repo_root / "docs" / "lineage" / "active"
    if not lineage_active.exists():
        return 0
    deleted = 0
    for d in lineage_active.glob(f"{issue}-*"):
        if not d.is_dir():
            continue
        try:
            shutil.rmtree(d)
            print(f"  Deleted lineage dir: {d.relative_to(repo_root)}")
            deleted += 1
        except OSError as e:
            print(f"  WARNING: could not delete {d}: {e}")
    return deleted


def reopen_issue(repo: str, issue: int) -> bool:
    """Reopen the GitHub issue if it's currently closed."""
    result = _run([
        "gh", "issue", "view", str(issue),
        "--repo", repo,
        "--json", "state",
    ])
    if result.returncode != 0:
        return False
    try:
        info = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False
    if info.get("state") == "OPEN":
        return False
    r = _run([
        "gh", "issue", "reopen", str(issue),
        "--repo", repo,
    ])
    if r.returncode == 0:
        print(f"  Reopened issue #{issue}")
        return True
    print(f"  WARNING: could not reopen issue #{issue}: {r.stderr.strip()}")
    return False


def reset_one_issue(repo_root: Path, repo: str, issue: int) -> None:
    """Run all six reset steps for one issue."""
    print(f"\nResetting issue #{issue}:")
    close_open_prs(repo, issue)
    remove_worktree(repo_root, issue)
    delete_local_branches(repo_root, issue)
    delete_lineage_dirs(repo_root, issue)
    reopen_issue(repo, issue)


def all_logged_issues(repo_root: Path) -> list[int]:
    """Read run-log.jsonl and return unique issue numbers."""
    log_path = repo_root / "data" / "speedrun" / "run-log.jsonl"
    if not log_path.exists():
        return []
    issues: set[int] = set()
    with log_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if "issue" in entry:
                    issues.add(int(entry["issue"]))
            except (json.JSONDecodeError, ValueError, TypeError):
                continue
    return sorted(issues)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reset speed-run state for one or more issues",
    )
    parser.add_argument(
        "--repo", required=True, type=Path,
        help="Path to the target repo (e.g., /c/Users/mcwiz/Projects/boostgauge)",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--issue", type=int, help="Reset a single issue")
    group.add_argument(
        "--all-issues", action="store_true",
        help="Reset every issue that has appeared in run-log.jsonl",
    )
    args = parser.parse_args()

    repo_root = args.repo.resolve()
    if not repo_root.exists():
        print(f"ERROR: repo path does not exist: {repo_root}")
        return 1

    try:
        repo = _gh_repo(repo_root)
    except RuntimeError as e:
        print(f"ERROR: {e}")
        return 1

    if args.issue:
        reset_one_issue(repo_root, repo, args.issue)
    else:
        issues = all_logged_issues(repo_root)
        if not issues:
            print("No issues in run-log.jsonl — nothing to reset.")
            return 0
        print(f"Resetting {len(issues)} issue(s) from run-log: {issues}")
        for issue in issues:
            reset_one_issue(repo_root, repo, issue)

    print("\nspawn state restored")
    return 0


if __name__ == "__main__":
    sys.exit(main())
