"""No agy call the governance client makes passes --sandbox (#3608).

#3516 added `--sandbox` to every agy call. On Windows it builds an AppContainer and
on 2026-09-25 raised a UAC administrator-rights prompt. Operator ruling: no agent
ever requests elevation, and agents do not pass --sandbox. Both transports are
pinned here so the flag cannot come back.
"""
from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch

from assemblyzero.core import gemini_client as gc


def _client() -> gc.GeminiClient:
    client = gc.GeminiClient(model="gemini-3.1-pro-high")
    client._agy_cli = "/fake/agy"
    return client


def _no_sandbox(argv: list[str]) -> bool:
    return not any(a == "--sandbox" or a.startswith("--sandbox=") for a in argv)


def test_the_safety_args_are_empty():
    assert gc.AGY_SAFETY_ARGS == []


def test_the_pty_path_never_passes_sandbox(monkeypatch):
    seen = {}

    def spawn(argv, cwd, dimensions, *a, **kw):
        seen["argv"] = list(argv)
        raise TimeoutError("stop here; only the argv matters")

    monkeypatch.setitem(sys.modules, "winpty", types.ModuleType("winpty"))
    monkeypatch.setattr(gc, "_spawn_pty_bounded", spawn)

    ok, _text, _err = _client()._invoke_via_cli("sys", "short prompt")

    assert ok is False
    assert seen["argv"][0] == "/fake/agy"
    assert _no_sandbox(seen["argv"])


@patch("assemblyzero.core.gemini_client.subprocess.Popen")
def test_the_stdin_path_never_passes_sandbox(mock_popen):
    proc = MagicMock()
    proc.pid = 1
    proc.communicate.return_value = ("fine", "")
    proc.returncode = 0
    mock_popen.return_value = proc

    _client()._invoke_via_cli("sys", "x" * 31000)

    argv = mock_popen.call_args[0][0]
    assert argv[0] == "/fake/agy"
    assert _no_sandbox(argv)
