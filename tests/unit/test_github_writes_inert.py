"""#2826: a replay never writes to GitHub.

On 2026-09-04 a replay of a halted run reached the spec review's BLOCKED
path and ``file_must_resolve`` wrote boostgauge #434 -- a copy of a question
already ruled and closed -- from the throwaway clone, whose ``origin`` is the
real repository. The next authorised launch was refused by it.

These tests pin the one switch that makes every write inert, the two
runners that honour it, the filer's explicit branch, and the replay runner's
use of it. The control -- writes are live when the switch is off -- is here
too, so the guard cannot be satisfied by a runner that never runs anything.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

from assemblyzero.core.github_writes import (
    INERT_ENV,
    SUPPRESSED_MARK,
    inert_github_writes,
    inert_reason,
    is_github_write,
    suppress_if_inert,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _live_by_default(monkeypatch):
    monkeypatch.delenv(INERT_ENV, raising=False)


class TestTheClosedSet:
    @pytest.mark.parametrize("argv", [
        ["git", "push"],
        ["git", "push", "--set-upstream", "origin", "issue-4"],
        ["git", "-C", "/some/repo", "push", "-u", "origin", "grave"],
        ["gh", "pr", "create", "--title", "t", "--body", "b"],
        ["gh", "pr", "merge", "https://github.com/o/r/pull/1", "--squash"],
        ["gh", "issue", "create", "--repo", "o/r", "--title", "t"],
        ["gh", "issue", "comment", "5", "--repo", "o/r", "--body", "x"],
        ["gh", "label", "create", "must-resolve", "--repo", "o/r"],
        "git push origin main",
    ])
    def test_writes_are_writes(self, argv):
        assert is_github_write(argv)

    @pytest.mark.parametrize("argv", [
        ["git", "fetch", "origin"],
        ["git", "status", "--porcelain"],
        ["git", "-C", "/some/repo", "remote", "get-url", "origin"],
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        ["gh", "pr", "view", "https://github.com/o/r/pull/1", "--json", "state"],
        ["gh", "issue", "list", "--repo", "o/r", "--label", "must-resolve"],
        ["gh", "issue", "view", "4", "--json", "title,body"],
        ["gh", "auth", "status"],
        ["pytest", "-q"],
        [],
    ])
    def test_reads_are_not(self, argv):
        assert not is_github_write(argv)


class TestTheSwitch:
    def test_live_when_unset(self):
        assert inert_reason() == ""
        assert suppress_if_inert(["git", "push"]) is None

    def test_context_sets_then_restores(self):
        with inert_github_writes("replay"):
            assert inert_reason() == "replay"
            result = suppress_if_inert(["gh", "pr", "create"], log=lambda _: None)
            assert result is not None
            assert result.returncode == 0
            assert result.stdout.startswith(SUPPRESSED_MARK)
            assert "replay" in result.stdout
        assert inert_reason() == ""

    def test_restores_a_previous_value(self, monkeypatch):
        monkeypatch.setenv(INERT_ENV, "outer")
        with inert_github_writes("inner"):
            assert inert_reason() == "inner"
        assert inert_reason() == "outer"

    def test_reads_still_run_under_inert(self):
        with inert_github_writes("replay"):
            assert suppress_if_inert(["gh", "issue", "list"], log=lambda _: None) is None

    def test_blank_reason_is_refused(self):
        with pytest.raises(ValueError):
            with inert_github_writes("  "):
                pass


class TestRunCommand:
    def test_a_write_is_not_spawned_under_inert(self, monkeypatch):
        from assemblyzero.utils import shell

        def never(*_args, **_kwargs):
            raise AssertionError("subprocess.run was called for a GitHub write under inert")

        monkeypatch.setattr(shell.subprocess, "run", never)
        with inert_github_writes("replay"):
            result = shell.run_command(["git", "push", "origin", "issue-4"])
        assert result.returncode == 0
        assert SUPPRESSED_MARK in result.stdout

    def test_a_read_is_spawned_under_inert(self, monkeypatch):
        from assemblyzero.utils import shell

        seen: list[list[str]] = []

        def fake_run(command, **_kwargs):
            seen.append(list(command))
            return subprocess.CompletedProcess(command, 0, "main\n", "")

        monkeypatch.setattr(shell.subprocess, "run", fake_run)
        with inert_github_writes("replay"):
            result = shell.run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"])
        assert result.stdout == "main\n"
        assert seen == [["git", "rev-parse", "--abbrev-ref", "HEAD"]]

    def test_a_write_is_spawned_when_live(self, monkeypatch):
        """The control: with the switch off, a push reaches subprocess."""
        from assemblyzero.utils import shell

        seen: list[list[str]] = []

        def fake_run(command, **_kwargs):
            seen.append(list(command))
            return subprocess.CompletedProcess(command, 0, "", "")

        monkeypatch.setattr(shell.subprocess, "run", fake_run)
        shell.run_command(["git", "push", "origin", "issue-4"])
        assert seen == [["git", "push", "origin", "issue-4"]]


def _conflict() -> dict:
    return {
        "criterion_a": "Live OS state",
        "criterion_b": "Memory % exactly matches psutil.virtual_memory().percent",
        "diverging_situation": "memory moves between the collector's read and the test's",
    }


def _live_runner(created_url: str = "https://github.com/o/r/issues/99\n"):
    """A fake gh/git that answers the reads and records the writes."""
    calls: list[list[str]] = []

    def runner(args):
        calls.append(list(args))
        if args[:2] == ["git", "-C"] and "remote" in args:
            return subprocess.CompletedProcess(args, 0, "https://github.com/o/r.git\n", "")
        if args[:3] == ["gh", "issue", "list"]:
            return subprocess.CompletedProcess(args, 0, "[]", "")
        if args[:3] == ["gh", "issue", "create"]:
            return subprocess.CompletedProcess(args, 0, created_url, "")
        return subprocess.CompletedProcess(args, 0, "", "")

    return runner, calls


class TestTheFiler:
    def test_files_nothing_under_inert(self, tmp_path):
        from assemblyzero.speedrun import must_resolve as mr

        calls: list[list[str]] = []

        def runner(args):
            calls.append(list(args))
            raise AssertionError(f"gh was invoked under inert: {args}")

        with inert_github_writes("replay"):
            result = mr.file_must_resolve(
                tmp_path, 4, _conflict(), runner=runner, log=lambda _: None
            )

        assert result.ok
        assert result.action == "suppressed"
        assert result.issue_number is None
        assert result.detail == "replay"
        assert calls == []

        rows = [
            json.loads(line)
            for line in mr.filed_ledger_path(tmp_path).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(rows) == 1
        assert rows[0]["suppressed"] == "replay"
        assert rows[0]["number"] is None
        assert rows[0]["fingerprint"] == result.fingerprint
        # The launcher's reader keys on the number, so it never counts this.
        assert mr.read_filed(tmp_path) == []

    def test_still_files_when_live(self, tmp_path):
        """The control: the same call with the switch off files the issue."""
        from assemblyzero.speedrun import must_resolve as mr

        runner, calls = _live_runner()
        result = mr.file_must_resolve(
            tmp_path, 4, _conflict(), runner=runner, log=lambda _: None
        )
        assert result.action == "filed"
        assert result.issue_number == 99
        assert any(c[:3] == ["gh", "issue", "create"] for c in calls)
        assert [row["number"] for row in mr.read_filed(tmp_path)] == [99]

    def test_the_filers_own_runner_honours_the_switch(self, monkeypatch):
        from assemblyzero.speedrun import must_resolve as mr

        def never(*_args, **_kwargs):
            raise AssertionError("subprocess.run was called for a GitHub write under inert")

        monkeypatch.setattr(mr.subprocess, "run", never)
        with inert_github_writes("replay"):
            result = mr._default_runner(["gh", "issue", "create", "--repo", "o/r"])
        assert result.returncode == 0
        assert SUPPRESSED_MARK in result.stdout


def _load_replay_run():
    path = ROOT / "tools" / "replay_run.py"
    spec = importlib.util.spec_from_file_location("replay_run_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TestTheReplayRunner:
    def test_main_collects_under_inert(self, tmp_path, monkeypatch, capsys):
        replay_run = _load_replay_run()
        observed: list[str] = []

        def fake_collect(_args):
            observed.append(inert_reason())
            return [], ["nothing recorded"]

        monkeypatch.setattr(replay_run, "collect", fake_collect)
        clone = tmp_path / "clone"
        clone.mkdir()
        rc = replay_run.main([
            "--recording", str(tmp_path), "--clone", str(clone), "--issue", "4",
        ])
        assert observed == ["replay"]
        assert inert_reason() == ""
        assert rc == 0

    def test_the_graph_is_streamed_under_inert(self):
        """Pinned at the source: the stream loop sits inside the context, so a
        caller of replay_spec_stage that bypasses main is covered too."""
        source = (ROOT / "tools" / "replay_run.py").read_text(encoding="utf-8")
        stream_at = source.index("for event in graph.stream(state, config):")
        guard_at = source.rindex('with inert_github_writes("replay"):', 0, stream_at)
        assert stream_at - guard_at < 400, "the inert guard must sit directly above the stream loop"
