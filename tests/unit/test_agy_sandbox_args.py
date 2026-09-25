"""Every agy call the governance client makes is sandboxed (#3516, ADR 0233).

Measured through `GeminiClient._invoke_via_cli`: without `--sandbox`, agy
ran a shell command and wrote a file at an absolute path outside its temp
cwd; with it, the shell was refused (the file write was not). The flag is
what removes shell execution, so both transports must carry it.
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


def test_the_safety_args_are_the_sandbox_flag():
    assert gc.AGY_SAFETY_ARGS == ["--sandbox"]


def test_the_pty_path_passes_sandbox(monkeypatch):
    seen = {}

    def spawn(argv, cwd, dimensions, *a, **kw):
        seen["argv"] = list(argv)
        raise TimeoutError("stop here; only the argv matters")

    monkeypatch.setitem(sys.modules, "winpty", types.ModuleType("winpty"))
    monkeypatch.setattr(gc, "_spawn_pty_bounded", spawn)

    ok, _text, _err = _client()._invoke_via_cli("sys", "short prompt")

    assert ok is False
    argv = seen["argv"]
    assert argv[0] == "/fake/agy"
    assert argv[1] == "--sandbox"
    assert argv.index("--sandbox") < argv.index("-p")


@patch("assemblyzero.core.gemini_client.subprocess.Popen")
def test_the_stdin_path_passes_sandbox(mock_popen):
    proc = MagicMock()
    proc.pid = 1
    proc.communicate.return_value = ("fine", "")
    proc.returncode = 0
    mock_popen.return_value = proc

    _client()._invoke_via_cli("sys", "x" * 31000)

    argv = mock_popen.call_args[0][0]
    assert argv[:2] == ["/fake/agy", "--sandbox"]
