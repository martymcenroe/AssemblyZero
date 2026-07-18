#!/usr/bin/env python3
"""One-shot: upgrade comp-environ's auto-reviewer.yml to the NEW caller format.

Bug (comp-environ#11): comp-environ's `.github/workflows/auto-reviewer.yml`
is in the OLD format -- `name: auto-reviewer` (lowercase), `secrets: inherit`,
no `permissions:` block, no `with: required_checks`. The reusable workflow at
AssemblyZero/.github/workflows/auto-reviewer.yml declares its permissions,
inputs, and secrets in the NEW shape, so OLD-format callers hit
`startup_failure` after 0s on every PR. Cerberus therefore never approves,
and every PR on comp-environ is blocked indefinitely.

comp-environ was deployed via the buggy `deploy_auto_reviewer_workflow.py`
(#1128 sweep). Same root cause as boostgauge -- see
`upgrade_boostgauge_auto_reviewer.py`, which this script mirrors.

Why direct-to-main and not a PR
-------------------------------
This is a bootstrap. The thing being fixed IS the PR approver. A PR carrying
this fix could never be approved, because the broken auto-reviewer is what
would have to approve it. Chicken-and-egg. The Contents API PUT to main is
the only way in. The commit message carries `Closes #11` so the issue-reference
discipline is satisfied via the commit (GitHub closes issues referenced by
commits landing on the default branch).

Canonical content
-----------------
CALLER_WORKFLOW below is byte-for-byte identical to the CALLER_WORKFLOW
constant in `tools/deploy_auto_reviewer_fleet.py` (verified against the live
files in Aletheia and Talos, 2026-07-18). Matching it exactly keeps
comp-environ idempotent if the fleet deployer is ever re-run. Note this
differs in COMMENT TEXT ONLY from the constant in
`upgrade_boostgauge_auto_reviewer.py`; the functional YAML is the same.

Sanctioned classic-PAT pattern per ADR-0216 + #1141:

  1. classic_pat_session() decrypts the PAT into local heap only.
  2. List active rulesets targeting main; check classic enforce_admins.
  3. For each blocking ruleset: PATCH bypass_actors to add the Repository
     admin role (actor_id=5) -- does NOT change rule parameters, only adds
     admin to the bypass list. Disable classic enforce_admins if set.
  4. PUT the file via Contents API on main (admin bypass allows write).
  5. Restore protection in a try/finally so it runs even on PUT failure.

This is NOT `gh pr merge --admin`. NOT a force-push. NOT a reduction in the
protection RULES. The bypass window is bounded to a single PUT,
admin-role-scoped, atomic.

Dry-run by default per standard 0017. Pass --apply to mutate.
No banned commands appear in this source, so --apply is the correct flag
(--execute is reserved for scripts whose source contains one).

REQUIRED operational rule (`feedback_az_tools_user_runs_script.md`):
  The user runs this script in their own Git Bash. Never invoke via an
  agent's Bash tool -- an agent-spawned process is the agent's child, which
  defeats ADR-0216's "PAT lives only in this process's heap" guarantee.

Required classic PAT scopes:
  - repo (full)        -- ruleset PATCH, protection toggle, Contents API write
  - workflow           -- Contents API write to .github/workflows/*

Usage:
    cd /c/Users/mcwiz/Projects/AssemblyZero
    poetry run python tools/upgrade_comp_environ_auto_reviewer.py           # dry run
    poetry run python tools/upgrade_comp_environ_auto_reviewer.py --apply   # mutate
"""
from __future__ import annotations

import argparse
import base64
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pat_session import classic_pat_session  # noqa: E402

GITHUB_USER = "martymcenroe"
REPO = "comp-environ"
BRANCH = "main"
WORKFLOW_PATH = ".github/workflows/auto-reviewer.yml"
GH_API = "https://api.github.com"
HTTP_TIMEOUT_S = 30
REPO_ADMIN_ROLE_ID = 5  # GitHub repository role: admin

# Byte-for-byte identical to deploy_auto_reviewer_fleet.py::CALLER_WORKFLOW.
# Do not reflow or re-comment -- drift breaks fleet-deployer idempotency.
CALLER_WORKFLOW = """\
name: Auto Review

# Caller workflow: invokes the reusable auto-reviewer from AssemblyZero.
# Deployed by tools/deploy_auto_reviewer_fleet.py (#736)

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
    "ci: upgrade auto-reviewer.yml to NEW caller format (Closes #11)\n"
    "\n"
    "OLD format (secrets: inherit, no permissions block, no required_checks\n"
    "input) causes startup_failure on every PR, blocking Cerberus approval.\n"
    "Landed directly on main via Contents API: a PR carrying this fix could\n"
    "not be approved, because the broken approver is what this fixes."
)

# Fields writable via the "Update a repository ruleset" PUT endpoint.
# Server-managed fields (id, source, _links, ...) must NOT appear in the body.
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
    blocking = []
    explicit_ref = f"refs/heads/{BRANCH}"
    for summary in r.json():
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
    body = {f: ruleset[f] for f in RULESET_WRITABLE_FIELDS if f in ruleset}
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
    r = requests.put(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/rulesets/{ruleset_id}",
        headers=_headers(pat),
        json=_ruleset_put_body(current, new_actors),
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
    r2 = requests.put(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/rulesets/{ruleset_id}",
        headers=_headers(pat),
        json=_ruleset_put_body(r.json(), original),
        timeout=HTTP_TIMEOUT_S,
    )
    r2.raise_for_status()


def put_file(blob_sha: str, pat: str) -> None:
    # Normalize to LF: Contents API stores bytes verbatim, and a CRLF body
    # would flip the whole file's line endings on origin (ADR-0216 gotcha 3).
    content_bytes = CALLER_WORKFLOW.replace("\r\n", "\n").encode("utf-8")
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


def check_reviewer_secrets(pat: str) -> tuple[bool, list[str]]:
    """Report whether the Cerberus secrets exist on this repo.

    comp-environ#11 notes a second failure mode: even with the caller format
    fixed, the reusable workflow fails if REVIEWER_APP_ID /
    REVIEWER_APP_PRIVATE_KEY are absent. Checking here surfaces that now
    instead of after the test PR. Read-only -- never prints secret VALUES,
    which the API does not return anyway.
    """
    required = ["REVIEWER_APP_ID", "REVIEWER_APP_PRIVATE_KEY"]
    r = requests.get(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/actions/secrets",
        headers=_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code >= 300:
        return False, [f"(could not list secrets: HTTP {r.status_code})"]
    present = {s["name"] for s in r.json().get("secrets", [])}
    missing = [n for n in required if n not in present]
    return not missing, missing


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
    return bool(enforce.get("enabled", False)) if isinstance(enforce, dict) else False


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
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Actually write. Without this, the script reports and exits.",
    )
    args = ap.parse_args()

    print(f"Target: {GITHUB_USER}/{REPO} branch={BRANCH}")
    print(f"File:   {WORKFLOW_PATH}")
    print(f"Mode:   {'APPLY' if args.apply else 'DRY RUN (pass --apply to write)'}")
    print()

    with classic_pat_session() as pat:
        current, blob_sha = get_file(pat)
        if current is None:
            print("  File does not exist on main -- wrong tool. Use "
                  "deploy_auto_reviewer_workflow.py to create it.")
            return 1

        if current.replace("\r\n", "\n") == CALLER_WORKFLOW:
            print("  Content already matches canonical NEW format -- nothing to do.")
            return 0

        print(f"  Existing file (blob sha={blob_sha[:7]}) differs from canonical.")
        print(f"  Current first line: {current.splitlines()[0]!r}")
        print(f"  Will become:        {CALLER_WORKFLOW.splitlines()[0]!r}")
        print()

        rulesets = list_blocking_rulesets(pat)
        classic_prot = get_classic_protection(pat)
        classic_strict = is_enforce_admins_on(classic_prot)
        print(f"  Protection: rulesets={len(rulesets)} classic_enforce_admins={classic_strict}")

        secrets_ok, missing = check_reviewer_secrets(pat)
        if secrets_ok:
            print("  Cerberus secrets: both present.")
        else:
            print(f"  Cerberus secrets: MISSING {', '.join(missing)}")
            print("    The format fix alone will NOT make Cerberus approve.")
            print("    Deploy them with tools/deploy_cerberus_secrets.py, then retest.")

        if not args.apply:
            print()
            print("  DRY RUN -- no changes made. Re-run with --apply to write.")
            return 0

        if not rulesets and not classic_strict:
            print("  No blocking protection -- direct PUT.")
            put_file(blob_sha, pat)
            print("  PUT succeeded.")
            return 0

        restorations: list[tuple[int, list[dict]]] = []
        classic_disabled = False
        try:
            if classic_strict:
                print(f"  Disabling classic enforce_admins on {BRANCH}...")
                disable_enforce_admins(pat)
                classic_disabled = True
                print("    disabled.")
            for rs in rulesets:
                rs_id = rs["id"]
                print(f"  Adding admin bypass to ruleset {rs_id} ({rs.get('name')})...")
                restorations.append((rs_id, add_admin_bypass(rs_id, pat)))
                print("    added.")
            print("  PUT file via Contents API...")
            put_file(blob_sha, pat)
            print("    PUT succeeded.")
        finally:
            # Restore in reverse order: rulesets first, then classic.
            for rs_id, original in restorations:
                try:
                    print(f"  Restoring bypass_actors on ruleset {rs_id}...")
                    restore_bypass(rs_id, original, pat)
                    print("    restored.")
                except Exception as e:
                    print(f"    WARNING: restore failed: {e}")
                    print("    Manually restore via:")
                    print(f"      GET /repos/{GITHUB_USER}/{REPO}/rulesets/{rs_id}")
                    print(f"      then PUT with bypass_actors={original!r}")
            if classic_disabled:
                try:
                    print(f"  Restoring classic enforce_admins on {BRANCH}...")
                    enable_enforce_admins(pat)
                    print("    restored.")
                except Exception as e:
                    print(f"    WARNING: enforce_admins restore failed: {e}")
                    print("    Manually restore via:")
                    print(f"      POST /repos/{GITHUB_USER}/{REPO}"
                          f"/branches/{BRANCH}/protection/enforce_admins")

    print()
    print("Next: verify the landed file, then push the assemblyZero branch and")
    print("open its PR -- that PR is the live test that Cerberus now approves.")
    print("  gh api repos/martymcenroe/comp-environ/contents/"
          ".github/workflows/auto-reviewer.yml --jq '.content' | base64 -d | head -1")
    print("  # expect: name: Auto Review")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
