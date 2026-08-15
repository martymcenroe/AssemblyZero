"""The launcher's half of the emergency stop (#2422).

The module-level fixtures in `test_speedrun_emergency_stop.py` pin the stop
mechanism. These pin the launcher wiring: that `--kill` reaches the process
tree and stamps the RUN's own events log, that a killed roll is reported as a
verdict rather than a failure, and -- the part boostgauge #1 is sitting in
right now -- that the next launch RESUMES a run that was stopped mid-stage
instead of redrawing everything it had already paid for.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.speedrun.emergency_stop import KILL_EXIT_CODE, KILLED_MARKER

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import speedrun_roll as sr  # noqa: E402


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "boostgauge"
    (r / ".git").mkdir(parents=True)
    (r / "data" / "speedrun").mkdir(parents=True)
    return r


@pytest.fixture
def log_dir(repo):
    d = repo / "data" / "speedrun" / "runs"
    d.mkdir(parents=True)
    return d


# ---------------------------------------------------------------------------
# Part 1: the kill command stamps the RUN's log, not just the wrapper's
# ---------------------------------------------------------------------------


class TestKillCommand:
    def test_stamps_killed_by_operator_into_the_runs_own_events_log(
        self, repo, log_dir
    ):
        """`--detach-stop` wrote only `detach-events.log`, which is the
        wrapper's record. A postmortem reads the run's log, and an ordered
        stop that never appears there is indistinguishable from a crash."""
        run_log = log_dir / "run-issue1-132000-events.log"
        run_log.write_text("13:20:00 START issue=#1\n", encoding="utf-8")
        sr.pid_file(log_dir).write_text("48324", encoding="utf-8")

        with patch.object(sr, "is_live_python", return_value=True), \
             patch.object(sr, "tree_kill", return_value=(True, "")), \
             patch.object(sr, "_run"):
            code = sr.kill_roll(repo, log_dir, 1)

        assert code == 0
        assert KILLED_MARKER in run_log.read_text(encoding="utf-8")

    def test_stamp_names_the_pid_that_was_killed(self, repo, log_dir):
        run_log = log_dir / "run-issue1-132000-events.log"
        run_log.write_text("", encoding="utf-8")
        sr.pid_file(log_dir).write_text("48324", encoding="utf-8")

        with patch.object(sr, "is_live_python", return_value=True), \
             patch.object(sr, "tree_kill", return_value=(True, "")), \
             patch.object(sr, "_run"):
            sr.kill_roll(repo, log_dir, 1)

        assert "48324" in run_log.read_text(encoding="utf-8")

    def test_another_issues_log_is_not_stamped(self, repo, log_dir):
        mine = log_dir / "run-issue1-132000-events.log"
        theirs = log_dir / "run-issue2-140000-events.log"
        mine.write_text("", encoding="utf-8")
        theirs.write_text("", encoding="utf-8")
        sr.pid_file(log_dir).write_text("48324", encoding="utf-8")

        with patch.object(sr, "is_live_python", return_value=True), \
             patch.object(sr, "tree_kill", return_value=(True, "")), \
             patch.object(sr, "_run"):
            sr.kill_roll(repo, log_dir, 1)

        assert KILLED_MARKER in mine.read_text(encoding="utf-8")
        assert KILLED_MARKER not in theirs.read_text(encoding="utf-8")

    def test_a_stale_pid_is_not_killed(self, repo, log_dir):
        """Windows recycles pids. A stale file plus an unlucky reuse would
        tree-kill somebody else's work on a shared machine."""
        sr.pid_file(log_dir).write_text("48324", encoding="utf-8")
        killed = []

        with patch.object(sr, "is_live_python", return_value=False), \
             patch.object(sr, "tree_kill", side_effect=lambda p: killed.append(p)), \
             patch.object(sr, "_run"):
            code = sr.kill_roll(repo, log_dir, 1)

        assert code == 0
        assert killed == []

    def test_kill_clears_the_stop_file(self, repo, log_dir):
        """A stop file that outlived its run would stop the NEXT launch, which
        the operator would experience as a launcher that refuses to start."""
        stop = repo / "data" / "speedrun" / "KILL-1"
        stop.write_text("", encoding="utf-8")

        with patch.object(sr, "_run"):
            sr.kill_roll(repo, log_dir, 1)

        assert not stop.exists()

    def test_kill_without_a_running_roll_is_not_an_error(self, repo, log_dir):
        with patch.object(sr, "_run"):
            assert sr.kill_roll(repo, log_dir, 1) == 0

    def test_kill_is_dispatched_before_any_gate(self, repo, log_dir):
        """An emergency stop a gate could refuse is not an emergency stop."""
        called = {}

        def _kill(repo_root, ld, issue):
            called["issue"] = issue
            return 0

        with patch.object(sr, "kill_roll", side_effect=_kill), \
             patch.object(sr, "check_assemblyzero_tree") as tree, \
             patch.object(sr, "check_box_health") as health:
            code = sr.main(["--repo", str(repo), "--kill", "--issue", "1"])

        assert code == 0
        assert called["issue"] == 1
        # Neither gate was consulted -- the stop does not depend on a clean tree.
        tree.assert_not_called()
        health.assert_not_called()


# ---------------------------------------------------------------------------
# Part 4: the next launch RESUMES a run that was stopped mid-stage
# ---------------------------------------------------------------------------


def _state(tmp_path, **overrides) -> Path:
    """boostgauge #1's state as measured after the 2026-08-15 kill.

    spec passed, impl was in flight, and impl has NO stage_results entry --
    because an ordered stop never gets to record one.
    """
    data = {
        "issue_number": 1,
        "current_stage": "impl",
        "resumed_from": "spec",
        "target_repo": str(tmp_path / "boostgauge"),
        "base_branch": "hardening-run-17",
        "lld_path": str(tmp_path / "boostgauge" / "docs" / "lld" / "LLD-001.md"),
        "spec_path": str(tmp_path / "boostgauge" / "docs" / "lld" / "spec-0001.md"),
        "stage_results": {
            "triage": {"status": "skipped", "error_message": ""},
            "lld": {"status": "passed", "error_message": ""},
            "spec": {"status": "passed", "error_message": ""},
        },
        "started_at": "2026-08-15T16:42:31+00:00",
        "completed_at": "",
    }
    data.update(overrides)
    path = tmp_path / "1.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class _Log:
    def __init__(self):
        self.lines = []

    def write(self, message):
        self.lines.append(message)


@pytest.fixture
def resumable(tmp_path, repo):
    """Everything resume_plan checks, held true except the stage selection."""
    state = _state(tmp_path)
    with patch.object(sr, "_orchestrator_state_path", return_value=state), \
         patch.object(sr, "resolve_attempt_branch", return_value="hardening-run-17"), \
         patch.object(sr, "_open_lld_pr_exists", return_value=True), \
         patch.object(sr, "draft_is_stale", return_value=False), \
         patch.object(sr, "_restore_artifact", return_value=True):
        yield state


class TestKilledRunResumes:
    def test_a_run_stopped_mid_impl_resumes_from_impl(self, resumable, repo):
        """The live defect: `resume_plan` chose the stage by scanning for a
        FAILED status. A killed run has none, so it matched nothing, returned
        None, and the next launch redrew the LLD and the spec both."""
        log = _Log()
        assert sr.resume_plan(Path("."), repo, 1, log) == "impl"

    def test_the_log_says_it_was_stopped_rather_than_failed(self, resumable, repo):
        log = _Log()
        sr.resume_plan(Path("."), repo, 1, log)
        assert any("stopped mid-stage" in line for line in log.lines)

    def test_a_failed_stage_still_wins_over_the_in_flight_one(
        self, tmp_path, repo
    ):
        """The pre-existing path must not change: a recorded failure is the
        stage to resume from, whatever `current_stage` happens to say."""
        state = _state(
            tmp_path,
            stage_results={
                "triage": {"status": "skipped", "error_message": ""},
                "lld": {"status": "passed", "error_message": ""},
                "spec": {"status": "failed", "error_message": "cap"},
            },
        )
        log = _Log()
        with patch.object(sr, "_orchestrator_state_path", return_value=state), \
             patch.object(sr, "resolve_attempt_branch", return_value="hardening-run-17"), \
             patch.object(sr, "_open_lld_pr_exists", return_value=True), \
             patch.object(sr, "draft_is_stale", return_value=False), \
             patch.object(sr, "_restore_artifact", return_value=True):
            assert sr.resume_plan(Path("."), repo, 1, log) == "spec"

    def test_a_completed_run_is_not_resumed(self, tmp_path, repo):
        """`completed_at` means finished, not halted. Without this guard a
        successful roll would look resumable forever."""
        state = _state(tmp_path, completed_at="2026-08-15T19:00:00+00:00")
        log = _Log()
        with patch.object(sr, "_orchestrator_state_path", return_value=state), \
             patch.object(sr, "resolve_attempt_branch", return_value="hardening-run-17"), \
             patch.object(sr, "_open_lld_pr_exists", return_value=True), \
             patch.object(sr, "draft_is_stale", return_value=False), \
             patch.object(sr, "_restore_artifact", return_value=True):
            assert sr.resume_plan(Path("."), repo, 1, log) is None

    def test_a_gap_before_the_in_flight_stage_is_not_resumed(
        self, tmp_path, repo
    ):
        """If an earlier stage never passed, the in-flight stage has an input
        nobody produced. Resuming into that is worse than redrawing."""
        state = _state(
            tmp_path,
            stage_results={
                "triage": {"status": "skipped", "error_message": ""},
                "lld": {"status": "passed", "error_message": ""},
                # spec never ran at all
            },
        )
        log = _Log()
        with patch.object(sr, "_orchestrator_state_path", return_value=state), \
             patch.object(sr, "resolve_attempt_branch", return_value="hardening-run-17"), \
             patch.object(sr, "_open_lld_pr_exists", return_value=True), \
             patch.object(sr, "draft_is_stale", return_value=False), \
             patch.object(sr, "_restore_artifact", return_value=True):
            assert sr.resume_plan(Path("."), repo, 1, log) is None

    def test_an_unresumable_in_flight_stage_is_declined(self, tmp_path, repo):
        """`lld` is not in RESUMABLE_STAGES; being mid-flight does not make
        it one."""
        state = _state(
            tmp_path,
            current_stage="lld",
            stage_results={"triage": {"status": "skipped", "error_message": ""}},
        )
        log = _Log()
        with patch.object(sr, "_orchestrator_state_path", return_value=state), \
             patch.object(sr, "resolve_attempt_branch", return_value="hardening-run-17"), \
             patch.object(sr, "_open_lld_pr_exists", return_value=True), \
             patch.object(sr, "draft_is_stale", return_value=False), \
             patch.object(sr, "_restore_artifact", return_value=True):
            assert sr.resume_plan(Path("."), repo, 1, log) is None


class TestHaltedStageUnit:
    """`_halted_stage` in isolation -- the guards are the whole point."""

    def test_in_flight_stage_is_returned(self):
        results = {
            "triage": {"status": "skipped"},
            "lld": {"status": "passed"},
            "spec": {"status": "passed"},
        }
        data = {"current_stage": "impl", "completed_at": ""}
        assert sr._halted_stage(data, results) == "impl"

    def test_finished_current_stage_is_not_in_flight(self):
        results = {
            "triage": {"status": "skipped"},
            "lld": {"status": "passed"},
            "spec": {"status": "passed"},
        }
        data = {"current_stage": "spec", "completed_at": ""}
        assert sr._halted_stage(data, results) is None

    def test_an_unrecorded_earlier_stage_is_a_gap(self):
        """Conservative by design: resume is an optimization, fresh is always
        correct, so an unexplained hole declines rather than guessing."""
        results = {"lld": {"status": "passed"}, "spec": {"status": "passed"}}
        data = {"current_stage": "impl", "completed_at": ""}
        assert sr._halted_stage(data, results) is None

    def test_unknown_stage_name_is_declined(self):
        data = {"current_stage": "nonsense", "completed_at": ""}
        assert sr._halted_stage(data, {}) is None

    def test_missing_current_stage_is_declined(self):
        assert sr._halted_stage({"completed_at": ""}, {}) is None


# ---------------------------------------------------------------------------
# The verdict
# ---------------------------------------------------------------------------


class TestKilledVerdictRendering:
    def test_a_kill_is_not_rendered_as_a_failure(self, repo, capsys):
        with patch.object(sr, "_requirements_unverified_lines", return_value=[]):
            sr._render_verdict(
                repo, requested=[1], rolled=[], blocked=[], stopped_at=1,
                code=KILL_EXIT_CODE,
            )
        out = capsys.readouterr().out
        assert "STOPPED BY OPERATOR" in out
        assert "FAILED" not in out
        assert "exhausting" not in out

    def test_the_verdict_promises_the_resume(self, repo, capsys):
        with patch.object(sr, "_requirements_unverified_lines", return_value=[]):
            sr._render_verdict(
                repo, requested=[1], rolled=[], blocked=[], stopped_at=1,
                code=KILL_EXIT_CODE,
            )
        assert "resumes" in capsys.readouterr().out

    def test_an_ordinary_failure_still_reads_as_a_failure(self, repo, capsys):
        """The kill branch must not swallow real failures."""
        with patch.object(sr, "_requirements_unverified_lines", return_value=[]):
            sr._render_verdict(
                repo, requested=[1], rolled=[], blocked=[], stopped_at=1, code=1,
            )
        assert "ROLL FAILED" in capsys.readouterr().out
