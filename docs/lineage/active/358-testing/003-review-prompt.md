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

# Test Plan for Issue #358

## Requirements to Cover

- REQ-T010: detect_cascade_risk()
- REQ-T020: detect_cascade_risk()
- REQ-T040: detect_cascade_risk()
- REQ-T050: detect_cascade_risk()
- REQ-T060: detect_cascade_risk()
- REQ-T080: detect_cascade_risk()
- REQ-T090: log_cascade_event()
- REQ-T100: merge_patterns()
- REQ-T110: detect_cascade_risk()
- REQ-T120: detect_cascade_risk()
- REQ-T130: format_block_message()
- REQ-T140: get_cascade_stats()
- REQ-T160: handle_cascade_detection()
- REQ-T170: create_cascade_event()
- REQ-T180: load_user_patterns()
- REQ-T190: merge_patterns()
- REQ-T200: detect_cascade_risk()
- REQ-T210: detect_cascade_risk()
- REQ-T260: validate_claude_md_cascade_rule()
- REQ-T270: validate_claude_md_cascade_rule()
- REQ-T280: validate_claude_md_cascade_rule()

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
- **Description:** `detect_cascade_risk()` | `"Great, issue #42 is fixed! Should I continue with issue #43?"` | `detected=True, risk_level>=MEDIUM`
- **Mock needed:** False
- **Assertions:** 

### test_t020
- **Type:** unit
- **Requirement:** 
- **Description:** `detect_cascade_risk()` | `"Done! What's next?\n1. Yes, start issue #44\n2. No, stop here"` | `risk_level=CRITICAL, action=block_and_alert`
- **Mock needed:** False
- **Assertions:** 

### test_t030
- **Type:** unit
- **Requirement:** 
- **Description:** `detect_cascade_risk()`, `is_permission_prompt()` | `"Allow bash command: git push origin main? (y/n)"` | `detected=False, action=allow`
- **Mock needed:** False
- **Assertions:** 

### test_t040
- **Type:** unit
- **Requirement:** 
- **Description:** `detect_cascade_risk()` | `"I've completed the refactor. Now let me also update the tests..."` | `detected=True, risk_level>=MEDIUM`
- **Mock needed:** False
- **Assertions:** 

### test_t050
- **Type:** unit
- **Requirement:** 
- **Description:** `detect_cascade_risk()` | `"While I'm at it, I could also fix the related CSS issue..."` | `detected=True, risk_level>=MEDIUM`
- **Mock needed:** False
- **Assertions:** 

### test_t060
- **Type:** unit
- **Requirement:** 
- **Description:** `detect_cascade_risk()` | `""` and `None` | `detected=False, risk_level=NONE`
- **Mock needed:** False
- **Assertions:** 

### test_t070
- **Type:** unit
- **Requirement:** 
- **Description:** `load_user_patterns()`, `load_default_patterns()` | Corrupt JSON file | Empty user patterns, 15+ defaults, no crash
- **Mock needed:** False
- **Assertions:** 

### test_t080
- **Type:** unit
- **Requirement:** 
- **Description:** `detect_cascade_risk()` | `"a"*10000 + " Should I " + "b"*10000` | Completes in <100ms
- **Mock needed:** False
- **Assertions:** 

### test_t090
- **Type:** unit
- **Requirement:** 
- **Description:** `log_cascade_event()` | Valid CascadeEvent | JSONL file with all fields
- **Mock needed:** False
- **Assertions:** 

### test_t100
- **Type:** unit
- **Requirement:** 
- **Description:** `merge_patterns()` | Default CP-001 + user CP-001 | User regex used
- **Mock needed:** False
- **Assertions:** 

### test_t110
- **Type:** unit
- **Requirement:** 
- **Description:** `detect_cascade_risk()` | `"Should I format this differently?"` | `action=allow`
- **Mock needed:** False
- **Assertions:** 

### test_t120
- **Type:** unit
- **Requirement:** 
- **Description:** `detect_cascade_risk()` | Single-category vs multi-category text | Multi score > single score
- **Mock needed:** False
- **Assertions:** 

### test_t130
- **Type:** unit
- **Requirement:** 
- **Description:** `format_block_message()` | HIGH risk result | Contains "cascade", risk level, pattern IDs
- **Mock needed:** False
- **Assertions:** 

### test_t140
- **Type:** unit
- **Requirement:** 
- **Description:** `get_cascade_stats()` | Log with 5 events (3 blocked, 2 allowed) | `{total_checks: 5, detections: 3, blocks: 3, allowed: 2}`
- **Mock needed:** False
- **Assertions:** 

### test_t150
- **Type:** unit
- **Requirement:** 
- **Description:** `main()` via subprocess | JSON hook input with cascade/clean text | exit(2) for cascade, exit(0) for clean
- **Mock needed:** False
- **Assertions:** 

### test_t160
- **Type:** unit
- **Requirement:** 
- **Description:** `handle_cascade_detection()` | MEDIUM risk result | Returns `False`
- **Mock needed:** False
- **Assertions:** 

### test_t170
- **Type:** unit
- **Requirement:** 
- **Description:** `create_cascade_event()` | HIGH risk result | All 8 CascadeEvent fields present
- **Mock needed:** False
- **Assertions:** 

### test_t180
- **Type:** unit
- **Requirement:** 
- **Description:** `load_user_patterns()` | Valid JSON with 2 patterns | Returns 2 patterns
- **Mock needed:** False
- **Assertions:** 

### test_t190
- **Type:** unit
- **Requirement:** 
- **Description:** `merge_patterns()` | Default CP-001 regex A + user CP-001 regex B | Merged CP-001 has regex B
- **Mock needed:** False
- **Assertions:** 

### test_t200
- **Type:** unit
- **Requirement:** 
- **Description:** `detect_cascade_risk()` | 2000-char text, 100 runs | Average <5ms
- **Mock needed:** False
- **Assertions:** 

### test_t210
- **Type:** unit
- **Requirement:** 
- **Description:** `detect_cascade_risk()` | 10000-char text, 100 runs | Average <5ms
- **Mock needed:** False
- **Assertions:** 

### test_t260
- **Type:** unit
- **Requirement:** 
- **Description:** `validate_claude_md_cascade_rule()` | `CLAUDE.md` | `rule_present=True`
- **Mock needed:** False
- **Assertions:** 

### test_t270
- **Type:** unit
- **Requirement:** 
- **Description:** `validate_claude_md_cascade_rule()` | `CLAUDE.md` | `contains_open_ended=True, forbids_numbered_options=True`
- **Mock needed:** False
- **Assertions:** 

### test_t280
- **Type:** unit
- **Requirement:** 
- **Description:** `validate_claude_md_cascade_rule()` | `CLAUDE.md` | `section_correct=True`
- **Mock needed:** False
- **Assertions:** 

## Original Test Plan Section

| Test ID | Tests Function(s) | Input | Expected Output |
|---------|-------------------|-------|-----------------|
| T010 | `detect_cascade_risk()` | `"Great, issue #42 is fixed! Should I continue with issue #43?"` | `detected=True, risk_level>=MEDIUM` |
| T020 | `detect_cascade_risk()` | `"Done! What's next?\n1. Yes, start issue #44\n2. No, stop here"` | `risk_level=CRITICAL, action=block_and_alert` |
| T030 | `detect_cascade_risk()`, `is_permission_prompt()` | `"Allow bash command: git push origin main? (y/n)"` | `detected=False, action=allow` |
| T040 | `detect_cascade_risk()` | `"I've completed the refactor. Now let me also update the tests..."` | `detected=True, risk_level>=MEDIUM` |
| T050 | `detect_cascade_risk()` | `"While I'm at it, I could also fix the related CSS issue..."` | `detected=True, risk_level>=MEDIUM` |
| T060 | `detect_cascade_risk()` | `""` and `None` | `detected=False, risk_level=NONE` |
| T070 | `load_user_patterns()`, `load_default_patterns()` | Corrupt JSON file | Empty user patterns, 15+ defaults, no crash |
| T080 | `detect_cascade_risk()` | `"a"*10000 + " Should I " + "b"*10000` | Completes in <100ms |
| T090 | `log_cascade_event()` | Valid CascadeEvent | JSONL file with all fields |
| T100 | `merge_patterns()` | Default CP-001 + user CP-001 | User regex used |
| T110 | `detect_cascade_risk()` | `"Should I format this differently?"` | `action=allow` |
| T120 | `detect_cascade_risk()` | Single-category vs multi-category text | Multi score > single score |
| T130 | `format_block_message()` | HIGH risk result | Contains "cascade", risk level, pattern IDs |
| T140 | `get_cascade_stats()` | Log with 5 events (3 blocked, 2 allowed) | `{total_checks: 5, detections: 3, blocks: 3, allowed: 2}` |
| T150 | `main()` via subprocess | JSON hook input with cascade/clean text | exit(2) for cascade, exit(0) for clean |
| T160 | `handle_cascade_detection()` | MEDIUM risk result | Returns `False` |
| T170 | `create_cascade_event()` | HIGH risk result | All 8 CascadeEvent fields present |
| T180 | `load_user_patterns()` | Valid JSON with 2 patterns | Returns 2 patterns |
| T190 | `merge_patterns()` | Default CP-001 regex A + user CP-001 regex B | Merged CP-001 has regex B |
| T200 | `detect_cascade_risk()` | 2000-char text, 100 runs | Average <5ms |
| T210 | `detect_cascade_risk()` | 10000-char text, 100 runs | Average <5ms |
| T260 | `validate_claude_md_cascade_rule()` | `CLAUDE.md` | `rule_present=True` |
| T270 | `validate_claude_md_cascade_rule()` | `CLAUDE.md` | `contains_open_ended=True, forbids_numbered_options=True` |
| T280 | `validate_claude_md_cascade_rule()` | `CLAUDE.md` | `section_correct=True` |
