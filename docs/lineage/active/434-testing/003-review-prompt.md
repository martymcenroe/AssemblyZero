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

# Test Plan for Issue #434

## Requirements to Cover

- REQ-T010: strip_ansi_codes()
- REQ-T020: strip_ansi_codes()
- REQ-T030: strip_ansi_codes()
- REQ-T040: strip_ansi_codes()
- REQ-T050: strip_ansi_codes()
- REQ-T060: parse_token_count()
- REQ-T070: parse_token_count()
- REQ-T080: parse_token_count()
- REQ-T090: parse_token_count()
- REQ-T100: parse_token_count()
- REQ-T110: parse_cost_value()
- REQ-T120: parse_cost_value()
- REQ-T130: parse_cost_value()
- REQ-T140: parse_cost_value()
- REQ-T150: parse_cost_value()
- REQ-T160: extract_usage_line()
- REQ-T170: extract_usage_line()
- REQ-T180: extract_usage_line()
- REQ-T190: extract_usage_line()
- REQ-T200: extract_model_name()
- REQ-T210: extract_model_name()
- REQ-T220: extract_model_name()
- REQ-T230: extract_model_name()
- REQ-T240: extract_model_name()
- REQ-T250: parse_usage_block()
- REQ-T260: parse_usage_block()
- REQ-T270: parse_usage_block()
- REQ-T280: parse_usage_block()
- REQ-T290: parse_usage_block()
- REQ-T300: parse_usage_data()
- REQ-T310: Module import
- REQ-T320: strip_ansi_codes()
- REQ-T330: parse_usage_block()
- REQ-T340: All parsing functions
- REQ-T350: All parsing functions

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

### test_t010
- **Type:** unit
- **Requirement:** 
- **Description:** `strip_ansi_codes()` | `"\033[32mGreen\033[0m"` | `"Green"`
- **Mock needed:** False
- **Assertions:** 

### test_t020
- **Type:** unit
- **Requirement:** 
- **Description:** `strip_ansi_codes()` | `"\033[1m\033[31mBold Red\033[0m"` | `"Bold Red"`
- **Mock needed:** False
- **Assertions:** 

### test_t030
- **Type:** unit
- **Requirement:** 
- **Description:** `strip_ansi_codes()` | `"plain text"` | `"plain text"`
- **Mock needed:** False
- **Assertions:** 

### test_t040
- **Type:** unit
- **Requirement:** 
- **Description:** `strip_ansi_codes()` | `""` | `""`
- **Mock needed:** False
- **Assertions:** 

### test_t050
- **Type:** unit
- **Requirement:** 
- **Description:** `strip_ansi_codes()` | `"\033[2J\033[HText"` | `"Text"`
- **Mock needed:** False
- **Assertions:** 

### test_t060
- **Type:** unit
- **Requirement:** 
- **Description:** `parse_token_count()` | `"1234"` | `1234`
- **Mock needed:** False
- **Assertions:** 

### test_t070
- **Type:** unit
- **Requirement:** 
- **Description:** `parse_token_count()` | `"1,234,567"` | `1234567`
- **Mock needed:** False
- **Assertions:** 

### test_t080
- **Type:** unit
- **Requirement:** 
- **Description:** `parse_token_count()` | `" 500 "` | `500`
- **Mock needed:** False
- **Assertions:** 

### test_t090
- **Type:** unit
- **Requirement:** 
- **Description:** `parse_token_count()` | `"0"` | `0`
- **Mock needed:** False
- **Assertions:** 

### test_t100
- **Type:** unit
- **Requirement:** 
- **Description:** `parse_token_count()` | `"abc"` | Raises `ValueError`
- **Mock needed:** False
- **Assertions:** 

### test_t110
- **Type:** unit
- **Requirement:** 
- **Description:** `parse_cost_value()` | `"$0.0042"` | `0.0042`
- **Mock needed:** False
- **Assertions:** 

### test_t120
- **Type:** unit
- **Requirement:** 
- **Description:** `parse_cost_value()` | `"0.0042"` | `0.0042`
- **Mock needed:** False
- **Assertions:** 

### test_t130
- **Type:** unit
- **Requirement:** 
- **Description:** `parse_cost_value()` | `"$0.00"` | `0.0`
- **Mock needed:** False
- **Assertions:** 

### test_t140
- **Type:** unit
- **Requirement:** 
- **Description:** `parse_cost_value()` | `" $1.23 "` | `1.23`
- **Mock needed:** False
- **Assertions:** 

### test_t150
- **Type:** unit
- **Requirement:** 
- **Description:** `parse_cost_value()` | `"free"` | Raises `ValueError`
- **Mock needed:** False
- **Assertions:** 

### test_t160
- **Type:** unit
- **Requirement:** 
- **Description:** `extract_usage_line()` | `CLEAN_USAGE_LINE` fixture | `UsageRecord` with `session_id="abc123"`, `input_tokens=15234`, etc.
- **Mock needed:** False
- **Assertions:** 

### test_t170
- **Type:** unit
- **Requirement:** 
- **Description:** `extract_usage_line()` | `ANSI_USAGE_LINE` fixture | Same `UsageRecord` as T160
- **Mock needed:** False
- **Assertions:** 

### test_t180
- **Type:** unit
- **Requirement:** 
- **Description:** `extract_usage_line()` | `"Starting session..."` | `None`
- **Mock needed:** False
- **Assertions:** 

### test_t190
- **Type:** unit
- **Requirement:** 
- **Description:** `extract_usage_line()` | `"abc123  claude-sonnet"` | `None`
- **Mock needed:** False
- **Assertions:** 

### test_t200
- **Type:** unit
- **Requirement:** 
- **Description:** `extract_model_name()` | `"model: claude-sonnet-4-20250514"` | `"claude-sonnet-4-20250514"`
- **Mock needed:** False
- **Assertions:** 

### test_t210
- **Type:** unit
- **Requirement:** 
- **Description:** `extract_model_name()` | `"model: claude-opus-4-20250514"` | `"claude-opus-4-20250514"`
- **Mock needed:** False
- **Assertions:** 

### test_t220
- **Type:** unit
- **Requirement:** 
- **Description:** `extract_model_name()` | `"model: claude-haiku-3-20250514"` | `"claude-haiku-3-20250514"`
- **Mock needed:** False
- **Assertions:** 

### test_t230
- **Type:** unit
- **Requirement:** 
- **Description:** `extract_model_name()` | `"no model info here"` | `None`
- **Mock needed:** False
- **Assertions:** 

### test_t240
- **Type:** unit
- **Requirement:** 
- **Description:** `extract_model_name()` | Two model strings in one text | `"claude-sonnet-4-20250514"` (first match)
- **Mock needed:** False
- **Assertions:** 

### test_t250
- **Type:** unit
- **Requirement:** 
- **Description:** `parse_usage_block()` | `FULL_USAGE_BLOCK` fixture | List of 2 `UsageRecord`s
- **Mock needed:** False
- **Assertions:** 

### test_t260
- **Type:** unit
- **Requirement:** 
- **Description:** `parse_usage_block()` | `MIXED_BLOCK` fixture | List of 2 records (skips non-matching)
- **Mock needed:** False
- **Assertions:** 

### test_t270
- **Type:** unit
- **Requirement:** 
- **Description:** `parse_usage_block()` | `""` | `[]`
- **Mock needed:** False
- **Assertions:** 

### test_t280
- **Type:** unit
- **Requirement:** 
- **Description:** `parse_usage_block()` | `ANSI_FULL_BLOCK` fixture | List of 2 records (same as clean)
- **Mock needed:** False
- **Assertions:** 

### test_t290
- **Type:** unit
- **Requirement:** 
- **Description:** `parse_usage_block()` | Single clean usage line | List of 1 record
- **Mock needed:** False
- **Assertions:** 

### test_t300
- **Type:** unit
- **Requirement:** 
- **Description:** `parse_usage_data()` | `golden_input.txt` content | Matches `golden_output.txt` (excluding volatile `timestamp` field)
- **Mock needed:** False
- **Assertions:** 

### test_t310
- **Type:** unit
- **Requirement:** 
- **Description:** Module import | `importlib.util.spec_from_file_location` + `exec_module` | No stdout output
- **Mock needed:** False
- **Assertions:** 

### test_t320
- **Type:** unit
- **Requirement:** 
- **Description:** `strip_ansi_codes()` | `ANSI_USAGE_LINE` fixture | `ANSI_USAGE_LINE_EXPECTED_CLEAN`
- **Mock needed:** False
- **Assertions:** 

### test_t330
- **Type:** unit
- **Requirement:** 
- **Description:** `parse_usage_block()` | `FULL_USAGE_BLOCK` fixture | `FULL_USAGE_BLOCK_EXPECTED` all fields match
- **Mock needed:** False
- **Assertions:** 

### test_t340
- **Type:** unit
- **Requirement:** 
- **Description:** All parsing functions | Various inputs with socket blocked | Zero `socket.connect` calls
- **Mock needed:** False
- **Assertions:** 

### test_t350
- **Type:** unit
- **Requirement:** 
- **Description:** All parsing functions | >10k char adversarial strings | Completes < 100ms, correct result
- **Mock needed:** False
- **Assertions:** 

## Original Test Plan Section

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `strip_ansi_codes()` | `"\033[32mGreen\033[0m"` | `"Green"` |
| T020 | `strip_ansi_codes()` | `"\033[1m\033[31mBold Red\033[0m"` | `"Bold Red"` |
| T030 | `strip_ansi_codes()` | `"plain text"` | `"plain text"` |
| T040 | `strip_ansi_codes()` | `""` | `""` |
| T050 | `strip_ansi_codes()` | `"\033[2J\033[HText"` | `"Text"` |
| T060 | `parse_token_count()` | `"1234"` | `1234` |
| T070 | `parse_token_count()` | `"1,234,567"` | `1234567` |
| T080 | `parse_token_count()` | `" 500 "` | `500` |
| T090 | `parse_token_count()` | `"0"` | `0` |
| T100 | `parse_token_count()` | `"abc"` | Raises `ValueError` |
| T110 | `parse_cost_value()` | `"$0.0042"` | `0.0042` |
| T120 | `parse_cost_value()` | `"0.0042"` | `0.0042` |
| T130 | `parse_cost_value()` | `"$0.00"` | `0.0` |
| T140 | `parse_cost_value()` | `" $1.23 "` | `1.23` |
| T150 | `parse_cost_value()` | `"free"` | Raises `ValueError` |
| T160 | `extract_usage_line()` | `CLEAN_USAGE_LINE` fixture | `UsageRecord` with `session_id="abc123"`, `input_tokens=15234`, etc. |
| T170 | `extract_usage_line()` | `ANSI_USAGE_LINE` fixture | Same `UsageRecord` as T160 |
| T180 | `extract_usage_line()` | `"Starting session..."` | `None` |
| T190 | `extract_usage_line()` | `"abc123  claude-sonnet"` | `None` |
| T200 | `extract_model_name()` | `"model: claude-sonnet-4-20250514"` | `"claude-sonnet-4-20250514"` |
| T210 | `extract_model_name()` | `"model: claude-opus-4-20250514"` | `"claude-opus-4-20250514"` |
| T220 | `extract_model_name()` | `"model: claude-haiku-3-20250514"` | `"claude-haiku-3-20250514"` |
| T230 | `extract_model_name()` | `"no model info here"` | `None` |
| T240 | `extract_model_name()` | Two model strings in one text | `"claude-sonnet-4-20250514"` (first match) |
| T250 | `parse_usage_block()` | `FULL_USAGE_BLOCK` fixture | List of 2 `UsageRecord`s |
| T260 | `parse_usage_block()` | `MIXED_BLOCK` fixture | List of 2 records (skips non-matching) |
| T270 | `parse_usage_block()` | `""` | `[]` |
| T280 | `parse_usage_block()` | `ANSI_FULL_BLOCK` fixture | List of 2 records (same as clean) |
| T290 | `parse_usage_block()` | Single clean usage line | List of 1 record |
| T300 | `parse_usage_data()` | `golden_input.txt` content | Matches `golden_output.txt` (excluding volatile `timestamp` field) |
| T310 | Module import | `importlib.util.spec_from_file_location` + `exec_module` | No stdout output |
| T320 | `strip_ansi_codes()` | `ANSI_USAGE_LINE` fixture | `ANSI_USAGE_LINE_EXPECTED_CLEAN` |
| T330 | `parse_usage_block()` | `FULL_USAGE_BLOCK` fixture | `FULL_USAGE_BLOCK_EXPECTED` all fields match |
| T340 | All parsing functions | Various inputs with socket blocked | Zero `socket.connect` calls |
| T350 | All parsing functions | >10k char adversarial strings | Completes < 100ms, correct result |
