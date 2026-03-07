"""Tests for telemetry emit calls in Two-Strikes / Size Gate (#614)."""

from unittest.mock import patch, MagicMock
import pytest

from assemblyzero.workflows.testing.nodes.implement_code import (
    validate_code_response,
    generate_file_with_retry,
    ImplementationError,
)


class TestSizeGateTelemetry:
    """Verify quality.gate_rejected fires on drastic file shrink."""

    @patch("assemblyzero.workflows.testing.nodes.implementation.parsers.emit")
    def test_drastic_shrink_emits_quality_gate_rejected(self, mock_emit):
        existing = "line\n" * 270
        new_code = "line\n" * 56

        valid, _ = validate_code_response(new_code, "src/foo.py", existing)

        assert valid is False
        mock_emit.assert_called_once_with(
            "quality.gate_rejected",
            repo="",
            metadata={"filepath": "src/foo.py", "type": "size_gate", "error": "drastic_shrink"},
        )

    @patch("assemblyzero.workflows.testing.nodes.implementation.parsers.emit")
    def test_no_shrink_does_not_emit(self, mock_emit):
        existing = "line\n" * 20
        new_code = "line\n" * 20

        valid, _ = validate_code_response(new_code, "src/foo.py", existing)

        assert valid is True
        mock_emit.assert_not_called()


class TestRetryStrikeOneTelemetry:
    """Verify retry.strike_one fires on second retry attempt."""

    @patch("assemblyzero.workflows.testing.nodes.implementation.orchestrator.emit")
    @patch("assemblyzero.workflows.testing.nodes.implementation.orchestrator.call_claude_for_file")
    def test_strike_one_emits_on_second_attempt(self, mock_claude, mock_emit):
        # First attempt: API error. Second attempt: API error (triggers strike_one). Both fail.
        mock_claude.return_value = (None, "API error: quota exceeded")

        with pytest.raises(ImplementationError):
            generate_file_with_retry(
                filepath="src/bar.py",
                base_prompt="implement bar",
                audit_dir=None,
                max_retries=2,
            )

        # retry.strike_one should have been emitted when attempt_num == 2
        strike_calls = [
            c for c in mock_emit.call_args_list
            if c[0][0] == "retry.strike_one"
        ]
        assert len(strike_calls) == 1
        assert strike_calls[0][1]["metadata"]["filepath"] == "src/bar.py"


class TestHaltAndPlanTelemetry:
    """Verify workflow.halt_and_plan fires when retries are exhausted."""

    @patch("assemblyzero.workflows.testing.nodes.implementation.orchestrator.emit")
    @patch("assemblyzero.workflows.testing.nodes.implementation.orchestrator.call_claude_for_file")
    def test_halt_and_plan_emits_on_max_retries(self, mock_claude, mock_emit):
        mock_claude.return_value = (None, "API error: timeout")

        with pytest.raises(ImplementationError):
            generate_file_with_retry(
                filepath="src/baz.py",
                base_prompt="implement baz",
                audit_dir=None,
                max_retries=2,
            )

        halt_calls = [
            c for c in mock_emit.call_args_list
            if c[0][0] == "workflow.halt_and_plan"
        ]
        assert len(halt_calls) >= 1
        assert halt_calls[0][1]["metadata"]["filepath"] == "src/baz.py"
        assert halt_calls[0][1]["metadata"]["reason"] == "max_retries_exceeded"
