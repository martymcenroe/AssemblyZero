#!/usr/bin/env python3
"""Re-enable wikis on all repos.

Usage:
    poetry run python tools/enable_wikis.py

Requires: gh CLI authenticated (fine-grained PAT is fine — needs repo metadata write).
"""

import subprocess
import sys

GITHUB_USER = "martymcenroe"


def get_all_repos() -> list[str]:
    result = subprocess.run(
        ["gh", "repo", "list", GITHUB_USER, "--limit", "200",
         "--json", "name,hasWikiEnabled", "--jq", '.[] | "\(.name)\t\(.hasWikiEnabled)"'],
        capture_output=True, text=True, check=True
    )
    repos = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        name, enabled = line.strip().split("\t")
        repos.append((name, enabled == "true"))
    return sorted(repos)


def enable_wiki(repo: str) -> bool:
    result = subprocess.run(
        ["gh", "api", "-X", "PATCH", f"/repos/{GITHUB_USER}/{repo}",
         "-F", "has_wiki=true"],
        capture_output=True, text=True
    )
    return result.returncode == 0


def main():
    print("Fetching repo list...")
    repos = get_all_repos()
    print(f"Found {len(repos)} repos\n")

    already_on = [name for name, enabled in repos if enabled]
    needs_fix = [name for name, enabled in repos if not enabled]

    print(f"  Wiki already enabled: {len(already_on)}")
    print(f"  Wiki disabled: {len(needs_fix)}\n")

    if not needs_fix:
        print("Nothing to do.")
        return

    succeeded = 0
    failed = []

    for i, repo in enumerate(needs_fix, 1):
        if enable_wiki(repo):
            print(f"  [{i}/{len(needs_fix)}] {repo}: enabled")
            succeeded += 1
        else:
            print(f"  [{i}/{len(needs_fix)}] {repo}: FAILED")
            failed.append(repo)

    print(f"\nDone: {succeeded}/{len(needs_fix)} wikis enabled")
    if failed:
        print(f"Failed: {', '.join(failed)}")


if __name__ == "__main__":
    main()
