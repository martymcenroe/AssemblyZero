"""--detach without a view turned the operator into a log spelunker (#2138).

The roll narrates everything into `detached-launcher.log`; runbook 0952 then
told the operator to open more consoles and tail it by hand, which standard
0026 now prohibits: the console an operator launches from IS the display.

These pin the contract: following is the default and opting OUT is the flag,
a failed hand-off never follows, `--follow` is a pure viewer that runs no
spend gates, Ctrl+C detaches the view and never reaches the roll, and the
drain/status helpers the loop is built from read incrementally and never fold
"could not query" into "done". Also pins the documents: the standard's two
load-bearing clauses, and that runbook 0952 leads with the follower rather
than a tail command.
"""

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS = REPO_ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def _healthy_box(*_args, **_kwargs):
    """#1920: these tests exercise wiring, not machine health. Same stub as
    the sibling detach tests."""
    from assemblyzero.speedrun.box_health import BoxHealth

    return BoxHealth(True, [], "")

import speedrun_roll as sr  # noqa: E402


@pytest.fixture
def repo(tmp_path):
    """Enough of a repo for main() -- the git-touching checks are patched."""
    r = tmp_path / "boostgauge"
    (r / ".git").mkdir(parents=True)
    return r


def _wire(repo, argv_tail, *, launch_code=0):
    """Run main() with the hand-off and the follower both recorded, not run."""
    calls = {"launch": 0, "follow": []}

    def _launch(*_a, **_k):
        calls["launch"] += 1
        return launch_code

    def _follow(log_dir, **kw):
        calls["follow"].append((log_dir, kw))
        return 0

    with patch.object(sr, "check_assemblyzero_tree", lambda p: []), \
            patch.object(sr, "check_box_health", _healthy_box), \
            patch.object(sr, "open_must_resolve_issues", lambda r: ([], None)), \
            patch.object(sr, "launch_detached", _launch), \
            patch.object(sr, "follow_roll", _follow), \
            patch.object(sr.sys, "platform", "win32"):
        code = sr.main(["--repo", str(repo), *argv_tail])
    return code, calls


class TestFollowIsTheDefault:
    """Standard 0026: watching is never opt-in. Opting OUT is the flag."""

    def test_detach_streams_after_a_successful_handoff(self, repo):
        code, calls = _wire(repo, ["--issue", "7", "--detach"])
        assert code == 0
        assert calls["launch"] == 1
        assert len(calls["follow"]) == 1

    def test_no_follow_hands_off_and_returns(self, repo):
        code, calls = _wire(repo, ["--issue", "7", "--detach", "--no-follow"])
        assert code == 0
        assert calls["launch"] == 1
        assert calls["follow"] == []

    def test_a_failed_handoff_never_follows(self, repo):
        """Streaming after a failed schedule would sit on a roll that does not
        exist, hiding the 91 the operator needs to see."""
        code, calls = _wire(repo, ["--issue", "7", "--detach"], launch_code=91)
        assert code == 91
        assert calls["follow"] == []


class TestReattach:
    def test_follow_needs_no_issue_and_does_not_wait_for_start(self, repo):
        code, calls = _wire(repo, ["--follow"])
        assert code == 0
        assert calls["launch"] == 0
        assert len(calls["follow"]) == 1
        assert calls["follow"][0][1].get("wait_for_start") is False

    def test_follow_runs_no_spend_gates(self, repo):
        """A viewer must attach even when a gate would refuse a launch --
        the roll it is watching already passed those gates."""

        def _boom(*_a, **_k):
            raise AssertionError("a spend gate ran for a pure viewer")

        with patch.object(sr, "check_assemblyzero_tree", _boom), \
                patch.object(sr, "check_box_health", _boom), \
                patch.object(sr, "open_must_resolve_issues", _boom), \
                patch.object(sr, "follow_roll", lambda *a, **k: 0), \
                patch.object(sr.sys, "platform", "win32"):
            assert sr.main(["--repo", str(repo), "--follow"]) == 0

    def test_follow_refuses_an_issue(self, repo, capsys):
        code, calls = _wire(repo, ["--follow", "--issue", "7"])
        assert code == 91
        assert calls["follow"] == []
        assert "no --issue" in capsys.readouterr().out

    def test_non_windows_refuses(self, repo, capsys):
        with patch.object(sr, "follow_roll", lambda *a, **k: 0), \
                patch.object(sr.sys, "platform", "linux"):
            code = sr.main(["--repo", str(repo), "--follow"])
        assert code == 91
        assert "ERROR" in capsys.readouterr().out


class TestDrain:
    def test_reads_only_what_was_appended(self, tmp_path):
        # Bytes, not text: on Windows a text-mode write translates \n to \r\n
        # and the assertion would be about the translation, not the drain.
        f = tmp_path / "narration.log"
        f.write_bytes(b"one\n")
        pos, chunk = sr._drain(f, 0)
        assert chunk == "one\n"
        with f.open("ab") as fh:
            fh.write(b"two\n")
        pos, chunk = sr._drain(f, pos)
        assert chunk == "two\n"

    def test_a_missing_file_is_quiet(self, tmp_path):
        assert sr._drain(tmp_path / "nope.log", 0) == (0, "")


def _scripted_run(stdout, returncode=0):
    def _run(cmd, cwd=None):
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr="")

    return _run


class TestTaskStatus:
    def test_running_is_read_from_the_csv(self):
        line = f'"\\{sr.TASK_NAME}","N/A","Running"'
        with patch.object(sr, "_run", _scripted_run(line)):
            assert sr._task_status() == "Running"

    def test_ready_is_read_from_the_csv(self):
        line = f'"\\{sr.TASK_NAME}","N/A","Ready"'
        with patch.object(sr, "_run", _scripted_run(line)):
            assert sr._task_status() == "Ready"

    def test_a_failed_query_is_unknown_not_done(self):
        """Folding "could not ask" into "finished" would detach the view from
        a live roll on any transient schtasks hiccup."""
        with patch.object(sr, "_run", _scripted_run("", returncode=1)):
            assert sr._task_status() == ""

    def test_garbage_output_is_unknown(self):
        with patch.object(sr, "_run", _scripted_run("INFO: nothing here")):
            assert sr._task_status() == ""


class TestLastResult:
    def _csv(self, value):
        return (
            '"HostName","TaskName","Status","Last Result","Author"\n'
            f'"BOX","\\{sr.TASK_NAME}","Ready","{value}","user"'
        )

    def test_the_rolls_exit_code_comes_back(self):
        with patch.object(sr, "_run", _scripted_run(self._csv("91"))):
            assert sr._task_last_result() == 91

    def test_success_is_zero(self):
        with patch.object(sr, "_run", _scripted_run(self._csv("0"))):
            assert sr._task_last_result() == 0

    def test_a_scheduler_status_is_not_an_exit_code(self):
        """267009 is SCHED_S_TASK_RUNNING, not a result of the roll."""
        with patch.object(sr, "_run", _scripted_run(self._csv("267009"))):
            assert sr._task_last_result() == 1

    def test_a_failed_query_is_none(self):
        with patch.object(sr, "_run", _scripted_run("", returncode=1)):
            assert sr._task_last_result() is None


class TestFollowLoop:
    def _runs(self, tmp_path):
        d = tmp_path / "runs"
        d.mkdir()
        return d

    def test_streams_then_returns_the_rolls_result(self, tmp_path, capsys):
        runs = self._runs(tmp_path)
        narration = runs / "detached-launcher.log"
        narration.write_text("BASE clean\nLAUNCH base=x\n", encoding="utf-8")

        statuses = iter(["Running", "Ready"])
        with patch.object(sr, "_task_status", lambda: next(statuses)), \
                patch.object(sr, "_task_last_result", lambda: 91), \
                patch.object(sr.time, "sleep", lambda s: None):
            code = sr.follow_roll(runs, context_bytes=narration.stat().st_size)

        out = capsys.readouterr().out
        assert code == 91
        assert "LAUNCH base=x" in out
        assert "The roll is done" in out

    def test_content_written_after_the_last_status_poll_still_prints(
        self, tmp_path, capsys
    ):
        """The roll's final lines land between the last drain and the status
        flip; the loop must drain again before declaring done."""
        runs = self._runs(tmp_path)
        narration = runs / "detached-launcher.log"
        narration.write_text("", encoding="utf-8")

        def _flip():
            with narration.open("a", encoding="utf-8") as fh:
                fh.write("All 1 issue(s) rolled.\n")
            return "Ready"

        statuses = iter([lambda: "Running", _flip])
        with patch.object(sr, "_task_status", lambda: next(statuses)()), \
                patch.object(sr, "_task_last_result", lambda: 0), \
                patch.object(sr.time, "sleep", lambda s: None):
            code = sr.follow_roll(runs)

        assert code == 0
        assert "All 1 issue(s) rolled." in capsys.readouterr().out

    def test_reattach_to_nothing_says_so_immediately(self, tmp_path, capsys):
        runs = self._runs(tmp_path)
        with patch.object(sr, "_task_status", lambda: "Ready"), \
                patch.object(sr.time, "sleep", lambda s: None):
            code = sr.follow_roll(runs, wait_for_start=False)
        assert code == 0
        assert "No roll is running" in capsys.readouterr().out

    def test_ctrl_c_detaches_the_view_and_never_the_roll(self, tmp_path, capsys):
        """The whole reason following can be the default: stopping the watch
        must be consequence-free for the work."""
        runs = self._runs(tmp_path)
        recorder = []

        def _record(cmd, cwd=None):
            recorder.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        def _interrupt():
            raise KeyboardInterrupt

        with patch.object(sr, "_task_status", _interrupt), \
                patch.object(sr, "_run", _record), \
                patch.object(sr.time, "sleep", lambda s: None):
            code = sr.follow_roll(runs)

        out = capsys.readouterr().out
        assert code == 0
        assert "still running" in out
        assert "--follow" in out and "--detach-stop" in out
        assert [c for c in recorder if c[0] in ("taskkill",)] == []
        assert [c for c in recorder if c[0] == "schtasks" and "/End" in c] == []


class TestHeartbeatNote:
    def test_the_freshest_heartbeat_and_its_last_line(self, tmp_path):
        old = tmp_path / "run-a-heartbeat.log"
        new = tmp_path / "run-b-heartbeat.log"
        old.write_text("01:00:00 alive\n", encoding="utf-8")
        new.write_text("01:00:00 alive\n02:00:00 alive\n", encoding="utf-8")
        os.utime(old, (1_000_000, 1_000_000))
        os.utime(new, (2_000_000, 2_000_000))
        assert sr._newest_heartbeat(tmp_path) == "run-b-heartbeat.log: 02:00:00 alive"

    def test_no_heartbeat_yet_is_empty(self, tmp_path):
        assert sr._newest_heartbeat(tmp_path) == ""


class TestTheDocumentsConform:
    """#2137: the standard's load-bearing clauses, pinned at string level the
    same way test_sweep_source_contains_no_force pins the sweep."""

    STANDARD = REPO_ROOT / "docs" / "standards" / "0026-operator-console-narration.md"
    RUNBOOK = REPO_ROOT / "docs" / "runbooks" / "0952-speedrun-operator-solo.md"

    def test_the_standard_exists_with_its_load_bearing_clauses(self):
        text = self.STANDARD.read_text(encoding="utf-8")
        assert "never opt-in" in text
        assert "stops the view, never the work" in text

    def test_the_runbook_leads_with_the_follower_not_a_tail(self):
        text = self.RUNBOOK.read_text(encoding="utf-8")
        assert "You are already watching" in text
        watch = text.index("You are already watching")
        first_tail = text.index("tail -f")
        assert watch < first_tail, (
            "runbook 0952 must present the follower before any tail command"
        )
