"""The provider owns CLAUDECODE for its nested sessions (#3505).

The roll already sets it (`test_speedrun_roll.py` pins that); the two
standalone tools relied on the operator typing `CLAUDECODE=` at launch,
and a forgotten prefix failed every nested call with an error that read
as the model's. Both transports the provider uses get the same env.
"""
from __future__ import annotations

import json
from unittest.mock import Mock, patch

from assemblyzero.core.llm_provider import ClaudeCLIProvider, _nested_claude_env


def _stream_proc(payload: str = "", returncode: int = 0):
    proc = Mock()
    proc.pid = 12345
    lines = []
    if payload:
        event = json.loads(payload)
        event.setdefault("type", "result")
        lines.append(json.dumps(event))
    proc.stdout = iter(lines)
    proc.stderr = Mock()
    proc.stderr.read.return_value = ""
    proc.stdin = Mock()
    proc.poll.return_value = returncode
    proc.returncode = returncode
    return proc


class TestNestedClaudeEnv:
    def test_clears_claudecode_even_when_the_parent_set_it(self, monkeypatch):
        monkeypatch.setenv("CLAUDECODE", "1")
        env = _nested_claude_env()
        assert env["CLAUDECODE"] == ""
        assert env["PYTHONWARNINGS"] == "ignore"

    def test_the_empty_string_is_set_when_the_parent_had_nothing(self, monkeypatch):
        monkeypatch.delenv("CLAUDECODE", raising=False)
        env = _nested_claude_env()
        assert "CLAUDECODE" in env and env["CLAUDECODE"] == ""

    def test_the_rest_of_the_environment_is_inherited(self, monkeypatch):
        monkeypatch.setenv("AZ_TEST_MARKER", "present")
        assert _nested_claude_env()["AZ_TEST_MARKER"] == "present"


class TestTheInvokeTransportUsesIt:
    @patch("subprocess.Popen")
    @patch.object(ClaudeCLIProvider, "_find_cli")
    def test_invoke_launches_with_claudecode_cleared(self, mock_find_cli, mock_popen, monkeypatch):
        monkeypatch.setenv("CLAUDECODE", "1")
        mock_find_cli.return_value = "/usr/local/bin/claude"
        mock_popen.return_value = _stream_proc('{"result": "ok"}')

        result = ClaudeCLIProvider().invoke(system_prompt="sys", content="hi")

        assert result.success is True
        env = mock_popen.call_args.kwargs["env"]
        assert env["CLAUDECODE"] == ""


def _settings_arg(cmd: list[str]) -> dict:
    i = cmd.index("--settings")
    return json.loads(cmd[i + 1])


class TestNestedCallsLoadNoUserHooks:
    """#3504, ADR 0232. Measured: one nested call fired SessionStart (a
    baseline file written into the repo holding the cwd) and SessionEnd (a
    full transcript-archive pass). The flag turns every user hook off."""

    @patch("subprocess.Popen")
    @patch.object(ClaudeCLIProvider, "_find_cli")
    def test_invoke_disables_all_hooks(self, mock_find_cli, mock_popen):
        mock_find_cli.return_value = "/usr/local/bin/claude"
        mock_popen.return_value = _stream_proc('{"result": "ok"}')

        ClaudeCLIProvider().invoke(system_prompt="sys", content="hi")

        cmd = mock_popen.call_args.args[0]
        assert _settings_arg(cmd) == {"disableAllHooks": True}
        # The user settings still load (the login lives there); only hooks go.
        assert cmd[cmd.index("--setting-sources") + 1] == "user"

    @patch("subprocess.Popen")
    @patch.object(ClaudeCLIProvider, "_find_cli")
    def test_the_large_prompt_path_disables_them_too(self, mock_find_cli, mock_popen):
        """The temp-dir path widens --setting-sources to user,project; the
        hooks flag must survive that edit of the command line."""
        mock_find_cli.return_value = "/usr/local/bin/claude"
        mock_popen.return_value = _stream_proc('{"result": "ok"}')
        big = "x" * (ClaudeCLIProvider.SYSTEM_PROMPT_CLI_LIMIT + 1)

        ClaudeCLIProvider().invoke(system_prompt=big, content="hi")

        cmd = mock_popen.call_args.args[0]
        assert _settings_arg(cmd) == {"disableAllHooks": True}

    @patch("subprocess.Popen")
    @patch.object(ClaudeCLIProvider, "_find_cli")
    def test_the_liveness_probe_disables_them_too(self, mock_find_cli, mock_popen):
        mock_find_cli.return_value = "/usr/local/bin/claude"
        proc = Mock()
        proc.communicate.return_value = ('{"result": "ok"}', "")
        proc.returncode = 0
        mock_popen.return_value = proc

        ClaudeCLIProvider()._probe_alive()

        cmd = mock_popen.call_args.args[0]
        assert _settings_arg(cmd) == {"disableAllHooks": True}
