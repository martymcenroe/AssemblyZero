"""The pipeline's agy agent takes none of the machine's customizations but its hooks (#4531).

agy gives a Markdown agent the user's rules, skills, plugins, subagents and MCP
servers unless ``inheritCustomizations: false``. Without it every call carried
the operator's whole agy rule set as ``<user_rules>``: an empty prompt was
billed 16,079 input tokens on 2026-11-02, and 2,126 with it. The switch also
drops the machine's hooks, which are the shell guard's hold on agy, so the
definition names the hooks file again, by an absolute path: agy drops an entry
it cannot resolve, ``~/`` included, without a word.

These tests pin the definition and the path it names. The token figures are
measured live by ``tools/agy_agent_probe.py``.
"""
from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.core import gemini_client as gc

HOOKS = "/home/someone/.gemini/config/hooks.json"


def _front(definition: str) -> dict:
    yaml = pytest.importorskip("yaml")
    return yaml.safe_load(definition.split("---")[1])


def test_the_agent_inherits_no_customizations():
    front = _front(gc.agent_definition(HOOKS))
    assert front["inheritCustomizations"] is False
    assert front["inheritMcp"] is False
    assert front["tools"] == []
    assert front["commandExecutionPolicy"] == "off"


def test_the_agent_names_the_hooks_file_it_is_given_and_no_other():
    assert _front(gc.agent_definition(HOOKS))["hooks"] == [HOOKS]


def test_the_agent_has_no_rules_or_skills_of_its_own():
    front = _front(gc.agent_definition(HOOKS))
    assert "rules" not in front and "skills" not in front


@pytest.mark.parametrize("bad", ["~/.gemini/config/hooks.json", ".gemini/config/hooks.json", ""])
def test_a_hooks_file_that_is_not_absolute_is_refused(bad):
    with pytest.raises(ValueError):
        gc.agent_definition(bad)


def test_the_hooks_file_sits_under_the_home_given():
    assert gc.agy_hooks_file("/home/someone") == HOOKS
    assert gc.agy_hooks_file("/home/someone/") == HOOKS


def test_a_home_that_is_not_absolute_is_refused():
    with pytest.raises(ValueError):
        gc.agy_hooks_file("~")


def test_a_path_with_a_space_survives_the_yaml():
    spaced = "/home/some one/.gemini/config/hooks.json"
    assert _front(gc.agent_definition(spaced))["hooks"] == [spaced]


def test_the_written_file_is_the_definition(tmp_path):
    path = gc.write_text_only_agent(tmp_path, HOOKS)
    assert path == tmp_path / ".agents" / "agents" / gc.AGY_AGENT_NAME / "agent.md"
    assert path.read_text(encoding="utf-8") == gc.agent_definition(HOOKS)


def test_a_native_agy_reads_the_hooks_under_this_process_home(monkeypatch, tmp_path):
    monkeypatch.setattr(gc.Path, "home", classmethod(lambda cls: gc.PurePosixPath("/home/me")))
    client = gc.GeminiClient(model="gemini-3.8-flash-high")
    client._agy_cli = "/home/me/.local/bin/agy"
    assert client._agy_hooks_file() == "/home/me/.gemini/config/hooks.json"


def test_a_wsl_agy_reads_the_hooks_under_wsl_home_not_the_windows_one():
    from tests.conftest import STAND_IN_WSL_HOME

    client = gc.GeminiClient(model="gemini-3.8-flash-high")
    client._agy_cli = gc.AGY_WSL_PREFIX + "/home/stand-in/.local/bin/agy"
    assert client._agy_hooks_file() == STAND_IN_WSL_HOME + "/" + gc.AGY_HOOKS_RELATIVE


def test_a_wsl_home_that_cannot_be_read_starts_no_agy(monkeypatch):
    def unreadable():
        raise RuntimeError("WSL's HOME could not be read")

    monkeypatch.setattr(gc, "_wsl_home", unreadable)
    client = gc.GeminiClient(model="gemini-3.8-flash-high")
    client._agy_cli = gc.AGY_WSL_PREFIX + "/home/stand-in/.local/bin/agy"
    with patch.object(gc.subprocess, "Popen") as popen, pytest.raises(RuntimeError):
        client._invoke_via_stdin("prompt")
    popen.assert_not_called()


@pytest.mark.real_agy_lookup
def test_wsl_home_reads_printenv_home():
    gc._wsl_home.cache_clear()
    done = subprocess.CompletedProcess(args=[], returncode=0, stdout="/home/someone\n", stderr="")
    with patch.object(gc.shutil, "which", return_value="wsl.exe"), \
         patch.object(gc.subprocess, "run", return_value=done) as run:
        assert gc._wsl_home() == "/home/someone"
    assert run.call_args[0][0] == ["wsl.exe", "--exec", "printenv", "HOME"]
    gc._wsl_home.cache_clear()


@pytest.mark.real_agy_lookup
@pytest.mark.parametrize("returncode, stdout", [(1, ""), (0, "C:\\Users\\someone\n"), (0, "")])
def test_wsl_home_that_is_not_a_linux_path_raises(returncode, stdout):
    gc._wsl_home.cache_clear()
    done = subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")
    with patch.object(gc.shutil, "which", return_value="wsl.exe"), \
         patch.object(gc.subprocess, "run", return_value=done), \
         pytest.raises(RuntimeError):
        gc._wsl_home()
    gc._wsl_home.cache_clear()


@pytest.mark.real_agy_lookup
def test_no_wsl_at_all_raises():
    gc._wsl_home.cache_clear()
    with patch.object(gc.shutil, "which", return_value=None), pytest.raises(RuntimeError):
        gc._wsl_home()
    gc._wsl_home.cache_clear()


def test_the_conversation_id_reaches_the_caller():
    """The probe finds agy's own transcript of a call by this id."""
    client = gc.GeminiClient(model="gemini-3.8-flash-high")
    client._agy_cli = "/stand-in/agy"
    client._agy_hooks_file = lambda: HOOKS
    reply = json.dumps({
        "conversation_id": "c0ffee00-0000-4000-8000-000000000001",
        "status": "SUCCESS", "response": "fine",
        "usage": {"input_tokens": 2126, "output_tokens": 5},
    })
    proc = MagicMock()
    proc.pid = 1
    proc.communicate.return_value = (reply, "")
    proc.returncode = 0
    spent: dict = {}
    with patch.object(gc.subprocess, "Popen", return_value=proc):
        ok, text, _err = client._agy_once("prompt", 30, spent)
    assert ok is True and text == "fine"
    assert spent["conversation_id"] == "c0ffee00-0000-4000-8000-000000000001"
    assert spent["usage"]["input_tokens"] == 2126
