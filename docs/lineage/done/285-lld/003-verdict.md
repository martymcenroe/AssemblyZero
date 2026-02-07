# LLD Review: 1285 - Bug: Integration Tests Run by Default

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The LLD correctly identifies the configuration changes needed to gate integration tests. However, it relies on manual verification for the primary acceptance criteria and misses a test scenario for one of the requirements. These Quality issues prevent automated validation in CI and must be addressed before approval.

## Open Questions Resolved
- [x] ~~Should we add an `e2e` marker in addition to `integration`?~~ **RESOLVED: Yes - per issue specification (Agreed).**
- [x] ~~Should we add an `expensive` marker for quota-heavy tests?~~ **RESOLVED: Yes - per issue specification (Agreed).**

## Requirement Coverage Analysis (MANDATORY)

**Section 3 Requirements:**
| # | Requirement | Test(s) | Status |
|---|-------------|---------|--------|
| 1 | `pytest tests/` runs without making any real API calls by default | 010, 040 | ✓ Covered |
| 2 | `pytest tests/ -m integration` runs only integration-marked tests | 020 | ✓ Covered |
| 3 | `pytest tests/ -m "integration or e2e"` runs all external-service tests | - | **GAP** |
| 4 | Test markers are documented in pyproject.toml | 030 | ✓ Covered |
| 5 | Deselected test count is visible in pytest output | 010 | ✓ Covered |

**Coverage Calculation:** 4 requirements covered / 5 total = **80%**

**Verdict:** **BLOCK** (Requires ≥95%)

**Missing Scenarios:**
- Please add a test scenario (e.g., `050`) to verify that the combined query `-m "integration or e2e"` correctly collects both types of tests (Requirement 3).

## Tier 1: BLOCKING Issues
No blocking issues found in Tier 1 categories.

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
- [ ] **Manual Testing Violation (CRITICAL):** Section 10.3 and Scenarios 010, 020, and 040 rely on "Manual" verification. This violates the "No Human Delegation" protocol. Configuration changes can and must be tested automatically.
    - **Recommendation:** Define a "meta-test" script (e.g., `tests/meta/test_pytest_config.py` or a CI shell script) that invokes `pytest` as a subprocess (e.g., `subprocess.run(["pytest", ...], capture_output=True)`) and asserts that the stdout contains the expected "deselected" counts or "collected" items. This ensures the configuration cannot regress without CI failing.
- [ ] **Requirement Coverage:** Coverage is 80% (<95%). Requirement 3 is not tested.
- [ ] **TDD Coverage Target:** Section 10.0 lists "Coverage Target: N/A". Please specify "Coverage Target: 100% of Scenarios" or similar. Configuration behavior must be fully verified.

## Tier 3: SUGGESTIONS
- Consider adding a `pytest.ini` check if `pyproject.toml` is not the only config source, though `pyproject.toml` is preferred.
- For Scenario 040 (No API calls), this can be automated by running the default test suite in a subprocess with network disabled (if environment permits) or by using a library like `pytest-socket` to enforce no outgoing connections during the default run.

## Questions for Orchestrator
1. None.

## Verdict
[ ] **APPROVED** - Ready for implementation
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision