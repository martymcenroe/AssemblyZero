"""Unit tests for assemblyzero/core/recovery_plan.py.

Issue #486: Halt-and-Plan pattern — self-babysitting workflows.

Tests cover:
- RecoveryPlan dataclass serialization/deserialization
- generate_recovery_plan() factory function
- save() persistence to disk
- print_summary() human-readable output
"""

import json
from pathlib import Path

import pytest

from assemblyzero.core.recovery_plan import (
    RecoveryPlan,
    generate_recovery_plan,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def sample_plan() -> RecoveryPlan:
    """A representative recovery plan for testing."""
    return generate_recovery_plan(
        issue_number=102,
        workflow="implementation_spec",
        stage="N5_review",
        error_type="capacity_exhausted",
        error_message="api-key-1: Capacity exhausted after 3 retries (503/529)",
        state={"spec_draft": "...", "review_iteration": 1},
        cost_spent_usd=3.60,
        cost_budget_usd=10.0,
    )


@pytest.fixture
def stagnation_plan() -> RecoveryPlan:
    """A recovery plan for stagnation errors (non-transient)."""
    return generate_recovery_plan(
        issue_number=99,
        workflow="requirements",
        stage="N3_review",
        error_type="stagnation",
        error_message="Two consecutive BLOCKED verdicts with same issues.",
        state={"iteration_count": 4},
        cost_spent_usd=2.40,
        cost_budget_usd=5.0,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: RecoveryPlan dataclass
# ═══════════════════════════════════════════════════════════════════════════════


class TestRecoveryPlanDataclass:
    """Tests for RecoveryPlan structure and fields."""

    def test_all_fields_populated(self, sample_plan: RecoveryPlan) -> None:
        """Factory produces a plan with all required fields non-empty."""
        assert sample_plan.issue_number == 102
        assert sample_plan.workflow == "implementation_spec"
        assert sample_plan.stage == "N5_review"
        assert sample_plan.error_type == "capacity_exhausted"
        assert len(sample_plan.error_message) > 0
        assert sample_plan.halted_at  # ISO timestamp
        # state_path is set by halt_node, empty from factory alone
        assert isinstance(sample_plan.state_path, str)

    def test_transient_classification(self, sample_plan: RecoveryPlan) -> None:
        """Capacity exhausted errors are classified as transient."""
        assert sample_plan.is_transient is True

    def test_stagnation_is_not_transient(self, stagnation_plan: RecoveryPlan) -> None:
        """Stagnation errors are classified as non-transient."""
        assert stagnation_plan.is_transient is False

    def test_resume_command_populated(self, sample_plan: RecoveryPlan) -> None:
        """Resume command includes workflow tool and issue number."""
        assert "102" in sample_plan.resume_command
        assert "implementation_spec" in sample_plan.resume_command or "impl" in sample_plan.resume_command

    def test_cost_fields(self, sample_plan: RecoveryPlan) -> None:
        """Cost fields are carried through correctly."""
        assert sample_plan.cost_spent_usd == pytest.approx(3.60)
        assert sample_plan.cost_budget_usd == pytest.approx(10.0)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Serialization round-trip
# ═══════════════════════════════════════════════════════════════════════════════


class TestSerialization:
    """Tests for save/load round-trip."""

    def test_serialize_roundtrip(self, sample_plan: RecoveryPlan, tmp_path: Path) -> None:
        """Saving and loading a plan preserves all fields."""
        plan_path = sample_plan.save(tmp_path)
        assert plan_path.exists()

        with open(plan_path, encoding="utf-8") as f:
            data = json.load(f)

        assert data["issue_number"] == 102
        assert data["workflow"] == "implementation_spec"
        assert data["error_type"] == "capacity_exhausted"
        assert data["is_transient"] is True
        assert data["cost_spent_usd"] == pytest.approx(3.60)

    def test_save_to_disk(self, sample_plan: RecoveryPlan, tmp_path: Path) -> None:
        """save() creates a JSON file in the specified directory."""
        plan_path = sample_plan.save(tmp_path)
        assert plan_path.suffix == ".json"
        assert plan_path.parent == tmp_path
        content = plan_path.read_text(encoding="utf-8")
        assert len(content) > 0
        # Must be valid JSON
        data = json.loads(content)
        assert isinstance(data, dict)

    def test_save_creates_directory(self, tmp_path: Path) -> None:
        """save() creates the target directory if it doesn't exist."""
        nested = tmp_path / "deeply" / "nested" / "dir"
        plan = generate_recovery_plan(
            issue_number=1,
            workflow="testing",
            stage="N4_green",
            error_type="budget",
            error_message="Budget exceeded",
            state={},
        )
        plan_path = plan.save(nested)
        assert plan_path.exists()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: generate_recovery_plan factory
# ═══════════════════════════════════════════════════════════════════════════════


class TestGenerateRecoveryPlan:
    """Tests for the generate_recovery_plan() factory function."""

    def test_generate_plan_transient(self) -> None:
        """Transient error types produce is_transient=True."""
        for error_type in ("capacity_exhausted", "quota_exhausted"):
            plan = generate_recovery_plan(
                issue_number=1,
                workflow="requirements",
                stage="N3_review",
                error_type=error_type,
                error_message="Temporary failure",
                state={},
            )
            assert plan.is_transient is True, f"{error_type} should be transient"

    def test_generate_plan_non_transient(self) -> None:
        """Non-transient error types produce is_transient=False."""
        for error_type in ("stagnation", "auth", "budget"):
            plan = generate_recovery_plan(
                issue_number=1,
                workflow="requirements",
                stage="N3_review",
                error_type=error_type,
                error_message="Permanent failure",
                state={},
            )
            assert plan.is_transient is False, f"{error_type} should not be transient"

    def test_recommendation_populated(self) -> None:
        """Generated plans include a non-empty recommendation."""
        plan = generate_recovery_plan(
            issue_number=50,
            workflow="testing",
            stage="N4_green",
            error_type="stagnation",
            error_message="Zero progress across 2 iterations",
            state={"iteration_count": 5},
        )
        assert len(plan.recommendation) > 0

    def test_earliest_retry_for_transient(self) -> None:
        """Transient errors get an earliest_retry timestamp."""
        plan = generate_recovery_plan(
            issue_number=10,
            workflow="implementation_spec",
            stage="N5_review",
            error_type="capacity_exhausted",
            error_message="503 capacity",
            state={},
        )
        assert len(plan.earliest_retry) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: print_summary
# ═══════════════════════════════════════════════════════════════════════════════


class TestPrintSummary:
    """Tests for print_summary() console output."""

    def test_print_summary_contains_key_info(
        self, sample_plan: RecoveryPlan, capsys: pytest.CaptureFixture
    ) -> None:
        """print_summary outputs issue number, workflow, error type, and recommendation."""
        sample_plan.print_summary()
        captured = capsys.readouterr()
        assert "102" in captured.out
        assert "implementation_spec" in captured.out
        assert "capacity_exhausted" in captured.out

    def test_print_summary_no_exceptions(self, stagnation_plan: RecoveryPlan) -> None:
        """print_summary does not raise for any plan type."""
        stagnation_plan.print_summary()  # Should not raise
