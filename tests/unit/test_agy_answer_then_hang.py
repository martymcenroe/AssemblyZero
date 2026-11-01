"""#4509: a call uses agy's answer once it has arrived, whether or not agy exits.

On a 108,943-character prompt agy printed its whole reply at 20.5 s and was still
alive at 120 s, with nothing else in its session. The transport waited for the
exit, threw the answer away at 300 s, and called it a capacity failure, twice,
which ended a real implementation run at its first file.

Each test here runs a real process, a stand-in for agy, because the defect is in
what happens between a process and its pipes. A mock of `communicate` is the
thing that hid it.
"""

from __future__ import annotations

import json
import os
import sys
import textwrap
import time
from pathlib import Path

import pytest

import assemblyzero.core.gemini_client as gc
from assemblyzero.core.gemini_client import GeminiClient

REPLY = {
    "status": "SUCCESS",
    "response": "the model's answer",
    "usage": {"input_tokens": 3, "output_tokens": 4},
}


def _stand_in(tmp_path: Path, body: str) -> list[str]:
    script = tmp_path / "stand_in_agy.py"
    script.write_text(
        "import json, os, sys, time\n"
        "sys.stdin.read()\n"
        f"PID_FILE = {str(tmp_path / 'pid')!r}\n"
        "open(PID_FILE, 'w').write(str(os.getpid()))\n"
        + textwrap.dedent(body),
        encoding="utf-8",
    )
    return [sys.executable, str(script)]


@pytest.fixture
def call(tmp_path, monkeypatch):
    """One `_agy_once` against a stand-in, with the settle time short."""
    monkeypatch.setattr(gc, "AGY_ANSWER_SETTLE_SECONDS", 0.5)
    monkeypatch.setattr(gc, "AGY_ANSWER_POLL_SECONDS", 0.05)
    monkeypatch.setattr(GeminiClient, "_find_agy_cli", lambda self: "agy")

    def run(body: str, timeout: float = 20.0):
        argv = _stand_in(tmp_path, body)
        monkeypatch.setattr(GeminiClient, "_agy_argv", lambda self, cwd, *tail: argv)
        client = GeminiClient(model="gemini-3.8-flash-high")
        spent: dict = {}
        started = time.monotonic()
        result = client._agy_once("the prompt", timeout, spent)
        return result, spent, time.monotonic() - started

    return run


def _printed(reply: dict | str) -> str:
    text = reply if isinstance(reply, str) else json.dumps(reply)
    return f"print({text!r}, flush=True)\n"


def _is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return Path(f"/proc/{pid}/stat").read_text().split()[2] != "Z"


class TestAnAnswerAndNoExit:
    HANG = "time.sleep(600)\n"

    def test_t1_the_answer_is_used_and_the_call_returns_in_seconds(self, call, tmp_path):
        (ok, text, error), spent, took = call(_printed(REPLY) + self.HANG)

        assert (ok, text, error) == (True, "the model's answer", "")
        assert took < 10, "it waited for an exit that was never coming"
        assert spent["usage"] == REPLY["usage"]

    @pytest.mark.skipif(os.name == "nt", reason="reads /proc")
    def test_t1_the_process_is_gone_when_the_call_returns(self, call, tmp_path):
        call(_printed(REPLY) + self.HANG)

        assert not _is_alive(int((tmp_path / "pid").read_text()))

    def test_t2_a_bad_status_is_still_a_failed_call(self, call):
        (ok, _, error), _, _ = call(
            _printed({**REPLY, "status": "FAILED"}) + self.HANG
        )

        assert ok is False
        assert "FAILED" in error

    def test_the_failed_exit_of_a_process_we_ended_is_not_held_against_it(self, call):
        (ok, _, error), _, _ = call(_printed(REPLY) + self.HANG)

        assert ok is True
        assert "exited" not in error


class TestWhatNeverEndsACallEarly:
    HANG = "time.sleep(600)\n"

    @pytest.mark.parametrize("output", [
        '{"status": "SUCC',
        "plain text, and more may be coming",
        "Warning: agent not found",
    ])
    def test_t3_unfinished_output_waits_for_the_timeout(self, call, output):
        (ok, _, error), _, took = call(_printed(output) + self.HANG, timeout=3.0)

        assert ok is False
        assert "timeout" in error
        assert took >= 3.0

    def test_t5_silence_times_out(self, call):
        (ok, _, error), _, took = call(self.HANG, timeout=2.0)

        assert ok is False
        assert "timeout" in error
        assert took >= 2.0

    def test_a_reply_that_grows_is_not_cut_off(self, call):
        body = textwrap.dedent(
            """\
            sys.stdout.write('{"status": "SUCCESS", "response": "first half')
            sys.stdout.flush()
            time.sleep(1.5)
            sys.stdout.write(' and second half", "usage": {}}\\n')
            sys.stdout.flush()
            time.sleep(600)
            """
        )

        (ok, text, _), _, _ = call(body)

        assert ok is True
        assert text == "first half and second half"


class TestAnAgyThatExits:
    def test_t4_a_failed_exit_still_counts(self, call):
        (ok, _, error), _, _ = call(_printed(REPLY) + "sys.exit(1)\n")

        assert ok is False
        assert "exited 1" in error

    def test_a_clean_exit_is_as_it_was(self, call):
        (ok, text, _), _, took = call(_printed(REPLY))

        assert (ok, text) == (True, "the model's answer")
        assert took < 5

    def test_plain_text_and_an_exit_is_as_it_was(self, call):
        (ok, text, _), _, _ = call(_printed("just text"))

        assert (ok, text) == (True, "just text")

    def test_a_broken_reply_still_raises(self, call):
        with pytest.raises(RuntimeError, match="does not parse"):
            call(_printed('{"status": "SUCCESS", broken}'))
