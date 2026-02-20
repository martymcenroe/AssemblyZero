"""Unit tests for orchestrator stage execution.

Issue #305: End-to-End Orchestration Workflow (Issue → Code)
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from assemblyzero.workflows.orchestrator.config import get_default_config
from assemblyzero.workflows.orchestrator.stages import (
    STAGE_RUNNERS,
    check_human_gate,
    run_triage_stage,
    should_skip_stage,
)
from assemblyzero.workflows.orchestrator.state import (
    OrchestrationState,
    StageResult,
    create_initial_state,
)


class TestShouldSkipStage:
    """Tests for should_skip_stage (T020)."""

    def test_skip_lld_with_existing_artifact(self):
        """T020: Pipeline skips stages with existing artifacts."""
        config = get_default_config()
        state = create_initial_state(305, config)
        existing = {"lld": "docs/lld/active/305-test.md"}

        with patch("assemblyzero.workflows.orchestrator.stages.validate_artifact", return_value=True):
            skip, path = should_skip_stage(state, "lld", existing)
        assert skip is True
        assert path == "docs/lld/active/305-test.md"

    def test_no_skip_when_config_disabled(self):
        config = get_default_config()
        config["skip_existing_lld"] = False
        state = create_initial_state(305, config)
        existing = {"lld": "docs/lld/active/305-test.md"}

        skip, path = should_skip_stage(state, "lld", existing)
        assert skip is False
        assert path is None

    def test_no_skip_impl_stage(self):
        config = get_default_config()
        state = create_initial_state(305, config)
        existing = {"impl": "../AssemblyZero-305"}

        skip, path = should_skip_stage(state, "impl", existing)
        assert skip is False

    def test_no_skip_pr_stage(self):
        config = get_default_config()
        state = create_initial_state(305, config)
        existing = {"pr": "https://github.com/test/pr/1"}

        skip, path = should_skip_stage(state, "pr", existing)
        assert skip is False

    def test_no_skip_when_no_artifact(self):
        config = get_default_config()
        state = create_initial_state(305, config)
        existing = {"triage": None}

        skip, path = should_skip_stage(state, "triage", existing)
        assert skip is False


class TestCheckHumanGate:
    """Tests for check_human_gate (T040)."""

    def test_gate_enabled_returns_false(self):
        """T040: Human gates configurable per stage."""
        config = get_default_config()
        config["gates"]["pr"] = True
        state = create_initial_state(305, config)

        result = check_human_gate(state, "pr")
        assert result is False

    def test_gate_disabled_returns_true(self):
        config = get_default_config()
        config["gates"]["lld"] = False
        state = create_initial_state(305, config)

        result = check_human_gate(state, "lld")
        assert result is True

    def test_gate_not_configured_defaults_to_no_gate(self):
        config = get_default_config()
        config["gates"] = {}
        state = create_initial_state(305, config)

        result = check_human_gate(state, "triage")
        assert result is True


class TestRunTriageStage:
    """Tests for run_triage_stage."""

    @patch("assemblyzero.workflows.orchestrator.stages.detect_existing_artifacts")
    @patch("assemblyzero.workflows.orchestrator.stages.validate_artifact")
    def test_skips_when_artifact_exists(self, mock_validate, mock_detect):
        mock_detect.return_value = {"triage": "docs/lineage/305/issue-brief.md", "lld": None, "spec": None, "impl": None, "pr": None}
        mock_validate.return_value = True

        config = get_default_config()
        state = create_initial_state(305, config)
        new_state = run_triage_stage(state)

        assert new_state["stage_results"]["triage"]["status"] == "skipped"
        assert new_state["current_stage"] == "lld"


class TestStageRunners:
    """Tests for STAGE_RUNNERS mapping."""

    def test_all_stages_have_runners(self):
        from assemblyzero.workflows.orchestrator.state import STAGE_ORDER
        for stage in STAGE_ORDER:
            assert stage in STAGE_RUNNERS, f"Missing runner for stage: {stage}"
