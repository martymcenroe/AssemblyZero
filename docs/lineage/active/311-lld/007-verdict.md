# LLD Review: 1311-Feature: Implementation workflow runs wrong test file

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The LLD is well-structured, addressing a clear workflow consistency issue (TDD path tracking). It correctly identifies the state machine approach as the solution to the "wrong test file" bug. The design includes comprehensive mechanical validation, safety checks for file deletion, and a 100% coverage test plan. The transition from implicit convention to explicit state tracking is robust.

## Open Questions Resolved
- [x] ~~Should we deprecate the `tests/test_issue_N.py` scaffold pattern entirely in favor of `tests/unit/test_<module>.py`?~~ **RESOLVED: No. Keep scaffold for "Red" phase initialization, enforce cleanup in "Green/Refactor".**
- [x] ~~Do we need migration for existing scaffold files from past issues?~~ **RESOLVED: No. Apply cleanup lazily on re-activation.**

## Requirement Coverage Analysis (MANDATORY)

**Section 3 Requirements:**
| # | Requirement | Test(s) | Status |
|---|-------------|---------|--------|
| R1 | Verification phase runs the SAME test file that was created/modified in red/green phases | T070 | ✓ Covered |
| R2 | Test file path is explicitly stored in TDD state, not inferred | T010, T020 | ✓ Covered |
| R3 | Scaffold files (`tests/test_issue_N.py`) are cleaned up when unit tests exist | T050, T060, T100 | ✓ Covered |
| R4 | Workflow reports clear error if test file path is missing from state | T080, T090 | ✓ Covered |
| R5 | Moving a test file updates state and tracks history | T030, T040 | ✓ Covered |
| R6 | All phases log which test file path they are using | T120 | ✓ Covered |

**Coverage Calculation:** 6 requirements covered / 6 total = **100%**

**Verdict:** PASS

## Tier 1: BLOCKING Issues
No blocking issues found. LLD is approved for implementation.

### Cost
- [ ] No issues found. Local file operations only.

### Safety
- [ ] No issues found. Destructive file operations (`cleanup_stale_scaffold`) are strictly scoped to the `tests/test_issue_N.py` pattern to prevent data loss.

### Security
- [ ] No issues found.

### Legal
- [ ] No issues found.

## Tier 2: HIGH PRIORITY Issues
No high-priority issues found.

### Architecture
- [ ] No issues found. Design adheres to project structure (`agentos/core/`) and state management patterns.

### Observability
- [ ] No issues found. Requirement R6 ensures logging compliance.

### Quality
- [ ] **Requirement Coverage:** PASS (100%). Test plan is complete and valid.

## Tier 3: SUGGESTIONS
- **Constraint Handling:** In `track_test_file_move`, consider verifying that the `new_path` actually exists before updating state, to prevent state pointing to a phantom file if the move failed.
- **Logging:** Ensure the log output format is machine-parsable (e.g., `[TDD] Using test file: ...`) to facilitate future automated auditing or dashboarding.

## Questions for Orchestrator
1. None.

## Verdict
[x] **APPROVED** - Ready for implementation
[ ] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision