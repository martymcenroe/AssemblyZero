"""mechanical_hooks.py (N4.5) under standard 0034, one test per sweep site.

N4.5 runs the target's post_implement_command and stages what it built. The
``git add`` that stages it ran with ``check=False`` and its return code was
never read, so a staging that failed went on to the tests as if the build's
output were in the tree. It now halts. The other four sites were already
halts, or the documented "no hook"; they are pinned. Every halt is an ERROR
line on stderr. Line numbers in the names are ledger 0908's, at its base
``79e18ad1``. The hook commands are real shell commands in a temporary
directory, and ``git`` is the real one.
"""
from __future__ import annotations

import importlib
import json
import subprocess
from pathlib import Path

import pytest

from assemblyzero.workflows.testing.graph import route_after_mechanical_hooks

# The nodes package re-exports the node FUNCTION under the module's name.
mh = importlib.import_module("assemblyzero.workflows.testing.nodes.mechanical_hooks")


def _target(tmp_path: Path, command: str | None, *, git: bool = True) -> dict:
    if git:
        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    if command is not None:
        (tmp_path / ".unleashed.json").write_text(
            json.dumps({"post_implement_command": command}), encoding="utf-8"
        )
    return {"repo_root": str(tmp_path), "issue_number": 5}


def _halts(state: dict, result: dict) -> bool:
    return route_after_mechanical_hooks({**state, **result}) == "HALT"


# --- line 70: no .unleashed.json (kept) ----------------------------------------


def test_70_no_config_is_no_hook(tmp_path):
    state = _target(tmp_path, None)
    assert mh.mechanical_hooks(state) == {}


# --- line 74: the config cannot be read (kept) ---------------------------------


def test_74_a_config_that_is_not_json_halts(tmp_path, capsys):
    state = _target(tmp_path, None)
    (tmp_path / ".unleashed.json").write_text("{not json", encoding="utf-8")

    result = mh.mechanical_hooks(state)

    assert "could not be read as JSON" in result["error_message"]
    assert _halts(state, result)
    assert "ERROR [N4.5]" in capsys.readouterr().err


# --- line 91: the hook cannot start (kept) -------------------------------------


def test_91_a_hook_that_cannot_start_halts(tmp_path, monkeypatch, capsys):
    state = _target(tmp_path, "build-it")

    def refuse(*args, **kwargs):
        raise OSError(2, "No such file or directory: '/bin/sh'")

    monkeypatch.setattr(mh.subprocess, "run", refuse)
    result = mh.mechanical_hooks(state)

    assert "could not start" in result["error_message"]
    assert _halts(state, result)
    assert "ERROR [N4.5]" in capsys.readouterr().err


# --- line 98: the hook exits non-zero (kept) -----------------------------------


def test_98_a_hook_that_fails_halts_with_its_exit_code(tmp_path, capsys):
    state = _target(tmp_path, "echo broken build >&2; exit 3")

    result = mh.mechanical_hooks(state)

    assert "exit code 3" in result["error_message"]
    assert "broken build" in result["error_message"]
    assert _halts(state, result)
    assert "ERROR [N4.5]" in capsys.readouterr().err


# --- line 108: staging the hook's output fails --------------------------------


def test_108_a_staging_that_fails_halts_with_gits_stderr(tmp_path, capsys):
    """The target is not a git repository, so `git add .` exits 128."""
    state = _target(tmp_path, "true", git=False)

    result = mh.mechanical_hooks(state)

    assert "git add" in result["error_message"]
    assert "exit code 128" in result["error_message"]
    assert "not a git repository" in result["error_message"]
    assert _halts(state, result)
    assert "ERROR [N4.5]" in capsys.readouterr().err


def test_108_git_that_cannot_start_halts(tmp_path, monkeypatch):
    state = _target(tmp_path, "true")
    real_run = mh.subprocess.run

    def no_git(args, *a, **k):
        if isinstance(args, list) and args[:1] == ["git"]:
            raise FileNotFoundError(2, "No such file or directory", "git")
        return real_run(args, *a, **k)

    monkeypatch.setattr(mh.subprocess, "run", no_git)
    result = mh.mechanical_hooks(state)

    assert "git add" in result["error_message"]
    assert "FileNotFoundError" in result["error_message"]
    assert _halts(state, result)


def test_a_hook_that_succeeds_stages_what_it_built(tmp_path):
    """Kept: the hook's output is staged, and nothing is returned."""
    state = _target(tmp_path, "touch built.txt")

    assert mh.mechanical_hooks(state) == {}
    staged = subprocess.run(
        ["git", "-C", str(tmp_path), "diff", "--cached", "--name-only"],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    assert "built.txt" in staged


@pytest.mark.parametrize("config", [{}, {"post_implement_command": ""}])
def test_a_config_with_no_command_is_no_hook(tmp_path, config):
    """Kept: a config that names no command runs nothing."""
    state = _target(tmp_path, None)
    (tmp_path / ".unleashed.json").write_text(json.dumps(config), encoding="utf-8")
    assert mh.mechanical_hooks(state) == {}
