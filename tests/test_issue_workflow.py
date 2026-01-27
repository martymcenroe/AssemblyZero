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
