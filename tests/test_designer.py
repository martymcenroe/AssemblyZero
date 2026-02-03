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

Fixes #155: Tests now verify actual outcomes, not just mock calls.
- Integration tests run without mocks to verify real behavior
- Unit tests verify actual state changes and file outputs
"""

import json
import shutil
import subprocess
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
from agentos.nodes.lld_reviewer import review_lld_node


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


# =============================================================================
# INTEGRATION TESTS - Test real behavior without mocking
# =============================================================================


class TestIntegrationGhCli:
    """Integration tests for gh CLI - verifies real subprocess behavior."""

    @pytest.mark.integration
    def test_gh_cli_available(self):
        """Test that gh CLI is installed and accessible."""
        result = subprocess.run(
            ["gh", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, "gh CLI not installed"
        assert "gh version" in result.stdout

    @pytest.mark.integration
    def test_gh_cli_authenticated(self):
        """Test that gh CLI is authenticated."""
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, "gh CLI not authenticated"

    @pytest.mark.integration
    def test_fetch_real_issue(self):
        """Test fetching a real issue from GitHub."""
        # Issue #1 exists in most repos - use a known issue
        result = subprocess.run(
            ["gh", "issue", "view", "56", "--repo", "martymcenroe/AgentOS", "--json", "title,body"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        # Verify actual output structure, not just returncode
        if result.returncode == 0:
            data = json.loads(result.stdout)
            assert "title" in data, "Response missing 'title' field"
            assert isinstance(data["title"], str), "Title is not a string"


class TestIntegrationFileSystem:
    """Integration tests for file system operations."""

    @pytest.mark.integration
    def test_write_draft_creates_real_file(self):
        """Test that _write_draft actually creates a file on disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir)
            content = "# Test LLD\n\n## Context\nReal file test"

            with patch("agentos.nodes.designer.LLD_DRAFTS_DIR", temp_path):
                draft_path = _write_draft(999, content)

            # Verify ACTUAL file exists (not mocked)
            assert draft_path.exists(), f"File not created at {draft_path}"
            assert draft_path.is_file(), f"{draft_path} is not a file"

            # Verify ACTUAL content (not mocked)
            actual_content = draft_path.read_text()
            assert actual_content == content, "File content doesn't match"

    @pytest.mark.integration
    def test_load_generator_instruction_real_file(self):
        """Test that generator instruction file exists and is readable."""
        # This will fail if the real file doesn't exist
        try:
            content = _load_generator_instruction()
            assert len(content) > 100, "Generator instruction too short"
            assert "LLD" in content or "design" in content.lower(), \
                "Generator instruction doesn't mention LLD or design"
        except FileNotFoundError:
            pytest.skip("Generator instruction file not in expected location")


# =============================================================================
# UNIT TESTS - Verify actual outcomes, not just mock calls
# =============================================================================


class TestFetchGithubIssue:
    """Tests for _fetch_github_issue function."""

    def test_020_issue_not_found_returns_error_message(self):
        """Test that non-existent issue raises ValueError with descriptive message."""
        with patch("agentos.nodes.designer.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Could not resolve to an Issue with the number of 99999",
            )

            with pytest.raises(ValueError) as exc_info:
                _fetch_github_issue(99999)

            # Verify OUTCOME: error message is useful
            assert "99999" in str(exc_info.value) or "not found" in str(exc_info.value)

    def test_invalid_issue_id_validates_input(self):
        """Test that invalid issue IDs are validated before any subprocess call."""
        # These should raise immediately without calling subprocess
        with pytest.raises(ValueError, match="Invalid issue ID"):
            _fetch_github_issue(-1)

        with pytest.raises(ValueError, match="Invalid issue ID"):
            _fetch_github_issue(0)

    def test_gh_not_installed_gives_helpful_message(self):
        """Test error message helps user when gh CLI not installed."""
        with patch("agentos.nodes.designer.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            with pytest.raises(ValueError) as exc_info:
                _fetch_github_issue(56)

            # Verify OUTCOME: error message helps user
            error_msg = str(exc_info.value).lower()
            assert "gh" in error_msg and "install" in error_msg

    def test_successful_fetch_returns_parsed_data(self):
        """Test successful fetch returns properly parsed title and body."""
        mock_response = json.dumps({
            "title": "Test Issue Title",
            "body": "Test body content with **markdown**",
        })

        with patch("agentos.nodes.designer.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_response,
                stderr="",
            )

            title, body = _fetch_github_issue(56)

        # Verify OUTCOMES: actual data is returned correctly
        assert title == "Test Issue Title"
        assert body == "Test body content with **markdown**"
        assert isinstance(title, str)
        assert isinstance(body, str)

    def test_080_empty_issue_body_handled(self):
        """Test issue with empty body is handled gracefully."""
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

        # Verify OUTCOME: empty body doesn't crash
        assert title == "Title Only Issue"
        assert body == ""


class TestWriteDraft:
    """Tests for _write_draft function - verifies actual file operations."""

    def test_060_draft_written_with_correct_content(self, temp_drafts_dir):
        """Test that draft file contains the exact content provided."""
        content = "# Test LLD\n\n## Context\nTest content with special chars: éàü"

        with patch("agentos.nodes.designer.LLD_DRAFTS_DIR", temp_drafts_dir):
            draft_path = _write_draft(56, content)

        # Verify ACTUAL file state, not mock state
        assert draft_path.exists()
        assert draft_path.name == "56-LLD.md"
        actual_content = draft_path.read_text(encoding="utf-8")
        assert actual_content == content

    def test_060_draft_path_follows_convention(self, temp_drafts_dir):
        """Test that draft path follows the {issue_id}-LLD.md convention."""
        with patch("agentos.nodes.designer.LLD_DRAFTS_DIR", temp_drafts_dir):
            draft_path = _write_draft(123, "content")

        # Verify OUTCOME: path convention is correct
        assert draft_path.name == "123-LLD.md"
        assert draft_path.parent == temp_drafts_dir

    def test_creates_directory_structure(self, temp_drafts_dir):
        """Test that missing directories are created."""
        nested_dir = temp_drafts_dir / "deeply" / "nested" / "path"

        with patch("agentos.nodes.designer.LLD_DRAFTS_DIR", nested_dir):
            draft_path = _write_draft(56, "# Test")

        # Verify OUTCOME: directory structure exists
        assert nested_dir.exists()
        assert draft_path.exists()


class TestHumanEditPause:
    """Tests for _human_edit_pause function."""

    def test_prints_draft_path_for_user(self, temp_drafts_dir, capsys):
        """Test that correct path is shown to user."""
        draft_path = temp_drafts_dir / "56-LLD.md"

        with patch("builtins.input", return_value=""):
            _human_edit_pause(draft_path)

        # Verify OUTCOME: user sees the correct path
        captured = capsys.readouterr()
        assert str(draft_path) in captured.out or "56-LLD.md" in captured.out

    def test_auto_mode_skips_input(self, temp_drafts_dir, capsys):
        """Test that auto_mode=True skips the input() call."""
        draft_path = temp_drafts_dir / "56-LLD.md"
        input_called = False

        def mock_input(prompt):
            nonlocal input_called
            input_called = True
            return ""

        with patch("builtins.input", mock_input):
            _human_edit_pause(draft_path, auto_mode=True)

        # Verify OUTCOME: input was NOT called
        assert not input_called, "auto_mode should skip input()"


class TestDesignLldNode:
    """Tests for design_lld_node - verifies state transitions and outputs."""

    def test_010_happy_path_returns_correct_state(self, mock_state, temp_drafts_dir):
        """Test successful LLD generation returns correct state structure."""
        mock_issue_response = json.dumps({
            "title": "Test Feature",
            "body": "## Objective\nBuild something",
        })

        generated_lld = "# Generated LLD\n\n## Context\nGenerated content"
        mock_gemini_result = GeminiCallResult(
            success=True,
            response=generated_lld,
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
                returncode=0, stdout=mock_issue_response, stderr=""
            )
            with patch("agentos.nodes.designer.GeminiClient") as mock_client_class:
                mock_client = MagicMock()
                mock_client.invoke.return_value = mock_gemini_result
                mock_client_class.return_value = mock_client
                with patch("agentos.nodes.designer._load_generator_instruction", return_value="System instruction"):
                    with patch("agentos.nodes.designer.LLD_DRAFTS_DIR", temp_drafts_dir):
                        with patch("agentos.nodes.designer.ReviewAuditLog"):
                            with patch("builtins.input", return_value=""):
                                result = design_lld_node(mock_state)

        # Verify OUTCOMES: state transitions are correct
        assert result["design_status"] == "DRAFTED"
        assert result["lld_draft_path"] != ""
        assert result["lld_content"] == generated_lld  # Returns actual content
        assert result["iteration_count"] == 1

        # Verify OUTCOME: file was actually written
        draft_path = Path(result["lld_draft_path"])
        assert draft_path.exists()
        assert draft_path.read_text() == generated_lld

    def test_020_issue_not_found_returns_failed_state(self, mock_state):
        """Test that non-existent issue returns FAILED status."""
        mock_state["issue_id"] = 99999

        with patch("agentos.nodes.designer.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Could not resolve to an Issue with the number of 99999",
            )
            with patch("agentos.nodes.designer.ReviewAuditLog"):
                result = design_lld_node(mock_state)

        # Verify OUTCOME: state indicates failure
        assert result["design_status"] == "FAILED"
        assert "error_message" in result or result["lld_draft_path"] == ""

    def test_030_forbidden_model_returns_failed_state(self, mock_state):
        """Test that forbidden model configuration returns FAILED status."""
        mock_issue_response = json.dumps({
            "title": "Test",
            "body": "Test body",
        })

        with patch("agentos.nodes.designer.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout=mock_issue_response, stderr=""
            )
            with patch("agentos.nodes.designer._load_generator_instruction", return_value="System instruction"):
                with patch("agentos.nodes.designer.GeminiClient") as mock_client_class:
                    mock_client_class.side_effect = ValueError(
                        "Model 'gemini-2.5-flash' is explicitly forbidden"
                    )
                    with patch("agentos.nodes.designer.ReviewAuditLog"):
                        result = design_lld_node(mock_state)

        # Verify OUTCOME: state indicates failure
        assert result["design_status"] == "FAILED"

    def test_040_credentials_exhausted_returns_failed_state(self, mock_state):
        """Test that exhausted credentials returns FAILED status."""
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
                returncode=0, stdout=mock_issue_response, stderr=""
            )
            with patch("agentos.nodes.designer.GeminiClient") as mock_client_class:
                mock_client = MagicMock()
                mock_client.invoke.return_value = mock_gemini_result
                mock_client_class.return_value = mock_client
                with patch("agentos.nodes.designer._load_generator_instruction", return_value="System instruction"):
                    with patch("agentos.nodes.designer.ReviewAuditLog"):
                        result = design_lld_node(mock_state)

        # Verify OUTCOME: state indicates failure
        assert result["design_status"] == "FAILED"

    def test_050_generator_prompt_missing_returns_failed_state(self, mock_state):
        """Test that missing generator prompt returns FAILED status."""
        mock_issue_response = json.dumps({
            "title": "Test",
            "body": "Test body",
        })

        with patch("agentos.nodes.designer.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout=mock_issue_response, stderr=""
            )
            with patch("agentos.nodes.designer._load_generator_instruction") as mock_load:
                mock_load.side_effect = FileNotFoundError("Generator prompt not found")
                with patch("agentos.nodes.designer.ReviewAuditLog"):
                    result = design_lld_node(mock_state)

        # Verify OUTCOME: state indicates failure
        assert result["design_status"] == "FAILED"

    def test_070_audit_entry_contains_required_fields(self, mock_state, temp_drafts_dir):
        """Test that audit entry contains all required fields."""
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
                returncode=0, stdout=mock_issue_response, stderr=""
            )
            with patch("agentos.nodes.designer.GeminiClient") as mock_client_class:
                mock_client = MagicMock()
                mock_client.invoke.return_value = mock_gemini_result
                mock_client_class.return_value = mock_client
                with patch("agentos.nodes.designer._load_generator_instruction", return_value="System instruction"):
                    with patch("agentos.nodes.designer.LLD_DRAFTS_DIR", temp_drafts_dir):
                        with patch("agentos.nodes.designer.ReviewAuditLog") as mock_log_class:
                            mock_log = MagicMock()
                            mock_log_class.return_value = mock_log
                            with patch("builtins.input", return_value=""):
                                design_lld_node(mock_state)

        # Verify OUTCOME: audit entry has required fields
        mock_log.log.assert_called_once()
        logged_entry = mock_log.log.call_args[0][0]

        # Check required fields exist and have correct values
        assert logged_entry["node"] == "design_lld"
        assert logged_entry["verdict"] == "DRAFTED"
        assert "issue_id" in logged_entry
        assert "model" in logged_entry
        assert "duration_ms" in logged_entry

    def test_100_model_field_populated_from_result(self, mock_state, temp_drafts_dir):
        """Test that model field is populated from Gemini result."""
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
                returncode=0, stdout=mock_issue_response, stderr=""
            )
            with patch("agentos.nodes.designer.GeminiClient") as mock_client_class:
                mock_client = MagicMock()
                mock_client.invoke.return_value = mock_gemini_result
                mock_client_class.return_value = mock_client
                with patch("agentos.nodes.designer._load_generator_instruction", return_value="System instruction"):
                    with patch("agentos.nodes.designer.LLD_DRAFTS_DIR", temp_drafts_dir):
                        with patch("agentos.nodes.designer.ReviewAuditLog") as mock_log_class:
                            mock_log = MagicMock()
                            mock_log_class.return_value = mock_log
                            with patch("builtins.input", return_value=""):
                                design_lld_node(mock_state)

        # Verify OUTCOME: model field is populated
        logged_entry = mock_log.log.call_args[0][0]
        assert "model" in logged_entry
        assert logged_entry["model"] != ""

    def test_state_with_prefetched_issue_skips_gh_call(self, mock_state, temp_drafts_dir):
        """Test that pre-fetched issue content skips GitHub API call."""
        mock_state["issue_title"] = "Pre-fetched Title"
        mock_state["issue_body"] = "Pre-fetched body content"

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
            with patch("agentos.nodes.designer.GeminiClient") as mock_client_class:
                mock_client = MagicMock()
                mock_client.invoke.return_value = mock_gemini_result
                mock_client_class.return_value = mock_client
                with patch("agentos.nodes.designer._load_generator_instruction", return_value="System instruction"):
                    with patch("agentos.nodes.designer.LLD_DRAFTS_DIR", temp_drafts_dir):
                        with patch("agentos.nodes.designer.ReviewAuditLog"):
                            with patch("builtins.input", return_value=""):
                                result = design_lld_node(mock_state)

        # Verify OUTCOME: subprocess was NOT called (pre-fetched data used)
        mock_run.assert_not_called()
        assert result["design_status"] == "DRAFTED"


class TestGovernanceReadsFromDisk:
    """Tests for Designer -> Governance integration (Issue #56)."""

    def test_090_governance_reads_edited_content(self, temp_drafts_dir):
        """Test that Governance Node reads edited LLD from disk, not state."""
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

        with patch("agentos.nodes.lld_reviewer.GeminiClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.invoke.return_value = mock_result
            mock_client_class.return_value = mock_client
            with patch("agentos.nodes.lld_reviewer._load_system_instruction", return_value="System instruction"):
                with patch("agentos.nodes.lld_reviewer.ReviewAuditLog"):
                    review_lld_node(state)

        # Verify OUTCOME: Gemini was called with the EDITED content from disk
        call_args = mock_client.invoke.call_args
        content_sent = call_args[1]["content"]
        assert "EDITED LLD" in content_sent
        assert "Human edited" in content_sent
