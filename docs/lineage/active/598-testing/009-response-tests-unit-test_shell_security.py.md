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
