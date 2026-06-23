#!/usr/bin/env python3
"""Merge all open pr-sentinel permissions PRs across the fleet.

Uses the in-process classic-PAT pattern (ADR-0216) for all privileged calls:
  (a) DELETE .../branches/main/protection/enforce_admins  — disable admin enforcement
  (b) PUT    .../pulls/{n}/merge  {"merge_method": "squash"}  — merge the PR
  (c) POST   .../branches/main/protection/enforce_admins  — re-enable admin enforcement

Step (c) runs in a try/finally block so admin enforcement is ALWAYS restored
even if the merge fails.  Leaving enforce_admins disabled is a hard safety
failure; the try/finally is non-negotiable.

Defaults to DRY-RUN; pass --apply to mutate (standard 0017).

OPERATOR-RUN ONLY (ADR-0216 §6.1): run this yourself in your own Git Bash.
NEVER let an agent invoke it via its Bash tool — the spawned Python process
would be the agent's child and its heap is theoretically readable while the
PAT is in scope.

Usage:
    poetry run python tools/merge_sentinel_permissions_prs.py            # dry-run
    poetry run python tools/merge_sentinel_permissions_prs.py --apply    # execute
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pat_session import classic_pat_session  # noqa: E402

GITHUB_USER = "martymcenroe"
GH_API = "https://api.github.com"
HTTP_TIMEOUT_S = 30
PR_TITLE_PATTERN = "fix: add permissions block to pr-sentinel workflow"


def _gh_headers(pat: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


@dataclass
class MergeResult:
    repo: str
    pr_number: int
    success: bool
    detail: str
    protection_restored: bool = True
    errors: list[str] = field(default_factory=list)


def find_open_prs() -> list[dict]:
    """Find all open PRs matching the sentinel permissions title pattern."""
    result = subprocess.run(
        [
            "gh", "search", "prs",
            "--author", GITHUB_USER,
            "--state", "open",
            PR_TITLE_PATTERN,
            "--limit", "100",
            "--json", "repository,number,title,url",
        ],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        output = (result.stdout + result.stderr).strip()
        print(f"  ERROR searching for PRs: {output[:200]}")
        return []
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"  ERROR parsing search results: {result.stdout[:200]}")
        return []


def _disable_enforce_admins(repo_full_name: str, pat: str) -> tuple[bool, str]:
    """DELETE enforce_admins via classic PAT. Returns (ok, detail)."""
    resp = requests.delete(
        f"{GH_API}/repos/{repo_full_name}/branches/main/protection/enforce_admins",
        headers=_gh_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    # 204 No Content is the success response for DELETE enforce_admins
    if resp.status_code in (200, 204):
        return (True, "disabled")
    return (False, f"HTTP {resp.status_code}: {resp.text[:160]}")


def _enable_enforce_admins(repo_full_name: str, pat: str) -> tuple[bool, str]:
    """POST enforce_admins via classic PAT. Returns (ok, detail)."""
    resp = requests.post(
        f"{GH_API}/repos/{repo_full_name}/branches/main/protection/enforce_admins",
        headers=_gh_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    if resp.status_code in (200, 201):
        return (True, "restored")
    return (False, f"HTTP {resp.status_code}: {resp.text[:160]}")


def _merge_pr_rest(repo_full_name: str, pr_number: int, pat: str) -> tuple[bool, str]:
    """PUT /pulls/{n}/merge via classic PAT. Returns (ok, detail).

    The classic PAT merges through branch protection without --admin.
    That is the entire point of ADR-0216 here.
    """
    resp = requests.put(
        f"{GH_API}/repos/{repo_full_name}/pulls/{pr_number}/merge",
        headers=_gh_headers(pat),
        json={"merge_method": "squash"},
        timeout=HTTP_TIMEOUT_S,
    )
    if resp.status_code in (200, 201):
        sha = resp.json().get("sha", "")
        return (True, f"squash-merged sha={sha[:10]}")
    return (False, f"HTTP {resp.status_code}: {resp.text[:200]}")


def merge_pr(repo_full_name: str, pr_number: int, pat: str) -> MergeResult:
    """Disable enforce_admins, merge PR via REST, ALWAYS re-enable.

    The try/finally ensures enforce_admins is restored even if the merge
    call raises an exception.  Leaving a repo unprotected is a hard failure.
    """
    result = MergeResult(
        repo=repo_full_name,
        pr_number=pr_number,
        success=False,
        detail="",
    )

    # Step (a): disable enforce_admins
    ok, detail = _disable_enforce_admins(repo_full_name, pat)
    if not ok:
        result.detail = f"Failed to disable enforce_admins: {detail}"
        result.protection_restored = True  # never changed it
        return result

    # Steps (b) + (c) — try/finally guarantees (c) always runs
    try:
        # Step (b): merge via REST (no --admin)
        ok, detail = _merge_pr_rest(repo_full_name, pr_number, pat)
        if ok:
            result.success = True
            result.detail = detail
        else:
            result.detail = f"Merge failed: {detail}"
    finally:
        # Step (c): re-enable enforce_admins — unconditional
        ok_restore, restore_detail = _enable_enforce_admins(repo_full_name, pat)
        result.protection_restored = ok_restore
        if not ok_restore:
            result.errors.append(
                f"CRITICAL: enforce_admins NOT restored: {restore_detail}"
            )

    return result


def write_report(results: list[MergeResult]) -> Path:
    """Write results to a markdown audit file."""
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%d-%H%M%S")
    output_dir = (
        Path(__file__).parent.parent / "docs" / "audits" / "github-protection"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"merge-sentinel-prs-{timestamp}.md"

    successes = [r for r in results if r.success]
    failures = [r for r in results if not r.success]
    unrestored = [r for r in results if not r.protection_restored]

    lines = [
        "# Sentinel Permissions PR Merge Report",
        "",
        f"**Date:** {now.isoformat()}",
        "**Script:** `tools/merge_sentinel_permissions_prs.py`",
        f"**PR title pattern:** `{PR_TITLE_PATTERN}`",
        "**Method:** in-process classic-PAT (ADR-0216): disable enforce_admins → "
        "REST squash-merge → re-enable enforce_admins (try/finally)",
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
        lines.append(
            f"| {r.repo} | #{r.pr_number} | {status} | {restored} | {detail} |"
        )

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
                f"- **{r.repo}**: "
                f"`gh api repos/{r.repo}/branches/main/protection/enforce_admins -X POST`"
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
        f"*Generated by tools/merge_sentinel_permissions_prs.py on "
        f"{now.strftime('%Y-%m-%d')}*",
    ])

    output_file.write_text("\n".join(lines), encoding="utf-8")
    return output_file


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--apply", action="store_true",
        help="Actually merge PRs (default: dry-run preview).",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Merge Sentinel Permissions PRs")
    print("=" * 60)

    # Find open PRs (read-only — fine-grained PAT via gh CLI is sufficient)
    print(f"\nSearching for open PRs matching: {PR_TITLE_PATTERN}")
    prs = find_open_prs()
    print(f"  Found {len(prs)} open PRs")

    if not prs:
        print("\n  No PRs to merge. Done.")
        return 0

    if not args.apply:
        print(
            f"\nDRY-RUN (pass --apply to merge). Would process {len(prs)} PR(s):\n"
        )
        for pr in prs:
            repo = pr.get("repository", {}).get("nameWithOwner", "unknown")
            num = pr.get("number", "?")
            title = pr.get("title", "")[:60]
            print(f"  - {repo} #{num}  {title}")
        print(
            "\nFor each PR: disable enforce_admins → REST squash-merge → "
            "re-enable enforce_admins (try/finally)"
        )
        return 0

    # --apply: open classic-PAT session for the entire batch
    results: list[MergeResult] = []
    print(f"\nMerging {len(prs)} PR(s) via classic-PAT (ADR-0216)...\n")

    with classic_pat_session() as pat:
        for i, pr in enumerate(prs, 1):
            repo_name = pr.get("repository", {}).get("nameWithOwner", "unknown")
            pr_number = pr.get("number", 0)
            print(f"  [{i}/{len(prs)}] {repo_name} #{pr_number}")

            result = merge_pr(repo_name, pr_number, pat)
            results.append(result)

            status = "OK" if result.success else f"FAIL: {result.detail[:60]}"
            restored = (
                "" if result.protection_restored else " [PROTECTION NOT RESTORED!]"
            )
            print(f"    -> {status}{restored}")
            for err in result.errors:
                print(f"    !! {err}")

            if i < len(prs):
                time.sleep(1)

    # Write audit report
    report_path = write_report(results)

    successes = sum(1 for r in results if r.success)
    failures = sum(1 for r in results if not r.success)
    unrestored = sum(1 for r in results if not r.protection_restored)

    print("\n" + "=" * 60)
    print(f"Done. {successes} succeeded, {failures} failed.")
    if unrestored:
        print(f"  WARNING: {unrestored} repo(s) have enforce_admins NOT restored — see report!")
    print(f"Report saved to: {report_path}")
    print("=" * 60)

    if failures or unrestored:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
