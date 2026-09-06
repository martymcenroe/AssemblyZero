#!/usr/bin/env python3
"""Land Polybolos's test-runner workflow, and then require it (AZ #2929).

Polybolos had 2,652 tests and nothing in CI ran them. `.github/workflows/` held
one file, whose `required_checks` is `issue-reference`, so `mergeable_state:
clean` meant pr-sentinel passed and Cerberus approved — never that a test ran.
Ten PRs merged into that repo's `main` on 2026-09-06 under that regime.

The agent's fine-grained PAT cannot push a file under `.github/workflows/`: it
has no `workflow` scope, deliberately (ADR-0216 §1, and root CLAUDE.md "When
git push Is Rejected For Workflow Scope"). It also gets a 403 on branch
protection. So both halves run here through the admin-scope classic PAT, which
this process gpg-decrypts in-heap per ADR-0216: the PAT lives only as a local
variable inside the `with classic_pat_session()` block, is consumed by
`requests` directly, and never reaches env, argv, disk, or a log.

Everything else for that repo's CI issue — the skip audit, the declaration of
what may skip, the one test that had to change, pytest-xdist — is already on
branch `502-ci-runs-the-suite` and open as a pull request, pushed normally.
This adds the single file that PR cannot carry, to that same branch, so the
change lands as one PR against one issue rather than being split in two for an
authentication reason. That is what distinguishes this from `land_career_test_ci.py`
and `hermes_add_ci_workflow.py`, which each open a branch and PR of their own.

Two phases, separated by a merge and by evidence.

  --apply
      PUT `.github/workflows/tests.yml` onto branch `502-ci-runs-the-suite`.
      The push re-triggers the PR's checks, and because the workflow file is on
      the PR branch, `pull_request` runs it — the PR tests itself.

  --require-check --apply
      Add `tests` to `main`'s required status checks, AFTER that PR has merged
      and the check has been seen green at least once. Run in this order and
      never the other: **requiring a check that has never reported blocks every
      PR in the repo** until it is removed again.

      Blast radius: every open and future PR must produce a check named
      `tests`. Rollback, with the classic PAT:

        DELETE /repos/martymcenroe/Polybolos/branches/main/protection
               /required_status_checks/contexts   {"contexts": ["tests"]}

      It uses the add-a-context endpoint rather than a whole-protection PUT, so
      nothing else about the rule is rewritten. If required status checks are
      not configured at all it reports that and stops — turning them on is a
      decision about the repo, not a step in a landing script.

Usage (RUN THIS YOURSELF in your own Git Bash — never through an agent's Bash
tool, per the _pat_session operational rule: a script the agent invokes is a
process the agent parents, which dissolves the heap-only guarantee):

    cd /c/Users/mcwiz/Projects/AssemblyZero
    poetry run python tools/land_polybolos_ci_workflow.py

That is the dry run and it writes nothing, nor does it ask for the passphrase.
Then:

    poetry run python tools/land_polybolos_ci_workflow.py --apply

Requires ~/.secrets/classic-pat.gpg and gpg-agent `default-cache-ttl 0`.
"""

from __future__ import annotations

import argparse
import base64
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pat_session import classic_pat_session  # noqa: E402

OWNER = "martymcenroe"
REPO = "Polybolos"
GH_API = "https://api.github.com"
BRANCH = "502-ci-runs-the-suite"
FILE_PATH = ".github/workflows/tests.yml"
CHECK_NAME = "tests"
HTTP_TIMEOUT_S = 30

# Authored with \n and encoded as UTF-8 bytes: the Contents API stores bytes
# verbatim, so CRLF here would land CRLF on origin (root CLAUDE.md gotcha 3).
WORKFLOW_YAML = """name: tests

# CI runs the suite (#502).
#
# Until this existed, 2,652 tests ran when a person typed `pytest` and at no
# other time -- which is how test_census_essay.py sat red on main for
# ninety-five minutes on 2026-09-06 with nothing saying so.
#
# windows-latest, because that is the only platform this engine runs on: it
# drives Chrome over CDP on the operator's Windows machine. A green Ubuntu run
# would be evidence about a platform that does not exist for this product, and a
# red one for a path-separator reason would train us to wave the check through.
# This repo already knows what happens to a check that cries wolf.
#
# `-n auto` is not a nicety. The suite is 189s serially and 42s across the
# machine's cores, and a required check spending a private repo's Windows
# minutes has to be affordable to survive.

on:
  pull_request:
    branches: [main]
  # A red `main` was invisible. This is what makes it visible.
  push:
    branches: [main]

concurrency:
  group: tests-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read

jobs:
  tests:
    name: tests
    runs-on: windows-latest
    timeout-minutes: 25
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.14'

      - name: Install poetry
        run: pipx install poetry

      # In-project so actions/cache can address it. Without this the venv lands
      # in a per-user cache directory the key cannot reach.
      - name: Keep the venv in the tree
        run: poetry config virtualenvs.in-project true

      - name: Cache the virtualenv
        uses: actions/cache@v4
        with:
          path: .venv
          key: venv-${{ runner.os }}-py314-${{ hashFiles('poetry.lock') }}

      # Installs the root project too, which `python -m polybolos.cli` needs:
      # test_cli.py fails without it, and that failure looks nothing like its
      # cause.
      - name: Install
        run: poetry install --no-interaction

      # `poetry install` installs the Playwright PACKAGE. It does not download
      # a browser, and two tests launch a real headless one on purpose: the
      # defect they cover is what the browser does with scrollIntoView under
      # `scroll-behavior: smooth`, which stopped the first live run on field one
      # of twenty-five. A fake locator would test nothing but the test, so a
      # browser-driving product's CI is exactly where they belong.
      #
      # ~130 MB cold, near-instant once the cache is warm.
      - name: Cache the Playwright browser
        uses: actions/cache@v4
        with:
          path: ~\\AppData\\Local\\ms-playwright
          key: playwright-${{ runner.os }}-${{ hashFiles('poetry.lock') }}

      - name: Install the Playwright browser
        run: poetry run playwright install chromium

      - name: ruff
        run: poetry run ruff check .

      - name: pytest
        run: poetry run pytest -n auto --junitxml=data/ci/junit.xml

      # A skip is not a pass. Four tests read state only the operator's machine
      # has, they skip here, and pytest counts a skip toward a green run. This
      # fails the run on a skip nobody declared -- and on a declaration nothing
      # used, which is a standing licence for a test to vanish later.
      #
      # `if: always()` so a failing suite still reports what it declined to run.
      - name: Every skip is declared
        if: always()
        run: poetry run python tools/ci_skip_audit.py --report data/ci/junit.xml
"""


def _headers(pat: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def existing_sha(pat: str) -> str | None:
    """The file's blob sha on the branch, or None. Makes the PUT idempotent."""
    r = requests.get(
        f"{GH_API}/repos/{OWNER}/{REPO}/contents/{FILE_PATH}",
        params={"ref": BRANCH},
        headers=_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return str(r.json()["sha"])


def put_workflow(pat: str) -> None:
    payload: dict[str, object] = {
        "message": (
            "ci: run the suite on every PR and on main\n\n"
            "The one file the pull request could not carry: a fine-grained PAT "
            "has no `workflow` scope, so this lands through the Contents API."
        ),
        "content": base64.b64encode(WORKFLOW_YAML.encode("utf-8")).decode("ascii"),
        "branch": BRANCH,
    }
    sha = existing_sha(pat)
    if sha is not None:
        payload["sha"] = sha
        print(f"  {FILE_PATH} is already on {BRANCH} — updating it in place")
    r = requests.put(
        f"{GH_API}/repos/{OWNER}/{REPO}/contents/{FILE_PATH}",
        headers=_headers(pat),
        json=payload,
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    print(f"  committed {FILE_PATH} on {BRANCH} @ {r.json()['commit']['sha'][:8]}")
    print("  the workflow is on the PR branch, so the PR now tests itself")


def read_protection(pat: str) -> dict[str, object] | None:
    r = requests.get(
        f"{GH_API}/repos/{OWNER}/{REPO}/branches/main/protection",
        headers=_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return dict(r.json())


def require_check(pat: str, apply: bool) -> int:
    protection = read_protection(pat)
    if protection is None:
        print("main has no branch protection at all. Nothing here to add a check to.")
        return 1

    checks = protection.get("required_status_checks")
    if not isinstance(checks, dict):
        print(
            "main is protected, but required status checks are not configured.\n"
            "Turning them on changes what every PR in the repo must satisfy, "
            "which is a decision about the repo rather than a step in this "
            "task. Stopping here."
        )
        return 1

    contexts = list(checks.get("contexts") or [])
    print(f"  required status checks now: {contexts or '(none)'}")
    if CHECK_NAME in contexts:
        print(f"  `{CHECK_NAME}` is already required — nothing to do.")
        return 0
    if not apply:
        print(f"  DRY-RUN — would add `{CHECK_NAME}` to that list.")
        return 0

    r = requests.post(
        f"{GH_API}/repos/{OWNER}/{REPO}/branches/main/protection"
        "/required_status_checks/contexts",
        headers=_headers(pat),
        json={"contexts": [CHECK_NAME]},
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    print(f"  required status checks are now: {r.json()}")
    print("  `mergeable_state: clean` now means the tests passed.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Actually write. Without it this previews and touches nothing.",
    )
    ap.add_argument(
        "--require-check",
        action="store_true",
        help=(
            "Phase 2: add the check to main's required status checks. Only "
            "after the PR has merged and the check has been seen green."
        ),
    )
    args = ap.parse_args()

    if not args.apply and not args.require_check:
        print(
            f"DRY-RUN — would PUT this at {OWNER}/{REPO}:{FILE_PATH} "
            f"on branch {BRANCH}:\n"
        )
        print(WORKFLOW_YAML)
        print("Re-run with --apply to land it.")
        return 0

    with classic_pat_session() as pat:
        if args.require_check:
            return require_check(pat, apply=args.apply)
        print(f"Landing {FILE_PATH} on {OWNER}/{REPO}@{BRANCH} ...")
        put_workflow(pat)
        print(
            "\nDone. Watch the pull request: a `tests` check should appear and "
            "go green.\nAfter it merges, run this again with "
            "--require-check --apply."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
