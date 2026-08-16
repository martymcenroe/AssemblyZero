#!/usr/bin/env python3
"""Land Aletheia #775 (remove deploy-infra + post-deploy-smoke from ci.yml).

Issue: martymcenroe/Aletheia#775 (follow-up to #773).

Removes the last static-credential path from CI: the manual-only `deploy-infra`
job (and its `post-deploy-smoke` companion) were the only remaining consumers of
the admin `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` repo secrets. Deploys are
done locally via provision.sh, so the jobs are redundant. After this merges, the
two repo secrets are unreferenced and can be deleted in Settings.

Same mechanism + threat model as land_aletheia_ci_oidc.py: the fine-grained PAT
can't push workflow files (ADR-0216 §1), so this lands the already-committed fix
(local branch `775-retire-deploy-infra-static-keys`) via the gpg-decrypted classic
PAT + Contents API + PR + squash-merge. THE OPERATOR RUNS THIS in their own Git
Bash; an agent must never invoke it.

Usage (operator, one run):
    cd /c/Users/mcwiz/Projects/AssemblyZero
    poetry run python tools/land_aletheia_775.py --apply
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
BRANCH = "775-retire-deploy-infra-static-keys"
LOCAL_BRANCH = "775-retire-deploy-infra-static-keys"
ISSUE_NUMBER = 775
ALETHEIA_REPO = Path("C:/Users/mcwiz/Projects/Aletheia")
HTTP_TIMEOUT_S = 30
POLL_INTERVAL_S = 10
MERGEABLE_TIMEOUT_S = 900

PR_TITLE = "ci: remove deploy-infra + post-deploy-smoke; drop static AWS keys (Closes #775)"
PR_BODY = """## Summary

Removes the `deploy-infra` and `post-deploy-smoke` jobs from `ci.yml`. `deploy-infra`
ran `provision.sh` on manual dispatch using the admin static keys
(`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`) — it was the last consumer of those
secrets and is redundant with local `provision.sh` deploys. Also drops the now-unused
`workflow_dispatch` trigger.

After this merges, the two repo secrets are unreferenced and should be deleted
(Settings → Secrets and variables → Actions). Completes the OIDC hardening from #773 —
CI now holds no long-lived AWS credentials.

Closes #775
"""


def _headers(pat: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def read_fixed_ci_yml() -> bytes:
    """Return the fixed ci.yml bytes from the local branch blob (LF, not CRLF)."""
    proc = subprocess.run(
        ["git", "-C", str(ALETHEIA_REPO), "show", f"{LOCAL_BRANCH}:{WORKFLOW_PATH}"],
        capture_output=True, check=True,
    )
    return proc.stdout.replace(b"\r\n", b"\n")


def get_branch_head(pat: str, branch: str = "main") -> str:
    r = requests.get(f"{GH_API}/repos/{GITHUB_USER}/{REPO}/git/refs/heads/{branch}",
                     headers=_headers(pat), timeout=HTTP_TIMEOUT_S)
    r.raise_for_status()
    return r.json()["object"]["sha"]


def ensure_branch(pat: str, source_sha: str) -> None:
    r = requests.post(f"{GH_API}/repos/{GITHUB_USER}/{REPO}/git/refs",
                      headers=_headers(pat),
                      json={"ref": f"refs/heads/{BRANCH}", "sha": source_sha},
                      timeout=HTTP_TIMEOUT_S)
    if r.status_code == 422:
        print(f"  branch {BRANCH} already exists — reusing it")
        return
    r.raise_for_status()


def get_file_sha(pat: str, ref: str) -> str:
    r = requests.get(f"{GH_API}/repos/{GITHUB_USER}/{REPO}/contents/{WORKFLOW_PATH}",
                     params={"ref": ref}, headers=_headers(pat), timeout=HTTP_TIMEOUT_S)
    r.raise_for_status()
    return r.json()["sha"]


def put_file(pat: str, content: bytes, file_sha: str) -> None:
    r = requests.put(f"{GH_API}/repos/{GITHUB_USER}/{REPO}/contents/{WORKFLOW_PATH}",
                     headers=_headers(pat),
                     json={"message": f"ci: remove deploy-infra + post-deploy-smoke; drop static AWS keys (Closes #{ISSUE_NUMBER})",
                           "content": base64.b64encode(content).decode(),
                           "sha": file_sha, "branch": BRANCH},
                     timeout=HTTP_TIMEOUT_S)
    r.raise_for_status()


def create_pr(pat: str) -> int:
    r = requests.post(f"{GH_API}/repos/{GITHUB_USER}/{REPO}/pulls",
                      headers=_headers(pat),
                      json={"title": PR_TITLE, "head": BRANCH, "base": "main", "body": PR_BODY},
                      timeout=HTTP_TIMEOUT_S)
    if r.status_code == 422 and "already exist" in r.text.lower():
        existing = requests.get(f"{GH_API}/repos/{GITHUB_USER}/{REPO}/pulls",
                                params={"state": "open", "head": f"{GITHUB_USER}:{BRANCH}"},
                                headers=_headers(pat), timeout=HTTP_TIMEOUT_S)
        existing.raise_for_status()
        num = existing.json()[0]["number"]
        print(f"  PR for {BRANCH} already open (#{num}) — reusing")
        return num
    r.raise_for_status()
    return r.json()["number"]


def mergeable_state(pat: str, pr: int) -> str | None:
    r = requests.get(f"{GH_API}/repos/{GITHUB_USER}/{REPO}/pulls/{pr}",
                     headers=_headers(pat), timeout=HTTP_TIMEOUT_S)
    r.raise_for_status()
    return r.json().get("mergeable_state")


def wait_for_mergeable(pat: str, pr: int, timeout_s: int = MERGEABLE_TIMEOUT_S) -> str:
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
    r = requests.put(f"{GH_API}/repos/{GITHUB_USER}/{REPO}/pulls/{pr}/merge",
                     headers=_headers(pat), json={"merge_method": "squash"},
                     timeout=HTTP_TIMEOUT_S)
    r.raise_for_status()
    return r.json().get("sha", "")


def delete_remote_branch(pat: str) -> None:
    try:
        requests.delete(f"{GH_API}/repos/{GITHUB_USER}/{REPO}/git/refs/heads/{BRANCH}",
                        headers=_headers(pat), timeout=HTTP_TIMEOUT_S)
    except requests.RequestException:
        pass


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true",
                    help="Perform branch + commit + PR + squash-merge. Default: dry-run.")
    args = ap.parse_args()

    content = read_fixed_ci_yml()
    print(f"Loaded fixed {WORKFLOW_PATH} from local branch {LOCAL_BRANCH}: {len(content)} bytes")
    if b"secrets.AWS" in content:
        print("ERROR: fixed ci.yml STILL references secrets.AWS_* — wrong branch/content. Aborting.")
        return 1
    if b"AletheiaCIAuditRole" not in content:
        print("ERROR: fixed ci.yml missing the OIDC role (would undo #773) — wrong content. Aborting.")
        return 1
    print("  guard OK: static AWS keys removed, OIDC role preserved")

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
        print("Next: delete the AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY repo secrets in "
              "Settings → Secrets and variables → Actions. Then CI holds no static AWS creds.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
