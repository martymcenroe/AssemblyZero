#!/usr/bin/env python3
"""Land Hermes .github/workflows/ci.yml via the classic-PAT Contents API.

martymcenroe/Hermes#536.

Hermes has no CI workflow that runs its vitest suites -- PRs merge on the
auto-reviewer's issue-reference check alone, with no test verification. This
tool adds `.github/workflows/ci.yml` (root + dashboard vitest jobs, Node 22,
non-blocking).

WHY A SCRIPT INSTEAD OF `git push`:
The fine-grained PAT used for normal Hermes work cannot create or update files
under `.github/workflows/` (GitHub rejects it: "without `workflow` scope").
ADR-0216 (in-process classic-PAT decryption) is the sanctioned path: the
classic PAT is gpg-decrypted inside THIS Python process, used for REST calls,
and never written to env / argv / disk. The change lands via the Contents API
(PUT) + a PR + an API squash-merge.

REQUIRED CLASSIC-PAT SCOPES: repo (full) + workflow.

OPERATIONAL RULE (ADR-0216, load-bearing):
    The OPERATOR runs this script in their own Git Bash. An agent must NEVER
    invoke it via its Bash tool -- the spawned Python process would be the
    agent's child and its heap (holding the decrypted PAT for a few seconds)
    is theoretically agent-readable.

    Also confirm ~/.gnupg/gpg-agent.conf has `default-cache-ttl 0` /
    `max-cache-ttl 0` (then `gpgconf --kill gpg-agent`) so a sibling process
    cannot silently decrypt the PAT while a passphrase is cached.

USAGE (run from the AssemblyZero repo so poetry resolves `requests`):
    cd /c/Users/mcwiz/Projects/AssemblyZero
    poetry run python tools/hermes_add_ci_workflow.py            # dry-run
    poetry run python tools/hermes_add_ci_workflow.py --apply    # land it

Default is dry-run (prints the plan, no mutations). `--apply` performs the
mutation. The source contains no command from the universal CLAUDE.md
"Banned commands (ALWAYS)" table (no force-push, no --admin, no git reset),
so the canonical `--apply` gate applies -- NOT `--execute`.

Idempotent: skips if ci.yml already exists on main; skips if an open PR with
the same title already exists.
"""

from __future__ import annotations

import argparse
import base64
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pat_session import classic_pat_session  # noqa: E402

OWNER = "martymcenroe"
REPO = "Hermes"
GH_API = "https://api.github.com"
WORKFLOW_PATH = ".github/workflows/ci.yml"
BRANCH = "536-ci-workflow"
ISSUE_NUMBER = 536
PR_TITLE = "ci: run the vitest suites on push and PR (Closes #536)"
HTTP_TIMEOUT_S = 30
POLL_INTERVAL_S = 10
MERGEABLE_TIMEOUT_S = 900

# The workflow file content. Defined inline as a Python str (LF line endings),
# so there is no CRLF-from-Windows-working-tree hazard (ADR-0216 gotcha #3).
CI_YML = """name: CI

# Runs the vitest suites on every push to main and every PR targeting main.
# NON-BLOCKING by default (not a required status check); making it gating is a
# separate branch-protection follow-up (#644). Playwright e2e is intentionally
# excluded -- `npm test` runs `vitest run` only, never `test:e2e`.
#
# Added via tools/hermes_add_ci_workflow.py (classic-PAT Contents API,
# ADR-0216) because fine-grained PATs cannot push .github/workflows/*.

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read

jobs:
  root-tests:
    name: Root suite (vitest)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: 'npm'
      - run: npm ci
      - run: npm test

  dashboard-tests:
    name: Dashboard suite (vitest)
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: dashboard
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: 'npm'
          cache-dependency-path: dashboard/package-lock.json
      - run: npm ci
      - run: npm test
"""

PR_BODY = """## Summary

Adds `.github/workflows/ci.yml` so the vitest suites actually run in CI on
every push to `main` and every PR targeting `main`. Until now Hermes had no
test-running workflow -- PRs merged on the auto-reviewer's `issue-reference`
check alone, with no test verification (the resume claim of "N tests in CI"
had no real source of truth).

## Jobs
- **Root suite (vitest)** -- `npm ci` + `npm test` (`vitest run`) at repo root.
- **Dashboard suite (vitest)** -- `npm ci` + `npm test` in `dashboard/`.

Both pin Node 22 (the repo has no `.nvmrc`/engines). Playwright e2e is excluded
-- `npm test` runs `vitest run` only.

## Non-blocking for now
Not added to branch protection as a required check yet -- a green run across
real PRs should be observed before it gates merges, to avoid a flaky-on-arrival
required check wedging the queue. follow-up: #644.

## How this landed
Via the classic-PAT Contents API (ADR-0216), because fine-grained PATs cannot
push files under `.github/workflows/`. Script: `tools/hermes_add_ci_workflow.py`
in AssemblyZero.

Closes #536
"""


def _headers(pat: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def file_exists_on_main(pat: str) -> bool:
    r = requests.get(
        f"{GH_API}/repos/{OWNER}/{REPO}/contents/{WORKFLOW_PATH}",
        params={"ref": "main"},
        headers=_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code == 404:
        return False
    r.raise_for_status()
    return True


def find_open_pr(pat: str) -> int | None:
    r = requests.get(
        f"{GH_API}/repos/{OWNER}/{REPO}/pulls",
        params={"state": "open", "per_page": 100},
        headers=_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    for pr in r.json():
        if pr.get("title", "") == PR_TITLE or pr.get("head", {}).get("ref") == BRANCH:
            return pr["number"]
    return None


def main_head_sha(pat: str) -> str:
    r = requests.get(
        f"{GH_API}/repos/{OWNER}/{REPO}/git/refs/heads/main",
        headers=_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json()["object"]["sha"]


def create_branch(sha: str, pat: str) -> None:
    r = requests.post(
        f"{GH_API}/repos/{OWNER}/{REPO}/git/refs",
        headers=_headers(pat),
        json={"ref": f"refs/heads/{BRANCH}", "sha": sha},
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code == 422:
        # Ref already exists from a prior partial run -- reuse it.
        print(f"  branch {BRANCH} already exists, reusing")
        return
    r.raise_for_status()


def put_file(pat: str) -> None:
    content_b64 = base64.b64encode(CI_YML.encode("utf-8")).decode("ascii")
    r = requests.put(
        f"{GH_API}/repos/{OWNER}/{REPO}/contents/{WORKFLOW_PATH}",
        headers=_headers(pat),
        json={
            "message": "ci: add vitest CI workflow (Closes #536)",
            "content": content_b64,
            "branch": BRANCH,
        },
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()


def create_pr(pat: str) -> int:
    r = requests.post(
        f"{GH_API}/repos/{OWNER}/{REPO}/pulls",
        headers=_headers(pat),
        json={"title": PR_TITLE, "head": BRANCH, "base": "main", "body": PR_BODY},
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json()["number"]


def wait_for_mergeable(pr_number: int, pat: str) -> str:
    """Poll until mergeable. Accepts 'clean' OR 'unstable'.

    'unstable' matters here: the new ci.yml runs on its own PR, so while those
    non-required jobs are pending/failing the state is 'unstable' -- which a
    squash merge still accepts (ADR-0216 gotcha #4, self-referential check).
    'blocked' is a WAIT state, NOT terminal: right after the PR opens it just
    means Cerberus-AZ has not posted its approving review yet (typically
    10-30s, occasionally minutes). Keep polling THROUGH 'blocked' until
    'clean'/'unstable' or the timeout. Only 'dirty' (a real merge conflict)
    fails immediately -- waiting cannot resolve a conflict.

    BUGFIX: an earlier version returned on the FIRST 'blocked' (after ~10s) and
    left the PR open + unmerged -- it bailed before Cerberus ever approved.
    That was the failure on PR #648.
    """
    deadline = time.time() + MERGEABLE_TIMEOUT_S
    last = "unknown"
    while time.time() < deadline:
        r = requests.get(
            f"{GH_API}/repos/{OWNER}/{REPO}/pulls/{pr_number}",
            headers=_headers(pat),
            timeout=HTTP_TIMEOUT_S,
        )
        r.raise_for_status()
        last = r.json().get("mergeable_state") or "unknown"
        if last in ("clean", "unstable"):
            return last
        if last == "dirty":
            return last
        print(f"  mergeable_state={last}, waiting {POLL_INTERVAL_S}s for Cerberus approval...")
        time.sleep(POLL_INTERVAL_S)
    return last


def merge_pr(pr_number: int, pat: str) -> str:
    r = requests.put(
        f"{GH_API}/repos/{OWNER}/{REPO}/pulls/{pr_number}/merge",
        headers=_headers(pat),
        json={"merge_method": "squash"},
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json().get("sha", "")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Perform the mutation. Default is dry-run (plan only).",
    )
    args = parser.parse_args()

    with classic_pat_session() as pat:
        if file_exists_on_main(pat):
            print(f"{WORKFLOW_PATH} already exists on main -- nothing to do.")
            return 0

        existing = find_open_pr(pat)
        if existing is not None:
            if not args.apply:
                print(f"Open PR #{existing} already adds this workflow. "
                      f"Re-run with --apply to wait for it to become mergeable and merge it.")
                return 0
            # RESUME: a prior run opened the PR + pushed the file but did not
            # merge (e.g. the pre-bugfix early-bail on 'blocked'). Finish it.
            print(f"Resuming: open PR #{existing} already exists -- waiting for mergeable...")
            state = wait_for_mergeable(existing, pat)
            if state not in ("clean", "unstable"):
                print(f"  PR #{existing} not mergeable (state={state}). Retained for manual review.")
                return 1
            merge_sha = merge_pr(existing, pat)
            print(f"  PR #{existing} squash-merged at {merge_sha[:8]}  OK")
            return 0

        if not args.apply:
            print("DRY-RUN (no changes). Would:")
            print(f"  1. branch {BRANCH} from main HEAD")
            print(f"  2. PUT {WORKFLOW_PATH} ({len(CI_YML)} bytes) via Contents API")
            print(f"  3. open PR '{PR_TITLE}'")
            print("  4. wait for mergeable (clean/unstable), then squash-merge")
            print("Re-run with --apply to land it.")
            return 0

        print(f"Landing {WORKFLOW_PATH} on {OWNER}/{REPO}...")
        sha = main_head_sha(pat)
        create_branch(sha, pat)
        put_file(pat)
        pr_number = create_pr(pat)
        print(f"  opened PR #{pr_number}")

        state = wait_for_mergeable(pr_number, pat)
        if state not in ("clean", "unstable"):
            print(f"  PR #{pr_number} not mergeable (state={state}). "
                  f"Branch + PR retained for manual review.")
            return 1

        merge_sha = merge_pr(pr_number, pat)
        print(f"  PR #{pr_number} squash-merged at {merge_sha[:8]}  OK")
        print()
        print("Done. Pull main locally:  git checkout main && git pull")
        return 0


if __name__ == "__main__":
    sys.exit(main())
