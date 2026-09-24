"""The implementation branch is not pushed before there is work (#3511).

`create_worktree` pushed `{issue}-implementation` the moment the worktree
existed, so a run that halted at N0, N1 or N3 had already published an empty
branch, and nothing removed it. These cut a throwaway repo with a bare origin
and read the origin's refs after the call.
"""
from __future__ import annotations

import io
import subprocess
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pytest


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert result.returncode == 0, f"git {' '.join(args)}: {result.stderr}"
    return result


@pytest.fixture
def target_repo(tmp_path: Path) -> Path:
    origin = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "-q", "--bare", "--initial-branch=main", str(origin)],
        capture_output=True, text=True, check=True,
    )
    root = tmp_path / "target"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "Test")
    (root / ".gitignore").write_text("data/\n", encoding="utf-8")
    (root / "README.md").write_text("base\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")
    _git(root, "remote", "add", "origin", str(origin))
    _git(root, "push", "-qu", "origin", "main")
    return root


@pytest.fixture(autouse=True)
def _state_dir(tmp_path, monkeypatch):
    """A halt writes a state snapshot and a resume contract under
    ``~/.assemblyzero/workflow_state``; keep both inside the test's tree."""
    from assemblyzero.core import resume_contract, state_persistence

    state = tmp_path / "workflow_state"
    monkeypatch.setattr(state_persistence, "STATE_DIR", state)
    monkeypatch.setattr(resume_contract, "STATE_DIR", state)
    return state


def _origin_refs(target: Path) -> str:
    return _git(target.parent / "origin.git", "for-each-ref",
                "--format=%(refname) %(objectname)").stdout


class TestNoPushBeforeWork:
    def test_create_worktree_pushes_nothing(self, target_repo):
        from tools.run_implement_from_lld import create_worktree

        before = _origin_refs(target_repo)

        path, error = create_worktree(target_repo, 42)

        assert error == ""
        assert path.exists()
        assert _origin_refs(target_repo) == before
        # The branch exists locally, with no upstream: nothing was published.
        upstream = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--abbrev-ref", "@{upstream}"],
            capture_output=True, text=True,
        )
        assert upstream.returncode != 0

    @staticmethod
    def _run(target_repo: Path, tmp_path: Path, *extra: str) -> str:
        from tools import run_implement_from_lld as tool

        argv = [
            "prog", "--issue", "42", "--repo", str(target_repo), "--auto",
            "--db-path", str(tmp_path / "ckpt.db"), *extra,
        ]
        out = io.StringIO()
        with patch("sys.argv", argv), redirect_stdout(out):
            try:
                tool.main()
            except SystemExit:
                pass
        return out.getvalue()

    def test_a_run_that_halts_at_n0_leaves_the_origin_unchanged(self, target_repo, tmp_path):
        """No LLD exists for issue 42 and this is not a mock run, so N0
        halts. The worktree was cut; the origin's refs are what they were."""
        before = _origin_refs(target_repo)

        out = self._run(target_repo, tmp_path)

        assert "[N0]" in out and "[N1]" not in out, out
        assert (target_repo.parent / "target-42").exists(), out
        assert _origin_refs(target_repo) == before, out

    def test_a_full_mock_run_leaves_the_origin_unchanged(self, target_repo, tmp_path):
        """`--mock` loads a mock LLD and runs every node, cutting local
        checkpoint commits on the way. None of it reaches the origin."""
        before = _origin_refs(target_repo)

        out = self._run(target_repo, tmp_path, "--mock")

        assert "[N4]" in out, out
        assert _origin_refs(target_repo) == before, out
