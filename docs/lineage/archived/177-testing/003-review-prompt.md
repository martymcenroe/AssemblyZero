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

# Test Plan for Issue #177

## Requirements to Cover

- REQ-1: Implementation workflow refuses to proceed if LLD approval is not genuine
- REQ-2: Clear error message explains why the LLD failed verification
- REQ-3: Error message suggests re-running LLD workflow with `--gates verdict`
- REQ-4: Gate passes for LLDs with genuine Gemini APPROVED footer
- REQ-5: Gate passes for LLDs with APPROVED as final review log verdict
- REQ-6: Gate fails for false approvals (status mismatch)
- REQ-7: Gate fails for LLDs with no approval evidence

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

### test_010
- **Type:** unit
- **Requirement:** 
- **Description:** Genuine footer approval | Auto | LLD with `<sub>**Gemini Review:** APPROVED...` | is_valid=True, confidence="high" | Returns pass
- **Mock needed:** False
- **Assertions:** 

### test_020
- **Type:** unit
- **Requirement:** 
- **Description:** Review log approval (final) | Auto | LLD with `\ | APPROVED \ | ` as last row | is_valid=True, confidence="medium" | Returns pass
- **Mock needed:** False
- **Assertions:** 

### test_030
- **Type:** unit
- **Requirement:** 
- **Description:** False approval - REVISE then APPROVED status | Auto | Review shows REVISE, status APPROVED | is_valid=False, error_type="forgery" | Returns fail with "FALSE APPROVAL"
- **Mock needed:** False
- **Assertions:** 

### test_040
- **Type:** unit
- **Requirement:** 
- **Description:** False approval - PENDING then APPROVED status | Auto | Review shows PENDING, status APPROVED | is_valid=False, error_type="forgery" | Returns fail with "FALSE APPROVAL"
- **Mock needed:** False
- **Assertions:** 

### test_050
- **Type:** unit
- **Requirement:** 
- **Description:** No approval evidence | Auto | LLD with no approval markers | is_valid=False, error_type="not_approved" | Returns fail
- **Mock needed:** False
- **Assertions:** 

### test_060
- **Type:** unit
- **Requirement:** 
- **Description:** Multiple reviews, last is APPROVED | Auto | 3 reviews: REVISE, REVISE, APPROVED | is_valid=True | Returns pass
- **Mock needed:** False
- **Assertions:** 

### test_070
- **Type:** unit
- **Requirement:** 
- **Description:** Multiple reviews, last is REVISE | Auto | 3 reviews: APPROVED, REVISE | is_valid=False | Returns fail
- **Mock needed:** False
- **Assertions:** 

### test_080
- **Type:** unit
- **Requirement:** 
- **Description:** Empty review log | Auto | Review log section exists but empty | is_valid=False, error_type="not_approved" | Returns fail
- **Mock needed:** False
- **Assertions:** 

### test_090
- **Type:** integration
- **Requirement:** 
- **Description:** Gate integration - pass | Auto | Valid LLD path | No exception raised | Workflow continues
- **Mock needed:** False
- **Assertions:** 

### test_100
- **Type:** integration
- **Requirement:** 
- **Description:** Gate integration - fail | Auto | Invalid LLD path | LLDVerificationError raised | Exception has suggestion
- **Mock needed:** False
- **Assertions:** 

### test_110
- **Type:** unit
- **Requirement:** 
- **Description:** Path traversal attempt | Auto | Path outside project root | Raises exception before read | Security check blocks
- **Mock needed:** False
- **Assertions:** 

### test_120
- **Type:** unit
- **Requirement:** 
- **Description:** Status APPROVED but no Final Status line | Auto | LLD missing Final Status section | is_valid=False, error_type="not_approved" | Returns fail
- **Mock needed:** False
- **Assertions:** 

## Original Test Plan Section

*Ref: [0005-testing-strategy-and-protocols.md](0005-testing-strategy-and-protocols.md)*

**Testing Philosophy:** 100% automated test coverage. All scenarios can be tested with fixture files.

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | Genuine footer approval | Auto | LLD with `<sub>**Gemini Review:** APPROVED...` | is_valid=True, confidence="high" | Returns pass |
| 020 | Review log approval (final) | Auto | LLD with `\| APPROVED \|` as last row | is_valid=True, confidence="medium" | Returns pass |
| 030 | False approval - REVISE then APPROVED status | Auto | Review shows REVISE, status APPROVED | is_valid=False, error_type="forgery" | Returns fail with "FALSE APPROVAL" |
| 040 | False approval - PENDING then APPROVED status | Auto | Review shows PENDING, status APPROVED | is_valid=False, error_type="forgery" | Returns fail with "FALSE APPROVAL" |
| 050 | No approval evidence | Auto | LLD with no approval markers | is_valid=False, error_type="not_approved" | Returns fail |
| 060 | Multiple reviews, last is APPROVED | Auto | 3 reviews: REVISE, REVISE, APPROVED | is_valid=True | Returns pass |
| 070 | Multiple reviews, last is REVISE | Auto | 3 reviews: APPROVED, REVISE | is_valid=False | Returns fail |
| 080 | Empty review log | Auto | Review log section exists but empty | is_valid=False, error_type="not_approved" | Returns fail |
| 090 | Gate integration - pass | Auto | Valid LLD path | No exception raised | Workflow continues |
| 100 | Gate integration - fail | Auto | Invalid LLD path | LLDVerificationError raised | Exception has suggestion |
| 110 | Path traversal attempt | Auto | Path outside project root | Raises exception before read | Security check blocks |
| 120 | Status APPROVED but no Final Status line | Auto | LLD missing Final Status section | is_valid=False, error_type="not_approved" | Returns fail |

### 10.2 Test Commands

```bash
# Run all automated tests
poetry run pytest tests/test_lld_verification.py -v

# Run only fast/mocked tests (exclude live)
poetry run pytest tests/test_lld_verification.py -v -m "not live"

# Run with coverage
poetry run pytest tests/test_lld_verification.py -v --cov=src/utils/lld_verification
```

### 10.3 Manual Tests (Only If Unavoidable)

N/A - All scenarios automated.
