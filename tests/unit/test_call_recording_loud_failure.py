"""call_recording.py under standard 0034, one test per sweep site (#3772).

The recording is the replay's input: ReplayProvider answers call N with
recorded response N only while the code sends recorded prompt N. A call the
run consumed and the recording lacks makes every replay diverge at it as if
the code had changed, so a write that fails now stops the call, and a line
that is not a call record stops the read, naming the file and the line. A
recording that ends in a write its process died in is still read up to that
line, and refuses the next append. The replay's own refusals are loud where
they happen. Line numbers in the names are ledger 0908's, at its base
``79e18ad1``.
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from assemblyzero.core import call_recording as cr
from assemblyzero.core.call_recording import (
    RecordingProvider,
    ReplayProvider,
    read_calls,
)
from assemblyzero.core.llm_provider import MockProvider


def _call(seq: int, prompt: str = "s") -> dict:
    return {"seq": seq, "system_prompt": prompt, "content": "c", "response": f"r{seq}",
            "success": True, "error_message": ""}


def _write(directory: Path, text: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / cr.CALLS_FILENAME
    path.write_text(text, encoding="utf-8")
    return path


def _lines(*calls: dict) -> str:
    return "".join(json.dumps(c) + "\n" for c in calls)


def _blocked(tmp_path: Path) -> Path:
    """An audit directory that cannot be made: a file stands where it goes."""
    blocker = tmp_path / "blocker"
    blocker.write_text("a file where the directory should be", encoding="utf-8")
    return blocker / "lineage"


class TestTheWrite:
    def test_153_an_append_that_cannot_be_written_raises(self, tmp_path):
        audit_dir = _blocked(tmp_path)

        with pytest.raises(RuntimeError, match="cannot append call 1") as raised:
            cr._append(str(audit_dir), _call(1))
        assert str(audit_dir / cr.CALLS_FILENAME) in str(raised.value)
        assert "Error" in str(raised.value)

    def test_154_the_append_tag_is_gone(self):
        assert "fail-open" not in inspect.getsource(cr._append)

    def test_251_the_call_stops_when_its_line_cannot_be_written(self, tmp_path):
        provider = RecordingProvider(MockProvider(model="review"), audit_dir=str(_blocked(tmp_path)))

        with pytest.raises(RuntimeError, match="calls.jsonl"):
            provider.invoke("s", "c")

    def test_a_clean_recording_reads_back_in_order(self, tmp_path):
        """Kept: what the recorder writes reads back whole and numbered."""
        provider = RecordingProvider(MockProvider(model="review"), audit_dir=str(tmp_path))
        provider.invoke("s", "first")
        provider.invoke("s", "second")

        calls, truncated = read_calls(tmp_path)
        assert [c["seq"] for c in calls] == [1, 2]
        assert [c["content"] for c in calls] == ["first", "second"]
        assert truncated == 0


class TestTheRead:
    def test_179_a_line_that_is_not_json_raises_naming_it(self, tmp_path):
        path = _write(tmp_path, _lines(_call(1)) + "{not json\n" + _lines(_call(3)))

        with pytest.raises(RuntimeError, match="line 2") as raised:
            read_calls(tmp_path)
        assert str(path) in str(raised.value)
        assert "not JSON" in str(raised.value)

    def test_180_the_read_tag_is_gone(self):
        assert "fail-open" not in inspect.getsource(cr.read_calls)

    def test_187_a_line_that_is_not_a_call_record_raises(self, tmp_path):
        _write(tmp_path, _lines(_call(1)) + json.dumps({"stage": "spec"}) + "\n")

        with pytest.raises(RuntimeError, match="line 2") as raised:
            read_calls(tmp_path)
        assert "not a call record" in str(raised.value)

    def test_187_a_json_line_that_is_not_an_object_raises(self, tmp_path):
        _write(tmp_path, "[1, 2]\n")

        with pytest.raises(RuntimeError, match="not a call record"):
            read_calls(tmp_path)

    def test_a_partial_last_line_is_counted_not_read_and_quiet(self, tmp_path, capsys):
        """Kept: a write its process died in has no newline, and its call never
        reached the run. The recording is read up to it, and says it ends in one."""
        _write(tmp_path, _lines(_call(1), _call(2)) + '{"seq": 3, "system_pro')

        calls, truncated = read_calls(tmp_path)
        assert [c["seq"] for c in calls] == [1, 2]
        assert truncated == 1
        assert cr.summarize(tmp_path).unreadable == 1
        assert "ERROR" not in capsys.readouterr().err

    def test_an_absent_recording_is_empty_and_quiet(self, tmp_path, capsys):
        """Kept: a run that predates the recorder has none, which is an answer."""
        assert read_calls(tmp_path) == ([], 0)
        assert capsys.readouterr().err == ""


class TestTheNextSequenceNumber:
    def test_284_a_recording_ending_in_a_partial_write_refuses_the_next_call(self, tmp_path):
        path = _write(tmp_path, _lines(_call(1)) + '{"seq": 2, "system_pro')
        provider = RecordingProvider(MockProvider(model="review"), audit_dir=str(tmp_path))

        with pytest.raises(RuntimeError, match="did not complete") as raised:
            provider.invoke("s", "c")
        assert str(path) in str(raised.value)
        # Nothing was joined onto the partial line.
        assert path.read_text(encoding="utf-8").endswith('"system_pro')


class TestTheReplay:
    def test_353_running_past_the_recording_is_loud(self, capsys):
        replay = ReplayProvider([_call(1)])
        replay.invoke("s", "c")

        second = replay.invoke("s", "c")

        assert second.success is False
        err = capsys.readouterr().err
        assert "ERROR [REPLAY]" in err
        assert "holds 1 call(s)" in err

    def test_372_a_divergence_is_loud(self, capsys):
        replay = ReplayProvider([_call(1, prompt="the recorded prompt")])

        result = replay.invoke("a changed prompt", "c")

        assert result.success is False
        err = capsys.readouterr().err
        assert "ERROR [REPLAY]" in err
        assert "system prompt at call 1" in err

    def test_388_a_recorded_call_with_no_outcome_is_refused(self, capsys):
        call = _call(1)
        del call["success"]
        replay = ReplayProvider([call])

        result = replay.invoke("s", "c")

        assert result.success is False
        assert "success" in result.error_message
        assert result.error_message.startswith("ReplayProvider:")
        assert replay.served == 0
        assert "ERROR [REPLAY]" in capsys.readouterr().err

    def test_a_faithful_replay_is_quiet(self, capsys):
        """Kept: a call that matches the recording is answered with it."""
        result = ReplayProvider([_call(1)]).invoke("s", "c")

        assert result.success is True and result.response == "r1"
        assert capsys.readouterr().err == ""
