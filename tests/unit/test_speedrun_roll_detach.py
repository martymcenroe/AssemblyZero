"""A roll must outlive the session that started it (#2015).

Two boostgauge rolls died on 2026-07-31 with no `session-events.log` at all --
no trapped signal, no `finally`. Measured the same day: a backgrounded parent
killed by the harness takes every child with it, and neither DETACHED_PROCESS
nor CREATE_BREAKAWAY_FROM_JOB escapes. A scheduled task does, because the Task
Scheduler service parents it instead of the agent's shell.

These pin the parts of that hand-off which are silent when they break: the
relaunch argv, the task definition's long-run settings, the failure paths, and
-- load-bearing for every future diagnosis -- that the launcher never writes
the session log it is used to detect the absence of.
"""

import argparse
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import speedrun_roll as sr  # noqa: E402


@pytest.fixture
def repo(tmp_path):
    """Enough of a repo for main() -- the git-touching checks are patched."""
    r = tmp_path / "boostgauge"
    (r / ".git").mkdir(parents=True)
    return r


class _Recorder:
    """Stands in for _run, recording argv and replaying scripted exit codes."""

    def __init__(self, codes=None):
        self.calls = []
        self.codes = codes or {}

    def __call__(self, cmd, cwd=None):
        self.calls.append(cmd)
        code = self.codes.get(cmd[1] if len(cmd) > 1 else "", 0)
        return subprocess.CompletedProcess(cmd, code, stdout="", stderr="boom")

    def schtasks(self, verb):
        return [c for c in self.calls if c[0] == "schtasks" and c[1] == verb]


def _detach(repo, recorder, issues=("7",), platform="win32"):
    argv = ["--repo", str(repo), "--detach"]
    for i in issues:
        argv += ["--issue", str(i)]
    with patch.object(sr, "check_assemblyzero_tree", lambda p: []), \
            patch.object(sr, "_run", recorder), \
            patch.object(sr.sys, "platform", platform):
        return sr.main(argv)


class TestRelaunchArgv:
    def _args(self, issues=(7, 41)):
        return argparse.Namespace(
            issue=list(issues), log_dir=None, assemblyzero_root=None,
            detach=True, detached_stdout=None,
        )

    def test_the_detach_request_is_not_passed_on(self, tmp_path):
        """A relaunch that kept --detach would schedule a task that schedules a
        task, forever, and never roll anything."""
        argv = sr.detached_argv(
            self._args(), [], tmp_path / "repo", tmp_path / "az", tmp_path / "logs"
        )
        assert "--detach" not in argv

    def test_every_issue_survives_the_rebuild(self, tmp_path):
        argv = sr.detached_argv(
            self._args((7, 41, 1)), [], tmp_path / "r", tmp_path / "az", tmp_path / "l"
        )
        assert [argv[i + 1] for i, a in enumerate(argv) if a == "--issue"] == [
            "7", "41", "1"
        ]

    def test_paths_are_absolute_because_the_scheduler_picks_the_cwd(self, tmp_path):
        argv = sr.detached_argv(
            self._args(), [], tmp_path / "r", tmp_path / "az", tmp_path / "l"
        )
        for flag in ("--repo", "--log-dir", "--assemblyzero-root"):
            value = argv[argv.index(flag) + 1]
            assert Path(value).is_absolute(), f"{flag} must be absolute, got {value}"

    def test_unrecognised_flags_are_forwarded(self, tmp_path):
        """parse_known_args passes pipeline flags through; detaching must not
        silently drop them."""
        argv = sr.detached_argv(
            self._args(), ["--no-gate-pr"], tmp_path / "r", tmp_path / "a",
            tmp_path / "l",
        )
        assert "--no-gate-pr" in argv

    def test_the_rebuilt_argv_actually_parses(self, tmp_path, repo):
        """Guard: the relaunch is only ever executed by the scheduler, so a
        malformed argv would surface as a task that dies instantly with nobody
        watching. Feed it back through main() and require it to reach a roll."""
        argv = sr.detached_argv(
            self._args((7,)), ["--no-gate-pr"], repo, tmp_path / "az", tmp_path / "l"
        )
        rolled = []
        with patch.object(sr, "check_assemblyzero_tree", lambda p: []), \
                patch.object(sr, "roll_issue",
                             lambda *a: rolled.append(a) or 0), \
                patch.object(sr, "restore_repo", lambda *a: []):
            code = sr.main(argv)

        assert code == 0
        assert [c[1] for c in rolled] == [7]


class TestTaskDefinition:
    def _xml(self, **kw):
        base = dict(
            command=r"C:\py\python.exe", arguments="-x", working_dir=r"C:\az",
            description="roll #7", user="DOM\\user",
        )
        base.update(kw)
        return sr.build_task_xml(**base)

    def test_no_trigger_so_it_can_never_fire_on_its_own(self):
        assert "<Triggers />" in self._xml()

    def test_no_execution_time_limit(self):
        """The scheduler's default stops a task partway; an arc runs hours."""
        assert "<ExecutionTimeLimit>PT0S</ExecutionTimeLimit>" in self._xml()

    def test_the_scheduler_may_not_hard_terminate_the_roll(self):
        assert "<AllowHardTerminate>false</AllowHardTerminate>" in self._xml()

    def test_battery_state_neither_blocks_nor_stops_it(self):
        xml = self._xml()
        assert "<DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>" in xml
        assert "<StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>" in xml

    def test_runs_unelevated_as_the_current_user(self):
        """Runbook 0903 hard rule: no UAC, and gh credentials come from the
        user's own profile."""
        xml = self._xml()
        assert "<RunLevel>LeastPrivilege</RunLevel>" in xml
        assert "<LogonType>InteractiveToken</LogonType>" in xml

    def test_a_second_roll_does_not_stomp_a_running_one(self):
        assert "<MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>" in self._xml()

    def test_xml_special_characters_are_escaped(self):
        """A repo path or description with & or < would otherwise produce a
        definition schtasks rejects."""
        xml = self._xml(description="roll #7 & #41 <fast>")
        assert "&amp;" in xml and "&lt;fast&gt;" in xml
        assert "& #41" not in xml


class TestLaunch:
    def test_it_creates_then_starts_the_task(self, repo):
        rec = _Recorder()
        assert _detach(repo, rec) == 0
        verbs = [c[1] for c in rec.calls if c[0] == "schtasks"]
        assert verbs == ["/Create", "/Run"]

    def test_the_definition_is_written_as_utf16(self, repo):
        """schtasks rejects a UTF-8 definition as malformed -- a silent,
        confusing failure if this regresses."""
        rec = _Recorder()
        _detach(repo, rec)
        xml_path = repo / "data" / "speedrun" / "runs" / "detached-task.xml"
        assert xml_path.read_bytes()[:2] in (b"\xff\xfe", b"\xfe\xff")
        assert "<Triggers />" in xml_path.read_text(encoding="utf-16")

    def test_a_failed_create_does_not_start_anything(self, repo):
        rec = _Recorder(codes={"/Create": 1})
        assert _detach(repo, rec) == 91
        assert rec.schtasks("/Run") == []

    def test_a_failed_start_is_reported_not_swallowed(self, repo):
        rec = _Recorder(codes={"/Run": 1})
        assert _detach(repo, rec) == 91

    def test_a_failure_says_why_in_the_detach_log(self, repo):
        rec = _Recorder(codes={"/Create": 1})
        _detach(repo, rec)
        log = (repo / "data" / "speedrun" / "runs" / "detach-events.log").read_text(
            encoding="utf-8"
        )
        assert "DETACH create failed" in log and "boom" in log

    def test_non_windows_refuses_loudly_and_rolls_nothing(self, repo, capsys):
        """Silently rolling inline would hand back exactly the fragile run the
        operator asked to escape."""
        rec = _Recorder()
        code = _detach(repo, rec, platform="linux")
        assert code == 91
        assert rec.schtasks("/Create") == []
        assert "ERROR" in capsys.readouterr().out

    def test_a_stale_tree_blocks_before_the_task_is_created(self, repo):
        rec = _Recorder()
        with patch.object(sr, "check_assemblyzero_tree",
                          lambda p: ["2 commit(s) behind origin/main"]), \
                patch.object(sr, "_run", rec):
            code = sr.main(["--repo", str(repo), "--issue", "7", "--detach"])

        assert code == 91
        assert rec.calls == [], "a stale tree must not reach the scheduler"


class TestTheSessionLogStaysDiagnostic:
    """The absence of session-events.log is how an uncatchable kill is told
    apart from an orderly exit. A launcher that wrote it would silently retire
    that evidence for every future death."""

    def test_detaching_does_not_create_the_session_log(self, repo):
        rec = _Recorder()
        _detach(repo, rec)
        runs = repo / "data" / "speedrun" / "runs"
        assert not (runs / "session-events.log").exists()
        assert (runs / "detach-events.log").exists()


class TestConsolelessNarration:
    def test_stdout_is_rebound_to_the_file(self, tmp_path):
        """A scheduled task inherits no console, so prints must land somewhere
        or the roll narrates into nothing."""
        target = tmp_path / "nested" / "launcher.log"
        real = sys.stdout
        try:
            sr._redirect_stdio(target)
            print("hello from a task")
        finally:
            sys.stdout.close()
            sys.stdout = real
        assert "hello from a task" in target.read_text(encoding="utf-8")

    def test_the_relaunch_asks_for_that_redirect(self, tmp_path):
        args = argparse.Namespace(
            issue=[7], log_dir=None, assemblyzero_root=None,
            detach=True, detached_stdout=None,
        )
        argv = sr.detached_argv(args, [], tmp_path / "r", tmp_path / "a", tmp_path / "l")
        assert "--detached-stdout" in argv
