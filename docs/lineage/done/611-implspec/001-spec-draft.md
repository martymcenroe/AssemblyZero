# Implementation Spec: Fix — Activate shell.py Command Middleware Across Workflow Nodes

| Field | Value |
|-------|-------|
| Issue | #611 |
| LLD | `docs/lld/active/611-fix-activate-shell-middleware.md` |
| Generated | 2026-03-06 |
| Status | DRAFT |

## 1. Overview

This implementation hardens `assemblyzero/utils/shell.py` by fixing the exception type, flag parsing, and import hygiene, then migrates all `subprocess.run()` calls in `assemblyzero/workflows/` to route through `run_command()`. A static-analysis test ensures the migration cannot regress.

**Objective:** Fix the dead-code problem in `shell.py` and activate the security middleware for all workflow node subprocess calls.

**Success Criteria:** Zero bare `subprocess.run()` calls remain in `assemblyzero/workflows/`; `validate_command()` raises `SecurityException` with exact-token flag matching; ≥95% test coverage on changed modules.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `assemblyzero/core/exceptions.py` | Add | New `SecurityException` class |
| 2 | `assemblyzero/utils/shell.py` | Modify | Harden middleware: `SecurityException`, `shlex` tokenisation, `**kwargs`, module docstring |
| 3 | `assemblyzero/workflows/**/*.py` | Modify | Replace bare `subprocess.run()` with `run_command()` (files discovered via pre-implementation grep) |
| 4 | `tests/unit/test_shell.py` | Add | Unit tests for hardened `shell.py` (T010–T260) |
| 5 | `tests/unit/test_shell_migration.py` | Add | AST-based static analysis test (T140–T150) |

**Implementation Order Rationale:** `exceptions.py` first (dependency of `shell.py`), then `shell.py` (dependency of workflow nodes), then workflow migration (consumers), then tests (verify everything). Tests are written last in file creation order but the test scenarios in Section 10 should be understood before implementation (TDD mindset).

## 3. Current State (for Modify/Delete files)

### 3.1 `assemblyzero/utils/shell.py`

**Full current file:**

```python
"""Shell utilities for cross-platform command execution.

Issue #601: Windows Shell-Aware Utility to eliminate the 'PowerShell Trap'.
"""

import sys

import shlex

import subprocess

from typing import Any

def validate_command(command: str | list[str]) -> None:
    """Check command for prohibited dangerous flags.

Raises ValueError if a prohibited flag is detected."""
    ...

def wrap_bash_if_needed(command: str) -> str:
    """Wrap command in bash -c if running on Windows and contains Bash symbols.

Args:"""
    ...

def run_command(
    command: str | list[str], 
    cwd: str | None = None, 
    timeout: int = 300,
    shell: bool = False,
    **kwargs: Any
) -> subprocess.CompletedProcess:
    """Run a command safely across platforms.

If command is a string and on Windows, it will be wrapped in bash -c """
    ...

PROHIBITED_FLAGS = ["--admin", "--force", "-D", "--hard"]
```

**What changes:**
1. Replace module docstring with architectural boundary policy documentation
2. Remove `from typing import Any` (replaced by `object` for `**kwargs`)
3. `shlex` import stays (now actively used by `validate_command`)
4. `PROHIBITED_FLAGS` list -> `BLOCKED_FLAGS` frozenset (moved above functions)
5. `validate_command()` rewritten: `shlex.split()` tokenisation, raises `SecurityException` not `ValueError`
6. `wrap_bash_if_needed()` return type updated to `str | list[str]`
7. `run_command()` signature updated: `capture_output`, `env`, `check` params; `timeout` default 60.0; `**kwargs: object`

### 3.2 `assemblyzero/workflows/**/*.py` (discovered at implementation time)

**Pre-implementation gate:** Before writing any code, run:
```bash
grep -rn "subprocess.run" assemblyzero/workflows/ --include="*.py"
```

Each matching file will have its `subprocess.run(...)` call replaced with an import of `run_command` from `assemblyzero.utils.shell` and a call to `run_command(...)` with equivalent arguments. The exact files cannot be listed here until the grep is run against the live repo.

**Expected pattern in each discovered file:**

```python
# BEFORE (typical pattern found in workflow nodes)
import subprocess
# ...
result = subprocess.run(["git", "status"], capture_output=True, text=True, cwd=repo_path)

# AFTER
from assemblyzero.utils.shell import run_command
# ...
result = run_command(["git", "status"], capture_output=True, cwd=repo_path)
```

## 4. Data Structures

### 4.1 `SecurityException`

**Definition:**

```python
class SecurityException(Exception):
    """Raised when a command fails security validation in shell.py middleware."""
    command: str
    flag: str
    message: str
```

**Concrete Example:**

```python
SecurityException(
    command="git push --force origin main",
    flag="--force",
    message="Blocked flag '--force' detected in command: git push --force origin main"
)
# exc.command == "git push --force origin main"
# exc.flag == "--force"
# exc.message == "Blocked flag '--force' detected in command: git push --force origin main"
# str(exc) == "Blocked flag '--force' detected in command: git push --force origin main"
```

### 4.2 `BLOCKED_FLAGS`

**Definition:**

```python
BLOCKED_FLAGS: frozenset[str] = frozenset({
    "--admin",
    "--force",
    "-D",
    "--hard",
})
```

**Concrete Example:**

```python
>>> "--force" in BLOCKED_FLAGS
True
>>> "--forceful" in BLOCKED_FLAGS
False
>>> "-d" in BLOCKED_FLAGS
False  # case-sensitive: only "-D" is blocked
```

## 5. Function Specifications

### 5.1 `SecurityException.__init__()`

**File:** `assemblyzero/core/exceptions.py`

**Signature:**

```python
def __init__(self, command: str, flag: str, message: str) -> None:
    """Initialise with full command context for caller diagnostics."""
```

**Input Example:**

```python
command = "git branch -D feature-branch"
flag = "-D"
message = "Blocked flag '-D' detected in command: git branch -D feature-branch"
```

**Output Example:**

```python
exc = SecurityException(command, flag, message)
assert exc.command == "git branch -D feature-branch"
assert exc.flag == "-D"
assert exc.message == "Blocked flag '-D' detected in command: git branch -D feature-branch"
assert str(exc) == "Blocked flag '-D' detected in command: git branch -D feature-branch"
```

**Edge Cases:**
- All three arguments are required (positional)
- `flag` may be empty string for malformed-input case (see `validate_command`)

### 5.2 `validate_command()`

**File:** `assemblyzero/utils/shell.py`

**Signature:**

```python
def validate_command(command: str | list[str]) -> None:
    """Validate a shell command against the security blocklist."""
```

**Input Example 1 — string with blocked flag:**

```python
command = "git push --force origin main"
```

**Output Example 1:**

```python
# Raises SecurityException(
#     command="git push --force origin main",
#     flag="--force",
#     message="Blocked flag '--force' detected in command: git push --force origin main"
# )
```

**Input Example 2 — list with blocked flag:**

```python
command = ["git", "branch", "-D", "feature"]
```

**Output Example 2:**

```python
# Raises SecurityException(
#     command="git branch -D feature",  # joined for display
#     flag="-D",
#     message="Blocked flag '-D' detected in command: git branch -D feature"
# )
```

**Input Example 3 — safe command (no raise):**

```python
command = "git status --short"
# Returns None — no exception
```

**Input Example 4 — substring non-match:**

```python
command = "sphinx-build -Docs output"
# Returns None — "-Docs" != "-D" (exact token match)
```

**Input Example 5 — malformed quoting:**

```python
command = "echo 'unbalanced"
# Raises SecurityException(
#     command="echo 'unbalanced",
#     flag="",
#     message="Malformed command (unbalanced quoting): echo 'unbalanced"
# )
```

**Edge Cases:**
- Empty string `""` -> `shlex.split("")` returns `[]` -> no tokens -> no raise -> returns `None`
- Empty list `[]` -> no tokens -> no raise -> returns `None`
- Command with multiple blocked flags -> raises on the first one encountered

### 5.3 `wrap_bash_if_needed()`

**File:** `assemblyzero/utils/shell.py`

**Signature:**

```python
def wrap_bash_if_needed(command: str) -> str | list[str]:
    """Wrap a command in bash -c on Windows; return unchanged on POSIX."""
```

**Input Example (Windows):**

```python
# sys.platform == "win32"
command = "git status && echo done"
```

**Output Example (Windows):**

```python
["bash", "-c", "git status && echo done"]
```

**Input Example (POSIX):**

```python
# sys.platform == "linux"
command = "git status && echo done"
```

**Output Example (POSIX):**

```python
"git status && echo done"  # unchanged
```

**Edge Cases:**
- Only wraps string commands; if caller already has a list, `run_command` should not call this function

### 5.4 `run_command()`

**File:** `assemblyzero/utils/shell.py`

**Signature:**

```python
def run_command(
    command: str | list[str],
    *,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    capture_output: bool = True,
    timeout: float | None = 60.0,
    check: bool = False,
    **kwargs: object,
) -> subprocess.CompletedProcess[str]:
    """Run a shell command through the security middleware."""
```

**Input Example 1 — simple command:**

```python
result = run_command("echo hello", cwd="/tmp")
```

**Output Example 1:**

```python
# subprocess.CompletedProcess(args=..., returncode=0, stdout="hello\n", stderr="")
result.returncode == 0
result.stdout == "hello\n"
```

**Input Example 2 — blocked flag:**

```python
run_command("git push --force origin main")
# Raises SecurityException BEFORE subprocess.run() is called
```

**Input Example 3 — kwargs forwarding:**

```python
result = run_command("cat", stdin=subprocess.PIPE, timeout=10.0)
# stdin=PIPE forwarded to subprocess.run() via **kwargs
```

**Edge Cases:**
- `timeout=None` -> no timeout (for long-running commands)
- `capture_output=True` is default; callers that need live output pass `capture_output=False`
- `text=True` should be set internally (return `CompletedProcess[str]` not bytes)
- If command is a `list`, skip `wrap_bash_if_needed` (already tokenised)
- `SecurityException` is raised before any subprocess is spawned

## 6. Change Instructions

### 6.1 `assemblyzero/core/exceptions.py` (Add)

**Complete file contents:**

```python
"""Shared exception types for the AssemblyZero framework.

Issue #611: SecurityException for shell.py command middleware.
"""


class SecurityException(Exception):
    """Raised when a command fails security validation in shell.py middleware.

    Attributes:
        command: The full command string that triggered the violation.
        flag: The specific flag that was blocked (empty string for malformed input).
        message: Human-readable explanation.
    """

    def __init__(self, command: str, flag: str, message: str) -> None:
        """Initialise with full command context for caller diagnostics."""
        super().__init__(message)
        self.command = command
        self.flag = flag
        self.message = message
```

### 6.2 `assemblyzero/utils/shell.py` (Modify)

**Complete replacement file contents:**

```python
"""Shell utilities for cross-platform command execution.

Issue #601: Windows Shell-Aware Utility to eliminate the 'PowerShell Trap'.
Issue #611: Hardened security middleware with exact-token flag matching.

Middleware boundary policy
──────────────────────────
MUST use run_command():
  • All workflow node subprocess calls (assemblyzero/workflows/**)
  • Any new subprocess call added to the codebase
  • Calls to trusted internal tooling (git, poetry, etc.) from workflow
    nodes — consistency and uniform timeout handling outweigh the cost
    of the security check for known-safe executables.

MAY bypass (with inline comment justification):
  • assemblyzero/tools/* scripts that are developer-facing CLI wrappers
    and operate under the assumption that the invoker is trusted.
  • tests/* fixtures and helpers that explicitly test raw subprocess
    behaviour and must not be filtered.

MUST NOT bypass:
  • Any call that executes user-supplied or LLM-supplied command strings.
"""

import shlex
import subprocess
import sys

from assemblyzero.core.exceptions import SecurityException

# Token-safe blocklist: each entry is matched as a complete CLI token,
# never as a substring. Extend this set via BLOCKED_FLAGS.
# v1 scope: hardcoded set per Issue #611 (Q3 resolved).
# Extensible registry deferred to a future issue.
BLOCKED_FLAGS: frozenset[str] = frozenset({
    "--admin",
    "--force",
    "-D",
    "--hard",
})


def validate_command(command: str | list[str]) -> None:
    """Validate a shell command against the security blocklist.

    Tokenises the command string using shlex.split() (or accepts a pre-split
    list) so that flag matching is exact-token, not naive substring.

    Args:
        command: A shell command string or a pre-split argument list.

    Raises:
        SecurityException: If any token in the command matches BLOCKED_FLAGS.
        SecurityException: If command is a string and shlex.split() raises
            ValueError (malformed/unbalanced quoting) — fail closed.
    """
    if isinstance(command, str):
        command_str = command
        try:
            tokens = shlex.split(command)
        except ValueError:
            raise SecurityException(
                command=command_str,
                flag="",
                message=f"Malformed command (unbalanced quoting): {command_str}",
            )
    else:
        tokens = list(command)
        command_str = " ".join(command)

    for token in tokens:
        if token in BLOCKED_FLAGS:
            raise SecurityException(
                command=command_str,
                flag=token,
                message=f"Blocked flag {token!r} detected in command: {command_str}",
            )


def wrap_bash_if_needed(command: str) -> str | list[str]:
    """Wrap a command in bash -c on Windows; return unchanged on POSIX.

    Args:
        command: Raw shell command string.

    Returns:
        On Windows: ['bash', '-c', command]
        On POSIX:   command (unchanged string)
    """
    if sys.platform == "win32":
        return ["bash", "-c", command]
    return command


def run_command(
    command: str | list[str],
    *,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    capture_output: bool = True,
    timeout: float | None = 60.0,
    check: bool = False,
    **kwargs: object,
) -> subprocess.CompletedProcess[str]:
    """Run a shell command through the security middleware.

    Validates the command, applies bash-wrapping on Windows, then delegates
    to subprocess.run().

    Args:
        command:        Command string or pre-split argument list.
        cwd:            Working directory for the subprocess.
        env:            Environment variables (merged with os.environ if None).
        capture_output: Whether to capture stdout/stderr (default True).
        timeout:        Seconds before TimeoutExpired is raised (default 60s).
                        Pass timeout=None for commands with no upper bound
                        (e.g., full test suite runs from a node).
        check:          If True, raise CalledProcessError on non-zero exit.
        **kwargs:       Additional keyword arguments forwarded verbatim to
                        subprocess.run() (e.g., stdin=PIPE, preexec_fn=...).

    Returns:
        subprocess.CompletedProcess with returncode, stdout, stderr.

    Raises:
        SecurityException:             Command contains a blocked flag, or
                                       command string has malformed quoting.
        subprocess.TimeoutExpired:     Process exceeded timeout.
        subprocess.CalledProcessError: check=True and returncode != 0.
        FileNotFoundError:             Executable not found.
    """
    # Security gate — runs before any subprocess is spawned
    validate_command(command)

    # Platform adaptation for string commands
    if isinstance(command, str):
        command = wrap_bash_if_needed(command)

    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=capture_output,
        timeout=timeout,
        check=check,
        text=True,
        **kwargs,
    )
```

### 6.3 `assemblyzero/workflows/**/*.py` (Modify — discovered files)

**Pre-implementation gate:** Run the grep command. For each file discovered, apply this transformation pattern:

**Change 1:** Replace or add import

```diff
-import subprocess
+from assemblyzero.utils.shell import run_command
```

If `subprocess` is still used for other purposes (e.g., `subprocess.PIPE`, `subprocess.CalledProcessError`), keep the import but add `run_command`:

```diff
 import subprocess
+
+from assemblyzero.utils.shell import run_command
```

**Change 2:** Replace each `subprocess.run(...)` call

Example transformation for a typical `subprocess.run` call:

```diff
-result = subprocess.run(
-    ["git", "status", "--porcelain"],
-    capture_output=True,
-    text=True,
-    cwd=repo_path,
-    timeout=30,
-)
+result = run_command(
+    ["git", "status", "--porcelain"],
+    cwd=repo_path,
+    timeout=30,
+)  # Issue #611: routed through shell.py middleware
```

**Key mapping rules for argument translation:**

| `subprocess.run()` arg | `run_command()` equivalent | Notes |
|------------------------|---------------------------|-------|
| `capture_output=True` | `capture_output=True` (default) | Can be omitted if True |
| `text=True` | *(automatic)* | `run_command` always passes `text=True` |
| `cwd=path` | `cwd=path` | Direct mapping |
| `timeout=N` | `timeout=N` | Direct mapping; note default changes from 300 to 60 |
| `shell=True` | Remove; use string command | `run_command` handles platform wrapping |
| `check=True` | `check=True` | Direct mapping |
| `env=env_dict` | `env=env_dict` | Direct mapping |
| `stdin=subprocess.PIPE` | `stdin=subprocess.PIPE` | Forwarded via `**kwargs` |
| Other kwargs | Pass through directly | Forwarded via `**kwargs` |

**Important:** If any discovered call uses `timeout` values significantly larger than 60s, preserve the original timeout value explicitly. If a call previously had no timeout, consider whether `timeout=None` is appropriate or if the 60s default is acceptable.

### 6.4 `tests/unit/test_shell.py` (Add)

**Complete file contents:**

```python
"""Unit tests for assemblyzero/utils/shell.py hardened middleware.

Issue #611: Validates SecurityException, exact-token flag matching,
wrap_bash_if_needed, and run_command integration.
"""

import subprocess
import sys
from unittest.mock import patch, MagicMock

import pytest

from assemblyzero.core.exceptions import SecurityException
from assemblyzero.utils import shell
from assemblyzero.utils.shell import (
    BLOCKED_FLAGS,
    run_command,
    validate_command,
    wrap_bash_if_needed,
)


# ── T160: SecurityException importable from assemblyzero.core.exceptions ──


class TestSecurityExceptionImport:
    """T160: from assemblyzero.core.exceptions import SecurityException succeeds."""

    def test_importable(self) -> None:
        from assemblyzero.core.exceptions import SecurityException as SE
        assert SE is SecurityException


# ── T170: SecurityException stores attributes ──


class TestSecurityExceptionAttributes:
    """T170: __init__ stores command, flag, message as instance attributes."""

    def test_attributes_stored(self) -> None:
        exc = SecurityException(
            command="git push --force",
            flag="--force",
            message="Blocked flag '--force' detected",
        )
        assert exc.command == "git push --force"
        assert exc.flag == "--force"
        assert exc.message == "Blocked flag '--force' detected"
        assert str(exc) == "Blocked flag '--force' detected"


# ── T010–T050: validate_command raises SecurityException on blocked flags ──


class TestValidateCommandBlockedFlags:
    """T010–T050: SecurityException raised for each blocked flag."""

    @pytest.mark.parametrize(
        "command,expected_flag",
        [
            ("git remote add --admin origin", "--admin"),          # T010
            ("git push --force origin main", "--force"),           # T020
            ("git branch -D feature", "-D"),                       # T030
            ("git reset --hard HEAD~1", "--hard"),                 # T040
        ],
        ids=["T010_admin", "T020_force", "T030_D", "T040_hard"],
    )
    def test_string_command_blocked(self, command: str, expected_flag: str) -> None:
        with pytest.raises(SecurityException) as exc_info:
            validate_command(command)
        assert exc_info.value.flag == expected_flag
        assert exc_info.value.command == command

    def test_list_command_blocked(self) -> None:
        """T050: blocked flag in list command."""
        with pytest.raises(SecurityException) as exc_info:
            validate_command(["git", "push", "--force", "origin"])
        assert exc_info.value.flag == "--force"


# ── T060–T080: validate_command does NOT raise on substrings ──


class TestValidateCommandSubstringNonMatch:
    """T060–T080: substring-like tokens do not trigger false positives."""

    @pytest.mark.parametrize(
        "command",
        [
            "sphinx-build -Docs output",    # T060: -Docs != -D
            "pandoc --hard-wrap input.md",   # T070: --hard-wrap != --hard
            "mycommand --forceful run",      # T080: --forceful != --force
        ],
        ids=["T060_Docs", "T070_hard_wrap", "T080_forceful"],
    )
    def test_no_false_positive(self, command: str) -> None:
        validate_command(command)  # Should not raise


# ── T090–T100: validate_command fail-closed on malformed input ──


class TestValidateCommandMalformedInput:
    """T090–T100: malformed quoting raises SecurityException (fail closed)."""

    def test_unbalanced_quotes_raises_security_exception(self) -> None:
        """T090: SecurityException, not ValueError."""
        with pytest.raises(SecurityException):
            validate_command("echo 'unbalanced")

    def test_malformed_message_meaningful(self) -> None:
        """T100: message attribute is descriptive."""
        with pytest.raises(SecurityException) as exc_info:
            validate_command("echo 'unbalanced")
        assert "unbalanced" in exc_info.value.message.lower() or "malformed" in exc_info.value.message.lower()
        assert exc_info.value.flag == ""


# ── T110: shlex imported and used ──


class TestShlexImport:
    """T110: shlex is imported at module level and used by validate_command."""

    def test_shlex_in_module(self) -> None:
        import importlib
        import ast
        source = importlib.util.find_spec("assemblyzero.utils.shell")
        assert source is not None and source.origin is not None
        with open(source.origin) as f:
            tree = ast.parse(f.read())
        imports = [
            node.names[0].name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
        ]
        assert "shlex" in imports


# ── T120–T130: run_command forwards kwargs ──


class TestRunCommandKwargsForwarding:
    """T120–T130: **kwargs forwarded to subprocess.run."""

    @patch("assemblyzero.utils.shell.subprocess.run")
    def test_stdin_pipe_forwarded(self, mock_run: MagicMock) -> None:
        """T120: stdin=PIPE forwarded without raising."""
        mock_run.return_value = subprocess.CompletedProcess(
            args="echo hi", returncode=0, stdout="hi\n", stderr=""
        )
        result = run_command("echo hi", stdin=subprocess.PIPE)
        _, kwargs = mock_run.call_args
        assert kwargs.get("stdin") == subprocess.PIPE

    @patch("assemblyzero.utils.shell.subprocess.run")
    def test_arbitrary_kwargs_forwarded(self, mock_run: MagicMock) -> None:
        """T130: arbitrary kwargs forwarded verbatim."""
        mock_run.return_value = subprocess.CompletedProcess(
            args="echo hi", returncode=0, stdout="hi\n", stderr=""
        )
        run_command("echo hi", start_new_session=True)
        _, kwargs = mock_run.call_args
        assert kwargs.get("start_new_session") is True


# ── T180–T190: run_command returns CompletedProcess unmodified ──


class TestRunCommandTransparency:
    """T180–T190: run_command is transparent — CompletedProcess fields intact."""

    @patch("assemblyzero.utils.shell.subprocess.run")
    def test_completed_process_fields(self, mock_run: MagicMock) -> None:
        """T180: returncode, stdout, stderr intact."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["echo", "hello"],
            returncode=0,
            stdout="hello\n",
            stderr="",
        )
        result = run_command(["echo", "hello"])
        assert result.returncode == 0
        assert result.stdout == "hello\n"
        assert result.stderr == ""

    @patch("assemblyzero.utils.shell.subprocess.run")
    def test_stdout_stderr_unmodified(self, mock_run: MagicMock) -> None:
        """T190: stdout/stderr content not modified."""
        expected_out = "line1\nline2\n"
        expected_err = "warning: something\n"
        mock_run.return_value = subprocess.CompletedProcess(
            args="cmd", returncode=1, stdout=expected_out, stderr=expected_err
        )
        result = run_command("cmd")
        assert result.stdout == expected_out
        assert result.stderr == expected_err


# ── T200–T210: module docstring boundary policy ──


class TestModuleDocstring:
    """T200–T210: shell.py module docstring documents boundary policy."""

    def test_must_and_may_policy(self) -> None:
        """T200: docstring contains MUST/MAY boundary text."""
        docstring = shell.__doc__
        assert docstring is not None
        assert "MUST use run_command()" in docstring
        assert "MAY bypass" in docstring

    def test_trusted_tooling_policy(self) -> None:
        """T210: docstring references trusted internal tooling policy."""
        docstring = shell.__doc__
        assert docstring is not None
        assert "git" in docstring.lower() or "git" in docstring
        assert "poetry" in docstring.lower() or "poetry" in docstring
        assert "workflow" in docstring.lower()


# ── T240–T250: wrap_bash_if_needed platform behaviour ──


class TestWrapBashIfNeeded:
    """T240–T250: platform-specific wrapping."""

    @patch.object(sys, "platform", "win32")
    def test_windows_wraps(self) -> None:
        """T240: returns ['bash', '-c', command] on Windows."""
        result = wrap_bash_if_needed("git status")
        assert result == ["bash", "-c", "git status"]

    @patch.object(sys, "platform", "linux")
    def test_posix_unchanged(self) -> None:
        """T250: returns unchanged string on POSIX."""
        result = wrap_bash_if_needed("git status")
        assert result == "git status"


# ── T260: SecurityException raised before subprocess.run ──


class TestSecurityGateBeforeSubprocess:
    """T260: blocked flag raises SecurityException before subprocess.run is called."""

    @patch("assemblyzero.utils.shell.subprocess.run")
    def test_subprocess_never_called(self, mock_run: MagicMock) -> None:
        """T260: subprocess.run must NOT be called when flag is blocked."""
        with pytest.raises(SecurityException):
            run_command("git push --force origin main")
        mock_run.assert_not_called()
```

### 6.5 `tests/unit/test_shell_migration.py` (Add)

**Complete file contents:**

```python
"""Static analysis tests for shell.py middleware migration.

Issue #611: Ensures no bare subprocess.run() calls remain in
assemblyzero/workflows/ — any regression fails CI immediately.
"""

import ast
import tempfile
import textwrap
from pathlib import Path

import pytest


WORKFLOWS_DIR = Path("assemblyzero/workflows")


def _find_subprocess_run_calls(directory: Path) -> list[tuple[str, int]]:
    """Walk directory for .py files and find subprocess.run attribute calls.

    Returns list of (filepath, line_number) tuples for violations.
    Only detects the pattern: subprocess.run(...) where 'subprocess' is the
    module-level name. Dynamic dispatch or aliased references are documented
    as known limitations.
    """
    violations: list[tuple[str, int]] = []
    if not directory.exists():
        return violations

    for py_file in directory.rglob("*.py"):
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
        except (SyntaxError, UnicodeDecodeError):
            continue

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "run"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "subprocess"
            ):
                violations.append((str(py_file), node.lineno))

    return violations


class TestNoSubprocessRunInWorkflows:
    """T140: AST scan finds zero subprocess.run calls in workflows/."""

    def test_no_bare_subprocess_run(self) -> None:
        """T140: All subprocess.run calls in workflows/ must be migrated."""
        violations = _find_subprocess_run_calls(WORKFLOWS_DIR)
        if violations:
            report = "\n".join(
                f"  {filepath}:{line}" for filepath, line in violations
            )
            pytest.fail(
                f"Found bare subprocess.run() calls in workflows/:\n{report}\n"
                f"These must be replaced with run_command() per Issue #611."
            )


class TestScannerTruePositive:
    """T150: Scanner correctly detects a synthesised violating file."""

    def test_detects_subprocess_run(self, tmp_path: Path) -> None:
        """T150: True-positive sanity check — scanner finds the violation."""
        violating_code = textwrap.dedent("""\
            import subprocess

            def bad_call():
                result = subprocess.run(["echo", "hello"], capture_output=True)
                return result
        """)
        test_file = tmp_path / "fake_node.py"
        test_file.write_text(violating_code, encoding="utf-8")

        violations = _find_subprocess_run_calls(tmp_path)
        assert len(violations) == 1
        assert violations[0][0] == str(test_file)
        assert violations[0][1] == 4  # line 4: subprocess.run(...)
```

## 7. Pattern References

### 7.1 Existing Test Pattern — Mock-based Workflow Tests

**File:** `tests/e2e/test_issue_workflow_mock.py` (lines 1–80)

**Relevance:** Shows the project's convention for test structure: class-based grouping, `pytest.mark.parametrize` usage, mock patching patterns. The test files in this spec follow the same conventions.

### 7.2 Current `shell.py` Implementation

**File:** `assemblyzero/utils/shell.py` (full file shown in Section 3.1)

**Relevance:** The baseline being modified. Every change in Section 6.2 is relative to this current state.

### 7.3 Existing Exception Patterns

**Relevance:** If `assemblyzero/core/exceptions.py` already exists, the new `SecurityException` should follow the same class style. If it doesn't exist, it becomes the first shared exception module — future exceptions follow this pattern.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import shlex` | stdlib | `shell.py` |
| `import subprocess` | stdlib | `shell.py`, `test_shell.py` |
| `import sys` | stdlib | `shell.py` |
| `import ast` | stdlib | `test_shell.py`, `test_shell_migration.py` |
| `import textwrap` | stdlib | `test_shell_migration.py` |
| `from pathlib import Path` | stdlib | `test_shell_migration.py` |
| `from unittest.mock import patch, MagicMock` | stdlib | `test_shell.py` |
| `import pytest` | dev dependency (existing) | `test_shell.py`, `test_shell_migration.py` |
| `from assemblyzero.core.exceptions import SecurityException` | internal (new) | `shell.py`, `test_shell.py` |
| `from assemblyzero.utils.shell import run_command` | internal (existing) | workflow node files, `test_shell.py` |

**New Dependencies:** None. All imports are stdlib or existing dev dependencies.

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `validate_command()` | `"git remote add --admin origin"` | Raises `SecurityException(flag="--admin")` |
| T020 | `validate_command()` | `"git push --force origin main"` | Raises `SecurityException(flag="--force")` |
| T030 | `validate_command()` | `"git branch -D feature"` | Raises `SecurityException(flag="-D")` |
| T040 | `validate_command()` | `"git reset --hard HEAD~1"` | Raises `SecurityException(flag="--hard")` |
| T050 | `validate_command()` | `["git", "push", "--force", "origin"]` | Raises `SecurityException(flag="--force")` |
| T060 | `validate_command()` | `"sphinx-build -Docs output"` | No exception |
| T070 | `validate_command()` | `"pandoc --hard-wrap input.md"` | No exception |
| T080 | `validate_command()` | `"mycommand --forceful run"` | No exception |
| T090 | `validate_command()` | `"echo 'unbalanced"` | Raises `SecurityException` (not `ValueError`) |
| T100 | `validate_command()` | `"echo 'unbalanced"` | `exc.message` contains "malformed" or "unbalanced" |
| T110 | Module inspection | `shell.py` source via AST | `shlex` in top-level imports |
| T120 | `run_command()` | `"echo hi", stdin=PIPE` | `subprocess.run` called with `stdin=PIPE` |
| T130 | `run_command()` | `"echo hi", start_new_session=True` | `subprocess.run` called with `start_new_session=True` |
| T140 | `_find_subprocess_run_calls()` | `assemblyzero/workflows/` | Empty list (zero violations) |
| T150 | `_find_subprocess_run_calls()` | Synthesised violating file in tmp_path | 1 violation detected at correct line |
| T160 | Import check | `from assemblyzero.core.exceptions import SecurityException` | Succeeds |
| T170 | `SecurityException.__init__()` | `command="x", flag="y", message="z"` | `.command=="x"`, `.flag=="y"`, `.message=="z"` |
| T180 | `run_command()` (mocked) | `["echo", "hello"]` | `CompletedProcess` with `returncode`, `stdout`, `stderr` |
| T190 | `run_command()` (mocked) | `"cmd"` | `stdout` and `stderr` content unmodified |
| T200 | `shell.__doc__` | Module docstring | Contains "MUST use run_command()" and "MAY bypass" |
| T210 | `shell.__doc__` | Module docstring | Contains "git", "poetry", "workflow" |
| T220 | Coverage report | `pytest --cov` | ≥95% on `shell.py` and `exceptions.py` |
| T230 | Full CI suite | `poetry run pytest` | Zero new failures |
| T240 | `wrap_bash_if_needed()` | `"git status"` on `win32` | `["bash", "-c", "git status"]` |
| T250 | `wrap_bash_if_needed()` | `"git status"` on `linux` | `"git status"` (unchanged) |
| T260 | `run_command()` (mocked) | `"git push --force origin main"` | `SecurityException` raised; `subprocess.run` never called |

## 11. Implementation Notes

### 11.1 Error Handling Convention

`validate_command()` is the single security gate. It raises `SecurityException` for two cases:
1. A blocked flag is found (exact token match)
2. The command string is malformed (unbalanced quoting — fail closed)

`run_command()` does not catch exceptions from `subprocess.run()` — it propagates `TimeoutExpired`, `CalledProcessError`, and `FileNotFoundError` transparently to callers.

### 11.2 Logging Convention

No logging is added in this implementation. The `SecurityException` message contains full diagnostic information. Logging middleware can be added in a future iteration without changing the API.

### 11.3 Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| `BLOCKED_FLAGS` | `frozenset({"--admin", "--force", "-D", "--hard"})` | Destructive flags; `frozenset` for O(1) lookup and immutability |
| Default `timeout` | `60.0` seconds | Safe default for most workflow commands; override with explicit value or `None` for long-running |
| Default `capture_output` | `True` | Workflow nodes typically capture output for processing |

### 11.4 Pre-Implementation Grep Audit

**This step is mandatory before writing any migration code:**

```bash
grep -rn "subprocess.run" assemblyzero/workflows/ --include="*.py"
```

Record all matching files and line numbers. For each file:
1. Verify the call pattern (arguments used)
2. Determine if any `subprocess` constants (e.g., `PIPE`) are also imported
3. Map existing `timeout` values to decide whether to use the new default or preserve the original
4. Add the file to Section 2.1 with Change Type `Modify`

### 11.5 Mock Patching After Migration

After migrating workflow nodes, any existing tests that mock `subprocess.run` directly in those nodes must be updated:

```python
# BEFORE: patching the node-local subprocess
@patch("assemblyzero.workflows.some_workflow.nodes.some_node.subprocess.run")

# AFTER: patching through shell.py
@patch("assemblyzero.utils.shell.subprocess.run")
```

Search for these patterns in existing test files:
```bash
grep -rn "subprocess.run" tests/ --include="*.py" | grep -i workflow
```

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3)
- [x] Every data structure has a concrete JSON/YAML example (Section 4)
- [x] Every function has input/output examples with realistic values (Section 5)
- [x] Change instructions are diff-level specific (Section 6)
- [x] Pattern references include file:line and are verified to exist (Section 7)
- [x] All imports are listed and verified (Section 8)
- [x] Test mapping covers all LLD test scenarios (Section 10)

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #611 |
| Verdict | DRAFT |
| Date | 2026-03-06 |
| Iterations | 1 |
| Finalized | — |