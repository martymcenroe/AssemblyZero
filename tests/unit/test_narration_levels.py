"""Follower view levels: terse/verbose with live switching (#2159).

The roll emits everything once; verbosity is a property of the VIEW. These
pin the line-buffered filter, the emit-once invariant (the log on disk is
identical whichever level watched), the live toggle, and the flag plumb.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import speedrun_roll as sr  # noqa: E402


class TestTheFilter:
    def test_terse_keeps_actionable_lines_and_drops_detail(self):
        view = sr._NarrationView("terse")
        out = view.feed("n", (
            "2026-08-09 15:10 LAUNCH base=run-17 -> x.log\n"
            "some model chatter about tokens\n"
            "NODE [3/11] requirements consistency gate -- checking\n"
            "more incidental detail\n"
            "ROLL BLOCKED: issue(s) #1 await an operator ruling.\n"
        ))
        assert "LAUNCH" in out and "NODE [3/11]" in out and "ROLL BLOCKED" in out
        assert "chatter" not in out and "incidental" not in out

    def test_verbose_passes_everything_through(self):
        view = sr._NarrationView("verbose")
        chunk = "anything at all\npartial tail without newline"
        assert view.feed("n", chunk) == chunk

    def test_a_line_split_across_drains_is_judged_once_whole(self):
        """A drain can end mid-line; the filter must reassemble before
        judging, or NODE lines get dropped when cut at the wrong byte."""
        view = sr._NarrationView("terse")
        first = view.feed("n", "NOD")
        second = view.feed("n", "E [1/2] load input -- reads the issue\n")
        assert first == ""
        assert "NODE [1/2]" in second

    def test_streams_buffer_independently(self):
        view = sr._NarrationView("terse")
        view.feed("narration", "NOD")
        out = view.feed("roll", "NODE [2/2] finalize -- saves\n")
        assert "NODE [2/2]" in out
        out = view.feed("narration", "E [1/2] load input -- reads\n")
        assert "NODE [1/2]" in out

    def test_toggle_flips_and_clears_partials(self):
        view = sr._NarrationView("terse")
        view.feed("n", "half a li")
        assert view.toggle() == "verbose"
        assert view.feed("n", "detail now visible\n") == "detail now visible\n"
        assert view.toggle() == "terse"


class TestTheKeyToggle:
    def test_v_toggles_and_announces(self, capsys, monkeypatch):
        keys = iter(["v"])

        class _FakeMsvcrt:
            @staticmethod
            def kbhit():
                return bool(keys.__length_hint__())

            @staticmethod
            def getwch():
                return next(keys)

        monkeypatch.setitem(sys.modules, "msvcrt", _FakeMsvcrt)
        view = sr._NarrationView("verbose")

        sr._poll_view_keys(view)

        assert view.level == "terse"
        assert "narration level: terse" in capsys.readouterr().out

    def test_other_keys_are_ignored(self, monkeypatch):
        keys = iter(["x", "q"])

        class _FakeMsvcrt:
            @staticmethod
            def kbhit():
                return bool(keys.__length_hint__())

            @staticmethod
            def getwch():
                return next(keys)

        monkeypatch.setitem(sys.modules, "msvcrt", _FakeMsvcrt)
        view = sr._NarrationView("terse")

        sr._poll_view_keys(view)

        assert view.level == "terse"


class TestFollowIntegration:
    def test_terse_follow_filters_the_stream_and_the_log_stays_complete(
        self, tmp_path, capsys
    ):
        runs = tmp_path / "runs"
        runs.mkdir()
        narration = runs / "detached-launcher.log"
        narration.write_bytes(b"")

        def _flip():
            with narration.open("ab") as fh:
                fh.write(b"boring detail line\nSTORM BACKOFF 15m\n")
            return "Ready"

        statuses = iter([lambda: "Running", _flip])
        with patch.object(sr, "_task_status", lambda: next(statuses)()), \
                patch.object(sr, "_task_last_result", lambda: 0), \
                patch.object(sr, "_poll_view_keys", lambda v: None), \
                patch.object(sr.time, "sleep", lambda s: None):
            sr.follow_roll(runs, level="terse")

        out = capsys.readouterr().out
        assert "STORM BACKOFF" in out
        assert "boring detail line" not in out
        on_disk = narration.read_bytes().decode()
        assert "boring detail line" in on_disk, "the view filters; the log never does"

    def test_the_narration_flag_reaches_the_follower(self, tmp_path):
        seen = {}

        def _follow(log_dir, **kw):
            seen.update(kw)
            return 0

        repo = tmp_path / "r"
        (repo / ".git").mkdir(parents=True)
        with patch.object(sr, "follow_roll", _follow), \
                patch.object(sr.sys, "platform", "win32"):
            sr.main(["--repo", str(repo), "--follow", "--narration", "terse"])

        assert seen.get("level") == "terse"
