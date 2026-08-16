"""The emergency stop, proven on the platform that runs it (#2431).

The stop landed in #2422 and CI runs `ubuntu-latest` while the fleet runs
Windows, so its Windows branches were verified by nobody. That asymmetry has
already bitten once in the other direction: #2422's POSIX `tree_kill` SIGKILLed
its own caller, and only a Linux CI job found it -- the Windows path took
`taskkill /F /T` and every local run passed.

This is the control the operator was promised after being reduced to
considering a machine reboot, so it is proven where it runs:

  * `tree_kill`'s `taskkill /T /F` branch, against a real process tree with a
    real grandchild -- the tree part is the whole point, and a parent-only kill
    would pass a single-process test;
  * `is_live_python`'s `tasklist` parsing, against this interpreter and against
    a pid that is not one;
  * the kill-file path with the LAUNCHER MID-CALL, driving the real
    `roll_issue` rather than `KillWatch` alone;
  * `kill_roll` end to end, stamping a real events log.

Marked `windows_paths` and selected by a `windows-latest` CI job. `skipif` on
its own would leave them silently unrun everywhere, which is the state this
issue is about.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from assemblyzero.speedrun.emergency_stop import (
    KILL_EXIT_CODE,
    KILLED_MARKER,
    tree_kill,
)

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import speedrun_roll as sr  # noqa: E402

pytestmark = [
    pytest.mark.windows_paths,
    pytest.mark.skipif(sys.platform != "win32", reason="Windows-only code paths"),
]


def _spawn_tree() -> tuple[subprocess.Popen, int]:
    """A parent python that spawns a child python and prints the child's pid.

    A tree, not a process: `taskkill /T` is what distinguishes this stop from
    one that leaves model-calling orphans reparented to nothing, and a
    single-process fixture cannot tell the two apart.
    """
    code = (
        "import subprocess, sys, time;"
        "c = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)']);"
        "print(c.pid, flush=True);"
        "time.sleep(120)"
    )
    parent = subprocess.Popen(
        [sys.executable, "-c", code],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
    )
    child_pid = int(parent.stdout.readline().strip())
    return parent, child_pid


def _only_the_orchestrate_child():
    """Replace ONLY the orchestrate child with a long sleeper.

    `monkeypatch.setattr(sr.subprocess, "Popen", ...)` patches the shared
    `subprocess` module, and `subprocess.run` builds on `Popen` -- so a
    blanket stub also hijacks `tree_kill`'s own `taskkill` call. A first cut
    did exactly that: the kill fired on time, then sat inside `subprocess.run`
    waiting on a 120-second sleeper it had spawned instead of taskkill, and the
    test reported "the stop took 124s" as though the launcher were broken.

    The product was fine; an isolated repro of the same watch fired in 2.12s.
    A stub broad enough to catch the code under test's own subprocess calls
    manufactures product bugs, so this one passes everything through except
    the one command it means to replace.
    """
    real_popen = subprocess.Popen

    def popen(cmd, **kwargs):
        is_orchestrate = any("orchestrate.py" in str(part) for part in cmd)
        if not is_orchestrate:
            return real_popen(cmd, **kwargs)
        kwargs.pop("env", None)
        return real_popen(
            [sys.executable, "-c", "import time; time.sleep(120)"], **kwargs,
        )

    return popen


def _alive(pid: int) -> bool:
    result = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
        capture_output=True, text=True,
    )
    return f'"{pid}"' in (result.stdout or "")


class TestTreeKillOnWindows:
    def test_it_kills_the_whole_tree_not_just_the_parent(self):
        parent, child_pid = _spawn_tree()
        try:
            assert _alive(child_pid), "fixture failed to start a grandchild"
            ok, detail = tree_kill(parent.pid)
            assert ok is True, detail
            parent.wait(timeout=20)

            deadline = time.time() + 20
            while _alive(child_pid) and time.time() < deadline:
                time.sleep(0.25)
            assert not _alive(child_pid), (
                f"grandchild {child_pid} survived the tree kill -- this is the "
                "orphan class the stop exists to prevent"
            )
        finally:
            for pid in (child_pid, parent.pid):
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    capture_output=True,
                )

    def test_a_dead_pid_is_reported_not_raised(self):
        ok, detail = tree_kill(999999999)
        assert ok is False
        assert detail

    def test_the_path_conversion_trap_cannot_recur(self):
        """The operator's first manual attempt failed because Git Bash
        rewrote `/F` into a drive path. The child gets MSYS_NO_PATHCONV=1."""
        import inspect

        from assemblyzero.speedrun import emergency_stop

        source = inspect.getsource(emergency_stop.tree_kill)
        assert "MSYS_NO_PATHCONV" in source


class TestIsLivePythonOnWindows:
    """`tasklist` parsing, which decides whether a recorded pid may be killed.
    It reports 'INFO: No tasks...' on stdout with exit 0 when nothing matches,
    so the pid must be looked for rather than the exit code trusted."""

    def test_this_interpreter_is_a_live_python(self):
        assert sr.is_live_python(str(os.getpid())) is True

    def test_a_dead_pid_is_not(self):
        assert sr.is_live_python("999999999") is False

    def test_a_non_numeric_pid_is_not(self):
        assert sr.is_live_python("not-a-pid") is False

    def test_a_live_non_python_process_is_not(self):
        """The guard that stops a recycled pid authorising a kill of somebody
        else's work on a shared machine."""
        proc = subprocess.Popen(
            ["cmd", "/c", "ping -n 30 127.0.0.1 > NUL"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            time.sleep(0.5)
            assert sr.is_live_python(str(proc.pid)) is False
        finally:
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                capture_output=True,
            )


class TestTheKillFileStopsTheRealLauncherMidCall:
    """The operator's specific ask, and the case the whole issue is about.

    Drives `roll_issue` -- the real function, with the real Popen, the real
    KillWatch and the real Windows tree kill -- and drops the stop file while
    the child is provably still running.
    """

    @pytest.fixture
    def repo(self, tmp_path):
        r = tmp_path / "target"
        (r / ".git").mkdir(parents=True)
        (r / "data" / "speedrun").mkdir(parents=True)
        return r

    def test_the_launcher_returns_the_kill_verdict(self, repo, tmp_path, monkeypatch):
        log_dir = tmp_path / "runs"
        log_dir.mkdir()

        monkeypatch.setattr(sr, "ensure_base", lambda *_a, **_k: "arc")
        monkeypatch.setattr(sr.subprocess, "Popen", _only_the_orchestrate_child())

        # Drop the stop file once the child is genuinely mid-call.
        import threading

        def drop():
            time.sleep(3)
            (repo / "data" / "speedrun" / "KILL-1").write_text("", encoding="utf-8")

        threading.Thread(target=drop, daemon=True).start()

        started = time.time()
        code = sr.roll_issue(repo, 1, log_dir, tmp_path, [])
        elapsed = time.time() - started

        assert code == KILL_EXIT_CODE
        assert elapsed < 60, (
            f"the stop took {elapsed:.0f}s; the child sleeps 120s, so a value "
            "near that means the kill did not land mid-call"
        )

    def test_the_run_log_records_an_ordered_stop(self, repo, tmp_path, monkeypatch):
        log_dir = tmp_path / "runs"
        log_dir.mkdir()
        monkeypatch.setattr(sr, "ensure_base", lambda *_a, **_k: "arc")

        monkeypatch.setattr(sr.subprocess, "Popen", _only_the_orchestrate_child())

        import threading

        def drop():
            time.sleep(3)
            (repo / "data" / "speedrun" / "KILL").write_text("", encoding="utf-8")

        threading.Thread(target=drop, daemon=True).start()
        sr.roll_issue(repo, 1, log_dir, tmp_path, [])

        logs = list(log_dir.glob("run-issue1-*-events.log"))
        assert logs, "the run wrote no events log"
        text = logs[0].read_text(encoding="utf-8")
        assert KILLED_MARKER in text
        assert "mid-call" in text

    def test_the_stop_file_is_cleared_so_the_next_launch_runs(
        self, repo, tmp_path, monkeypatch
    ):
        """A stop file that outlived its run would stop the NEXT launch, which
        the operator would experience as a launcher that refuses to start."""
        log_dir = tmp_path / "runs"
        log_dir.mkdir()
        monkeypatch.setattr(sr, "ensure_base", lambda *_a, **_k: "arc")

        monkeypatch.setattr(sr.subprocess, "Popen", _only_the_orchestrate_child())

        stop = repo / "data" / "speedrun" / "KILL-1"

        import threading

        def drop():
            time.sleep(3)
            stop.write_text("", encoding="utf-8")

        threading.Thread(target=drop, daemon=True).start()
        sr.roll_issue(repo, 1, log_dir, tmp_path, [])

        assert not stop.exists()


class TestKillRollOnWindows:
    def test_it_stamps_the_run_log_and_returns_zero(self, tmp_path):
        repo = tmp_path / "target"
        (repo / "data" / "speedrun").mkdir(parents=True)
        log_dir = tmp_path / "runs"
        log_dir.mkdir()
        run_log = log_dir / "run-issue1-132000-events.log"
        run_log.write_text("13:20:00 START issue=#1\n", encoding="utf-8")

        # A real process to kill, recorded the way a roll records itself.
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(120)"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        sr.pid_file(log_dir).write_text(str(proc.pid), encoding="utf-8")
        try:
            assert sr.is_live_python(str(proc.pid)) is True
            code = sr.kill_roll(repo, log_dir, 1)
            assert code == 0
            assert proc.wait(timeout=20) is not None
            assert KILLED_MARKER in run_log.read_text(encoding="utf-8")
            assert not sr.pid_file(log_dir).exists()
        finally:
            if proc.poll() is None:  # pragma: no cover
                subprocess.run(
                    ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                    capture_output=True,
                )
