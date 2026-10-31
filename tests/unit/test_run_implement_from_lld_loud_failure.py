"""Every failure in `tools/run_implement_from_lld.py` is loud and alerts (#4097).

ADR 0236 and standard 0034: a failure is loud on standard error, logged with
details, stops what depends on it, and alerts the operator. The #3581 sweep
recorded 23 sites in this entry point (ledger 0908, lines from `79e18ad1`).
PR #4159 fixed eight of them (296, 345, 353, 1344, 1377, 1442, 1458, 1484),
tested in `test_impl_lands_through_driver.py`; these are the other fifteen.

Each test is named for its ledger line and drives `main()` with stand-ins, the
way `test_impl_lands_through_driver.py` does: a throwaway target repository,
a stand-in testing graph, a fake merge driver where a real run lands, and a
stand-in `subprocess.run` for the one git command a test makes fail. No model
is called and no graph node runs.

The entry point's shape: `main()` has one handler, which prints the failure
at ERROR on stderr (with its traceback when the tool did not name it itself),
calls `alert.alert_operator`, and exits 1. Everything below it raises.
"""
from __future__ import annotations

import io
import subprocess
import sys
import tokenize
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from assemblyzero.core import merge_driver

COMPLETED = {"issue_number": 42, "workflow_status": "completed", "error_message": ""}


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    assert result.returncode == 0, f"git {' '.join(args)}: {result.stderr}"
    return result


@pytest.fixture(autouse=True)
def _isolate_home(tmp_path, monkeypatch):
    """Halt snapshots, resume contracts and the audit log stay in tmp (#3531)."""
    from assemblyzero.core import resume_contract, state_persistence
    from assemblyzero.workflows.testing import audit as testing_audit

    state = tmp_path / "workflow_state"
    monkeypatch.setattr(state_persistence, "STATE_DIR", state)
    monkeypatch.setattr(resume_contract, "STATE_DIR", state)
    monkeypatch.setattr(
        testing_audit, "WORKFLOW_AUDIT_FILE", tmp_path / "workflow-audit.jsonl"
    )
    monkeypatch.delenv("ASSEMBLYZERO_WORKFLOW_DB", raising=False)
    # main sets this in os.environ for an --auto run; recorded here, it is
    # restored when the test ends instead of leaking into the next one.
    monkeypatch.setenv("ASSEMBLYZERO_AUTO_MODE", "1")


@pytest.fixture(autouse=True)
def _disarm_call_recording():
    from assemblyzero.core import call_recording

    yield
    call_recording.reset_context()


@pytest.fixture(autouse=True)
def _restore_streams():
    """The run record tees stdout and stderr until it is finished."""
    out, err = sys.stdout, sys.stderr
    yield
    sys.stdout, sys.stderr = out, err


@pytest.fixture
def target(tmp_path: Path) -> Path:
    origin = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "-q", "--bare", "--initial-branch=main", str(origin)],
        capture_output=True, text=True, check=True,
    )
    root = tmp_path / "target"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "Test")
    (root / ".gitignore").write_text("data/\ndocs/lineage/\n", encoding="utf-8")
    (root / "README.md").write_text("base\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")
    _git(root, "remote", "add", "origin", str(origin))
    _git(root, "push", "-qu", "origin", "main")
    return root


@pytest.fixture
def driver_configured(tmp_path, monkeypatch) -> None:
    driver = tmp_path / "tracked_pr_land.py"
    driver.write_text("", encoding="utf-8")
    monkeypatch.setenv(merge_driver.DRIVER_ENV, str(driver))

    def land(**kwargs):
        return merge_driver.Landing(pr_number=77, squash_sha="0123abcd", output="[OK]")

    monkeypatch.setattr(merge_driver, "land", land)


class _FakeApp:
    def __init__(self, values, write_work):
        self._values = values
        self._write_work = write_work

    def stream(self, initial_state, config):
        if self._write_work and initial_state.get("worktree_path"):
            wt = Path(initial_state["worktree_path"])
            (wt / "impl.py").write_text("x = 1\n", encoding="utf-8")
        yield {"N7_finalize": self._values}

    def get_state(self, config):
        return SimpleNamespace(values=self._values)


class _FakeWorkflow:
    """A stand-in testing graph. ``builds`` counts how often it was built."""

    def __init__(self, values=COMPLETED, write_work=True, raises=None):
        self._app = _FakeApp(values, write_work)
        self._raises = raises
        self.builds = 0
        self.streams = 0

    def __call__(self):
        self.builds += 1
        if self._raises is not None:
            raise self._raises
        return self

    def compile(self, checkpointer=None):
        outer = self

        class _Counted:
            def stream(self, initial_state, config):
                outer.streams += 1
                yield from outer._app.stream(initial_state, config)

            def get_state(self, config):
                return outer._app.get_state(config)

        return _Counted()


def _run_main(*argv: str, workflow: _FakeWorkflow | None = None) -> int:
    from tools import run_implement_from_lld as tool

    workflow = workflow or _FakeWorkflow()
    with patch("sys.argv", ["prog", *argv]), \
         patch("assemblyzero.workflows.testing.build_testing_workflow", new=workflow):
        try:
            return tool.main()
        except SystemExit as exc:
            return exc.code


def _mock_run(target: Path, tmp_path: Path, *extra: str) -> list[str]:
    return ["--issue", "42", "--repo", str(target), "--auto", "--mock",
            "--db-path", str(tmp_path / "ckpt.db"), *extra]


def _stub_git(monkeypatch, words: tuple[str, ...], result: subprocess.CompletedProcess):
    """Make the one git command whose argv holds ``words`` in order fail."""
    real = subprocess.run

    def run(argv, *args, **kwargs):
        argv = list(argv)
        if argv[:1] == ["git"] and all(w in argv for w in words):
            return result
        return real(argv, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", run)


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
    assert alert["where"].startswith("tools/run_implement_from_lld.py")
    assert alert["consequence"]
    return err


# --- Helpers that returned "" or None for a git failure -----------------------


class TestGitReadsRaise:
    def test_77_an_unreadable_branch_names_gits_error(
        self, tmp_path, capsys, operator_alerts,
    ):
        """It returned "", and the caller refused on stdout without git's
        stderr. An unborn HEAD makes rev-parse fail for real."""
        empty = tmp_path / "empty"
        empty.mkdir()
        _git(empty, "init", "-q", "-b", "main")
        workflow = _FakeWorkflow()

        rc = _run_main(*_mock_run(empty, tmp_path), workflow=workflow)

        _assert_failed(rc, capsys, operator_alerts, "rev-parse", "ambiguous argument 'HEAD'")
        assert workflow.builds == 0

    def test_123_a_failed_worktree_listing_is_not_no_worktree(
        self, target, tmp_path, driver_configured, monkeypatch, capsys, operator_alerts,
    ):
        """It returned None, "no existing worktree", and the run cut a new one
        beside whatever the listing could not show."""
        _stub_git(monkeypatch, ("worktree", "list"),
                  subprocess.CompletedProcess(["git"], 128, stdout="", stderr="fatal: listing exploded"))
        workflow = _FakeWorkflow()

        rc = _run_main("--issue", "42", "--repo", str(target), "--auto",
                       "--db-path", str(tmp_path / "ckpt.db"), workflow=workflow)

        _assert_failed(rc, capsys, operator_alerts, "fatal: listing exploded")
        assert not (target.parent / "target-42").exists()
        assert workflow.builds == 0


# --- The run's record ------------------------------------------------------------


class TestTheStatusFile:
    def test_961_an_unwritable_status_file_fails_the_run(
        self, target, tmp_path, capsys, operator_alerts,
    ):
        """It passed ("best-effort"): agents that read the file to tell a
        success from a failure found nothing, and the run exited 0."""
        status = target / "data" / "speedrun" / "runs" / ".implement-status-42.json"
        status.mkdir(parents=True)

        rc = _run_main(*_mock_run(target, tmp_path))

        _assert_failed(rc, capsys, operator_alerts, str(status))

    def test_961_the_status_file_is_written_on_success(self, target, tmp_path, operator_alerts):
        rc = _run_main(*_mock_run(target, tmp_path))

        assert rc == 0
        status = target / "data" / "speedrun" / "runs" / ".implement-status-42.json"
        assert '"SUCCESS"' in status.read_text(encoding="utf-8")
        assert operator_alerts == []


# --- Refusals before anything ran --------------------------------------------------


class TestRefusalsAlert:
    def test_990_a_missing_repository_alerts(self, tmp_path, capsys, operator_alerts):
        missing = tmp_path / "nope"

        rc = _run_main("--issue", "42", "--repo", str(missing), "--auto", "--mock")

        _assert_failed(rc, capsys, operator_alerts, str(missing))

    def test_996_no_repository_to_detect_alerts(
        self, tmp_path, monkeypatch, capsys, operator_alerts,
    ):
        nowhere = tmp_path / "nowhere"
        nowhere.mkdir()
        monkeypatch.chdir(nowhere)

        rc = _run_main("--issue", "42", "--auto", "--mock")

        _assert_failed(rc, capsys, operator_alerts, "Not in a git repository")

    def test_1008_a_non_positive_issue_alerts(self, target, capsys, operator_alerts):
        rc = _run_main("--issue", "0", "--repo", str(target), "--auto", "--mock")

        _assert_failed(rc, capsys, operator_alerts, "--issue must be a positive integer")

    def test_1087_another_issues_work_branch_alerts(
        self, target, tmp_path, capsys, operator_alerts,
    ):
        _git(target, "switch", "-q", "-c", "99-implementation")
        workflow = _FakeWorkflow()

        rc = _run_main(*_mock_run(target, tmp_path), workflow=workflow)

        _assert_failed(rc, capsys, operator_alerts, "99-implementation")
        assert workflow.builds == 0

    def test_1096_a_detached_head_alerts(self, target, tmp_path, capsys, operator_alerts):
        _git(target, "switch", "-q", "--detach", "HEAD")
        workflow = _FakeWorkflow()

        rc = _run_main(*_mock_run(target, tmp_path), workflow=workflow)

        _assert_failed(rc, capsys, operator_alerts, "detached HEAD")
        assert workflow.builds == 0

    def test_1123_a_failed_worktree_cut_alerts(
        self, target, tmp_path, capsys, operator_alerts,
    ):
        """A mock run never reuses a directory; the cut fails for real."""
        (target.parent / "target-42").mkdir()
        workflow = _FakeWorkflow()

        rc = _run_main(*_mock_run(target, tmp_path), workflow=workflow)

        _assert_failed(rc, capsys, operator_alerts, "already exists")
        assert workflow.builds == 0


# --- --select: a failure is not a cancel -------------------------------------------


def _lld(target: Path, name: str = "LLD-042.md") -> Path:
    lld_dir = target / "docs" / "lld" / "active"
    lld_dir.mkdir(parents=True, exist_ok=True)
    path = lld_dir / name
    path.write_text("# 42 - A feature\n\n| 2026-10-01 | APPROVED |\n", encoding="utf-8")
    return path


class TestSelect:
    def test_1003_select_with_no_lld_directory_fails(self, target, capsys, operator_alerts):
        """It printed and exited 0, as if the operator had cancelled."""
        rc = _run_main("--select", "--repo", str(target), "--auto", "--mock")

        _assert_failed(rc, capsys, operator_alerts, "no LLD directory")

    def test_1003_select_with_no_lld_files_fails(self, target, capsys, operator_alerts):
        (target / "docs" / "lld" / "active").mkdir(parents=True)

        rc = _run_main("--select", "--repo", str(target), "--auto", "--mock")

        _assert_failed(rc, capsys, operator_alerts, "no LLD files")

    def test_1003_an_invalid_selection_fails(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        _lld(target)
        monkeypatch.setattr("builtins.input", lambda *_a: "seven")

        rc = _run_main("--select", "--repo", str(target), "--auto", "--mock")

        _assert_failed(rc, capsys, operator_alerts, "invalid selection 'seven'")

    def test_1003_cancelling_the_menu_exits_zero(
        self, target, monkeypatch, capsys, operator_alerts,
    ):
        """Choosing 0 is the operator's decision, not a failure."""
        _lld(target)
        monkeypatch.setattr("builtins.input", lambda *_a: "0")
        workflow = _FakeWorkflow()

        rc = _run_main("--select", "--repo", str(target), "--auto", "--mock", workflow=workflow)

        assert rc == 0
        assert operator_alerts == []
        assert workflow.builds == 0


# --- Context files and the profile --------------------------------------------------


class TestInputs:
    def test_1181_one_invalid_context_file_stops_the_run(
        self, target, tmp_path, capsys, operator_alerts,
    ):
        """It printed the rejection and ran with the context that was left."""
        workflow = _FakeWorkflow(write_work=False)

        rc = _run_main(*_mock_run(target, tmp_path, "--no-worktree",
                                  "--context", "README.md", "--context", "missing.md"),
                       workflow=workflow)

        _assert_failed(rc, capsys, operator_alerts, "missing.md")
        assert workflow.streams == 0

    def test_1183_all_invalid_context_files_alert(
        self, target, tmp_path, capsys, operator_alerts,
    ):
        workflow = _FakeWorkflow(write_work=False)

        rc = _run_main(*_mock_run(target, tmp_path, "--no-worktree", "--context", "missing.md"),
                       workflow=workflow)

        _assert_failed(rc, capsys, operator_alerts, "missing.md")
        assert workflow.streams == 0

    def test_1181_valid_context_files_run(self, target, tmp_path, operator_alerts):
        workflow = _FakeWorkflow(write_work=False)

        rc = _run_main(*_mock_run(target, tmp_path, "--no-worktree", "--context", "README.md"),
                       workflow=workflow)

        assert rc == 0
        assert workflow.streams == 1
        assert operator_alerts == []

    def test_1199_an_invalid_profile_alerts(self, target, tmp_path, capsys, operator_alerts):
        workflow = _FakeWorkflow(write_work=False)

        rc = _run_main(*_mock_run(target, tmp_path, "--no-worktree", "--seat", "bogus"),
                       workflow=workflow)

        _assert_failed(rc, capsys, operator_alerts, "--seat 'bogus'")
        assert workflow.streams == 0


# --- --resume ----------------------------------------------------------------------


def _checkpoint(db: Path, thread_id: str) -> None:
    """A real checkpoint for ``thread_id``: a one-node graph run once."""
    from typing import TypedDict

    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.graph import END, START, StateGraph

    class _S(TypedDict):
        n: int

    graph = StateGraph(_S)
    graph.add_node("one", lambda s: {"n": s["n"] + 1})
    graph.add_edge(START, "one")
    graph.add_edge("one", END)
    with SqliteSaver.from_conn_string(str(db)) as memory:
        graph.compile(checkpointer=memory).invoke(
            {"n": 0}, {"configurable": {"thread_id": thread_id}},
        )


class TestResume:
    def test_1331_resume_with_no_checkpoint_refuses(
        self, target, tmp_path, capsys, operator_alerts,
    ):
        """It printed "starting fresh" and ran from the start."""
        workflow = _FakeWorkflow(write_work=False)

        rc = _run_main(*_mock_run(target, tmp_path, "--no-worktree", "--resume"),
                       workflow=workflow)

        _assert_failed(rc, capsys, operator_alerts, "--resume", "no checkpoint")
        assert workflow.streams == 0

    def test_1331_resume_with_a_checkpoint_runs(self, target, tmp_path, operator_alerts):
        _checkpoint(tmp_path / "ckpt.db", "42-testing")
        workflow = _FakeWorkflow(write_work=False)

        rc = _run_main(*_mock_run(target, tmp_path, "--no-worktree", "--resume"),
                       workflow=workflow)

        assert rc == 0
        assert workflow.streams == 1
        assert operator_alerts == []


# --- The entry point's handler -------------------------------------------------------


class TestTheHandler:
    def test_1489_an_exception_outside_mains_try_alerts(
        self, target, tmp_path, capsys, operator_alerts,
    ):
        """build_testing_workflow's re-raise escaped main as a bare traceback."""
        workflow = _FakeWorkflow(raises=RuntimeError("build exploded"))

        rc = _run_main(*_mock_run(target, tmp_path), workflow=workflow)

        err = _assert_failed(rc, capsys, operator_alerts, "RuntimeError: build exploded")
        assert "Traceback" in err


def test_the_module_carries_no_fail_open_tag():
    tool = Path(__file__).resolve().parents[2] / "tools" / "run_implement_from_lld.py"
    source = tool.read_text(encoding="utf-8")
    tags = [
        tok.string for tok in tokenize.generate_tokens(io.StringIO(source).readline)
        if tok.type == tokenize.COMMENT and "fail-open:" in tok.string
    ]
    assert tags == []
