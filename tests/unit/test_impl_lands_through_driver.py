"""A real implementation run lands its branch through the merge driver (#4150).

A real run used to end by pushing `<issue>-implementation` and printing a
`gh pr create` that this machine's gh wrapper refuses to every process but the
fleet merge driver. #3704 fixed the same defect in the LLD workflow. These hold
`tools/run_implement_from_lld.py` to the same shape: commit, hand the worktree
and branch to `merge_driver.land`, push nothing itself, refuse at start when
`AZ_MERGE_DRIVER` is unset, and halt through the HALT node, which alerts, when
the end state cannot be reached (ADR 0236).

They also hold the run's outcome to the same rule: a run is a success only
when N7 finalize said so (`workflow_status == "completed"`, #2677). Every
other end is a failure that alerts and exits 1, and lands nothing.
"""
from __future__ import annotations

import io
import subprocess
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from assemblyzero.core import merge_driver


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


@pytest.fixture(autouse=True)
def _disarm_call_recording():
    from assemblyzero.core import call_recording

    yield
    call_recording.reset_context()


@pytest.fixture
def driver_configured(tmp_path, monkeypatch) -> Path:
    driver = tmp_path / "tracked_pr_land.py"
    driver.write_text("", encoding="utf-8")
    monkeypatch.setenv(merge_driver.DRIVER_ENV, str(driver))
    return driver


@pytest.fixture
def target_repo(tmp_path: Path) -> Path:
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


def _origin_heads(target: Path) -> str:
    origin = target.parent / "origin.git"
    return _git(origin, "for-each-ref", "--format=%(refname)", "refs/heads/").stdout


def _worktree_with_work(target: Path) -> Path:
    """A worktree on `42-implementation` with a checkpoint commit, late work
    written after it, an ignored lineage directory and a cache."""
    wt = target.parent / "target-42"
    _git(target, "worktree", "add", "-q", "-b", "42-implementation", str(wt))
    (wt / "impl.py").write_text("x = 1\n", encoding="utf-8")
    _git(wt, "add", "impl.py")
    _git(wt, "commit", "-qm", "[CP:post-green] issue #42")
    (wt / "report.md").write_text("late\n", encoding="utf-8")
    lineage = wt / "docs" / "lineage" / "active" / "42-testing"
    lineage.mkdir(parents=True)
    (lineage / "001-lld.md").write_text("lineage\n", encoding="utf-8")
    (wt / "__pycache__").mkdir()
    (wt / "__pycache__" / "x.pyc").write_bytes(b"\0")
    return wt


class _Landed:
    """A fake `merge_driver.land` that records its call and reports a landing."""

    def __init__(self):
        self.calls: list[dict] = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return merge_driver.Landing(pr_number=77, squash_sha="0123abcd", output="[OK] stage=landed")


class _Refused:
    """A fake `merge_driver.land` that refuses as the driver does on a failed check."""

    OUTPUT = (
        "[FAIL] stage=checks_failed\n"
        "PR #77 is unstable because its own checks failed; nothing merged."
    )

    def __init__(self):
        self.calls: list[dict] = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        raise merge_driver.MergeDriverError(
            f"the merge driver did not land {kwargs['branch']} (exit 1):\n{self.OUTPUT}"
        )


class _SpyRun:
    """Every subprocess argv the finish runs, delegated to the real thing."""

    def __init__(self):
        self.argvs: list[list[str]] = []
        self._real = subprocess.run

    def __call__(self, argv, *args, **kwargs):
        self.argvs.append(list(argv))
        return self._real(argv, *args, **kwargs)


# --- T1: the success path lands through the driver and pushes nothing --------


class TestARealRunLandsThroughTheDriver:
    def test_the_driver_is_called_once_with_the_branch_worktree_and_title(
        self, target_repo, driver_configured, monkeypatch,
    ):
        from tools.run_implement_from_lld import finish_standalone_run

        wt = _worktree_with_work(target_repo)
        land = _Landed()
        monkeypatch.setattr(merge_driver, "land", land)

        finished, lines = finish_standalone_run(target_repo, wt, 42, "main", mock=False)

        assert finished, lines
        assert len(land.calls) == 1
        call = land.calls[0]
        assert call["branch"] == "42-implementation"
        assert Path(call["worktree"]) == wt
        assert call["title"].endswith("(Closes #42)")
        assert call["issue"] == 42
        assert call["base"] == "main"
        assert any("landed: PR #77" in ln and "0123abcd" in ln for ln in lines), lines

    def test_the_body_file_closes_the_issue_on_its_own_line(
        self, target_repo, driver_configured, monkeypatch,
    ):
        from tools.run_implement_from_lld import finish_standalone_run

        wt = _worktree_with_work(target_repo)
        land = _Landed()
        monkeypatch.setattr(merge_driver, "land", land)

        finish_standalone_run(target_repo, wt, 42, "main", mock=False)

        body_file = Path(land.calls[0]["body_file"])
        assert body_file.parent == target_repo / "data" / "assemblyzero" / "pr-bodies"
        assert "Closes #42" in body_file.read_text(encoding="utf-8").splitlines()

    def test_nothing_is_pushed_and_gh_is_never_run(
        self, target_repo, driver_configured, monkeypatch,
    ):
        import tools.run_implement_from_lld as tool

        wt = _worktree_with_work(target_repo)
        heads_before = _origin_heads(target_repo)
        monkeypatch.setattr(merge_driver, "land", _Landed())
        spy = _SpyRun()
        monkeypatch.setattr(tool.subprocess, "run", spy)

        tool.finish_standalone_run(target_repo, wt, 42, "main", mock=False)

        assert _origin_heads(target_repo) == heads_before
        assert not [a for a in spy.argvs if "push" in a], spy.argvs
        assert not [a for a in spy.argvs if a and Path(a[0]).name in ("gh", "gh.exe")]

    def test_the_late_work_is_committed_on_the_branch_the_driver_gets(
        self, target_repo, driver_configured, monkeypatch,
    ):
        from tools.run_implement_from_lld import finish_standalone_run

        wt = _worktree_with_work(target_repo)
        monkeypatch.setattr(merge_driver, "land", _Landed())

        finish_standalone_run(target_repo, wt, 42, "main", mock=False)

        files = _git(target_repo, "ls-tree", "--name-only", "42-implementation").stdout.split()
        assert "impl.py" in files and "report.md" in files

    def test_ignored_lineage_is_kept_and_caches_are_not(
        self, target_repo, driver_configured, monkeypatch,
    ):
        from tools.run_implement_from_lld import finish_standalone_run

        wt = _worktree_with_work(target_repo)
        monkeypatch.setattr(merge_driver, "land", _Landed())

        finish_standalone_run(target_repo, wt, 42, "main", mock=False)

        kept = list((target_repo / "data" / "runs-kept").rglob("001-lld.md"))
        assert len(kept) == 1
        assert kept[0].read_text(encoding="utf-8") == "lineage\n"
        assert not list((target_repo / "data" / "runs-kept").rglob("x.pyc"))

    def test_no_gh_pr_create_line_is_printed(
        self, target_repo, driver_configured, monkeypatch,
    ):
        from tools.run_implement_from_lld import finish_standalone_run

        wt = _worktree_with_work(target_repo)
        monkeypatch.setattr(merge_driver, "land", _Landed())

        _, lines = finish_standalone_run(target_repo, wt, 42, "main", mock=False)

        assert not [ln for ln in lines if "gh pr create" in ln], lines


# --- T3: a refusal or a git failure keeps everything and says why ------------


class TestAnUnfinishedRunKeepsItsWork:
    def test_a_driver_refusal_keeps_the_worktree_and_branch_with_its_output(
        self, target_repo, driver_configured, monkeypatch,
    ):
        from tools.run_implement_from_lld import finish_standalone_run

        wt = _worktree_with_work(target_repo)
        monkeypatch.setattr(merge_driver, "land", _Refused())

        finished, lines = finish_standalone_run(target_repo, wt, 42, "main", mock=False)

        assert not finished
        assert wt.exists()
        assert "42-implementation" in _git(target_repo, "branch", "--list").stdout
        assert any("stage=checks_failed" in ln for ln in lines), lines

    def test_a_git_status_failure_stops_before_anything_is_moved(
        self, target_repo, driver_configured, monkeypatch,
    ):
        """Ledger 0908, line 296: an unchecked `git status` read as an empty
        listing, nothing was kept, and the removal then deleted ignored files."""
        from tools.run_implement_from_lld import finish_standalone_run

        wt = _worktree_with_work(target_repo)
        (wt / ".git").write_text("gitdir: /nonexistent/worktree\n", encoding="utf-8")
        land = _Landed()
        monkeypatch.setattr(merge_driver, "land", land)

        finished, lines = finish_standalone_run(target_repo, wt, 42, "main", mock=False)

        assert not finished
        assert not land.calls
        assert (wt / "docs" / "lineage" / "active" / "42-testing" / "001-lld.md").exists()
        assert any(ln.startswith("stopped: `git status") for ln in lines), lines

    def test_work_the_final_checkpoint_missed_is_never_moved_aside_and_landed(
        self, target_repo, driver_configured, monkeypatch,
    ):
        """commit_checkpoint reports a failed commit only on stdout (#3810).
        The finish used to move what it left untracked into runs-kept, after
        which the tree read clean and the branch went out without it."""
        from assemblyzero.workflows.testing import checkpoints
        from tools.run_implement_from_lld import finish_standalone_run

        wt = _worktree_with_work(target_repo)
        monkeypatch.setattr(checkpoints, "commit_checkpoint", lambda *a, **k: False)
        land = _Landed()
        monkeypatch.setattr(merge_driver, "land", land)

        finished, lines = finish_standalone_run(target_repo, wt, 42, "main", mock=False)

        assert not finished
        assert not land.calls
        assert (wt / "report.md").read_text(encoding="utf-8") == "late\n"
        assert not (target_repo / "data" / "runs-kept").exists()
        assert any("did not commit everything" in ln and "report.md" in ln for ln in lines), lines

    def test_the_checkpoints_own_exclusions_do_not_stop_the_finish(
        self, target_repo, driver_configured, monkeypatch,
    ):
        from tools.run_implement_from_lld import finish_standalone_run

        wt = _worktree_with_work(target_repo)
        (wt / ".assemblyzero").mkdir()
        (wt / ".assemblyzero" / "state.json").write_text("{}\n", encoding="utf-8")
        land = _Landed()
        monkeypatch.setattr(merge_driver, "land", land)

        finished, lines = finish_standalone_run(target_repo, wt, 42, "main", mock=False)

        assert finished, lines
        assert len(land.calls) == 1
        assert list((target_repo / "data" / "runs-kept").rglob("state.json"))

    def test_a_detached_head_in_a_real_run_is_a_stop_not_a_finish(
        self, target_repo, driver_configured, monkeypatch,
    ):
        """Ledger 0908, line 353: an empty branch name skipped the push, removed
        the worktree and returned finished=True."""
        from tools.run_implement_from_lld import finish_standalone_run

        wt = _worktree_with_work(target_repo)
        _git(wt, "add", "report.md")
        _git(wt, "commit", "-qm", "late")
        _git(wt, "switch", "-q", "--detach")
        land = _Landed()
        monkeypatch.setattr(merge_driver, "land", land)

        finished, lines = finish_standalone_run(target_repo, wt, 42, "main", mock=False)

        assert not finished
        assert wt.exists()
        assert not land.calls
        assert any("no branch" in ln for ln in lines), lines


# --- T2: the start-up refusal ------------------------------------------------


def _args(**overrides):
    base = {"dry_run": False, "mock": False, "scaffold_only": False, "no_worktree": False}
    base.update(overrides)
    return SimpleNamespace(**base)


class TestTheDriverIsCheckedAtStart:
    def test_a_real_run_needs_the_driver(self, monkeypatch):
        from tools.run_implement_from_lld import landing_preflight

        monkeypatch.delenv(merge_driver.DRIVER_ENV, raising=False)
        reason = landing_preflight(_args())
        assert reason and "AZ_MERGE_DRIVER is not set" in reason

    @pytest.mark.parametrize("flag", ["dry_run", "mock", "scaffold_only", "no_worktree"])
    def test_a_run_that_lands_nothing_does_not(self, flag, monkeypatch):
        from tools.run_implement_from_lld import landing_preflight

        monkeypatch.delenv(merge_driver.DRIVER_ENV, raising=False)
        assert landing_preflight(_args(**{flag: True})) is None

    def test_main_refuses_before_any_graph_is_built(
        self, target_repo, tmp_path, monkeypatch, operator_alerts, capsys,
    ):
        from tools import run_implement_from_lld as tool

        monkeypatch.delenv(merge_driver.DRIVER_ENV, raising=False)
        argv = ["prog", "--issue", "42", "--repo", str(target_repo), "--auto",
                "--db-path", str(tmp_path / "ckpt.db")]
        with patch("sys.argv", argv), \
             patch("assemblyzero.workflows.testing.build_testing_workflow") as build, \
             patch("assemblyzero.core.resume_contract.check_and_consume") as consume, \
             pytest.raises(SystemExit) as exc:
            tool.main()

        assert exc.value.code not in (0, None)
        build.assert_not_called()
        consume.assert_not_called()
        assert not (target_repo.parent / "target-42").exists()
        assert "AZ_MERGE_DRIVER is not set" in capsys.readouterr().err
        assert len(operator_alerts) == 1
        assert "AZ_MERGE_DRIVER is not set" in operator_alerts[0]["cause"]


# --- The run's outcome, driven through main() with a stand-in graph ----------


class _FakeApp:
    def __init__(self, values, events, write_work):
        self._values = values
        self._events = events
        self._write_work = write_work

    def stream(self, initial_state, config):
        if self._write_work:
            wt = Path(initial_state["worktree_path"])
            (wt / "impl.py").write_text("x = 1\n", encoding="utf-8")
        for event in self._events:
            if isinstance(event, BaseException):
                raise event
            yield event

    def get_state(self, config):
        return SimpleNamespace(values=self._values)


class _FakeWorkflow:
    def __init__(self, values, events=(), write_work=True):
        self._app = _FakeApp(values, list(events), write_work)

    def compile(self, checkpointer=None):
        return self._app


def _run_main(target: Path, tmp_path: Path, workflow) -> tuple[int, str]:
    from tools import run_implement_from_lld as tool

    argv = ["prog", "--issue", "42", "--repo", str(target), "--auto",
            "--db-path", str(tmp_path / "ckpt.db")]
    out = io.StringIO()
    with patch("sys.argv", argv), redirect_stdout(out), \
         patch("assemblyzero.workflows.testing.build_testing_workflow", return_value=workflow):
        try:
            rc = tool.main()
        except SystemExit as exc:
            rc = exc.code
    return rc, out.getvalue()


COMPLETED = {"issue_number": 42, "workflow_status": "completed", "error_message": ""}


class TestTheRunsOutcome:
    def test_a_completed_run_lands_and_exits_zero(
        self, target_repo, tmp_path, driver_configured, monkeypatch, operator_alerts,
    ):
        land = _Landed()
        monkeypatch.setattr(merge_driver, "land", land)

        rc, out = _run_main(target_repo, tmp_path, _FakeWorkflow(COMPLETED))

        assert rc == 0, out
        assert len(land.calls) == 1, out
        assert "Status: SUCCESS" in out
        assert not operator_alerts

    def test_a_driver_refusal_halts_alerts_and_exits_one(
        self, target_repo, tmp_path, driver_configured, monkeypatch, operator_alerts,
    ):
        """T3: the driver's output reaches the HALT node's alert; the worktree
        and the branch are kept for the driver's route."""
        monkeypatch.setattr(merge_driver, "land", _Refused())

        rc, out = _run_main(target_repo, tmp_path, _FakeWorkflow(COMPLETED))

        assert rc == 1, out
        assert "Status: SUCCESS" not in out
        assert (target_repo.parent / "target-42").exists()
        assert "42-implementation" in _git(target_repo, "branch", "--list").stdout
        halts = [a for a in operator_alerts if "HALT" in a["where"]]
        assert halts, operator_alerts
        assert "stage=checks_failed" in halts[0]["cause"]
        status = target_repo / "data" / "speedrun" / "runs" / ".implement-status-42.json"
        assert '"FAILED"' in status.read_text(encoding="utf-8")

    def test_an_end_short_of_finalize_is_a_failure_and_lands_nothing(
        self, target_repo, tmp_path, driver_configured, monkeypatch, operator_alerts,
    ):
        """The testing graph has routes to END with no error_message (an
        iteration cap, a spent budget). Only N7 sets workflow_status."""
        land = _Landed()
        monkeypatch.setattr(merge_driver, "land", land)
        capped = {"issue_number": 42, "error_message": "", "next_node": "N4_implement_code"}

        rc, out = _run_main(target_repo, tmp_path, _FakeWorkflow(capped))

        assert rc == 1, out
        assert not land.calls
        assert "Status: SUCCESS" not in out
        assert (target_repo.parent / "target-42").exists()
        assert any("N7" in a["cause"] for a in operator_alerts), operator_alerts

    def test_no_final_state_is_a_failure(
        self, target_repo, tmp_path, driver_configured, monkeypatch, operator_alerts,
    ):
        """Ledger 0908, line 1484: recorded a halt, then exited 0."""
        monkeypatch.setattr(merge_driver, "land", _Landed())

        rc, out = _run_main(target_repo, tmp_path, _FakeWorkflow({}))

        assert rc == 1, out
        assert any("no final state" in a["cause"] for a in operator_alerts), operator_alerts

    def test_an_unexpected_exception_alerts(
        self, target_repo, tmp_path, driver_configured, monkeypatch, operator_alerts,
    ):
        """Ledger 0908, line 1458: [FATAL] on stdout, return 1, no alert."""
        monkeypatch.setattr(merge_driver, "land", _Landed())
        workflow = _FakeWorkflow(COMPLETED, events=[RuntimeError("boom")])

        rc, out = _run_main(target_repo, tmp_path, workflow)

        assert rc == 1, out
        assert any("RuntimeError: boom" in a["cause"] for a in operator_alerts), operator_alerts

    def test_an_error_that_bypassed_halt_alerts_here(
        self, target_repo, tmp_path, driver_configured, monkeypatch, operator_alerts, capsys,
    ):
        """Ledger 0908, lines 1344 and 1377: a node's error went to stdout and
        the ended run alerted no one unless HALT had run."""
        monkeypatch.setattr(merge_driver, "land", _Landed())
        ended = {"issue_number": 42, "error_message": "N3 could not run pytest"}
        workflow = _FakeWorkflow(ended, events=[{"N3_verify_red": ended}])

        rc, out = _run_main(target_repo, tmp_path, workflow)

        assert rc == 1, out
        assert "[ERROR] N3 could not run pytest" in capsys.readouterr().err
        assert any("N3 could not run pytest" in a["cause"] for a in operator_alerts)

    def test_an_error_that_went_through_halt_is_not_alerted_twice(
        self, target_repo, tmp_path, driver_configured, monkeypatch, operator_alerts,
    ):
        monkeypatch.setattr(merge_driver, "land", _Landed())
        halted = {"issue_number": 42, "error_message": "N3 failed",
                  "workflow_status": "halted"}

        rc, out = _run_main(target_repo, tmp_path, _FakeWorkflow(halted))

        assert rc == 1, out
        assert not operator_alerts
