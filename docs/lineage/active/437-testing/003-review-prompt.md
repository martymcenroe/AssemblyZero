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

# Test Plan for Issue #437

## Requirements to Cover

- REQ-T010: test_consolidate_detects_file_exceeding_threshold
- REQ-T020: test_consolidate_skips_file_below_threshold
- REQ-T030: test_consolidate_exact_threshold_boundary
- REQ-T040: test_rotation_creates_numbered_backup
- REQ-T050: test_rotation_increments_existing_backups
- REQ-T060: test_rotation_preserves_content_integrity
- REQ-T070: test_rotation_creates_fresh_active_file
- REQ-T080: test_consolidate_large_file_with_multiple_sources
- REQ-T090: test_consolidate_handles_concurrent_rotation_gracefully
- REQ-T100: test_consolidate_large_file_read_only_filesystem
- REQ-T110: test_consolidate_large_file_disk_full_simulation
- REQ-T120: test_no_actual_large_files_created
- REQ-T130: test_operations_confined_to_tmp_path

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
- **Description:** `test_consolidate_detects_file_exceeding_threshold` | File with mocked size 52_428_801 | Backup `.1` exists, active file < threshold
- **Mock needed:** True
- **Assertions:** 

### test_t020
- **Type:** unit
- **Requirement:** 
- **Description:** `test_consolidate_skips_file_below_threshold` | File with mocked size 10_485_760 | No backup files, original file unchanged
- **Mock needed:** True
- **Assertions:** 

### test_t030
- **Type:** unit
- **Requirement:** 
- **Description:** `test_consolidate_exact_threshold_boundary` | File with mocked size 52_428_800 | Consistent with `>` or `>=` semantics
- **Mock needed:** True
- **Assertions:** 

### test_t040
- **Type:** unit
- **Requirement:** 
- **Description:** `test_rotation_creates_numbered_backup` | Large file, no existing backups | `history.log.1` exists with original content
- **Mock needed:** False
- **Assertions:** 

### test_t050
- **Type:** unit
- **Requirement:** 
- **Description:** `test_rotation_increments_existing_backups` | Large file + `.1` + `.2` | `.1`→`.2`→`.3` cascade, new `.1` = old active
- **Mock needed:** False
- **Assertions:** 

### test_t060
- **Type:** unit
- **Requirement:** 
- **Description:** `test_rotation_preserves_content_integrity` | 500 numbered lines, trigger rotation | All 500 lines present across all files
- **Mock needed:** False
- **Assertions:** 

### test_t070
- **Type:** unit
- **Requirement:** 
- **Description:** `test_rotation_creates_fresh_active_file` | Large file triggers rotation | Active file exists, size < 1024 bytes
- **Mock needed:** False
- **Assertions:** 

### test_t080
- **Type:** unit
- **Requirement:** 
- **Description:** `test_consolidate_large_file_with_multiple_sources` | 3 source files + large history | All source content preserved
- **Mock needed:** False
- **Assertions:** 

### test_t090
- **Type:** unit
- **Requirement:** 
- **Description:** `test_consolidate_handles_concurrent_rotation_gracefully` | Large file + existing backups, rotate twice | No crash, files exist
- **Mock needed:** False
- **Assertions:** 

### test_t100
- **Type:** unit
- **Requirement:** 
- **Description:** `test_consolidate_large_file_read_only_filesystem` | Read-only directory | `PermissionError` or `OSError` raised, original intact
- **Mock needed:** True
- **Assertions:** 

### test_t110
- **Type:** unit
- **Requirement:** 
- **Description:** `test_consolidate_large_file_disk_full_simulation` | `shutil.move` raises `OSError` | `OSError` raised, original file intact
- **Mock needed:** False
- **Assertions:** 

### test_t120
- **Type:** unit
- **Requirement:** 
- **Description:** `test_no_actual_large_files_created` | Post-rotation tmp_path walk | All files < 1MB on disk
- **Mock needed:** False
- **Assertions:** 

### test_t130
- **Type:** unit
- **Requirement:** 
- **Description:** `test_operations_confined_to_tmp_path` | Parent dir snapshot before/after | No new files outside tmp_path
- **Mock needed:** False
- **Assertions:** 

## Original Test Plan Section

| Test ID | Tests Function/Behavior | Input | Expected Output |
|---------|------------------------|-------|-----------------|
| T010 | `test_consolidate_detects_file_exceeding_threshold` | File with mocked size 52_428_801 | Backup `.1` exists, active file < threshold |
| T020 | `test_consolidate_skips_file_below_threshold` | File with mocked size 10_485_760 | No backup files, original file unchanged |
| T030 | `test_consolidate_exact_threshold_boundary` | File with mocked size 52_428_800 | Consistent with `>` or `>=` semantics |
| T040 | `test_rotation_creates_numbered_backup` | Large file, no existing backups | `history.log.1` exists with original content |
| T050 | `test_rotation_increments_existing_backups` | Large file + `.1` + `.2` | `.1`→`.2`→`.3` cascade, new `.1` = old active |
| T060 | `test_rotation_preserves_content_integrity` | 500 numbered lines, trigger rotation | All 500 lines present across all files |
| T070 | `test_rotation_creates_fresh_active_file` | Large file triggers rotation | Active file exists, size < 1024 bytes |
| T080 | `test_consolidate_large_file_with_multiple_sources` | 3 source files + large history | All source content preserved |
| T090 | `test_consolidate_handles_concurrent_rotation_gracefully` | Large file + existing backups, rotate twice | No crash, files exist |
| T100 | `test_consolidate_large_file_read_only_filesystem` | Read-only directory | `PermissionError` or `OSError` raised, original intact |
| T110 | `test_consolidate_large_file_disk_full_simulation` | `shutil.move` raises `OSError` | `OSError` raised, original file intact |
| T120 | `test_no_actual_large_files_created` | Post-rotation tmp_path walk | All files < 1MB on disk |
| T130 | `test_operations_confined_to_tmp_path` | Parent dir snapshot before/after | No new files outside tmp_path |
