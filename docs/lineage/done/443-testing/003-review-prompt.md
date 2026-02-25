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

# Test Plan for Issue #443

## Requirements to Cover

- REQ-T010: estimate_iteration_cost()
- REQ-T020: estimate_iteration_cost()
- REQ-T030: estimate_iteration_cost()
- REQ-T040: estimate_iteration_cost()
- REQ-T050: check_circuit_breaker()
- REQ-T060: check_circuit_breaker()
- REQ-T070: check_circuit_breaker()
- REQ-T080: check_circuit_breaker()
- REQ-T090: check_circuit_breaker()
- REQ-T100: record_iteration_cost()
- REQ-T110: record_iteration_cost()
- REQ-T120: record_iteration_cost()
- REQ-T130: record_iteration_cost()
- REQ-T140: budget_summary()
- REQ-T150: budget_summary()
- REQ-T160: budget_summary()
- REQ-T170: budget_summary()
- REQ-T180: check_circuit_breaker()
- REQ-T190: check_circuit_breaker()
- REQ-T200: All 4 functions
- REQ-T210: All 4 functions (except record)
- REQ-T220: Module import
- REQ-T230: Source inspection
- REQ-T240: inspect.getmembers()
- REQ-T250: Module import

## Detected Test Types

- browser
- e2e
- integration
- mobile
- performance
- terminal
- unit

## Required Tools

- appium
- click.testing
- detox
- docker-compose
- locust
- pexpect
- playwright
- pytest
- pytest-benchmark
- selenium

## Mock Guidance

**Browser/UI Tests:** Real browser required, mock backend APIs for isolation
**End-to-End Tests:** Minimal mocking - test against real (sandboxed) systems
**Integration Tests:** Use test doubles for external services, real DB where possible
**Mobile App Tests:** Use emulators/simulators, mock backend services
**Performance Tests:** Test against representative data volumes
**Terminal/CLI Tests:** Use CliRunner or capture stdout/stderr
**Unit Tests:** Mock external dependencies (APIs, DB, filesystem)

## Coverage Target

95%

## Test Scenarios

### test_t010
- **Type:** unit
- **Requirement:** 
- **Description:** `estimate_iteration_cost()` | `empty_state` fixture | `float >= 0.0`
- **Mock needed:** False
- **Assertions:** 

### test_t020
- **Type:** unit
- **Requirement:** 
- **Description:** `estimate_iteration_cost()` | `mid_budget_state` fixture | `float >= 0.0` reflecting activity
- **Mock needed:** False
- **Assertions:** 

### test_t030
- **Type:** unit
- **Requirement:** 
- **Description:** `estimate_iteration_cost()` | Arbitrary valid state | `isinstance(result, (int, float))`
- **Mock needed:** False
- **Assertions:** 

### test_t040
- **Type:** unit
- **Requirement:** 
- **Description:** `estimate_iteration_cost()` | Low vs high activity states | `high >= low`
- **Mock needed:** False
- **Assertions:** 

### test_t050
- **Type:** unit
- **Requirement:** 
- **Description:** `check_circuit_breaker()` | `empty_state` fixture | `tripped is False`
- **Mock needed:** False
- **Assertions:** 

### test_t060
- **Type:** unit
- **Requirement:** 
- **Description:** `check_circuit_breaker()` | `mid_budget_state` fixture | `tripped is False`
- **Mock needed:** False
- **Assertions:** 

### test_t070
- **Type:** unit
- **Requirement:** 
- **Description:** `check_circuit_breaker()` | `over_budget_state` fixture | `tripped is True`
- **Mock needed:** False
- **Assertions:** 

### test_t080
- **Type:** unit
- **Requirement:** 
- **Description:** `check_circuit_breaker()` | State at `iteration == max_iterations` | `tripped is True`
- **Mock needed:** False
- **Assertions:** 

### test_t090
- **Type:** unit
- **Requirement:** 
- **Description:** `check_circuit_breaker()` | Any valid state | Return has bool + str
- **Mock needed:** False
- **Assertions:** 

### test_t100
- **Type:** unit
- **Requirement:** 
- **Description:** `record_iteration_cost()` | `empty_state` + `1.50` | `spent_dollars == 1.50`
- **Mock needed:** False
- **Assertions:** 

### test_t110
- **Type:** unit
- **Requirement:** 
- **Description:** `record_iteration_cost()` | `empty_state` + 3×`1.0` | `spent_dollars == 3.0`
- **Mock needed:** False
- **Assertions:** 

### test_t120
- **Type:** unit
- **Requirement:** 
- **Description:** `record_iteration_cost()` | `empty_state` + `0.0` | `spent_dollars` unchanged
- **Mock needed:** False
- **Assertions:** 

### test_t130
- **Type:** unit
- **Requirement:** 
- **Description:** `record_iteration_cost()` | `mid_budget_state` + `0.50` | Non-cost fields unchanged
- **Mock needed:** False
- **Assertions:** 

### test_t140
- **Type:** unit
- **Requirement:** 
- **Description:** `budget_summary()` | `empty_state` fixture | Non-empty `str`
- **Mock needed:** False
- **Assertions:** 

### test_t150
- **Type:** unit
- **Requirement:** 
- **Description:** `budget_summary()` | `mid_budget_state` fixture | Contains budget numbers
- **Mock needed:** False
- **Assertions:** 

### test_t160
- **Type:** unit
- **Requirement:** 
- **Description:** `budget_summary()` | State with `budget_dollars=0` | No exception, returns `str`
- **Mock needed:** False
- **Assertions:** 

### test_t170
- **Type:** unit
- **Requirement:** 
- **Description:** `budget_summary()` | State with `budget_dollars=1e12` | No exception, returns `str`
- **Mock needed:** False
- **Assertions:** 

### test_t180
- **Type:** unit
- **Requirement:** 
- **Description:** `check_circuit_breaker()` | Zero budget state | `tripped is True`
- **Mock needed:** False
- **Assertions:** 

### test_t190
- **Type:** unit
- **Requirement:** 
- **Description:** `check_circuit_breaker()` | Huge budget state | `tripped is False`
- **Mock needed:** False
- **Assertions:** 

### test_t200
- **Type:** unit
- **Requirement:** 
- **Description:** All 4 functions | State with `spent_dollars=-5.0` | No unhandled exception
- **Mock needed:** False
- **Assertions:** 

### test_t210
- **Type:** unit
- **Requirement:** 
- **Description:** All 4 functions (except record) | `{}` empty dict | No unhandled crash
- **Mock needed:** False
- **Assertions:** 

### test_t220
- **Type:** unit
- **Requirement:** 
- **Description:** Module import | N/A | Import succeeds, no network libs
- **Mock needed:** True
- **Assertions:** 

### test_t230
- **Type:** unit
- **Requirement:** 
- **Description:** Source inspection | N/A | No HTTP URL patterns
- **Mock needed:** False
- **Assertions:** 

### test_t240
- **Type:** unit
- **Requirement:** 
- **Description:** `inspect.getmembers()` | Module object | All public funcs are tested
- **Mock needed:** False
- **Assertions:** 

### test_t250
- **Type:** unit
- **Requirement:** 
- **Description:** Module import | N/A | Clean import, no side effects
- **Mock needed:** False
- **Assertions:** 

## Original Test Plan Section

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `estimate_iteration_cost()` | `empty_state` fixture | `float >= 0.0` |
| T020 | `estimate_iteration_cost()` | `mid_budget_state` fixture | `float >= 0.0` reflecting activity |
| T030 | `estimate_iteration_cost()` | Arbitrary valid state | `isinstance(result, (int, float))` |
| T040 | `estimate_iteration_cost()` | Low vs high activity states | `high >= low` |
| T050 | `check_circuit_breaker()` | `empty_state` fixture | `tripped is False` |
| T060 | `check_circuit_breaker()` | `mid_budget_state` fixture | `tripped is False` |
| T070 | `check_circuit_breaker()` | `over_budget_state` fixture | `tripped is True` |
| T080 | `check_circuit_breaker()` | State at `iteration == max_iterations` | `tripped is True` |
| T090 | `check_circuit_breaker()` | Any valid state | Return has bool + str |
| T100 | `record_iteration_cost()` | `empty_state` + `1.50` | `spent_dollars == 1.50` |
| T110 | `record_iteration_cost()` | `empty_state` + 3×`1.0` | `spent_dollars == 3.0` |
| T120 | `record_iteration_cost()` | `empty_state` + `0.0` | `spent_dollars` unchanged |
| T130 | `record_iteration_cost()` | `mid_budget_state` + `0.50` | Non-cost fields unchanged |
| T140 | `budget_summary()` | `empty_state` fixture | Non-empty `str` |
| T150 | `budget_summary()` | `mid_budget_state` fixture | Contains budget numbers |
| T160 | `budget_summary()` | State with `budget_dollars=0` | No exception, returns `str` |
| T170 | `budget_summary()` | State with `budget_dollars=1e12` | No exception, returns `str` |
| T180 | `check_circuit_breaker()` | Zero budget state | `tripped is True` |
| T190 | `check_circuit_breaker()` | Huge budget state | `tripped is False` |
| T200 | All 4 functions | State with `spent_dollars=-5.0` | No unhandled exception |
| T210 | All 4 functions (except record) | `{}` empty dict | No unhandled crash |
| T220 | Module import | N/A | Import succeeds, no network libs |
| T230 | Source inspection | N/A | No HTTP URL patterns |
| T240 | `inspect.getmembers()` | Module object | All public funcs are tested |
| T250 | Module import | N/A | Clean import, no side effects |
