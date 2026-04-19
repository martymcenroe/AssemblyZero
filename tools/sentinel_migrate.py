#!/usr/bin/env python3
"""Migrate outlier repos to fleet-standard pr-sentinel branch protection.

Issue #960 / #886 Phase 2.

Per `data/branch-protection-audit.csv`, two repos in the fleet
(AssemblyZero + sextant) gate branch protection on the legacy
`issue-reference` check (app_id 15368, GitHub Actions workflow). The
fleet-standard is `pr-sentinel / issue-reference` (app_id 2975092,
Cloudflare Worker), which recognizes the `No-Issue:` exemption that
dependabot and other automated tools rely on.

This script flips both outlier repos to the fleet-standard context.
It uses the in-process classic-PAT pattern from #959: the PAT is
gpg-decrypted inside this Python process, lives only as a local heap
variable in the with-block, and is consumed by `requests` directly —
never via `gh` subprocess, never via env, never via argv.

Defensive checks (per repo):
  1. Confirm the repo is in the expected outlier state (currently
     gated on `issue-reference`); refuse to touch repos already on
     the fleet-standard.
  2. Confirm the worker check (`pr-sentinel / issue-reference`) is
     SUCCESS on the latest commit on `main`; refuse to migrate to a
     check that would block all subsequent PRs.

Usage:
    poetry run python tools/sentinel_migrate.py [--dry-run]

`--dry-run` prints the GET → diff → would-PUT plan without making the
PUT call. Default is live execution.

The gpg-encrypted PAT must exist at ~/.secrets/classic-pat.gpg.
gpg-agent prompts on first call and caches the passphrase per its TTL.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pat_session import classic_pat_session  # noqa: E402

GITHUB_USER = "martymcenroe"
GH_API = "https://api.github.com"
OLD_CONTEXT = "issue-reference"
NEW_CONTEXT = "pr-sentinel / issue-reference"
WORKER_APP_ID = 2975092
AUDIT_CSV = Path(__file__).resolve().parent.parent / "data" / "branch-protection-audit.csv"
HTTP_TIMEOUT_S = 30


def _gh_headers(pat: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def find_outliers(audit_csv: Path = AUDIT_CSV) -> list[str]:
    """Return repo names where branch protection gates on OLD_CONTEXT."""
    outliers: list[str] = []
    with audit_csv.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("contexts") == OLD_CONTEXT:
                outliers.append(row["repo"])
    return outliers


def get_branch_protection(repo: str, pat: str) -> dict[str, Any]:
    r = requests.get(
        f"{GH_API}/repos/{GITHUB_USER}/{repo}/branches/main/protection",
        headers=_gh_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json()


def get_worker_check_status(repo: str, pat: str) -> str | None:
    """Return the conclusion of the worker check on the most recent PR.

    The Cloudflare Worker posts `pr-sentinel / issue-reference` only on PR
    events (opened, synchronize, edited, reopened) — NOT on push-to-main.
    So we verify the worker is healthy by checking its conclusion on the
    most recent PR's head commit (any state — open, closed, or merged).

    Returns 'success', 'failure', 'neutral', etc., or None if no PR exists
    or the check is missing on the most recent PR's head commit.
    """
    pr_resp = requests.get(
        f"{GH_API}/repos/{GITHUB_USER}/{repo}/pulls",
        params={"state": "all", "per_page": 1, "sort": "updated", "direction": "desc"},
        headers=_gh_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    pr_resp.raise_for_status()
    prs = pr_resp.json()
    if not prs:
        return None
    head_sha = prs[0]["head"]["sha"]

    cr_resp = requests.get(
        f"{GH_API}/repos/{GITHUB_USER}/{repo}/commits/{head_sha}/check-runs",
        params={"per_page": 100},
        headers=_gh_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    cr_resp.raise_for_status()
    for run in cr_resp.json().get("check_runs", []):
        if run.get("name") == NEW_CONTEXT:
            return run.get("conclusion")
    return None


def build_put_payload(current: dict[str, Any]) -> dict[str, Any]:
    """Build the PUT payload from a GET response, swapping the required check.

    PUT body shape differs from GET response shape (GitHub API quirk):
      - GET nests fields under `required_status_checks` / `required_pull_request_reviews`
        with extra metadata (urls, etc.)
      - PUT expects flatter, normalized objects with only the writable fields.
    """
    # required_status_checks: replace OLD_CONTEXT with NEW_CONTEXT in `checks`
    rsc_in = current.get("required_status_checks") or {}
    payload_rsc = {
        "strict": rsc_in.get("strict", False),
        "checks": [
            {"context": NEW_CONTEXT, "app_id": WORKER_APP_ID},
        ],
    }

    # required_pull_request_reviews: pass through writable fields only
    rprv_in = current.get("required_pull_request_reviews") or {}
    payload_rprv: dict[str, Any] | None = None
    if rprv_in:
        payload_rprv = {
            "dismiss_stale_reviews": rprv_in.get("dismiss_stale_reviews", False),
            "require_code_owner_reviews": rprv_in.get("require_code_owner_reviews", False),
            "required_approving_review_count": rprv_in.get("required_approving_review_count", 1),
        }
        if "require_last_push_approval" in rprv_in:
            payload_rprv["require_last_push_approval"] = rprv_in["require_last_push_approval"]

    # restrictions: PUT requires a value (object or null) when the field is
    # present in the GET response, even if all sub-fields are empty.
    restrictions_in = current.get("restrictions")
    payload_restrictions: dict[str, Any] | None = None
    if restrictions_in:
        payload_restrictions = {
            "users": [u["login"] for u in restrictions_in.get("users", [])],
            "teams": [t["slug"] for t in restrictions_in.get("teams", [])],
            "apps": [a["slug"] for a in restrictions_in.get("apps", [])],
        }

    payload: dict[str, Any] = {
        "required_status_checks": payload_rsc,
        "enforce_admins": current.get("enforce_admins", {}).get("enabled", True),
        "required_pull_request_reviews": payload_rprv,
        "restrictions": payload_restrictions,
    }

    # GitHub allows a few optional extras to pass through if they were set.
    for opt in ("required_linear_history", "allow_force_pushes",
                "allow_deletions", "block_creations",
                "required_conversation_resolution", "lock_branch",
                "allow_fork_syncing"):
        v = current.get(opt)
        if isinstance(v, dict) and "enabled" in v:
            payload[opt] = v["enabled"]
        elif v is not None:
            payload[opt] = v

    return payload


def put_branch_protection(repo: str, payload: dict[str, Any], pat: str) -> dict[str, Any]:
    r = requests.put(
        f"{GH_API}/repos/{GITHUB_USER}/{repo}/branches/main/protection",
        headers=_gh_headers(pat),
        json=payload,
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json()


def current_contexts(protection: dict[str, Any]) -> list[str]:
    """Return the list of context names currently required, regardless of
    whether they live in `contexts` (legacy) or `checks` (new)."""
    rsc = protection.get("required_status_checks") or {}
    if rsc.get("checks"):
        return [c["context"] for c in rsc["checks"]]
    return list(rsc.get("contexts") or [])


def migrate_repo(repo: str, pat: str, dry_run: bool) -> str:
    """Migrate one repo. Returns a one-line status string."""
    try:
        current = get_branch_protection(repo, pat)
    except requests.HTTPError as e:
        return f"{repo}: ERROR fetching current protection — {e}"

    contexts_now = current_contexts(current)
    if NEW_CONTEXT in contexts_now and OLD_CONTEXT not in contexts_now:
        return f"{repo}: already on fleet-standard, skipping"
    if OLD_CONTEXT not in contexts_now:
        return (
            f"{repo}: REFUSING — current contexts={contexts_now} "
            f"do not match expected outlier shape (expected {OLD_CONTEXT!r})"
        )

    worker_status = get_worker_check_status(repo, pat)
    if worker_status != "success":
        return (
            f"{repo}: REFUSING — worker check {NEW_CONTEXT!r} on main is "
            f"{worker_status!r} (must be 'success' before migration)"
        )

    payload = build_put_payload(current)

    if dry_run:
        diff = json.dumps(
            {"current_contexts": contexts_now, "would_set": payload["required_status_checks"]},
            indent=2,
        )
        return f"{repo}: DRY-RUN\n{diff}"

    try:
        put_branch_protection(repo, payload, pat)
    except requests.HTTPError as e:
        return f"{repo}: ERROR applying protection — {e} {getattr(e.response, 'text', '')[:200]}"

    after = get_branch_protection(repo, pat)
    after_contexts = current_contexts(after)
    if NEW_CONTEXT in after_contexts and OLD_CONTEXT not in after_contexts:
        return f"{repo}: {OLD_CONTEXT} → {NEW_CONTEXT}  ✓"
    return (
        f"{repo}: PUT succeeded but verification did not show expected state — "
        f"after={after_contexts}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print would-be PUT payload without applying.",
    )
    args = parser.parse_args()

    outliers = find_outliers(AUDIT_CSV)
    if not outliers:
        print("No outlier repos found in audit CSV. Nothing to do.")
        return 0

    print(f"Found {len(outliers)} outlier repo(s): {outliers}")

    with classic_pat_session() as pat:
        for repo in outliers:
            print(migrate_repo(repo, pat, args.dry_run))

    return 0


if __name__ == "__main__":
    sys.exit(main())
