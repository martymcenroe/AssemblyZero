#!/usr/bin/env python3
"""Fleet-wide branch-protection audit (Issue #1124).

THIS SCRIPT MUST BE RUN BY THE USER, NOT BY AN AGENT.
It uses an in-process classic PAT (ADR-0216). The PAT is decrypted into
the Python process heap; an agent-spawned subprocess would have
theoretical heap-read access.

Surfaced 2026-05-11 by the boostgauge agent: three repos (`boostgauge`,
`patent-general`, `gh-galaxy-quest`) have rulesets with
`required_approving_review_count: 0`, contradicting the root CLAUDE.md
fleet-wide guarantee. All three were created BEFORE the
`new_repo_setup.py` count=0 -> count=1 fix in April 2026, so they got
the buggy weak-protection template. `tools/fix_branch_protections.py`
only handles the NO-protection case, not the WEAK case, so they sit
unfixed.

What this script does:

  1. Lists all martymcenroe repos via /user/repos (read-only;
     fine-grained PAT scope is sufficient for the listing -- we use the
     classic PAT for everything to keep the heap-residency story
     consistent within one `with` block).
  2. For each non-archived repo with a default branch, GETs:
       /repos/{owner}/{repo}/branches/{default}/protection   (legacy)
       /repos/{owner}/{repo}/rulesets                          (newer)
     The classic PAT has the admin scope needed to read the legacy
     protection endpoint; the fine-grained PAT cannot.
  3. Classifies each repo:
       STRICT       all four bars met (>=1 approval, status checks,
                    enforce_admins, no force pushes, protected=true)
       WEAK         protected=true but at least one bar fails
       UNPROTECTED  protected=false OR 404 on the protection endpoint
       UNKNOWN      could not determine (network error etc.)
  4. Writes a TSV with one row per repo to a local file.
  5. Prints a summary of every repo that fails the policy bar so the
     operator can decide remediation scope.

Usage (run from inside an AssemblyZero checkout):

    poetry run python tools/audit_fleet_branch_protection.py
    poetry run python tools/audit_fleet_branch_protection.py --limit 10        # smoke test
    poetry run python tools/audit_fleet_branch_protection.py --output X.tsv    # custom path
    poetry run python tools/audit_fleet_branch_protection.py --repos a,b,c     # subset

Output goes to `audit_fleet_branch_protection_results.tsv` in the cwd
by default. The agent can read that file to plan remediation; the PAT
never leaves the script's process.

Issue: #1124 | Related: ADR-0216 (in-process classic PAT)
"""

from __future__ import annotations

import argparse
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
DEFAULT_OUTPUT = Path("audit_fleet_branch_protection_results.tsv")

# Policy bar -- what STRICT means. A repo failing any of these is WEAK.
REQUIRED_REVIEWS_MIN = 1
REQUIRE_STATUS_CHECKS = True
REQUIRE_ENFORCE_ADMINS = True
ALLOW_FORCE_PUSHES_MAX = False


@dataclass
class RepoVerdict:
    name: str
    default_branch: str | None = None
    protected_flag: bool | None = None
    required_reviews: int | None = None
    has_status_checks: bool | None = None
    enforce_admins: bool | None = None
    allow_force_pushes: bool | None = None
    ruleset_count: int | None = None
    classification: str = "UNKNOWN"
    failures: list[str] = field(default_factory=list)
    error: str | None = None

    def tsv_row(self) -> str:
        cols = [
            self.name,
            self.classification,
            self.default_branch or "",
            "" if self.protected_flag is None else str(self.protected_flag),
            "" if self.required_reviews is None else str(self.required_reviews),
            "" if self.has_status_checks is None else str(self.has_status_checks),
            "" if self.enforce_admins is None else str(self.enforce_admins),
            "" if self.allow_force_pushes is None else str(self.allow_force_pushes),
            "" if self.ruleset_count is None else str(self.ruleset_count),
            ",".join(self.failures),
            self.error or "",
        ]
        return "\t".join(cols)


TSV_HEADER = "\t".join([
    "repo", "classification", "default_branch", "protected_flag",
    "required_reviews", "has_status_checks", "enforce_admins",
    "allow_force_pushes", "ruleset_count", "failed_bars", "error",
])


def list_repos() -> list[dict]:
    """List all martymcenroe repos via gh CLI. Read-only; fine-grained PAT OK.

    We don't use the classic PAT for the listing -- the listing is publicly
    visible info (repo names) that doesn't need elevated scope. Keeping the
    classic-PAT exposure narrow is the spirit of ADR-0216.
    """
    result = subprocess.run(
        ["gh", "repo", "list", GITHUB_USER, "--limit", "200",
         "--json", "name,defaultBranchRef,isArchived,isFork"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        check=False, timeout=60,
    )
    if result.returncode != 0:
        sys.exit(f"gh repo list failed: {result.stderr.strip()[:300]}")
    import json
    data = json.loads(result.stdout or "[]")
    return data


def _get(url: str, pat: str) -> tuple[int, dict | None]:
    """GET helper. Returns (status_code, json_or_none). Never raises."""
    headers = {
        "Authorization": f"token {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        r = requests.get(url, headers=headers, timeout=HTTP_TIMEOUT_S)
    except requests.RequestException as e:
        return 0, {"_error": str(e)}
    try:
        body = r.json() if r.text else None
    except ValueError:
        body = None
    return r.status_code, body


def classify(verdict: RepoVerdict) -> None:
    """Mutate verdict.classification + verdict.failures in place."""
    if verdict.error:
        verdict.classification = "UNKNOWN"
        return

    if verdict.protected_flag is False:
        verdict.classification = "UNPROTECTED"
        verdict.failures.append("protected_flag=false")
        return

    failures: list[str] = []
    if verdict.required_reviews is None or verdict.required_reviews < REQUIRED_REVIEWS_MIN:
        failures.append(
            f"required_reviews={verdict.required_reviews} < {REQUIRED_REVIEWS_MIN}"
        )
    if REQUIRE_STATUS_CHECKS and not verdict.has_status_checks:
        failures.append("no_required_status_checks")
    if REQUIRE_ENFORCE_ADMINS and not verdict.enforce_admins:
        failures.append("enforce_admins=false")
    if verdict.allow_force_pushes:
        failures.append("allow_force_pushes=true")

    verdict.failures = failures
    verdict.classification = "WEAK" if failures else "STRICT"


def audit_one_repo(repo_obj: dict, pat: str) -> RepoVerdict:
    name = repo_obj["name"]
    default = (repo_obj.get("defaultBranchRef") or {}).get("name")
    v = RepoVerdict(name=name, default_branch=default)

    if not default:
        v.error = "no_default_branch"
        v.classification = "UNKNOWN"
        return v

    # Legacy branch-protection endpoint -- needs classic PAT admin scope
    code, body = _get(
        f"{GH_API}/repos/{GITHUB_USER}/{name}/branches/{default}/protection", pat,
    )
    if code == 404:
        # Either no protection set OR our PAT can't see it. The /branches/{default}
        # endpoint's "protected" flag (queried separately) tells us which.
        prot_code, prot_body = _get(
            f"{GH_API}/repos/{GITHUB_USER}/{name}/branches/{default}", pat,
        )
        if prot_code == 200 and isinstance(prot_body, dict):
            v.protected_flag = prot_body.get("protected", False)
        classify(v)
        return v
    if code == 0:
        v.error = "network_error"
        classify(v)
        return v
    if code >= 300 or not isinstance(body, dict):
        v.error = f"protection GET returned {code}"
        classify(v)
        return v

    v.protected_flag = True
    rpr = body.get("required_pull_request_reviews") or {}
    v.required_reviews = rpr.get("required_approving_review_count", 0)
    rsc = body.get("required_status_checks") or {}
    v.has_status_checks = bool(
        (rsc.get("contexts") or []) or (rsc.get("checks") or [])
    )
    enforce = body.get("enforce_admins") or {}
    v.enforce_admins = bool(enforce.get("enabled")) if isinstance(enforce, dict) else False
    afp = body.get("allow_force_pushes") or {}
    v.allow_force_pushes = bool(afp.get("enabled")) if isinstance(afp, dict) else False

    # Cross-reference rulesets count (newer overlay)
    rs_code, rs_body = _get(f"{GH_API}/repos/{GITHUB_USER}/{name}/rulesets", pat)
    if rs_code == 200 and isinstance(rs_body, list):
        v.ruleset_count = len(rs_body)
    elif rs_code == 200 and isinstance(rs_body, dict):
        v.ruleset_count = len(rs_body.get("rulesets", []))

    classify(v)
    return v


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n")[0])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help=f"TSV output path (default: {DEFAULT_OUTPUT})")
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
        missing = names - {r["name"] for r in repos}
        if missing:
            print(f"WARNING: requested repos not found: {sorted(missing)}", file=sys.stderr)
    else:
        # Skip archived + forks by default; the policy doesn't apply to them.
        repos = [
            r for r in all_repos
            if not r.get("isArchived") and not r.get("isFork")
        ]
        if args.limit:
            repos = repos[: args.limit]

    print(f"Auditing {len(repos)} repos...\n")

    verdicts: list[RepoVerdict] = []
    with classic_pat_session() as pat:
        for i, repo_obj in enumerate(repos, 1):
            v = audit_one_repo(repo_obj, pat)
            verdicts.append(v)
            print(f"  [{i}/{len(repos)}] {v.name}: {v.classification}"
                  + (f"  ({', '.join(v.failures)})" if v.failures else "")
                  + (f"  ERROR: {v.error}" if v.error else ""))

    # Write TSV
    args.output.write_text(
        TSV_HEADER + "\n" + "\n".join(v.tsv_row() for v in verdicts) + "\n",
        encoding="utf-8",
    )
    print(f"\nTSV written: {args.output.resolve()}")

    # Summary
    by_class: dict[str, list[RepoVerdict]] = {}
    for v in verdicts:
        by_class.setdefault(v.classification, []).append(v)
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for cls in ("STRICT", "WEAK", "UNPROTECTED", "UNKNOWN"):
        count = len(by_class.get(cls, []))
        print(f"  {cls}: {count}")
    print()

    failing = [v for v in verdicts if v.classification in ("WEAK", "UNPROTECTED")]
    if failing:
        print("REPOS FAILING THE POLICY BAR:")
        for v in failing:
            failures = ", ".join(v.failures) if v.failures else v.error or "no detail"
            print(f"  - {v.name} [{v.classification}]: {failures}")
        return 2  # non-zero exit so a CI / scheduled run notices

    print("All audited repos pass the policy bar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
