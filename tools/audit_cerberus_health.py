"""Fleet-wide read-only audit of Cerberus auth state per repo.

The Actions Secrets API never returns secret VALUES (by design), so direct
introspection of "which key is deployed where" is impossible. The only
signal is OBSERVATION: did the auto-reviewer workflow actually succeed at
the JWT exchange that requires the deployed key to match an active App key?

This tool reads recent Auto Review workflow runs across all user-owned
repos, filters out dependabot-branch runs (architecturally-failing,
unrelated to key health), and classifies each repo by the most recent
non-dependabot run's conclusion.

Use case: pre-rotation gate. Before revoking a Cerberus key on the App
page, run this audit. Any repo NOT marked HEALTHY needs investigation or
re-deploy first; otherwise the revoke silently breaks them.

Read-only. Uses gh CLI's fine-grained PAT for all calls. No classic PAT,
no pinentry, no secrets touched.

Issue: martymcenroe/AssemblyZero#1284
Related: unleashed#658 (architectural finding)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterable

GITHUB_USER = "martymcenroe"
WORKFLOW_FILE = ".github/workflows/auto-reviewer.yml"
DEFAULT_DAYS = 30
RUNS_PER_PAGE = 30


# Classifications
HEALTHY = "HEALTHY"
UNCERTAIN = "UNCERTAIN"
UNKNOWN = "UNKNOWN"
NOT_DEPLOYED = "NOT_DEPLOYED"


@dataclass
class RepoStatus:
    name: str
    classification: str
    detail: str = ""
    last_run_ts: str = ""

    def __str__(self) -> str:
        ts = f" {self.last_run_ts}" if self.last_run_ts else ""
        sep = " -- " if self.detail else ""
        return f"  {self.name}{sep}{self.detail}{ts}"


@dataclass
class AuditReport:
    by_classification: dict[str, list[RepoStatus]] = field(default_factory=lambda: {
        HEALTHY: [], UNCERTAIN: [], UNKNOWN: [], NOT_DEPLOYED: [],
    })

    def add(self, status: RepoStatus) -> None:
        self.by_classification.setdefault(status.classification, []).append(status)

    def count(self, classification: str) -> int:
        return len(self.by_classification.get(classification, []))


def _gh(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["gh", *args],
        capture_output=True, text=True, encoding="utf-8",
        errors="replace", check=check,
    )


def list_owned_repos() -> list[str]:
    """Return a sorted list of user-owned repo names."""
    r = _gh("repo", "list", GITHUB_USER, "--limit", "200",
            "--json", "name", "--jq", ".[].name", check=True)
    return sorted(n.strip() for n in r.stdout.strip().splitlines() if n.strip())


def auto_reviewer_yml_present(repo: str) -> bool:
    """Return True iff .github/workflows/auto-reviewer.yml exists on origin."""
    r = _gh("api", f"/repos/{GITHUB_USER}/{repo}/contents/{WORKFLOW_FILE}",
            "--silent", check=False)
    return r.returncode == 0


def recent_auto_review_runs(repo: str) -> list[dict]:
    """Return the recent Auto Review workflow runs for a repo, most-recent-first.

    Returns an empty list if the workflow doesn't exist or returns an error.
    """
    r = _gh("api",
            f"/repos/{GITHUB_USER}/{repo}/actions/runs",
            "-X", "GET",
            "-f", f"per_page={RUNS_PER_PAGE}",
            check=False)
    if r.returncode != 0:
        return []
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        return []
    runs = data.get("workflow_runs", [])
    # Filter to the Auto Review workflow (matches by workflow name or path)
    return [
        run for run in runs
        if run.get("name") == "Auto Review"
        or run.get("path", "").endswith("/auto-reviewer.yml")
    ]


def is_dependabot_run(run: dict) -> bool:
    """Return True if the run was triggered by dependabot.

    Dependabot Auto Review runs were architecturally-failing pre-#1131; post
    they don't fire at all. Either way, they're not signal about key health.
    """
    actor = (run.get("actor") or {}).get("login", "")
    if actor.startswith("dependabot"):
        return True
    branch = run.get("head_branch", "") or ""
    return branch.startswith("dependabot/")


def parse_iso(ts: str) -> datetime | None:
    """Parse an ISO-8601 timestamp; return None on parse failure."""
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def classify(repo: str, runs: list[dict], days: int) -> RepoStatus:
    """Classify a repo by its most recent non-dependabot Auto Review run.

    Pure function -- given runs list, returns a RepoStatus. Tested directly.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    relevant: list[dict] = []
    for run in runs:
        if is_dependabot_run(run):
            continue
        ts = parse_iso(run.get("created_at", ""))
        if ts is None or ts < cutoff:
            continue
        relevant.append(run)

    if not relevant:
        return RepoStatus(
            repo, UNKNOWN,
            detail=f"no non-dependabot Auto Review runs in the last {days} days",
        )

    # Most recent first
    relevant.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    latest = relevant[0]
    conclusion = latest.get("conclusion") or "(in_progress)"
    created = latest.get("created_at", "")

    if conclusion == "success":
        return RepoStatus(repo, HEALTHY, detail="success", last_run_ts=created)
    if conclusion == "startup_failure":
        return RepoStatus(
            repo, UNCERTAIN,
            detail="startup_failure (likely Mode A old caller format)",
            last_run_ts=created,
        )
    if conclusion == "failure":
        return RepoStatus(
            repo, UNCERTAIN,
            detail="failure (investigate -- may be revoked key or other issue)",
            last_run_ts=created,
        )
    return RepoStatus(
        repo, UNCERTAIN, detail=f"conclusion={conclusion}", last_run_ts=created,
    )


def audit_repos(
    repos: Iterable[str], days: int, include_not_deployed: bool,
) -> AuditReport:
    report = AuditReport()
    for repo in repos:
        if not auto_reviewer_yml_present(repo):
            if include_not_deployed:
                report.add(RepoStatus(repo, NOT_DEPLOYED))
            continue
        runs = recent_auto_review_runs(repo)
        report.add(classify(repo, runs, days))
    return report


def print_report(report: AuditReport, days: int) -> None:
    """Render the audit report to stdout."""
    print("Cerberus health audit -- read-only "
          "(no PRs opened, no secrets touched)")
    print("=" * 70)

    total = sum(report.count(c) for c in (HEALTHY, UNCERTAIN, UNKNOWN))
    print(f"Repos audited (with auto-reviewer.yml): {total}")
    if report.count(NOT_DEPLOYED):
        print(f"Repos without auto-reviewer.yml (skipped unless --include-not-deployed): "
              f"{report.count(NOT_DEPLOYED)}")
    print()

    for cls in (HEALTHY, UNCERTAIN, UNKNOWN, NOT_DEPLOYED):
        statuses = report.by_classification.get(cls, [])
        if not statuses:
            continue
        statuses.sort(key=lambda s: s.name.lower())
        print(f"{cls} ({len(statuses)}):")
        for s in statuses:
            print(s)
        print()

    print("=" * 70)
    print("Rotation pre-check guidance:")
    print(f"  HEALTHY ({report.count(HEALTHY)}): safe to rotate -- the deployed key "
          "authenticates against an active App key today")
    print(f"  UNCERTAIN ({report.count(UNCERTAIN)}): already broken or otherwise "
          "non-passing; investigate before relying on these repos for any "
          "rotation-safety claim")
    print(f"  UNKNOWN ({report.count(UNKNOWN)}): no recent observation; "
          "trigger a synthetic PR (separate tool) to verify before rotation")
    if report.count(NOT_DEPLOYED) and report.count(NOT_DEPLOYED) > 0:
        print(f"  NOT_DEPLOYED ({report.count(NOT_DEPLOYED)}): no auto-reviewer.yml; "
              "out of scope for Cerberus key rotation")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only fleet audit of Cerberus auth state per repo. Classifies "
            "each user-owned repo as HEALTHY / UNCERTAIN / UNKNOWN / NOT_DEPLOYED "
            "based on the most recent non-dependabot Auto Review workflow run."
        ),
    )
    parser.add_argument(
        "--repo", default=None,
        help="Scan a single repo by name (no owner prefix). Default: all owned repos.",
    )
    parser.add_argument(
        "--days", type=int, default=DEFAULT_DAYS,
        help=f"Window for 'recent' runs (default {DEFAULT_DAYS}).",
    )
    parser.add_argument(
        "--include-not-deployed", action="store_true",
        help="Include repos without auto-reviewer.yml in the output.",
    )
    args = parser.parse_args(argv)

    repos = [args.repo] if args.repo else list_owned_repos()
    print(f"Scanning {len(repos)} repo(s)...\n", file=sys.stderr)
    report = audit_repos(repos, args.days, args.include_not_deployed)
    print_report(report, args.days)

    # Exit 0 iff no UNCERTAIN (HEALTHY + UNKNOWN are not failures for audit
    # purposes; UNKNOWN just means "haven't verified yet"). Exit 1 surfaces
    # the presence of UNCERTAIN repos in CI/scripted contexts.
    return 1 if report.count(UNCERTAIN) > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
