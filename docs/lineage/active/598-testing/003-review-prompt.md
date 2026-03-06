# Test Plan Review Prompt

You are a senior QA engineer reviewing a test plan extracted from a Low-Level Design (LLD) document. Your goal is to ensure the test plan provides adequate coverage and uses real, executable tests.

## Pre-Validated (Do NOT Re-Check)

**Issue #495:** The following have been confirmed by automated mechanical gates before this review. Do not re-check these — focus on semantic test quality instead.

- **Test plan section exists** with named scenarios: VERIFIED
- **Requirement coverage** ≥ 95%: VERIFIED
- **No vague assertions**: VERIFIED — no "verify it works" patterns detected
- **No human delegation**: VERIFIED — no "manual verification" keywords found

## Review Criteria

### 1. Test Type Appropriateness

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
## Test Type Review

| Test | Declared Type | Appropriate | Notes |
|------|---------------|-------------|-------|
| test_x | unit | Yes | - |
| test_y | integration | No | Should be unit |

## Edge Cases

- [ ] Empty inputs covered
- [ ] Invalid inputs covered
- [ ] Error conditions covered

## Semantic Issues

{Any issues found with test logic, mock strategy, or test design}

## Verdict

[x] **APPROVED** - Test plan is ready for implementation

OR

[x] **BLOCKED** - Test plan needs revision

## Required Changes (if BLOCKED)

1. [Specific, actionable change needed]
2. [Specific, actionable change needed]
```

## Important Notes

- Coverage, assertion quality, and human delegation are pre-validated — focus on semantic quality
- Provide specific, actionable feedback
- Reference specific tests and requirements by name


---

# Test Plan for Issue #598

## Requirements to Cover

- REQ-T010: validate_shell_command
- REQ-T020: validate_shell_command
- REQ-T030: validate_shell_command
- REQ-T040: validate_shell_command
- REQ-T050: validate_shell_command
- REQ-T060: validate_shell_command
- REQ-T070: validate_shell_command
- REQ-T080: validate_shell_command
- REQ-T090: validate_shell_command

## Detected Test Types

- browser
- e2e
- integration
- mobile
- security
- terminal
- unit

## Required Tools

- appium
- bandit
- click.testing
- detox
- docker-compose
- pexpect
- playwright
- pytest
- safety
- selenium

## Mock Guidance

**Browser/UI Tests:** Real browser required, mock backend APIs for isolation
**End-to-End Tests:** Minimal mocking - test against real (sandboxed) systems
**Integration Tests:** Use test doubles for external services, real DB where possible
**Mobile App Tests:** Use emulators/simulators, mock backend services
**Security Tests:** Never use real credentials, test edge cases thoroughly
**Terminal/CLI Tests:** Use CliRunner or capture stdout/stderr
**Unit Tests:** Mock external dependencies (APIs, DB, filesystem)

## Coverage Target

95%

## Test Scenarios

### test_t010
- **Type:** unit
- **Requirement:** 
- **Description:** `validate_shell_command` | `"ls -la"` | Returns `None`
- **Mock needed:** False
- **Assertions:** 

### test_t020
- **Type:** unit
- **Requirement:** 
- **Description:** `validate_shell_command` | `"git push --force"` | Raises `SecurityException`
- **Mock needed:** False
- **Assertions:** 

### test_t030
- **Type:** unit
- **Requirement:** 
- **Description:** `validate_shell_command` | `"gh pr merge --admin"` | Raises `SecurityException`
- **Mock needed:** False
- **Assertions:** 

### test_t040
- **Type:** unit
- **Requirement:** 
- **Description:** `validate_shell_command` | `"git branch -D feat"` | Raises `SecurityException`
- **Mock needed:** False
- **Assertions:** 

### test_t050
- **Type:** unit
- **Requirement:** 
- **Description:** `validate_shell_command` | `"git reset --hard HEAD"` | Raises `SecurityException`
- **Mock needed:** False
- **Assertions:** 

### test_t060
- **Type:** unit
- **Requirement:** 
- **Description:** `validate_shell_command` | `"git push --force-with-lease"` | Returns `None`
- **Mock needed:** False
- **Assertions:** 

### test_t070
- **Type:** unit
- **Requirement:** 
- **Description:** `validate_shell_command` | `'git commit -m "Do not use --force"'` | Returns `None`
- **Mock needed:** False
- **Assertions:** 

### test_t080
- **Type:** unit
- **Requirement:** 
- **Description:** `validate_shell_command` | `['git', 'push', '--force']` | Raises `SecurityException`
- **Mock needed:** False
- **Assertions:** 

### test_t090
- **Type:** unit
- **Requirement:** 
- **Description:** `validate_shell_command` | `"git push --force=true"` | Raises `SecurityException`
- **Mock needed:** False
- **Assertions:** 

## Original Test Plan Section

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `validate_shell_command` | `"ls -la"` | Returns `None` |
| T020 | `validate_shell_command` | `"git push --force"` | Raises `SecurityException` |
| T030 | `validate_shell_command` | `"gh pr merge --admin"` | Raises `SecurityException` |
| T040 | `validate_shell_command` | `"git branch -D feat"` | Raises `SecurityException` |
| T050 | `validate_shell_command` | `"git reset --hard HEAD"` | Raises `SecurityException` |
| T060 | `validate_shell_command` | `"git push --force-with-lease"` | Returns `None` |
| T070 | `validate_shell_command` | `'git commit -m "Do not use --force"'` | Returns `None` |
| T080 | `validate_shell_command` | `['git', 'push', '--force']` | Raises `SecurityException` |
| T090 | `validate_shell_command` | `"git push --force=true"` | Raises `SecurityException` |
