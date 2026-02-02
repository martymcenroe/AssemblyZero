"""Unit tests for Requirements Workflow Nodes.

Issue #101: Unified Requirements Workflow

Tests for:
- load_input (brief or issue loading)
- generate_draft (pluggable drafter)
- human_gate (unified human interaction)
- review (pluggable reviewer)
- finalize (issue filing or LLD saving)
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile


class TestLoadInputNode:
    """Tests for load_input node."""

    def test_loads_brief_for_issue_workflow(self, tmp_path):
        """Test loading brief content for issue workflow."""
        from agentos.workflows.requirements.nodes.load_input import load_input
        from agentos.workflows.requirements.state import create_initial_state

        # Create brief file
        brief_file = tmp_path / "ideas" / "active" / "my-feature.md"
        brief_file.parent.mkdir(parents=True)
        brief_file.write_text("# My Feature\n\nDescription of the feature.")

        state = create_initial_state(
            workflow_type="issue",
            agentos_root=str(tmp_path),
            target_repo=str(tmp_path),
            brief_file=str(brief_file),
        )

        result = load_input(state)

        assert result.get("error_message", "") == ""
        assert "My Feature" in result.get("brief_content", "")
        assert result.get("slug") == "my-feature"

    @patch("subprocess.run")
    def test_loads_issue_for_lld_workflow(self, mock_run, tmp_path):
        """Test loading issue content for LLD workflow."""
        from agentos.workflows.requirements.nodes.load_input import load_input
        from agentos.workflows.requirements.state import create_initial_state

        # Mock gh CLI response
        mock_run.return_value = Mock(
            returncode=0,
            stdout='{"title": "Add authentication", "body": "## Requirements\\n\\n- OAuth support"}',
        )

        state = create_initial_state(
            workflow_type="lld",
            agentos_root=str(tmp_path),
            target_repo=str(tmp_path),
            issue_number=42,
        )

        result = load_input(state)

        assert result.get("error_message", "") == ""
        assert result.get("issue_title") == "Add authentication"
        assert "OAuth" in result.get("issue_body", "")

    def test_creates_audit_dir(self, tmp_path):
        """Test that audit directory is created."""
        from agentos.workflows.requirements.nodes.load_input import load_input
        from agentos.workflows.requirements.state import create_initial_state

        brief_file = tmp_path / "brief.md"
        brief_file.write_text("# Brief")

        state = create_initial_state(
            workflow_type="issue",
            agentos_root=str(tmp_path),
            target_repo=str(tmp_path),
            brief_file=str(brief_file),
        )

        result = load_input(state)

        audit_dir = result.get("audit_dir", "")
        assert audit_dir != ""
        assert Path(audit_dir).exists()

    def test_returns_error_for_missing_brief(self, tmp_path):
        """Test error when brief file doesn't exist."""
        from agentos.workflows.requirements.nodes.load_input import load_input
        from agentos.workflows.requirements.state import create_initial_state

        state = create_initial_state(
            workflow_type="issue",
            agentos_root=str(tmp_path),
            target_repo=str(tmp_path),
            brief_file=str(tmp_path / "nonexistent.md"),
        )

        result = load_input(state)

        assert result.get("error_message", "") != ""


class TestGenerateDraftNode:
    """Tests for generate_draft node."""

    @patch("agentos.workflows.requirements.nodes.generate_draft.get_provider")
    def test_generates_draft_with_drafter(self, mock_get_provider, tmp_path):
        """Test draft generation using configured drafter."""
        from agentos.workflows.requirements.nodes.generate_draft import generate_draft
        from agentos.workflows.requirements.state import create_initial_state

        # Setup mock provider
        mock_provider = Mock()
        mock_provider.invoke.return_value = Mock(
            success=True,
            response="# Generated Draft\n\nContent here.",
            error_message=None,
        )
        mock_get_provider.return_value = mock_provider

        # Create template file
        template_dir = tmp_path / "docs" / "templates"
        template_dir.mkdir(parents=True)
        (template_dir / "0101-issue-template.md").write_text("# Template\n{{CONTENT}}")

        state = create_initial_state(
            workflow_type="issue",
            agentos_root=str(tmp_path),
            target_repo=str(tmp_path),
            brief_file="brief.md",
        )
        state["brief_content"] = "# My Feature"
        state["audit_dir"] = str(tmp_path / "audit")
        Path(state["audit_dir"]).mkdir(parents=True)

        result = generate_draft(state)

        assert result.get("error_message", "") == ""
        assert "Generated Draft" in result.get("current_draft", "")
        mock_provider.invoke.assert_called_once()

    @patch("agentos.workflows.requirements.nodes.generate_draft.get_provider")
    def test_handles_drafter_failure(self, mock_get_provider, tmp_path):
        """Test handling of drafter failure."""
        from agentos.workflows.requirements.nodes.generate_draft import generate_draft
        from agentos.workflows.requirements.state import create_initial_state

        # Setup mock provider to fail
        mock_provider = Mock()
        mock_provider.invoke.return_value = Mock(
            success=False,
            response=None,
            error_message="API rate limit exceeded",
        )
        mock_get_provider.return_value = mock_provider

        # Create template
        template_dir = tmp_path / "docs" / "templates"
        template_dir.mkdir(parents=True)
        (template_dir / "0101-issue-template.md").write_text("# Template")

        state = create_initial_state(
            workflow_type="issue",
            agentos_root=str(tmp_path),
            target_repo=str(tmp_path),
            brief_file="brief.md",
        )
        state["brief_content"] = "# Brief"
        state["audit_dir"] = str(tmp_path / "audit")
        Path(state["audit_dir"]).mkdir(parents=True)

        result = generate_draft(state)

        assert result.get("error_message", "") != ""
        assert "rate limit" in result.get("error_message", "").lower()

    @patch("agentos.workflows.requirements.nodes.generate_draft.get_provider")
    def test_increments_draft_count(self, mock_get_provider, tmp_path):
        """Test that draft_count is incremented."""
        from agentos.workflows.requirements.nodes.generate_draft import generate_draft
        from agentos.workflows.requirements.state import create_initial_state

        mock_provider = Mock()
        mock_provider.invoke.return_value = Mock(
            success=True,
            response="# Draft",
            error_message=None,
        )
        mock_get_provider.return_value = mock_provider

        template_dir = tmp_path / "docs" / "templates"
        template_dir.mkdir(parents=True)
        (template_dir / "0101-issue-template.md").write_text("# Template")

        state = create_initial_state(
            workflow_type="issue",
            agentos_root=str(tmp_path),
            target_repo=str(tmp_path),
            brief_file="brief.md",
        )
        state["brief_content"] = "# Brief"
        state["audit_dir"] = str(tmp_path / "audit")
        state["draft_count"] = 2
        Path(state["audit_dir"]).mkdir(parents=True)

        result = generate_draft(state)

        assert result.get("draft_count") == 3


class TestHumanGateNode:
    """Tests for human_gate node."""

    def test_draft_gate_routes_to_review(self, tmp_path):
        """Test draft gate routes to review when user chooses Send."""
        from agentos.workflows.requirements.nodes.human_gate import human_gate_draft
        from agentos.workflows.requirements.state import create_initial_state

        state = create_initial_state(
            workflow_type="lld",
            agentos_root=str(tmp_path),
            target_repo=str(tmp_path),
            issue_number=42,
            auto_mode=True,  # Skip interactive prompt
        )
        state["current_draft"] = "# LLD Content"

        result = human_gate_draft(state)

        assert result.get("next_node") == "N3_review"

    def test_draft_gate_routes_to_revise(self, tmp_path):
        """Test draft gate routes to revise when critique exists."""
        from agentos.workflows.requirements.nodes.human_gate import human_gate_draft
        from agentos.workflows.requirements.state import create_initial_state

        state = create_initial_state(
            workflow_type="lld",
            agentos_root=str(tmp_path),
            target_repo=str(tmp_path),
            issue_number=42,
            auto_mode=True,
        )
        state["current_draft"] = "# LLD"
        state["current_verdict"] = "BLOCKED: Missing security section"

        result = human_gate_draft(state)

        assert result.get("next_node") == "N1_generate_draft"

    def test_verdict_gate_routes_to_finalize_on_approve(self, tmp_path):
        """Test verdict gate routes to finalize when approved."""
        from agentos.workflows.requirements.nodes.human_gate import human_gate_verdict
        from agentos.workflows.requirements.state import create_initial_state

        state = create_initial_state(
            workflow_type="lld",
            agentos_root=str(tmp_path),
            target_repo=str(tmp_path),
            issue_number=42,
            auto_mode=True,
        )
        state["current_verdict"] = "APPROVED: All requirements met"
        state["lld_status"] = "APPROVED"

        result = human_gate_verdict(state)

        assert result.get("next_node") == "N5_finalize"

    def test_increments_iteration_count(self, tmp_path):
        """Test that iteration_count is incremented."""
        from agentos.workflows.requirements.nodes.human_gate import human_gate_draft
        from agentos.workflows.requirements.state import create_initial_state

        state = create_initial_state(
            workflow_type="lld",
            agentos_root=str(tmp_path),
            target_repo=str(tmp_path),
            issue_number=42,
            auto_mode=True,
        )
        state["current_draft"] = "# Draft"
        state["iteration_count"] = 3

        result = human_gate_draft(state)

        assert result.get("iteration_count") == 4

    def test_skips_gate_when_disabled(self, tmp_path):
        """Test gate is skipped when disabled in config."""
        from agentos.workflows.requirements.nodes.human_gate import human_gate_draft
        from agentos.workflows.requirements.state import create_initial_state

        state = create_initial_state(
            workflow_type="lld",
            agentos_root=str(tmp_path),
            target_repo=str(tmp_path),
            issue_number=42,
            gates_draft=False,  # Disable draft gate
        )
        state["current_draft"] = "# Draft"

        result = human_gate_draft(state)

        # Should skip to review
        assert result.get("next_node") == "N3_review"


class TestReviewNode:
    """Tests for review node."""

    @patch("agentos.workflows.requirements.nodes.review.get_provider")
    def test_reviews_draft_with_reviewer(self, mock_get_provider, tmp_path):
        """Test review using configured reviewer."""
        from agentos.workflows.requirements.nodes.review import review
        from agentos.workflows.requirements.state import create_initial_state

        # Setup mock provider
        mock_provider = Mock()
        mock_provider.invoke.return_value = Mock(
            success=True,
            response="## Verdict: APPROVED\n\nAll requirements met.",
            error_message=None,
        )
        mock_get_provider.return_value = mock_provider

        # Create review prompt
        prompt_dir = tmp_path / "docs" / "skills"
        prompt_dir.mkdir(parents=True)
        (prompt_dir / "0702c-LLD-Review-Prompt.md").write_text("# Review Prompt")

        state = create_initial_state(
            workflow_type="lld",
            agentos_root=str(tmp_path),
            target_repo=str(tmp_path),
            issue_number=42,
        )
        state["current_draft"] = "# LLD Content"
        state["audit_dir"] = str(tmp_path / "audit")
        Path(state["audit_dir"]).mkdir(parents=True)

        result = review(state)

        assert result.get("error_message", "") == ""
        assert "APPROVED" in result.get("current_verdict", "")
        mock_provider.invoke.assert_called_once()

    @patch("agentos.workflows.requirements.nodes.review.get_provider")
    def test_increments_verdict_count(self, mock_get_provider, tmp_path):
        """Test that verdict_count is incremented."""
        from agentos.workflows.requirements.nodes.review import review
        from agentos.workflows.requirements.state import create_initial_state

        mock_provider = Mock()
        mock_provider.invoke.return_value = Mock(
            success=True,
            response="APPROVED",
            error_message=None,
        )
        mock_get_provider.return_value = mock_provider

        prompt_dir = tmp_path / "docs" / "skills"
        prompt_dir.mkdir(parents=True)
        (prompt_dir / "0702c-LLD-Review-Prompt.md").write_text("# Prompt")

        state = create_initial_state(
            workflow_type="lld",
            agentos_root=str(tmp_path),
            target_repo=str(tmp_path),
            issue_number=42,
        )
        state["current_draft"] = "# Draft"
        state["audit_dir"] = str(tmp_path / "audit")
        state["verdict_count"] = 1
        Path(state["audit_dir"]).mkdir(parents=True)

        result = review(state)

        assert result.get("verdict_count") == 2

    @patch("agentos.workflows.requirements.nodes.review.get_provider")
    def test_appends_to_verdict_history(self, mock_get_provider, tmp_path):
        """Test that verdict is appended to history."""
        from agentos.workflows.requirements.nodes.review import review
        from agentos.workflows.requirements.state import create_initial_state

        mock_provider = Mock()
        mock_provider.invoke.return_value = Mock(
            success=True,
            response="BLOCKED: Missing tests",
            error_message=None,
        )
        mock_get_provider.return_value = mock_provider

        prompt_dir = tmp_path / "docs" / "skills"
        prompt_dir.mkdir(parents=True)
        (prompt_dir / "0702c-LLD-Review-Prompt.md").write_text("# Prompt")

        state = create_initial_state(
            workflow_type="lld",
            agentos_root=str(tmp_path),
            target_repo=str(tmp_path),
            issue_number=42,
        )
        state["current_draft"] = "# Draft"
        state["audit_dir"] = str(tmp_path / "audit")
        state["verdict_history"] = ["Previous verdict"]
        Path(state["audit_dir"]).mkdir(parents=True)

        result = review(state)

        assert len(result.get("verdict_history", [])) == 2
        assert "Missing tests" in result.get("verdict_history", [""])[-1]


class TestLoadInputNodeAdditional:
    """Additional tests for load_input node coverage."""

    def test_returns_error_for_missing_brief_file_field(self, tmp_path):
        """Test error when brief_file field is empty."""
        from agentos.workflows.requirements.nodes.load_input import load_input
        from agentos.workflows.requirements.state import create_initial_state

        state = create_initial_state(
            workflow_type="issue",
            agentos_root=str(tmp_path),
            target_repo=str(tmp_path),
            brief_file="",  # Empty
        )

        result = load_input(state)

        assert result.get("error_message", "") != ""
        assert "brief" in result.get("error_message", "").lower()

    def test_mock_mode_for_lld(self, tmp_path):
        """Test mock mode for LLD workflow."""
        from agentos.workflows.requirements.nodes.load_input import load_input
        from agentos.workflows.requirements.state import create_initial_state

        state = create_initial_state(
            workflow_type="lld",
            agentos_root=str(tmp_path),
            target_repo=str(tmp_path),
            issue_number=42,
            mock_mode=True,
        )

        result = load_input(state)

        assert result.get("error_message", "") == ""
        assert "Mock Issue" in result.get("issue_title", "")

    @patch("subprocess.run")
    def test_lld_with_context_files(self, mock_run, tmp_path):
        """Test LLD workflow with context files."""
        from agentos.workflows.requirements.nodes.load_input import load_input
        from agentos.workflows.requirements.state import create_initial_state

        mock_run.return_value = Mock(
            returncode=0,
            stdout='{"title": "Test Issue", "body": "Description"}',
        )

        # Create context file
        ctx_file = tmp_path / "context.md"
        ctx_file.write_text("# Context\n\nSome context here.")

        state = create_initial_state(
            workflow_type="lld",
            agentos_root=str(tmp_path),
            target_repo=str(tmp_path),
            issue_number=42,
            context_files=[str(ctx_file)],
        )

        result = load_input(state)

        assert result.get("error_message", "") == ""
        assert "Context" in result.get("context_content", "")


class TestGenerateDraftNodeAdditional:
    """Additional tests for generate_draft node coverage."""

    @patch("agentos.workflows.requirements.nodes.generate_draft.get_provider")
    def test_generates_lld_draft(self, mock_get_provider, tmp_path):
        """Test draft generation for LLD workflow."""
        from agentos.workflows.requirements.nodes.generate_draft import generate_draft
        from agentos.workflows.requirements.state import create_initial_state

        mock_provider = Mock()
        mock_provider.invoke.return_value = Mock(
            success=True,
            response="# LLD for Feature\n\nDesign here.",
            error_message=None,
        )
        mock_get_provider.return_value = mock_provider

        template_dir = tmp_path / "docs" / "templates"
        template_dir.mkdir(parents=True)
        (template_dir / "0102-feature-lld-template.md").write_text("# LLD Template")

        state = create_initial_state(
            workflow_type="lld",
            agentos_root=str(tmp_path),
            target_repo=str(tmp_path),
            issue_number=42,
        )
        state["issue_title"] = "Add Feature"
        state["issue_body"] = "## Requirements\n\n- Req 1"
        state["audit_dir"] = str(tmp_path / "audit")
        Path(state["audit_dir"]).mkdir(parents=True)

        result = generate_draft(state)

        assert result.get("error_message", "") == ""
        assert "LLD" in result.get("current_draft", "")

    def test_returns_error_for_missing_template(self, tmp_path):
        """Test error when template file is missing."""
        from agentos.workflows.requirements.nodes.generate_draft import generate_draft
        from agentos.workflows.requirements.state import create_initial_state

        state = create_initial_state(
            workflow_type="issue",
            agentos_root=str(tmp_path),
            target_repo=str(tmp_path),
            brief_file="brief.md",
        )
        state["brief_content"] = "# Brief"

        result = generate_draft(state)

        assert result.get("error_message", "") != ""
        assert "template" in result.get("error_message", "").lower()

    @patch("agentos.workflows.requirements.nodes.generate_draft.get_provider")
    def test_revision_mode_with_history(self, mock_get_provider, tmp_path):
        """Test revision mode with verdict history."""
        from agentos.workflows.requirements.nodes.generate_draft import generate_draft
        from agentos.workflows.requirements.state import create_initial_state

        mock_provider = Mock()
        mock_provider.invoke.return_value = Mock(
            success=True,
            response="# Revised Draft\n\nFixed issues.",
            error_message=None,
        )
        mock_get_provider.return_value = mock_provider

        template_dir = tmp_path / "docs" / "templates"
        template_dir.mkdir(parents=True)
        (template_dir / "0101-issue-template.md").write_text("# Template")

        state = create_initial_state(
            workflow_type="issue",
            agentos_root=str(tmp_path),
            target_repo=str(tmp_path),
            brief_file="brief.md",
        )
        state["brief_content"] = "# Brief"
        state["current_draft"] = "# Old Draft"
        state["verdict_history"] = ["BLOCKED: Missing section"]
        state["audit_dir"] = str(tmp_path / "audit")
        Path(state["audit_dir"]).mkdir(parents=True)

        result = generate_draft(state)

        assert result.get("error_message", "") == ""
        # The prompt should include revision context
        call_args = mock_provider.invoke.call_args
        assert "BLOCKED" in str(call_args) or "Revised" in result.get("current_draft", "")


class TestHumanGateNodeAdditional:
    """Additional tests for human_gate node coverage."""

    def test_verdict_gate_routes_to_revise_on_block(self, tmp_path):
        """Test verdict gate routes to revise when blocked."""
        from agentos.workflows.requirements.nodes.human_gate import human_gate_verdict
        from agentos.workflows.requirements.state import create_initial_state

        state = create_initial_state(
            workflow_type="lld",
            agentos_root=str(tmp_path),
            target_repo=str(tmp_path),
            issue_number=42,
            auto_mode=True,
        )
        state["current_verdict"] = "BLOCKED: Missing tests"
        state["lld_status"] = "BLOCKED"

        result = human_gate_verdict(state)

        assert result.get("next_node") == "N1_generate_draft"

    def test_verdict_gate_disabled_routes_based_on_status(self, tmp_path):
        """Test verdict gate when disabled routes based on lld_status."""
        from agentos.workflows.requirements.nodes.human_gate import human_gate_verdict
        from agentos.workflows.requirements.state import create_initial_state

        state = create_initial_state(
            workflow_type="lld",
            agentos_root=str(tmp_path),
            target_repo=str(tmp_path),
            issue_number=42,
            gates_verdict=False,
        )
        state["lld_status"] = "BLOCKED"

        result = human_gate_verdict(state)

        assert result.get("next_node") == "N1_generate_draft"


class TestReviewNodeAdditional:
    """Additional tests for review node coverage."""

    @patch("agentos.workflows.requirements.nodes.review.get_provider")
    def test_reviews_issue_workflow(self, mock_get_provider, tmp_path):
        """Test review for issue workflow."""
        from agentos.workflows.requirements.nodes.review import review
        from agentos.workflows.requirements.state import create_initial_state

        mock_provider = Mock()
        mock_provider.invoke.return_value = Mock(
            success=True,
            response="APPROVED: Issue looks good.",
            error_message=None,
        )
        mock_get_provider.return_value = mock_provider

        prompt_dir = tmp_path / "docs" / "skills"
        prompt_dir.mkdir(parents=True)
        (prompt_dir / "0701c-Issue-Review-Prompt.md").write_text("# Issue Review Prompt")

        state = create_initial_state(
            workflow_type="issue",
            agentos_root=str(tmp_path),
            target_repo=str(tmp_path),
            brief_file="brief.md",
        )
        state["current_draft"] = "# Issue Content"
        state["audit_dir"] = str(tmp_path / "audit")
        Path(state["audit_dir"]).mkdir(parents=True)

        result = review(state)

        assert result.get("error_message", "") == ""
        assert result.get("lld_status") == "APPROVED"

    @patch("agentos.workflows.requirements.nodes.review.get_provider")
    def test_review_handles_blocked_status(self, mock_get_provider, tmp_path):
        """Test review correctly sets BLOCKED status."""
        from agentos.workflows.requirements.nodes.review import review
        from agentos.workflows.requirements.state import create_initial_state

        mock_provider = Mock()
        mock_provider.invoke.return_value = Mock(
            success=True,
            response="BLOCKED: Missing required sections.",
            error_message=None,
        )
        mock_get_provider.return_value = mock_provider

        prompt_dir = tmp_path / "docs" / "skills"
        prompt_dir.mkdir(parents=True)
        (prompt_dir / "0702c-LLD-Review-Prompt.md").write_text("# Prompt")

        state = create_initial_state(
            workflow_type="lld",
            agentos_root=str(tmp_path),
            target_repo=str(tmp_path),
            issue_number=42,
        )
        state["current_draft"] = "# Draft"
        state["audit_dir"] = str(tmp_path / "audit")
        Path(state["audit_dir"]).mkdir(parents=True)

        result = review(state)

        assert result.get("lld_status") == "BLOCKED"

    def test_review_returns_error_for_missing_prompt(self, tmp_path):
        """Test review returns error when prompt file is missing."""
        from agentos.workflows.requirements.nodes.review import review
        from agentos.workflows.requirements.state import create_initial_state

        state = create_initial_state(
            workflow_type="lld",
            agentos_root=str(tmp_path),
            target_repo=str(tmp_path),
            issue_number=42,
        )
        state["current_draft"] = "# Draft"

        result = review(state)

        assert result.get("error_message", "") != ""
        assert "prompt" in result.get("error_message", "").lower()


class TestFinalizeNode:
    """Tests for finalize node."""

    @patch("subprocess.run")
    def test_files_github_issue(self, mock_run, tmp_path):
        """Test filing GitHub issue for issue workflow."""
        from agentos.workflows.requirements.nodes.finalize import finalize
        from agentos.workflows.requirements.state import create_initial_state

        # Mock gh CLI response
        mock_run.return_value = Mock(
            returncode=0,
            stdout="https://github.com/user/repo/issues/123",
        )

        state = create_initial_state(
            workflow_type="issue",
            agentos_root=str(tmp_path),
            target_repo=str(tmp_path),
            brief_file="brief.md",
        )
        state["current_draft"] = "# Issue Title\n\nDescription"
        state["slug"] = "my-feature"
        state["audit_dir"] = str(tmp_path / "audit")
        Path(state["audit_dir"]).mkdir(parents=True)

        result = finalize(state)

        assert result.get("error_message", "") == ""
        assert "github.com" in result.get("issue_url", "")

    def test_saves_lld_to_target_repo(self, tmp_path):
        """Test saving LLD for LLD workflow."""
        from agentos.workflows.requirements.nodes.finalize import finalize
        from agentos.workflows.requirements.state import create_initial_state

        state = create_initial_state(
            workflow_type="lld",
            agentos_root=str(tmp_path / "agentos"),
            target_repo=str(tmp_path / "repo"),
            issue_number=42,
        )
        state["current_draft"] = "# LLD Content"
        state["issue_title"] = "Add Feature"
        state["lld_status"] = "APPROVED"
        state["audit_dir"] = str(tmp_path / "repo" / "audit")
        Path(state["audit_dir"]).mkdir(parents=True)

        result = finalize(state)

        assert result.get("error_message", "") == ""
        final_path = result.get("final_lld_path", "")
        assert final_path != ""
        assert Path(final_path).exists()
        # Verify it's in target_repo, not agentos_root
        assert "repo" in final_path

    def test_updates_lld_status_tracking(self, tmp_path):
        """Test that LLD status tracking is updated."""
        from agentos.workflows.requirements.nodes.finalize import finalize
        from agentos.workflows.requirements.state import create_initial_state
        from agentos.workflows.requirements.audit import load_lld_tracking

        target_repo = tmp_path / "repo"
        target_repo.mkdir()

        state = create_initial_state(
            workflow_type="lld",
            agentos_root=str(tmp_path / "agentos"),
            target_repo=str(target_repo),
            issue_number=99,
        )
        state["current_draft"] = "# LLD"
        state["issue_title"] = "Feature"
        state["lld_status"] = "APPROVED"
        state["verdict_count"] = 2
        state["audit_dir"] = str(target_repo / "audit")
        Path(state["audit_dir"]).mkdir(parents=True)

        finalize(state)

        tracking = load_lld_tracking(target_repo)
        assert "99" in tracking["issues"]
        assert tracking["issues"]["99"]["status"] == "approved"


class TestFinalizeNodeAdditional:
    """Additional tests for finalize node coverage."""

    @patch("subprocess.run")
    def test_handles_gh_cli_failure(self, mock_run, tmp_path):
        """Test handling of gh CLI failure."""
        from agentos.workflows.requirements.nodes.finalize import finalize
        from agentos.workflows.requirements.state import create_initial_state

        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="gh: not found",
        )

        state = create_initial_state(
            workflow_type="issue",
            agentos_root=str(tmp_path),
            target_repo=str(tmp_path),
            brief_file="brief.md",
        )
        state["current_draft"] = "# Title\n\nBody"
        state["audit_dir"] = str(tmp_path / "audit")

        result = finalize(state)

        assert result.get("error_message", "") != ""

    def test_returns_error_for_missing_issue_number(self, tmp_path):
        """Test error when issue_number is missing for LLD."""
        from agentos.workflows.requirements.nodes.finalize import finalize
        from agentos.workflows.requirements.state import create_initial_state

        state = create_initial_state(
            workflow_type="lld",
            agentos_root=str(tmp_path),
            target_repo=str(tmp_path),
            issue_number=0,  # Missing
        )
        state["current_draft"] = "# LLD"
        state["lld_status"] = "APPROVED"

        result = finalize(state)

        assert result.get("error_message", "") != ""

    def test_returns_error_for_empty_title(self, tmp_path):
        """Test error when issue title cannot be parsed."""
        from agentos.workflows.requirements.nodes.finalize import finalize
        from agentos.workflows.requirements.state import create_initial_state

        state = create_initial_state(
            workflow_type="issue",
            agentos_root=str(tmp_path),
            target_repo=str(tmp_path),
            brief_file="brief.md",
        )
        state["current_draft"] = "No title here, just body"  # No # heading
        state["audit_dir"] = str(tmp_path / "audit")

        result = finalize(state)

        assert result.get("error_message", "") != ""
