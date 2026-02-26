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

# Test Plan for Issue #381

## Requirements to Cover

- REQ-T010: detect_framework_from_lld()
- REQ-T020: detect_framework_from_lld()
- REQ-T030: detect_framework_from_lld()
- REQ-T040: detect_framework_from_lld()
- REQ-T050: detect_framework_from_project()
- REQ-T060: detect_framework_from_project()
- REQ-T070: resolve_framework()
- REQ-T080: get_framework_config()
- REQ-T090: get_framework_config()
- REQ-T100: get_runner()
- REQ-T110: get_runner()
- REQ-T120: PytestRunner.validate_test_file()
- REQ-T130: PytestRunner.validate_test_file()
- REQ-T140: PlaywrightRunner.validate_test_file()
- REQ-T150: PlaywrightRunner.validate_test_file()
- REQ-T160: JestRunner.validate_test_file()
- REQ-T170: JestRunner.validate_test_file()
- REQ-T180: PlaywrightRunner.parse_results()
- REQ-T190: JestRunner.parse_results()
- REQ-T200: PytestRunner.parse_results()
- REQ-T210: compute_scenario_coverage()
- REQ-T220: PlaywrightRunner.run_tests()
- REQ-T230: JestRunner.run_tests()
- REQ-T240: PytestRunner.run_tests()
- REQ-T250: PlaywrightRunner.__init__()
- REQ-T270: determine_test_file_path()
- REQ-T280: determine_test_file_path()
- REQ-T330: Full chain
- REQ-T340: Full chain

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
- **Description:** `detect_framework_from_lld()` | `test_framework_detector.py` | LLD with `.spec.ts` pattern | `TestFramework.PLAYWRIGHT`
- **Mock needed:** False
- **Assertions:** 

### test_t020
- **Type:** unit
- **Requirement:** 
- **Description:** `detect_framework_from_lld()` | `test_framework_detector.py` | LLD with `.test.ts` and jest | `TestFramework.JEST`
- **Mock needed:** False
- **Assertions:** 

### test_t030
- **Type:** unit
- **Requirement:** 
- **Description:** `detect_framework_from_lld()` | `test_framework_detector.py` | LLD with no indicators | `TestFramework.PYTEST`
- **Mock needed:** False
- **Assertions:** 

### test_t040
- **Type:** unit
- **Requirement:** 
- **Description:** `detect_framework_from_lld()` | `test_framework_detector.py` | LLD with "Test Framework: Playwright" | `TestFramework.PLAYWRIGHT`
- **Mock needed:** False
- **Assertions:** 

### test_t050
- **Type:** unit
- **Requirement:** 
- **Description:** `detect_framework_from_project()` | `test_framework_detector.py` | Dir with `playwright.config.ts` | `TestFramework.PLAYWRIGHT`
- **Mock needed:** False
- **Assertions:** 

### test_t060
- **Type:** unit
- **Requirement:** 
- **Description:** `detect_framework_from_project()` | `test_framework_detector.py` | Dir with jest in package.json | `TestFramework.JEST`
- **Mock needed:** False
- **Assertions:** 

### test_t070
- **Type:** unit
- **Requirement:** 
- **Description:** `resolve_framework()` | `test_framework_detector.py` | LLD=Playwright, project=Jest | `TestFramework.PLAYWRIGHT`
- **Mock needed:** False
- **Assertions:** 

### test_t080
- **Type:** unit
- **Requirement:** 
- **Description:** `get_framework_config()` | `test_runner_registry.py` | `TestFramework.PLAYWRIGHT` | Config with npx playwright, .spec.ts, SCENARIO
- **Mock needed:** False
- **Assertions:** 

### test_t090
- **Type:** unit
- **Requirement:** 
- **Description:** `get_framework_config()` | `test_runner_registry.py` | `TestFramework.PYTEST` | Config with pytest, test_*.py, LINE
- **Mock needed:** False
- **Assertions:** 

### test_t100
- **Type:** unit
- **Requirement:** 
- **Description:** `get_runner()` | `test_runner_registry.py` | `TestFramework.PYTEST` | `PytestRunner` instance
- **Mock needed:** False
- **Assertions:** 

### test_t110
- **Type:** unit
- **Requirement:** 
- **Description:** `get_runner()` | `test_runner_registry.py` | `TestFramework.PLAYWRIGHT` | `PlaywrightRunner` instance
- **Mock needed:** False
- **Assertions:** 

### test_t120
- **Type:** unit
- **Requirement:** 
- **Description:** `PytestRunner.validate_test_file()` | `test_pytest_runner.py` | Valid Python test | `[]`
- **Mock needed:** False
- **Assertions:** 

### test_t130
- **Type:** unit
- **Requirement:** 
- **Description:** `PytestRunner.validate_test_file()` | `test_pytest_runner.py` | Python file, no imports | Error list
- **Mock needed:** False
- **Assertions:** 

### test_t140
- **Type:** unit
- **Requirement:** 
- **Description:** `PlaywrightRunner.validate_test_file()` | `test_playwright_runner.py` | Valid .spec.ts | `[]`
- **Mock needed:** False
- **Assertions:** 

### test_t150
- **Type:** unit
- **Requirement:** 
- **Description:** `PlaywrightRunner.validate_test_file()` | `test_playwright_runner.py` | .spec.ts missing import | Error list
- **Mock needed:** False
- **Assertions:** 

### test_t160
- **Type:** unit
- **Requirement:** 
- **Description:** `JestRunner.validate_test_file()` | `test_jest_runner.py` | Valid .test.ts | `[]`
- **Mock needed:** False
- **Assertions:** 

### test_t170
- **Type:** unit
- **Requirement:** 
- **Description:** `JestRunner.validate_test_file()` | `test_jest_runner.py` | .test.ts no describe/it | Error list
- **Mock needed:** False
- **Assertions:** 

### test_t180
- **Type:** unit
- **Requirement:** 
- **Description:** `PlaywrightRunner.parse_results()` | `test_playwright_runner.py` | Fixture JSON | Correct counts
- **Mock needed:** False
- **Assertions:** 

### test_t190
- **Type:** unit
- **Requirement:** 
- **Description:** `JestRunner.parse_results()` | `test_jest_runner.py` | Fixture JSON | Correct counts
- **Mock needed:** False
- **Assertions:** 

### test_t200
- **Type:** unit
- **Requirement:** 
- **Description:** `PytestRunner.parse_results()` | `test_pytest_runner.py` | pytest stdout | Correct counts + coverage
- **Mock needed:** False
- **Assertions:** 

### test_t210
- **Type:** unit
- **Requirement:** 
- **Description:** `compute_scenario_coverage()` | `test_check_coverage_node.py` | 35/38, 38/38, 0/0 | 92.1%, 100%, 0.0%
- **Mock needed:** False
- **Assertions:** 

### test_t220
- **Type:** unit
- **Requirement:** 
- **Description:** `PlaywrightRunner.run_tests()` | `test_playwright_runner.py` | Mocked subprocess | npx playwright test --reporter=json
- **Mock needed:** True
- **Assertions:** 

### test_t230
- **Type:** unit
- **Requirement:** 
- **Description:** `JestRunner.run_tests()` | `test_jest_runner.py` | Mocked subprocess | npx jest --json
- **Mock needed:** True
- **Assertions:** 

### test_t240
- **Type:** unit
- **Requirement:** 
- **Description:** `PytestRunner.run_tests()` | `test_pytest_runner.py` | Mocked subprocess | pytest --tb=short -q
- **Mock needed:** True
- **Assertions:** 

### test_t250
- **Type:** unit
- **Requirement:** 
- **Description:** `PlaywrightRunner.__init__()` | `test_playwright_runner.py` | npx missing | `EnvironmentError`
- **Mock needed:** False
- **Assertions:** 

### test_t260
- **Type:** unit
- **Requirement:** 
- **Description:** `run_tests()` node | `test_run_tests_node.py` | Timeout result | Graceful handling
- **Mock needed:** False
- **Assertions:** 

### test_t270
- **Type:** unit
- **Requirement:** 
- **Description:** `determine_test_file_path()` | `test_scaffold_tests_multifw.py` | Playwright config | `.spec.ts` path
- **Mock needed:** False
- **Assertions:** 

### test_t280
- **Type:** unit
- **Requirement:** 
- **Description:** `determine_test_file_path()` | `test_scaffold_tests_multifw.py` | No framework config | Not `.spec.ts`
- **Mock needed:** False
- **Assertions:** 

### test_t290
- **Type:** unit
- **Requirement:** 
- **Description:** `run_tests()` node | `test_run_tests_node.py` | Playwright state | runner.validate called
- **Mock needed:** False
- **Assertions:** 

### test_t300
- **Type:** unit
- **Requirement:** 
- **Description:** `check_coverage()` node | `test_check_coverage_node.py` | 38/38 SCENARIO | green=True
- **Mock needed:** False
- **Assertions:** 

### test_t310
- **Type:** unit
- **Requirement:** 
- **Description:** `check_coverage()` node | `test_check_coverage_node.py` | 97% LINE | green=True
- **Mock needed:** False
- **Assertions:** 

### test_t320
- **Type:** unit
- **Requirement:** 
- **Description:** `check_coverage()` node | `test_check_coverage_node.py` | NONE type | green=True
- **Mock needed:** False
- **Assertions:** 

### test_t330
- **Type:** unit
- **Requirement:** 
- **Description:** Full chain | `test_run_tests_node.py` + `test_check_coverage_node.py` | Mocked full flow | All nodes succeed
- **Mock needed:** True
- **Assertions:** 

### test_t340
- **Type:** unit
- **Requirement:** 
- **Description:** Full chain | `test_check_coverage_node.py` | Standard pytest state | Backward compat
- **Mock needed:** False
- **Assertions:** 

## Original Test Plan Section

| Test ID | Tests Function | File | Input | Expected Output |
|---------|---------------|------|-------|-----------------|
| T010 | `detect_framework_from_lld()` | `test_framework_detector.py` | LLD with `.spec.ts` pattern | `TestFramework.PLAYWRIGHT` |
| T020 | `detect_framework_from_lld()` | `test_framework_detector.py` | LLD with `.test.ts` and jest | `TestFramework.JEST` |
| T030 | `detect_framework_from_lld()` | `test_framework_detector.py` | LLD with no indicators | `TestFramework.PYTEST` |
| T040 | `detect_framework_from_lld()` | `test_framework_detector.py` | LLD with "Test Framework: Playwright" | `TestFramework.PLAYWRIGHT` |
| T050 | `detect_framework_from_project()` | `test_framework_detector.py` | Dir with `playwright.config.ts` | `TestFramework.PLAYWRIGHT` |
| T060 | `detect_framework_from_project()` | `test_framework_detector.py` | Dir with jest in package.json | `TestFramework.JEST` |
| T070 | `resolve_framework()` | `test_framework_detector.py` | LLD=Playwright, project=Jest | `TestFramework.PLAYWRIGHT` |
| T080 | `get_framework_config()` | `test_runner_registry.py` | `TestFramework.PLAYWRIGHT` | Config with npx playwright, .spec.ts, SCENARIO |
| T090 | `get_framework_config()` | `test_runner_registry.py` | `TestFramework.PYTEST` | Config with pytest, test_*.py, LINE |
| T100 | `get_runner()` | `test_runner_registry.py` | `TestFramework.PYTEST` | `PytestRunner` instance |
| T110 | `get_runner()` | `test_runner_registry.py` | `TestFramework.PLAYWRIGHT` | `PlaywrightRunner` instance |
| T120 | `PytestRunner.validate_test_file()` | `test_pytest_runner.py` | Valid Python test | `[]` |
| T130 | `PytestRunner.validate_test_file()` | `test_pytest_runner.py` | Python file, no imports | Error list |
| T140 | `PlaywrightRunner.validate_test_file()` | `test_playwright_runner.py` | Valid .spec.ts | `[]` |
| T150 | `PlaywrightRunner.validate_test_file()` | `test_playwright_runner.py` | .spec.ts missing import | Error list |
| T160 | `JestRunner.validate_test_file()` | `test_jest_runner.py` | Valid .test.ts | `[]` |
| T170 | `JestRunner.validate_test_file()` | `test_jest_runner.py` | .test.ts no describe/it | Error list |
| T180 | `PlaywrightRunner.parse_results()` | `test_playwright_runner.py` | Fixture JSON | Correct counts |
| T190 | `JestRunner.parse_results()` | `test_jest_runner.py` | Fixture JSON | Correct counts |
| T200 | `PytestRunner.parse_results()` | `test_pytest_runner.py` | pytest stdout | Correct counts + coverage |
| T210 | `compute_scenario_coverage()` | `test_check_coverage_node.py` | 35/38, 38/38, 0/0 | 92.1%, 100%, 0.0% |
| T220 | `PlaywrightRunner.run_tests()` | `test_playwright_runner.py` | Mocked subprocess | npx playwright test --reporter=json |
| T230 | `JestRunner.run_tests()` | `test_jest_runner.py` | Mocked subprocess | npx jest --json |
| T240 | `PytestRunner.run_tests()` | `test_pytest_runner.py` | Mocked subprocess | pytest --tb=short -q |
| T250 | `PlaywrightRunner.__init__()` | `test_playwright_runner.py` | npx missing | `EnvironmentError` |
| T260 | `run_tests()` node | `test_run_tests_node.py` | Timeout result | Graceful handling |
| T270 | `determine_test_file_path()` | `test_scaffold_tests_multifw.py` | Playwright config | `.spec.ts` path |
| T280 | `determine_test_file_path()` | `test_scaffold_tests_multifw.py` | No framework config | Not `.spec.ts` |
| T290 | `run_tests()` node | `test_run_tests_node.py` | Playwright state | runner.validate called |
| T300 | `check_coverage()` node | `test_check_coverage_node.py` | 38/38 SCENARIO | green=True |
| T310 | `check_coverage()` node | `test_check_coverage_node.py` | 97% LINE | green=True |
| T320 | `check_coverage()` node | `test_check_coverage_node.py` | NONE type | green=True |
| T330 | Full chain | `test_run_tests_node.py` + `test_check_coverage_node.py` | Mocked full flow | All nodes succeed |
| T340 | Full chain | `test_check_coverage_node.py` | Standard pytest state | Backward compat |
