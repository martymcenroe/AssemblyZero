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

# Test Plan for Issue #444

## Requirements to Cover



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
- **Description:** Tests Phase | Invocation | Expected Output Characteristics
- **Mock needed:** False
- **Assertions:** 

### test_t010_scenario_010
- **Type:** unit
- **Requirement:** 
- **Description:** Backward compat | `/test-gaps` | Layer 1 output only; no Layer 2/3 headings; structure identical to pre-change
- **Mock needed:** False
- **Assertions:** 

### test_t020_scenario_020
- **Type:** unit
- **Requirement:** 
- **Description:** Layer 2 CI analysis | `/test-gaps --layer infra` | CI findings table with at least one check; header shows project type
- **Mock needed:** False
- **Assertions:** 

### test_t030_scenario_030
- **Type:** unit
- **Requirement:** 
- **Description:** Layer 2 skip audit | `/test-gaps --layer infra` | Skip audit table with classifications
- **Mock needed:** False
- **Assertions:** 

### test_t040_scenario_040
- **Type:** unit
- **Requirement:** 
- **Description:** Layer 2 pyramid | `/test-gaps --layer infra` | Pyramid visualization with counts and percentages
- **Mock needed:** False
- **Assertions:** 

### test_t050_scenario_050
- **Type:** unit
- **Requirement:** 
- **Description:** Layer 3 auto-detection | `/test-gaps --layer heuristics` | Header shows detected project type with "(auto)"
- **Mock needed:** False
- **Assertions:** 

### test_t060_scenario_060
- **Type:** unit
- **Requirement:** 
- **Description:** Project type override | `/test-gaps --layer heuristics --project-type api` | Header shows "api (override)"; API checks run
- **Mock needed:** True
- **Assertions:** 

### test_t070_scenario_070
- **Type:** unit
- **Requirement:** 
- **Description:** Report quality | `/test-gaps --layer heuristics` | Report Quality table with scores
- **Mock needed:** False
- **Assertions:** 

### test_t080_scenario_080
- **Type:** unit
- **Requirement:** 
- **Description:** Full output structure | `/test-gaps --full` | All 3 layer headings; Recommended Actions sorted CRITICAL→LOW; Issues to Create with only HIGH+ items
- **Mock needed:** False
- **Assertions:** 

### test_t090_scenario_090
- **Type:** unit
- **Requirement:** 
- **Description:** Cost ceiling | `/test-gaps --full` | Completes within 50 tool calls
- **Mock needed:** False
- **Assertions:** 

### test_t100_scenario_100
- **Type:** unit
- **Requirement:** 
- **Description:** All argument flags | Various | Each flag produces correct routing
- **Mock needed:** False
- **Assertions:** 

### test_t110_scenario_110
- **Type:** unit
- **Requirement:** 
- **Description:** No workflows | `/test-gaps --layer infra` (no .github/workflows/) | "No CI workflows found" message, no error
- **Mock needed:** False
- **Assertions:** 

### test_t120_scenario_120
- **Type:** unit
- **Requirement:** 
- **Description:** Generic fallback | `/test-gaps --layer heuristics` (no markers) | "generic (auto)" in header; "no heuristic checks available" note
- **Mock needed:** False
- **Assertions:** 

## Original Test Plan Section

*Map each LLD test scenario to the specific skill behavior it validates.*

| Test ID | Tests Phase | Invocation | Expected Output Characteristics |
|---------|------------|------------|-------------------------------|
| T010 / Scenario 010 | Backward compat | `/test-gaps` | Layer 1 output only; no Layer 2/3 headings; structure identical to pre-change |
| T020 / Scenario 020 | Layer 2 CI analysis | `/test-gaps --layer infra` | CI findings table with at least one check; header shows project type |
| T030 / Scenario 030 | Layer 2 skip audit | `/test-gaps --layer infra` | Skip audit table with classifications |
| T040 / Scenario 040 | Layer 2 pyramid | `/test-gaps --layer infra` | Pyramid visualization with counts and percentages |
| T050 / Scenario 050 | Layer 3 auto-detection | `/test-gaps --layer heuristics` | Header shows detected project type with "(auto)" |
| T060 / Scenario 060 | Project type override | `/test-gaps --layer heuristics --project-type api` | Header shows "api (override)"; API checks run |
| T070 / Scenario 070 | Report quality | `/test-gaps --layer heuristics` | Report Quality table with scores |
| T080 / Scenario 080 | Full output structure | `/test-gaps --full` | All 3 layer headings; Recommended Actions sorted CRITICAL→LOW; Issues to Create with only HIGH+ items |
| T090 / Scenario 090 | Cost ceiling | `/test-gaps --full` | Completes within 50 tool calls |
| T100 / Scenario 100 | All argument flags | Various | Each flag produces correct routing |
| T110 / Scenario 110 | No workflows | `/test-gaps --layer infra` (no .github/workflows/) | "No CI workflows found" message, no error |
| T120 / Scenario 120 | Generic fallback | `/test-gaps --layer heuristics` (no markers) | "generic (auto)" in header; "no heuristic checks available" note |

**Verification Method:** All tests are manual — run the skill in a Claude Code session and inspect output. See LLD Section 10.3 for justification.
