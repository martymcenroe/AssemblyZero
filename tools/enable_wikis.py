#!/usr/bin/env python3
"""Re-enable wikis on all repos via the in-process classic-PAT pattern (ADR-0216).

Enabling a wiki is a repo-settings PATCH (`Administration: write`) which the
fleet's fine-grained PAT cannot perform — it returns 403 (verified 2026-05-31,
#1474). This tool decrypts the classic PAT in-process and calls the GitHub REST
API directly via `requests`; it never sets os.environ, never passes the PAT via
argv, never logs it.

Defaults to DRY-RUN; pass --apply to mutate (standard 0017).

OPERATOR-RUN ONLY (ADR-0216 §6.1): run this yourself in your own Git Bash. NEVER
let an agent invoke it via its Bash tool — the spawned Python process would be
the agent's child and its heap is theoretically readable while the PAT is in
scope.

Usage:
    poetry run python tools/enable_wikis.py            # dry-run (default)
    poetry run python tools/enable_wikis.py --apply    # enable wikis
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pat_session import classic_pat_session  # noqa: E402

GITHUB_USER = "martymcenroe"
GH_API = "https://api.github.com"
HTTP_TIMEOUT_S = 30


def _gh_headers(pat: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def get_all_repos() -> list[tuple[str, bool]]:
    """List repos + current wiki status.

    Read-only — a fine-grained PAT via the gh CLI is sufficient here; only the
    PATCH (enable_wiki) needs the classic PAT.
    """
    result = subprocess.run(
        ["gh", "repo", "list", GITHUB_USER, "--limit", "200",
         "--json", "name,hasWikiEnabled",
         "--jq", r'.[] | "\(.name)\t\(.hasWikiEnabled)"'],
        capture_output=True, text=True, check=True,
    )
    repos = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        name, enabled = line.strip().split("\t")
        repos.append((name, enabled == "true"))
    return sorted(repos)


def enable_wiki(repo: str, pat: str) -> tuple[bool, str]:
    """PATCH has_wiki=true via the classic PAT. Returns (ok, detail)."""
    resp = requests.patch(
        f"{GH_API}/repos/{GITHUB_USER}/{repo}",
        headers=_gh_headers(pat),
        json={"has_wiki": True},
        timeout=HTTP_TIMEOUT_S,
    )
    if resp.status_code == 200:
        return (True, "enabled")
    return (False, f"HTTP {resp.status_code}: {resp.text[:160]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--apply", action="store_true",
        help="Actually enable wikis (default: dry-run preview).",
    )
    args = parser.parse_args()

    print("Fetching repo list...")
    repos = get_all_repos()
    needs_fix = [name for name, enabled in repos if not enabled]
    print(f"Found {len(repos)} repos; {len(needs_fix)} with wiki disabled.\n")

    if not needs_fix:
        print("Nothing to do.")
        return 0

    if not args.apply:
        print("DRY-RUN (pass --apply to enable). Would enable wikis on:")
        for repo in needs_fix:
            print(f"  - {repo}")
        return 0

    succeeded = 0
    failed = []
    with classic_pat_session() as pat:
        for i, repo in enumerate(needs_fix, 1):
            ok, detail = enable_wiki(repo, pat)
            if ok:
                print(f"  [{i}/{len(needs_fix)}] {repo}: {detail}")
                succeeded += 1
            else:
                print(f"  [{i}/{len(needs_fix)}] {repo}: FAILED — {detail}")
                failed.append(repo)

    print(f"\nDone: {succeeded}/{len(needs_fix)} wikis enabled")
    if failed:
        print(f"Failed: {', '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
