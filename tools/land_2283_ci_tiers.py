#!/usr/bin/env python3
"""Land AssemblyZero's CI tier wiring via the in-process classic PAT (#2283).

The fine-grained PAT the agent uses cannot push files under `.github/workflows/`
(it lacks the `workflow` scope -- see root CLAUDE.md "When git push Is Rejected
For Workflow Scope"). So `ci.yml` is landed here through the GitHub Contents API
using the admin-scope classic PAT, which this process gpg-decrypts in-heap per
ADR-0216 (#959): the PAT lives only as a local variable inside the
`with classic_pat_session()` block, is consumed by `requests` directly, and is
never written to env, argv, disk, or a log.

The workflow is embedded in this file as WORKFLOW_YAML rather than read from
disk, so the script is self-contained and the working tree stays clean. What it
changes:

  - integration runs BEFORE merge instead of only after merge to main
  - e2e runs at all (it never has)
  - adversarial runs at all (it never has); with no Gemini credential in the
    environment its autouse fixture skips, so the step passes with `1 skipped`

What it does (idempotent):
  1. Compare the embedded workflow to what is on main. Identical -> exit 0.
  2. Create branch `2283-ci-tiers` from main (reuses it if it exists).
  3. PUT the file on that branch via the Contents API, passing the existing
     blob sha because this is an UPDATE, not a create.
  4. Open a PR ("Closes #2283"), poll until mergeable, squash-merge.
  5. Delete the remote branch. Local git is never touched (API only).

This waits for `clean` and will NOT merge on `unstable`. That is deliberate and
is the opposite of the self-referential case in `fleet_delete_pr_sentinel.py`:
the whole point of this change is that the new tiers run, and this PR is the
first thing they run on. A red new tier here is the result, not an obstacle --
investigate it rather than merging past it.

Usage (RUN THIS YOURSELF in your own Git Bash -- never via an agent's Bash tool,
per the _pat_session operational rule):
    cd /c/Users/mcwiz/Projects/AssemblyZero
    poetry run python tools/land_2283_ci_tiers.py --dry-run   # preview, no writes
    poetry run python tools/land_2283_ci_tiers.py             # live

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
REPO = "AssemblyZero"
GH_API = "https://api.github.com"
BRANCH = "2283-ci-tiers"
FILE_PATH = ".github/workflows/ci.yml"
HTTP_TIMEOUT_S = 30
MERGE_POLL_ATTEMPTS = 40
MERGE_POLL_SLEEP_S = 15

COMMIT_MESSAGE = (
    "ci: run every test tier before merge, not just unit (Closes #2283)"
)
PR_TITLE = COMMIT_MESSAGE
PR_BODY = """Closes #2283

`pyproject`'s `addopts` deselects the integration, e2e and adversarial tiers, so each needs its own step naming its marker. Until now only unit ran on a PR, and integration ran after merge to main.

That is how #2280 was able to rot: the e2e mock harness capped the graph at five super-steps, nodes were added ahead of mechanical validation over time, and the tier silently stopped reaching the loop it exists to exercise. Nothing ran it, so nothing said so. It was found by hand during a pre-roll verification pass.

## Changes

| Tier | Before | After |
|---|---|---|
| unit | every PR | unchanged |
| integration | **only after merge to main** | every PR |
| e2e | **never ran** | every PR |
| adversarial | **never ran** | every PR |

## Notes

**Selectors are `tests/` plus the marker, never a directory.** Two e2e-marked tests live in `tests/unit/test_issue_257.py`, so `tests/e2e/` would quietly run 17 of 19 -- the same shape of silent partial coverage this issue is about.

**Integration moved before merge.** Detecting a break after merge to main is detection at the point where reverting is most expensive. Six of its seventy tests skip without a GitHub token or Gemini access; that is a reason to tolerate skips, not to defer the other sixty-four.

**e2e is free.** Fully mock-driven, no credentials, about six seconds for the tier.

**adversarial skips cleanly.** Its autouse fixture skips before constructing a client when neither `GOOGLE_API_KEY` nor `GEMINI_API_KEY` is set, so the step passes with `1 skipped`. Verified locally through the same `test-gate.py` wrapper CI uses: exit 0. It is deliberately **not** `continue-on-error` -- a skip is already the quiet outcome, and swallowing a genuine failure on top of that would recreate the blind spot this issue exists to close. When the credential question in #2285 is settled the step starts asserting with no workflow change.

## Landing

Via the classic-PAT Contents API (`tools/land_2283_ci_tiers.py`), because the fine-grained PAT cannot push `.github/workflows/`. Run by the operator, per ADR-0216.
"""


def _headers(pat: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


#: The workflow to land, embedded so this script is self-contained.
#:
#: The agent cannot commit `.github/workflows/`, so a script that read the file
#: from disk would depend on an uncommitted working-tree edit surviving until
#: the operator ran it. Embedding keeps the tree clean and makes the script the
#: single artifact to review.
#:
#: Authored LF-only on purpose: the Contents API stores bytes verbatim, and a
#: CRLF payload would flip the whole file's line endings on origin, producing a
#: whole-file diff (ADR-0216 gotcha 3).
WORKFLOW_YAML = """# CI Workflow - every test tier on every push/PR
# Issues #325, #116, #225, #2283
#
# pyproject's addopts deselects integration, e2e and adversarial, so each tier
# needs its own step naming its marker. Until #2283 only unit ran on a PR and
# integration ran after merge to main, which is how the e2e tier silently
# stopped reaching the loop it exists to exercise (#2280): nothing ran it.
#
# Tier selectors use `tests/` plus the marker, never a directory alone -- two
# e2e-marked tests live in tests/unit/test_issue_257.py, and `tests/e2e/` would
# quietly run 17 of 19.

name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v7

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.14'

      - name: Install Poetry
        uses: snok/install-poetry@v1
        with:
          virtualenvs-create: true
          virtualenvs-in-project: true

      - name: Cache dependencies
        uses: actions/cache@v6
        with:
          path: .venv
          key: venv-${{ runner.os }}-${{ hashFiles('poetry.lock') }}-v2
          restore-keys: |
            venv-${{ runner.os }}-

      - name: Install dependencies
        run: poetry install --no-interaction --with dev

      - name: Run unit tests with coverage
        run: poetry run python tools/test-gate.py tests/unit/ -v --tb=short --cov=assemblyzero --cov-report=term-missing --cov-report=xml:coverage.xml
        env:
          LANGSMITH_TRACING: "false"

      # #2283: was `if: github.event_name == 'push' && github.ref == 'refs/heads/main'`,
      # so it landed AFTER merge -- detecting a break at the point where
      # reverting is most expensive. It runs before merge now. Six of its
      # seventy tests skip without a GitHub token or Gemini access; that is a
      # reason to tolerate skips here, not to defer the other sixty-four.
      - name: Run integration tests
        run: poetry run python tools/test-gate.py tests/ -v --tb=short -m integration
        env:
          LANGSMITH_TRACING: "false"
          ASSEMBLYZERO_MOCK_MODE: "1"

      # Fully mock-driven and needs no credentials -- the whole tier runs in
      # about six seconds, so there was never a cost argument for excluding it.
      - name: Run e2e tests
        run: poetry run python tools/test-gate.py tests/ -v --tb=short -m e2e
        env:
          LANGSMITH_TRACING: "false"
          ASSEMBLYZERO_MOCK_MODE: "1"

      # One test, and it needs live Gemini access. With no credential in the
      # environment its autouse fixture skips before constructing a client, so
      # this step passes with `1 skipped` rather than failing or erroring.
      # Deliberately NOT continue-on-error: a skip is already the quiet
      # outcome, and swallowing a genuine failure on top of that would recreate
      # exactly the blind spot #2283 exists to close. When the credential in
      # #2285 is settled this step starts asserting instead of skipping, with
      # no workflow change.
      - name: Run adversarial tests
        run: poetry run python tools/test-gate.py tests/ -v --tb=short -m adversarial
        env:
          LANGSMITH_TRACING: "false"

      - name: Upload coverage report
        if: always()
        uses: actions/upload-artifact@v7
        with:
          name: coverage-report
          path: coverage.xml
          retention-days: 30"""


def local_content() -> bytes:
    return WORKFLOW_YAML.encode("utf-8")


def remote_file(pat: str) -> tuple[bytes | None, str | None]:
    """(content, blob_sha) of the file on main, or (None, None) if absent."""
    r = requests.get(
        f"{GH_API}/repos/{OWNER}/{REPO}/contents/{FILE_PATH}",
        params={"ref": "main"},
        headers=_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code == 404:
        return None, None
    r.raise_for_status()
    payload = r.json()
    return base64.b64decode(payload["content"]), payload["sha"]


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


def put_file(pat: str, blob_sha: str | None) -> None:
    body = {
        "message": COMMIT_MESSAGE,
        "content": base64.b64encode(local_content()).decode("ascii"),
        "branch": BRANCH,
    }
    if blob_sha:
        # Required for an update; omitting it makes the API treat this as a
        # create and reject it with 422.
        body["sha"] = blob_sha
    r = requests.put(
        f"{GH_API}/repos/{OWNER}/{REPO}/contents/{FILE_PATH}",
        headers=_headers(pat),
        json=body,
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
    if r.status_code == 422 and "already exists" in r.text.lower():
        existing = requests.get(
            f"{GH_API}/repos/{OWNER}/{REPO}/pulls",
            headers=_headers(pat),
            params={"head": f"{OWNER}:{BRANCH}", "state": "open"},
            timeout=HTTP_TIMEOUT_S,
        )
        existing.raise_for_status()
        num = existing.json()[0]["number"]
        print(f"  PR #{num} already open -- reusing")
        return num
    r.raise_for_status()
    num = r.json()["number"]
    print(f"  opened PR #{num}")
    return num


def wait_mergeable(pat: str, num: int) -> bool:
    """Poll until `clean`. `unstable` is NOT accepted -- see module docstring."""
    for i in range(1, MERGE_POLL_ATTEMPTS + 1):
        r = requests.get(
            f"{GH_API}/repos/{OWNER}/{REPO}/pulls/{num}",
            headers=_headers(pat),
            timeout=HTTP_TIMEOUT_S,
        )
        r.raise_for_status()
        state = r.json().get("mergeable_state")
        print(f"  poll {i}: mergeable_state={state}")
        if state == "clean":
            return True
        if state == "dirty":
            print("  ABORT: the PR has conflicts.")
            return False
        time.sleep(MERGE_POLL_SLEEP_S)
    print("  ABORT: never reached 'clean'. Inspect the checks on the PR --")
    print("  a red NEW tier here is this change working, not a problem to bypass.")
    return False


def squash_merge(pat: str, num: int) -> str:
    r = requests.put(
        f"{GH_API}/repos/{OWNER}/{REPO}/pulls/{num}/merge",
        headers=_headers(pat),
        json={"merge_method": "squash"},
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    sha = r.json().get("sha", "")
    print(f"  merged PR #{num} -> {sha}")
    return sha


def delete_branch(pat: str) -> None:
    r = requests.delete(
        f"{GH_API}/repos/{OWNER}/{REPO}/git/refs/heads/{BRANCH}",
        headers=_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code in (204, 422, 404):
        print(f"  deleted remote branch {BRANCH}")
        return
    r.raise_for_status()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show the plan and the diff summary without writing anything.",
    )
    args = parser.parse_args(argv)

    local = local_content()
    print(f"Embedded {FILE_PATH}: {len(local)} bytes (LF)")

    with classic_pat_session() as pat:
        remote, blob_sha = remote_file(pat)

        if remote is None:
            print(f"  {FILE_PATH} does not exist on main -- this would CREATE it.")
        elif remote == local:
            print("  main already matches the local file. Nothing to do.")
            return 0
        else:
            print(f"  main differs ({len(remote)} bytes) -- this is an UPDATE.")

        if args.dry_run:
            print("\nDRY RUN -- nothing was written. Would:")
            print(f"  1. create branch {BRANCH} from main")
            print(f"  2. PUT {FILE_PATH} (sha={blob_sha[:8] if blob_sha else 'none'})")
            print("  3. open a PR, wait for 'clean', squash-merge")
            print(f"  4. delete remote branch {BRANCH}")
            return 0

        ensure_branch(pat, main_sha(pat))
        put_file(pat, blob_sha)
        num = open_pr(pat)
        if not wait_mergeable(pat, num):
            print(f"\nPR #{num} is open and NOT merged. Nothing was forced.")
            return 1
        merge_sha = squash_merge(pat, num)
        delete_branch(pat)

    print(f"\nLanded. PR #{num}, merge {merge_sha}")
    print("Then, in your normal shell:  git fetch origin && git checkout main "
          "&& git merge origin/main --ff-only")
    return 0


if __name__ == "__main__":
    sys.exit(main())
