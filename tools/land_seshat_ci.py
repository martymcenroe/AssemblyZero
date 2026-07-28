#!/usr/bin/env python3
"""Land Seshat's staged CI workflow (pytest + ruff) via the in-process classic PAT.

Seshat #3 / AssemblyZero #1854. The fine-grained PAT every agent session uses
cannot push files under `.github/workflows/` -- it lacks the `workflow` scope,
and that exclusion is load-bearing (ADR-0216 section 1: without it an agent
could edit its own pr-sentinel workflow to disable governance). So the workflow
file is landed here through the GitHub Contents API using the admin-scope
classic PAT, which this process gpg-decrypts in-heap per ADR-0216 (#959): the
PAT lives only as a local variable inside the `with classic_pat_session()`
block, is consumed by `requests` directly, and never reaches env, argv, disk,
or a log.

What it does (idempotent -- safe to re-run):
  1. If `.github/workflows/tests.yml` already exists on main -> report + exit 0.
  2. Create branch `ci/tests-workflow-3` from main.
  3. PUT the workflow file on that branch via the Contents API.
  4. DELETE the now-redundant staged copy at `docs/ci/tests.yml` on the same
     branch, so the repo does not carry two copies that can drift.
  5. Open a PR ("Closes #3"), WAIT for the new `tests` check to finish and
     report its conclusion, then squash-merge.
  6. Delete the remote branch. Local git is never touched (API only).

Step 5 deliberately waits for the workflow's own first run rather than merging
as soon as GitHub says `unstable`. This PR *adds* the check, and for
`pull_request` events GitHub evaluates the workflow from the merge ref -- so the
landing PR is the first real exercise of the CI being installed. Merging without
looking at that result would install an instrument without reading it, which is
the failure mode this fleet keeps filing issues about.

Usage (RUN THIS YOURSELF in your own Git Bash -- never via an agent's Bash tool,
per the _pat_session operational rule: a Python process spawned by an agent is
the agent's child, and its heap is theoretically readable while the PAT is in
scope):
    cd /c/Users/mcwiz/Projects/AssemblyZero
    poetry run python tools/land_seshat_ci.py            # live
    poetry run python tools/land_seshat_ci.py --dry-run  # preview, no writes

Requires ~/.secrets/classic-pat.gpg (one-time setup in the _pat_session
docstring) and gpg-agent default-cache-ttl 0, so a sibling's silent decrypt
attempt surfaces pinentry.
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
REPO = "Seshat"
GH_API = "https://api.github.com"
BRANCH = "ci/tests-workflow-3"
FILE_PATH = ".github/workflows/tests.yml"
STAGED_PATH = "docs/ci/tests.yml"
ISSUE = 3
CHECK_NAME = "tests"
HTTP_TIMEOUT_S = 30
MERGE_POLL_ATTEMPTS = 30
MERGE_POLL_SLEEP_S = 10
CHECK_POLL_ATTEMPTS = 40
CHECK_POLL_SLEEP_S = 15

PAT_REASON = "land Seshat CI workflow (pytest + ruff)"

# LF-only on purpose (authored with \n). The Contents API stores bytes verbatim,
# so CRLF here would land CRLF on origin and flip the whole file's line endings
# (root CLAUDE.md gotcha #3). This is the staged docs/ci/tests.yml content with
# its staging preamble removed -- that comment explained why the file lived in
# docs/ci/, which stops being true the moment it lands here.
WORKFLOW_YAML = """name: tests

on:
  pull_request:

jobs:
  python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pipx install poetry
      - run: poetry install
      - run: poetry run pytest tests/unit -q
      - run: poetry run ruff check src tests
"""

PR_TITLE = f"ci: run pytest + ruff on every PR (Closes #{ISSUE})"
PR_BODY = (
    f"Closes #{ISSUE}\n\n"
    "Moves the CI workflow staged at `docs/ci/tests.yml` into "
    "`.github/workflows/tests.yml`, and removes the staged copy so the repo "
    "does not carry two versions that can drift.\n\n"
    "Landed via the classic-PAT Contents API (ADR-0216) because the "
    "fine-grained PAT every agent session uses cannot push under "
    "`.github/workflows/` -- it lacks the `workflow` scope, and that exclusion "
    "is load-bearing.\n\n"
    "Prerequisite already merged: ruff was absent from `pyproject.toml`, so "
    "this workflow would have gone red on arrival with a command-not-found. "
    "Ruff is now present with an explicitly pinned rule set and all findings "
    "cleared (Seshat #26).\n\n"
    "This PR is itself the first exercise of the check it installs -- for "
    "`pull_request` events the workflow is evaluated from the merge ref, so "
    "`tests` runs here before the merge.\n"
)


def _headers(pat: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def get_file(pat: str, path: str, ref: str) -> dict | None:
    """Return the Contents-API record for `path` at `ref`, or None if absent."""
    r = requests.get(
        f"{GH_API}/repos/{OWNER}/{REPO}/contents/{path}",
        params={"ref": ref},
        headers=_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


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
        print(f"  branch {BRANCH} already exists -- reusing")
        return
    r.raise_for_status()
    print(f"  created branch {BRANCH} @ {sha[:8]}")


def put_workflow(pat: str) -> None:
    existing = get_file(pat, FILE_PATH, BRANCH)
    payload: dict[str, object] = {
        "message": f"ci: add pytest + ruff workflow (Closes #{ISSUE})",
        "content": base64.b64encode(WORKFLOW_YAML.encode("utf-8")).decode("ascii"),
        "branch": BRANCH,
    }
    if existing:
        # Re-run against a half-finished branch: update in place.
        payload["sha"] = existing["sha"]
    r = requests.put(
        f"{GH_API}/repos/{OWNER}/{REPO}/contents/{FILE_PATH}",
        headers=_headers(pat),
        json=payload,
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    print(f"  committed {FILE_PATH} on {BRANCH}")


def delete_staged_copy(pat: str) -> None:
    staged = get_file(pat, STAGED_PATH, BRANCH)
    if staged is None:
        print(f"  {STAGED_PATH} already absent on {BRANCH} -- nothing to remove")
        return
    r = requests.delete(
        f"{GH_API}/repos/{OWNER}/{REPO}/contents/{STAGED_PATH}",
        headers=_headers(pat),
        json={
            "message": f"chore: drop staged CI copy now that it is live (Closes #{ISSUE})",
            "sha": staged["sha"],
            "branch": BRANCH,
        },
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    print(f"  removed staged {STAGED_PATH} on {BRANCH}")


def find_open_pr(pat: str) -> int | None:
    r = requests.get(
        f"{GH_API}/repos/{OWNER}/{REPO}/pulls",
        params={"head": f"{OWNER}:{BRANCH}", "state": "open"},
        headers=_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    prs = r.json()
    return prs[0]["number"] if prs else None


def open_pr(pat: str) -> int:
    existing = find_open_pr(pat)
    if existing:
        print(f"  reusing open PR #{existing}")
        return existing
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


def head_sha(pat: str, num: int) -> str:
    r = requests.get(
        f"{GH_API}/repos/{OWNER}/{REPO}/pulls/{num}",
        headers=_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json()["head"]["sha"]


def wait_for_ci(pat: str, sha: str) -> str:
    """Wait for the newly-installed `tests` check and return its conclusion.

    Returns the conclusion string ("success", "failure", ...), or "absent" if
    the check never appeared within the poll budget. Never raises on a failing
    check -- the caller decides what to do, and a red result is information,
    not an error in this script.
    """
    for i in range(1, CHECK_POLL_ATTEMPTS + 1):
        r = requests.get(
            f"{GH_API}/repos/{OWNER}/{REPO}/commits/{sha}/check-runs",
            headers=_headers(pat),
            timeout=HTTP_TIMEOUT_S,
        )
        r.raise_for_status()
        runs = {c["name"]: c for c in r.json().get("check_runs", [])}
        run = runs.get(CHECK_NAME)
        if run is None:
            print(f"  [{i}/{CHECK_POLL_ATTEMPTS}] {CHECK_NAME}: not registered yet")
        elif run["status"] == "completed":
            print(f"  [{i}/{CHECK_POLL_ATTEMPTS}] {CHECK_NAME}: {run['conclusion']}")
            return run["conclusion"] or "unknown"
        else:
            print(f"  [{i}/{CHECK_POLL_ATTEMPTS}] {CHECK_NAME}: {run['status']}")
        time.sleep(CHECK_POLL_SLEEP_S)
    return "absent"


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
            # `unstable` = mergeable, but a NON-required check is pending or
            # failing. `tests` is brand new and therefore not yet a required
            # check, so it parks the PR at `unstable`. By this point required
            # review (Cerberus) and pr-sentinel are already satisfied, and the
            # caller has separately inspected the `tests` conclusion.
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
    ap.add_argument(
        "--merge-on-red",
        action="store_true",
        help="Merge even if the new tests check fails. Default is to stop and report.",
    )
    args = ap.parse_args()

    if args.dry_run:
        print(
            f"DRY-RUN -- would land {OWNER}/{REPO}:{FILE_PATH} via branch "
            f"{BRANCH} + PR (Closes #{ISSUE}), and remove {STAGED_PATH}:\n"
        )
        print(WORKFLOW_YAML)
        return 0

    with classic_pat_session(reason=PAT_REASON) as pat:
        if get_file(pat, FILE_PATH, "main"):
            print(f"{FILE_PATH} already exists on main -- nothing to do.")
            return 0

        print(f"Landing {FILE_PATH} in {OWNER}/{REPO} ...")
        ensure_branch(pat, main_sha(pat))
        put_workflow(pat)
        delete_staged_copy(pat)
        num = open_pr(pat)

        print(f"Waiting for the new `{CHECK_NAME}` check on PR #{num} ...")
        conclusion = wait_for_ci(pat, head_sha(pat, num))

        if conclusion == "success":
            print("  CI is green on its first run.")
        elif conclusion == "absent":
            print(
                f"  `{CHECK_NAME}` never registered within the poll budget. The "
                f"branch and PR exist; inspect PR #{num} on GitHub.",
                file=sys.stderr,
            )
            return 1
        elif not args.merge_on_red:
            print(
                f"  `{CHECK_NAME}` concluded `{conclusion}`. NOT merging.\n"
                f"  The workflow landed on the branch and PR #{num} is open, so "
                f"the failure is visible and fixable there. Re-run with "
                f"--merge-on-red to override.",
                file=sys.stderr,
            )
            return 1

        if not wait_mergeable(pat, num):
            print(
                f"PR #{num} did not reach a mergeable state. Inspect it on "
                f"GitHub; the branch and file are committed.",
                file=sys.stderr,
            )
            return 1
        merge_pr(pat, num)
        delete_branch(pat)
        print(f"Done. CI is live on {OWNER}/{REPO}; #{ISSUE} closed by the merge.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
