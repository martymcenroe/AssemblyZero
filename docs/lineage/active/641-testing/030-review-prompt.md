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

- REQ-1: `select_model_for_file()` returns `HAIKU_MODEL` for `__init__.py` regardless of path depth.
- REQ-2: `select_model_for_file()` returns `HAIKU_MODEL` for `conftest.py` regardless of path depth.
- REQ-3: `select_model_for_file()` returns `HAIKU_MODEL` when `is_test_scaffold=True`, regardless of filename or line count.
- REQ-4: `select_model_for_file()` returns `HAIKU_MODEL` when `estimated_line_count` is between 1 and 49 inclusive.
- REQ-5: `select_model_for_file()` returns the configured default model (Sonnet) for all other files.
- REQ-6: `select_model_for_file()` treats negative `estimated_line_count` as unknown (same as 0) — does not route to Haiku.
- REQ-7: `call_claude_for_file()` accepts an optional `model` parameter; when `None`, behaviour is identical to the pre-change version.
- REQ-8: `generate_file_with_retry()` calls `select_model_for_file()` and passes the result to `call_claude_for_file()`.
- REQ-9: All routing decisions are logged at `INFO` level inside `select_model_for_file()` with file path, resolved model name, and routing reason.
- REQ-10: All new code has ≥ 95% test coverage verified by `pytest-cov`.
- REQ-11: No existing tests are broken by this change.

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

### test_id
- **Type:** unit
- **Requirement:** 
- **Description:** Test Description | Expected Behavior | Status
- **Mock needed:** False
- **Assertions:** 

### test_t010
- **Type:** unit
- **Requirement:** 
- **Description:** `select_model_for_file` routes `__init__.py` to Haiku | Returns `HAIKU_MODEL` | RED
- **Mock needed:** False
- **Assertions:** 

### test_t020
- **Type:** unit
- **Requirement:** 
- **Description:** `select_model_for_file` routes `conftest.py` to Haiku | Returns `HAIKU_MODEL` | RED
- **Mock needed:** False
- **Assertions:** 

### test_t030
- **Type:** unit
- **Requirement:** 
- **Description:** `select_model_for_file` routes test scaffold to Haiku | Returns `HAIKU_MODEL` when `is_test_scaffold=True` | RED
- **Mock needed:** False
- **Assertions:** 

### test_t040
- **Type:** unit
- **Requirement:** 
- **Description:** `select_model_for_file` routes 49-line file to Haiku | Returns `HAIKU_MODEL` | RED
- **Mock needed:** False
- **Assertions:** 

### test_t050
- **Type:** unit
- **Requirement:** 
- **Description:** `select_model_for_file` routes 50-line file to Sonnet | Returns default model | RED
- **Mock needed:** False
- **Assertions:** 

### test_t060
- **Type:** unit
- **Requirement:** 
- **Description:** `select_model_for_file` routes unknown-size complex file to Sonnet | Returns default model when `estimated_line_count=0` | RED
- **Mock needed:** False
- **Assertions:** 

### test_t070
- **Type:** unit
- **Requirement:** 
- **Description:** `select_model_for_file` routes deeply nested `__init__.py` to Haiku | Path depth irrelevant; basename match wins | RED
- **Mock needed:** False
- **Assertions:** 

### test_t080
- **Type:** unit
- **Requirement:** 
- **Description:** `call_claude_for_file` uses supplied model when provided | Anthropic client called with correct model string | RED
- **Mock needed:** False
- **Assertions:** 

### test_t090
- **Type:** unit
- **Requirement:** 
- **Description:** `call_claude_for_file` uses default model when `model=None` | Existing behaviour preserved | RED
- **Mock needed:** False
- **Assertions:** 

### test_t100
- **Type:** unit
- **Requirement:** 
- **Description:** `generate_file_with_retry` passes routed model to `call_claude_for_file` | Integration of routing -> call | RED
- **Mock needed:** False
- **Assertions:** 

### test_t110
- **Type:** unit
- **Requirement:** 
- **Description:** Routing decision logged at INFO level with reason | Logger called with file path, model name, and reason | RED
- **Mock needed:** False
- **Assertions:** 

### test_t120
- **Type:** unit
- **Requirement:** 
- **Description:** Negative line count treated as unknown | Returns `DEFAULT_MODEL` when `estimated_line_count=-1` | RED
- **Mock needed:** False
- **Assertions:** 

### test_t130
- **Type:** unit
- **Requirement:** 
- **Description:** Returns `HAIKU_MODEL` for lower boundary | RED
- **Mock needed:** False
- **Assertions:** 

### test_t140
- **Type:** unit
- **Requirement:** 
- **Description:** Returns `DEFAULT_MODEL` just above threshold | RED
- **Mock needed:** False
- **Assertions:** 

### test_t150
- **Type:** unit
- **Requirement:** 
- **Description:** Coverage ≥ 95% on new/modified code | `pytest-cov` report shows ≥ 95% line coverage | RED
- **Mock needed:** False
- **Assertions:** 

### test_t160
- **Type:** unit
- **Requirement:** 
- **Description:** No regressions in existing unit test suite | All pre-existing tests pass after change | RED
- **Mock needed:** False
- **Assertions:** 

### test_010
- **Type:** unit
- **Requirement:** 
- **Description:** `__init__.py` in root (REQ-1) | Auto | `file_path="assemblyzero/__init__.py"`, `estimated_line_count=0`, `is_test_scaffold=False` | `HAIKU_MODEL` | `assert result == HAIKU_MODEL`
- **Mock needed:** False
- **Assertions:** 

### test_020
- **Type:** unit
- **Requirement:** 
- **Description:** `conftest.py` in tests root (REQ-2) | Auto | `file_path="tests/conftest.py"`, `estimated_line_count=0`, `is_test_scaffold=False` | `HAIKU_MODEL` | `assert result == HAIKU_MODEL`
- **Mock needed:** False
- **Assertions:** 

### test_030
- **Type:** unit
- **Requirement:** 
- **Description:** Test scaffold flag overrides line count (REQ-3) | Auto | `file_path="tests/unit/test_foo.py"`, `estimated_line_count=200`, `is_test_scaffold=True` | `HAIKU_MODEL` | Flag overrides line count and filen
- **Mock needed:** False
- **Assertions:** 

### test_040
- **Type:** unit
- **Requirement:** 
- **Description:** Auto | `file_path="assemblyzero/utils/helper.py"`, `estimated_line_count=49`, `is_test_scaffold=False` | `HAIKU_MODEL` | `assert result == HAIKU_MODEL`
- **Mock needed:** False
- **Assertions:** 

### test_050
- **Type:** unit
- **Requirement:** 
- **Description:** Auto | `file_path="assemblyzero/utils/helper.py"`, `estimated_line_count=50`, `is_test_scaffold=False` | `DEFAULT_MODEL` | Exactly 50 lines goes to Sonnet (threshold is `< 50`)
- **Mock needed:** False
- **Assertions:** 

### test_060
- **Type:** unit
- **Requirement:** 
- **Description:** 200-line complex file (REQ-5) | Auto | `file_path="assemblyzero/core/engine.py"`, `estimated_line_count=200`, `is_test_scaffold=False` | `DEFAULT_MODEL` | `assert result == DEFAULT_MODEL`
- **Mock needed:** False
- **Assertions:** 

### test_070
- **Type:** unit
- **Requirement:** 
- **Description:** Unknown size complex file (REQ-5) | Auto | `file_path="assemblyzero/core/engine.py"`, `estimated_line_count=0`, `is_test_scaffold=False` | `DEFAULT_MODEL` | `0` means unknown; don't route to Haiku
- **Mock needed:** False
- **Assertions:** 

### test_080
- **Type:** unit
- **Requirement:** 
- **Description:** Deeply nested `__init__.py` (REQ-1) | Auto | `file_path="assemblyzero/workflows/testing/nodes/__init__.py"` | `HAIKU_MODEL` | Basename match regardless of depth
- **Mock needed:** False
- **Assertions:** 

### test_090
- **Type:** unit
- **Requirement:** 
- **Description:** `call_claude_for_file` explicit model (REQ-7) | Auto | `model="claude-3-haiku-20240307"`, mock client | Anthropic client receives `model="claude-3-haiku-20240307"` | Mock assert called with correct mo
- **Mock needed:** True
- **Assertions:** 

### test_100
- **Type:** unit
- **Requirement:** 
- **Description:** `call_claude_for_file` default model (REQ-7) | Auto | `model=None`, mock client | Anthropic client receives configured default | Backward-compatible path
- **Mock needed:** True
- **Assertions:** 

### test_110
- **Type:** integration
- **Requirement:** 
- **Description:** `generate_file_with_retry` routing integration (REQ-8) | Auto | `file_path="tests/__init__.py"`, mock `call_claude_for_file` | `call_claude_for_file` called with `model=HAIKU_MODEL` | End-to-end routi
- **Mock needed:** True
- **Assertions:** 

### test_120
- **Type:** unit
- **Requirement:** 
- **Description:** Routing log emission includes reason (REQ-9) | Auto | Any routed call, mock logger | `logger.info` called with file path, model name, and reason string | `mock_logger.info.assert_called_once()` and re
- **Mock needed:** True
- **Assertions:** 

### test_130
- **Type:** unit
- **Requirement:** 
- **Description:** Auto | `estimated_line_count=1` | `HAIKU_MODEL` | Lower boundary check
- **Mock needed:** False
- **Assertions:** 

### test_140
- **Type:** unit
- **Requirement:** 
- **Description:** Negative line count treated as unknown (REQ-6) | Auto | `estimated_line_count=-1` | `DEFAULT_MODEL` | Defensive: negative = unknown, no Haiku routing
- **Mock needed:** False
- **Assertions:** 

### test_150
- **Type:** unit
- **Requirement:** 
- **Description:** Coverage ≥ 95% on new/modified code (REQ-10) | Auto | Run `pytest --cov=assemblyzero/workflows/testing/nodes/implement_code --cov-report=term-missing` | Coverage report shows ≥ 95% line coverage | CI 
- **Mock needed:** False
- **Assertions:** 

### test_160
- **Type:** unit
- **Requirement:** 
- **Description:** No regressions in existing unit test suite (REQ-11) | Auto | Run `pytest tests/unit/ -m "not integration and not e2e and not adversarial"` | All pre-existing tests pass | Exit code 0; zero failures, z
- **Mock needed:** False
- **Assertions:** 

## Original Test Plan Section

### 10.0 Test Plan (TDD - Complete Before Implementation)

**TDD Requirement:** Tests MUST be written and failing BEFORE implementation begins.

| Test ID | Test Description | Expected Behavior | Status |
|---------|------------------|-------------------|--------|
| T010 | `select_model_for_file` routes `__init__.py` to Haiku | Returns `HAIKU_MODEL` | RED |
| T020 | `select_model_for_file` routes `conftest.py` to Haiku | Returns `HAIKU_MODEL` | RED |
| T030 | `select_model_for_file` routes test scaffold to Haiku | Returns `HAIKU_MODEL` when `is_test_scaffold=True` | RED |
| T040 | `select_model_for_file` routes 49-line file to Haiku | Returns `HAIKU_MODEL` | RED |
| T050 | `select_model_for_file` routes 50-line file to Sonnet | Returns default model | RED |
| T060 | `select_model_for_file` routes unknown-size complex file to Sonnet | Returns default model when `estimated_line_count=0` | RED |
| T070 | `select_model_for_file` routes deeply nested `__init__.py` to Haiku | Path depth irrelevant; basename match wins | RED |
| T080 | `call_claude_for_file` uses supplied model when provided | Anthropic client called with correct model string | RED |
| T090 | `call_claude_for_file` uses default model when `model=None` | Existing behaviour preserved | RED |
| T100 | `generate_file_with_retry` passes routed model to `call_claude_for_file` | Integration of routing -> call | RED |
| T110 | Routing decision logged at INFO level with reason | Logger called with file path, model name, and reason | RED |
| T120 | Negative line count treated as unknown | Returns `DEFAULT_MODEL` when `estimated_line_count=-1` | RED |
| T130 | 1-line file routes to Haiku | Returns `HAIKU_MODEL` for lower boundary | RED |
| T140 | 51-line file routes to Sonnet | Returns `DEFAULT_MODEL` just above threshold | RED |
| T150 | Coverage ≥ 95% on new/modified code | `pytest-cov` report shows ≥ 95% line coverage | RED |
| T160 | No regressions in existing unit test suite | All pre-existing tests pass after change | RED |

**Coverage Target:** ≥95% for all new/modified code

**TDD Checklist:**
- [ ] All tests written before implementation
- [ ] Tests currently RED (failing)
- [ ] Test IDs match scenario IDs in 10.1
- [ ] Test file created at: `tests/unit/test_implement_code_routing.py`

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | `__init__.py` in root (REQ-1) | Auto | `file_path="assemblyzero/__init__.py"`, `estimated_line_count=0`, `is_test_scaffold=False` | `HAIKU_MODEL` | `assert result == HAIKU_MODEL` |
| 020 | `conftest.py` in tests root (REQ-2) | Auto | `file_path="tests/conftest.py"`, `estimated_line_count=0`, `is_test_scaffold=False` | `HAIKU_MODEL` | `assert result == HAIKU_MODEL` |
| 030 | Test scaffold flag overrides line count (REQ-3) | Auto | `file_path="tests/unit/test_foo.py"`, `estimated_line_count=200`, `is_test_scaffold=True` | `HAIKU_MODEL` | Flag overrides line count and filename |
| 040 | 49-line small file (REQ-4) | Auto | `file_path="assemblyzero/utils/helper.py"`, `estimated_line_count=49`, `is_test_scaffold=False` | `HAIKU_MODEL` | `assert result == HAIKU_MODEL` |
| 050 | 50-line boundary file (REQ-5) | Auto | `file_path="assemblyzero/utils/helper.py"`, `estimated_line_count=50`, `is_test_scaffold=False` | `DEFAULT_MODEL` | Exactly 50 lines goes to Sonnet (threshold is `< 50`) |
| 060 | 200-line complex file (REQ-5) | Auto | `file_path="assemblyzero/core/engine.py"`, `estimated_line_count=200`, `is_test_scaffold=False` | `DEFAULT_MODEL` | `assert result == DEFAULT_MODEL` |
| 070 | Unknown size complex file (REQ-5) | Auto | `file_path="assemblyzero/core/engine.py"`, `estimated_line_count=0`, `is_test_scaffold=False` | `DEFAULT_MODEL` | `0` means unknown; don't route to Haiku |
| 080 | Deeply nested `__init__.py` (REQ-1) | Auto | `file_path="assemblyzero/workflows/testing/nodes/__init__.py"` | `HAIKU_MODEL` | Basename match regardless of depth |
| 090 | `call_claude_for_file` explicit model (REQ-7) | Auto | `model="claude-3-haiku-20240307"`, mock client | Anthropic client receives `model="claude-3-haiku-20240307"` | Mock assert called with correct model |
| 100 | `call_claude_for_file` default model (REQ-7) | Auto | `model=None`, mock client | Anthropic client receives configured default | Backward-compatible path |
| 110 | `generate_file_with_retry` routing integration (REQ-8) | Auto | `file_path="tests/__init__.py"`, mock `call_claude_for_file` | `call_claude_for_file` called with `model=HAIKU_MODEL` | End-to-end routing check |
| 120 | Routing log emission includes reason (REQ-9) | Auto | Any routed call, mock logger | `logger.info` called with file path, model name, and reason string | `mock_logger.info.assert_called_once()` and reason in call args |
| 130 | 1-line file routes to Haiku (REQ-4) | Auto | `estimated_line_count=1` | `HAIKU_MODEL` | Lower boundary check |
| 140 | Negative line count treated as unknown (REQ-6) | Auto | `estimated_line_count=-1` | `DEFAULT_MODEL` | Defensive: negative = unknown, no Haiku routing |
| 150 | Coverage ≥ 95% on new/modified code (REQ-10) | Auto | Run `pytest --cov=assemblyzero/workflows/testing/nodes/implement_code --cov-report=term-missing` | Coverage report shows ≥ 95% line coverage | CI exits 0 with `--cov-fail-under=95` flag |
| 160 | No regressions in existing unit test suite (REQ-11) | Auto | Run `pytest tests/unit/ -m "not integration and not e2e and not adversarial"` | All pre-existing tests pass | Exit code 0; zero failures, zero errors |

### 10.2 Test Commands

```bash

# Run new routing unit tests only
poetry run pytest tests/unit/test_implement_code_routing.py -v

# Run with coverage report
poetry run pytest tests/unit/test_implement_code_routing.py -v \
    --cov=assemblyzero/workflows/testing/nodes/implement_code \
    --cov-report=term-missing \
    --cov-fail-under=95

# Run full unit suite to check for regressions (REQ-11)
poetry run pytest tests/unit/ -v -m "not integration and not e2e and not adversarial"

# Run only fast/mocked tests
poetry run pytest tests/unit/test_implement_code_routing.py -v -m "not live"
```

### 10.3 Manual Tests (Only If Unavoidable)

**N/A - All scenarios automated.** The routing logic is pure Python with no I/O; all paths are exercisable with mocks and deterministic inputs.

---
