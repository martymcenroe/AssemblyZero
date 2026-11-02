"""The verdict half of tools/agy_agent_probe.py (#4531).

The probe's calls are real and run by hand; what is tested here is everything
that decides whether a check passes, so a wrong reading cannot pass as T2 or T3.
"""

import importlib.util
import json
from pathlib import Path

TOOL = Path(__file__).resolve().parents[2] / "tools" / "agy_agent_probe.py"
spec = importlib.util.spec_from_file_location("agy_agent_probe", TOOL)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

USER_INPUT = {"type": "USER_INPUT", "content": "run whoami"}
HOOK = {"type": "EPHEMERAL_MESSAGE", "content": "Checks that ran ..."}
REFUSAL = {"type": "PLANNER_RESPONSE", "content": "I cannot run commands."}


def test_one_turn_with_no_tool_passes():
    ok, seen = probe.turn_verdict([USER_INPUT, HOOK, REFUSAL])
    assert ok is True
    assert seen.startswith("1 model turn(s), 0 tool call(s), 0 tool step(s)")


def test_a_tool_call_fails():
    calling = dict(REFUSAL, tool_calls=[{"name": "run_command", "args": {}}])
    ok, seen = probe.turn_verdict([USER_INPUT, calling])
    assert ok is False and "1 tool call(s)" in seen


def test_a_tool_step_fails():
    ok, _ = probe.turn_verdict([USER_INPUT, REFUSAL, {"type": "GENERIC"}, REFUSAL])
    assert ok is False


def test_a_second_turn_fails():
    ok, seen = probe.turn_verdict([USER_INPUT, REFUSAL, REFUSAL])
    assert ok is False and seen.startswith("2 model turn(s)")


def test_no_transcript_fails():
    ok, seen = probe.turn_verdict([])
    assert ok is False and "not found" in seen


def test_a_reply_carrying_the_user_name_fails():
    ok, seen = probe.whoami_verdict([USER_INPUT, REFUSAL], "The output is mcwiz.", "mcwiz")
    assert ok is False and "user name" in seen


def test_a_refusal_without_the_user_name_passes():
    ok, _ = probe.whoami_verdict([USER_INPUT, REFUSAL], "I cannot run commands.", "mcwiz")
    assert ok is True


def test_hook_messages_are_counted():
    assert probe.hook_messages([USER_INPUT, HOOK, REFUSAL]) == 1
    assert probe.hook_messages([USER_INPUT, REFUSAL]) == 0


def test_the_transcript_is_read_by_conversation_id(tmp_path):
    logs = tmp_path / "conv-1" / ".system_generated" / "logs"
    logs.mkdir(parents=True)
    rows = [USER_INPUT, REFUSAL]
    (logs / "transcript_full.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\nnot json\n", encoding="utf-8")
    assert probe.read_transcript("conv-1", brain=tmp_path) == rows
    assert probe.read_transcript("missing", brain=tmp_path) == []


def test_the_empty_prompt_is_the_transports_shape_with_nothing_in_it():
    prompt = probe.compose("gemini-3.8-flash-high", "", "")
    assert prompt == (
        "You are gemini-3.8-flash-high.\n\n<system_instruction>\n\n</system_instruction>\n\n"
        "<user_content>\n\n</user_content>"
    )


def test_the_sized_prompt_is_2141_characters():
    exit_probe = probe._exit_probe()
    prompt = exit_probe.compose_prompt(
        "gemini-3.8-flash-high", exit_probe.build_content(probe.SIZED_CONTENT_CHARS))
    assert len(prompt) == 2_141


def test_an_unknown_check_is_refused_before_any_call(capsys):
    assert probe.main(["--checks", "empty,nonsense"]) == 1
    assert "unknown check" in capsys.readouterr().err
