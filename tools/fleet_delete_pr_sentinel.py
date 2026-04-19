#!/usr/bin/env python3
"""Fleet-wide deletion of legacy `.github/workflows/pr-sentinel.yml`.

Issue #975 / #886 Phase 3.

For each repo that still carries the legacy per-repo workflow file
(while branch protection already gates on the Cloudflare Worker check
`pr-sentinel / issue-reference`), this tool:

  1. Skips if the file doesn't exist (idempotent — handles re-runs).
  2. Skips if there's already an open deletion PR for the file (idempotent).
  3. Files an issue describing the cleanup.
  4. Creates a branch from main HEAD.
  5. Deletes the file via the Contents API (creates a commit on the branch).
  6. Opens a PR with `Closes #N` in title and body.
  7. Polls mergeable_state until it's mergeable (clean OR unstable —
     unstable means non-required checks are failing, which is fine
     because the only required check is the worker, which our
     `Closes #N` PR satisfies).
  8. Squash-merges via API.

All authentication via _pat_session.classic_pat_session() — the classic
PAT is gpg-decrypted inside this Python process and lives only as a
local heap variable. Never written to env, never passed via subprocess.

Required scopes on the classic PAT:
  - repo (full)        — for issue/branch/PR/merge operations
  - workflow           — for editing .github/workflows/* (the deletion
                         creates a commit modifying a workflow file)

Usage:
    poetry run python tools/fleet_delete_pr_sentinel.py [--dry-run]
                                                        [--repos REPO1,REPO2]

`--dry-run` lists what would happen, takes no action.
`--repos` overrides the default discovery (a GitHub code search) with an
explicit comma-separated list of `owner/repo` strings — useful for
running against a single repo first.

Verified safe by today's manual runs against AssemblyZero (#974) and
sextant (#27).
"""

from __future__ import annotations

import argparse
import base64
import re
import sys
import time
from pathlib import Path
from typing import Any

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pat_session import classic_pat_session  # noqa: E402

GITHUB_USER = "martymcenroe"
GH_API = "https://api.github.com"
WORKFLOW_PATH = ".github/workflows/pr-sentinel.yml"
DELETION_PR_TITLE_PREFIX = "chore: delete legacy pr-sentinel.yml"
HTTP_TIMEOUT_S = 30
POLL_INTERVAL_S = 10
# 900s default (was 300s in PR #976). The first fleet run found ~10% of
# repos legitimately took longer than 5 min for Cerberus-AZ to post its
# approving review. 15 min covers the observed tail. Override with
# --mergeable-timeout for unusual cases.
MERGEABLE_TIMEOUT_S = 900
MAX_REPOS_PER_RUN = 50  # safety cap

# Issue-ref pattern matched by the Cloudflare Worker's verify-issues.js.
# Either bare `#N` (same-repo, populated when caller supplies just an issue
# number) or fully-qualified `owner/repo#N` (cross-repo, used when the
# target repo has issues disabled).
EXTERNAL_REF_PATTERN = re.compile(
    r"^(?:[\w.-]+/[\w.-]+)?#\d+$"
)

ISSUE_BODY = """## Context

Branch protection on this repo gates on the Cloudflare Worker check
`pr-sentinel / issue-reference` (app_id 2975092). The legacy per-repo
`.github/workflows/pr-sentinel.yml` (app_id 15368) is now redundant —
and actively posts FAILURE checks on every dependabot PR (since it
doesn't recognize `No-Issue:` exemptions), making mergeable_state
report `unstable` even when the required check passes.

## Scope

Delete `.github/workflows/pr-sentinel.yml`. No other changes — the
auto-reviewer chain uses substring matching that catches the worker's
check name after this deletion.

## Companion changes already merged

- martymcenroe/AssemblyZero#974
- martymcenroe/sextant#27

This is part of #886 Phase 3 (fleet-wide retirement). Filed and
processed automatically by `tools/fleet_delete_pr_sentinel.py`.
"""

PR_BODY = """## Summary

Deletes `.github/workflows/pr-sentinel.yml`. Closes #{issue_number}.

Branch protection on this repo gates on the Cloudflare Worker check
`pr-sentinel / issue-reference` (app_id 2975092). The legacy per-repo
workflow (app_id 15368) is redundant — and actively posts FAILURE
checks on every dependabot PR since it doesn't recognize `No-Issue:`.

## Companion changes already merged

- martymcenroe/AssemblyZero#974
- martymcenroe/sextant#27

Part of #886 Phase 3 (fleet-wide retirement). Filed and processed
automatically by `tools/fleet_delete_pr_sentinel.py`.

🤖 Filed by tools/fleet_delete_pr_sentinel.py
"""


def _gh_headers(pat: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def discover_repos(pat: str) -> list[str]:
    """Find repos in the user's account that contain WORKFLOW_PATH.

    Uses GitHub code search. Returns a sorted list of repo names
    (without the owner prefix; we hardcode GITHUB_USER).
    """
    r = requests.get(
        f"{GH_API}/search/code",
        params={
            "q": f"filename:pr-sentinel.yml user:{GITHUB_USER}",
            "per_page": 100,
        },
        headers=_gh_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    full_names = {item["repository"]["full_name"] for item in r.json().get("items", [])}
    repos = sorted(name.split("/", 1)[1] for name in full_names if name.startswith(f"{GITHUB_USER}/"))
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


def find_existing_deletion_pr(repo: str, pat: str) -> int | None:
    """Return the number of an open deletion PR if one exists."""
    r = requests.get(
        f"{GH_API}/repos/{GITHUB_USER}/{repo}/pulls",
        params={"state": "open", "per_page": 100},
        headers=_gh_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    for pr in r.json():
        if pr.get("title", "").startswith(DELETION_PR_TITLE_PREFIX):
            return pr["number"]
    return None


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


def delete_file_on_branch(
    repo: str, path: str, file_sha: str, message: str, branch: str, pat: str
) -> None:
    r = requests.delete(
        f"{GH_API}/repos/{GITHUB_USER}/{repo}/contents/{path}",
        headers=_gh_headers(pat),
        json={"message": message, "sha": file_sha, "branch": branch},
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
    repo: str, pr_number: int, pat: str,
    timeout_s: int = MERGEABLE_TIMEOUT_S,
    sleep_fn=time.sleep,
) -> str:
    """Poll until the PR is in a mergeable state. Returns the final state.

    Accepts both 'clean' (all checks pass) and 'unstable' (only non-required
    checks failing — gh pr merge --squash succeeds in both cases).

    `dirty` (merge conflict) is returned immediately — won't resolve via
    waiting. `blocked` is treated the same: the required check or the
    approval is missing, and unlike auto-reviewer-pending state, `blocked`
    does not become `clean` by itself within reasonable time.

    Note: `blocked` CAN flip to `clean` later if Cerberus posts an
    approving review after our wait timer started but before it fired,
    so we only return `blocked` after at least one poll cycle.
    """
    deadline = time.time() + timeout_s
    last_state = "unknown"
    polled_at_least_once = False
    while time.time() < deadline:
        state = get_mergeable_state(repo, pr_number, pat) or "unknown"
        last_state = state
        if state in ("clean", "unstable"):
            return state
        if state == "dirty":
            return state
        if state == "blocked" and polled_at_least_once:
            return state  # caller decides whether to abort
        polled_at_least_once = True
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


def process_repo(
    repo: str, pat: str, dry_run: bool,
    mergeable_timeout: int = MERGEABLE_TIMEOUT_S,
    external_issue_ref: str | None = None,
) -> str:
    """Process one repo. Returns a one-line status string.

    Args:
        repo: Owner-less repo name (owner is GITHUB_USER).
        pat: gpg-decrypted classic PAT.
        dry_run: If True, no API mutations.
        mergeable_timeout: Seconds to wait for mergeable_state to resolve.
        external_issue_ref: If set (e.g. "owner/repo#123" or "#123"), skip
            create_issue and use the supplied ref in the PR title/body.
            Required for repos that have issues disabled.
    """
    file_info = get_file_info(repo, WORKFLOW_PATH, pat)
    if file_info is None:
        return f"{repo}: {WORKFLOW_PATH} not present, skipping"

    existing_pr = find_existing_deletion_pr(repo, pat)
    if existing_pr is not None:
        return f"{repo}: open deletion PR already exists (#{existing_pr}), skipping"

    if dry_run:
        ref_note = f" using external ref {external_issue_ref}" if external_issue_ref else ""
        return f"{repo}: WOULD delete {WORKFLOW_PATH} (sha={file_info['sha'][:8]}) via new issue + PR{ref_note}"

    if external_issue_ref:
        # Use the supplied ref directly. Branch name uses the issue number
        # portion of the ref so it remains unique and informative.
        ref_for_pr = external_issue_ref  # e.g., "martymcenroe/AssemblyZero#980"
        ref_number_only = external_issue_ref.split("#")[-1]
        branch = f"delete-pr-sentinel-{ref_number_only}"
    else:
        issue_number = create_issue(
            repo,
            title="chore: delete legacy .github/workflows/pr-sentinel.yml",
            body=ISSUE_BODY,
            pat=pat,
        )
        ref_for_pr = f"#{issue_number}"
        branch = f"{issue_number}-fix"

    main_sha = get_branch_head(repo, "main", pat)
    create_branch(repo, branch, main_sha, pat)

    delete_file_on_branch(
        repo,
        path=WORKFLOW_PATH,
        file_sha=file_info["sha"],
        message=f"chore: delete legacy pr-sentinel.yml (Closes {ref_for_pr})",
        branch=branch,
        pat=pat,
    )

    pr_title = f"chore: delete legacy pr-sentinel.yml (Closes {ref_for_pr})"
    pr_number = create_pr(
        repo,
        head=branch,
        base="main",
        title=pr_title,
        body=PR_BODY.format(issue_number=ref_for_pr),
        pat=pat,
    )

    final_state = wait_for_mergeable(repo, pr_number, pat, timeout_s=mergeable_timeout)
    if final_state not in ("clean", "unstable"):
        return (
            f"{repo}: PR #{pr_number} did not become mergeable "
            f"(final state: {final_state}). Branch + issue retained for human review."
        )

    try:
        merge_sha = merge_pr(repo, pr_number, pat)
    except requests.HTTPError as e:
        return f"{repo}: PR #{pr_number} merge failed — {e}"

    return f"{repo}: PR #{pr_number} merged at {merge_sha[:8]}  ✓"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dry-run", action="store_true",
                        help="List what would happen; take no action.")
    parser.add_argument("--repos", default="",
                        help="Comma-separated owner-less repo names. "
                             "Defaults to GitHub code-search discovery.")
    parser.add_argument("--mergeable-timeout", type=int, default=MERGEABLE_TIMEOUT_S,
                        help=f"Seconds to wait for PR mergeable_state to "
                             f"resolve (default: {MERGEABLE_TIMEOUT_S}).")
    parser.add_argument("--external-issue-ref", default=None,
                        help="Use an external issue reference (e.g. "
                             "'owner/repo#123' or '#123') instead of "
                             "filing a new issue in the target repo. "
                             "Required when the target has issues disabled. "
                             "When set, --repos must contain exactly one repo.")
    args = parser.parse_args()

    if args.external_issue_ref:
        if not EXTERNAL_REF_PATTERN.match(args.external_issue_ref):
            print(f"Invalid --external-issue-ref: {args.external_issue_ref!r}. "
                  f"Expected '#N' or 'owner/repo#N'.")
            return 1
        if not args.repos or "," in args.repos:
            print("--external-issue-ref requires --repos with exactly one repo "
                  "(prevents pointing many PRs at the same closing issue).")
            return 1

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
                line = process_repo(
                    repo, pat, args.dry_run,
                    mergeable_timeout=args.mergeable_timeout,
                    external_issue_ref=args.external_issue_ref,
                )
            except requests.HTTPError as e:
                line = f"{repo}: ERROR — {e} {getattr(e.response, 'text', '')[:200]}"
            except Exception as e:  # noqa: BLE001
                line = f"{repo}: UNEXPECTED ERROR — {type(e).__name__}: {e}"
            print(line)
            results.append(line)

        merged = sum(1 for r in results if "merged at" in r)
        skipped = sum(1 for r in results if "skipping" in r)
        errors = sum(1 for r in results if "ERROR" in r)
        print()
        print(f"=== Summary === merged: {merged}  skipped: {skipped}  errored: {errors}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
