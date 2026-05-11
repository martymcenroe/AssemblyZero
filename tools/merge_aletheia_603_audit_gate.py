#!/usr/bin/env python3
"""Land Aletheia #603 (remove abandoned audit-schedule gate) via API only.

Issue #603. The active fine-grained PAT lacks `workflow` scope so `git push`
is rejected. This script reproduces the local single-file commit on origin
via the GitHub Contents API, opens the PR, polls until mergeable_state is
'clean', squash-merges, and cleans up the remote branch. As a final step
it nudges PR #584 (close+reopen) which became unstable behind the same
dead audit-schedule check.

All authentication via _pat_session.classic_pat_session() per ADR-0216:
gpg-decrypted in-process, never written to env, never logged, never passed
via subprocess argv.

Required scopes on the classic PAT:
  - repo (full)  -- for PR/merge/branch operations
  - workflow     -- for the commit modifying .github/workflows/ci.yml

Usage:
    poetry run python tools/merge_aletheia_603_audit_gate.py [--dry-run]
                                                              [--skip-584-nudge]
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

REPO_OWNER = "martymcenroe"
REPO_NAME = "Aletheia"
GH_API = "https://api.github.com"
ISSUE_NUMBER = 603
BRANCH_NAME = "603-remove-audit-schedule-gate"
WORKFLOW_PATH = ".github/workflows/ci.yml"
LOCAL_FILE = Path("C:/Users/mcwiz/Projects/Aletheia/.github/workflows/ci.yml")
COMPANION_PR = 584
HTTP_TIMEOUT_S = 30
POLL_INTERVAL_S = 10
MERGEABLE_TIMEOUT_S = 600

PR_TITLE = "ci: remove abandoned audit-schedule gate (Closes #603)"

COMMIT_MESSAGE = """ci: remove abandoned audit-schedule gate (Closes #603)

The audit-schedule CI job runs tools/audit_schedule_check.py against
docs/0800-audit-*.md schedule data that no longer exists in the repo.
The audit policy was retired but the enforcing job was not.

Effect: every PR shows UNSTABLE, main's nightly CI reports failure.
Not a required check, so no merge gate is being lifted -- just CI noise.

The audit_*.py scripts in tools/ remain in place; their cleanup is a
separate decision.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
"""

PR_BODY = """## Summary

Removes the `audit-schedule` job from `.github/workflows/ci.yml`. The job
referenced `tools/audit_schedule_check.py` against `docs/0800-audit-*.md`
schedule data that no longer exists in the repo, so it failed on every PR
(UNSTABLE mergeable_state) and on every nightly main run.

Not a required check; no merge gate is being lifted -- just CI noise.

The local `git push` was rejected because the fine-grained PAT lacks
`workflow` scope. Landed via `tools/merge_aletheia_603_audit_gate.py`
following ADR-0216 (in-process classic PAT decryption).

Closes #603.
"""


def _gh_headers(pat: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def get_file_info(path: str, ref: str, pat: str) -> dict[str, Any]:
    r = requests.get(
        f"{GH_API}/repos/{REPO_OWNER}/{REPO_NAME}/contents/{path}",
        params={"ref": ref},
        headers=_gh_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json()


def get_branch_head(branch: str, pat: str) -> str:
    r = requests.get(
        f"{GH_API}/repos/{REPO_OWNER}/{REPO_NAME}/git/refs/heads/{branch}",
        headers=_gh_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json()["object"]["sha"]


def create_branch(branch: str, source_sha: str, pat: str) -> None:
    r = requests.post(
        f"{GH_API}/repos/{REPO_OWNER}/{REPO_NAME}/git/refs",
        headers=_gh_headers(pat),
        json={"ref": f"refs/heads/{branch}", "sha": source_sha},
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code == 422:
        existing_sha = get_branch_head(branch, pat)
        if existing_sha != source_sha:
            raise RuntimeError(
                f"Branch refs/heads/{branch} already exists pointing at "
                f"{existing_sha[:8]} (expected {source_sha[:8]}). "
                f"Either delete the stale ref or rerun with a different branch name."
            )
        print("  (branch ref already exists at expected sha; idempotent)")
        return
    r.raise_for_status()


def update_file_on_branch(
    path: str, file_sha: str, content_bytes: bytes, message: str, branch: str, pat: str
) -> None:
    r = requests.put(
        f"{GH_API}/repos/{REPO_OWNER}/{REPO_NAME}/contents/{path}",
        headers=_gh_headers(pat),
        json={
            "message": message,
            "content": base64.b64encode(content_bytes).decode("ascii"),
            "sha": file_sha,
            "branch": branch,
        },
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code == 409:
        raise RuntimeError(
            f"PUT /contents returned 409 Conflict. Likely the branch already "
            f"has a newer version of {path} from a previous run. Delete the "
            f"branch ref and rerun, or inspect the branch state manually."
        )
    r.raise_for_status()


def find_existing_pr(head: str, pat: str) -> int | None:
    r = requests.get(
        f"{GH_API}/repos/{REPO_OWNER}/{REPO_NAME}/pulls",
        params={"state": "open", "head": f"{REPO_OWNER}:{head}", "per_page": 5},
        headers=_gh_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    prs = r.json()
    return prs[0]["number"] if prs else None


def create_pr(head: str, base: str, title: str, body: str, pat: str) -> int:
    r = requests.post(
        f"{GH_API}/repos/{REPO_OWNER}/{REPO_NAME}/pulls",
        headers=_gh_headers(pat),
        json={"title": title, "head": head, "base": base, "body": body},
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json()["number"]


def get_mergeable_state(pr_number: int, pat: str) -> str | None:
    r = requests.get(
        f"{GH_API}/repos/{REPO_OWNER}/{REPO_NAME}/pulls/{pr_number}",
        headers=_gh_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json().get("mergeable_state")


def wait_for_mergeable(pr_number: int, pat: str, timeout_s: int) -> str:
    """Poll until mergeable_state is mergeable. Returns the final state.

    Accepts 'clean' OR 'unstable'. The bootstrap reality of this PR: it
    deletes the audit-schedule job, but until merged, audit-schedule still
    runs on the PR itself and fails -- making mergeable_state stuck at
    'unstable' forever. The only path to 'clean' is to merge through
    unstable. fleet_delete_pr_sentinel.py uses the same logic for the same
    reason (the legacy check fails on the PR that deletes the legacy check).

    'dirty' / 'blocked' return as-is for the caller to abort.
    """
    deadline = time.time() + timeout_s
    last = "unknown"
    polled_once = False
    while time.time() < deadline:
        state = get_mergeable_state(pr_number, pat) or "unknown"
        last = state
        print(f"  mergeable_state: {state}")
        if state in ("clean", "unstable"):
            return state
        if state == "dirty":
            return state
        if state == "blocked" and polled_once:
            return state
        polled_once = True
        time.sleep(POLL_INTERVAL_S)
    return last


def merge_pr_squash(pr_number: int, pat: str) -> str:
    r = requests.put(
        f"{GH_API}/repos/{REPO_OWNER}/{REPO_NAME}/pulls/{pr_number}/merge",
        headers=_gh_headers(pat),
        json={"merge_method": "squash"},
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json().get("sha", "")


def delete_branch_ref(branch: str, pat: str) -> None:
    r = requests.delete(
        f"{GH_API}/repos/{REPO_OWNER}/{REPO_NAME}/git/refs/heads/{branch}",
        headers=_gh_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code in (404, 422):
        print("  (branch already deleted -- likely repo auto-delete-head setting)")
        return
    r.raise_for_status()


def nudge_pr(pr_number: int, pat: str) -> None:
    """Close then reopen a PR to re-trigger CI checks."""
    for state in ("closed", "open"):
        r = requests.patch(
            f"{GH_API}/repos/{REPO_OWNER}/{REPO_NAME}/pulls/{pr_number}",
            headers=_gh_headers(pat),
            json={"state": state},
            timeout=HTTP_TIMEOUT_S,
        )
        r.raise_for_status()


def land_change(pat: str) -> tuple[int, str]:
    """Run the full ladder. Returns (pr_number, merge_sha)."""
    content = LOCAL_FILE.read_bytes()
    # Normalize CRLF -> LF. The Contents API stores the bytes verbatim; on
    # Windows with core.autocrlf=true the working tree is CRLF but blobs
    # are LF. Submitting raw bytes flips the whole file's line endings on
    # origin and creates a noisy whole-file diff. Normalize to match what
    # `git commit` would have produced.
    content = content.replace(b"\r\n", b"\n")
    if b"\n  audit-schedule:" in content:
        raise RuntimeError(
            f"Local file {LOCAL_FILE} still contains the audit-schedule job. "
            f"Refusing to commit a non-fix as a fix."
        )

    file_info = get_file_info(WORKFLOW_PATH, "main", pat)
    main_file_sha = file_info["sha"]
    print(f"main file sha: {main_file_sha[:8]}")

    main_head = get_branch_head("main", pat)
    print(f"main HEAD:     {main_head[:8]}")

    existing = find_existing_pr(BRANCH_NAME, pat)
    if existing is not None:
        print(f"Existing PR #{existing} found; resuming at poll step.")
        pr_number = existing
    else:
        create_branch(BRANCH_NAME, main_head, pat)
        print(f"branch ref created: refs/heads/{BRANCH_NAME}")

        update_file_on_branch(
            path=WORKFLOW_PATH,
            file_sha=main_file_sha,
            content_bytes=content,
            message=COMMIT_MESSAGE,
            branch=BRANCH_NAME,
            pat=pat,
        )
        print("file updated on branch")

        try:
            pr_number = create_pr(
                head=BRANCH_NAME,
                base="main",
                title=PR_TITLE,
                body=PR_BODY,
                pat=pat,
            )
            print(f"PR opened: #{pr_number}")
        except Exception:
            print(
                f"\nERROR after branch ref + commit creation:\n"
                f"  Branch on origin: refs/heads/{BRANCH_NAME}\n"
                f"  Manual cleanup: DELETE /repos/{REPO_OWNER}/{REPO_NAME}/"
                f"git/refs/heads/{BRANCH_NAME}\n"
            )
            raise

    print(f"Polling mergeable_state (timeout {MERGEABLE_TIMEOUT_S}s)...")
    state = wait_for_mergeable(pr_number, pat, MERGEABLE_TIMEOUT_S)
    if state not in ("clean", "unstable"):
        raise RuntimeError(
            f"PR #{pr_number} did not reach a mergeable state "
            f"(final state: {state!r}). REFUSING to merge.\n"
            f"  PR: https://github.com/{REPO_OWNER}/{REPO_NAME}/pull/{pr_number}\n"
            f"  Branch ref left in place: refs/heads/{BRANCH_NAME}"
        )

    merge_sha = merge_pr_squash(pr_number, pat)
    print(f"merged at: {merge_sha[:8]}")

    delete_branch_ref(BRANCH_NAME, pat)

    return pr_number, merge_sha


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dry-run", action="store_true",
                        help="List what would happen; take no action.")
    parser.add_argument("--skip-584-nudge", action="store_true",
                        help="Skip the close+reopen of PR #584.")
    args = parser.parse_args()

    if not LOCAL_FILE.exists():
        print(f"ERROR: local file missing: {LOCAL_FILE}")
        return 1

    if args.dry_run:
        print(f"[DRY-RUN] target: {REPO_OWNER}/{REPO_NAME}")
        print(f"[DRY-RUN] would create branch: {BRANCH_NAME}")
        print(f"[DRY-RUN] would update {WORKFLOW_PATH}")
        print(f"[DRY-RUN] would open PR: {PR_TITLE}")
        if not args.skip_584_nudge:
            print(f"[DRY-RUN] would nudge PR #{COMPANION_PR}")
        return 0

    with classic_pat_session() as pat:
        try:
            pr_number, merge_sha = land_change(pat)
        except Exception as e:  # noqa: BLE001
            print(f"FATAL: {e}")
            return 2

        print(f"\nMain change landed: PR #{pr_number} merged at {merge_sha[:8]}")

        if not args.skip_584_nudge:
            try:
                nudge_pr(COMPANION_PR, pat)
                print(f"PR #{COMPANION_PR} closed+reopened (re-triggered checks)")
            except requests.HTTPError as e:
                print(f"WARNING: PR #{COMPANION_PR} nudge failed -- "
                      f"manual close+reopen needed. {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
