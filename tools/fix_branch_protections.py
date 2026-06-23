#!/usr/bin/env python3
"""Fix branch protections on repos identified by the GitHub Protection Audit.

Sets branch protection on repos with NO protection (A01 FAIL) and disables
wikis on repos where it is an attack surface.  The protection payload matches
the existing fleet standard: block force-push, block deletion, enforce_admins,
require pr-sentinel / issue-reference status check.

Both operations are privileged writes that 403 on the fleet's fine-grained
PAT; they are sent via requests + the in-process classic-PAT pattern
(ADR-0216, #962).  Read-only calls (listing repos, reading current protection)
keep using the gh CLI with the fine-grained PAT.

Defaults to DRY-RUN (prints the would-be protection payload per repo);
pass --apply to PUT / PATCH for real (standard 0017).

OPERATOR-RUN ONLY (ADR-0216 §6.1): run this yourself in your own Git Bash.
NEVER let an agent invoke it via its Bash tool — the spawned Python process
would be the agent's child and its heap is theoretically readable while the
PAT is in scope.

Usage:
    poetry run python tools/fix_branch_protections.py            # dry-run
    poetry run python tools/fix_branch_protections.py --apply    # mutate
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pat_session import classic_pat_session  # noqa: E402

GITHUB_USER = "martymcenroe"
GH_API = "https://api.github.com"
HTTP_TIMEOUT_S = 30

# Repos with zero branch protection (A01 FAIL from audit-20260308-202639-classic.md)
REPOS_NO_PROTECTION = [
    "power-agent.github.io",
    "nec2017-analyzer",
    "github-readme-stats",
    "GentlePersuader",
    "CS512_link_predictor",
    "Hermes",
]

# Repos with wikis that have content (A10 FAIL from same audit)
REPOS_WIKI_CONTENT = [
    "unleashed",
    "RCA-PDF-extraction-pipeline",
    "HermesWiki",
    "gh-link-auditor",
    "dotfiles",
    "dont-stop-now",
    "collectibricks",
    "Hermes",
]


def _gh_headers(pat: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


@dataclass
class FixResult:
    repo: str
    action: str
    success: bool
    detail: str
    http_status: int | None = None


# ---------------------------------------------------------------------------
# Read-only helpers — gh CLI / fine-grained PAT is sufficient
# ---------------------------------------------------------------------------


def get_default_branch(repo: str) -> str:
    """Return the default branch name for a repo (read-only, gh CLI)."""
    full_repo = f"{GITHUB_USER}/{repo}"
    result = subprocess.run(
        ["gh", "api", f"/repos/{full_repo}", "--jq", ".default_branch"],
        capture_output=True, text=True, timeout=HTTP_TIMEOUT_S,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return "main"


def verify_branch_protection(repo: str) -> FixResult:
    """Read back protection and verify key fields (read-only, gh CLI)."""
    full_repo = f"{GITHUB_USER}/{repo}"
    branch = get_default_branch(repo)
    endpoint = f"/repos/{full_repo}/branches/{branch}/protection"

    result = subprocess.run(
        ["gh", "api", endpoint],
        capture_output=True, text=True, timeout=HTTP_TIMEOUT_S,
    )
    output = result.stdout or result.stderr or ""

    if result.returncode != 0:
        return FixResult(
            repo=full_repo,
            action="verify_branch_protection",
            success=False,
            detail=f"Could not read back protection: {output[:200]}",
        )

    try:
        data = json.loads(output)
        force_push = data.get("allow_force_pushes", {}).get("enabled", "?")
        deletion = data.get("allow_deletions", {}).get("enabled", "?")
        enforce = data.get("enforce_admins", {}).get("enabled", "?")
        checks = data.get("required_status_checks", {})
        contexts = checks.get("contexts", []) if checks else []

        detail = (
            f"force_push={force_push}, deletion={deletion}, "
            f"enforce_admins={enforce}, checks={contexts}"
        )
        all_good = (
            force_push is False
            and deletion is False
            and enforce is True
        )
        return FixResult(
            repo=full_repo,
            action="verify_branch_protection",
            success=all_good,
            detail=detail,
            http_status=200,
        )
    except json.JSONDecodeError:
        return FixResult(
            repo=full_repo,
            action="verify_branch_protection",
            success=False,
            detail=f"Invalid JSON response: {output[:200]}",
        )


# ---------------------------------------------------------------------------
# Privileged writes — classic PAT required; pat passed in explicitly
# ---------------------------------------------------------------------------


def set_branch_protection(repo: str, pat: str) -> FixResult:
    """PUT branch protection via the classic PAT.  Returns (FixResult)."""
    full_repo = f"{GITHUB_USER}/{repo}"
    branch = get_default_branch(repo)
    url = f"{GH_API}/repos/{full_repo}/branches/{branch}/protection"

    payload = {
        "required_pull_request_reviews": {
            "dismiss_stale_reviews": False,
            "require_code_owner_reviews": False,
            "required_approving_review_count": 0,
        },
        "enforce_admins": True,
        "restrictions": None,
        "required_status_checks": {
            "strict": True,
            "contexts": ["pr-sentinel / issue-reference"],
        },
        "allow_force_pushes": False,
        "allow_deletions": False,
    }

    resp = requests.put(url, headers=_gh_headers(pat), json=payload, timeout=HTTP_TIMEOUT_S)
    if resp.status_code == 200:
        return FixResult(
            repo=full_repo,
            action="set_branch_protection",
            success=True,
            detail=(
                f"Protection on '{branch}': force-push blocked, deletion blocked, "
                "enforce_admins=true, required check=pr-sentinel / issue-reference"
            ),
            http_status=200,
        )
    return FixResult(
        repo=full_repo,
        action="set_branch_protection",
        success=False,
        detail=resp.text[:200],
        http_status=resp.status_code,
    )


def disable_wiki(repo: str, pat: str) -> FixResult:
    """PATCH has_wiki=false via the classic PAT.  Returns (FixResult)."""
    full_repo = f"{GITHUB_USER}/{repo}"
    url = f"{GH_API}/repos/{full_repo}"

    resp = requests.patch(url, headers=_gh_headers(pat), json={"has_wiki": False}, timeout=HTTP_TIMEOUT_S)
    if resp.status_code == 200:
        return FixResult(
            repo=full_repo,
            action="disable_wiki",
            success=True,
            detail="Wiki disabled",
            http_status=200,
        )
    return FixResult(
        repo=full_repo,
        action="disable_wiki",
        success=False,
        detail=resp.text[:200],
        http_status=resp.status_code,
    )


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------


def write_report(results: list[FixResult], dry_run: bool) -> Path:
    """Write results to a markdown audit file."""
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%d-%H%M%S")
    output_dir = Path(__file__).parent.parent / "docs" / "audits" / "github-protection"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"fix-{timestamp}.md"

    successes = [r for r in results if r.success]
    failures = [r for r in results if not r.success]
    run_mode = "DRY-RUN" if dry_run else "APPLIED"

    lines = [
        "# Branch Protection Fix Report",
        "",
        f"**Date:** {now.isoformat()}",
        f"**Mode:** {run_mode}",
        "**Script:** `tools/fix_branch_protections.py`",
        "",
        "## Summary",
        "",
        "| Status | Count |",
        "|--------|-------|",
        f"| SUCCESS | {len(successes)} |",
        f"| FAILURE | {len(failures)} |",
        "",
        "## Results",
        "",
        "| Repo | Action | Status | Detail |",
        "|------|--------|--------|--------|",
    ]

    for r in results:
        status = "SUCCESS" if r.success else f"**FAILURE** (HTTP {r.http_status})"
        lines.append(f"| {r.repo} | {r.action} | {status} | {r.detail} |")

    if failures:
        lines.extend([
            "",
            "## Failures Requiring Manual Action",
            "",
        ])
        for r in failures:
            lines.append(f"- **{r.repo}** [{r.action}]: {r.detail}")

    lines.extend([
        "",
        "---",
        "",
        f"*Generated by tools/fix_branch_protections.py on {now.strftime('%Y-%m-%d')}*",
    ])

    output_file.write_text("\n".join(lines), encoding="utf-8")
    return output_file


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--apply", action="store_true",
        help="Actually apply branch-protection writes (default: dry-run preview).",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Branch Protection Fix Script")
    if not args.apply:
        print("  [DRY-RUN — pass --apply to mutate]")
    print("=" * 60)

    results: list[FixResult] = []

    # -----------------------------------------------------------------------
    # Phase 1: Branch protection on unprotected repos
    # -----------------------------------------------------------------------
    print(f"\nPhase 1: Branch protection on {len(REPOS_NO_PROTECTION)} repos...")

    if not args.apply:
        for repo in REPOS_NO_PROTECTION:
            branch = get_default_branch(repo)
            full_repo = f"{GITHUB_USER}/{repo}"
            print(f"\n  [{repo}]")
            print(f"    would PUT /repos/{full_repo}/branches/{branch}/protection")
            print(
                "    payload: enforce_admins=true, allow_force_pushes=false, "
                "allow_deletions=false, required_status_checks=[pr-sentinel / issue-reference], "
                "required_approving_review_count=0, restrictions=null"
            )
    else:
        with classic_pat_session() as pat:
            for repo in REPOS_NO_PROTECTION:
                print(f"\n  [{repo}]")
                result = set_branch_protection(repo, pat)
                results.append(result)
                status = "OK" if result.success else f"FAIL: {result.detail[:80]}"
                print(f"    set_branch_protection: {status}")

                if result.success:
                    verify = verify_branch_protection(repo)
                    results.append(verify)
                    vstatus = "OK" if verify.success else f"FAIL: {verify.detail[:80]}"
                    print(f"    verify: {vstatus}")

    # -----------------------------------------------------------------------
    # Phase 2: Disable wikis
    # -----------------------------------------------------------------------
    print(f"\nPhase 2: Wikis on {len(REPOS_WIKI_CONTENT)} repos...")

    if not args.apply:
        for repo in REPOS_WIKI_CONTENT:
            full_repo = f"{GITHUB_USER}/{repo}"
            print(f"  would PATCH /repos/{full_repo} {{has_wiki: false}}")
    else:
        with classic_pat_session() as pat:
            for repo in REPOS_WIKI_CONTENT:
                print(f"\n  [{repo}]")
                result = disable_wiki(repo, pat)
                results.append(result)
                status = "OK" if result.success else f"FAIL: {result.detail[:80]}"
                print(f"    disable_wiki: {status}")

    # -----------------------------------------------------------------------
    # Report
    # -----------------------------------------------------------------------
    if args.apply and results:
        report_path = write_report(results, dry_run=False)
        successes = sum(1 for r in results if r.success)
        failures = sum(1 for r in results if not r.success)
        print("\n" + "=" * 60)
        print(f"Done. {successes} succeeded, {failures} failed.")
        print(f"Report saved to: {report_path}")
        print("=" * 60)
        return 1 if failures else 0
    elif not args.apply:
        print("\nDry-run complete. Pass --apply to apply the above changes.")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
