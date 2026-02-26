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

# Test Plan for Issue #180

## Requirements to Cover

- REQ-1: Cleanup after merge
- REQ-2: Generate learning summary

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

### test_id
- **Type:** unit
- **Requirement:** 
- **Description:** Tests Function | File | Input | Expected Output
- **Mock needed:** False
- **Assertions:** 

### test_t010
- **Type:** unit
- **Requirement:** 
- **Description:** `build_testing_workflow()` graph structure | `test_cleanup.py` | Compiled graph | N9_cleanup node exists; N9→END edge exists
- **Mock needed:** False
- **Assertions:** 

### test_t020
- **Type:** unit
- **Requirement:** 
- **Description:** `cleanup()` | `test_cleanup.py` | State with merged PR, active lineage | pr_merged=True, summary in done/, worktree removed
- **Mock needed:** False
- **Assertions:** 

### test_t030
- **Type:** unit
- **Requirement:** 
- **Description:** `cleanup()` | `test_cleanup.py` | State with open PR, active lineage | pr_merged=False, summary in active/, lineage preserved
- **Mock needed:** False
- **Assertions:** 

### test_t040
- **Type:** unit
- **Requirement:** 
- **Description:** `cleanup()` | `test_cleanup.py` | State without pr_url | cleanup_skipped_reason="No PR URL in state"
- **Mock needed:** False
- **Assertions:** 

### test_t050
- **Type:** unit
- **Requirement:** 
- **Description:** `cleanup()` | `test_cleanup.py` | State with no active dir | learning_summary_path=""
- **Mock needed:** False
- **Assertions:** 

### test_t060
- **Type:** unit
- **Requirement:** 
- **Description:** `cleanup()` | `test_cleanup.py` | remove_worktree raises CalledProcessError | No exception propagated
- **Mock needed:** False
- **Assertions:** 

### test_t070
- **Type:** unit
- **Requirement:** 
- **Description:** `check_pr_merged()` | `test_cleanup_helpers.py` | gh returns "MERGED" | True
- **Mock needed:** False
- **Assertions:** 

### test_t080
- **Type:** unit
- **Requirement:** 
- **Description:** `check_pr_merged()` | `test_cleanup_helpers.py` | gh returns "OPEN" | False
- **Mock needed:** False
- **Assertions:** 

### test_t090
- **Type:** unit
- **Requirement:** 
- **Description:** `check_pr_merged()` | `test_cleanup_helpers.py` | Empty/malformed URL | ValueError
- **Mock needed:** False
- **Assertions:** 

### test_t095
- **Type:** unit
- **Requirement:** 
- **Description:** `check_pr_merged()` | `test_cleanup_helpers.py` | subprocess.TimeoutExpired | TimeoutExpired raised
- **Mock needed:** False
- **Assertions:** 

### test_t100
- **Type:** unit
- **Requirement:** 
- **Description:** `remove_worktree()` | `test_cleanup_helpers.py` | Existing path, git succeeds | True
- **Mock needed:** False
- **Assertions:** 

### test_t110
- **Type:** unit
- **Requirement:** 
- **Description:** `remove_worktree()` | `test_cleanup_helpers.py` | Nonexistent path | False
- **Mock needed:** False
- **Assertions:** 

### test_t120
- **Type:** unit
- **Requirement:** 
- **Description:** `get_worktree_branch()` | `test_cleanup_helpers.py` | Porcelain output with match | "issue-180-cleanup"
- **Mock needed:** False
- **Assertions:** 

### test_t130
- **Type:** unit
- **Requirement:** 
- **Description:** `get_worktree_branch()` | `test_cleanup_helpers.py` | Porcelain output without match | None
- **Mock needed:** False
- **Assertions:** 

### test_t140
- **Type:** unit
- **Requirement:** 
- **Description:** `delete_local_branch()` | `test_cleanup_helpers.py` | Branch exists | True
- **Mock needed:** False
- **Assertions:** 

### test_t150
- **Type:** unit
- **Requirement:** 
- **Description:** `delete_local_branch()` | `test_cleanup_helpers.py` | Branch "not found" in stderr | False
- **Mock needed:** False
- **Assertions:** 

### test_t160
- **Type:** unit
- **Requirement:** 
- **Description:** `archive_lineage()` | `test_cleanup_helpers.py` | active exists, done doesn't | Done path, active removed
- **Mock needed:** False
- **Assertions:** 

### test_t170
- **Type:** unit
- **Requirement:** 
- **Description:** `archive_lineage()` | `test_cleanup_helpers.py` | active doesn't exist | None
- **Mock needed:** False
- **Assertions:** 

### test_t180
- **Type:** unit
- **Requirement:** 
- **Description:** `archive_lineage()` | `test_cleanup_helpers.py` | done already exists | Timestamped path
- **Mock needed:** False
- **Assertions:** 

### test_t190
- **Type:** unit
- **Requirement:** 
- **Description:** `extract_iteration_data()` | `test_cleanup_helpers.py` | Dir with green-phase file | [IterationSnapshot(coverage=98.5)]
- **Mock needed:** False
- **Assertions:** 

### test_t200
- **Type:** unit
- **Requirement:** 
- **Description:** `extract_iteration_data()` | `test_cleanup_helpers.py` | Empty dir | []
- **Mock needed:** False
- **Assertions:** 

### test_t210
- **Type:** unit
- **Requirement:** 
- **Description:** `detect_stall()` | `test_cleanup_helpers.py` | [85.0, 85.0, 88.0] | (True, 2)
- **Mock needed:** False
- **Assertions:** 

### test_t220
- **Type:** unit
- **Requirement:** 
- **Description:** `detect_stall()` | `test_cleanup_helpers.py` | [80.0, 85.0, 90.0, 95.0] | (False, None)
- **Mock needed:** False
- **Assertions:** 

### test_t230
- **Type:** unit
- **Requirement:** 
- **Description:** `build_learning_summary()` | `test_cleanup_helpers.py` | Dir with fixtures | LearningSummaryData fully populated
- **Mock needed:** False
- **Assertions:** 

### test_t240
- **Type:** unit
- **Requirement:** 
- **Description:** `render_learning_summary()` | `test_cleanup_helpers.py` | LearningSummaryData | Markdown with all sections
- **Mock needed:** False
- **Assertions:** 

### test_t250
- **Type:** unit
- **Requirement:** 
- **Description:** `render_learning_summary()` | `test_cleanup_helpers.py` | Data with stall_detected=True | "Stall detected: Yes" in output
- **Mock needed:** False
- **Assertions:** 

### test_t260
- **Type:** unit
- **Requirement:** 
- **Description:** `write_learning_summary()` | `test_cleanup_helpers.py` | Dir + content string | File exists at path
- **Mock needed:** False
- **Assertions:** 

### test_t270
- **Type:** unit
- **Requirement:** 
- **Description:** `cleanup()` | `test_cleanup.py` | TimeoutExpired + CalledProcessError | State returned, no exception
- **Mock needed:** False
- **Assertions:** 

### test_t280
- **Type:** unit
- **Requirement:** 
- **Description:** `route_after_document()` | `test_cleanup.py` | state with issue_number=180 | "N9_cleanup"
- **Mock needed:** False
- **Assertions:** 

### test_t290
- **Type:** unit
- **Requirement:** 
- **Description:** `route_after_document()` | `test_cleanup.py` | state without issue_number | "end"
- **Mock needed:** False
- **Assertions:** 

### test_t300
- **Type:** unit
- **Requirement:** 
- **Description:** `cleanup()` | `test_cleanup.py` | Full state | Result has pr_merged (bool), learning_summary_path (str), cleanup_skipped_reason (str)
- **Mock needed:** False
- **Assertions:** 

### test_t310
- **Type:** unit
- **Requirement:** 
- **Description:** `cleanup()` | `test_cleanup.py` | PR not merged + active dir | "/active/" in learning_summary_path
- **Mock needed:** False
- **Assertions:** 

### test_t320
- **Type:** unit
- **Requirement:** 
- **Description:** `cleanup()` | `test_cleanup.py` | PR merged + active dir | "/done/" in learning_summary_path
- **Mock needed:** False
- **Assertions:** 

## Original Test Plan Section

| Test ID | Tests Function | File | Input | Expected Output |
|---------|---------------|------|-------|-----------------|
| T010 | `build_testing_workflow()` graph structure | `test_cleanup.py` | Compiled graph | N9_cleanup node exists; N9→END edge exists |
| T020 | `cleanup()` | `test_cleanup.py` | State with merged PR, active lineage | pr_merged=True, summary in done/, worktree removed |
| T030 | `cleanup()` | `test_cleanup.py` | State with open PR, active lineage | pr_merged=False, summary in active/, lineage preserved |
| T040 | `cleanup()` | `test_cleanup.py` | State without pr_url | cleanup_skipped_reason="No PR URL in state" |
| T050 | `cleanup()` | `test_cleanup.py` | State with no active dir | learning_summary_path="" |
| T060 | `cleanup()` | `test_cleanup.py` | remove_worktree raises CalledProcessError | No exception propagated |
| T070 | `check_pr_merged()` | `test_cleanup_helpers.py` | gh returns "MERGED" | True |
| T080 | `check_pr_merged()` | `test_cleanup_helpers.py` | gh returns "OPEN" | False |
| T090 | `check_pr_merged()` | `test_cleanup_helpers.py` | Empty/malformed URL | ValueError |
| T095 | `check_pr_merged()` | `test_cleanup_helpers.py` | subprocess.TimeoutExpired | TimeoutExpired raised |
| T100 | `remove_worktree()` | `test_cleanup_helpers.py` | Existing path, git succeeds | True |
| T110 | `remove_worktree()` | `test_cleanup_helpers.py` | Nonexistent path | False |
| T120 | `get_worktree_branch()` | `test_cleanup_helpers.py` | Porcelain output with match | "issue-180-cleanup" |
| T130 | `get_worktree_branch()` | `test_cleanup_helpers.py` | Porcelain output without match | None |
| T140 | `delete_local_branch()` | `test_cleanup_helpers.py` | Branch exists | True |
| T150 | `delete_local_branch()` | `test_cleanup_helpers.py` | Branch "not found" in stderr | False |
| T160 | `archive_lineage()` | `test_cleanup_helpers.py` | active exists, done doesn't | Done path, active removed |
| T170 | `archive_lineage()` | `test_cleanup_helpers.py` | active doesn't exist | None |
| T180 | `archive_lineage()` | `test_cleanup_helpers.py` | done already exists | Timestamped path |
| T190 | `extract_iteration_data()` | `test_cleanup_helpers.py` | Dir with green-phase file | [IterationSnapshot(coverage=98.5)] |
| T200 | `extract_iteration_data()` | `test_cleanup_helpers.py` | Empty dir | [] |
| T210 | `detect_stall()` | `test_cleanup_helpers.py` | [85.0, 85.0, 88.0] | (True, 2) |
| T220 | `detect_stall()` | `test_cleanup_helpers.py` | [80.0, 85.0, 90.0, 95.0] | (False, None) |
| T230 | `build_learning_summary()` | `test_cleanup_helpers.py` | Dir with fixtures | LearningSummaryData fully populated |
| T240 | `render_learning_summary()` | `test_cleanup_helpers.py` | LearningSummaryData | Markdown with all sections |
| T250 | `render_learning_summary()` | `test_cleanup_helpers.py` | Data with stall_detected=True | "Stall detected: Yes" in output |
| T260 | `write_learning_summary()` | `test_cleanup_helpers.py` | Dir + content string | File exists at path |
| T270 | `cleanup()` | `test_cleanup.py` | TimeoutExpired + CalledProcessError | State returned, no exception |
| T280 | `route_after_document()` | `test_cleanup.py` | state with issue_number=180 | "N9_cleanup" |
| T290 | `route_after_document()` | `test_cleanup.py` | state without issue_number | "end" |
| T300 | `cleanup()` | `test_cleanup.py` | Full state | Result has pr_merged (bool), learning_summary_path (str), cleanup_skipped_reason (str) |
| T310 | `cleanup()` | `test_cleanup.py` | PR not merged + active dir | "/active/" in learning_summary_path |
| T320 | `cleanup()` | `test_cleanup.py` | PR merged + active dir | "/done/" in learning_summary_path |
