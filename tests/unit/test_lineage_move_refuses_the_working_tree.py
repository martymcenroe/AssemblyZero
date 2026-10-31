"""An unset audit_dir must never move the working tree (#4303).

`Path("")` is the working directory, which exists, so N7 used to hand it to
`move_lineage_to_done` as the run's lineage. That fell back to `audit_dir.name`,
which is empty, so `<target>/docs/lineage/done` itself became the destination,
and `shutil.move` copies across a filesystem boundary and then deletes the
source. The documented launch is from the AssemblyZero checkout with `--repo`
naming another repository, so that is the checkout it would have deleted.
"""
from __future__ import annotations

import importlib
import shutil
from pathlib import Path

import pytest

from assemblyzero.workflows.requirements import audit

# The nodes package re-exports the node FUNCTION under the module's name.
fin = importlib.import_module("assemblyzero.workflows.testing.nodes.finalize")


@pytest.fixture
def target(tmp_path: Path) -> Path:
    repo = tmp_path / "target"
    (repo / "docs" / "lineage" / "active").mkdir(parents=True)
    return repo


@pytest.fixture
def no_move(monkeypatch):
    """Any call to `shutil.move` fails the test, whatever the code does with it."""

    def refuse(*args, **_kwargs):
        pytest.fail(f"shutil.move was reached with {args}")

    monkeypatch.setattr(shutil, "move", refuse)


def _state(repo: Path, **overrides) -> dict:
    state = {
        "issue_number": 7,
        "repo_root": str(repo),
        "lld_path": "",
        "test_report_path": "",
        "implementation_report_path": "",
        "test_files": ["tests/test_x.py"],
        "implementation_files": ["x.py"],
        "coverage_achieved": 95.0,
        "coverage_target": 90,
        "iteration_count": 1,
        "green_phase_output": "4 passed in 0.2s",
        "skip_e2e": True,
    }
    state.update(overrides)
    return state


class TestN7RefusesAnUnsetAuditDir:
    """T1, R1."""

    @pytest.mark.parametrize("state_extra", [{}, {"audit_dir": ""}])
    def test_it_halts_and_touches_nothing(
        self, tmp_path, monkeypatch, capsys, target, no_move, state_extra
    ):
        sandbox = tmp_path / "started-here"
        sandbox.mkdir()
        sentinel = sandbox / "sentinel.txt"
        sentinel.write_text("still here", encoding="utf-8")
        monkeypatch.chdir(sandbox)

        result = fin.finalize(_state(target, **state_extra))

        assert "audit_dir" in result["error_message"]
        assert sentinel.read_text(encoding="utf-8") == "still here"
        assert [path.name for path in sandbox.iterdir()] == ["sentinel.txt"]
        assert not (target / "docs" / "lineage" / "done").exists()
        assert not (target / "docs" / "reports").exists()
        assert "ERROR [N7]" in capsys.readouterr().err

    def test_its_error_routes_to_halt(self, target, monkeypatch, tmp_path):
        from assemblyzero.workflows.testing.graph import route_after_finalize

        monkeypatch.chdir(tmp_path)
        assert route_after_finalize(fin.finalize(_state(target))) == "HALT"


class TestTheMoveAcceptsOnlyALineage:
    """T2 and T3, R2 and R3: each raises before anything on disk changes."""

    def _refused(self, source: Path, target: Path, operator_alerts) -> None:
        with pytest.raises(audit.LineageSourceError) as raised:
            audit.move_lineage_to_done(source, target)
        assert str(source) in str(raised.value)
        assert not (target / "docs" / "lineage" / "done").exists()
        assert len(operator_alerts) == 1
        assert operator_alerts[0]["repo"] == str(target)

    def test_the_working_directory_as_a_dot(
        self, tmp_path, monkeypatch, target, no_move, operator_alerts
    ):
        monkeypatch.chdir(tmp_path)
        self._refused(Path("."), target, operator_alerts)

    def test_a_directory_of_the_target_outside_active(self, target, no_move, operator_alerts):
        self._refused(target / "docs", target, operator_alerts)

    def test_the_active_root_itself(self, target, no_move, operator_alerts):
        self._refused(target / "docs" / "lineage" / "active", target, operator_alerts)

    def test_the_working_directory_by_absolute_path(
        self, tmp_path, monkeypatch, target, no_move, operator_alerts
    ):
        sandbox = tmp_path / "started-here"
        sandbox.mkdir()
        monkeypatch.chdir(sandbox)
        self._refused(sandbox, target, operator_alerts)

    def test_the_target_repository(self, target, no_move, operator_alerts):
        self._refused(target, target, operator_alerts)

    def test_an_ancestor_of_the_working_directory(
        self, tmp_path, monkeypatch, target, no_move, operator_alerts
    ):
        deep = tmp_path / "a" / "b"
        deep.mkdir(parents=True)
        monkeypatch.chdir(deep)
        self._refused(tmp_path / "a", target, operator_alerts)

    def test_a_file_under_active(self, target, no_move, operator_alerts):
        stray = target / "docs" / "lineage" / "active" / "stray.md"
        stray.write_text("not a lineage", encoding="utf-8")
        self._refused(stray, target, operator_alerts)

    def test_a_lineage_holding_the_working_directory(
        self, target, monkeypatch, no_move, operator_alerts
    ):
        """Strictly inside active/, and still never moved out from under the run."""
        lineage = target / "docs" / "lineage" / "active" / "7-testing"
        inner = lineage / "run-1"
        inner.mkdir(parents=True)
        monkeypatch.chdir(inner)
        self._refused(lineage, target, operator_alerts)


def test_a_real_lineage_still_moves(target, operator_alerts):
    """T4, R2."""
    active = target / "docs" / "lineage" / "active" / "7-testing" / "run-1"
    active.mkdir(parents=True)
    (active / "001-report.md").write_text("report", encoding="utf-8")

    done = audit.move_lineage_to_done(active, target)

    assert done == target / "docs" / "lineage" / "done" / "7-testing" / "run-1"
    assert (done / "001-report.md").read_text(encoding="utf-8") == "report"
    assert not active.exists()
    assert operator_alerts == []


def test_n7_writes_its_audit_files_where_the_state_says(tmp_path, monkeypatch, target):
    """T5, R4: run from elsewhere, and nothing lands in the working directory."""
    sandbox = tmp_path / "started-here"
    sandbox.mkdir()
    monkeypatch.chdir(sandbox)
    lineage = target / "docs" / "lineage" / "active" / "7-testing" / "run-1"
    lineage.mkdir(parents=True)

    result = fin.finalize(
        _state(target, audit_dir=str(lineage), token_budget=100, estimated_tokens_used=10)
    )

    assert not result.get("error_message")
    assert list(sandbox.iterdir()) == []
    done = target / "docs" / "lineage" / "done" / "7-testing" / "run-1"
    names = [path.name for path in done.iterdir()]
    assert any(name.endswith("summary.md") for name in names)
    assert any(name.endswith("token-budget.md") for name in names)
    assert not lineage.exists()
