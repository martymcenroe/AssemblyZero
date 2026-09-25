"""The archival step leaves the environment alone unless asked, and never evicts it from under a run (#3614, #3626).

On 2026-09-25 the step evicted a worktree's environment twice while a test
tier was running from it, and the tier lost `site-packages` mid-run.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import tools.archive_worktree_lineage as awl

ROOT = Path(__file__).resolve().parents[2]


def _worktree(tmp_path: Path) -> Path:
    wt = tmp_path / "AssemblyZero-9999"
    (wt / ".venv").mkdir(parents=True)
    (wt / "pyproject.toml").write_text("[tool.poetry]\n", encoding="utf-8")
    return wt


def _proc(pid: int, name: str, exe: str | None, cwd: str | None):
    return SimpleNamespace(info={"pid": pid, "name": name, "exe": exe, "cwd": cwd})


def _run_ok(*a, **k):
    return subprocess.CompletedProcess(args=a, returncode=0, stdout="", stderr="")


def test_default_run_never_touches_the_environment(tmp_path, monkeypatch):
    wt = _worktree(tmp_path)
    monkeypatch.setattr(awl, "require_linked_worktree", lambda p: None)
    monkeypatch.setattr(awl, "archive_lineage", lambda *a: [])
    spawned = []
    monkeypatch.setattr(awl.subprocess, "run", lambda *a, **k: spawned.append(a))
    with patch("sys.argv", ["prog", "--worktree", str(wt), "--issue", "9999", "--main-repo", str(tmp_path)]):
        awl.main()
    assert spawned == []
    assert (wt / ".venv").is_dir()


def test_eviction_warns_before_it_runs(tmp_path, monkeypatch, capsys):
    """#3614 T1."""
    wt = _worktree(tmp_path)
    monkeypatch.setattr(awl, "require_linked_worktree", lambda p: None)
    monkeypatch.setattr(awl, "processes_using", lambda p: [])
    order = []
    monkeypatch.setattr(awl.subprocess, "run", lambda *a, **k: order.append("run") or _run_ok())
    awl.evict_poetry_venv(wt)
    out = capsys.readouterr().out
    assert "WARNING: removing this worktree's poetry environment" in out
    assert order == ["run"]


def test_eviction_refuses_beside_a_running_tier(tmp_path, monkeypatch):
    """#3614 T2 and #3626 test 2: a process running from the worktree is named, and nothing is spawned."""
    wt = _worktree(tmp_path)
    monkeypatch.setattr(awl, "require_linked_worktree", lambda p: None)
    monkeypatch.setattr(awl, "_own_lineage", lambda: {1})
    procs = [
        _proc(1, "python.exe", str(wt / ".venv" / "Scripts" / "python.exe"), str(wt)),  # this run
        _proc(4242, "python.exe", "C:/Python314/python.exe", str(wt)),  # a pytest tier, cwd in the worktree
        _proc(7, "explorer.exe", "C:/Windows/explorer.exe", "C:/Windows"),
    ]
    import psutil

    monkeypatch.setattr(psutil, "process_iter", lambda attrs: iter(procs))
    spawned = []
    monkeypatch.setattr(awl.subprocess, "run", lambda *a, **k: spawned.append(a))
    with pytest.raises(SystemExit) as exc:
        awl.evict_poetry_venv(wt)
    assert "PID 4242" in str(exc.value)
    assert "PID 7" not in str(exc.value) and "PID 1 " not in str(exc.value)
    assert spawned == []
    assert (wt / ".venv").is_dir()


def test_a_process_whose_exe_is_in_the_worktree_counts(tmp_path, monkeypatch):
    wt = _worktree(tmp_path)
    monkeypatch.setattr(awl, "_own_lineage", lambda: set())
    import psutil

    monkeypatch.setattr(
        psutil, "process_iter",
        lambda attrs: iter([_proc(55, "python.exe", str(wt / ".venv" / "Scripts" / "python.exe"), "C:/elsewhere")]),
    )
    assert awl.processes_using(wt) == [(55, "python.exe")]


def test_a_sibling_directory_with_the_same_prefix_does_not_count(tmp_path, monkeypatch):
    wt = _worktree(tmp_path)
    sibling = tmp_path / "AssemblyZero-99990"
    monkeypatch.setattr(awl, "_own_lineage", lambda: set())
    import psutil

    monkeypatch.setattr(psutil, "process_iter", lambda attrs: iter([_proc(9, "x", None, str(sibling))]))
    assert awl.processes_using(wt) == []


def test_claude_md_runs_the_archive_after_the_tests_and_before_the_push():
    """#3614 T3: the order of the three lines in the merge sequence."""
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    after_tests = text.index("# Inside the worktree, after the last test run:")
    archive = text.index("tools/archive_worktree_lineage.py --worktree . --issue {ID} --main-repo .")
    push = text.index("# Then push and create the PR")
    assert after_tests < archive < push
    assert "--evict-venv" in text
