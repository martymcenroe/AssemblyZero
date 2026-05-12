#!/usr/bin/env python3
"""Deploy the canonical auto-reviewer.yml workflow to repos missing it (#1128).

THIS SCRIPT MUST BE RUN BY THE USER, NOT BY AN AGENT.
Uses an in-process classic PAT (ADR-0216). The PAT carries `workflow`
scope so it can push `.github/workflows/*` via the Contents API --
fine-grained PATs intentionally lack that scope.

What this script does:

  1. Determines the canonical auto-reviewer.yml content. By default,
     reads it from the local AssemblyZero checkout (the one this
     script lives in -- AssemblyZero's own auto-reviewer.yml IS the
     canonical source since other repos call it as a reusable workflow
     via `uses: martymcenroe/AssemblyZero/.github/workflows/auto-reviewer.yml@main`).
     But wait -- each repo ALSO needs its own auto-reviewer.yml that
     calls the reusable one. That caller file is the CALLER pattern
     used by every other repo. We deploy THAT caller pattern.
  2. For each target repo, PUTs the caller file via Contents API to
     `.github/workflows/auto-reviewer.yml` on the default branch.
  3. Idempotent: skips repos that already have the file.

The canonical CALLER file is a 6-line YAML that invokes the AZ
reusable workflow on PR events:

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

    # Apply
    poetry run python tools/deploy_auto_reviewer_workflow.py \
        --repos comp-environ,gh-galaxy-quest --apply --confirm-yes

Issue: #1128 | Related: PR #1119 (#1118 dual-scope secrets), ADR-0216
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

            ok, err = put_workflow(repo, branch, None, pat)
            if ok:
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
