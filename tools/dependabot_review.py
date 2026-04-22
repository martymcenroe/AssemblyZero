#!/usr/bin/env python3
"""Deterministic dependabot PR review + merge.

Hard gates (no LLM in the loop):

1. Author gate: every PR must be authored by `dependabot[bot]`. Any other
   author is a hard refusal — the script will not approve or merge it.
2. Test gate: `poetry run pytest` must exit 0. Non-zero exit means the PR
   is commented on and left for human review; no approval, no merge.

For each open dependabot-authored PR:

- Create an audit worktree from current main
- `gh pr checkout <N>` into the worktree (brings the dep bump in)
- Evict any poetry-cached venv (Fix 5 / #944) so Windows file locks release
- `poetry install` (fresh)
- `poetry run pytest` — capture exit code
- On green (exit 0):
    - Edit PR body to append `No-Issue: automated dependency update (...)`
      so pr-sentinel's No-Issue exemption passes
    - `gh pr review --approve` via the invoking user's credentials (creates a
      PullRequestReview event attributed to that user)
    - Poll `mergeable_state` until clean
    - `gh pr merge --squash`
    - Clean up worktree + audit branch
- On red (non-zero):
    - Comment on PR with exit code + forensics worktree path
    - If multi-package PR: request `@dependabot recreate` to split into
      per-package PRs
    - Leave worktree in place for forensics
    - Move to next PR (one failure does not block the queue)

Usage:
    poetry run python tools/dependabot_review.py [--repo OWNER/REPO] [--dry-run]

Issue: #949 | Related: #692 | Runbook: 0911 v2.0
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

GITHUB_USER = "martymcenroe"
DEFAULT_REPO = f"{GITHUB_USER}/AssemblyZero"
# GitHub returns different strings for the same bot depending on API surface:
#   - REST API / web UI:              "dependabot[bot]"
#   - gh CLI GraphQL .author.login:   "app/dependabot"
# Accept both forms at the hard gate — still refuses anything else.
ACCEPTED_AUTHORS: tuple[str, ...] = ("dependabot[bot]", "app/dependabot")
POLL_INTERVAL_S = 10
# Issue #971: 300s default was too tight; ~10% of fleet runs missed the
# Cerberus-AZ approval window. 900s covers the observed tail. The
# fleet_delete_pr_sentinel.py companion also uses 900s after #981.
MERGEABLE_TIMEOUT_S = 900
PYTEST_TIMEOUT_S = 1800
POETRY_INSTALL_TIMEOUT_S = 600


@dataclass
class PRInfo:
    number: int
    title: str
    author_login: str
    body: str
    head_ref: str


# ---------------------------------------------------------------------------
# Subprocess wrapper — every command is visible
# ---------------------------------------------------------------------------

def run(cmd: list[str], cwd: str | None = None,
        timeout: int | None = None) -> subprocess.CompletedProcess:
    """Run a subprocess and echo the command to stdout."""
    print(f"  $ {' '.join(cmd)}")
    try:
        return subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True,
            timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT after {timeout}s")
        return subprocess.CompletedProcess(cmd, returncode=124, stdout="", stderr="TIMEOUT")


def run_gh_with_body(args_pre: list[str], body: str) -> subprocess.CompletedProcess:
    """Run a gh command, passing `body` via --body-file to avoid argv size limits.

    Windows CreateProcess rejects command lines over ~32K chars (WinError 206).
    Dependabot multi-package PR bodies regularly exceed this with embedded
    release notes. --body-file makes gh read the body from disk instead of
    argv, sidestepping the limit on every platform.
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8",
    ) as tf:
        tf.write(body)
        tmp_path = tf.name
    try:
        return run(args_pre + ["--body-file", tmp_path])
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# PR enumeration
# ---------------------------------------------------------------------------

def list_dependabot_prs(repo: str) -> list[PRInfo]:
    result = run([
        "gh", "pr", "list", "--repo", repo,
        "--author", "app/dependabot",
        "--state", "open",
        "--json", "number,title,author,body,headRefName",
    ])
    if result.returncode != 0:
        sys.exit(f"Failed to list PRs: {result.stderr}")
    raw = json.loads(result.stdout or "[]")
    return [
        PRInfo(
            number=r["number"],
            title=r["title"],
            author_login=r["author"]["login"],
            body=r["body"] or "",
            head_ref=r["headRefName"],
        )
        for r in raw
    ]


def count_packages(body: str) -> int:
    """Count 'Updates `pkg`' blocks in the PR body — one per package bumped."""
    return len(re.findall(r"Updates `[^`]+`", body))


# ---------------------------------------------------------------------------
# Hard gates
# ---------------------------------------------------------------------------

def verify_author(pr: PRInfo) -> bool:
    if pr.author_login not in ACCEPTED_AUTHORS:
        print(f"  REFUSE: PR #{pr.number} author is '{pr.author_login}', "
              f"expected one of {ACCEPTED_AUTHORS} — this script operates only "
              f"on dependabot PRs")
        return False
    return True


# ---------------------------------------------------------------------------
# Worktree + env setup
# ---------------------------------------------------------------------------

def create_audit_worktree(main_repo: Path, pr_number: int) -> tuple[Path, str]:
    worktree = main_repo.parent / f"{main_repo.name}-dependabot-{pr_number}"
    branch = f"dependabot-audit-{pr_number}"
    result = run(["git", "-C", str(main_repo), "worktree", "add",
                  str(worktree), "-b", branch, "main"])
    if result.returncode != 0:
        sys.exit(f"Could not create worktree: {result.stderr}")
    return worktree, branch


def checkout_pr_into_worktree(worktree: Path, pr_number: int, repo: str) -> bool:
    result = run(["gh", "pr", "checkout", str(pr_number), "--repo", repo],
                 cwd=str(worktree))
    return result.returncode == 0


def evict_poetry_venv(worktree: Path) -> None:
    """Fix 5 / #944 — evict poetry-cached venv to release Windows file locks."""
    if not (worktree / "pyproject.toml").exists():
        return
    run(["poetry", "env", "remove", "--all"], cwd=str(worktree))


def install_deps(worktree: Path) -> bool:
    if not (worktree / "pyproject.toml").exists():
        return True  # Not a poetry project
    result = run(["poetry", "install"], cwd=str(worktree),
                 timeout=POETRY_INSTALL_TIMEOUT_S)
    return result.returncode == 0


# ---------------------------------------------------------------------------
# Test gate
# ---------------------------------------------------------------------------

def run_tests(worktree: Path) -> int:
    result = run(["poetry", "run", "pytest", "-q", "--tb=short"],
                 cwd=str(worktree), timeout=PYTEST_TIMEOUT_S)
    print(f"  pytest exit code: {result.returncode}")
    return result.returncode


# ---------------------------------------------------------------------------
# PR mutation (only after both gates pass)
# ---------------------------------------------------------------------------

def inject_no_issue(pr: PRInfo, repo: str) -> bool:
    package_count = count_packages(pr.body)
    tag = (
        f"No-Issue: automated dependency update "
        f"({package_count} package{'s' if package_count != 1 else ''}, "
        f"approved after green test run via tools/dependabot_review.py)"
    )
    new_body = pr.body.rstrip() + "\n\n" + tag
    result = run_gh_with_body(
        ["gh", "pr", "edit", str(pr.number), "--repo", repo],
        new_body,
    )
    return result.returncode == 0


def approve_pr(pr_number: int, repo: str) -> bool:
    result = run([
        "gh", "pr", "review", str(pr_number), "--repo", repo, "--approve",
        "--body",
        "Automated review via tools/dependabot_review.py — test suite passed "
        "(exit 0). Deterministic gate; no LLM in loop. "
        "Author and exit-code gates enforced.",
    ])
    return result.returncode == 0


def wait_for_mergeable(pr_number: int, repo: str) -> bool:
    """Poll until the PR is in a mergeable state. Returns True on success.

    Issue #971: accepts both 'clean' (all checks pass) and 'unstable'
    (only non-required checks failing — `gh pr merge --squash` succeeds
    in both cases). Today's pattern: legacy issue-reference checks fail
    on dependabot PRs even though the worker check passes; mergeable_state
    reports `unstable`, not `clean`. Branch protection is the actual gate.

    Tolerates one cycle of `blocked` to absorb the Cerberus-arrival race
    where the App posts approval between two of our polls.
    """
    deadline = time.time() + MERGEABLE_TIMEOUT_S
    polled_at_least_once = False
    while time.time() < deadline:
        result = run(["gh", "api", f"repos/{repo}/pulls/{pr_number}",
                      "--jq", ".mergeable_state"])
        state = (result.stdout or "").strip().strip('"')
        print(f"  mergeable_state: {state}")
        if state in ("clean", "unstable"):
            return True
        if state == "dirty":
            return False  # merge conflict; waiting won't help
        if state == "blocked" and polled_at_least_once:
            return False
        polled_at_least_once = True
        time.sleep(POLL_INTERVAL_S)
    return False


def squash_merge(pr_number: int, repo: str) -> bool:
    result = run(["gh", "pr", "merge", str(pr_number), "--repo", repo, "--squash"])
    return result.returncode == 0


def comment_on_pr(pr_number: int, repo: str, body: str) -> None:
    run_gh_with_body(
        ["gh", "pr", "comment", str(pr_number), "--repo", repo],
        body,
    )


def request_dependabot_recreate(pr_number: int, repo: str) -> None:
    comment_on_pr(
        pr_number, repo,
        "Test suite failed on this multi-package PR. Splitting via @dependabot "
        "recreate to isolate the failing package.",
    )
    comment_on_pr(pr_number, repo, "@dependabot recreate")


def request_dependabot_rebase(pr_number: int, repo: str) -> None:
    """Issue #994: auto-recover from stale-branch deferrals.

    When a dependabot PR's base SHA is behind current main, test failures
    are often caused by missing fixes that have since landed on main rather
    than by the dependency upgrade itself. Posting `@dependabot rebase`
    triggers dependabot to force-push a rebased branch; the next
    /dependabot run can then re-test against the up-to-date code.

    Non-destructive: if the failure is real (upgrade incompatibility),
    the rebased PR will fail again on next run.
    """
    comment_on_pr(
        pr_number, repo,
        "Test suite failed AND this PR's base is behind current `main`. "
        "Many failures from this pattern resolve after rebasing onto the "
        "latest baseline (vs. being real upgrade incompatibilities). "
        "Requesting `@dependabot rebase` so the next `/dependabot` run "
        "evaluates against current main.",
    )
    comment_on_pr(pr_number, repo, "@dependabot rebase")


def is_pr_branch_stale(pr_number: int, repo: str) -> bool:
    """Issue #994: True if the PR's base SHA differs from main HEAD.

    Cheap proxy for "the branch is missing recent commits from main."
    Used in the deferral path to decide whether to auto-request a rebase
    before treating the test failure as an upgrade incompatibility.
    """
    base_result = run([
        "gh", "api", f"repos/{repo}/pulls/{pr_number}",
        "--jq", ".base.sha",
    ])
    main_result = run([
        "gh", "api", f"repos/{repo}/branches/main",
        "--jq", ".commit.sha",
    ])
    pr_base = (base_result.stdout or "").strip().strip('"')
    main_head = (main_result.stdout or "").strip().strip('"')
    if not pr_base or not main_head:
        return False  # Conservative: don't trigger rebase on uncertain state
    return pr_base != main_head


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def cleanup_worktree(main_repo: Path, worktree: Path, branch: str) -> None:
    evict_poetry_venv(worktree)
    run(["git", "-C", str(main_repo), "worktree", "remove", str(worktree)])
    run(["git", "-C", str(main_repo), "branch", "-D", branch])


# ---------------------------------------------------------------------------
# Per-PR processing
# ---------------------------------------------------------------------------

def process_pr(pr: PRInfo, repo: str, main_repo: Path) -> str:
    """Process a single PR. Returns 'merged', 'deferred', or 'errored'."""
    print(f"\n=== PR #{pr.number}: {pr.title} ===")

    if not verify_author(pr):
        return "errored"

    worktree, branch = create_audit_worktree(main_repo, pr.number)

    if not checkout_pr_into_worktree(worktree, pr.number, repo):
        print("  ERROR: gh pr checkout failed")
        cleanup_worktree(main_repo, worktree, branch)
        return "errored"

    evict_poetry_venv(worktree)

    if not install_deps(worktree):
        print("  ERROR: poetry install failed")
        comment_on_pr(pr.number, repo,
                      "Automated review via tools/dependabot_review.py — "
                      "`poetry install` failed. Check Actions / worktree for details.")
        # Leave worktree for forensics
        return "deferred"

    exit_code = run_tests(worktree)

    if exit_code != 0:
        package_count = count_packages(pr.body)
        comment_on_pr(
            pr.number, repo,
            f"Automated review via tools/dependabot_review.py — test suite "
            f"FAILED (exit {exit_code}). Worktree retained at `{worktree}` "
            f"for forensics. Not approving, not merging.",
        )
        # Issue #994: prefer staleness diagnosis over recreate.
        # If the branch is behind main, the failure may be an artifact of a
        # missing fix on main; rebase first before considering the upgrade
        # incompatible.
        if is_pr_branch_stale(pr.number, repo):
            print("  PR branch is stale (base behind main) — "
                  "requesting @dependabot rebase")
            request_dependabot_rebase(pr.number, repo)
        elif package_count > 1:
            print(f"  Multi-package PR ({package_count} packages) — "
                  f"requesting dependabot recreate")
            request_dependabot_recreate(pr.number, repo)
        # Leave worktree in place for forensics
        return "deferred"

    # ---- Green path ----
    if not inject_no_issue(pr, repo):
        print("  ERROR: inject No-Issue failed")
        cleanup_worktree(main_repo, worktree, branch)
        return "errored"

    # Small wait for pr-sentinel to re-evaluate the edited body
    time.sleep(5)

    if not approve_pr(pr.number, repo):
        print("  ERROR: approve failed")
        cleanup_worktree(main_repo, worktree, branch)
        return "errored"

    if not wait_for_mergeable(pr.number, repo):
        print(f"  ERROR: mergeable_state never reached 'clean' within {MERGEABLE_TIMEOUT_S}s")
        cleanup_worktree(main_repo, worktree, branch)
        return "errored"

    if not squash_merge(pr.number, repo):
        print("  ERROR: merge failed")
        cleanup_worktree(main_repo, worktree, branch)
        return "errored"

    cleanup_worktree(main_repo, worktree, branch)
    return "merged"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deterministic dependabot PR review + merge "
                    "(author gate + exit-code gate, no LLM in loop).",
    )
    parser.add_argument("--repo", default=DEFAULT_REPO,
                        help=f"GitHub repo (default: {DEFAULT_REPO})")
    parser.add_argument("--main-repo", default=str(Path.cwd()),
                        help="Path to main repo (default: cwd)")
    parser.add_argument("--dry-run", action="store_true",
                        help="List PRs that would be processed; take no action")
    args = parser.parse_args()

    main_repo = Path(args.main_repo).resolve()
    if not (main_repo / ".git").exists():
        sys.exit(f"Not a git repo: {main_repo}")

    prs = list_dependabot_prs(args.repo)
    if not prs:
        print("No open dependabot PRs. Nothing to do.")
        return

    print(f"Found {len(prs)} open dependabot PR(s):")
    for pr in prs:
        print(f"  #{pr.number}: {pr.title} ({count_packages(pr.body)} packages)")

    if args.dry_run:
        print("\n(dry-run; exiting)")
        return

    results: dict[str, list[int]] = {"merged": [], "deferred": [], "errored": []}
    for pr in prs:
        status = process_pr(pr, args.repo, main_repo)
        results[status].append(pr.number)

    print("\n=== Summary ===")
    print(f"  Merged:   {results['merged']}")
    print(f"  Deferred (test failures / install errors, worktree retained): "
          f"{results['deferred']}")
    print(f"  Errored:  {results['errored']}")


if __name__ == "__main__":
    main()
