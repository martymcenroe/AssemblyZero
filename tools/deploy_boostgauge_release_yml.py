#!/usr/bin/env python3
"""One-shot deploy of `.github/workflows/release.yml` to boostgauge.

Closes martymcenroe/boostgauge#50.

Why this exists: editing `.github/workflows/*` requires `workflow` scope,
which the fine-grained PAT used by `gh` and `git push` does not carry.
This script uses the in-process classic-PAT pattern (ADR-0216) to land
the file via the GitHub Contents API.

Idempotent: if the branch or file already exists on origin, the script
skips that step and continues. Safe to re-run.

What it does:
  1. Decrypt the classic PAT into local heap (pinentry prompts).
  2. Check whether `release.yml` is already on main — if so, exit.
  3. Check whether `50-deploy-release-yml` branch already exists on
     origin — if so, check whether an open PR exists; reuse if yes,
     create if no.
  4. Create the branch from main HEAD if absent.
  5. PUT the file via Contents API (creates a commit on the branch).
  6. Open a PR with `Closes #50` if no open PR for the branch exists.
  7. Print the PR URL. STOP.

Does NOT merge. Cerberus auto-approves once secrets are deployed; you
merge through normal `gh pr merge --squash` flow.

Required classic PAT scopes:
  - repo (full)        — branch ref, PR ops
  - workflow           — Contents API write to .github/workflows/*

REQUIRED operational rule (`feedback_az_tools_user_runs_script.md`):
  The user runs this script in their own Git Bash. Never invoke via
  an agent's Bash tool — the spawned Python process becomes the
  agent's child and its heap is theoretically readable by the agent
  for the seconds the PAT is in scope.

Usage:
    cd /c/Users/mcwiz/Projects/AssemblyZero
    poetry run python tools/deploy_boostgauge_release_yml.py

This is a one-shot for boostgauge #50. Safe to delete after the PR
merges. If a similar deploy is ever needed for another repo, copy +
adjust the constants at the top.
"""
from __future__ import annotations

import base64
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pat_session import classic_pat_session  # noqa: E402

GITHUB_USER = "martymcenroe"
REPO = "boostgauge"
ISSUE_NUMBER = 50
BRANCH = f"{ISSUE_NUMBER}-deploy-release-yml"
WORKFLOW_PATH = ".github/workflows/release.yml"
GH_API = "https://api.github.com"
HTTP_TIMEOUT_S = 30

PR_TITLE = "chore: deploy release.yml — tag-triggered PyPI publish via OIDC"

COMMIT_MESSAGE = (
    "chore: deploy release.yml — tag-triggered PyPI publish via OIDC "
    f"(Closes #{ISSUE_NUMBER})"
)

PR_BODY = f"""## Summary

Deploys `.github/workflows/release.yml` matching the canonical template
embedded in `AssemblyZero/tools/new_repo_setup.py:1355-1400` (#1074).
Tag-triggered on `v*.*.*` pattern. OIDC handshake to PyPI; no token
stored in secrets. `environment: pypi` must match the publisher record
registered per runbook 0934 BEFORE the first tag push.

Workflow is wired but not yet exercised — first run is during the
speedrun's phase 6 (`git tag v0.1.0 && git push origin v0.1.0`).

Landed via Contents API + classic PAT (ADR-0216) because editing
`.github/workflows/*` requires `workflow` scope that the
fine-grained PAT used by `git push` doesn't carry.

Closes #{ISSUE_NUMBER}
Refs #33 (Cerberus secrets deploy — required for this PR's auto-approve)

🤖 Filed by `AssemblyZero/tools/deploy_boostgauge_release_yml.py`
"""

# Verbatim copy of the release.yml block in new_repo_setup.py:1361-1399.
# Line endings normalized to LF (matches what Contents API stores and
# what every other repo in the fleet carries).
RELEASE_YML = """name: Release to PyPI

# Tag-triggered publish to PyPI via OIDC Trusted Publisher (no token in
# secrets). Configure the publisher per runbook 0934 BEFORE the first
# tag push — pre-#0934 tag pushes will fail at the publish step with a
# "no pending publisher" error from PyPI.

on:
  push:
    tags:
      - "v*.*.*"

permissions:
  id-token: write  # Required for OIDC trust handshake with PyPI.
  contents: read

jobs:
  release:
    runs-on: ubuntu-latest
    environment: pypi  # Must match the environment registered on PyPI.
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.10"

      - name: Install Poetry
        run: pipx install poetry

      - name: Build distributions
        run: poetry build

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        # No password / token — OIDC Trusted Publisher handles auth.
"""


def _headers(pat: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def file_exists_on_main(pat: str) -> bool:
    r = requests.get(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/contents/{WORKFLOW_PATH}",
        params={"ref": "main"},
        headers=_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code == 404:
        return False
    r.raise_for_status()
    return True


def branch_exists(pat: str) -> bool:
    r = requests.get(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/git/refs/heads/{BRANCH}",
        headers=_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code == 404:
        return False
    r.raise_for_status()
    return True


def file_exists_on_branch(pat: str) -> bool:
    r = requests.get(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/contents/{WORKFLOW_PATH}",
        params={"ref": BRANCH},
        headers=_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code == 404:
        return False
    r.raise_for_status()
    return True


def find_open_pr(pat: str) -> tuple[int | None, str | None]:
    r = requests.get(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/pulls",
        params={"state": "open", "head": f"{GITHUB_USER}:{BRANCH}", "per_page": 10},
        headers=_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    items = r.json()
    if not items:
        return None, None
    pr = items[0]
    return pr["number"], pr["html_url"]


def get_main_head_sha(pat: str) -> str:
    r = requests.get(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/git/refs/heads/main",
        headers=_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json()["object"]["sha"]


def create_branch(pat: str, source_sha: str) -> None:
    r = requests.post(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/git/refs",
        headers=_headers(pat),
        json={"ref": f"refs/heads/{BRANCH}", "sha": source_sha},
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()


def put_file_on_branch(pat: str) -> None:
    # CRLF normalization not strictly needed here — RELEASE_YML is an
    # in-source string with \n line endings. Belt-and-suspenders below.
    content_bytes = RELEASE_YML.encode("utf-8").replace(b"\r\n", b"\n")
    r = requests.put(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/contents/{WORKFLOW_PATH}",
        headers=_headers(pat),
        json={
            "message": COMMIT_MESSAGE,
            "content": base64.b64encode(content_bytes).decode("ascii"),
            "branch": BRANCH,
        },
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()


def create_pr(pat: str) -> tuple[int, str]:
    r = requests.post(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/pulls",
        headers=_headers(pat),
        json={
            "title": PR_TITLE,
            "head": BRANCH,
            "base": "main",
            "body": PR_BODY,
        },
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    data = r.json()
    return data["number"], data["html_url"]


def main() -> int:
    print(f"Target: {GITHUB_USER}/{REPO}")
    print(f"Branch: {BRANCH}")
    print(f"File:   {WORKFLOW_PATH}")
    print(f"Issue:  #{ISSUE_NUMBER}")
    print()

    with classic_pat_session() as pat:
        # Idempotency: skip everything if file is already on main.
        if file_exists_on_main(pat):
            print(f"  {WORKFLOW_PATH} already exists on main — nothing to do.")
            return 0

        # Check for existing open PR (reuse if present).
        existing_pr_num, existing_pr_url = find_open_pr(pat)
        if existing_pr_num is not None:
            print(f"  Open PR already exists: #{existing_pr_num}")
            print(f"  URL: {existing_pr_url}")
            print(f"  No-op. Merge through normal flow.")
            return 0

        # Idempotency: if branch exists but file doesn't, drop the file
        # on the branch and open a PR. If file exists on branch but no
        # PR, just open the PR.
        if branch_exists(pat):
            print(f"  Branch {BRANCH} already exists on origin.")
            if not file_exists_on_branch(pat):
                print(f"  Adding {WORKFLOW_PATH} to existing branch...")
                put_file_on_branch(pat)
                print(f"    PUT contents/{WORKFLOW_PATH} succeeded.")
            else:
                print(f"  File already present on branch.")
        else:
            main_sha = get_main_head_sha(pat)
            print(f"  Creating branch {BRANCH} from main@{main_sha[:7]}...")
            create_branch(pat, main_sha)
            print(f"  PUT contents/{WORKFLOW_PATH} on branch...")
            put_file_on_branch(pat)
            print(f"    succeeded.")

        # Open the PR.
        print(f"  Opening PR...")
        pr_num, pr_url = create_pr(pat)
        print()
        print(f"PR #{pr_num} opened: {pr_url}")
        print()
        print("Next step: wait for Cerberus auto-approve (if secrets are")
        print("deployed), then `gh pr merge {N} --squash --repo {repo}`.")
        print("If Cerberus secrets are NOT deployed, this PR will sit in")
        print("`mergeable_state: blocked` until they are.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
