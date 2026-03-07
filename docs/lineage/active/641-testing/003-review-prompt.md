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

# Test Plan for Issue #641

## Requirements to Cover

- REQ-T010: select_model_for_file()
- REQ-T020: select_model_for_file()
- REQ-T030: select_model_for_file()
- REQ-T040: select_model_for_file()
- REQ-T050: select_model_for_file()
- REQ-T060: select_model_for_file()
- REQ-T070: select_model_for_file()
- REQ-T080: select_model_for_file()
- REQ-T090: call_claude_for_file()
- REQ-T100: call_claude_for_file()
- REQ-T110: generate_file_with_retry()
- REQ-T120: select_model_for_file()
- REQ-T130: select_model_for_file()
- REQ-T140: select_model_for_file()
- REQ-T150: Coverage check
- REQ-T160: Regression check

## Detected Test Types

- browser
- e2e
- integration
- mobile
- terminal
- unit

## Required Tools

- appium
- click.testing
- detox
- docker-compose
- pexpect
- playwright
- pytest
- selenium

## Mock Guidance

**Browser/UI Tests:** Real browser required, mock backend APIs for isolation
**End-to-End Tests:** Minimal mocking - test against real (sandboxed) systems
**Integration Tests:** Use test doubles for external services, real DB where possible
**Mobile App Tests:** Use emulators/simulators, mock backend services
**Terminal/CLI Tests:** Use CliRunner or capture stdout/stderr
**Unit Tests:** Mock external dependencies (APIs, DB, filesystem)

## Coverage Target

95%

## Test Scenarios

### test_t010
- **Type:** unit
- **Requirement:** 
- **Description:** `select_model_for_file()` | `file_path="assemblyzero/__init__.py", estimated_line_count=0, is_test_scaffold=False` | `HAIKU_MODEL` (`"claude-3-haiku-20240307"`)
- **Mock needed:** False
- **Assertions:** 

### test_t020
- **Type:** unit
- **Requirement:** 
- **Description:** `select_model_for_file()` | `file_path="tests/conftest.py", estimated_line_count=0, is_test_scaffold=False` | `HAIKU_MODEL`
- **Mock needed:** False
- **Assertions:** 

### test_t030
- **Type:** unit
- **Requirement:** 
- **Description:** `select_model_for_file()` | `file_path="tests/unit/test_foo.py", estimated_line_count=200, is_test_scaffold=True` | `HAIKU_MODEL`
- **Mock needed:** False
- **Assertions:** 

### test_t040
- **Type:** unit
- **Requirement:** 
- **Description:** `select_model_for_file()` | `file_path="assemblyzero/utils/helper.py", estimated_line_count=49, is_test_scaffold=False` | `HAIKU_MODEL`
- **Mock needed:** False
- **Assertions:** 

### test_t050
- **Type:** unit
- **Requirement:** 
- **Description:** `select_model_for_file()` | `file_path="assemblyzero/utils/helper.py", estimated_line_count=50, is_test_scaffold=False` | `CLAUDE_MODEL` (default)
- **Mock needed:** False
- **Assertions:** 

### test_t060
- **Type:** unit
- **Requirement:** 
- **Description:** `select_model_for_file()` | `file_path="assemblyzero/core/engine.py", estimated_line_count=200, is_test_scaffold=False` | `CLAUDE_MODEL`
- **Mock needed:** False
- **Assertions:** 

### test_t070
- **Type:** unit
- **Requirement:** 
- **Description:** `select_model_for_file()` | `file_path="assemblyzero/core/engine.py", estimated_line_count=0, is_test_scaffold=False` | `CLAUDE_MODEL`
- **Mock needed:** False
- **Assertions:** 

### test_t080
- **Type:** unit
- **Requirement:** 
- **Description:** `select_model_for_file()` | `file_path="assemblyzero/workflows/testing/nodes/__init__.py"` | `HAIKU_MODEL`
- **Mock needed:** False
- **Assertions:** 

### test_t090
- **Type:** unit
- **Requirement:** 
- **Description:** `call_claude_for_file()` | Signature inspection: `model` param exists with default `None` | Parameter present
- **Mock needed:** False
- **Assertions:** 

### test_t100
- **Type:** unit
- **Requirement:** 
- **Description:** `call_claude_for_file()` | Signature inspection: `model` default is `None` | Backward-compatible
- **Mock needed:** False
- **Assertions:** 

### test_t110
- **Type:** unit
- **Requirement:** 
- **Description:** `generate_file_with_retry()` | `filepath="tests/__init__.py"`, mocked routing/call | `select_model_for_file` called; model passed to `call_claude_for_file`
- **Mock needed:** True
- **Assertions:** 

### test_t120
- **Type:** unit
- **Requirement:** 
- **Description:** `select_model_for_file()` | `estimated_line_count=-1` | `CLAUDE_MODEL`
- **Mock needed:** False
- **Assertions:** 

### test_t130
- **Type:** unit
- **Requirement:** 
- **Description:** `select_model_for_file()` | `estimated_line_count=1` | `HAIKU_MODEL`
- **Mock needed:** False
- **Assertions:** 

### test_t140
- **Type:** unit
- **Requirement:** 
- **Description:** `select_model_for_file()` | `estimated_line_count=51` | `CLAUDE_MODEL`
- **Mock needed:** False
- **Assertions:** 

### test_t150
- **Type:** unit
- **Requirement:** 
- **Description:** Coverage check | `pytest --cov --cov-fail-under=95` | Exit code 0
- **Mock needed:** False
- **Assertions:** 

### test_t160
- **Type:** unit
- **Requirement:** 
- **Description:** Regression check | `pytest tests/unit/ -m "not integration"` | Exit code 0
- **Mock needed:** False
- **Assertions:** 

## Original Test Plan Section

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `select_model_for_file()` | `file_path="assemblyzero/__init__.py", estimated_line_count=0, is_test_scaffold=False` | `HAIKU_MODEL` (`"claude-3-haiku-20240307"`) |
| T020 | `select_model_for_file()` | `file_path="tests/conftest.py", estimated_line_count=0, is_test_scaffold=False` | `HAIKU_MODEL` |
| T030 | `select_model_for_file()` | `file_path="tests/unit/test_foo.py", estimated_line_count=200, is_test_scaffold=True` | `HAIKU_MODEL` |
| T040 | `select_model_for_file()` | `file_path="assemblyzero/utils/helper.py", estimated_line_count=49, is_test_scaffold=False` | `HAIKU_MODEL` |
| T050 | `select_model_for_file()` | `file_path="assemblyzero/utils/helper.py", estimated_line_count=50, is_test_scaffold=False` | `CLAUDE_MODEL` (default) |
| T060 | `select_model_for_file()` | `file_path="assemblyzero/core/engine.py", estimated_line_count=200, is_test_scaffold=False` | `CLAUDE_MODEL` |
| T070 | `select_model_for_file()` | `file_path="assemblyzero/core/engine.py", estimated_line_count=0, is_test_scaffold=False` | `CLAUDE_MODEL` |
| T080 | `select_model_for_file()` | `file_path="assemblyzero/workflows/testing/nodes/__init__.py"` | `HAIKU_MODEL` |
| T090 | `call_claude_for_file()` | Signature inspection: `model` param exists with default `None` | Parameter present |
| T100 | `call_claude_for_file()` | Signature inspection: `model` default is `None` | Backward-compatible |
| T110 | `generate_file_with_retry()` | `filepath="tests/__init__.py"`, mocked routing/call | `select_model_for_file` called; model passed to `call_claude_for_file` |
| T120 | `select_model_for_file()` | `estimated_line_count=-1` | `CLAUDE_MODEL` |
| T130 | `select_model_for_file()` | `estimated_line_count=1` | `HAIKU_MODEL` |
| T140 | `select_model_for_file()` | `estimated_line_count=51` | `CLAUDE_MODEL` |
| T150 | Coverage check | `pytest --cov --cov-fail-under=95` | Exit code 0 |
| T160 | Regression check | `pytest tests/unit/ -m "not integration"` | Exit code 0 |
