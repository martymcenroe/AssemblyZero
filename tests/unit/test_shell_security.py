"""Tests for Permissible Command Middleware (Issue #598, #611)."""

import pytest
from assemblyzero.core.errors import SecurityException
from assemblyzero.utils.shell import run_command, validate_command


class TestValidateCommand:
    def test_prohibited_admin(self):
        with pytest.raises(SecurityException, match="--admin"):
            validate_command("gh pr merge --admin")

    def test_prohibited_force(self):
        with pytest.raises(SecurityException, match="--force"):
            validate_command(["git", "push", "--force"])

    def test_prohibited_dash_D(self):
        with pytest.raises(SecurityException, match="-D"):
            validate_command("git branch -D test")

    def test_prohibited_hard(self):
        with pytest.raises(SecurityException, match="--hard"):
            validate_command("git reset --hard")

    def test_safe_commands_pass(self):
        validate_command("ls -la")
        validate_command(["git", "status"])
        validate_command("gh pr list")

    def test_no_false_positive_substring(self):
        """Flags inside other tokens must NOT trigger (e.g., --Description, --hard-wrap)."""
        validate_command("echo --Description")
        validate_command("pandoc --hard-wrap")
        validate_command(["tool", "--force-color"])

    def test_exception_attributes(self):
        with pytest.raises(SecurityException) as exc_info:
            validate_command("git push --force origin")
        assert exc_info.value.flag == "--force"
        assert "--force" in exc_info.value.command


class TestRunCommandBlocks:
    def test_run_command_refuses_prohibited(self):
        with pytest.raises(SecurityException, match="Security Block"):
            run_command("echo test --admin")
