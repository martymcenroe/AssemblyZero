"""Tests for N1b validate_test_plan node.

Issue #166: Test IDs match LLD Section 10.0 (T110-T130).
"""

from pathlib import Path

import pytest

from assemblyzero.workflows.requirements.nodes.validate_test_plan import (
    validate_test_plan_node,
    _build_validation_feedback,
)
from assemblyzero.workflows.requirements.graph import (
    route_after_validate_test_plan,
)


# =============================================================================
# Test fixtures
# =============================================================================

LLD_PASSING = """\
# 999 - Feature: Passing

## 3. Requirements

1. The system must validate input data
2. The system must return errors on failure

## 10. Verification & Testing

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | Validate input check (Requirement 1) | Auto | Data | Result | Pass |
| 020 | Error on failure check (Requirement 2) | Auto | Bad data | Error | Pass |
"""

LLD_FAILING = """\
# 999 - Feature: Failing

## 3. Requirements

1. Requirement A
2. Requirement B
3. Requirement C
4. Requirement D
5. Requirement E
6. Requirement F

## 10. Verification & Testing

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | Test for Requirement 1 | Auto | Input | Output | Pass |
| 020 | Test for Requirement 2 | Auto | Input | Output | Pass |
| 030 | Test for Requirement 3 | Auto | Input | Output | Pass |
"""


def _make_state(**overrides) -> dict:
    """Build a minimal workflow state for testing."""
    state = {
        "workflow_type": "lld",
        "assemblyzero_root": "/fake/root",
        "target_repo": "/fake/repo",
        "current_draft": LLD_PASSING,
        "test_plan_validation_attempts": 0,
        "iteration_count": 0,
        "max_iterations": 20,
        "config_gates_draft": True,
        "config_gates_verdict": True,
        "lld_status": "PENDING",
        "error_message": "",
    }
    state.update(overrides)
    return state


# =============================================================================
# T110: Node routes to Gemini on pass
# =============================================================================

class TestNodeRoutesToGeminiOnPass:
    """T110: Node returns valid state on pass."""

    def test_node_routes_to_gemini_on_pass(self):
        """T110: Passing LLD sets validation result with passed=True."""
        state = _make_state(current_draft=LLD_PASSING)
        result = validate_test_plan_node(state)
        assert result["test_plan_validation_result"]["passed"] is True
        assert result["error_message"] == ""
        assert result["test_plan_validation_attempts"] == 1

    def test_routing_passes_to_human_gate(self):
        """T110: Route function sends to N2 on pass with gates enabled (#565)."""
        state = _make_state(
            current_draft=LLD_PASSING,
            test_plan_validation_result={"passed": True},
            config_gates_draft=True,
            error_message="",
        )
        route = route_after_validate_test_plan(state)
        assert route == "N2_human_gate_draft"

    def test_routing_passes_to_review_gates_disabled(self):
        """Routing sends to N3 on pass with gates disabled (#565)."""
        state = _make_state(
            test_plan_validation_result={"passed": True},
            config_gates_draft=False,
            error_message="",
        )
        route = route_after_validate_test_plan(state)
        assert route == "N3_review"


# =============================================================================
# T120: Node routes to draft on fail
# =============================================================================

class TestNodeRoutesToDraftOnFail:
    """T120: Node returns feedback on failure."""

    def test_node_routes_to_draft_on_fail(self):
        """T120: Failing LLD sets validation result and feedback."""
        state = _make_state(current_draft=LLD_FAILING)
        result = validate_test_plan_node(state)
        assert result["test_plan_validation_result"]["passed"] is False
        assert "user_feedback" in result
        assert "coverage" in result["user_feedback"].lower()
        assert result["lld_status"] == "BLOCKED"

    def test_routing_fails_to_draft(self):
        """T120: Route function sends to N1 on fail."""
        state = _make_state(
            test_plan_validation_result={"passed": False},
            error_message="",
            iteration_count=1,
        )
        route = route_after_validate_test_plan(state)
        assert route == "N1_generate_draft"


# =============================================================================
# T130: Node max attempts
# =============================================================================

class TestNodeMaxAttempts:
    """T130: Node escalates after 3 failures."""

    def test_node_max_attempts(self):
        """T130: After 3 attempts, returns error for escalation."""
        state = _make_state(test_plan_validation_attempts=3)
        result = validate_test_plan_node(state)
        assert "error_message" in result
        assert result["error_message"] != ""
        assert "3" in result["error_message"]

    def test_routing_max_attempts_ends(self):
        """T130: Route function sends to END on error from max attempts."""
        state = _make_state(
            error_message="Test plan validation failed after 3 attempts",
        )
        route = route_after_validate_test_plan(state)
        assert route == "HALT"

    def test_routing_max_iterations_ends(self):
        """Max iterations reached routes to HALT."""
        state = _make_state(
            test_plan_validation_result={"passed": False},
            error_message="",
            iteration_count=20,
            max_iterations=20,
        )
        route = route_after_validate_test_plan(state)
        assert route == "HALT"


# =============================================================================
# Additional node tests
# =============================================================================

class TestNodeEdgeCases:
    """Additional edge cases for the node."""

    def test_no_draft_content(self):
        """Empty draft returns error."""
        state = _make_state(current_draft="")
        result = validate_test_plan_node(state)
        assert result["error_message"] != ""

    def test_increments_attempts(self):
        """Each call increments attempts counter."""
        state = _make_state(test_plan_validation_attempts=1)
        result = validate_test_plan_node(state)
        assert result["test_plan_validation_attempts"] == 2

    def test_increments_iteration_count(self):
        """Node increments iteration_count on success or failure."""
        state = _make_state(iteration_count=5, current_draft=LLD_PASSING)
        result = validate_test_plan_node(state)
        assert result["iteration_count"] == 6


class TestCounterResetAfterReview:
    """Issue #567: test_plan_validation_attempts resets after Gemini review."""

    def test_review_resets_counter(self):
        """Review node return dict includes test_plan_validation_attempts: 0."""
        from assemblyzero.workflows.requirements.nodes.review import review

        state = {
            "workflow_type": "lld",
            "assemblyzero_root": str(Path(__file__).parent.parent.parent),
            "target_repo": "/fake/repo",
            "config_mock_mode": True,
            "config_reviewer": "mock:review",
            "config_gates_draft": True,
            "config_gates_verdict": True,
            "audit_dir": "/tmp/fake_audit",
            "current_draft": "# 99 - Feature\n\n## 1. Context\n\nContent.\n",
            "verdict_history": [],
            "verdict_count": 0,
            "iteration_count": 1,
            "max_iterations": 20,
            "test_plan_validation_attempts": 2,
            "cost_budget_usd": 0.0,
            "node_costs": {},
            "node_tokens": {},
        }
        result = review(state)
        assert result["test_plan_validation_attempts"] == 0


class TestBuildValidationFeedback:
    """Test feedback generation."""

    def test_feedback_includes_coverage(self):
        """Feedback mentions coverage percentage."""
        result = {
            "coverage_percentage": 50.0,
            "requirements_count": 6,
            "mapped_count": 3,
            "violations": [
                {
                    "check_type": "coverage",
                    "severity": "error",
                    "requirement_id": "REQ-4",
                    "test_id": None,
                    "message": "Requirement REQ-4 has no test coverage",
                    "line_number": None,
                },
            ],
        }
        feedback = _build_validation_feedback(result)
        assert "50.0%" in feedback
        assert "REQ-4" in feedback
        assert "Errors" in feedback

    def test_feedback_separates_warnings(self):
        """Feedback separates errors and warnings."""
        result = {
            "coverage_percentage": 100.0,
            "requirements_count": 1,
            "mapped_count": 1,
            "violations": [
                {
                    "check_type": "consistency",
                    "severity": "warning",
                    "requirement_id": None,
                    "test_id": "T010",
                    "message": "Type inconsistency",
                    "line_number": None,
                },
            ],
        }
        feedback = _build_validation_feedback(result)
        assert "Warnings" in feedback
        assert "Errors" not in feedback
