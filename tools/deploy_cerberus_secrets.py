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

Issue: #736 | Related: #732
"""

import subprocess
import sys
from pathlib import Path

APP_ID = "3079970"
GITHUB_USER = "martymcenroe"


def get_all_repos() -> list[str]:
    """Get all repos for the user via gh CLI."""
    result = subprocess.run(
        ["gh", "repo", "list", GITHUB_USER, "--limit", "200",
         "--json", "name", "--jq", ".[].name"],
        capture_output=True, text=True, check=True
    )
    repos = [r.strip() for r in result.stdout.strip().split("\n") if r.strip()]
    return sorted(repos)


def set_secret(repo: str, name: str, value: str) -> bool:
    """Set a GitHub Actions secret on a repo."""
    result = subprocess.run(
        ["gh", "secret", "set", name, "--repo", f"{GITHUB_USER}/{repo}",
         "--body", value],
        capture_output=True, text=True
    )
    return result.returncode == 0


def deploy_to_repo(repo: str, pem_content: str) -> tuple[bool, list[str]]:
    """Deploy REVIEWER_APP_ID + REVIEWER_APP_PRIVATE_KEY to a single repo.

    Args:
        repo: Repo name (not owner/name) under GITHUB_USER.
        pem_content: The raw .pem file contents.

    Returns:
        (success, failed_secret_names). `success` is True iff both secrets set.
    """
    failed: list[str] = []
    if not set_secret(repo, "REVIEWER_APP_ID", APP_ID):
        failed.append("REVIEWER_APP_ID")
    if not set_secret(repo, "REVIEWER_APP_PRIVATE_KEY", pem_content):
        failed.append("REVIEWER_APP_PRIVATE_KEY")
    return (len(failed) == 0, failed)


def verify_secrets(repo: str) -> tuple[bool, list[str]]:
    """Check that both required Cerberus secrets are present on the repo.

    Args:
        repo: Repo name (not owner/name) under GITHUB_USER.

    Returns:
        (all_present, missing_secret_names).
    """
    required = {"REVIEWER_APP_ID", "REVIEWER_APP_PRIVATE_KEY"}
    result = subprocess.run(
        ["gh", "api", f"repos/{GITHUB_USER}/{repo}/actions/secrets",
         "--jq", ".secrets[].name"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return (False, sorted(required))
    present = {n.strip() for n in result.stdout.split("\n") if n.strip()}
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

    for i, repo in enumerate(repos, 1):
        prefix = f"[{i}/{len(repos)}] {repo}"
        ok, failed_names = deploy_to_repo(repo, pem_content)
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
