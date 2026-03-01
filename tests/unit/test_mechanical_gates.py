"""Tests for Issue #496: Mechanical gates before Gemini calls.

Validates that _run_mechanical_gates catches structural issues
before expensive Gemini API calls in review_test_plan.
"""

import pytest

from assemblyzero.workflows.testing.nodes.review_test_plan import (
    _run_mechanical_gates,
)


def _make_state(**overrides) -> dict:
    """Create a minimal valid state for testing."""
    base = {
        "test_scenarios": [
            {"name": "test_create_user", "type": "unit"},
            {"name": "test_delete_user", "type": "unit"},
        ],
        "requirements": ["R1: User creation", "R2: User deletion"],
        "lld_content": "This is a detailed LLD with enough words to pass the minimum word count gate for testing purposes. " * 3,
    }
    base.update(overrides)
    return base


class TestGate1NoScenarios:
    """Gate 1: No test scenarios."""

    def test_no_scenarios_blocks(self):
        state = _make_state(test_scenarios=[])
        errors = _run_mechanical_gates(state)
        assert len(errors) == 1
        assert "No test scenarios" in errors[0]

    def test_missing_scenarios_key_blocks(self):
        state = _make_state()
        del state["test_scenarios"]
        errors = _run_mechanical_gates(state)
        assert len(errors) == 1
        assert "No test scenarios" in errors[0]

    def test_no_scenarios_returns_early(self):
        """When no scenarios, skip other gates (nothing to check)."""
        state = _make_state(test_scenarios=[], requirements=[], lld_content="")
        errors = _run_mechanical_gates(state)
        # Only 1 error, not 3 (no cascading errors)
        assert len(errors) == 1


class TestGate2NoRequirements:
    """Gate 2: No requirements."""

    def test_no_requirements_flags_error(self):
        state = _make_state(requirements=[])
        errors = _run_mechanical_gates(state)
        assert any("No requirements" in e for e in errors)

    def test_missing_requirements_key(self):
        state = _make_state()
        del state["requirements"]
        errors = _run_mechanical_gates(state)
        assert any("No requirements" in e for e in errors)


class TestGate3CoverageRatio:
    """Gate 3: Scenario-to-requirement coverage ratio."""

    def test_fewer_scenarios_than_requirements(self):
        state = _make_state(
            test_scenarios=[{"name": "test_one", "type": "unit"}],
            requirements=["R1", "R2", "R3"],
        )
        errors = _run_mechanical_gates(state)
        assert any("coverage ratio" in e for e in errors)

    def test_equal_scenarios_and_requirements_passes(self):
        state = _make_state(
            test_scenarios=[
                {"name": "test_a", "type": "unit"},
                {"name": "test_b", "type": "unit"},
            ],
            requirements=["R1", "R2"],
        )
        errors = _run_mechanical_gates(state)
        assert not any("coverage ratio" in e for e in errors)

    def test_more_scenarios_than_requirements_passes(self):
        state = _make_state(
            test_scenarios=[
                {"name": "test_a", "type": "unit"},
                {"name": "test_b", "type": "unit"},
                {"name": "test_c", "type": "unit"},
            ],
            requirements=["R1", "R2"],
        )
        errors = _run_mechanical_gates(state)
        assert not any("coverage ratio" in e for e in errors)

    def test_no_requirements_skips_ratio_check(self):
        """If requirements are missing, Gate 2 catches it, not Gate 3."""
        state = _make_state(requirements=[])
        errors = _run_mechanical_gates(state)
        assert not any("coverage ratio" in e for e in errors)


class TestGate4DuplicateScenarios:
    """Gate 4: Duplicate scenario names."""

    def test_duplicate_names_detected(self):
        state = _make_state(
            test_scenarios=[
                {"name": "test_create_user", "type": "unit"},
                {"name": "test_create_user", "type": "unit"},
            ],
        )
        errors = _run_mechanical_gates(state)
        assert any("Duplicate scenario" in e for e in errors)

    def test_case_insensitive_duplicate_detection(self):
        state = _make_state(
            test_scenarios=[
                {"name": "Test_Create_User", "type": "unit"},
                {"name": "test_create_user", "type": "unit"},
            ],
        )
        errors = _run_mechanical_gates(state)
        assert any("Duplicate scenario" in e for e in errors)

    def test_unique_names_pass(self):
        state = _make_state()
        errors = _run_mechanical_gates(state)
        assert not any("Duplicate scenario" in e for e in errors)

    def test_string_scenarios_handled(self):
        """Scenarios can be plain strings too."""
        state = _make_state(
            test_scenarios=["test_one", "test_one"],
        )
        errors = _run_mechanical_gates(state)
        assert any("Duplicate scenario" in e for e in errors)


class TestGate5LLDContent:
    """Gate 5: LLD content minimum substance."""

    def test_empty_lld_content_blocks(self):
        state = _make_state(lld_content="")
        errors = _run_mechanical_gates(state)
        assert any("No LLD content" in e for e in errors)

    def test_too_short_lld_blocks(self):
        state = _make_state(lld_content="Just a few words")
        errors = _run_mechanical_gates(state)
        assert any("too short" in e for e in errors)

    def test_adequate_lld_passes(self):
        state = _make_state()
        errors = _run_mechanical_gates(state)
        assert not any("LLD content" in e for e in errors)
        assert not any("too short" in e for e in errors)


class TestAllGatesPass:
    """Test that a valid state passes all gates."""

    def test_valid_state_returns_no_errors(self):
        state = _make_state()
        errors = _run_mechanical_gates(state)
        assert errors == []

    def test_multiple_errors_collected(self):
        """When multiple gates fail, all errors are reported."""
        state = _make_state(
            requirements=[],
            lld_content="short",
        )
        errors = _run_mechanical_gates(state)
        assert len(errors) >= 2
        assert any("requirements" in e.lower() for e in errors)
        assert any("short" in e.lower() or "lld content" in e.lower() for e in errors)
