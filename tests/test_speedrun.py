"""Tests for assemblyzero.utils.speedrun (#1076)."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from assemblyzero.utils.speedrun import (
    HALT_CLASSIFICATIONS,
    LapSplitWriter,
    RunLogger,
    _next_attempt_number,
    classify_halt,
)


# ---------------------------------------------------------------------------
# LapSplitWriter
# ---------------------------------------------------------------------------


def test_lap_split_writer_creates_initial_file(tmp_path: Path):
    """start() writes the JSON file immediately with empty splits."""
    writer = LapSplitWriter.start(tmp_path, issue=42)
    assert writer.issue == 42
    assert writer.attempt == 1  # First attempt for this issue
    assert writer.output_path.exists()
    data = json.loads(writer.output_path.read_text(encoding="utf-8"))
    assert data["issue"] == 42
    assert data["attempt"] == 1
    assert data["splits"] == []
    assert "started_at" in data


def test_lap_split_writer_increments_attempt(tmp_path: Path):
    """Second start() for same issue gets attempt=2."""
    LapSplitWriter.start(tmp_path, issue=42)
    second = LapSplitWriter.start(tmp_path, issue=42)
    assert second.attempt == 2


def test_lap_split_writer_explicit_attempt(tmp_path: Path):
    """Caller can override attempt number."""
    writer = LapSplitWriter.start(tmp_path, issue=42, attempt=7)
    assert writer.attempt == 7


def test_lap_split_writer_records_beats_with_elapsed_time(tmp_path: Path):
    """beat() appends a {beat, t} entry; t is seconds since start."""
    writer = LapSplitWriter.start(tmp_path, issue=42)
    # Mock the started_at to a known value so we can assert deltas.
    writer.started_at = time.time() - 10.0  # Pretend run started 10s ago
    writer.beat("lld_drafted")
    data = json.loads(writer.output_path.read_text(encoding="utf-8"))
    assert len(data["splits"]) == 1
    assert data["splits"][0]["beat"] == "lld_drafted"
    assert 9.5 < data["splits"][0]["t"] < 11.0  # ~10s elapsed


def test_lap_split_writer_finalize_writes_outcome(tmp_path: Path):
    """finalize() writes a completed_<outcome> beat with optional failure_mode."""
    writer = LapSplitWriter.start(tmp_path, issue=42)
    writer.finalize("success")
    data = json.loads(writer.output_path.read_text(encoding="utf-8"))
    assert data["splits"][-1]["beat"] == "completed_success"
    assert "failure_mode" not in data["splits"][-1]


def test_lap_split_writer_finalize_with_failure_mode(tmp_path: Path):
    """finalize('fail', 'gemini-503') writes the classification."""
    writer = LapSplitWriter.start(tmp_path, issue=42)
    writer.finalize("fail", failure_mode="gemini-503")
    data = json.loads(writer.output_path.read_text(encoding="utf-8"))
    assert data["splits"][-1]["beat"] == "completed_fail"
    assert data["splits"][-1]["failure_mode"] == "gemini-503"


def test_next_attempt_number_finds_max(tmp_path: Path):
    """_next_attempt_number scans existing files and returns max+1."""
    speedrun_dir = tmp_path / "data" / "speedrun"
    speedrun_dir.mkdir(parents=True)
    # Create some existing attempt files
    (speedrun_dir / "42-1.json").write_text("{}")
    (speedrun_dir / "42-3.json").write_text("{}")
    (speedrun_dir / "42-5.json").write_text("{}")
    # Different issue, should not interfere
    (speedrun_dir / "99-10.json").write_text("{}")
    assert _next_attempt_number(speedrun_dir, 42) == 6
    assert _next_attempt_number(speedrun_dir, 99) == 11
    assert _next_attempt_number(speedrun_dir, 100) == 1  # No prior attempts


def test_next_attempt_number_handles_empty_dir(tmp_path: Path):
    """Returns 1 when dir doesn't exist or has no matching files."""
    assert _next_attempt_number(tmp_path / "nope", 42) == 1


# ---------------------------------------------------------------------------
# classify_halt
# ---------------------------------------------------------------------------


def test_classify_halt_returns_known_label():
    """Every classification returned by classify_halt is in HALT_CLASSIFICATIONS."""
    # Cover all named classifications
    cases = [
        ({}, "503 Service Unavailable", "gemini-503"),
        ({}, "RESOURCE_EXHAUSTED quota exceeded", "gemini-quota"),
        ({"test_plan_status": "BLOCKED"}, "", "test-plan-blocked"),
        (
            {"validation_iteration_count": 20, "max_iterations": 20,
             "validation_errors": ["x"]},
            "",
            "mech-validation-loop",
        ),
        (
            {"completeness_iteration_count": 3, "max_completeness_iterations": 3,
             "completeness_errors": ["x"]},
            "",
            "completeness-gate-failed",
        ),
        (
            {"coverage_percentage": 70.0, "coverage_target": 80.0},
            "",
            "coverage-target-missed",
        ),
        ({"stagnation_detected": True}, "", "stagnation"),
        ({}, "", "unknown"),
        ({}, "completely random error", "unknown"),
    ]
    for state, msg, expected in cases:
        result = classify_halt(state, msg)
        assert result in HALT_CLASSIFICATIONS, f"Unknown result: {result}"
        assert result == expected, f"Expected {expected}, got {result} for {state}/{msg!r}"


def test_classify_halt_test_plan_blocked_takes_priority():
    """test_plan_status=BLOCKED beats other signals."""
    result = classify_halt(
        {"test_plan_status": "BLOCKED"},
        "503 Service Unavailable",
    )
    assert result == "test-plan-blocked"


def test_classify_halt_recognizes_429_in_message():
    result = classify_halt({}, "HTTP 429 rate limit hit")
    assert result == "gemini-quota"


def test_classify_halt_recognizes_overloaded():
    result = classify_halt({}, "Anthropic Overloaded")
    assert result == "gemini-503"


# ---------------------------------------------------------------------------
# RunLogger
# ---------------------------------------------------------------------------


def test_run_logger_complete_run_appends_jsonl(tmp_path: Path):
    """complete_run appends one JSONL entry."""
    logger = RunLogger(tmp_path)
    logger.complete_run(
        issue=42,
        attempt=1,
        started_at_iso="2026-05-09T20:00:00Z",
        outcome="success",
        total_seconds=523.4,
    )
    log = tmp_path / "data" / "speedrun" / "run-log.jsonl"
    assert log.exists()
    content = log.read_text(encoding="utf-8")
    line = content.strip()
    entry = json.loads(line)
    assert entry["issue"] == 42
    assert entry["attempt"] == 1
    assert entry["outcome"] == "success"
    assert entry["total_seconds"] == 523.4
    assert entry["failure_mode"] is None


def test_run_logger_appends_multiple_runs(tmp_path: Path):
    """Multiple complete_run calls append; don't overwrite."""
    logger = RunLogger(tmp_path)
    logger.complete_run(
        issue=42, attempt=1, started_at_iso="2026-05-09T20:00:00Z",
        outcome="fail", total_seconds=120.0, failure_mode="gemini-503",
    )
    logger.complete_run(
        issue=42, attempt=2, started_at_iso="2026-05-09T20:10:00Z",
        outcome="success", total_seconds=480.0,
    )
    entries = logger.read_all()
    assert len(entries) == 2
    assert entries[0]["attempt"] == 1
    assert entries[0]["failure_mode"] == "gemini-503"
    assert entries[1]["attempt"] == 2
    assert entries[1]["failure_mode"] is None


def test_run_logger_read_all_handles_missing_log(tmp_path: Path):
    """read_all() returns [] when log file doesn't exist."""
    logger = RunLogger(tmp_path)
    assert logger.read_all() == []


def test_run_logger_skips_malformed_lines(tmp_path: Path, caplog):
    """read_all skips invalid JSONL lines and logs a warning."""
    log_path = tmp_path / "data" / "speedrun" / "run-log.jsonl"
    log_path.parent.mkdir(parents=True)
    log_path.write_text(
        '{"valid": 1}\n'
        'not json at all\n'
        '{"valid": 2}\n',
        encoding="utf-8",
    )
    logger = RunLogger(tmp_path)
    entries = logger.read_all()
    # Two valid lines kept; one malformed silently skipped (with WARNING).
    assert len(entries) == 2
    assert entries[0]["valid"] == 1
    assert entries[1]["valid"] == 2
