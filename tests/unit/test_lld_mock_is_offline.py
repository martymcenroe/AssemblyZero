"""`run_requirements_workflow.py --mock` is an offline rehearsal (#3512).

N5 already stopped cutting a branch and opening a PR under `--mock` (#2288).
N0b did not read the flag: whenever `base_branch` was set -- always, for
`--type lld` -- it ran `git fetch origin <base>` and cut the `{issue}-lld`
worktree and branch in the target repo. So a mock run needed a network and
left a worktree and a branch behind.

These run the real tool in mock mode against a throwaway repo that has no
remote at all, and read the worktree list and the branch list afterwards.
"""
from __future__ import annotations

import io
import subprocess
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert result.returncode == 0, f"git {' '.join(args)}: {result.stderr}"
    return result


@pytest.fixture(autouse=True)
def _state_dir(tmp_path, monkeypatch):
    """Keep any halt snapshot out of the real ~/.assemblyzero (#3531)."""
    from assemblyzero.core import resume_contract, state_persistence

    state = tmp_path / "workflow_state"
    monkeypatch.setattr(state_persistence, "STATE_DIR", state)
    monkeypatch.setattr(resume_contract, "STATE_DIR", state)


@pytest.fixture(autouse=True)
def _disarm_call_recording():
    """`main()` leaves call recording armed; disarm it so later tests in the
    session get plain providers (see test_lld_mock_completes.py, #3533)."""
    from assemblyzero.core import call_recording

    yield
    call_recording.reset_context()


@pytest.fixture
def offline_repo(tmp_path: Path) -> Path:
    """A target repo with no remote: any fetch or push would fail."""
    root = tmp_path / "target"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "Test")
    (root / ".gitignore").write_text("data/\n", encoding="utf-8")
    (root / "README.md").write_text("base\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")
    return root


def _snapshot(repo: Path) -> dict[str, str]:
    return {
        "worktrees": _git(repo, "worktree", "list", "--porcelain").stdout,
        "branches": _git(repo, "branch", "--list", "--all").stdout,
    }


def _run_mock(target: Path) -> tuple[int, str, list[list[str]]]:
    """Run the tool in mock mode, recording every git command N0b and N5
    send through `git_operations.run_command`."""
    from assemblyzero.workflows.requirements import git_operations
    from tools.run_requirements_workflow import main

    seen: list[list[str]] = []
    real = git_operations.run_command

    def recording(cmd, *a, **kw):
        seen.append(list(cmd))
        return real(cmd, *a, **kw)

    argv = [
        "prog", "--type", "lld", "--issue", "42", "--mock", "--yes",
        "--review", "none", "--repo", str(target), "--base-branch", "main",
    ]
    out = io.StringIO()
    with patch("sys.argv", argv), patch(
        "tools.run_requirements_workflow.resolve_roots",
        return_value=(ROOT, target),
    ), patch.object(git_operations, "run_command", recording), redirect_stdout(out):
        rc = main()
    return rc, out.getvalue(), seen


class TestMockIsOffline:
    def test_a_mock_run_completes_with_no_remote(self, offline_repo):
        rc, out, _ = _run_mock(offline_repo)
        assert rc == 0, out
        assert "cannot read the arc" not in out, out

    def test_a_mock_run_cuts_no_worktree_and_no_branch(self, offline_repo):
        before = _snapshot(offline_repo)

        rc, out, _ = _run_mock(offline_repo)

        assert rc == 0, out
        assert _snapshot(offline_repo) == before, out
        assert not (offline_repo / "data" / "worktrees").exists(), out

    def test_a_mock_run_sends_no_fetch_and_no_push(self, offline_repo):
        rc, out, seen = _run_mock(offline_repo)

        assert rc == 0, out
        remote_ops = [c for c in seen if "fetch" in c or "push" in c]
        assert remote_ops == [], remote_ops
