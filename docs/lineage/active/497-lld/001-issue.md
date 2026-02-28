---
repo: martymcenroe/AssemblyZero
issue: 497
url: https://github.com/martymcenroe/AssemblyZero/issues/497
fetched: 2026-02-28T21:21:47.115968Z
---

# Issue #497: Cumulative verdict history causes unbounded prompt bloat in LLD revision loop

## Problem

In the LLD draft→review→draft loop (`workflows/requirements/nodes/generate_draft.py`), the full verdict history is included cumulatively in every revision prompt. Each iteration adds another ~2,000-token verdict to the prompt without removing or summarizing prior ones.

### Growth pattern

| Iteration | Verdict tokens in prompt | Total prompt estimate |
|---|---|---|
| 1 (initial) | 0 | ~2,500 |
| 2 | ~2,000 (verdict 1) | ~6,500 |
| 3 | ~4,000 (verdict 1 + 2) | ~10,500 |
| 4 | ~6,000 (verdict 1 + 2 + 3) | ~14,500 |
| 5 | ~8,000 (verdict 1 + 2 + 3 + 4) | ~18,500 |

By iteration 4-5, the prompt is dominated by stale feedback. Verdict 1's blocking issues were either fixed in draft 2 (making verdict 1 irrelevant) or persisted into verdict 2 (making verdict 1 redundant).

### No truncation safeguard

The impl spec loop (Loop 2) has a 120,000-char truncation safeguard that drops low-priority sections. The LLD loop has **no equivalent** — the prompt grows without bound until context limits are hit.

### Where in code

- `generate_draft.py` lines 256-259: verdict history inserted as `## ALL Gemini Review Feedback (CUMULATIVE)`
- `verdict_history` is a list that grows by one entry per review iteration
- No summarization, truncation, or deduplication

## Proposed solution

Replace cumulative verdict history with a rolling window:

### Option A: Latest verdict only + change summary
```
## Review Feedback (Iteration 3)
{verdict_3_full}

## Prior Review Summary
- Iteration 1: BLOCKED — 3 issues (2 fixed, 1 persists: "missing rollback plan")
- Iteration 2: BLOCKED — 2 issues (1 fixed, 1 persists: "missing rollback plan")
```

One full verdict (~2,000 tokens) + a structured summary of prior iterations (~200 tokens). Fixed cost regardless of iteration count.

### Option B: Diff-only feedback
Compare verdict N with verdict N-1. Only include issues that are NEW or PERSISTING. Drop issues marked as resolved.

With #494 (JSON migration), this becomes trivial: `json_diff(verdict_n_minus_1, verdict_n)` to extract new/persisting blocking issues.

### Option C: Token budget for feedback
Cap verdict history at N tokens (e.g., 4,000). If cumulative exceeds budget, summarize oldest verdicts first.

## Acceptance criteria

- [ ] Revision prompt has bounded feedback size regardless of iteration count
- [ ] Latest verdict is always included in full (most actionable)
- [ ] Prior verdicts summarized or diffed (not dropped entirely — persistent issues must be visible)
- [ ] Token cost of iteration 5 prompt is within 20% of iteration 2 prompt
- [ ] No regression in revision quality (LLM still fixes flagged issues)

## Dependencies & cross-references

- **#494** — JSON review output makes verdict diffing trivial
- **#489** — section-level revision (complementary — targets sections, this targets feedback)
- **#491** — diff-aware review (complementary)
- `generate_draft.py` lines 256-259 — the cumulative insertion point