# 0932 - Deferred-Scope Audit

**Category:** Runbook / Issue-Closure Hygiene
**Version:** 1.1
**Last Updated:** 2026-10-07
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
- `agy` on PATH and signed in. The classifier is the `tools.audit_deferred_scope` seat, and it must resolve to a `gemini:` spec (Gemini through agy, ADR 0237). Under a profile where it does not, the tool refuses before its first call.
- The alert channel configured (`AZ_OPERATOR_EMAIL_FROM` or `~/.assemblyzero/alert.json`, #3729), because a failed run alerts the operator.
- Network access to GitHub.

## Invocation

From the AssemblyZero checkout:

```bash
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
| C | Per candidate, the classifier seat (Gemini through agy) returns strict JSON: `is_deferral`, `summary`, `addressed_in`, `addressed_status`, `new_repo_related`, `still_relevant`, `rationale` | Cached by SHA-1 of (issue#, keyword, location, context); reruns skip already-classified candidates. Only successful classifications are cached. |
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

## When the Audit Stops

Every failure stops the run (ADR 0236, #3584):
- a failed `gh` fetch;
- a corrupt cache;
- a classifier call that fails;
- an answer that is not JSON;
- a classifier seat that does not resolve to Gemini.

On any of these, the tool alerts the operator by email and on standard error, with the phase, the candidate's issue number and the spec. It then exits 1 and writes **no** report, because reports are written only after every candidate is classified. A report on disk is therefore always complete.

To resume, fix the cause named in the alert and rerun. Classifications already made are in the cache, so the rerun picks up where the last one stopped. A corrupt cache names its file: move it aside, or rerun with `--refresh` for the corpus and state-index caches.

A `--limit N` run classifies only the first N candidates, and its reports say so in the Method line.

## Caches

| Path | Content | Lifetime |
|------|---------|----------|
| `data/closed-issues-snapshot-{date}.json` | Issue corpus (body + comments + labels) | Re-fetched on `--refresh` or when `{date}` changes. |
| `data/issue-state-index-{date}.json` | Open/closed state and title of every issue | Re-fetched on `--refresh` or when `{date}` changes. |
| `data/deferred-scope-llm-cache.json` | Successful classifications keyed by content hash | Permanent; safely shared across runs. Entries carrying an error, written before #3584, are dropped and reclassified. Delete to re-classify everything. |

Both are in `.gitignore` — regenerable from the tool itself.

## Costs & Time

- **Phase A**: ~3 min for ~600 issues on a cold fetch (rate-limit safe; uses cache thereafter).
- **Phase C**: ~2 sec/candidate × ~180 candidates ≈ 6 min cold. Subsequent runs hit the cache and finish in seconds.
- **LLM tokens**: Gemini through agy on the operator's subscription; there is no API key and no API cost (ADR 0237).

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
| 2026-10-07 | v1.1: Gemini through agy under every profile; every failure stops the audit and alerts, with no partial report; the ERROR category is gone (#3584). |
