#!/usr/bin/env python3
"""Deploy the canonical auto-reviewer.yml workflow to repos missing it (#1128).

THIS SCRIPT MUST BE RUN BY THE USER, NOT BY AN AGENT.
Uses an in-process classic PAT (ADR-0216). The PAT carries `workflow`
scope so it can push `.github/workflows/*` via the Contents API --
fine-grained PATs intentionally lack that scope.

What this script does:

  1. Determines the canonical auto-reviewer.yml content. Each repo
     gets the CALLER pattern (a 6-line YAML that invokes AZ's reusable
     auto-reviewer workflow via `uses:`).
  2. For each target repo, PUTs the caller file via Contents API to
     `.github/workflows/auto-reviewer.yml` on the default branch.
  3. Idempotent: skips repos that already have the file.

#1135 + #1137: bootstrap mode for STRICT-protected repos missing the workflow.
The original (pre-#1135) tool only worked when direct PUT to main was
allowed -- on protected repos (classic protection with enforce_admins
and/or active rulesets with pull_request rule) the PUT is refused
with "Repository rule violations found".

Bootstrap covers two independent protection mechanisms:

CLASSIC PROTECTION (#1135) -- enforce_admins toggle:
  a. DELETEs the enforce_admins sub-resource (admins bypass)
  b. PUTs the workflow file (admin push succeeds)
  c. POSTs the enforce_admins sub-resource (restores)

RULESETS (#1137) -- bypass_actors toggle:
  a. GETs each active ruleset targeting the branch
  b. PATCHes ruleset to add Repository admin role (actor_id=5) to
     bypass_actors with bypass_mode=always
  c. After PUT, PATCHes ruleset to restore original bypass_actors

Both dimensions are detected first, applied in sequence, and restored
in reverse via try/finally so restoration runs even if PUT fails. This
is the sanctioned classic-PAT pattern per root CLAUDE.md
("elevated-scope landings: workflow-file edits, branch-protection
updates ... use in-process classic-PAT"). It is NOT the banned
`--admin` flag (which is the `gh pr merge --admin` shortcut). The
bypass window is bounded to a single PUT, owner-role-scoped, atomic.

The canonical CALLER file is:

    name: auto-reviewer
    on:
      pull_request:
        types: [opened, synchronize, reopened]
    jobs:
      review:
        uses: martymcenroe/AssemblyZero/.github/workflows/auto-reviewer.yml@main
        secrets: inherit

Usage:

    # Dry-run (default; safe)
    poetry run python tools/deploy_auto_reviewer_workflow.py --repos comp-environ,gh-galaxy-quest

    # Apply (auto-detects strict protection and bootstraps if needed)
    poetry run python tools/deploy_auto_reviewer_workflow.py \
        --repos comp-environ,gh-galaxy-quest,boostgauge --apply --confirm-yes

Issue: #1128, #1135 | Related: #1126 (protection remediation), ADR-0216
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
GH_API = "https://api.github.com"
HTTP_TIMEOUT_S = 30
WORKFLOW_PATH = ".github/workflows/auto-reviewer.yml"

# Canonical caller workflow. Mirrors what every other repo in the fleet
# uses to invoke the AssemblyZero reusable auto-reviewer.yml.
CALLER_WORKFLOW = """\
name: auto-reviewer

on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  review:
    uses: martymcenroe/AssemblyZero/.github/workflows/auto-reviewer.yml@main
    secrets: inherit
"""


def _headers(pat: str) -> dict[str, str]:
    return {
        "Authorization": f"token {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def get_default_branch(repo: str, pat: str) -> str | None:
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


def workflow_status(repo: str, branch: str, pat: str) -> tuple[bool | None, str | None]:
    """Return (exists, blob_sha). exists=None means GET errored.
    blob_sha is the SHA of the existing file (needed for PUT-update),
    or None when the file doesn't exist."""
    try:
        r = requests.get(
            f"{GH_API}/repos/{GITHUB_USER}/{repo}/contents/{WORKFLOW_PATH}?ref={branch}",
            headers=_headers(pat), timeout=HTTP_TIMEOUT_S,
        )
    except requests.RequestException:
        return None, None
    if r.status_code == 404:
        return False, None
    if r.status_code != 200:
        return None, None
    return True, r.json().get("sha")


def put_workflow(repo: str, branch: str, existing_sha: str | None,
                 pat: str) -> tuple[bool, str | None]:
    """PUT the canonical workflow content to the repo's default branch.
    CRLF-normalised per memory: Contents API stores bytes verbatim;
    Windows working trees ship CRLF which would flip line endings.

    Returns (success, error)."""
    content_bytes = CALLER_WORKFLOW.replace("\r\n", "\n").encode("utf-8")
    payload: dict = {
        "message": (
            "ci: add auto-reviewer.yml -- Cerberus auto-approve on PRs "
            "(fleet readiness, #1128)"
        ),
        "content": base64.b64encode(content_bytes).decode("ascii"),
        "branch": branch,
    }
    if existing_sha:
        payload["sha"] = existing_sha

    try:
        r = requests.put(
            f"{GH_API}/repos/{GITHUB_USER}/{repo}/contents/{WORKFLOW_PATH}",
            headers=_headers(pat), json=payload, timeout=HTTP_TIMEOUT_S,
        )
    except requests.RequestException as e:
        return False, f"network: {e}"
    if r.status_code >= 300:
        return False, f"PUT {r.status_code}: {r.text[:300]}"
    return True, None


# ---------------------------------------------------------------------------
# #1135: bootstrap support for STRICT-protected repos
# ---------------------------------------------------------------------------

def get_protection(repo: str, branch: str,
                   pat: str) -> tuple[dict | None, str | None]:
    """GET classic branch protection.

    Returns (protection_dict, error). protection_dict is None on 404
    (unprotected) AND on GET failure -- callers should check error to
    distinguish. error is None when the GET succeeded (200 or 404).
    """
    try:
        r = requests.get(
            f"{GH_API}/repos/{GITHUB_USER}/{repo}/branches/{branch}/protection",
            headers=_headers(pat), timeout=HTTP_TIMEOUT_S,
        )
    except requests.RequestException as e:
        return None, f"network: {e}"
    if r.status_code == 404:
        return None, None  # unprotected, not an error
    if r.status_code >= 300:
        return None, f"GET protection {r.status_code}: {r.text[:200]}"
    return r.json(), None


def is_enforce_admins_on(prot: dict | None) -> bool:
    """True iff classic protection's enforce_admins.enabled is True.

    When enforce_admins is True, admins (including the classic-PAT identity
    acting as the repo owner) are subject to branch protection rules,
    blocking direct Contents API PUT to the protected branch.
    """
    if prot is None:
        return False
    enforce = prot.get("enforce_admins")
    if not isinstance(enforce, dict):
        return False
    return bool(enforce.get("enabled", False))


def disable_enforce_admins(repo: str, branch: str,
                           pat: str) -> tuple[bool, str | None]:
    """DELETE the enforce_admins sub-resource. After this, admins bypass
    branch protection rules (reviews, status checks, force-push, deletion).

    The DELETE is the canonical GitHub API for toggling enforce_admins off;
    it does NOT remove the rest of branch protection, only this dimension.
    """
    url = f"{GH_API}/repos/{GITHUB_USER}/{repo}/branches/{branch}/protection/enforce_admins"
    try:
        r = requests.delete(url, headers=_headers(pat), timeout=HTTP_TIMEOUT_S)
    except requests.RequestException as e:
        return False, f"network: {e}"
    if r.status_code >= 300:
        return False, f"DELETE enforce_admins {r.status_code}: {r.text[:200]}"
    return True, None


def enable_enforce_admins(repo: str, branch: str,
                          pat: str) -> tuple[bool, str | None]:
    """POST the enforce_admins sub-resource. Restores admin enforcement
    after a bootstrap PUT.
    """
    url = f"{GH_API}/repos/{GITHUB_USER}/{repo}/branches/{branch}/protection/enforce_admins"
    try:
        r = requests.post(url, headers=_headers(pat), timeout=HTTP_TIMEOUT_S)
    except requests.RequestException as e:
        return False, f"network: {e}"
    if r.status_code >= 300:
        return False, f"POST enforce_admins {r.status_code}: {r.text[:200]}"
    return True, None


REPO_ADMIN_ROLE_ID = 5  # GitHub repository role: admin

# Fields from a GET ruleset response that are writable via PUT (the canonical
# "Update a repository ruleset" endpoint). Other fields are server-managed
# (id, source, source_type, node_id, created_at, updated_at,
# current_user_can_bypass, _links) and must NOT be sent in the PUT body.
RULESET_WRITABLE_FIELDS = ("name", "target", "enforcement", "conditions", "rules")


def _ruleset_put_body(ruleset: dict, bypass_actors: list[dict]) -> dict:
    """Build a PUT body for `Update a repository ruleset` from a GET response.

    Copies only the writable fields (skipping server-managed ones) and
    overwrites bypass_actors with the caller's value. GitHub returns 404
    on PATCH against this endpoint (#1141) -- PUT is the only supported
    update method.
    """
    body: dict = {}
    for field in RULESET_WRITABLE_FIELDS:
        if field in ruleset:
            body[field] = ruleset[field]
    body["bypass_actors"] = bypass_actors
    return body


def list_blocking_rulesets(repo: str, branch: str,
                           pat: str) -> tuple[list[dict], str | None]:
    """List active rulesets targeting the given branch.

    Returns (rulesets_with_details, error). Each item in the returned
    list is the FULL ruleset detail dict (caller needs `id` and current
    `bypass_actors`). Rulesets are filtered to those with:
      - enforcement="active"
      - target="branch"
      - conditions.ref_name.include containing "~DEFAULT_BRANCH" or the
        explicit "refs/heads/{branch}" entry

    Empty list means no ruleset bootstrap is needed (or no rulesets exist).
    """
    try:
        r = requests.get(
            f"{GH_API}/repos/{GITHUB_USER}/{repo}/rulesets",
            headers=_headers(pat), timeout=HTTP_TIMEOUT_S,
        )
    except requests.RequestException as e:
        return [], f"network: {e}"
    if r.status_code == 404:
        # Repo has no rulesets surface at all -- treat as empty
        return [], None
    if r.status_code >= 300:
        return [], f"GET rulesets {r.status_code}: {r.text[:200]}"

    summaries = r.json()
    if not isinstance(summaries, list):
        return [], None

    blocking: list[dict] = []
    explicit_ref = f"refs/heads/{branch}"
    for summary in summaries:
        if summary.get("enforcement") != "active":
            continue
        if summary.get("target") != "branch":
            continue
        # Fetch full detail to get conditions + bypass_actors
        rs_id = summary.get("id")
        if rs_id is None:
            continue
        try:
            rd = requests.get(
                f"{GH_API}/repos/{GITHUB_USER}/{repo}/rulesets/{rs_id}",
                headers=_headers(pat), timeout=HTTP_TIMEOUT_S,
            )
        except requests.RequestException as e:
            return [], f"network on ruleset {rs_id}: {e}"
        if rd.status_code >= 300:
            return [], f"GET ruleset {rs_id} -> {rd.status_code}: {rd.text[:200]}"
        details = rd.json()
        ref_name = (details.get("conditions") or {}).get("ref_name") or {}
        include = ref_name.get("include") or []
        if "~DEFAULT_BRANCH" in include or explicit_ref in include:
            blocking.append(details)
    return blocking, None


def add_admin_bypass(repo: str, ruleset_id: int,
                     pat: str) -> tuple[bool, list[dict] | None, str | None]:
    """Add Repository admin role to a ruleset's bypass_actors.

    Captures and returns the ORIGINAL bypass_actors so the caller can
    restore exactly what was there (instead of assuming the list was
    empty). Returns (success, original_bypass_actors, error).

    On 404 / failure during the initial GET, original is None and the
    PUT is not attempted.

    #1141: uses PUT with the full ruleset body. PATCH is not a supported
    method on this endpoint -- GitHub returns 404 (not 405) when method
    and resource don't match.
    """
    try:
        r = requests.get(
            f"{GH_API}/repos/{GITHUB_USER}/{repo}/rulesets/{ruleset_id}",
            headers=_headers(pat), timeout=HTTP_TIMEOUT_S,
        )
    except requests.RequestException as e:
        return False, None, f"network: {e}"
    if r.status_code >= 300:
        return False, None, f"GET ruleset {ruleset_id} -> {r.status_code}: {r.text[:200]}"

    current = r.json()
    original = current.get("bypass_actors") or []
    # Don't double-add if the admin role is already a bypass actor.
    already_present = any(
        a.get("actor_id") == REPO_ADMIN_ROLE_ID
        and a.get("actor_type") == "RepositoryRole"
        for a in original
    )
    if already_present:
        return True, original, None  # No-op; caller restores to identical state

    new_actors = list(original) + [{
        "actor_id": REPO_ADMIN_ROLE_ID,
        "actor_type": "RepositoryRole",
        "bypass_mode": "always",
    }]
    put_body = _ruleset_put_body(current, new_actors)
    try:
        r = requests.put(
            f"{GH_API}/repos/{GITHUB_USER}/{repo}/rulesets/{ruleset_id}",
            headers=_headers(pat),
            json=put_body,
            timeout=HTTP_TIMEOUT_S,
        )
    except requests.RequestException as e:
        return False, original, f"network: {e}"
    if r.status_code >= 300:
        return False, original, f"PUT ruleset {ruleset_id} -> {r.status_code}: {r.text[:200]}"
    return True, original, None


def restore_bypass(repo: str, ruleset_id: int, original: list[dict],
                   pat: str) -> tuple[bool, str | None]:
    """Restore a ruleset's bypass_actors to the original list.

    #1141: GET to capture the current writable fields (in case they
    changed between add and restore -- defensive), then PUT with the
    original bypass_actors. PATCH is not supported on this endpoint.
    """
    try:
        r = requests.get(
            f"{GH_API}/repos/{GITHUB_USER}/{repo}/rulesets/{ruleset_id}",
            headers=_headers(pat), timeout=HTTP_TIMEOUT_S,
        )
    except requests.RequestException as e:
        return False, f"network on GET: {e}"
    if r.status_code >= 300:
        return False, f"GET ruleset {ruleset_id} -> {r.status_code}: {r.text[:200]}"
    current = r.json()
    put_body = _ruleset_put_body(current, original)
    try:
        r = requests.put(
            f"{GH_API}/repos/{GITHUB_USER}/{repo}/rulesets/{ruleset_id}",
            headers=_headers(pat),
            json=put_body,
            timeout=HTTP_TIMEOUT_S,
        )
    except requests.RequestException as e:
        return False, f"network: {e}"
    if r.status_code >= 300:
        return False, f"PUT ruleset {ruleset_id} -> {r.status_code}: {r.text[:200]}"
    return True, None


def deploy_with_bootstrap(repo: str, branch: str,
                          pat: str) -> tuple[bool, str | None, bool]:
    """Deploy auto-reviewer.yml to a repo, bootstrapping past strict
    protection (classic + rulesets) if necessary.

    Returns (success, error, bootstrap_used). bootstrap_used is True
    when any protection toggle (classic enforce_admins or ruleset
    bypass_actors) was applied. Restoration always runs via try/finally.

    Restoration failures emit CRITICAL stderr messages with recovery
    commands; if the PUT succeeded but any restoration failed, the
    function returns the restoration error as load-bearing.
    """
    # Probe both protection dimensions BEFORE touching anything.
    prot, err = get_protection(repo, branch, pat)
    if err:
        return False, f"could not GET protection: {err}", False
    classic_strict = is_enforce_admins_on(prot)

    rulesets, err = list_blocking_rulesets(repo, branch, pat)
    if err:
        return False, f"could not GET rulesets: {err}", False
    has_rulesets = bool(rulesets)

    if not classic_strict and not has_rulesets:
        # Permissive: direct PUT
        ok, put_err = put_workflow(repo, branch, None, pat)
        return ok, put_err, False

    # Bootstrap path
    if classic_strict:
        print(f"  bootstrap: classic protection strict (enforce_admins=True)")
    if has_rulesets:
        rs_ids = [rs.get("id") for rs in rulesets]
        print(f"  bootstrap: {len(rulesets)} active ruleset(s) targeting {branch}: {rs_ids}")

    classic_disabled = False
    rs_originals: dict[int, list[dict]] = {}  # ruleset_id -> original bypass_actors

    # Step 1: apply both bypasses (classic first so the unwind order is
    # symmetric: rulesets restored first, classic last).
    if classic_strict:
        print(f"  bootstrap: disabling enforce_admins on {repo}/{branch}")
        ok, disable_err = disable_enforce_admins(repo, branch, pat)
        if not ok:
            return False, f"could not disable enforce_admins: {disable_err}", False
        classic_disabled = True

    for rs in rulesets:
        rs_id = rs["id"]
        print(f"  bootstrap: adding admin bypass to ruleset {rs_id}")
        ok, original, err = add_admin_bypass(repo, rs_id, pat)
        if not ok:
            # Unwind whatever was already applied via the finally block by
            # raising into try.
            # NOTE: rs_originals already captures what to restore;
            # classic_disabled flag will trigger enforce_admins restore.
            # Return into the outer flow by jumping to finally via the put
            # never executing.
            # We do this by setting put_ok=False with the bypass error and
            # falling into the try/finally below.
            # Simplest implementation: short-circuit by returning here only
            # AFTER running the same unwind logic.
            # Manually unwind here to keep the finally block focused on the
            # PUT lifecycle.
            crit = _emergency_unwind(repo, branch, pat, rs_originals, classic_disabled)
            full_err = f"could not add bypass to ruleset {rs_id}: {err}"
            if crit:
                full_err += f"; unwind issues: {crit}"
            return False, full_err, True
        rs_originals[rs_id] = original or []

    # Step 2: PUT inside try/finally so step 3 always runs.
    put_ok = False
    put_err: str | None = None
    restore_errs: list[str] = []
    try:
        put_ok, put_err = put_workflow(repo, branch, None, pat)
    finally:
        # Step 3: restore in reverse order -- rulesets first, then classic.
        for rs_id, original in rs_originals.items():
            print(f"  bootstrap: restoring bypass_actors on ruleset {rs_id}")
            ok2, err2 = restore_bypass(repo, rs_id, original, pat)
            if not ok2:
                recovery = (
                    f"PATCH {GH_API}/repos/{GITHUB_USER}/{repo}/rulesets/{rs_id} "
                    f"with classic PAT: bypass_actors={original}"
                )
                print(
                    f"  CRITICAL: failed to restore bypass_actors on ruleset {rs_id}!\n"
                    f"  Ruleset is currently WEAKENED on {repo}.\n"
                    f"  Recovery: {recovery}\n"
                    f"  Error: {err2}",
                    file=sys.stderr,
                )
                restore_errs.append(f"ruleset {rs_id}: {err2}")
        if classic_disabled:
            print(f"  bootstrap: restoring enforce_admins on {repo}/{branch}")
            ok2, err2 = enable_enforce_admins(repo, branch, pat)
            if not ok2:
                recovery_url = (
                    f"{GH_API}/repos/{GITHUB_USER}/{repo}/branches/{branch}"
                    "/protection/enforce_admins"
                )
                print(
                    f"  CRITICAL: failed to restore enforce_admins on {repo}!\n"
                    f"  Branch protection is currently WEAKENED on this repo.\n"
                    f"  Recovery: POST {recovery_url} with classic PAT.\n"
                    f"  Error: {err2}",
                    file=sys.stderr,
                )
                restore_errs.append(f"enforce_admins: {err2}")

    if put_ok and restore_errs:
        return False, f"PUT succeeded but restoration failed: {'; '.join(restore_errs)}", True
    return put_ok, put_err, True


def _emergency_unwind(repo: str, branch: str, pat: str,
                      rs_originals: dict[int, list[dict]],
                      classic_disabled: bool) -> str | None:
    """Best-effort unwind when bootstrap set-up itself fails partway.

    Called when add_admin_bypass on the Nth ruleset fails: prior rulesets
    have already been modified, classic protection may have been
    weakened, and we never reached the try/finally that handles normal
    restoration. This function restores any state that was already
    applied. Returns a comma-joined error string if any restoration
    fails, else None.
    """
    errs: list[str] = []
    for rs_id, original in rs_originals.items():
        ok, err = restore_bypass(repo, rs_id, original, pat)
        if not ok:
            errs.append(f"ruleset {rs_id}: {err}")
    if classic_disabled:
        ok, err = enable_enforce_admins(repo, branch, pat)
        if not ok:
            errs.append(f"enforce_admins: {err}")
    return "; ".join(errs) if errs else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n")[0])
    parser.add_argument(
        "--repos", required=True,
        help="Comma-separated repo names to target. Required -- no default-list "
             "discovery; the operator must name each target explicitly.",
    )
    parser.add_argument("--apply", action="store_true",
                        help="Actually PUT the file. Default is dry-run.")
    parser.add_argument("--confirm-yes", action="store_true",
                        help="Belt-and-braces second flag required with --apply.")
    args = parser.parse_args(argv)

    if args.apply and not args.confirm_yes:
        print("ERROR: --apply requires --confirm-yes (deliberate second flag).",
              file=sys.stderr)
        return 1

    targets = [r.strip() for r in args.repos.split(",") if r.strip()]
    if not targets:
        print("ERROR: --repos was empty after parsing.", file=sys.stderr)
        return 1

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"Mode: {mode}")
    print(f"Targets: {', '.join(targets)}")
    print()

    failures: list[str] = []
    skipped: list[str] = []

    with classic_pat_session() as pat:
        for repo in targets:
            print(f"--- {repo} ---")
            branch = get_default_branch(repo, pat)
            if not branch:
                print("  ERROR: could not resolve default branch")
                failures.append(repo)
                continue

            exists, sha = workflow_status(repo, branch, pat)
            if exists is None:
                print("  ERROR: could not query workflow file state")
                failures.append(repo)
                continue
            if exists:
                print("  already present -- skipping (idempotent)")
                skipped.append(repo)
                continue

            print(f"  branch: {branch}")
            print(f"  would PUT {WORKFLOW_PATH} ({len(CALLER_WORKFLOW)} bytes)")
            if not args.apply:
                continue

            # #1135: deploy_with_bootstrap auto-detects strict protection
            # and toggles enforce_admins around the PUT when needed.
            ok, err, bootstrap_used = deploy_with_bootstrap(repo, branch, pat)
            if ok:
                if bootstrap_used:
                    print("  APPLIED (via bootstrap)")
                else:
                    print("  APPLIED")
            else:
                print(f"  FAILED: {err}")
                failures.append(repo)

    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    if skipped:
        print(f"  already present (no-op): {', '.join(skipped)}")
    if not args.apply:
        print("  dry-run -- no PUTs. Re-run with --apply --confirm-yes to apply.")
    if failures:
        print(f"  FAILURES: {', '.join(failures)}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
