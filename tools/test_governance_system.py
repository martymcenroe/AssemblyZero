#!/usr/bin/env python3
"""PR Governance System Test Suite.

Two modes:
  --mode local    Create real test PRs to verify happy/failure paths.
                  Works with fine-grained PAT. Targets a single repo.
  --mode audit    Fleet-wide branch protection comparison against canonical config.
                  Requires classic PAT with repo + admin:repo_hook scopes.

Usage:
    # Local tests on a specific repo
    poetry run python tools/test_governance_system.py --mode local --repo martymcenroe/Sextant

    # Local tests on AssemblyZero (default)
    poetry run python tools/test_governance_system.py --mode local

    # Fleet-wide audit (requires classic PAT)
    gh auth login -h github.com -p https   # classic PAT
    poetry run python tools/test_governance_system.py --mode audit
    gh auth login -h github.com -p https   # back to fine-grained

    # Dry run (show what would happen, don't create PRs)
    poetry run python tools/test_governance_system.py --mode local --dry-run

Issue: #887 | Related: #886
Standard: 0016-pr-sentinel-system-architecture.md
"""

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

GITHUB_USER = "martymcenroe"
DEFAULT_REPO = f"{GITHUB_USER}/AssemblyZero"
SENTINEL_HEALTH_URL = "https://pr-sentinel.mcwizard1.workers.dev/health"

# Canonical branch protection settings (from standard 0016)
CANONICAL = {
    "required_approving_review_count": 1,
    "enforce_admins": True,
    "allow_force_pushes": False,
    "allow_deletions": False,
    "strict": False,
    # Context: either "pr-sentinel / issue-reference" (fleet) or
    # "issue-reference" with app_id filter (AZ/Sextant). Both valid.
    "context_must_contain": "issue-reference",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@dataclass
class TestResult:
    test_id: str
    name: str
    expected: str
    actual: str
    passed: bool
    detail: str = ""
    duration_s: float = 0.0


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


def run_curl(url: str, timeout: int = 10) -> tuple[int, str]:
    """Run curl and return (status_code, body)."""
    cmd = ["curl", "-s", "-o", "-", "-w", "\n%{http_code}", url]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        lines = result.stdout.strip().rsplit("\n", 1)
        if len(lines) == 2:
            body, status = lines
            return int(status), body
        return 0, result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return 0, "TIMEOUT or curl not found"


def detect_token_type() -> str:
    """Detect whether current gh auth is classic or fine-grained."""
    rc, output = run_gh("auth", "status")
    if "ghp_" in (output or ""):
        return "classic"
    if "github_pat_" in (output or ""):
        return "fine-grained"
    return "unknown"


def get_all_repos() -> list[str]:
    """Get all non-archived, non-fork repos."""
    rc, output = run_gh(
        "repo", "list", GITHUB_USER,
        "--limit", "200",
        "--json", "nameWithOwner,isArchived,isFork",
        "--no-archived",
        timeout=60,
    )
    if rc != 0:
        print(f"  ERROR listing repos: {output[:200]}")
        return []
    repos = json.loads(output)
    return [r["nameWithOwner"] for r in repos if not r.get("isFork", False)]


# ---------------------------------------------------------------------------
# Local mode: PR-based integration tests
# ---------------------------------------------------------------------------

def create_test_issue(repo: str, title: str) -> int | None:
    """Create a test issue and return its number."""
    rc, output = run_gh(
        "issue", "create",
        "--repo", repo,
        "--title", title,
        "--body", "Auto-created by test_governance_system.py. Safe to close.",
    )
    if rc != 0:
        print(f"    ERROR creating issue: {output[:200]}")
        return None
    # Extract issue number from URL
    # Output is like: https://github.com/owner/repo/issues/123
    parts = output.strip().split("/")
    try:
        return int(parts[-1])
    except (ValueError, IndexError):
        print(f"    ERROR parsing issue number from: {output}")
        return None


def close_test_issue(repo: str, number: int):
    """Close a test issue."""
    run_gh("issue", "close", str(number), "--repo", repo)


def create_test_branch(repo: str, branch_name: str) -> bool:
    """Create a branch with a trivial commit via the Contents API."""
    # Get the SHA of main
    rc, output = run_gh(
        "api", f"repos/{repo}/git/ref/heads/main",
        "--jq", ".object.sha",
    )
    if rc != 0:
        print(f"    ERROR getting main SHA: {output[:200]}")
        return False
    main_sha = output.strip().strip('"')

    # Create the branch ref
    body = json.dumps({
        "ref": f"refs/heads/{branch_name}",
        "sha": main_sha,
    })
    rc, output = run_gh(
        "api", f"repos/{repo}/git/refs",
        "-X", "POST", "--input", "-",
        stdin=body,
    )
    if rc != 0:
        print(f"    ERROR creating branch: {output[:200]}")
        return False

    # Create a trivial file on the branch
    import base64
    content = base64.b64encode(
        f"# Governance test\nCreated at {datetime.now(timezone.utc).isoformat()}\n".encode()
    ).decode()
    file_body = json.dumps({
        "message": "test: governance system verification",
        "content": content,
        "branch": branch_name,
    })
    rc, output = run_gh(
        "api", f"repos/{repo}/contents/test-governance-{branch_name}.md",
        "-X", "PUT", "--input", "-",
        stdin=file_body,
    )
    if rc != 0:
        print(f"    ERROR creating test file: {output[:200]}")
        return False

    return True


def create_test_pr(repo: str, branch: str, title: str, body: str) -> int | None:
    """Create a PR and return its number."""
    pr_body = json.dumps({
        "title": title,
        "head": branch,
        "base": "main",
        "body": body,
    })
    rc, output = run_gh(
        "api", f"repos/{repo}/pulls",
        "-X", "POST", "--input", "-",
        "--jq", ".number",
        stdin=pr_body,
    )
    if rc != 0:
        print(f"    ERROR creating PR: {output[:200]}")
        return None
    try:
        return int(output.strip())
    except ValueError:
        print(f"    ERROR parsing PR number from: {output}")
        return None


def wait_for_checks(repo: str, pr_number: int, max_wait: int = 120) -> dict:
    """Wait for check runs to appear and complete. Returns check state."""
    # Get head SHA
    rc, output = run_gh(
        "api", f"repos/{repo}/pulls/{pr_number}",
        "--jq", ".head.sha",
    )
    if rc != 0:
        return {"error": f"Cannot get PR SHA: {output[:200]}"}
    head_sha = output.strip().strip('"')

    start = time.time()
    while time.time() - start < max_wait:
        # Try check runs first (works if token has checks:read)
        rc, output = run_gh(
            "api", f"repos/{repo}/commits/{head_sha}/check-runs",
            "--jq", '.check_runs[] | {name, conclusion, status}',
        )
        if rc == 0 and output.strip():
            checks = []
            for line in output.strip().split("\n"):
                try:
                    checks.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

            sentinel_checks = [
                c for c in checks
                if "issue-reference" in (c.get("name") or "")
            ]
            if sentinel_checks:
                all_complete = all(
                    c.get("status") == "completed" for c in sentinel_checks
                )
                if all_complete:
                    return {
                        "checks": sentinel_checks,
                        "elapsed": time.time() - start,
                    }

        # Fallback: check mergeable_state
        rc, output = run_gh(
            "api", f"repos/{repo}/pulls/{pr_number}",
            "--jq", ".mergeable_state",
        )
        state = output.strip().strip('"') if rc == 0 else "unknown"
        if state in ("clean", "blocked", "unstable"):
            return {
                "mergeable_state": state,
                "elapsed": time.time() - start,
            }

        time.sleep(10)

    return {"timeout": True, "elapsed": max_wait}


def cleanup_test_pr(repo: str, pr_number: int, branch: str):
    """Close PR, delete branch, delete test file."""
    run_gh("api", f"repos/{repo}/pulls/{pr_number}",
           "-X", "PATCH", "--input", "-",
           stdin=json.dumps({"state": "closed"}))
    run_gh("api", f"repos/{repo}/git/refs/heads/{branch}", "-X", "DELETE")


def test_happy_path(repo: str) -> TestResult:
    """T01: PR with valid Closes #N should pass checks and reach clean state."""
    t0 = time.time()
    branch = f"test-gov-t01-{int(time.time())}"

    # Create issue
    issue_num = create_test_issue(repo, "test: governance T01 happy path")
    if not issue_num:
        return TestResult("T01", "Happy path (Closes #N)", "pass",
                          "Could not create issue", False)

    # Create branch + PR
    if not create_test_branch(repo, branch):
        close_test_issue(repo, issue_num)
        return TestResult("T01", "Happy path (Closes #N)", "pass",
                          "Could not create branch", False)

    pr_num = create_test_pr(
        repo, branch,
        f"test: governance T01 Closes #{issue_num}",
        f"## Summary\nGovernance test: happy path\n\nCloses #{issue_num}",
    )
    if not pr_num:
        close_test_issue(repo, issue_num)
        return TestResult("T01", "Happy path (Closes #N)", "pass",
                          "Could not create PR", False)

    print(f"    PR #{pr_num} created, waiting for checks...")

    # Wait for checks
    result = wait_for_checks(repo, pr_num, max_wait=180)

    # Evaluate
    passed = False
    actual = ""
    if "timeout" in result:
        actual = "Timed out waiting for checks (180s)"
    elif "error" in result:
        actual = result["error"]
    elif "checks" in result:
        conclusions = [c.get("conclusion") for c in result["checks"]]
        passed = "success" in conclusions
        actual = f"Check conclusions: {conclusions} ({result['elapsed']:.0f}s)"
    elif "mergeable_state" in result:
        passed = result["mergeable_state"] == "clean"
        actual = f"mergeable_state: {result['mergeable_state']} ({result['elapsed']:.0f}s)"

    # Cleanup
    cleanup_test_pr(repo, pr_num, branch)
    close_test_issue(repo, issue_num)

    return TestResult("T01", "Happy path (Closes #N)",
                      "Check passes, mergeable_state clean",
                      actual, passed, duration_s=time.time() - t0)


def test_no_issue_ref(repo: str) -> TestResult:
    """T02: PR with no issue reference should be blocked."""
    t0 = time.time()
    branch = f"test-gov-t02-{int(time.time())}"

    if not create_test_branch(repo, branch):
        return TestResult("T02", "No issue reference", "blocked",
                          "Could not create branch", False)

    pr_num = create_test_pr(
        repo, branch,
        "test: governance T02 no ref",
        "## Summary\nThis PR intentionally has no issue reference.",
    )
    if not pr_num:
        return TestResult("T02", "No issue reference", "blocked",
                          "Could not create PR", False)

    print(f"    PR #{pr_num} created, waiting for checks...")
    result = wait_for_checks(repo, pr_num, max_wait=120)

    passed = False
    actual = ""
    if "timeout" in result:
        actual = "Timed out — checks may not have run"
    elif "checks" in result:
        conclusions = [c.get("conclusion") for c in result["checks"]]
        passed = all(c != "success" for c in conclusions)
        actual = f"Check conclusions: {conclusions} ({result['elapsed']:.0f}s)"
    elif "mergeable_state" in result:
        passed = result["mergeable_state"] == "blocked"
        actual = f"mergeable_state: {result['mergeable_state']} ({result['elapsed']:.0f}s)"

    cleanup_test_pr(repo, pr_num, branch)

    return TestResult("T02", "No issue reference",
                      "Check fails, mergeable_state blocked",
                      actual, passed, duration_s=time.time() - t0)


def test_closed_issue_ref(repo: str) -> TestResult:
    """T03: PR referencing a closed issue should be blocked by the Worker."""
    t0 = time.time()
    branch = f"test-gov-t03-{int(time.time())}"

    # Create and immediately close an issue
    issue_num = create_test_issue(repo, "test: governance T03 closed issue")
    if not issue_num:
        return TestResult("T03", "Closed issue reference", "blocked",
                          "Could not create issue", False)
    close_test_issue(repo, issue_num)
    time.sleep(2)  # let GitHub propagate the close

    if not create_test_branch(repo, branch):
        return TestResult("T03", "Closed issue reference", "blocked",
                          "Could not create branch", False)

    pr_num = create_test_pr(
        repo, branch,
        f"test: governance T03 Closes #{issue_num}",
        f"## Summary\nReferences a closed issue.\n\nCloses #{issue_num}",
    )
    if not pr_num:
        return TestResult("T03", "Closed issue reference", "blocked",
                          "Could not create PR", False)

    print(f"    PR #{pr_num} created (refs closed #{issue_num}), waiting...")
    result = wait_for_checks(repo, pr_num, max_wait=120)

    passed = False
    actual = ""
    if "timeout" in result:
        actual = "Timed out — Worker may not have processed"
    elif "checks" in result:
        conclusions = [c.get("conclusion") for c in result["checks"]]
        # Worker should fail (action_required), Actions may pass (regex only)
        worker_failed = "action_required" in conclusions
        passed = worker_failed
        actual = f"Check conclusions: {conclusions} ({result['elapsed']:.0f}s)"
    elif "mergeable_state" in result:
        passed = result["mergeable_state"] == "blocked"
        actual = f"mergeable_state: {result['mergeable_state']} ({result['elapsed']:.0f}s)"

    cleanup_test_pr(repo, pr_num, branch)

    return TestResult("T03", "Closed issue reference",
                      "Worker check fails (action_required)",
                      actual, passed, duration_s=time.time() - t0)


def test_naked_hash(repo: str) -> TestResult:
    """T04: PR with naked (#N) instead of Closes #N should be blocked."""
    t0 = time.time()
    branch = f"test-gov-t04-{int(time.time())}"

    issue_num = create_test_issue(repo, "test: governance T04 naked hash")
    if not issue_num:
        return TestResult("T04", "Naked #N format", "blocked",
                          "Could not create issue", False)

    if not create_test_branch(repo, branch):
        close_test_issue(repo, issue_num)
        return TestResult("T04", "Naked #N format", "blocked",
                          "Could not create branch", False)

    pr_num = create_test_pr(
        repo, branch,
        f"test: governance T04 (#{issue_num})",
        f"## Summary\nUses naked hash format.\n\n(#{issue_num})",
    )
    if not pr_num:
        close_test_issue(repo, issue_num)
        return TestResult("T04", "Naked #N format", "blocked",
                          "Could not create PR", False)

    print(f"    PR #{pr_num} created (naked #{issue_num}), waiting...")
    result = wait_for_checks(repo, pr_num, max_wait=120)

    passed = False
    actual = ""
    if "timeout" in result:
        actual = "Timed out"
    elif "checks" in result:
        conclusions = [c.get("conclusion") for c in result["checks"]]
        passed = all(c != "success" for c in conclusions)
        actual = f"Check conclusions: {conclusions} ({result['elapsed']:.0f}s)"
    elif "mergeable_state" in result:
        passed = result["mergeable_state"] == "blocked"
        actual = f"mergeable_state: {result['mergeable_state']} ({result['elapsed']:.0f}s)"

    cleanup_test_pr(repo, pr_num, branch)
    close_test_issue(repo, issue_num)

    return TestResult("T04", "Naked #N format",
                      "Check fails, mergeable_state blocked",
                      actual, passed, duration_s=time.time() - t0)


def test_empty_body(repo: str) -> TestResult:
    """T05: PR with empty body should be blocked."""
    t0 = time.time()
    branch = f"test-gov-t05-{int(time.time())}"

    if not create_test_branch(repo, branch):
        return TestResult("T05", "Empty PR body", "blocked",
                          "Could not create branch", False)

    pr_num = create_test_pr(
        repo, branch,
        "test: governance T05 empty body",
        "",
    )
    if not pr_num:
        return TestResult("T05", "Empty PR body", "blocked",
                          "Could not create PR", False)

    print(f"    PR #{pr_num} created (empty body), waiting...")
    result = wait_for_checks(repo, pr_num, max_wait=120)

    passed = False
    actual = ""
    if "timeout" in result:
        actual = "Timed out"
    elif "checks" in result:
        conclusions = [c.get("conclusion") for c in result["checks"]]
        passed = all(c != "success" for c in conclusions)
        actual = f"Check conclusions: {conclusions} ({result['elapsed']:.0f}s)"
    elif "mergeable_state" in result:
        passed = result["mergeable_state"] == "blocked"
        actual = f"mergeable_state: {result['mergeable_state']} ({result['elapsed']:.0f}s)"

    cleanup_test_pr(repo, pr_num, branch)

    return TestResult("T05", "Empty PR body",
                      "Check fails, mergeable_state blocked",
                      actual, passed, duration_s=time.time() - t0)


def test_no_issue_exemption(repo: str) -> TestResult:
    """T06: PR with No-Issue: exemption should pass."""
    t0 = time.time()
    branch = f"test-gov-t06-{int(time.time())}"

    if not create_test_branch(repo, branch):
        return TestResult("T06", "No-Issue exemption", "pass",
                          "Could not create branch", False)

    pr_num = create_test_pr(
        repo, branch,
        "test: governance T06 no-issue exemption",
        "## Summary\nGovernance test.\n\nNo-Issue: automated governance test",
    )
    if not pr_num:
        return TestResult("T06", "No-Issue exemption", "pass",
                          "Could not create PR", False)

    print(f"    PR #{pr_num} created (No-Issue exemption), waiting...")
    result = wait_for_checks(repo, pr_num, max_wait=180)

    passed = False
    actual = ""
    if "timeout" in result:
        actual = "Timed out waiting for checks"
    elif "checks" in result:
        conclusions = [c.get("conclusion") for c in result["checks"]]
        passed = "success" in conclusions
        actual = f"Check conclusions: {conclusions} ({result['elapsed']:.0f}s)"
    elif "mergeable_state" in result:
        # Note: Actions workflow doesn't support No-Issue, so this may
        # depend on which check gates the repo
        actual = f"mergeable_state: {result['mergeable_state']} ({result['elapsed']:.0f}s)"
        passed = result["mergeable_state"] == "clean"

    cleanup_test_pr(repo, pr_num, branch)

    return TestResult("T06", "No-Issue exemption",
                      "Worker check passes (No-Issue pattern)",
                      actual, passed, duration_s=time.time() - t0)


def test_worker_health() -> TestResult:
    """T07: Cloudflare Worker health endpoint should return 200."""
    t0 = time.time()
    status, body = run_curl(SENTINEL_HEALTH_URL)
    passed = status == 200 and body.strip() == "ok"
    actual = f"HTTP {status}, body: {body[:50]}"
    return TestResult("T07", "Worker health check",
                      "HTTP 200, body: ok",
                      actual, passed, duration_s=time.time() - t0)


def test_cerberus_secrets(repo: str) -> TestResult:
    """T08: Cerberus secrets should exist on the repo."""
    t0 = time.time()
    rc, output = run_gh("secret", "list", "--repo", repo)
    if rc != 0:
        return TestResult("T08", "Cerberus secrets present",
                          "REVIEWER_APP_ID + REVIEWER_APP_PRIVATE_KEY",
                          f"Cannot list secrets: {output[:100]}", False,
                          duration_s=time.time() - t0)

    has_app_id = "REVIEWER_APP_ID" in output
    has_key = "REVIEWER_APP_PRIVATE_KEY" in output
    passed = has_app_id and has_key
    missing = []
    if not has_app_id:
        missing.append("REVIEWER_APP_ID")
    if not has_key:
        missing.append("REVIEWER_APP_PRIVATE_KEY")

    actual = "Both present" if passed else f"Missing: {', '.join(missing)}"
    return TestResult("T08", "Cerberus secrets present",
                      "REVIEWER_APP_ID + REVIEWER_APP_PRIVATE_KEY",
                      actual, passed, duration_s=time.time() - t0)


def test_workflow_files(repo: str) -> TestResult:
    """T09: Required workflow files should exist with correct permissions."""
    t0 = time.time()
    issues = []

    for wf_name in ["pr-sentinel.yml", "auto-reviewer.yml"]:
        rc, output = run_gh(
            "api", f"repos/{repo}/contents/.github/workflows/{wf_name}",
            "--jq", ".content",
        )
        if rc != 0:
            issues.append(f"{wf_name}: missing")
            continue

        # Decode and check for permissions block
        import base64
        try:
            content = base64.b64decode(output.strip().strip('"')).decode()
            if "permissions:" not in content:
                issues.append(f"{wf_name}: missing permissions block")
        except Exception:
            issues.append(f"{wf_name}: cannot decode")

    passed = len(issues) == 0
    actual = "All present with permissions" if passed else "; ".join(issues)
    return TestResult("T09", "Workflow files present",
                      "pr-sentinel.yml + auto-reviewer.yml with permissions",
                      actual, passed, duration_s=time.time() - t0)


def run_local_tests(repo: str, dry_run: bool = False) -> list[TestResult]:
    """Run all local-mode tests against a single repo."""
    results = []

    print(f"\n{'=' * 60}")
    print(f"Governance System Tests — Local Mode")
    print(f"Repo: {repo}")
    print(f"{'=' * 60}")

    # Infrastructure tests (fast, no PR creation)
    print("\n--- Infrastructure Tests ---")

    print("  T07: Worker health check...")
    results.append(test_worker_health())
    print(f"    {'PASS' if results[-1].passed else 'FAIL'}: {results[-1].actual}")

    print(f"  T08: Cerberus secrets on {repo}...")
    results.append(test_cerberus_secrets(repo))
    print(f"    {'PASS' if results[-1].passed else 'FAIL'}: {results[-1].actual}")

    print(f"  T09: Workflow files on {repo}...")
    results.append(test_workflow_files(repo))
    print(f"    {'PASS' if results[-1].passed else 'FAIL'}: {results[-1].actual}")

    if dry_run:
        print("\n--- Dry run: skipping PR-based tests ---")
        return results

    # PR-based tests (slow, creates real PRs)
    print("\n--- Happy Path Tests ---")

    print("  T01: Valid Closes #N...")
    results.append(test_happy_path(repo))
    print(f"    {'PASS' if results[-1].passed else 'FAIL'}: {results[-1].actual}")

    print("  T06: No-Issue exemption...")
    results.append(test_no_issue_exemption(repo))
    print(f"    {'PASS' if results[-1].passed else 'FAIL'}: {results[-1].actual}")

    print("\n--- Failure Path Tests ---")

    print("  T02: No issue reference...")
    results.append(test_no_issue_ref(repo))
    print(f"    {'PASS' if results[-1].passed else 'FAIL'}: {results[-1].actual}")

    print("  T03: Closed issue reference...")
    results.append(test_closed_issue_ref(repo))
    print(f"    {'PASS' if results[-1].passed else 'FAIL'}: {results[-1].actual}")

    print("  T04: Naked #N format...")
    results.append(test_naked_hash(repo))
    print(f"    {'PASS' if results[-1].passed else 'FAIL'}: {results[-1].actual}")

    print("  T05: Empty PR body...")
    results.append(test_empty_body(repo))
    print(f"    {'PASS' if results[-1].passed else 'FAIL'}: {results[-1].actual}")

    return results


# ---------------------------------------------------------------------------
# Audit mode: fleet-wide branch protection comparison
# ---------------------------------------------------------------------------

def audit_repo_protection(repo: str) -> list[TestResult]:
    """Audit a single repo's branch protection against canonical config."""
    results = []
    prefix = repo.split("/")[-1]

    # Read branch protection
    rc, output = run_gh(
        "api", f"repos/{repo}/branches/main/protection",
    )

    if rc != 0:
        if "404" in output:
            results.append(TestResult(
                f"{prefix}/A01", "Branch protection exists",
                "Protection configured", "No protection on main",
                False, detail="HTTP 404",
            ))
        elif "403" in output:
            results.append(TestResult(
                f"{prefix}/A01", "Branch protection exists",
                "Readable", "Token lacks admin scope (HTTP 403)",
                False, detail="Need classic PAT",
            ))
        return results

    try:
        prot = json.loads(output)
    except json.JSONDecodeError:
        results.append(TestResult(
            f"{prefix}/A01", "Branch protection exists",
            "Valid JSON", f"Invalid response: {output[:100]}",
            False,
        ))
        return results

    # A01: Protection exists
    results.append(TestResult(
        f"{prefix}/A01", "Branch protection exists",
        "Yes", "Yes", True,
    ))

    # A02: Review count
    reviews = prot.get("required_pull_request_reviews")
    if reviews:
        count = reviews.get("required_approving_review_count", 0)
    else:
        count = "not configured"
    expected = CANONICAL["required_approving_review_count"]
    results.append(TestResult(
        f"{prefix}/A02", "Required review count",
        str(expected), str(count),
        count == expected,
    ))

    # A03: enforce_admins
    ea = prot.get("enforce_admins", {})
    ea_val = ea.get("enabled", False) if isinstance(ea, dict) else False
    results.append(TestResult(
        f"{prefix}/A03", "enforce_admins",
        str(CANONICAL["enforce_admins"]), str(ea_val),
        ea_val == CANONICAL["enforce_admins"],
    ))

    # A04: Force push blocked
    fp = prot.get("allow_force_pushes", {})
    fp_val = fp.get("enabled", True) if isinstance(fp, dict) else True
    results.append(TestResult(
        f"{prefix}/A04", "Force push blocked",
        str(CANONICAL["allow_force_pushes"]), str(fp_val),
        fp_val == CANONICAL["allow_force_pushes"],
    ))

    # A05: Deletion blocked
    dl = prot.get("allow_deletions", {})
    dl_val = dl.get("enabled", True) if isinstance(dl, dict) else True
    results.append(TestResult(
        f"{prefix}/A05", "Deletion blocked",
        str(CANONICAL["allow_deletions"]), str(dl_val),
        dl_val == CANONICAL["allow_deletions"],
    ))

    # A06: Status checks — context contains "issue-reference"
    sc = prot.get("required_status_checks")
    if sc and isinstance(sc, dict):
        contexts = sc.get("contexts", [])
        strict = sc.get("strict", False)
    else:
        contexts = []
        strict = None

    has_sentinel = any(
        CANONICAL["context_must_contain"] in ctx for ctx in contexts
    )
    results.append(TestResult(
        f"{prefix}/A06", "issue-reference check required",
        f"Context containing '{CANONICAL['context_must_contain']}'",
        f"Contexts: {contexts}",
        has_sentinel,
    ))

    # A07: strict=false
    if strict is not None:
        results.append(TestResult(
            f"{prefix}/A07", "strict mode",
            str(CANONICAL["strict"]), str(strict),
            strict == CANONICAL["strict"],
        ))

    return results


def run_audit(repos: list[str]) -> list[TestResult]:
    """Run fleet-wide audit."""
    results = []

    print(f"\n{'=' * 60}")
    print(f"Governance System Audit — Fleet Mode")
    print(f"Repos: {len(repos)}")
    print(f"{'=' * 60}\n")

    for i, repo in enumerate(repos, 1):
        print(f"  [{i}/{len(repos)}] {repo}...", end=" ")
        repo_results = audit_repo_protection(repo)
        results.extend(repo_results)

        fails = sum(1 for r in repo_results if not r.passed)
        if fails:
            print(f"{'FAIL'} ({fails} issues)")
        else:
            print("OK")

        if i < len(repos):
            time.sleep(0.3)

    return results


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def write_report(results: list[TestResult], mode: str, repo: str | None) -> Path:
    """Write test results to markdown."""
    now = datetime.now(timezone.utc)
    output_dir = Path(__file__).parent.parent / "docs" / "audits" / "governance-tests"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{mode}-{now.strftime('%Y%m%d-%H%M%S')}.md"

    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)

    lines = [
        "# Governance System Test Report",
        "",
        f"**Date:** {now.isoformat()}",
        f"**Mode:** {mode}",
    ]
    if repo:
        lines.append(f"**Repo:** {repo}")
    lines.extend([
        f"**Script:** `tools/test_governance_system.py`",
        f"**Standard:** 0016-pr-sentinel-system-architecture.md",
        "",
        "## Summary",
        "",
        f"| Result | Count |",
        f"|--------|-------|",
        f"| PASS | {passed} |",
        f"| FAIL | {failed} |",
        f"| Total | {len(results)} |",
        "",
        "## Results",
        "",
        "| ID | Test | Expected | Actual | Result |",
        "|---|---|---|---|---|",
    ])

    for r in results:
        status = "PASS" if r.passed else "**FAIL**"
        actual_clean = r.actual.replace("|", "\\|").replace("\n", " ")[:120]
        expected_clean = r.expected.replace("|", "\\|")[:80]
        lines.append(
            f"| {r.test_id} | {r.name} | {expected_clean} | {actual_clean} | {status} |"
        )

    failures = [r for r in results if not r.passed]
    if failures:
        lines.extend(["", "## Failures", ""])
        for r in failures:
            lines.append(f"- **{r.test_id} ({r.name}):** expected `{r.expected}`, "
                         f"got `{r.actual}`")
            if r.detail:
                lines.append(f"  - Detail: {r.detail}")

    lines.extend([
        "",
        "---",
        f"*Generated by tools/test_governance_system.py on {now.strftime('%Y-%m-%d')}*",
    ])

    output_file.write_text("\n".join(lines), encoding="utf-8")
    return output_file


def print_summary(results: list[TestResult]):
    """Print summary table to stdout."""
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)

    print(f"\n{'=' * 60}")
    print(f"RESULTS: {passed} passed, {failed} failed, {len(results)} total")
    print(f"{'=' * 60}")

    if failed:
        print("\nFailures:")
        for r in results:
            if not r.passed:
                print(f"  {r.test_id} {r.name}")
                print(f"    Expected: {r.expected}")
                print(f"    Actual:   {r.actual}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="PR Governance System Test Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  poetry run python tools/test_governance_system.py --mode local
  poetry run python tools/test_governance_system.py --mode local --repo martymcenroe/Sextant
  poetry run python tools/test_governance_system.py --mode local --dry-run
  poetry run python tools/test_governance_system.py --mode audit
        """,
    )
    parser.add_argument(
        "--mode", required=True, choices=["local", "audit"],
        help="Test mode: 'local' for PR tests, 'audit' for fleet comparison",
    )
    parser.add_argument(
        "--repo", default=DEFAULT_REPO,
        help=f"Target repo for local mode (default: {DEFAULT_REPO})",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Infrastructure checks only, skip PR creation",
    )
    args = parser.parse_args()

    token_type = detect_token_type()
    print(f"Token type: {token_type}")

    if args.mode == "audit" and "fine-grained" in token_type:
        print("\nERROR: Audit mode requires classic PAT with repo + admin:repo_hook scopes.")
        print("Run: gh auth login -h github.com -p https")
        sys.exit(1)

    if args.mode == "local":
        results = run_local_tests(args.repo, dry_run=args.dry_run)
        report = write_report(results, "local", args.repo)
    else:
        repos = get_all_repos()
        if not repos:
            print("ERROR: No repos found.")
            sys.exit(1)
        results = run_audit(repos)
        report = write_report(results, "audit", None)

    print_summary(results)
    print(f"\nReport: {report}")

    failed = sum(1 for r in results if not r.passed)
    sys.exit(2 if failed else 0)


if __name__ == "__main__":
    main()
