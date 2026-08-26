"""The operator-wait state shouts, and only at a terminal (#2527).

The operator's words after the gate's first live loop: "it wasn't clear to me
from the terminal output that my judgment was requested... it looks kinda
like the counting it is doing when an LLM is slow." Both states printed white
ticks at one cadence. These tests pin the repair: the waiting surfaces render
amber on a TTY and verbatim into files, the stage tick says whose turn it is
while a gate has declared an operator wait, and the treatment lives in
``operator_wait`` — the class — not in the visual gate alone.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from assemblyzero.core import operator_wait
from assemblyzero.core.stage_watchdog import StageWatchdog
from assemblyzero.visual_gate import bundle as bundle_mod
from assemblyzero.visual_gate.server import wait_for_feedback


@pytest.fixture(autouse=True)
def _no_leaked_wait():
    """Every test starts and ends outside an operator wait."""
    operator_wait.end()
    yield
    operator_wait.end()


class _Tty(io.StringIO):
    def isatty(self) -> bool:
        return True


class TestPaint:
    def test_a_tty_gets_amber(self):
        painted = operator_wait.paint("hello", stream=_Tty())
        assert painted.startswith("\x1b[33;1m")
        assert painted.endswith("\x1b[0m")
        assert "hello" in painted

    def test_a_file_gets_the_text_verbatim(self):
        # A log file must not accumulate escape codes.
        assert operator_wait.paint("hello", stream=io.StringIO()) == "hello"

    def test_a_stream_without_isatty_gets_the_text_verbatim(self):
        assert operator_wait.paint("hello", stream=object()) == "hello"


class TestTheDeclaredWait:
    def test_begin_and_end_bracket_the_state(self):
        assert operator_wait.active() is None
        operator_wait.begin(url="http://127.0.0.1:1/", note="round-001")
        assert operator_wait.active() == {
            "url": "http://127.0.0.1:1/", "note": "round-001",
        }
        operator_wait.end()
        assert operator_wait.active() is None

    def test_end_is_idempotent(self):
        operator_wait.end()
        operator_wait.end()
        assert operator_wait.active() is None


class TestTheStageTickSaysWhoseTurn:
    def test_outside_a_wait_the_tick_is_unchanged(self):
        line = StageWatchdog("visual", nominal_seconds=None).status_line(120)
        assert line == "    [STAGE] visual running 120s"

    def test_inside_a_wait_the_tick_names_the_operator(self):
        operator_wait.begin(url="http://127.0.0.1:1/")
        line = StageWatchdog("visual", nominal_seconds=None).status_line(120)
        assert "awaiting OPERATOR" in line

    def test_inside_a_wait_no_slow_or_stalled_verdict_is_issued(self):
        """Elapsed time during an operator wait measures the operator's
        attention, not the stage's health — a 40-minute think must not print
        STALLED as if the machine were sick."""
        operator_wait.begin(url="http://127.0.0.1:1/")
        line = StageWatchdog("spec", nominal_seconds=10.0).status_line(600)
        assert "awaiting OPERATOR" in line
        assert "SLOW" not in line
        assert "STALLED" not in line

    def test_the_verdicts_return_when_the_wait_ends(self):
        operator_wait.begin()
        operator_wait.end()
        line = StageWatchdog("spec", nominal_seconds=10.0).status_line(600)
        assert "STALLED" in line


class TestTheWaitingLine:
    def _round(self, tmp_path) -> Path:
        d = tmp_path / "round-001"
        d.mkdir()
        return d

    def test_the_reminder_says_the_judgment_is_requested_with_the_url(self, tmp_path):
        round_dir = self._round(tmp_path)
        bundle_mod.write_pending(round_dir, "http://127.0.0.1:9999/")
        lines: list[str] = []
        with pytest.raises(TimeoutError):
            wait_for_feedback(
                round_dir, poll_seconds=0.01, reminder_every=0.02,
                deadline=0.2, log=lines.append,
            )
        reminders = [line for line in lines if "AWAITING OPERATOR" in line]
        assert reminders, lines
        assert "http://127.0.0.1:9999/" in reminders[0]
        assert "judgment is requested" in reminders[0]

    def test_the_wait_declares_itself_and_clears_on_exit(self, tmp_path):
        """wait_for_feedback brackets the process-wide state even when it
        leaves by exception — the finally is the contract."""
        round_dir = self._round(tmp_path)
        seen: list[dict | None] = []

        def probe(_line: str) -> None:
            seen.append(operator_wait.active())

        with pytest.raises(TimeoutError):
            wait_for_feedback(
                round_dir, poll_seconds=0.01, reminder_every=0.02,
                deadline=0.1, log=probe,
            )
        assert any(s is not None for s in seen), "the wait never declared itself"
        assert operator_wait.active() is None, "the wait leaked past its exit"

    def test_no_escape_codes_reach_a_non_tty_log(self, tmp_path):
        round_dir = self._round(tmp_path)
        lines: list[str] = []
        with pytest.raises(TimeoutError):
            wait_for_feedback(
                round_dir, poll_seconds=0.01, reminder_every=0.02,
                deadline=0.1, log=lines.append,
            )
        # log=lines.append writes through no TTY; paint() consulted stdout,
        # which pytest captures (not a TTY), so the lines carry no ANSI.
        assert all("\x1b[" not in line for line in lines), lines
