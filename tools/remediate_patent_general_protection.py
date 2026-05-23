#!/usr/bin/env python3
"""One-shot: migrate patent-general from Rulesets to classic Branch Protection (per #1203 Option A).

patent-general's main branch is currently protected via Rulesets (ruleset id
13696329, "main"), but the fleet standard uses classic Branch Protection.
The ruleset is also configured WEAKER than the fleet — required_approving_
review_count is 0 and no required_status_checks. Per #1203 Option A,
migrate to classic with the fleet-standard rules.

Steps:
    1. DELETE the existing ruleset (releases the weak protection)
    2. PUT classic Branch Protection with fleet-standard rules
    3. Verify both: ruleset is gone, classic is in place

THIS SCRIPT MUST BE RUN BY THE USER, NOT BY AN AGENT.
Uses an in-process classic PAT (ADR-0216). Requires `repo` scope (full)
for both the ruleset DELETE and the branch-protection PUT.

Idempotent:
    - If the ruleset is already gone, the DELETE returns 404 (treated as
      success — already removed).
    - If classic protection is already in place with matching body, the
      PUT is a no-op on GitHub's side.

Usage:
    cd /c/Users/mcwiz/Projects/AssemblyZero
    poetry run python tools/remediate_patent_general_protection.py [--dry-run]

Issue: #1203
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pat_session import classic_pat_session  # noqa: E402

GITHUB_USER = "martymcenroe"
REPO = "patent-general"
RULESET_ID = 13696329  # the existing weak ruleset to be deleted
BRANCH = "main"
GH_API = "https://api.github.com"
HTTP_TIMEOUT_S = 30

# Canonical fleet-standard branch protection body. Mirrors what
# new_repo_setup.py's configure_branch_protection() PUTs on every new repo.
# Keep in sync with that function — single source of truth lives there;
# this is the patent-general-specific mirror.
CLASSIC_PROTECTION_BODY = {
    "required_status_checks": {
        "strict": False,
        "contexts": ["pr-sentinel / issue-reference"],
    },
    "enforce_admins": True,
    "required_pull_request_reviews": {
        "dismiss_stale_reviews": False,
        "require_code_owner_reviews": False,
        "required_approving_review_count": 1,
    },
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


def get_ruleset(pat: str, ruleset_id: int) -> tuple[bool, str]:
    """Probe whether the ruleset exists. Returns (exists, status_str)."""
    r = requests.get(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/rulesets/{ruleset_id}",
        headers=_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code == 200:
        return True, "exists"
    if r.status_code == 404:
        return False, "already removed"
    return False, f"unexpected HTTP {r.status_code}: {r.text[:200]}"


def delete_ruleset(pat: str, ruleset_id: int) -> tuple[bool, str]:
    """DELETE the ruleset. 404 is treated as success (already gone)."""
    r = requests.delete(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/rulesets/{ruleset_id}",
        headers=_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code in (204, 404):
        return True, "deleted" if r.status_code == 204 else "already gone"
    return False, f"DELETE HTTP {r.status_code}: {r.text[:300]}"


def put_classic_protection(pat: str) -> tuple[bool, str]:
    """PUT fleet-standard classic Branch Protection on main."""
    r = requests.put(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/branches/{BRANCH}/protection",
        headers=_headers(pat),
        json=CLASSIC_PROTECTION_BODY,
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code in (200, 201):
        return True, "applied"
    return False, f"PUT HTTP {r.status_code}: {r.text[:300]}"


def verify_classic_protection(pat: str) -> tuple[bool, str]:
    """Verify the classic protection is in place with expected fields."""
    r = requests.get(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/branches/{BRANCH}/protection",
        headers=_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code != 200:
        return False, f"GET HTTP {r.status_code}: {r.text[:200]}"
    p = r.json()
    failures: list[str] = []
    if not (p.get("enforce_admins") or {}).get("enabled"):
        failures.append("enforce_admins not enabled")
    reviews = p.get("required_pull_request_reviews") or {}
    if reviews.get("required_approving_review_count") != 1:
        failures.append(
            f"required_approving_review_count={reviews.get('required_approving_review_count')!r}, want 1"
        )
    checks = (p.get("required_status_checks") or {}).get("contexts") or []
    if "pr-sentinel / issue-reference" not in checks:
        failures.append(
            f"'pr-sentinel / issue-reference' not in required checks ({checks!r})"
        )
    if failures:
        return False, "; ".join(failures)
    return True, "enforce_admins=on, 1 review, pr-sentinel check"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n")[0])
    parser.add_argument("--dry-run", action="store_true",
                        help="Probe state and print plan without DELETE or PUT.")
    args = parser.parse_args(argv)

    print(f"Target: {GITHUB_USER}/{REPO} branch={BRANCH}")
    print(f"Ruleset to remove: {RULESET_ID}")
    print(f"Mode: {'DRY-RUN' if args.dry_run else 'APPLY'}")
    print()

    with classic_pat_session() as pat:
        # Step 0: probe current state
        exists, status = get_ruleset(pat, RULESET_ID)
        print(f"  Ruleset {RULESET_ID}: {status}")

        if args.dry_run:
            print()
            print("  Plan (--apply to execute):")
            if exists:
                print(f"    1. DELETE /repos/{GITHUB_USER}/{REPO}/rulesets/{RULESET_ID}")
            else:
                print("    1. (skip — ruleset already removed)")
            print(
                f"    2. PUT  /repos/{GITHUB_USER}/{REPO}/branches/{BRANCH}/protection "
                "(fleet-standard body)"
            )
            print("    3. Verify classic protection in place.")
            return 0

        # Step 1: delete ruleset
        print()
        print(f"  Deleting ruleset {RULESET_ID}...")
        ok, detail = delete_ruleset(pat, RULESET_ID)
        if not ok:
            print(f"    FAILED: {detail}")
            return 2
        print(f"    {detail}")

        # Step 2: PUT classic protection
        print()
        print(f"  PUT classic Branch Protection on {BRANCH}...")
        ok, detail = put_classic_protection(pat)
        if not ok:
            print(f"    FAILED: {detail}")
            print()
            print("  CRITICAL: ruleset was deleted but classic protection failed to apply.")
            print(f"  patent-general's {BRANCH} branch is currently UNPROTECTED.")
            print("  Recover by re-running this script or by re-creating the ruleset manually.")
            return 2
        print(f"    {detail}")

        # Step 3: verify
        print()
        print("  Verifying classic protection state on origin...")
        ok, detail = verify_classic_protection(pat)
        if not ok:
            print(f"    VERIFICATION FAILED: {detail}")
            return 2
        print(f"    OK — {detail}")

        # Step 4: confirm ruleset is gone
        still_there, status = get_ruleset(pat, RULESET_ID)
        print(f"  Ruleset {RULESET_ID} post-fix: {status}")
        if still_there:
            print("    WARNING: ruleset still present after DELETE attempt.")
            return 2

    print()
    print("=" * 60)
    print(f"patent-general migrated to classic Branch Protection (Closes AZ#1203)")
    print("=" * 60)
    print("Next: file a comment on AZ#1203 with the verification output,")
    print("then close. Follow-up: AZ#1211 (rewrite runbook 0926).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
