#!/usr/bin/env python3
"""Fleet-wide set of `.unleashed.json` `claude.permissionMode = "auto"`.

AssemblyZero #979 / martymcenroe/unleashed#343.

For each user-owned repo that contains a `.unleashed.json` with no
`claude.permissionMode` set (or set to anything other than `auto`), this
tool:

  1. Skips if the file does not exist.
  2. Skips if `claude.permissionMode` is already `"auto"` (idempotent).
  3. Skips if an open PR from a prior run of this tool exists (idempotent).
  4. Files a per-repo issue describing the change.
  5. Creates a branch from main HEAD.
  6. Edits `.unleashed.json` via Contents API: adds (or creates) the
     `claude` block with `permissionMode: "auto"`, preserving all other
     fields. Re-serializes with 2-space indent + trailing newline.
  7. Opens a PR with `Closes #N` in title and body.
  8. Polls `mergeable_state` until `clean` or `unstable`.
  9. Squash-merges via API.

All auth via `_pat_session.classic_pat_session()` — gpg-decrypted classic
PAT, lives only as a local heap variable. Never written to env, never
passed via subprocess.

Required scopes on the classic PAT:
  - repo (full) — issue/branch/PR/merge operations + Contents edits

Usage:
    poetry run python tools/fleet_set_permission_mode.py [--dry-run]
                                                         [--repos REPO1,REPO2]

`--dry-run` lists what would happen, takes no action.
`--repos` overrides code-search discovery with an explicit comma-
separated list of owner-less repo names.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from pathlib import Path
from typing import Any

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pat_session import classic_pat_session  # noqa: E402

GITHUB_USER = "martymcenroe"
GH_API = "https://api.github.com"
TARGET_PATH = ".unleashed.json"
PR_TITLE_PREFIX = "feat: set claude.permissionMode=auto"
TARGET_KEY = "permissionMode"
TARGET_VALUE = "auto"
TARGET_BLOCK = "claude"
UMBRELLA_REF = "martymcenroe/unleashed#343"
HTTP_TIMEOUT_S = 30
POLL_INTERVAL_S = 10
MERGEABLE_TIMEOUT_S = 300
MAX_REPOS_PER_RUN = 100

ISSUE_BODY = f"""## Context

The unleashed wrapper reads `.unleashed.json` → `claude.permissionMode` and
forwards it to Claude Code via `--permission-mode`. Currently this repo's
`.unleashed.json` does not set the field, so every session starts in
`default` mode and the user has to Shift+Tab into `auto` manually.

## Scope

Set `claude.permissionMode` to `"auto"` in `.unleashed.json`. No other
changes. The `claude` block is created if absent; existing fields (model,
effort, etc.) are preserved.

## Why auto is safe here

The unleashed wrapper already auto-approves `Do you want to proceed?`
permission prompts — that's its purpose. Claude Code's internal `auto`
mode means those prompts are not shown in the first place. Same effective
authority, less PTY noise and fewer auto-approve timing races.

## Umbrella

Tracked in {UMBRELLA_REF}. Filed and processed automatically by
`tools/fleet_set_permission_mode.py` in AssemblyZero.
"""

PR_BODY = f"""## Summary

Adds `"permissionMode": "auto"` to the `claude` block of `.unleashed.json`.
Closes #{{issue_number}}.

The unleashed wrapper reads this field at launch and forwards it as
`--permission-mode auto` to Claude Code, so sessions launch directly in
auto mode instead of requiring a manual Shift+Tab cycle.

## Umbrella

Part of the fleet rollout tracked in {UMBRELLA_REF}. Filed and processed
automatically by `tools/fleet_set_permission_mode.py` in AssemblyZero.
"""


def _gh_headers(pat: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def discover_repos(pat: str) -> list[str]:
    """Find repos in the user's account that contain TARGET_PATH.

    Uses GitHub code search. Returns sorted owner-less repo names.
    """
    r = requests.get(
        f"{GH_API}/search/code",
        params={
            "q": f"path:{TARGET_PATH} user:{GITHUB_USER}",
            "per_page": 100,
        },
        headers=_gh_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    full_names = {item["repository"]["full_name"] for item in r.json().get("items", [])}
    repos = sorted(
        name.split("/", 1)[1]
        for name in full_names
        if name.startswith(f"{GITHUB_USER}/")
    )
    return repos


def get_file_info(repo: str, path: str, pat: str) -> dict[str, Any] | None:
    r = requests.get(
        f"{GH_API}/repos/{GITHUB_USER}/{repo}/contents/{path}",
        params={"ref": "main"},
        headers=_gh_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def find_existing_pr(repo: str, pat: str) -> int | None:
    r = requests.get(
        f"{GH_API}/repos/{GITHUB_USER}/{repo}/pulls",
        params={"state": "open", "per_page": 100},
        headers=_gh_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    for pr in r.json():
        if pr.get("title", "").startswith(PR_TITLE_PREFIX):
            return pr["number"]
    return None


def already_set(current_content_b64: str) -> bool:
    raw = base64.b64decode(current_content_b64).decode("utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return False
    block = data.get(TARGET_BLOCK) or {}
    return block.get(TARGET_KEY) == TARGET_VALUE


def compute_new_content(current_content_b64: str) -> str:
    """Parse, add permissionMode, re-serialize. Returns base64 new content.

    Preserves all other fields. Uses 2-space indent + trailing newline,
    matching the repo's existing convention.
    """
    raw = base64.b64decode(current_content_b64).decode("utf-8")
    data = json.loads(raw)
    block = data.setdefault(TARGET_BLOCK, {})
    block[TARGET_KEY] = TARGET_VALUE
    serialized = json.dumps(data, indent=2) + "\n"
    return base64.b64encode(serialized.encode("utf-8")).decode("ascii")


def create_issue(repo: str, title: str, body: str, pat: str) -> int:
    r = requests.post(
        f"{GH_API}/repos/{GITHUB_USER}/{repo}/issues",
        headers=_gh_headers(pat),
        json={"title": title, "body": body},
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json()["number"]


def get_branch_head(repo: str, branch: str, pat: str) -> str:
    r = requests.get(
        f"{GH_API}/repos/{GITHUB_USER}/{repo}/git/refs/heads/{branch}",
        headers=_gh_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json()["object"]["sha"]


def create_branch(repo: str, branch: str, source_sha: str, pat: str) -> None:
    r = requests.post(
        f"{GH_API}/repos/{GITHUB_USER}/{repo}/git/refs",
        headers=_gh_headers(pat),
        json={"ref": f"refs/heads/{branch}", "sha": source_sha},
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()


def put_file_on_branch(
    repo: str,
    path: str,
    new_content_b64: str,
    file_sha: str,
    message: str,
    branch: str,
    pat: str,
) -> None:
    r = requests.put(
        f"{GH_API}/repos/{GITHUB_USER}/{repo}/contents/{path}",
        headers=_gh_headers(pat),
        json={
            "message": message,
            "content": new_content_b64,
            "sha": file_sha,
            "branch": branch,
        },
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()


def create_pr(
    repo: str, head: str, base: str, title: str, body: str, pat: str
) -> int:
    r = requests.post(
        f"{GH_API}/repos/{GITHUB_USER}/{repo}/pulls",
        headers=_gh_headers(pat),
        json={"title": title, "head": head, "base": base, "body": body},
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json()["number"]


def get_mergeable_state(repo: str, pr_number: int, pat: str) -> str | None:
    r = requests.get(
        f"{GH_API}/repos/{GITHUB_USER}/{repo}/pulls/{pr_number}",
        headers=_gh_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json().get("mergeable_state")


def wait_for_mergeable(
    repo: str, pr_number: int, pat: str, sleep_fn=time.sleep
) -> str:
    deadline = time.time() + MERGEABLE_TIMEOUT_S
    last_state = "unknown"
    while time.time() < deadline:
        state = get_mergeable_state(repo, pr_number, pat) or "unknown"
        last_state = state
        if state in ("clean", "unstable"):
            return state
        if state in ("dirty",):
            return state
        sleep_fn(POLL_INTERVAL_S)
    return last_state


def merge_pr(repo: str, pr_number: int, pat: str) -> str:
    r = requests.put(
        f"{GH_API}/repos/{GITHUB_USER}/{repo}/pulls/{pr_number}/merge",
        headers=_gh_headers(pat),
        json={"merge_method": "squash"},
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json().get("sha", "")


def process_repo(repo: str, pat: str, dry_run: bool) -> str:
    file_info = get_file_info(repo, TARGET_PATH, pat)
    if file_info is None:
        return f"{repo}: {TARGET_PATH} not present, skipping"

    if already_set(file_info["content"]):
        return f"{repo}: {TARGET_BLOCK}.{TARGET_KEY} already '{TARGET_VALUE}', skipping"

    existing_pr = find_existing_pr(repo, pat)
    if existing_pr is not None:
        return f"{repo}: open PR already exists (#{existing_pr}), skipping"

    if dry_run:
        return f"{repo}: WOULD set {TARGET_BLOCK}.{TARGET_KEY}={TARGET_VALUE} (file sha={file_info['sha'][:8]})"

    try:
        new_content_b64 = compute_new_content(file_info["content"])
    except json.JSONDecodeError as e:
        return f"{repo}: malformed {TARGET_PATH} ({e}), skipping"

    issue_number = create_issue(
        repo,
        title="feat: set claude.permissionMode=auto in .unleashed.json",
        body=ISSUE_BODY,
        pat=pat,
    )

    branch = f"{issue_number}-fix"
    main_sha = get_branch_head(repo, "main", pat)
    create_branch(repo, branch, main_sha, pat)

    put_file_on_branch(
        repo,
        path=TARGET_PATH,
        new_content_b64=new_content_b64,
        file_sha=file_info["sha"],
        message=f"feat: set claude.permissionMode=auto (Closes #{issue_number})",
        branch=branch,
        pat=pat,
    )

    pr_title = f"feat: set claude.permissionMode=auto (Closes #{issue_number})"
    pr_number = create_pr(
        repo,
        head=branch,
        base="main",
        title=pr_title,
        body=PR_BODY.format(issue_number=issue_number),
        pat=pat,
    )

    final_state = wait_for_mergeable(repo, pr_number, pat)
    if final_state not in ("clean", "unstable"):
        return (
            f"{repo}: PR #{pr_number} did not become mergeable "
            f"(final state: {final_state}). Branch + issue retained for human review."
        )

    try:
        merge_sha = merge_pr(repo, pr_number, pat)
    except requests.HTTPError as e:
        return f"{repo}: PR #{pr_number} merge failed -- {e}"

    return f"{repo}: PR #{pr_number} merged at {merge_sha[:8]}  OK"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dry-run", action="store_true",
                        help="List what would happen; take no action.")
    parser.add_argument("--repos", default="",
                        help="Comma-separated owner-less repo names. "
                             "Defaults to code-search discovery.")
    args = parser.parse_args()

    with classic_pat_session() as pat:
        if args.repos:
            repos = [r.strip() for r in args.repos.split(",") if r.strip()]
        else:
            repos = discover_repos(pat)

        if not repos:
            print("No repos to process.")
            return 0

        if len(repos) > MAX_REPOS_PER_RUN:
            print(f"Refusing: discovered {len(repos)} repos, "
                  f"safety cap is {MAX_REPOS_PER_RUN}. "
                  f"Use --repos to process a subset.")
            return 1

        print(f"Processing {len(repos)} repo(s){' (DRY-RUN)' if args.dry_run else ''}:")
        results: list[str] = []
        for repo in repos:
            try:
                line = process_repo(repo, pat, args.dry_run)
            except requests.HTTPError as e:
                line = f"{repo}: ERROR -- {e} {getattr(e.response, 'text', '')[:200]}"
            except Exception as e:  # noqa: BLE001
                line = f"{repo}: UNEXPECTED ERROR -- {type(e).__name__}: {e}"
            print(line)
            results.append(line)

        merged = sum(1 for r in results if "merged at" in r)
        skipped = sum(1 for r in results if "skipping" in r)
        errors = sum(1 for r in results if "ERROR" in r)
        would = sum(1 for r in results if "WOULD" in r)
        print()
        print(f"=== Summary === merged: {merged}  skipped: {skipped}  errored: {errors}  would: {would}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
