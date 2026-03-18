#!/usr/bin/env python3
"""Deploy auto-reviewer fleet-wide and enable required PR reviews.

ONE-TIME fleet deployment. After this, agents cannot self-merge.

Requires classic PAT with: repo + workflow scopes.

For each repo:
  1. Deploy auto-reviewer.yml caller workflow via Contents API
  2. Enable required pull request reviews (1 approval) in branch protection

Usage:
    gh auth login -h github.com -p https   # classic PAT (repo + workflow)
    poetry run python tools/deploy_auto_reviewer_fleet.py
    gh auth login -h github.com -p https   # back to fine-grained

Issue: #736 | Related: #732
"""

import base64
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

GITHUB_USER = "martymcenroe"
WORKFLOW_PATH = ".github/workflows/auto-reviewer.yml"

# Caller workflow deployed to every repo (except AssemblyZero which has the reusable)
CALLER_WORKFLOW = """\
name: Auto Review

# Caller workflow: invokes the reusable auto-reviewer from AssemblyZero.
# Deployed by tools/deploy_auto_reviewer_fleet.py (#736)

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


@dataclass
class RepoResult:
    repo: str
    default_branch: str
    workflow_ok: bool
    workflow_detail: str
    reviews_ok: bool
    reviews_detail: str


def run_gh(*args: str, timeout: int = 30, stdin: str = None) -> tuple[int, str]:
    """Run a gh CLI command and return (returncode, output)."""
    cmd = ["gh", *args]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            input=stdin,
        )
        output = (result.stdout or "") + (result.stderr or "")
        return result.returncode, output.strip()
    except subprocess.TimeoutExpired:
        return 1, "TIMEOUT"
    except FileNotFoundError:
        return 1, "gh CLI not found"


def detect_token_type() -> str:
    rc, output = run_gh("auth", "status")
    if "ghp_" in (output or ""):
        return "classic"
    if "github_pat_" in (output or ""):
        return "fine-grained"
    return "unknown"


def get_all_repos() -> list[dict]:
    """Get all non-archived repos with their default branch."""
    rc, output = run_gh(
        "repo", "list", GITHUB_USER,
        "--limit", "200",
        "--json", "nameWithOwner,isArchived,isFork,defaultBranchRef",
        "--no-archived",
        timeout=60,
    )
    if rc != 0:
        print(f"  ERROR listing repos: {output[:200]}")
        return []
    return json.loads(output)


def deploy_workflow(repo: str, branch: str) -> tuple[bool, str]:
    """Deploy caller workflow to repo via Contents API.

    Temporarily disables enforce_admins to bypass branch protection,
    same pattern as merge_sentinel_permissions_prs.py.
    """
    content_b64 = base64.b64encode(CALLER_WORKFLOW.encode()).decode()

    # Check if file exists (need sha to update)
    rc, output = run_gh(
        "api", f"repos/{repo}/contents/{WORKFLOW_PATH}",
        "--jq", ".sha",
        timeout=30,
    )

    body = {
        "message": "ci: deploy auto-reviewer caller workflow (#736)",
        "content": content_b64,
    }

    if rc == 0 and output.strip():
        body["sha"] = output.strip().strip('"')

    # Disable enforce_admins to bypass branch protection
    run_gh(
        "api", f"repos/{repo}/branches/{branch}/protection/enforce_admins",
        "-X", "DELETE",
        timeout=15,
    )

    # Create/update file
    rc, output = run_gh(
        "api", f"repos/{repo}/contents/{WORKFLOW_PATH}",
        "-X", "PUT",
        "--input", "-",
        timeout=30,
        stdin=json.dumps(body),
    )

    # ALWAYS re-enable enforce_admins
    run_gh(
        "api", f"repos/{repo}/branches/{branch}/protection/enforce_admins",
        "-X", "POST",
        timeout=15,
    )

    if rc == 0:
        return True, "OK"
    return False, output[:200]


def enable_required_reviews(repo: str, branch: str) -> tuple[bool, str]:
    """Enable required PR reviews in branch protection, preserving existing settings."""
    # Get current protection
    rc, output = run_gh(
        "api", f"repos/{repo}/branches/{branch}/protection",
        timeout=15,
    )

    if rc != 0:
        # No branch protection — create from scratch
        body = {
            "required_status_checks": {
                "strict": False,
                "contexts": ["pr-sentinel / issue-reference"],
            },
            "enforce_admins": True,
            "required_pull_request_reviews": {
                "required_approving_review_count": 1,
            },
            "restrictions": None,
        }
        rc2, out2 = run_gh(
            "api", f"repos/{repo}/branches/{branch}/protection",
            "-X", "PUT",
            "--input", "-",
            timeout=15,
            stdin=json.dumps(body),
        )
        if rc2 == 0:
            return True, "Created new protection"
        return False, f"No existing protection, create failed: {out2[:150]}"

    # Parse current protection
    try:
        current = json.loads(output)
    except json.JSONDecodeError:
        return False, "Failed to parse current protection"

    # Preserve required_status_checks
    sc = current.get("required_status_checks")
    if sc:
        sc_body = {
            "strict": sc.get("strict", False),
            "contexts": sc.get("contexts", []),
        }
    else:
        sc_body = None

    # Preserve enforce_admins
    ea = current.get("enforce_admins", {})
    ea_val = ea.get("enabled", True) if isinstance(ea, dict) else bool(ea)

    # Preserve restrictions
    restrictions = current.get("restrictions")
    if restrictions:
        restrictions_body = {
            "users": [u["login"] for u in restrictions.get("users", [])],
            "teams": [t["slug"] for t in restrictions.get("teams", [])],
            "apps": [a["slug"] for a in restrictions.get("apps", [])],
        }
    else:
        restrictions_body = None

    # PUT with reviews added
    body = {
        "required_status_checks": sc_body,
        "enforce_admins": ea_val,
        "required_pull_request_reviews": {
            "required_approving_review_count": 1,
        },
        "restrictions": restrictions_body,
    }

    rc, output = run_gh(
        "api", f"repos/{repo}/branches/{branch}/protection",
        "-X", "PUT",
        "--input", "-",
        timeout=15,
        stdin=json.dumps(body),
    )

    if rc == 0:
        return True, "OK"
    return False, output[:200]


def write_report(results: list[RepoResult]) -> Path:
    now = datetime.now(timezone.utc)
    output_dir = Path(__file__).parent.parent / "docs" / "audits" / "github-protection"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"deploy-auto-reviewer-{now.strftime('%Y%m%d-%H%M%S')}.md"

    wf_ok = sum(1 for r in results if r.workflow_ok)
    rv_ok = sum(1 for r in results if r.reviews_ok)

    lines = [
        "# Auto-Reviewer Fleet Deployment Report",
        "",
        f"**Date:** {now.isoformat()}",
        f"**Script:** `tools/deploy_auto_reviewer_fleet.py`",
        f"**Method:** Contents API (workflow) + Branch Protection API (reviews)",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "|--------|-------|",
        f"| Repos processed | {len(results)} |",
        f"| Workflows deployed | {wf_ok} |",
        f"| Required reviews enabled | {rv_ok} |",
        "",
        "## Results",
        "",
        "| Repo | Branch | Workflow | Reviews | Detail |",
        "|------|--------|----------|---------|--------|",
    ]

    for r in sorted(results, key=lambda x: x.repo):
        wf = "OK" if r.workflow_ok else "**FAIL**"
        rv = "OK" if r.reviews_ok else "**FAIL**"
        detail = f"{r.workflow_detail} / {r.reviews_detail}".replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {r.repo} | {r.default_branch} | {wf} | {rv} | {detail[:80]} |")

    wf_fail = [r for r in results if not r.workflow_ok]
    rv_fail = [r for r in results if not r.reviews_ok]

    if wf_fail:
        lines.extend(["", "## Workflow Deployment Failures", ""])
        for r in wf_fail:
            lines.append(f"- **{r.repo}**: {r.workflow_detail}")

    if rv_fail:
        lines.extend(["", "## Required Reviews Failures", ""])
        for r in rv_fail:
            lines.append(f"- **{r.repo}**: {r.reviews_detail}")

    lines.extend(["", "---", "",
        f"*Generated by tools/deploy_auto_reviewer_fleet.py on {now.strftime('%Y-%m-%d')}*"])

    output_file.write_text("\n".join(lines), encoding="utf-8")
    return output_file


def main():
    print("=" * 60)
    print("Deploy Auto-Reviewer Fleet-Wide")
    print("After this, agents cannot self-merge PRs.")
    print("=" * 60)

    token_type = detect_token_type()
    print(f"\nToken type: {token_type}")

    if token_type == "fine-grained":
        print("\n  ERROR: Requires classic PAT with repo + workflow scopes.")
        print("  Run: gh auth login -h github.com -p https")
        sys.exit(1)

    if token_type == "unknown":
        print("\n  WARNING: Could not detect token type. Proceeding...")

    print("\nFetching repos...")
    repos = get_all_repos()
    print(f"  Found {len(repos)} repos\n")

    if not repos:
        sys.exit(1)

    # AssemblyZero has the reusable workflow at this path — don't overwrite it
    skip_workflow = {"martymcenroe/AssemblyZero"}
    # Repos that can never be deployed to (ruleset blocks Contents API, no workaround)
    skip_entirely = {"martymcenroe/patent-general"}

    results: list[RepoResult] = []

    for i, repo_info in enumerate(repos, 1):
        name = repo_info["nameWithOwner"]
        branch_ref = repo_info.get("defaultBranchRef", {})
        branch = branch_ref.get("name", "main") if isinstance(branch_ref, dict) else "main"
        is_fork = repo_info.get("isFork", False)

        print(f"  [{i}/{len(repos)}] {name} ({branch})")

        # Skip forks (no branch protection on free plan, not our code)
        if is_fork:
            print(f"    Skipped — fork")
            results.append(RepoResult(
                repo=name, default_branch=branch,
                workflow_ok=True, workflow_detail="Skipped (fork)",
                reviews_ok=True, reviews_detail="Skipped (fork)",
            ))
            continue

        # Skip repos with rulesets that block Contents API
        if name in skip_entirely:
            print(f"    Skipped — ruleset blocks deployment")
            results.append(RepoResult(
                repo=name, default_branch=branch,
                workflow_ok=True, workflow_detail="Skipped (ruleset)",
                reviews_ok=True, reviews_detail="Skipped (ruleset)",
            ))
            continue

        # Deploy workflow
        if name in skip_workflow:
            wf_ok, wf_detail = True, "Skipped (has reusable workflow)"
        else:
            wf_ok, wf_detail = deploy_workflow(name, branch)
        print(f"    Workflow: {'OK' if wf_ok else 'FAIL'} — {wf_detail[:60]}")

        # Enable required reviews
        rv_ok, rv_detail = enable_required_reviews(name, branch)
        print(f"    Reviews:  {'OK' if rv_ok else 'FAIL'} — {rv_detail[:60]}")

        results.append(RepoResult(
            repo=name,
            default_branch=branch,
            workflow_ok=wf_ok,
            workflow_detail=wf_detail,
            reviews_ok=rv_ok,
            reviews_detail=rv_detail,
        ))

        if i < len(repos):
            time.sleep(0.5)

    # Write report
    report_path = write_report(results)

    # Summary
    wf_ok = sum(1 for r in results if r.workflow_ok)
    rv_ok = sum(1 for r in results if r.reviews_ok)

    print(f"\n{'=' * 60}")
    print(f"Workflows: {wf_ok}/{len(results)} deployed")
    print(f"Reviews:   {rv_ok}/{len(results)} enabled")

    wf_fail = [r for r in results if not r.workflow_ok]
    rv_fail = [r for r in results if not r.reviews_ok]

    if wf_fail:
        print(f"\nWorkflow failures ({len(wf_fail)}):")
        for r in wf_fail:
            print(f"  - {r.repo}: {r.workflow_detail[:80]}")

    if rv_fail:
        print(f"\nReview failures ({len(rv_fail)}):")
        for r in rv_fail:
            print(f"  - {r.repo}: {r.reviews_detail[:80]}")

    print(f"\nReport: {report_path}")
    print("=" * 60)

    if wf_fail or rv_fail:
        sys.exit(2)


if __name__ == "__main__":
    main()
