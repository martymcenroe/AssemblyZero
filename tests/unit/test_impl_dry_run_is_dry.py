"""`run_implement_from_lld.py --dry-run` touches nothing (#3508).

The dry-run exit sat after worktree creation, which creates a sibling
directory, cuts a branch and pushes it to origin, and then the tool printed
"no files modified". These cut a throwaway repo with a bare origin and read
the worktree list, the branch list and the origin's refs after the call.
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


def _snapshot(target: Path) -> dict[str, str]:
    origin = target.parent / "origin.git"
    return {
        "worktrees": _git(target, "worktree", "list", "--porcelain").stdout,
        "branches": _git(target, "branch", "--list").stdout,
        "origin_refs": _git(origin, "for-each-ref", "--format=%(refname)").stdout,
    }


def _run_main(target: Path, tmp_path: Path, *extra: str) -> tuple[int, str]:
    from tools import run_implement_from_lld as tool

    argv = [
        "prog", "--issue", "42", "--repo", str(target), "--dry-run",
        "--db-path", str(tmp_path / "ckpt.db"), *extra,
    ]
    out = io.StringIO()
    with patch("sys.argv", argv), redirect_stdout(out):
        rc = tool.main()
    return rc, out.getvalue()


class TestTheDryRunIsDry:
    def test_dry_run_cuts_nothing_and_pushes_nothing(self, target_repo, tmp_path):
        before = _snapshot(target_repo)

        rc, out = _run_main(target_repo, tmp_path)

        assert rc == 0
        assert _snapshot(target_repo) == before
        assert not (target_repo.parent / "target-42").exists()
        assert "Nothing was created, pushed or modified" in out

    def test_dry_run_names_the_worktree_and_branch_it_would_cut(self, target_repo, tmp_path):
        rc, out = _run_main(target_repo, tmp_path)
        assert rc == 0
        assert "target-42" in out
        assert "42-implementation from main" in out
        assert "LLD-042.md (NOT FOUND)" in out

    def test_dry_run_with_no_worktree_says_so(self, target_repo, tmp_path):
        rc, out = _run_main(target_repo, tmp_path, "--no-worktree")
        assert rc == 0
        assert "none (--no-worktree)" in out

    def test_dry_run_writes_no_run_record_and_no_db(self, target_repo, tmp_path):
        rc, _ = _run_main(target_repo, tmp_path)
        assert rc == 0
        assert not (target_repo / "data" / "speedrun").exists()
        assert not (tmp_path / "ckpt.db").exists()
