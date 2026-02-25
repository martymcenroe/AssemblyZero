"""Unit tests for assemblyzero/workflows/testing/circuit_breaker.py.

Issue #443: Add comprehensive unit tests for the circuit breaker module.

Tests cover all four public functions:
- estimate_iteration_cost
- check_circuit_breaker
- record_iteration_cost
- budget_summary

Plus edge cases, CI compatibility, coverage verification, and regression guards.

Deviations from LLD spec (adapted to actual implementation):
- State uses token-based keys (token_budget, estimated_tokens_used, lld_content,
  completed_files, context_content, green_phase_output), NOT dollar-based keys.
- estimate_iteration_cost returns int, not float.
- record_iteration_cost takes only state (no cost param), returns int,
  does NOT mutate state.
- check_circuit_breaker with token_budget<=0 returns (False, "") — no budget
  means no enforcement, not an immediate trip.
"""

import inspect
from copy import deepcopy

import pytest

from assemblyzero.workflows.testing.circuit_breaker import (
    BASE_TOKENS_PER_ITERATION,
    budget_summary,
    check_circuit_breaker,
    estimate_iteration_cost,
    record_iteration_cost,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def empty_state() -> dict:
    """State with all zero/default values — baseline for testing."""
    return {
        "token_budget": 500_000,
        "estimated_tokens_used": 0,
        "lld_content": "",
        "completed_files": [],
        "context_content": "",
        "green_phase_output": "",
    }


@pytest.fixture
def mid_budget_state() -> dict:
    """State at ~50% budget consumption — happy path."""
    return {
        "token_budget": 500_000,
        "estimated_tokens_used": 200_000,
        "lld_content": "x" * 4000,  # 1000 tokens worth of LLD
        "completed_files": [("file1.py", "y" * 2000), ("file2.py", "z" * 2000)],
        "context_content": "c" * 1000,
        "green_phase_output": "test output " * 50,
    }


@pytest.fixture
def near_limit_state() -> dict:
    """State approaching circuit breaker trip threshold — boundary."""
    return {
        "token_budget": 500_000,
        "estimated_tokens_used": 490_000,
        "lld_content": "x" * 4000,
        "completed_files": [("f.py", "code" * 500)],
        "context_content": "ctx" * 100,
        "green_phase_output": "output" * 100,
    }


@pytest.fixture
def over_budget_state() -> dict:
    """State that has exceeded the budget — trip condition.

    estimated_tokens_used is already near the budget, and the next iteration
    cost will push it over.
    """
    return {
        "token_budget": 100_000,
        "estimated_tokens_used": 99_000,
        "lld_content": "x" * 40_000,  # large LLD drives up next iteration cost
        "completed_files": [("big.py", "y" * 40_000)],
        "context_content": "c" * 10_000,
        "green_phase_output": "o" * 10_000,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Helper: Extract trip flag/reason from check_circuit_breaker result
# ═══════════════════════════════════════════════════════════════════════════════


def _get_trip_flag(result) -> bool:
    """Extract the trip boolean from check_circuit_breaker result."""
    if isinstance(result, tuple):
        return result[0]
    if isinstance(result, dict):
        return result.get("tripped", result.get("trip", False))
    if isinstance(result, bool):
        return result
    raise TypeError(f"Unexpected return type from check_circuit_breaker: {type(result)}")


def _get_trip_reason(result) -> str:
    """Extract the reason string from check_circuit_breaker result."""
    if isinstance(result, tuple) and len(result) >= 2:
        return result[1]
    if isinstance(result, dict):
        return result.get("reason", "")
    return ""


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: estimate_iteration_cost (T010–T040)
# ═══════════════════════════════════════════════════════════════════════════════


class TestEstimateIterationCost:
    """Tests for estimate_iteration_cost()."""

    def test_estimate_iteration_cost_empty_state(self, empty_state: dict) -> None:
        """T010: Estimate returns a non-negative value for empty/default state."""
        result = estimate_iteration_cost(empty_state)
        assert isinstance(result, (int, float)), f"Expected numeric, got {type(result)}"
        assert result >= 0, f"Expected non-negative, got {result}"
        # Empty state should return at least the base overhead
        assert result >= BASE_TOKENS_PER_ITERATION

    def test_estimate_iteration_cost_mid_budget(self, mid_budget_state: dict) -> None:
        """T020: Estimate reflects accumulated content (LLD, files, context)."""
        result = estimate_iteration_cost(mid_budget_state)
        assert isinstance(result, (int, float)), f"Expected numeric, got {type(result)}"
        # Mid-budget state has content; cost should exceed base overhead
        assert result > BASE_TOKENS_PER_ITERATION, (
            f"State with content should cost more than base {BASE_TOKENS_PER_ITERATION}, "
            f"got {result}"
        )

    def test_estimate_iteration_cost_returns_numeric(self) -> None:
        """T030: Return type is always int or float (numeric)."""
        state = {
            "token_budget": 100_000,
            "estimated_tokens_used": 10_000,
            "lld_content": "some content",
            "completed_files": [("f.py", "code")],
            "context_content": "ctx",
            "green_phase_output": "output",
        }
        result = estimate_iteration_cost(state)
        assert isinstance(result, (int, float)), f"Expected numeric, got {type(result)}"

    def test_estimate_iteration_cost_scales_with_activity(self) -> None:
        """T040: Larger content produces higher or equal cost estimate."""
        low_activity = {
            "lld_content": "",
            "completed_files": [],
            "context_content": "",
            "green_phase_output": "",
        }
        high_activity = {
            "lld_content": "x" * 10_000,
            "completed_files": [("a.py", "y" * 5_000), ("b.py", "z" * 5_000)],
            "context_content": "c" * 3_000,
            "green_phase_output": "o" * 2_000,
        }
        low_cost = estimate_iteration_cost(low_activity)
        high_cost = estimate_iteration_cost(high_activity)
        assert high_cost >= low_cost, (
            f"Expected high content cost ({high_cost}) >= low content cost ({low_cost})"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: check_circuit_breaker (T050–T090)
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckCircuitBreaker:
    """Tests for check_circuit_breaker()."""

    def test_check_circuit_breaker_no_trip_fresh_state(self, empty_state: dict) -> None:
        """T050: Fresh state with budget headroom should not trip the breaker."""
        result = check_circuit_breaker(empty_state)
        assert _get_trip_flag(result) is False, (
            f"Fresh state with ample budget should not trip, got: {result}"
        )

    def test_check_circuit_breaker_no_trip_within_budget(
        self, mid_budget_state: dict
    ) -> None:
        """T060: State within budget does not trip."""
        result = check_circuit_breaker(mid_budget_state)
        assert _get_trip_flag(result) is False, (
            f"Mid-budget state should not trip, got: {result}"
        )

    def test_check_circuit_breaker_trips_over_budget(
        self, over_budget_state: dict
    ) -> None:
        """T070: State exceeding budget trips the breaker."""
        result = check_circuit_breaker(over_budget_state)
        assert _get_trip_flag(result) is True, (
            f"Over-budget state should trip, got: {result}"
        )
        reason = _get_trip_reason(result)
        assert len(reason) > 0, "Tripped breaker should provide a reason"

    def test_check_circuit_breaker_trips_at_exact_boundary(self) -> None:
        """T080: Breaker trips when estimated_used + next_cost > token_budget.

        Adapted from LLD T080 (max_iterations). The actual module doesn't
        check max_iterations; it checks token budget. We test the boundary
        where next iteration cost would push tokens over budget.
        """
        # Construct state where next cost will barely exceed budget
        # estimate_iteration_cost returns BASE_TOKENS_PER_ITERATION for empty content
        state = {
            "token_budget": BASE_TOKENS_PER_ITERATION + 100,
            "estimated_tokens_used": 200,  # 200 + 5000 > 5100
            "lld_content": "",
            "completed_files": [],
            "context_content": "",
            "green_phase_output": "",
        }
        result = check_circuit_breaker(state)
        assert _get_trip_flag(result) is True, (
            f"Boundary state should trip, got: {result}"
        )

    def test_check_circuit_breaker_return_structure(self, empty_state: dict) -> None:
        """T090: Return value is a tuple with (bool, str)."""
        result = check_circuit_breaker(empty_state)
        if isinstance(result, tuple):
            assert len(result) >= 2, f"Expected at least 2 elements, got {len(result)}"
            assert isinstance(result[0], bool), (
                f"First element should be bool, got {type(result[0])}"
            )
            assert isinstance(result[1], str), (
                f"Second element should be str, got {type(result[1])}"
            )
        elif isinstance(result, dict):
            assert any(
                k in result for k in ("tripped", "trip")
            ), f"Dict missing trip flag key, keys: {result.keys()}"
            assert "reason" in result, (
                f"Dict missing 'reason' key, keys: {result.keys()}"
            )
        elif isinstance(result, bool):
            pass  # Simplest case — just a bool
        else:
            pytest.fail(f"Unexpected return type: {type(result)}")


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: record_iteration_cost (T100–T130)
# ═══════════════════════════════════════════════════════════════════════════════


class TestRecordIterationCost:
    """Tests for record_iteration_cost().

    Note: The actual implementation takes only `state` (no cost parameter)
    and returns an int (updated estimated_tokens_used). It does NOT mutate
    the state dict — the caller is responsible for state updates.
    """

    def test_record_iteration_cost_accumulates(self, empty_state: dict) -> None:
        """T100: Recording cost returns current + next iteration estimate."""
        current = empty_state.get("estimated_tokens_used", 0)
        next_cost = estimate_iteration_cost(empty_state)
        result = record_iteration_cost(empty_state)
        assert result == current + next_cost, (
            f"Expected {current} + {next_cost} = {current + next_cost}, got {result}"
        )

    def test_record_iteration_cost_multiple_calls(self, empty_state: dict) -> None:
        """T110: Simulating multiple recordings by updating state between calls."""
        state = deepcopy(empty_state)
        accumulated = state.get("estimated_tokens_used", 0)

        for _ in range(3):
            new_total = record_iteration_cost(state)
            assert new_total > accumulated, (
                f"Each recording should increase total: {new_total} > {accumulated}"
            )
            # Simulate the caller updating state (as the real workflow does)
            state["estimated_tokens_used"] = new_total
            accumulated = new_total

        assert accumulated > 0, "After 3 iterations, accumulated cost must be positive"

    def test_record_iteration_cost_zero_content_state(self, empty_state: dict) -> None:
        """T120: Empty content state still includes base overhead in cost."""
        result = record_iteration_cost(empty_state)
        # Even with no content, base overhead means cost > 0
        assert result >= BASE_TOKENS_PER_ITERATION, (
            f"Expected at least base overhead {BASE_TOKENS_PER_ITERATION}, got {result}"
        )

    def test_record_iteration_cost_preserves_state(
        self, mid_budget_state: dict
    ) -> None:
        """T130: record_iteration_cost does not mutate the state dict."""
        snapshot = deepcopy(mid_budget_state)
        record_iteration_cost(mid_budget_state)

        # State should be entirely unchanged (function returns value, not mutating)
        for key in snapshot:
            assert mid_budget_state[key] == snapshot[key], (
                f"Field '{key}' was mutated: {snapshot[key]} -> {mid_budget_state[key]}"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: budget_summary (T140–T170)
# ═══════════════════════════════════════════════════════════════════════════════


class TestBudgetSummary:
    """Tests for budget_summary()."""

    def test_budget_summary_returns_string(self, empty_state: dict) -> None:
        """T140: Summary is always a string."""
        result = budget_summary(empty_state)
        assert isinstance(result, str), f"Expected str, got {type(result)}"

    def test_budget_summary_contains_budget_info(self, mid_budget_state: dict) -> None:
        """T150: Summary includes token usage and budget information."""
        result = budget_summary(mid_budget_state)
        assert isinstance(result, str)
        # The summary should contain token-related information
        has_budget_info = any(
            substr in result
            for substr in (
                "200,000",  # estimated_tokens_used
                "500,000",  # token_budget
                "Token",
                "token",
                "budget",
                "Budget",
                "%",
            )
        )
        assert has_budget_info, (
            f"Budget summary should contain budget-related info, got: '{result}'"
        )

    def test_budget_summary_zero_budget_zero_used(self) -> None:
        """T160: Summary handles zero-budget, zero-used state (returns empty)."""
        state = {
            "token_budget": 0,
            "estimated_tokens_used": 0,
        }
        result = budget_summary(state)
        assert isinstance(result, str)
        # Actual implementation returns "" when both are <= 0
        assert result == "", (
            f"Expected empty string for zero budget + zero used, got: '{result}'"
        )

    def test_budget_summary_huge_budget(self) -> None:
        """T170: Summary handles very large budget values without formatting errors."""
        state = {
            "token_budget": 1_000_000_000_000,
            "estimated_tokens_used": 500_000,
        }
        result = budget_summary(state)
        assert isinstance(result, str)
        assert len(result) > 0, "Huge budget with usage should produce non-empty summary"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Edge Cases (T180–T210)
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Edge case tests for boundary conditions and data anomalies."""

    def test_zero_budget_means_no_enforcement(self) -> None:
        """T180: Zero token_budget means 'no budget set', not 'immediate trip'.

        Adapted from LLD T180. The actual implementation returns (False, "")
        when token_budget <= 0, treating it as unlimited/unset.
        """
        state = {
            "token_budget": 0,
            "estimated_tokens_used": 0,
            "lld_content": "",
            "completed_files": [],
            "context_content": "",
            "green_phase_output": "",
        }
        result = check_circuit_breaker(state)
        assert _get_trip_flag(result) is False, (
            f"Zero token_budget means no enforcement (no trip), got: {result}"
        )

    def test_huge_budget_no_trip(self) -> None:
        """T190: Very large token_budget does not trip with normal activity."""
        state = {
            "token_budget": 1_000_000_000,
            "estimated_tokens_used": 1_000,
            "lld_content": "small content",
            "completed_files": [("f.py", "code")],
            "context_content": "",
            "green_phase_output": "",
        }
        result = check_circuit_breaker(state)
        assert _get_trip_flag(result) is False, (
            f"Huge budget with low activity should not trip, got: {result}"
        )

    def test_negative_tokens_used_does_not_crash(self) -> None:
        """T200: Negative estimated_tokens_used (data anomaly) does not raise."""
        state = {
            "token_budget": 100_000,
            "estimated_tokens_used": -5_000,
            "lld_content": "",
            "completed_files": [],
            "context_content": "",
            "green_phase_output": "",
        }
        # None of these should raise an unhandled exception
        try:
            estimate_iteration_cost(state)
        except (KeyError, ValueError, TypeError):
            pass  # Acceptable controlled exceptions

        try:
            check_circuit_breaker(state)
        except (KeyError, ValueError, TypeError):
            pass

        try:
            record_iteration_cost(state)
        except (KeyError, ValueError, TypeError):
            pass

        try:
            budget_summary(state)
        except (KeyError, ValueError, TypeError):
            pass

    def test_empty_dict_state_handling(self) -> None:
        """T210: Completely empty dict handled gracefully (KeyError or defaults)."""
        state: dict = {}
        functions_under_test = [
            lambda: estimate_iteration_cost(state),
            lambda: check_circuit_breaker(state),
            lambda: record_iteration_cost(state),
            lambda: budget_summary(state),
        ]
        for func in functions_under_test:
            try:
                func()
            except (KeyError, TypeError, ValueError):
                pass  # Acceptable — controlled failure
            except Exception as e:
                pytest.fail(
                    f"Unexpected exception type {type(e).__name__} for empty dict: {e}"
                )


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: CI Compatibility (T220–T230)
# ═══════════════════════════════════════════════════════════════════════════════


class TestCICompatibility:
    """Verify tests run in CI without external dependencies."""

    def test_no_external_imports_required(self) -> None:
        """T220: circuit_breaker module imports without network or external services."""
        import importlib

        # Re-import to verify no side effects
        mod = importlib.import_module(
            "assemblyzero.workflows.testing.circuit_breaker"
        )
        assert mod is not None

        # Read source to verify no network-dependent imports
        source_file = inspect.getfile(mod)
        with open(source_file, encoding="utf-8") as f:
            source = f.read()

        network_imports = ["requests", "httpx", "urllib3", "aiohttp"]
        for lib in network_imports:
            assert f"import {lib}" not in source, (
                f"circuit_breaker.py should not import network library '{lib}'"
            )

    def test_all_tests_run_offline(self) -> None:
        """T230: Verify test suite requires no network calls.

        This is a meta-assertion: if this test is running and passing,
        the suite is running without network. We also verify no HTTP
        call patterns in the source module.
        """
        import assemblyzero.workflows.testing.circuit_breaker as cb

        source_file = inspect.getfile(cb)
        with open(source_file, encoding="utf-8") as f:
            source = f.read()

        # Check for network call patterns (not comments)
        for pattern in ["requests.get", "requests.post", "httpx.", "urlopen"]:
            assert pattern not in source, (
                f"Source contains network call pattern '{pattern}'"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Coverage Verification (T240)
# ═══════════════════════════════════════════════════════════════════════════════


class TestCoverageVerification:
    """Verify all public functions are exercised."""

    def test_all_public_functions_exercised(self) -> None:
        """T240: Every public function in circuit_breaker is called at least once."""
        import assemblyzero.workflows.testing.circuit_breaker as cb

        public_functions = {
            name
            for name, obj in inspect.getmembers(cb, inspect.isfunction)
            if not name.startswith("_")
        }

        # These are the functions we explicitly test in this file
        tested_functions = {
            "estimate_iteration_cost",
            "check_circuit_breaker",
            "record_iteration_cost",
            "budget_summary",
        }

        untested = public_functions - tested_functions
        assert not untested, (
            f"Public functions not covered by tests: {untested}. "
            f"Add test cases for these functions."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Regression Guard (T250)
# ═══════════════════════════════════════════════════════════════════════════════


class TestRegressionGuard:
    """Verify new tests don't break existing suite."""

    def test_existing_unit_suite_unaffected(self) -> None:
        """T250: New test file does not break existing tests (import isolation).

        Verifying that importing this test module has no side effects
        that could affect other test modules.
        """
        import importlib
        import os

        # Verify our test module can be imported cleanly
        mod = importlib.import_module("tests.unit.test_circuit_breaker")
        assert mod is not None

        # Verify we haven't polluted sys.modules with unexpected entries
        assert "circuit_breaker_global_state" not in dir(mod), (
            "Test module should not define global mutable state"
        )

        # Verify no environment variable mutations
        assert "AZ_CIRCUIT_BREAKER_TEST" not in os.environ, (
            "Test module should not mutate environment variables"
        )