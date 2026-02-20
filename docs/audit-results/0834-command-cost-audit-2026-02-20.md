# 0834 Command Cost Audit — 2026-02-20

**Issue:** #370
**Scope:** All slash commands across AssemblyZero canonical + user-level stubs

## Inventory

### AssemblyZero Canonical Commands (8 files, 1530 lines total)

| Command | Lines | Tier | Subagents | Model Hint | Notes |
|---------|------:|------|-----------|------------|-------|
| `audit.md` | 302 | Expensive | 0 (inline) | Sonnet | Full audit suite, necessarily large |
| `cleanup.md` | 295 | Medium | 1 Sonnet | Sonnet | Normal/full delegate to subagent |
| `friction.md` | 210 | Light | 0 | Sonnet | Grep-based analysis, no LLM calls |
| `onboard.md` | 183 | Light-Medium | 0 | Haiku/Sonnet | Mode-dependent cost |
| `code-review.md` | 157 | Medium | 1 Sonnet | Sonnet | Single review agent |
| `test-gaps.md` | 152 | Light | 0 | Sonnet | Grep pre-filter, read matched |
| `promote.md` | 129 | Light | 0 | — | File copy + generalization |
| `commit-push-pr.md` | 102 | Trivial | 0 | Haiku | Simple git workflow |

### User-Level Commands (13 files, 739 lines total)

| Command | Lines | Type | Notes |
|---------|------:|------|-------|
| `handoff.md` | 163 | Canonical | Direct execution, no subagent |
| `sync-permissions.md` | 119 | Python delegation | Zero LLM cost |
| `quote.md` | 119 | Canonical | Git + wiki editing |
| `blog-draft.md` | 82 | Template | File creation only |
| `blog-review.md` | 74 | Tool delegation | Gemini review |
| `audit.md` | 49 | Delegating stub | → AssemblyZero canonical |
| `cleanup.md` | 30 | Delegating stub | → AssemblyZero canonical |
| `unleashed-version.md` | 18 | Trivial | Single echo command |
| 5x stubs | 17 each | Delegating stubs | onboard, friction, commit-push-pr, code-review, test-gaps |

## Changes Made (97 lines removed)

| File | Before | After | Saved | What was removed |
|------|-------:|------:|------:|------------------|
| `friction.md` | 241 | 210 | 31 | JSONL structure reference (model already knows), redundant quick-reference table |
| `test-gaps.md` | 191 | 152 | 39 | Example output section (33 lines of sample that model doesn't need) |
| `commit-push-pr.md` | 114 | 102 | 12 | Rules section (duplicates CLAUDE.md), stale model ref (4.5→4.6) |
| `cleanup.md` | 302 | 295 | 7 | Redundant "parsimonious commits" and "worktree isolation" rules (already in CLAUDE.md) |
| `onboard.md` | 191 | 183 | 8 | "Efficiency Notes" section (obvious best practices) |
| `code-review.md` | 160 | 157 | 3 | Historical design comment about previous 5-agent approach |
| **Total** | **1199** | **1099** | **100** | **~8% reduction in canonical command tokens** |

## Token Impact Estimate

- ~100 lines removed ≈ 400-500 tokens saved per command invocation
- Commands are loaded into context on every `/command` invocation
- At ~$3/M input tokens (Opus), savings are marginal per-invocation but compound across sessions

## Findings: No Further Action Needed

- **Delegating stubs** (17 lines each) are already minimal — good pattern
- **audit.md** (302 lines) is necessarily large — each audit description is needed for execution
- **handoff.md** (163 lines) is necessarily detailed — template precision matters for context transfer
- **sync-permissions.md** and **blog-review.md** delegate to Python tools — efficient pattern
- No commands were identified as Python-delegable that aren't already (sync-permissions already does this)
