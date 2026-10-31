"""halt_evidence.py under standard 0034, one test per sweep site (#3778).

The halt's evidence bundle is written after the halt has already alerted and
its state and plan are on disk. A piece of evidence the bundle cannot read is a
failure of its own: it alerts the operator with its cause, and the bundle names
it as unread rather than leaving it out, so nothing in the bundle reads as
complete when it is not. A lineage directory the state names and that is not
there is an ERROR line, because the HALT node's copy into that directory raises
on it and alerts. When an alert cannot be delivered the HALT node raises after
the state, the plan and the halt's own alert. Line numbers in the names are
ledger 0908's, at its base ``79e18ad1``.
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

import assemblyzero.core.halt_evidence as he
import assemblyzero.core.resume_contract as rc
import assemblyzero.core.state_persistence as sp
from assemblyzero.core import alert
from assemblyzero.core.halt_node import create_halt_node
from assemblyzero.core.halt_paths import repository_dirname


def _repo_with_record(tmp_path: Path, lines: list[str]) -> Path:
    repo = tmp_path / "repo"
    runs = repo / "data" / "speedrun" / "runs"
    runs.mkdir(parents=True)
    (runs / "preserved-branches.jsonl").write_text(
        "".join(line + "\n" for line in lines), encoding="utf-8"
    )
    return repo


def _record(repo: Path) -> Path:
    return repo / "data" / "speedrun" / "runs" / "preserved-branches.jsonl"


def _lineage(tmp_path: Path) -> Path:
    audit = tmp_path / "lineage"
    audit.mkdir()
    (audit / "001-draft.md").write_text("same\n", encoding="utf-8")
    (audit / "002-draft.md").write_text("same\n", encoding="utf-8")
    (audit / "003-verdict.md").write_text("different\n", encoding="utf-8")
    return audit


def _unreadable(monkeypatch, method: str, target: Path) -> None:
    real = getattr(Path, method)

    def refuse(self, *args, **kwargs):
        if self == target:
            raise PermissionError(13, "Permission denied", str(self))
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, method, refuse)


GOOD = (
    '{"at": "2026-08-27 13:01:22", "branch": "graveyard/leavings-1", '
    '"detail": "1 file(s)", "run": "", "source": "leavings"}'
)


class TestLineageArtifacts:
    def test_43_an_unreadable_artifact_alerts_and_is_named_unread(
        self, tmp_path, monkeypatch, operator_alerts
    ):
        audit = _lineage(tmp_path)
        _unreadable(monkeypatch, "read_bytes", audit / "002-draft.md")

        evidence = he.build_halt_evidence(
            {"issue_number": 42, "audit_dir": str(audit), "repo_root": str(tmp_path)},
            "testing", stage="N4", error_message="halt",
        )

        assert len(operator_alerts) == 1
        sent = operator_alerts[0]
        assert "002-draft.md" in sent["what"]
        assert "PermissionError" in sent["cause"]
        assert sent["issue"] == 42
        row = next(f for f in evidence["artifacts"]["files"] if f["name"] == "002-draft.md")
        assert row["sha256"] is None
        assert "PermissionError" in row["unreadable"]
        assert any("002-draft.md" in item for item in evidence["unread_evidence"])
        md = he.render_halt_evidence_md(evidence)
        assert "Evidence that could not be read" in md
        assert "readable files only" in md

    def test_readable_artifacts_are_hashed_and_grouped_quietly(
        self, tmp_path, operator_alerts
    ):
        """Kept: a lineage dir that reads cleanly alerts nothing."""
        audit = _lineage(tmp_path)

        evidence = he.build_halt_evidence(
            {"issue_number": 1, "audit_dir": str(audit)},
            "testing", stage="N4", error_message="halt",
        )

        assert operator_alerts == []
        assert not evidence.get("unread_evidence")
        assert evidence["artifacts"]["identical_groups"] == [["001-draft.md", "002-draft.md"]]

    def test_44_86_92_no_fail_open_tag_remains(self):
        assert "fail-open" not in inspect.getsource(he)


class TestThePreservationRecord:
    def test_85_a_corrupt_record_in_the_tail_alerts_and_keeps_its_place(
        self, tmp_path, operator_alerts
    ):
        repo = _repo_with_record(tmp_path, [GOOD, "{ not json", GOOD])

        evidence = he.build_halt_evidence(
            {"issue_number": 7, "repo_root": str(repo)},
            "testing", stage="N4", error_message="halt",
        )

        assert len(operator_alerts) == 1
        assert "line 2" in operator_alerts[0]["what"]
        assert "JSONDecodeError" in operator_alerts[0]["cause"]
        tail = evidence["preserved_refs_tail"]
        assert len(tail) == 3
        assert tail[1]["corrupt_line"] == 2
        assert any("line 2" in item for item in evidence["unread_evidence"])
        assert "corrupt record" in he.render_halt_evidence_md(evidence)

    def test_85_a_record_that_is_not_an_object_alerts(self, tmp_path, operator_alerts):
        repo = _repo_with_record(tmp_path, [GOOD, '["not", "a", "record"]'])

        evidence = he.build_halt_evidence(
            {"issue_number": 7, "repo_root": str(repo)},
            "testing", stage="N4", error_message="halt",
        )

        assert len(operator_alerts) == 1
        assert "not a record" in operator_alerts[0]["cause"]
        assert evidence["preserved_refs_tail"][1]["corrupt_line"] == 2
        he.render_halt_evidence_md(evidence)  # renders, never AttributeError

    def test_a_corrupt_line_before_the_tail_is_not_read(self, tmp_path, operator_alerts):
        """Kept: the bundle carries the last PRESERVED_TAIL records, so only
        those are read; a line before them shapes nothing in the bundle."""
        repo = _repo_with_record(tmp_path, ["{ not json"] + [GOOD] * he.PRESERVED_TAIL)

        evidence = he.build_halt_evidence(
            {"issue_number": 7, "repo_root": str(repo)},
            "testing", stage="N4", error_message="halt",
        )

        assert operator_alerts == []
        assert len(evidence["preserved_refs_tail"]) == he.PRESERVED_TAIL

    def test_91_an_unreadable_record_alerts_and_is_named_unread(
        self, tmp_path, monkeypatch, operator_alerts
    ):
        repo = _repo_with_record(tmp_path, [GOOD])
        _unreadable(monkeypatch, "read_text", _record(repo))

        evidence = he.build_halt_evidence(
            {"issue_number": 7, "repo_root": str(repo)},
            "testing", stage="N4", error_message="halt",
        )

        assert len(operator_alerts) == 1
        assert str(_record(repo)) in operator_alerts[0]["what"]
        assert "PermissionError" in operator_alerts[0]["cause"]
        assert any("preservation record" in item for item in evidence["unread_evidence"])
        assert "preservation record" in he.render_halt_evidence_md(evidence)

    def test_an_absent_record_is_quiet(self, tmp_path, operator_alerts):
        """Kept: a repo where no branch was ever preserved has no record."""
        evidence = he.build_halt_evidence(
            {"issue_number": 7, "repo_root": str(tmp_path)},
            "testing", stage="N4", error_message="halt",
        )

        assert operator_alerts == []
        assert evidence["preserved_refs_tail"] == []
        assert not evidence.get("unread_evidence")


class TestTheAuditDir:
    def test_120_a_named_audit_dir_that_is_missing_is_an_error_line(
        self, tmp_path, capsys, caplog, operator_alerts
    ):
        missing = tmp_path / "gone"

        evidence = he.build_halt_evidence(
            {"issue_number": 7, "audit_dir": str(missing)},
            "testing", stage="N4", error_message="halt",
        )

        err = capsys.readouterr().err
        assert "ERROR [HALT EVIDENCE]" in err
        assert str(missing) in err
        assert any(
            r.levelname == "ERROR" and str(missing) in r.getMessage() for r in caplog.records
        )
        assert any(str(missing) in item for item in evidence["unread_evidence"])
        assert "not a directory" in he.render_halt_evidence_md(evidence)

    def test_120_the_halt_node_alerts_for_a_missing_audit_dir(
        self, tmp_path, monkeypatch, capsys, operator_alerts
    ):
        """Pins why site 120 is an ERROR line and not a third alert: the HALT
        node's copy into the audit dir raises on the same directory, and that
        is alerted with the directory named."""
        store = tmp_path / "state"
        store.mkdir()
        monkeypatch.setattr(rc, "STATE_DIR", store)
        monkeypatch.setattr(sp, "STATE_DIR", store)
        missing = tmp_path / "gone"

        create_halt_node("testing")(
            {"issue_number": 7, "repo_root": str(tmp_path), "audit_dir": str(missing),
             "error_message": "halt"}
        )
        capsys.readouterr()

        assert any(
            a["what"] == "the halt's evidence bundle was not written" and str(missing) in a["cause"]
            for a in operator_alerts
        )

    def test_no_audit_dir_named_is_quiet(self, tmp_path, capsys, operator_alerts):
        """Kept: a run with no lineage has none to list."""
        evidence = he.build_halt_evidence(
            {"issue_number": 7}, "testing", stage="N4", error_message="halt",
        )

        assert "ERROR" not in capsys.readouterr().err
        assert not evidence.get("unread_evidence")


class TestWhenTheReporterFails:
    def test_an_undelivered_evidence_alert_leaves_the_halt_saved_and_raises(
        self, tmp_path, monkeypatch, capsys
    ):
        """The halt alerts first and its state and plan are on disk; an
        evidence alert that cannot be delivered then raises out of the HALT
        node, so the run exits non-zero rather than hide the failed alert."""
        store = tmp_path / "state"
        store.mkdir()
        monkeypatch.setattr(rc, "STATE_DIR", store)
        monkeypatch.setattr(sp, "STATE_DIR", store)
        audit = _lineage(tmp_path)
        _unreadable(monkeypatch, "read_bytes", audit / "002-draft.md")
        delivered: list[dict] = []

        def first_only(**kwargs):
            if delivered:
                raise alert.AlertDeliveryError("email: SES refused")
            delivered.append(kwargs)
            return kwargs

        monkeypatch.setattr(alert, "alert_operator", first_only)

        with pytest.raises(alert.AlertDeliveryError):
            create_halt_node("testing")(
                {"issue_number": 7, "repo_root": str(tmp_path), "audit_dir": str(audit),
                 "error_message": "halt"}
            )
        capsys.readouterr()

        halted_in = store / repository_dirname(tmp_path)
        assert len(delivered) == 1
        assert delivered[0]["what"].startswith("the testing workflow halted")
        snapshot = json.loads((halted_in / "testing-7.json").read_text(encoding="utf-8"))
        assert snapshot, "the state snapshot is written before any evidence"
        assert (halted_in / "recovery-7-testing.json").is_file(), "so is the recovery plan"
