#!/usr/bin/env python3
"""Batch remove per-repo security hooks now covered by global ~/.claude/settings.json.

Phase 2 of AssemblyZero #872: secret-guard.sh and bash-gate.sh are now registered
globally in ~/.claude/settings.json pointing to ~/.claude/hooks/. Per-repo copies
are redundant (double-firing) and stale (older versions).

For each repo:
1. Removes .claude/hooks/bash-gate.sh and .claude/hooks/secret-guard.sh
2. Removes those entries from .claude/settings.json Bash matcher
3. Cleans up empty directories and settings files
4. Creates issue, branch, commit, push, PR

Usage:
    poetry run python tools/batch_cleanup_security_hooks.py --dry-run
    poetry run python tools/batch_cleanup_security_hooks.py
    poetry run python tools/batch_cleanup_security_hooks.py --repo unleashed
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

PROJECTS_ROOT = Path("C:/Users/mcwiz/Projects")

# Hook files being removed (now global)
HOOK_FILES_TO_REMOVE = ["secret-guard.sh", "bash-gate.sh"]

# Repos to skip entirely (no per-repo hooks deployed, or handled manually)
SKIP_REPOS = {"AssemblyZero"}

ISSUE_TITLE = "chore: remove per-repo security hooks (now global)"
ISSUE_BODY = """\
## Summary

Remove per-repo copies of `secret-guard.sh` and `bash-gate.sh`. These hooks are
now registered globally in `~/.claude/settings.json` pointing to `~/.claude/hooks/`.

Per-repo copies cause double-firing (global + local) and version drift (local copies
are stale, missing Categories E-H hardening from AssemblyZero #714).

## Context

Part of AssemblyZero #872 (consolidate per-repo security hooks to global).
"""

BRANCH_PREFIX = "cleanup-security-hooks"


def run(cmd: list[str], cwd: str | None = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    result = subprocess.run(
        cmd, capture_output=True, text=True, cwd=cwd,
        encoding="utf-8", errors="replace"
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(cmd)}\n"
            f"stderr: {result.stderr}\nstdout: {result.stdout}"
        )
    return result


def list_repos(owner: str) -> list[str]:
    """List all non-archived repos for the owner."""
    result = run([
        "gh", "repo", "list", owner,
        "--limit", "200", "--no-archived",
        "--json", "name", "--jq", ".[].name"
    ])
    return [r.strip() for r in result.stdout.strip().split("\n") if r.strip()]


def repo_has_hooks_to_clean(repo_path: Path) -> bool:
    """Check if repo has per-repo security hooks that need removal."""
    hooks_dir = repo_path / ".claude" / "hooks"
    return any((hooks_dir / f).exists() for f in HOOK_FILES_TO_REMOVE)


def clean_settings_json(repo_path: Path) -> bool:
    """Remove security hook entries from .claude/settings.json.

    Returns True if the file was modified.
    """
    settings_path = repo_path / ".claude" / "settings.json"
    if not settings_path.exists():
        return False

    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False

    hooks = settings.get("hooks", {})
    pre_tool_use = hooks.get("PreToolUse", [])
    modified = False

    # Filter out security hook entries from each matcher block
    cleaned_pre_tool_use = []
    for block in pre_tool_use:
        block_hooks = block.get("hooks", [])

        # Remove entries referencing our hook files
        cleaned_hooks = [
            h for h in block_hooks
            if not any(hf in h.get("command", "") for hf in HOOK_FILES_TO_REMOVE)
        ]

        if len(cleaned_hooks) != len(block_hooks):
            modified = True

        # Keep the block only if it still has hooks
        if cleaned_hooks:
            block["hooks"] = cleaned_hooks
            cleaned_pre_tool_use.append(block)
        elif block_hooks:
            # Block had hooks but now empty — mark as modified
            modified = True

    if not modified:
        return False

    # Update or clean up
    if cleaned_pre_tool_use:
        hooks["PreToolUse"] = cleaned_pre_tool_use
    else:
        hooks.pop("PreToolUse", None)

    # If hooks section is now empty (no PreToolUse, no PostToolUse with content)
    post_tool_use = hooks.get("PostToolUse", [])
    if not hooks.get("PreToolUse") and not post_tool_use:
        settings.pop("hooks", None)

    # If settings is now empty, delete the file
    if not settings:
        settings_path.unlink()
        return True

    settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    return True


def cleanup_repo(owner: str, repo_name: str, dry_run: bool) -> str:
    """Remove per-repo security hooks from a single repo. Returns status."""
    repo_path = PROJECTS_ROOT / repo_name
    if not repo_path.exists() or not (repo_path / ".git").exists():
        return "SKIP (not cloned)"

    if not repo_has_hooks_to_clean(repo_path):
        return "SKIP (no hooks to clean)"

    if dry_run:
        hooks_dir = repo_path / ".claude" / "hooks"
        found = [f for f in HOOK_FILES_TO_REMOVE if (hooks_dir / f).exists()]
        return f"WOULD CLEAN ({', '.join(found)})"

    # Get default branch
    for branch in ["main", "master"]:
        check = run(["git", "rev-parse", "--verify", branch], cwd=str(repo_path), check=False)
        if check.returncode == 0:
            default_branch = branch
            break
    else:
        return "ERROR: no main/master branch"

    # Ensure on default branch and up to date
    run(["git", "checkout", default_branch], cwd=str(repo_path))
    run(["git", "pull", "--ff-only"], cwd=str(repo_path), check=False)

    # Create issue
    result = run([
        "gh", "issue", "create",
        "--repo", f"{owner}/{repo_name}",
        "--title", ISSUE_TITLE,
        "--body", ISSUE_BODY
    ])
    issue_url = result.stdout.strip()
    issue_number = issue_url.split("/")[-1]

    branch_name = f"{issue_number}-{BRANCH_PREFIX}"
    run(["git", "checkout", "-b", branch_name], cwd=str(repo_path))

    # Remove hook files
    hooks_dir = repo_path / ".claude" / "hooks"
    removed_files = []
    for hook_file in HOOK_FILES_TO_REMOVE:
        target = hooks_dir / hook_file
        if target.exists():
            target.unlink()
            removed_files.append(hook_file)

    # Remove empty hooks directory (only if no other files remain)
    if hooks_dir.exists() and not any(hooks_dir.iterdir()):
        hooks_dir.rmdir()

    # Clean settings.json
    clean_settings_json(repo_path)

    # Remove empty .claude directory (only if nothing remains)
    claude_dir = repo_path / ".claude"
    if claude_dir.exists() and not any(claude_dir.iterdir()):
        claude_dir.rmdir()

    # Stage and commit
    run(["git", "add", "-A", ".claude/"], cwd=str(repo_path))

    # Check if there are actually changes to commit
    status = run(["git", "status", "--porcelain"], cwd=str(repo_path))
    if not status.stdout.strip():
        run(["git", "checkout", default_branch], cwd=str(repo_path))
        run(["git", "branch", "-d", branch_name], cwd=str(repo_path))
        return "SKIP (no changes after cleanup)"

    commit_msg = (
        f"chore: remove per-repo security hooks (now global) Closes #{issue_number}\n\n"
        f"secret-guard.sh and bash-gate.sh are now registered globally in\n"
        f"~/.claude/settings.json. Per-repo copies caused double-firing\n"
        f"and version drift.\n\n"
        f"Upstream: AssemblyZero #872\n\n"
        f"Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
    )
    run(["git", "commit", "-m", commit_msg], cwd=str(repo_path))

    # Push
    run(["git", "push", "-u", "origin", "HEAD"], cwd=str(repo_path))

    # Create PR
    pr_body = (
        f"## Summary\n\n"
        f"- Remove per-repo `secret-guard.sh` and `bash-gate.sh` (now global)\n"
        f"- Clean up `.claude/settings.json` hook registration\n"
        f"- Global hooks in `~/.claude/hooks/` provide protection fleet-wide\n\n"
        f"Closes #{issue_number}\n\n"
        f"## Test plan\n\n"
        f"- [ ] Verify global hooks fire on blocked patterns (e.g. `cat .env`)\n\n"
        f"Generated with [Claude Code](https://claude.com/claude-code)"
    )
    result = run([
        "gh", "pr", "create",
        "--repo", f"{owner}/{repo_name}",
        "--title", f"chore: remove per-repo security hooks (now global) Closes #{issue_number}",
        "--body", pr_body
    ], cwd=str(repo_path))
    pr_url = result.stdout.strip()

    # Switch back to default branch
    run(["git", "checkout", default_branch], cwd=str(repo_path))

    return f"CLEANED ({', '.join(removed_files)}) -- Issue #{issue_number}, PR {pr_url}"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Batch cleanup per-repo security hooks")
    parser.add_argument("--owner", default="martymcenroe", help="GitHub owner")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be done without making changes")
    parser.add_argument("--repo", help="Clean a single repo (for testing)")
    args = parser.parse_args()

    print(f"Security Hook Cleanup -- {'DRY RUN' if args.dry_run else 'LIVE'}")
    print(f"Owner: {args.owner}")
    print()

    if args.repo:
        repos = [args.repo]
    else:
        repos = list_repos(args.owner)

    print(f"Found {len(repos)} repos")
    print()

    results = {}
    for repo_name in sorted(repos):
        if repo_name in SKIP_REPOS:
            results[repo_name] = "SKIP (excluded)"
            print(f"  [{repo_name}] SKIP (excluded)")
            continue

        print(f"  [{repo_name}] Processing...")
        try:
            status = cleanup_repo(args.owner, repo_name, args.dry_run)
            results[repo_name] = status
            print(f"  [{repo_name}] {status}")
        except Exception as e:
            results[repo_name] = f"ERROR: {e}"
            print(f"  [{repo_name}] ERROR: {e}")

    # Summary
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    cleaned = sum(1 for v in results.values() if v.startswith("CLEANED"))
    skipped = sum(1 for v in results.values() if v.startswith("SKIP"))
    would = sum(1 for v in results.values() if v.startswith("WOULD"))
    errors = sum(1 for v in results.values() if v.startswith("ERROR"))
    print(f"  Cleaned: {cleaned}")
    print(f"  Skipped: {skipped}")
    print(f"  Would:   {would}")
    print(f"  Errors:  {errors}")
    print(f"  Total:   {len(results)}")

    if errors:
        print()
        print("ERRORS:")
        for repo, status in sorted(results.items()):
            if status.startswith("ERROR"):
                print(f"  {repo}: {status}")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
