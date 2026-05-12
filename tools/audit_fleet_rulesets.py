#!/usr/bin/env python3
"""Fleet-wide repository-ruleset audit (Closes #905).

The companion to `audit_fleet_branch_protection.py`. That tool covers
*classic* branch protection; this one covers the newer *rulesets* API
surface. They are independent: a repo can have both, either, or neither.

#905 was filed 2026-04-09 after a batch config fix surfaced a 6.5x timing
spread in merge readiness across 5 repos. The today (2026-05-12)
three-iteration bootstrap saga (#1135 / #1137 / #1141) re-confirmed why
this audit is load-bearing: `comp-environ` had no rulesets and bootstrap
worked first try; `boostgauge` and `gh-galaxy-quest` each had an active
ruleset with a `pull_request` rule and `bypass_actors: []`, blocking the
direct-push bootstrap entirely until #1137 added ruleset bypass support.

Had this audit existed in April, the ruleset divergence would have been
visible BEFORE the deploy tool encountered it as a 409 in production.

What this script does:

  1. List all martymcenroe non-archived non-fork repos via `gh repo list`.
  2. For each repo, GET /repos/{owner}/{repo}/rulesets (gh CLI uses the
     user's fine-grained PAT -- read scope on rulesets is sufficient,
     no classic PAT needed).
  3. For each active branch-target ruleset, fetch full detail to
     extract: targeted refs, rule types present, bypass_actors count,
     whether the Repository admin role can bypass.
  4. Emit a TSV with one row per repo: ruleset count, IDs, main-target
     subset, rule type fingerprint, bypass actor metadata.
  5. Print a summary distinguishing repos that have rulesets blocking
     direct push to the default branch (i.e., where deploy tools must
     route through PRs OR use admin bypass).

The agent can run this safely -- no secret is unlocked.

Usage (from any AssemblyZero checkout):

    poetry run python tools/audit_fleet_rulesets.py
    poetry run python tools/audit_fleet_rulesets.py --limit 10
    poetry run python tools/audit_fleet_rulesets.py --output /tmp/rulesets.tsv
    poetry run python tools/audit_fleet_rulesets.py --repos boostgauge,gh-galaxy-quest

Issue: #905 | Companion: tools/audit_fleet_branch_protection.py
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

GITHUB_USER = "martymcenroe"
HTTP_TIMEOUT_S = 30
DEFAULT_OUTPUT = Path("audit_fleet_rulesets_results.tsv")
REPO_ADMIN_ROLE_ID = 5  # GitHub repository admin role (matches deploy_auto_reviewer_workflow.py)

# Rule types that, when present in a ruleset targeting the default branch,
# block direct push via Contents API. Used for the blocks_direct_push flag.
BLOCKING_RULE_TYPES = frozenset({
    "pull_request",
    "deletion",        # blocks branch deletion, not pushes -- but worth flagging
    "non_fast_forward",
    "required_signatures",
    "required_status_checks",
    "creation",
    "update",
})


@dataclass
class RulesetSummary:
    """One ruleset's relevant audit data."""
    rs_id: int
    name: str
    enforcement: str
    target: str
    targets_default_branch: bool
    rule_types: list[str]
    bypass_actor_count: int
    admin_role_bypass: bool

    def blocks_direct_push_to_default(self) -> bool:
        if not self.targets_default_branch:
            return False
        if self.enforcement != "active":
            return False
        return any(t in BLOCKING_RULE_TYPES for t in self.rule_types)


@dataclass
class RepoVerdict:
    name: str
    default_branch: str | None = None
    ruleset_count: int = 0
    rulesets: list[RulesetSummary] = field(default_factory=list)
    error: str | None = None

    @property
    def main_target_rulesets(self) -> list[RulesetSummary]:
        return [r for r in self.rulesets if r.targets_default_branch]

    @property
    def blocks_direct_push(self) -> bool:
        return any(r.blocks_direct_push_to_default() for r in self.rulesets)

    @property
    def can_admin_bypass(self) -> bool:
        """Across all default-branch-targeting active rulesets, is the
        Repository admin role a bypass actor? If yes, classic-PAT-as-owner
        can direct-push without ruleset modification."""
        return all(
            r.admin_role_bypass
            for r in self.rulesets
            if r.targets_default_branch and r.enforcement == "active"
        )

    def tsv_row(self) -> str:
        if self.error:
            return "\t".join([self.name, "", "ERROR", "", "", "", "", "", "", self.error])

        main_subset = self.main_target_rulesets
        rule_types: set[str] = set()
        bypass_count = 0
        for r in main_subset:
            rule_types.update(r.rule_types)
            bypass_count += r.bypass_actor_count

        ruleset_id_summary = ";".join(f"{r.rs_id}:{r.name}" for r in self.rulesets)
        main_target_ids = ";".join(str(r.rs_id) for r in main_subset)

        return "\t".join([
            self.name,
            self.default_branch or "",
            "yes" if self.blocks_direct_push else "no",
            "yes" if main_subset and self.can_admin_bypass else "no",
            str(self.ruleset_count),
            ruleset_id_summary,
            main_target_ids,
            ",".join(sorted(rule_types)),
            str(bypass_count),
            "",
        ])


TSV_HEADER = "\t".join([
    "repo",
    "default_branch",
    "blocks_direct_push_to_default",
    "admin_bypass_present",
    "ruleset_count",
    "ruleset_ids",
    "default_branch_target_ruleset_ids",
    "default_branch_rule_types",
    "default_branch_bypass_actor_count",
    "error",
])


def run_gh(args: list[str]) -> tuple[int, str, str]:
    """Wrapper for `gh ...`. Returns (returncode, stdout, stderr).

    Uses gh CLI's fine-grained PAT auth; read-only ruleset queries are
    permitted without the classic PAT. Bounded timeout per call.
    """
    try:
        result = subprocess.run(
            ["gh"] + args,
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", check=False, timeout=HTTP_TIMEOUT_S,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"gh timeout after {HTTP_TIMEOUT_S}s"
    except OSError as e:
        return 1, "", f"gh OSError: {e}"


def list_user_repos() -> list[dict]:
    rc, stdout, stderr = run_gh([
        "repo", "list", GITHUB_USER, "--limit", "200",
        "--json", "name,defaultBranchRef,isArchived,isFork",
    ])
    if rc != 0:
        sys.exit(f"gh repo list failed: {stderr.strip()[:300]}")
    return json.loads(stdout or "[]")


def list_ruleset_summaries(repo: str) -> tuple[list[dict], str | None]:
    """Returns (ruleset_summaries, error). Summaries are the list-endpoint
    shape (id, name, target, enforcement). The detail endpoint must be
    called separately for conditions / rules / bypass_actors."""
    rc, stdout, stderr = run_gh([
        "api", f"repos/{GITHUB_USER}/{repo}/rulesets",
        "--header", "Accept: application/vnd.github+json",
    ])
    if rc != 0:
        # 404 from this endpoint typically means "no rulesets" rather than
        # repo not found, but gh CLI surfaces both as exit 1. Distinguish
        # by stderr content.
        if "Not Found" in stderr or "404" in stderr:
            return [], None
        return [], f"gh rulesets list: {stderr.strip()[:200]}"
    try:
        data = json.loads(stdout or "[]")
    except json.JSONDecodeError as e:
        return [], f"parse rulesets: {e}"
    if not isinstance(data, list):
        return [], None
    return data, None


def get_ruleset_detail(repo: str, rs_id: int) -> tuple[dict | None, str | None]:
    rc, stdout, stderr = run_gh([
        "api", f"repos/{GITHUB_USER}/{repo}/rulesets/{rs_id}",
        "--header", "Accept: application/vnd.github+json",
    ])
    if rc != 0:
        return None, f"gh rulesets detail {rs_id}: {stderr.strip()[:200]}"
    try:
        return json.loads(stdout), None
    except json.JSONDecodeError as e:
        return None, f"parse detail {rs_id}: {e}"


def summarize_ruleset(detail: dict, default_branch: str | None) -> RulesetSummary:
    """Reduce a ruleset detail dict to the audit-relevant fields."""
    rs_id = int(detail.get("id", 0))
    name = str(detail.get("name", ""))
    enforcement = str(detail.get("enforcement", ""))
    target = str(detail.get("target", ""))

    # Determine if the ruleset targets the repo's default branch.
    ref_name = (detail.get("conditions") or {}).get("ref_name") or {}
    include = ref_name.get("include") or []
    targets_default = "~DEFAULT_BRANCH" in include or (
        default_branch is not None and f"refs/heads/{default_branch}" in include
    )

    rules = detail.get("rules") or []
    rule_types = [str(r.get("type", "")) for r in rules if r.get("type")]

    bypass_actors = detail.get("bypass_actors") or []
    bypass_count = len(bypass_actors)
    admin_bypass = any(
        a.get("actor_id") == REPO_ADMIN_ROLE_ID
        and a.get("actor_type") == "RepositoryRole"
        for a in bypass_actors
    )

    return RulesetSummary(
        rs_id=rs_id,
        name=name,
        enforcement=enforcement,
        target=target,
        targets_default_branch=targets_default,
        rule_types=rule_types,
        bypass_actor_count=bypass_count,
        admin_role_bypass=admin_bypass,
    )


def audit_one(repo_obj: dict) -> RepoVerdict:
    name = repo_obj.get("name", "")
    default = (repo_obj.get("defaultBranchRef") or {}).get("name")
    v = RepoVerdict(name=name, default_branch=default)

    summaries, err = list_ruleset_summaries(name)
    if err:
        v.error = err
        return v

    v.ruleset_count = len(summaries)
    for summary in summaries:
        rs_id = summary.get("id")
        if rs_id is None:
            continue
        detail, det_err = get_ruleset_detail(name, int(rs_id))
        if det_err:
            v.error = det_err
            return v
        if detail is None:
            continue
        v.rulesets.append(summarize_ruleset(detail, default))
    return v


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n")[0])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help=f"TSV output path (default: {DEFAULT_OUTPUT})")
    parser.add_argument("--limit", type=int, default=None,
                        help="Audit only first N repos (smoke test)")
    parser.add_argument("--repos", default=None,
                        help="Comma-separated repo names; overrides full discovery")
    args = parser.parse_args(argv)

    print("Listing repos via gh CLI (read-only)...")
    all_repos = list_user_repos()

    if args.repos:
        wanted = {r.strip() for r in args.repos.split(",") if r.strip()}
        repos = [r for r in all_repos if r["name"] in wanted]
    else:
        repos = [r for r in all_repos if not r.get("isArchived") and not r.get("isFork")]
        if args.limit:
            repos = repos[: args.limit]

    print(f"Auditing {len(repos)} repos for repository rulesets...\n")

    verdicts: list[RepoVerdict] = []
    for i, repo_obj in enumerate(repos, 1):
        v = audit_one(repo_obj)
        verdicts.append(v)
        if v.error:
            tag = f"ERROR ({v.error[:80]})"
        else:
            tag = (
                f"{v.ruleset_count} ruleset(s), "
                f"blocks_direct_push={'yes' if v.blocks_direct_push else 'no'}"
            )
        print(f"  [{i}/{len(repos)}] {v.name}: {tag}")

    args.output.write_text(
        TSV_HEADER + "\n" + "\n".join(v.tsv_row() for v in verdicts) + "\n",
        encoding="utf-8",
    )
    print(f"\nTSV written: {args.output.resolve()}")

    blocking = [v for v in verdicts if not v.error and v.blocks_direct_push]
    no_admin_bypass = [
        v for v in blocking
        if not v.can_admin_bypass
    ]

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Total audited: {len(verdicts)}")
    print(f"  With any ruleset: {sum(1 for v in verdicts if not v.error and v.ruleset_count > 0)}")
    print(f"  Blocks direct push to default branch: {len(blocking)}")
    print(f"    of those, no admin bypass: {len(no_admin_bypass)}")

    if no_admin_bypass:
        print("\nREPOS THAT WILL REQUIRE BOOTSTRAP for any direct-PUT deploy:")
        for v in no_admin_bypass:
            rule_summary = ",".join(sorted({
                t for rs in v.main_target_rulesets for t in rs.rule_types
            }))
            print(f"  - {v.name}: rules={rule_summary or '(none)'}")
    else:
        print("\nNo repos require ruleset bootstrap.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
