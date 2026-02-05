# LLD Review: 321-Implementation workflow silently exits on API timeout

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The LLD provides a solid technical approach for handling API timeouts using `asyncio.wait_for`. However, there is a discrepancy between the TDD Test Plan (Section 10.0) and the Test Scenarios (Section 10.1), resulting in missing coverage for the "Configurability" requirement in the TDD plan. This must be aligned before approval.

## Open Questions Resolved
- [x] ~~What is the appropriate timeout value for implementation calls?~~ **RESOLVED: 120s is appropriate for code generation tasks. Keep this default.**
- [x] ~~Should we implement exponential backoff retry before failing, or just fail fast?~~ **RESOLVED: Fail fast. Retry logic creates complexity better handled by the specific Retry issue (#309).**
- [x] ~~Should timeout be configurable via environment variable or settings file?~~ **RESOLVED: Yes. Use `os.getenv` in `constants.py` to allow override without code changes.**

## Requirement Coverage Analysis (MANDATORY)

**Section 3 Requirements:**
| # | Requirement | Test(s) | Status |
|---|-------------|---------|--------|
| 1 | API timeout produces clear error message | T010, T040, T050 | ✓ Covered |
| 2 | Workflow exits with non-zero code (1) on timeout | T030 | ✓ Covered |
| 3 | Timeout is configurable via `IMPLEMENTATION_TIMEOUT_SECONDS` | - | **GAP** (Present in 10.1 Scenarios as ID 070, but missing from TDD Plan 10.0) |
| 4 | Partial state is preserved - prompt file still exists | T060 | ✓ Covered |
| 5 | Error is logged to both stderr and workflow log | T070 | ✓ Covered |
| 6 | No silent failures | T010, T030 | ✓ Covered |

**Coverage Calculation:** 5 requirements covered / 6 total = **83%**

**Verdict:** **BLOCK**

**Missing Test Scenarios:**
- The TDD Plan (Section 10.0) must include a test for Requirement 3 (Configurability). Scenario 070 in Section 10.1 covers this ("Configurable timeout"), but it was replaced by "test_timeout_logged_to_stderr" in Section 10.0. Please reconcile the lists so both Logging and Configurability are tested.

## Tier 1: BLOCKING Issues
No blocking issues found. LLD is approved for implementation subject to Tier 2 fixes.

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
- [ ] **Test Plan/Scenario Mismatch:** Section 10.0 (TDD Plan) and Section 10.1 (Scenarios) are out of sync.
    - 10.0 T070 is `test_timeout_logged_to_stderr`
    - 10.1 ID 070 is `Configurable timeout`
    - Please ensure **both** scenarios exist in both tables. You likely need a T080 to cover the missing requirement.
- [ ] **Requirement Coverage:** BLOCK. Coverage is 83% (<95%). Add the missing test case to Section 10.0 to proceed.

## Tier 3: SUGGESTIONS
- **Implementation Detail:** In `constants.py`, ensure `IMPLEMENTATION_TIMEOUT_SECONDS` casts the environment variable to `int` and handles `ValueError` (e.g., `int(os.getenv("...", 120))`).

## Questions for Orchestrator
1. None.

## Verdict
[ ] **APPROVED** - Ready for implementation
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision