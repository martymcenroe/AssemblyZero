# LLD Review: 1311-Feature: Implementation workflow runs wrong test file

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The LLD proposes a robust state-based tracking mechanism to resolve the test file path ambiguity in the TDD workflow. The design correctly identifies the need for explicit state over convention-based inference. However, the LLD is **BLOCKED** due to missing test coverage for Requirement R6 (Logging) and pending decisions on open questions.

## Open Questions Resolved
- [x] ~~Should we deprecate the `tests/test_issue_N.py` scaffold pattern entirely in favor of `tests/unit/test_<module>.py`?~~ **RESOLVED: No.** The scaffold pattern serves as a necessary temporary scratchpad when the target module name or structure is not yet known. Keep the scaffold pattern for the "Red" phase initialization, but enforce the transition/cleanup to `tests/unit/` as part of the "Green/Refactor" phase completion.
- [x] ~~Do we need migration for existing scaffold files from past issues?~~ **RESOLVED: No.** Do not mass-migrate history. Apply the cleanup logic lazily: if a developer re-activates an old issue context, the workflow should detect the conflict (scaffold + unit exist) and prompt/execute the cleanup then.

## Requirement Coverage Analysis (MANDATORY)

**Section 3 Requirements:**
| # | Requirement | Test(s) | Status |
|---|-------------|---------|--------|
| R1 | Verification phase runs the SAME test file that was created/modified in red/green phases | T070 (Scenario 070) | ✓ Covered |
| R2 | Test file path is explicitly stored in TDD state, not inferred | T010, T020 (Scenarios 010, 020) | ✓ Covered |
| R3 | Scaffold files (`tests/test_issue_N.py`) are cleaned up when unit tests exist | T050 (Scenario 050) | ✓ Covered |
| R4 | Workflow reports clear error if test file path is missing from state | T080, T090 (Scenarios 080, 090) | ✓ Covered |
| R5 | Moving a test file updates state and tracks history | T030, T040 (Scenarios 030, 040) | ✓ Covered |
| R6 | All phases log which test file path they are using | - | **GAP** |

**Coverage Calculation:** 5 requirements covered / 6 total = **83%**

**Verdict:** BLOCK

**Missing Test Scenarios:**
- Needs a test scenario (e.g., T120) that captures logs/stdout and asserts that the `test_file_path` is printed during phase execution.

## Tier 1: BLOCKING Issues
No blocking issues found. LLD is approved for implementation regarding Cost, Safety, Security, and Legal.

### Cost
- [ ] No issues found.

### Safety
- [ ] No issues found. The strict pattern matching (`test_issue_N.py`) for file deletion in `cleanup_stale_scaffold` is an acceptable safety control without requiring human confirmation for every TDD cycle, as these are temporary system-generated artifacts.

### Security
- [ ] No issues found.

### Legal
- [ ] No issues found.

## Tier 2: HIGH PRIORITY Issues

### Architecture
- [ ] No issues found. File paths are semantically correct for the project structure.

### Observability
- [ ] **Missing Log Verification:** Requirement R6 mandates logging, but there is no verification of this behavior. While the code might log it, the absence of a test means this feature could regress silently.

### Quality
- [ ] **Requirement Coverage:** 83% (<95%). You must add a test case to verify Requirement R6 (Logging).
- [ ] **Test Completeness:** Ensure `resolve_test_file_conflict` logic covers the edge case where `state.test_file_path` points to a non-existent file, but a valid unit test exists in `tests/unit/`. The current logic implies it, but an explicit test case would prevent "stuck" states.

## Tier 3: SUGGESTIONS
- Consider adding a "dry run" or "audit" mode to the `cleanup_stale_scaffold` function to list what would be deleted without actually deleting it, useful for debugging state issues.

## Questions for Orchestrator
1. None.

## Verdict
[ ] **APPROVED** - Ready for implementation
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision