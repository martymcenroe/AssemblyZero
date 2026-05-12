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

#1135: bootstrap mode for STRICT-protected repos missing the workflow.
The original (pre-#1135) tool only worked when direct PUT to main was
allowed -- on STRICT repos (1 review + status checks + enforce_admins)
the PUT is refused with "Repository rule violations found". When a
repo's classic branch protection has enforce_admins=True, the tool now:

  a. DELETEs the enforce_admins sub-resource (admins can bypass)
  b. PUTs the workflow file (succeeds because PAT identity == owner == admin)
  c. POSTs the enforce_admins sub-resource (restores admin enforcement)
  d. All wrapped in try/finally so step (c) runs even if (b) fails.

This is the sanctioned classic-PAT pattern per root CLAUDE.md
("elevated-scope landings: workflow-file edits, branch-protection
updates ... use in-process classic-PAT"). It is NOT the banned
`--admin` flag (which is the `gh pr merge --admin` shortcut). The
bypass window is one HTTP request, owner-only, atomic.

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


def deploy_with_bootstrap(repo: str, branch: str,
                          pat: str) -> tuple[bool, str | None, bool]:
    """Deploy auto-reviewer.yml to a repo, bootstrapping past strict
    protection if necessary.

    Returns (success, error, bootstrap_used). bootstrap_used is True
    when enforce_admins was toggled. enforce_admins is always restored
    on exit -- success OR failure -- via try/finally.

    If enforce_admins restoration ITSELF fails, the error message
    includes a manual recovery command. Operator MUST run that command;
    the repo is left with weakened protection until they do.
    """
    prot, err = get_protection(repo, branch, pat)
    if err:
        return False, f"could not GET protection: {err}", False

    if not is_enforce_admins_on(prot):
        # Permissive branch -- direct PUT works
        ok, put_err = put_workflow(repo, branch, None, pat)
        return ok, put_err, False

    # Strict path: relax enforce_admins, PUT, restore.
    print(f"  bootstrap: strict protection detected (enforce_admins=True)")
    print(f"  bootstrap: disabling enforce_admins on {repo}/{branch}")
    ok, disable_err = disable_enforce_admins(repo, branch, pat)
    if not ok:
        return False, f"could not disable enforce_admins: {disable_err}", False

    put_ok = False
    put_err: str | None = None
    restore_err: str | None = None
    try:
        put_ok, put_err = put_workflow(repo, branch, None, pat)
    finally:
        # Restoration ALWAYS runs (try/finally), even if put_workflow raised.
        # Avoid `return` from `finally` -- it would swallow exceptions; instead
        # capture the result and decide what to surface after the block.
        print(f"  bootstrap: restoring enforce_admins on {repo}/{branch}")
        enable_ok, enable_err = enable_enforce_admins(repo, branch, pat)
        if not enable_ok:
            recovery_url = (
                f"{GH_API}/repos/{GITHUB_USER}/{repo}/branches/{branch}"
                "/protection/enforce_admins"
            )
            print(
                f"  CRITICAL: failed to restore enforce_admins on {repo}!\n"
                f"  Branch protection is currently WEAKENED on this repo.\n"
                f"  Recovery: POST {recovery_url} with classic PAT.\n"
                f"  Error: {enable_err}",
                file=sys.stderr,
            )
            restore_err = enable_err

    # Restoration failure on top of PUT success is load-bearing -- surface it.
    if put_ok and restore_err:
        return False, f"PUT succeeded but enforce_admins restore failed: {restore_err}", True
    return put_ok, put_err, True


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
