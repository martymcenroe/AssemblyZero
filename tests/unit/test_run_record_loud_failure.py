"""run_record.py under standard 0034, one test per sweep site (#3791).

The run record is what a standalone run leaves for the session that cleans up
after it. Nothing the run produces reads it, so a record that cannot be
written does not stop the run; it alerts the operator, once per thing that
broke, with the cause, and every line it could not keep is an ERROR line on
the console instead. What does raise: a git question that cannot be answered
(``left_in_place`` makes no partial list, since the finishing commands built
from one would be wrong) and a profile the record cannot describe (the run's
seats would fail on it later, after spending). Line numbers in the names are
ledger 0908's, at its base ``79e18ad1``.
"""
from __future__ import annotations

import inspect
import subprocess
import sys
from pathlib import Path

import pytest

from assemblyzero.core import run_record as rr
from assemblyzero.core.run_record import RunRecord, left_in_place


def _git(repo: Path, *args: str) -> None:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    assert result.returncode == 0, f"git {' '.join(args)}: {result.stderr}"


@pytest.fixture
def target_repo(tmp_path: Path) -> Path:
    root = tmp_path / "target"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "Test")
    (root / ".gitignore").write_text("data/\n", encoding="utf-8")
    (root / "README.md").write_text("base\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")
    return root


@pytest.fixture
def restore_streams():
    """A record that is never finished would leave the tee installed."""
    out, err = sys.stdout, sys.stderr
    yield
    sys.stdout, sys.stderr = out, err


def _failing_git(monkeypatch, word: str, stderr: str = "fatal: the query broke") -> None:
    """Every git command naming ``word`` exits 128; the rest run for real."""
    real = subprocess.run

    def run(cmd, *args, **kwargs):
        if cmd and cmd[0] == "git" and word in cmd:
            return subprocess.CompletedProcess(cmd, 128, stdout="", stderr=stderr)
        return real(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", run)


class _FlakyFile:
    """A real run log whose write, flush or close can be made to fail."""

    def __init__(self, real):
        self._real = real
        self.fail_write = self.fail_flush = self.fail_close = False

    def write(self, text):
        if self.fail_write:
            raise OSError(28, "No space left on device")
        return self._real.write(text)

    def flush(self):
        if self.fail_flush:
            raise OSError(28, "No space left on device")
        return self._real.flush()

    def close(self):
        self._real.close()
        if self.fail_close:
            raise OSError(5, "Input/output error")


def _flaky_run_log(monkeypatch) -> list[_FlakyFile]:
    """The run log (``<tag>.log``) opens as a _FlakyFile; returns them."""
    real = Path.open
    opened: list[_FlakyFile] = []

    def open_(self, *args, **kwargs):
        handle = real(self, *args, **kwargs)
        if self.name.endswith(".log") and not self.name.endswith("-events.log"):
            opened.append(_FlakyFile(handle))
            return opened[-1]
        return handle

    monkeypatch.setattr(Path, "open", open_)
    return opened


def _refuse_open(monkeypatch, suffix: str, exc: OSError) -> None:
    real = Path.open

    def open_(self, *args, **kwargs):
        if self.name.endswith(suffix):
            raise exc
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", open_)


class _Console:
    """A console stream that can be made to refuse writes (a closed pipe)."""

    def __init__(self):
        self.text = ""
        self.broken = False

    def write(self, text):
        if self.broken:
            raise BrokenPipeError(32, "Broken pipe")
        self.text += text
        return len(text)

    def flush(self):
        if self.broken:
            raise BrokenPipeError(32, "Broken pipe")


def _no_tag(function) -> None:
    assert "fail-open" not in inspect.getsource(function)


# ---------------------------------------------------------------------------
# The tee (77, 78, 87, 88)
# ---------------------------------------------------------------------------


class TestTheTee:
    def test_77_a_run_log_that_refuses_a_write_alerts_once(
        self, target_repo, monkeypatch, capsys, restore_streams, operator_alerts
    ):
        logs = _flaky_run_log(monkeypatch)
        record = RunRecord.start("lld", target_repo, 42, argv=["prog"])
        logs[0].fail_write = True

        print("the first line the log refused")
        print("and a second")
        record.finish("success")

        assert len(operator_alerts) == 1
        alert = operator_alerts[0]
        assert str(record.out_path) in alert["what"]
        assert "OSError" in alert["cause"] and "No space left" in alert["cause"]
        assert "console" in alert["consequence"]
        out = capsys.readouterr().out
        assert "the first line the log refused" in out and "and a second" in out

    def test_78_the_write_tag_is_gone(self):
        _no_tag(rr._Tee.write)

    def test_87_a_run_log_that_refuses_a_flush_alerts(
        self, target_repo, monkeypatch, restore_streams, operator_alerts
    ):
        logs = _flaky_run_log(monkeypatch)
        record = RunRecord.start("lld", target_repo, 42, argv=["prog"])
        logs[0].fail_flush = True

        sys.stdout.flush()
        record.finish("success")

        assert len(operator_alerts) == 1
        assert "flush" in operator_alerts[0]["where"]
        assert "No space left" in operator_alerts[0]["cause"]

    def test_88_the_flush_tag_is_gone(self):
        _no_tag(rr._Tee.flush)

    def test_a_tee_that_outlives_its_record_writes_to_the_console_quietly(
        self, target_repo, capsys, restore_streams, operator_alerts
    ):
        """Kept: a logging handler made during the run still holds the tee.
        After the record is finished there is no log to write to, which is
        not a failure, and the console still gets the text."""
        record = RunRecord.start("lld", target_repo, 42, argv=["prog"])
        tee = sys.stdout
        record.finish("success")

        tee.write("printed after the record closed\n")
        tee.flush()

        assert operator_alerts == []
        assert "printed after the record closed" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# git (103, 104, 107)
# ---------------------------------------------------------------------------


class TestGit:
    def test_103_a_git_that_cannot_run_raises(self, tmp_path, monkeypatch):
        def run(cmd, *args, **kwargs):
            raise FileNotFoundError(2, "No such file or directory", "git")

        monkeypatch.setattr(subprocess, "run", run)

        with pytest.raises(RuntimeError, match="FileNotFoundError") as raised:
            rr._git(tmp_path, "status", "--porcelain")
        assert "git status --porcelain" in str(raised.value)
        assert str(tmp_path) in str(raised.value)

    def test_103_a_git_that_times_out_raises(self, tmp_path, monkeypatch):
        def run(cmd, *args, **kwargs):
            raise subprocess.TimeoutExpired(cmd, 20)

        monkeypatch.setattr(subprocess, "run", run)

        with pytest.raises(RuntimeError, match="TimeoutExpired"):
            rr._git(tmp_path, "worktree", "list", "--porcelain")

    def test_104_the_git_tag_is_gone(self):
        _no_tag(rr._git)

    def test_107_a_git_that_exits_non_zero_raises_with_its_stderr(self, tmp_path):
        with pytest.raises(RuntimeError, match="exit 128") as raised:
            rr._git(tmp_path, "status", "--porcelain")
        assert "not a git repository" in str(raised.value)


# ---------------------------------------------------------------------------
# What the run left in place (134, 144, 155, 165)
# ---------------------------------------------------------------------------


class TestLeftInPlace:
    def test_134_a_worktree_list_that_fails_raises(self, target_repo, monkeypatch):
        _failing_git(monkeypatch, "worktree", "fatal: worktrees broke")

        with pytest.raises(RuntimeError, match="git worktree list") as raised:
            left_in_place(target_repo, 42)
        assert "worktrees broke" in str(raised.value)

    def test_134_the_record_says_unknown_and_alerts_once(
        self, target_repo, monkeypatch, capsys, restore_streams, operator_alerts
    ):
        _git(target_repo, "branch", "42-lld")
        _failing_git(monkeypatch, "worktree", "fatal: worktrees broke")
        record = RunRecord.start("lld", target_repo, 42, argv=["prog"])
        try:
            raise ValueError("the run died")
        except ValueError as exc:
            record.crash(exc)
        record.finish("halt", "the run died")

        events = record.events_path.read_text(encoding="utf-8")
        assert "left in place: unknown" in events
        assert "worktrees broke" in events
        # No partial list: the branch is not offered for `git branch -d`
        # while a worktree nobody could list may still hold it.
        assert "branch: 42-lld" not in events
        assert "branch -d" not in events
        assert len(operator_alerts) == 1
        assert "worktrees broke" in operator_alerts[0]["cause"]
        out = capsys.readouterr().out
        assert "[run] left in place: unknown" in out
        assert "branch -d" not in out

    def test_144_a_branch_list_that_fails_raises(self, target_repo, monkeypatch):
        _failing_git(monkeypatch, "--list", "fatal: branches broke")

        with pytest.raises(RuntimeError, match="git branch --list 42-") as raised:
            left_in_place(target_repo, 42)
        assert "branches broke" in str(raised.value)

    def test_155_a_remote_ref_list_that_fails_raises(self, target_repo, monkeypatch):
        _failing_git(monkeypatch, "for-each-ref", "fatal: refs broke")

        with pytest.raises(RuntimeError, match="git for-each-ref") as raised:
            left_in_place(target_repo, 42)
        assert "refs broke" in str(raised.value)

    def test_165_a_status_that_fails_raises(self, target_repo, monkeypatch):
        _failing_git(monkeypatch, "status", "fatal: index broke")

        with pytest.raises(RuntimeError, match="git status") as raised:
            left_in_place(target_repo, 42)
        assert "index broke" in str(raised.value)

    def test_a_clean_run_alerts_no_one(self, target_repo, restore_streams, operator_alerts):
        """Kept: a run on a clean target leaves nothing and says so, quietly."""
        record = RunRecord.start("lld", target_repo, 42, argv=["prog"])
        record.node("N1_draft")
        record.finish("success")

        assert operator_alerts == []
        assert left_in_place(target_repo, 42) == []
        assert "left in place (0):" in record.events_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Opening the record (271, 272, 283)
# ---------------------------------------------------------------------------


class TestStart:
    def test_271_a_run_log_that_cannot_be_opened_alerts(
        self, target_repo, monkeypatch, restore_streams, operator_alerts
    ):
        out = sys.stdout
        _refuse_open(monkeypatch, ".log", PermissionError(13, "Permission denied"))
        # The events log is refused too (it ends in .log); only the run log's
        # alert is asserted here, the events log's is site 410's.
        record = RunRecord.start("lld", target_repo, 42, argv=["prog"])
        record.finish("success")

        run_log = [a for a in operator_alerts if str(record.out_path) in a["what"]]
        assert len(run_log) == 1
        assert "PermissionError" in run_log[0]["cause"]
        assert "console" in run_log[0]["consequence"]
        assert sys.stdout is out

    def test_272_the_start_tag_is_gone(self):
        _no_tag(RunRecord.start)

    def test_283_a_head_git_cannot_read_alerts_with_the_cause(
        self, target_repo, monkeypatch, restore_streams, operator_alerts
    ):
        _failing_git(monkeypatch, "rev-parse", "fatal: HEAD broke")
        record = RunRecord.start("lld", target_repo, 42, argv=["prog"])
        record.finish("success")

        assert len(operator_alerts) == 1
        assert "HEAD broke" in operator_alerts[0]["cause"]
        events = record.events_path.read_text(encoding="utf-8")
        assert "head=unknown" in events and "HEAD broke" in events


# ---------------------------------------------------------------------------
# The profile header (318, 319)
# ---------------------------------------------------------------------------


class TestProfile:
    def test_318_a_profile_the_record_cannot_describe_raises(
        self, target_repo, monkeypatch, restore_streams
    ):
        from assemblyzero.core import seats

        def seat_table(profile):
            raise seats.ProfileError("impl.code: spec is empty")

        monkeypatch.setattr(seats, "seat_table", seat_table)
        record = RunRecord.start("impl", target_repo, 42, argv=["prog"])
        try:
            with pytest.raises(seats.ProfileError, match="spec is empty"):
                record.profile({"name": "mock", "sha256": "abc", "source": "test"})
        finally:
            record.finish("fail", "profile")

    def test_319_the_profile_tag_is_gone(self):
        _no_tag(RunRecord.profile)


# ---------------------------------------------------------------------------
# finish's console list (378, 379)
# ---------------------------------------------------------------------------


class TestFinish:
    def test_378_a_console_that_refuses_the_list_alerts(
        self, target_repo, restore_streams, operator_alerts
    ):
        console = _Console()
        sys.stdout = console
        record = RunRecord.start("lld", target_repo, 42, argv=["prog"])
        console.broken = True

        record.finish("success")

        assert len(operator_alerts) == 1
        assert "BrokenPipeError" in operator_alerts[0]["cause"]
        assert str(record.events_path) in operator_alerts[0]["consequence"]
        assert sys.stdout is console

    def test_379_the_finish_tag_is_gone(self):
        _no_tag(RunRecord.finish)


# ---------------------------------------------------------------------------
# The events log, and the line about it (410, 411, 420, 421)
# ---------------------------------------------------------------------------


class TestTheEventsLog:
    def test_410_an_events_log_that_cannot_be_written_alerts_once(
        self, target_repo, monkeypatch, capsys, restore_streams, operator_alerts
    ):
        _refuse_open(monkeypatch, "-events.log", OSError(28, "No space left on device"))
        record = RunRecord.start("lld", target_repo, 42, argv=["prog"])
        record.node("N1_draft")
        record.finish("success")

        assert len(operator_alerts) == 1
        alert = operator_alerts[0]
        assert str(record.events_path) in alert["what"]
        assert "No space left" in alert["cause"]
        err = capsys.readouterr().err
        assert "ERROR [run]" in err
        assert "node N1_draft" in err

    def test_411_the_events_tag_is_gone(self):
        _no_tag(RunRecord._write_events)

    def test_420_an_error_line_that_cannot_be_written_alerts(
        self, target_repo, monkeypatch, restore_streams, operator_alerts
    ):
        console = _Console()
        sys.stderr = console
        _refuse_open(monkeypatch, "-events.log", OSError(28, "No space left on device"))
        record = RunRecord.start("lld", target_repo, 42, argv=["prog"])
        console.broken = True

        record.node("N1_draft")
        record.finish("success")

        broken = [a for a in operator_alerts if "BrokenPipeError" in a["cause"]]
        assert broken, operator_alerts
        assert "node N1_draft" in broken[0]["consequence"]

    def test_421_no_tag_is_left_in_the_module(self):
        """The 421 tag sat in the stderr warning helper, which is gone."""
        assert "fail-open" not in inspect.getsource(rr)


# ---------------------------------------------------------------------------
# Closing the run log (434, 435)
# ---------------------------------------------------------------------------


class TestClose:
    def test_434_a_run_log_that_will_not_close_alerts(
        self, target_repo, monkeypatch, restore_streams, operator_alerts
    ):
        logs = _flaky_run_log(monkeypatch)
        out, err = sys.stdout, sys.stderr
        record = RunRecord.start("lld", target_repo, 42, argv=["prog"])
        logs[0].fail_close = True

        record.finish("success")

        assert len(operator_alerts) == 1
        assert str(record.out_path) in operator_alerts[0]["what"]
        assert "Input/output error" in operator_alerts[0]["cause"]
        assert sys.stdout is out and sys.stderr is err

    def test_435_the_close_tag_is_gone(self):
        _no_tag(RunRecord._restore_streams)
