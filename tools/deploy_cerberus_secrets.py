#!/usr/bin/env python3
"""Deploy Cerberus (GitHub App) secrets to all repos.

THIS SCRIPT MUST BE RUN BY THE USER, NOT BY AN AGENT.
It handles a private key file — agents must never touch this.

Usage:
    1. Download the .pem from GitHub App settings
    2. Run:  poetry run python tools/deploy_cerberus_secrets.py /path/to/cerberus.pem
    3. DELETE the .pem file immediately after

The script sets two GitHub Actions secrets on every repo:
    - REVIEWER_APP_ID (3079970)
    - REVIEWER_APP_PRIVATE_KEY (contents of the .pem)

All secret writes use an in-process classic PAT via
`tools/_pat_session.classic_pat_session()` (ADR-0216). The PAT is
never placed in the shell env block or subprocess argv. Secret values
are encrypted with libsodium sealed-box against the repo's public key
per GitHub's API contract.

Issue: #736 | Related: #732, #1007 (in-process PAT migration)
"""

import base64
import subprocess
import sys
from pathlib import Path

import requests
from nacl import encoding, public

# Shared with new_repo_setup.py and other v3 callers.
try:
    from _pat_session import classic_pat_session
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from _pat_session import classic_pat_session

APP_ID = "3079970"
GITHUB_USER = "martymcenroe"
_GH_API = "https://api.github.com"
_HTTP_TIMEOUT_S = 30


def _gh_headers(pat: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def get_all_repos() -> list[str]:
    """Get all repos for the user via gh CLI. Read-only — fine-grained PAT OK."""
    result = subprocess.run(
        ["gh", "repo", "list", GITHUB_USER, "--limit", "200",
         "--json", "name", "--jq", ".[].name"],
        capture_output=True, text=True, check=True
    )
    repos = [r.strip() for r in result.stdout.strip().split("\n") if r.strip()]
    return sorted(repos)


def _get_repo_public_key(repo: str, pat: str) -> tuple[str, str] | None:
    """Fetch the repo's Actions-secrets public key.

    Returns (key_id, base64_public_key) on success, or None on failure.
    GitHub requires the sealed-box encrypted secret value + key_id when
    creating/updating a repo secret via the REST API.
    """
    try:
        resp = requests.get(
            f"{_GH_API}/repos/{GITHUB_USER}/{repo}/actions/secrets/public-key",
            headers=_gh_headers(pat),
            timeout=_HTTP_TIMEOUT_S,
        )
    except requests.RequestException:
        return None
    if resp.status_code >= 300:
        return None
    data = resp.json()
    return data["key_id"], data["key"]


def _encrypt_secret(public_key_b64: str, secret_value: str) -> str:
    """Sealed-box encrypt `secret_value` against the repo's public key.

    Matches the scheme documented at
    https://docs.github.com/en/rest/actions/secrets#create-or-update-a-repository-secret
    """
    pk = public.PublicKey(public_key_b64.encode("utf-8"), encoding.Base64Encoder())
    sealed_box = public.SealedBox(pk)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")


def set_secret(repo: str, name: str, value: str, pat: str) -> bool:
    """Set a GitHub Actions secret on a repo via REST API with in-process PAT.

    Args:
        repo: Repo name (no owner prefix); paired with GITHUB_USER.
        name: Secret name (e.g. "REVIEWER_APP_ID").
        value: Plaintext secret value (will be sealed-box encrypted before PUT).
        pat: Classic PAT from classic_pat_session().

    Returns:
        True on HTTP 2xx; False otherwise (including failure to fetch public key).
    """
    pk = _get_repo_public_key(repo, pat)
    if pk is None:
        return False
    key_id, public_key_b64 = pk
    encrypted_value = _encrypt_secret(public_key_b64, value)
    try:
        resp = requests.put(
            f"{_GH_API}/repos/{GITHUB_USER}/{repo}/actions/secrets/{name}",
            headers=_gh_headers(pat),
            json={"encrypted_value": encrypted_value, "key_id": key_id},
            timeout=_HTTP_TIMEOUT_S,
        )
    except requests.RequestException:
        return False
    return resp.status_code < 300


def deploy_to_repo(repo: str, pem_content: str, pat: str) -> tuple[bool, list[str]]:
    """Deploy REVIEWER_APP_ID + REVIEWER_APP_PRIVATE_KEY to a single repo.

    Args:
        repo: Repo name (not owner/name) under GITHUB_USER.
        pem_content: The raw .pem file contents.
        pat: Classic PAT from classic_pat_session().

    Returns:
        (success, failed_secret_names). `success` is True iff both secrets set.
    """
    failed: list[str] = []
    if not set_secret(repo, "REVIEWER_APP_ID", APP_ID, pat):
        failed.append("REVIEWER_APP_ID")
    if not set_secret(repo, "REVIEWER_APP_PRIVATE_KEY", pem_content, pat):
        failed.append("REVIEWER_APP_PRIVATE_KEY")
    return (len(failed) == 0, failed)


def verify_secrets(repo: str, pat: str) -> tuple[bool, list[str]]:
    """Check that both required Cerberus secrets are present on the repo.

    Uses the same in-process PAT as deploy_to_repo for consistency (avoids
    depending on whatever gh auth happens to be pointed at).

    Args:
        repo: Repo name (not owner/name) under GITHUB_USER.
        pat: Classic PAT from classic_pat_session().

    Returns:
        (all_present, missing_secret_names).
    """
    required = {"REVIEWER_APP_ID", "REVIEWER_APP_PRIVATE_KEY"}
    try:
        resp = requests.get(
            f"{_GH_API}/repos/{GITHUB_USER}/{repo}/actions/secrets",
            headers=_gh_headers(pat),
            timeout=_HTTP_TIMEOUT_S,
        )
    except requests.RequestException:
        return (False, sorted(required))
    if resp.status_code >= 300:
        return (False, sorted(required))
    present = {s["name"] for s in resp.json().get("secrets", [])}
    missing = sorted(required - present)
    return (len(missing) == 0, missing)


def main():
    if len(sys.argv) != 2:
        print("Usage: poetry run python tools/deploy_cerberus_secrets.py /path/to/cerberus.pem")
        sys.exit(1)

    pem_path = Path(sys.argv[1])
    if not pem_path.exists():
        print(f"ERROR: File not found: {pem_path}")
        sys.exit(1)

    if not pem_path.suffix == ".pem":
        print(f"WARNING: Expected .pem file, got: {pem_path.name}")
        response = input("Continue anyway? [y/N] ")
        if response.lower() != "y":
            sys.exit(1)

    pem_content = pem_path.read_text(encoding="utf-8").strip()
    if "PRIVATE KEY" not in pem_content:
        print("ERROR: File doesn't look like a private key")
        sys.exit(1)

    print(f"Cerberus App ID: {APP_ID}")
    print(f"Private key: {pem_path.name} ({len(pem_content)} chars)")
    print()

    print("Fetching repo list...")
    repos = get_all_repos()
    print(f"Found {len(repos)} repos\n")

    succeeded = 0
    failed = []

    with classic_pat_session() as pat:
        for i, repo in enumerate(repos, 1):
            prefix = f"[{i}/{len(repos)}] {repo}"
            ok, failed_names = deploy_to_repo(repo, pem_content, pat)
            if ok:
                print(f"  {prefix}: OK")
                succeeded += 1
            else:
                print(f"  {prefix}: FAILED ({', '.join(failed_names)})")
                failed.append(repo)

    print(f"\n{'=' * 50}")
    print(f"Done: {succeeded}/{len(repos)} repos configured")
    if failed:
        print(f"Failed: {', '.join(failed)}")
    print(f"\n*** NOW DELETE THE .pem FILE: {pem_path} ***")
    print("The secret is stored in GitHub — you never need the file again.")


if __name__ == "__main__":
    main()
