# LLD Review: 172-Feature: Add smoke test that actually runs the workflow after TDD completion

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The design is solid and addresses the core problem of catching import errors early. Security and safety constraints (subprocess isolation, read-only `--help`) are well-defined. However, a data consistency error in the Test Plan (Section 10) creates ambiguity regarding coverage for Requirement 1, dropping validated coverage below the 95% threshold. This requires a minor revision to align the Test ID descriptions between Section 10.0 and 10.1.

## Open Questions Resolved
No open questions found in Section 1.

## Requirement Coverage Analysis (MANDATORY)

**Section 3 Requirements:**
| # | Requirement | Test(s) | Status |
|---|-------------|---------|--------|
| 1 | TDD workflow runs smoke test after green phase passes | T080 | **GAP** (See Note 1) |
| 2 | Smoke test imports and runs the actual entry point (via subprocess) | T020 | ✓ Covered |
| 3 | ImportError/ModuleNotFoundError fails the workflow with clear error message | T030, T040, T070, T080* | ✓ Covered |
| 4 | Smoke test results are recorded in workflow state for reporting | T050, T060 | ✓ Covered |
| 5 | Smoke test can be disabled via configuration for faster iteration | T090 | ✓ Covered |

*Note 1:* **T080 Description Mismatch.** In Section 10.0, T080 is defined as `test_workflow_integration_smoke_after_green` (covering Req 1). However, in Section 10.1, Scenario 080 is defined as "Error message shows failed import" (covering Req 3). Because the Scenario definition for Req 1 is effectively missing (replaced by a duplicate Req 3 scenario), Requirement 1 is technically uncovered in the Scenario table.

**Coverage Calculation:** 4 requirements covered / 5 total = **80%**

**Verdict:** **BLOCK** (Must be ≥95%)

**Missing Test Scenarios:**
- Scenario 080 must be updated in Section 10.1 to match T080 in Section 10.0 (Testing the graph transition from Green -> Smoke).
- The current content of Scenario 080 (Error messaging) should be moved to a new ID or merged into Scenario 030/040.

## Tier 1: BLOCKING Issues
No blocking cost, safety, security, or legal issues found.

### Cost
- [ ] No issues found.

### Safety
- [ ] No issues found.

### Security
- [ ] No issues found.

### Legal
- [ ] No issues found.

## Tier 2: HIGH PRIORITY Issues

### Architecture
- [ ] No issues found.

### Observability
- [ ] No issues found.

### Quality
- [ ] **Test Plan Inconsistency (Section 10):** Test ID `T080` / `080` has conflicting definitions.
    - **10.0:** `test_workflow_integration_smoke_after_green` (Integration logic)
    - **10.1:** "Error message shows failed import" (Error handling logic)
    **Recommendation:** Update Section 10.1 Scenario 080 to describe the integration test: "Input: Green phase completes. Expected: Smoke test node is called next." Ensure the error message test (currently occupying 080) is preserved under a different ID or merged with T030.
- [ ] **Requirement Coverage:** **BLOCK** - Coverage is 80% due to the ambiguity above.

## Tier 3: SUGGESTIONS
- **Scenario ID Hygiene:** Ensure 10.0 and 10.1 remain perfectly synced.
- **Clarification:** Section 2.5 Pseudocode mentions `should_run_smoke_test`. Ensure T090 explicitly tests this conditional edge.

## Questions for Orchestrator
None.

## Verdict
[ ] **APPROVED** - Ready for implementation
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision