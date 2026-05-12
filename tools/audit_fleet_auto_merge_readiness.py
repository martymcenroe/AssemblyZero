#!/usr/bin/env python3
"""Comprehensive fleet audit: is each repo ready for PRs to auto-merge?

THIS SCRIPT MUST BE RUN BY THE USER, NOT BY AN AGENT.
Uses an in-process classic PAT (ADR-0216).

A repo is auto-merge-ready iff ALL FOUR are true:

  1. Branch protection is strict
       (>=1 review, status checks required, enforce_admins, no force pushes)
  2. .github/workflows/auto-reviewer.yml exists on the default branch
  3. Actions secrets contain REVIEWER_APP_ID + REVIEWER_APP_PRIVATE_KEY
  4. Dependabot secrets contain REVIEWER_APP_ID + REVIEWER_APP_PRIVATE_KEY

#1124 audited dimension 1. #1118 added dimension 4. This script checks
all four and reports per-repo readiness.

Output:
  - audit_fleet_auto_merge_readiness_results.tsv (one row per repo)
  - Summary printed listing every NOT_READY repo with the failing dims

Issue: #1128 | Related: #1124 (protection audit), #1118 (dependabot scope)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pat_session import classic_pat_session  # noqa: E402

GITHUB_USER = "martymcenroe"
GH_API = "https://api.github.com"
HTTP_TIMEOUT_S = 30
WORKFLOW_PATH = ".github/workflows/auto-reviewer.yml"
REQUIRED_SECRETS = {"REVIEWER_APP_ID", "REVIEWER_APP_PRIVATE_KEY"}
DEFAULT_OUTPUT = Path("audit_fleet_auto_merge_readiness_results.tsv")


@dataclass
class RepoReadiness:
    name: str
    default_branch: str | None = None
    protection_strict: bool | None = None
    workflow_present: bool | None = None
    actions_secrets_complete: bool | None = None
    dependabot_secrets_complete: bool | None = None
    failures: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def verdict(self) -> str:
        if self.error:
            return "UNKNOWN"
        if self.failures:
            return "NOT_READY"
        return "READY"

    def tsv_row(self) -> str:
        return "\t".join([
            self.name,
            self.verdict,
            self.default_branch or "",
            _b(self.protection_strict),
            _b(self.workflow_present),
            _b(self.actions_secrets_complete),
            _b(self.dependabot_secrets_complete),
            ",".join(self.failures),
            self.error or "",
        ])


def _b(v: bool | None) -> str:
    return "" if v is None else str(v)


TSV_HEADER = "\t".join([
    "repo", "verdict", "default_branch",
    "protection_strict", "workflow_present",
    "actions_secrets_complete", "dependabot_secrets_complete",
    "failures", "error",
])


def _headers(pat: str) -> dict[str, str]:
    return {
        "Authorization": f"token {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _api_get(url: str, pat: str) -> tuple[int, dict | list | None]:
    try:
        r = requests.get(url, headers=_headers(pat), timeout=HTTP_TIMEOUT_S)
    except requests.RequestException as e:
        return 0, {"_error": str(e)}
    try:
        body = r.json() if r.text else None
    except ValueError:
        body = None
    return r.status_code, body


def list_repos() -> list[dict]:
    """List martymcenroe repos via gh CLI (read-only; fine-grained PAT OK)."""
    result = subprocess.run(
        ["gh", "repo", "list", GITHUB_USER, "--limit", "200",
         "--json", "name,defaultBranchRef,isArchived,isFork"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        check=False, timeout=60,
    )
    if result.returncode != 0:
        sys.exit(f"gh repo list failed: {result.stderr.strip()[:300]}")
    return json.loads(result.stdout or "[]")


def check_protection(repo: str, default: str, pat: str) -> tuple[bool | None, str | None]:
    """Return (is_strict, error). is_strict=None on error."""
    code, body = _api_get(
        f"{GH_API}/repos/{GITHUB_USER}/{repo}/branches/{default}/protection", pat,
    )
    if code == 404:
        return False, None  # unprotected
    if code == 0 or not isinstance(body, dict):
        return None, f"protection GET {code}"
    if code >= 300:
        return None, f"protection GET {code}"

    rpr = body.get("required_pull_request_reviews") or {}
    rsc = body.get("required_status_checks") or {}
    enforce = body.get("enforce_admins") or {}
    afp = body.get("allow_force_pushes") or {}

    reviews_ok = rpr.get("required_approving_review_count", 0) >= 1
    checks_ok = bool((rsc.get("contexts") or []) or (rsc.get("checks") or []))
    enforce_ok = bool(enforce.get("enabled")) if isinstance(enforce, dict) else False
    no_force = not (bool(afp.get("enabled")) if isinstance(afp, dict) else False)

    return (reviews_ok and checks_ok and enforce_ok and no_force), None


def check_workflow(repo: str, default: str, pat: str) -> tuple[bool | None, str | None]:
    """Return (workflow_present, error). Checks default-branch HEAD."""
    code, body = _api_get(
        f"{GH_API}/repos/{GITHUB_USER}/{repo}/contents/{WORKFLOW_PATH}?ref={default}", pat,
    )
    if code == 404:
        return False, None
    if code == 200:
        return True, None
    return None, f"workflow GET {code}"


def check_secrets(repo: str, scope: str, pat: str) -> tuple[bool | None, str | None]:
    """scope: 'actions' or 'dependabot'. Returns (all_present, error)."""
    code, body = _api_get(
        f"{GH_API}/repos/{GITHUB_USER}/{repo}/{scope}/secrets", pat,
    )
    if code != 200 or not isinstance(body, dict):
        return None, f"{scope}/secrets GET {code}"
    present = {s["name"] for s in body.get("secrets", [])}
    return REQUIRED_SECRETS.issubset(present), None


def audit_one(repo_obj: dict, pat: str) -> RepoReadiness:
    name = repo_obj["name"]
    default = (repo_obj.get("defaultBranchRef") or {}).get("name")
    r = RepoReadiness(name=name, default_branch=default)

    if not default:
        r.error = "no_default_branch"
        return r

    # 1. Branch protection
    is_strict, err = check_protection(name, default, pat)
    r.protection_strict = is_strict
    if err:
        r.error = err
        return r
    if not is_strict:
        r.failures.append("branch_protection_not_strict")

    # 2. Workflow file
    has_wf, err = check_workflow(name, default, pat)
    r.workflow_present = has_wf
    if err:
        r.error = err
        return r
    if not has_wf:
        r.failures.append("auto_reviewer_yml_missing")

    # 3. Actions secrets
    has_act, err = check_secrets(name, "actions", pat)
    r.actions_secrets_complete = has_act
    if err:
        r.error = err
        return r
    if not has_act:
        r.failures.append("actions_secrets_incomplete")

    # 4. Dependabot secrets
    has_dep, err = check_secrets(name, "dependabot", pat)
    r.dependabot_secrets_complete = has_dep
    if err:
        r.error = err
        return r
    if not has_dep:
        r.failures.append("dependabot_secrets_incomplete")

    return r


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n")[0])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=None,
                        help="Audit only the first N repos (smoke test)")
    parser.add_argument("--repos", default=None,
                        help="Comma-separated repo names; overrides full discovery")
    args = parser.parse_args(argv)

    print("Listing repos via gh CLI (read-only)...")
    all_repos = list_repos()

    if args.repos:
        names = {r.strip() for r in args.repos.split(",") if r.strip()}
        repos = [r for r in all_repos if r["name"] in names]
    else:
        repos = [r for r in all_repos if not r.get("isArchived") and not r.get("isFork")]
        if args.limit:
            repos = repos[: args.limit]

    print(f"Auditing {len(repos)} repos across 4 dimensions...\n")

    results: list[RepoReadiness] = []
    with classic_pat_session() as pat:
        for i, repo_obj in enumerate(repos, 1):
            r = audit_one(repo_obj, pat)
            results.append(r)
            tag = r.verdict
            extra = (f" -- {', '.join(r.failures)}" if r.failures else "")
            err = (f" ERROR: {r.error}" if r.error else "")
            print(f"  [{i}/{len(repos)}] {r.name}: {tag}{extra}{err}")

    args.output.write_text(
        TSV_HEADER + "\n" + "\n".join(r.tsv_row() for r in results) + "\n",
        encoding="utf-8",
    )
    print(f"\nTSV written: {args.output.resolve()}")

    by_verdict: dict[str, list[RepoReadiness]] = {}
    for r in results:
        by_verdict.setdefault(r.verdict, []).append(r)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for v in ("READY", "NOT_READY", "UNKNOWN"):
        count = len(by_verdict.get(v, []))
        print(f"  {v}: {count}")

    not_ready = by_verdict.get("NOT_READY", [])
    if not_ready:
        print("\nREPOS NOT READY FOR AUTO-MERGE:")
        for r in not_ready:
            print(f"  - {r.name}: {', '.join(r.failures)}")
        return 2

    print("\nAll audited repos ready for auto-merge.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
