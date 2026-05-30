#!/usr/bin/env python3
"""One-shot deploy of `.github/workflows/deploy-landing.yml` to boostgauge.

Closes martymcenroe/boostgauge#66.

Why this exists: editing `.github/workflows/*` requires `workflow` scope,
which the fine-grained PAT used by `gh` and `git push` does not carry.
This script uses the in-process classic-PAT pattern (ADR-0216) to land
the file via the GitHub Contents API.

Idempotent: if the branch or file already exists on origin, the script
skips that step and continues. Safe to re-run.

What it does:
  1. Decrypt the classic PAT into local heap (pinentry prompts).
  2. Check whether `deploy-landing.yml` is already on main -- if so, exit.
  3. Check whether `66-deploy-landing-workflow` branch already exists on
     origin -- if so, check whether an open PR exists; reuse if yes,
     create if no.
  4. Create the branch from main HEAD if absent.
  5. PUT the file via Contents API (creates a commit on the branch).
  6. Open a PR with `Closes #66` if no open PR for the branch exists.
  7. Print the PR URL. STOP.

Does NOT merge. Cerberus auto-approves on the upgraded auto-reviewer
workflow (commit a4fcb50); merge through normal `gh pr merge --squash`
flow once `mergeable_state` flips to `clean`.

Required classic PAT scopes:
  - repo (full)        -- branch ref, PR ops
  - workflow           -- Contents API write to .github/workflows/*

REQUIRED operational rule (`feedback_az_tools_user_runs_script`):
  The user runs this script in their own Git Bash. Never invoke via
  an agent's Bash tool -- the spawned Python process becomes the
  agent's child and its heap is theoretically readable by the agent
  for the seconds the PAT is in scope.

Usage:
    cd /c/Users/mcwiz/Projects/AssemblyZero
    poetry run python tools/deploy_boostgauge_landing_workflow.py

This is a one-shot for boostgauge #66. Safe to delete after the PR
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
ISSUE_NUMBER = 66
BRANCH = f"{ISSUE_NUMBER}-deploy-landing-workflow"
WORKFLOW_PATH = ".github/workflows/deploy-landing.yml"
GH_API = "https://api.github.com"
HTTP_TIMEOUT_S = 30

PR_TITLE = (
    "feat: auto-deploy landing page to Cloudflare Pages on push to main"
)

COMMIT_MESSAGE = (
    "feat: auto-deploy landing page to Cloudflare Pages on push to main "
    f"(Closes #{ISSUE_NUMBER})"
)

PR_BODY = f"""## Summary

Adds `.github/workflows/deploy-landing.yml`. Triggers on push to `main`
when files under `docs/landing/` or this workflow itself change
(paths filter avoids burning CI minutes on unrelated changes).

Uses the official `cloudflare/wrangler-action@v3`, authenticating via
the `CLOUDFLARE_API_TOKEN` GitHub Actions secret. Account ID is inline
(already public in `CLAUDE.md`).

## Required follow-up (browser, one-time)

After this PR merges, add the secret so the workflow can actually run:

1. Cloudflare dashboard -> user icon -> **My Profile** -> **API Tokens**
   -> **Create Token**
2. Custom token with permissions:
   - **Account -> Cloudflare Pages -> Edit**
3. Account Resources: the boostgauge owner's account
4. Copy the generated token (shown ONCE)
5. GitHub: `github.com/martymcenroe/boostgauge` -> **Settings** ->
   **Secrets and variables** -> **Actions** -> **New repository secret**
   - Name: `CLOUDFLARE_API_TOKEN`
   - Value: paste the token
6. Save

Then any push touching `docs/landing/` deploys to
`https://boostgauge.martymcenroe.ai` within ~30 seconds.

## Why this PR is landed via Contents API instead of `git push`

Editing `.github/workflows/*` requires the `workflow` scope. The
fine-grained PAT used by `gh` and `git push` doesn't carry that scope.
This PR is filed via the in-process classic-PAT pattern (ADR-0216)
from `AssemblyZero/tools/deploy_boostgauge_landing_workflow.py` --
the standard fleet pattern for workflow-file edits.

Closes #{ISSUE_NUMBER}

Filed by `AssemblyZero/tools/deploy_boostgauge_landing_workflow.py`
"""

# The workflow file content. Line endings normalized to LF below.
DEPLOY_LANDING_YML = """name: Deploy landing page to Cloudflare Pages

on:
  push:
    branches: [main]
    paths:
      - "docs/landing/**"
      - ".github/workflows/deploy-landing.yml"
  workflow_dispatch: {}

permissions:
  contents: read
  deployments: write

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment:
      name: cloudflare-pages
      url: https://boostgauge.martymcenroe.ai
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Deploy to Cloudflare Pages
        uses: cloudflare/wrangler-action@v3
        with:
          apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          accountId: 4fe1c5e241425c85d0f2c35c69fb45b8
          command: pages deploy docs/landing --project-name=boostgauge --branch=main --commit-hash=${{ github.sha }} --commit-message="${{ github.event.head_commit.message }}"
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
    # CRLF normalization not strictly needed here -- DEPLOY_LANDING_YML
    # is an in-source string with \n line endings. Belt-and-suspenders.
    content_bytes = DEPLOY_LANDING_YML.encode("utf-8").replace(b"\r\n", b"\n")
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
            print(f"  {WORKFLOW_PATH} already exists on main -- nothing to do.")
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
        print("Next step: Cerberus should auto-approve on the upgraded")
        print("auto-reviewer.yml. Wait for mergeable_state=clean, then:")
        print(f"  gh pr merge {pr_num} --squash --repo {GITHUB_USER}/{REPO}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
