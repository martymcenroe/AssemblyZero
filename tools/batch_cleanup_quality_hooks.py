#!/usr/bin/env python3
"""Batch remove per-repo quality hooks now covered by global ~/.claude/settings.json.

Phase 3 of AssemblyZero #873: pre-edit-check.sh, pre-edit-security-warn.sh,
post-edit-lint.sh, and pre-commit-report-check.sh are now registered globally.
Per-repo copies in 5 repos are redundant.

For each repo:
1. Removes the 4 quality hook files from .claude/hooks/
2. Removes those entries from .claude/settings.json
3. Cleans up empty directories
4. Creates issue, branch, commit, push, PR

Usage:
    poetry run python tools/batch_cleanup_quality_hooks.py --dry-run
    poetry run python tools/batch_cleanup_quality_hooks.py
    poetry run python tools/batch_cleanup_quality_hooks.py --repo Aletheia
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

PROJECTS_ROOT = Path("C:/Users/mcwiz/Projects")

# Only these repos have quality hooks deployed
TARGET_REPOS = {"Aletheia", "Talos", "Clio", "maintenance", "maintenance-pytest"}

# Hook files being removed (now global)
HOOK_FILES_TO_REMOVE = [
    "pre-edit-check.sh",
    "pre-edit-security-warn.sh",
    "post-edit-lint.sh",
    "pre-commit-report-check.sh",
]

ISSUE_TITLE = "chore: remove per-repo quality hooks (now global)"
ISSUE_BODY = """\
## Summary

Remove per-repo copies of quality hooks (worktree isolation, security warnings,
lint, report gate). These hooks are now registered globally in
`~/.claude/settings.json` pointing to `~/.claude/hooks/`.

Global versions include improvements:
- `pre-edit-check.sh`: Dynamic repo name in worktree suggestion
- `post-edit-lint.sh`: Asymmetric degradation (always-ruff, config-check ESLint)
- `pre-commit-report-check.sh`: Auto-detect guard (only enforces if docs/reports/ exists)

## Context

Part of AssemblyZero #873 (consolidate quality-tier hooks to global).
"""

BRANCH_PREFIX = "cleanup-quality-hooks"


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


def clean_settings_json(repo_path: Path) -> bool:
    """Remove quality hook entries from .claude/settings.json.

    Returns True if the file was modified.
    """
    settings_path = repo_path / ".claude" / "settings.json"
    if not settings_path.exists():
        return False

    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False

    modified = False

    for event_key in ["PreToolUse", "PostToolUse"]:
        matcher_list = settings.get("hooks", {}).get(event_key, [])
        cleaned_list = []
        for block in matcher_list:
            block_hooks = block.get("hooks", [])
            cleaned_hooks = [
                h for h in block_hooks
                if not any(hf in h.get("command", "") for hf in HOOK_FILES_TO_REMOVE)
            ]
            if len(cleaned_hooks) != len(block_hooks):
                modified = True
            if cleaned_hooks:
                block["hooks"] = cleaned_hooks
                cleaned_list.append(block)
            elif block_hooks:
                modified = True
        if modified:
            if cleaned_list:
                settings["hooks"][event_key] = cleaned_list
            else:
                settings.get("hooks", {}).pop(event_key, None)

    if not modified:
        return False

    # Clean up empty hooks section
    hooks = settings.get("hooks", {})
    if not any(hooks.get(k) for k in ["PreToolUse", "PostToolUse"]):
        settings.pop("hooks", None)

    if not settings:
        settings_path.unlink()
    else:
        settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    return True


def cleanup_repo(owner: str, repo_name: str, dry_run: bool) -> str:
    """Remove per-repo quality hooks from a single repo. Returns status."""
    repo_path = PROJECTS_ROOT / repo_name
    if not repo_path.exists() or not (repo_path / ".git").exists():
        return "SKIP (not cloned)"

    hooks_dir = repo_path / ".claude" / "hooks"
    found = [f for f in HOOK_FILES_TO_REMOVE if (hooks_dir / f).exists()]
    if not found:
        return "SKIP (no quality hooks found)"

    if dry_run:
        return f"WOULD CLEAN ({', '.join(found)})"

    # Get default branch
    for branch in ["main", "master"]:
        check = run(["git", "rev-parse", "--verify", branch], cwd=str(repo_path), check=False)
        if check.returncode == 0:
            default_branch = branch
            break
    else:
        return "ERROR: no main/master branch"

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
    removed_files = []
    for hook_file in HOOK_FILES_TO_REMOVE:
        target = hooks_dir / hook_file
        if target.exists():
            target.unlink()
            removed_files.append(hook_file)

    # Remove empty hooks directory
    if hooks_dir.exists() and not any(hooks_dir.iterdir()):
        hooks_dir.rmdir()

    # Clean settings.json
    clean_settings_json(repo_path)

    # Remove empty .claude directory
    claude_dir = repo_path / ".claude"
    if claude_dir.exists() and not any(claude_dir.iterdir()):
        claude_dir.rmdir()

    # Stage and commit
    run(["git", "add", "-A", ".claude/"], cwd=str(repo_path))

    status = run(["git", "status", "--porcelain"], cwd=str(repo_path))
    if not status.stdout.strip():
        run(["git", "checkout", default_branch], cwd=str(repo_path))
        run(["git", "branch", "-d", branch_name], cwd=str(repo_path))
        return "SKIP (no changes after cleanup)"

    commit_msg = (
        f"chore: remove per-repo quality hooks (now global) Closes #{issue_number}\n\n"
        f"Quality hooks (worktree isolation, security warnings, lint, report gate)\n"
        f"are now registered globally in ~/.claude/settings.json.\n\n"
        f"Upstream: AssemblyZero #873\n\n"
        f"Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
    )
    run(["git", "commit", "-m", commit_msg], cwd=str(repo_path))
    run(["git", "push", "-u", "origin", "HEAD"], cwd=str(repo_path))

    pr_body = (
        f"## Summary\n\n"
        f"- Remove per-repo quality hooks (now global in `~/.claude/hooks/`)\n"
        f"- Removed: {', '.join(removed_files)}\n"
        f"- Global versions include dynamic repo names, asymmetric lint, auto-detect guards\n\n"
        f"Closes #{issue_number}\n\n"
        f"## Test plan\n\n"
        f"- [ ] Verify global worktree isolation blocks code edits on main\n"
        f"- [ ] Verify global lint fires on Python file edits\n\n"
        f"Generated with [Claude Code](https://claude.com/claude-code)"
    )
    result = run([
        "gh", "pr", "create",
        "--repo", f"{owner}/{repo_name}",
        "--title", f"chore: remove per-repo quality hooks (now global) Closes #{issue_number}",
        "--body", pr_body
    ], cwd=str(repo_path))
    pr_url = result.stdout.strip()

    run(["git", "checkout", default_branch], cwd=str(repo_path))

    return f"CLEANED ({', '.join(removed_files)}) -- Issue #{issue_number}, PR {pr_url}"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Batch cleanup per-repo quality hooks")
    parser.add_argument("--owner", default="martymcenroe", help="GitHub owner")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--repo", help="Clean a single repo")
    args = parser.parse_args()

    print(f"Quality Hook Cleanup -- {'DRY RUN' if args.dry_run else 'LIVE'}")
    print(f"Owner: {args.owner}")
    print()

    if args.repo:
        repos = [args.repo]
    else:
        repos = sorted(TARGET_REPOS)

    print(f"Target repos: {len(repos)}")
    print()

    results = {}
    for repo_name in repos:
        print(f"  [{repo_name}] Processing...")
        try:
            status = cleanup_repo(args.owner, repo_name, args.dry_run)
            results[repo_name] = status
            print(f"  [{repo_name}] {status}")
        except Exception as e:
            results[repo_name] = f"ERROR: {e}"
            print(f"  [{repo_name}] ERROR: {e}")

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

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
