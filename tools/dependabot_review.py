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

#1360: each fleet repo's PRs are processed in worktrees against THAT
repo's local clone -- not against AssemblyZero's git (which pre-#1360
hosted every fleet PR's content and accumulated foreign refs). Repos
without a local clone at `~/Projects/<name>` are skipped with a clear
diagnostic; no on-the-fly clone is created.

Per-repo orphan canary (also #1360): before processing a repo, scan
that repo's worktrees for leaked `dependabot-audit-N` pairs from prior
crashed runs. If any are found the repo is skipped this run (or
proceeds anyway with --ignore-orphans). Pre-#1360 a single global
canary aborted the whole fleet on AssemblyZero's state alone.

Usage:
    poetry run python tools/dependabot_review.py [--repo OWNER/REPO] [--dry-run]

Issue: #949 | Related: #692, #1116 | Runbook: 0911 v2.0
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import tomllib
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

GITHUB_USER = "martymcenroe"
DEFAULT_REPO = f"{GITHUB_USER}/AssemblyZero"
# Windows-only creationflag that isolates each child subprocess in its
# own process group. Without this, parent + child share a console
# group, so a child-side console event (e.g. pytest dying during
# config init when an import-time error fires, or `gh` shutting down
# after an HTTP error) can propagate as a CTRL_C_EVENT to the parent
# Python process and be received as SIGINT -- which the main thread
# raises as `KeyboardInterrupt`. This was tonight's "phantom Ctrl-C"
# (#1172): the user wasn't pressing anything, but pytest's collection
# crash on AZ #1097 (langchain-core 1.3.3 breaks test_auth_middleware
# import) propagated a console signal up. On non-Windows platforms
# the flag value is 0 (no-op); subprocess.CREATE_NEW_PROCESS_GROUP is
# only defined on Windows so the conditional protects portability.
_CREATION_FLAGS = (
    subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
)
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
# Pytest exit codes since pytest 5.0 (2019):
#   0 = all tests passed
#   1 = a test failed
#   2 = interrupted (Ctrl-C, etc.)
#   3 = internal error
#   4 = usage error
#   5 = no tests collected
# Exit 5 means the repo has no test suite (decorative-deps honeypot,
# scaffold-only repos). A dependency bump cannot turn N>0 tests into 0,
# so exit 5 reliably means "nothing to break" -- safe to treat as a
# pass for the dep-bump gate. Pre-#1397 the gate was `if exit_code != 0`
# which deferred every clean PR in any test-less repo (the honeypot
# never merged a single dependabot PR in 7 months for this reason).
# ADR 00001 sec 6 + the honeypot CLAUDE.md previously claimed
# "pytest returns 0 when no tests collected" -- that was true on
# pytest <5.0; doc fix tracked separately.
PYTEST_EXIT_NO_TESTS_COLLECTED = 5


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
        quiet_on_failure: bool = False,
        env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
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
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"  [{ts}] $ {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=timeout, check=False,
            creationflags=_CREATION_FLAGS,
            env=env,
        )
    except subprocess.TimeoutExpired:
        ts2 = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"  [{ts2}] TIMEOUT after {timeout}s")
        return subprocess.CompletedProcess(cmd, returncode=124, stdout="", stderr="TIMEOUT")
    if result.returncode != 0 and not quiet_on_failure:
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        ts3 = datetime.datetime.now().strftime("%H:%M:%S")
        # Show the TAIL of the output (last 2000 chars), not the head.
        # Pytest's failure summary, mypy's error counts, gh's last
        # response, git's actual error line -- all live at the END of
        # subprocess output. The original 500-char head capture was
        # consistently showing only the boring lead-in (e.g. pytest
        # progress dots) and missing the actual failure details that
        # make diagnosis possible.
        if stderr:
            tail = stderr[-2000:] if len(stderr) > 2000 else stderr
            prefix = "tail" if len(stderr) > 2000 else "all"
            print(f"  [{ts3}] [exit {result.returncode}] stderr ({prefix}, {len(stderr)} chars):")
            for line in tail.splitlines():
                print(f"  | {line}")
        elif stdout:
            tail = stdout[-2000:] if len(stdout) > 2000 else stdout
            prefix = "tail" if len(stdout) > 2000 else "all"
            print(f"  [{ts3}] [exit {result.returncode}] stdout ({prefix}, {len(stdout)} chars):")
            for line in tail.splitlines():
                print(f"  | {line}")
        else:
            print(f"  [{ts3}] [exit {result.returncode}] (no output)")
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

class PRListError(Exception):
    """#1370: raised by list_dependabot_prs when `gh pr list` fails.

    Replaces a former sys.exit. list_dependabot_prs runs inside
    ThreadPoolExecutor workers (process_repo) in --fleet mode; sys.exit
    raised SystemExit (BaseException), which escaped main()'s
    worker-aggregation `except Exception` and truncated the fleet
    summary. A plain Exception is caught by process_repo, recorded as an
    errored entry for that repo, and the sweep continues."""


def list_dependabot_prs(repo: str) -> list[PRInfo]:
    result = run([
        "gh", "pr", "list", "--repo", repo,
        "--author", "app/dependabot",
        "--state", "open",
        "--json", "number,title,author,body,headRefName",
    ])
    if result.returncode != 0:
        raise PRListError(
            f"Failed to list PRs for {repo}: {(result.stderr or '').strip()[:200]}"
        )
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

def create_audit_worktree(
    target_repo: Path, pr_number: int
) -> tuple[Path, str] | tuple[None, None]:
    """#1360: operate on `target_repo`'s git, not the script's invocation
    directory. Worktree path is `{target_repo.parent}/{target_repo.name}-
    dependabot-{N}`, hosted by `target_repo.git/worktrees/`. Pre-#1360
    this used a single main_repo (AssemblyZero) for every fleet repo's
    PRs, polluting AZ's git objects.

    #1370: returns (None, None) on worktree-add failure instead of
    sys.exit. This function runs inside ThreadPoolExecutor workers in
    --fleet mode; sys.exit raises SystemExit (a BaseException, not
    Exception), which escaped the worker-aggregation `except Exception`
    in main() and silently truncated the fleet summary -- every PR
    processed AFTER the failing one was dropped from the merged/deferred/
    errored counts even though the work had completed. Returning a
    sentinel lets process_pr record this PR as 'errored' and the sweep
    continue to the next PR / repo, so the summary stays truthful."""
    worktree = target_repo.parent / f"{target_repo.name}-dependabot-{pr_number}"
    branch = f"dependabot-audit-{pr_number}"
    result = run(["git", "-C", str(target_repo), "worktree", "add",
                  str(worktree), "-b", branch, "main"])
    if result.returncode != 0:
        print(
            f"  ERROR: could not create worktree at {worktree}: "
            f"{(result.stderr or '').strip()[:200]}",
            file=sys.stderr,
        )
        return None, None
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


def _clean_subprocess_env() -> dict[str, str]:
    """Return os.environ minus poetry-activation hints.

    The tool is invoked via `poetry run python tools/dependabot_review.py`,
    which sets VIRTUAL_ENV (and sometimes POETRY_ACTIVE) in this process'
    environment pointing at AssemblyZero's own venv. If those leak into the
    subprocess env when we shell out to `poetry install` / `poetry run
    pytest` against a TARGET repo's worktree, poetry treats the venv as
    already-activated and skips per-cwd resolution -- every audit then runs
    in AZ's venv instead of the target's own.

    Symptom that surfaced this: sqlalchemy/sqlite tracebacks in pytest
    output for dispatch/Talos/patent-general (none of which depend on
    sqlalchemy), all routed through `assemblyzero-tools-{hash}` venv paths.
    """
    env = os.environ.copy()
    env.pop("VIRTUAL_ENV", None)
    env.pop("POETRY_ACTIVE", None)
    return env


def _has_dev_group(pyproject: Path) -> bool:
    """Return True iff pyproject.toml declares a `dev` poetry group.

    Recognizes [tool.poetry.group.dev] (Poetry-native) and
    [dependency-groups] dev = [...] (PEP 735).
    """
    with pyproject.open("rb") as f:
        data = tomllib.load(f)
    poetry_groups = data.get("tool", {}).get("poetry", {}).get("group", {})
    if "dev" in poetry_groups:
        return True
    return "dev" in data.get("dependency-groups", {})


def install_deps(worktree: Path) -> bool:
    """Install project dependencies, plus the `dev` group when present.

    AssemblyZero declares pytest under PEP 735 `[dependency-groups]
    dev = [...]`, which `poetry install` (no flags) does NOT include by
    default -- the audit venv ends up without pytest and every test run
    fails with `ModuleNotFoundError: No module named 'pytest'` regardless
    of whether the dep upgrade actually broke anything. The fleet CI
    workflow already passes `--with dev` for the same reason; mirroring
    that here makes the audit venv match production.

    `--with dev` is only added when pyproject.toml actually declares the
    group. Poetry errors out (does NOT warn) on `--with dev` when the
    group is absent, so passing it unconditionally defers any repo that
    has no dev group for a tool-level reason unrelated to the dep upgrade.

    `--no-root` skips installing the project itself, only its dependencies.
    Required for decorative-deps repos like dependabot-honeypot that have
    no src/ directory -- without --no-root, every fleet sweep on such a
    PR errors with "No file/folder found for package <name>". The fleet
    sweep tests dep upgrades, not the project's own code, so installing
    the root is unnecessary in every case.
    """
    pyproject = worktree / "pyproject.toml"
    if not pyproject.exists():
        return True  # Not a poetry project
    cmd = ["poetry", "install", "--no-root"]
    if _has_dev_group(pyproject):
        cmd.extend(["--with", "dev"])
    result = run(cmd, cwd=str(worktree), timeout=POETRY_INSTALL_TIMEOUT_S,
                 env=_clean_subprocess_env())
    return result.returncode == 0


# ---------------------------------------------------------------------------
# Test gate
# ---------------------------------------------------------------------------

def run_tests(worktree: Path) -> int:
    # #1371: PYTHONDONTWRITEBYTECODE=1 stops Python from writing
    # __pycache__/*.pyc next to the target repo's test files during the audit
    # run. Without it, any target repo whose .gitignore lacks __pycache__/
    # ends up with untracked .pyc files that dirty the audit worktree, making
    # `git worktree remove` (no --force) refuse and leak the worktree.
    pytest_env = _clean_subprocess_env()
    pytest_env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = run(["poetry", "run", "pytest", "-q", "--tb=short"],
                 cwd=str(worktree), timeout=PYTEST_TIMEOUT_S, env=pytest_env)
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

    Issue #1399: 'blocked' is NOT a terminal state. It usually means
    cerberus-az has not approved yet (the body edit in inject_no_issue
    invalidates cerberus's prior approval; cerberus then re-evaluates,
    typically within 30s-300s but with a tail past 5+ minutes). Pre-#1399
    the loop bailed after the SECOND poll of 'blocked' (~10s total), which
    silently failed every PR where cerberus took longer than one
    POLL_INTERVAL_S cycle to arrive — #84 and #47 on 2026-05-29/30 are
    the documented cases. The fix: poll through 'blocked' until the full
    MERGEABLE_TIMEOUT_S budget is exhausted. The caller reclassifies a
    non-'dirty' timeout as deferred (not errored) since the approval
    persists and the next run picks the PR up cleanly.
    """
    start = time.time()
    deadline = start + MERGEABLE_TIMEOUT_S
    while time.time() < deadline:
        result = run(["gh", "api", f"repos/{repo}/pulls/{pr_number}",
                      "--jq", ".mergeable_state"])
        state = (result.stdout or "").strip().strip('"')
        elapsed = int(time.time() - start)
        print(f"  mergeable_state: {state} (elapsed {elapsed}s)")
        if state in ("clean", "unstable"):
            return True
        if state == "dirty":
            return False  # merge conflict; waiting won't help
        time.sleep(POLL_INTERVAL_S)
    elapsed = int(time.time() - start)
    print(f"  mergeable_state: timed out after {elapsed}s "
          f"(MERGEABLE_TIMEOUT_S={MERGEABLE_TIMEOUT_S})")
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


# #1400: file patterns that mean "this PR could affect the Python test
# environment" -- standard manifests, lockfiles, and any Python source.
# Order matters only for readability; we check every changed file.
_PYTHON_RELEVANT_FILES = frozenset({
    "pyproject.toml",
    "poetry.lock",
    "setup.py",
    "setup.cfg",
    "Pipfile",
    "Pipfile.lock",
})


def pr_touches_python(pr_number: int, repo: str) -> bool:
    """#1400: True iff the PR's diff includes any Python-relevant file.

    Used by _process_pr_inside_worktree to decide whether to run the
    `poetry install` + `pytest` gate. A PR that does not touch any Python
    file or manifest cannot break the Python venv by construction --
    running the Python gate on it is wasted work AND creates false
    negatives when the worktree's lockfile has any pre-existing issue
    unrelated to the PR (the bug that bit honeypot's docker PRs #52, #53,
    #55 on 2026-05-29/30 -- their branches predate the LLM-cleanup
    martymcenroe/dependabot-honeypot#67/#71/#72/#76 and still carry the
    jiter manifest, but the docker bump itself cannot have caused that).

    Conservative on failure: if `gh pr diff` cannot list the changed
    files, return True so the Python gate still runs (no false-pass).
    """
    result = run(
        ["gh", "pr", "diff", str(pr_number), "--repo", repo, "--name-only"],
        quiet_on_failure=True,
    )
    if result.returncode != 0:
        print(f"  WARNING: could not list PR #{pr_number} changed files "
              f"(gh pr diff --name-only failed); running Python gate as "
              f"the safe default (#1400).",
              file=sys.stderr)
        return True
    files = [f.strip() for f in (result.stdout or "").splitlines() if f.strip()]
    for f in files:
        # Any *.py file anywhere in the repo.
        if f.endswith(".py"):
            return True
        # Any known Python manifest/lockfile at any path depth.
        basename = f.rsplit("/", 1)[-1]
        if basename in _PYTHON_RELEVANT_FILES:
            return True
        # requirements.txt, requirements-dev.txt, requirements/*.txt, etc.
        if basename.startswith("requirements") and basename.endswith(".txt"):
            return True
    return False


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def cleanup_worktree(target_repo: Path, worktree: Path, branch: str) -> bool:
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

    # #1377: do NOT `git restore .` here. The two historical sources of
    # worktree dirt are both fixed at the source now: the inventory-node
    # cwd-write (#1155, raises instead of scribbling on cwd) and pytest
    # bytecode caching (#1371, PYTHONDONTWRITEBYTECODE=1 in run_tests).
    # `git restore <path>` is a banned working-tree-destroying pattern
    # (Projects/CLAUDE.md) -- it silently discards any uncommitted change.
    # If a worktree is unexpectedly dirty after those fixes, that is a NEW
    # writer we want to SEE, not silently wipe. Surface it loudly and let
    # the non-`--force` `git worktree remove` below refuse (its failure is
    # already reported LOUDLY). The audit run makes no commits -- gh pr
    # checkout uses --detach (#1107) -- so a dirty tree is always a bug to
    # diagnose, never expected state.
    if worktree.exists():
        dirty = run(["git", "-C", str(worktree), "status", "--porcelain"],
                    quiet_on_failure=True)
        dirt = (dirty.stdout or "").strip()
        if dirt:
            print(
                f"  CLEANUP WARNING: audit worktree {worktree} is dirty before "
                f"removal. This is unexpected (the audit run commits nothing and "
                f"the known dirt sources are fixed: #1155 inventory, #1371 .pyc). "
                f"Investigate the writer -- do NOT add a `git restore`. "
                f"`git worktree remove` (no --force) will refuse below if this "
                f"dirt blocks it.\n"
                f"  git status --porcelain:\n"
                + "\n".join(f"    {line}" for line in dirt.splitlines()),
                file=sys.stderr,
            )

    wt_remove = run(["git", "-C", str(target_repo), "worktree", "remove", str(worktree)])
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

    br_delete = run(["git", "-C", str(target_repo), "branch", "-d", branch])
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


def check_for_orphan_worktrees(target_repo: Path) -> list[str]:
    """#1133/#1357/#1360: enumerate pre-existing dependabot worktrees in
    `target_repo`'s git that match BOTH the script's path pattern
    (`{target_name}-dependabot-N`) AND a paired `dependabot-audit-N`
    branch. Returns list of orphan worktree paths. Empty list = clean.

    The branch is the strong-provenance signal. `create_audit_worktree`
    creates worktrees via `git worktree add ... -b dependabot-audit-N`,
    so the branch always exists when this script leaves a worktree behind.
    `cleanup_worktree` deletes the branch via `git branch -d`. A real
    leaked worktree from a crashed run therefore has BOTH the matching
    path AND the matching branch; if the branch is missing, the worktree
    is not this script's orphan.

    #1360: the canary is now per-repo — each fleet repo's git is scanned
    separately rather than one global scan against AssemblyZero's git
    that aborted the whole fleet on per-repo state.

    Before #1357 the canary matched on path name alone (`if prefix in
    Path(path).name`), which false-positived on any worktree whose name
    happened to contain `{target_name}-dependabot-` regardless of origin.
    """
    # Provenance step: enumerate the script's own audit branches. If
    # none exist, there cannot be any real script orphans.
    branch_result = run([
        "git", "-C", str(target_repo), "branch", "--list",
        "--format=%(refname:short)", "dependabot-audit-*",
    ])
    if branch_result.returncode != 0:
        # Diagnostic-on-diagnostic failure: don't block the script.
        return []
    audit_ns: set[str] = set()
    for raw in branch_result.stdout.splitlines():
        name = raw.strip()
        if not name.startswith("dependabot-audit-"):
            continue
        n_str = name[len("dependabot-audit-"):]
        if n_str.isdigit():
            audit_ns.add(n_str)
    if not audit_ns:
        return []

    # Now pair worktrees against the audit-branch set.
    result = run(["git", "-C", str(target_repo), "worktree", "list", "--porcelain"])
    if result.returncode != 0:
        return []
    orphans: list[str] = []
    prefix = f"{target_repo.name}-dependabot-"
    for line in result.stdout.splitlines():
        if not line.startswith("worktree "):
            continue
        path = line[len("worktree "):].strip()
        name = Path(path).name
        if not name.startswith(prefix):
            continue
        n_str = name[len(prefix):]
        if n_str in audit_ns:
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

    # #1400: only run the Python gate (poetry install + pytest) when the
    # PR actually touches a Python file or manifest. A Dockerfile-only
    # bump, an npm bump, or a github-actions workflow pin cannot break
    # the Python venv by construction; running the Python gate on those
    # PRs is wasted work and creates false-negative deferrals when the
    # PR's branch has any pre-existing lockfile issue (e.g. honeypot's
    # docker PRs #52/#53/#55 carried the pre-cleanup jiter manifest).
    if pr_touches_python(pr.number, repo):
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

        # #1397: exit 5 = "no tests collected" is a normal pytest result for
        # test-less repos (decorative-deps honeypots, scaffold stubs), not a
        # failure. A dep bump cannot turn N>0 tests into 0, so exit 5 means
        # "this repo has no test suite" -- safe to treat as pass for the
        # dep-bump gate. Log loudly so the run output reflects the decision.
        if exit_code == PYTEST_EXIT_NO_TESTS_COLLECTED:
            print("  pytest: no tests collected (exit 5) -- treating as PASS "
                  "(decorative-deps repo with no test suite)")
            exit_code = 0
    else:
        # #1400: PR did not touch any Python-relevant file. Skip the Python
        # gate entirely and treat as pass for the dep-bump gate. The PR
        # can only have changed Docker / npm / workflow / docs content;
        # those cannot break a Python venv. Eventual follow-up: add
        # ecosystem-specific gates here (npm test, docker build, etc.)
        # if/when needed -- the honeypot's decorative-deps purpose means
        # "skip gate, pass through" is currently the right semantic.
        print(f"  PR #{pr.number} touches no Python-relevant files -- "
              f"skipping poetry install + pytest gate (#1400). "
              f"Treating as PASS for the dep-bump gate.")
        exit_code = 0

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
        if final_state == "dirty":
            print(f"  ERROR: mergeable_state '{final_state}' -- merge conflict, "
                  f"requesting @dependabot rebase. Approval persists; next run "
                  f"re-evaluates post-rebase.")
            request_dependabot_rebase(pr.number, repo)
            return "errored"
        # #1399: blocked/behind/unknown after timeout = state is genuinely
        # in-flight (cerberus arrival tail, required check still running,
        # base branch lag, etc.), NOT a permanent failure. Classify as
        # "deferred" so the summary shows "try again next run" instead of
        # "investigate this error". The approval persists; the next run
        # finds the PR mergeable and merges it. This is the actual fix
        # for the #84 (2026-05-29) and #47 (2026-05-30) cases where the
        # tool reported errored but a re-run merged the PR within seconds.
        print(f"  DEFER: mergeable_state '{final_state}' after wait timeout -- "
              f"likely cerberus-arrival tail or pending check. Approval "
              f"persists; next run will re-evaluate. (See #1399.)")
        return "deferred"

    if not squash_merge(pr.number, repo):
        print("  ERROR: merge failed")
        return "errored"

    return "merged"


def process_pr(pr: PRInfo, repo: str, target_repo: Path) -> str:
    """Process a single PR. Returns 'merged', 'deferred', or 'errored'.

    #1360: `target_repo` is the local clone of the PR's repo. Pre-#1360
    this was `main_repo` (always AssemblyZero), which forced foreign
    PR content into AZ's git.

    #1133: cleanup is wrapped in try/finally so it runs on every exit
    path -- normal return, sub-helper return, OR exception (Ctrl-C,
    subprocess timeout, network blip). The pre-#1133 design only
    covered explicit return statements, so any exception leaked the
    worktree.
    """
    print(f"\n=== PR #{pr.number}: {pr.title} ===")

    if not verify_author(pr):
        return "errored"

    worktree, branch = create_audit_worktree(target_repo, pr.number)
    if worktree is None:
        # #1370: worktree-add failed (e.g. an orphan already occupies the
        # path). create_audit_worktree already printed the diagnostic.
        # Record this PR as errored and let the sweep continue -- do NOT
        # enter the cleanup try/finally below with a None worktree.
        return "errored"

    try:
        return _process_pr_inside_worktree(pr, repo, worktree)
    finally:
        cleanup_ok = cleanup_worktree(target_repo, worktree, branch)
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

def resolve_target_repo_dir(repo_full: str, default_parent: Path) -> Path | None:
    """#1360: resolve the local clone path for a fleet repo.

    Returns Path to the local clone, or None if not found. Lookup:

    1. If `repo_full`'s short name matches the script's working-dir name
       (`default_parent.name`), return `default_parent` itself — this is
       the AZ-self path (or whatever repo the script runs from).
    2. Sibling-clone path: `default_parent.parent / <short_name>` with a
       `.git` directory or file inside.

    When neither is present the caller skips the repo with a clear
    diagnostic; the script does NOT silently fall back to hosting the
    foreign PR in `default_parent.git` (which was the pre-#1360 design
    that polluted AZ's `.git/objects` with every fleet repo's commits
    and caused cleanup failures on foreign untracked-file paths).
    """
    repo_name = repo_full.split("/")[-1]
    if repo_name == default_parent.name:
        return default_parent
    candidate = default_parent.parent / repo_name
    git_path = candidate / ".git"
    if git_path.exists():
        return candidate
    return None


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
    ignore_orphans: bool = False,
) -> dict[str, list[str]]:
    """Process all dependabot PRs in one repo, sequentially.

    #1360: `main_repo` here is only used as a parent-dir hint for finding
    the sibling clone of `repo`. The actual worktree machinery operates
    on the target repo's git, not main_repo's. Skips the repo entirely
    if no local clone is found.

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

    # #1360: resolve the target repo's local clone. Required for per-repo
    # worktree hosting (the foreign-PR-in-AZ-git pollution fix).
    target_repo = resolve_target_repo_dir(repo, main_repo)
    if target_repo is None:
        repo_name = repo.split("/")[-1]
        expected_path = main_repo.parent / repo_name
        print(
            f"  SKIP: no local clone for {repo} (looked at {expected_path}). "
            f"Clone the repo locally and re-run.",
            file=sys.stderr,
        )
        sub["errored"].append(f"{repo}#missing-clone")
        return sub

    # #1360/#1358: per-repo orphan canary. Pre-#1360 a global canary ran
    # once against AssemblyZero's worktree list and aborted the whole
    # fleet on per-repo state. Now each repo's git is scanned independently
    # — an orphan on dispatch blocks only dispatch's PRs, AZ proceeds.
    orphans = check_for_orphan_worktrees(target_repo)
    if orphans:
        print(
            f"  WARNING: pre-existing dependabot worktrees on "
            f"{target_repo.name}:",
            file=sys.stderr,
        )
        for o in orphans:
            print(f"    {o}", file=sys.stderr)
        if not ignore_orphans:
            print(
                f"  SKIP: {repo} this run. Resolve the orphans, then re-run. "
                f"Pass --ignore-orphans to override.",
                file=sys.stderr,
            )
            sub["errored"].append(f"{repo}#orphan-worktrees")
            return sub
        print(
            f"  proceeding anyway because --ignore-orphans was set",
            file=sys.stderr,
        )

    try:
        prs = list_dependabot_prs(repo)
    except PRListError as e:
        # #1370: a PR-list failure for this repo must not abort the whole
        # fleet sweep. Record it as errored and move on; other repos'
        # results still aggregate into the summary.
        print(f"  ERROR: {e}", file=sys.stderr)
        sub["errored"].append(f"{repo}#pr-list-failed")
        return sub
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
        status = process_pr(pr, repo, target_repo)
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

    # #1360: the orphan-worktree canary is now per-repo (inside
    # process_repo). Pre-#1360 there was a global canary here that
    # aborted the whole fleet on AssemblyZero's worktree state; that
    # blocked work across 16 repos every time AZ had even one orphan,
    # and conflated foreign-repo worktrees (which pre-#1360 lived in
    # AZ's namespace) with AZ's own orphans. See #1360 for the full
    # investigation; #1358 closed by this same change.

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

    # Wrap the worker dispatch + summary print in try/finally so the
    # Summary block ALWAYS prints, even when a stray SIGINT trips the
    # KeyboardInterrupt handler in __main__ before we'd otherwise
    # reach the summary section. Without this, the previous run
    # finished processing every PR but exited via SIGINT during
    # executor.shutdown() teardown, losing the entire Summary +
    # FLEET-COMPLETE marker. (Despite #1173's CREATE_NEW_PROCESS_GROUP
    # fix, SIGINT is still arriving from somewhere in the Windows
    # scheduled-task subprocess tree. Not worth chasing further --
    # belt-and-suspenders: print summary in finally.)
    try:
        # Issue #1093: parallelize across repos in --fleet mode. Single-
        # repo mode (or --workers=1) keeps the sequential path. Within a
        # repo, processing is always sequential.
        if args.fleet and args.workers > 1 and not args.dry_run:
            print(f"\nProcessing {len(repos)} repo(s) with {args.workers} "
                  f"worker(s)...")
            with ThreadPoolExecutor(max_workers=args.workers) as executor:
                futures = {
                    executor.submit(
                        process_repo, repo, main_repo, args.dry_run,
                        args.ignore_orphans,
                    ): repo
                    for repo in repos
                }
                for future in as_completed(futures):
                    repo = futures[future]
                    try:
                        sub = future.result()
                    except KeyboardInterrupt:
                        # Intentional Ctrl-C: let it propagate to __main__'s
                        # handler (sys.exit(130)). The finally below still
                        # prints the partial summary first.
                        raise
                    except BaseException as e:
                        # #1370: catch BaseException, not just Exception. A
                        # worker that raised SystemExit (e.g. a stray sys.exit
                        # deep in a helper) previously escaped an
                        # `except Exception` here, propagated out of the
                        # as_completed loop, and dropped every worker that
                        # hadn't been iterated yet -- truncating the summary
                        # even though those workers had completed. Recording
                        # the failing repo and continuing keeps the summary
                        # truthful regardless of the exception class.
                        print(f"\n  [ERROR] worker for {repo} raised: "
                              f"{type(e).__name__}: {e}")
                        sub = {"merged": [], "deferred": [], "errored": [repo]}
                    for k in ("merged", "deferred", "errored"):
                        results[k].extend(sub[k])
        else:
            for repo in repos:
                sub = process_repo(
                    repo, main_repo, args.dry_run, args.ignore_orphans,
                )
                for k in ("merged", "deferred", "errored"):
                    results[k].extend(sub[k])
    finally:
        # Dry-run skips the result-aggregation summary -- it only
        # listed PRs without taking action, so there's nothing to
        # summarize. Real runs always print Summary + FLEET-COMPLETE,
        # even if a stray SIGINT cut the processing loop short --
        # try/finally ensures we get the partial-results report.
        # No `return` here; return-in-finally would swallow any
        # KeyboardInterrupt being propagated up to __main__'s catch.
        if args.dry_run:
            print("\n(dry-run; exiting)")
        else:
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

            # Self-marked completion line. The PowerShell wrapper's OK/EXIT
            # marker write proved unreliable in the scheduled-task context
            # (Status:Ready, Last Result:0, but no | OK | line ever lands).
            # Printing a marker as the last line of the python tool's output
            # bypasses that -- cmd /c >> $LogFile captures it reliably, since
            # we already know the per-line streaming works. morning_status_tool
            # can grep for this marker as a secondary completion signal.
            end_stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(
                f"\n=== {end_stamp} | FLEET-COMPLETE | "
                f"merged={len(results['merged'])} "
                f"deferred={len(results['deferred'])} "
                f"errored={len(results['errored'])} ==="
            )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # SIGINT can reach the parent for two distinct reasons on
        # Windows: (a) the user actually pressed Ctrl-C, or (b) a
        # child subprocess crashed and its console-group event
        # propagated up. The old message blamed the user
        # unconditionally -- which is wrong, and was reported as
        # #1172 after multiple phantom interruptions during tonight's
        # fleet runs. After landing the _CREATION_FLAGS isolation,
        # case (b) should be largely eliminated, but the message
        # stays neutral so we don't lie if it ever does fire.
        print(
            "\nInterrupted (SIGINT received) -- shutting down "
            "cleanly. Worker threads will finish their current PR's "
            "cleanup. Next run resumes from this state.",
            file=sys.stderr,
        )
        sys.exit(130)
