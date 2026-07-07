"""Integration tests for the dependabot_review worktree guard (#1699).

dependabot_review.py creates its own audit worktrees off the main repo. Launched
from inside a linked worktree, `--main-repo` (default cwd) silently points at the
worktree and the tool operates on the wrong git dir. The guard is code-level, not
memory-level. These tests exercise REAL `git worktree` state — the guard is a
statement about git behaviour, so a mock would prove nothing.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools"))

import dependabot_review as dr  # noqa: E402


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=True,
    )


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main", str(path)],
                   capture_output=True, check=True)
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "Test")
    (path / "f.txt").write_text("x", encoding="utf-8")
    _git(path, "add", "f.txt")
    _git(path, "commit", "-m", "init")
    return path


@pytest.fixture
def main_and_worktree(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    wt = tmp_path / "wt"
    _git(repo, "worktree", "add", "-b", "wt-branch", str(wt))
    return repo, wt


class TestIsLinkedWorktree:
    def test_main_repo_not_flagged(self, main_and_worktree):
        repo, _ = main_and_worktree
        assert dr.is_linked_worktree(repo) is False

    def test_linked_worktree_flagged(self, main_and_worktree):
        _, wt = main_and_worktree
        assert dr.is_linked_worktree(wt) is True

    def test_non_git_dir_not_flagged(self, tmp_path):
        # Must not false-positive on a plain directory; the separate
        # `.git`-exists check owns the "not a repo" case.
        plain = tmp_path / "plain"
        plain.mkdir()
        assert dr.is_linked_worktree(plain) is False


class TestGuardNotWorktree:
    def test_guard_exits_on_worktree(self, main_and_worktree):
        _, wt = main_and_worktree
        with pytest.raises(SystemExit) as exc:
            dr.guard_not_worktree(wt)
        msg = str(exc.value).lower()
        assert "worktree" in msg
        assert "#1699" in str(exc.value)

    def test_guard_passes_on_main(self, main_and_worktree):
        repo, _ = main_and_worktree
        # Must not raise.
        dr.guard_not_worktree(repo)
