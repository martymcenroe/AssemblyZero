"""A new repository gets no Auto Review caller, and the tools that deployed one are gone (#4719).

The reusable Auto Review workflow is retired (#3663: every job `if: false`), and the
pr-sentinel Worker approves as Cerberus once `issue-reference` passes. The per-repository
caller, `.github/workflows/auto-reviewer.yml`, only ever ran a skipped job, and the fleet is
removing it. These tests hold that the scaffolder does not add it back.

The scaffold runs in a `tmp_path` sandbox. `new_repo.run_command` (git, gh, poetry) and
`new_repo.config` (machine-level fleet configuration) are the I/O boundaries replaced here,
as in tests/unit/test_new_repo.py; `git init` really runs, because the scaffold's own
checks ask real git about the ignore rules.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools"
TESTS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import new_repo

CALLER = "auto-reviewer.yml"
RETIRED_TOOLS = ("deploy_auto_reviewer_workflow", "upgrade_auto_reviewer_caller")


def _ok(cmd, cwd=None, check=True):
    if cmd[:2] == ["git", "init"]:
        subprocess.run(["git", "init", "-q"], cwd=cwd, check=True)
    return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")


def _scaffold(tmp_path: Path, name: str, *flags: str) -> tuple[Path, list[list[str]]]:
    with patch("new_repo.config") as cfg, patch("new_repo.run_command") as run:
        cfg.projects_root.return_value = str(tmp_path)
        cfg.projects_root_unix.return_value = "/tmp/projects"
        cfg.assemblyzero_root.return_value = str(tmp_path / "AssemblyZero")
        run.side_effect = _ok
        with patch("sys.argv", ["new_repo.py", name, "--no-github", *flags]):
            try:
                new_repo.main()
            except SystemExit as e:  # a full local run exits through sys.exit
                assert not e.code, f"the scaffold exited {e.code}"
        return tmp_path / name, [c[0][0] for c in run.call_args_list]


@pytest.mark.parametrize("enable_pypi", [True, False])
def test_create_github_workflows_writes_no_caller(tmp_path: Path, enable_pypi):
    new_repo.create_github_workflows(tmp_path, enable_pypi=enable_pypi)
    assert list(tmp_path.rglob(CALLER)) == []


def test_a_scaffolded_repository_carries_no_caller(tmp_path: Path, capsys):
    project, commands = _scaffold(tmp_path, "NoCaller")
    assert project.is_dir()
    assert list(project.rglob(CALLER)) == []
    # PyPI is off by default, so no workflow file is written, and the local-only
    # path does not try to `git add` a workflows directory that is not there.
    assert not (project / ".github" / "workflows").exists()
    assert ["git", "add", ".github/workflows"] not in commands
    assert CALLER not in capsys.readouterr().out


def test_a_scaffolded_pypi_repository_carries_only_the_release_workflow(tmp_path: Path):
    project, commands = _scaffold(tmp_path, "PypiNoCaller", "--pypi")
    assert sorted(p.name for p in (project / ".github" / "workflows").iterdir()) == ["release.yml"]
    assert ["git", "add", ".github/workflows"] in commands


def test_the_scaffolder_keeps_no_caller_template_and_no_caller_check():
    assert not hasattr(new_repo, "_CANONICAL_AUTO_REVIEWER_CALLER")
    assert not hasattr(new_repo, "verify_workflow_content_on_origin")
    src = (TOOLS / "new_repo.py").read_text(encoding="utf-8")
    assert f"[PASS] {CALLER}" not in src and f"Created {CALLER}" not in src


def test_the_retired_tools_are_gone_and_nothing_imports_them():
    for name in RETIRED_TOOLS:
        assert not (TOOLS / f"{name}.py").exists(), name
    here = Path(__file__).resolve()
    for root in (TOOLS, TESTS):
        for py in root.rglob("*.py"):
            if py.resolve() == here:
                continue
            text = py.read_text(encoding="utf-8", errors="replace")
            for name in RETIRED_TOOLS:
                assert name not in text, f"{py} still names {name}"
