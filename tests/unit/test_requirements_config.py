"""Unit tests for Requirements Workflow Configuration.

Issue #101: Unified Requirements Workflow

Tests for:
- GateConfig dataclass and from_string factory
- WorkflowConfig dataclass and validation
- create_issue_config and create_lld_config factories
- WORKFLOW_PRESETS
"""

import pytest
from pathlib import Path

from assemblyzero.workflows.requirements.config import (
    GateConfig,
    WorkflowConfig,
    create_issue_config,
    create_lld_config,
    WORKFLOW_PRESETS,
)


class TestGateConfig:
    """Tests for GateConfig dataclass."""

    def test_default_both_gates_enabled(self):
        """Test default has both gates enabled."""
        config = GateConfig()
        assert config.draft_gate is True
        assert config.verdict_gate is True

    def test_from_string_both(self):
        """Test parsing 'draft,verdict' enables both gates."""
        config = GateConfig.from_string("draft,verdict")
        assert config.draft_gate is True
        assert config.verdict_gate is True

    def test_from_string_draft_only(self):
        """Test parsing 'draft' enables only draft gate."""
        config = GateConfig.from_string("draft")
        assert config.draft_gate is True
        assert config.verdict_gate is False

    def test_from_string_verdict_only(self):
        """Test parsing 'verdict' enables only verdict gate."""
        config = GateConfig.from_string("verdict")
        assert config.draft_gate is False
        assert config.verdict_gate is True

    def test_from_string_none(self):
        """Test parsing 'none' disables both gates."""
        config = GateConfig.from_string("none")
        assert config.draft_gate is False
        assert config.verdict_gate is False

    def test_from_string_case_insensitive(self):
        """Test parsing is case-insensitive."""
        config = GateConfig.from_string("DRAFT,VERDICT")
        assert config.draft_gate is True
        assert config.verdict_gate is True

    def test_from_string_with_whitespace(self):
        """Test parsing handles whitespace."""
        config = GateConfig.from_string("  draft  ")
        assert config.draft_gate is True
        assert config.verdict_gate is False

    def test_from_string_invalid(self):
        """Test parsing invalid string raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            GateConfig.from_string("invalid")
        assert "Invalid gates specification" in str(exc_info.value)

    def test_str_both(self):
        """Test string representation with both gates."""
        config = GateConfig(draft_gate=True, verdict_gate=True)
        assert str(config) == "draft,verdict"

    def test_str_draft_only(self):
        """Test string representation with draft gate only."""
        config = GateConfig(draft_gate=True, verdict_gate=False)
        assert str(config) == "draft"

    def test_str_verdict_only(self):
        """Test string representation with verdict gate only."""
        config = GateConfig(draft_gate=False, verdict_gate=True)
        assert str(config) == "verdict"

    def test_str_none(self):
        """Test string representation with no gates."""
        config = GateConfig(draft_gate=False, verdict_gate=False)
        assert str(config) == "none"


class TestWorkflowConfig:
    """Tests for WorkflowConfig dataclass."""

    def test_issue_config_defaults(self):
        """Test issue workflow has correct default paths."""
        config = WorkflowConfig(workflow_type="issue")
        assert config.workflow_type == "issue"
        assert config.drafter == "claude:opus-4.5"
        assert config.reviewer == "gemini:3-pro-preview"
        assert "0101" in str(config.draft_template_path)
        assert "0701c" in str(config.review_prompt_path)

    def test_lld_config_defaults(self):
        """Test LLD workflow has correct default paths."""
        config = WorkflowConfig(workflow_type="lld")
        assert config.workflow_type == "lld"
        assert "0102" in str(config.draft_template_path)
        assert "0702c" in str(config.review_prompt_path)

    def test_custom_drafter_reviewer(self):
        """Test custom drafter and reviewer."""
        config = WorkflowConfig(
            workflow_type="lld",
            drafter="gemini:flash",
            reviewer="claude:sonnet",
        )
        assert config.drafter == "gemini:flash"
        assert config.reviewer == "claude:sonnet"

    def test_gates_config(self):
        """Test gates configuration."""
        config = WorkflowConfig(
            workflow_type="lld",
            gates=GateConfig(draft_gate=True, verdict_gate=False),
        )
        assert config.gates.draft_gate is True
        assert config.gates.verdict_gate is False

    def test_mode_flags(self):
        """Test mode flags."""
        config = WorkflowConfig(
            workflow_type="lld",
            auto_mode=True,
            mock_mode=True,
            debug_mode=True,
            dry_run=True,
        )
        assert config.auto_mode is True
        assert config.mock_mode is True
        assert config.debug_mode is True
        assert config.dry_run is True

    def test_validate_valid_config(self):
        """Test validation passes for valid config."""
        config = WorkflowConfig(workflow_type="lld")
        errors = config.validate()
        assert len(errors) == 0
        assert config.is_valid()

    def test_validate_invalid_workflow_type(self):
        """Test validation catches invalid workflow_type."""
        # Create config with invalid type by bypassing __post_init__
        config = WorkflowConfig.__new__(WorkflowConfig)
        config.workflow_type = "invalid"
        config.drafter = "claude:opus"
        config.reviewer = "gemini:pro"
        config.max_iterations = 20

        errors = config.validate()
        assert any("workflow_type" in e for e in errors)

    def test_validate_invalid_drafter_spec(self):
        """Test validation catches invalid drafter spec."""
        config = WorkflowConfig(
            workflow_type="lld",
            drafter="invalid-no-colon",
        )
        errors = config.validate()
        assert any("drafter spec" in e for e in errors)

    def test_validate_invalid_reviewer_spec(self):
        """Test validation catches invalid reviewer spec."""
        config = WorkflowConfig(
            workflow_type="lld",
            reviewer="invalid-no-colon",
        )
        errors = config.validate()
        assert any("reviewer spec" in e for e in errors)

    def test_validate_invalid_max_iterations(self):
        """Test validation catches invalid max_iterations."""
        config = WorkflowConfig(
            workflow_type="lld",
            max_iterations=0,
        )
        errors = config.validate()
        assert any("max_iterations" in e for e in errors)


class TestCreateIssueConfig:
    """Tests for create_issue_config factory."""

    def test_default_config(self):
        """Test default issue config."""
        config = create_issue_config()
        assert config.workflow_type == "issue"
        assert config.drafter == "claude:opus-4.5"
        assert config.reviewer == "gemini:3-pro-preview"
        assert config.gates.draft_gate is True
        assert config.gates.verdict_gate is True

    def test_custom_gates(self):
        """Test custom gates string."""
        config = create_issue_config(gates="draft")
        assert config.gates.draft_gate is True
        assert config.gates.verdict_gate is False

    def test_auto_mode(self):
        """Test auto mode flag."""
        config = create_issue_config(auto_mode=True)
        assert config.auto_mode is True

    def test_is_valid(self):
        """Test created config is valid."""
        config = create_issue_config()
        assert config.is_valid()


class TestCreateLLDConfig:
    """Tests for create_lld_config factory."""

    def test_default_config(self):
        """Test default LLD config."""
        config = create_lld_config()
        assert config.workflow_type == "lld"
        assert config.drafter == "claude:opus-4.5"
        assert config.reviewer == "gemini:3-pro-preview"

    def test_custom_drafter_reviewer(self):
        """Test custom drafter and reviewer."""
        config = create_lld_config(
            drafter="gemini:flash",
            reviewer="claude:sonnet",
        )
        assert config.drafter == "gemini:flash"
        assert config.reviewer == "claude:sonnet"

    def test_mock_mode(self):
        """Test mock mode flag."""
        config = create_lld_config(mock_mode=True)
        assert config.mock_mode is True

    def test_is_valid(self):
        """Test created config is valid."""
        config = create_lld_config()
        assert config.is_valid()


class TestWorkflowPresets:
    """Tests for WORKFLOW_PRESETS dictionary."""

    def test_presets_exist(self):
        """Test expected presets exist."""
        assert "issue-standard" in WORKFLOW_PRESETS
        assert "issue-auto" in WORKFLOW_PRESETS
        assert "lld-standard" in WORKFLOW_PRESETS
        assert "lld-draft-only" in WORKFLOW_PRESETS
        assert "lld-auto" in WORKFLOW_PRESETS
        assert "test-mock" in WORKFLOW_PRESETS

    def test_issue_standard_preset(self):
        """Test issue-standard preset."""
        preset = WORKFLOW_PRESETS["issue-standard"]
        assert preset.workflow_type == "issue"
        assert preset.gates.draft_gate is True
        assert preset.gates.verdict_gate is True

    def test_issue_auto_preset(self):
        """Test issue-auto preset has no gates."""
        preset = WORKFLOW_PRESETS["issue-auto"]
        assert preset.workflow_type == "issue"
        assert preset.gates.draft_gate is False
        assert preset.gates.verdict_gate is False
        assert preset.auto_mode is True

    def test_lld_draft_only_preset(self):
        """Test lld-draft-only preset."""
        preset = WORKFLOW_PRESETS["lld-draft-only"]
        assert preset.workflow_type == "lld"
        assert preset.gates.draft_gate is True
        assert preset.gates.verdict_gate is False

    def test_test_mock_preset(self):
        """Test test-mock preset uses mock providers."""
        preset = WORKFLOW_PRESETS["test-mock"]
        assert preset.mock_mode is True
        assert "mock:" in preset.drafter
        assert "mock:" in preset.reviewer

    def test_all_presets_valid(self):
        """Test all presets are valid configurations."""
        for name, preset in WORKFLOW_PRESETS.items():
            assert preset.is_valid(), f"Preset '{name}' is not valid: {preset.validate()}"
