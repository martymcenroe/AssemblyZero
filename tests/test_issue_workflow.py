"""Tests for Issue creation workflow (Issue #62).

Tests cover:
- N0: Brief loading and slug generation
- N1: Pre-flight checks (VS Code, gh)
- N2: Claude drafting
- N3: Human edit draft routing
- N4: Gemini review
- N5: Human edit verdict routing
- N6: Issue filing and error handling
- Audit trail management
- State persistence
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agentos.workflows.issue.audit import (
    generate_slug,
    next_file_number,
    save_audit_file,
    save_filed_metadata,
    slug_exists,
)
from agentos.workflows.issue.nodes.file_issue import (
    parse_labels_from_draft,
    parse_title_from_draft,
)
from agentos.workflows.issue.nodes.load_brief import load_brief
from agentos.workflows.issue.nodes.sandbox import (
    check_gh_authenticated,
    check_vscode_available,
)
from agentos.workflows.issue.state import (
    HumanDecision,
    IssueWorkflowState,
    SlugCollisionChoice,
)


class TestSlugGeneration:
    """Test slug generation from brief filenames."""

    def test_simple_filename(self):
        """Test simple filename conversion."""
        assert generate_slug("governance-notes.md") == "governance-notes"

    def test_spaces_to_hyphens(self):
        """Test spaces converted to hyphens."""
        assert generate_slug("My Feature Ideas.md") == "my-feature-ideas"

    def test_underscores_to_hyphens(self):
        """Test underscores converted to hyphens."""
        assert generate_slug("auth_redesign_notes.md") == "auth-redesign-notes"

    def test_removes_special_chars(self):
        """Test special characters removed."""
        assert generate_slug("feature!@#$%notes.md") == "featurenotes"

    def test_collapses_multiple_hyphens(self):
        """Test multiple hyphens collapsed."""
        assert generate_slug("feature---notes.md") == "feature-notes"

    def test_full_path(self):
        """Test with full path - only uses filename."""
        assert generate_slug("/path/to/my-brief.md") == "my-brief"


class TestAuditFileNumbering:
    """Test sequential file numbering in audit trail."""

    def test_empty_directory(self, tmp_path):
        """Test first file gets number 1."""
        assert next_file_number(tmp_path) == 1

    def test_increments_after_existing(self, tmp_path):
        """Test increments past existing files."""
        (tmp_path / "001-brief.md").touch()
        (tmp_path / "002-draft.md").touch()
        assert next_file_number(tmp_path) == 3

    def test_handles_gaps(self, tmp_path):
        """Test finds max even with gaps."""
        (tmp_path / "001-brief.md").touch()
        (tmp_path / "005-draft.md").touch()
        assert next_file_number(tmp_path) == 6

    def test_ignores_non_numbered(self, tmp_path):
        """Test ignores files without NNN- prefix."""
        (tmp_path / "readme.md").touch()
        (tmp_path / "001-brief.md").touch()
        assert next_file_number(tmp_path) == 2


class TestAuditFileSaving:
    """Test audit file saving."""

    def test_save_creates_file(self, tmp_path):
        """Test file is created with correct name."""
        path = save_audit_file(tmp_path, 1, "brief.md", "# My Brief")
        assert path.exists()
        assert path.name == "001-brief.md"

    def test_save_content_correct(self, tmp_path):
        """Test content is saved correctly."""
        content = "# Test Content\n\nWith multiple lines."
        path = save_audit_file(tmp_path, 42, "draft.md", content)
        assert path.read_text() == content

    def test_save_numbered_correctly(self, tmp_path):
        """Test three-digit padding."""
        path = save_audit_file(tmp_path, 7, "feedback.txt", "Fix diagrams")
        assert path.name == "007-feedback.txt"


class TestFiledMetadata:
    """Test filed.json metadata."""

    def test_creates_json(self, tmp_path):
        """Test JSON file is created."""
        path = save_filed_metadata(
            tmp_path,
            number=10,
            issue_number=62,
            issue_url="https://github.com/owner/repo/issues/62",
            title="Test Issue",
            brief_file="test-brief.md",
            total_iterations=5,
            draft_count=3,
            verdict_count=2,
        )
        assert path.exists()
        assert path.name == "010-filed.json"

    def test_json_content(self, tmp_path):
        """Test JSON contains correct fields."""
        path = save_filed_metadata(
            tmp_path,
            number=1,
            issue_number=123,
            issue_url="https://example.com/issues/123",
            title="My Issue",
            brief_file="brief.md",
            total_iterations=10,
            draft_count=4,
            verdict_count=3,
        )
        data = json.loads(path.read_text())
        assert data["issue_number"] == 123
        assert data["title"] == "My Issue"
        assert data["draft_count"] == 4
        assert "filed_at" in data


class TestLoadBrief:
    """Test N0 load_brief node."""

    def test_missing_brief_file(self):
        """Test error when brief file not specified."""
        state: IssueWorkflowState = {"brief_file": ""}
        result = load_brief(state)
        assert "error_message" in result
        assert "No brief file" in result["error_message"]

    def test_brief_not_found(self):
        """Test error when brief file doesn't exist."""
        state: IssueWorkflowState = {"brief_file": "/nonexistent/file.md"}
        result = load_brief(state)
        assert "error_message" in result
        assert "not found" in result["error_message"]

    @patch("agentos.workflows.issue.nodes.load_brief.get_repo_root")
    @patch("agentos.workflows.issue.nodes.load_brief.slug_exists")
    @patch("agentos.workflows.issue.nodes.load_brief.create_audit_dir")
    @patch("agentos.workflows.issue.nodes.load_brief.save_audit_file")
    def test_loads_brief_content(
        self, mock_save, mock_create, mock_exists, mock_root, tmp_path
    ):
        """Test brief content is loaded."""
        # Create temp brief file
        brief_path = tmp_path / "test-brief.md"
        brief_path.write_text("# My Brief\n\nContent here.")

        mock_root.return_value = tmp_path
        mock_exists.return_value = False
        mock_create.return_value = tmp_path / "docs/audit/active/test-brief"

        state: IssueWorkflowState = {"brief_file": str(brief_path)}
        result = load_brief(state)

        assert result.get("brief_content") == "# My Brief\n\nContent here."
        assert result.get("slug") == "test-brief"

    @patch("agentos.workflows.issue.nodes.load_brief.get_repo_root")
    @patch("agentos.workflows.issue.nodes.load_brief.slug_exists")
    def test_detects_slug_collision(self, mock_exists, mock_root, tmp_path):
        """Test collision detection."""
        brief_path = tmp_path / "existing.md"
        brief_path.write_text("content")

        mock_root.return_value = tmp_path
        mock_exists.return_value = True  # Simulate collision

        state: IssueWorkflowState = {"brief_file": str(brief_path)}
        result = load_brief(state)

        assert "SLUG_COLLISION" in result.get("error_message", "")


class TestPreFlightChecks:
    """Test N1 sandbox pre-flight checks."""

    @patch("shutil.which")
    def test_vscode_not_found(self, mock_which):
        """Test error when VS Code not in PATH."""
        mock_which.return_value = None
        ok, error = check_vscode_available()
        assert not ok
        assert "VS Code CLI not found" in error

    @patch("shutil.which")
    def test_vscode_found(self, mock_which):
        """Test success when VS Code is available."""
        mock_which.return_value = "/usr/bin/code"
        ok, error = check_vscode_available()
        assert ok
        assert error == ""

    @patch("shutil.which")
    def test_gh_not_found(self, mock_which):
        """Test error when gh not in PATH."""
        mock_which.return_value = None
        ok, error = check_gh_authenticated()
        assert not ok
        assert "gh" in error.lower()

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_gh_not_authenticated(self, mock_run, mock_which):
        """Test error when gh not authenticated."""
        mock_which.return_value = "/usr/bin/gh"
        mock_run.return_value = MagicMock(returncode=1, stderr="not logged in")
        ok, error = check_gh_authenticated()
        assert not ok
        assert "not authenticated" in error.lower()


class TestLabelParsing:
    """Test label parsing from draft."""

    def test_parse_backtick_labels(self):
        """Test parsing labels with backticks."""
        draft = """# Title

Some content.

**Labels:** `enhancement`, `langgraph`, `governance`
"""
        labels = parse_labels_from_draft(draft)
        assert labels == ["enhancement", "langgraph", "governance"]

    def test_parse_no_labels(self):
        """Test when no labels line."""
        draft = "# Title\n\nNo labels here."
        labels = parse_labels_from_draft(draft)
        assert labels == []

    def test_parse_single_label(self):
        """Test single label."""
        draft = "**Labels:** `bug`"
        labels = parse_labels_from_draft(draft)
        assert labels == ["bug"]


class TestTitleParsing:
    """Test title parsing from draft."""

    def test_parse_h1_title(self):
        """Test parsing H1 heading as title."""
        draft = "# My Great Feature\n\nContent here."
        title = parse_title_from_draft(draft)
        assert title == "My Great Feature"

    def test_parse_no_h1(self):
        """Test fallback when no H1."""
        draft = "No heading here.\n\nJust content."
        title = parse_title_from_draft(draft)
        assert title == "Untitled Issue"

    def test_parse_multiple_h1(self):
        """Test uses first H1."""
        draft = "# First Title\n\n# Second Title"
        title = parse_title_from_draft(draft)
        assert title == "First Title"


class TestHumanDecisions:
    """Test human decision enums."""

    def test_send_value(self):
        """Test SEND maps to S."""
        assert HumanDecision.SEND.value == "S"

    def test_approve_value(self):
        """Test APPROVE maps to A."""
        assert HumanDecision.APPROVE.value == "A"

    def test_revise_value(self):
        """Test REVISE maps to R."""
        assert HumanDecision.REVISE.value == "R"

    def test_manual_value(self):
        """Test MANUAL maps to M."""
        assert HumanDecision.MANUAL.value == "M"


class TestSlugCollisionChoice:
    """Test slug collision choice enum."""

    def test_resume_value(self):
        """Test RESUME maps to R."""
        assert SlugCollisionChoice.RESUME.value == "R"

    def test_new_name_value(self):
        """Test NEW_NAME maps to N."""
        assert SlugCollisionChoice.NEW_NAME.value == "N"

    def test_abort_value(self):
        """Test ABORT maps to A."""
        assert SlugCollisionChoice.ABORT.value == "A"


class TestGraphRouting:
    """Test graph conditional routing."""

    def test_route_after_draft_send(self):
        """Test routing to review after Send."""
        from agentos.workflows.issue.graph import route_after_draft_edit

        state: IssueWorkflowState = {"next_node": "N4_review", "error_message": ""}
        result = route_after_draft_edit(state)
        assert result == "N4_review"

    def test_route_after_draft_revise(self):
        """Test routing to draft after Revise."""
        from agentos.workflows.issue.graph import route_after_draft_edit

        state: IssueWorkflowState = {"next_node": "N2_draft", "error_message": ""}
        result = route_after_draft_edit(state)
        assert result == "N2_draft"

    def test_route_after_verdict_approve(self):
        """Test routing to file after Approve."""
        from agentos.workflows.issue.graph import route_after_verdict_edit

        state: IssueWorkflowState = {"next_node": "N6_file", "error_message": ""}
        result = route_after_verdict_edit(state)
        assert result == "N6_file"

    def test_route_after_verdict_revise(self):
        """Test routing to draft after Revise."""
        from agentos.workflows.issue.graph import route_after_verdict_edit

        state: IssueWorkflowState = {"next_node": "N2_draft", "error_message": ""}
        result = route_after_verdict_edit(state)
        assert result == "N2_draft"


class TestClaudeHeadless:
    """Test Claude headless mode (claude -p) integration."""

    @patch("agentos.workflows.issue.nodes.draft.find_claude_cli")
    @patch("subprocess.run")
    def test_call_claude_headless_success(self, mock_run, mock_find):
        """Test successful claude -p call."""
        from agentos.workflows.issue.nodes.draft import call_claude_headless

        mock_find.return_value = "/usr/bin/claude"
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"result": "# Test Issue\\n\\nThis is a test."}',
            stderr="",
        )

        result = call_claude_headless("Test prompt")
        assert result == "# Test Issue\n\nThis is a test."
        mock_run.assert_called_once()

    @patch("agentos.workflows.issue.nodes.draft.find_claude_cli")
    @patch("subprocess.run")
    def test_call_claude_headless_with_system_prompt(self, mock_run, mock_find):
        """Test claude -p with system prompt."""
        from agentos.workflows.issue.nodes.draft import call_claude_headless

        mock_find.return_value = "/usr/bin/claude"
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"result": "Response"}',
            stderr="",
        )

        call_claude_headless("User prompt", "System prompt")

        # Verify --system-prompt was included (not --append-system-prompt)
        call_args = mock_run.call_args[0][0]
        assert "--system-prompt" in call_args
        assert "System prompt" in call_args
        # Verify project context is skipped
        assert "--setting-sources" in call_args
        assert "user" in call_args
        # Verify tools are disabled
        assert "--tools" in call_args

    @patch("agentos.workflows.issue.nodes.draft.find_claude_cli")
    @patch("subprocess.run")
    def test_call_claude_headless_failure(self, mock_run, mock_find):
        """Test claude -p failure handling."""
        from agentos.workflows.issue.nodes.draft import call_claude_headless

        mock_find.return_value = "/usr/bin/claude"
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error: something went wrong",
        )

        with pytest.raises(RuntimeError) as exc_info:
            call_claude_headless("Test prompt")
        assert "claude -p failed" in str(exc_info.value)

    @patch("agentos.workflows.issue.nodes.draft.find_claude_cli")
    @patch("subprocess.run")
    def test_call_claude_headless_timeout(self, mock_run, mock_find):
        """Test claude -p timeout handling."""
        import subprocess
        from agentos.workflows.issue.nodes.draft import call_claude_headless

        mock_find.return_value = "/usr/bin/claude"
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=300)

        with pytest.raises(RuntimeError) as exc_info:
            call_claude_headless("Test prompt")
        assert "timed out" in str(exc_info.value)

    @patch("agentos.workflows.issue.nodes.draft.find_claude_cli")
    def test_call_claude_headless_not_found(self, mock_find):
        """Test claude command not found."""
        from agentos.workflows.issue.nodes.draft import call_claude_headless

        mock_find.side_effect = RuntimeError("claude command not found")

        with pytest.raises(RuntimeError) as exc_info:
            call_claude_headless("Test prompt")
        assert "not found" in str(exc_info.value)


class TestDraftNode:
    """Test N2 draft node."""

    @patch("agentos.workflows.issue.nodes.draft.call_claude_headless")
    @patch("agentos.workflows.issue.nodes.draft.load_issue_template")
    def test_draft_success(self, mock_template, mock_claude, tmp_path):
        """Test successful draft generation."""
        from agentos.workflows.issue.nodes.draft import draft

        # Setup mocks
        mock_template.return_value = "# Template\n\n## Section"
        mock_claude.return_value = "# Generated Issue\n\nContent here."

        # Create audit dir
        audit_dir = tmp_path / "audit"
        audit_dir.mkdir()

        state: IssueWorkflowState = {
            "audit_dir": str(audit_dir),
            "brief_content": "My brief content",
            "file_counter": 0,
            "draft_count": 0,
        }

        result = draft(state)

        assert result["error_message"] == ""
        assert result["current_draft"] == "# Generated Issue\n\nContent here."
        assert result["draft_count"] == 1
        assert (audit_dir / "001-draft.md").exists()

    @patch("agentos.workflows.issue.nodes.draft.call_claude_headless")
    @patch("agentos.workflows.issue.nodes.draft.load_issue_template")
    def test_draft_revision_mode(self, mock_template, mock_claude, tmp_path):
        """Test draft revision with feedback."""
        from agentos.workflows.issue.nodes.draft import draft

        mock_template.return_value = "# Template"
        mock_claude.return_value = "# Revised Issue"

        audit_dir = tmp_path / "audit"
        audit_dir.mkdir()
        (audit_dir / "001-brief.md").touch()

        state: IssueWorkflowState = {
            "audit_dir": str(audit_dir),
            "brief_content": "Original brief",
            "current_draft": "# Original Draft",
            "user_feedback": "Please add more detail",
            "file_counter": 1,
            "draft_count": 1,
        }

        result = draft(state)

        # Verify feedback was included in prompt
        call_args = mock_claude.call_args[0][0]
        assert "Please add more detail" in call_args
        assert "Original Draft" in call_args
        assert result["user_feedback"] == ""  # Cleared after use


class TestGraphCompilation:
    """Test that the graph compiles without errors."""

    def test_build_graph(self):
        """Test graph builds successfully."""
        from agentos.workflows.issue.graph import build_issue_workflow

        workflow = build_issue_workflow()
        assert workflow is not None

    def test_graph_has_all_nodes(self):
        """Test all expected nodes exist."""
        from agentos.workflows.issue.graph import build_issue_workflow

        workflow = build_issue_workflow()
        nodes = workflow.nodes
        expected = [
            "N0_load_brief",
            "N1_sandbox",
            "N2_draft",
            "N3_human_edit_draft",
            "N4_review",
            "N5_human_edit_verdict",
            "N6_file",
        ]
        for node in expected:
            assert node in nodes, f"Missing node: {node}"


class TestWorkflowResume:
    """Test workflow resume functionality (CLI tool)."""

    @patch("tools.run_issue_workflow.get_repo_root")
    @patch("tools.run_issue_workflow.slug_exists")
    @patch("tools.run_issue_workflow.build_issue_workflow")
    @patch("tools.run_issue_workflow.SqliteSaver")
    def test_resume_continues_workflow(self, mock_saver, mock_build, mock_exists, mock_root):
        """Test resume actually continues streaming events."""
        from tools.run_issue_workflow import run_resume_workflow

        # Mock repo setup
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_root.return_value = Path(tmpdir)
            mock_exists.return_value = True

            # Mock the workflow and compiled app
            mock_workflow = MagicMock()
            mock_app = MagicMock()
            mock_workflow.compile.return_value = mock_app
            mock_build.return_value = mock_workflow

            # Mock state showing a paused workflow
            mock_state = MagicMock()
            mock_state.values = {
                "iteration_count": 3,
                "draft_count": 2,
                "verdict_count": 1,
            }
            mock_app.get_state.return_value = mock_state

            # Mock streaming events - simulate workflow continuing
            mock_app.stream.return_value = [
                {"N4_review": {"error_message": ""}},
                {"N5_human_edit_verdict": {"error_message": ""}},
                {"N6_file": {"issue_url": "https://github.com/owner/repo/issues/123"}},
            ]

            # Run resume with brief file
            result = run_resume_workflow("test-brief.md")

            # Verify success
            assert result == 0
            # Verify stream was called to continue workflow
            mock_app.stream.assert_called_once()

    @patch("tools.run_issue_workflow.get_repo_root")
    @patch("tools.run_issue_workflow.slug_exists")
    @patch("tools.run_issue_workflow.build_issue_workflow")
    @patch("tools.run_issue_workflow.SqliteSaver")
    def test_resume_handles_abort(self, mock_saver, mock_build, mock_exists, mock_root):
        """Test resume handles ABORTED error correctly."""
        from tools.run_issue_workflow import run_resume_workflow

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_root.return_value = Path(tmpdir)
            mock_exists.return_value = True

            mock_workflow = MagicMock()
            mock_app = MagicMock()
            mock_workflow.compile.return_value = mock_app
            mock_build.return_value = mock_workflow

            mock_state = MagicMock()
            mock_state.values = {"iteration_count": 2}
            mock_app.get_state.return_value = mock_state

            # Mock event with ABORTED error
            mock_app.stream.return_value = [
                {"N3_human_edit_draft": {"error_message": "ABORTED: User cancelled"}},
            ]

            result = run_resume_workflow("test-brief.md")

            # Verify returns 0 for user abort (not an error)
            assert result == 0

    @patch("tools.run_issue_workflow.get_repo_root")
    @patch("tools.run_issue_workflow.slug_exists")
    @patch("tools.run_issue_workflow.build_issue_workflow")
    @patch("tools.run_issue_workflow.SqliteSaver")
    def test_resume_handles_manual(self, mock_saver, mock_build, mock_exists, mock_root):
        """Test resume handles MANUAL workflow stop correctly."""
        from tools.run_issue_workflow import run_resume_workflow

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_root.return_value = Path(tmpdir)
            mock_exists.return_value = True

            mock_workflow = MagicMock()
            mock_app = MagicMock()
            mock_workflow.compile.return_value = mock_app
            mock_build.return_value = mock_workflow

            mock_state = MagicMock()
            mock_state.values = {"iteration_count": 2}
            mock_app.get_state.return_value = mock_state

            # Mock event with MANUAL error
            mock_app.stream.return_value = [
                {"N5_human_edit_verdict": {"error_message": "MANUAL: Needs manual filing"}},
            ]

            result = run_resume_workflow("test-brief.md")

            # Verify returns 0 for manual stop (not an error)
            assert result == 0

    @patch("tools.run_issue_workflow.get_repo_root")
    @patch("tools.run_issue_workflow.slug_exists")
    @patch("tools.run_issue_workflow.build_issue_workflow")
    @patch("tools.run_issue_workflow.SqliteSaver")
    def test_resume_handles_error(self, mock_saver, mock_build, mock_exists, mock_root):
        """Test resume handles workflow errors correctly."""
        from tools.run_issue_workflow import run_resume_workflow

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_root.return_value = Path(tmpdir)
            mock_exists.return_value = True

            mock_workflow = MagicMock()
            mock_app = MagicMock()
            mock_workflow.compile.return_value = mock_app
            mock_build.return_value = mock_workflow

            mock_state = MagicMock()
            mock_state.values = {"iteration_count": 2}
            mock_app.get_state.return_value = mock_state

            # Mock event with error in final state
            mock_app.stream.return_value = [
                {"N4_review": {"error_message": ""}},
                {"N6_file": {"error_message": "Failed to create issue: API error"}},
            ]

            result = run_resume_workflow("test-brief.md")

            # Verify returns 1 for error
            assert result == 1

    @patch("tools.run_issue_workflow.get_repo_root")
    @patch("tools.run_issue_workflow.slug_exists")
    @patch("tools.run_issue_workflow.build_issue_workflow")
    @patch("tools.run_issue_workflow.SqliteSaver")
    def test_resume_streams_multiple_events(self, mock_saver, mock_build, mock_exists, mock_root):
        """Test resume processes multiple events correctly."""
        from tools.run_issue_workflow import run_resume_workflow

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_root.return_value = Path(tmpdir)
            mock_exists.return_value = True

            mock_workflow = MagicMock()
            mock_app = MagicMock()
            mock_workflow.compile.return_value = mock_app
            mock_build.return_value = mock_workflow

            mock_state = MagicMock()
            mock_state.values = {"iteration_count": 1}
            mock_app.get_state.return_value = mock_state

            # Mock multiple events being streamed
            events_streamed = []

            def mock_stream(state, config):
                events = [
                    {"N4_review": {"error_message": ""}},
                    {"N5_human_edit_verdict": {"error_message": ""}},
                    {"N2_draft": {"error_message": ""}},
                    {"N4_review": {"error_message": ""}},
                    {"N5_human_edit_verdict": {"error_message": ""}},
                    {"N6_file": {"issue_url": "https://github.com/owner/repo/issues/456"}},
                ]
                for event in events:
                    events_streamed.append(event)
                    yield event

            mock_app.stream = mock_stream

            result = run_resume_workflow("test-brief.md")

            # Verify all events were processed
            assert len(events_streamed) == 6
            assert result == 0

    @patch("tools.run_issue_workflow.get_repo_root")
    @patch("tools.run_issue_workflow.slug_exists")
    @patch("tools.run_issue_workflow.build_issue_workflow")
    @patch("tools.run_issue_workflow.SqliteSaver")
    def test_resume_empty_stream_completes(self, mock_saver, mock_build, mock_exists, mock_root):
        """Test resume completes gracefully when no events to process."""
        from tools.run_issue_workflow import run_resume_workflow

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_root.return_value = Path(tmpdir)
            mock_exists.return_value = True

            mock_workflow = MagicMock()
            mock_app = MagicMock()
            mock_workflow.compile.return_value = mock_app
            mock_build.return_value = mock_workflow

            mock_state = MagicMock()
            mock_state.values = {"iteration_count": 5}
            mock_app.get_state.return_value = mock_state

            # Mock empty stream (workflow already complete)
            mock_app.stream.return_value = iter([])

            result = run_resume_workflow("test-brief.md")

            # Verify returns 0 (no error)
            assert result == 0


class TestWorkflowResumeIntegration:
    """Integration tests for resume with real SQLite database.

    These tests use a real SQLite checkpointer (not mocked) to verify
    the actual checkpoint/resume behavior works correctly.
    """

    def test_checkpoint_db_path_env_var(self):
        """Test that AGENTOS_WORKFLOW_DB environment variable works."""
        import os
        from tools.run_issue_workflow import get_checkpoint_db_path

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            custom_db = tmpdir / "custom.db"

            # Set environment variable
            old_env = os.environ.get("AGENTOS_WORKFLOW_DB")
            try:
                os.environ["AGENTOS_WORKFLOW_DB"] = str(custom_db)
                result = get_checkpoint_db_path()
                assert result == custom_db
            finally:
                # Restore original environment
                if old_env:
                    os.environ["AGENTOS_WORKFLOW_DB"] = old_env
                else:
                    os.environ.pop("AGENTOS_WORKFLOW_DB", None)

    def test_checkpoint_db_path_default(self):
        """Test default checkpoint database path."""
        import os
        from tools.run_issue_workflow import get_checkpoint_db_path

        # Ensure env var is not set
        old_env = os.environ.get("AGENTOS_WORKFLOW_DB")
        try:
            os.environ.pop("AGENTOS_WORKFLOW_DB", None)
            result = get_checkpoint_db_path()
            expected = Path.home() / ".agentos" / "issue_workflow.db"
            assert result == expected
        finally:
            if old_env:
                os.environ["AGENTOS_WORKFLOW_DB"] = old_env

    def test_sqlite_checkpointer_saves_state(self):
        """Test that SQLite checkpointer actually saves workflow state.

        This test verifies the core checkpoint mechanism that resume depends on.
        """
        from langgraph.checkpoint.sqlite import SqliteSaver
        from langgraph.graph import END, StateGraph
        from typing import TypedDict

        class SimpleState(TypedDict, total=False):
            counter: int
            msg: str

        def increment(state: SimpleState) -> dict:
            return {"counter": state.get("counter", 0) + 1}

        def set_msg(state: SimpleState) -> dict:
            return {"msg": f"Counter is {state.get('counter', 0)}"}

        # Build a simple workflow
        workflow = StateGraph(SimpleState)
        workflow.add_node("increment", increment)
        workflow.add_node("set_msg", set_msg)
        workflow.set_entry_point("increment")
        workflow.add_edge("increment", "set_msg")
        workflow.add_edge("set_msg", END)

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Run workflow with checkpointer
            with SqliteSaver.from_conn_string(str(db_path)) as memory:
                app = workflow.compile(checkpointer=memory)
                config = {"configurable": {"thread_id": "test-thread"}}

                # Run the workflow
                for event in app.stream({"counter": 0}, config):
                    pass

                # Verify checkpoint was saved
                state = app.get_state(config)
                assert state.values.get("counter") == 1
                assert state.values.get("msg") == "Counter is 1"

            # Reopen database and verify state persisted
            with SqliteSaver.from_conn_string(str(db_path)) as memory:
                app = workflow.compile(checkpointer=memory)
                config = {"configurable": {"thread_id": "test-thread"}}

                # Get saved state
                state = app.get_state(config)
                assert state.values.get("counter") == 1
                assert state.values.get("msg") == "Counter is 1"

    def test_workflow_resume_from_checkpoint(self):
        """Test that workflow can resume from a checkpoint.

        This test creates a checkpoint mid-workflow and verifies
        that resuming with stream(None, config) continues correctly.
        """
        from langgraph.checkpoint.sqlite import SqliteSaver
        from langgraph.graph import END, StateGraph
        from typing import TypedDict

        class CounterState(TypedDict, total=False):
            counter: int
            nodes_visited: list

        def node_a(state: CounterState) -> dict:
            visited = state.get("nodes_visited", [])
            return {
                "counter": state.get("counter", 0) + 1,
                "nodes_visited": visited + ["A"],
            }

        def node_b(state: CounterState) -> dict:
            visited = state.get("nodes_visited", [])
            return {
                "counter": state.get("counter", 0) + 10,
                "nodes_visited": visited + ["B"],
            }

        def node_c(state: CounterState) -> dict:
            visited = state.get("nodes_visited", [])
            return {
                "counter": state.get("counter", 0) + 100,
                "nodes_visited": visited + ["C"],
            }

        # Build workflow: A -> B -> C
        workflow = StateGraph(CounterState)
        workflow.add_node("A", node_a)
        workflow.add_node("B", node_b)
        workflow.add_node("C", node_c)
        workflow.set_entry_point("A")
        workflow.add_edge("A", "B")
        workflow.add_edge("B", "C")
        workflow.add_edge("C", END)

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Run workflow completely
            with SqliteSaver.from_conn_string(str(db_path)) as memory:
                app = workflow.compile(checkpointer=memory)
                config = {"configurable": {"thread_id": "resume-test"}}

                # Run the full workflow
                final_state = None
                for event in app.stream({"counter": 0, "nodes_visited": []}, config):
                    for node_name, output in event.items():
                        final_state = output

                # Verify all nodes ran
                assert final_state["counter"] == 111  # 1 + 10 + 100
                assert final_state["nodes_visited"] == ["A", "B", "C"]

            # Resume with stream(None, config) - should have nothing to do
            with SqliteSaver.from_conn_string(str(db_path)) as memory:
                app = workflow.compile(checkpointer=memory)
                config = {"configurable": {"thread_id": "resume-test"}}

                # Resume - should yield nothing since workflow completed
                events = list(app.stream(None, config))
                assert len(events) == 0  # No more events, workflow complete

                # State should still be accessible
                state = app.get_state(config)
                assert state.values.get("counter") == 111


class TestBriefIdeaDetection:
    """Test that --brief auto-detects ideas/active/ files for cleanup."""

    def test_brief_from_ideas_active_sets_source_idea(self, tmp_path, monkeypatch):
        """When --brief is from ideas/active/, source_idea should be set."""
        # Create ideas/active/ structure
        ideas_active = tmp_path / "ideas" / "active"
        ideas_active.mkdir(parents=True)
        idea_file = ideas_active / "test-idea.md"
        idea_file.write_text("# Test Idea")

        # Test the detection logic used in main()
        brief_path = Path(str(idea_file)).resolve()
        repo_root = tmp_path
        ideas_active_dir = repo_root / "ideas" / "active"

        # The condition checks if parent directory is ideas/active/
        assert brief_path.parent == ideas_active_dir

    def test_brief_from_elsewhere_no_source_idea(self, tmp_path, monkeypatch):
        """When --brief is NOT from ideas/active/, source_idea should not be set."""
        # Create file outside ideas/active/
        other_dir = tmp_path / "other"
        other_dir.mkdir()
        brief_file = other_dir / "notes.md"
        brief_file.write_text("# Notes")

        # Test the detection logic
        brief_path = Path(str(brief_file)).resolve()
        repo_root = tmp_path
        ideas_active_dir = repo_root / "ideas" / "active"

        # The condition should NOT match
        assert brief_path.parent != ideas_active_dir

    def test_brief_from_ideas_done_no_source_idea(self, tmp_path, monkeypatch):
        """When --brief is from ideas/done/, source_idea should not be set."""
        # Create ideas/done/ structure (not active)
        ideas_done = tmp_path / "ideas" / "done"
        ideas_done.mkdir(parents=True)
        done_file = ideas_done / "completed-idea.md"
        done_file.write_text("# Completed Idea")

        # Test the detection logic
        brief_path = Path(str(done_file)).resolve()
        repo_root = tmp_path
        ideas_active_dir = repo_root / "ideas" / "active"

        # The condition should NOT match
        assert brief_path.parent != ideas_active_dir

    @patch("tools.run_issue_workflow.run_new_workflow")
    @patch("tools.run_issue_workflow.get_repo_root")
    def test_main_sets_source_idea_for_ideas_active(
        self, mock_root, mock_run_new, tmp_path, monkeypatch
    ):
        """Test main() actually passes source_idea when --brief is in ideas/active/."""
        import sys

        # Create ideas/active/ structure
        ideas_active = tmp_path / "ideas" / "active"
        ideas_active.mkdir(parents=True)
        idea_file = ideas_active / "test-idea.md"
        idea_file.write_text("# Test Idea")

        mock_root.return_value = tmp_path
        mock_run_new.return_value = 0

        # Simulate --brief argument
        from tools.run_issue_workflow import main

        monkeypatch.setattr(sys, "argv", ["run_issue_workflow.py", "--brief", str(idea_file)])

        main()

        # Verify source_idea was passed
        mock_run_new.assert_called_once_with(str(idea_file), source_idea=str(idea_file.resolve()))

    @patch("tools.run_issue_workflow.run_new_workflow")
    @patch("tools.run_issue_workflow.get_repo_root")
    def test_main_no_source_idea_for_other_paths(
        self, mock_root, mock_run_new, tmp_path, monkeypatch
    ):
        """Test main() does NOT pass source_idea when --brief is elsewhere."""
        import sys

        # Create file outside ideas/active/
        other_dir = tmp_path / "docs"
        other_dir.mkdir()
        brief_file = other_dir / "notes.md"
        brief_file.write_text("# Notes")

        mock_root.return_value = tmp_path
        mock_run_new.return_value = 0

        from tools.run_issue_workflow import main

        monkeypatch.setattr(sys, "argv", ["run_issue_workflow.py", "--brief", str(brief_file)])

        main()

        # Verify source_idea was NOT passed
        mock_run_new.assert_called_once_with(str(brief_file))
