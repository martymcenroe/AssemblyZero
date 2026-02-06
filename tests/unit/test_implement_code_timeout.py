"""Tests for timeout handling in implementation workflow.

Issue #321: Implementation workflow silently exits on API timeout.
Solution: Add timeout to SDK fallback, ensure errors propagate correctly.

TDD: These tests are written BEFORE implementation.
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
import time


# =============================================================================
# T010: SDK timeout handling
# =============================================================================


class TestSDKTimeout:
    """Tests for SDK timeout behavior."""

    def test_sdk_timeout_returns_error(self):
        """T010: SDK call that times out should return error tuple."""
        from assemblyzero.workflows.testing.nodes.implement_code import (
            call_claude_for_file,
        )
        import httpx

        # Mock the CLI to not exist, forcing SDK fallback
        with patch(
            "assemblyzero.workflows.testing.nodes.implement_code._find_claude_cli",
            return_value=None,
        ):
            # Mock anthropic module at import time
            mock_anthropic = MagicMock()
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client

            # Simulate timeout by raising httpx.TimeoutException
            mock_client.messages.create.side_effect = httpx.TimeoutException(
                "Connection timed out"
            )

            with patch.dict(
                "sys.modules",
                {"anthropic": mock_anthropic, "httpx": httpx},
            ):
                response, error = call_claude_for_file("test prompt")

                assert response == ""
                assert "timeout" in error.lower()

    def test_sdk_timeout_does_not_hang(self):
        """SDK should not hang indefinitely on slow responses."""
        from assemblyzero.workflows.testing.nodes.implement_code import (
            call_claude_for_file,
            SDK_TIMEOUT,
        )

        # Verify SDK_TIMEOUT constant exists and is reasonable
        assert hasattr(
            __import__(
                "assemblyzero.workflows.testing.nodes.implement_code",
                fromlist=["SDK_TIMEOUT"],
            ),
            "SDK_TIMEOUT",
        )
        assert SDK_TIMEOUT > 0
        assert SDK_TIMEOUT <= 600  # Max 10 minutes


# =============================================================================
# T020: Error propagation
# =============================================================================


class TestErrorPropagation:
    """Tests for error propagation through workflow."""

    def test_api_error_raises_implementation_error(self):
        """API errors should raise ImplementationError, not return success."""
        from assemblyzero.workflows.testing.nodes.implement_code import (
            generate_file_with_retry,
            ImplementationError,
        )

        # Mock call_claude_for_file to always return error
        with patch(
            "assemblyzero.workflows.testing.nodes.implement_code.call_claude_for_file"
        ) as mock_call:
            mock_call.return_value = ("", "API timeout after 300s")

            with pytest.raises(ImplementationError) as exc_info:
                generate_file_with_retry(
                    filepath="test.py",
                    base_prompt="test prompt",
                    audit_dir=None,
                    max_retries=3,
                )

            assert "API error" in str(exc_info.value)

    def test_timeout_error_includes_duration(self):
        """Timeout errors should include how long we waited."""
        from assemblyzero.workflows.testing.nodes.implement_code import (
            call_claude_for_file,
            SDK_TIMEOUT,
        )
        import httpx

        with patch(
            "assemblyzero.workflows.testing.nodes.implement_code._find_claude_cli",
            return_value=None,
        ):
            mock_anthropic = MagicMock()
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.side_effect = httpx.TimeoutException("timed out")

            with patch.dict(
                "sys.modules",
                {"anthropic": mock_anthropic, "httpx": httpx},
            ):
                response, error = call_claude_for_file("test")

                # Error should mention timeout duration
                assert "timeout" in error.lower()
                assert str(SDK_TIMEOUT) in error


# =============================================================================
# T030: CLI timeout handling (already exists, verify it works)
# =============================================================================


class TestCLITimeout:
    """Tests for CLI timeout behavior (should already work)."""

    def test_cli_timeout_returns_error(self):
        """CLI timeout should return error tuple, not hang."""
        from assemblyzero.workflows.testing.nodes.implement_code import (
            call_claude_for_file,
        )
        import subprocess

        with patch(
            "assemblyzero.workflows.testing.nodes.implement_code._find_claude_cli",
            return_value="/usr/bin/claude",
        ):
            with patch(
                "assemblyzero.workflows.testing.nodes.implement_code.subprocess.run"
            ) as mock_run:
                mock_run.side_effect = subprocess.TimeoutExpired(
                    cmd="claude", timeout=300
                )

                response, error = call_claude_for_file("test prompt")

                assert response == ""
                assert "timeout" in error.lower() or "timed out" in error.lower()

    def test_cli_timeout_value(self):
        """CLI timeout should be 5 minutes (300 seconds)."""
        from assemblyzero.workflows.testing.nodes.implement_code import (
            CLI_TIMEOUT,
        )

        assert CLI_TIMEOUT == 300


# =============================================================================
# T040: Workflow exit code
# =============================================================================


class TestWorkflowExitCode:
    """Tests for correct exit codes on failure."""

    def test_implementation_error_has_nonzero_exit(self, tmp_path):
        """ImplementationError should cause workflow to exit non-zero."""
        from assemblyzero.workflows.testing.nodes.implement_code import (
            implement_code,
            ImplementationError,
        )
        from assemblyzero.workflows.testing.state import TestingWorkflowState

        # Create required directories
        audit_dir = tmp_path / "docs" / "lineage" / "active" / "42-testing"
        audit_dir.mkdir(parents=True)
        (tmp_path / "src").mkdir(parents=True)

        state: TestingWorkflowState = {
            "issue_number": 42,
            "repo_root": str(tmp_path),
            "mock_mode": False,
            "audit_dir": str(audit_dir),
            "file_counter": 1,
            "iteration_count": 0,
            "lld_content": "Test LLD",
            "test_files": [],
            "test_scenarios": [],
            "files_to_modify": [
                {"path": "src/module.py", "change_type": "Add", "description": "Test"},
            ],
        }

        with patch(
            "assemblyzero.workflows.testing.nodes.implement_code.call_claude_for_file"
        ) as mock_call:
            # Return timeout error
            mock_call.return_value = ("", "SDK timeout after 300s")

            # Should raise ImplementationError, not return success
            with pytest.raises(ImplementationError):
                implement_code(state)
