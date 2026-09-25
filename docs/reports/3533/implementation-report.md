# Implementation Report — --mock drafts a valid LLD so a mock LLD run reaches review and finalize (#3533)

Backfilled 2026-09-25 after the merge, from PR #3534 (merge `51057e77`) and its body (#3559). No report was written at the time; nothing was re-run for the backfill, and every claim below is the PR's own.

Parent: #3502. This change unblocked #3512, #3510 and the stage 6 rehearsal, whose acceptance tests all need a mock LLD run that finishes.

## What was wrong

In mock mode, `generate_draft` always drafted with `mock:draft`. That is an issue-shaped document with no `### 2.1`, `## 11` or `## 12`, so N1.5 rejected every draft and a `--mock` LLD run halted at `N1_draft_iter20`. Review and finalize never ran, so `--mock` rehearsed none of the write path.

## What changed

- `MockProvider.DEFAULT_RESPONSES["lld"]` holds a minimal LLD: one new root-level file in 2.1, one requirement, a 10.0 and 10.1 test plan mapping `(REQ-1)`, and sections 11 and 12. It clears N1.5 and N1b on a near-empty repo.
- In mock mode, an LLD run drafts from `mock:lld`. A caller that names a `mock:` drafter explicitly keeps it; the e2e loop-to-halt harness passes `mock:draft` and so still exercises the loop it was written for. The issue workflow's mock draft is unchanged.

## Files

`assemblyzero/core/llm_provider.py`, `assemblyzero/workflows/requirements/nodes/generate_draft.py`, `tests/unit/test_lld_mock_completes.py`.
