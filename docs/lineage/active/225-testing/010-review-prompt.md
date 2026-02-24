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

# Test Plan for Issue #225

## Requirements to Cover

- REQ-T010: run_pytest()
- REQ-T025: ensure_verbose_flag()
- REQ-T030: parse_skipped_tests()
- REQ-T040: parse_skipped_tests()
- REQ-T050: detect_critical_tests()
- REQ-T060: detect_critical_tests()
- REQ-T070: find_audit_block()
- REQ-T080: find_audit_block()
- REQ-T090: match_test_to_audit()
- REQ-T100: main()
- REQ-T140: main()
- REQ-T150: main()
- REQ-T160: main()

## Detected Test Types

- browser
- e2e
- integration
- mobile
- performance
- security
- terminal
- unit

## Required Tools

- appium
- bandit
- click.testing
- detox
- docker-compose
- locust
- pexpect
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
**Terminal/CLI Tests:** Use CliRunner or capture stdout/stderr
**Unit Tests:** Mock external dependencies (APIs, DB, filesystem)

## Coverage Target

95%

## Test Scenarios

### test_id
- **Type:** unit
- **Requirement:** 
- **Description:** Tests Function | File | Input | Expected Output
- **Mock needed:** False
- **Assertions:** 

### test_t010
- **Type:** unit
- **Requirement:** 
- **Description:** `run_pytest()` | `test_parser.py` | `args=["tests/unit/", "-v", "-x"]` | subprocess called with matching args
- **Mock needed:** False
- **Assertions:** 

### test_t020
- **Type:** unit
- **Requirement:** 
- **Description:** `run_pytest()` + `main()` | `test_parser.py`, `test_integration.py` | pytest returns 1 | gate returns 1
- **Mock needed:** False
- **Assertions:** 

### test_t025
- **Type:** unit
- **Requirement:** 
- **Description:** `ensure_verbose_flag()` | `test_parser.py` | `args=["tests/", "--tb=short"]` | `[..., "-v"]` appended
- **Mock needed:** False
- **Assertions:** 

### test_t030
- **Type:** unit
- **Requirement:** 
- **Description:** `parse_skipped_tests()` | `test_parser.py` | inline SKIPPED output | `SkippedTest` with correct fields
- **Mock needed:** False
- **Assertions:** 

### test_t040
- **Type:** unit
- **Requirement:** 
- **Description:** `parse_skipped_tests()` | `test_parser.py` | multiple skipped lines | 3 `SkippedTest` objects
- **Mock needed:** False
- **Assertions:** 

### test_t050
- **Type:** unit
- **Requirement:** 
- **Description:** `detect_critical_tests()` | `test_parser.py` | test with "critical" in name | `is_critical=True`
- **Mock needed:** False
- **Assertions:** 

### test_t060
- **Type:** unit
- **Requirement:** 
- **Description:** `detect_critical_tests()` | `test_parser.py` | test with "security"/"auth" in name | `is_critical=True`
- **Mock needed:** False
- **Assertions:** 

### test_t070
- **Type:** unit
- **Requirement:** 
- **Description:** `find_audit_block()` | `test_auditor.py` | stdout containing audit block | `AuditBlock` with `source="stdout"`
- **Mock needed:** False
- **Assertions:** 

### test_t080
- **Type:** unit
- **Requirement:** 
- **Description:** `find_audit_block()` | `test_auditor.py` | `.skip-audit.md` file | `AuditBlock` with `source="file"`
- **Mock needed:** False
- **Assertions:** 

### test_t090
- **Type:** unit
- **Requirement:** 
- **Description:** `match_test_to_audit()` | `test_auditor.py` | exact and glob patterns | `True`/`False` matches
- **Mock needed:** False
- **Assertions:** 

### test_t100
- **Type:** unit
- **Requirement:** 
- **Description:** `main()` | `test_integration.py` | skips, no audit | exit code 1
- **Mock needed:** False
- **Assertions:** 

### test_t110
- **Type:** unit
- **Requirement:** 
- **Description:** `validate_audit()` + `main()` | `test_auditor.py`, `test_integration.py` | test not in audit | unaudited list populated, exit 1
- **Mock needed:** False
- **Assertions:** 

### test_t120
- **Type:** unit
- **Requirement:** 
- **Description:** `validate_audit()` + `main()` | `test_auditor.py`, `test_integration.py` | critical + UNVERIFIED | unverified list populated, exit 1
- **Mock needed:** False
- **Assertions:** 

### test_t130
- **Type:** unit
- **Requirement:** 
- **Description:** `validate_audit()` + `main()` | `test_auditor.py`, `test_integration.py` | all audited | `([], [])`, exit 0
- **Mock needed:** False
- **Assertions:** 

### test_t140
- **Type:** unit
- **Requirement:** 
- **Description:** `main()` | `test_integration.py` | WARNING logged, exit 0
- **Mock needed:** False
- **Assertions:** 

### test_t150
- **Type:** unit
- **Requirement:** 
- **Description:** `main()` | `test_integration.py` | no skipped tests | pytest exit code returned
- **Mock needed:** False
- **Assertions:** 

### test_t160
- **Type:** unit
- **Requirement:** 
- **Description:** `main()` | `test_integration.py` | all flags passed through
- **Mock needed:** False
- **Assertions:** 

## Original Test Plan Section

| Test ID | Tests Function | File | Input | Expected Output |
|---------|---------------|------|-------|-----------------|
| T010 | `run_pytest()` | `test_parser.py` | `args=["tests/unit/", "-v", "-x"]` | subprocess called with matching args |
| T020 | `run_pytest()` + `main()` | `test_parser.py`, `test_integration.py` | pytest returns 1 | gate returns 1 |
| T025 | `ensure_verbose_flag()` | `test_parser.py` | `args=["tests/", "--tb=short"]` | `[..., "-v"]` appended |
| T030 | `parse_skipped_tests()` | `test_parser.py` | inline SKIPPED output | `SkippedTest` with correct fields |
| T040 | `parse_skipped_tests()` | `test_parser.py` | multiple skipped lines | 3 `SkippedTest` objects |
| T050 | `detect_critical_tests()` | `test_parser.py` | test with "critical" in name | `is_critical=True` |
| T060 | `detect_critical_tests()` | `test_parser.py` | test with "security"/"auth" in name | `is_critical=True` |
| T070 | `find_audit_block()` | `test_auditor.py` | stdout containing audit block | `AuditBlock` with `source="stdout"` |
| T080 | `find_audit_block()` | `test_auditor.py` | `.skip-audit.md` file | `AuditBlock` with `source="file"` |
| T090 | `match_test_to_audit()` | `test_auditor.py` | exact and glob patterns | `True`/`False` matches |
| T100 | `main()` | `test_integration.py` | skips, no audit | exit code 1 |
| T110 | `validate_audit()` + `main()` | `test_auditor.py`, `test_integration.py` | test not in audit | unaudited list populated, exit 1 |
| T120 | `validate_audit()` + `main()` | `test_auditor.py`, `test_integration.py` | critical + UNVERIFIED | unverified list populated, exit 1 |
| T130 | `validate_audit()` + `main()` | `test_auditor.py`, `test_integration.py` | all audited | `([], [])`, exit 0 |
| T140 | `main()` | `test_integration.py` | `--skip-gate-bypass "reason"` | WARNING logged, exit 0 |
| T150 | `main()` | `test_integration.py` | no skipped tests | pytest exit code returned |
| T160 | `main()` | `test_integration.py` | `--cov --tb=short -k name` | all flags passed through |
