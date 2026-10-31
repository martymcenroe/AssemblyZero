"""Cascade-event telemetry fails loudly (ADR 0236, #3585).

A cascade event that could not be written was a plain print and was lost; a
corrupt log line, an event with a bad timestamp, and a log that could not be
read were skipped or read as zero, so the detector's accuracy stats
undercounted. Now the write logs at ERROR naming the log and raises (its one
caller, the block handler, alerts), and the stats reader raises naming the
log and the line.

One test per ledger site, named for the line the ledger gives at ``79e18ad1``.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta

import pytest

from assemblyzero.telemetry.cascade_events import get_cascade_stats, log_cascade_event

EVENT = {
    "timestamp": datetime.now(UTC).isoformat(),
    "event_type": "cascade_risk",
    "risk_level": "high",
    "action_taken": "blocked",
    "matched_patterns": ["CP-001"],
    "model_output_snippet": "Should I continue?",
    "session_id": "s-1",
    "auto_approve_blocked": True,
}


def _log_with(tmp_path, *lines: str):
    path = tmp_path / "cascade-events.jsonl"
    path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
    return path


def test_72_a_write_that_fails_logs_error_and_raises_naming_the_log(tmp_path, caplog):
    (tmp_path / "blocked").write_text("not a directory\n", encoding="utf-8")
    path = tmp_path / "blocked" / "cascade-events.jsonl"

    with caplog.at_level(logging.ERROR), pytest.raises(OSError) as raised:
        log_cascade_event(EVENT, log_path=path)

    assert str(path) in str(raised.value)
    assert any(r.levelno >= logging.ERROR and str(path) in r.getMessage() for r in caplog.records)


def test_152_a_corrupt_line_raises_naming_it(tmp_path):
    path = _log_with(tmp_path, json.dumps(EVENT), "{not json")

    with pytest.raises(ValueError) as raised:
        get_cascade_stats(path, since_hours=0)

    assert f"{path}:2" in str(raised.value)


def test_152_a_line_that_is_not_an_object_raises(tmp_path):
    path = _log_with(tmp_path, "[1, 2]")

    with pytest.raises(ValueError) as raised:
        get_cascade_stats(path, since_hours=0)

    assert f"{path}:1" in str(raised.value)


def test_161_an_event_with_a_bad_timestamp_raises_naming_it(tmp_path):
    path = _log_with(tmp_path, json.dumps(EVENT), json.dumps(dict(EVENT, timestamp="yesterday")))

    with pytest.raises(ValueError) as raised:
        get_cascade_stats(path, since_hours=24)

    assert f"{path}:2" in str(raised.value)
    assert "yesterday" in str(raised.value)


def test_161_an_event_with_a_naive_timestamp_raises_naming_it(tmp_path):
    naive = datetime.now(UTC).replace(tzinfo=None).isoformat()
    path = _log_with(tmp_path, json.dumps(dict(EVENT, timestamp=naive)))

    with pytest.raises(ValueError) as raised:
        get_cascade_stats(path, since_hours=24)

    assert f"{path}:1" in str(raised.value)


def test_161_with_no_window_no_timestamp_is_read(tmp_path):
    path = _log_with(tmp_path, json.dumps(dict(EVENT, timestamp="yesterday")))

    assert get_cascade_stats(path, since_hours=0)["total_checks"] == 1


def test_170_a_log_that_cannot_be_read_raises(tmp_path, caplog):
    path = tmp_path / "cascade-events.jsonl"
    path.mkdir()  # a directory where the log must be

    with caplog.at_level(logging.ERROR), pytest.raises(OSError):
        get_cascade_stats(path)

    assert any(r.levelno >= logging.ERROR and str(path) in r.getMessage() for r in caplog.records)


def test_an_absent_log_is_zero_stats(tmp_path):
    stats = get_cascade_stats(tmp_path / "none.jsonl")
    assert stats == {"total_checks": 0, "detections": 0, "blocks": 0, "allowed": 0}


def test_a_clean_log_counts_every_event_in_the_window(tmp_path):
    old = (datetime.now(UTC) - timedelta(hours=48)).isoformat()
    path = _log_with(
        tmp_path,
        json.dumps(EVENT),
        json.dumps(dict(EVENT, auto_approve_blocked=False)),
        json.dumps(dict(EVENT, timestamp=old)),
    )

    stats = get_cascade_stats(path, since_hours=24)

    assert stats == {"total_checks": 2, "detections": 1, "blocks": 1, "allowed": 1}
