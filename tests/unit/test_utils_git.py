"""Tests for assemblyzero/utils/git.py — canonical branch helpers.

Closes #1758. Written FIRST (TDD) to pin the attempt-branch contract:
integrate into the branch the repo is standing on; never assume main.
Includes the #1756 regression: `speedrun-attempt-1` must NOT be treated
as issue #1's work branch.
"""

from unittest.mock import Mock, patch

import pytest

from assemblyzero.utils.git import (
    GitBranchError,
    current_branch,
    is_generated_work_branch,
    is_issue_work_branch,
    validate_integration_branch,
)


class TestCurrentBranch:
    """current_branch() — detect the checked-out branch, fail loud."""

    @patch("assemblyzero.utils.git.subprocess.run")
    def test_returns_main_when_on_main(self, mock_run):
        mock_run.return_value = Mock(returncode=0, stdout="main\n", stderr="")
        assert current_branch("/some/repo") == "main"

    @patch("assemblyzero.utils.git.subprocess.run")
    def test_returns_attempt_branch_when_checked_out(self, mock_run):
        mock_run.return_value = Mock(
            returncode=0, stdout="speedrun-attempt-1\n", stderr=""
        )
        assert current_branch("/some/repo") == "speedrun-attempt-1"

    @patch("assemblyzero.utils.git.subprocess.run")
    def test_runs_rev_parse_in_given_repo(self, mock_run):
        mock_run.return_value = Mock(returncode=0, stdout="main\n", stderr="")
        current_branch("/some/repo")
        args, kwargs = mock_run.call_args
        assert args[0] == ["git", "rev-parse", "--abbrev-ref", "HEAD"]
        assert kwargs["cwd"] == "/some/repo"

    @patch("assemblyzero.utils.git.subprocess.run")
    def test_detached_head_raises(self, mock_run):
        mock_run.return_value = Mock(returncode=0, stdout="HEAD\n", stderr="")
        with pytest.raises(GitBranchError, match="detached HEAD"):
            current_branch("/some/repo")

    @patch("assemblyzero.utils.git.subprocess.run")
    def test_empty_output_raises(self, mock_run):
        mock_run.return_value = Mock(returncode=0, stdout="\n", stderr="")
        with pytest.raises(GitBranchError):
            current_branch("/some/repo")

    @patch("assemblyzero.utils.git.subprocess.run")
    def test_git_failure_raises(self, mock_run):
        mock_run.return_value = Mock(
            returncode=128, stdout="", stderr="fatal: not a git repository"
        )
        with pytest.raises(GitBranchError, match="not a git repository"):
            current_branch("/some/repo")


class TestIsGeneratedWorkBranch:
    """is_generated_work_branch() — recognize AZ-generated branch names."""

    @pytest.mark.parametrize(
        "branch",
        ["7-lld", "41-implementation", "issue-7", "1754-lld", "issue-1234"],
    )
    def test_generated_patterns_match(self, branch):
        assert is_generated_work_branch(branch) is True

    @pytest.mark.parametrize(
        "branch",
        [
            "main",
            "master",
            "speedrun-attempt-1",
            "83-gitignore-hardening",  # human-named work branch, not generated
            "feature/issue-7",  # not a full match
            "7-lld-extra",
            "my-issue-7",
        ],
    )
    def test_other_branches_do_not_match(self, branch):
        assert is_generated_work_branch(branch) is False


class TestIsIssueWorkBranch:
    """is_issue_work_branch() — exact match for THIS issue only."""

    def test_implementation_branch_matches(self):
        assert is_issue_work_branch("1-implementation", 1) is True

    def test_orchestrator_branch_matches(self):
        assert is_issue_work_branch("issue-1", 1) is True

    def test_speedrun_attempt_1_does_not_match_issue_1(self):
        """THE #1756 regression: substring matching let issue #1 run
        in-place on speedrun-attempt-1 with checkpoints as no-ops."""
        assert is_issue_work_branch("speedrun-attempt-1", 1) is False

    def test_other_issues_branch_does_not_match(self):
        assert is_issue_work_branch("41-implementation", 1) is False

    def test_lld_branch_is_not_an_implementation_branch(self):
        assert is_issue_work_branch("1-lld", 1) is False

    def test_partial_number_does_not_match(self):
        assert is_issue_work_branch("11-implementation", 1) is False


class TestValidateIntegrationBranch:
    """validate_integration_branch() — refuse generated work branches."""

    @pytest.mark.parametrize("branch", ["main", "master", "speedrun-attempt-1", "develop"])
    def test_integration_branches_pass(self, branch):
        validate_integration_branch(branch)  # must not raise

    @pytest.mark.parametrize("branch", ["7-lld", "41-implementation", "issue-7"])
    def test_generated_work_branches_raise(self, branch):
        with pytest.raises(GitBranchError, match="generated work branch"):
            validate_integration_branch(branch)
