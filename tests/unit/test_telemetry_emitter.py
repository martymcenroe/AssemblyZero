"""Tests for assemblyzero.telemetry.emitter — core emit/track functionality."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.telemetry import emitter
from assemblyzero.telemetry.emitter import (
    _build_event,
    _is_enabled,
    _write_to_buffer,
    emit,
    flush,
    track_tool,
)


class TestIsEnabled:
    """Test kill switch behavior."""

    def test_enabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            assert _is_enabled() is True

    def test_enabled_when_set_to_1(self):
        with patch.dict(os.environ, {"ASSEMBLYZERO_TELEMETRY": "1"}):
            assert _is_enabled() is True

    def test_disabled_when_set_to_0(self):
        with patch.dict(os.environ, {"ASSEMBLYZERO_TELEMETRY": "0"}):
            assert _is_enabled() is False


class TestBuildEvent:
    """Test event construction."""

    def test_contains_required_fields(self):
        event = _build_event("workflow.start", repo="AssemblyZero")
        assert event["event_type"] == "workflow.start"
        assert event["repo"] == "AssemblyZero"
        assert event["pk"] == "REPO#AssemblyZero"
        assert event["sk"].startswith("EVENT#")
        assert event["gsi1pk"].startswith("ACTOR#")
        assert event["gsi2pk"].startswith("USER#")
        assert event["gsi3pk"].startswith("DATE#")
        assert "timestamp" in event
        assert "machine_id" in event
        assert "ttl" in event
        assert isinstance(event["ttl"], int)

    def test_metadata_included(self):
        event = _build_event("tool.start", repo="Talos", metadata={"issue": 42})
        assert event["metadata"]["issue"] == 42

    def test_no_metadata_when_none(self):
        event = _build_event("tool.start", repo="Talos")
        assert "metadata" not in event

    def test_unknown_repo_fallback(self):
        event = _build_event("error.unhandled")
        assert event["pk"] == "REPO#unknown"
        assert event["repo"] == "unknown"


class TestWriteToBuffer:
    """Test local JSONL buffer fallback."""

    def test_writes_jsonl(self, tmp_path):
        """Events are written as JSONL to the buffer directory."""
        with patch.object(emitter, "_BUFFER_DIR", tmp_path / "buffer"):
            event = {"event_type": "test", "timestamp": "2026-01-01T00:00:00"}
            _write_to_buffer(event)

            files = list((tmp_path / "buffer").glob("*.jsonl"))
            assert len(files) == 1

            with open(files[0]) as f:
                data = json.loads(f.readline())
            assert data["event_type"] == "test"

    def test_appends_multiple_events(self, tmp_path):
        """Multiple events append to the same daily file."""
        with patch.object(emitter, "_BUFFER_DIR", tmp_path / "buffer"):
            _write_to_buffer({"n": 1})
            _write_to_buffer({"n": 2})

            files = list((tmp_path / "buffer").glob("*.jsonl"))
            assert len(files) == 1

            with open(files[0]) as f:
                lines = f.readlines()
            assert len(lines) == 2

    def test_never_raises(self, tmp_path):
        """Buffer write failures are silently swallowed."""
        with patch.object(emitter, "_BUFFER_DIR", Path("/nonexistent/path/buffer")):
            # Should not raise
            _write_to_buffer({"event_type": "test"})


class TestEmit:
    """Test the main emit() function."""

    def test_disabled_does_nothing(self):
        """When kill switch is off, emit does nothing."""
        with patch.dict(os.environ, {"ASSEMBLYZERO_TELEMETRY": "0"}):
            # Should not raise, should not write
            emit("test.event", repo="Test")

    def test_falls_back_to_buffer_when_no_dynamo(self, tmp_path):
        """Without DynamoDB, events go to buffer."""
        with (
            patch.object(emitter, "_dynamo_client", None),
            patch.object(emitter, "_dynamo_init_attempted", True),
            patch.object(emitter, "_BUFFER_DIR", tmp_path / "buffer"),
        ):
            emit("test.event", repo="TestRepo")

            files = list((tmp_path / "buffer").glob("*.jsonl"))
            assert len(files) == 1

    def test_never_raises_on_any_error(self):
        """emit() must never raise, even with catastrophic failures."""
        with patch.object(emitter, "_build_event", side_effect=RuntimeError("boom")):
            # Should not raise
            emit("test.event")


class TestTrackTool:
    """Test the track_tool context manager."""

    def test_emits_start_and_complete(self):
        """Successful execution emits start + complete."""
        events = []
        with patch.object(emitter, "emit", side_effect=lambda *a, **kw: events.append(a[0])):
            with track_tool("my_tool", repo="TestRepo"):
                pass

        assert events == ["tool.start", "tool.complete"]

    def test_emits_start_and_error_on_exception(self):
        """Failed execution emits start + error, re-raises."""
        events = []
        with patch.object(emitter, "emit", side_effect=lambda *a, **kw: events.append(a[0])):
            with pytest.raises(ValueError, match="boom"):
                with track_tool("my_tool", repo="TestRepo"):
                    raise ValueError("boom")

        assert events == ["tool.start", "tool.error"]

    def test_preserves_original_exception(self):
        """track_tool re-raises the original exception unmodified."""
        with patch.object(emitter, "emit"):
            with pytest.raises(TypeError, match="bad type"):
                with track_tool("my_tool"):
                    raise TypeError("bad type")

    def test_includes_duration_ms(self):
        """Complete/error events include duration_ms in metadata."""
        captured_metadata = {}

        def capture_emit(event_type, repo="", metadata=None):
            if metadata and "duration_ms" in metadata:
                captured_metadata[event_type] = metadata["duration_ms"]

        with patch.object(emitter, "emit", side_effect=capture_emit):
            with track_tool("my_tool"):
                pass

        assert "tool.complete" in captured_metadata
        assert isinstance(captured_metadata["tool.complete"], int)
        assert captured_metadata["tool.complete"] >= 0


class TestFlush:
    """Test buffer flush to DynamoDB."""

    def test_returns_zero_when_disabled(self):
        with patch.dict(os.environ, {"ASSEMBLYZERO_TELEMETRY": "0"}):
            assert flush() == 0

    def test_returns_zero_when_no_client(self):
        with (
            patch.object(emitter, "_dynamo_client", None),
            patch.object(emitter, "_dynamo_init_attempted", True),
        ):
            assert flush() == 0

    def test_flushes_buffer_files(self, tmp_path):
        """Flush reads buffer files and sends to DynamoDB."""
        buffer_dir = tmp_path / "buffer"
        buffer_dir.mkdir()
        buffer_file = buffer_dir / "2026-02-24.jsonl"
        buffer_file.write_text('{"event_type":"test","pk":"REPO#X","sk":"EVENT#1"}\n')

        mock_table = MagicMock()
        with (
            patch.object(emitter, "_BUFFER_DIR", buffer_dir),
            patch.object(emitter, "_dynamo_client", mock_table),
            patch.object(emitter, "_dynamo_init_attempted", True),
        ):
            count = flush()

        assert count == 1
        mock_table.put_item.assert_called_once()
        # Buffer file should be deleted after successful flush
        assert not buffer_file.exists()

    def test_keeps_failed_lines_in_buffer(self, tmp_path):
        """Lines that fail to sync remain in the buffer file."""
        buffer_dir = tmp_path / "buffer"
        buffer_dir.mkdir()
        buffer_file = buffer_dir / "2026-02-24.jsonl"
        buffer_file.write_text(
            '{"n":1}\n'
            '{"n":2}\n'
        )

        mock_table = MagicMock()
        # First put succeeds, second fails
        mock_table.put_item.side_effect = [None, Exception("throttled")]

        with (
            patch.object(emitter, "_BUFFER_DIR", buffer_dir),
            patch.object(emitter, "_dynamo_client", mock_table),
            patch.object(emitter, "_dynamo_init_attempted", True),
        ):
            count = flush()

        assert count == 1
        # Buffer file should still exist with the failed line
        assert buffer_file.exists()
        remaining = buffer_file.read_text().strip()
        assert '"n": 2' in remaining or '"n":2' in remaining
