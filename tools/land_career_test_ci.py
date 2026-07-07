#!/usr/bin/env python3
"""Land the career repo's test-runner CI workflow via the in-process classic PAT.

career #1262. The fine-grained PAT the agent uses cannot push files under
`.github/workflows/` (it lacks the `workflow` scope — see root CLAUDE.md
"When git push Is Rejected For Workflow Scope"). So the workflow file is landed
here through the GitHub Contents API using the admin-scope classic PAT, which
this process gpg-decrypts in-heap per ADR-0216 (#959): the PAT lives only as a
local variable inside the `with classic_pat_session()` block, is consumed by
`requests` directly, and is never written to env, argv, disk, or a log.

What it does (idempotent):
  1. If `.github/workflows/test.yml` already exists on main -> report + exit 0.
  2. Create branch `ci/test-workflow-1262` from main.
  3. PUT the workflow file on that branch via the Contents API.
  4. Open a PR ("Closes #1262"), poll until mergeable, squash-merge.
  5. Delete the remote branch. Local git is never touched (API only).

Usage (RUN THIS YOURSELF in your own Git Bash — never via an agent's Bash tool,
per the _pat_session operational rule):
    cd /c/Users/mcwiz/Projects/AssemblyZero
    poetry run python tools/land_career_test_ci.py            # live
    poetry run python tools/land_career_test_ci.py --dry-run  # preview, no writes

Requires ~/.secrets/classic-pat.gpg (one-time setup in _pat_session docstring)
and gpg-agent default-cache-ttl 0 (so a sibling's silent decrypt surfaces
pinentry).
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
REPO = "career"
GH_API = "https://api.github.com"
BRANCH = "ci/test-workflow-1262"
FILE_PATH = ".github/workflows/test.yml"
HTTP_TIMEOUT_S = 30
MERGE_POLL_ATTEMPTS = 30
MERGE_POLL_SLEEP_S = 10

# LF-only on purpose (authored with \n) — the Contents API stores bytes verbatim,
# so CRLF would land CRLF on origin. npm ci because dashboard/ has a package-lock.
# SCOPE: src/ + cli/ ONLY — the self-contained unit/driver tests. tests/api/* are
# live integration tests that hit the PRODUCTION API and require a key absent from
# CI, so the full `npm test` would be red (35 × HTTP 401) or pollute prod
# (career #1262 finding 2026-06-16). Those stay a local/manual concern.
WORKFLOW_YAML = """name: tests

on:
  push:
  pull_request:

jobs:
  vitest:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: dashboard
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
      - run: npm ci
      - run: npx playwright install --with-deps chromium
      # src/ + cli/ only — tests/api/* hit prod + need a key (career #1262).
      - run: npx vitest run src/ cli/
"""

PR_TITLE = "ci: run the self-contained vitest suite on push + PR (Closes #1262)"
PR_BODY = (
    "Closes #1262\n\n"
    "Adds a GitHub Actions workflow that runs the self-contained vitest tests "
    "(`vitest run src/ cli/`) on every push and pull request, with Playwright "
    "Chromium for the driver fixtures. Landed via the classic-PAT Contents API "
    "because the fine-grained PAT cannot push `.github/workflows/`.\n\n"
    "Scope: `tests/api/*` are excluded — they are live integration tests that hit "
    "the production API and require a key absent from CI, so the full `npm test` "
    "would be red (35 × HTTP 401) or write to prod (career #1262 finding).\n"
)


def _headers(pat: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def file_exists_on_main(pat: str) -> bool:
    r = requests.get(
        f"{GH_API}/repos/{OWNER}/{REPO}/contents/{FILE_PATH}",
        params={"ref": "main"},
        headers=_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code == 200:
        return True
    if r.status_code == 404:
        return False
    r.raise_for_status()
    return False


def main_sha(pat: str) -> str:
    r = requests.get(
        f"{GH_API}/repos/{OWNER}/{REPO}/git/ref/heads/main",
        headers=_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json()["object"]["sha"]


def ensure_branch(pat: str, sha: str) -> None:
    r = requests.post(
        f"{GH_API}/repos/{OWNER}/{REPO}/git/refs",
        headers=_headers(pat),
        json={"ref": f"refs/heads/{BRANCH}", "sha": sha},
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code == 422 and "already exists" in r.text.lower():
        print(f"  branch {BRANCH} already exists — reusing")
        return
    r.raise_for_status()
    print(f"  created branch {BRANCH} @ {sha[:8]}")


def put_file(pat: str) -> None:
    content_b64 = base64.b64encode(WORKFLOW_YAML.encode("utf-8")).decode("ascii")
    r = requests.put(
        f"{GH_API}/repos/{OWNER}/{REPO}/contents/{FILE_PATH}",
        headers=_headers(pat),
        json={
            "message": "ci: add vitest test-runner workflow (Closes #1262)",
            "content": content_b64,
            "branch": BRANCH,
        },
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    print(f"  committed {FILE_PATH} on {BRANCH}")


def open_pr(pat: str) -> int:
    r = requests.post(
        f"{GH_API}/repos/{OWNER}/{REPO}/pulls",
        headers=_headers(pat),
        json={"title": PR_TITLE, "head": BRANCH, "base": "main", "body": PR_BODY},
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    num = r.json()["number"]
    print(f"  opened PR #{num}")
    return num


def wait_mergeable(pat: str, num: int) -> bool:
    for i in range(1, MERGE_POLL_ATTEMPTS + 1):
        r = requests.get(
            f"{GH_API}/repos/{OWNER}/{REPO}/pulls/{num}",
            headers=_headers(pat),
            timeout=HTTP_TIMEOUT_S,
        )
        r.raise_for_status()
        state = r.json().get("mergeable_state")
        print(f"  [{i}/{MERGE_POLL_ATTEMPTS}] mergeable_state={state}")
        if state in ("clean", "unstable"):
            # `unstable` = mergeable, but a NON-required check is pending/failing.
            # This PR adds tests.yml (on: push), which fires on the feature-branch
            # push and shows as a non-required pending check on the PR, parking it
            # at `unstable` for the whole CI run — it never reaches `clean` inside a
            # sane poll budget. By the time the state is `unstable`, required review
            # + checks (Cerberus approval) are already satisfied, so merging is safe.
            # Mirrors fleet_delete_pr_sentinel.py + root CLAUDE.md gotcha #4.
            return True
        if state == "dirty":
            return False
        time.sleep(MERGE_POLL_SLEEP_S)
    return False


def merge_pr(pat: str, num: int) -> None:
    r = requests.put(
        f"{GH_API}/repos/{OWNER}/{REPO}/pulls/{num}/merge",
        headers=_headers(pat),
        json={"merge_method": "squash"},
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    print(f"  merged PR #{num}")


def delete_branch(pat: str) -> None:
    r = requests.delete(
        f"{GH_API}/repos/{OWNER}/{REPO}/git/refs/heads/{BRANCH}",
        headers=_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code in (204, 422, 404):
        print(f"  cleaned up remote branch {BRANCH}")
        return
    r.raise_for_status()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="Preview without any writes.")
    args = ap.parse_args()

    if args.dry_run:
        print("DRY-RUN — would land this workflow at "
              f"{OWNER}/{REPO}:{FILE_PATH} via branch {BRANCH} + PR (Closes #1262):\n")
        print(WORKFLOW_YAML)
        return 0

    with classic_pat_session() as pat:
        if file_exists_on_main(pat):
            print(f"{FILE_PATH} already exists on main — nothing to do.")
            return 0
        print(f"Landing {FILE_PATH} in {OWNER}/{REPO} ...")
        ensure_branch(pat, main_sha(pat))
        put_file(pat)
        num = open_pr(pat)
        if not wait_mergeable(pat, num):
            print(f"PR #{num} did not reach a clean mergeable state. "
                  f"Inspect it on GitHub; the branch + file are committed.",
                  file=sys.stderr)
            return 1
        merge_pr(pat, num)
        delete_branch(pat)
        print("Done. Test CI is live; #1262 closed by the merge.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
