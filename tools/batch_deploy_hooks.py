#!/usr/bin/env python3
"""Batch deploy security hooks to all GitHub repos.

Deploys secret-guard.sh and bash-gate.sh to every repo under the owner.
Creates issues, branches, commits, pushes, and PRs automatically.

Usage:
    poetry run python tools/batch_deploy_hooks.py --owner martymcenroe --dry-run
    poetry run python tools/batch_deploy_hooks.py --owner martymcenroe
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECTS_ROOT = Path("C:/Users/mcwiz/Projects")
ASSEMBLY_ZERO = PROJECTS_ROOT / "AssemblyZero"
HOOKS_SOURCE = ASSEMBLY_ZERO / ".claude" / "hooks"

# Already patched -- skip these
ALREADY_PATCHED = {"AssemblyZero", "Aletheia", "Talos", "Hermes", "Agora"}

# Hook files to deploy
HOOK_FILES = ["secret-guard.sh", "bash-gate.sh"]

ISSUE_TITLE = "Deploy security hooks: secret-guard.sh + bash-gate.sh"
ISSUE_BODY = """\
## Summary

Deploy canonical security hooks from AssemblyZero:
- `secret-guard.sh` -- blocks agent access to `.env`, `.dev.vars`, `.aws/credentials`
- `bash-gate.sh` -- blocks chain operators and destructive git commands

## Context

All repos must have baseline agent protection hooks. This is part of a
cross-repo security hardening effort tracked in AssemblyZero #696, #697.
"""

BRANCH_PREFIX = "deploy-security-hooks"


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


def repo_has_hooks(repo_path: Path) -> bool:
    """Check if a repo already has both hook files and settings configured."""
    hooks_dir = repo_path / ".claude" / "hooks"
    settings_file = repo_path / ".claude" / "settings.json"

    has_files = all((hooks_dir / f).exists() for f in HOOK_FILES)
    if not has_files:
        return False

    if not settings_file.exists():
        return False

    try:
        settings = json.loads(settings_file.read_text(encoding="utf-8"))
        hooks = settings.get("hooks", {}).get("PreToolUse", [])
        has_secret_guard = False
        has_bash_gate = False
        for matcher_block in hooks:
            for hook in matcher_block.get("hooks", []):
                cmd = hook.get("command", "")
                if "secret-guard.sh" in cmd:
                    has_secret_guard = True
                if "bash-gate.sh" in cmd:
                    has_bash_gate = True
        return has_secret_guard and has_bash_gate
    except (json.JSONDecodeError, KeyError):
        return False


def ensure_cloned(owner: str, repo_name: str) -> Path:
    """Ensure repo is cloned locally. Returns the path."""
    repo_path = PROJECTS_ROOT / repo_name
    if repo_path.exists() and (repo_path / ".git").exists():
        return repo_path

    # Clone it
    print(f"    Cloning {owner}/{repo_name}...")
    run(["git", "clone", f"https://github.com/{owner}/{repo_name}.git",
         str(repo_path)])
    return repo_path


def get_default_branch(repo_path: Path) -> str:
    """Get the default branch name."""
    result = run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=str(repo_path)
    )
    current = result.stdout.strip()

    # Check if main or master exists
    for branch in ["main", "master"]:
        check = run(
            ["git", "rev-parse", "--verify", branch],
            cwd=str(repo_path), check=False
        )
        if check.returncode == 0:
            return branch

    return current


def generate_settings_json(repo_name: str, existing_settings: dict | None) -> dict:
    """Generate or merge settings.json with hook configuration."""
    hook_entries = [
        {
            "type": "command",
            "command": f"bash /c/Users/mcwiz/Projects/{repo_name}/.claude/hooks/secret-guard.sh",
            "timeout": 5,
            "description": "Secret File Guard (blocks access to .env, credentials)"
        },
        {
            "type": "command",
            "command": f"bash /c/Users/mcwiz/Projects/{repo_name}/.claude/hooks/bash-gate.sh",
            "timeout": 5,
            "description": "Bash Command Gate (blocks &&, |, ;)"
        }
    ]

    bash_matcher = {
        "matcher": "Bash",
        "hooks": hook_entries
    }

    if existing_settings is None:
        return {
            "hooks": {
                "PreToolUse": [bash_matcher],
                "PostToolUse": []
            }
        }

    # Merge into existing settings
    settings = json.loads(json.dumps(existing_settings))  # deep copy
    hooks = settings.setdefault("hooks", {})
    pre_tool_use = hooks.setdefault("PreToolUse", [])

    # Find existing Bash matcher
    bash_block = None
    for block in pre_tool_use:
        if block.get("matcher") == "Bash":
            bash_block = block
            break

    if bash_block is None:
        # Add new Bash matcher
        pre_tool_use.insert(0, bash_matcher)
    else:
        # Add missing hooks to existing Bash matcher
        existing_commands = {h.get("command", "") for h in bash_block.get("hooks", [])}
        for entry in hook_entries:
            if entry["command"] not in existing_commands:
                bash_block["hooks"].insert(0, entry)

    return settings


def deploy_to_repo(owner: str, repo_name: str, dry_run: bool) -> str:
    """Deploy hooks to a single repo. Returns status string."""
    repo_path = ensure_cloned(owner, repo_name)

    # Check if already fully patched
    if repo_has_hooks(repo_path):
        return "SKIP (already patched)"

    if dry_run:
        return "WOULD DEPLOY"

    default_branch = get_default_branch(repo_path)

    # Make sure we're on default branch and up to date
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

    # Create branch
    run(["git", "checkout", "-b", branch_name], cwd=str(repo_path))

    # Create .claude/hooks/ directory
    hooks_dir = repo_path / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    # Copy hook files
    for hook_file in HOOK_FILES:
        src = HOOKS_SOURCE / hook_file
        dst = hooks_dir / hook_file
        shutil.copy2(str(src), str(dst))

    # Generate/merge settings.json
    settings_path = repo_path / ".claude" / "settings.json"
    existing_settings = None
    if settings_path.exists():
        try:
            existing_settings = json.loads(
                settings_path.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            existing_settings = None

    new_settings = generate_settings_json(repo_name, existing_settings)
    settings_path.write_text(
        json.dumps(new_settings, indent=2) + "\n",
        encoding="utf-8"
    )

    # Stage and commit
    run(["git", "add", ".claude/"], cwd=str(repo_path))

    commit_msg = (
        f"fix: deploy security hooks (close #{issue_number})\n\n"
        f"- Add secret-guard.sh (blocks .env, .dev.vars, .aws/credentials access)\n"
        f"- Add bash-gate.sh (blocks chain operators and destructive git)\n"
        f"- Configure hooks in .claude/settings.json\n\n"
        f"Upstream: AssemblyZero #696, #697\n\n"
        f"Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
    )
    run(["git", "commit", "-m", commit_msg], cwd=str(repo_path))

    # Push
    run(["git", "push", "-u", "origin", "HEAD"], cwd=str(repo_path))

    # Create PR
    pr_body = (
        f"## Summary\n\n"
        f"- Add `secret-guard.sh` -- blocks agent access to `.env`, `.dev.vars`, `.aws/credentials`\n"
        f"- Add `bash-gate.sh` -- blocks chain operators and destructive git commands\n"
        f"- Configure hooks in `.claude/settings.json`\n\n"
        f"Closes #{issue_number}\n"
        f"Upstream: AssemblyZero #696, #697\n\n"
        f"## Test plan\n\n"
        f"- [ ] Run `github_protection_audit.py --hooks` -- verify PASS\n\n"
        f"Generated with [Claude Code](https://claude.com/claude-code)"
    )
    result = run([
        "gh", "pr", "create",
        "--repo", f"{owner}/{repo_name}",
        "--title", f"Deploy security hooks: secret-guard.sh + bash-gate.sh (#{issue_number})",
        "--body", pr_body
    ], cwd=str(repo_path))
    pr_url = result.stdout.strip()

    # Switch back to default branch
    run(["git", "checkout", default_branch], cwd=str(repo_path))

    return f"DEPLOYED -- Issue #{issue_number}, PR {pr_url}"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Batch deploy security hooks")
    parser.add_argument("--owner", default="martymcenroe", help="GitHub owner")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be done without making changes")
    parser.add_argument("--repo", help="Deploy to a single repo (for testing)")
    args = parser.parse_args()

    print(f"Batch Hook Deployment -- {'DRY RUN' if args.dry_run else 'LIVE'}")
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
        if repo_name in ALREADY_PATCHED:
            results[repo_name] = "SKIP (already patched)"
            print(f"  [{repo_name}] SKIP (already patched)")
            continue

        print(f"  [{repo_name}] Processing...")
        try:
            status = deploy_to_repo(args.owner, repo_name, args.dry_run)
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
    deployed = sum(1 for v in results.values() if v.startswith("DEPLOYED"))
    skipped = sum(1 for v in results.values() if v.startswith("SKIP"))
    would = sum(1 for v in results.values() if v.startswith("WOULD"))
    errors = sum(1 for v in results.values() if v.startswith("ERROR"))
    print(f"  Deployed: {deployed}")
    print(f"  Skipped:  {skipped}")
    print(f"  Would:    {would}")
    print(f"  Errors:   {errors}")
    print(f"  Total:    {len(results)}")

    if errors:
        print()
        print("ERRORS:")
        for repo, status in sorted(results.items()):
            if status.startswith("ERROR"):
                print(f"  {repo}: {status}")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
