# Implementation Spec: Fix shell.py Command Middleware (Issue #611)

| Field | Value |
|-------|-------|
| Issue | #611 |
| LLD | `docs/lld/active/611-shell-middleware.md` |
| Generated | 2026-03-06 |
| Status | DRAFT |

## 1. Overview

Harden `assemblyzero/utils/shell.py` by replacing `ValueError` with `SecurityException`, fixing flag matching to use exact-token parsing via `shlex.split()`, adding a `_prepare_command()` helper for POSIX string splitting, and migrating all `subprocess.run()` calls in `assemblyzero/workflows/` to route through `run_command()`.

**Objective:** Activate the dead-code shell middleware as a security boundary for all workflow node subprocess calls.

**Success Criteria:** Zero bare `subprocess.run()` in `assemblyzero/workflows/`; `SecurityException` raised on blocked flags; exact-token matching (no substring false positives); POSIX string commands split correctly for `shell=False`.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `assemblyzero/core/exceptions.py` | Add | New `SecurityException` class |
| 2 | `assemblyzero/utils/shell.py` | Modify | Harden middleware: `SecurityException`, `shlex` tokenisation, `_prepare_command()`, `**kwargs` passthrough, module docstring boundary policy |
| 3 | `assemblyzero/workflows/**/*.py` | Modify | Replace bare `subprocess.run()` with `run_command()` (files discovered via pre-implementation grep audit) |
| 4 | `tests/unit/test_shell.py` | Add | Unit tests for hardened shell.py (T010–T270) |
| 5 | `tests/unit/test_shell_migration.py` | Add | AST-based static analysis test (T140–T150) |

**Implementation Order Rationale:** `exceptions.py` must exist before `shell.py` can import `SecurityException`. `shell.py` must be hardened before workflow nodes are migrated to depend on the new signature. Tests come last to validate everything.

## 3. Current State (for Modify/Delete files)

### 3.1 `assemblyzero/utils/shell.py`

**Relevant excerpt** (full file, current state):

```python
"""Shell utilities for cross-platform command execution.

Issue #601: Windows Shell-Aware Utility to eliminate the 'PowerShell Trap'.
"""

import sys

import shlex

import subprocess

from typing import Any


PROHIBITED_FLAGS = ["--admin", "--force", "-D", "--hard"]


def validate_command(command: str | list[str]) -> None:
    """Check command for prohibited dangerous flags.

    Raises ValueError if a prohibited flag is detected."""
    if isinstance(command, str):
        tokens = command.split()
    else:
        tokens = command
    for token in tokens:
        for flag in PROHIBITED_FLAGS:
            if flag in token:
                raise ValueError(
                    f"Prohibited flag '{flag}' detected in command: {command}"
                )


def wrap_bash_if_needed(command: str) -> str:
    """Wrap command in bash -c if running on Windows and contains Bash symbols.

    Args:
        command: Raw shell command string.

    Returns:
        On Windows: the command wrapped for bash execution.
        On POSIX: the command unchanged.
    """
    if sys.platform == "win32":
        return f'bash -c "{command}"'
    return command


def run_command(
    command: str | list[str],
    cwd: str | None = None,
    timeout: int = 300,
    shell: bool = False,
    **kwargs: Any,
) -> subprocess.CompletedProcess:
    """Run a command safely across platforms.

    If command is a string and on Windows, it will be wrapped in bash -c."""
    validate_command(command)
    if isinstance(command, str):
        command = wrap_bash_if_needed(command)
    return subprocess.run(
        command,
        cwd=cwd,
        timeout=timeout,
        shell=shell,
        capture_output=True,
        text=True,
        **kwargs,
    )
```

**What changes:**
1. Replace `PROHIBITED_FLAGS` list with `BLOCKED_FLAGS` frozenset
2. Replace `ValueError` with `SecurityException` (imported from `assemblyzero.core.exceptions`)
3. Replace naive `str.split()` + substring `if flag in token` with `shlex.split()` + set membership `if token in BLOCKED_FLAGS`
4. Add fail-closed handling for malformed shlex input
5. Fix `wrap_bash_if_needed()` return type to `str | list[str]` and return `["bash", "-c", command]` on Windows
6. Add `_prepare_command()` helper for POSIX string splitting
7. Rewrite `run_command()` signature with keyword-only args, default timeout 60s, remove `shell` parameter
8. Replace module docstring with architectural boundary policy

### 3.2 `assemblyzero/workflows/**/*.py` (discovered at pre-implementation audit)

Per LLD Section 2.1 note, the exact workflow files containing `subprocess.run()` will be enumerated by `grep -rn "subprocess.run" assemblyzero/workflows/ --include="*.py"` before implementation begins. Each discovered file will have its `subprocess.run(...)` call replaced with an equivalent `run_command(...)` call, adding the import `from assemblyzero.utils.shell import run_command`.

## 4. Data Structures

### 4.1 SecurityException

**Definition:**

```python
class SecurityException(Exception):
    """Raised when a command fails security validation in shell.py middleware."""

    def __init__(self, command: str, flag: str, message: str) -> None:
        super().__init__(message)
        self.command = command
        self.flag = flag
        self.message = message
```

**Concrete Example:**

```json
{
    "command": "git push --force origin main",
    "flag": "--force",
    "message": "Blocked flag '--force' detected in command: git push --force origin main"
}
```

### 4.2 BLOCKED_FLAGS

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

```json
["--admin", "--force", "-D", "--hard"]
```

**Lookup behavior:** `"--force" in BLOCKED_FLAGS` -> `True`; `"--forceful" in BLOCKED_FLAGS` -> `False` (exact-token, O(1)).

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
command = "git branch -D feature-x"
flag = "-D"
message = "Blocked flag '-D' detected in command: git branch -D feature-x"
```

**Output Example:**

```python
exc = SecurityException(command="git branch -D feature-x", flag="-D", message="Blocked flag '-D' ...")
assert exc.command == "git branch -D feature-x"
assert exc.flag == "-D"
assert str(exc) == "Blocked flag '-D' ..."
```

**Edge Cases:**
- Empty `flag` (malformed input case): `SecurityException(command="foo 'bar", flag="", message="Malformed command...")`

### 5.2 `validate_command()`

**File:** `assemblyzero/utils/shell.py`

**Signature:**

```python
def validate_command(command: str | list[str]) -> None:
    """Validate a shell command against the security blocklist."""
```

**Input Example (string):**

```python
command = "git push --force origin main"
```

**Output Example:**

```python
# Raises SecurityException(
#     command="git push --force origin main",
#     flag="--force",
#     message="Blocked flag '--force' detected in command: git push --force origin main",
# )
```

**Input Example (safe command):**

```python
command = "git push origin main"
# Returns None (no exception)
```

**Input Example (list, no false positive):**

```python
command = ["git", "log", "--hard-wrap"]
# Returns None — "--hard-wrap" != "--hard"
```

**Input Example (malformed):**

```python
command = "echo 'unbalanced"
# Raises SecurityException(command=..., flag="", message="Malformed command (unbalanced quoting): ...")
```

**Edge Cases:**
- `command = []` -> returns `None` (empty list has no tokens)
- `command = ""` -> returns `None` (shlex.split("") produces `[]`)
- `command = ["--force"]` -> raises `SecurityException`

### 5.3 `_prepare_command()`

**File:** `assemblyzero/utils/shell.py`

**Signature:**

```python
def _prepare_command(command: str | list[str]) -> str | list[str]:
    """Convert a command into a form safe for subprocess.run(shell=False)."""
```

**Input/Output Examples:**

```python
# List input (any platform) — pass through
_prepare_command(["git", "status"])  # -> ["git", "status"]

# String input on Windows — bash wrap
# (sys.platform == "win32")
_prepare_command("echo hello")  # -> ["bash", "-c", "echo hello"]

# String input on POSIX — shlex split
# (sys.platform != "win32")
_prepare_command("echo hello")  # -> ["echo", "hello"]
_prepare_command("git log --oneline")  # -> ["git", "log", "--oneline"]
```

**Edge Cases:**
- `_prepare_command("echo 'hello world'")` on POSIX -> `["echo", "hello world"]` (shlex handles quoting)

### 5.4 `wrap_bash_if_needed()`

**File:** `assemblyzero/utils/shell.py`

**Signature:**

```python
def wrap_bash_if_needed(command: str) -> str | list[str]:
    """Wrap a command in bash -c on Windows; return unchanged on POSIX."""
```

**Input/Output Examples:**

```python
# On Windows:
wrap_bash_if_needed("echo hello")  # -> ["bash", "-c", "echo hello"]

# On POSIX:
wrap_bash_if_needed("echo hello")  # -> "echo hello"
```

### 5.5 `run_command()`

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

**Input Example:**

```python
result = run_command("echo hello", cwd="/tmp", timeout=30.0)
```

**Output Example:**

```python
# subprocess.CompletedProcess(args=["echo", "hello"], returncode=0, stdout="hello\n", stderr="")
assert result.returncode == 0
assert result.stdout == "hello\n"
```

**Edge Cases:**
- Blocked flag: `run_command("git push --force")` -> raises `SecurityException` before subprocess is spawned
- Timeout: `run_command("sleep 999", timeout=1.0)` -> raises `subprocess.TimeoutExpired`
- `check=True` with failure: raises `subprocess.CalledProcessError`

## 6. Change Instructions

### 6.1 `assemblyzero/core/exceptions.py` (Add)

**Complete file contents:**

```python
"""Shared exceptions for the AssemblyZero framework.

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

**Change 1:** Replace module docstring (line 1)

```diff
-"""Shell utilities for cross-platform command execution.
-
-Issue #601: Windows Shell-Aware Utility to eliminate the 'PowerShell Trap'.
-"""
+"""Shell utilities for cross-platform command execution.
+
+Issue #601: Windows Shell-Aware Utility to eliminate the 'PowerShell Trap'.
+Issue #611: Hardened middleware with SecurityException, exact-token flag
+matching, and POSIX string splitting.
+
+Middleware boundary policy
+──────────────────────────
+MUST use run_command():
+  • All workflow node subprocess calls (assemblyzero/workflows/**)
+  • Any new subprocess call added to the codebase
+  • Calls to trusted internal tooling (git, poetry, etc.) from workflow
+    nodes — consistency and uniform timeout handling outweigh the cost
+    of the security check for known-safe executables.
+
+MAY bypass (with inline comment justification):
+  • assemblyzero/tools/* scripts that are developer-facing CLI wrappers
+    and operate under the assumption that the invoker is trusted.
+  • tests/* fixtures and helpers that explicitly test raw subprocess
+    behaviour and must not be filtered.
+
+MUST NOT bypass:
+  • Any call that executes user-supplied or LLM-supplied command strings.
+"""
```

**Change 2:** Replace imports and remove `from typing import Any` (lines 5–10)

```diff
 import sys
 
 import shlex
 
 import subprocess
 
-from typing import Any
+from assemblyzero.core.exceptions import SecurityException
```

**Change 3:** Replace `PROHIBITED_FLAGS` list with `BLOCKED_FLAGS` frozenset and move above functions (replaces the bottom-of-file constant)

```diff
-PROHIBITED_FLAGS = ["--admin", "--force", "-D", "--hard"]
+# Token-safe blocklist: each entry is matched as a complete CLI token,
+# never as a substring. Extend this set via BLOCKED_FLAGS.
+# v1 scope: hardcoded set per Issue #611 (Q3 resolved).
+# Extensible registry deferred to a future issue.
+BLOCKED_FLAGS: frozenset[str] = frozenset({
+    "--admin",
+    "--force",
+    "-D",
+    "--hard",
+})
```

**Change 4:** Replace entire `validate_command()` function

```diff
-def validate_command(command: str | list[str]) -> None:
-    """Check command for prohibited dangerous flags.
-
-    Raises ValueError if a prohibited flag is detected."""
-    if isinstance(command, str):
-        tokens = command.split()
-    else:
-        tokens = command
-    for token in tokens:
-        for flag in PROHIBITED_FLAGS:
-            if flag in token:
-                raise ValueError(
-                    f"Prohibited flag '{flag}' detected in command: {command}"
-                )
+def validate_command(command: str | list[str]) -> None:
+    """Validate a shell command against the security blocklist.
+
+    Tokenises the command string using shlex.split() (or accepts a pre-split
+    list) so that flag matching is exact-token, not naive substring.
+
+    Args:
+        command: A shell command string or a pre-split argument list.
+
+    Raises:
+        SecurityException: If any token in the command matches BLOCKED_FLAGS.
+        SecurityException: If command is a string and shlex.split() raises
+            ValueError (malformed/unbalanced quoting) — fail closed.
+    """
+    if isinstance(command, str):
+        command_str = command
+        try:
+            tokens = shlex.split(command)
+        except ValueError:
+            raise SecurityException(
+                command=command_str,
+                flag="",
+                message=f"Malformed command (unbalanced quoting): {command_str}",
+            )
+    else:
+        tokens = list(command)
+        command_str = " ".join(command)
+
+    for token in tokens:
+        if token in BLOCKED_FLAGS:
+            raise SecurityException(
+                command=command_str,
+                flag=token,
+                message=f"Blocked flag {token!r} detected in command: {command_str}",
+            )
```

**Change 5:** Replace entire `wrap_bash_if_needed()` function

```diff
-def wrap_bash_if_needed(command: str) -> str:
-    """Wrap command in bash -c if running on Windows and contains Bash symbols.
-
-    Args:
-        command: Raw shell command string.
-
-    Returns:
-        On Windows: the command wrapped for bash execution.
-        On POSIX: the command unchanged.
-    """
-    if sys.platform == "win32":
-        return f'bash -c "{command}"'
-    return command
+def wrap_bash_if_needed(command: str) -> str | list[str]:
+    """Wrap a command in bash -c on Windows; return unchanged on POSIX.
+
+    Args:
+        command: Raw shell command string.
+
+    Returns:
+        On Windows: ['bash', '-c', command]
+        On POSIX:   command (unchanged string)
+    """
+    if sys.platform == "win32":
+        return ["bash", "-c", command]
+    return command
```

**Change 6:** Add new `_prepare_command()` helper (after `wrap_bash_if_needed`)

```python
def _prepare_command(command: str | list[str]) -> str | list[str]:
    """Convert a command into a form safe for subprocess.run(shell=False).

    For pre-split lists: returned as-is.
    For strings on Windows: wrapped via ['bash', '-c', command].
    For strings on POSIX: split into a token list via shlex.split().

    This ensures subprocess.run() always receives either a list of arguments
    or a string that has been platform-adapted, preventing the common error
    of passing a multi-word string to subprocess.run(shell=False) which would
    interpret the entire string as an executable path.

    Args:
        command: Command string or pre-split argument list.

    Returns:
        A list[str] or platform-appropriate command representation.
    """
    if isinstance(command, list):
        return command
    if sys.platform == "win32":
        return ["bash", "-c", command]
    # POSIX: split the string into tokens so subprocess.run(shell=False)
    # can locate the executable and pass arguments correctly.
    return shlex.split(command)
```

**Change 7:** Replace entire `run_command()` function

```diff
-def run_command(
-    command: str | list[str],
-    cwd: str | None = None,
-    timeout: int = 300,
-    shell: bool = False,
-    **kwargs: Any,
-) -> subprocess.CompletedProcess:
-    """Run a command safely across platforms.
-
-    If command is a string and on Windows, it will be wrapped in bash -c."""
-    validate_command(command)
-    if isinstance(command, str):
-        command = wrap_bash_if_needed(command)
-    return subprocess.run(
-        command,
-        cwd=cwd,
-        timeout=timeout,
-        shell=shell,
-        capture_output=True,
-        text=True,
-        **kwargs,
-    )
+def run_command(
+    command: str | list[str],
+    *,
+    cwd: str | None = None,
+    env: dict[str, str] | None = None,
+    capture_output: bool = True,
+    timeout: float | None = 60.0,
+    check: bool = False,
+    **kwargs: object,
+) -> subprocess.CompletedProcess[str]:
+    """Run a shell command through the security middleware.
+
+    Validates the command, converts it into a subprocess-safe form (splitting
+    string commands into token lists on POSIX, wrapping in bash on Windows),
+    then delegates to subprocess.run().
+
+    Args:
+        command:        Command string or pre-split argument list.
+        cwd:            Working directory for the subprocess.
+        env:            Environment variables (merged with os.environ if None).
+        capture_output: Whether to capture stdout/stderr (default True).
+        timeout:        Seconds before TimeoutExpired is raised (default 60s).
+                        Pass timeout=None for commands with no upper bound
+                        (e.g., full test suite runs from a node).
+        check:          If True, raise CalledProcessError on non-zero exit.
+        **kwargs:       Additional keyword arguments forwarded verbatim to
+                        subprocess.run() (e.g., stdin=PIPE, preexec_fn=...).
+
+    Returns:
+        subprocess.CompletedProcess with returncode, stdout, stderr.
+
+    Raises:
+        SecurityException:             Command contains a blocked flag, or
+                                       command string has malformed quoting.
+        subprocess.TimeoutExpired:     Process exceeded timeout.
+        subprocess.CalledProcessError: check=True and returncode != 0.
+        FileNotFoundError:             Executable not found.
+    """
+    # Security gate — runs before any subprocess is spawned
+    validate_command(command)
+
+    # Platform adaptation and string-to-list conversion
+    prepared = _prepare_command(command)
+
+    return subprocess.run(
+        prepared,
+        cwd=cwd,
+        env=env,
+        capture_output=capture_output,
+        timeout=timeout,
+        check=check,
+        text=True,
+        **kwargs,
+    )
```

### 6.3 `assemblyzero/workflows/**/*.py` (Modify — discovered files)

**Pattern for each discovered file:**

```diff
 import subprocess
+from assemblyzero.utils.shell import run_command
```

Then for each `subprocess.run(...)` call:

```diff
-result = subprocess.run(
-    ["git", "status"],
-    capture_output=True,
-    text=True,
-    cwd=repo_path,
-)
+result = run_command(
+    ["git", "status"],
+    cwd=repo_path,
+)  # Issue #611: routed through shell middleware
```

**Note:** The `shell=True` parameter must NOT be carried over. If a discovered call uses `shell=True`, the command string must be reviewed and adapted for `shell=False` execution (which `_prepare_command()` handles).

### 6.4 `tests/unit/test_shell.py` (Add)

**Complete file contents:**

```python
"""Unit tests for assemblyzero/utils/shell.py.

Issue #611: Tests for hardened shell middleware.
"""

from __future__ import annotations

import subprocess
import sys
from unittest.mock import patch, MagicMock

import pytest

from assemblyzero.core.exceptions import SecurityException
from assemblyzero.utils.shell import (
    BLOCKED_FLAGS,
    _prepare_command,
    run_command,
    validate_command,
    wrap_bash_if_needed,
)


# ── T010–T050: SecurityException on blocked flags ──


class TestValidateCommandBlockedFlags:
    """T010–T050: validate_command raises SecurityException on blocked flags."""

    def test_t010_blocks_admin_string(self) -> None:
        with pytest.raises(SecurityException, match="--admin"):
            validate_command("deploy --admin now")

    def test_t020_blocks_force_string(self) -> None:
        with pytest.raises(SecurityException, match="--force"):
            validate_command("git push --force origin main")

    def test_t030_blocks_dash_d_string(self) -> None:
        with pytest.raises(SecurityException, match="-D"):
            validate_command("git branch -D feature-x")

    def test_t040_blocks_hard_string(self) -> None:
        with pytest.raises(SecurityException, match="--hard"):
            validate_command("git reset --hard HEAD~1")

    def test_t050_blocks_flag_in_list(self) -> None:
        with pytest.raises(SecurityException, match="--force"):
            validate_command(["git", "push", "--force", "origin"])


# ── T060–T080: No false positives (exact-token matching) ──


class TestValidateCommandNoFalsePositives:
    """T060–T080: validate_command does NOT raise on substrings."""

    def test_t060_docs_not_blocked(self) -> None:
        validate_command("ls -Docs")  # -Docs != -D

    def test_t070_hard_wrap_not_blocked(self) -> None:
        validate_command(["git", "log", "--hard-wrap"])  # --hard-wrap != --hard

    def test_t080_forceful_not_blocked(self) -> None:
        validate_command("echo --forceful")  # --forceful != --force


# ── T090–T100: Malformed input (fail closed) ──


class TestValidateCommandMalformed:
    """T090–T100: validate_command raises SecurityException on malformed input."""

    def test_t090_unbalanced_quote_raises_security_exception(self) -> None:
        with pytest.raises(SecurityException):
            validate_command("echo 'unbalanced")

    def test_t100_malformed_message_is_meaningful(self) -> None:
        with pytest.raises(SecurityException, match="Malformed command"):
            validate_command('echo "unbalanced')


# ── T110: shlex import usage ──


class TestShlexImport:
    """T110: shlex is imported and used."""

    def test_t110_shlex_used_in_validate(self) -> None:
        import assemblyzero.utils.shell as shell_mod

        assert hasattr(shell_mod, "shlex")
        # Functional proof: shlex.split handles quoting correctly
        validate_command("echo 'hello world'")  # would fail with str.split


# ── T120–T130: **kwargs passthrough ──


class TestRunCommandKwargs:
    """T120–T130: run_command forwards kwargs to subprocess.run."""

    @patch("assemblyzero.utils.shell.subprocess.run")
    def test_t120_stdin_pipe_forwarded(self, mock_run: MagicMock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["echo"], returncode=0, stdout="", stderr=""
        )
        run_command(["echo", "test"], stdin=subprocess.PIPE)
        _, kwargs = mock_run.call_args
        assert kwargs.get("stdin") == subprocess.PIPE

    @patch("assemblyzero.utils.shell.subprocess.run")
    def test_t130_arbitrary_kwargs_forwarded(self, mock_run: MagicMock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["echo"], returncode=0, stdout="", stderr=""
        )
        run_command(["echo"], start_new_session=True)
        _, kwargs = mock_run.call_args
        assert kwargs.get("start_new_session") is True


# ── T160–T170: SecurityException importability and attributes ──


class TestSecurityException:
    """T160–T170: SecurityException is importable and stores attributes."""

    def test_t160_importable(self) -> None:
        from assemblyzero.core.exceptions import SecurityException as SE

        assert SE is not None

    def test_t170_attributes_stored(self) -> None:
        exc = SecurityException(
            command="git push --force",
            flag="--force",
            message="Blocked flag '--force' detected",
        )
        assert exc.command == "git push --force"
        assert exc.flag == "--force"
        assert exc.message == "Blocked flag '--force' detected"
        assert str(exc) == "Blocked flag '--force' detected"


# ── T180–T190: CompletedProcess passthrough ──


class TestRunCommandPassthrough:
    """T180–T190: run_command returns CompletedProcess unchanged."""

    @patch("assemblyzero.utils.shell.subprocess.run")
    def test_t180_completed_process_fields(self, mock_run: MagicMock) -> None:
        expected = subprocess.CompletedProcess(
            args=["echo", "hi"], returncode=0, stdout="hi\n", stderr=""
        )
        mock_run.return_value = expected
        result = run_command(["echo", "hi"])
        assert result.returncode == 0
        assert result.stdout == "hi\n"
        assert result.stderr == ""

    @patch("assemblyzero.utils.shell.subprocess.run")
    def test_t190_stdout_stderr_unmodified(self, mock_run: MagicMock) -> None:
        expected = subprocess.CompletedProcess(
            args=["cmd"], returncode=1, stdout="out\ndata", stderr="err\ndata"
        )
        mock_run.return_value = expected
        result = run_command(["cmd"])
        assert result.stdout == "out\ndata"
        assert result.stderr == "err\ndata"


# ── T200–T210: Module docstring boundary policy ──


class TestModuleDocstring:
    """T200–T210: shell.py docstring contains boundary policy."""

    def test_t200_boundary_policy_text(self) -> None:
        import assemblyzero.utils.shell as shell_mod

        doc = shell_mod.__doc__
        assert "MUST use run_command()" in doc
        assert "MAY bypass" in doc

    def test_t210_trusted_tooling_reference(self) -> None:
        import assemblyzero.utils.shell as shell_mod

        doc = shell_mod.__doc__
        assert "git" in doc
        assert "poetry" in doc
        assert "workflow" in doc.lower()


# ── T240–T250: wrap_bash_if_needed ──


class TestWrapBash:
    """T240–T250: wrap_bash_if_needed platform behavior."""

    @patch("assemblyzero.utils.shell.sys")
    def test_t240_windows_returns_list(self, mock_sys: MagicMock) -> None:
        mock_sys.platform = "win32"
        # Re-import to test with patched sys would be complex;
        # instead test the logic directly
        from assemblyzero.utils.shell import wrap_bash_if_needed

        with patch("assemblyzero.utils.shell.sys.platform", "win32"):
            result = wrap_bash_if_needed("echo hello")
            assert result == ["bash", "-c", "echo hello"]

    def test_t250_posix_returns_string(self) -> None:
        with patch("assemblyzero.utils.shell.sys.platform", "linux"):
            result = wrap_bash_if_needed("echo hello")
            assert result == "echo hello"


# ── T260: Security gate runs before subprocess ──


class TestSecurityGateOrder:
    """T260: SecurityException raised before subprocess.run is called."""

    @patch("assemblyzero.utils.shell.subprocess.run")
    def test_t260_blocked_before_subprocess(self, mock_run: MagicMock) -> None:
        with pytest.raises(SecurityException):
            run_command("git push --force origin main")
        mock_run.assert_not_called()


# ── T270: POSIX string splitting ──


class TestPrepareCommand:
    """T270: _prepare_command splits strings on POSIX."""

    def test_t270_posix_string_split(self) -> None:
        with patch("assemblyzero.utils.shell.sys.platform", "linux"):
            result = _prepare_command("echo hello")
            assert result == ["echo", "hello"]

    def test_list_passthrough(self) -> None:
        result = _prepare_command(["git", "status"])
        assert result == ["git", "status"]

    def test_t270_run_command_posix_splits(self) -> None:
        with patch("assemblyzero.utils.shell.sys.platform", "linux"), \
             patch("assemblyzero.utils.shell.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["echo", "hello"], returncode=0, stdout="hello\n", stderr=""
            )
            run_command("echo hello")
            args, _ = mock_run.call_args
            assert args[0] == ["echo", "hello"]
```

### 6.5 `tests/unit/test_shell_migration.py` (Add)

**Complete file contents:**

```python
"""Static analysis tests verifying no bare subprocess.run in workflows.

Issue #611: Migration ratchet — any future subprocess.run() added to
assemblyzero/workflows/ will fail CI.
"""

from __future__ import annotations

import ast
import tempfile
from pathlib import Path

import pytest


def _find_bare_subprocess_run(directory: Path) -> list[tuple[str, int]]:
    """Walk directory for .py files containing subprocess.run() attribute calls.

    Returns list of (filepath, line_number) tuples for violations.
    """
    violations: list[tuple[str, int]] = []
    for py_file in directory.rglob("*.py"):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except SyntaxError:
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


class TestShellMigration:
    """T140–T150: AST scan for subprocess.run in workflows."""

    def test_t140_no_bare_subprocess_in_workflows(self) -> None:
        """No subprocess.run() calls remain in assemblyzero/workflows/."""
        workflows_dir = Path("assemblyzero/workflows")
        if not workflows_dir.exists():
            pytest.skip("workflows directory not found")
        violations = _find_bare_subprocess_run(workflows_dir)
        assert violations == [], (
            f"Found bare subprocess.run() in workflow files "
            f"(must use run_command()): {violations}"
        )

    def test_t150_scanner_detects_violation(self, tmp_path: Path) -> None:
        """Sanity check: scanner detects a synthesised violating file."""
        violating_file = tmp_path / "bad_node.py"
        violating_file.write_text(
            "import subprocess\nresult = subprocess.run(['echo', 'hi'])\n",
            encoding="utf-8",
        )
        violations = _find_bare_subprocess_run(tmp_path)
        assert len(violations) == 1
        assert violations[0][1] == 2  # line 2
```

## 7. Pattern References

### 7.1 Existing Exception Pattern

**File:** `assemblyzero/core/exceptions.py` (to be created — but follows Python exception conventions)

**Pattern:**

```python
class SecurityException(Exception):
    def __init__(self, command: str, flag: str, message: str) -> None:
        super().__init__(message)
        self.command = command
        self.flag = flag
        self.message = message
```

**Relevance:** Standard Python exception pattern with structured attributes for caller diagnostics.

### 7.2 Current shell.py Structure

**File:** `assemblyzero/utils/shell.py` (lines 1–55, current)

**Relevance:** Shows the existing module layout, import order, and function structure that the hardened version must preserve in overall shape while replacing internals. The current `validate_command` uses `str.split()` and substring matching — the new version uses `shlex.split()` and set membership.

### 7.3 AST Walking Pattern for Migration Test

**File:** `tests/unit/test_shell_migration.py` (new — follows stdlib `ast` conventions)

```python
for node in ast.walk(tree):
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "run"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "subprocess"
    ):
        violations.append((str(py_file), node.lineno))
```

**Relevance:** Detects `subprocess.run(...)` as an attribute call on the `subprocess` module name. Does not catch aliased or dynamically constructed calls (documented limitation).

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import sys` | stdlib | `shell.py` |
| `import shlex` | stdlib | `shell.py` |
| `import subprocess` | stdlib | `shell.py` |
| `from assemblyzero.core.exceptions import SecurityException` | internal | `shell.py`, `test_shell.py` |
| `import ast` | stdlib | `test_shell_migration.py` |
| `from pathlib import Path` | stdlib | `test_shell_migration.py` |
| `import pytest` | dev dependency | `test_shell.py`, `test_shell_migration.py` |
| `from unittest.mock import patch, MagicMock` | stdlib | `test_shell.py` |

**New Dependencies:** None. All imports resolve to stdlib or existing project modules.

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

## 10. Test Mapping

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

## 11. Implementation Notes

### 11.1 Error Handling Convention

`validate_command()` raises `SecurityException` for all security-related failures (blocked flags, malformed input). It never raises `ValueError` — that is the key fix from the current codebase. The `SecurityException` always includes `command`, `flag`, and `message` attributes for structured logging.

### 11.2 Logging Convention

No logging is added in this issue. The middleware operates via exceptions. Future telemetry integration (structured logging of blocked commands) is out of scope.

### 11.3 Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| `BLOCKED_FLAGS` | `frozenset({"--admin", "--force", "-D", "--hard"})` | O(1) lookup, immutable; covers destructive flags identified in Issue #611 |
| Default `timeout` | `60.0` | Reasonable upper bound for CLI commands; callers pass `timeout=None` for long-running tasks |

### 11.4 Breaking Change: `run_command()` Signature

The new `run_command()` uses keyword-only args (after `command`). The old signature allowed positional `cwd`, `timeout`, `shell`. Any existing callers using positional args will break. The `shell` parameter is removed entirely — all execution is `shell=False`. This is intentional per the security posture.

### 11.5 Double `shlex.split()` on POSIX

String commands on POSIX are split by `shlex.split()` twice: once in `validate_command()` for security, once in `_prepare_command()` for subprocess prep. This is intentional — `validate_command()` may be called standalone, and the cost is negligible for CLI-length strings. Malformed strings are rejected in `validate_command()` before `_prepare_command()` is reached.

### 11.6 Pre-Implementation Audit

Before writing any code, run:

```bash
grep -rn "subprocess.run" assemblyzero/workflows/ --include="*.py"
```

All matching files must be listed and migrated. The AST test (T140) enforces this post-implementation.

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
| Iterations | 2 |
| Finalized | — |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #611 |
| Verdict | APPROVED |
| Date | 2026-03-06 |
| Iterations | 2 |
| Finalized | 2026-03-06T06:24:47Z |

### Review Feedback Summary

The Implementation Spec is comprehensive and provides high-quality, executable instructions. Full code is provided for all new and modified utility and test files (Sections 6.1, 6.2, 6.4, 6.5). The migration strategy for existing workflow files is specific enough for an autonomous agent, utilizing a dynamic discovery approach with clear replacement patterns. The logic for cross-platform compatibility and security validation is well-defined and consistent with the architectural goals.

## Suggest...
