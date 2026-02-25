# Implementation Request: tests/unit/test_circuit_breaker.py

## Task

Write the complete contents of `tests/unit/test_circuit_breaker.py`.

Change type: Add
Description: New unit test file with 25 test cases covering all public functions and edge cases

## LLD Specification

# Implementation Spec: Test: Add Unit Tests for Circuit Breaker Module

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #443 |
| LLD | `docs/lld/active/443-test-circuit-breaker-unit-tests.md` |
| Generated | 2026-02-25 |
| Status | DRAFT |

## 1. Overview

Add 25 assertion-based unit tests for `assemblyzero/workflows/testing/circuit_breaker.py`, covering all four public functions (`estimate_iteration_cost`, `check_circuit_breaker`, `record_iteration_cost`, `budget_summary`), edge cases, CI compatibility, coverage verification, and regression guards.

**Objective:** Replace smoke-test-only coverage with proper assertion-based unit tests for the circuit breaker module.

**Success Criteria:**
1. All 25 tests pass with `poetry run pytest tests/unit/test_circuit_breaker.py -v`
2. Coverage of `circuit_breaker.py` ≥ 95% line coverage
3. No regressions in the existing test suite

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `tests/unit/test_circuit_breaker.py` | Add | New unit test file with 25 test cases covering all public functions and edge cases |

**Implementation Order Rationale:** Single file — no dependency ordering needed. The source module already exists; only a test file is added.

## 3. Current State (for Modify/Delete files)

No files are being modified or deleted. This is a pure addition.

### 3.1 Source Under Test: `assemblyzero/workflows/testing/circuit_breaker.py`

**NOTE:** This file is NOT modified, but its public API must be understood to write correct tests. The implementation agent MUST inspect this file first and adapt test expectations to the actual signatures and return types.

**Expected public functions (from LLD):**

```python
def estimate_iteration_cost(state: dict) -> float:
    """Estimate the cost of the next iteration based on current state."""
    ...

def check_circuit_breaker(state: dict) -> tuple[bool, str]:
    """Check whether the circuit breaker should trip.
    Returns (tripped: bool, reason: str).
    """
    ...

def record_iteration_cost(state: dict, cost: float) -> dict:
    """Record an iteration's cost into the state. Mutates/returns state."""
    ...

def budget_summary(state: dict) -> str:
    """Return a human-readable budget summary string."""
    ...
```

**CRITICAL PRE-IMPLEMENTATION STEP:** Before writing any test code, the implementing agent MUST run:

```bash
python -c "import inspect; import assemblyzero.workflows.testing.circuit_breaker as cb; members = [(n, inspect.signature(f)) for n, f in inspect.getmembers(cb, inspect.isfunction) if not n.startswith('_')]; print('\n'.join(f'{n}{s}' for n, s in members))"
```

This reveals actual function signatures. If they differ from the LLD assumptions, adapt the test code accordingly. Document any deviations in Section 10.

## 4. Data Structures

### 4.1 Test State Dictionary (fixture shape)

**Definition:**

```python
# Mirrors TDDState TypedDict used by the TDD workflow
state: dict = {
    "budget_dollars": float,
    "spent_dollars": float,
    "iteration": int,
    "max_iterations": int,
    "llm_calls": int,
    "test_runs": int,
}
```

**Concrete Example — `empty_state`:**

```json
{
    "budget_dollars": 10.0,
    "spent_dollars": 0.0,
    "iteration": 0,
    "max_iterations": 10,
    "llm_calls": 0,
    "test_runs": 0
}
```

**Concrete Example — `mid_budget_state`:**

```json
{
    "budget_dollars": 10.0,
    "spent_dollars": 5.0,
    "iteration": 5,
    "max_iterations": 10,
    "llm_calls": 25,
    "test_runs": 15
}
```

**Concrete Example — `near_limit_state`:**

```json
{
    "budget_dollars": 10.0,
    "spent_dollars": 9.5,
    "iteration": 9,
    "max_iterations": 10,
    "llm_calls": 50,
    "test_runs": 30
}
```

**Concrete Example — `over_budget_state`:**

```json
{
    "budget_dollars": 10.0,
    "spent_dollars": 12.0,
    "iteration": 8,
    "max_iterations": 10,
    "llm_calls": 60,
    "test_runs": 40
}
```

## 5. Function Specifications

### 5.1 Fixture: `empty_state()`

**File:** `tests/unit/test_circuit_breaker.py`

**Signature:**

```python
@pytest.fixture
def empty_state() -> dict:
    """State with all zero/default values — baseline for testing."""
    ...
```

**Output Example:**

```python
{
    "budget_dollars": 10.0,
    "spent_dollars": 0.0,
    "iteration": 0,
    "max_iterations": 10,
    "llm_calls": 0,
    "test_runs": 0,
}
```

**Edge Cases:** N/A — fixture, not a function under test.

### 5.2 Fixture: `mid_budget_state()`

**File:** `tests/unit/test_circuit_breaker.py`

**Signature:**

```python
@pytest.fixture
def mid_budget_state() -> dict:
    """State at ~50% budget consumption — happy path."""
    ...
```

**Output Example:**

```python
{
    "budget_dollars": 10.0,
    "spent_dollars": 5.0,
    "iteration": 5,
    "max_iterations": 10,
    "llm_calls": 25,
    "test_runs": 15,
}
```

### 5.3 Fixture: `near_limit_state()`

**File:** `tests/unit/test_circuit_breaker.py`

**Signature:**

```python
@pytest.fixture
def near_limit_state() -> dict:
    """State approaching circuit breaker trip threshold — boundary."""
    ...
```

**Output Example:**

```python
{
    "budget_dollars": 10.0,
    "spent_dollars": 9.5,
    "iteration": 9,
    "max_iterations": 10,
    "llm_calls": 50,
    "test_runs": 30,
}
```

### 5.4 Fixture: `over_budget_state()`

**File:** `tests/unit/test_circuit_breaker.py`

**Signature:**

```python
@pytest.fixture
def over_budget_state() -> dict:
    """State that has exceeded the budget — trip condition."""
    ...
```

**Output Example:**

```python
{
    "budget_dollars": 10.0,
    "spent_dollars": 12.0,
    "iteration": 8,
    "max_iterations": 10,
    "llm_calls": 60,
    "test_runs": 40,
}
```

### 5.5 Test: `test_estimate_iteration_cost_empty_state()`

**File:** `tests/unit/test_circuit_breaker.py`

**Input Example:**

```python
state = {"budget_dollars": 10.0, "spent_dollars": 0.0, "iteration": 0,
         "max_iterations": 10, "llm_calls": 0, "test_runs": 0}
```

**Output Example:**

```python
result = estimate_iteration_cost(state)
# result == 0.0 (or some non-negative float)
```

**Assertions:**
- `isinstance(result, float)`
- `result >= 0.0`

### 5.6 Test: `test_estimate_iteration_cost_mid_budget()`

**Input Example:**

```python
state = {"budget_dollars": 10.0, "spent_dollars": 5.0, "iteration": 5,
         "max_iterations": 10, "llm_calls": 25, "test_runs": 15}
```

**Output Example:**

```python
result = estimate_iteration_cost(state)
# result > 0.0 (reflects accumulated activity)
```

**Assertions:**
- `isinstance(result, float)`
- `result > 0.0` (state has activity, cost should be positive)

### 5.7 Test: `test_estimate_iteration_cost_returns_float()`

**Input Example:**

```python
state = {"budget_dollars": 5.0, "spent_dollars": 1.0, "iteration": 1,
         "max_iterations": 5, "llm_calls": 3, "test_runs": 2}
```

**Assertions:**
- `isinstance(result, float)` — strict type check, not int

### 5.8 Test: `test_estimate_iteration_cost_scales_with_activity()`

**Input Example:**

```python
low_activity = {"budget_dollars": 10.0, "spent_dollars": 0.0, "iteration": 0,
                "max_iterations": 10, "llm_calls": 0, "test_runs": 0}
high_activity = {"budget_dollars": 10.0, "spent_dollars": 5.0, "iteration": 5,
                 "max_iterations": 10, "llm_calls": 50, "test_runs": 30}
```

**Assertions:**
- `estimate_iteration_cost(high_activity) >= estimate_iteration_cost(low_activity)`

### 5.9 Test: `test_check_circuit_breaker_no_trip_fresh_state()`

**Input Example:**

```python
state = empty_state  # fixture
```

**Output Example:**

```python
result = check_circuit_breaker(state)
# result == (False, "") or (False, "some reason")
```

**Assertions:**
- `result[0] is False` (or `result["tripped"] is False` — adapt to actual return type)

### 5.10 Test: `test_check_circuit_breaker_no_trip_within_budget()`

**Input Example:**

```python
state = mid_budget_state  # fixture
```

**Assertions:**
- Trip flag is `False`

### 5.11 Test: `test_check_circuit_breaker_trips_over_budget()`

**Input Example:**

```python
state = over_budget_state  # fixture
```

**Assertions:**
- Trip flag is `True`
- Reason string is non-empty

### 5.12 Test: `test_check_circuit_breaker_trips_max_iterations()`

**Input Example:**

```python
state = {"budget_dollars": 100.0, "spent_dollars": 1.0, "iteration": 10,
         "max_iterations": 10, "llm_calls": 5, "test_runs": 5}
```

**Assertions:**
- Trip flag is `True` (max iterations reached regardless of budget)

### 5.13 Test: `test_check_circuit_breaker_return_structure()`

**Input Example:**

```python
state = empty_state  # any valid state
```

**Assertions:**
- Result is a tuple (or dict) containing a boolean and a string
- `isinstance(result[0], bool)` and `isinstance(result[1], str)` (adapt if dict)

### 5.14 Test: `test_record_iteration_cost_accumulates()`

**Input Example:**

```python
state = empty_state  # spent_dollars == 0.0
cost = 1.50
```

**Output Example:**

```python
updated = record_iteration_cost(state, cost)
# updated["spent_dollars"] == pytest.approx(1.50)
```

**Assertions:**
- `updated["spent_dollars"] == pytest.approx(1.50)`

### 5.15 Test: `test_record_iteration_cost_multiple_calls()`

**Input Example:**

```python
state = empty_state  # spent_dollars == 0.0
# Record 1.0 three times
```

**Assertions:**
- After three recordings of 1.0, `state["spent_dollars"] == pytest.approx(3.0)`

### 5.16 Test: `test_record_iteration_cost_zero_amount()`

**Input Example:**

```python
state = empty_state  # spent_dollars == 0.0
cost = 0.0
```

**Assertions:**
- `state["spent_dollars"] == pytest.approx(0.0)` (unchanged)

### 5.17 Test: `test_record_iteration_cost_preserves_other_fields()`

**Input Example:**

```python
state = mid_budget_state  # all fields populated
original_iteration = state["iteration"]
original_max = state["max_iterations"]
original_llm_calls = state["llm_calls"]
original_test_runs = state["test_runs"]
```

**Assertions:**
- After recording cost, `iteration`, `max_iterations`, `llm_calls`, `test_runs` remain unchanged

### 5.18 Test: `test_budget_summary_returns_string()`

**Input:** `empty_state` fixture

**Assertions:**
- `isinstance(result, str)`
- `len(result) > 0`

### 5.19 Test: `test_budget_summary_contains_budget_info()`

**Input:** `mid_budget_state` with `spent_dollars=5.0`, `budget_dollars=10.0`

**Assertions:**
- Result string contains "5" (spent amount) or equivalent numeric representation
- Result string contains "10" or "5" (remaining or total)

### 5.20 Test: `test_budget_summary_zero_budget()`

**Input:**

```python
state = {"budget_dollars": 0.0, "spent_dollars": 0.0, "iteration": 0,
         "max_iterations": 10, "llm_calls": 0, "test_runs": 0}
```

**Assertions:**
- No exception raised
- `isinstance(result, str)`

### 5.21 Test: `test_budget_summary_huge_budget()`

**Input:**

```python
state = {"budget_dollars": 1e12, "spent_dollars": 0.0, "iteration": 0,
         "max_iterations": 10, "llm_calls": 0, "test_runs": 0}
```

**Assertions:**
- No exception raised
- `isinstance(result, str)`

### 5.22 Test: `test_zero_budget_immediate_trip()`

**Input:**

```python
state = {"budget_dollars": 0.0, "spent_dollars": 0.0, "iteration": 0,
         "max_iterations": 10, "llm_calls": 0, "test_runs": 0}
```

**Assertions:**
- `check_circuit_breaker(state)` trips (`True`)

### 5.23 Test: `test_huge_budget_no_trip()`

**Input:**

```python
state = {"budget_dollars": 1e9, "spent_dollars": 1.0, "iteration": 1,
         "max_iterations": 100, "llm_calls": 5, "test_runs": 3}
```

**Assertions:**
- `check_circuit_breaker(state)` does NOT trip (`False`)

### 5.24 Test: `test_negative_spent_does_not_crash()`

**Input:**

```python
state = {"budget_dollars": 10.0, "spent_dollars": -5.0, "iteration": 1,
         "max_iterations": 10, "llm_calls": 1, "test_runs": 1}
```

**Assertions:**
- No unhandled exception from any of the four public functions

### 5.25 Test: `test_empty_dict_state_handling()`

**Input:**

```python
state = {}
```

**Assertions:**
- Each function either returns a sensible default or raises `KeyError`/`TypeError` — but no unhandled crash (e.g., no `AttributeError` on NoneType, no `ZeroDivisionError`)
- Use `pytest.raises` if the function is expected to raise, or just call and confirm no crash

### 5.26 Test: `test_no_external_imports_required()`

**Assertions:**
- `import assemblyzero.workflows.testing.circuit_breaker` succeeds
- Module's `__file__` exists
- No imports from `requests`, `httpx`, `urllib3`, `socket` in the module source

### 5.27 Test: `test_all_tests_run_offline()`

**Assertions:**
- This is a meta-test; verifying the absence of network-dependent code
- Read the source file and assert no `requests.get`, `httpx`, `urlopen` patterns

### 5.28 Test: `test_all_public_functions_exercised()`

**Assertions:**
- Use `inspect.getmembers` to get all public functions
- Cross-reference with a hardcoded set of expected functions
- Assert the set of public functions is a subset of what's tested

### 5.29 Test: `test_existing_unit_suite_unaffected()`

**Assertions:**
- `import tests.unit.test_circuit_breaker` succeeds without ImportError
- No module-level side effects (no `os.environ` mutations, no file I/O)

## 6. Change Instructions

### 6.1 `tests/unit/test_circuit_breaker.py` (Add)

**Complete file contents:**

```python
"""Unit tests for assemblyzero/workflows/testing/circuit_breaker.py.

Issue #443: Add comprehensive unit tests for the circuit breaker module.

Tests cover all four public functions:
- estimate_iteration_cost
- check_circuit_breaker
- record_iteration_cost
- budget_summary

Plus edge cases, CI compatibility, coverage verification, and regression guards.
"""

import inspect
from copy import deepcopy

import pytest

from assemblyzero.workflows.testing.circuit_breaker import (
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
        "budget_dollars": 10.0,
        "spent_dollars": 0.0,
        "iteration": 0,
        "max_iterations": 10,
        "llm_calls": 0,
        "test_runs": 0,
    }


@pytest.fixture
def mid_budget_state() -> dict:
    """State at ~50% budget consumption — happy path."""
    return {
        "budget_dollars": 10.0,
        "spent_dollars": 5.0,
        "iteration": 5,
        "max_iterations": 10,
        "llm_calls": 25,
        "test_runs": 15,
    }


@pytest.fixture
def near_limit_state() -> dict:
    """State approaching circuit breaker trip threshold — boundary."""
    return {
        "budget_dollars": 10.0,
        "spent_dollars": 9.5,
        "iteration": 9,
        "max_iterations": 10,
        "llm_calls": 50,
        "test_runs": 30,
    }


@pytest.fixture
def over_budget_state() -> dict:
    """State that has exceeded the budget — trip condition."""
    return {
        "budget_dollars": 10.0,
        "spent_dollars": 12.0,
        "iteration": 8,
        "max_iterations": 10,
        "llm_calls": 60,
        "test_runs": 40,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Helper: Adapt to actual return type of check_circuit_breaker
# ═══════════════════════════════════════════════════════════════════════════════
#
# The LLD assumes check_circuit_breaker returns (bool, str).
# If the actual module returns a dict like {"tripped": bool, "reason": str},
# update _get_trip_flag() and _get_trip_reason() accordingly.
#
# IMPLEMENTATION NOTE: The implementing agent MUST inspect the actual
# return type of check_circuit_breaker and adjust these helpers if needed.


def _get_trip_flag(result) -> bool:
    """Extract the trip boolean from check_circuit_breaker result.

    Adapt this if the return type is not a tuple.
    """
    if isinstance(result, tuple):
        return result[0]
    if isinstance(result, dict):
        return result.get("tripped", result.get("trip", False))
    # If it's a plain bool, return directly
    if isinstance(result, bool):
        return result
    raise TypeError(f"Unexpected return type from check_circuit_breaker: {type(result)}")


def _get_trip_reason(result) -> str:
    """Extract the reason string from check_circuit_breaker result.

    Adapt this if the return type is not a tuple.
    """
    if isinstance(result, tuple) and len(result) >= 2:
        return result[1]
    if isinstance(result, dict):
        return result.get("reason", "")
    return ""


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: estimate_iteration_cost (REQ-1)
# ═══════════════════════════════════════════════════════════════════════════════


class TestEstimateIterationCost:
    """Tests for estimate_iteration_cost()."""

    def test_estimate_iteration_cost_empty_state(self, empty_state: dict) -> None:
        """T010: Estimate returns a non-negative float for empty/default state."""
        result = estimate_iteration_cost(empty_state)
        assert isinstance(result, (int, float)), f"Expected numeric, got {type(result)}"
        result_float = float(result)
        assert result_float >= 0.0, f"Expected non-negative, got {result_float}"

    def test_estimate_iteration_cost_mid_budget(self, mid_budget_state: dict) -> None:
        """T020: Estimate reflects accumulated state (calls, runs)."""
        result = estimate_iteration_cost(mid_budget_state)
        assert isinstance(result, (int, float)), f"Expected numeric, got {type(result)}"
        # Mid-budget state has activity; cost estimate should be positive
        # NOTE: If the function returns 0.0 for all states, this test will
        # catch that as a potential issue. Relax to >= 0.0 if that's correct behavior.
        assert float(result) >= 0.0

    def test_estimate_iteration_cost_returns_float(self) -> None:
        """T030: Return type is always float (or numeric)."""
        state = {
            "budget_dollars": 5.0,
            "spent_dollars": 1.0,
            "iteration": 1,
            "max_iterations": 5,
            "llm_calls": 3,
            "test_runs": 2,
        }
        result = estimate_iteration_cost(state)
        assert isinstance(result, (int, float)), f"Expected numeric, got {type(result)}"

    def test_estimate_iteration_cost_scales_with_activity(self) -> None:
        """T040: Higher activity state produces higher or equal cost estimate."""
        low_activity = {
            "budget_dollars": 10.0,
            "spent_dollars": 0.0,
            "iteration": 0,
            "max_iterations": 10,
            "llm_calls": 0,
            "test_runs": 0,
        }
        high_activity = {
            "budget_dollars": 10.0,
            "spent_dollars": 5.0,
            "iteration": 5,
            "max_iterations": 10,
            "llm_calls": 50,
            "test_runs": 30,
        }
        low_cost = float(estimate_iteration_cost(low_activity))
        high_cost = float(estimate_iteration_cost(high_activity))
        assert high_cost >= low_cost, (
            f"Expected high activity cost ({high_cost}) >= low activity cost ({low_cost})"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: check_circuit_breaker (REQ-1)
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckCircuitBreaker:
    """Tests for check_circuit_breaker()."""

    def test_check_circuit_breaker_no_trip_fresh_state(self, empty_state: dict) -> None:
        """T050: Fresh state should not trip the breaker."""
        result = check_circuit_breaker(empty_state)
        assert _get_trip_flag(result) is False, (
            f"Fresh state should not trip, got: {result}"
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

    def test_check_circuit_breaker_trips_max_iterations(self) -> None:
        """T080: Reaching max_iterations trips the breaker regardless of budget."""
        state = {
            "budget_dollars": 100.0,
            "spent_dollars": 1.0,
            "iteration": 10,
            "max_iterations": 10,
            "llm_calls": 5,
            "test_runs": 5,
        }
        result = check_circuit_breaker(state)
        assert _get_trip_flag(result) is True, (
            f"Max-iteration state should trip, got: {result}"
        )

    def test_check_circuit_breaker_return_structure(self, empty_state: dict) -> None:
        """T090: Return value includes trip boolean and reason string."""
        result = check_circuit_breaker(empty_state)
        # Accept tuple(bool, str) or dict with tripped/reason keys
        if isinstance(result, tuple):
            assert len(result) >= 2, f"Expected at least 2 elements, got {len(result)}"
            assert isinstance(result[0], bool), f"First element should be bool, got {type(result[0])}"
            assert isinstance(result[1], str), f"Second element should be str, got {type(result[1])}"
        elif isinstance(result, dict):
            assert any(
                k in result for k in ("tripped", "trip")
            ), f"Dict missing trip flag key, keys: {result.keys()}"
            assert "reason" in result, f"Dict missing 'reason' key, keys: {result.keys()}"
        elif isinstance(result, bool):
            # Simplest case — just a bool. Still valid, but note it.
            pass
        else:
            pytest.fail(f"Unexpected return type: {type(result)}")


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: record_iteration_cost (REQ-1)
# ═══════════════════════════════════════════════════════════════════════════════


class TestRecordIterationCost:
    """Tests for record_iteration_cost()."""

    def test_record_iteration_cost_accumulates(self, empty_state: dict) -> None:
        """T100: Recording a cost increases spent_dollars."""
        original_spent = empty_state["spent_dollars"]
        updated = record_iteration_cost(empty_state, 1.50)
        # Function may mutate in-place and/or return the state
        target = updated if updated is not None else empty_state
        assert target["spent_dollars"] == pytest.approx(original_spent + 1.50), (
            f"Expected spent_dollars={original_spent + 1.50}, got {target['spent_dollars']}"
        )

    def test_record_iteration_cost_multiple_calls(self, empty_state: dict) -> None:
        """T110: Multiple recordings accumulate correctly."""
        state = empty_state
        for _ in range(3):
            result = record_iteration_cost(state, 1.0)
            state = result if result is not None else state
        assert state["spent_dollars"] == pytest.approx(3.0), (
            f"Expected spent_dollars=3.0, got {state['spent_dollars']}"
        )

    def test_record_iteration_cost_zero_amount(self, empty_state: dict) -> None:
        """T120: Recording zero cost does not change spent_dollars."""
        before = empty_state["spent_dollars"]
        result = record_iteration_cost(empty_state, 0.0)
        target = result if result is not None else empty_state
        assert target["spent_dollars"] == pytest.approx(before), (
            f"Expected spent_dollars unchanged at {before}, got {target['spent_dollars']}"
        )

    def test_record_iteration_cost_preserves_other_fields(
        self, mid_budget_state: dict
    ) -> None:
        """T130: Recording cost only mutates cost-related fields."""
        snapshot = deepcopy(mid_budget_state)
        result = record_iteration_cost(mid_budget_state, 0.50)
        target = result if result is not None else mid_budget_state

        # These fields should not change
        for field in ("iteration", "max_iterations", "llm_calls", "test_runs"):
            if field in snapshot:
                assert target.get(field) == snapshot[field], (
                    f"Field '{field}' changed: {snapshot[field]} -> {target.get(field)}"
                )


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: budget_summary (REQ-1)
# ═══════════════════════════════════════════════════════════════════════════════


class TestBudgetSummary:
    """Tests for budget_summary()."""

    def test_budget_summary_returns_string(self, empty_state: dict) -> None:
        """T140: Summary is always a non-empty string."""
        result = budget_summary(empty_state)
        assert isinstance(result, str), f"Expected str, got {type(result)}"
        assert len(result) > 0, "Expected non-empty string"

    def test_budget_summary_contains_budget_info(self, mid_budget_state: dict) -> None:
        """T150: Summary includes spent and remaining amounts."""
        result = budget_summary(mid_budget_state)
        assert isinstance(result, str)
        # The summary should contain some numeric representation of the budget
        # Check that at least one of the key numbers appears in the string
        has_budget_info = any(
            substr in result
            for substr in ("5.0", "5.00", "10.0", "10.00", "50%", "spent", "remaining")
        )
        assert has_budget_info, (
            f"Budget summary should contain budget-related info, got: '{result}'"
        )

    def test_budget_summary_zero_budget(self) -> None:
        """T160: Summary handles zero-budget state without error."""
        state = {
            "budget_dollars": 0.0,
            "spent_dollars": 0.0,
            "iteration": 0,
            "max_iterations": 10,
            "llm_calls": 0,
            "test_runs": 0,
        }
        result = budget_summary(state)
        assert isinstance(result, str)

    def test_budget_summary_huge_budget(self) -> None:
        """T170: Summary handles very large budget values without formatting errors."""
        state = {
            "budget_dollars": 1e12,
            "spent_dollars": 0.0,
            "iteration": 0,
            "max_iterations": 10,
            "llm_calls": 0,
            "test_runs": 0,
        }
        result = budget_summary(state)
        assert isinstance(result, str)
        assert len(result) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Edge Cases (REQ-2)
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Edge case tests for boundary conditions and data anomalies."""

    def test_zero_budget_immediate_trip(self) -> None:
        """T180: Zero budget_dollars causes immediate circuit breaker trip."""
        state = {
            "budget_dollars": 0.0,
            "spent_dollars": 0.0,
            "iteration": 0,
            "max_iterations": 10,
            "llm_calls": 0,
            "test_runs": 0,
        }
        result = check_circuit_breaker(state)
        assert _get_trip_flag(result) is True, (
            f"Zero budget should cause immediate trip, got: {result}"
        )

    def test_huge_budget_no_trip(self) -> None:
        """T190: Very large budget_dollars does not trip with normal activity."""
        state = {
            "budget_dollars": 1e9,
            "spent_dollars": 1.0,
            "iteration": 1,
            "max_iterations": 100,
            "llm_calls": 5,
            "test_runs": 3,
        }
        result = check_circuit_breaker(state)
        assert _get_trip_flag(result) is False, (
            f"Huge budget with low activity should not trip, got: {result}"
        )

    def test_negative_spent_does_not_crash(self) -> None:
        """T200: Negative spent_dollars (data anomaly) does not raise."""
        state = {
            "budget_dollars": 10.0,
            "spent_dollars": -5.0,
            "iteration": 1,
            "max_iterations": 10,
            "llm_calls": 1,
            "test_runs": 1,
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
            budget_summary(state)
        except (KeyError, ValueError, TypeError):
            pass

    def test_empty_dict_state_handling(self) -> None:
        """T210: Completely empty dict handled gracefully (KeyError or defaults)."""
        state: dict = {}
        functions_under_test = [
            lambda: estimate_iteration_cost(state),
            lambda: check_circuit_breaker(state),
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
# Tests: CI Compatibility (REQ-3)
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
        with open(source_file, "r", encoding="utf-8") as f:
            source = f.read()

        network_imports = ["requests", "httpx", "urllib3", "aiohttp"]
        for lib in network_imports:
            assert f"import {lib}" not in source, (
                f"circuit_breaker.py should not import network library '{lib}'"
            )

    def test_all_tests_run_offline(self) -> None:
        """T230: Verify test suite completes without network calls.

        This is a meta-assertion: if this test is running and passing,
        the suite is running without network. We also verify no HTTP
        patterns in the source module.
        """
        import assemblyzero.workflows.testing.circuit_breaker as cb

        source_file = inspect.getfile(cb)
        with open(source_file, "r", encoding="utf-8") as f:
            source = f.read()

        # No HTTP URL patterns in source
        assert "http://" not in source.lower() or "# http" in source.lower(), (
            "Source contains HTTP URLs suggesting network calls"
        )
        assert "https://" not in source.lower() or "# https" in source.lower(), (
            "Source contains HTTPS URLs suggesting network calls"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Coverage Verification (REQ-4)
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
# Tests: Regression Guard (REQ-5)
# ═══════════════════════════════════════════════════════════════════════════════


class TestRegressionGuard:
    """Verify new tests don't break existing suite."""

    def test_existing_unit_suite_unaffected(self) -> None:
        """T250: New test file does not break existing tests (import isolation).

        Verifying that importing this test module has no side effects
        that could affect other test modules.
        """
        import importlib
        import sys

        # Verify our test module can be imported cleanly
        mod = importlib.import_module("tests.unit.test_circuit_breaker")
        assert mod is not None

        # Verify we haven't polluted sys.modules with unexpected entries
        # (no circuit_breaker-specific globals leaked)
        assert "circuit_breaker_global_state" not in dir(mod), (
            "Test module should not define global mutable state"
        )

        # Verify no environment variable mutations
        import os

        # The module should not have set any AZ_* environment variables
        # (test isolation principle)
        assert "AZ_CIRCUIT_BREAKER_TEST" not in os.environ, (
            "Test module should not mutate environment variables"
        )
```

**CRITICAL ADAPTATION INSTRUCTIONS FOR IMPLEMENTING AGENT:**

Before writing the final test file, the implementing agent MUST:

1. **Inspect actual function signatures:**
   ```bash
   python -c "
   import inspect
   import assemblyzero.workflows.testing.circuit_breaker as cb
   for name, obj in inspect.getmembers(cb, inspect.isfunction):
       if not name.startswith('_'):
           print(f'{name}{inspect.signature(obj)}')
   "
   ```

2. **Adapt based on findings:**
   - If `check_circuit_breaker` returns `dict` instead of `tuple`, the `_get_trip_flag`/`_get_trip_reason` helpers handle this
   - If `record_iteration_cost` mutates in-place and returns `None`, the `result if result is not None else state` pattern handles this
   - If function names differ (e.g., `get_budget_summary` vs `budget_summary`), update imports and all references
   - If additional required state keys exist beyond the 6 in fixtures, add them

3. **Adapt import path** if the module path differs from `assemblyzero.workflows.testing.circuit_breaker`

4. **Document all deviations** in the Implementation Report under "Deviations from Spec"

## 7. Pattern References

### 7.1 Existing Workflow Test Pattern

**File:** `tests/test_integration_workflow.py` (lines 1-80)

**Relevance:** Shows the project's established pattern for structuring test files — import conventions, fixture patterns, assertion style. The new test file should match the import and organization conventions used here.

### 7.2 Existing Issue Workflow Test Pattern

**File:** `tests/test_issue_workflow.py` (lines 1-80)

**Relevance:** Another example of test structure in the project. Consistent naming, docstring conventions, and assertion patterns should be followed.

### 7.3 Source Module Pattern

**File:** `assemblyzero/workflows/testing/circuit_breaker.py` (full file)

**Relevance:** The system under test. Must be read in its entirety before implementation to discover actual function signatures, parameter names, return types, and any additional state keys used.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `pytest` | pip (dev dependency) | `tests/unit/test_circuit_breaker.py` |
| `inspect` | stdlib | `tests/unit/test_circuit_breaker.py` (T220, T230, T240) |
| `copy.deepcopy` | stdlib | `tests/unit/test_circuit_breaker.py` (T130) |
| `importlib` | stdlib | `tests/unit/test_circuit_breaker.py` (T220, T250) |
| `assemblyzero.workflows.testing.circuit_breaker` | internal | `tests/unit/test_circuit_breaker.py` |

**New Dependencies:** None. All imports are either stdlib or already in dev dependencies.

## 9. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `estimate_iteration_cost()` | `empty_state` fixture | `float >= 0.0` |
| T020 | `estimate_iteration_cost()` | `mid_budget_state` fixture | `float >= 0.0` reflecting activity |
| T030 | `estimate_iteration_cost()` | Arbitrary valid state | `isinstance(result, (int, float))` |
| T040 | `estimate_iteration_cost()` | Low vs high activity states | `high >= low` |
| T050 | `check_circuit_breaker()` | `empty_state` fixture | `tripped is False` |
| T060 | `check_circuit_breaker()` | `mid_budget_state` fixture | `tripped is False` |
| T070 | `check_circuit_breaker()` | `over_budget_state` fixture | `tripped is True` |
| T080 | `check_circuit_breaker()` | State at `iteration == max_iterations` | `tripped is True` |
| T090 | `check_circuit_breaker()` | Any valid state | Return has bool + str |
| T100 | `record_iteration_cost()` | `empty_state` + `1.50` | `spent_dollars == 1.50` |
| T110 | `record_iteration_cost()` | `empty_state` + 3×`1.0` | `spent_dollars == 3.0` |
| T120 | `record_iteration_cost()` | `empty_state` + `0.0` | `spent_dollars` unchanged |
| T130 | `record_iteration_cost()` | `mid_budget_state` + `0.50` | Non-cost fields unchanged |
| T140 | `budget_summary()` | `empty_state` fixture | Non-empty `str` |
| T150 | `budget_summary()` | `mid_budget_state` fixture | Contains budget numbers |
| T160 | `budget_summary()` | State with `budget_dollars=0` | No exception, returns `str` |
| T170 | `budget_summary()` | State with `budget_dollars=1e12` | No exception, returns `str` |
| T180 | `check_circuit_breaker()` | Zero budget state | `tripped is True` |
| T190 | `check_circuit_breaker()` | Huge budget state | `tripped is False` |
| T200 | All 4 functions | State with `spent_dollars=-5.0` | No unhandled exception |
| T210 | All 4 functions (except record) | `{}` empty dict | No unhandled crash |
| T220 | Module import | N/A | Import succeeds, no network libs |
| T230 | Source inspection | N/A | No HTTP URL patterns |
| T240 | `inspect.getmembers()` | Module object | All public funcs are tested |
| T250 | Module import | N/A | Clean import, no side effects |

## 10. Implementation Notes

### 10.1 Error Handling Convention

Tests use try/except with acceptable exception types (`KeyError`, `ValueError`, `TypeError`) for edge case tests (T200, T210). Unexpected exception types cause `pytest.fail()` with a descriptive message. This follows the principle: "we test that the module fails gracefully, not that it never fails."

### 10.2 Logging Convention

No logging in test code. Tests communicate through assertions and pytest's built-in output.

### 10.3 Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| `empty_state.budget_dollars` | `10.0` | Round number, easy mental arithmetic for assertions |
| `mid_budget_state.spent_dollars` | `5.0` | Exactly 50% — clear halfway point |
| `over_budget_state.spent_dollars` | `12.0` | 120% of budget — clearly over |
| `near_limit_state.spent_dollars` | `9.5` | 95% of budget — boundary testing |
| Huge budget value | `1e9` / `1e12` | Tests formatting edge cases with large numbers |

### 10.4 Adaptation Protocol

The implementation spec provides a complete file with adaptation points marked by comments. The implementing agent should:

1. **First:** Inspect the actual source module (see Section 3.1 command)
2. **Second:** Compare actual signatures against the spec
3. **Third:** Modify the helper functions (`_get_trip_flag`, `_get_trip_reason`) and fixture fields as needed
4. **Fourth:** Run the test suite and fix any signature mismatches
5. **Fifth:** Verify ≥ 95% coverage

### 10.5 Known Risk: Return Type Uncertainty

The LLD assumes `check_circuit_breaker` returns `tuple[bool, str]`. The implementation spec includes `_get_trip_flag()` and `_get_trip_reason()` helper functions that handle three possible return types:
- `tuple(bool, str)` — most likely
- `dict` with `tripped`/`reason` keys — possible
- Plain `bool` — simplest case

This defensive coding ensures the tests work regardless of exact return shape.

### 10.6 pytest.approx Usage

All float comparisons use `pytest.approx()` to avoid floating-point precision issues. This is especially important for:
- T100 (`spent_dollars == 1.50`)
- T110 (`spent_dollars == 3.0`)
- T120 (`spent_dollars` unchanged)

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3) — N/A, no Modify files
- [x] Every data structure has a concrete JSON/YAML example (Section 4)
- [x] Every function has input/output examples with realistic values (Section 5)
- [x] Change instructions are diff-level specific (Section 6) — complete file provided
- [x] Pattern references include file:line and are verified to exist (Section 7)
- [x] All imports are listed and verified (Section 8)
- [x] Test mapping covers all LLD test scenarios (Section 9) — all 25 mapped

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #443 |
| Verdict | DRAFT |
| Date | 2026-02-25 |
| Iterations | 1 |
| Finalized | — |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #443 |
| Verdict | APPROVED |
| Date | 2026-02-25 |
| Iterations | 0 |
| Finalized | 2026-02-25T20:25:08Z |

### Review Feedback Summary

Approved with suggestions:
- **Import Path Verification:** The spec assumes the module is at `assemblyzero.workflows.testing.circuit_breaker`. While the adaptation instructions mention checking this, the implementing agent should be explicitly encouraged to use `find . -name circuit_breaker.py` if the import fails initially.
- **Coverage Tooling:** The spec references running coverage checks. Ensure `pytest-cov` is installed in the environment; if not, the agent should know to install it or skip...


## Required File Paths (from LLD - do not deviate)

The following paths are specified in the LLD. Write ONLY to these paths:


Any files written to other paths will be rejected.

## Repository Structure

The actual directory layout of this repository:

```
tests/
  accessibility/
  benchmark/
  compliance/
  contract/
  e2e/
  fixtures/
    metrics/
    mock_repo/
      src/
    scout/
    verdict_analyzer/
  harness/
  integration/
  security/
  tools/
  unit/
    test_gate/
  visual/
  __init__.py
  conftest.py
  test_assemblyzero_config.py
  test_audit.py
  test_audit_sharding.py
  test_credentials.py
  test_designer.py
  test_gemini_client.py
  test_gemini_credentials_v2.py
  test_integration_workflow.py
  ... and 13 more files
assemblyzero/
  core/
    validation/
  graphs/
  hooks/
  nodes/
  telemetry/
  utils/
  workflow/
  workflows/
    implementation_spec/
      nodes/
    issue/
      nodes/
    orchestrator/
    parallel/
    requirements/
      nodes/
      parsers/
    scout/
    testing/
      completeness/
      knowledge/
      nodes/
      templates/
  __init__.py
  tracing.py
dashboard/
  src/
    client/
      components/
      pages/
  package.json
  tsconfig.client.json
  tsconfig.json
  tsconfig.worker.json
  wrangler.toml
data/
  unleashed/
  handoff-log.md
```

Use these real paths — do NOT invent paths that don't exist.

## Tests That Must Pass

```python
# From C:\Users\mcwiz\Projects\AssemblyZero\tests\unit\test_circuit_breaker.py
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


```

## Previous Attempt Failed

The previous implementation had this error:

```
============================= test session starts =============================
platform win32 -- Python 3.14.0, pytest-9.0.2, pluggy-1.6.0 -- C:\Users\mcwiz\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Scripts\python.exe
cachedir: .pytest_cache
benchmark: 5.2.3 (defaults: timer=time.perf_counter disable_gc=False min_rounds=5 min_time=0.000005 max_time=1.0 calibration_precision=10 warmup=False warmup_iterations=100000)
rootdir: C:\Users\mcwiz\Projects\AssemblyZero
configfile: pyproject.toml
plugins: anyio-4.12.1, langsmith-0.6.9, benchmark-5.2.3, cov-7.0.0
collecting ... collected 25 items

tests/unit/test_circuit_breaker.py::TestEstimateIterationCost::test_estimate_iteration_cost_empty_state PASSED [  4%]
tests/unit/test_circuit_breaker.py::TestEstimateIterationCost::test_estimate_iteration_cost_mid_budget PASSED [  8%]
tests/unit/test_circuit_breaker.py::TestEstimateIterationCost::test_estimate_iteration_cost_returns_numeric PASSED [ 12%]
tests/unit/test_circuit_breaker.py::TestEstimateIterationCost::test_estimate_iteration_cost_scales_with_activity PASSED [ 16%]
tests/unit/test_circuit_breaker.py::TestCheckCircuitBreaker::test_check_circuit_breaker_no_trip_fresh_state PASSED [ 20%]
tests/unit/test_circuit_breaker.py::TestCheckCircuitBreaker::test_check_circuit_breaker_no_trip_within_budget PASSED [ 24%]
tests/unit/test_circuit_breaker.py::TestCheckCircuitBreaker::test_check_circuit_breaker_trips_over_budget PASSED [ 28%]
tests/unit/test_circuit_breaker.py::TestCheckCircuitBreaker::test_check_circuit_breaker_trips_at_exact_boundary PASSED [ 32%]
tests/unit/test_circuit_breaker.py::TestCheckCircuitBreaker::test_check_circuit_breaker_return_structure PASSED [ 36%]
tests/unit/test_circuit_breaker.py::TestRecordIterationCost::test_record_iteration_cost_accumulates PASSED [ 40%]
tests/unit/test_circuit_breaker.py::TestRecordIterationCost::test_record_iteration_cost_multiple_calls PASSED [ 44%]
tests/unit/test_circuit_breaker.py::TestRecordIterationCost::test_record_iteration_cost_zero_content_state PASSED [ 48%]
tests/unit/test_circuit_breaker.py::TestRecordIterationCost::test_record_iteration_cost_preserves_state PASSED [ 52%]
tests/unit/test_circuit_breaker.py::TestBudgetSummary::test_budget_summary_returns_string PASSED [ 56%]
tests/unit/test_circuit_breaker.py::TestBudgetSummary::test_budget_summary_contains_budget_info PASSED [ 60%]
tests/unit/test_circuit_breaker.py::TestBudgetSummary::test_budget_summary_zero_budget_zero_used PASSED [ 64%]
tests/unit/test_circuit_breaker.py::TestBudgetSummary::test_budget_summary_huge_budget PASSED [ 68%]
tests/unit/test_circuit_breaker.py::TestEdgeCases::test_zero_budget_means_no_enforcement PASSED [ 72%]
tests/unit/test_circuit_breaker.py::TestEdgeCases::test_huge_budget_no_trip PASSED [ 76%]
tests/unit/test_circuit_breaker.py::TestEdgeCases::test_negative_tokens_used_does_not_crash PASSED [ 80%]
tests/unit/test_circuit_breaker.py::TestEdgeCases::test_empty_dict_state_handling PASSED [ 84%]
tests/unit/test_circuit_breaker.py::TestCICompatibility::test_no_external_imports_required PASSED [ 88%]
tests/unit/test_circuit_breaker.py::TestCICompatibility::test_all_tests_run_offline PASSED [ 92%]
tests/unit/test_circuit_breaker.py::TestCoverageVerification::test_all_public_functions_exercised PASSED [ 96%]
tests/unit/test_circuit_breaker.py::TestRegressionGuard::test_existing_unit_suite_unaffected PASSED [100%]
ERROR: Coverage failure: total of 9 is less than fail-under=95


============================== warnings summary ===============================
..\..\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\langchain_core\_api\deprecation.py:25
  C:\Users\mcwiz\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\langchain_core\_api\deprecation.py:25: UserWarning: Core Pydantic V1 functionality isn't compatible with Python 3.14 or greater.
    from pydantic.v1.fields import FieldInfo as FieldInfoV1

..\..\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\google\genai\types.py:43
  C:\Users\mcwiz\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\google\genai\types.py:43: DeprecationWarning: '_UnionGenericAlias' is deprecated and slated for removal in Python 3.17
    VersionedUnionType = Union[builtin_types.UnionType, _UnionGenericAlias]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=============================== tests coverage ================================
_______________ coverage: platform win32, python 3.14.0-final-0 _______________

Name                                                                        Stmts   Miss  Cover   Missing
---------------------------------------------------------------------------------------------------------
assemblyzero\__init__.py                                                        1      0   100%
assemblyzero\core\__init__.py                                                   5      0   100%
assemblyzero\core\audit.py                                                    102     82    20%   80-106, 117-136, 144-145, 157-165, 182-208, 222-242, 253-272, 281-282, 290, 328
assemblyzero\core\claude_client.py                                             36     36     0%   11-123
assemblyzero\core\config.py                                                    16      0   100%
assemblyzero\core\gemini_client.py                                            281    226    20%   114-116, 120-122, 173-192, 208-251, 283-299, 303-313, 335-392, 421-639, 663-704, 708-726, 730-732, 744-758, 764-767, 771-788, 792, 796-804
assemblyzero\core\llm_provider.py                                             322    246    24%   76-96, 108-132, 145, 151, 170, 202-214, 218, 222, 233-257, 278-403, 440-449, 453, 457, 465-475, 489-500, 518-613, 636-638, 642, 646, 665-676, 714-721, 725, 729, 733-737, 755-802, 834-841, 845, 849, 867-885, 909-919, 941-957
assemblyzero\core\state.py                                                      6      0   100%
assemblyzero\core\tdd_path_tracking.py                                         61     61     0%   9-190
assemblyzero\core\validation\__init__.py                                        2      0   100%
assemblyzero\core\validation\test_plan_validator.py                           168    147    12%   114-164, 180-233, 250-255, 280-306, 320-326, 349-377, 392-408, 423-444, 462-483, 507-551
assemblyzero\graphs\__init__.py                                                 0      0   100%
assemblyzero\hooks\__init__.py                                                  5      0   100%
assemblyzero\hooks\cascade_action.py                                           34     28    18%   41-78, 95-118
assemblyzero\hooks\cascade_detector.py                                         72     61    15%   57-110, 135-164, 180-190, 195
assemblyzero\hooks\cascade_patterns.py                                         70     52    26%   49, 209-260, 276-292
assemblyzero\hooks\file_write_validator.py                                     40     31    22%   37-71, 91-106, 111-116, 121, 126
assemblyzero\hooks\types.py                                                    16      0   100%
assemblyzero\nodes\__init__.py                                                  5      5     0%   3-11
assemblyzero\nodes\check_type_renames.py                                      125    125     0%   9-314
assemblyzero\nodes\designer.py                                                134    134     0%   15-501
assemblyzero\nodes\lld_reviewer.py                                             90     90     0%   7-335
assemblyzero\nodes\smoke_test_node.py                                          58     58     0%   9-204
assemblyzero\telemetry\__init__.py                                              3      3     0%   19-27
assemblyzero\telemetry\__main__.py                                              2      2     0%   3-5
assemblyzero\telemetry\actor.py                                                30     30     0%   7-62
assemblyzero\telemetry\cascade_events.py                                       71     71     0%   9-163
assemblyzero\telemetry\emitter.py                                             119    119     0%   10-243
assemblyzero\telemetry\sync.py                                                  9      9     0%   7-22
assemblyzero\tracing.py                                                        10     10     0%   13-39
assemblyzero\utils\__init__.py                                                  4      0   100%
assemblyzero\utils\codebase_reader.py                                         153    133    13%   21-22, 62, 79-103, 131-203, 227-260, 277-372
assemblyzero\utils\file_type.py                                                12      4    67%   42-43, 51, 59
assemblyzero\utils\github_metrics_client.py                                    83     83     0%   9-243
assemblyzero\utils\lld_path_enforcer.py                                        79     68    14%   37-67, 82-123, 138-143, 157-188, 202-209, 214-215, 220-221
assemblyzero\utils\lld_verification.py                                         98     85    13%   55-58, 75-76, 93-146, 164-178, 196-247, 269-284, 307-339, 351-361
assemblyzero\utils\metrics_aggregator.py                                      161    161     0%   9-447
assemblyzero\utils\metrics_config.py                                           78     78     0%   6-207
assemblyzero\utils\metrics_models.py                                           59     59     0%   6-97
assemblyzero\utils\pattern_scanner.py                                         185    163    12%   128-154, 166-216, 228-253, 265-281, 293-322, 334-360, 381-404, 421-493
assemblyzero\workflow\__init__.py                                               2      2     0%   6-8
assemblyzero\workflow\checkpoint.py                                            27     27     0%   7-77
assemblyzero\workflows\__init__.py                                              0      0   100%
assemblyzero\workflows\implementation_spec\__init__.py                          3      3     0%   24-36
assemblyzero\workflows\implementation_spec\graph.py                            85     85     0%   27-324
assemblyzero\workflows\implementation_spec\nodes\__init__.py                    8      8     0%   15-46
assemblyzero\workflows\implementation_spec\nodes\analyze_codebase.py          382    382     0%   18-971
assemblyzero\workflows\implementation_spec\nodes\finalize_spec.py              80     80     0%   22-311
assemblyzero\workflows\implementation_spec\nodes\generate_spec.py             206    206     0%   20-764
assemblyzero\workflows\implementation_spec\nodes\human_gate.py                 62     62     0%   21-204
assemblyzero\workflows\implementation_spec\nodes\load_lld.py                   92     92     0%   16-299
assemblyzero\workflows\implementation_spec\nodes\review_spec.py               132    132     0%   22-521
assemblyzero\workflows\implementation_spec\nodes\validate_completeness.py     189    189     0%   21-654
assemblyzero\workflows\implementation_spec\state.py                            43     43     0%   12-150
assemblyzero\workflows\issue\__init__.py                                        3      3     0%   10-13
assemblyzero\workflows\issue\audit.py                                         186    186     0%   12-570
assemblyzero\workflows\issue\graph.py                                          59     59     0%   11-249
assemblyzero\workflows\issue\nodes\__init__.py                                  8      8     0%   15-23
assemblyzero\workflows\issue\nodes\draft.py                                    94     94     0%   10-294
assemblyzero\workflows\issue\nodes\file_issue.py                              185    185     0%   9-472
assemblyzero\workflows\issue\nodes\human_edit_draft.py                        131    131     0%   9-252
assemblyzero\workflows\issue\nodes\human_edit_verdict.py                      140    140     0%   10-278
assemblyzero\workflows\issue\nodes\load_brief.py                               49     49     0%   9-184
assemblyzero\workflows\issue\nodes\review.py                                   77     77     0%   9-193
assemblyzero\workflows\issue\nodes\sandbox.py                                  30     30     0%   11-104
assemblyzero\workflows\issue\state.py                                          18     18     0%   9-40
assemblyzero\workflows\orchestrator\__init__.py                                 4      4     0%   6-26
assemblyzero\workflows\orchestrator\artifacts.py                               58     58     0%   6-125
assemblyzero\workflows\orchestrator\config.py                                  57     57     0%   6-143
assemblyzero\workflows\orchestrator\graph.py                                  142    142     0%   6-322
assemblyzero\workflows\orchestrator\resume.py                                  68     68     0%   6-154
assemblyzero\workflows\orchestrator\stages.py                                 143    143     0%   11-432
assemblyzero\workflows\orchestrator\state.py                                   66     66     0%   6-150
assemblyzero\workflows\parallel\__init__.py                                     5      5     0%   3-8
assemblyzero\workflows\parallel\coordinator.py                                 85     85     0%   3-184
assemblyzero\workflows\parallel\credential_coordinator.py                      59     59     0%   3-127
assemblyzero\workflows\parallel\input_sanitizer.py                             13     13     0%   3-39
assemblyzero\workflows\parallel\output_prefixer.py                             19     19     0%   3-45
assemblyzero\workflows\requirements\__init__.py                                 4      0   100%
assemblyzero\workflows\requirements\audit.py                                  229    193    16%   98-171, 195-200, 220-223, 248-256, 275-286, 306-309, 336-344, 365-373, 393-411, 427-456, 492-506, 520-529, 550-580, 593-606, 631-636, 657-664, 700-703, 728-768, 800-855
assemblyzero\workflows\requirements\config.py                                  68     22    68%   53, 57, 64-71, 110, 117, 127-149, 157
assemblyzero\workflows\requirements\git_operations.py                          30     23    23%   27-30, 55-101
assemblyzero\workflows\requirements\graph.py                                  119     96    19%   106-111, 136-147, 171-187, 209-228, 247-254, 277-314, 333-340, 356, 384-494
assemblyzero\workflows\requirements\nodes\__init__.py                           9      0   100%
assemblyzero\workflows\requirements\nodes\analyze_codebase.py                 229    209     9%   72, 103-236, 255-301, 324-391, 404-428, 444-466, 478-501, 517-538, 550-567
assemblyzero\workflows\requirements\nodes\finalize.py                         163    146    10%   39-40, 57-75, 87-133, 149-174, 199-221, 236-332, 343-369, 384-402
assemblyzero\workflows\requirements\nodes\generate_draft.py                   156    146     6%   46-141, 168-292, 307-348, 370-390
assemblyzero\workflows\requirements\nodes\human_gate.py                        88     81     8%   26-40, 52-67, 84-138, 159-233
assemblyzero\workflows\requirements\nodes\load_input.py                       114     96    16%   61-66, 78-111, 129-221, 240-272, 291-307, 320-321
assemblyzero\workflows\requirements\nodes\review.py                           117    104    11%   44-141, 168-184, 196-214, 237-250, 262-276, 289-300, 316-332
assemblyzero\workflows\requirements\nodes\validate_mechanical.py              429    384    10%   137-160, 182-217, 234-265, 281-300, 319-331, 348-367, 389-395, 411-417, 445-469, 482, 507-515, 528-565, 582-596, 610-697, 713-748, 767-864, 880-900, 915-935, 951-974, 986-1015, 1027-1048, 1060-1069, 1087-1124, 1158-1345
assemblyzero\workflows\requirements\nodes\validate_test_plan.py                58     53     9%   35-80, 99-142
assemblyzero\workflows\requirements\parsers\__init__.py                         3      3     0%   6-14
assemblyzero\workflows\requirements\parsers\draft_updater.py                  130    130     0%   8-315
assemblyzero\workflows\requirements\parsers\verdict_parser.py                  94     94     0%   8-295
assemblyzero\workflows\requirements\state.py                                   44     24    45%   282-358, 370-391
assemblyzero\workflows\scout\__init__.py                                        3      3     0%   7-18
assemblyzero\workflows\scout\budget.py                                         21     21     0%   7-76
assemblyzero\workflows\scout\graph.py                                           5      5     0%   6-62
assemblyzero\workflows\scout\instrumentation.py                                40     40     0%   6-126
assemblyzero\workflows\scout\nodes.py                                         151    151     0%   6-345
assemblyzero\workflows\scout\prompts.py                                        11     11     0%   7-76
assemblyzero\workflows\scout\security.py                                       44     44     0%   6-132
assemblyzero\workflows\scout\templates.py                                      33     33     0%   6-124
assemblyzero\workflows\testing\__init__.py                                      3      0   100%
assemblyzero\workflows\testing\audit.py                                        88     65    26%   33-35, 71-79, 92-96, 110-121, 141-144, 162-165, 185-229, 251-272, 284-321
assemblyzero\workflows\testing\circuit_breaker.py                              46      1    98%   137
assemblyzero\workflows\testing\completeness\__init__.py                         3      0   100%
assemblyzero\workflows\testing\completeness\ast_analyzer.py                   280    243    13%   83-106, 118-121, 137-148, 165-176, 199-268, 286-333, 351-390, 414-472, 490-510, 530-605, 634-695, 718-725
assemblyzero\workflows\testing\completeness\report_generator.py               129     99    23%   86-128, 159-183, 204-209, 221-228, 240-259, 277-290, 320-396, 413-429
assemblyzero\workflows\testing\exit_code_router.py                             27     17    37%   44-71, 83-92
assemblyzero\workflows\testing\graph.py                                       121    105    13%   85-88, 102-118, 134-142, 164-180, 196-209, 225-228, 244-270, 284-298, 312-320, 332-461
assemblyzero\workflows\testing\knowledge\__init__.py                            2      0   100%
assemblyzero\workflows\testing\knowledge\patterns.py                           60     49    18%   21-32, 37, 97-116, 128-129, 141-149, 161-170, 184-193
assemblyzero\workflows\testing\nodes\__init__.py                               11      0   100%
assemblyzero\workflows\testing\nodes\completeness_gate.py                     115    102    11%   80-257, 281-303, 320-352
assemblyzero\workflows\testing\nodes\document.py                              140    126    10%   42-62, 74-85, 97-104, 116-117, 129-142, 154-167, 180-215, 227-361
assemblyzero\workflows\testing\nodes\e2e_validation.py                        109     92    16%   42-43, 62-106, 127, 148, 160-331, 341-359
assemblyzero\workflows\testing\nodes\finalize.py                              110     98    11%   42-74, 87-123, 135-241, 257-261
assemblyzero\workflows\testing\nodes\implement_code.py                        626    568     9%   74-78, 81-85, 88-94, 97-101, 110-113, 118-133, 157-186, 194-214, 222-241, 249-253, 269-312, 318-339, 344-368, 388-401, 417-424, 447-508, 525-582, 604-644, 653-661, 675-676, 702-840, 859-862, 870-879, 899-967, 988-1007, 1033-1128, 1159-1178, 1190-1405, 1416-1433, 1452-1544, 1554-1623, 1637-1660, 1677
assemblyzero\workflows\testing\nodes\load_lld.py                              315    289     8%   49-70, 85-107, 120, 146-173, 192-232, 249-297, 314-416, 421-422, 427-439, 444-455, 460-476, 493-505, 521-585, 605-675, 698-827, 845-916
assemblyzero\workflows\testing\nodes\review_test_plan.py                      168    151    10%   55-69, 81-89, 106-125, 143-149, 154, 215-263, 275-421, 443-483, 496-511, 519-566
assemblyzero\workflows\testing\nodes\scaffold_tests.py                        317    298     6%   71-129, 147-203, 218-281, 297-327, 346-390, 411-511, 529-614, 619-637, 656-661, 673-732, 741-774
assemblyzero\workflows\testing\nodes\validate_commit_message.py                12      9    25%   28-47
assemblyzero\workflows\testing\nodes\validate_tests_mechanical.py             114    102    11%   48-61, 87-156, 175-205, 226-286, 311-324
assemblyzero\workflows\testing\nodes\verify_phases.py                         204    191     6%   57-93, 115-253, 275-616, 630-655, 665-714
assemblyzero\workflows\testing\path_validator.py                               70     70     0%   7-181
assemblyzero\workflows\testing\state.py                                        13      0   100%
assemblyzero\workflows\testing\templates\__init__.py                            5      0   100%
assemblyzero\workflows\testing\templates\cp_docs.py                            73     65    11%   23-33, 45-60, 72-83, 105-189, 211-296
assemblyzero\workflows\testing\templates\lessons.py                           115    107     7%   31-161, 174-199, 215-231, 243-257, 279-304
assemblyzero\workflows\testing\templates\runbook.py                            94     86     9%   22-37, 49-59, 71-81, 93-103, 125-259
assemblyzero\workflows\testing\templates\wiki_page.py                          74     67     9%   22-32, 44-48, 60-72, 92-152, 165-207
---------------------------------------------------------------------------------------------------------
TOTAL                                                                       11651  10582     9%
FAIL Required test coverage of 95% not reached. Total coverage: 9.18%
======================= 25 passed, 2 warnings in 2.02s ========================


```

Fix the issue in your implementation.

## Output Format

Output ONLY the file contents. No explanations, no markdown headers, just the Python code.

```python
# Your Python code here
```

IMPORTANT:
- Output the COMPLETE file contents
- Do NOT output a summary or description
- Do NOT say "I've implemented..."
- Just output the Python code in a single fenced code block
