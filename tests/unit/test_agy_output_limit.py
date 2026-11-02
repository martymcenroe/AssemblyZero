"""An answer agy cut at its output token limit is named as that, never used (#4543).

On 2026-11-02 three implementation-spec drafting calls ended with
``"status": "ERROR"`` and a non-empty ``response``. agy's own record of each
conversation (``brain/<id>/.system_generated/logs/transcript.jsonl``) shows the
same five steps: the prompt, a hook message, a model turn stopped at 65,531 or
65,532 output tokens (thinking included), an ``ERROR_MESSAGE`` step in which agy
tells the model "Your previous response was cut off because it exceeded the
output token limit / Please continue from where you left off, keeping your
response shorter / Retries remaining: 3", and a second model turn. The
envelope's ``usage.output_tokens`` is the sum of the two turns.

The fixtures below keep that shape and those numbers; the answer text is
invented. The transport used to fail these as ``agy status 'ERROR'`` with 400
characters of the answer, classified UNKNOWN.
"""
from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.core import gemini_client as gc
from assemblyzero.core.gemini_client import GeminiErrorType

HOOKS = "/home/someone/.gemini/config/hooks.json"
CONVERSATION = "986f610b-9cd1-4262-a410-54c533786fb6"
AGY_CUT_NOTICE = (
    "Your previous response was cut off because it exceeded the output token limit\n"
    "Please continue from where you left off, keeping your response shorter\n"
    "Retries remaining: 3"
)
#: Invented, in the shape of the first call's answer: an unfinished first turn.
ANSWER = (
    "\n```\nLet's check if lines 722-730 in CURRENT SPEC are unique:\n"
    "Yes, the row occurs exactly once.\n\n<<<<<<< SEARCH\ndef test_one():\n"
    "    assert quota_left() > 0  # a timeout here is a 503\n=======\n"
)
USAGE = {
    "input_tokens": 103330, "output_tokens": 74905, "thinking_tokens": 67816,
    "cache_read_tokens": 28757, "total_tokens": 178235,
}


def envelope(status: str = "ERROR", response: str = ANSWER, **extra) -> str:
    return json.dumps({
        "conversation_id": CONVERSATION, "status": status,
        "response": response, "usage": USAGE, **extra,
    })


def cut_record() -> list[dict]:
    """agy's record of the first call, as its transcript.jsonl holds it."""
    return [
        {"step_index": 0, "source": "USER_EXPLICIT", "type": "USER_INPUT", "status": "DONE"},
        {"step_index": 1, "source": "SYSTEM_SDK", "type": "EPHEMERAL_MESSAGE", "status": "DONE"},
        {"step_index": 2, "source": "MODEL", "type": "PLANNER_RESPONSE", "status": "DONE",
         "input_tokens": 25522, "cache_read_tokens": 0, "output_tokens": 65531},
        {"step_index": 3, "source": "SYSTEM", "type": "ERROR_MESSAGE", "status": "DONE",
         "error": AGY_CUT_NOTICE, "content": "Error: " + AGY_CUT_NOTICE},
        {"step_index": 4, "source": "MODEL", "type": "PLANNER_RESPONSE", "status": "DONE",
         "input_tokens": 77808, "cache_read_tokens": 28757, "output_tokens": 9374},
    ]


def one_turn_record() -> list[dict]:
    return [step for step in cut_record() if step["step_index"] <= 2]


def write_record(home, steps: list[dict]) -> None:
    path = home / gc.AGY_TRANSCRIPT_RELATIVE.format(conversation_id=CONVERSATION)
    path.parent.mkdir(parents=True)
    path.write_text("".join(json.dumps(s) + "\n" for s in steps), encoding="utf-8")


def call(stdout: str, home, stderr: str = "") -> tuple[bool, str, str]:
    """One ``_agy_once`` on a Linux agy whose home is ``home``."""
    client = gc.GeminiClient(model="gemini-3.8-flash-high")
    client._agy_cli = "/stand-in/agy"
    client._agy_hooks_file = lambda: HOOKS
    proc = MagicMock()
    proc.pid = 1
    proc.communicate.return_value = (stdout, stderr)
    proc.returncode = 0
    with patch.object(gc.subprocess, "Popen", return_value=proc), \
            patch.object(gc.Path, "home", classmethod(lambda cls: home)):
        return client._agy_once("prompt", 30, {})


# --- T2: the envelope of these three calls is named for its cause ----------

def test_t2_the_cut_envelope_is_named_as_cut_at_the_output_limit(tmp_path):
    write_record(tmp_path, cut_record())
    ok, text, err = call(envelope(), tmp_path)
    assert ok is False and text == ""
    assert err.startswith(gc.AGY_OUTPUT_LIMIT_FAILURE)
    assert "Cut turn: 65,531 output tokens" in err
    assert "opens with the cut turn, so it is not one complete answer" in err
    assert CONVERSATION in err  # where agy's record is


def test_t2_the_answer_is_never_in_the_failure(tmp_path):
    write_record(tmp_path, cut_record())
    _, _, err = call(envelope(), tmp_path)
    assert "Let's check if lines" not in err and "SEARCH" not in err
    assert f"answer: {len(ANSWER):,} characters" in err


@pytest.mark.parametrize("tokens", [65529, 65503])
def test_the_first_hundred_characters_carry_no_number(tokens):
    """``invoke`` keeps 100 characters of each attempt, and the stage retry
    reads "503" or "529" there as a capacity outage."""
    from assemblyzero.core.errors import is_capacity_message

    steps = cut_record()
    steps[2]["output_tokens"] = tokens
    reply = json.loads(envelope())
    for steps_seen in (steps, one_turn_record(), None):
        failure = gc.status_failure("ERROR", reply, "", "/r/0f4290aa-503", steps_seen)
        assert not any(ch.isdigit() for ch in failure[:100]), failure[:100]
        assert not is_capacity_message(failure[:100])


def test_t2_invoke_classifies_the_cut_and_never_returns_the_answer():
    """Classified OUTPUT_LIMIT, not UNKNOWN; every attempt said; no answer used.

    The answer mentions a quota, a timeout and a 503, and the counts in the
    failure text are the kind that can hold "429": none of it may reach the
    word classifier.
    """
    failure = gc.status_failure(
        "ERROR", json.loads(envelope()), "", "/home/x/transcript.jsonl", cut_record(),
    )
    assert failure.startswith(gc.AGY_OUTPUT_LIMIT_FAILURE)
    client = gc.GeminiClient(model="gemini-3.8-flash-high")
    client._agy_cli = "/stand-in/agy"
    with patch.object(client, "_invoke_via_cli", return_value=(False, "", failure)) as sent, \
            patch.object(gc.time, "sleep"), patch.object(gc, "_loud") as loud:
        result = client.invoke("system", "content")
    assert result.success is False and result.response is None
    assert result.error_type == GeminiErrorType.OUTPUT_LIMIT
    assert sent.call_count == gc.MAX_RETRIES_PER_CREDENTIAL
    said = " ".join(str(c.args[0]) for c in loud.call_args_list)
    assert "(OUTPUT_LIMIT)" in said and "UNKNOWN" not in said
    assert gc.AGY_OUTPUT_LIMIT_FAILURE in result.error_message


def test_a_retry_that_answers_is_used():
    failure = gc.status_failure(
        "ERROR", json.loads(envelope()), "", "/home/x/transcript.jsonl", cut_record(),
    )
    client = gc.GeminiClient(model="gemini-3.8-flash-high")
    client._agy_cli = "/stand-in/agy"
    replies = [(False, "", failure), (True, "the whole answer", "")]
    with patch.object(client, "_invoke_via_cli", side_effect=replies), \
            patch.object(gc.time, "sleep"), patch.object(gc, "_loud"):
        result = client.invoke("system", "content")
    assert result.success is True and result.response == "the whole answer"
    assert result.attempts == 2


# --- an ERROR agy's record does not explain stays an unknown failure ------

def test_an_error_with_no_cut_in_the_record_is_not_called_a_cut(tmp_path):
    write_record(tmp_path, one_turn_record())
    ok, _, err = call(envelope(), tmp_path)
    assert ok is False
    assert not err.startswith(gc.AGY_OUTPUT_LIMIT_FAILURE)
    assert err.startswith("agy status 'ERROR'")
    assert "shows no output-limit cut" in err


def test_an_unreadable_record_is_said_and_not_guessed(tmp_path):
    ok, _, err = call(envelope(), tmp_path)  # no record written
    assert ok is False
    assert err.startswith("agy status 'ERROR'")
    assert "agy's record could not be read" in err and "FileNotFoundError" in err


def test_a_broken_record_is_said_and_not_guessed(tmp_path):
    path = tmp_path / gc.AGY_TRANSCRIPT_RELATIVE.format(conversation_id=CONVERSATION)
    path.parent.mkdir(parents=True)
    path.write_text("not json\n", encoding="utf-8")
    _, _, err = call(envelope(), tmp_path)
    assert "agy's record could not be read" in err and "is not JSON" in err


def test_agys_stderr_is_kept_in_the_failure(tmp_path):
    write_record(tmp_path, one_turn_record())
    _, _, err = call(envelope(), tmp_path, stderr="error: stream reset by peer\n")
    assert err.endswith("stderr: error: stream reset by peer")
    assert gc.status_failure_words(err).startswith('{"status": "ERROR"}')


def invoke_on(failure: str):
    """``invoke`` over attempts that all fail with ``failure``: (result, attempts)."""
    client = gc.GeminiClient(model="gemini-3.8-flash-high")
    client._agy_cli = "/stand-in/agy"
    with patch.object(client, "_invoke_via_cli", return_value=(False, "", failure)) as sent, \
            patch.object(gc.time, "sleep"), patch.object(gc, "_loud"):
        return client.invoke("system", "content"), sent.call_count


def test_ids_paths_and_counts_in_a_status_failure_are_not_read_as_words():
    """A count or an id holding "429", or a path holding "quota", is not a rate limit."""
    reply = json.loads(envelope())
    reply["conversation_id"] = "0f4290aa-0000-4000-8000-000000005030"
    reply["usage"] = {"input_tokens": 104290, "output_tokens": 5030}
    failure = gc.status_failure("ERROR", reply, "", "/home/quota/429/transcript.jsonl", one_turn_record())
    assert failure.startswith(gc.AGY_STATUS_FAILURE)
    result, attempts = invoke_on(failure)
    assert result.error_type == GeminiErrorType.UNKNOWN
    assert attempts == gc.MAX_RETRIES_PER_CREDENTIAL


def test_an_answer_naming_a_quota_is_not_a_quota_failure(tmp_path):
    """The old failure carried the answer, and the classifier read its words."""
    write_record(tmp_path, one_turn_record())
    _, _, err = call(envelope(response="RESOURCE_EXHAUSTED: quota 429"), tmp_path)
    assert "RESOURCE_EXHAUSTED" not in err
    result, _ = invoke_on(err)
    assert result.error_type == GeminiErrorType.UNKNOWN


def test_agys_own_stderr_still_classifies_a_status_failure():
    reply = json.loads(envelope())
    failure = gc.status_failure("ERROR", reply, "error: Individual quota reached.", "/r", None)
    result, attempts = invoke_on(failure)
    assert result.error_type == GeminiErrorType.QUOTA_EXHAUSTED and attempts == 1


def test_a_field_agy_adds_to_its_envelope_still_classifies_a_status_failure():
    reply = json.loads(envelope(error="RESOURCE_EXHAUSTED"))
    failure = gc.status_failure("ERROR", reply, "", "/r", None)
    assert "RESOURCE_EXHAUSTED" in gc.status_failure_words(failure)
    result, attempts = invoke_on(failure)
    assert result.error_type == GeminiErrorType.QUOTA_EXHAUSTED and attempts == 1


# --- reading agy's record ---------------------------------------------------

def test_the_record_path_is_agys_brain_under_the_home():
    path = gc.agy_transcript_file("/home/someone", CONVERSATION)
    assert path == (
        f"/home/someone/.gemini/antigravity-cli/brain/{CONVERSATION}"
        "/.system_generated/logs/transcript.jsonl"
    )


@pytest.mark.parametrize("bad", ["../../etc/passwd", "", "not-a-uuid", f"{CONVERSATION}/.."])
def test_a_conversation_id_that_is_not_a_uuid_makes_no_path(bad):
    with pytest.raises(ValueError):
        gc.agy_transcript_file("/home/someone", bad)


def test_an_envelope_naming_no_conversation_reads_nothing():
    client = gc.GeminiClient(model="gemini-3.8-flash-high")
    client._agy_cli = "/stand-in/agy"
    with pytest.raises(gc.AgyRecordUnreadable, match="names no conversation"):
        client._agy_record(None)


def test_a_wsl_cat_that_fails_is_said():
    client = gc.GeminiClient(model="gemini-3.8-flash-high")
    client._agy_cli = gc.AGY_WSL_PREFIX + "/home/someone/.local/bin/agy"
    failed = subprocess.CompletedProcess([], 1, stdout="", stderr="cat: No such file or directory")
    with patch.object(gc, "_wsl_home", return_value="/home/someone"), \
            patch.object(gc.subprocess, "run", return_value=failed), \
            pytest.raises(gc.AgyRecordUnreadable, match="cat exited 1: cat: No such file"):
        client._agy_record(CONVERSATION)


def test_a_wsl_agys_record_is_read_through_wsl():
    client = gc.GeminiClient(model="gemini-3.8-flash-high")
    client._agy_cli = gc.AGY_WSL_PREFIX + "/home/someone/.local/bin/agy"
    body = "".join(json.dumps(s) + "\n" for s in cut_record())
    done = subprocess.CompletedProcess([], 0, stdout=body, stderr="")
    with patch.object(gc, "_wsl_home", return_value="/home/someone"), \
            patch.object(gc.subprocess, "run", return_value=done) as run:
        steps, where = client._agy_record(CONVERSATION)
    expected = gc.agy_transcript_file("/home/someone", CONVERSATION)
    assert run.call_args.args[0] == ["wsl.exe", "--exec", "cat", expected]
    assert where == expected and gc.output_limit_cuts(steps) == [65531]


def test_cuts_are_counted_per_notice():
    steps = cut_record() + [
        {"type": "ERROR_MESSAGE", "error": AGY_CUT_NOTICE},
        {"type": "PLANNER_RESPONSE", "output_tokens": 100},
    ]
    assert gc.output_limit_cuts(steps) == [65531, 9374]
    assert gc.output_limit_cuts(one_turn_record()) == []
    assert gc.output_limit_cuts([{"type": "ERROR_MESSAGE", "error": "other"}]) == []
