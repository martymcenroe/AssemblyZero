#!/usr/bin/env python3
"""Fix branch protections on repos identified by the GitHub Protection Audit.

This script is designed to be run MANUALLY by the user with a classic token.
The agent writes it; the user reviews it, auths with a classic token, runs it,
then brings the agent back to analyze the results.

Usage:
    1. Review this script (it only calls `gh api` — no token handling)
    2. gh auth login → paste classic token (repo + admin:repo_hook + read:org)
    3. poetry run python tools/fix_branch_protections.py
    4. gh auth login → restore fine-grained PAT
    5. Delete classic token

What it does:
    - Sets branch protection on repos with NO protection (A01 FAIL)
    - Config matches existing protected repos: block force push, block deletion,
      enforce_admins, require pr-sentinel status check
    - Disables wiki on repos where it's an attack surface
    - Saves results to docs/audits/github-protection/fix-TIMESTAMP.md

What it does NOT do:
    - Read, store, or transmit any token
    - Modify any code or file content
    - Push to any repo
    - Access any secrets
"""

import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

GITHUB_USER = "martymcenroe"

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


@dataclass
class FixResult:
    repo: str
    action: str
    success: bool
    detail: str
    http_status: int | None = None


def gh_api(method: str, endpoint: str, *args: str) -> tuple[int, str]:
    """Call gh api and return (returncode, combined output)."""
    cmd = ["gh", "api", "-X", method, endpoint, *args]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30
        )
        output = result.stdout or result.stderr or ""
        # Try to extract HTTP status from error message
        http_status = None
        if "HTTP " in output:
            for part in output.split("HTTP "):
                if len(part) >= 3 and part[:3].isdigit():
                    http_status = int(part[:3])
                    break
        return result.returncode, output.strip(), http_status
    except subprocess.TimeoutExpired:
        return 1, "TIMEOUT", None
    except FileNotFoundError:
        return 1, "gh CLI not found", None


def detect_token_type() -> str:
    """Detect whether current gh auth is classic or fine-grained."""
    rc, output, _ = gh_api("GET", "/user")
    if rc != 0:
        return "unknown (auth failed)"
    # Classic tokens return X-OAuth-Scopes header; fine-grained do not
    rc2, output2, _ = gh_api("GET", "/rate_limit")
    # Fine-grained PATs get 403 on admin endpoints classic can access
    rc3, _, _ = gh_api(
        "GET", f"/repos/{GITHUB_USER}/AssemblyZero/branches/main/protection"
    )
    if rc3 == 0:
        return "classic"
    return "fine-grained (cannot read branch protection — this script needs a classic token)"


def get_default_branch(repo: str) -> str:
    """Get the default branch name for a repo."""
    full_repo = f"{GITHUB_USER}/{repo}"
    rc, output, _ = gh_api("GET", f"/repos/{full_repo}", "--jq", ".default_branch")
    if rc == 0 and output.strip():
        return output.strip()
    return "main"  # fallback


def set_branch_protection(repo: str) -> FixResult:
    """Set branch protection matching the standard config."""
    full_repo = f"{GITHUB_USER}/{repo}"
    branch = get_default_branch(repo)
    endpoint = f"/repos/{full_repo}/branches/{branch}/protection"

    rc, output, http_status = gh_api(
        "PUT", endpoint,
        "-F", "required_pull_request_reviews[dismiss_stale_reviews]=false",
        "-F", "required_pull_request_reviews[require_code_owner_reviews]=false",
        "-F", "required_pull_request_reviews[required_approving_review_count]=0",
        "-F", "enforce_admins=true",
        "-F", "restrictions=null",
        "-F", "required_status_checks[strict]=true",
        "-f", "required_status_checks[contexts][]=pr-sentinel / issue-reference",
        "-F", "allow_force_pushes=false",
        "-F", "allow_deletions=false",
    )

    if rc == 0:
        return FixResult(
            repo=full_repo,
            action="set_branch_protection",
            success=True,
            detail=f"Protection on '{branch}': force-push blocked, deletion blocked, "
                   "enforce_admins=true, required check=pr-sentinel / issue-reference",
            http_status=200,
        )
    else:
        return FixResult(
            repo=full_repo,
            action="set_branch_protection",
            success=False,
            detail=output[:200],
            http_status=http_status,
        )


def verify_branch_protection(repo: str) -> FixResult:
    """Verify branch protection was actually set by reading it back."""
    full_repo = f"{GITHUB_USER}/{repo}"
    branch = get_default_branch(repo)
    endpoint = f"/repos/{full_repo}/branches/{branch}/protection"

    rc, output, http_status = gh_api("GET", endpoint)
    if rc != 0:
        return FixResult(
            repo=full_repo,
            action="verify_branch_protection",
            success=False,
            detail=f"Could not read back protection: {output[:200]}",
            http_status=http_status,
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
            http_status=http_status,
        )


def disable_wiki(repo: str) -> FixResult:
    """Disable wiki on a repo."""
    full_repo = f"{GITHUB_USER}/{repo}"
    endpoint = f"/repos/{full_repo}"

    rc, output, http_status = gh_api(
        "PATCH", endpoint,
        "-F", "has_wiki=false",
    )

    if rc == 0:
        return FixResult(
            repo=full_repo,
            action="disable_wiki",
            success=True,
            detail="Wiki disabled",
            http_status=200,
        )
    else:
        return FixResult(
            repo=full_repo,
            action="disable_wiki",
            success=False,
            detail=output[:200],
            http_status=http_status,
        )


def write_report(results: list[FixResult], token_type: str) -> Path:
    """Write results to a markdown audit file."""
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%d-%H%M%S")
    output_dir = Path(__file__).parent.parent / "docs" / "audits" / "github-protection"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"fix-{timestamp}.md"

    successes = [r for r in results if r.success]
    failures = [r for r in results if not r.success]

    lines = [
        "# Branch Protection Fix Report",
        "",
        f"**Date:** {now.isoformat()}",
        f"**Token type:** {token_type}",
        f"**Script:** `tools/fix_branch_protections.py`",
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


def main():
    print("=" * 60)
    print("Branch Protection Fix Script")
    print("=" * 60)

    # Detect token type
    print("\nDetecting token type...")
    token_type = detect_token_type()
    print(f"  Token type: {token_type}")

    if "fine-grained" in token_type or "unknown" in token_type:
        print("\n  WARNING: This script requires a classic token with repo scope.")
        print("  Run: gh auth login → paste classic token")
        print("  Then re-run this script.")
        sys.exit(1)

    results: list[FixResult] = []

    # Phase 1: Set branch protection on unprotected repos
    print(f"\nPhase 1: Setting branch protection on {len(REPOS_NO_PROTECTION)} repos...")
    for repo in REPOS_NO_PROTECTION:
        print(f"\n  [{repo}]")
        result = set_branch_protection(repo)
        results.append(result)
        status = "OK" if result.success else f"FAIL: {result.detail[:80]}"
        print(f"    set_branch_protection: {status}")

        if result.success:
            verify = verify_branch_protection(repo)
            results.append(verify)
            status = "OK" if verify.success else f"FAIL: {verify.detail[:80]}"
            print(f"    verify: {status}")

    # Phase 2: Disable wikis on repos with content
    print(f"\nPhase 2: Disabling wikis on {len(REPOS_WIKI_CONTENT)} repos...")
    for repo in REPOS_WIKI_CONTENT:
        print(f"\n  [{repo}]")
        result = disable_wiki(repo)
        results.append(result)
        status = "OK" if result.success else f"FAIL: {result.detail[:80]}"
        print(f"    disable_wiki: {status}")

    # Write report
    report_path = write_report(results, token_type)

    # Summary
    successes = sum(1 for r in results if r.success)
    failures = sum(1 for r in results if not r.success)
    print("\n" + "=" * 60)
    print(f"Done. {successes} succeeded, {failures} failed.")
    print(f"Report saved to: {report_path}")
    print("=" * 60)

    if failures:
        sys.exit(2)


if __name__ == "__main__":
    main()
