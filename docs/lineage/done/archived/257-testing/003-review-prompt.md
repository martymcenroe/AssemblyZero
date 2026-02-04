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

# Test Plan for Issue #257

## Requirements to Cover

- REQ-1: When Gemini returns APPROVED verdict with resolved questions, the draft's Open Questions section is updated with checked boxes and resolution text
- REQ-2: Tier 3 suggestions from approved verdicts are incorporated into the draft (either inline or in a Reviewer Suggestions section)
- REQ-3: The final LLD document contains all resolved questions marked with `- [x]` and strikethrough
- REQ-4: Mechanical validation passes after draft update (no "unresolved open questions" blocks)
- REQ-5: Original draft content is preserved except for the specific updates (no loss of author content)
- REQ-6: Failed parsing logs a warning but does not block the workflow
- REQ-7: The workflow requires no manual intervention after Gemini approves

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
- **Description:** Test Description | Expected Behavior | Status
- **Mock needed:** False
- **Assertions:** 

### test_t010
- **Type:** unit
- **Requirement:** 
- **Description:** Parse APPROVED verdict with resolved questions | Returns VerdictParseResult with resolutions | RED
- **Mock needed:** False
- **Assertions:** 

### test_t020
- **Type:** unit
- **Requirement:** 
- **Description:** Parse APPROVED verdict with Tier 3 suggestions | Returns VerdictParseResult with suggestions | RED
- **Mock needed:** False
- **Assertions:** 

### test_t030
- **Type:** unit
- **Requirement:** 
- **Description:** Parse REJECTED verdict | Returns VerdictParseResult with empty resolutions | RED
- **Mock needed:** False
- **Assertions:** 

### test_t040
- **Type:** unit
- **Requirement:** 
- **Description:** Update draft open questions with resolutions | Checkboxes changed to `- [x]` with resolution text | RED
- **Mock needed:** False
- **Assertions:** 

### test_t050
- **Type:** unit
- **Requirement:** 
- **Description:** Update draft with suggestions (new section) | Reviewer Suggestions section appended | RED
- **Mock needed:** False
- **Assertions:** 

### test_t060
- **Type:** unit
- **Requirement:** 
- **Description:** Handle missing open question in draft | Log warning, continue processing | RED
- **Mock needed:** False
- **Assertions:** 

### test_t070
- **Type:** e2e
- **Requirement:** 
- **Description:** End-to-end: review node updates draft on approval | State contains updated_draft after approval | RED
- **Mock needed:** False
- **Assertions:** 

### test_t080
- **Type:** e2e
- **Requirement:** 
- **Description:** End-to-end: finalize uses updated draft | Final LLD contains resolved questions | RED
- **Mock needed:** False
- **Assertions:** 

### test_t090
- **Type:** unit
- **Requirement:** 
- **Description:** Idempotency: same verdict applied twice | Same result both times | RED
- **Mock needed:** False
- **Assertions:** 

### test_010
- **Type:** unit
- **Requirement:** 
- **Description:** Parse approved verdict with resolutions | Auto | Verdict with "Open Questions: RESOLVED" | List of ResolvedQuestion | Correct questions and resolution text extracted
- **Mock needed:** False
- **Assertions:** 

### test_020
- **Type:** unit
- **Requirement:** 
- **Description:** Parse approved verdict with suggestions | Auto | Verdict with "Tier 3" section | List of Tier3Suggestion | All suggestions captured
- **Mock needed:** False
- **Assertions:** 

### test_030
- **Type:** unit
- **Requirement:** 
- **Description:** Parse rejected verdict | Auto | REJECTED verdict | Empty resolutions list | No resolutions extracted
- **Mock needed:** False
- **Assertions:** 

### test_040
- **Type:** unit
- **Requirement:** 
- **Description:** Update draft checkboxes | Auto | Draft + resolutions | Updated draft
- **Mock needed:** False
- **Assertions:** 

### test_050
- **Type:** unit
- **Requirement:** 
- **Description:** Add suggestions section | Auto | Draft + suggestions | Updated draft | New section at end
- **Mock needed:** False
- **Assertions:** 

### test_060
- **Type:** unit
- **Requirement:** 
- **Description:** Missing question in draft | Auto | Resolution for non-existent question | Warning logged, draft unchanged | No error thrown
- **Mock needed:** False
- **Assertions:** 

### test_070
- **Type:** integration
- **Requirement:** 
- **Description:** Review node integration | Auto | State with APPROVED verdict | State with updated_draft | Draft contains resolutions
- **Mock needed:** False
- **Assertions:** 

### test_080
- **Type:** integration
- **Requirement:** 
- **Description:** Finalize node integration | Auto | State with updated_draft | Final LLD | LLD contains `- [x]`
- **Mock needed:** False
- **Assertions:** 

### test_090
- **Type:** unit
- **Requirement:** 
- **Description:** Idempotent update | Auto | Apply same verdict twice | Same draft | No duplicate markers
- **Mock needed:** False
- **Assertions:** 

### test_100
- **Type:** unit
- **Requirement:** 
- **Description:** Empty Open Questions section | Auto | Verdict resolves nothing | Unchanged draft | No modifications
- **Mock needed:** False
- **Assertions:** 

### test_110
- **Type:** unit
- **Requirement:** 
- **Description:** Malformed verdict | Auto | Verdict missing expected sections | Warning, original draft | Graceful degradation
- **Mock needed:** False
- **Assertions:** 

## Original Test Plan Section

*Ref: [0005-testing-strategy-and-protocols.md](0005-testing-strategy-and-protocols.md)*

**Testing Philosophy:** Strive for 100% automated test coverage. Manual tests are a last resort for scenarios that genuinely cannot be automated (e.g., visual inspection, hardware interaction). Every scenario marked "Manual" requires justification.

### 10.0 Test Plan (TDD - Complete Before Implementation)

**TDD Requirement:** Tests MUST be written and failing BEFORE implementation begins.

| Test ID | Test Description | Expected Behavior | Status |
|---------|------------------|-------------------|--------|
| T010 | Parse APPROVED verdict with resolved questions | Returns VerdictParseResult with resolutions | RED |
| T020 | Parse APPROVED verdict with Tier 3 suggestions | Returns VerdictParseResult with suggestions | RED |
| T030 | Parse REJECTED verdict | Returns VerdictParseResult with empty resolutions | RED |
| T040 | Update draft open questions with resolutions | Checkboxes changed to `- [x]` with resolution text | RED |
| T050 | Update draft with suggestions (new section) | Reviewer Suggestions section appended | RED |
| T060 | Handle missing open question in draft | Log warning, continue processing | RED |
| T070 | End-to-end: review node updates draft on approval | State contains updated_draft after approval | RED |
| T080 | End-to-end: finalize uses updated draft | Final LLD contains resolved questions | RED |
| T090 | Idempotency: same verdict applied twice | Same result both times | RED |

**Coverage Target:** ≥95% for all new code

**TDD Checklist:**
- [ ] All tests written before implementation
- [ ] Tests currently RED (failing)
- [ ] Test IDs match scenario IDs in 10.1
- [ ] Test file created at: `tests/unit/test_verdict_parser.py`, `tests/unit/test_draft_updater.py`

*Note: Update Status from RED to GREEN as implementation progresses. All tests should be RED at LLD review time.*

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | Parse approved verdict with resolutions | Auto | Verdict with "Open Questions: RESOLVED" | List of ResolvedQuestion | Correct questions and resolution text extracted |
| 020 | Parse approved verdict with suggestions | Auto | Verdict with "Tier 3" section | List of Tier3Suggestion | All suggestions captured |
| 030 | Parse rejected verdict | Auto | REJECTED verdict | Empty resolutions list | No resolutions extracted |
| 040 | Update draft checkboxes | Auto | Draft + resolutions | Updated draft | `- [ ]` → `- [x] ~~orig~~ **RESOLVED:**` |
| 050 | Add suggestions section | Auto | Draft + suggestions | Updated draft | New section at end |
| 060 | Missing question in draft | Auto | Resolution for non-existent question | Warning logged, draft unchanged | No error thrown |
| 070 | Review node integration | Auto | State with APPROVED verdict | State with updated_draft | Draft contains resolutions |
| 080 | Finalize node integration | Auto | State with updated_draft | Final LLD | LLD contains `- [x]` |
| 090 | Idempotent update | Auto | Apply same verdict twice | Same draft | No duplicate markers |
| 100 | Empty Open Questions section | Auto | Verdict resolves nothing | Unchanged draft | No modifications |
| 110 | Malformed verdict | Auto | Verdict missing expected sections | Warning, original draft | Graceful degradation |

*Note: Use 3-digit IDs with gaps of 10 (010, 020, 030...) to allow insertions.*

**Type values:**
- `Auto` - Fully automated, runs in CI (pytest, playwright, etc.)

### 10.2 Test Commands

```bash
# Run all automated tests
poetry run pytest tests/unit/test_verdict_parser.py tests/unit/test_draft_updater.py tests/integration/test_review_node_update.py -v

# Run only parser tests
poetry run pytest tests/unit/test_verdict_parser.py -v

# Run only updater tests
poetry run pytest tests/unit/test_draft_updater.py -v

# Run integration tests
poetry run pytest tests/integration/test_review_node_update.py -v
```

### 10.3 Manual Tests (Only If Unavoidable)

N/A - All scenarios automated.
