# Extracted Test Plan

## Scenarios

### test_t010
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `validate_command()` | `"deploy --admin now"` | Raises `SecurityException` matching `--admin`

### test_t020
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `validate_command()` | `"git push --force origin main"` | Raises `SecurityException` matching `--force`

### test_t030
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `validate_command()` | `"git branch -D feature-x"` | Raises `SecurityException` matching `-D`

### test_t040
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `validate_command()` | `"git reset --hard HEAD~1"` | Raises `SecurityException` matching `--hard`

### test_t050
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `validate_command()` | `["git", "push", "--force", "origin"]` | Raises `SecurityException` matching `--force`

### test_t060
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `validate_command()` | `"ls -Docs"` | Returns `None` (no exception)

### test_t070
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `validate_command()` | `["git", "log", "--hard-wrap"]` | Returns `None` (no exception)

### test_t080
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `validate_command()` | `"echo --forceful"` | Returns `None` (no exception)

### test_t090
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `validate_command()` | `"echo 'unbalanced"` | Raises `SecurityException` (not `ValueError`)

### test_t100
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `validate_command()` | `'echo "unbalanced'` | Raises `SecurityException` with `"Malformed command"` in message

### test_t110
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `shell` module | Module inspection | `shlex` attribute exists on module

### test_t120
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `run_command()` | `["echo", "test"], stdin=subprocess.PIPE` | `subprocess.run` called with `stdin=PIPE`

### test_t130
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `run_command()` | `["echo"], start_new_session=True` | `subprocess.run` called with `start_new_session=True`

### test_t140
- Type: unit
- Requirement: 
- Mock needed: False
- Description: AST scanner | `assemblyzero/workflows/` directory | Empty violations list

### test_t150
- Type: unit
- Requirement: 
- Mock needed: False
- Description: AST scanner | Synthesised violating `.py` file | 1 violation detected at line 2

### test_t160
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Import | `from assemblyzero.core.exceptions import SecurityException` | Import succeeds

### test_t170
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `SecurityException.__init__()` | `command="git push --force", flag="--force", message="..."` | Attributes stored correctly

### test_t180
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `run_command()` | `["echo", "hi"]` (mocked) | `CompletedProcess` with `returncode=0, stdout="hi\n"`

### test_t190
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `run_command()` | `["cmd"]` (mocked, rc=1) | `stdout` and `stderr` unmodified

### test_t200
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `shell.__doc__` | Module docstring inspection | Contains `"MUST use run_command()"` and `"MAY bypass"`

### test_t210
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `shell.__doc__` | Module docstring inspection | Contains `"git"`, `"poetry"`, `"workflow"`

### test_t220
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Coverage | `pytest --cov` | ≥ 95% on `shell.py` and `exceptions.py`

### test_t230
- Type: unit
- Requirement: 
- Mock needed: False
- Description: CI suite | Full test run | Zero new failures

### test_t240
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `wrap_bash_if_needed()` | `"echo hello"` on win32 | `["bash", "-c", "echo hello"]`

### test_t250
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `wrap_bash_if_needed()` | `"echo hello"` on POSIX | `"echo hello"`

### test_t260
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `run_command()` | `"git push --force origin main"` | Raises `SecurityException`; `subprocess.run` not called

### test_t270
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `_prepare_command()` / `run_command()` | `"echo hello"` on POSIX | `["echo", "hello"]` passed to `subprocess.run`

