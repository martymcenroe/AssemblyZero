"""Unit tests for assemblyzero/core/halt_node.py.

Issue #486: Halt-and-Plan pattern — self-babysitting workflows.

Tests cover:
- create_halt_node: factory function returns a valid LangGraph node
- halt_with_plan: saves state, generates plan, prints summary
- Error classification for different error types
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.core.halt_node import create_halt_node


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def halt_fn():
    """A halt node function for implementation_spec workflow."""
    return create_halt_node("implementation_spec")


@pytest.fixture
def error_state() -> dict:
    """A state dict with an error (capacity exhausted)."""
    return {
        "issue_number": 102,
        "error_message": "api-key-1: Capacity exhausted after 3 retries (503/529)",
        "review_iteration": 1,
        "spec_draft": "# Spec Draft\n...",
        "cost_budget_usd": 10.0,
    }


@pytest.fixture
def stagnation_state() -> dict:
    """A state dict with stagnation error."""
    return {
        "issue_number": 99,
        "error_message": "Two consecutive BLOCKED verdicts with same issues. Halting.",
        "iteration_count": 4,
        "cost_budget_usd": 5.0,
    }


@pytest.fixture
def quota_state() -> dict:
    """A state dict with quota exhausted error."""
    return {
        "issue_number": 50,
        "error_message": "All credentials exhausted: api-key-1: Quota exhausted. Wait for quota reset.",
        "cost_budget_usd": 8.0,
    }


@pytest.fixture
def budget_state() -> dict:
    """A state dict with budget exceeded error."""
    return {
        "issue_number": 75,
        "error_message": "Cost budget exceeded: $5.20 spent of $5.00 budget",
        "cost_budget_usd": 5.0,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: create_halt_node
# ═══════════════════════════════════════════════════════════════════════════════


class TestCreateHaltNode:
    """Tests for the create_halt_node() factory function."""

    def test_returns_callable(self) -> None:
        """Factory returns a callable function."""
        fn = create_halt_node("testing")
        assert callable(fn)

    def test_different_workflows(self) -> None:
        """Factory works for all supported workflow names."""
        for name in ("requirements", "implementation_spec", "testing", "orchestrator"):
            fn = create_halt_node(name)
            assert callable(fn)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: halt_with_plan execution
# ═══════════════════════════════════════════════════════════════════════════════


class TestHaltWithPlan:
    """Tests for the halt node function execution."""

    def test_halt_saves_state(self, halt_fn, error_state: dict, tmp_path: Path) -> None:
        """Halt node saves state snapshot to disk."""
        with patch("assemblyzero.core.halt_node.STATE_DIR", tmp_path / "state"):
            result = halt_fn(error_state)

        assert "state_snapshot_path" in result
        snapshot_path = Path(result["state_snapshot_path"])
        assert snapshot_path.exists()

    def test_halt_generates_plan(self, halt_fn, error_state: dict, tmp_path: Path) -> None:
        """Halt node generates a recovery plan JSON file."""
        with patch("assemblyzero.core.halt_node.STATE_DIR", tmp_path / "state"):
            result = halt_fn(error_state)

        assert "recovery_plan_path" in result
        plan_path = Path(result["recovery_plan_path"])
        assert plan_path.exists()

        with open(plan_path, encoding="utf-8") as f:
            plan_data = json.load(f)
        assert plan_data["issue_number"] == 102
        assert plan_data["workflow"] == "implementation_spec"

    def test_halt_prints_summary(
        self, halt_fn, error_state: dict, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Halt node prints a human-readable summary."""
        with patch("assemblyzero.core.halt_node.STATE_DIR", tmp_path / "state"):
            halt_fn(error_state)

        captured = capsys.readouterr()
        assert "HALT" in captured.out or "halt" in captured.out.lower()
        assert "102" in captured.out

    def test_halt_returns_state_update(self, halt_fn, error_state: dict, tmp_path: Path) -> None:
        """Halt node returns dict suitable for LangGraph state update."""
        with patch("assemblyzero.core.halt_node.STATE_DIR", tmp_path / "state"):
            result = halt_fn(error_state)

        assert isinstance(result, dict)
        assert "recovery_plan_path" in result
        assert "state_snapshot_path" in result


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Error classification
# ═══════════════════════════════════════════════════════════════════════════════


class TestErrorClassification:
    """Tests for error type classification from error_message."""

    def test_classify_capacity(self, halt_fn, error_state: dict, tmp_path: Path) -> None:
        """Capacity exhausted error is classified correctly."""
        with patch("assemblyzero.core.halt_node.STATE_DIR", tmp_path / "state"):
            result = halt_fn(error_state)

        plan_path = Path(result["recovery_plan_path"])
        with open(plan_path, encoding="utf-8") as f:
            plan = json.load(f)
        assert plan["error_type"] == "capacity_exhausted"
        assert plan["is_transient"] is True

    def test_classify_quota(self, halt_fn, quota_state: dict, tmp_path: Path) -> None:
        """Quota exhausted error is classified correctly."""
        with patch("assemblyzero.core.halt_node.STATE_DIR", tmp_path / "state"):
            result = halt_fn(quota_state)

        plan_path = Path(result["recovery_plan_path"])
        with open(plan_path, encoding="utf-8") as f:
            plan = json.load(f)
        assert plan["error_type"] == "quota_exhausted"
        assert plan["is_transient"] is True

    def test_classify_stagnation(self, halt_fn, stagnation_state: dict, tmp_path: Path) -> None:
        """Stagnation error is classified correctly."""
        with patch("assemblyzero.core.halt_node.STATE_DIR", tmp_path / "state"):
            result = halt_fn(stagnation_state)

        plan_path = Path(result["recovery_plan_path"])
        with open(plan_path, encoding="utf-8") as f:
            plan = json.load(f)
        assert plan["error_type"] == "stagnation"
        assert plan["is_transient"] is False

    def test_classify_budget(self, halt_fn, budget_state: dict, tmp_path: Path) -> None:
        """Budget exceeded error is classified correctly."""
        with patch("assemblyzero.core.halt_node.STATE_DIR", tmp_path / "state"):
            result = halt_fn(budget_state)

        plan_path = Path(result["recovery_plan_path"])
        with open(plan_path, encoding="utf-8") as f:
            plan = json.load(f)
        assert plan["error_type"] == "budget"
        assert plan["is_transient"] is False
