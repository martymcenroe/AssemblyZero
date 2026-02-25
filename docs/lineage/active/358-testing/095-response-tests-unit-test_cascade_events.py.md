

```python
"""Unit tests for cascade telemetry events.

Issue #358: Auto-Approve Safety — Prevent Cascading Task Execution
Tests: T090, T140, T170
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from assemblyzero.hooks.cascade_detector import CascadeRiskLevel
from assemblyzero.telemetry.cascade_events import (
    CascadeEvent,
    create_cascade_event,
    get_cascade_stats,
    log_cascade_event,
)


# ── T090: Event logging structure ──


class TestLogCascadeEvent:
    """T090: Valid JSONL with all CascadeEvent fields (REQ-4)."""

    def test_writes_valid_jsonl(self, tmp_path: Path) -> None:
        log_file = tmp_path / "cascade-events.jsonl"
        event: CascadeEvent = {
            "timestamp": "2026-02-25T14:32:07.123456+00:00",
            "event_type": "cascade_risk",
            "risk_level": "high",
            "action_taken": "blocked",
            "matched_patterns": ["CP-001", "CP-020"],
            "model_output_snippet": "I've fixed issue #42. Should I continue?",
            "session_id": "sess_abc123",
            "auto_approve_blocked": True,
        }
        log_cascade_event(event, log_path=log_file)

        content = log_file.read_text(encoding="utf-8")
        lines = content.strip().split("\n")
        assert len(lines) == 1

        parsed = json.loads(lines[0])
        assert parsed["event_type"] == "cascade_risk"
        assert parsed["risk_level"] == "high"
        assert parsed["action_taken"] == "blocked"
        assert parsed["matched_patterns"] == ["CP-001", "CP-020"]
        assert parsed["session_id"] == "sess_abc123"
        assert parsed["auto_approve_blocked"] is True
        assert len(parsed["model_output_snippet"]) <= 200

    def test_appends_multiple_events(self, tmp_path: Path) -> None:
        log_file = tmp_path / "cascade-events.jsonl"
        for i in range(3):
            event: CascadeEvent = {
                "timestamp": f"2026-02-25T14:32:0{i}.000000+00:00",
                "event_type": "cascade_risk",
                "risk_level": "medium",
                "action_taken": "blocked",
                "matched_patterns": [f"CP-{i:03d}"],
                "model_output_snippet": f"Sample {i}",
                "session_id": "sess_test",
                "auto_approve_blocked": True,
            }
            log_cascade_event(event, log_path=log_file)

        lines = log_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 3

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        log_file = tmp_path / "subdir" / "deep" / "cascade-events.jsonl"
        event: CascadeEvent = {
            "timestamp": "2026-02-25T14:32:07.000000+00:00",
            "event_type": "cascade_risk",
            "risk_level": "low",
            "action_taken": "allowed",
            "matched_patterns": [],
            "model_output_snippet": "",
            "session_id": "sess_test",
            "auto_approve_blocked": False,
        }
        log_cascade_event(event, log_path=log_file)
        assert log_file.exists()


# ── T170: Cascade event field completeness ──


class TestCreateCascadeEvent:
    """T170: Create event with all required fields (REQ-4)."""

    def test_all_fields_present(self) -> None:
        result = {
            "detected": True,
            "risk_level": CascadeRiskLevel.HIGH,
            "matched_patterns": ["CP-001", "CP-020"],
            "matched_text": "Should I continue?",
            "recommended_action": "block_and_prompt",
            "confidence": 0.85,
        }
        event = create_cascade_event(
            result=result,  # type: ignore[arg-type]
            session_id="sess_abc123",
            model_output="I've fixed issue #42. Should I continue with issue #43?",
            action_taken="blocked",
        )

        # Verify all 8 required fields
        assert "timestamp" in event
        # Verify timestamp is valid ISO 8601
        datetime.fromisoformat(event["timestamp"])

        assert event["event_type"] == "cascade_risk"
        assert event["risk_level"] == "high"
        assert event["action_taken"] == "blocked"
        assert event["matched_patterns"] == ["CP-001", "CP-020"]
        assert isinstance(event["model_output_snippet"], str)
        assert len(event["model_output_snippet"]) <= 200
        assert event["session_id"] == "sess_abc123"
        assert event["auto_approve_blocked"] is True

    def test_truncates_long_output(self) -> None:
        result = {
            "detected": True,
            "risk_level": CascadeRiskLevel.MEDIUM,
            "matched_patterns": ["CP-030"],
            "matched_text": "test",
            "recommended_action": "block_and_prompt",
            "confidence": 0.6,
        }
        long_output = "x" * 500
        event = create_cascade_event(
            result=result,  # type: ignore[arg-type]
            session_id="sess_test",
            model_output=long_output,
            action_taken="blocked",
        )
        assert len(event["model_output_snippet"]) == 200

    def test_risk_level_enum_to_string(self) -> None:
        result = {
            "detected": False,
            "risk_level": CascadeRiskLevel.NONE,
            "matched_patterns": [],
            "matched_text": "",
            "recommended_action": "allow",
            "confidence": 0.0,
        }
        event = create_cascade_event(
            result=result,  # type: ignore[arg-type]
            session_id="sess_test",
            model_output="clean output",
            action_taken="allowed",
        )
        assert event["risk_level"] == "none"
        assert isinstance(event["risk_level"], str)


# ── T140: Stats calculation ──


class TestGetCascadeStats:
    """T140: get_cascade_stats returns correct counts (REQ-4)."""

    def test_correct_counts(self, tmp_path: Path) -> None:
        log_file = tmp_path / "cascade-events.jsonl"
        now = datetime.now(timezone.utc)

        # Write 5 events: 3 blocked, 2 allowed
        events = [
            {"timestamp": (now - timedelta(hours=1)).isoformat(), "event_type": "cascade_risk", "risk_level": "high", "action_taken": "blocked", "matched_patterns": ["CP-001"], "model_output_snippet": "test", "session_id": "s1", "auto_approve_blocked": True},
            {"timestamp": (now - timedelta(hours=2)).isoformat(), "event_type": "cascade_risk", "risk_level": "medium", "action_taken": "blocked", "matched_patterns": ["CP-030"], "model_output_snippet": "test", "session_id": "s1", "auto_approve_blocked": True},
            {"timestamp": (now - timedelta(hours=3)).isoformat(), "event_type": "cascade_risk", "risk_level": "critical", "action_taken": "alerted", "matched_patterns": ["CP-001", "CP-010"], "model_output_snippet": "test", "session_id": "s1", "auto_approve_blocked": True},
            {"timestamp": (now - timedelta(hours=4)).isoformat(), "event_type": "cascade_risk", "risk_level": "none", "action_taken": "allowed", "matched_patterns": [], "model_output_snippet": "clean", "session_id": "s1", "auto_approve_blocked": False},
            {"timestamp": (now - timedelta(hours=5)).isoformat(), "event_type": "cascade_risk", "risk_level": "low", "action_taken": "allowed", "matched_patterns": [], "model_output_snippet": "clean", "session_id": "s1", "auto_approve_blocked": False},
        ]
        with log_file.open("w", encoding="utf-8") as f:
            for e in events:
                f.write(json.dumps(e) + "\n")

        stats = get_cascade_stats(log_path=log_file, since_hours=24)
        assert stats["total_checks"] == 5
        assert stats["detections"] == 3
        assert stats["blocks"] == 3
        assert stats["allowed"] == 2

    def test_time_filter(self, tmp_path: Path) -> None:
        log_file = tmp_path / "cascade-events.jsonl"
        now = datetime.now(timezone.utc)

        events = [
            {"timestamp": (now - timedelta(hours=1)).isoformat(), "event_type": "cascade_risk", "risk_level": "high", "action_taken": "blocked", "matched_patterns": ["CP-001"], "model_output_snippet": "test", "session_id": "s1", "auto_approve_blocked": True},
            {"timestamp": (now - timedelta(hours=48)).isoformat(), "event_type": "cascade_risk", "risk_level": "high", "action_taken": "blocked", "matched_patterns": ["CP-001"], "model_output_snippet": "test", "session_id": "s1", "auto_approve_blocked": True},
        ]
        with log_file.open("w", encoding="utf-8") as f:
            for e in events:
                f.write(json.dumps(e) + "\n")

        stats = get_cascade_stats(log_path=log_file, since_hours=24)
        assert stats["total_checks"] == 1  # Only the recent one

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        stats = get_cascade_stats(log_path=tmp_path / "nonexistent.jsonl")
        assert stats == {"total_checks": 0, "detections": 0, "blocks": 0, "allowed": 0}

    def test_corrupt_lines_skipped(self, tmp_path: Path) -> None:
        log_file = tmp_path / "cascade-events.jsonl"
        now = datetime.now(timezone.utc)

        with log_file.open("w", encoding="utf-8") as f:
            f.write(json.dumps({"timestamp": (now - timedelta(hours=1)).isoformat(), "event_type": "cascade_risk", "risk_level": "high", "action_taken": "blocked", "matched_patterns": ["CP-001"], "model_output_snippet": "test", "session_id": "s1", "auto_approve_blocked": True}) + "\n")
            f.write("THIS IS NOT JSON\n")
            f.write(json.dumps({"timestamp": (now - timedelta(hours=2)).isoformat(), "event_type": "cascade_risk", "risk_level": "none", "action_taken": "allowed", "matched_patterns": [], "model_output_snippet": "clean", "session_id": "s1", "auto_approve_blocked": False}) + "\n")

        stats = get_cascade_stats(log_path=log_file, since_hours=24)
        assert stats["total_checks"] == 2  # Corrupt line skipped
```
