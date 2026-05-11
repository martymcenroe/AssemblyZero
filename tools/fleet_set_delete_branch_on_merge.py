#!/usr/bin/env python3
"""Fleet-wide: flip delete_branch_on_merge to True on every owned, non-archived repo.

Follow-up to today's bulk merge of 38 cleanup-security-hooks PRs (2026-04-30):
17 of the merged repos still had "Automatically delete head branches" disabled,
leaving stale remote branches that needed manual cleanup. This script flips the
setting on every owned, non-archived repo so future merges auto-clean.

Idempotent. Safe to re-run. Skips repos already set to True.

Required scopes on the classic PAT:
  - repo (full) -- the classic 'repo' scope grants Administration:write on
                   owned repos, which is what PATCH /repos/{owner}/{repo}
                   needs to mutate delete_branch_on_merge.

OPERATIONAL RULE (per ADR-0216 + 2026-04-30 hardenings):
  This script MUST be run by the user in their own Git Bash. It MUST NOT be
  invoked by an agent (Claude Code, Codex, Gemini) via the agent's Bash tool.
  Reason: the agent's subprocess inherits theoretical heap-read access to the
  PAT during the seconds the script runs.

Assumes ~/.gnupg/gpg-agent.conf has all cache TTLs at 0 (applied 2026-04-30
per ADR-0216 hardening). The script does not depend on this for correctness,
but security depends on it: with caching disabled, every gpg invocation
prompts pinentry fresh, so a sibling process's silent decrypt attempt would
surface a dialog the user can refuse. See _pat_session.py docstring for the
rationale.

Usage:
    poetry run python tools/fleet_set_delete_branch_on_merge.py [--dry-run]
                                                                 [--repos R1,R2,...]
                                                                 [--include-archived]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pat_session import classic_pat_session  # noqa: E402

REPO_OWNER = "martymcenroe"
GH_API = "https://api.github.com"
HTTP_TIMEOUT_S = 30
MAX_RETRIES = 4
INITIAL_BACKOFF_S = 1.0
PER_PAGE = 100


def _gh_headers(pat: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _request_with_retry(
    method: str, url: str, pat: str, **kwargs
) -> requests.Response:
    """HTTP request with exponential backoff on transient errors.

    Retries: connection errors, timeouts, 5xx, 429 (rate-limited), and
    403 with X-RateLimit-Remaining=0 (secondary rate limit).

    Does NOT retry: 4xx other than 403/429 (permanent for this caller).
    """
    backoff = INITIAL_BACKOFF_S
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            r = requests.request(
                method, url, headers=_gh_headers(pat), timeout=HTTP_TIMEOUT_S, **kwargs
            )
        except (requests.ConnectionError, requests.Timeout) as e:
            last_exc = e
            if attempt < MAX_RETRIES:
                print(f"    network error ({type(e).__name__}); retry in {backoff}s")
                time.sleep(backoff)
                backoff *= 2
                continue
            raise

        # Rate limit detection
        if r.status_code == 429:
            retry_after = int(r.headers.get("Retry-After", "30"))
            if attempt < MAX_RETRIES:
                print(f"    HTTP 429; sleeping {retry_after}s per Retry-After")
                time.sleep(retry_after)
                continue
        if r.status_code == 403 and r.headers.get("X-RateLimit-Remaining") == "0":
            reset = int(r.headers.get("X-RateLimit-Reset", "0"))
            wait = max(reset - int(time.time()), 30)
            if attempt < MAX_RETRIES:
                print(f"    primary rate limit hit; sleeping {wait}s until reset")
                time.sleep(wait)
                continue
        if 500 <= r.status_code < 600:
            if attempt < MAX_RETRIES:
                print(f"    HTTP {r.status_code}; retry in {backoff}s")
                time.sleep(backoff)
                backoff *= 2
                continue

        # All other responses: return as-is (caller decides 4xx handling)
        return r

    if last_exc:
        raise last_exc
    raise RuntimeError(f"exhausted retries on {method} {url}")


def list_owned_repos(pat: str, include_archived: bool) -> list[dict[str, Any]]:
    """Return list of repos owned by the authenticated user.

    Each entry: {"name": str, "full_name": str, "archived": bool,
                 "delete_branch_on_merge": bool, ...}
    """
    repos: list[dict[str, Any]] = []
    page = 1
    while True:
        r = _request_with_retry(
            "GET",
            f"{GH_API}/user/repos",
            pat,
            params={
                "affiliation": "owner",
                "per_page": PER_PAGE,
                "page": page,
            },
        )
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        repos.extend(batch)
        if len(batch) < PER_PAGE:
            break
        page += 1
    if not include_archived:
        repos = [r for r in repos if not r.get("archived", False)]
    return repos


def get_setting(repo_full_name: str, pat: str) -> bool | None:
    """Return current delete_branch_on_merge for the repo, or None on error."""
    r = _request_with_retry("GET", f"{GH_API}/repos/{repo_full_name}", pat)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return bool(r.json().get("delete_branch_on_merge", False))


def set_setting(repo_full_name: str, value: bool, pat: str) -> None:
    """Flip delete_branch_on_merge to value. Raises on non-2xx."""
    r = _request_with_retry(
        "PATCH",
        f"{GH_API}/repos/{repo_full_name}",
        pat,
        json={"delete_branch_on_merge": value},
    )
    r.raise_for_status()


def process_repo(
    repo: dict[str, Any], pat: str, dry_run: bool
) -> tuple[str, str]:
    """Return (status, detail) for one repo.

    status in: 'already_on', 'flipped', 'would_flip', 'archived',
               'permission_denied', 'not_found', 'error'
    """
    full_name = repo["full_name"]
    if repo.get("archived", False):
        return ("archived", f"{full_name}: archived, skipped")
    current = repo.get("delete_branch_on_merge")
    if current is True:
        return ("already_on", f"{full_name}: already true, skipped")
    if current is None:
        # Wasn't in the list response; explicit GET to confirm.
        try:
            current = get_setting(full_name, pat)
        except requests.HTTPError as e:
            return ("error", f"{full_name}: GET failed: {e}")
        if current is None:
            return ("not_found", f"{full_name}: GET returned 404")
        if current is True:
            return ("already_on", f"{full_name}: already true (post-GET), skipped")
    if dry_run:
        return ("would_flip", f"{full_name}: WOULD flip false -> true")
    try:
        set_setting(full_name, True, pat)
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 403:
            return ("permission_denied", f"{full_name}: 403 -- PAT lacks scope")
        return ("error", f"{full_name}: PATCH failed: {e}")
    return ("flipped", f"{full_name}: flipped false -> true")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dry-run", action="store_true",
                        help="List what would change; take no action.")
    parser.add_argument("--repos", default="",
                        help="Comma-separated owner-less repo names. "
                             "Defaults to all owned, non-archived repos.")
    parser.add_argument("--include-archived", action="store_true",
                        help="Include archived repos (default: skip).")
    args = parser.parse_args()

    with classic_pat_session() as pat:
        # Pre-flight: one cheap call to confirm PAT auth works before we
        # start iterating. Fail fast if scope is wrong.
        r = _request_with_retry("GET", f"{GH_API}/user", pat)
        if r.status_code != 200:
            print(f"ERROR: pre-flight /user check failed: {r.status_code} {r.text[:200]}")
            return 1
        whoami = r.json().get("login", "?")
        print(f"Authenticated as: {whoami}")

        if args.repos:
            names = [n.strip() for n in args.repos.split(",") if n.strip()]
            # Build minimal repo dicts; explicit GET fills in missing fields.
            repos = [{"name": n, "full_name": f"{REPO_OWNER}/{n}",
                      "archived": False, "delete_branch_on_merge": None}
                     for n in names]
        else:
            try:
                repos = list_owned_repos(pat, include_archived=args.include_archived)
            except Exception as e:  # noqa: BLE001
                print(f"ERROR: discovery failed: {e}")
                return 2

        print(f"Processing {len(repos)} repo(s){' (DRY-RUN)' if args.dry_run else ''}")
        print()

        counts: dict[str, int] = {}
        for repo in repos:
            try:
                status, detail = process_repo(repo, pat, args.dry_run)
            except Exception as e:  # noqa: BLE001
                status, detail = "error", f"{repo.get('full_name','?')}: UNEXPECTED {type(e).__name__}: {e}"
            counts[status] = counts.get(status, 0) + 1
            print(f"  [{status:18s}] {detail}")

        print()
        print("=== Summary ===")
        for status in ("flipped", "would_flip", "already_on", "archived",
                       "not_found", "permission_denied", "error"):
            n = counts.get(status, 0)
            if n:
                print(f"  {status}: {n}")

        # Non-zero exit if any repo errored or hit permission denied.
        if counts.get("error", 0) or counts.get("permission_denied", 0):
            return 3

    return 0


if __name__ == "__main__":
    sys.exit(main())
