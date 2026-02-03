# Test Plan Review Prompt

You are a senior QA engineer reviewing a test plan extracted from a Low-Level Design (LLD) document. Your goal is to ensure the test plan provides adequate coverage and uses real, executable tests.

## Pre-Flight Check

Before reviewing, verify these fundamentals:
- [ ] Test plan section exists and is not empty
- [ ] At least one test scenario is defined
- [ ] Test scenarios have names and descriptions

If any pre-flight check fails, immediately return BLOCKED with the specific issue.

## Review Criteria

### 1. Coverage Analysis (CRITICAL - 100% threshold per ADR 0207)

Calculate coverage by mapping test scenarios to requirements:

```
Coverage = (Requirements with tests / Total requirements) * 100
```

For each requirement, identify:
- Which test(s) cover it
- If no test covers it, flag as a gap

**BLOCKING if:** Coverage < 95%

### 2. Test Reality Check (CRITICAL)

Every test MUST be an executable automated test. Flag any test that:
- Delegates to "manual verification" or "human review"
- Says "verify by inspection" or "visual check"
- Has no clear assertions or expected outcomes
- Is vague like "test that it works"

**BLOCKING if:** Any test is not executable

### 3. No Human Delegation

Tests must NOT require human intervention. Flag any test that:
- Requires someone to "observe" behavior
- Needs "judgment" to determine pass/fail
- Says "ask the user" or "get feedback"

**BLOCKING if:** Any test delegates to humans

### 4. Test Type Appropriateness

Validate that test types match the functionality:
- **Unit tests:** Isolated, mock dependencies, test single functions
- **Integration tests:** Test component interactions, may use real DB
- **E2E tests:** Full user flows, minimal mocking
- **Browser tests:** Require real browser (Playwright/Selenium)
- **CLI tests:** Test command-line interfaces

**WARNING (not blocking) if:** Test types seem mismatched

### 5. Edge Cases

Check for edge case coverage:
- Empty inputs
- Invalid inputs
- Boundary conditions
- Error conditions
- Concurrent access (if applicable)

**WARNING (not blocking) if:** Edge cases seem missing

## Output Format

Provide your verdict in this exact format:

```markdown
## Pre-Flight Gate

- [x] PASSED / [ ] FAILED: Test plan exists
- [x] PASSED / [ ] FAILED: Scenarios defined
- [x] PASSED / [ ] FAILED: Scenarios have names

## Coverage Analysis

| Requirement | Test(s) | Status |
|-------------|---------|--------|
| REQ-1       | test_x  | Covered |
| REQ-2       | -       | GAP |

**Coverage: X/Y requirements (Z%)**

## Test Reality Check

| Test | Issue | Status |
|------|-------|--------|
| test_x | None | OK |
| test_y | "Manual check" | FAIL |

## Human Delegation Check

- [ ] PASSED: No human delegation found
- [ ] FAILED: [list tests that delegate to humans]

## Test Type Review

| Test | Declared Type | Appropriate | Notes |
|------|---------------|-------------|-------|
| test_x | unit | Yes | - |
| test_y | integration | No | Should be unit |

## Edge Cases

- [ ] Empty inputs covered
- [ ] Invalid inputs covered
- [ ] Error conditions covered

## Verdict

[x] **APPROVED** - Test plan is ready for implementation

OR

[x] **BLOCKED** - Test plan needs revision

## Required Changes (if BLOCKED)

1. [Specific, actionable change needed]
2. [Specific, actionable change needed]
```

## Important Notes

- Be strict on coverage (95% threshold)
- Be strict on test reality (no manual tests)
- Provide specific, actionable feedback
- Reference specific tests and requirements by name


---

# Test Plan for Issue #141

## Requirements to Cover

- REQ-1: LLD files in `docs/lld/active/` are moved to `docs/lld/done/` on successful workflow completion
- REQ-2: Report files in `docs/reports/active/` are moved to `docs/reports/done/` on successful workflow completion
- REQ-3: Archival is logged in workflow output for audit trail
- REQ-4: Missing files are handled gracefully (logged, not errored)
- REQ-5: `done/` directories are created if they don't exist
- REQ-6: Archival only happens on successful completion (not on failure/abort)

## Detected Test Types

- browser
- e2e
- integration
- mobile
- performance
- security
- unit

## Required Tools

- appium
- bandit
- detox
- docker-compose
- locust
- playwright
- pytest
- pytest-benchmark
- safety
- selenium

## Mock Guidance

**Browser/UI Tests:** Real browser required, mock backend APIs for isolation
**End-to-End Tests:** Minimal mocking - test against real (sandboxed) systems
**Integration Tests:** Use test doubles for external services, real DB where possible
**Mobile App Tests:** Use emulators/simulators, mock backend services
**Performance Tests:** Test against representative data volumes
**Security Tests:** Never use real credentials, test edge cases thoroughly
**Unit Tests:** Mock external dependencies (APIs, DB, filesystem)

## Coverage Target

95%

## Test Scenarios

### test_010
- **Type:** integration
- **Requirement:** 
- **Description:** Happy path - LLD archived | integration | State with valid LLD path in active/ | LLD moved to done/, path returned | File exists in done/, not in active/, log contains success message
- **Mock needed:** False
- **Assertions:** 

### test_020
- **Type:** integration
- **Requirement:** 
- **Description:** Happy path - Reports archived | integration | State with report paths in active/ | Reports moved to done/ | Files exist in done/, not in active/, log contains success message
- **Mock needed:** False
- **Assertions:** 

### test_030
- **Type:** integration
- **Requirement:** 
- **Description:** LLD not found | integration | State with non-existent LLD path | Warning logged, None returned | No exception, log contains warning
- **Mock needed:** False
- **Assertions:** 

### test_040
- **Type:** integration
- **Requirement:** 
- **Description:** LLD not in active/ | integration | State with LLD in arbitrary path | Skip archival, None returned | File unchanged, log indicates skip
- **Mock needed:** False
- **Assertions:** 

### test_050
- **Type:** integration
- **Requirement:** 
- **Description:** done/ doesn't exist | integration | Valid LLD, no done/ directory | done/ created, LLD moved | Directory created, file moved
- **Mock needed:** False
- **Assertions:** 

### test_060
- **Type:** integration
- **Requirement:** 
- **Description:** Destination file exists | integration | LLD exists in both active/ and done/ | Append timestamp to new name | No overwrite, both files preserved
- **Mock needed:** False
- **Assertions:** 

### test_070
- **Type:** unit
- **Requirement:** 
- **Description:** Empty state | unit | State with no paths | Graceful no-op | No exception, empty archival list
- **Mock needed:** False
- **Assertions:** 

### test_080
- **Type:** integration
- **Requirement:** 
- **Description:** Mixed success | integration | Some files exist, some don't | Archive existing, log missing | Partial archival succeeds
- **Mock needed:** False
- **Assertions:** 

### test_090
- **Type:** integration
- **Requirement:** 
- **Description:** Workflow failed - no archival | integration | State with workflow_success=False, valid LLD path | No files moved, skip logged | Files remain in active/, log indicates skip
- **Mock needed:** False
- **Assertions:** 

### test_100
- **Type:** unit
- **Requirement:** 
- **Description:** Exception during file rename | unit | Valid LLD, mock rename to raise OSError | None returned, error logged | No exception propagated, log contains error message
- **Mock needed:** True
- **Assertions:** 

### test_110
- **Type:** unit
- **Requirement:** 
- **Description:** Generate summary | unit | Complete TestReportMetadata dict | Markdown summary string | Contains issue number, coverage %, file lists, E2E status
- **Mock needed:** False
- **Assertions:** 

### test_120
- **Type:** unit
- **Requirement:** 
- **Description:** LLD archival fails via wrapper | unit | State with LLD path not in active/ | Skipped list includes LLD path | archived=[], skipped=[lld_path]
- **Mock needed:** False
- **Assertions:** 

### test_130
- **Type:** unit
- **Requirement:** 
- **Description:** Impl report archival fails | unit | State with impl_report path not in active/ | Skipped list includes impl report | archived=[], skipped=[impl_path]
- **Mock needed:** False
- **Assertions:** 

### test_140
- **Type:** integration
- **Requirement:** 
- **Description:** E2E evaluation (skip_e2e=False) | integration | State with skip_e2e=False, e2e_output="passed" | E2E passed evaluated from output | finalize completes, e2e logic exercised
- **Mock needed:** False
- **Assertions:** 

### test_150
- **Type:** integration
- **Requirement:** 
- **Description:** Successful workflow with archival | integration | State with workflow_success=True (default), valid LLD | LLD archived, archival printed | archived_files populated, LLD moved to done/
- **Mock needed:** False
- **Assertions:** 

## Original Test Plan Section

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | Happy path - LLD archived | integration | State with valid LLD path in active/ | LLD moved to done/, path returned | File exists in done/, not in active/, log contains success message |
| 020 | Happy path - Reports archived | integration | State with report paths in active/ | Reports moved to done/ | Files exist in done/, not in active/, log contains success message |
| 030 | LLD not found | integration | State with non-existent LLD path | Warning logged, None returned | No exception, log contains warning |
| 040 | LLD not in active/ | integration | State with LLD in arbitrary path | Skip archival, None returned | File unchanged, log indicates skip |
| 050 | done/ doesn't exist | integration | Valid LLD, no done/ directory | done/ created, LLD moved | Directory created, file moved |
| 060 | Destination file exists | integration | LLD exists in both active/ and done/ | Append timestamp to new name | No overwrite, both files preserved |
| 070 | Empty state | unit | State with no paths | Graceful no-op | No exception, empty archival list |
| 080 | Mixed success | integration | Some files exist, some don't | Archive existing, log missing | Partial archival succeeds |
| 090 | Workflow failed - no archival | integration | State with workflow_success=False, valid LLD path | No files moved, skip logged | Files remain in active/, log indicates skip |
| 100 | Exception during file rename | unit | Valid LLD, mock rename to raise OSError | None returned, error logged | No exception propagated, log contains error message |
| 110 | Generate summary | unit | Complete TestReportMetadata dict | Markdown summary string | Contains issue number, coverage %, file lists, E2E status |
| 120 | LLD archival fails via wrapper | unit | State with LLD path not in active/ | Skipped list includes LLD path | archived=[], skipped=[lld_path] |
| 130 | Impl report archival fails | unit | State with impl_report path not in active/ | Skipped list includes impl report | archived=[], skipped=[impl_path] |
| 140 | E2E evaluation (skip_e2e=False) | integration | State with skip_e2e=False, e2e_output="passed" | E2E passed evaluated from output | finalize completes, e2e logic exercised |
| 150 | Successful workflow with archival | integration | State with workflow_success=True (default), valid LLD | LLD archived, archival printed | archived_files populated, LLD moved to done/ |

### 10.2 Test Commands

```bash
# Run all automated tests
poetry run pytest tests/workflows/testing/nodes/test_finalize.py -v

# Run only archival-specific tests
poetry run pytest tests/workflows/testing/nodes/test_finalize.py -v -k "archive"

# Run with coverage
poetry run pytest tests/workflows/testing/nodes/test_finalize.py -v --cov=agentos/workflows/testing/nodes/finalize
```

### 10.3 Manual Tests (Only If Unavoidable)

N/A - All scenarios automated.
