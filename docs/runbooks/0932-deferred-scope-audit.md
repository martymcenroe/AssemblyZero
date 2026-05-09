# 0932 - Deferred-Scope Audit

**Category:** Runbook / Issue-Closure Hygiene
**Version:** 1.0
**Last Updated:** 2026-05-09
**Tool location:** `tools/audit_deferred_scope.py`
**Related:** #930, root CLAUDE.md "Closing Discipline (Deferred Scope Rule)"

---

## Purpose

Audit every closed AssemblyZero issue for "deferred scope" language — work that was acknowledged in the closing comment but pushed to a follow-up issue, PR, or future iteration. Surface the cases where the follow-up was never filed (ORPHANED) before they quietly pile up across the project.

The closing-discipline rule (added 2026-04-21 via #998 / PR #999) requires every deferral to have a follow-up issue filed BEFORE the parent closes. This tool finds the gaps where that discipline failed historically and gives the user a worked list to act on.

## When to Run

- **Periodically** — quarterly is reasonable; weekly is excessive (LLM time + cache churn).
- **Before a major refactor** — surface deferred concerns in the area being touched.
- **Before creating a new repo** — the new-repo subset report flags blockers in the new-repo creation pipeline.
- **After a long working session** with many closed PRs — get recent deferrals classified before context fades.

## Prerequisites

- `gh auth status` — fine-grained PAT works (the tool only does read-only `gh issue list` + `gh api .../comments`).
- `claude` CLI (Max subscription; no API key per root CLAUDE.md) on PATH.
- Network access to GitHub.

## Invocation

```bash
cd /c/Users/mcwiz/Projects/AssemblyZero

# Full pipeline: fetch + regex + LLM classify + write reports
poetry run python tools/audit_deferred_scope.py

# Only phases A + B (no LLM): quick view of regex candidates
poetry run python tools/audit_deferred_scope.py --no-llm

# Force re-fetch of the closed-issue corpus (otherwise uses today's cache)
poetry run python tools/audit_deferred_scope.py --refresh

# Dev: limit to N candidates for testing
poetry run python tools/audit_deferred_scope.py --limit 5
```

## What the Tool Does

Four phases:

| Phase | Action | Notes |
|-------|--------|-------|
| A | `gh issue list --state closed --limit 2000` + paginated per-issue `/comments` | Cached to `data/closed-issues-snapshot-{date}.json` (gitignored, regenerable). Backoff on 429/abuse. |
| B | Regex first-pass over body + comments using 12 deferral patterns (`deferred`, `out-of-scope`, `follow-up`, `phase 2-9`, `tracked separately`, `TODO`, …) | One hit per (keyword, location) per issue — prevents one wordy comment from generating a dozen candidates. |
| C | Per candidate, `claude --print` returns strict JSON: `is_deferral`, `summary`, `addressed_in`, `addressed_status`, `new_repo_related`, `still_relevant`, `rationale` | Cached by SHA-1 of (issue#, keyword, location, context); reruns skip already-classified candidates. |
| D | Render Markdown reports grouped by category | Two outputs: full + new-repo subset. |

Outputs (today's date in filename):
- `docs/audits/0851-deferred-scope-audit-{TODAY}.md` — full report across every closed issue.
- `docs/audits/0852-deferred-scope-new-repo-{TODAY}.md` — subset where `new_repo_related == true`.

## Categories

| Category | Meaning | Action |
|----------|---------|--------|
| **CAUGHT** | Follow-up issue was filed and is closed | None — closing discipline held end-to-end. |
| **ADDRESSED_OPEN** | Follow-up filed, still open | Normal lifecycle; track via the follow-up issue. |
| **ORPHANED** | Still relevant; no follow-up filed | **File a new issue** with the deferred summary as the body. |
| **OBSOLETE** | No longer applies (tech/process changed) | Comment on the original issue noting the deferred work is moot. |
| **UNCLASSIFIED** | LLM judged still-relevance as unclear | Manual review. |
| **ERROR** | LLM call failed | Re-run; if it persists, run with `--limit` against the specific candidate to inspect. |

## Caches

| Path | Content | Lifetime |
|------|---------|----------|
| `data/closed-issues-snapshot-{date}.json` | Issue corpus (body + comments + labels) | Re-fetched on `--refresh` or when `{date}` changes. |
| `data/deferred-scope-llm-cache.json` | LLM responses keyed by content hash | Permanent; safely shared across runs. Delete to re-classify everything. |

Both are in `.gitignore` — regenerable from the tool itself.

## Costs & Time

- **Phase A**: ~3 min for ~600 issues on a cold fetch (rate-limit safe; uses cache thereafter).
- **Phase C**: ~2 sec/candidate × ~180 candidates ≈ 6 min cold. Subsequent runs hit the cache and finish in seconds.
- **LLM tokens**: routed through `claude --print` on the user's Max subscription; no API costs.

## Acting on ORPHANED Findings

Open the report. For each ORPHANED row:

1. Read the original issue and the deferred summary.
2. Decide: file a follow-up issue, or close as obsolete with a comment.
3. **Filing:** open a new issue, paste the rationale, link the parent issue. Apply closing-discipline rule going forward.
4. **Obsolete:** comment on the parent issue explaining why the deferred work no longer applies.

Do not bulk-file follow-ups blind. The LLM is conservative; `still_relevant=true` is its judgment, not a verdict.

## Related Documents

- Closing-discipline rule: root `CLAUDE.md` → "Closing Discipline (Deferred Scope Rule)".
- Tracking issue: [#930](https://github.com/martymcenroe/AssemblyZero/issues/930).
- Latest reports: `docs/audits/0851-deferred-scope-audit-*.md`, `docs/audits/0852-deferred-scope-new-repo-*.md`.

## History

| Date | Change |
|------|--------|
| 2026-05-09 | v1.0: Initial runbook (#930). |
