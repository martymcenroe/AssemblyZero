#!/usr/bin/env python3
"""Backfill .github/dependabot.yml across existing fleet repos (#1569).

The new-repo half of #1334 shipped in new_repo_setup.py: fresh repos get a
version-update `.github/dependabot.yml` at creation time. This is the
existing-fleet half — repos created before that change have Dependabot
*security* updates flipped on (via enable_dependabot.py / #1331) but no
`dependabot.yml`, so they emit only security PRs, never version-update PRs.

What this tool does (per target repo):
  1. GET default branch + check whether `.github/dependabot.yml` already
     exists on it. If present -> skip (idempotent).
  2. Detect ecosystems by probing marker files over the Contents API
     (pyproject.toml -> pip, package.json -> npm, Dockerfile -> docker;
     github-actions always included). Reuses the fleet-standard rendering
     from new_repo_setup.py so the backfilled file is byte-identical to what
     the scaffolder emits for new repos.
  3. Create a tracking issue IN THE TARGET REPO (so the per-repo PR's
     `Closes #N` satisfies that repo's pr-sentinel), branch from the default
     branch, commit the new file via the Contents API, open a PR, wait for it
     to become mergeable (Cerberus auto-approves), and squash-merge.

`.github/dependabot.yml` lives under `.github/` (NOT `.github/workflows/`), so
it needs no `workflow` PAT scope — but landing a file on a protected `main`
still requires the branch+PR+merge flow, which is why this mirrors
fleet_delete_pr_sentinel.py rather than doing a naive direct-to-main PUT.

Per ADR-0216: classic PAT decrypted in-process via classic_pat_session().
The PAT lives only in this Python process's heap; never in env, never in
subprocess argv, never via `gh auth`. **The OPERATOR runs this script, not
the agent** — the in-process protection assumes the Python process is the
operator's, not an agent's child.

Per AssemblyZero standard 0017: `--apply` flag required to mutate. Default is
a dry-run that reports what WOULD change.

Usage:
  poetry run python tools/generate_dependabot_yml.py --repo OWNER/NAME
  poetry run python tools/generate_dependabot_yml.py --repo OWNER/NAME --apply
  poetry run python tools/generate_dependabot_yml.py --fleet
  poetry run python tools/generate_dependabot_yml.py --fleet --apply

Exit codes:
  0 — completed (dry-run or apply); all targets processed without errors
  1 — argument or input error
  2 — one or more per-repo errors during processing (partial state)

Related:
  - #1569 — this issue (existing-fleet backfill)
  - #1334 — parent (new-repo half shipped via new_repo_setup.py)
  - #1331 / enable_dependabot.py — flips the API toggles (sibling tool)
  - ADR-0216 — in-process classic PAT pattern
  - fleet_delete_pr_sentinel.py — the Contents-API + branch + PR + merge template
"""
from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests

# tools/ on path for sibling imports (matches enable_dependabot.py pattern).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pat_session import classic_pat_session  # noqa: E402
from new_repo_setup import (  # noqa: E402
    _DEPENDABOT_ECOSYSTEMS,
    ecosystems_for_markers,
    render_dependabot_yml,
)


GITHUB_USER = "martymcenroe"
GH_API = "https://api.github.com"
DEPENDABOT_PATH = ".github/dependabot.yml"
PR_TITLE_PREFIX = "chore(deps): add dependabot.yml"
HTTP_TIMEOUT_S = 30
POLL_INTERVAL_S = 10
# 900s mirrors fleet_delete_pr_sentinel.py: ~10% of repos take >5 min for
# Cerberus-AZ to post its approving review. Override with --mergeable-timeout.
MERGEABLE_TIMEOUT_S = 900
FLEET_REPO_LIMIT = 200
MAX_REPOS_PER_RUN = 50  # safety cap; capped overflow is logged, never silent

ISSUE_TITLE = "chore(deps): add .github/dependabot.yml version-update config"
ISSUE_BODY = (
    "This repo predates the scaffolder change that ships "
    "`.github/dependabot.yml` at creation time, so it currently emits only "
    "Dependabot *security* PRs — never *version-update* PRs. This adds a "
    "version-update config detecting the repo's ecosystems "
    "(pip / npm / docker / github-actions).\n\n"
    "Fleet backfill tracked in martymcenroe/AssemblyZero#1569."
)


# ────────────────────────────────────────────────────────────────────
# Result type
# ────────────────────────────────────────────────────────────────────


@dataclass
class BackfillResult:
    """Per-repo result. One per target."""
    repo: str
    status: str  # human-readable one-liner
    ok: bool
    skipped: bool = False
    ecosystems: list[str] = field(default_factory=list)


# ────────────────────────────────────────────────────────────────────
# GitHub REST helpers (self-contained, mirrors fleet_delete_pr_sentinel.py)
# ────────────────────────────────────────────────────────────────────


def _gh_headers(pat: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def get_default_branch(repo: str, pat: str) -> str:
    r = requests.get(
        f"{GH_API}/repos/{GITHUB_USER}/{repo}",
        headers=_gh_headers(pat), timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json()["default_branch"]


def file_exists_on_branch(repo: str, path: str, branch: str, pat: str) -> bool:
    """True iff `path` exists on `branch`. 404 -> False."""
    r = requests.get(
        f"{GH_API}/repos/{GITHUB_USER}/{repo}/contents/{path}",
        params={"ref": branch},
        headers=_gh_headers(pat), timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code == 404:
        return False
    r.raise_for_status()
    return True


def detect_ecosystems_via_api(
    repo: str, branch: str, pat: str
) -> list[tuple[str, str]]:
    """Detect dependabot ecosystems by probing marker files over the API.

    Mirrors new_repo_setup.detect_dependabot_ecosystems() but checks marker
    presence via the Contents API instead of a local checkout, so it works
    against any repo without cloning. github-actions is always included
    (appended by ecosystems_for_markers).
    """
    present = {
        marker
        for marker, _eco, _label in _DEPENDABOT_ECOSYSTEMS
        if file_exists_on_branch(repo, marker, branch, pat)
    }
    return ecosystems_for_markers(present)


def find_existing_backfill_pr(repo: str, pat: str) -> Optional[int]:
    """Return the number of an open backfill PR if one exists (idempotency)."""
    r = requests.get(
        f"{GH_API}/repos/{GITHUB_USER}/{repo}/pulls",
        params={"state": "open", "per_page": 100},
        headers=_gh_headers(pat), timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    for pr in r.json():
        if pr.get("title", "").startswith(PR_TITLE_PREFIX):
            return pr["number"]
    return None


def create_issue(repo: str, title: str, body: str, pat: str) -> int:
    r = requests.post(
        f"{GH_API}/repos/{GITHUB_USER}/{repo}/issues",
        headers=_gh_headers(pat),
        json={"title": title, "body": body}, timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json()["number"]


def get_branch_head(repo: str, branch: str, pat: str) -> str:
    r = requests.get(
        f"{GH_API}/repos/{GITHUB_USER}/{repo}/git/refs/heads/{branch}",
        headers=_gh_headers(pat), timeout=HTTP_TIMEOUT_S,
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


def put_new_file_on_branch(
    repo: str, path: str, content: str, message: str, branch: str, pat: str
) -> None:
    """Create a NEW file on `branch` via the Contents API.

    No `sha` field is sent — this is a create, not an update; callers must
    have confirmed the file is absent (idempotency skip) first. Content is
    LF-normalized before base64 so a Windows operator doesn't flip line
    endings on the remote (the ADR-0216 CRLF gotcha).
    """
    normalized = content.replace("\r\n", "\n")
    content_b64 = base64.b64encode(normalized.encode("utf-8")).decode("ascii")
    r = requests.put(
        f"{GH_API}/repos/{GITHUB_USER}/{repo}/contents/{path}",
        headers=_gh_headers(pat),
        json={"message": message, "content": content_b64, "branch": branch},
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


def get_mergeable_state(repo: str, pr_number: int, pat: str) -> Optional[str]:
    r = requests.get(
        f"{GH_API}/repos/{GITHUB_USER}/{repo}/pulls/{pr_number}",
        headers=_gh_headers(pat), timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json().get("mergeable_state")


def wait_for_mergeable(
    repo: str, pr_number: int, pat: str,
    timeout_s: int = MERGEABLE_TIMEOUT_S,
    sleep_fn=time.sleep,
) -> str:
    """Poll until the PR is mergeable. Returns the final state.

    Accepts both 'clean' and 'unstable' (only non-required checks failing —
    squash-merge succeeds in both). 'dirty' (conflict) returns immediately.
    'blocked' returns only after at least one poll cycle (Cerberus may post
    its approving review a beat after the timer starts).
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
            return state
        polled_at_least_once = True
        sleep_fn(POLL_INTERVAL_S)
    return last_state


def merge_pr(repo: str, pr_number: int, pat: str) -> str:
    r = requests.put(
        f"{GH_API}/repos/{GITHUB_USER}/{repo}/pulls/{pr_number}/merge",
        headers=_gh_headers(pat),
        json={"merge_method": "squash"}, timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json().get("sha", "")


# ────────────────────────────────────────────────────────────────────
# Fleet enumeration
# ────────────────────────────────────────────────────────────────────


def list_fleet_repos(user: str = GITHUB_USER) -> list[str]:
    """List user-owned, non-fork, non-archive repo names (owner-less)."""
    result = subprocess.run(
        ["gh", "repo", "list", user,
         "--limit", str(FLEET_REPO_LIMIT),
         "--json", "name,isArchived,isFork"],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        sys.exit(f"Failed to list fleet repos: {result.stderr}")
    repos = json.loads(result.stdout or "[]")
    return sorted(
        r["name"] for r in repos
        if not r.get("isArchived") and not r.get("isFork")
    )


# ────────────────────────────────────────────────────────────────────
# Per-repo processing
# ────────────────────────────────────────────────────────────────────


def process_repo(
    repo: str, pat: str, apply: bool,
    mergeable_timeout: int = MERGEABLE_TIMEOUT_S,
) -> BackfillResult:
    """Backfill one repo. Returns a BackfillResult.

    apply=False is a dry-run: detects state + reports what would change,
    makes NO mutations.
    """
    branch_default = get_default_branch(repo, pat)

    # Idempotency: already has the file -> skip.
    if file_exists_on_branch(repo, DEPENDABOT_PATH, branch_default, pat):
        return BackfillResult(
            repo=repo, status=f"already has {DEPENDABOT_PATH} — skipping",
            ok=True, skipped=True,
        )

    # Idempotency: an open backfill PR is already in flight -> skip.
    existing_pr = find_existing_backfill_pr(repo, pat)
    if existing_pr is not None:
        return BackfillResult(
            repo=repo,
            status=f"open backfill PR already exists (#{existing_pr}) — skipping",
            ok=True, skipped=True,
        )

    ecosystems = detect_ecosystems_via_api(repo, branch_default, pat)
    eco_names = [eco for eco, _label in ecosystems]
    content = render_dependabot_yml(ecosystems)

    if not apply:
        return BackfillResult(
            repo=repo,
            status=(f"WOULD create {DEPENDABOT_PATH} on {branch_default} "
                    f"(ecosystems: {', '.join(eco_names)}) via new issue + PR"),
            ok=True, ecosystems=eco_names,
        )

    issue_number = create_issue(repo, ISSUE_TITLE, ISSUE_BODY, pat)
    ref = f"#{issue_number}"
    branch = f"{issue_number}-add-dependabot-yml"

    head_sha = get_branch_head(repo, branch_default, pat)
    create_branch(repo, branch, head_sha, pat)

    commit_msg = f"chore(deps): add dependabot.yml version-update config (Closes {ref})"
    put_new_file_on_branch(
        repo, DEPENDABOT_PATH, content, commit_msg, branch, pat
    )

    pr_title = f"{PR_TITLE_PREFIX} version-update config (Closes {ref})"
    pr_body = (
        f"Adds `{DEPENDABOT_PATH}` with weekly grouped version-update config "
        f"for: {', '.join(eco_names)}.\n\n"
        f"Generated by `tools/generate_dependabot_yml.py` (fleet backfill, "
        f"martymcenroe/AssemblyZero#1569).\n\n"
        f"Closes {ref}"
    )
    pr_number = create_pr(repo, branch, branch_default, pr_title, pr_body, pat)

    final_state = wait_for_mergeable(repo, pr_number, pat, timeout_s=mergeable_timeout)
    if final_state not in ("clean", "unstable"):
        return BackfillResult(
            repo=repo,
            status=(f"PR #{pr_number} did not become mergeable "
                    f"(final state: {final_state}). Branch + issue retained "
                    f"for human review."),
            ok=False, ecosystems=eco_names,
        )

    try:
        merge_sha = merge_pr(repo, pr_number, pat)
    except requests.RequestException as e:
        return BackfillResult(
            repo=repo,
            status=f"PR #{pr_number} mergeable but merge failed: {e}",
            ok=False, ecosystems=eco_names,
        )
    return BackfillResult(
        repo=repo,
        status=(f"created + merged {DEPENDABOT_PATH} via PR #{pr_number} "
                f"(merge {merge_sha[:8]}, ecosystems: {', '.join(eco_names)})"),
        ok=True, ecosystems=eco_names,
    )


# ────────────────────────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────────────────────────


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Backfill .github/dependabot.yml across existing fleet "
                    "repos (#1569). Per ADR-0216 — operator runs, not the agent.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--repo", metavar="OWNER/NAME",
        help="Single repo to backfill (e.g., martymcenroe/career)",
    )
    group.add_argument(
        "--fleet", action="store_true",
        help="All user-owned non-fork non-archive repos",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Mutate. Default: dry-run (detects state + reports what would change).",
    )
    parser.add_argument(
        "--user", default=GITHUB_USER,
        help=f"GitHub user for --fleet enumeration (default: {GITHUB_USER})",
    )
    parser.add_argument(
        "--mergeable-timeout", type=int, default=MERGEABLE_TIMEOUT_S,
        help=f"Seconds to wait for each PR to become mergeable (default: {MERGEABLE_TIMEOUT_S})",
    )
    args = parser.parse_args(argv)

    if args.repo:
        if "/" not in args.repo:
            print(f"ERROR: --repo expects OWNER/NAME, got {args.repo!r}", file=sys.stderr)
            return 1
        targets = [args.repo.split("/", 1)[1]]
    else:
        targets = list_fleet_repos(args.user)

    if len(targets) > MAX_REPOS_PER_RUN:
        print(f"NOTE: {len(targets)} targets exceeds MAX_REPOS_PER_RUN "
              f"({MAX_REPOS_PER_RUN}); processing the first {MAX_REPOS_PER_RUN}, "
              f"deferring {len(targets) - MAX_REPOS_PER_RUN}. Re-run to continue "
              f"(idempotent skip handles already-done repos).")
        targets = targets[:MAX_REPOS_PER_RUN]

    print(f"Targets: {len(targets)} repo(s)")
    if not args.apply:
        print("DRY-RUN MODE (no mutations). Pass --apply to backfill.")
    print()

    n_errored = 0
    n_skipped = 0
    n_changed = 0
    with classic_pat_session() as pat:
        for name in targets:
            try:
                result = process_repo(name, pat, args.apply, args.mergeable_timeout)
            except requests.RequestException as e:
                result = BackfillResult(repo=name, status=f"ERROR: {e}", ok=False)
            print(f"=== {result.repo} ===")
            print(f"  {result.status}")
            print()
            if not result.ok:
                n_errored += 1
            elif result.skipped:
                n_skipped += 1
            else:
                n_changed += 1

    verb = "changed" if args.apply else "would change"
    print(f"Summary: {n_changed} {verb}, {n_skipped} skipped, {n_errored} errored "
          f"of {len(targets)} target(s).")
    if n_errored:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
