"""The requirements workflow's git operations under standard 0034 (#3585).

Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md (base ``79e18ad1``), for
``assemblyzero/workflows/requirements/git_operations.py``. A fetch of the arc
that fails raises with git's stderr, where the worktree was cut from whatever
stale ref was on disk; the two answers that are not failures stay answers (no
``origin`` remote, and an origin that does not carry the branch, both of which
fall back to the local base, #2684). A worktree that reuses an existing branch
is refused when that branch does not descend from the arc. A commit's SHA is
read with ``git rev-parse HEAD`` and raises when it cannot be, where it was
parsed out of ``git commit``'s summary line and silently left "".
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from assemblyzero.workflows.requirements import git_operations as go
from assemblyzero.workflows.requirements.git_operations import GitOperationError


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repo with a `main` and an `arc` branch, and no remote."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    (root / "README.md").write_text("seed\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "seed")
    _git(root, "branch", "arc")
    (root / "data").mkdir()
    return root


class TestTheArcFetch:
    def test_116_a_fetch_that_fails_raises_with_its_stderr(self, repo, tmp_path):
        _git(repo, "remote", "add", "origin", str(tmp_path / "moved-away.git"))

        with pytest.raises(GitOperationError) as raised:
            go.lld_start_point(repo, "arc")
        message = str(raised.value)
        assert "fetch" in message
        assert "rc=" in message
        assert "moved-away.git" in message

    def test_no_origin_remote_falls_back_to_the_local_base(self, repo):
        """Kept: a local-only repo has nothing to fetch (#2684)."""
        assert go.lld_start_point(repo, "arc") == "arc"

    def test_an_origin_without_the_branch_falls_back_to_the_local_base(self, repo, tmp_path):
        """Kept: an arc not pushed yet is cut from the local branch (#2684)."""
        upstream = tmp_path / "up.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(upstream)],
                       check=True, capture_output=True)
        _git(repo, "remote", "add", "origin", str(upstream))
        _git(repo, "push", "-q", "origin", "main")

        assert go.lld_start_point(repo, "arc") == "arc"

    def test_an_origin_with_the_branch_is_preferred(self, repo, tmp_path):
        upstream = tmp_path / "up.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(upstream)],
                       check=True, capture_output=True)
        _git(repo, "remote", "add", "origin", str(upstream))
        _git(repo, "push", "-q", "origin", "arc")

        assert go.lld_start_point(repo, "arc") == "origin/arc"


class TestTheWorktreeCut:
    def test_180_a_reused_branch_that_is_not_on_the_arc_is_refused(self, repo):
        # A stale 7-lld branch from an aborted run, cut from somewhere else.
        _git(repo, "switch", "-q", "--orphan", "elsewhere")
        (repo / "other.txt").write_text("unrelated\n", encoding="utf-8")
        _git(repo, "add", "other.txt")
        _git(repo, "commit", "-q", "-m", "unrelated history")
        _git(repo, "branch", "7-lld")
        _git(repo, "switch", "-q", "main")

        with pytest.raises(GitOperationError) as raised:
            go.setup_lld_worktree(repo, 7, base_branch="arc")
        message = str(raised.value)
        assert "7-lld" in message
        assert "arc" in message
        assert not go.lld_worktree_path_for(repo, 7).exists()

    def test_a_reused_branch_on_the_arc_is_accepted(self, repo):
        """Kept: a prior aborted run's branch, cut from the arc, is reused."""
        _git(repo, "branch", "7-lld", "arc")

        path, branch = go.setup_lld_worktree(repo, 7, base_branch="arc")
        assert branch == "7-lld"
        assert path.is_dir()


class TestTheCommitSha:
    def test_265_the_sha_comes_from_rev_parse(self, tmp_path):
        """A root commit's summary is `[main (root-commit) abc1234] ...`; the
        old parse returned `(root-commit)` as the SHA."""
        responses = [
            Mock(returncode=0, stdout="", stderr=""),  # git add
            Mock(returncode=0, stdout="[main (root-commit) abc1234] docs", stderr=""),
            Mock(returncode=0, stdout="abc1234\n", stderr=""),  # git rev-parse
        ]
        landing = Mock(pr_number=0, pr_url="https://example.test/pull/1")
        with patch.object(go, "run_command", side_effect=responses + [Mock(returncode=1)]), \
             patch.object(go.merge_driver, "land", return_value=landing):
            sha, url = go.commit_and_pr(
                [str(tmp_path / "LLD-007.md")], tmp_path, tmp_path, 7, "7-lld", "main",
            )
        assert sha == "abc1234"
        assert url == "https://example.test/pull/1"

    def test_265_a_sha_that_cannot_be_read_raises(self, tmp_path):
        responses = [
            Mock(returncode=0, stdout="", stderr=""),
            Mock(returncode=0, stdout="", stderr=""),
            Mock(returncode=128, stdout="", stderr="fatal: bad HEAD"),
        ]
        never = Mock(side_effect=AssertionError("nothing may land without its SHA"))
        with patch.object(go, "run_command", side_effect=responses), \
             patch.object(go.merge_driver, "land", never), \
             pytest.raises(GitOperationError, match="rev-parse HEAD") as raised:
            go.commit_and_pr(
                [str(tmp_path / "LLD-007.md")], tmp_path, tmp_path, 7, "7-lld", "main",
            )
        assert "bad HEAD" in str(raised.value)

    def test_395_a_sha_that_cannot_be_read_raises(self, tmp_path):
        responses = [
            Mock(returncode=0, stdout="", stderr=""),
            Mock(returncode=0, stdout="", stderr=""),
            Mock(returncode=128, stdout="", stderr="fatal: bad HEAD"),
        ]
        with patch.object(go, "run_command", side_effect=responses), \
             pytest.raises(GitOperationError, match="rev-parse HEAD") as raised:
            go.commit_and_push(["a.md"], "lld", tmp_path, issue_number=7)
        assert "bad HEAD" in str(raised.value)

    def test_395_the_sha_comes_from_rev_parse(self, tmp_path):
        responses = [
            Mock(returncode=0, stdout="", stderr=""),
            Mock(returncode=0, stdout="[main (root-commit) def5678] docs", stderr=""),
            Mock(returncode=0, stdout="def5678\n", stderr=""),
            Mock(returncode=0, stdout="", stderr=""),  # git push
        ]
        with patch.object(go, "run_command", side_effect=responses):
            assert go.commit_and_push(["a.md"], "lld", tmp_path, issue_number=7) == "def5678"


class TestTheRepoArg:
    def test_330_an_origin_that_cannot_be_read_is_best_effort(self, tmp_path):
        """Compliant, pinned: "" is the documented answer, and commit_and_pr
        then uses the driver's own PR URL."""
        with patch.object(go, "run_command", return_value=Mock(returncode=2, stdout="")):
            assert go._resolve_repo_arg(tmp_path) == ""
