"""Unit tests for orchestrator state management.

Issue #305: End-to-End Orchestration Workflow (Issue → Code)
"""

import pytest

from assemblyzero.workflows.orchestrator.config import get_default_config
from assemblyzero.workflows.orchestrator.state import (
    STAGE_ORDER,
    OrchestrationState,
    StageResult,
    create_initial_state,
    get_next_stage,
    update_stage_result,
)


class TestCreateInitialState:
    """Tests for create_initial_state (T100)."""

    def test_fresh_state_has_correct_defaults(self):
        """T100: Fresh state has correct defaults."""
        config = get_default_config()
        state = create_initial_state(305, config)

        assert state["issue_number"] == 305
        assert state["current_stage"] == "triage"
        assert state["issue_brief_path"] == ""
        assert state["lld_path"] == ""
        assert state["spec_path"] == ""
        assert state["worktree_path"] == ""
        assert state["pr_url"] == ""
        assert state["stage_results"] == {}
        assert state["started_at"] != ""
        assert state["completed_at"] == ""
        assert state["error_message"] == ""

    def test_stage_attempts_initialized_to_zero(self):
        config = get_default_config()
        state = create_initial_state(305, config)
        for stage in STAGE_ORDER:
            assert state["stage_attempts"][stage] == 0

    def test_negative_issue_number_raises(self):
        config = get_default_config()
        with pytest.raises(ValueError, match="issue_number must be positive"):
            create_initial_state(-1, config)

    def test_zero_issue_number_raises(self):
        config = get_default_config()
        with pytest.raises(ValueError, match="issue_number must be positive"):
            create_initial_state(0, config)


class TestGetNextStage:
    """Tests for get_next_stage."""

    def test_triage_to_lld(self):
        assert get_next_stage("triage") == "lld"

    def test_lld_to_spec(self):
        assert get_next_stage("lld") == "spec"

    def test_spec_to_impl(self):
        assert get_next_stage("spec") == "impl"

    def test_impl_to_pr(self):
        assert get_next_stage("impl") == "pr"

    def test_pr_to_done(self):
        assert get_next_stage("pr") == "done"

    def test_done_stays_done(self):
        assert get_next_stage("done") == "done"

    def test_invalid_stage_raises(self):
        with pytest.raises(ValueError, match="Unknown stage: invalid"):
            get_next_stage("invalid")


class TestUpdateStageResult:
    """Tests for update_stage_result (T110)."""

    def test_passed_advances_stage(self):
        """T110: State updates correctly on stage complete."""
        config = get_default_config()
        state = create_initial_state(305, config)
        result = StageResult(
            status="passed",
            artifact_path="docs/lineage/305/issue-brief.md",
            error_message="",
            duration_seconds=85.3,
            attempts=1,
        )
        new_state = update_stage_result(state, "triage", result)
        assert new_state["current_stage"] == "lld"
        assert new_state["issue_brief_path"] == "docs/lineage/305/issue-brief.md"
        assert "triage" in new_state["stage_results"]

    def test_skipped_advances_stage(self):
        config = get_default_config()
        state = create_initial_state(305, config)
        result = StageResult(
            status="skipped",
            artifact_path="docs/lineage/305/issue-brief.md",
            error_message="",
            duration_seconds=0.01,
            attempts=0,
        )
        new_state = update_stage_result(state, "triage", result)
        assert new_state["current_stage"] == "lld"

    def test_failed_does_not_advance(self):
        config = get_default_config()
        state = create_initial_state(305, config)
        result = StageResult(
            status="failed",
            artifact_path="",
            error_message="Triage failed: API error",
            duration_seconds=10.0,
            attempts=1,
        )
        new_state = update_stage_result(state, "triage", result)
        assert new_state["current_stage"] == "triage"
        assert new_state["error_message"] == "Triage failed: API error"

    def test_blocked_does_not_advance(self):
        config = get_default_config()
        state = create_initial_state(305, config)
        result = StageResult(
            status="blocked",
            artifact_path="",
            error_message="LLD blocked by reviewer",
            duration_seconds=300.0,
            attempts=1,
        )
        # Advance to lld first
        state_at_lld = dict(state)
        state_at_lld["current_stage"] = "lld"
        new_state = update_stage_result(OrchestrationState(**state_at_lld), "lld", result)
        assert new_state["current_stage"] == "lld"

    def test_pr_passed_sets_done_and_completed(self):
        config = get_default_config()
        state = create_initial_state(305, config)
        state_at_pr = dict(state)
        state_at_pr["current_stage"] = "pr"
        result = StageResult(
            status="passed",
            artifact_path="https://github.com/martymcenroe/AssemblyZero/pull/312",
            error_message="",
            duration_seconds=12.1,
            attempts=1,
        )
        new_state = update_stage_result(OrchestrationState(**state_at_pr), "pr", result)
        assert new_state["current_stage"] == "done"
        assert new_state["completed_at"] != ""
        assert new_state["pr_url"] == "https://github.com/martymcenroe/AssemblyZero/pull/312"

    def test_does_not_mutate_original_state(self):
        config = get_default_config()
        state = create_initial_state(305, config)
        result = StageResult(status="passed", artifact_path="test.md", error_message="", duration_seconds=1.0, attempts=1)
        new_state = update_stage_result(state, "triage", result)
        assert state["current_stage"] == "triage"
        assert new_state["current_stage"] == "lld"
