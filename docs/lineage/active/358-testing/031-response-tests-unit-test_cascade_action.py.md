

```python
"""Unit tests for cascade action handlers.

Issue #358: Auto-Approve Safety — Prevent Cascading Task Execution
Tests: T130, T150, T160
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from assemblyzero.hooks.cascade_action import (
    format_block_message,
    handle_cascade_detection,
)
from assemblyzero.hooks.cascade_detector import (
    CascadeDetectionResult,
    CascadeRiskLevel,
)


# ── T130: Block message formatting ──


class TestFormatBlockMessage:
    """T130: format_block_message produces readable output (REQ-2)."""

    def test_contains_required_elements(self) -> None:
        result: CascadeDetectionResult = {
            "detected": True,
            "risk_level": CascadeRiskLevel.HIGH,
            "matched_patterns": ["CP-001", "CP-020"],
            "matched_text": "Should I continue with issue #43?",
            "recommended_action": "block_and_prompt",
            "confidence": 0.85,
        }
        message = format_block_message(result)

        assert "CASCADE" in message.upper() or "cascade" in message.lower()
        assert "HIGH" in message
        assert "CP-001" in message
        assert "CP-020" in message
        assert "manual input" in message.lower() or "decide" in message.lower()
        assert "Should I continue" in message

    def test_truncates_long_matched_text(self) -> None:
        result: CascadeDetectionResult = {
            "detected": True,
            "risk_level": CascadeRiskLevel.MEDIUM,
            "matched_patterns": ["CP-031"],
            "matched_text": "x" * 200,
            "recommended_action": "block_and_prompt",
            "confidence": 0.6,
        }
        message = format_block_message(result)
        assert "..." in message

    def test_handles_empty_patterns(self) -> None:
        result: CascadeDetectionResult = {
            "detected": True,
            "risk_level": CascadeRiskLevel.MEDIUM,
            "matched_patterns": [],
            "matched_text": "",
            "recommended_action": "block_and_prompt",
            "confidence": 0.6,
        }
        message = format_block_message(result)
        assert "unknown" in message


# ── T150: Hook exit codes (tested via handle_cascade_detection return) ──


class TestHandleCascadeDetection:
    """T150/T160: handle_cascade_detection returns correct values (REQ-2)."""

    @patch("assemblyzero.hooks.cascade_action.log_cascade_event")
    @patch("assemblyzero.hooks.cascade_action.create_cascade_event")
    def test_allow_returns_true(self, mock_create: object, mock_log: object) -> None:
        result: CascadeDetectionResult = {
            "detected": False,
            "risk_level": CascadeRiskLevel.NONE,
            "matched_patterns": [],
            "matched_text": "",
            "recommended_action": "allow",
            "confidence": 0.0,
        }
        assert handle_cascade_detection(result, "sess-123", "clean output") is True

    @patch("assemblyzero.hooks.cascade_action.log_cascade_event")
    @patch("assemblyzero.hooks.cascade_action.create_cascade_event")
    def test_block_and_prompt_returns_false(self, mock_create: object, mock_log: object) -> None:
        """T160: Auto-approve blocked on MEDIUM risk (REQ-2)."""
        mock_create.return_value = {  # type: ignore[union-attr]
            "timestamp": "2026-02-25T00:00:00+00:00",
            "event_type": "cascade_risk",
            "risk_level": "medium",
            "action_taken": "blocked",
            "matched_patterns": ["CP-031"],
            "model_output_snippet": "test",
            "session_id": "sess-123",
            "auto_approve_blocked": True,
        }
        result: CascadeDetectionResult = {
            "detected": True,
            "risk_level": CascadeRiskLevel.MEDIUM,
            "matched_patterns": ["CP-031"],
            "matched_text": "should I fix those too?",
            "recommended_action": "block_and_prompt",
            "confidence": 0.65,
        }
        assert handle_cascade_detection(result, "sess-123", "model output") is False

    @patch("assemblyzero.hooks.cascade_action.log_cascade_event")
    @patch("assemblyzero.hooks.cascade_action.create_cascade_event")
    def test_block_and_alert_returns_false(self, mock_create: object, mock_log: object) -> None:
        mock_create.return_value = {  # type: ignore[union-attr]
            "timestamp": "2026-02-25T00:00:00+00:00",
            "event_type": "cascade_risk",
            "risk_level": "critical",
            "action_taken": "alerted",
            "matched_patterns": ["CP-001", "CP-020", "CP-010"],
            "model_output_snippet": "test",
            "session_id": "sess-123",
            "auto_approve_blocked": True,
        }
        result: CascadeDetectionResult = {
            "detected": True,
            "risk_level": CascadeRiskLevel.CRITICAL,
            "matched_patterns": ["CP-001", "CP-020", "CP-010"],
            "matched_text": "Should I continue?",
            "recommended_action": "block_and_alert",
            "confidence": 1.0,
        }
        assert handle_cascade_detection(result, "sess-123", "model output") is False

    @patch("assemblyzero.hooks.cascade_action.log_cascade_event", side_effect=Exception("disk full"))
    @patch("assemblyzero.hooks.cascade_action.create_cascade_event")
    def test_telemetry_failure_still_blocks(self, mock_create: object, mock_log: object) -> None:
        """Telemetry failure must not prevent blocking."""
        mock_create.return_value = {  # type: ignore[union-attr]
            "timestamp": "2026-02-25T00:00:00+00:00",
            "event_type": "cascade_risk",
            "risk_level": "high",
            "action_taken": "blocked",
            "matched_patterns": ["CP-001"],
            "model_output_snippet": "test",
            "session_id": "sess-123",
            "auto_approve_blocked": True,
        }
        result: CascadeDetectionResult = {
            "detected": True,
            "risk_level": CascadeRiskLevel.HIGH,
            "matched_patterns": ["CP-001"],
            "matched_text": "Should I continue?",
            "recommended_action": "block_and_prompt",
            "confidence": 0.75,
        }
        # Should still return False even though logging failed
        assert handle_cascade_detection(result, "sess-123", "model output") is False
```
