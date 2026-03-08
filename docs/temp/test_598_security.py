"""Tests for Permissible Command Middleware (Issue #598)."""

import pytest
from assemblyzero.utils.shell import run_command, validate_command

def test_validate_command_prohibited():
    """Test that prohibited flags are detected and blocked."""
    with pytest.raises(ValueError, match="Security Block: Command contains prohibited flag '--admin'"):
        validate_command("gh pr merge --admin")
        
    with pytest.raises(ValueError, match="Security Block: Command contains prohibited flag '--force'"):
        validate_command(["git", "push", "--force"])
        
    with pytest.raises(ValueError, match="Security Block: Command contains prohibited flag '-D'"):
        validate_command("git branch -D test")

def test_validate_command_safe():
    """Test that safe commands pass validation."""
    validate_command("ls -la")
    validate_command(["git", "status"])
    validate_command("gh pr list")

def test_run_command_blocks_prohibited():
    """Test that run_command refuses to execute prohibited commands."""
    with pytest.raises(ValueError, match="Security Block"):
        run_command("echo test --admin")
