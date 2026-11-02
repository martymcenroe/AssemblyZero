"""The agent check reads agy's own diagnostics, never the model's answer (#4538).

Since #4199 agy's stdout is one line of JSON, ``{"conversation_id", "status",
"response", "usage"}``, and the check read all of it. A review whose answer
mentioned a ``--agent`` flag was failed as "agy did not run as
assemblyzero-text": three paid calls between 2026-10-27 and 2026-11-02, one of
them ``status SUCCESS``. The envelopes below follow the shape those calls left
in the model-call ledger. The warning is agy's own string, from its binary:
``warning: ignoring --agent %q because we are resuming an existing conversation``.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from assemblyzero.core import gemini_client as gc

HOOKS = "/home/someone/.gemini/config/hooks.json"
AGY_WARNING = (
    'warning: ignoring --agent "assemblyzero-text" because we are resuming an '
    "existing conversation"
)
#: A changelog review of the kind that was thrown away: the answer names the flag.
ANSWER_NAMING_THE_FLAG = json.dumps({"warnings": [{
    "version": "2.1.307",
    "change": "Added the --agent flag to pick a custom agent at launch.",
}]}, indent=2)


def _envelope(status: str = "SUCCESS", response: str = ANSWER_NAMING_THE_FLAG, **extra) -> str:
    return json.dumps({
        "conversation_id": "a2cf1cb6-9a12-4178-be7f-eae483cc9d9d",
        "status": status,
        "response": response,
        "usage": {"input_tokens": 111770, "output_tokens": 900},
        **extra,
    })


def _call(stdout: str, stderr: str = "") -> tuple[bool, str, str]:
    client = gc.GeminiClient(model="gemini-3.8-flash-high")
    client._agy_cli = "/stand-in/agy"
    client._agy_hooks_file = lambda: HOOKS
    proc = MagicMock()
    proc.pid = 1
    proc.communicate.return_value = (stdout, stderr)
    proc.returncode = 0
    with patch.object(gc.subprocess, "Popen", return_value=proc):
        return client._agy_once("prompt", 30, {})


def test_t1_an_answer_naming_the_flag_passes():
    ok, text, err = _call(_envelope())
    assert ok is True, err
    assert text == ANSWER_NAMING_THE_FLAG
    assert "--agent" in text


def test_t1_a_failed_call_naming_the_flag_is_failed_for_its_status():
    ok, _text, err = _call(_envelope(status="ERROR"))
    assert ok is False
    assert err.startswith("agy status 'ERROR'")
    assert "did not run as" not in err


def test_t2_agys_warning_on_stderr_still_fails_a_successful_envelope():
    ok, text, err = _call(_envelope(response="a review"), stderr=AGY_WARNING + "\n")
    assert ok is False and text == ""
    assert err == f"agy did not run as assemblyzero-text: {AGY_WARNING}"


def test_t2_agys_warning_on_plain_stdout_still_fails():
    ok, text, err = _call(AGY_WARNING + "\nI ran whoami\n")
    assert ok is False and text == ""
    assert "did not run as assemblyzero-text" in err


def test_a_warning_agy_puts_in_the_envelope_outside_the_answer_fails():
    ok, _text, err = _call(_envelope(response="a review", warnings=[AGY_WARNING]))
    assert ok is False
    assert "did not run as assemblyzero-text" in err


def test_the_diagnostics_never_carry_the_answer():
    reply = json.loads(_envelope())
    seen = gc.agy_diagnostics("stderr line", _envelope(), reply)
    assert ANSWER_NAMING_THE_FLAG not in seen and "--agent" not in seen
    assert "stderr line" in seen and reply["conversation_id"] in seen


def test_without_an_envelope_the_diagnostics_are_both_streams():
    assert gc.agy_diagnostics("err", "plain out", None) == "err\nplain out"
