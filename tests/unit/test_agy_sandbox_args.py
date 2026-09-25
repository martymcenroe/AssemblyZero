"""Every agy call runs as the pipeline's own tool-less agent, and no call
carries a flag whose mechanism is elevation (#3612, #3608, #3605, #3603; ADR
0233 as amended 2026-09-25).

#3516 added `--sandbox` to every agy call on 2026-09-24. On Windows it makes
agy build an AppContainer for each shell command the model attempts, which
needs an administrator token that agy obtains by relaunching itself elevated:
a UAC dialog naming agy.exe, raised three times in one pipeline call on
2026-09-25. The operator's ruling: no agent ever requests elevation, agents do
not pass --sandbox, and he is never asked to approve anything.

What keeps a call text-only is on the pipeline's side of every call: the
transport writes an agent definition with `tools: []` and
`commandExecutionPolicy: off` into the call's temporary directory and passes
`--agent assemblyzero-text`. Nothing is read from the machine's agy settings.
"""
from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.core import gemini_client as gc

ELEVATING_FLAGS = ("--sandbox", "--dangerously-skip-permissions")
AGENT_RELATIVE = "/.agents/agents/assemblyzero-text/agent.md"


def _client() -> gc.GeminiClient:
    client = gc.GeminiClient(model="gemini-3.1-pro-high")
    client._agy_cli = "/fake/agy"
    return client


def _no_elevating_flag(argv: list[str]) -> bool:
    return not any(
        a == flag or a.startswith(flag + "=") for a in argv for flag in ELEVATING_FLAGS
    )


def _agent_file_in(cwd: str) -> str:
    from pathlib import Path

    return (Path(cwd) / ".agents" / "agents" / "assemblyzero-text" / "agent.md").read_text(
        encoding="utf-8"
    )


def test_the_safety_args_are_empty():
    assert gc.AGY_SAFETY_ARGS == []


def test_the_definition_has_no_tools_and_no_command_execution():
    front = gc.AGY_AGENT_DEFINITION.split("---")[1]
    fields = dict(
        line.split(":", 1) for line in front.strip().splitlines() if ":" in line
    )
    assert fields["name"].strip() == gc.AGY_AGENT_NAME == "assemblyzero-text"
    assert fields["tools"].strip() == "[]"
    # Quoted on purpose: a YAML 1.1 parser reads a bare `off` as false.
    assert fields["commandExecutionPolicy"].strip() == '"off"'
    assert fields["inheritMcp"].strip() == "false"
    yaml = pytest.importorskip("yaml")
    parsed = yaml.safe_load(front)
    assert parsed["tools"] == []
    assert parsed["commandExecutionPolicy"] == "off"


@pytest.mark.usefixtures("windows_pty")
def test_the_pty_path_runs_as_the_agent_written_into_its_cwd(monkeypatch):
    seen = {}

    def spawn(argv, cwd, dimensions, *a, **kw):
        seen["argv"] = list(argv)
        seen["agent_file"] = _agent_file_in(cwd)
        raise TimeoutError("stop here; only the argv and the cwd matter")

    monkeypatch.setitem(sys.modules, "winpty", types.ModuleType("winpty"))
    monkeypatch.setattr(gc, "_spawn_pty_bounded", spawn)

    ok, _text, _err = _client()._invoke_via_cli("sys", "short prompt")

    assert ok is False
    argv = seen["argv"]
    assert argv[:4] == ["/fake/agy", "--agent", "assemblyzero-text", "-p"]
    assert _no_elevating_flag(argv)
    assert seen["agent_file"] == gc.AGY_AGENT_DEFINITION


@patch("assemblyzero.core.gemini_client.subprocess.Popen")
def test_the_stdin_path_runs_as_the_agent_written_into_its_cwd(mock_popen):
    seen = {}

    def popen(argv, **kwargs):
        seen["argv"] = list(argv)
        seen["agent_file"] = _agent_file_in(kwargs["cwd"])
        proc = MagicMock()
        proc.pid = 1
        proc.communicate.return_value = ("fine", "")
        proc.returncode = 0
        return proc

    mock_popen.side_effect = popen

    ok, text, _err = _client()._invoke_via_cli("sys", "x" * 31000)

    assert ok is True and text == "fine"
    argv = seen["argv"]
    assert argv[:5] == ["/fake/agy", "--agent", "assemblyzero-text", "--model", "gemini-3.1-pro-high"]
    assert _no_elevating_flag(argv)
    assert seen["agent_file"] == gc.AGY_AGENT_DEFINITION


@patch("assemblyzero.core.gemini_client.subprocess.Popen")
def test_an_agent_agy_could_not_load_is_a_failed_call(mock_popen):
    proc = MagicMock()
    proc.pid = 1
    proc.communicate.return_value = (
        "a review from the default agent",
        "Warning: ignoring --agent \"assemblyzero-text\": agent not found\n",
    )
    proc.returncode = 0
    mock_popen.return_value = proc

    ok, text, err = _client()._invoke_via_cli("sys", "x" * 31000)

    assert ok is False and text == ""
    assert "assemblyzero-text" in err and "agent not found" in err


def test_nothing_reads_the_machine_settings():
    for name in ("require_headless_tool_denial", "AGY_SETTINGS_PATH", "AgyToolExecutionEnabledError"):
        assert not hasattr(gc, name)
