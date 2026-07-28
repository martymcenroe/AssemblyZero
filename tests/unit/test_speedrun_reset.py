"""
Post-cut sweep behavior for tools/speedrun_reset.py.

A CUT take leaves worktrees, work branches, and an open LLD PR behind. The
reset tool predates the attempt-branch model (#1759/#1755), so this suite
pins the two properties that model requires:

- the sweep never touches the attempt branch it is standing on;
- the sweep never destroys uncommitted work, and never escalates to (or
  advertises) a force-delete when git refuses.

Issue: #1762
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tools"))

from speedrun_reset import (
    close_open_prs,
    current_branch,
    delete_local_branches,
    relocate_lld_artifacts,
    remove_worktree,
    worktree_is_dirty,
)

TOOL_SOURCE = (Path(__file__).parent.parent.parent / "tools" / "speedrun_reset.py").read_text(
    encoding="utf-8"
)


def _completed(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(
        args=["git"], returncode=returncode, stdout=stdout, stderr=stderr
    )


class TestBranchSweepIsAttemptBranchAware:

    def test_never_deletes_the_checked_out_branch(self, tmp_path):
        """
        The attempt branch is what the run stands on. Even if it somehow
        matched the issue glob, deleting it would cut the branch out from
        under the attempt.
        """
        calls = []

        def fake_run(cmd, cwd=None, check=False):
            calls.append(cmd)
            if cmd[:3] == ["git", "branch", "--list"]:
                return _completed(stdout="  1234-lld\n* 1234-attempt\n")
            if cmd[:3] == ["git", "rev-parse", "--abbrev-ref"]:
                return _completed(stdout="1234-attempt\n")
            return _completed()

        with patch("speedrun_reset._run", side_effect=fake_run):
            deleted = delete_local_branches(tmp_path, 1234)

        assert deleted == 1
        deletions = [c for c in calls if c[:3] == ["git", "branch", "-d"]]
        assert deletions == [["git", "branch", "-d", "1234-lld"]]

    def test_impl_branch_issue_n_is_swept(self, tmp_path):
        """#1862: the pipeline's issue-{N} impl branch is a candidate too."""
        calls = []

        def fake_run(cmd, cwd=None, check=False):
            calls.append(cmd)
            if cmd[:3] == ["git", "branch", "--list"]:
                return _completed(stdout="  issue-7\n  7-lld\n")
            if cmd[:2] == ["git", "rev-parse"]:
                return _completed(stdout="hardening-run-11\n")
            return _completed()

        with patch("speedrun_reset._run", side_effect=fake_run):
            deleted = delete_local_branches(tmp_path, 7)

        assert deleted == 2
        list_call = next(c for c in calls if c[:3] == ["git", "branch", "--list"])
        assert "issue-7" in list_call
        deleted_branches = [c[3] for c in calls if c[:3] == ["git", "branch", "-d"]]
        assert "issue-7" in deleted_branches
        assert "7-lld" in deleted_branches

    def test_attempt_branch_does_not_match_the_issue_glob(self, tmp_path):
        """Enumeration is scoped to `{issue}-*`; `attempt-test-1` is not swept."""
        with patch("speedrun_reset._run", return_value=_completed(stdout="")) as run:
            delete_local_branches(tmp_path, 1234)
        listing = run.call_args_list[0].args[0]
        assert listing == ["git", "branch", "--list", "1234-*"]

    def test_unmerged_branch_is_left_alone_without_suggesting_force_delete(
        self, tmp_path, capsys
    ):
        def fake_run(cmd, cwd=None, check=False):
            if cmd[:3] == ["git", "branch", "--list"]:
                return _completed(stdout="  1234-implementation\n")
            if cmd[:3] == ["git", "rev-parse", "--abbrev-ref"]:
                return _completed(stdout="attempt-test-1\n")
            if cmd[:3] == ["git", "branch", "-d"]:
                return _completed(returncode=1, stderr="not fully merged")
            return _completed()

        with patch("speedrun_reset._run", side_effect=fake_run):
            deleted = delete_local_branches(tmp_path, 1234)

        assert deleted == 0
        out = capsys.readouterr().out
        assert "unmerged commits" in out
        assert "-D" not in out, "must never advertise a force-delete to the operator"

    def test_source_contains_no_force_delete_instruction(self):
        """
        Guard against reintroduction. The tool previously printed
        `git branch -D` as a suggestion -- an instructed ban is an
        executed ban.
        """
        assert "branch -D" not in TOOL_SOURCE
        assert "worktree remove --force" not in TOOL_SOURCE


class TestWorktreeSweepPreservesWork:

    def test_dirty_worktree_is_left_in_place(self, tmp_path, capsys):
        """git refused, and the tree holds work -- respect the refusal."""
        repo = tmp_path / "repo"
        repo.mkdir()
        worktree = tmp_path / "repo-1234"
        worktree.mkdir()

        def fake_run(cmd, cwd=None, check=False):
            if cmd[:3] == ["git", "worktree", "remove"]:
                return _completed(returncode=1, stderr="contains modified files")
            if cmd[:3] == ["git", "status", "--porcelain"]:
                return _completed(stdout=" M src/thing.py\n")
            return _completed()

        with patch("speedrun_reset._run", side_effect=fake_run):
            removed = remove_worktree(repo, 1234)

        assert removed is False
        assert worktree.exists(), "a worktree holding work must survive the sweep"
        out = capsys.readouterr().out
        assert "uncommitted work" in out

    def test_unreadable_worktree_is_treated_as_holding_work(self, tmp_path):
        """If status cannot be read, assume work is present rather than delete."""
        with patch("speedrun_reset._run", return_value=_completed(returncode=128)):
            assert worktree_is_dirty(tmp_path) is True

    def test_clean_unregistered_directory_is_removed(self, tmp_path, capsys):
        repo = tmp_path / "repo"
        repo.mkdir()
        worktree = tmp_path / "repo-1234"
        worktree.mkdir()
        (worktree / "leftover.txt").write_text("x", encoding="utf-8")

        def fake_run(cmd, cwd=None, check=False):
            if cmd[:3] == ["git", "worktree", "remove"]:
                return _completed(returncode=1, stderr="is not a working tree")
            if cmd[:3] == ["git", "status", "--porcelain"]:
                return _completed(stdout="")
            return _completed()

        with patch("speedrun_reset._run", side_effect=fake_run):
            removed = remove_worktree(repo, 1234)

        assert removed is True
        assert not worktree.exists()

    def test_successful_removal_prunes_stale_registration(self, tmp_path):
        """
        Without a prune, git keeps the path registered and the next
        `worktree add` there fails as already-registered.
        """
        repo = tmp_path / "repo"
        repo.mkdir()
        worktree = tmp_path / "repo-1234"
        worktree.mkdir()
        calls = []

        def fake_run(cmd, cwd=None, check=False):
            calls.append(cmd)
            return _completed()

        with patch("speedrun_reset._run", side_effect=fake_run):
            assert remove_worktree(repo, 1234) is True

        assert ["git", "worktree", "prune"] in calls

    def test_missing_worktree_is_not_an_error(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        assert remove_worktree(repo, 1234) is False

    def test_lld_worktree_is_swept_too(self, tmp_path, capsys):
        """#1848: the requirements workflow's -lld worktree is also debris."""
        repo = tmp_path / "repo"
        repo.mkdir()
        lld_worktree = tmp_path / "repo-1234-lld"
        lld_worktree.mkdir()
        calls = []

        def fake_run(cmd, cwd=None, check=False):
            calls.append(cmd)
            return _completed()

        with patch("speedrun_reset._run", side_effect=fake_run):
            assert remove_worktree(repo, 1234) is True

        removed_paths = [
            cmd[3] for cmd in calls if cmd[:3] == ["git", "worktree", "remove"]
        ]
        assert str(lld_worktree) in removed_paths

    def test_both_worktrees_swept_in_one_call(self, tmp_path):
        """#1848: base and -lld worktrees both targeted."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (tmp_path / "repo-1234").mkdir()
        (tmp_path / "repo-1234-lld").mkdir()
        calls = []

        def fake_run(cmd, cwd=None, check=False):
            calls.append(cmd)
            return _completed()

        with patch("speedrun_reset._run", side_effect=fake_run):
            assert remove_worktree(repo, 1234) is True

        removed_paths = [
            cmd[3] for cmd in calls if cmd[:3] == ["git", "worktree", "remove"]
        ]
        assert str(tmp_path / "repo-1234") in removed_paths
        assert str(tmp_path / "repo-1234-lld") in removed_paths


class TestArtifactRelocation:
    """#1849: untracked LLD/spec artifacts must leave the docs/lld tree."""

    def _make_repo(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / "docs" / "lld" / "active").mkdir(parents=True)
        (repo / "docs" / "lld" / "drafts").mkdir(parents=True)
        return repo

    def test_untracked_artifacts_relocated(self, tmp_path, capsys):
        repo = self._make_repo(tmp_path)
        lld = repo / "docs" / "lld" / "active" / "LLD-007.md"
        lld.write_text("# LLD", encoding="utf-8")
        spec = repo / "docs" / "lld" / "drafts" / "spec-0007-implementation-readiness.md"
        spec.write_text("# spec", encoding="utf-8")

        # git ls-files --error-unmatch: nonzero == untracked
        with patch("speedrun_reset._run", return_value=_completed(returncode=1)):
            moved = relocate_lld_artifacts(repo, 7)

        assert moved == 2
        dest = repo / "data" / "speedrun" / "reset-artifacts" / "issue-7"
        assert (dest / "LLD-007.md").exists()
        assert (dest / "spec-0007-implementation-readiness.md").exists()
        assert not lld.exists()
        assert not spec.exists()
        # emptied drafts dir is itself debris
        assert not (repo / "docs" / "lld" / "drafts").exists()

    def test_tracked_artifact_left_alone(self, tmp_path):
        repo = self._make_repo(tmp_path)
        lld = repo / "docs" / "lld" / "active" / "LLD-007.md"
        lld.write_text("# LLD", encoding="utf-8")

        # git ls-files --error-unmatch: zero == tracked, deliberate content
        with patch("speedrun_reset._run", return_value=_completed(returncode=0)):
            moved = relocate_lld_artifacts(repo, 7)

        assert moved == 0
        assert lld.exists()

    def test_no_artifacts_is_not_an_error(self, tmp_path):
        repo = self._make_repo(tmp_path)
        with patch("speedrun_reset._run", return_value=_completed(returncode=1)):
            assert relocate_lld_artifacts(repo, 7) == 0

    def test_collision_gets_numeric_suffix(self, tmp_path):
        repo = self._make_repo(tmp_path)
        lld = repo / "docs" / "lld" / "active" / "LLD-007.md"
        lld.write_text("# second run", encoding="utf-8")
        dest_dir = repo / "data" / "speedrun" / "reset-artifacts" / "issue-7"
        dest_dir.mkdir(parents=True)
        (dest_dir / "LLD-007.md").write_text("# first run", encoding="utf-8")

        with patch("speedrun_reset._run", return_value=_completed(returncode=1)):
            moved = relocate_lld_artifacts(repo, 7)

        assert moved == 1
        assert (dest_dir / "LLD-007.1.md").read_text(encoding="utf-8") == "# second run"
        assert (dest_dir / "LLD-007.md").read_text(encoding="utf-8") == "# first run"


class TestPrEnumerationIsBaseAgnostic:

    def test_pr_search_does_not_filter_by_base_branch(self):
        """
        PRs raised during an attempt target the attempt branch, not main.
        Filtering by base would make the sweep miss every one of them.
        """
        with patch("speedrun_reset._run", return_value=_completed(stdout="[]")) as run:
            close_open_prs("owner/repo", 1234)
        cmd = run.call_args.args[0]
        assert "--base" not in cmd
        assert "Closes #1234" in cmd


class TestCurrentBranch:

    def test_returns_branch_name(self, tmp_path):
        with patch("speedrun_reset._run", return_value=_completed(stdout="attempt-test-1\n")):
            assert current_branch(tmp_path) == "attempt-test-1"

    def test_returns_empty_string_when_undetermined(self, tmp_path):
        with patch("speedrun_reset._run", return_value=_completed(returncode=128)):
            assert current_branch(tmp_path) == ""
