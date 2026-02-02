"""Tests for the designer node.

Test Scenarios from LLD (Issue #56):
- 010: Happy path - LLD generated
- 020: Issue not found
- 030: Forbidden model
- 040: Credentials exhausted
- 050: Generator prompt missing
- 060: Draft written correctly
- 070: Audit entry written
- 080: Empty issue body
- 090: Governance reads from disk
- 100: Model logged correctly
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agentos.core.gemini_client import GeminiCallResult, GeminiErrorType
from agentos.nodes.designer import (
    _fetch_github_issue,
    _human_edit_pause,
    _load_generator_instruction,
    _write_draft,
    design_lld_node,
)
from agentos.nodes.governance import review_lld_node


@pytest.fixture
def mock_state():
    """Create a mock AgentState for Designer Node."""
    return {
        "messages": [],
        "issue_id": 56,
        "worktree_path": "/tmp/test-worktree",
        "lld_content": "",
        "lld_status": "PENDING",
        "lld_draft_path": "",
        "design_status": "PENDING",
        "gemini_critique": "",
        "iteration_count": 0,
    }


@pytest.fixture
def temp_drafts_dir():
    """Create a temporary drafts directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestFetchGithubIssue:
    """Tests for _fetch_github_issue function."""

    def test_020_issue_not_found(self):
        """Test that non-existent issue raises ValueError."""
        # Mock subprocess to return error
        with patch("agentos.nodes.designer.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Could not resolve to an Issue with the number of 99999",
            )

            with pytest.raises(ValueError, match="not found"):
                _fetch_github_issue(99999)

    def test_invalid_issue_id_raises_error(self):
        """Test that invalid issue ID raises ValueError."""
        with pytest.raises(ValueError, match="Invalid issue ID"):
            _fetch_github_issue(-1)

        with pytest.raises(ValueError, match="Invalid issue ID"):
            _fetch_github_issue(0)

    def test_gh_not_installed(self):
        """Test error when gh CLI not installed."""
        with patch("agentos.nodes.designer.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            with pytest.raises(ValueError, match="gh CLI not installed"):
                _fetch_github_issue(56)

    def test_successful_fetch(self):
        """Test successful issue fetch."""
        mock_response = json.dumps({
            "title": "Test Issue",
            "body": "Test body content",
        })

        with patch("agentos.nodes.designer.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_response,
                stderr="",
            )

            title, body = _fetch_github_issue(56)

        assert title == "Test Issue"
        assert body == "Test body content"

    def test_080_empty_issue_body(self):
        """Test issue with empty body."""
        mock_response = json.dumps({
            "title": "Title Only Issue",
            "body": "",
        })

        with patch("agentos.nodes.designer.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_response,
                stderr="",
            )

            title, body = _fetch_github_issue(56)

        assert title == "Title Only Issue"
        assert body == ""


class TestWriteDraft:
    """Tests for _write_draft function."""

    def test_060_draft_written_correctly(self, temp_drafts_dir):
        """Test that draft is written to correct path."""
        content = "# Test LLD\n\n## Context\nTest content"

        with patch("agentos.nodes.designer.LLD_DRAFTS_DIR", temp_drafts_dir):
            draft_path = _write_draft(56, content)

        assert draft_path.exists()
        assert draft_path.name == "56-LLD.md"
        assert draft_path.read_text() == content

    def test_creates_directory_if_missing(self, temp_drafts_dir):
        """Test that drafts directory is created if missing."""
        new_dir = temp_drafts_dir / "new_subdir"
        content = "# Test LLD"

        with patch("agentos.nodes.designer.LLD_DRAFTS_DIR", new_dir):
            draft_path = _write_draft(56, content)

        assert draft_path.exists()
        assert new_dir.exists()


class TestHumanEditPause:
    """Tests for _human_edit_pause function."""

    def test_prints_correct_message(self, temp_drafts_dir, capsys):
        """Test that correct message is printed."""
        draft_path = temp_drafts_dir / "56-LLD.md"

        with patch("builtins.input", return_value=""):
            _human_edit_pause(draft_path)

        captured = capsys.readouterr()
        assert "Draft saved:" in captured.out
        assert "56-LLD.md" in captured.out

    def test_blocks_on_input(self, temp_drafts_dir):
        """Test that function blocks on input."""
        draft_path = temp_drafts_dir / "56-LLD.md"
        input_called = False

        def mock_input(prompt):
            nonlocal input_called
            input_called = True
            assert "Enter" in prompt
            return ""

        with patch("builtins.input", mock_input):
            _human_edit_pause(draft_path)

        assert input_called


class TestDesignLldNode:
    """Tests for design_lld_node function."""

    def test_010_happy_path_lld_generated(self, mock_state, temp_drafts_dir):
        """Test successful LLD generation."""
        mock_issue_response = json.dumps({
            "title": "Test Feature",
            "body": "## Objective\nBuild something",
        })

        mock_gemini_result = GeminiCallResult(
            success=True,
            response="# Generated LLD\n\n## Context\nGenerated content",
            raw_response="{}",
            error_type=None,
            error_message=None,
            credential_used="test-key",
            rotation_occurred=False,
            attempts=1,
            duration_ms=5000,
            model_verified="gemini-3-pro-preview",
        )

        with patch("agentos.nodes.designer.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_issue_response,
                stderr="",
            )

            with patch("agentos.nodes.designer.GeminiClient") as mock_client_class:
                mock_client = MagicMock()
                mock_client.invoke.return_value = mock_gemini_result
                mock_client_class.return_value = mock_client

                with patch("agentos.nodes.designer._load_generator_instruction") as mock_load:
                    mock_load.return_value = "System instruction"

                    with patch("agentos.nodes.designer.LLD_DRAFTS_DIR", temp_drafts_dir):
                        with patch("agentos.nodes.designer.ReviewAuditLog") as mock_log_class:
                            mock_log = MagicMock()
                            mock_log_class.return_value = mock_log

                            with patch("builtins.input", return_value=""):
                                result = design_lld_node(mock_state)

        assert result["design_status"] == "DRAFTED"
        assert result["lld_draft_path"] != ""
        assert result["lld_content"] == ""  # Empty - governance reads from disk
        assert result["iteration_count"] == 1

    def test_020_issue_not_found(self, mock_state):
        """Test that non-existent issue returns FAILED."""
        mock_state["issue_id"] = 99999

        with patch("agentos.nodes.designer.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Could not resolve to an Issue with the number of 99999",
            )

            with patch("agentos.nodes.designer.ReviewAuditLog") as mock_log_class:
                mock_log = MagicMock()
                mock_log_class.return_value = mock_log

                result = design_lld_node(mock_state)

        assert result["design_status"] == "FAILED"
        assert "not found" in result.get("lld_draft_path", "") or result["design_status"] == "FAILED"

    def test_030_forbidden_model(self, mock_state):
        """Test that forbidden model raises ValueError."""
        mock_issue_response = json.dumps({
            "title": "Test",
            "body": "Test body",
        })

        with patch("agentos.nodes.designer.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_issue_response,
                stderr="",
            )

            with patch("agentos.nodes.designer._load_generator_instruction") as mock_load:
                mock_load.return_value = "System instruction"

                # Make GeminiClient raise ValueError for forbidden model
                with patch("agentos.nodes.designer.GeminiClient") as mock_client_class:
                    mock_client_class.side_effect = ValueError(
                        "Model 'gemini-2.5-flash' is explicitly forbidden"
                    )

                    with patch("agentos.nodes.designer.ReviewAuditLog") as mock_log_class:
                        mock_log = MagicMock()
                        mock_log_class.return_value = mock_log

                        result = design_lld_node(mock_state)

        assert result["design_status"] == "FAILED"

    def test_040_credentials_exhausted(self, mock_state):
        """Test that exhausted credentials returns FAILED."""
        mock_issue_response = json.dumps({
            "title": "Test",
            "body": "Test body",
        })

        mock_gemini_result = GeminiCallResult(
            success=False,
            response=None,
            raw_response=None,
            error_type=GeminiErrorType.QUOTA_EXHAUSTED,
            error_message="All credentials exhausted",
            credential_used="",
            rotation_occurred=True,
            attempts=3,
            duration_ms=10000,
            model_verified="",
        )

        with patch("agentos.nodes.designer.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_issue_response,
                stderr="",
            )

            with patch("agentos.nodes.designer.GeminiClient") as mock_client_class:
                mock_client = MagicMock()
                mock_client.invoke.return_value = mock_gemini_result
                mock_client_class.return_value = mock_client

                with patch("agentos.nodes.designer._load_generator_instruction") as mock_load:
                    mock_load.return_value = "System instruction"

                    with patch("agentos.nodes.designer.ReviewAuditLog") as mock_log_class:
                        mock_log = MagicMock()
                        mock_log_class.return_value = mock_log

                        result = design_lld_node(mock_state)

        assert result["design_status"] == "FAILED"

    def test_050_generator_prompt_missing(self, mock_state):
        """Test that missing generator prompt returns FAILED."""
        mock_issue_response = json.dumps({
            "title": "Test",
            "body": "Test body",
        })

        with patch("agentos.nodes.designer.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_issue_response,
                stderr="",
            )

            with patch("agentos.nodes.designer._load_generator_instruction") as mock_load:
                mock_load.side_effect = FileNotFoundError("Generator prompt not found")

                with patch("agentos.nodes.designer.ReviewAuditLog") as mock_log_class:
                    mock_log = MagicMock()
                    mock_log_class.return_value = mock_log

                    result = design_lld_node(mock_state)

        assert result["design_status"] == "FAILED"

    def test_070_audit_entry_written(self, mock_state, temp_drafts_dir):
        """Test that audit entry is written on success."""
        mock_issue_response = json.dumps({
            "title": "Test",
            "body": "Test body",
        })

        mock_gemini_result = GeminiCallResult(
            success=True,
            response="# LLD",
            raw_response="{}",
            error_type=None,
            error_message=None,
            credential_used="test-key",
            rotation_occurred=False,
            attempts=1,
            duration_ms=5000,
            model_verified="gemini-3-pro-preview",
        )

        with patch("agentos.nodes.designer.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_issue_response,
                stderr="",
            )

            with patch("agentos.nodes.designer.GeminiClient") as mock_client_class:
                mock_client = MagicMock()
                mock_client.invoke.return_value = mock_gemini_result
                mock_client_class.return_value = mock_client

                with patch("agentos.nodes.designer._load_generator_instruction") as mock_load:
                    mock_load.return_value = "System instruction"

                    with patch("agentos.nodes.designer.LLD_DRAFTS_DIR", temp_drafts_dir):
                        with patch("agentos.nodes.designer.ReviewAuditLog") as mock_log_class:
                            mock_log = MagicMock()
                            mock_log_class.return_value = mock_log

                            with patch("builtins.input", return_value=""):
                                design_lld_node(mock_state)

        # Verify audit log was called
        mock_log.log.assert_called_once()
        logged_entry = mock_log.log.call_args[0][0]
        assert logged_entry["node"] == "design_lld"
        assert logged_entry["verdict"] == "DRAFTED"

    def test_100_model_logged_correctly(self, mock_state, temp_drafts_dir):
        """Test that model is logged correctly in audit entry."""
        mock_issue_response = json.dumps({
            "title": "Test",
            "body": "Test body",
        })

        mock_gemini_result = GeminiCallResult(
            success=True,
            response="# LLD",
            raw_response="{}",
            error_type=None,
            error_message=None,
            credential_used="test-key",
            rotation_occurred=False,
            attempts=1,
            duration_ms=5000,
            model_verified="gemini-3-pro-preview",
        )

        with patch("agentos.nodes.designer.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_issue_response,
                stderr="",
            )

            with patch("agentos.nodes.designer.GeminiClient") as mock_client_class:
                mock_client = MagicMock()
                mock_client.invoke.return_value = mock_gemini_result
                mock_client_class.return_value = mock_client

                with patch("agentos.nodes.designer._load_generator_instruction") as mock_load:
                    mock_load.return_value = "System instruction"

                    with patch("agentos.nodes.designer.LLD_DRAFTS_DIR", temp_drafts_dir):
                        with patch("agentos.nodes.designer.ReviewAuditLog") as mock_log_class:
                            mock_log = MagicMock()
                            mock_log_class.return_value = mock_log

                            with patch("builtins.input", return_value=""):
                                with patch("agentos.nodes.designer.REVIEWER_MODEL", "gemini-3-pro-preview"):
                                    design_lld_node(mock_state)

        logged_entry = mock_log.log.call_args[0][0]
        assert "gemini-3-pro" in logged_entry["model"]


class TestGovernanceReadsFromDisk:
    """Tests for Designer -> Governance integration (Issue #56)."""

    def test_090_governance_reads_from_disk(self, temp_drafts_dir):
        """Test that Governance Node reads edited LLD from disk."""
        # Create a draft file with EDITED content
        draft_path = temp_drafts_dir / "56-LLD.md"
        edited_content = "# EDITED LLD\n\n## Context\nHuman edited this content"
        draft_path.write_text(edited_content)

        # State has empty lld_content but valid lld_draft_path
        state = {
            "messages": [],
            "issue_id": 56,
            "worktree_path": "/tmp/test",
            "lld_content": "",  # Empty - should be ignored
            "lld_status": "PENDING",
            "lld_draft_path": str(draft_path),  # Points to edited file
            "design_status": "DRAFTED",
            "gemini_critique": "",
            "iteration_count": 1,
        }

        mock_result = GeminiCallResult(
            success=True,
            response="[x] **APPROVED**",
            raw_response="{}",
            error_type=None,
            error_message=None,
            credential_used="test-key",
            rotation_occurred=False,
            attempts=1,
            duration_ms=5000,
            model_verified="gemini-3-pro-preview",
        )

        with patch("agentos.nodes.governance.GeminiClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.invoke.return_value = mock_result
            mock_client_class.return_value = mock_client

            with patch("agentos.nodes.governance._load_system_instruction") as mock_load:
                mock_load.return_value = "System instruction"

                with patch("agentos.nodes.governance.ReviewAuditLog") as mock_log_class:
                    mock_log = MagicMock()
                    mock_log_class.return_value = mock_log

                    result = review_lld_node(state)

        # Verify Gemini was called with the EDITED content from disk
        call_args = mock_client.invoke.call_args
        content_sent = call_args[1]["content"]
        assert "EDITED LLD" in content_sent
        assert "Human edited" in content_sent
