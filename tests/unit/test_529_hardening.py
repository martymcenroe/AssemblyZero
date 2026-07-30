"""Anthropic 529/overload/outage rides out as capacity, never a verdict (#1917).

The 2026-07-29 Anthropic outage (status page red across claude.ai, the
API, and Claude Code) is the reference event. These tests pin the whole
contract, layer by layer, so an overloaded provider can never again be
mistaken for a permanent failure:

- CLI layer: an ``API Error: 529 … overloaded_error`` message from the
  claude CLI stays retryable (with_retry may run its short backoff).
- SDK layer: connection failures at the outage edge classify retryable
  (the unknown-error fallback used to kill them on the spot).
- Halt layer: the flattened message classifies ``capacity_exhausted``,
  which is in TRANSIENT_ERROR_TYPES, so the recovery plan says
  transient and the orchestrator's escalating capacity backoff (#1909)
  engages.
"""

from unittest.mock import MagicMock

from assemblyzero.core.errors import (
    CapacityError,
    classify_anthropic_error,
    classify_http_status,
    is_capacity_message,
)
from assemblyzero.core.halt_node import classify_error
from assemblyzero.core.llm_provider import is_non_retryable_error
from assemblyzero.core.recovery_plan import (
    TRANSIENT_ERROR_TYPES,
    generate_recovery_plan,
)

# The claude CLI surfaces provider overload as this flavor of stderr,
# prefixed by ClaudeCLIProvider into "claude -p failed: …".
CLI_529_MESSAGE = (
    'claude -p failed: API Error: 529 '
    '{"type":"error","error":{"type":"overloaded_error","message":"Overloaded"}}'
)


class TestCLILayer:
    def test_529_overload_is_retryable_at_the_cli(self):
        assert is_non_retryable_error(CLI_529_MESSAGE) is False

    def test_billing_stays_non_retryable(self):
        assert (
            is_non_retryable_error("Your credit balance is too low") is True
        )


class TestSDKLayer:
    def test_connection_error_is_retryable(self):
        """Outage-edge connection failures used to hit the non-retryable
        fallback and die instantly."""
        import anthropic

        exc = anthropic.APIConnectionError(request=MagicMock())
        classified = classify_anthropic_error(exc)
        assert classified.retryable is True

    def test_timeout_still_maps_to_timeout(self):
        """The new branch must not shadow APITimeoutError (its subclass
        relationship runs the other way: timeout IS-A connection error)."""
        import anthropic
        from assemblyzero.core.errors import TimeoutError_

        exc = anthropic.APITimeoutError(request=MagicMock())
        assert isinstance(classify_anthropic_error(exc), TimeoutError_)

    def test_http_529_is_capacity(self):
        classified = classify_http_status(529, "Overloaded")
        assert isinstance(classified, CapacityError)
        assert classified.retryable is True


class TestHaltLayer:
    def test_cli_529_message_is_a_capacity_signature(self):
        assert is_capacity_message(CLI_529_MESSAGE) is True

    def test_cli_529_message_classifies_capacity_exhausted(self):
        assert classify_error(CLI_529_MESSAGE) == "capacity_exhausted"

    def test_capacity_exhausted_is_transient(self):
        assert "capacity_exhausted" in TRANSIENT_ERROR_TYPES

    def test_recovery_plan_for_529_says_transient(self):
        plan = generate_recovery_plan(
            issue_number=4,
            workflow="implementation_spec",
            stage="N1_draft",
            error_type=classify_error(CLI_529_MESSAGE),
            error_message=CLI_529_MESSAGE,
            state={},
        )
        assert plan.is_transient is True
