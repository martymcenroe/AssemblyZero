"""Speed-run lap splits and the run log fail loudly (ADR 0236, #3585).

A lap-split file or a run-log entry that could not be written was a WARNING
and the run went on, so the durable cross-attempt record silently lost the
attempt. A malformed run-log line was skipped with a WARNING, so the summary
counted fewer attempts than the log holds. Each now alerts the operator and
raises, naming the file (and the line).

One test per ledger site, named for the line the ledger gives at ``79e18ad1``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from assemblyzero.utils.speedrun import LapSplitWriter, RunLogger


def test_144_a_lap_split_that_cannot_be_written_alerts_and_raises(tmp_path, operator_alerts):
    writer = LapSplitWriter.start(tmp_path, issue=35, attempt=1)
    writer.output_path.unlink()
    writer.output_path.mkdir()  # a directory where the file must be

    with pytest.raises(OSError):
        writer.beat("lld_approved")

    assert len(operator_alerts) == 1
    alert = operator_alerts[0]
    assert "lap split" in alert["what"]
    assert str(writer.output_path) in alert["cause"]
    assert alert["issue"] == 35


def test_320_a_run_log_entry_that_cannot_be_appended_alerts_and_raises(tmp_path, operator_alerts):
    run_log = RunLogger(tmp_path)
    run_log.log_path.mkdir(parents=True)  # a directory where the log must be

    with pytest.raises(OSError):
        run_log.complete_run(
            issue=35, attempt=7, started_at_iso="2026-10-30T00:00:00Z",
            outcome="success", total_seconds=1.0, profile="default",
        )

    assert len(operator_alerts) == 1
    assert "run-log" in operator_alerts[0]["what"]
    assert operator_alerts[0]["issue"] == 35


def test_335_a_malformed_run_log_line_alerts_and_raises_naming_it(tmp_path, operator_alerts):
    run_log = RunLogger(tmp_path)
    run_log.log_path.parent.mkdir(parents=True)
    run_log.log_path.write_text(
        json.dumps({"issue": 1, "attempt": 1}) + "\n" + "{not json\n", encoding="utf-8",
    )

    with pytest.raises(ValueError) as excinfo:
        run_log.read_all()

    assert f"{run_log.log_path}:2" in str(excinfo.value)
    assert len(operator_alerts) == 1


def test_an_absent_run_log_is_a_quiet_empty_answer(tmp_path, operator_alerts):
    assert RunLogger(tmp_path).read_all() == []
    assert operator_alerts == []


def test_a_written_attempt_reads_back(tmp_path, operator_alerts):
    run_log = RunLogger(Path(tmp_path))
    run_log.complete_run(
        issue=35, attempt=7, started_at_iso="2026-10-30T00:00:00Z",
        outcome="success", total_seconds=1.0, profile="default",
    )
    writer = LapSplitWriter.start(tmp_path, issue=35, attempt=1)
    writer.beat("workflow_started")

    assert [e["attempt"] for e in run_log.read_all()] == [7]
    assert operator_alerts == []
