---
repo: martymcenroe/AssemblyZero
issue: 507
url: https://github.com/martymcenroe/AssemblyZero/issues/507
fetched: 2026-03-01T04:10:24.466668Z
---

# Issue #507: enhancement: enforce extract-and-discard pattern for all LLM-populated state fields

## Problem

Not all nodes follow the same discipline when storing LLM output in workflow state. Some nodes extract only what's needed and discard the raw response; others store full prose in state fields. This inconsistency leads to prompt bloat, redundant storage, and harder-to-maintain code.

## The Pattern (Gold Standard)

Two nodes already do this correctly:

### `implement_code.py` (Testing Workflow)
- Calls Claude, gets back a full response with explanation + code
- **Extracts** only the code block from the response
- Stores extracted code in `completed_files` state field
- Raw response goes to audit trail file only
- State carries structured data; audit carries prose

### `review_spec.py` (Impl Spec Workflow)  
- Calls Gemini reviewer, gets back full verdict prose
- **Extracts** structured `review_feedback` and single-word `review_verdict`
- Stores only the extracted fields in state
- Full verdict goes to audit trail file only

### The Anti-Pattern

`review.py` (Requirements Workflow) — stores full verdict prose (~2,000 tokens) in `current_verdict` AND saves to audit file. This is #506.

## What This Issue Covers

A systematic audit and refactor to ensure **every node that calls an LLM** follows the extract-and-discard pattern:

1. **Audit all LLM-calling nodes** — identify which store raw prose in state vs extracted data
2. **Define the contract**: state fields carry structured/extracted data only; audit trail carries full responses
3. **Refactor violating nodes** to extract what's needed and discard the rest
4. **Document the pattern** so future nodes follow it by default

## Known LLM-Calling Nodes to Audit

From the state field analysis (18 LLM-populated fields across ~170 total):

| Node | Workflow | LLM | State Field | Stores | Compliant? |
|------|----------|-----|-------------|--------|------------|
| `generate_draft.py` | Requirements | Claude | `current_draft` | Full draft | ✅ (draft IS the artifact) |
| `review.py` | Requirements | Gemini | `current_verdict` | Full prose | ❌ #506 |
| `review.py` | Requirements | Gemini | `verdict_history` | Cumulative prose | ❌ #497 |
| `generate_spec.py` | Impl Spec | Claude | `spec_draft` | Full spec | ✅ (spec IS the artifact) |
| `review_spec.py` | Impl Spec | Gemini | `review_feedback` | Extracted feedback | ✅ |
| `review_spec.py` | Impl Spec | Gemini | `review_verdict` | Single word | ✅ |
| `review_test_plan.py` | Testing | Gemini | `test_plan_verdict` | Full prose | ⚠️ (saved to audit, not reused — but still in state) |
| `implement_code.py` | Testing | Claude | `completed_files` | Extracted code | ✅ |
| `adversarial_node.py` | Testing | Gemini | `adversarial_analysis` | Structured object | ✅ |

Note: `current_draft` and `spec_draft` are **the artifacts themselves** — they're not "raw LLM responses" but the actual deliverables. These are correctly in state.

## Difficulty

This is an **LLD-level** effort because:
- Each node's consumers need to be traced (what reads the state field downstream?)
- The revision nodes need structured feedback to know what to fix — can't just delete the field
- `verdict_history` (#497) and `current_verdict` (#506) changes must be coordinated
- Ideally done after #494 (JSON migration) provides reliable structured verdicts
- Testing: need to verify that revision loops still work correctly with structured data instead of prose

## Depends On

- #494 (JSON migration) — provides structured verdict objects that make extraction trivial
- #506 (requirements review node redundancy) — the specific instance this generalizes

## Acceptance Criteria

- [ ] Audit document listing every LLM-calling node and its state field compliance
- [ ] All non-artifact LLM state fields store structured/extracted data only
- [ ] Full LLM responses preserved in audit trail files (already the case for most)
- [ ] Revision nodes consume structured feedback successfully
- [ ] All existing tests pass, no regressions
- [ ] Pattern documented in engineering standards (`docs/standards/`)