"""No agy call carries a flag whose mechanism is elevation, and no call runs
on a machine whose agy executes the model's tool calls (#3605, #3603; ADR 0233
as amended 2026-09-25).

`--sandbox` was passed here from 2026-09-24 to 2026-09-25. On Windows it makes
agy build an AppContainer for each shell command the model attempts, which
needs an administrator token that agy obtains by relaunching itself elevated:
a UAC dialog naming agy.exe, raised three times in one pipeline call on
2026-09-25. The operator's ruling: no agent ever gets elevated rights.

What keeps a headless call text-only is agy's `toolPermission` setting. The
documented default, `request-review`, soft-denies a shell command in print
mode. The transport reads the settings file and refuses anything else before a
subprocess starts.
"""
from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.core import gemini_client as gc

ELEVATING_FLAGS = ("--sandbox", "--dangerously-skip-permissions")


def _client() -> gc.GeminiClient:
    client = gc.GeminiClient(model="gemini-3.1-pro-high")
    client._agy_cli = "/fake/agy"
    return client


def _settings(tmp_path, body: str):
    path = tmp_path / "settings.json"
    path.write_text(body, encoding="utf-8")
    return path


def test_the_safety_args_are_empty():
    assert gc.AGY_SAFETY_ARGS == []


def test_the_pty_path_carries_no_elevating_flag(monkeypatch):
    seen = {}

    def spawn(argv, cwd, dimensions, *a, **kw):
        seen["argv"] = list(argv)
        raise TimeoutError("stop here; only the argv matters")

    monkeypatch.setitem(sys.modules, "winpty", types.ModuleType("winpty"))
    monkeypatch.setattr(gc, "_spawn_pty_bounded", spawn)

    ok, _text, _err = _client()._invoke_via_cli("sys", "short prompt")

    assert ok is False
    argv = seen["argv"]
    assert argv[:2] == ["/fake/agy", "-p"]
    for flag in ELEVATING_FLAGS:
        assert flag not in argv


@patch("assemblyzero.core.gemini_client.subprocess.Popen")
def test_the_stdin_path_carries_no_elevating_flag(mock_popen):
    proc = MagicMock()
    proc.pid = 1
    proc.communicate.return_value = ("fine", "")
    proc.returncode = 0
    mock_popen.return_value = proc

    _client()._invoke_via_cli("sys", "x" * 31000)

    argv = mock_popen.call_args[0][0]
    assert argv[:3] == ["/fake/agy", "--model", "gemini-3.1-pro-high"]
    for flag in ELEVATING_FLAGS:
        assert flag not in argv


@pytest.mark.parametrize("value", ["always-proceed", "proceed-in-sandbox", "strict"])
def test_a_machine_that_executes_tool_calls_gets_no_call(monkeypatch, tmp_path, value):
    monkeypatch.setattr(
        gc, "AGY_SETTINGS_PATH", _settings(tmp_path, f'{{"toolPermission": "{value}"}}')
    )
    spawned = []
    monkeypatch.setattr(gc, "_spawn_pty_bounded", lambda *a, **k: spawned.append(a))
    monkeypatch.setitem(sys.modules, "winpty", types.ModuleType("winpty"))

    with pytest.raises(gc.AgyToolExecutionEnabledError) as excinfo:
        _client()._invoke_via_cli("sys", "short prompt")

    assert value in str(excinfo.value)
    assert "request-review" in str(excinfo.value)
    assert spawned == []


def test_request_review_and_an_absent_key_pass(tmp_path):
    for body in ('{"toolPermission": "request-review"}', '{"colorScheme": "dark"}'):
        gc.require_headless_tool_denial(_settings(tmp_path, body))


def test_a_missing_settings_file_passes(tmp_path):
    gc.require_headless_tool_denial(tmp_path / "absent.json")


def test_unparseable_settings_refuse(tmp_path):
    with pytest.raises(gc.AgyToolExecutionEnabledError) as excinfo:
        gc.require_headless_tool_denial(_settings(tmp_path, "{not json"))
    assert "not valid JSON" in str(excinfo.value)


def test_invoke_refuses_before_reading_credentials(monkeypatch, tmp_path):
    monkeypatch.setattr(
        gc, "AGY_SETTINGS_PATH", _settings(tmp_path, '{"toolPermission": "always-proceed"}')
    )
    client = _client()

    def never(*a, **k):
        raise AssertionError("credentials were read after the refusal should have fired")

    monkeypatch.setattr(client, "_load_credentials", never)

    with pytest.raises(gc.AgyToolExecutionEnabledError):
        client.invoke("sys", "content")
