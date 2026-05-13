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
    - Comment on PR with exit code (PR + Actions output is the forensic
      record -- no local artifact retained, #1116)
    - If multi-package PR: request `@dependabot recreate` to split into
      per-package PRs
    - Clean up worktree + audit branch
    - Move to next PR (one failure does not block the queue)

Cleanup contract (#1116, hardened in #1133): zero persistent disk
artifacts on ANY exit path -- normal return, deferred, errored, OR
exception. Exit paths through `return` are covered by the try/finally
wrapper in process_pr; exception paths are covered by the same finally
block. If `git worktree remove` itself fails (e.g., the working tree
went dirty mid-run), cleanup_worktree prints a CLEANUP FAILURE warning
to stderr with the captured exit code and stderr -- the operator MUST
investigate that path before the next run, because a leaked worktree
breaks subsequent `git worktree add` for the same PR number.

On startup, a canary lists pre-existing `*-dependabot-N` worktrees and
refuses to proceed unless --ignore-orphans is passed (so accumulating
debt is loud rather than silent).

Usage:
    poetry run python tools/dependabot_review.py [--repo OWNER/REPO] [--dry-run]

Issue: #949 | Related: #692, #1116 | Runbook: 0911 v2.0
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

GITHUB_USER = "martymcenroe"
DEFAULT_REPO = f"{GITHUB_USER}/AssemblyZero"
# Issue #1091: --fleet mode uses gh repo list to enumerate user-owned repos.
# Cap at 200 — well above current ~60-repo count without paginating.
FLEET_REPO_LIMIT = 200
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
        timeout: int | None = None,
        quiet_on_failure: bool = False) -> subprocess.CompletedProcess:
    """Run a subprocess and echo the command to stdout.

    `encoding="utf-8", errors="replace"` is mandatory on Windows.
    Default `text=True` decodes with the system locale (cp1252 on most
    Windows installs), which crashes in `_readerthread` if any
    subprocess emits a non-cp1252 byte (e.g. `git worktree list` output,
    `gh pr` body containing an em-dash, pytest output with a non-ASCII
    test name). The reader thread crash leaves stdout silently empty,
    so the caller sees CompletedProcess with no output and proceeds as
    if the command succeeded -- which is catastrophic on the merge path.
    UTF-8 + replace tolerates any byte stream without crashing.

    On non-zero exit, prints stderr (or stdout if stderr is empty) so
    the operator sees WHY a command failed. Without this, every "ERROR:
    X failed" line in the per-PR trace was uninformative -- and worse,
    sometimes gh CLI returns non-zero on success (e.g. emits a warning
    but the operation completed), so the caller can't trust the exit
    code alone. Truncated to 500 chars to bound the noise.

    `quiet_on_failure=True` suppresses the error print for calls where
    non-zero is the expected filter signal (e.g. probing for the
    existence of a file in the fleet enumeration -- a 404 just means
    "this repo doesn't have pyproject.toml", not "something broke").
    """
    print(f"  $ {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT after {timeout}s")
        return subprocess.CompletedProcess(cmd, returncode=124, stdout="", stderr="TIMEOUT")
    if result.returncode != 0 and not quiet_on_failure:
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        if stderr:
            print(f"  [exit {result.returncode}] stderr: {stderr[:500]}")
        elif stdout:
            print(f"  [exit {result.returncode}] stdout: {stdout[:500]}")
        else:
            print(f"  [exit {result.returncode}] (no output)")
    return result


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
    # --detach: do NOT create a local branch named after the PR's headRefName
    # (e.g., "dependabot/pip/pip-foo"). cleanup_worktree only deletes the audit
    # branch we created in create_audit_worktree; without --detach, the dep
    # branch survives every "successful" cleanup and accumulates as orphan
    # local refs. (#1107)
    result = run(["gh", "pr", "checkout", str(pr_number), "--repo", repo, "--detach"],
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
    """Squash-merge the PR. Returns True iff the PR is actually merged
    according to GitHub's `merged` field.

    `gh pr merge --squash` returns non-zero in cases where the merge
    actually succeeded -- e.g. gh prints a warning during cleanup, or
    a transient connection blip drops the post-merge status response.
    Trusting the exit code alone caused tonight's automation-scripts
    #29 to print "ERROR: merge failed" even though the merge had
    landed. Re-query the PR after the merge attempt to find out what
    really happened.
    """
    run(["gh", "pr", "merge", str(pr_number), "--repo", repo, "--squash"])
    check = run([
        "gh", "api", f"repos/{repo}/pulls/{pr_number}",
        "--jq", ".merged",
    ])
    return (check.stdout or "").strip().lower() == "true"


def comment_on_pr(pr_number: int, repo: str, body: str) -> None:
    """Post a regular issue comment. Use for @dependabot bot commands.

    Issue comments do NOT count toward the user's Code Review profile
    stat. For comments where the user wants attribution credit (e.g.,
    test-failure deferral notes), use `review_comment_on_pr` instead.
    Bot-directed commands like `@dependabot recreate` / `@dependabot
    rebase` should stay as issue comments — that's the form dependabot
    documents and there's no need to risk parsing differences.
    """
    run_gh_with_body(
        ["gh", "pr", "comment", str(pr_number), "--repo", repo],
        body,
    )


def review_comment_on_pr(pr_number: int, repo: str, body: str) -> bool:
    """Post a comment AS A FORMAL REVIEW (#1091).

    Creates a `PullRequestReview` event with state=COMMENTED. This
    counts toward the invoking user's Code Review profile stat (the
    GitHub activity overview wedge), unlike `gh pr comment` which
    creates an unattributed issue comment.

    Use for comments on the deferral path (test failure, install
    failure) where the user — having gone through the trouble of
    auditing the PR — should get review credit even though the PR
    isn't being merged.

    Returns True on success.
    """
    result = run_gh_with_body(
        [
            "gh", "pr", "review", str(pr_number),
            "--repo", repo, "--comment",
        ],
        body,
    )
    return result.returncode == 0


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

def cleanup_worktree(main_repo: Path, worktree: Path, branch: str) -> bool:
    """Remove the audit worktree and its branch. Returns True iff both
    operations exited with status 0.

    `git branch -d` (lowercase, safe) is sufficient here because the audit
    branch is created from `main` by create_audit_worktree and never moves --
    checkout_pr_into_worktree uses `gh pr checkout --detach` (#1107), so the
    worktree's HEAD detaches without committing on the audit branch. After
    the dep PR is squash-merged, main fast-forwards past the original tip,
    leaving the audit branch fully reachable from main -> safe-delete works.
    `branch -D` is permanently banned per memory feedback_destructive_flag_scrutiny.

    #1133: previously this function discarded subprocess exit codes, so
    a dirty worktree (e.g., cascade detector having appended to a tracked
    file -- pre-#1134) caused `git worktree remove` to fail silently and
    leak the worktree. Now exit codes are inspected; failures are printed
    LOUDLY to stderr with the captured stderr text so the operator can
    diagnose. The bool return lets the caller decide whether to escalate;
    process_pr's try/finally surfaces failures as a WARNING but does not
    flip the PR processing result.
    """
    success = True
    evict_poetry_venv(worktree)

    wt_remove = run(["git", "-C", str(main_repo), "worktree", "remove", str(worktree)])
    if wt_remove.returncode != 0:
        success = False
        print(
            f"  CLEANUP FAILURE: `git worktree remove {worktree}` returned "
            f"{wt_remove.returncode}\n"
            f"  stderr: {wt_remove.stderr.strip()[:300] if wt_remove.stderr else '(none)'}\n"
            f"  This worktree is now an ORPHAN. Investigate before next run "
            f"-- a stuck worktree blocks `git worktree add` for the same PR.",
            file=sys.stderr,
        )

    br_delete = run(["git", "-C", str(main_repo), "branch", "-d", branch])
    if br_delete.returncode != 0:
        success = False
        # branch -d failing post-worktree-remove-failure is expected (the
        # branch is still associated with the leaked worktree). Print
        # diagnostically rather than crying wolf separately when the root
        # cause is already surfaced above.
        if wt_remove.returncode == 0:
            print(
                f"  CLEANUP FAILURE: `git branch -d {branch}` returned "
                f"{br_delete.returncode}\n"
                f"  stderr: {br_delete.stderr.strip()[:300] if br_delete.stderr else '(none)'}",
                file=sys.stderr,
            )

    return success


def check_for_orphan_worktrees(main_repo: Path) -> list[str]:
    """#1133: enumerate pre-existing dependabot worktrees so the operator
    can be warned at startup. Returns list of orphan worktree paths
    matching the `{main_name}-dependabot-N` pattern. Empty list = clean.
    """
    result = run(["git", "-C", str(main_repo), "worktree", "list", "--porcelain"])
    if result.returncode != 0:
        # If we can't even list, return empty -- don't block the script on
        # a diagnostic that itself errored.
        return []
    orphans: list[str] = []
    prefix = f"{main_repo.name}-dependabot-"
    for line in result.stdout.splitlines():
        if not line.startswith("worktree "):
            continue
        path = line[len("worktree "):].strip()
        if prefix in Path(path).name:
            orphans.append(path)
    return orphans


# ---------------------------------------------------------------------------
# Per-PR processing
# ---------------------------------------------------------------------------

def _process_pr_inside_worktree(
    pr: PRInfo, repo: str, worktree: Path,
) -> str:
    """Inner pipeline that assumes the audit worktree has been created.

    Returns 'merged', 'deferred', or 'errored'. Does NOT clean up --
    cleanup is the caller's responsibility (process_pr's try/finally).
    """
    if not checkout_pr_into_worktree(worktree, pr.number, repo):
        print("  ERROR: gh pr checkout failed")
        return "errored"

    evict_poetry_venv(worktree)

    if not install_deps(worktree):
        print("  ERROR: poetry install failed")
        # Issue #1091: post as a formal review-comment so the failure
        # path also accrues to the user's Code Review profile stat.
        review_comment_on_pr(
            pr.number, repo,
            "Automated review via tools/dependabot_review.py -- "
            "`poetry install` failed. See the PR's Actions output for the "
            "captured stderr; re-run locally via `gh pr checkout` if needed.",
        )
        return "deferred"

    exit_code = run_tests(worktree)

    if exit_code != 0:
        package_count = count_packages(pr.body)
        # Issue #1091: post as a formal review-comment (creates a
        # PullRequestReview event attributed to the invoking user)
        # rather than an issue comment. Even on the deferral path the
        # user has audited the PR; the credit should reflect that.
        review_comment_on_pr(
            pr.number, repo,
            f"Automated review via tools/dependabot_review.py -- test suite "
            f"FAILED (exit {exit_code}). Not approving, not merging. "
            f"Re-run locally via `gh pr checkout` if needed; the PR's Actions "
            f"output is the forensic record.",
        )
        # Issue #994: prefer staleness diagnosis over recreate.
        # If the branch is behind main, the failure may be an artifact of a
        # missing fix on main; rebase first before considering the upgrade
        # incompatible.
        if is_pr_branch_stale(pr.number, repo):
            print("  PR branch is stale (base behind main) -- "
                  "requesting @dependabot rebase")
            request_dependabot_rebase(pr.number, repo)
        elif package_count > 1:
            print(f"  Multi-package PR ({package_count} packages) -- "
                  f"requesting dependabot recreate")
            request_dependabot_recreate(pr.number, repo)
        return "deferred"

    # ---- Green path ----
    if not inject_no_issue(pr, repo):
        print("  ERROR: inject No-Issue failed")
        return "errored"

    # Small wait for pr-sentinel to re-evaluate the edited body
    time.sleep(5)

    if not approve_pr(pr.number, repo):
        print("  ERROR: approve failed")
        return "errored"

    if not wait_for_mergeable(pr.number, repo):
        # Distinguish failure modes. Re-query mergeable_state to decide
        # remediation. The approval from approve_pr has already been
        # posted -- on the dirty branch (merge conflict), dependabot
        # rebase resolves the conflict without us touching the
        # approval (GitHub auto-dismisses stale reviews on force-push
        # if dismiss_stale_reviews is on; otherwise it persists and
        # the next tool run skips re-approval). Without this branch,
        # the tool would mark green-but-dirty PRs as "errored" forever
        # even though dependabot can fix them with one comment.
        final_state_result = run([
            "gh", "api", f"repos/{repo}/pulls/{pr.number}",
            "--jq", ".mergeable_state",
        ])
        final_state = (final_state_result.stdout or "").strip().strip('"')
        print(f"  ERROR: mergeable_state failed to reach 'clean' (got '{final_state}')")
        if final_state == "dirty":
            print("  Merge conflict -- requesting @dependabot rebase. "
                  "Approval persists; next run re-evaluates post-rebase.")
            request_dependabot_rebase(pr.number, repo)
        return "errored"

    if not squash_merge(pr.number, repo):
        print("  ERROR: merge failed")
        return "errored"

    return "merged"


def process_pr(pr: PRInfo, repo: str, main_repo: Path) -> str:
    """Process a single PR. Returns 'merged', 'deferred', or 'errored'.

    #1133: cleanup is wrapped in try/finally so it runs on every exit
    path -- normal return, sub-helper return, OR exception (Ctrl-C,
    subprocess timeout, network blip). The pre-#1133 design only
    covered explicit return statements, so any exception leaked the
    worktree.
    """
    print(f"\n=== PR #{pr.number}: {pr.title} ===")

    if not verify_author(pr):
        return "errored"

    worktree, branch = create_audit_worktree(main_repo, pr.number)

    try:
        return _process_pr_inside_worktree(pr, repo, worktree)
    finally:
        cleanup_ok = cleanup_worktree(main_repo, worktree, branch)
        if not cleanup_ok:
            # cleanup_worktree already printed the diagnostic. Add a
            # one-line WARNING for the operator who's scanning the
            # summary -- this is a leaked worktree they need to address.
            print(
                f"  WARNING: leftover state for PR #{pr.number} at {worktree}. "
                f"Manual cleanup required before next run.",
                file=sys.stderr,
            )


# ---------------------------------------------------------------------------
# Fleet enumeration (Issue #1091)
# ---------------------------------------------------------------------------

def list_fleet_repos(user: str = GITHUB_USER) -> list[str]:
    """List user-owned repos that we should attempt to process.

    Returns repos as 'owner/name' strings. Filters to repos where this
    tool can actually run the test gate — i.e., repos with a
    `pyproject.toml` on `main`. Non-Poetry repos (npm, Cargo, etc.)
    are omitted because the existing test gate can't validate them.
    Future per-language test runners can lift this filter.
    """
    result = run([
        "gh", "repo", "list", user,
        "--limit", str(FLEET_REPO_LIMIT),
        "--json", "name,nameWithOwner,isArchived,isFork",
    ])
    if result.returncode != 0:
        sys.exit(f"Failed to list fleet repos: {result.stderr}")
    repos = json.loads(result.stdout or "[]")

    candidates: list[str] = []
    for r in repos:
        if r.get("isArchived") or r.get("isFork"):
            continue
        candidates.append(r["nameWithOwner"])

    # Filter to repos that have a pyproject.toml on main. Non-Python
    # repos would defer every PR (poetry run pytest fails) which is a
    # waste — and would file failure-path review-comments on PRs the
    # user can't actually approve. Skip silently instead.
    processable: list[str] = []
    for repo in candidates:
        # 404 = "no pyproject.toml in this repo" = "not a Python repo we
        # can run pytest in". That's the FILTER signal, not an error;
        # suppress the stderr noise for these calls.
        check = run(
            [
                "gh", "api", f"repos/{repo}/contents/pyproject.toml",
                "--jq", ".name",
            ],
            quiet_on_failure=True,
        )
        if check.returncode == 0 and check.stdout.strip():
            processable.append(repo)

    return processable


# ---------------------------------------------------------------------------
# Per-repo processing (Issue #1093 — extracted for cross-repo parallelism)
# ---------------------------------------------------------------------------

def process_repo(
    repo: str,
    main_repo: Path,
    dry_run: bool = False,
) -> dict[str, list[str]]:
    """Process all dependabot PRs in one repo, sequentially.

    Within a repo, PR processing is sequential — each merge moves
    `main` and subsequent PRs need to test against the new HEAD.
    Cross-repo parallelism is the caller's responsibility.

    Returns a per-repo result dict with the same shape as the
    aggregate (merged / deferred / errored lists of `repo#N` strings).
    Empty lists when no PRs are open.
    """
    sub: dict[str, list[str]] = {"merged": [], "deferred": [], "errored": []}
    print(f"\n{'=' * 60}")
    print(f"REPO: {repo}")
    print(f"{'=' * 60}")
    prs = list_dependabot_prs(repo)
    if not prs:
        print(f"  No open dependabot PRs in {repo}.")
        return sub
    print(f"  Found {len(prs)} open dependabot PR(s):")
    for pr in prs:
        print(f"    #{pr.number}: {pr.title} "
              f"({count_packages(pr.body)} packages)")
    if dry_run:
        return sub
    for pr in prs:
        status = process_pr(pr, repo, main_repo)
        sub[status].append(f"{repo}#{pr.number}")
    return sub


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
    parser.add_argument(
        "--fleet", action="store_true",
        help=(
            "Process dependabot PRs across ALL user-owned repos with a "
            "pyproject.toml on main, not just --repo. Multiplies review-"
            "event volume across the fleet. Mutually exclusive with "
            "--repo (--fleet wins). (#1091)"
        ),
    )
    parser.add_argument(
        "--workers", type=int, default=3,
        help=(
            "Cross-repo parallelism (#1093). Number of repos to process "
            "concurrently in --fleet mode. PRs within a single repo "
            "remain sequential (each merge moves main; the next PR "
            "should test against the new HEAD). Ignored when --fleet "
            "is not set. Default: 3."
        ),
    )
    parser.add_argument("--main-repo", default=str(Path.cwd()),
                        help="Path to main repo (default: cwd)")
    parser.add_argument("--dry-run", action="store_true",
                        help="List PRs that would be processed; take no action")
    parser.add_argument(
        "--ignore-orphans", action="store_true",
        help=(
            "#1133: by default the script refuses to run if pre-existing "
            "`*-dependabot-N` worktrees are detected (signal that a prior "
            "run leaked state). Pass this to proceed anyway -- but resolve "
            "the orphans first or they accumulate."
        ),
    )
    args = parser.parse_args()

    main_repo = Path(args.main_repo).resolve()
    if not (main_repo / ".git").exists():
        sys.exit(f"Not a git repo: {main_repo}")

    # #1133: orphan-worktree canary BEFORE any new worktrees are created.
    # If a prior run leaked state, refuse to proceed unless explicitly
    # overridden -- accumulating orphans is what got us into the #1133
    # situation in the first place.
    orphans = check_for_orphan_worktrees(main_repo)
    if orphans:
        print(
            f"\nWARNING: pre-existing dependabot worktrees detected on "
            f"{main_repo.name}:",
            file=sys.stderr,
        )
        for o in orphans:
            print(f"  {o}", file=sys.stderr)
        if not args.ignore_orphans:
            print(
                "\nThese are leftovers from prior runs that didn't reach "
                "cleanup.\nAborting to prevent further pile-up. Investigate "
                "the orphans, clean them up, then re-run. Pass "
                "--ignore-orphans to override (not recommended).",
                file=sys.stderr,
            )
            sys.exit(3)
        print(
            "  proceeding anyway because --ignore-orphans was set",
            file=sys.stderr,
        )

    # Issue #1091: fleet mode enumerates user-owned Poetry repos.
    if args.fleet:
        print(f"Fleet mode — enumerating {GITHUB_USER}'s Python repos...")
        repos = list_fleet_repos()
        print(f"  Found {len(repos)} Poetry-based repo(s) to scan.")
    else:
        repos = [args.repo]

    # Aggregate results across repos.
    results: dict[str, list[str]] = {
        "merged": [], "deferred": [], "errored": [],
    }

    # Issue #1093: parallelize across repos in --fleet mode. Single-
    # repo mode (or --workers=1) keeps the sequential path. Within a
    # repo, processing is always sequential.
    if args.fleet and args.workers > 1 and not args.dry_run:
        print(f"\nProcessing {len(repos)} repo(s) with {args.workers} "
              f"worker(s)...")
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {
                executor.submit(process_repo, repo, main_repo, args.dry_run): repo
                for repo in repos
            }
            for future in as_completed(futures):
                repo = futures[future]
                try:
                    sub = future.result()
                except Exception as e:
                    print(f"\n  [ERROR] worker for {repo} raised: {e}")
                    sub = {"merged": [], "deferred": [], "errored": [repo]}
                for k in ("merged", "deferred", "errored"):
                    results[k].extend(sub[k])
    else:
        for repo in repos:
            sub = process_repo(repo, main_repo, args.dry_run)
            for k in ("merged", "deferred", "errored"):
                results[k].extend(sub[k])

    if args.dry_run:
        print("\n(dry-run; exiting)")
        return

    # Issue #1093: review-event counter — every merged PR generated
    # one APPROVED review event; every deferred PR generated one
    # COMMENTED review event (per change A in #1091). Errored PRs
    # generated nothing (the script bailed before any gh pr review
    # call). The counter makes Code Review profile-stat math visible
    # so the operator can verify credit was earned each run.
    approved_events = len(results["merged"])
    commented_events = len(results["deferred"])
    total_events = approved_events + commented_events

    print("\n=== Summary ===")
    print(f"  Merged:   {results['merged']}")
    print(f"  Deferred (test failures / install errors, worktree retained): "
          f"{results['deferred']}")
    print(f"  Errored:  {results['errored']}")
    print(
        f"  Review events created: {approved_events} APPROVED "
        f"+ {commented_events} COMMENTED = {total_events} total"
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # Ctrl-C while ThreadPoolExecutor is alive prints a multi-frame
        # traceback through threading.wait that looks like a crash even
        # though it's the user's intentional stop. Catch and exit
        # cleanly. Worker threads may still be finishing their current
        # PR -- their try/finally in process_pr will clean up worktrees
        # before they exit. Subsequent runs pick up where this left off.
        print(
            "\nInterrupted by user (Ctrl-C). Letting worker threads "
            "finish current PR cleanup; next run resumes from here.",
            file=sys.stderr,
        )
        sys.exit(130)
