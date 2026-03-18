#!/usr/bin/env python3
"""Merge all open pr-sentinel permissions PRs across the fleet.

This script is designed to be run MANUALLY by the user with a classic token.
The agent writes it; the user reviews it, auths with a classic token, runs it,
then brings the agent back to analyze the results.

Usage:
    1. Review this script (it only calls `gh` — no token handling)
    2. gh auth login → paste classic token (repo scope)
    3. poetry run python tools/merge_sentinel_permissions_prs.py
    4. gh auth login → restore fine-grained PAT
    5. Delete classic token

What it does:
    - Finds all open PRs matching "add permissions block to pr-sentinel"
    - For each PR: disables enforce_admins, merges with --squash, re-enables enforce_admins
    - Saves results to docs/audits/github-protection/merge-sentinel-prs-TIMESTAMP.md

What it does NOT do:
    - Read, store, or transmit any token
    - Modify any code or file content
    - Access any secrets
"""

import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

GITHUB_USER = "martymcenroe"
PR_TITLE_PATTERN = "fix: add permissions block to pr-sentinel workflow"


@dataclass
class MergeResult:
    repo: str
    pr_number: int
    success: bool
    detail: str
    protection_restored: bool = True


def run_gh(*args: str, timeout: int = 30) -> tuple[int, str]:
    """Run a gh CLI command and return (returncode, output)."""
    cmd = ["gh", *args]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        output = (result.stdout or "") + (result.stderr or "")
        return result.returncode, output.strip()
    except subprocess.TimeoutExpired:
        return 1, "TIMEOUT"
    except FileNotFoundError:
        return 1, "gh CLI not found"


def detect_token_type() -> str:
    """Detect whether current gh auth is classic or fine-grained."""
    rc, output = run_gh("auth", "status")
    if rc != 0:
        return "unknown (auth failed)"
    if "ghp_" in output:
        return "classic"
    if "github_pat_" in output:
        return "fine-grained"
    return "unknown"


def find_open_prs() -> list[dict]:
    """Find all open PRs matching the sentinel permissions title pattern."""
    rc, output = run_gh(
        "search", "prs",
        "--author", GITHUB_USER,
        "--state", "open",
        PR_TITLE_PATTERN,
        "--limit", "100",
        "--json", "repository,number,title,url",
        timeout=60,
    )
    if rc != 0:
        print(f"  ERROR searching for PRs: {output[:200]}")
        return []

    import json
    try:
        prs = json.loads(output)
    except json.JSONDecodeError:
        print(f"  ERROR parsing search results: {output[:200]}")
        return []

    return prs


def disable_enforce_admins(repo_full_name: str) -> bool:
    """Disable enforce_admins on main branch protection."""
    rc, output = run_gh(
        "api", f"repos/{repo_full_name}/branches/main/protection/enforce_admins",
        "-X", "DELETE",
        timeout=15,
    )
    return rc == 0


def enable_enforce_admins(repo_full_name: str) -> bool:
    """Re-enable enforce_admins on main branch protection."""
    rc, output = run_gh(
        "api", f"repos/{repo_full_name}/branches/main/protection/enforce_admins",
        "-X", "POST",
        timeout=15,
    )
    return rc == 0


def merge_pr(repo_full_name: str, pr_number: int) -> MergeResult:
    """Temporarily disable enforce_admins, merge PR, re-enable."""
    # Step 1: Disable enforce_admins
    if not disable_enforce_admins(repo_full_name):
        return MergeResult(
            repo=repo_full_name,
            pr_number=pr_number,
            success=False,
            detail="Failed to disable enforce_admins",
            protection_restored=True,  # never changed it
        )

    # Step 2: Merge
    rc, output = run_gh(
        "pr", "merge", str(pr_number),
        "--repo", repo_full_name,
        "--squash",
        "--delete-branch",
        "--admin",
        timeout=30,
    )

    # Step 3: ALWAYS re-enable enforce_admins
    restored = enable_enforce_admins(repo_full_name)

    if rc == 0:
        return MergeResult(
            repo=repo_full_name,
            pr_number=pr_number,
            success=True,
            detail="Merged successfully",
            protection_restored=restored,
        )
    else:
        return MergeResult(
            repo=repo_full_name,
            pr_number=pr_number,
            success=False,
            detail=output[:200],
            protection_restored=restored,
        )


def write_report(results: list[MergeResult], token_type: str) -> Path:
    """Write results to a markdown audit file."""
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%d-%H%M%S")
    output_dir = Path(__file__).parent.parent / "docs" / "audits" / "github-protection"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"merge-sentinel-prs-{timestamp}.md"

    successes = [r for r in results if r.success]
    failures = [r for r in results if not r.success]
    unrestored = [r for r in results if not r.protection_restored]

    lines = [
        "# Sentinel Permissions PR Merge Report",
        "",
        f"**Date:** {now.isoformat()}",
        f"**Token type:** {token_type}",
        f"**Script:** `tools/merge_sentinel_permissions_prs.py`",
        f"**PR title pattern:** `{PR_TITLE_PATTERN}`",
        f"**Method:** Temporarily disable enforce_admins, merge --admin --squash, re-enable",
        "",
        "## Summary",
        "",
        "| Status | Count |",
        "|--------|-------|",
        f"| SUCCESS | {len(successes)} |",
        f"| FAILURE | {len(failures)} |",
        f"| TOTAL | {len(results)} |",
        f"| Protection NOT restored | {len(unrestored)} |",
        "",
        "## Results",
        "",
        "| Repo | PR # | Status | Protection Restored | Detail |",
        "|------|------|--------|---------------------|--------|",
    ]

    for r in sorted(results, key=lambda x: x.repo):
        status = "SUCCESS" if r.success else "**FAILURE**"
        restored = "Yes" if r.protection_restored else "**NO**"
        detail = r.detail.replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {r.repo} | #{r.pr_number} | {status} | {restored} | {detail} |")

    if unrestored:
        lines.extend([
            "",
            "## CRITICAL: Repos With Unrestored Protection",
            "",
            "These repos have enforce_admins DISABLED. Fix immediately:",
            "",
        ])
        for r in unrestored:
            lines.append(
                f"- **{r.repo}**: `gh api repos/{r.repo}/branches/main/protection/enforce_admins -X POST`"
            )

    if failures:
        lines.extend([
            "",
            "## Failures Requiring Manual Action",
            "",
        ])
        for r in sorted(failures, key=lambda x: x.repo):
            lines.append(f"- **{r.repo}** (#{r.pr_number}): {r.detail}")

    lines.extend([
        "",
        "---",
        "",
        f"*Generated by tools/merge_sentinel_permissions_prs.py on {now.strftime('%Y-%m-%d')}*",
    ])

    output_file.write_text("\n".join(lines), encoding="utf-8")
    return output_file


def main():
    print("=" * 60)
    print("Merge Sentinel Permissions PRs")
    print("=" * 60)

    # Detect token type
    print("\nDetecting token type...")
    token_type = detect_token_type()
    print(f"  Token type: {token_type}")

    if "fine-grained" in token_type:
        print("\n  WARNING: This script requires a classic token with repo scope.")
        print("  Run: gh auth login -h github.com -p https")
        print("  Then re-run this script.")
        sys.exit(1)

    if "unknown" in token_type:
        print("\n  WARNING: Could not detect token type. Proceeding anyway...")

    # Find open PRs
    print(f"\nSearching for open PRs matching: {PR_TITLE_PATTERN}")
    prs = find_open_prs()
    print(f"  Found {len(prs)} open PRs")

    if not prs:
        print("\n  No PRs to merge. Done.")
        sys.exit(0)

    # Dry-run preview
    print(f"\nWill merge {len(prs)} PRs using enforce_admins toggle method:")
    for pr in prs[:5]:
        repo = pr.get("repository", {}).get("nameWithOwner", "unknown")
        print(f"  - {repo} #{pr.get('number', '?')}")
    if len(prs) > 5:
        print(f"  ... and {len(prs) - 5} more")

    print("\nFor each PR: disable enforce_admins → merge --admin --squash → re-enable enforce_admins")
    print("Press Ctrl+C to abort.\n")
    time.sleep(3)

    # Merge each PR
    results: list[MergeResult] = []
    print(f"Merging {len(prs)} PRs...\n")

    for i, pr in enumerate(prs, 1):
        repo_name = pr.get("repository", {}).get("nameWithOwner", "unknown")
        pr_number = pr.get("number", 0)
        print(f"  [{i}/{len(prs)}] {repo_name} #{pr_number}")

        result = merge_pr(repo_name, pr_number)
        results.append(result)

        status = "OK" if result.success else f"FAIL: {result.detail[:60]}"
        restored = "" if result.protection_restored else " [PROTECTION NOT RESTORED!]"
        print(f"    → {status}{restored}")

        # Brief pause to avoid rate limiting
        if i < len(prs):
            time.sleep(1)

    # Write report
    report_path = write_report(results, token_type)

    # Summary
    successes = sum(1 for r in results if r.success)
    failures = sum(1 for r in results if not r.success)
    unrestored = sum(1 for r in results if not r.protection_restored)
    print("\n" + "=" * 60)
    print(f"Done. {successes} succeeded, {failures} failed.")
    if unrestored:
        print(f"  ⚠️  {unrestored} repos have enforce_admins NOT restored — see report!")
    print(f"Report saved to: {report_path}")
    print("=" * 60)

    if failures or unrestored:
        sys.exit(2)


if __name__ == "__main__":
    main()
