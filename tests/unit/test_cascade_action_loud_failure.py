"""A cascade block whose telemetry cannot be recorded alerts (ADR 0236, #3585).

The block handler swallowed every failure to build or write the cascade
event with a bare ``pass``, so the event was lost and nobody was told. It now
alerts the operator with the session id and the cause, and still blocks: the
block never depended on the telemetry.

One test per ledger site, named for the line the ledger gives at ``79e18ad1``.
"""

from __future__ import annotations

from unittest.mock import patch

from assemblyzero.hooks.cascade_action import handle_cascade_detection
from assemblyzero.hooks.types import CascadeRiskLevel


def _result(action: str) -> dict:
    return {
        "detected": action != "allow",
        "risk_level": CascadeRiskLevel.MEDIUM,
        "matched_patterns": ["CP-001"],
        "matched_text": "Should I continue?",
        "recommended_action": action,
        "confidence": 0.65,
    }


def test_64_a_telemetry_failure_alerts_with_the_session_and_still_blocks(operator_alerts):
    with patch(
        "assemblyzero.telemetry.cascade_events.log_cascade_event",
        side_effect=OSError("cannot append the cascade event to /x/cascade-events.jsonl"),
    ):
        allowed = handle_cascade_detection(_result("block_and_prompt"), "session-77", "out")

    assert allowed is False, "the block never depended on the telemetry"
    assert len(operator_alerts) == 1
    alert = operator_alerts[0]
    assert "session-77" in alert["what"]
    assert "OSError" in alert["cause"] and "/x/cascade-events.jsonl" in alert["cause"]


def test_64_an_event_that_cannot_be_built_alerts_too(operator_alerts):
    with patch(
        "assemblyzero.telemetry.cascade_events.create_cascade_event",
        side_effect=KeyError("matched_patterns"),
    ), patch("assemblyzero.telemetry.cascade_events.log_cascade_event") as log:
        allowed = handle_cascade_detection(_result("block_and_alert"), "s-2", "out", alert_enabled=False)

    assert allowed is False
    log.assert_not_called()
    assert len(operator_alerts) == 1
    assert "KeyError" in operator_alerts[0]["cause"]


def test_64_a_recorded_block_alerts_nobody(operator_alerts):
    with patch("assemblyzero.telemetry.cascade_events.log_cascade_event") as log:
        allowed = handle_cascade_detection(_result("block_and_prompt"), "s-3", "out")

    assert allowed is False
    log.assert_called_once()
    assert operator_alerts == []


def test_64_an_allowed_output_writes_nothing(operator_alerts):
    with patch("assemblyzero.telemetry.cascade_events.log_cascade_event") as log:
        assert handle_cascade_detection(_result("allow"), "s-4", "out") is True

    log.assert_not_called()
    assert operator_alerts == []
