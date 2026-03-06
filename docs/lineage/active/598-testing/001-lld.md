# Implementation Spec: Feature: Permissible Command Middleware

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #598 |
| LLD | `docs/lld/done/598-feature-permissible-command-middleware.md` |
| Generated | 2026-03-05 |
| Status | DRAFT |

## 1. Overview

This implementation will introduce a new security utility module, `assemblyzero.utils.shell`, designed to act as a "firewall" for shell commands. It will provide a validation function that parses command strings using `shlex` and blocks execution if prohibited flags like `--force`, `--admin`, `--hard`, or `-D` are detected, preventing potentially destructive or unauthorized actions.

**Objective:** Implement a mechanical "firewall" utility to validate shell commands and block dangerous flags (`--admin`, `--force`, `-D`, `--hard`) before execution.

**Success Criteria:**
- The utility must raise a `SecurityException` for commands containing prohibited flags.
- It must handle flags with assigned values (e.g., `--force=true`).
- It must not block flags within quoted strings.
- It must not block safe derivatives of flags (e.g., `--force-with-lease`).

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `assemblyzero/utils/shell.py` | Add | New module containing the command validation logic. |
| 2 | `tests/unit/test_shell_security.py` | Add | Unit tests to verify the validator's correctness and edge cases. |

**Implementation Order Rationale:** The core utility (`shell.py`) must be created before the tests that depend on it can be implemented and run.

## 3. Current State (for Modify/Delete files)

This implementation only involves adding new files. Therefore, this section is not applicable.

## 4. Data Structures

### 4.1 SecurityException

**Definition:**
A custom exception class raised when a command violates security policies.

```python
class SecurityException(Exception):
    """Raised when a command violates security policies."""
    pass
```

**Concrete Example:**
This is an exception class and is not represented as a data structure like JSON/YAML. It is raised with a message.
*Example Usage:* `raise SecurityException("Prohibited flag detected: --force")`

### 4.2 PROHIBITED_FLAGS

**Definition:**
An immutable set containing the string representation of all prohibited command-line flags.

```python
# Use frozenset for immutability and O(1) lookups.
PROHIBITED_FLAGS: frozenset[str] = frozenset({
    "--admin",
    "--force",
    "-D",
    "--hard"
})
```

**Concrete Example (YAML representation):**
```yaml
- "--admin"
- "--force"
- "-D"
- "--hard"
```

## 5. Function Specifications

### 5.1 `validate_shell_command()`

**File:** `assemblyzero/utils/shell.py`

**Signature:**

```python
import shlex
from typing import Union

# ... (SecurityException and PROHIBITED_FLAGS defined here) ...

def validate_shell_command(command: Union[str, list[str]]) -> None:
    """
    Validates a shell command against the prohibited flags list.

    Handles both string and list-based commands, as well as flag assignments
    (e.g., --force=true). Uses shlex for safe parsing of string commands.

    Args:
        command: The command string or list of arguments.

    Raises:
        SecurityException: If a prohibited flag is detected as a distinct token.
    """
    ...
```

**Input Example 1 (Unsafe String):**

```python
command = "git push --force=true origin main"
```

**Output Example 1:**

```python
# Raises SecurityException
# with message "Prohibited flag detected: --force"
```

**Input Example 2 (Safe String):**

```python
command = 'git commit -m "A message about not using --force"'
```

**Output Example 2:**

```python
None
```

**Input Example 3 (Unsafe List):**

```python
command = ["gh", "pr", "merge", "123", "--admin"]
```

**Output Example 3:**

```python
# Raises SecurityException
# with message "Prohibited flag detected: --admin"
```

**Edge Cases:**
- Safe derivative flag (`--force-with-lease`) -> Does not raise an exception.
- Flag inside a quoted string -> Does not raise an exception.
- Flag with value assignment (`--hard=true`) -> Raises an exception.
- Single dangerous flag token (`-D`) -> Raises an exception.
- Input is a list of strings vs. a single string -> Both are handled correctly.

## 6. Change Instructions

### 6.1 `assemblyzero/utils/shell.py` (Add)

**Complete file contents:**

```python
"""
Shell command security utilities.

Issue #598: Feature: Permissible Command Middleware
"""
import shlex
from typing import Union

class SecurityException(Exception):
    """Raised when a command violates security policies."""
    pass

# Use frozenset for immutability and O(1) lookups.
PROHIBITED_FLAGS: frozenset[str] = frozenset({
    "--admin",
    "--force",
    "-D",
    "--hard"
})


def validate_shell_command(command: Union[str, list[str]]) -> None:
    """
    Validates a shell command against the prohibited flags list.

    Handles both string and list-based commands, as well as flag assignments
    (e.g., --force=true). Uses shlex for safe parsing of string commands.

    Args:
        command: The command string or list of arguments.

    Raises:
        SecurityException: If a prohibited flag is detected as a distinct token.
    """
    if isinstance(command, str):
        tokens = shlex.split(command)
    else:
        tokens = command

    for token in tokens:
        # Handle flag=value syntax (e.g., --force=true) by checking the key part.
        # Split only on the first '=' to isolate the flag key.
        clean_token = token.split('=', 1)[0]

        if clean_token in PROHIBITED_FLAGS:
            raise SecurityException(f"Prohibited flag detected: {clean_token}")

```

### 6.2 `tests/unit/test_shell_security.py` (Add)

**Complete file contents:**

```python
"""
Unit tests for shell command security validation.

Issue #598: Feature: Permissible Command Middleware
"""
import pytest

from assemblyzero.utils.shell import validate_shell_command, SecurityException

# Test Scenarios from LLD Section 10.1
SAFE_COMMANDS = [
    "ls -la",
    "git push --force-with-lease",
    'git commit -m "Do not use --force"',
    ["git", "status"],
    ["echo", "A message about --hard resets"],
]

UNSAFE_COMMANDS = [
    ("git push --force", "--force"),
    ("gh pr merge --admin", "--admin"),
    ("git branch -D feature/dangerous", "-D"),
    ("git reset --hard HEAD~1", "--hard"),
    ("git push --force=true origin main", "--force"),
    (["git", "push", "--force"], "--force"),
    (["git", "reset", "--hard", "HEAD"], "--hard"),
]

@pytest.mark.parametrize("command", SAFE_COMMANDS)
def test_validate_safe_commands(command):
    """
    T010, T060, T070: Verify that safe commands pass validation without exceptions.
    """
    try:
        validate_shell_command(command)
    except SecurityException as e:
        pytest.fail(f"Safe command failed validation: '{command}'. Raised: {e}")

@pytest.mark.parametrize("command, expected_flag", UNSAFE_COMMANDS)
def test_validate_unsafe_commands(command, expected_flag):
    """
    T020-T050, T080, T090: Verify that unsafe commands raise a SecurityException.
    """
    with pytest.raises(SecurityException) as excinfo:
        validate_shell_command(command)
    
    assert f"Prohibited flag detected: {expected_flag}" in str(excinfo.value)

def test_validate_list_input_is_handled():
    """
    T080: Explicitly test that list inputs are handled correctly.
    """
    # Safe list command
    validate_shell_command(["git", "push", "--force-with-lease"])

    # Unsafe list command
    with pytest.raises(SecurityException):
        validate_shell_command(["git", "branch", "-D", "my-branch"])

```

## 7. Pattern References

### 7.1 Parameterized Testing

**File:** `tests/e2e/test_lld_workflow_mock.py` (lines 28-39)

```python
# Actual code from the referenced pattern
@pytest.mark.parametrize(
    "issue_content, expected_fragments, not_expected_fragments",
    [
        (
            "A simple feature request.",
            ["## 1. Context & Goal"],
            ["LLD is malformed"],
        ),
        (
            "# 1. Malformed LLD",
            ["LLD is malformed"],
            ["## 1. Context & Goal"],
        ),
    ],
)
def test_lld_workflow_validation(
    mock_github_api, issue_content, expected_fragments, not_expected_fragments
):
```

**Relevance:** The new test file `tests/unit/test_shell_security.py` should use `pytest.mark.parametrize` to efficiently test multiple safe and unsafe command variations. This pattern demonstrates how to set up parameterized tests with different inputs and expected outcomes, which is ideal for validating the various command strings defined in the LLD.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import shlex` | stdlib | `assemblyzero/utils/shell.py` |
| `from typing import Union` | stdlib | `assemblyzero/utils/shell.py` |
| `import pytest` | dev dependency | `tests/unit/test_shell_security.py` |
| `from assemblyzero.utils.shell import ...` | internal | `tests/unit/test_shell_security.py` |

**New Dependencies:** None. `pytest` is an existing development dependency.

## 9. Test Mapping

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

## 10. Implementation Notes

### 10.1 Fail Mode

The utility must **fail closed**. Any detection of a prohibited flag must result in a raised `SecurityException`, preventing the command from proceeding to execution. There should be no silent failures or warnings.

### 10.2 Parsing Strategy

The implementation must use `shlex.split()` for parsing command strings. This is a non-negotiable requirement from the LLD to ensure that shell quoting rules are respected and that flags inside string literals are not falsely identified as active flags.

### 10.3 Immutability

The `PROHIBITED_FLAGS` collection must be a `frozenset` to prevent any possibility of runtime modification.

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #598 |
| Verdict | APPROVED |
| Date | 2026-03-06 |
| Iterations | 0 |
| Finalized | 2026-03-06T00:57:05Z |

### Review Feedback Summary

The Implementation Spec is exemplary. It provides complete, copy-paste-ready source code for both the application logic and the unit tests. The logic accurately implements the requirements defined in the LLD, including the specific handling of edge cases like flag assignments (`--force=true`) and prohibited flag lists. The test cases utilize parameterized testing effectively to cover the required scenarios.
