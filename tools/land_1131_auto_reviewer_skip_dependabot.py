#!/usr/bin/env python3
"""Land the #1131 auto-reviewer.yml dependabot-skip fix via classic-PAT Contents API.

THIS SCRIPT MUST BE RUN BY THE USER, NOT BY AN AGENT.

The fix is a one-condition expansion to `.github/workflows/auto-reviewer.yml`
in AssemblyZero. The fine-grained PAT cannot push workflow files (no
`workflow` scope, intentionally per ADR-0216). Lands via the GitHub
Contents API using an in-process classic PAT.

The change makes auto-reviewer.yml SKIP dependabot PRs. Architectural
rationale in #1131:

- Cerberus is the AGENT fence -- breaks the self-authorization loop for
  PRs created by an agent acting under user credentials.
- Dependabot has its own governance: tools/dependabot_review.py runs
  tests + approves under the user's credentials.
- Running auto-reviewer.yml on dependabot PRs causes a noisy failure
  (Dependabot-scope secrets missing) and doesn't serve any architectural
  purpose.

What this script does:

  1. Reads `.github/workflows/auto-reviewer.yml` from origin/main via
     Contents API.
  2. Applies the #1131 fix: expands the existing `if:` on the auto-review
     job to also require `github.event.pull_request.user.login != 'dependabot[bot]'`.
  3. Validates the patch is idempotent (refuse if already applied).
  4. Creates a branch from main HEAD via API.
  5. PUTs the patched file (CRLF-normalised per the 2026-04-30 memory).
  6. Opens a PR with `Closes #1131` in title and body.
  7. Polls mergeable_state until clean or unstable (the auto-reviewer
     check itself runs on THIS PR and now skips dependabot, but this
     PR isn't dependabot, so the check should pass normally).
  8. Squash-merges via API.

Issue: #1131 | Related: #1104 / PR #1115 (precedent), ADR-0216
"""

from __future__ import annotations

import argparse
import base64
import sys
import time
from pathlib import Path
from typing import Any

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pat_session import classic_pat_session  # noqa: E402

GITHUB_USER = "martymcenroe"
REPO = f"{GITHUB_USER}/AssemblyZero"
GH_API = "https://api.github.com"
WORKFLOW_PATH = ".github/workflows/auto-reviewer.yml"
ISSUE_NUMBER = 1131
BRANCH = f"{ISSUE_NUMBER}-auto-reviewer-skip-dependabot"

HTTP_TIMEOUT_S = 30
POLL_INTERVAL_S = 10
MERGEABLE_TIMEOUT_S = 900

# The old `if:` -- existing single-line condition.
OLD_IF = (
    "    if: github.event_name == 'pull_request' "
    "|| github.event_name == 'workflow_call'"
)

# The new `if:` -- adds the dependabot skip condition.
NEW_IF = (
    "    # #1131: skip dependabot PRs. Cerberus is the agent fence; dependabot\n"
    "    # has its own governance via tools/dependabot_review.py.\n"
    "    if: (github.event_name == 'pull_request' "
    "|| github.event_name == 'workflow_call') "
    "&& github.event.pull_request.user.login != 'dependabot[bot]'"
)


def _headers(pat: str) -> dict[str, str]:
    return {
        "Authorization": f"token {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _api(method: str, url: str, pat: str, **kw: Any) -> requests.Response:
    return requests.request(method, url, headers=_headers(pat), timeout=HTTP_TIMEOUT_S, **kw)


def read_workflow(pat: str) -> tuple[str, str]:
    r = _api("GET", f"{GH_API}/repos/{REPO}/contents/{WORKFLOW_PATH}?ref=main", pat)
    if r.status_code >= 300:
        sys.exit(f"GET contents failed: {r.status_code} {r.text[:300]}")
    data = r.json()
    return base64.b64decode(data["content"]).decode("utf-8"), data["sha"]


def apply_patch(content: str) -> str | None:
    """Apply the #1131 fix. Returns patched text, or None if already applied."""
    if "dependabot[bot]" in content and "#1131" in content:
        return None  # already patched
    if OLD_IF not in content:
        sys.exit(
            "ERROR: expected `if:` block not found in workflow file. The "
            "file has drifted since this script was written -- re-derive "
            "the patch from current content."
        )
    return content.replace(OLD_IF, NEW_IF)


def main_head_sha(pat: str) -> str:
    r = _api("GET", f"{GH_API}/repos/{REPO}/git/refs/heads/main", pat)
    if r.status_code >= 300:
        sys.exit(f"GET main ref failed: {r.status_code}")
    return r.json()["object"]["sha"]


def create_branch(pat: str, main_sha: str) -> None:
    r = _api(
        "POST", f"{GH_API}/repos/{REPO}/git/refs", pat,
        json={"ref": f"refs/heads/{BRANCH}", "sha": main_sha},
    )
    if r.status_code == 422:
        print(f"  branch {BRANCH} already exists, reusing")
        return
    if r.status_code >= 300:
        sys.exit(f"POST branch failed: {r.status_code} {r.text[:300]}")


def get_blob_sha_on_branch(pat: str) -> str | None:
    r = _api("GET", f"{GH_API}/repos/{REPO}/contents/{WORKFLOW_PATH}?ref={BRANCH}", pat)
    if r.status_code >= 300:
        return None
    return r.json()["sha"]


def put_file(pat: str, new_content: str, blob_sha: str) -> None:
    new_bytes = new_content.replace("\r\n", "\n").encode("utf-8")
    payload = {
        "message": f"fix: auto-reviewer skips dependabot PRs (Closes #{ISSUE_NUMBER})",
        "content": base64.b64encode(new_bytes).decode("ascii"),
        "branch": BRANCH,
        "sha": blob_sha,
    }
    r = _api("PUT", f"{GH_API}/repos/{REPO}/contents/{WORKFLOW_PATH}", pat, json=payload)
    if r.status_code >= 300:
        sys.exit(f"PUT contents failed: {r.status_code} {r.text[:300]}")


def open_pr(pat: str) -> int:
    body = (
        f"Closes #{ISSUE_NUMBER}\n\n"
        "Adds a single `if:` condition to `.github/workflows/auto-reviewer.yml` "
        "so the auto-review job skips dependabot PRs entirely.\n\n"
        "Architectural rationale:\n"
        "- Cerberus is the agent fence -- breaks the self-authorization loop "
        "for PRs created by an agent acting under user credentials\n"
        "- Dependabot has its own governance via `tools/dependabot_review.py` "
        "(tests + approves under the user's creds, accruing to the user's profile)\n"
        "- Running auto-reviewer on dependabot PRs causes a noisy failure "
        "(Dependabot-scope secrets missing) and serves no architectural purpose\n\n"
        "Fleet-wide impact is automatic because consumer repos reference "
        "`@main` of this reusable workflow.\n"
    )
    r = _api(
        "POST", f"{GH_API}/repos/{REPO}/pulls", pat,
        json={
            "title": f"fix: auto-reviewer skips dependabot PRs (Closes #{ISSUE_NUMBER})",
            "head": BRANCH,
            "base": "main",
            "body": body,
        },
    )
    if r.status_code >= 300:
        existing = _api(
            "GET", f"{GH_API}/repos/{REPO}/pulls?head={GITHUB_USER}:{BRANCH}&state=open", pat,
        )
        if existing.status_code == 200 and existing.json():
            pr_n = existing.json()[0]["number"]
            print(f"  PR #{pr_n} already exists, reusing")
            return pr_n
        sys.exit(f"POST PR failed: {r.status_code} {r.text[:300]}")
    return r.json()["number"]


def wait_for_mergeable(pat: str, pr_n: int) -> None:
    deadline = time.time() + MERGEABLE_TIMEOUT_S
    while time.time() < deadline:
        r = _api("GET", f"{GH_API}/repos/{REPO}/pulls/{pr_n}", pat)
        if r.status_code >= 300:
            time.sleep(POLL_INTERVAL_S)
            continue
        state = r.json().get("mergeable_state")
        print(f"  PR #{pr_n}: mergeable_state={state}")
        if state in ("clean", "unstable"):
            return
        time.sleep(POLL_INTERVAL_S)
    sys.exit(f"Timed out waiting for PR #{pr_n} to be mergeable")


def squash_merge(pat: str, pr_n: int) -> None:
    r = _api("PUT", f"{GH_API}/repos/{REPO}/pulls/{pr_n}/merge", pat,
             json={"merge_method": "squash"})
    if r.status_code >= 300:
        sys.exit(f"PUT merge failed: {r.status_code} {r.text[:300]}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Land #1131 auto-reviewer dependabot-skip fix.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Write the patched YAML to a tempfile + diff path; no API writes.")
    args = parser.parse_args()

    if args.dry_run:
        local = Path(__file__).resolve().parents[1] / WORKFLOW_PATH
        if not local.is_file():
            print("Dry-run requires the workflow file in the current worktree.",
                  file=sys.stderr)
            return 1
        content = local.read_text(encoding="utf-8", errors="replace")
        new_content = apply_patch(content)
        if new_content is None:
            print("Already patched. No change needed.")
            return 0
        import tempfile
        tmp = tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".yml",
            prefix="auto-reviewer-1131-patched-", delete=False,
        )
        tmp.write(new_content)
        tmp.close()
        print(f"Patched YAML: {tmp.name}")
        print(f"Diff: diff -u '{local}' '{tmp.name}'")
        return 0

    with classic_pat_session() as pat:
        print("1. Reading current workflow file from main...")
        content, _ = read_workflow(pat)

        print("2. Applying patch...")
        new_content = apply_patch(content)
        if new_content is None:
            print("   Already patched. Nothing to do.")
            return 0

        print(f"3. Creating branch {BRANCH}...")
        main_sha = main_head_sha(pat)
        create_branch(pat, main_sha)

        print(f"4. PUTting patched file via Contents API on {BRANCH}...")
        branch_blob_sha = get_blob_sha_on_branch(pat)
        if branch_blob_sha is None:
            sys.exit("Failed to read blob sha on new branch -- aborting")
        put_file(pat, new_content, branch_blob_sha)

        print("5. Opening PR...")
        pr_n = open_pr(pat)
        print(f"   PR #{pr_n} -- https://github.com/{REPO}/pull/{pr_n}")

        print("6. Waiting for mergeable_state...")
        wait_for_mergeable(pat, pr_n)

        print("7. Squash-merging...")
        squash_merge(pat, pr_n)

    print(f"\nDone. #{ISSUE_NUMBER} fix landed via PR #{pr_n}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
