"""Tests for timeout handling in implementation workflow.

Issue #321: Implementation workflow silently exits on API timeout.
Issue #783: Refactored to test through unified provider gate (get_provider).
"""

import pytest
from unittest.mock import MagicMock, patch


# =============================================================================
# T010: Provider timeout handling
# =============================================================================


class TestProviderTimeout:
    """Tests for provider timeout behavior via get_provider."""

    def test_provider_timeout_returns_error(self):
        """T010: Provider call that times out should return error tuple."""
        from assemblyzero.workflows.testing.nodes.implement_code import (
            call_claude_for_file,
        )
        from assemblyzero.core.llm_provider import LLMCallResult

        mock_provider = MagicMock()
        mock_provider.invoke.return_value = LLMCallResult(
            success=False,
            response=None,
            raw_response=None,
            error_message="timeout after 300s waiting for response",
            provider="claude",
            model_used="opus",
            duration_ms=300000,
            attempts=1,
            retryable=True,
        )

        with patch(
            "assemblyzero.workflows.testing.nodes.implementation.claude_client.get_provider",
            return_value=mock_provider,
        ):
            response, error = call_claude_for_file("test prompt")

            assert response == ""
            assert "timeout" in error.lower()

    def test_provider_exception_returns_error(self):
        """Provider raising an exception should return error tuple."""
        from assemblyzero.workflows.testing.nodes.implement_code import (
            call_claude_for_file,
        )

        with patch(
            "assemblyzero.workflows.testing.nodes.implementation.claude_client.get_provider",
            side_effect=Exception("connection failed"),
        ):
            response, error = call_claude_for_file("test prompt")

            assert response == ""
            assert "Provider error" in error
            assert "connection failed" in error


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
            "assemblyzero.workflows.testing.nodes.implementation.orchestrator.call_claude_for_file"
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
        """Timeout errors should include the timeout value in the message."""
        from assemblyzero.workflows.testing.nodes.implement_code import (
            call_claude_for_file,
            compute_dynamic_timeout,
        )
        from assemblyzero.core.llm_provider import LLMCallResult

        prompt = "test"
        expected_timeout = compute_dynamic_timeout(prompt)

        mock_provider = MagicMock()
        mock_provider.invoke.return_value = LLMCallResult(
            success=False,
            response=None,
            raw_response=None,
            error_message=f"timeout after {expected_timeout}s waiting for response",
            provider="claude",
            model_used="opus",
            duration_ms=expected_timeout * 1000,
            attempts=1,
            retryable=True,
        )

        with patch(
            "assemblyzero.workflows.testing.nodes.implementation.claude_client.get_provider",
            return_value=mock_provider,
        ):
            response, error = call_claude_for_file(prompt)

            assert "timeout" in error.lower()
            assert str(expected_timeout) in error


# =============================================================================
# T030: CLI timeout constant (still exists for compute_dynamic_timeout)
# =============================================================================


class TestCLITimeout:
    """Tests for CLI timeout constant."""

    def test_cli_timeout_value(self):
        """CLI timeout should be 10 minutes (600 seconds). Issue #373."""
        from assemblyzero.workflows.testing.nodes.implement_code import (
            CLI_TIMEOUT,
        )

        assert CLI_TIMEOUT == 600


# =============================================================================
# T040: Non-retryable errors
# =============================================================================


class TestNonRetryableErrors:
    """Tests for non-retryable error handling."""

    def test_non_retryable_error_prefixed(self):
        """Non-retryable provider errors get [NON-RETRYABLE] prefix."""
        from assemblyzero.workflows.testing.nodes.implement_code import (
            call_claude_for_file,
        )
        from assemblyzero.core.llm_provider import LLMCallResult

        mock_provider = MagicMock()
        mock_provider.invoke.return_value = LLMCallResult(
            success=False,
            response=None,
            raw_response=None,
            error_message="invalid_api_key",
            provider="claude",
            model_used="opus",
            duration_ms=100,
            attempts=1,
            retryable=False,
        )

        with patch(
            "assemblyzero.workflows.testing.nodes.implementation.claude_client.get_provider",
            return_value=mock_provider,
        ):
            response, error = call_claude_for_file("test prompt")

            assert response == ""
            assert error.startswith("[NON-RETRYABLE]")


# =============================================================================
# T050: Workflow exit code
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
            "assemblyzero.workflows.testing.nodes.implementation.orchestrator.call_claude_for_file"
        ) as mock_call:
            # Return timeout error
            mock_call.return_value = ("", "SDK timeout after 300s")

            # Should raise ImplementationError, not return success
            with pytest.raises(ImplementationError):
                implement_code(state)


# =============================================================================
# T060: Provider gate is used (Issue #783)
# =============================================================================


class TestProviderGate:
    """Tests that call_claude_for_file uses get_provider (not direct SDK)."""

    def test_uses_get_provider(self):
        """call_claude_for_file must call get_provider, not anthropic.Anthropic."""
        from assemblyzero.workflows.testing.nodes.implement_code import (
            call_claude_for_file,
        )
        from assemblyzero.core.llm_provider import LLMCallResult

        mock_provider = MagicMock()
        mock_provider.invoke.return_value = LLMCallResult(
            success=True,
            response="```python\nprint('hello')\n```",
            raw_response="```python\nprint('hello')\n```",
            error_message=None,
            provider="claude",
            model_used="opus",
            duration_ms=1000,
            attempts=1,
        )

        with patch(
            "assemblyzero.workflows.testing.nodes.implementation.claude_client.get_provider",
            return_value=mock_provider,
        ) as mock_get:
            response, error = call_claude_for_file("write code")

            mock_get.assert_called_once_with("claude:opus")
            mock_provider.invoke.assert_called_once()
            assert response == "```python\nprint('hello')\n```"
            assert error == ""

    def test_passes_model_to_provider(self):
        """Model parameter flows through to get_provider spec."""
        from assemblyzero.workflows.testing.nodes.implement_code import (
            call_claude_for_file,
        )
        from assemblyzero.core.llm_provider import LLMCallResult

        mock_provider = MagicMock()
        mock_provider.invoke.return_value = LLMCallResult(
            success=True,
            response="code",
            raw_response="code",
            error_message=None,
            provider="claude",
            model_used="haiku",
            duration_ms=500,
            attempts=1,
        )

        with patch(
            "assemblyzero.workflows.testing.nodes.implementation.claude_client.get_provider",
            return_value=mock_provider,
        ) as mock_get:
            call_claude_for_file("prompt", model="haiku")

            mock_get.assert_called_once_with("claude:haiku")

    def test_no_direct_anthropic_import(self):
        """claude_client.py must not import anthropic directly."""
        import importlib
        import assemblyzero.workflows.testing.nodes.implementation.claude_client as mod

        source = importlib.util.find_spec(mod.__name__)
        assert source is not None
        import inspect
        src = inspect.getsource(mod)
        assert "import anthropic" not in src
        assert "anthropic.Anthropic" not in src
