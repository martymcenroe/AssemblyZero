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

# Test Plan for Issue #438

## Requirements to Cover

- REQ-1: Feature implements basic functionality
- REQ-2: Feature has test coverage
- REQ-3: Feature is documented

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
- **Description:** `test_lld_workflow_mock_completes_successfully` | Mock LLD input + mock config | `exit_status="success"`, no error_message, nodes_visited > 0
- **Mock needed:** True
- **Assertions:** 

### test_t020
- **Type:** unit
- **Requirement:** 
- **Description:** `test_lld_workflow_mock_no_api_credentials_required` | Same + all API env vars stripped | `exit_status="success"`, `api_calls_made=0`, tracker empty
- **Mock needed:** True
- **Assertions:** 

### test_t030
- **Type:** unit
- **Requirement:** 
- **Description:** `test_lld_workflow_mock_ci_compatible` | Same as T010 | `duration_seconds < 60`, `exit_status="success"`
- **Mock needed:** True
- **Assertions:** 

### test_t040
- **Type:** unit
- **Requirement:** 
- **Description:** `test_lld_workflow_mock_visits_all_nodes` | Same as T010 | All EXPECTED_NODES in visited set, none missing
- **Mock needed:** True
- **Assertions:** 

### test_t050
- **Type:** unit
- **Requirement:** 
- **Description:** `test_lld_workflow_mock_state_transitions` | Same as T010 | First node is entry, last is terminal, no self-loops
- **Mock needed:** True
- **Assertions:** 

### test_t060
- **Type:** unit
- **Requirement:** 
- **Description:** `test_lld_workflow_mock_produces_artifacts` | Same as T010 | Non-empty lld_content, non-empty review_verdict
- **Mock needed:** True
- **Assertions:** 

### test_t070
- **Type:** unit
- **Requirement:** 
- **Description:** `test_lld_workflow_mock_idempotent_rerun` | Same input, two fresh workspaces | `nodes_visited_1 == nodes_visited_2`, `filtered_state_1 == filtered_state_2`
- **Mock needed:** True
- **Assertions:** 

### test_t080
- **Type:** unit
- **Requirement:** 
- **Description:** `test_lld_workflow_mock_checkpoint_created` | Same as T010 | checkpoints.db exists, ≥1 row in checkpoint tables
- **Mock needed:** True
- **Assertions:** 

### test_t090
- **Type:** unit
- **Requirement:** 
- **Description:** `test_lld_workflow_mock_workspace_isolation` | Same as T010 + filesystem snapshots | No new files in cwd/docs or cwd/data; all artifacts under tmp_path
- **Mock needed:** True
- **Assertions:** 

## Original Test Plan Section

| Test ID | Tests Function/Scenario | Input | Expected Output |
|---------|------------------------|-------|-----------------|
| T010 | `test_lld_workflow_mock_completes_successfully` | Mock LLD input + mock config | `exit_status="success"`, no error_message, nodes_visited > 0 |
| T020 | `test_lld_workflow_mock_no_api_credentials_required` | Same + all API env vars stripped | `exit_status="success"`, `api_calls_made=0`, tracker empty |
| T030 | `test_lld_workflow_mock_ci_compatible` | Same as T010 | `duration_seconds < 60`, `exit_status="success"` |
| T040 | `test_lld_workflow_mock_visits_all_nodes` | Same as T010 | All EXPECTED_NODES in visited set, none missing |
| T050 | `test_lld_workflow_mock_state_transitions` | Same as T010 | First node is entry, last is terminal, no self-loops |
| T060 | `test_lld_workflow_mock_produces_artifacts` | Same as T010 | Non-empty lld_content, non-empty review_verdict |
| T070 | `test_lld_workflow_mock_idempotent_rerun` | Same input, two fresh workspaces | `nodes_visited_1 == nodes_visited_2`, `filtered_state_1 == filtered_state_2` |
| T080 | `test_lld_workflow_mock_checkpoint_created` | Same as T010 | checkpoints.db exists, ≥1 row in checkpoint tables |
| T090 | `test_lld_workflow_mock_workspace_isolation` | Same as T010 + filesystem snapshots | No new files in cwd/docs or cwd/data; all artifacts under tmp_path |
