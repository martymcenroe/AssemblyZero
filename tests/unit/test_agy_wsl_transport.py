"""agy runs inside WSL on Windows, never as agy.exe, and both paths check the agent (#3623).

The Windows build of agy wraps its shell in PowerShell, where the fleet's shell
guard cannot see it. So on Windows the transport finds agy inside WSL and runs
it through ``wsl.exe --cd <tmp> --exec <agy>``, always on the stdin path. And a
call that agy answered with its default agent (tools included) fails on either
path, not only on stdin.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.core import gemini_client as gc

MODEL = "gemini-3.1-pro-high"
WSL_AGY = "/home/someone/.local/bin/agy"
WARNING = "Warning: --agent assemblyzero-text could not be loaded; using the default agent"


@pytest.fixture(autouse=True)
def _fresh_cache():
    gc._find_wsl_agy.cache_clear()
    yield
    gc._find_wsl_agy.cache_clear()


def _completed(returncode: int, stdout: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


def _wsl_runner(which_rc: int, which_out: str, home: str = "/home/someone", test_rc: int = 0):
    calls: list[list[str]] = []

    def run(argv, **kwargs):
        calls.append(argv)
        tail = argv[2:]  # after "<wsl>", "--exec"
        if tail[:1] == ["which"]:
            return _completed(which_rc, which_out)
        if tail[:1] == ["printenv"]:
            return _completed(0, home + "\n")
        if tail[:1] == ["test"]:
            return _completed(test_rc)
        raise AssertionError(f"unexpected WSL call {argv}")

    return run, calls


# --- discovery -----------------------------------------------------------------

def test_windows_uses_the_wsl_agy_found_by_which(tmp_path):
    run, calls = _wsl_runner(0, WSL_AGY + "\n")
    with patch.object(gc, "_ON_WINDOWS", True), \
         patch.object(gc.shutil, "which", side_effect=lambda n: "C:/Windows/System32/wsl.exe" if n.startswith("wsl") else None), \
         patch.object(gc.subprocess, "run", side_effect=run):
        client = gc.GeminiClient(model=MODEL)
    assert client._agy_cli == gc.AGY_WSL_PREFIX + WSL_AGY
    assert all(c[1] == "--exec" for c in calls), "every WSL lookup is argv-only, no shell"


def test_windows_falls_back_to_home_local_bin():
    run, _ = _wsl_runner(1, "")
    with patch.object(gc, "_ON_WINDOWS", True), \
         patch.object(gc.shutil, "which", side_effect=lambda n: "wsl.exe" if n.startswith("wsl") else None), \
         patch.object(gc.subprocess, "run", side_effect=run):
        client = gc.GeminiClient(model=MODEL)
    assert client._agy_cli == gc.AGY_WSL_PREFIX + "/home/someone/.local/bin/agy"


def test_windows_never_returns_a_windows_agy_exe(tmp_path, monkeypatch):
    """Test 1: an agy.exe on PATH and at the old install location is ignored."""
    exe = tmp_path / "AppData" / "Local" / "agy" / "bin" / "agy.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    run, _ = _wsl_runner(0, WSL_AGY + "\n")

    def which(name):
        return {"agy": str(exe), "wsl.exe": "wsl.exe"}.get(name)

    with patch.object(gc, "_ON_WINDOWS", True), \
         patch.object(gc.shutil, "which", side_effect=which), \
         patch.object(gc.subprocess, "run", side_effect=run):
        client = gc.GeminiClient(model=MODEL)
    assert client._agy_cli.startswith(gc.AGY_WSL_PREFIX)
    assert "agy.exe" not in client._agy_cli


def test_windows_without_wsl_agy_is_not_found():
    """Test 2."""
    run, _ = _wsl_runner(1, "", test_rc=1)
    with patch.object(gc, "_ON_WINDOWS", True), \
         patch.object(gc.shutil, "which", side_effect=lambda n: "wsl.exe" if n.startswith("wsl") else "C:/agy/agy.exe"), \
         patch.object(gc.subprocess, "run", side_effect=run):
        client = gc.GeminiClient(model=MODEL)
    assert client._agy_cli is None


def test_windows_without_wsl_at_all_is_not_found():
    with patch.object(gc, "_ON_WINDOWS", True), \
         patch.object(gc.shutil, "which", side_effect=lambda n: None if n.startswith("wsl") else "C:/agy/agy.exe"):
        client = gc.GeminiClient(model=MODEL)
    assert client._agy_cli is None


def test_off_windows_uses_path():
    """Test 3."""
    with patch.object(gc, "_ON_WINDOWS", False), \
         patch.object(gc.shutil, "which", return_value="/usr/bin/agy"):
        client = gc.GeminiClient(model=MODEL)
    assert client._agy_cli == "/usr/bin/agy"


# --- the call ------------------------------------------------------------------

def _wsl_client() -> gc.GeminiClient:
    client = gc.GeminiClient(model=MODEL)
    client._agy_cli = gc.AGY_WSL_PREFIX + WSL_AGY
    return client


def _popen(stdout: str = "ok", stderr: str = "", returncode: int = 0) -> MagicMock:
    proc = MagicMock()
    proc.communicate.return_value = (stdout, stderr)
    proc.returncode = returncode
    proc.pid = 1234
    return proc


def test_wsl_short_prompt_rides_stdin_with_the_wsl_argv():
    """Test 4."""
    client = _wsl_client()
    with patch.object(gc.subprocess, "Popen", return_value=_popen("model text")) as popen:
        ok, text, err = client._invoke_via_cli("sys", "short content")
    assert ok is True and text == "model text", err
    argv = popen.call_args[0][0]
    cwd = popen.call_args[1]["cwd"]
    assert argv[:5] == ["wsl.exe", "--cd", cwd, "--exec", WSL_AGY]
    assert argv[5:] == ["--agent", gc.AGY_AGENT_NAME, "--model", MODEL]
    assert "--sandbox" not in argv and "-p" not in argv


def test_wsl_call_writes_the_agent_into_the_cwd_it_passes():
    client = _wsl_client()
    seen = {}

    def popen(argv, **kwargs):
        cwd = kwargs["cwd"]
        seen["exists"] = (Path(cwd) / ".agents" / "agents" / gc.AGY_AGENT_NAME / "agent.md").is_file()
        seen["cd"] = argv[2] == cwd
        return _popen("x")

    with patch.object(gc.subprocess, "Popen", side_effect=popen):
        client._invoke_via_cli("sys", "c")
    assert seen == {"exists": True, "cd": True}


def test_native_argv_is_unchanged():
    client = gc.GeminiClient(model=MODEL)
    client._agy_cli = "/usr/bin/agy"
    assert client._agy_argv("/tmp/x", "--model", MODEL) == ["/usr/bin/agy", "--model", MODEL]


# --- the agent check on both paths (test 5) ----------------------------------

def test_stdin_path_fails_on_an_agent_warning():
    client = _wsl_client()
    with patch.object(gc.subprocess, "Popen", return_value=_popen("I ran whoami", stderr=WARNING)):
        ok, text, err = client._invoke_via_stdin("prompt")
    assert ok is False and text == ""
    assert "did not run as assemblyzero-text" in err


@pytest.mark.parametrize("on_windows", [True, False])
def test_every_short_prompt_rides_stdin(on_windows):
    """#3624: there is one path, on every platform, for every agy."""
    client = gc.GeminiClient(model=MODEL)
    client._agy_cli = "C:/fake/agy" if on_windows else "/usr/bin/agy"
    with patch.object(gc, "_ON_WINDOWS", on_windows), \
         patch.object(client, "_invoke_via_stdin", return_value=(True, "ok", "")) as stdin:
        ok, _, _ = client._invoke_via_cli("sys", "short")
    assert ok is True
    stdin.assert_called_once()


def test_the_pty_helpers_are_gone():
    for name in ("_spawn_pty_bounded", "_read_pty_bounded", "SPAWN_TIMEOUT_SECONDS"):
        assert not hasattr(gc, name)
