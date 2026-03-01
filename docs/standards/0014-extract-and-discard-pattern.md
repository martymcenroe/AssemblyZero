# Standard 0014: Extract-and-Discard Pattern for LLM Responses

**Status:** Approved
**Issue:** #507
**Date:** 2026-03-01

## Pattern Definition

Every LLM-calling node MUST follow this sequence:

1. **Save** the full raw LLM response to an audit file (before any processing)
2. **Extract** structured/actionable data from the response
3. **Store** only the extracted data in workflow state — never raw prose

This ensures audit traceability (full response preserved) while keeping workflow
state small and deterministic (no multi-KB prose blobs flowing between nodes).

## Field Categories

| Category | Rule | Example |
|----------|------|---------|
| **Artifacts** | Full content OK — the LLM output IS the deliverable | `generate_draft.py` → draft content, `generate_spec.py` → spec content |
| **Verdicts/Feedback** | Extracted summary only — status + key feedback, ≤200 chars | `review.py` → `_extract_actionable_feedback()`, `review_test_plan.py` → `"BLOCKED: {summary}"` |
| **Code** | Extracted blocks only — strip surrounding prose | `implement_code.py` → code fence extraction |

## Compliance Checklist (New LLM-Calling Nodes)

When adding a new node that calls an LLM:

- [ ] Raw response saved to audit file via `save_audit_file()` BEFORE extraction
- [ ] State fields contain only extracted/structured data
- [ ] No raw prose longer than 200 characters stored in state
- [ ] Artifact fields (where content IS the deliverable) are documented as such

## Current Node Compliance

| Node | Workflow | Compliant | Method |
|------|----------|-----------|--------|
| `generate_draft.py` | Requirements | Yes (artifact) | Draft content is the deliverable |
| `review.py` | Requirements | Yes | `_extract_actionable_feedback()` extracts structured feedback |
| `generate_spec.py` | Impl Spec | Yes (artifact) | Spec content is the deliverable |
| `review_spec.py` | Impl Spec | Yes | Stores `review_verdict` enum + `review_feedback` summary |
| `review_test_plan.py` | Testing | Yes (#507) | Stores `"STATUS: summary[:200]"`, raw response in audit trail |
| `implement_code.py` | Testing | Yes | Extracts code blocks, discards surrounding prose |
