#!/usr/bin/env python3
"""Remediate weak / unprotected branch protection on the 3 named repos
identified by the #1124 audit (Closes #1126).

THIS SCRIPT MUST BE RUN BY THE USER, NOT BY AN AGENT.
It uses an in-process classic PAT (ADR-0216). The PAT is decrypted into
the Python process heap; an agent-spawned subprocess would have
theoretical heap-read access.

What this script does:

  1. Iterates TARGET_REPOS -- a hard-coded list of three repos
     (boostgauge, gh-galaxy-quest, comp-environ) that the #1124 audit
     flagged. NOT parameter-driven so a re-run can't accidentally
     widen scope.
  2. For each target, GETs the current protection state.
  3. Computes the diff against the TARGET_CONFIG (fleet-canonical
     strict config: 1 review, pr-sentinel status check, enforce_admins,
     no force pushes, no deletions).
  4. In --dry-run (default): prints the diff per repo, exits 0.
  5. In --apply --confirm-yes: PUTs the target config per repo,
     prints the resulting state, exits 0 on success.

Idempotent: a repo already at TARGET_CONFIG gets the same PUT and
GitHub no-ops it. Safe to re-run.

Usage:

    # Preview what would change (default; safe)
    poetry run python tools/remediate_fleet_branch_protection.py

    # Actually apply the changes
    poetry run python tools/remediate_fleet_branch_protection.py --apply --confirm-yes

Issue: #1126 | Related: #1124 (audit), ADR-0216 (classic PAT)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pat_session import classic_pat_session  # noqa: E402

GITHUB_USER = "martymcenroe"
GH_API = "https://api.github.com"
HTTP_TIMEOUT_S = 30

# Hard-coded scope (#1126). Not parameter-driven on purpose: a re-run
# must not be able to widen the blast radius via accidental --repos flag.
TARGET_REPOS: tuple[str, ...] = (
    "boostgauge",
    "gh-galaxy-quest",
    "comp-environ",
)

# Canonical strict config. Matches what the 49 STRICT fleet repos use.
TARGET_CONFIG: dict[str, Any] = {
    "required_pull_request_reviews": {
        "required_approving_review_count": 1,
        "dismiss_stale_reviews": False,
        "require_code_owner_reviews": False,
    },
    "required_status_checks": {
        "strict": True,
        "checks": [{"context": "pr-sentinel / issue-reference"}],
    },
    "enforce_admins": True,
    "restrictions": None,
    "allow_force_pushes": False,
    "allow_deletions": False,
}


def _headers(pat: str) -> dict[str, str]:
    return {
        "Authorization": f"token {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def get_default_branch(repo: str, pat: str) -> str | None:
    """Fetch the repo's default branch name. Returns None on any failure."""
    try:
        r = requests.get(
            f"{GH_API}/repos/{GITHUB_USER}/{repo}",
            headers=_headers(pat), timeout=HTTP_TIMEOUT_S,
        )
    except requests.RequestException:
        return None
    if r.status_code >= 300:
        return None
    return r.json().get("default_branch")


def get_current_protection(repo: str, default_branch: str, pat: str) -> dict | None:
    """GET current branch protection. Returns dict on 200, None on 404 / error."""
    try:
        r = requests.get(
            f"{GH_API}/repos/{GITHUB_USER}/{repo}/branches/{default_branch}/protection",
            headers=_headers(pat), timeout=HTTP_TIMEOUT_S,
        )
    except requests.RequestException:
        return None
    if r.status_code == 404:
        return None  # unprotected
    if r.status_code >= 300:
        return None
    return r.json()


def summarize_protection(prot: dict | None) -> dict[str, Any]:
    """Reduce a protection blob to the fields the policy bar cares about."""
    if prot is None:
        return {
            "protected": False,
            "required_reviews": None,
            "has_status_checks": False,
            "enforce_admins": False,
            "allow_force_pushes": False,
            "allow_deletions": False,
        }
    rpr = prot.get("required_pull_request_reviews") or {}
    rsc = prot.get("required_status_checks") or {}
    enforce = prot.get("enforce_admins") or {}
    afp = prot.get("allow_force_pushes") or {}
    adel = prot.get("allow_deletions") or {}
    return {
        "protected": True,
        "required_reviews": rpr.get("required_approving_review_count"),
        "has_status_checks": bool(
            (rsc.get("contexts") or []) or (rsc.get("checks") or [])
        ),
        "enforce_admins": bool(enforce.get("enabled")) if isinstance(enforce, dict) else False,
        "allow_force_pushes": bool(afp.get("enabled")) if isinstance(afp, dict) else False,
        "allow_deletions": bool(adel.get("enabled")) if isinstance(adel, dict) else False,
    }


def diff_lines(summary: dict[str, Any]) -> list[str]:
    """Return per-field deltas vs TARGET_CONFIG. Empty list = no change."""
    deltas: list[str] = []
    target_reviews = TARGET_CONFIG["required_pull_request_reviews"]["required_approving_review_count"]
    if summary["required_reviews"] != target_reviews:
        deltas.append(
            f"required_reviews: {summary['required_reviews']} -> {target_reviews}"
        )
    if not summary["has_status_checks"]:
        deltas.append(
            "required_status_checks: NONE -> [pr-sentinel / issue-reference]"
        )
    if not summary["enforce_admins"]:
        deltas.append(f"enforce_admins: {summary['enforce_admins']} -> True")
    if summary["allow_force_pushes"]:
        deltas.append("allow_force_pushes: True -> False")
    if summary["allow_deletions"]:
        deltas.append("allow_deletions: True -> False")
    if not summary["protected"]:
        deltas.insert(0, "protected: false -> true (creating protection)")
    return deltas


def apply_protection(repo: str, default_branch: str, pat: str) -> bool:
    """PUT the target protection config. Returns True on 2xx."""
    try:
        r = requests.put(
            f"{GH_API}/repos/{GITHUB_USER}/{repo}/branches/{default_branch}/protection",
            headers=_headers(pat),
            json=TARGET_CONFIG,
            timeout=HTTP_TIMEOUT_S,
        )
    except requests.RequestException as e:
        print(f"    PUT failed: {e}")
        return False
    if r.status_code >= 300:
        print(f"    PUT returned {r.status_code}: {r.text[:300]}")
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n")[0])
    parser.add_argument(
        "--apply", action="store_true",
        help="Actually PUT the target config. Default is dry-run.",
    )
    parser.add_argument(
        "--confirm-yes", action="store_true",
        help="Belt-and-braces second flag required alongside --apply.",
    )
    args = parser.parse_args(argv)

    if args.apply and not args.confirm_yes:
        print("ERROR: --apply requires --confirm-yes (a deliberate second flag "
              "to defeat muscle-memory mistakes).", file=sys.stderr)
        return 1

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"Mode: {mode}")
    print(f"Targets: {', '.join(TARGET_REPOS)}")
    print()

    failures: list[str] = []
    no_changes: list[str] = []

    with classic_pat_session() as pat:
        for repo in TARGET_REPOS:
            print(f"--- {repo} ---")
            default = get_default_branch(repo, pat)
            if not default:
                print("  ERROR: could not resolve default branch (repo missing? archived?)")
                failures.append(repo)
                continue
            prot = get_current_protection(repo, default, pat)
            summary = summarize_protection(prot)
            deltas = diff_lines(summary)

            if not deltas:
                print("  no changes needed (already at target config)")
                no_changes.append(repo)
                continue

            print(f"  branch: {default}")
            print("  changes:")
            for d in deltas:
                print(f"    - {d}")

            if not args.apply:
                continue

            ok = apply_protection(repo, default, pat)
            if ok:
                print("  APPLIED")
            else:
                print("  FAILED to apply (see error above)")
                failures.append(repo)

    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    if no_changes:
        print(f"  no-op (already strict): {', '.join(no_changes)}")
    if not args.apply:
        print("  dry-run mode -- no changes were written.")
        print("  Re-run with --apply --confirm-yes to apply.")
    if failures:
        print(f"  FAILURES: {', '.join(failures)}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
