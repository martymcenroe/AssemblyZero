# 0854 - PAT Migration Status (ADR-0216 fleet-wide audit)

**Auditor:** Claude Opus 4.7 (1M context)
**Date:** 2026-05-23
**Scope:** `tools/*.py` in `martymcenroe/AssemblyZero` (80 Python files)
**Trigger:** AZ #1204 (fleet-wide audit; identify pre-ADR-0216 holdouts)

## Methodology

Per #1204 methodology (semantic, not syntactic):

1. **Find current migrators.** `grep -l "from _pat_session import\|import _pat_session" tools/` → 18 files import the canonical pattern → MIGRATED.
2. **Find suspicious legacy auth patterns.** `grep -E "gh auth login|env GH_TOKEN|os\.environ\[\"GH_TOKEN\"\]"` on `tools/`. Hits inspected one by one to distinguish:
   - Docstring text describing how to RECOVER from a fine-grained failure ≠ actual use (e.g., `new_repo_setup.py` § "Push failed. Preferred recovery — env-scoped classic PAT")
   - Error-message text suggesting the operator run `gh auth login` ≠ the script swapping auth itself
   - Actual `subprocess.run(["gh", "auth", "login"...])` swap or invocation depending on classic-PAT in env — these are real legacy uses
3. **Find tools doing privileged operations without `_pat_session`.** Greppable endpoints: `/branches/*/protection`, `/rulesets`, `/repos/*/contents/.github/workflows/`, `/repos/{O}/{R}` (PATCH), `/actions/secrets/*`. Cross-reference with the `_pat_session` importer list.
4. **Classify** each tool into MIGRATED / NEEDS_MIGRATION / N/A / LEGACY_RETAINED.

## Results

### MIGRATED (18 tools — all importers of `tools/_pat_session`)

| Tool | Privileged operation |
|---|---|
| `_pat_session.py` | (the module itself) |
| `audit_fleet_auto_merge_readiness.py` | branch protection + workflow checks |
| `audit_fleet_branch_protection.py` | branch protection inspection (read but via classic for full visibility) |
| `deploy_auto_reviewer_workflow.py` | workflow file PUT (this tool is up for deletion per #1193 consolidation) |
| `deploy_boostgauge_landing_workflow.py` | workflow file PUT |
| `deploy_boostgauge_release_yml.py` | workflow file PUT |
| `deploy_cerberus_secrets.py` | Actions secrets PUT |
| `fleet_delete_pr_sentinel.py` | workflow file DELETE via PR |
| `fleet_set_delete_branch_on_merge.py` | repo settings PATCH |
| `fleet_set_permission_mode.py` | repo settings PATCH |
| `land_1104_auto_reviewer_fix.py` | workflow file edit via PR |
| `land_1131_auto_reviewer_skip_dependabot.py` | workflow file edit via PR |
| `merge_aletheia_603_audit_gate.py` | PR merge with classic-PAT-required path |
| `new_repo_setup.py` | repo create + workflow PUT + branch protection (mixed) |
| `remediate_fleet_branch_protection.py` | branch protection PUT |
| `remediate_patent_general_protection.py` | ruleset DELETE + branch protection PUT |
| `sentinel_migrate.py` | workflow file PUT |
| `update_clio_repo_metadata.py` | repo settings PATCH |
| `upgrade_boostgauge_auto_reviewer.py` | workflow file PUT via PR |

### NEEDS_MIGRATION (3 tools)

| Tool | Operation | Current auth | Tracked as |
|---|---|---|---|
| `deploy_auto_reviewer_fleet.py` | workflow file PUT across fleet | `gh auth login` classic-PAT swap | **#1193** (consolidation — extend `--repos` flag, migrate auth) |
| `push_workflow_fixes.py` | workflow file PUT (and repo settings) across multiple repos | `gh auth login` classic-PAT swap with interactive y/N | **#1236** |
| `fix_branch_protections.py` | branch protection PUT/PATCH/DELETE | `gh auth login` classic-PAT swap; uses internal `gh_api(method, endpoint, *args)` helper | **#1237** |

### LEGACY_RETAINED (1 tool)

| Tool | Reason |
|---|---|
| `merge_sentinel_permissions_prs.py` | Per root CLAUDE.md (under § "Merging PRs (Universal)"): "The deprecated `merge_sentinel_permissions_prs.py` (gh-CLI auth swap, v1) MUST NOT be used as a template for new tools. For elevated-scope landings use the in-process classic-PAT pattern." Intentionally kept as a break-glass / historical reference; documented as deprecated. |

### N/A (~58 tools — read-only, local-only, or fine-grained-PAT-sufficient)

Categories of N/A tools (not enumerated row-by-row to keep the report scannable):

- **Modules** (importable, not CLI tools): `_gate.py`, `_gh_retry.py`, `assemblyzero_config.py`, `assemblyzero_credentials.py`
- **Local-only file/git operations**: `append_session_log.py`, `archive_worktree_lineage.py`, `clean_transcript.py`, `consolidate_logs.py`, `repo_drift_check.py`, `speedrun_*.py` (3), `transcript_filters.py`, `update-doc-refs.py`
- **Read-only audits** (no mutation, can use fine-grained PAT): `audit_deferred_scope.py`, `audit_fleet_rulesets.py`, `audit_schedule_check.py`, `audit_tracked_log_writers.py`, `github_protection_audit.py`, `view_audit.py`, `validate_skill.py`, `verdict-analyzer.py`
- **Issue/PR/label/comment operations** (fine-grained-PAT scoped): `backfill_assemblyzero_flag.py`, `backfill_canonical_labels.py`, `backfill_issue_audit.py`, `backfill_telemetry.py`, `dependabot_morning_status.py`, `dependabot_review.py`, `merge_sentinel_permissions_prs.py` (listed above as LEGACY_RETAINED for its swap pattern, but its mutation surface is PR merge which fine-grained can do)
- **Hook/permissions deployment** (local file CRUD): `batch_cleanup_quality_hooks.py`, `batch_cleanup_security_hooks.py`, `batch_deploy_hooks.py`, `assemblyzero-permissions.py`
- **Generate/harvest/analytics scripts**: `assemblyzero-generate.py`, `assemblyzero-harvest.py`, `claude_usage_compute.py`, `claude-usage-scraper.py`, `collect_cross_project_metrics.py` (and `-` variant), `mine_quality_patterns.py`, `mine_verdict_patterns.py`, `model_scorecard.py`, `rebuild_knowledge_base.py`
- **Gemini-side tools** (not GitHub-API): `gemini-retry.py`, `gemini-rotate.py`, `gemini-test-credentials.py`, `gemini-test-credentials-v2.py`
- **Workflow orchestration** (Claude-side, local): `orchestrate.py`, `run_audit.py`, `run_implement_from_lld.py`, `run_implementation_spec_workflow.py`, `run_janitor_workflow.py`, `run_requirements_workflow.py`, `run_scout_workflow.py`
- **Misc local**: `modernize_dependencies.py`, `test-gate.py` (test artifact)

### Borderline cases worth verification (1 tool)

| Tool | Concern |
|---|---|
| `enable_wikis.py` | `subprocess.run(["gh", "api", "-X", "PATCH", f"/repos/{user}/{repo}", "-F", "has_wiki=true"])` is a repo settings PATCH. Per standard 0017 § 1, repo settings PATCH requires `Administration: write` which fine-grained PATs typically lack. Docstring claims "fine-grained PAT is fine" — could be true if the user's fine-grained PAT happens to have Administration scope on personal repos, or if `has_wiki` toggles at a different permission tier than `delete_branch_on_merge`. Tracked at **#1238**. |

### Known-tracked migration (1 tool — for completeness)

| Tool | Status |
|---|---|
| `test_governance_system.py` | Already tracked via #965 (open) — "refactor: migrate test_governance_system.py audit mode to in-process PAT pattern". Not duplicated. |

## Summary

| Category | Count |
|---|---|
| MIGRATED | 18 |
| NEEDS_MIGRATION (actively non-conformant) | 3 |
| LEGACY_RETAINED | 1 |
| N/A | ~58 |
| Borderline (verification needed) | 1 |
| Known-tracked open migration | 1 |
| **Total `tools/*.py` files** | **80** (≈ 18 + 3 + 1 + 58 = 80) |

## Issues filed

Per #1204 "file follow-up issues for each NEEDS_MIGRATION (except `deploy_auto_reviewer_fleet.py` tracked under #1193)":

- **`push_workflow_fixes.py`** → #1236
- **`fix_branch_protections.py`** → #1237
- **`enable_wikis.py`** (borderline verification) → #1238

## Re-execution

```bash
# 1. Find current migrators
grep -lE "from _pat_session import|import _pat_session" tools/*.py

# 2. Find suspicious legacy auth strings (inspect each hit semantically)
grep -nE "gh auth login|env GH_TOKEN|os\.environ\[\"GH_TOKEN\"\]|os\.getenv\(\"GH_TOKEN\"\)" tools/*.py

# 3. Find tools doing privileged ops (cross-check against migrator list)
grep -lE "/branches/.*/protection|/rulesets|repos/.+/contents/\.github/workflows|/actions/secrets|gh api .*-X (PUT|PATCH|DELETE)" tools/*.py
```

Per-result inspection MUST be semantic (read the code path, not just the regex match). Audit-tool-overfit lesson 2026-05-12: `audit_tracked_log_writers.py` was the cautionary tale — syntactic match without semantic verification flagged false positives.

## Audit Record

| Date | Auditor | Findings | Issues Filed |
|------|---------|----------|--------------|
| 2026-05-23 | Claude Opus 4.7 | 18 migrated; 3 needs-migration; 1 legacy-retained; 1 borderline; 1 known-tracked-open | #1236 (push_workflow_fixes), #1237 (fix_branch_protections), #1238 (enable_wikis verification) |
