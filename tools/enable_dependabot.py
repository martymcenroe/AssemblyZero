#!/usr/bin/env python3
"""Enable Dependabot on existing repos via REST API (#1331).

The defect this addresses: private repos created via runbooks 0901+0927
land with `.github/dependabot.yml` in place but Dependabot itself
disabled at the repo settings level. Result: yml is inert, no PRs emit,
the wedge starves. Confirmed 2026-05-26 on `martymcenroe/dependabot-honeypot`
— 11+ hours after yml landed + 65 decorative deps pinned to ~12-18mo old
versions, zero dependabot PRs opened.

What this tool does (per target repo):
  1. GET /repos/{owner}/{repo} — read current security_and_analysis state
  2. PATCH /repos/{owner}/{repo} with security_and_analysis enabling
     Dependabot security updates
  3. PUT /repos/{owner}/{repo}/vulnerability-alerts — enable alerts
  4. PUT /repos/{owner}/{repo}/automated-security-fixes — enable
     automated fixes

Per ADR-0216: classic PAT decrypted in-process via classic_pat_session().
The PAT lives only in this Python process's heap; never in env, never in
subprocess argv, never via `gh auth`. **The OPERATOR runs this script,
not the agent** — the in-process protection assumes the Python process is
the operator's, not an agent's child.

Per AssemblyZero standard 0017: `--apply` flag required to mutate. Default
behavior is dry-run that reports what WOULD change.

Usage:
  poetry run python tools/enable_dependabot.py --repo OWNER/NAME
  poetry run python tools/enable_dependabot.py --repo OWNER/NAME --apply
  poetry run python tools/enable_dependabot.py --fleet
  poetry run python tools/enable_dependabot.py --fleet --apply

Exit codes:
  0 — completed (dry-run or apply); all targets processed without errors
  1 — argument or input error
  2 — one or more per-repo errors during processing (partial state)

Related:
  - #1331 — this issue
  - ADR-0216 — in-process classic PAT pattern
  - runbook 0901 — new project setup (to be updated to call this)
  - runbook 0927 — new repo human checklist (to be updated)
  - sibling: companion integration in new_repo_setup.py for new-repo creation
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import requests

try:
    from _pat_session import classic_pat_session
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from _pat_session import classic_pat_session


GITHUB_USER = "martymcenroe"
FLEET_REPO_LIMIT = 200
HTTP_TIMEOUT_S = 30


# ────────────────────────────────────────────────────────────────────
# Public-API helper (the part new_repo_setup.py imports)
# ────────────────────────────────────────────────────────────────────


@dataclass
class EnableResult:
    """Per-repo result. One per target."""
    repo: str
    before: dict[str, Any]  # `security_and_analysis` block from GET
    actions: dict[str, str]  # endpoint -> "HTTP NNN" or "DRY-RUN" or "ERROR: ..."
    ok: bool  # True iff all actions succeeded (or all were dry-run)


def enable_dependabot_for_repo(
    owner: str,
    name: str,
    pat: str,
    apply: bool,
) -> EnableResult:
    """Enable Dependabot for one repo. Single-public function the
    scaffolder + the CLI both call.

    apply=False is a dry-run: reads current state, reports what would
    change, makes NO mutations.
    apply=True executes the three API calls.
    """
    repo = f"{owner}/{name}"
    headers = {
        "Authorization": f"token {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # Step 1: read current state. Always done, even in dry-run.
    actions: dict[str, str] = {}
    before: dict[str, Any] = {}
    try:
        r = requests.get(
            f"https://api.github.com/repos/{owner}/{name}",
            headers=headers, timeout=HTTP_TIMEOUT_S,
        )
        if r.status_code != 200:
            return EnableResult(
                repo=repo,
                before={},
                actions={"GET /repos": f"HTTP {r.status_code} — {r.text[:200]}"},
                ok=False,
            )
        before = r.json().get("security_and_analysis") or {}
    except requests.RequestException as e:
        return EnableResult(
            repo=repo,
            before={},
            actions={"GET /repos": f"ERROR: {e}"},
            ok=False,
        )

    all_ok = True

    # Step 2: PATCH security_and_analysis to enable dependabot_security_updates.
    if apply:
        try:
            r = requests.patch(
                f"https://api.github.com/repos/{owner}/{name}",
                headers=headers,
                json={
                    "security_and_analysis": {
                        "dependabot_security_updates": {"status": "enabled"},
                    }
                },
                timeout=HTTP_TIMEOUT_S,
            )
            actions["PATCH security_and_analysis.dependabot_security_updates"] = (
                f"HTTP {r.status_code}"
            )
            if r.status_code not in (200, 204):
                actions["PATCH security_and_analysis.dependabot_security_updates"] += (
                    f" — {r.text[:200]}"
                )
                all_ok = False
        except requests.RequestException as e:
            actions["PATCH security_and_analysis.dependabot_security_updates"] = (
                f"ERROR: {e}"
            )
            all_ok = False
    else:
        actions["PATCH security_and_analysis.dependabot_security_updates"] = (
            "DRY-RUN (would PATCH dependabot_security_updates.status=enabled)"
        )

    # Step 3: PUT /vulnerability-alerts (no body — toggle).
    if apply:
        try:
            r = requests.put(
                f"https://api.github.com/repos/{owner}/{name}/vulnerability-alerts",
                headers=headers, timeout=HTTP_TIMEOUT_S,
            )
            actions["PUT vulnerability-alerts"] = f"HTTP {r.status_code}"
            if r.status_code not in (204,):
                actions["PUT vulnerability-alerts"] += f" — {r.text[:200]}"
                all_ok = False
        except requests.RequestException as e:
            actions["PUT vulnerability-alerts"] = f"ERROR: {e}"
            all_ok = False
    else:
        actions["PUT vulnerability-alerts"] = "DRY-RUN (would PUT)"

    # Step 4: PUT /automated-security-fixes (no body — toggle).
    if apply:
        try:
            r = requests.put(
                f"https://api.github.com/repos/{owner}/{name}/automated-security-fixes",
                headers=headers, timeout=HTTP_TIMEOUT_S,
            )
            actions["PUT automated-security-fixes"] = f"HTTP {r.status_code}"
            if r.status_code not in (204,):
                actions["PUT automated-security-fixes"] += f" — {r.text[:200]}"
                all_ok = False
        except requests.RequestException as e:
            actions["PUT automated-security-fixes"] = f"ERROR: {e}"
            all_ok = False
    else:
        actions["PUT automated-security-fixes"] = "DRY-RUN (would PUT)"

    return EnableResult(repo=repo, before=before, actions=actions, ok=all_ok)


# ────────────────────────────────────────────────────────────────────
# Fleet enumeration
# ────────────────────────────────────────────────────────────────────


def list_fleet_repos(user: str = GITHUB_USER) -> list[str]:
    """List user-owned, non-fork, non-archive repos as 'owner/name' strings.

    Mirrors dependabot_review.py topology but does NOT filter to Poetry —
    Dependabot version-updates can target any ecosystem (pip, npm, docker,
    github-actions, cargo, etc.). Anything with `.github/dependabot.yml`
    on `main` is a valid target. We let the API tell us which actually
    have the yml; this function just enumerates the candidate set.
    """
    result = subprocess.run(
        ["gh", "repo", "list", user,
         "--limit", str(FLEET_REPO_LIMIT),
         "--json", "name,nameWithOwner,isArchived,isFork"],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        sys.exit(f"Failed to list fleet repos: {result.stderr}")
    repos = json.loads(result.stdout or "[]")
    return [
        r["nameWithOwner"] for r in repos
        if not r.get("isArchived") and not r.get("isFork")
    ]


# ────────────────────────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────────────────────────


def _format_result(r: EnableResult, apply: bool) -> str:
    """One-block summary per repo for human-readable output."""
    lines = [f"=== {r.repo} ==="]
    if r.before:
        current = r.before.get("dependabot_security_updates", {}).get("status", "unknown")
        lines.append(f"  Before: dependabot_security_updates = {current}")
    else:
        lines.append("  Before: (could not read state)")
    for endpoint, status in r.actions.items():
        lines.append(f"  {endpoint}: {status}")
    if not r.ok:
        lines.append("  >>> ERRORS encountered")
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Enable Dependabot on existing repos via REST API (#1331). "
                    "Per ADR-0216 — operator runs, not the agent.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--repo",
        metavar="OWNER/NAME",
        help="Single repo to enable (e.g., martymcenroe/dependabot-honeypot)",
    )
    group.add_argument(
        "--fleet",
        action="store_true",
        help="All user-owned non-fork non-archive repos (mirrors dependabot_review.py)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Mutate. Default: dry-run (reads state + reports what would change).",
    )
    parser.add_argument(
        "--user",
        default=GITHUB_USER,
        help=f"GitHub user for --fleet enumeration (default: {GITHUB_USER})",
    )
    args = parser.parse_args(argv)

    # Resolve targets.
    if args.repo:
        if "/" not in args.repo:
            print(f"ERROR: --repo expects OWNER/NAME format, got {args.repo!r}", file=sys.stderr)
            return 1
        targets = [args.repo]
    else:
        targets = list_fleet_repos(args.user)

    print(f"Targets: {len(targets)} repo(s)")
    if not args.apply:
        print("DRY-RUN MODE (no mutations will be made). Pass --apply to enable.")
    print()

    n_errored = 0
    with classic_pat_session() as pat:
        for target in targets:
            owner, name = target.split("/", 1)
            result = enable_dependabot_for_repo(owner, name, pat, args.apply)
            print(_format_result(result, args.apply))
            print()
            if not result.ok:
                n_errored += 1

    if n_errored:
        print(f"WARNING: {n_errored} of {len(targets)} repo(s) had errors")
        return 2
    if args.apply:
        print(f"Done. {len(targets)} repo(s) processed.")
    else:
        print(f"Dry-run complete. {len(targets)} repo(s) inspected. Re-run with --apply to mutate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
