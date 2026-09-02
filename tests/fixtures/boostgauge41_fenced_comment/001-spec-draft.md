# Implementation Spec: #41 - Feature: Telltale peak-hold needle logic (pure, no GUI)

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #41 |
| LLD | `docs/lld/active/41-telltale.md` |
| Generated | 2026-09-01 |
| Status | DRAFT |

## 1. Overview

**Objective:** Add the peak-hold "telltale" logic as a pure class (`Telltale`) that tracks the maximum value reached over a sliding time window with optional linear decay, fully decoupled from GUI and wall-clock time.

**Success Criteria:** Provide a fully deterministic, pure Python class implementing sliding-window max with linear decay that passes 100% of the defined test scenarios (TDD coverage) without wall-clock or GUI dependencies.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/telltale.py` | Add | Pure logic class `Telltale` implementing peak-hold semantics. |
| 2 | `tests/unit/test_telltale.py` | Add | Unit tests asserting the acceptance criteria for `Telltale`. |

**Implementation Order Rationale:** The pure logic class `telltale.py` must be implemented first, as it provides the target component required by the unit tests in `test_telltale.py`.

## 3. Current State (for Modify/Delete files)

*N/A — All files in this Implementation Spec are new additions (`Add`).*

## 4. Data Structures

### 4.1 Sample

**Definition:**

```python
from typing import NamedTuple

class Sample(NamedTuple):
    timestamp: float
    value: float
```

**Concrete Example:**

```json
{
    "timestamp": 10.5,
    "value": 42.0
}
```

## 5. Function Specifications

### 5.1 `Telltale.__init__()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def __init__(self, window: Optional[float], decay_rate: Optional[float] = None) -> None:
    """Construct a telltale with a window duration and optional decay rate."""
    ...
```

**Input Example:**

```python
window = 10.0
decay_rate = 15.0
```

**Output Example:**

```python
None # Modifies internal state
```

**Edge Cases:**
- `window <= 0` (e.g., `0` or `-5.0`) -> raises `ValueError`
- `decay_rate <= 0` (e.g., `0` or `-1.0`) -> raises `ValueError`

### 5.2 `Telltale.update()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def update(self, timestamp: float, value: float) -> None:
    """Feed one sample to the telltale history."""
    ...
```

**Input Example:**

```python
timestamp = 3.0
value = 42.5
```

**Output Example:**

```python
None # Modifies internal state
```

**Edge Cases:**
- `timestamp < self._max_fed_timestamp` -> raises `ValueError("timestamps must not decrease")`
- Equal timestamps -> both accepted and stored, reference time does not change

### 5.3 `Telltale.current_peak()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def current_peak(self) -> Optional[float]:
    """Return the maximum contribution among held samples."""
    ...
```

**Input Example:**

```python
# Assuming instance history: Sample(0.0, 100.0) -> departed at 10.0 (reference_time=12.0)
# window = 10.0, decay_rate = 15.0
```

**Output Example:**

```python
70.0 # Evaluates: 100.0 - 15.0 * (12.0 - 10.0)
```

**Edge Cases:**
- Empty history (no samples fed or just reset) -> returns `None`
- `decay_rate` is `None` -> aged-out samples are excluded entirely from calculations

### 5.4 `Telltale.reset()`

**File:** `src/boostgauge/telltale.py`

**Signature:**

```python
def reset(self) -> None:
    """Discard history, keeping configuration intact."""
    ...
```

**Input Example:**

```python
# Called on a Telltale instance with active history
```

**Output Example:**

```python
None # History cleared, config intact
```

**Edge Cases:**
- Reset on an already empty history -> Safe no-op

## 6. Change Instructions

### 6.1 `src/boostgauge/telltale.py` (Add)

**Complete file contents:**

```python
"""Peak-hold telltale logic.

Issue #41: Feature: Telltale peak-hold needle logic (pure, no GUI)
"""

from __future__ import annotations
from typing import Optional, NamedTuple
from collections import deque
import numbers

class Sample(NamedTuple):
    timestamp: float
    value: float

class Telltale:
    """Tracks the maximum value reached over a sliding time window with optional decay."""

    def __init__(self, window: Optional[float], decay_rate: Optional[float] = None) -> None:
        if window is not None and (not isinstance(window, numbers.Real) or window <= 0):
            raise ValueError("window must be a number > 0")
        if decay_rate is not None and (not isinstance(decay_rate, numbers.Real) or decay_rate <= 0):
            raise ValueError("decay_rate must be a number > 0")
        
        self.window = window
        self.decay_rate = decay_rate
        self._max_fed_timestamp: Optional[float] = None
        
        self._active_window: deque[Sample] = deque()
        self._departed_tracks: list[Sample] = []

    def update(self, timestamp: float, value: float) -> None:
        if self._max_fed_timestamp is not None and timestamp < self._max_fed_timestamp:
            raise ValueError("timestamps must not decrease")
        
        self._max_fed_timestamp = timestamp
        self._active_window.append(Sample(timestamp, value))
        
        if self.window is not None:
            # Prune aged-out samples strictly older than window
            while self._active_window and (timestamp - self._active_window[0].timestamp) > self.window:
                departed = self._active_window.popleft()
                if self.decay_rate is not None:
                    departure_time = departed.timestamp + self.window
                    self._departed_tracks.append(Sample(departure_time, departed.value))

    def current_peak(self) -> Optional[float]:
        if not self._active_window and not self._departed_tracks:
            return None
            
        has_active = len(self._active_window) > 0
        active_max = max((s.value for s in self._active_window)) if has_active else float('-inf')
        
        if self.decay_rate is None:
            return active_max if has_active else None
            
        if not self._departed_tracks:
            return active_max

        decayed_max = float('-inf')
        for dt, val in self._departed_tracks:
            age = self._max_fed_timestamp - dt
            decayed_val = val - (self.decay_rate * age)
            if decayed_val > decayed_max:
                decayed_max = decayed_val
                
        # Return global maximum
        return max(active_max, decayed_max) if has_active else decayed_max

    def reset(self) -> None:
        self._max_fed_timestamp = None
        self._active_window.clear()
        self._departed_tracks.clear()
```

### 6.2 `tests/unit/test_telltale.py` (Add)

**Complete file contents:**

Provide the standard `pytest` imports and the exact tests specified in section `10.1`.

```python
"""Unit tests for pure telltale peak-hold logic."""

import pytest
from boostgauge.telltale import Telltale

# Test functions defined in section 10.1 follow here.
```

## 7. Pattern References

*N/A - This is a self-contained pure math component with no direct precedents in the current GUI codebase.*

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from __future__ import annotations` | stdlib | `telltale.py`, `test_telltale.py` |
| `from typing import Optional, NamedTuple` | stdlib | `telltale.py` |
| `from collections import deque` | stdlib | `telltale.py` |
| `import numbers` | stdlib | `telltale.py` |
| `from boostgauge.telltale import Telltale` | internal | `test_telltale.py` |
| `import pytest` | pytest | `test_telltale.py` |

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| 010 | `Telltale.__init__()` | `Telltale(None)` | Object instance without exception |
| 020 | `update()` | `update(3.0, 42.5)` | 42.5 |
| 030 | `reset()` | `update(0.0, 100.0)`, `reset()`, `update(10.5, 7.0)` | 7.0 |
| 040 | `current_peak()` | Multiple `current_peak()` reads | Pure reads modify no state (always 70.0) |
| 050 | `current_peak()` | Fresh `Telltale(10.0)` | `None` |
| 060 | `update()` | `update(0.0, 100.0)`, `update(10.0, 0.0)` | 100.0 (closed boundary) |
| 070 | `update()` | `update(0.0, 100.0)`, `update(1000000.0, 5.0)` | 100.0 |
| 080 | `current_peak()` | Aged out, unset decay | 40.0 (drops instantly) |
| 090 | `current_peak()` | Aged out, set decay | 70.0 (100.0 - 15.0 * 2.0) |
| 100 | `update()` | `update(5.0, 1.0)`, `update(4.9, 1.0)` | Raises `ValueError` |
| 110 | `Telltale.__init__()` | `Telltale(0)` | Raises `ValueError` |
| 120 | `Telltale.__init__()` | `Telltale(10.0, 0)` | Raises `ValueError` |
| 130 | `update()` | Equal timestamps | 3.0 (accepted seamlessly) |
| 140 | `reset()` | `update()`, `reset()` | `None` |
| 150 | `update()` | Rising sequence `(0, 10)`, `(1, 20)`, `(2, 30)` | 30.0 |
| 160 | `current_peak()` | In-window | 100.0 (has not departed, no decay) |
| 170 | `update()` | Rejected update `(4.9, 9.0)` | 1.0 (state survives rejection) |
| 180 | `reset()` | `update(100.0, 1.0)`, `reset()`, `update(10.0, 7.0)`| 7.0 |
| 190 | `current_peak()` | Negative values `(-5.0, -20.0)` | -20.0 |
| 200 | `current_peak()` | Bounded track drop | 40.0 (Decay bounded by window max) |
| 210 | `current_peak()` | New high | 80.0 (New high beats the track) |
| 220 | `current_peak()` | `(5.0, 90.0)` track vs `(0.0, 100.0)` | 75.0 (90.0 - 15 * (16-15) = 75) |
| 230 | `current_peak()` | All-time | 100.0 (ignores decay) |
| 240 | `update()` | Equal timestamps | 3.0 |

### 10.1 Per-criterion test functions

```python
import pytest
from boostgauge.telltale import Telltale

def test_010_v1_window_none_allows_creation():
    # V1 - Window None allows creation (REQ-1) -- expected: No exception
    t = Telltale(None)
    assert t.window is None

def test_020_a1_update_sets_reference_time():
    # A1 - Update sets reference time and adds sample (REQ-2) -- expected: 42.5
    t = Telltale(10.0)
    t.update(3.0, 42.5)
    assert t.current_peak() == 42.5

def test_030_a6_reset_discards_decay_tracks():
    # A6 - Reset discards decay tracks (REQ-3) -- expected: 7.0
    t = Telltale(10.0, 15.0)
    t.update(0.0, 100.0)
    t.reset()
    t.update(10.5, 7.0)
    assert t.current_peak() == 7.0

def test_040_d5_current_peak_modifies_no_state():
    # D5 - current_peak modifies no state (REQ-4) -- expected: 70.0, 70.0, 70.0
    t = Telltale(10.0, 15.0)
    t.update(0.0, 100.0)
    t.update(9.0, 40.0)
    t.update(12.0, 0.0)
    assert t.current_peak() == 70.0
    assert t.current_peak() == 70.0
    assert t.current_peak() == 70.0

def test_050_n1_fresh_construction_reads_none():
    # N1 - Fresh construction reads None (REQ-5) -- expected: None
    t = Telltale(10.0)
    assert t.current_peak() is None

def test_060_a4_closed_boundary_in_window_semantics():
    # A4 - Closed boundary in-window semantics (REQ-6) -- expected: 100.0
    t = Telltale(10.0)
    t.update(0.0, 100.0)
    t.update(10.0, 0.0)
    assert t.current_peak() == 100.0

def test_070_t1_all_time_window_never_ages_out():
    # T1 - All-time window never ages out (REQ-7) -- expected: 100.0
    t = Telltale(None)
    t.update(0.0, 100.0)
    t.update(1000000.0, 5.0)
    assert t.current_peak() == 100.0

def test_080_h1_unset_decay_drops_aged_out_sample():
    # H1 - Unset decay drops aged-out sample entirely (REQ-8) -- expected: 40.0
    t = Telltale(10.0)
    t.update(0.0, 100.0)
    t.update(9.0, 40.0)
    t.update(10.5, 0.0)
    assert t.current_peak() == 40.0

def test_090_d1_set_decay_reduces_aged_out_contribution():
    # D1 - Set decay reduces aged-out contribution (REQ-9) -- expected: 70.0
    t = Telltale(10.0, 15.0)
    t.update(0.0, 100.0)
    t.update(9.0, 40.0)
    t.update(12.0, 0.0)
    assert t.current_peak() == 70.0

def test_100_v3_decreasing_timestamp_raises_valueerror():
    # V3 - Decreasing timestamp raises ValueError (REQ-10) -- expected: ValueError
    t = Telltale(10.0)
    t.update(5.0, 1.0)
    with pytest.raises(ValueError):
        t.update(4.9, 1.0)

def test_110_v1_invalid_window_raises_valueerror():
    # V1 - Invalid window raises ValueError (REQ-11) -- expected: ValueError
    with pytest.raises(ValueError):
        Telltale(0)

def test_120_v2_invalid_decay_rate_raises_valueerror():
    # V2 - Invalid decay_rate raises ValueError (REQ-12) -- expected: ValueError
    with pytest.raises(ValueError):
        Telltale(10.0, 0)

def test_130_a5_equal_timestamps_are_accepted():
    # A5 - Equal timestamps are accepted (REQ-13) -- expected: 3.0
    t = Telltale(10.0)
    t.update(5.0, 1.0)
    t.update(5.0, 3.0)
    assert t.current_peak() == 3.0

def test_140_n2_reset_discards_history_and_reads_none():
    # N2 - Reset discards history and reads None (REQ-5) -- expected: None
    t = Telltale(10.0)
    t.update(0.0, 100.0)
    t.reset()
    assert t.current_peak() is None

def test_150_a2_rising_series():
    # A2 - Rising series (REQ-6) -- expected: 30.0
    t = Telltale(10.0)
    t.update(0.0, 10.0)
    t.update(1.0, 20.0)
    t.update(2.0, 30.0)
    assert t.current_peak() == 30.0

def test_160_a3_in_window_values_never_decay():
    # A3 - In-window values never decay (REQ-9) -- expected: 100.0
    t = Telltale(10.0, 15.0)
    t.update(0.0, 100.0)
    t.update(5.0, 0.0)
    assert t.current_peak() == 100.0

def test_170_a7_history_unchanged_after_rejected_update():
    # A7 - History unchanged after rejected update (REQ-10) -- expected: 1.0
    t = Telltale(10.0)
    t.update(5.0, 1.0)
    with pytest.raises(ValueError):
        t.update(4.9, 9.0)
    assert t.current_peak() == 1.0

def test_180_a8_monotonic_contract_restarts_at_reset():
    # A8 - Monotonic contract restarts at reset (REQ-10) -- expected: 7.0
    t = Telltale(10.0)
    t.update(100.0, 1.0)
    t.reset()
    t.update(10.0, 7.0)
    assert t.current_peak() == 7.0

def test_190_h2_exclusion_is_not_a_zero():
    # H2 - Exclusion is not a zero (REQ-8) -- expected: -20.0
    t = Telltale(10.0)
    t.update(0.0, -5.0)
    t.update(11.0, -20.0)
    assert t.current_peak() == -20.0

def test_200_d2_decay_floor_is_window_max():
    # D2 - Decay floor is window max (REQ-9) -- expected: 40.0
    t = Telltale(10.0, 15.0)
    t.update(0.0, 100.0)
    t.update(9.0, 40.0)
    t.update(15.0, 0.0)
    assert t.current_peak() == 40.0

def test_210_d3_new_high_beats_the_track():
    # D3 - New high beats the track (REQ-9) -- expected: 80.0
    t = Telltale(10.0, 15.0)
    t.update(0.0, 100.0)
    t.update(9.0, 40.0)
    t.update(12.5, 80.0)
    assert t.current_peak() == 80.0

def test_220_d4_every_departed_high_keeps_its_own_track():
    # D4 - Every departed high keeps its own track (REQ-9) -- expected: 75.0
    t = Telltale(10.0, 15.0)
    t.update(0.0, 100.0)
    t.update(5.0, 90.0)
    t.update(16.0, 0.0)
    assert t.current_peak() == 75.0

def test_230_t2_all_time_ignores_decay():
    # T2 - All-time ignores decay (REQ-7) -- expected: 100.0
    t = Telltale(None, 15.0)
    t.update(0.0, 100.0)
    t.update(1000000.0, 5.0)
    assert t.current_peak() == 100.0

def test_240_v4_equal_timestamps_raise_nothing():
    # V4 - Equal timestamps raise nothing (REQ-13) -- expected: 3.0
    t = Telltale(10.0)
    t.update(5.0, 1.0)
    t.update(5.0, 3.0)
    assert t.current_peak() == 3.0
```

## 11. Implementation Notes

- **Memory Bounds**: Unbounded history growth is protected by pruning aged-out items from `_active_window`. 
- **Negative Support**: Use `float('-inf')` instead of `0.0` for maximum calculations, to support proper tracking when gauge handles exclusively negative values (#125).

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3)
- [x] Every data structure has a concrete JSON/YAML example (Section 4)
- [x] Every **non-test** function has input/output examples with realistic values (Section 5)
- [x] Every LLD pass criterion has a test function (Section 10.1) — these are exempt from the rule above
- [x] Change instructions are diff-level specific (Section 6)
- [x] Pattern references include file:line and are verified to exist (Section 7)
- [x] All imports are listed and verified (Section 8)
- [x] Test mapping covers all LLD test scenarios (Section 10)

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #41 |
| Verdict | APPROVED |
| Date | 2026-09-01 |
| Iterations | 1 |
| Finalized | 2026-09-01T19:42:15-05:00 |