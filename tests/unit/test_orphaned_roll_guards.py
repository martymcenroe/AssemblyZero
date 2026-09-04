"""Two guards for a roll whose wrapper died and whose run did not (#2510).

Three detached rolls in ten days had their wrapper killed while the
orchestrator carried on: 2026-08-24 at 00:00:25, 2026-09-02 at 17:28:45, and
2026-09-02 at 19:20:13. Each time the scheduled task reported exit 1, and each
time the follower read that state and announced `The roll is done: FAILED`
while the run was mid-stage.

On the third, an operator believed the verdict and ran `speedrun_reset.py`. It
closed the run's LLD PR, removed its worktree, deleted branch `4-lld` locally
and on origin, and archived `docs/lineage/active/4-implspec` and `4-lld` out
from under a process that was still writing into them. The run happened to be
in its ninth of nine review rounds with no path to approval, so nothing that
could have shipped was lost. That is luck.

The two guards are independent on purpose, because the failure needed both to
line up: the follower has to stop lying, AND the reset has to refuse even when
something lies to it.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import speedrun_reset  # noqa: E402
import speedrun_roll  # noqa: E402

from assemblyzero.workflows.orchestrator import resume  # noqa: E402


# ---------------------------------------------------------------------------
# Guard 1: the follower stops calling a live run done
# ---------------------------------------------------------------------------


def _log(dir_: Path, name: str, age_seconds: float, *, now: float = 1_000_000.0):
    path = dir_ / name
    path.write_text("alive\n", encoding="utf-8")
    os.utime(path, (now - age_seconds, now - age_seconds))
    return path


NOW = 1_000_000.0


class TestRunStillWriting:
    def test_a_fresh_heartbeat_means_the_run_is_alive(self, tmp_path):
        _log(tmp_path, "run-issue4-183941-heartbeat.log", 5)
        still, why = speedrun_roll.run_still_writing(tmp_path, now=NOW)
        assert still is True
        assert "heartbeat" in why and "5s ago" in why

    def test_a_growing_run_log_means_the_run_is_alive(self, tmp_path):
        """The heartbeat is the wrapper's; the run log is the orchestrator's.
        In all three incidents the heartbeat stopped and the log kept growing,
        so the log alone has to be enough."""
        _log(tmp_path, "run-issue4-183941-heartbeat.log", 600)
        _log(tmp_path, "run-issue4-183941.log", 10)
        still, why = speedrun_roll.run_still_writing(tmp_path, now=NOW)
        assert still is True
        assert "run-issue4-183941.log" in why

    def test_a_stale_heartbeat_alone_is_not_life(self, tmp_path):
        _log(tmp_path, "run-issue4-183941-heartbeat.log", 600)
        assert speedrun_roll.run_still_writing(tmp_path, now=NOW)[0] is False

    def test_an_empty_directory_is_not_life(self, tmp_path):
        assert speedrun_roll.run_still_writing(tmp_path, now=NOW) == (False, "")

    def test_the_events_log_does_not_count_as_life(self, tmp_path):
        """The events log gets its LAUNCH line at the start and then nothing
        until the wrapper writes EXIT -- which in all three incidents it never
        did. Counting it would read the launch as a sign of life for a minute
        after the wrapper was already dead."""
        _log(tmp_path, "run-issue4-183941-events.log", 5)
        assert speedrun_roll.run_still_writing(tmp_path, now=NOW)[0] is False

    def test_the_boundary_is_four_missed_beats(self, tmp_path):
        """15-second cadence, so 60s is four missed beats. Pinned because the
        number is the whole judgement: too small and jitter reads as death,
        too large and the operator waits on a finished run."""
        assert speedrun_roll.HEARTBEAT_FRESH_SECONDS == 60
        _log(tmp_path, "run-issue4-183941.log", 59)
        assert speedrun_roll.run_still_writing(tmp_path, now=NOW)[0] is True
        _log(tmp_path, "run-issue4-183941.log", 60)
        assert speedrun_roll.run_still_writing(tmp_path, now=NOW)[0] is False

    def test_a_log_that_says_how_it_ended_has_ended(self, tmp_path):
        """The cost of getting this wrong falls on every roll, not the rare
        one: a normal run writes its closing banner seconds before the task
        flips to Ready, so freshness alone would hold the follower silent for a
        minute after every success."""
        path = _log(tmp_path, "run-issue4-183941.log", 2)
        path.write_text(
            "[ORCHESTRATOR] All stages passed.\n", encoding="utf-8"
        )
        os.utime(path, (NOW - 2, NOW - 2))
        assert speedrun_roll.run_still_writing(tmp_path, now=NOW)[0] is False

    def test_a_failure_banner_also_ends_it(self, tmp_path):
        path = _log(tmp_path, "run-issue4-183941.log", 2)
        path.write_text(
            "  ORCHESTRATION FAILED at stage: spec\n", encoding="utf-8"
        )
        os.utime(path, (NOW - 2, NOW - 2))
        assert speedrun_roll.run_still_writing(tmp_path, now=NOW)[0] is False

    def test_a_fresh_log_with_no_banner_is_the_orphan(self, tmp_path):
        """The shape of all three incidents: the run is mid-stage, so it has
        written recently and has not said how it ended."""
        path = _log(tmp_path, "run-issue4-183941.log", 2)
        path.write_text(
            "NODE [7/11] generate draft -- the drafter writes it.\n",
            encoding="utf-8",
        )
        os.utime(path, (NOW - 2, NOW - 2))
        assert speedrun_roll.run_still_writing(tmp_path, now=NOW)[0] is True

    def test_an_unstattable_log_is_not_treated_as_life(self, tmp_path, monkeypatch):
        """Fail-open toward the old behaviour: without evidence of life the
        caller prints the verdict it printed before this existed. The guard can
        only be lost, never invented."""
        _log(tmp_path, "run-issue4-183941.log", 1)

        def _boom(self, *a, **k):
            raise OSError("gone")

        monkeypatch.setattr(Path, "stat", _boom)
        assert speedrun_roll.run_still_writing(tmp_path, now=NOW)[0] is False


class TestTheFollowerDoesNotCallAnOrphanDone:
    """The whole loop, driven the way the three incidents drove it: the task
    flips out of Running while the run log keeps growing."""

    def _runs(self, tmp_path: Path) -> Path:
        runs = tmp_path / "runs"
        runs.mkdir()
        (runs / "detached-launcher.log").write_bytes(b"")
        return runs

    def test_it_says_the_wrapper_ended_and_keeps_following(
        self, tmp_path, capsys, monkeypatch
    ):
        runs = self._runs(tmp_path)
        roll = runs / "run-issue4-183941.log"
        roll.write_bytes(b"")

        def _orphan():
            with roll.open("ab") as fh:
                fh.write(b"NODE [7/11] generate draft\n")
            return "Ready"

        def _finish():
            with roll.open("ab") as fh:
                fh.write(b"[ORCHESTRATOR] All stages passed.\n")
            return "Ready"

        statuses = iter([lambda: "Running", _orphan, _finish])
        monkeypatch.setattr(speedrun_roll, "_task_status", lambda: next(statuses)())
        monkeypatch.setattr(speedrun_roll, "_task_last_result", lambda: 1)
        monkeypatch.setattr(speedrun_roll.time, "sleep", lambda s: None)
        monkeypatch.setattr(speedrun_roll, "_poll_view_keys", lambda v: None)

        speedrun_roll.follow_roll(runs)
        out = capsys.readouterr().out

        assert "Wrapper ended at" in out
        assert "the run is still writing" in out
        assert "Do NOT reset or relaunch" in out
        assert out.index("Wrapper ended at") < out.index("The roll is done")

    def test_the_final_verdict_says_whose_exit_code_it_is(
        self, tmp_path, capsys, monkeypatch
    ):
        """The exit code belongs to the wrapper, which was killed. Printing it
        as the roll's verdict is what said FAILED about a run two stages from a
        PR."""
        runs = self._runs(tmp_path)
        roll = runs / "run-issue4-183941.log"
        roll.write_bytes(b"")

        def _orphan():
            with roll.open("ab") as fh:
                fh.write(b"NODE [7/11] generate draft\n")
            return "Ready"

        def _finish():
            with roll.open("ab") as fh:
                fh.write(b"[ORCHESTRATOR] All stages passed.\n")
            return "Ready"

        statuses = iter([lambda: "Running", _orphan, _finish])
        monkeypatch.setattr(speedrun_roll, "_task_status", lambda: next(statuses)())
        monkeypatch.setattr(speedrun_roll, "_task_last_result", lambda: 1)
        monkeypatch.setattr(speedrun_roll.time, "sleep", lambda s: None)
        monkeypatch.setattr(speedrun_roll, "_poll_view_keys", lambda v: None)

        speedrun_roll.follow_roll(runs)
        out = capsys.readouterr().out
        assert "the exit code above is the wrapper's and not the run's" in out

    def test_a_clean_finish_signs_off_at_once(
        self, tmp_path, capsys, monkeypatch
    ):
        """The control, and the one that matters most for cost: a roll that
        ends normally must not be held for a minute by a guard meant for
        orphans."""
        runs = self._runs(tmp_path)
        roll = runs / "run-issue4-183941.log"
        roll.write_bytes(b"")

        def _finish():
            with roll.open("ab") as fh:
                fh.write(b"[ORCHESTRATOR] All stages passed.\n")
            return "Ready"

        statuses = iter([lambda: "Running", _finish])
        monkeypatch.setattr(speedrun_roll, "_task_status", lambda: next(statuses)())
        monkeypatch.setattr(speedrun_roll, "_task_last_result", lambda: 0)
        monkeypatch.setattr(speedrun_roll.time, "sleep", lambda s: None)
        monkeypatch.setattr(speedrun_roll, "_poll_view_keys", lambda v: None)

        assert speedrun_roll.follow_roll(runs) == 0
        out = capsys.readouterr().out
        assert "The roll is done: SUCCEEDED" in out
        assert "Wrapper ended at" not in out


# ---------------------------------------------------------------------------
# Guard 2: the reset refuses under a live orchestrator
# ---------------------------------------------------------------------------


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A repo whose lock directory is where the orchestrator would write it."""
    root = tmp_path / "target"
    (root / ".assemblyzero" / "orchestrator" / "locks").mkdir(parents=True)
    monkeypatch.setattr(resume, "LOCK_DIR", Path(".assemblyzero/orchestrator/locks"))
    return root


def _lock(repo: Path, issue: int, pid: int) -> Path:
    path = repo / ".assemblyzero" / "orchestrator" / "locks" / f"{issue}.lock"
    path.write_text(json.dumps({"pid": pid, "hostname": "h"}), encoding="utf-8")
    return path


class TestTheResetRefusesUnderALiveOrchestrator:
    def test_a_live_lock_raises_rather_than_warning(self, repo, monkeypatch):
        """`raise`, not `print`. A warning is what the operator read past on
        2026-09-02; a reset that can run under a live orchestrator is the same
        class as a `git clean` in someone else's checkout."""
        _lock(repo, 4, 36848)
        monkeypatch.setattr(resume, "_is_pid_alive", lambda pid: pid == 36848)
        with pytest.raises(speedrun_reset.LiveOrchestratorError) as caught:
            speedrun_reset.refuse_if_orchestrator_is_live(repo, 4)
        assert "36848" in str(caught.value)
        assert "#4" in str(caught.value)

    def test_a_dead_pid_does_not_block_a_legitimate_reset(self, repo, monkeypatch):
        """A stale lock is the ordinary case after any crash, and refusing on
        one would make the tool useless exactly when it is needed."""
        _lock(repo, 4, 26780)
        monkeypatch.setattr(resume, "_is_pid_alive", lambda pid: False)
        speedrun_reset.refuse_if_orchestrator_is_live(repo, 4)

    def test_no_lock_at_all_does_not_block(self, repo):
        speedrun_reset.refuse_if_orchestrator_is_live(repo, 4)

    def test_a_corrupt_lock_does_not_block(self, repo):
        path = repo / ".assemblyzero" / "orchestrator" / "locks" / "4.lock"
        path.write_text("{not json", encoding="utf-8")
        speedrun_reset.refuse_if_orchestrator_is_live(repo, 4)

    def test_another_issues_live_lock_does_not_block_this_one(
        self, repo, monkeypatch
    ):
        _lock(repo, 331, 36848)
        monkeypatch.setattr(resume, "_is_pid_alive", lambda pid: True)
        speedrun_reset.refuse_if_orchestrator_is_live(repo, 4)

    def test_the_lock_is_read_from_the_target_repo_not_the_cwd(
        self, repo, monkeypatch, tmp_path
    ):
        """`LOCK_DIR` is repo-relative, and the reset is invoked from wherever
        the operator happens to be. Reading it from the cwd would look in
        AssemblyZero's own lock directory and find nothing, every time."""
        _lock(repo, 4, 36848)
        monkeypatch.setattr(resume, "_is_pid_alive", lambda pid: True)
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)
        with pytest.raises(speedrun_reset.LiveOrchestratorError):
            speedrun_reset.refuse_if_orchestrator_is_live(repo, 4)

    def test_the_working_directory_is_restored_after_a_refusal(
        self, repo, monkeypatch, tmp_path
    ):
        _lock(repo, 4, 36848)
        monkeypatch.setattr(resume, "_is_pid_alive", lambda pid: True)
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)
        with pytest.raises(speedrun_reset.LiveOrchestratorError):
            speedrun_reset.refuse_if_orchestrator_is_live(repo, 4)
        assert Path.cwd() == elsewhere.resolve()


class TestTheRefusalComesBeforeAnyWrite:
    def test_reset_one_issue_checks_before_it_pins(self, repo, monkeypatch):
        """The checkpoint pin is itself a write and everything after it is
        destructive, so the refusal has to precede the first step and not sit
        among them."""
        _lock(repo, 4, 36848)
        monkeypatch.setattr(resume, "_is_pid_alive", lambda pid: True)
        touched: list[str] = []
        for name in (
            "pin_checkpoint", "close_open_prs", "remove_worktree",
            "delete_local_branches", "delete_remote_branches",
            "archive_lineage_dirs", "relocate_lld_artifacts", "reopen_issue",
        ):
            monkeypatch.setattr(
                speedrun_reset, name,
                lambda *a, _n=name, **k: touched.append(_n),
            )
        with pytest.raises(speedrun_reset.LiveOrchestratorError):
            speedrun_reset.reset_one_issue(repo, "owner/repo", 4)
        assert touched == [], (
            f"the reset touched {touched} before refusing; on 2026-09-02 that "
            f"list was a closed PR and two deleted branches"
        )


class TestLiveOrchestratorPid:
    def test_it_reads_the_pid_the_lock_already_carried(self, repo, monkeypatch):
        _lock(repo, 4, 36848)
        monkeypatch.setattr(resume, "_is_pid_alive", lambda pid: True)
        monkeypatch.chdir(repo)
        assert resume.live_orchestrator_pid(4) == 36848

    def test_a_lock_with_no_pid_field_is_not_a_live_run(self, repo, monkeypatch):
        path = repo / ".assemblyzero" / "orchestrator" / "locks" / "4.lock"
        path.write_text(json.dumps({"hostname": "h"}), encoding="utf-8")
        monkeypatch.chdir(repo)
        assert resume.live_orchestrator_pid(4) is None
