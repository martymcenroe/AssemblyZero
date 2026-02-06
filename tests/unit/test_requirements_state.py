"""Unit tests for Requirements Workflow State.

Issue #101: Unified Requirements Workflow

Tests for:
- RequirementsWorkflowState TypedDict
- HumanDecision enum
- WorkflowType enum
- create_initial_state factory
- validate_state function
"""

import pytest

from assemblyzero.workflows.requirements.state import (
    RequirementsWorkflowState,
    HumanDecision,
    WorkflowType,
    SlugCollisionChoice,
    create_initial_state,
    validate_state,
)


class TestWorkflowType:
    """Tests for WorkflowType enum."""

    def test_issue_value(self):
        """Test ISSUE enum value."""
        assert WorkflowType.ISSUE == "issue"
        assert WorkflowType.ISSUE.value == "issue"

    def test_lld_value(self):
        """Test LLD enum value."""
        assert WorkflowType.LLD == "lld"
        assert WorkflowType.LLD.value == "lld"


class TestHumanDecision:
    """Tests for HumanDecision enum."""

    def test_send_value(self):
        """Test SEND decision."""
        assert HumanDecision.SEND == "S"

    def test_approve_value(self):
        """Test APPROVE decision."""
        assert HumanDecision.APPROVE == "A"

    def test_revise_value(self):
        """Test REVISE decision."""
        assert HumanDecision.REVISE == "R"

    def test_write_feedback_value(self):
        """Test WRITE_FEEDBACK decision."""
        assert HumanDecision.WRITE_FEEDBACK == "W"

    def test_manual_value(self):
        """Test MANUAL decision."""
        assert HumanDecision.MANUAL == "M"


class TestSlugCollisionChoice:
    """Tests for SlugCollisionChoice enum."""

    def test_resume_value(self):
        """Test RESUME choice."""
        assert SlugCollisionChoice.RESUME == "R"

    def test_new_name_value(self):
        """Test NEW_NAME choice."""
        assert SlugCollisionChoice.NEW_NAME == "N"

    def test_clean_value(self):
        """Test CLEAN choice."""
        assert SlugCollisionChoice.CLEAN == "C"

    def test_abort_value(self):
        """Test ABORT choice."""
        assert SlugCollisionChoice.ABORT == "A"


class TestCreateInitialState:
    """Tests for create_initial_state factory."""

    def test_issue_workflow_state(self):
        """Test creating initial state for issue workflow."""
        state = create_initial_state(
            workflow_type="issue",
            assemblyzero_root="/path/to/assemblyzero",
            target_repo="/path/to/repo",
            brief_file="/path/to/brief.md",
        )

        assert state["workflow_type"] == "issue"
        assert state["assemblyzero_root"] == "/path/to/assemblyzero"
        assert state["target_repo"] == "/path/to/repo"
        assert state["brief_file"] == "/path/to/brief.md"
        assert state["brief_content"] == ""
        assert state["slug"] == ""
        assert state["issue_url"] == ""

    def test_lld_workflow_state(self):
        """Test creating initial state for LLD workflow."""
        state = create_initial_state(
            workflow_type="lld",
            assemblyzero_root="/path/to/assemblyzero",
            target_repo="/path/to/repo",
            issue_number=42,
            context_files=["src/main.py", "docs/spec.md"],
        )

        assert state["workflow_type"] == "lld"
        assert state["assemblyzero_root"] == "/path/to/assemblyzero"
        assert state["target_repo"] == "/path/to/repo"
        assert state["issue_number"] == 42
        assert state["context_files"] == ["src/main.py", "docs/spec.md"]
        assert state["lld_status"] == "PENDING"

    def test_default_config_values(self):
        """Test default configuration values."""
        state = create_initial_state(
            workflow_type="lld",
            assemblyzero_root="/assemblyzero",
            target_repo="/repo",
            issue_number=1,
        )

        assert state["config_drafter"] == "claude:opus-4.5"
        assert state["config_reviewer"] == "gemini:3-pro-preview"
        assert state["config_gates_draft"] is True
        assert state["config_gates_verdict"] is True
        assert state["config_auto_mode"] is False
        assert state["config_mock_mode"] is False

    def test_custom_config_values(self):
        """Test custom configuration values."""
        state = create_initial_state(
            workflow_type="lld",
            assemblyzero_root="/assemblyzero",
            target_repo="/repo",
            issue_number=1,
            drafter="gemini:flash",
            reviewer="claude:sonnet",
            gates_draft=False,
            gates_verdict=True,
            auto_mode=True,
            mock_mode=True,
        )

        assert state["config_drafter"] == "gemini:flash"
        assert state["config_reviewer"] == "claude:sonnet"
        assert state["config_gates_draft"] is False
        assert state["config_gates_verdict"] is True
        assert state["config_auto_mode"] is True
        assert state["config_mock_mode"] is True

    def test_workflow_tracking_defaults(self):
        """Test workflow tracking defaults."""
        state = create_initial_state(
            workflow_type="lld",
            assemblyzero_root="/assemblyzero",
            target_repo="/repo",
            issue_number=1,
        )

        assert state["audit_dir"] == ""
        assert state["file_counter"] == 0
        assert state["iteration_count"] == 0
        assert state["draft_count"] == 0
        assert state["verdict_count"] == 0
        assert state["max_iterations"] == 20

    def test_artifact_defaults(self):
        """Test artifact defaults."""
        state = create_initial_state(
            workflow_type="lld",
            assemblyzero_root="/assemblyzero",
            target_repo="/repo",
            issue_number=1,
        )

        assert state["current_draft_path"] == ""
        assert state["current_draft"] == ""
        assert state["current_verdict_path"] == ""
        assert state["current_verdict"] == ""
        assert state["verdict_history"] == []
        assert state["user_feedback"] == ""

    def test_error_on_empty_assemblyzero_root(self):
        """Test that empty assemblyzero_root raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            create_initial_state(
                workflow_type="lld",
                assemblyzero_root="",
                target_repo="/repo",
                issue_number=1,
            )

        assert "assemblyzero_root" in str(exc_info.value)

    def test_error_on_empty_target_repo(self):
        """Test that empty target_repo raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            create_initial_state(
                workflow_type="lld",
                assemblyzero_root="/assemblyzero",
                target_repo="",
                issue_number=1,
            )

        assert "target_repo" in str(exc_info.value)

    def test_error_on_whitespace_paths(self):
        """Test that whitespace-only paths raise ValueError."""
        with pytest.raises(ValueError):
            create_initial_state(
                workflow_type="lld",
                assemblyzero_root="   ",
                target_repo="/repo",
                issue_number=1,
            )

    def test_context_files_default_to_empty_list(self):
        """Test that context_files defaults to empty list."""
        state = create_initial_state(
            workflow_type="lld",
            assemblyzero_root="/assemblyzero",
            target_repo="/repo",
            issue_number=1,
        )

        assert state["context_files"] == []


class TestValidateState:
    """Tests for validate_state function."""

    def test_valid_lld_state(self):
        """Test validation passes for valid LLD state."""
        state = create_initial_state(
            workflow_type="lld",
            assemblyzero_root="/assemblyzero",
            target_repo="/repo",
            issue_number=42,
        )

        errors = validate_state(state)
        assert len(errors) == 0

    def test_valid_issue_state(self):
        """Test validation passes for valid issue state."""
        state = create_initial_state(
            workflow_type="issue",
            assemblyzero_root="/assemblyzero",
            target_repo="/repo",
            brief_file="/path/to/brief.md",
        )

        errors = validate_state(state)
        assert len(errors) == 0

    def test_missing_assemblyzero_root(self):
        """Test validation catches missing assemblyzero_root."""
        state: RequirementsWorkflowState = {
            "workflow_type": "lld",
            "assemblyzero_root": "",
            "target_repo": "/repo",
            "issue_number": 42,
        }

        errors = validate_state(state)
        assert any("assemblyzero_root" in e for e in errors)

    def test_missing_target_repo(self):
        """Test validation catches missing target_repo."""
        state: RequirementsWorkflowState = {
            "workflow_type": "lld",
            "assemblyzero_root": "/assemblyzero",
            "target_repo": "",
            "issue_number": 42,
        }

        errors = validate_state(state)
        assert any("target_repo" in e for e in errors)

    def test_invalid_workflow_type(self):
        """Test validation catches invalid workflow_type."""
        state: RequirementsWorkflowState = {
            "workflow_type": "invalid",  # type: ignore
            "assemblyzero_root": "/assemblyzero",
            "target_repo": "/repo",
        }

        errors = validate_state(state)
        assert any("workflow_type" in e for e in errors)

    def test_issue_missing_brief_file(self):
        """Test validation catches missing brief_file for issue workflow."""
        state: RequirementsWorkflowState = {
            "workflow_type": "issue",
            "assemblyzero_root": "/assemblyzero",
            "target_repo": "/repo",
            "brief_file": "",
        }

        errors = validate_state(state)
        assert any("brief_file" in e for e in errors)

    def test_lld_missing_issue_number(self):
        """Test validation catches missing issue_number for LLD workflow."""
        state: RequirementsWorkflowState = {
            "workflow_type": "lld",
            "assemblyzero_root": "/assemblyzero",
            "target_repo": "/repo",
            "issue_number": 0,
        }

        errors = validate_state(state)
        assert any("issue_number" in e for e in errors)


class TestRequirementsWorkflowStateTypedDict:
    """Tests to verify TypedDict behavior."""

    def test_state_is_dict(self):
        """Test that state is a regular dict."""
        state = create_initial_state(
            workflow_type="lld",
            assemblyzero_root="/assemblyzero",
            target_repo="/repo",
            issue_number=1,
        )

        assert isinstance(state, dict)

    def test_can_access_fields(self):
        """Test that fields can be accessed by key."""
        state = create_initial_state(
            workflow_type="lld",
            assemblyzero_root="/assemblyzero",
            target_repo="/repo",
            issue_number=42,
        )

        assert state["issue_number"] == 42
        assert state.get("workflow_type") == "lld"

    def test_can_update_fields(self):
        """Test that fields can be updated."""
        state = create_initial_state(
            workflow_type="lld",
            assemblyzero_root="/assemblyzero",
            target_repo="/repo",
            issue_number=1,
        )

        state["iteration_count"] = 5
        state["current_draft"] = "# LLD Content"

        assert state["iteration_count"] == 5
        assert state["current_draft"] == "# LLD Content"
