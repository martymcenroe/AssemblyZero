"""workflows/testing/audit.py under standard 0034, one test per sweep site (#3585).

`next_file_number` on an audit directory that does not exist answered 1, as
if the directory were empty, so the file the caller then saved landed
nowhere it could be found; it now raises FileNotFoundError naming the
directory, after an ERROR line. Every caller in the testing workflow checks
the directory or creates it first, so the raise is for one that vanished.

`log_workflow_execution` logged a failed append to the workflow audit log at
WARNING and went on, so the log silently lost the event; it now raises
WorkflowAuditError naming the log and the cause, after an ERROR line, and
the run ends through the entry point's handler, which alerts. A directory it
cannot create fails the same way.

`parse_pytest_output` still reads a run with no coverage table as 0.0 (320):
its callers in `nodes/verify_phases.py`, another batch's file, compare and
record the value as a number, so None there needs that file changed first.
The strict xfail below records the open site and fails the day it is fixed.

Every test works in a temporary directory. Line numbers in the names are
ledger 0908's, at its base `79e18ad1`.
"""
from __future__ import annotations

import json

import pytest

from assemblyzero.workflows.testing import audit


class TestTheFileNumber:
    def test_121_a_missing_audit_dir_raises_naming_it(self, tmp_path, capsys):
        missing = tmp_path / "docs" / "lineage" / "active" / "7-testing"

        with pytest.raises(FileNotFoundError) as excinfo:
            audit.next_file_number(missing)

        assert str(missing) in str(excinfo.value)
        assert "ERROR" in capsys.readouterr().err

    def test_an_empty_audit_dir_starts_at_one(self, tmp_path, operator_alerts):
        """Kept: an audit directory that exists and holds nothing is file 1."""
        assert audit.next_file_number(tmp_path) == 1
        assert operator_alerts == []

    def test_the_next_number_follows_the_highest(self, tmp_path):
        (tmp_path / "001-lld.md").write_text("x", encoding="utf-8")
        (tmp_path / "004-verdict.md").write_text("x", encoding="utf-8")

        assert audit.next_file_number(tmp_path) == 5


class TestTheWorkflowAuditLog:
    def test_280_an_append_that_fails_raises_naming_the_log(self, tmp_path, monkeypatch, capsys):
        log = tmp_path / "workflow-audit.jsonl"
        log.mkdir()  # a directory where the log should be: the append fails
        monkeypatch.setattr(audit, "WORKFLOW_AUDIT_FILE", log)

        with pytest.raises(Exception) as excinfo:
            audit.log_workflow_execution(tmp_path, 7, "testing", "red_phase_complete")

        assert type(excinfo.value).__name__ == "WorkflowAuditError"
        message = str(excinfo.value)
        assert str(log) in message
        assert "red_phase_complete" in message
        assert isinstance(excinfo.value.__cause__, OSError)
        assert "ERROR" in capsys.readouterr().err

    def test_280_a_log_directory_that_cannot_be_made_raises_the_same_way(self, tmp_path, monkeypatch):
        blocker = tmp_path / "not-a-directory"
        blocker.write_text("x", encoding="utf-8")
        monkeypatch.setattr(audit, "WORKFLOW_AUDIT_FILE", blocker / "workflow-audit.jsonl")

        with pytest.raises(Exception) as excinfo:
            audit.log_workflow_execution(tmp_path, 7, "testing", "start")

        assert type(excinfo.value).__name__ == "WorkflowAuditError"

    def test_an_append_that_works_is_quiet(self, tmp_path, monkeypatch, capsys, operator_alerts):
        """Kept: the event is one JSON line in the log."""
        log = tmp_path / "logs" / "workflow-audit.jsonl"
        monkeypatch.setattr(audit, "WORKFLOW_AUDIT_FILE", log)

        audit.log_workflow_execution(tmp_path, 7, "testing", "start", {"k": 1})

        entry = json.loads(log.read_text(encoding="utf-8"))
        assert (entry["issue_number"], entry["event"], entry["details"]) == (7, "start", {"k": 1})
        assert "ERROR" not in capsys.readouterr().err
        assert operator_alerts == []


class TestTheCoverageRow:
    @pytest.mark.xfail(
        strict=True,
        reason="ledger 0908 audit.py:320 is open: verify_phases (another batch) "
        "compares and records parse_pytest_output's coverage as a number",
    )
    def test_320_no_total_row_is_not_measured(self):
        assert audit.parse_pytest_output("5 passed in 0.5s")["coverage"] is None

    def test_a_total_row_is_read(self):
        """Kept: pytest-cov's TOTAL percentage is the coverage."""
        parsed = audit.parse_pytest_output("5 passed in 0.5s\nTOTAL    150     12    92%\n")
        assert parsed["coverage"] == 92.0
