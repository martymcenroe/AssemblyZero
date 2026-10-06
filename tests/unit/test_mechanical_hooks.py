"""N4.5 mechanical hooks: the target's environment (#3705) and loud failure (#3706)."""

import json
import os
import subprocess
import sys
from pathlib import Path

from assemblyzero.workflows.testing.graph import route_after_mechanical_hooks
from assemblyzero.workflows.testing.nodes.mechanical_hooks import (
    hook_environment,
    mechanical_hooks,
)

#: A hook that records what it saw: VIRTUAL_ENV on the first line, PATH on
#: the second. Run through sys.executable, which is an absolute path, so the
#: stripped PATH cannot keep it from starting.
PROBE = (
    "import os, pathlib\n"
    "pathlib.Path('probe.txt').write_text("
    "repr(os.environ.get('VIRTUAL_ENV')) + '\\n' + os.environ.get('PATH', ''),"
    " encoding='utf-8')\n"
)


def _repo(tmp_path: Path, command: str) -> dict:
    (tmp_path / ".unleashed.json").write_text(
        json.dumps({"post_implement_command": command}), encoding="utf-8"
    )
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return {"repo_root": str(tmp_path)}


def test_hook_environment_drops_the_workflows_virtualenv(tmp_path):
    venv = tmp_path / "venv"
    env = {
        "VIRTUAL_ENV": str(venv),
        "POETRY_ACTIVE": "1",
        "PATH": os.pathsep.join([str(venv / "bin"), str(venv / "Scripts"), "/usr/bin"]),
        "HOME": str(tmp_path),
    }
    out = hook_environment(env)
    assert "VIRTUAL_ENV" not in out
    assert "POETRY_ACTIVE" not in out
    assert out["PATH"] == "/usr/bin"
    assert out["HOME"] == str(tmp_path)
    assert env["VIRTUAL_ENV"] == str(venv), "the caller's mapping is not mutated"


def test_hook_runs_without_the_workflows_virtualenv_and_stages_its_output(tmp_path, monkeypatch):
    (tmp_path / "probe.py").write_text(PROBE, encoding="utf-8")
    fake_venv = tmp_path / "fake-venv"
    (fake_venv / "bin").mkdir(parents=True)
    monkeypatch.setenv("VIRTUAL_ENV", str(fake_venv))
    monkeypatch.setenv("POETRY_ACTIVE", "1")
    monkeypatch.setenv("PATH", os.pathsep.join([str(fake_venv / "bin"), os.environ["PATH"]]))
    state = _repo(tmp_path, f'"{sys.executable}" probe.py')

    assert mechanical_hooks(state) == {}

    venv_line, path_line = (tmp_path / "probe.txt").read_text(encoding="utf-8").split("\n", 1)
    assert venv_line == "None"
    assert str(fake_venv / "bin") not in path_line.split(os.pathsep)
    status = subprocess.run(
        ["git", "-C", str(tmp_path), "status", "--porcelain"],
        capture_output=True, text=True, check=True,
    ).stdout
    assert "A  probe.txt" in status
    assert route_after_mechanical_hooks(state) == "N5_verify_green"


def test_a_failed_hook_halts_with_its_exit_code(tmp_path):
    state = _repo(tmp_path, "exit 3")
    out = mechanical_hooks(state)
    assert "exit code 3" in out["error_message"]
    assert "exit 3" in out["error_message"]
    assert route_after_mechanical_hooks({**state, **out}) == "HALT"


def test_an_unreadable_config_halts(tmp_path):
    (tmp_path / ".unleashed.json").write_text("{not json", encoding="utf-8")
    out = mechanical_hooks({"repo_root": str(tmp_path)})
    assert ".unleashed.json" in out["error_message"]
    assert route_after_mechanical_hooks(out) == "HALT"


def test_no_hook_means_no_update(tmp_path):
    (tmp_path / ".unleashed.json").write_text("{}", encoding="utf-8")
    assert mechanical_hooks({"repo_root": str(tmp_path)}) == {}
    assert mechanical_hooks({"repo_root": str(tmp_path / "absent")}) == {}


def test_the_node_carries_no_fail_open_tag():
    source = Path(mechanical_hooks.__code__.co_filename).read_text(encoding="utf-8")
    assert "fail-open:" not in source
