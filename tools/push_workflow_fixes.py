#!/usr/bin/env python3
"""Push workflow file fixes that require 'workflow' scope via the in-process classic-PAT pattern (ADR-0216).

Writing .github/workflows/*.yml requires a classic PAT with 'workflow' scope — the
fleet's fine-grained PAT returns 403 for these paths. This tool decrypts the classic
PAT in-process and calls the GitHub REST API directly via `requests`; it never sets
os.environ, never passes the PAT via argv, never logs it.

Defaults to DRY-RUN; pass --apply to mutate (standard 0017).

OPERATOR-RUN ONLY (ADR-0216 §6.1): run this yourself in your own Git Bash. NEVER
let an agent invoke it via its Bash tool — the spawned Python process would be the
agent's child and its heap is theoretically readable while the PAT is in scope.

What it does:
    Fix 1: Add missing permissions block to AssemblyZero's auto-reviewer-caller.yml
           (root cause of startup_failure on all AssemblyZero PRs)
    Fix 2: Change reusable auto-reviewer default from "pr-sentinel" to "issue-reference"
           (dependabot PRs use bare check run name, not composite workflow/job name)
    Fix 3: Deploy auto-reviewer caller to patent-general via PR
           (has GitHub ruleset instead of classic branch protection; uses Contents API)
    Fix 4: Enable auto-delete head branches on all repos (#752)
           (squash merges leave orphan branches — 48 found on career alone)

Issues: #752, #748, #737, #736

Usage:
    poetry run python tools/push_workflow_fixes.py            # dry-run (default)
    poetry run python tools/push_workflow_fixes.py --apply    # execute all fixes
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pat_session import classic_pat_session  # noqa: E402

GITHUB_USER = "martymcenroe"
GH_API = "https://api.github.com"
HTTP_TIMEOUT_S = 30


def _gh_headers(pat: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command (read-only ops only — fine-grained PAT via gh CLI)."""
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"  FAILED: {result.stderr.strip()}")
        sys.exit(1)
    return result


# ---------------------------------------------------------------------------
# Caller workflow content (written in Fix 1 locally; pushed to patent-general
# in Fix 3 via the Contents API).
# ---------------------------------------------------------------------------
CALLER_CONTENT = """name: Auto Review

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


# ---------------------------------------------------------------------------
# Fix 1 + 2: local file writes (working tree only — no GitHub API needed)
# ---------------------------------------------------------------------------

def apply_fix1(caller_path: str) -> None:
    """Write the permissions-annotated caller workflow to the local working tree."""
    with open(caller_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(CALLER_CONTENT)
    print(f"  Wrote {caller_path}")


def apply_fix2(reusable_path: str) -> None:
    """Patch the reusable workflow default required_checks in the local working tree."""
    with open(reusable_path, "r", encoding="utf-8") as f:
        content = f.read()

    old_default = 'default: "pr-sentinel"'
    new_default = 'default: "issue-reference"'

    if old_default not in content:
        print(f"  WARNING: '{old_default}' not found in {reusable_path}")
        print("  The file may have already been updated.")
    else:
        content = content.replace(old_default, new_default)
        with open(reusable_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        print(f"  Updated {reusable_path}")


# ---------------------------------------------------------------------------
# Fix 3: deploy auto-reviewer caller to patent-general via Contents API + PR
# (privileged — workflow scope required; all GitHub API calls inside classic_pat_session)
# ---------------------------------------------------------------------------

def get_main_sha(pg_repo: str) -> str | None:
    """Read-only: get the main branch SHA via gh CLI (fine-grained PAT is sufficient)."""
    result = run(
        ["gh", "api", f"repos/{pg_repo}/git/refs/heads/main", "--jq", ".object.sha"],
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def create_branch(pg_repo: str, branch: str, main_sha: str, pat: str) -> bool:
    """POST /repos/{owner}/{repo}/git/refs — creates the feature branch."""
    resp = requests.post(
        f"{GH_API}/repos/{pg_repo}/git/refs",
        headers=_gh_headers(pat),
        json={"ref": f"refs/heads/{branch}", "sha": main_sha},
        timeout=HTTP_TIMEOUT_S,
    )
    if resp.status_code in (201, 422):
        # 422 = branch already exists from a prior attempt; treat as success
        return True
    print(f"  WARNING: create branch HTTP {resp.status_code}: {resp.text[:160]}")
    return False


def push_workflow_file(
    pg_repo: str,
    branch: str,
    file_path: str,
    content: str,
    commit_message: str,
    pat: str,
) -> bool:
    """PUT /repos/{owner}/{repo}/contents/{path} — write workflow file via Contents API.

    CRLF-normalizes the content bytes before base64-encoding (ADR-0216 §6.3):
    Windows checkouts have CRLF; the Contents API stores bytes verbatim, so
    without normalization the whole file's line endings flip on origin.
    """
    # CRLF normalization (ADR-0216 §6.3) — must happen before base64 encoding
    content_bytes = content.encode("utf-8").replace(b"\r\n", b"\n")
    encoded = base64.b64encode(content_bytes).decode()

    # Check whether the file already exists (to get its SHA for updates)
    check_resp = requests.get(
        f"{GH_API}/repos/{pg_repo}/contents/{file_path}",
        headers=_gh_headers(pat),
        params={"ref": branch},
        timeout=HTTP_TIMEOUT_S,
    )
    body: dict = {
        "message": commit_message,
        "content": encoded,
        "branch": branch,
    }
    if check_resp.status_code == 200:
        body["sha"] = check_resp.json()["sha"]

    resp = requests.put(
        f"{GH_API}/repos/{pg_repo}/contents/{file_path}",
        headers=_gh_headers(pat),
        json=body,
        timeout=HTTP_TIMEOUT_S,
    )
    if resp.status_code in (200, 201):
        print("  Pushed workflow file to branch")
        return True
    print(f"  WARNING: push workflow file HTTP {resp.status_code}: {resp.text[:160]}")
    return False


def create_pr(
    pg_repo: str,
    branch: str,
    title: str,
    body: str,
    pat: str,
) -> str | None:
    """POST /repos/{owner}/{repo}/pulls — returns PR number as string, or None."""
    resp = requests.post(
        f"{GH_API}/repos/{pg_repo}/pulls",
        headers=_gh_headers(pat),
        json={"title": title, "body": body, "head": branch, "base": "main"},
        timeout=HTTP_TIMEOUT_S,
    )
    if resp.status_code == 201:
        pr_num = str(resp.json()["number"])
        pr_url = resp.json()["html_url"]
        print(f"  PR created: {pr_url}")
        return pr_num
    if resp.status_code == 422 and "already exists" in resp.text:
        # PR already open from prior attempt — find it via gh CLI (read-only)
        result = run(
            ["gh", "pr", "list", "--repo", pg_repo, "--head", branch,
             "--json", "number", "--jq", ".[0].number"],
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            pr_num = result.stdout.strip()
            print(f"  PR already exists: #{pr_num}")
            return pr_num
    print(f"  WARNING: create PR HTTP {resp.status_code}: {resp.text[:160]}")
    return None


def wait_and_merge_pr(pg_repo: str, pr_num: str, pat: str) -> bool:
    """Poll for Cerberus approval then merge via REST API (squash)."""
    print("  Waiting for Cerberus approval...")
    for attempt in range(12):
        time.sleep(10)
        result = run(
            ["gh", "api", f"repos/{pg_repo}/pulls/{pr_num}/reviews",
             "--jq", 'map(select(.state == "APPROVED")) | length'],
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip() not in ("", "0"):
            print("  Cerberus approved. Merging...")
            resp = requests.put(
                f"{GH_API}/repos/{pg_repo}/pulls/{pr_num}/merge",
                headers=_gh_headers(pat),
                json={"merge_method": "squash"},
                timeout=HTTP_TIMEOUT_S,
            )
            if resp.status_code == 200:
                print("  Merged.")
                return True
            print(f"  WARNING: merge HTTP {resp.status_code}: {resp.text[:160]}")
            return False
        print(f"    Attempt {attempt + 1}/12...")
    print("  WARNING: Cerberus did not approve within 2 minutes.")
    print(f"  PR #{pr_num} on {pg_repo} is still open — merge manually.")
    return False


def apply_fix3_privileged(pat: str) -> None:
    """All privileged GitHub API calls for Fix 3 — must run inside classic_pat_session."""
    pg_repo = "martymcenroe/patent-general"
    pg_branch = "ci/deploy-auto-reviewer"
    wf_file_path = ".github/workflows/auto-reviewer.yml"
    commit_msg = "ci: deploy auto-reviewer caller workflow (Closes #748)"
    pr_title = "ci: deploy auto-reviewer caller workflow (Closes #748)"
    pr_body = (
        "Deploy Cerberus auto-reviewer caller workflow.\n\n"
        "Closes martymcenroe/patent-general#748\n\n"
        "See parent: martymcenroe/AssemblyZero#748"
    )

    main_sha = get_main_sha(pg_repo)
    if not main_sha:
        print("  WARNING: Could not get patent-general main SHA. Skipping Fix 3.")
        return

    if not create_branch(pg_repo, pg_branch, main_sha, pat):
        print("  WARNING: Could not create branch. Skipping Fix 3.")
        return

    if not push_workflow_file(pg_repo, pg_branch, wf_file_path, CALLER_CONTENT, commit_msg, pat):
        print("  WARNING: Could not push workflow file. Skipping Fix 3.")
        return

    pr_num = create_pr(pg_repo, pg_branch, pr_title, pr_body, pat)
    if not pr_num:
        print("  WARNING: Could not create PR. Skipping merge.")
        return

    wait_and_merge_pr(pg_repo, pr_num, pat)


# ---------------------------------------------------------------------------
# Fix 4: enable auto-delete-head-branches fleet-wide
# (privileged — PATCH /repos/{owner}/{repo} needs classic PAT)
# ---------------------------------------------------------------------------

def list_repos() -> list[dict]:
    """Read-only: list all non-fork repos via gh CLI."""
    result = run(
        ["gh", "repo", "list", GITHUB_USER, "--limit", "200",
         "--json", "nameWithOwner,isFork", "--no-archived"],
        check=False,
    )
    if result.returncode != 0:
        print(f"  WARNING: Could not list repos: {result.stderr[:100]}")
        return []
    return json.loads(result.stdout)


def enable_delete_branch_on_merge(repo_full: str, pat: str) -> tuple[bool, str]:
    """PATCH /repos/{owner}/{repo} — enable delete_branch_on_merge. Returns (ok, detail)."""
    resp = requests.patch(
        f"{GH_API}/repos/{repo_full}",
        headers=_gh_headers(pat),
        json={"delete_branch_on_merge": True},
        timeout=HTTP_TIMEOUT_S,
    )
    if resp.status_code == 200 and resp.json().get("delete_branch_on_merge"):
        return (True, "enabled")
    return (False, f"HTTP {resp.status_code}: {resp.text[:80]}")


def apply_fix4_privileged(repos: list[dict], pat: str) -> None:
    """All privileged GitHub API calls for Fix 4 — must run inside classic_pat_session."""
    enabled = 0
    skipped = 0
    failed = 0
    for repo_info in repos:
        name = repo_info["nameWithOwner"]
        if repo_info.get("isFork"):
            skipped += 1
            continue
        ok, detail = enable_delete_branch_on_merge(name, pat)
        if ok:
            enabled += 1
        else:
            failed += 1
            print(f"  FAIL: {name}: {detail}")
    print(f"  Enabled: {enabled} | Skipped (forks): {skipped} | Failed: {failed}")


# ---------------------------------------------------------------------------
# Local AssemblyZero git steps (working tree + commit — no GitHub API write scope needed)
# ---------------------------------------------------------------------------

def stage_and_commit_local(caller_path: str, reusable_path: str) -> None:
    """Stage Fix 1 + Fix 2 changes and commit to the local AssemblyZero working tree."""
    run(["git", "add", caller_path, reusable_path])

    result = run(["git", "diff", "--cached", "--quiet"], check=False)
    if result.returncode == 0:
        print("  No local changes to commit (already pushed).")
        return

    commit_msg = (
        "fix: auto-reviewer — add caller permissions + fix dependabot check name"
        " (Closes #748)\n"
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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--apply", action="store_true",
        help="Execute all fixes (default: dry-run preview).",
    )
    args = parser.parse_args()

    # Verify we're in the AssemblyZero repo
    result = run(["git", "rev-parse", "--show-toplevel"], check=False)
    toplevel = result.stdout.strip().replace("\\", "/")
    if "AssemblyZero" not in toplevel:
        print(f"ERROR: Must run from AssemblyZero repo, got: {toplevel}")
        return 1

    caller_path = ".github/workflows/auto-reviewer-caller.yml"
    reusable_path = ".github/workflows/auto-reviewer.yml"
    pg_repo = "martymcenroe/patent-general"

    if not args.apply:
        print("DRY-RUN (pass --apply to execute). Planned writes:")
        print()
        print(f"  Fix 1 (local write):  {caller_path}")
        print(f"  Fix 2 (local write):  {reusable_path}")
        print(f"  Fix 3 (Contents API): {pg_repo}/.github/workflows/auto-reviewer.yml")
        print("           via branch:  ci/deploy-auto-reviewer → PR → squash merge")
        print("  Fix 4 (PATCH repos):  delete_branch_on_merge=true on all non-fork repos")
        return 0

    print("=" * 60)
    print("Push Workflow Fixes")
    print("=" * 60)
    print()

    # Fix 1: local write (no classic PAT needed)
    print("Fix 1: Add permissions block to auto-reviewer-caller.yml")
    apply_fix1(caller_path)
    print()

    # Fix 2: local write (no classic PAT needed)
    print("Fix 2: Change auto-reviewer.yml default from 'pr-sentinel' to 'issue-reference'")
    apply_fix2(reusable_path)
    print()

    # Local git commit for Fix 1 + Fix 2 (fine-grained PAT can push non-workflow commits)
    print("Staging and committing AssemblyZero workflow fixes...")
    stage_and_commit_local(caller_path, reusable_path)
    print()

    # Fix 3 + Fix 4: privileged GitHub API writes — enter classic_pat_session once
    repos = list_repos()  # read-only; fine-grained PAT fine here

    with classic_pat_session() as pat:
        # Fix 3: deploy auto-reviewer to patent-general via Contents API + PR
        print("Fix 3: Deploy auto-reviewer caller to patent-general via PR")
        apply_fix3_privileged(pat)
        print()

        # Fix 4: enable auto-delete head branches fleet-wide
        print("Fix 4: Enable auto-delete head branches fleet-wide")
        apply_fix4_privileged(repos, pat)
        print()

    print("=" * 60)
    print("DONE.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
