"""#2831: a stop ends the scheduled task only when the task is this repo's roll.

The task name is machine-global -- one AZ-SpeedrunRoll -- so `schtasks /End`
by name ends whatever roll is live. On 2026-09-05 a unit test killing its own
tmp roll ended the operator's live run 13 that way (Task Scheduler: Last
Result 267014, "terminated by the user"), which is the #2510 wrapper death.
The tool now reads the task's own command line and ends it only when that
names the repository the stop was asked about.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import speedrun_roll as sr  # noqa: E402


class _Scheduler:
    """Stands in for _run: answers the verbose query, records every End."""

    def __init__(self, task_repo: str | None, query_ok: bool = True):
        self.task_repo = task_repo
        self.query_ok = query_ok
        self.calls: list[list[str]] = []

    def __call__(self, cmd, cwd=None):
        self.calls.append(list(cmd))
        if cmd[:2] == ["schtasks", "/Query"]:
            if not self.query_ok:
                return subprocess.CompletedProcess(cmd, 1, "", "ERROR: cannot query")
            body = ""
            if self.task_repo:
                body = (
                    "TaskName:      \\AZ-SpeedrunRoll\n"
                    f"Task To Run:   pythonw.exe speedrun_roll.py --repo {self.task_repo} "
                    "--issue 4 --log-dir x\n"
                )
            return subprocess.CompletedProcess(cmd, 0, body, "")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    def ends(self) -> list[list[str]]:
        return [c for c in self.calls if c[:2] == ["schtasks", "/End"]]


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "boostgauge"
    (r / "data" / "speedrun" / "runs").mkdir(parents=True)
    return r


@pytest.fixture
def log_dir(repo):
    return repo / "data" / "speedrun" / "runs"


class TestTheQuestion:
    def test_the_task_that_names_this_repo_is_ours(self, repo):
        sched = _Scheduler(task_repo=str(repo))
        with patch.object(sr, "_run", sched):
            assert sr._task_names_repo(repo) is True

    def test_a_task_that_names_another_repo_is_not(self, repo, tmp_path):
        other = tmp_path / "somewhere-else"
        sched = _Scheduler(task_repo=str(other))
        with patch.object(sr, "_run", sched):
            assert sr._task_names_repo(repo) is False

    def test_forward_and_back_slashes_are_the_same_path(self, repo):
        sched = _Scheduler(task_repo=str(repo).replace("\\", "/"))
        with patch.object(sr, "_run", sched):
            assert sr._task_names_repo(repo) is True

    def test_a_scheduler_that_cannot_say_is_unknown(self, repo):
        sched = _Scheduler(task_repo=str(repo), query_ok=False)
        with patch.object(sr, "_run", sched):
            assert sr._task_names_repo(repo) is None

    def test_a_query_with_no_task_to_run_line_is_unknown(self, repo):
        sched = _Scheduler(task_repo=None)
        with patch.object(sr, "_run", sched):
            assert sr._task_names_repo(repo) is None


class TestKillRoll:
    """The 2026-09-05 shape: a kill against a tmp repo while the live roll is
    another repository's. Nothing is ended."""

    def _kill(self, repo, log_dir, sched):
        with patch.object(sr, "_run", sched), \
                patch.object(sr.sys, "platform", "win32"), \
                patch.object(sr, "is_live_python", lambda pid: False):
            return sr.kill_roll(repo, log_dir, 1)

    def test_another_repos_task_is_left_running(self, repo, log_dir, tmp_path, capsys):
        live = tmp_path / "the-operators-live-roll"
        sched = _Scheduler(task_repo=str(live))
        assert self._kill(repo, log_dir, sched) == 0
        assert sched.ends() == [], sched.calls
        assert "another repository" in capsys.readouterr().out

    def test_our_own_task_is_ended(self, repo, log_dir, sched=None):
        sched = _Scheduler(task_repo=str(repo))
        assert self._kill(repo, log_dir, sched) == 0
        assert len(sched.ends()) == 1, sched.calls

    def test_an_unqueryable_scheduler_ends_nothing_and_says_so(self, repo, log_dir, capsys):
        sched = _Scheduler(task_repo=str(repo), query_ok=False)
        assert self._kill(repo, log_dir, sched) == 0
        assert sched.ends() == []
        assert "could not say" in capsys.readouterr().out


class TestStopDetached:
    def _stop(self, repo, log_dir, sched):
        with patch.object(sr, "_run", sched), \
                patch.object(sr.sys, "platform", "win32"), \
                patch.object(sr, "is_live_python", lambda pid: False):
            return sr.stop_detached(log_dir, repo_root=repo)

    def test_another_repos_task_is_left_running(self, repo, log_dir, tmp_path):
        sched = _Scheduler(task_repo=str(tmp_path / "live"))
        assert self._stop(repo, log_dir, sched) == 0
        assert sched.ends() == [], sched.calls

    def test_our_own_task_is_ended(self, repo, log_dir):
        sched = _Scheduler(task_repo=str(repo))
        assert self._stop(repo, log_dir, sched) == 0
        assert len(sched.ends()) == 1, sched.calls

    def test_the_repo_is_derived_from_the_log_dir_when_not_given(self, repo, log_dir):
        sched = _Scheduler(task_repo=str(repo))
        with patch.object(sr, "_run", sched), \
                patch.object(sr.sys, "platform", "win32"), \
                patch.object(sr, "is_live_python", lambda pid: False):
            assert sr.stop_detached(log_dir) == 0
        assert len(sched.ends()) == 1, sched.calls


class TestTheEndIsNeverByNameAlone:
    def test_no_end_without_a_preceding_query(self, repo, log_dir):
        """Pinned at the call order: every End is preceded by the query that
        justifies it."""
        sched = _Scheduler(task_repo=str(repo))
        with patch.object(sr, "_run", sched), \
                patch.object(sr.sys, "platform", "win32"), \
                patch.object(sr, "is_live_python", lambda pid: False):
            sr.kill_roll(repo, log_dir, 1)
            sr.stop_detached(log_dir, repo_root=repo)
        verbs = [c[1] for c in sched.calls if c[0] == "schtasks"]
        for i, verb in enumerate(verbs):
            if verb == "/End":
                assert verbs[i - 1] == "/Query", verbs
