"""Unit tests for Requirements Workflow Git Operations.

Issue #194: Increase requirements workflow test coverage

Tests for:
- format_commit_message
- commit_and_push
- GitOperationError
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import subprocess


class TestGitOperationError:
    """Tests for GitOperationError exception."""

    def test_error_can_be_raised(self):
        """Test that GitOperationError can be raised."""
        from agentos.workflows.requirements.git_operations import GitOperationError

        with pytest.raises(GitOperationError) as exc_info:
            raise GitOperationError("test error")

        assert "test error" in str(exc_info.value)


class TestFormatCommitMessage:
    """Tests for format_commit_message function."""

    def test_lld_workflow_message(self):
        """Test commit message for LLD workflow."""
        from agentos.workflows.requirements.git_operations import format_commit_message

        msg = format_commit_message("lld", issue_number=42)

        assert "LLD-42" in msg
        assert "Closes #42" in msg

    def test_issue_workflow_message(self):
        """Test commit message for issue workflow."""
        from agentos.workflows.requirements.git_operations import format_commit_message

        msg = format_commit_message("issue", slug="my-feature")

        assert "my-feature" in msg
        assert "lineage" in msg


class TestCommitAndPush:
    """Tests for commit_and_push function."""

    def test_returns_empty_string_for_empty_files(self, tmp_path):
        """Test returns empty string when no files to commit."""
        from agentos.workflows.requirements.git_operations import commit_and_push

        result = commit_and_push(
            created_files=[],
            workflow_type="lld",
            target_repo=tmp_path,
            issue_number=42,
        )

        assert result == ""

    @patch("subprocess.run")
    def test_stages_each_file(self, mock_run, tmp_path):
        """Test that each file is staged individually."""
        from agentos.workflows.requirements.git_operations import commit_and_push

        mock_run.return_value = Mock(
            returncode=0,
            stdout="[main abc123] commit message",
            stderr="",
        )

        commit_and_push(
            created_files=["file1.md", "file2.md"],
            workflow_type="lld",
            target_repo=tmp_path,
            issue_number=42,
        )

        # Should call git add for each file, then commit, then push
        assert mock_run.call_count >= 3  # 2 adds + 1 commit + 1 push

    @patch("subprocess.run")
    def test_raises_on_stage_failure(self, mock_run, tmp_path):
        """Test raises GitOperationError on git add failure."""
        from agentos.workflows.requirements.git_operations import (
            commit_and_push,
            GitOperationError,
        )

        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="fatal: pathspec 'file.md' did not match any files",
        )

        with pytest.raises(GitOperationError) as exc_info:
            commit_and_push(
                created_files=["file.md"],
                workflow_type="lld",
                target_repo=tmp_path,
                issue_number=42,
            )

        assert "stage" in str(exc_info.value).lower()

    @patch("subprocess.run")
    def test_raises_on_commit_failure(self, mock_run, tmp_path):
        """Test raises GitOperationError on git commit failure."""
        from agentos.workflows.requirements.git_operations import (
            commit_and_push,
            GitOperationError,
        )

        # First call (add) succeeds, second call (commit) fails
        mock_run.side_effect = [
            Mock(returncode=0, stdout="", stderr=""),  # git add
            Mock(returncode=1, stdout="", stderr="nothing to commit"),  # git commit
        ]

        with pytest.raises(GitOperationError) as exc_info:
            commit_and_push(
                created_files=["file.md"],
                workflow_type="lld",
                target_repo=tmp_path,
                issue_number=42,
            )

        assert "commit" in str(exc_info.value).lower()

    @patch("subprocess.run")
    def test_raises_on_push_failure(self, mock_run, tmp_path):
        """Test raises GitOperationError on git push failure."""
        from agentos.workflows.requirements.git_operations import (
            commit_and_push,
            GitOperationError,
        )

        # add succeeds, commit succeeds, push fails
        mock_run.side_effect = [
            Mock(returncode=0, stdout="", stderr=""),  # git add
            Mock(returncode=0, stdout="[main abc123] msg", stderr=""),  # git commit
            Mock(returncode=1, stdout="", stderr="Permission denied"),  # git push
        ]

        with pytest.raises(GitOperationError) as exc_info:
            commit_and_push(
                created_files=["file.md"],
                workflow_type="lld",
                target_repo=tmp_path,
                issue_number=42,
            )

        assert "push" in str(exc_info.value).lower()

    @patch("subprocess.run")
    def test_extracts_commit_sha(self, mock_run, tmp_path):
        """Test that commit SHA is extracted from output."""
        from agentos.workflows.requirements.git_operations import commit_and_push

        mock_run.side_effect = [
            Mock(returncode=0, stdout="", stderr=""),  # git add
            Mock(returncode=0, stdout="[main abc123def] commit msg", stderr=""),  # git commit
            Mock(returncode=0, stdout="", stderr=""),  # git push
        ]

        result = commit_and_push(
            created_files=["file.md"],
            workflow_type="lld",
            target_repo=tmp_path,
            issue_number=42,
        )

        assert result == "abc123def"

    @patch("subprocess.run")
    def test_handles_commit_output_without_sha(self, mock_run, tmp_path):
        """Test handles commit output that doesn't match expected format."""
        from agentos.workflows.requirements.git_operations import commit_and_push

        mock_run.side_effect = [
            Mock(returncode=0, stdout="", stderr=""),  # git add
            Mock(returncode=0, stdout="", stderr=""),  # git commit (no stdout)
            Mock(returncode=0, stdout="", stderr=""),  # git push
        ]

        result = commit_and_push(
            created_files=["file.md"],
            workflow_type="lld",
            target_repo=tmp_path,
            issue_number=42,
        )

        assert result == ""  # No SHA extracted

    @patch("subprocess.run")
    def test_uses_path_as_cwd(self, mock_run, tmp_path):
        """Test that target_repo is used as cwd for git commands."""
        from agentos.workflows.requirements.git_operations import commit_and_push

        mock_run.return_value = Mock(
            returncode=0,
            stdout="[main abc123] msg",
            stderr="",
        )

        commit_and_push(
            created_files=["file.md"],
            workflow_type="lld",
            target_repo=tmp_path,
            issue_number=42,
        )

        # All calls should use target_repo as cwd
        for call in mock_run.call_args_list:
            assert call.kwargs.get("cwd") == str(tmp_path)
