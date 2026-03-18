#!/usr/bin/env python3
"""
Push workflow file fixes that require the 'workflow' scope.

THIS SCRIPT MUST BE RUN BY THE USER, NOT BY AN AGENT.
It pushes changes to .github/workflows/ files, which require a classic PAT
with 'workflow' scope. The fine-grained PAT agents use cannot push these.

Usage:
    1. Switch to classic PAT:  gh auth login -h github.com -p https
    2. Run:  poetry run python tools/push_workflow_fixes.py
    3. Switch back:  gh auth login -h github.com -p https  (paste fine-grained PAT)

What it does:
    Fix 1: Add missing permissions block to AssemblyZero's auto-reviewer-caller.yml
           (root cause of startup_failure on all AssemblyZero PRs)
    Fix 2: Change reusable auto-reviewer default from "pr-sentinel" to "issue-reference"
           (dependabot PRs use bare check run name, not composite workflow/job name)
    Fix 3: Deploy auto-reviewer caller to patent-general via PR
           (has GitHub ruleset instead of classic branch protection, Contents API blocked on main)
    Fix 4: Enable auto-delete head branches on all repos (#752)
           (squash merges leave orphan branches — 48 found on career alone)

Issue: #752, #748, #737, #736
"""

import subprocess
import sys


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"  FAILED: {result.stderr.strip()}")
        sys.exit(1)
    return result


def verify_classic_pat() -> bool:
    """Check that the current gh auth has workflow scope."""
    result = run(["gh", "auth", "status"], check=False)
    output = result.stdout + result.stderr
    if "workflow" not in output.lower():
        print("WARNING: Could not confirm 'workflow' scope on current PAT.")
        print("This script requires a classic PAT with 'workflow' scope.")
        response = input("Continue anyway? (y/N): ").strip().lower()
        return response == "y"
    return True


def main():
    print("=" * 60)
    print("Push Workflow Fixes (requires classic PAT with workflow scope)")
    print("=" * 60)
    print()

    # Verify we're in AssemblyZero
    result = run(["git", "rev-parse", "--show-toplevel"], check=False)
    toplevel = result.stdout.strip().replace("\\", "/")
    if "AssemblyZero" not in toplevel:
        print(f"ERROR: Must run from AssemblyZero repo, got: {toplevel}")
        sys.exit(1)

    # Check auth
    print("Checking GitHub auth...")
    if not verify_classic_pat():
        print("Aborted.")
        sys.exit(1)
    print()

    # Fix 1: AssemblyZero caller permissions
    print("Fix 1: Add permissions block to auto-reviewer-caller.yml")
    caller_path = ".github/workflows/auto-reviewer-caller.yml"

    caller_content = """name: Auto Review

# Caller workflow: invokes the reusable auto-reviewer from AssemblyZero.
# Copy this file to .github/workflows/auto-reviewer.yml in each repo.
#
# For repos with additional required checks beyond pr-sentinel, override:
#   required_checks: "issue-reference, CI, CodeQL"
#
# Issue: #736

on:
  pull_request:
    branches: [main]
    types: [opened, synchronize, reopened]

permissions:
  pull-requests: write
  checks: read

jobs:
  auto-review:
    uses: martymcenroe/AssemblyZero/.github/workflows/auto-reviewer.yml@main
    with:
      required_checks: "issue-reference"
    secrets:
      REVIEWER_APP_ID: ${{ secrets.REVIEWER_APP_ID }}
      REVIEWER_APP_PRIVATE_KEY: ${{ secrets.REVIEWER_APP_PRIVATE_KEY }}
"""

    with open(caller_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(caller_content)
    print(f"  Wrote {caller_path}")

    # Fix 2: Reusable workflow default
    print("Fix 2: Change auto-reviewer.yml default from 'pr-sentinel' to 'issue-reference'")
    reusable_path = ".github/workflows/auto-reviewer.yml"

    with open(reusable_path, "r", encoding="utf-8") as f:
        content = f.read()

    old_default = "default: \"pr-sentinel\""
    new_default = "default: \"issue-reference\""

    if old_default not in content:
        print(f"  WARNING: '{old_default}' not found in {reusable_path}")
        print("  The file may have already been updated.")
    else:
        content = content.replace(old_default, new_default)
        with open(reusable_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        print(f"  Updated {reusable_path}")

    print()

    # Fix 3: Deploy auto-reviewer to patent-general via PR
    # patent-general has a GitHub ruleset (not classic branch protection)
    # so the fleet deploy script can't push via Contents API to main.
    # Instead: create branch, push file, create PR, wait for Cerberus, merge.
    print("Fix 3: Deploy auto-reviewer caller to patent-general via PR")
    pg_repo = "martymcenroe/patent-general"
    pg_branch = "ci/deploy-auto-reviewer"

    import base64 as b64mod
    import time

    # Get main SHA
    result = run(["gh", "api", f"repos/{pg_repo}/git/refs/heads/main",
                  "--jq", ".object.sha"], check=False)
    if result.returncode != 0:
        print(f"  WARNING: Could not get patent-general main SHA. Skipping.")
    else:
        main_sha = result.stdout.strip()

        # Create branch (may already exist from prior attempt)
        run(["gh", "api", f"repos/{pg_repo}/git/refs",
             "-X", "POST", "-f", f"ref=refs/heads/{pg_branch}",
             "-f", f"sha={main_sha}"], check=False)

        # Push workflow file to branch
        wf_content = b64mod.b64encode(caller_content.encode()).decode()
        result = run([
            "gh", "api", f"repos/{pg_repo}/contents/.github/workflows/auto-reviewer.yml",
            "-X", "PUT",
            "-f", "message=ci: deploy auto-reviewer caller workflow (#748)",
            "-f", f"content={wf_content}",
            "-f", f"branch={pg_branch}",
        ], check=False)

        if result.returncode != 0:
            print(f"  WARNING: Could not push workflow file: {result.stderr[:100]}")
        else:
            print("  Pushed workflow file to branch")

            # Create PR
            result = run([
                "gh", "pr", "create",
                "--repo", pg_repo,
                "--head", pg_branch,
                "--title", "ci: deploy auto-reviewer caller workflow (#748)",
                "--body", "Deploy Cerberus auto-reviewer caller workflow.\n\nCloses martymcenroe/AssemblyZero#748",
            ], check=False)

            if result.returncode == 0:
                pr_url = result.stdout.strip()
                print(f"  PR created: {pr_url}")

                # Wait for Cerberus approval and merge
                print("  Waiting for Cerberus approval...")
                pr_num = pr_url.rstrip("/").split("/")[-1]
                for attempt in range(12):
                    time.sleep(10)
                    result = run([
                        "gh", "api", f"repos/{pg_repo}/pulls/{pr_num}/reviews",
                        "--jq", 'map(select(.state == "APPROVED")) | length',
                    ], check=False)
                    if result.returncode == 0 and result.stdout.strip() != "0":
                        print("  Cerberus approved. Merging...")
                        run(["gh", "pr", "merge", pr_num,
                             "--squash", "--repo", pg_repo], check=False)
                        print("  Merged.")
                        break
                    print(f"    Attempt {attempt + 1}/12...")
                else:
                    print("  WARNING: Cerberus did not approve within 2 minutes.")
                    print(f"  PR is open at {pr_url} — merge manually.")
            else:
                print(f"  WARNING: Could not create PR: {result.stderr[:100]}")

    print()

    # Stage, commit, push (AssemblyZero local changes only)
    print("Staging and committing AssemblyZero workflow fixes...")
    run(["git", "add", caller_path, reusable_path])

    # Check if there's anything to commit
    result = run(["git", "diff", "--cached", "--quiet"], check=False)
    if result.returncode == 0:
        print("  No local changes to commit (already pushed).")
    else:
        commit_msg = (
            "fix: auto-reviewer — add caller permissions + fix dependabot check name (#748)\n"
            "\n"
            "Two fixes:\n"
            "1. AssemblyZero's auto-reviewer-caller.yml was missing the permissions\n"
            "   block (pull-requests: write, checks: read) that the fleet deploy\n"
            "   script added to all other repos. Caused startup_failure on every\n"
            "   AssemblyZero PR.\n"
            "\n"
            "2. Changed the default required_checks from 'pr-sentinel' to\n"
            "   'issue-reference'. Dependabot PRs create check runs named\n"
            "   'issue-reference' (bare), while normal PRs create\n"
            "   'pr-sentinel / issue-reference' (composite). The contains()\n"
            "   matcher finds 'issue-reference' in both forms.\n"
            "\n"
            "Closes #748\n"
            "\n"
            "Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
        )

        run(["git", "commit", "-m", commit_msg])

        print()
        print("Pushing to origin...")
        result = run(["git", "push"], check=False)
        if result.returncode != 0:
            print("  Direct push failed, trying current branch...")
            branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
            run(["git", "push", "origin", branch])

    # Fix 4: Enable auto-delete head branches on all repos (#752)
    print("Fix 4: Enable auto-delete head branches fleet-wide")
    import json as json_mod

    result = run(["gh", "repo", "list", "martymcenroe",
                  "--limit", "200", "--json", "nameWithOwner,isFork",
                  "--no-archived"], check=False)
    if result.returncode != 0:
        print(f"  WARNING: Could not list repos: {result.stderr[:100]}")
    else:
        repos = json_mod.loads(result.stdout)
        enabled = 0
        skipped = 0
        failed = 0
        for repo_info in repos:
            name = repo_info["nameWithOwner"]
            if repo_info.get("isFork"):
                skipped += 1
                continue
            r = run(["gh", "api", "-X", "PATCH", f"repos/{name}",
                     "-F", "delete_branch_on_merge=true",
                     "--jq", ".delete_branch_on_merge"], check=False)
            if r.returncode == 0 and r.stdout.strip() == "true":
                enabled += 1
            else:
                failed += 1
                print(f"  FAIL: {name}: {r.stderr[:80]}")
        print(f"  Enabled: {enabled} | Skipped (forks): {skipped} | Failed: {failed}")

    print()
    print("=" * 60)
    print("DONE. Now switch back to the fine-grained PAT:")
    print("  gh auth login -h github.com -p https")
    print("=" * 60)


if __name__ == "__main__":
    main()
