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

# Test Plan for Issue #611

## Requirements to Cover

- REQ-T010: validate_command()
- REQ-T020: validate_command()
- REQ-T030: validate_command()
- REQ-T040: validate_command()
- REQ-T050: validate_command()
- REQ-T060: validate_command()
- REQ-T070: validate_command()
- REQ-T080: validate_command()
- REQ-T090: validate_command()
- REQ-T100: validate_command()
- REQ-T120: run_command()
- REQ-T130: run_command()
- REQ-T140: AST scanner
- REQ-T150: AST scanner
- REQ-T160: Import
- REQ-T170: SecurityException.__init__()
- REQ-T180: run_command()
- REQ-T190: run_command()
- REQ-T200: shell.__doc__
- REQ-T210: shell.__doc__
- REQ-T220: Coverage
- REQ-T230: CI suite
- REQ-T240: wrap_bash_if_needed()
- REQ-T250: wrap_bash_if_needed()
- REQ-T260: run_command()

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
- **Description:** `validate_command()` | `"deploy --admin now"` | Raises `SecurityException` matching `--admin`
- **Mock needed:** False
- **Assertions:** 

### test_t020
- **Type:** unit
- **Requirement:** 
- **Description:** `validate_command()` | `"git push --force origin main"` | Raises `SecurityException` matching `--force`
- **Mock needed:** False
- **Assertions:** 

### test_t030
- **Type:** unit
- **Requirement:** 
- **Description:** `validate_command()` | `"git branch -D feature-x"` | Raises `SecurityException` matching `-D`
- **Mock needed:** False
- **Assertions:** 

### test_t040
- **Type:** unit
- **Requirement:** 
- **Description:** `validate_command()` | `"git reset --hard HEAD~1"` | Raises `SecurityException` matching `--hard`
- **Mock needed:** False
- **Assertions:** 

### test_t050
- **Type:** unit
- **Requirement:** 
- **Description:** `validate_command()` | `["git", "push", "--force", "origin"]` | Raises `SecurityException` matching `--force`
- **Mock needed:** False
- **Assertions:** 

### test_t060
- **Type:** unit
- **Requirement:** 
- **Description:** `validate_command()` | `"ls -Docs"` | Returns `None` (no exception)
- **Mock needed:** False
- **Assertions:** 

### test_t070
- **Type:** unit
- **Requirement:** 
- **Description:** `validate_command()` | `["git", "log", "--hard-wrap"]` | Returns `None` (no exception)
- **Mock needed:** False
- **Assertions:** 

### test_t080
- **Type:** unit
- **Requirement:** 
- **Description:** `validate_command()` | `"echo --forceful"` | Returns `None` (no exception)
- **Mock needed:** False
- **Assertions:** 

### test_t090
- **Type:** unit
- **Requirement:** 
- **Description:** `validate_command()` | `"echo 'unbalanced"` | Raises `SecurityException` (not `ValueError`)
- **Mock needed:** False
- **Assertions:** 

### test_t100
- **Type:** unit
- **Requirement:** 
- **Description:** `validate_command()` | `'echo "unbalanced'` | Raises `SecurityException` with `"Malformed command"` in message
- **Mock needed:** False
- **Assertions:** 

### test_t110
- **Type:** unit
- **Requirement:** 
- **Description:** `shell` module | Module inspection | `shlex` attribute exists on module
- **Mock needed:** False
- **Assertions:** 

### test_t120
- **Type:** unit
- **Requirement:** 
- **Description:** `run_command()` | `["echo", "test"], stdin=subprocess.PIPE` | `subprocess.run` called with `stdin=PIPE`
- **Mock needed:** False
- **Assertions:** 

### test_t130
- **Type:** unit
- **Requirement:** 
- **Description:** `run_command()` | `["echo"], start_new_session=True` | `subprocess.run` called with `start_new_session=True`
- **Mock needed:** False
- **Assertions:** 

### test_t140
- **Type:** unit
- **Requirement:** 
- **Description:** AST scanner | `assemblyzero/workflows/` directory | Empty violations list
- **Mock needed:** False
- **Assertions:** 

### test_t150
- **Type:** unit
- **Requirement:** 
- **Description:** AST scanner | Synthesised violating `.py` file | 1 violation detected at line 2
- **Mock needed:** False
- **Assertions:** 

### test_t160
- **Type:** unit
- **Requirement:** 
- **Description:** Import | `from assemblyzero.core.exceptions import SecurityException` | Import succeeds
- **Mock needed:** False
- **Assertions:** 

### test_t170
- **Type:** unit
- **Requirement:** 
- **Description:** `SecurityException.__init__()` | `command="git push --force", flag="--force", message="..."` | Attributes stored correctly
- **Mock needed:** False
- **Assertions:** 

### test_t180
- **Type:** unit
- **Requirement:** 
- **Description:** `run_command()` | `["echo", "hi"]` (mocked) | `CompletedProcess` with `returncode=0, stdout="hi\n"`
- **Mock needed:** True
- **Assertions:** 

### test_t190
- **Type:** unit
- **Requirement:** 
- **Description:** `run_command()` | `["cmd"]` (mocked, rc=1) | `stdout` and `stderr` unmodified
- **Mock needed:** True
- **Assertions:** 

### test_t200
- **Type:** unit
- **Requirement:** 
- **Description:** `shell.__doc__` | Module docstring inspection | Contains `"MUST use run_command()"` and `"MAY bypass"`
- **Mock needed:** False
- **Assertions:** 

### test_t210
- **Type:** unit
- **Requirement:** 
- **Description:** `shell.__doc__` | Module docstring inspection | Contains `"git"`, `"poetry"`, `"workflow"`
- **Mock needed:** False
- **Assertions:** 

### test_t220
- **Type:** unit
- **Requirement:** 
- **Description:** Coverage | `pytest --cov` | ≥ 95% on `shell.py` and `exceptions.py`
- **Mock needed:** False
- **Assertions:** 

### test_t230
- **Type:** unit
- **Requirement:** 
- **Description:** CI suite | Full test run | Zero new failures
- **Mock needed:** False
- **Assertions:** 

### test_t240
- **Type:** unit
- **Requirement:** 
- **Description:** `wrap_bash_if_needed()` | `"echo hello"` on win32 | `["bash", "-c", "echo hello"]`
- **Mock needed:** False
- **Assertions:** 

### test_t250
- **Type:** unit
- **Requirement:** 
- **Description:** `wrap_bash_if_needed()` | `"echo hello"` on POSIX | `"echo hello"`
- **Mock needed:** False
- **Assertions:** 

### test_t260
- **Type:** unit
- **Requirement:** 
- **Description:** `run_command()` | `"git push --force origin main"` | Raises `SecurityException`; `subprocess.run` not called
- **Mock needed:** False
- **Assertions:** 

### test_t270
- **Type:** unit
- **Requirement:** 
- **Description:** `_prepare_command()` / `run_command()` | `"echo hello"` on POSIX | `["echo", "hello"]` passed to `subprocess.run`
- **Mock needed:** False
- **Assertions:** 

## Original Test Plan Section

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `validate_command()` | `"deploy --admin now"` | Raises `SecurityException` matching `--admin` |
| T020 | `validate_command()` | `"git push --force origin main"` | Raises `SecurityException` matching `--force` |
| T030 | `validate_command()` | `"git branch -D feature-x"` | Raises `SecurityException` matching `-D` |
| T040 | `validate_command()` | `"git reset --hard HEAD~1"` | Raises `SecurityException` matching `--hard` |
| T050 | `validate_command()` | `["git", "push", "--force", "origin"]` | Raises `SecurityException` matching `--force` |
| T060 | `validate_command()` | `"ls -Docs"` | Returns `None` (no exception) |
| T070 | `validate_command()` | `["git", "log", "--hard-wrap"]` | Returns `None` (no exception) |
| T080 | `validate_command()` | `"echo --forceful"` | Returns `None` (no exception) |
| T090 | `validate_command()` | `"echo 'unbalanced"` | Raises `SecurityException` (not `ValueError`) |
| T100 | `validate_command()` | `'echo "unbalanced'` | Raises `SecurityException` with `"Malformed command"` in message |
| T110 | `shell` module | Module inspection | `shlex` attribute exists on module |
| T120 | `run_command()` | `["echo", "test"], stdin=subprocess.PIPE` | `subprocess.run` called with `stdin=PIPE` |
| T130 | `run_command()` | `["echo"], start_new_session=True` | `subprocess.run` called with `start_new_session=True` |
| T140 | AST scanner | `assemblyzero/workflows/` directory | Empty violations list |
| T150 | AST scanner | Synthesised violating `.py` file | 1 violation detected at line 2 |
| T160 | Import | `from assemblyzero.core.exceptions import SecurityException` | Import succeeds |
| T170 | `SecurityException.__init__()` | `command="git push --force", flag="--force", message="..."` | Attributes stored correctly |
| T180 | `run_command()` | `["echo", "hi"]` (mocked) | `CompletedProcess` with `returncode=0, stdout="hi\n"` |
| T190 | `run_command()` | `["cmd"]` (mocked, rc=1) | `stdout` and `stderr` unmodified |
| T200 | `shell.__doc__` | Module docstring inspection | Contains `"MUST use run_command()"` and `"MAY bypass"` |
| T210 | `shell.__doc__` | Module docstring inspection | Contains `"git"`, `"poetry"`, `"workflow"` |
| T220 | Coverage | `pytest --cov` | ≥ 95% on `shell.py` and `exceptions.py` |
| T230 | CI suite | Full test run | Zero new failures |
| T240 | `wrap_bash_if_needed()` | `"echo hello"` on win32 | `["bash", "-c", "echo hello"]` |
| T250 | `wrap_bash_if_needed()` | `"echo hello"` on POSIX | `"echo hello"` |
| T260 | `run_command()` | `"git push --force origin main"` | Raises `SecurityException`; `subprocess.run` not called |
| T270 | `_prepare_command()` / `run_command()` | `"echo hello"` on POSIX | `["echo", "hello"]` passed to `subprocess.run` |
