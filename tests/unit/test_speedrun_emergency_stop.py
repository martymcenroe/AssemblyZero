"""The emergency stop must work when the operator has no prompt (#2422).

2026-08-15: a live roll had to be stopped and there was no operator interface
to stop it with. The console was streaming the detached run, the detach wrapper
is immune to casual interruption by design, and the kill was finally performed
by an agent reading a pid out of the events log and running a manual tree-kill
-- whose first attempt failed because Git Bash rewrote `taskkill /F` into a
drive path. The operator's stated fallback was rebooting the machine.

These pin the four parts of the interface, and the one that matters most is
the mid-call kill: a stop that only lands between stages would not have touched
the call that produced this issue, which had thirteen minutes left to run.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from assemblyzero.speedrun.emergency_stop import (
    KILL_EXIT_CODE,
    KILLED_MARKER,
    KillWatch,
    banner_lines,
    clear_kill_files,
    find_kill_file,
    kill_file_candidates,
    killed_verdict_lines,
    stop_command,
)

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "boostgauge"
    (r / "data" / "speedrun").mkdir(parents=True)
    return r


# ---------------------------------------------------------------------------
# Part 3: the kill file -- the promptless path
# ---------------------------------------------------------------------------


class TestKillFileDiscovery:
    def test_issue_scoped_file_is_found(self, repo):
        target = repo / "data" / "speedrun" / "KILL-1"
        target.write_text("", encoding="utf-8")
        assert find_kill_file(repo, 1) == target

    def test_bare_kill_stops_any_issue(self, repo):
        """Under stress the operator should not have to remember which issue
        is rolling. `touch data/speedrun/KILL` stops whatever is running."""
        target = repo / "data" / "speedrun" / "KILL"
        target.write_text("", encoding="utf-8")
        assert find_kill_file(repo, 7) == target

    def test_another_issues_file_does_not_stop_this_one(self, repo):
        """A machine running two campaigns must be able to stop one of them."""
        (repo / "data" / "speedrun" / "KILL-2").write_text("", encoding="utf-8")
        assert find_kill_file(repo, 1) is None

    def test_no_file_is_not_a_stop(self, repo):
        assert find_kill_file(repo, 1) is None

    def test_issue_scoped_name_is_offered_first(self, repo):
        names = [p.name for p in kill_file_candidates(repo, 1)]
        assert names == ["KILL-1", "KILL"]

    def test_clear_removes_both_forms(self, repo):
        base = repo / "data" / "speedrun"
        (base / "KILL-1").write_text("", encoding="utf-8")
        (base / "KILL").write_text("", encoding="utf-8")
        removed = clear_kill_files(repo, 1)
        assert len(removed) == 2
        assert find_kill_file(repo, 1) is None

    def test_clearing_nothing_is_not_an_error(self, repo):
        assert clear_kill_files(repo, 1) == []


class TestKillWatchMidCall:
    """The case the issue exists for: the child is RUNNING when the stop lands.

    A stop that only fires at a stage boundary is no use against a call with
    thirteen minutes left, which is exactly the call the operator could not
    stop. So these start a real child process, let it run, drop the stop file
    while it is still alive, and assert it died before finishing.
    """

    def _sleeper(self, seconds: float = 30) -> subprocess.Popen:
        """A real child that will outlive the test unless something kills it.

        `start_new_session` on POSIX is not incidental: it gives the child its
        OWN process group, which is both what the launcher does for the real
        pipeline and what makes the group-kill path safe to exercise. Without
        it the child shares this process's group, and a group kill would take
        the test runner down -- see `test_tree_kill_never_kills_its_own_group`.
        """
        kwargs = {}
        if sys.platform != "win32":
            kwargs["start_new_session"] = True
        return subprocess.Popen(
            [sys.executable, "-c", f"import time; time.sleep({seconds})"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **kwargs,
        )

    def test_child_is_killed_while_still_running(self, repo):
        proc = self._sleeper()
        messages: list[str] = []
        watch = KillWatch(repo, 1, on_kill=messages.append, poll_seconds=0.05)
        try:
            with watch.watch(proc):
                # The child is genuinely mid-call here -- not at a boundary,
                # not between stages, not waiting on anything we control.
                time.sleep(0.2)
                assert proc.poll() is None, "child should still be running"
                (repo / "data" / "speedrun" / "KILL-1").write_text("", encoding="utf-8")
                returncode = proc.wait(timeout=15)
        finally:
            if proc.poll() is None:  # pragma: no cover - only on a failed test
                proc.kill()

        assert watch.fired is True
        assert returncode is not None
        assert watch.kill_file is not None and watch.kill_file.name == "KILL-1"
        assert any(KILLED_MARKER in m for m in messages)
        assert any("mid-call" in m for m in messages)

    def test_stop_lands_within_a_poll_interval(self, repo):
        """The operator has already decided; the stop should land in seconds."""
        proc = self._sleeper()
        watch = KillWatch(repo, 1, poll_seconds=0.05)
        try:
            with watch.watch(proc):
                time.sleep(0.1)
                dropped = time.monotonic()
                (repo / "data" / "speedrun" / "KILL").write_text("", encoding="utf-8")
                proc.wait(timeout=15)
                elapsed = time.monotonic() - dropped
        finally:
            if proc.poll() is None:  # pragma: no cover
                proc.kill()
        assert watch.fired is True
        assert elapsed < 10, f"stop took {elapsed:.1f}s to land"

    def test_child_finishing_on_its_own_does_not_fire(self, repo):
        """No stop file, no kill -- the watch must not invent one."""
        proc = self._sleeper(0.1)
        watch = KillWatch(repo, 1, poll_seconds=0.05)
        with watch.watch(proc):
            returncode = proc.wait(timeout=15)
        assert watch.fired is False
        assert returncode == 0

    def test_watch_thread_stops_with_the_context(self, repo):
        proc = self._sleeper(0.1)
        watch = KillWatch(repo, 1, poll_seconds=0.05)
        before = threading.active_count()
        with watch.watch(proc):
            proc.wait(timeout=15)
        assert threading.active_count() <= before

    def test_check_now_is_the_boundary_path(self, repo):
        """Stage boundaries and between-issue gaps use the synchronous look."""
        watch = KillWatch(repo, 1, poll_seconds=0.05)
        assert watch.check_now() is False
        (repo / "data" / "speedrun" / "KILL-1").write_text("", encoding="utf-8")
        assert watch.check_now() is True
        assert watch.fired is True


class TestTreeKillBlastRadius:
    """A stop whose blast radius includes its own caller is not a stop.

    Caught on CI rather than reasoned about in advance: the first version of
    `tree_kill` called `os.killpg(os.getpgid(pid), SIGKILL)` unconditionally.
    A child spawned without `start_new_session` INHERITS the caller's process
    group, so on ubuntu-latest that named the group pytest was running in and
    SIGKILLed the test runner. The job hung at three times its usual duration.
    """

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX process groups")
    def test_tree_kill_never_kills_its_own_group(self):
        """A child sharing our group is killed ALONE, never by group."""
        from assemblyzero.speedrun import emergency_stop as es

        # No start_new_session: this child shares the test runner's group,
        # which is precisely the dangerous shape.
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        assert os.getpgid(proc.pid) == os.getpgid(0), "fixture assumes a shared group"
        try:
            ok, _detail = es.tree_kill(proc.pid)
            assert ok is True
            assert proc.wait(timeout=15) is not None
            # The whole point: we are still here to make this assertion.
            assert os.getpid() == os.getpid()
        finally:
            if proc.poll() is None:  # pragma: no cover
                proc.kill()

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX process groups")
    def test_a_child_in_its_own_group_is_killed_by_group(self):
        """The real launcher's shape: the whole tree goes, not just the top."""
        from assemblyzero.speedrun import emergency_stop as es

        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        assert os.getpgid(proc.pid) != os.getpgid(0)
        try:
            ok, _detail = es.tree_kill(proc.pid)
            assert ok is True
            assert proc.wait(timeout=15) is not None
        finally:
            if proc.poll() is None:  # pragma: no cover
                proc.kill()

    def test_a_pid_that_does_not_exist_is_reported_not_raised(self):
        from assemblyzero.speedrun import emergency_stop as es

        ok, detail = es.tree_kill(999999999)
        assert ok is False
        assert detail


# ---------------------------------------------------------------------------
# Part 2: the banner
# ---------------------------------------------------------------------------


class TestBanner:
    def test_banner_names_the_exact_stop_command(self, repo):
        text = "\n".join(banner_lines(repo, 1, repo / "data" / "speedrun" / "runs"))
        assert "--kill" in text
        assert "--issue 1" in text
        assert str(repo) in text

    def test_banner_teaches_the_promptless_path(self, repo):
        """The operator's actual situation was NO available prompt."""
        text = "\n".join(banner_lines(repo, 1, None))
        assert "KILL-1" in text
        assert "no free prompt" in text

    def test_banner_still_works_without_an_issue(self, repo):
        text = "\n".join(banner_lines(repo, None, None))
        assert "--kill" in text
        assert "KILL" in text

    def test_stop_command_is_pasteable(self, repo):
        cmd = stop_command(repo, 1)
        assert cmd.startswith("poetry run python tools/speedrun_roll.py")
        assert "&&" not in cmd and ";" not in cmd


# ---------------------------------------------------------------------------
# Part 4: killed is a clean verdict
# ---------------------------------------------------------------------------


class TestKilledVerdict:
    def test_exit_code_is_distinct_from_every_failure_class(self):
        from assemblyzero.core.exit_codes import CONFLICT_EXIT_CODE
        from assemblyzero.core.provider_storm import STORM_EXIT_CODE

        assert KILL_EXIT_CODE not in (0, 91, STORM_EXIT_CODE, CONFLICT_EXIT_CODE)

    def test_verdict_says_stopped_not_failed(self):
        text = "\n".join(killed_verdict_lines(1, None))
        assert "not a failure" in text
        assert "FAILED" not in text

    def test_verdict_promises_the_resume(self):
        text = "\n".join(killed_verdict_lines(1, None))
        assert "resumes" in text
