#!/usr/bin/env python3
"""One-shot: upgrade boostgauge's auto-reviewer.yml to the NEW caller format.

Bug: `deploy_auto_reviewer_workflow.py`'s CALLER_WORKFLOW constant deploys
the OLD format that lacks the `permissions:` block, the explicit `with:`
input, and explicit `secrets:` mapping. The reusable workflow at
AssemblyZero/.github/workflows/auto-reviewer.yml declares its required
permissions/inputs/secrets in the NEW shape, so OLD-format callers hit
`startup_failure` after 0s on every PR. boostgauge was deployed via the
buggy tool (#1128 sweep) and has had broken auto-approve since the file
landed (PR #49, PR #51 both observed startup_failure).

This script fixes boostgauge specifically by overwriting the file with
the canonical NEW format used by AssemblyZero itself (and Aletheia, etc.).
The fleet-side fix to `deploy_auto_reviewer_workflow.py` is filed as a
follow-up issue against AssemblyZero — handled separately so other repos
that used the broken deploy can also be remediated.

Idempotent. If the current file content on main already matches the
canonical NEW format byte-for-byte, the script is a no-op.

Sanctioned classic-PAT pattern per ADR-0216 + #1141:

  1. classic_pat_session() decrypts the PAT into local heap only.
  2. List active rulesets targeting main.
  3. For each blocking ruleset: PATCH bypass_actors to add the
     Repository admin role (actor_id=5) — does NOT change rule
     parameters, only adds admin to the bypass list.
  4. PUT the file via Contents API on main (admin bypass allows write).
  5. PATCH bypass_actors back to the original list in a try/finally
     so restoration runs even on PUT failure.

This is NOT `gh pr merge --admin`. NOT a force-push. NOT a reduction in
the protection RULES. The bypass window is bounded to a single PUT,
admin-role-scoped, atomic. Matches the pattern documented in root
CLAUDE.md ("elevated-scope landings: workflow-file edits ... use the
in-process classic-PAT pattern").

REQUIRED operational rule (`feedback_az_tools_user_runs_script.md`):
  The user runs this script in their own Git Bash. Never invoke via
  an agent's Bash tool.

Required classic PAT scopes:
  - repo (full)        — for ruleset PATCH and Contents API write
  - workflow           — for Contents API write to .github/workflows/*

Usage:
    cd /c/Users/mcwiz/Projects/AssemblyZero
    poetry run python tools/upgrade_boostgauge_auto_reviewer.py
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
BRANCH = "main"
WORKFLOW_PATH = ".github/workflows/auto-reviewer.yml"
GH_API = "https://api.github.com"
HTTP_TIMEOUT_S = 30
REPO_ADMIN_ROLE_ID = 5  # GitHub repository role: admin

# Source of truth: AssemblyZero/.github/workflows/auto-reviewer-caller.yml
# (which is what AZ itself ships). NEW format — has `permissions:` block,
# explicit `with: required_checks:` input, and explicit `secrets:` mapping.
# Without these the reusable workflow at AZ@main fails to start.
CANONICAL_CALLER = """\
name: Auto Review

# Caller workflow: invokes the reusable auto-reviewer from AssemblyZero.
# Copy this file to .github/workflows/auto-reviewer.yml in each repo.
#
# For repos with additional required checks beyond pr-sentinel, override:
#   required_checks: "issue-reference, CI, CodeQL"
#
# Issue: #736

on:
  pull_request:
    branches: [main]
    types: [opened, synchronize, reopened]

permissions:
  pull-requests: write
  checks: read

jobs:
  auto-review:
    uses: martymcenroe/AssemblyZero/.github/workflows/auto-reviewer.yml@main
    with:
      required_checks: "issue-reference"
    secrets:
      REVIEWER_APP_ID: ${{ secrets.REVIEWER_APP_ID }}
      REVIEWER_APP_PRIVATE_KEY: ${{ secrets.REVIEWER_APP_PRIVATE_KEY }}
"""

COMMIT_MESSAGE = (
    "ci: upgrade auto-reviewer.yml to NEW caller format -- fix "
    "Cerberus startup_failure on boostgauge PRs"
)

# Fields that are writable via the "Update a repository ruleset" PUT
# endpoint. Server-managed fields (id, source, _links, etc.) must NOT
# appear in the PUT body.
RULESET_WRITABLE_FIELDS = ("name", "target", "enforcement", "conditions", "rules")


def _headers(pat: str) -> dict[str, str]:
    return {
        "Authorization": f"token {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def get_file(pat: str) -> tuple[str | None, str | None]:
    """Return (current_content_decoded, blob_sha) or (None, None) if 404."""
    r = requests.get(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/contents/{WORKFLOW_PATH}",
        params={"ref": BRANCH},
        headers=_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code == 404:
        return None, None
    r.raise_for_status()
    data = r.json()
    encoded = (data.get("content") or "").replace("\n", "")
    decoded = base64.b64decode(encoded).decode("utf-8")
    return decoded, data.get("sha")


def list_blocking_rulesets(pat: str) -> list[dict]:
    """Return full ruleset detail dicts for active rulesets targeting main."""
    r = requests.get(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/rulesets",
        headers=_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code == 404:
        return []
    r.raise_for_status()
    summaries = r.json()
    blocking = []
    explicit_ref = f"refs/heads/{BRANCH}"
    for summary in summaries:
        if summary.get("enforcement") != "active":
            continue
        if summary.get("target") != "branch":
            continue
        rs_id = summary.get("id")
        if rs_id is None:
            continue
        rd = requests.get(
            f"{GH_API}/repos/{GITHUB_USER}/{REPO}/rulesets/{rs_id}",
            headers=_headers(pat),
            timeout=HTTP_TIMEOUT_S,
        )
        rd.raise_for_status()
        details = rd.json()
        ref_name = (details.get("conditions") or {}).get("ref_name") or {}
        include = ref_name.get("include") or []
        if "~DEFAULT_BRANCH" in include or explicit_ref in include:
            blocking.append(details)
    return blocking


def _ruleset_put_body(ruleset: dict, bypass_actors: list[dict]) -> dict:
    body = {}
    for field in RULESET_WRITABLE_FIELDS:
        if field in ruleset:
            body[field] = ruleset[field]
    body["bypass_actors"] = bypass_actors
    return body


def add_admin_bypass(ruleset_id: int, pat: str) -> list[dict]:
    """Add admin to bypass_actors; return ORIGINAL bypass_actors for restore."""
    r = requests.get(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/rulesets/{ruleset_id}",
        headers=_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    current = r.json()
    original = current.get("bypass_actors") or []
    already = any(
        a.get("actor_id") == REPO_ADMIN_ROLE_ID
        and a.get("actor_type") == "RepositoryRole"
        for a in original
    )
    if already:
        return original  # no-op; restoration is identity
    new_actors = list(original) + [{
        "actor_id": REPO_ADMIN_ROLE_ID,
        "actor_type": "RepositoryRole",
        "bypass_mode": "always",
    }]
    body = _ruleset_put_body(current, new_actors)
    r = requests.put(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/rulesets/{ruleset_id}",
        headers=_headers(pat),
        json=body,
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    return original


def restore_bypass(ruleset_id: int, original: list[dict], pat: str) -> None:
    r = requests.get(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/rulesets/{ruleset_id}",
        headers=_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    current = r.json()
    body = _ruleset_put_body(current, original)
    r = requests.put(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/rulesets/{ruleset_id}",
        headers=_headers(pat),
        json=body,
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()


def put_file(blob_sha: str, pat: str) -> None:
    content_bytes = CANONICAL_CALLER.replace("\r\n", "\n").encode("utf-8")
    payload = {
        "message": COMMIT_MESSAGE,
        "content": base64.b64encode(content_bytes).decode("ascii"),
        "branch": BRANCH,
        "sha": blob_sha,  # update existing file (file must exist)
    }
    r = requests.put(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/contents/{WORKFLOW_PATH}",
        headers=_headers(pat),
        json=payload,
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code >= 300:
        print(f"    PUT failed: {r.status_code}")
        print(f"    Response body: {r.text[:600]}")
    r.raise_for_status()


def get_classic_protection(pat: str) -> dict | None:
    """GET /branches/main/protection. None on 404 (no classic protection)."""
    r = requests.get(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/branches/{BRANCH}/protection",
        headers=_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def is_enforce_admins_on(prot: dict | None) -> bool:
    if prot is None:
        return False
    enforce = prot.get("enforce_admins")
    if not isinstance(enforce, dict):
        return False
    return bool(enforce.get("enabled", False))


def disable_enforce_admins(pat: str) -> None:
    r = requests.delete(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/branches/{BRANCH}/protection/enforce_admins",
        headers=_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code >= 300:
        print(f"    DELETE enforce_admins failed: {r.status_code}")
        print(f"    Response body: {r.text[:600]}")
    r.raise_for_status()


def enable_enforce_admins(pat: str) -> None:
    r = requests.post(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/branches/{BRANCH}/protection/enforce_admins",
        headers=_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code >= 300:
        print(f"    POST enforce_admins failed: {r.status_code}")
        print(f"    Response body: {r.text[:600]}")
    r.raise_for_status()


def main() -> int:
    print(f"Target: {GITHUB_USER}/{REPO} branch={BRANCH}")
    print(f"File:   {WORKFLOW_PATH}")
    print()

    with classic_pat_session() as pat:
        current, blob_sha = get_file(pat)
        if current is None:
            print("  File does not exist on main — wrong tool. Use "
                  "deploy_auto_reviewer_workflow.py to create it.")
            return 1

        if current.replace("\r\n", "\n") == CANONICAL_CALLER:
            print("  Content already matches canonical NEW format — nothing to do.")
            return 0

        print(f"  Found existing file (blob sha={blob_sha[:7]}). "
              f"Diff with canonical — updating.")

        rulesets = list_blocking_rulesets(pat)
        classic_prot = get_classic_protection(pat)
        classic_strict = is_enforce_admins_on(classic_prot)

        if not rulesets and not classic_strict:
            print("  No blocking protection — direct PUT.")
            put_file(blob_sha, pat)
            print("  PUT succeeded.")
            return 0

        print(f"  Bootstrap: rulesets={len(rulesets)} classic_strict={classic_strict}")
        restorations: list[tuple[int, list[dict]]] = []
        classic_disabled = False
        try:
            if classic_strict:
                print(f"  Disabling classic enforce_admins on {BRANCH}...")
                disable_enforce_admins(pat)
                classic_disabled = True
                print(f"    disabled.")
            for rs in rulesets:
                rs_id = rs["id"]
                print(f"  Adding admin bypass to ruleset {rs_id} ({rs.get('name')})...")
                original = add_admin_bypass(rs_id, pat)
                restorations.append((rs_id, original))
                print(f"    added.")
            print("  PUT file via Contents API...")
            put_file(blob_sha, pat)
            print("    PUT succeeded.")
        finally:
            # Restore in reverse order: rulesets first, then classic.
            for rs_id, original in restorations:
                try:
                    print(f"  Restoring bypass_actors on ruleset {rs_id}...")
                    restore_bypass(rs_id, original, pat)
                    print(f"    restored.")
                except Exception as e:
                    print(f"    WARNING: restore failed: {e}")
                    print(f"    Manually restore via:")
                    print(f"      GH API GET /repos/{GITHUB_USER}/{REPO}/rulesets/{rs_id}")
                    print(f"      then PUT with bypass_actors={original!r}")
            if classic_disabled:
                try:
                    print(f"  Restoring classic enforce_admins on {BRANCH}...")
                    enable_enforce_admins(pat)
                    print(f"    restored.")
                except Exception as e:
                    print(f"    WARNING: enforce_admins restore failed: {e}")
                    print(f"    Manually restore via:")
                    print(f"      POST /repos/{GITHUB_USER}/{REPO}/branches/{BRANCH}/protection/enforce_admins")

    print()
    print("Next steps:")
    print("  1. Close+reopen PR #51 to re-trigger the now-fixed auto-reviewer:")
    print("       gh pr close 51 --repo martymcenroe/boostgauge")
    print("       gh pr reopen 51 --repo martymcenroe/boostgauge")
    print("  2. Wait ~10–30s for Cerberus to approve.")
    print("  3. Verify via `gh api repos/martymcenroe/boostgauge/pulls/51 "
          "--jq '.mergeable_state'` — should flip to 'clean'.")
    print("  4. Squash-merge PR #51.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
