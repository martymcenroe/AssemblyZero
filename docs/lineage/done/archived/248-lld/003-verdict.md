# LLD Review: #248-Gemini-Answers-Open-Questions

## Identity Confirmation

I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate

PASSED

## Review Summary

The LLD is well-structured and addresses a clear workflow gap (the pre-review validation block). The proposed solution to move validation post-review and introduce a question-answering loop is sound. The TDD plan is comprehensive, and safety mechanisms (iteration budget) are in place.

## Open Questions Resolved

* [x] ~~Should we add a max retry count for the Gemini question-answering loop, or reuse the existing max_iterations budget?~~ **RESOLVED: Reuse the existing `max_iterations` budget.** Adding a separate counter introduces unnecessary state complexity. The global budget suffices to prevent infinite loops.
* [x] ~~What should happen if Gemini marks ALL questions as HUMAN REQUIRED - terminate workflow or force human gate?~~ **RESOLVED: Force Human Gate (N4).** Terminating the workflow defeats the purpose of "Human Required". The workflow must escalate to the human for resolution.
* [x] ~~Should the prompt changes be in the template file (0702c) or hardcoded in review.py?~~ **RESOLVED: Template file (0702c).** Prompts must be treated as versioned assets/data, not hardcoded strings in logic files.

## Requirement Coverage Analysis (MANDATORY)

**Section 3 Requirements:**
| # | Requirement | Test(s) | Status |
|---|-------------|---------|--------|
| 1 | Drafts with open questions proceed to Gemini review (not blocked pre-review) | T010 | ✓ Covered |
| 2 | Gemini review prompt includes instructions to answer open questions | T070 | ✓ Covered |
| 3 | Post-review check detects unanswered questions (not marked HUMAN REQUIRED) | T030 | ✓ Covered |
| 4 | Unanswered questions trigger loop back to Gemini with followup prompt | T030 | ✓ Covered |
| 5 | Only questions marked "HUMAN REQUIRED" escalate to human gate | T040 | ✓ Covered |
| 6 | Workflow respects max_iterations for combined revision+question loops | T050 | ✓ Covered |
| 7 | Final validation only blocks if HUMAN REQUIRED questions remain unanswered by human | T060 | ✓ Covered |

**Coverage Calculation:** 7 requirements covered / 7 total = **100%**

**Verdict:** PASS

## Tier 1: BLOCKING Issues

No blocking issues found. LLD is approved for implementation.

### Cost

* [ ] No issues found. Reuse of `max_iterations` ensures cost control.

### Safety

* [ ] No issues found. Fail-safe (Fail Closed) is explicitly defined.

### Security

* [ ] No issues found.

### Legal

* [ ] No issues found.

## Tier 2: HIGH PRIORITY Issues

No high-priority issues found.

### Architecture

* [ ] No issues found. Design fits the existing node/graph pattern.

### Observability

* [ ] **Logging Strategy:** While the logic is clear, ensure that the *transition* event (looping back to Gemini) is explicitly logged at INFO level. This is critical for debugging why a workflow is taking longer than expected. (Non-blocking, but strongly recommended during implementation).

### Quality

* [ ] **Requirement Coverage:** PASS (100%).

## Tier 3: SUGGESTIONS

* **Fixture Maintenance:** Ensure `0702c` template changes are synced with the test fixtures in `tests/unit/test_open_questions_loop.py` so tests don't drift from the actual prompt asset.
* **Metric:** Consider adding a metric for `question_loop_triggered_count` to track how often Gemini fails to answer questions on the first pass.

## Questions for Orchestrator

1. None.

## Verdict

[x] **APPROVED** - Ready for implementation
[ ] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision
