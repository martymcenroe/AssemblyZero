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

# Test Plan for Issue #248

## Requirements to Cover

- REQ-1: Drafts with open questions proceed to Gemini review (not blocked pre-review)
- REQ-2: Gemini review prompt includes instructions to answer open questions
- REQ-3: Post-review check detects unanswered questions (not marked HUMAN REQUIRED)
- REQ-4: Unanswered questions trigger loop back to Gemini with followup prompt
- REQ-5: Only questions marked "HUMAN REQUIRED" escalate to human gate
- REQ-6: Workflow respects max_iterations for combined revision+question loops
- REQ-7: Final validation only blocks if HUMAN REQUIRED questions remain unanswered by human

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

### test_id
- **Type:** unit
- **Requirement:** 
- **Description:** Test Description | Expected Behavior | Status
- **Mock needed:** False
- **Assertions:** 

### test_t010
- **Type:** unit
- **Requirement:** 
- **Description:** test_draft_with_questions_proceeds_to_review | Draft not blocked pre-review | RED
- **Mock needed:** False
- **Assertions:** 

### test_t020
- **Type:** unit
- **Requirement:** 
- **Description:** test_gemini_answers_questions | Questions resolved in verdict | RED
- **Mock needed:** False
- **Assertions:** 

### test_t030
- **Type:** unit
- **Requirement:** 
- **Description:** test_unanswered_triggers_loop | Loop back to N3 with followup | RED
- **Mock needed:** False
- **Assertions:** 

### test_t040
- **Type:** unit
- **Requirement:** 
- **Description:** test_human_required_escalates | Goes to human gate | RED
- **Mock needed:** False
- **Assertions:** 

### test_t050
- **Type:** unit
- **Requirement:** 
- **Description:** test_max_iterations_respected | Terminates after limit | RED
- **Mock needed:** False
- **Assertions:** 

### test_t060
- **Type:** unit
- **Requirement:** 
- **Description:** test_all_answered_proceeds_to_finalize | N5 reached when resolved | RED
- **Mock needed:** False
- **Assertions:** 

### test_t070
- **Type:** unit
- **Requirement:** 
- **Description:** test_prompt_includes_question_instructions | 0702c has new section | RED
- **Mock needed:** False
- **Assertions:** 

### test_010
- **Type:** unit
- **Requirement:** 
- **Description:** Draft with open questions proceeds | Auto | Draft with 3 unchecked questions | Reaches N3_review | No BLOCKED status pre-review
- **Mock needed:** False
- **Assertions:** 

### test_020
- **Type:** unit
- **Requirement:** 
- **Description:** Gemini answers questions | Auto | Review with question instructions | All questions [x] | Verdict contains resolutions
- **Mock needed:** False
- **Assertions:** 

### test_030
- **Type:** unit
- **Requirement:** 
- **Description:** Unanswered triggers loop | Auto | Verdict approves but questions unchecked | Loop to N3 | Followup prompt sent
- **Mock needed:** False
- **Assertions:** 

### test_040
- **Type:** unit
- **Requirement:** 
- **Description:** HUMAN REQUIRED escalates | Auto | Verdict with HUMAN REQUIRED | Goes to N4 | Human gate invoked
- **Mock needed:** False
- **Assertions:** 

### test_050
- **Type:** unit
- **Requirement:** 
- **Description:** Max iterations respected | Auto | 20 loops without resolution | Terminates | Exit with current state
- **Mock needed:** False
- **Assertions:** 

### test_060
- **Type:** unit
- **Requirement:** 
- **Description:** Resolved proceeds to finalize | Auto | All questions answered | Reaches N5 | APPROVED status
- **Mock needed:** False
- **Assertions:** 

### test_070
- **Type:** unit
- **Requirement:** 
- **Description:** Prompt updated | Auto | Load 0702c | Contains question instructions | Regex match
- **Mock needed:** False
- **Assertions:** 

## Original Test Plan Section

### 10.0 Test Plan (TDD)

| Test ID | Test Description | Expected Behavior | Status |
|---------|------------------|-------------------|--------|
| T010 | test_draft_with_questions_proceeds_to_review | Draft not blocked pre-review | RED |
| T020 | test_gemini_answers_questions | Questions resolved in verdict | RED |
| T030 | test_unanswered_triggers_loop | Loop back to N3 with followup | RED |
| T040 | test_human_required_escalates | Goes to human gate | RED |
| T050 | test_max_iterations_respected | Terminates after limit | RED |
| T060 | test_all_answered_proceeds_to_finalize | N5 reached when resolved | RED |
| T070 | test_prompt_includes_question_instructions | 0702c has new section | RED |

**Coverage Target:** ≥95%

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | Draft with open questions proceeds | Auto | Draft with 3 unchecked questions | Reaches N3_review | No BLOCKED status pre-review |
| 020 | Gemini answers questions | Auto | Review with question instructions | All questions [x] | Verdict contains resolutions |
| 030 | Unanswered triggers loop | Auto | Verdict approves but questions unchecked | Loop to N3 | Followup prompt sent |
| 040 | HUMAN REQUIRED escalates | Auto | Verdict with HUMAN REQUIRED | Goes to N4 | Human gate invoked |
| 050 | Max iterations respected | Auto | 20 loops without resolution | Terminates | Exit with current state |
| 060 | Resolved proceeds to finalize | Auto | All questions answered | Reaches N5 | APPROVED status |
| 070 | Prompt updated | Auto | Load 0702c | Contains question instructions | Regex match |
