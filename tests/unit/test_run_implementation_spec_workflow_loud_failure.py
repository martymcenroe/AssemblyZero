"""Every failure in `tools/run_implementation_spec_workflow.py` is loud and alerts (#4098).

ADR 0236 and standard 0034: a failure is loud on standard error, logged with
details, stops what depends on it, and alerts the operator. The #3581 sweep
recorded 10 sites in this entry point (ledger 0908, lines from `79e18ad1`).
Each test is named for its ledger line and drives `main()` with stand-ins: a
throwaway target repository, a stand-in for the compiled spec graph, and a
stand-in for `git` or the resume contract only where a test injects that
failure. No model is called and no graph node runs.

The entry point's shape: `main()` has one handler, which prints the failure
at ERROR on stderr (with its traceback when the tool did not name it itself),
calls `alert.alert_operator`, and returns 1. Everything below it raises. A
node's error goes to HALT inside the graph, which alerts; the tool alerts
only for an error that reached it without HALT.
"""
from __future__ import annotations

import io
import subprocess
import sys
import tokenize
from pathlib import Path
from unittest.mock import patch

import pytest


def _git(repo: Path, *args: str) -> None:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8", check=False,
    )
    assert result.returncode == 0, f"git {' '.join(args)}: {result.stderr}"


@pytest.fixture
def target(tmp_path: Path) -> Path:
    root = tmp_path / "target"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "Test")
    (root / "README.md").write_text("base\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")
    return root


def _lld(target: Path) -> Path:
    lld_dir = target / "docs" / "lld" / "active"
    lld_dir.mkdir(parents=True, exist_ok=True)
    path = lld_dir / "LLD-042.md"
    path.write_text("# 42 - A feature\n", encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def _environment(monkeypatch):
    """No root override; the auto-mode flag main sets is restored after."""
    monkeypatch.delenv("ASSEMBLYZERO_ROOT", raising=False)
    monkeypatch.setenv("ASSEMBLYZERO_AUTO_MODE", "1")


class _Graph:
    """Stands in for the compiled spec graph: yields ``events``, or raises."""

    def __init__(self, events, raises=None):
        self.events = list(events)
        self.raises = raises
        self.streams = 0

    def stream(self, state, config):
        self.streams += 1
        if self.raises is not None:
            raise self.raises
        yield from self.events


FINISHED = [
    {"N5_review_spec": {"review_verdict": "APPROVED"}},
    {"N6_finalize_spec": {"spec_path": "docs/lld/drafts/spec-0042.md", "error_message": ""}},
]


def _install(monkeypatch, events=FINISHED, raises=None) -> _Graph:
    from tools import run_implementation_spec_workflow as tool

    graph = _Graph(events, raises)
    monkeypatch.setattr(tool, "create_implementation_spec_graph", lambda: graph)
    return graph


def _main(*argv: str) -> int:
    from tools import run_implementation_spec_workflow as tool

    with patch("sys.argv", ["prog", *argv]):
        try:
            return tool.main()
        except SystemExit as exc:
            return exc.code


def _assert_failed(rc, capsys, operator_alerts, *needles: str) -> str:
    """Exit 1, an ERROR line on stderr, and one alert whose cause names it."""
    err = capsys.readouterr().err
    assert rc == 1, err
    assert "ERROR" in err
    assert len(operator_alerts) == 1, operator_alerts
    alert = operator_alerts[0]
    for needle in needles:
        assert needle in err, (needle, err)
        assert needle in alert["cause"], (needle, alert)
    assert alert["where"].startswith("tools/run_implementation_spec_workflow.py")
    assert alert["consequence"]
    return err


class TestTheTargetRepository:
    def test_293_git_failing_in_the_cwd_stops_the_run(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        """It passed and used the working directory as the target."""
        _lld(target)
        monkeypatch.chdir(target)
        graph = _install(monkeypatch)
        real = subprocess.run

        def run(argv, *args, **kwargs):
            if list(argv)[:1] == ["git"] and "--show-toplevel" in list(argv):
                raise subprocess.TimeoutExpired("git", 10)
            return real(argv, *args, **kwargs)

        monkeypatch.setattr(subprocess, "run", run)

        rc = _main("--issue", "42", "--mock")

        _assert_failed(rc, capsys, operator_alerts, "timed out")
        assert graph.streams == 0

    def test_296_a_cwd_outside_any_repository_refuses_without_repo(
        self, tmp_path, monkeypatch, capsys, operator_alerts,
    ):
        """It made the working directory the target repository."""
        nowhere = tmp_path / "nowhere"
        nowhere.mkdir()
        monkeypatch.chdir(nowhere)
        graph = _install(monkeypatch)

        rc = _main("--issue", "42", "--mock")

        err = _assert_failed(rc, capsys, operator_alerts, "not a git repository")
        assert "--repo" in err
        assert graph.streams == 0
        assert not (nowhere / "docs").exists()

    def test_335_the_assemblyzero_root_as_target_alerts(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        """It printed on stdout and exited 1 with no alert."""
        monkeypatch.setenv("ASSEMBLYZERO_ROOT", str(target))
        graph = _install(monkeypatch)

        rc = _main("--issue", "42", "--repo", str(target), "--mock")

        _assert_failed(rc, capsys, operator_alerts, "AssemblyZero root")
        assert graph.streams == 0

    def test_738_a_missing_repository_alerts(self, tmp_path, monkeypatch, capsys, operator_alerts):
        missing = tmp_path / "nope"
        _install(monkeypatch)

        rc = _main("--issue", "42", "--repo", str(missing), "--mock")

        _assert_failed(rc, capsys, operator_alerts, str(missing))


class TestTheInputs:
    def test_414_a_missing_lld_refuses_before_any_state(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        """It left lld_path empty and started the workflow anyway."""
        graph = _install(monkeypatch)
        consumed = []
        monkeypatch.setattr(
            "assemblyzero.core.resume_contract.check_and_consume",
            lambda *a, **k: consumed.append(a) or True,
        )

        rc = _main("--issue", "42", "--repo", str(target), "--mock")

        _assert_failed(rc, capsys, operator_alerts, "no LLD")
        assert graph.streams == 0
        assert consumed == []
        assert not (target / "docs" / "lineage").exists()

    def test_414_an_explicit_lld_that_is_not_there_refuses(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        graph = _install(monkeypatch)

        rc = _main("--issue", "42", "--repo", str(target), "--mock",
                   "--lld", "docs/lld/active/LLD-999.md")

        _assert_failed(rc, capsys, operator_alerts, "LLD-999.md")
        assert graph.streams == 0

    def test_727_a_non_positive_issue_alerts(self, target, monkeypatch, capsys, operator_alerts):
        graph = _install(monkeypatch)

        rc = _main("--issue", "0", "--repo", str(target), "--mock")

        _assert_failed(rc, capsys, operator_alerts, "--issue must be a positive integer")
        assert graph.streams == 0

    def test_635_a_refused_resume_contract_alerts(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        """It returned 1 with no alert from this file."""
        _lld(target)
        graph = _install(monkeypatch)

        def refuse(workflow, issue, *, accept_changed=False, log=print, **_kw):
            log("RESUME CONTRACT: the world changed since the halt")
            log("  LLD-042.md: hash changed")
            return False

        monkeypatch.setattr("assemblyzero.core.resume_contract.check_and_consume", refuse)

        rc = _main("--issue", "42", "--repo", str(target), "--mock")

        _assert_failed(rc, capsys, operator_alerts, "LLD-042.md: hash changed")
        assert graph.streams == 0


class TestTheRun:
    def test_a_finished_spec_succeeds_without_an_alert(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        _lld(target)
        graph = _install(monkeypatch)

        rc = _main("--issue", "42", "--repo", str(target), "--mock")

        assert rc == 0, capsys.readouterr().err
        assert graph.streams == 1
        assert operator_alerts == []

    def test_683_a_node_error_goes_to_stderr_and_halt_is_not_alerted_twice(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        """It printed the node's error on stdout. The HALT node alerted for
        it (it sets workflow_status "halted"), so the tool does not."""
        _lld(target)
        _install(monkeypatch, events=[
            {"N2_generate_spec": {"error_message": "N2 drafter failed"}},
            {"HALT": {"workflow_status": "halted", "error_message": "N2 drafter failed"}},
        ])

        rc = _main("--issue", "42", "--repo", str(target), "--mock")

        err = capsys.readouterr().err
        assert rc == 1
        assert "N2 drafter failed" in err
        assert operator_alerts == []

    def test_683_an_error_that_bypassed_halt_alerts_here(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        _lld(target)
        _install(monkeypatch, events=[{"N6_finalize_spec": {"error_message": "N6 could not write"}}])

        rc = _main("--issue", "42", "--repo", str(target), "--mock")

        _assert_failed(rc, capsys, operator_alerts, "N6 could not write")

    def test_696_a_graph_exception_alerts_with_its_type_and_traceback(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        """It printed the message on stdout with no type, a traceback only
        under --debug, and alerted no one."""
        _lld(target)
        _install(monkeypatch, raises=RuntimeError("graph exploded"))

        rc = _main("--issue", "42", "--repo", str(target), "--mock")

        err = _assert_failed(rc, capsys, operator_alerts, "RuntimeError: graph exploded")
        assert "Traceback" in err

    def test_557_cost_telemetry_is_emitted(self, target, monkeypatch, operator_alerts):
        from assemblyzero import telemetry

        _lld(target)
        _install(monkeypatch, events=[
            {"N6_finalize_spec": {"spec_path": "x.md", "node_costs": {"N2": 0.25}}},
        ])
        emitted = []
        monkeypatch.setattr(telemetry, "emit", lambda *a, **k: emitted.append((a, k)))

        rc = _main("--issue", "42", "--repo", str(target), "--mock")

        assert rc == 0
        assert emitted and emitted[0][0][0] == "workflow.cost"

    def test_557_a_missing_telemetry_module_fails_the_run(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        """An ImportError dropped the cost telemetry silently."""
        _lld(target)
        _install(monkeypatch, events=[
            {"N6_finalize_spec": {"spec_path": "x.md", "node_costs": {"N2": 0.25}}},
        ])
        monkeypatch.setitem(sys.modules, "assemblyzero.telemetry", None)

        rc = _main("--issue", "42", "--repo", str(target), "--mock")

        _assert_failed(rc, capsys, operator_alerts, "assemblyzero.telemetry")


def test_the_module_carries_no_fail_open_tag():
    tool = Path(__file__).resolve().parents[2] / "tools" / "run_implementation_spec_workflow.py"
    source = tool.read_text(encoding="utf-8")
    tags = [
        tok.string for tok in tokenize.generate_tokens(io.StringIO(source).readline)
        if tok.type == tokenize.COMMENT and "fail-open:" in tok.string
    ]
    assert tags == []
