#!/usr/bin/env python3
"""Land the Aletheia CI OIDC migration (ci.yml) via the classic-PAT Contents API.

Issue: martymcenroe/Aletheia#773.

The Aletheia fine-grained PAT deliberately lacks `workflow` scope (ADR-0216 §1),
so `git push` of a `.github/workflows/*` change is rejected. This tool lands the
already-committed ci.yml fix (local branch `773-ci-oidc-migration`) using the
gpg-decrypted classic PAT via the GitHub Contents API + PR + squash-merge.

The fix migrates the `compliance-audit` job from admin static keys to the
read-only OIDC role `AletheiaCIAuditRole` (already created + verified in AWS),
and gates `deploy-infra`/`post-deploy-smoke` to manual (`workflow_dispatch`) so
merges to main no longer auto-run provision.sh. This greens the nightly red
badge and removes long-lived CI credentials.

Auth: _pat_session.classic_pat_session() — the classic PAT is gpg-decrypted in
this process's heap only, never written to env or passed via argv. THE OPERATOR
RUNS THIS, in their own Git Bash. An agent must never invoke it (the PAT would
be readable from the agent's child-process heap for the seconds it's in scope).

Required classic-PAT scopes: repo (full) + workflow.

Usage (operator, one run):
    cd /c/Users/mcwiz/Projects/AssemblyZero
    poetry run python tools/land_aletheia_ci_oidc.py --apply

Default is dry-run (prints the plan, read-only). --apply performs the branch +
Contents-API commit + PR + squash-merge. Everything upstream (AWS role, ci.yml
edit) is already done and verified, so --apply directly is fine.
"""
from __future__ import annotations

import argparse
import base64
import subprocess
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pat_session import classic_pat_session  # noqa: E402

GITHUB_USER = "martymcenroe"
REPO = "Aletheia"
GH_API = "https://api.github.com"
WORKFLOW_PATH = ".github/workflows/ci.yml"
BRANCH = "773-ci-oidc-migration"
LOCAL_BRANCH = "773-ci-oidc-migration"
ISSUE_NUMBER = 773
ALETHEIA_REPO = Path("C:/Users/mcwiz/Projects/Aletheia")
SENTINEL = b"AletheiaCIAuditRole"  # must be present in the fixed ci.yml
HTTP_TIMEOUT_S = 30
POLL_INTERVAL_S = 10
MERGEABLE_TIMEOUT_S = 900

PR_TITLE = (
    "ci: migrate compliance-audit to GitHub OIDC read-only role; "
    "gate deploy to manual (Closes #773)"
)
PR_BODY = """## Summary

Migrates the `compliance-audit` CI job from admin static access keys to the
least-privilege OIDC role `AletheiaCIAuditRole` (assumed via GitHub Actions
`id-token`; trust scoped to `repo:martymcenroe/Aletheia:*`; only the three
read-only bedrock actions the audit tests call). Gates `deploy-infra` and
`post-deploy-smoke` to `workflow_dispatch` so merges to main no longer
auto-run `provision.sh`.

Fixes the nightly red badge (the `Configure AWS Credentials` step was failing
on missing/expired static secrets) and removes long-lived CI credentials. The
AWS OIDC provider + role were provisioned out-of-band and verified.

Closes #773
"""


def _headers(pat: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def read_fixed_ci_yml() -> bytes:
    """Return the fixed ci.yml bytes from the local branch blob (LF, not CRLF).

    Reads the git blob directly (git stores LF), so no working-tree CRLF leaks
    into the Contents API and flips the whole file's line endings on origin.
    """
    proc = subprocess.run(
        ["git", "-C", str(ALETHEIA_REPO), "show", f"{LOCAL_BRANCH}:{WORKFLOW_PATH}"],
        capture_output=True,
        check=True,
    )
    return proc.stdout.replace(b"\r\n", b"\n")


def get_branch_head(pat: str, branch: str = "main") -> str:
    r = requests.get(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/git/refs/heads/{branch}",
        headers=_headers(pat), timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json()["object"]["sha"]


def ensure_branch(pat: str, source_sha: str) -> None:
    r = requests.post(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/git/refs",
        headers=_headers(pat),
        json={"ref": f"refs/heads/{BRANCH}", "sha": source_sha},
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code == 422:  # ref already exists — reuse (idempotent re-run)
        print(f"  branch {BRANCH} already exists — reusing it")
        return
    r.raise_for_status()


def get_file_sha(pat: str, ref: str) -> str:
    r = requests.get(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/contents/{WORKFLOW_PATH}",
        params={"ref": ref}, headers=_headers(pat), timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json()["sha"]


def put_file(pat: str, content: bytes, file_sha: str) -> None:
    r = requests.put(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/contents/{WORKFLOW_PATH}",
        headers=_headers(pat),
        json={
            "message": f"ci: migrate compliance-audit to OIDC; gate deploy to manual (Closes #{ISSUE_NUMBER})",
            "content": base64.b64encode(content).decode(),
            "sha": file_sha,
            "branch": BRANCH,
        },
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()


def create_pr(pat: str) -> int:
    r = requests.post(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/pulls",
        headers=_headers(pat),
        json={"title": PR_TITLE, "head": BRANCH, "base": "main", "body": PR_BODY},
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code == 422 and "already exist" in r.text.lower():
        existing = requests.get(
            f"{GH_API}/repos/{GITHUB_USER}/{REPO}/pulls",
            params={"state": "open", "head": f"{GITHUB_USER}:{BRANCH}"},
            headers=_headers(pat), timeout=HTTP_TIMEOUT_S,
        )
        existing.raise_for_status()
        num = existing.json()[0]["number"]
        print(f"  PR for {BRANCH} already open (#{num}) — reusing")
        return num
    r.raise_for_status()
    return r.json()["number"]


def mergeable_state(pat: str, pr: int) -> str | None:
    r = requests.get(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/pulls/{pr}",
        headers=_headers(pat), timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json().get("mergeable_state")


def wait_for_mergeable(pat: str, pr: int, timeout_s: int = MERGEABLE_TIMEOUT_S) -> str:
    """Poll until clean/unstable (both squash-mergeable). Cerberus-AZ approves
    after pr-sentinel-mm passes, which can take up to a few minutes."""
    deadline = time.time() + timeout_s
    last, polled = "unknown", False
    while time.time() < deadline:
        state = mergeable_state(pat, pr) or "unknown"
        last = state
        print(f"  mergeable_state = {state}")
        if state in ("clean", "unstable"):
            return state
        if state == "dirty":
            return state
        if state == "blocked" and polled:
            return state
        polled = True
        time.sleep(POLL_INTERVAL_S)
    return last


def merge_pr(pat: str, pr: int) -> str:
    r = requests.put(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/pulls/{pr}/merge",
        headers=_headers(pat), json={"merge_method": "squash"},
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json().get("sha", "")


def delete_remote_branch(pat: str) -> None:
    """Best-effort cleanup of the remote branch after merge."""
    try:
        requests.delete(
            f"{GH_API}/repos/{GITHUB_USER}/{REPO}/git/refs/heads/{BRANCH}",
            headers=_headers(pat), timeout=HTTP_TIMEOUT_S,
        )
    except requests.RequestException:
        pass


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true",
                    help="Perform branch + commit + PR + squash-merge. Default: dry-run.")
    args = ap.parse_args()

    content = read_fixed_ci_yml()
    print(f"Loaded fixed {WORKFLOW_PATH} from local branch {LOCAL_BRANCH}: {len(content)} bytes")
    if SENTINEL not in content:
        print(f"ERROR: fixed ci.yml does not contain {SENTINEL!r} — wrong branch or content. Aborting.")
        return 1

    with classic_pat_session() as pat:
        main_sha = get_branch_head(pat, "main")
        print(f"main HEAD: {main_sha[:8]}")

        if not args.apply:
            cur = get_file_sha(pat, "main")
            print("\n=== DRY-RUN (no changes) ===")
            print(f"Would branch {BRANCH} from {main_sha[:8]}")
            print(f"Would update {WORKFLOW_PATH} (current blob {cur[:8]}) via Contents API")
            print(f"Would open PR: {PR_TITLE!r}")
            print(f"Would wait for mergeable, then squash-merge (Closes #{ISSUE_NUMBER})")
            print("\nRe-run with --apply to execute.")
            return 0

        print("\n=== APPLY ===")
        ensure_branch(pat, main_sha)
        file_sha = get_file_sha(pat, BRANCH)
        print(f"current {WORKFLOW_PATH} blob on branch: {file_sha[:8]}")
        put_file(pat, content, file_sha)
        print(f"committed fixed {WORKFLOW_PATH} on {BRANCH}")
        pr = create_pr(pat)
        print(f"PR #{pr} opened — waiting for checks + Cerberus-AZ approval...")
        state = wait_for_mergeable(pat, pr)
        if state not in ("clean", "unstable"):
            print(f"\nPR #{pr} did not become mergeable (final state: {state}). "
                  f"Branch + PR retained for review. NOT merged.")
            return 1
        sha = merge_pr(pat, pr)
        delete_remote_branch(pat)
        print(f"\n✓ PR #{pr} squash-merged at {sha[:8]} — Closes #{ISSUE_NUMBER}")
        print("The merge triggers CI on main; compliance-audit now runs via OIDC. Watch it go green.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
