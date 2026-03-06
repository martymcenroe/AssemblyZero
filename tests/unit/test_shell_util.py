"""Tests for Windows Shell-Aware Utility (Issue #601)."""

import pytest
import sys
from assemblyzero.utils.shell import wrap_bash_if_needed

@pytest.mark.skipif(sys.platform != "win32", reason="Windows specific test")
def test_wrap_bash_if_needed_windows():
    # Bash symbols
    assert wrap_bash_if_needed("echo test && ls") == "bash -c 'echo test && ls'"
    assert wrap_bash_if_needed("ls > file.txt") == "bash -c 'ls > file.txt'"
    assert wrap_bash_if_needed("echo $VAR") == "bash -c 'echo $VAR'"
    
    # No bash symbols
    assert wrap_bash_if_needed("ls") == "ls"
    assert wrap_bash_if_needed("git status") == "git status"
    
    # Single quotes in command
    assert wrap_bash_if_needed("echo 'hello' && ls") == "bash -c 'echo '\\''hello'\\'' && ls'"

def test_wrap_bash_if_needed_unix(monkeypatch):
    # Mock non-windows
    import sys as sys_module
    monkeypatch.setattr(sys_module, "platform", "linux")
    
    assert wrap_bash_if_needed("echo test && ls") == "echo test && ls"
