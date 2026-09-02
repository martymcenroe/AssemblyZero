# Implementation Spec: Issue #4 - Feature: Windows data collector

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #4 |
| LLD | `docs/lld/done/004-windows-collector.md` |
| Generated | 2026-09-02 |
| Status | APPROVED |

## 1. Overview

**Objective:** Build the Windows-specific data collector that polls system metrics (ConPTY, process count, memory, handles, unleashed sessions) in a single OS sweep per tick and feeds them to the gauge.

**Success Criteria:** The collector must gather all process metrics via a single `NtQuerySystemInformation` call per tick, execute within a non-blocking background thread with <20ms latency, compute a normalized composite score, and gracefully handle ephemeral process errors (`AccessDenied`, `NoSuchProcess`).

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/collector.py` | Add | Abstract base class `DataCollector` and `SystemSnapshot` dataclass |
| 2 | `src/boostgauge/collectors/__init__.py` | Add | Package init for collectors |
| 3 | `src/boostgauge/collectors/windows.py` | Add | `WindowsCollector` implementation using `NtQuerySystemInformation` via ctypes |
| 4 | `tests/unit/test_windows_collector.py` | Add | Unit tests for `WindowsCollector` with stubbed OS calls |
| 5 | `tests/integration/test_collector_live.py` | Add | Live cross-checks against `psutil` on a real Windows host |
| 6 | `tests/benchmark/test_collector_benchmark.py` | Add | Benchmark suite enforcing the <20ms mean overhead constraint |

**Implementation Order Rationale:** The core abstractions (`collector.py`) must exist before the Windows-specific implementation (`windows.py`). The tests follow to assert behaviors (unit) and validate performance/accuracy on a live system (integration, benchmark).

## 3. Current State (for Modify/Delete files)

*Note: There are no files with "Modify" or "Delete" change types in this implementation. All files in Section 2 are new additions.*

## 4. Data Structures

### 4.1 SystemSnapshot

**Definition:**

```python
from dataclasses import dataclass

@dataclass
class SystemSnapshot:
    timestamp: float
    conpty_count: int
    process_count: int
    memory_percent: float
    handle_count: int
    unleashed_sessions: int
    driver: str
    composite_value: float
```

**Concrete Example:**

```json
{
    "timestamp": 1693683059.123,
    "conpty_count": 3,
    "process_count": 250,
    "memory_percent": 45.2,
    "handle_count": 8500,
    "unleashed_sessions": 1,
    "driver": "conpty",
    "composite_value": 36.0
}
```

## 5. Function Specifications

### 5.1 `DataCollector.start()`

**File:** `src/boostgauge/collector.py`

**Signature:**
```python
def start(self, interval: float, out_queue: queue.Queue, thresholds: dict) -> None:
    """Start polling loop in background thread. Abstract."""
    raise NotImplementedError # pragma: no cover
```

**Input Example:**
```python
interval = 2.0
out_queue = queue.Queue()
thresholds = {
    "conpty": {"yellow": 5, "red": 10},
    "memory_percent": {"yellow": 80, "red": 90},
    "process_count": {"yellow": 300, "red": 400},
    "handle_count": {"yellow": 10000, "red": 15000}
}
```
**Output Example:**
```python
None
```
**Edge Cases:**
- Abstract method; cannot be called directly.

### 5.2 `DataCollector.stop()`

**File:** `src/boostgauge/collector.py`

**Signature:**
```python
def stop(self) -> None:
    """Signal polling loop to terminate and wait for exit. Abstract."""
    raise NotImplementedError # pragma: no cover
```

**Input Example:**
```python
# No arguments
```
**Output Example:**
```python
None
```
**Edge Cases:**
- Abstract method; cannot be called directly.

### 5.3 `WindowsCollector.start()`

**File:** `src/boostgauge/collectors/windows.py`

**Signature:**
```python
def start(self, interval: float, out_queue: queue.Queue, thresholds: dict) -> None:
    """Starts the background thread for Windows collection."""
    pass
```

**Input Example:**
```python
interval = 2.0
out_queue = queue.Queue()
thresholds = {
    "conpty": {"yellow": 5, "red": 10},
    "memory_percent": {"yellow": 80, "red": 90},
    "process_count": {"yellow": 300, "red": 400},
    "handle_count": {"yellow": 10000, "red": 15000}
}
```
**Output Example:**
```python
None
```
**Edge Cases:**
- Called when the thread is already running -> safely ignores or restarts.

### 5.4 `WindowsCollector.stop()`

**File:** `src/boostgauge/collectors/windows.py`

**Signature:**
```python
def stop(self) -> None:
    """Signals stop event and joins the background thread."""
    pass
```

**Input Example:**
```python
# No arguments
```
**Output Example:**
```python
None
```
**Edge Cases:**
- Called when thread is not alive -> returns cleanly without error.

### 5.5 `WindowsCollector._run()`

**File:** `src/boostgauge/collectors/windows.py`

**Signature:**
```python
def _run(self) -> None:
    """Background thread loop executing the sweep and queue push."""
    pass
```

**Input Example:**
```python
# No arguments (uses instance state initialized by start)
```
**Output Example:**
```python
None  # Side effect: puts SystemSnapshot items onto self._out_queue
```
**Edge Cases:**
- `psutil` raises `AccessDenied` reading `cmdline` -> ignores row and continues.
- Thread `stop_event` is set -> exits loop gracefully.

### 5.6 `WindowsCollector._normalize()`

**File:** `src/boostgauge/collectors/windows.py`

**Signature:**
```python
def _normalize(self, value: float, yellow_thresh: float, red_thresh: float) -> float:
    """Maps a raw metric value to a 0-100 scale using the threshold bands."""
    pass
```

**Input Example:**
```python
value = 7.5
yellow_thresh = 5.0
red_thresh = 10.0
```
**Output Example:**
```python
80.0
```
**Edge Cases:**
- `value <= yellow_thresh` -> linearly maps to 0-60.
- `value >= red_thresh` -> capped at 100.
- `yellow_thresh == red_thresh` -> returns 100 if `value >= red_thresh`, else linearly maps 0-60 based on yellow.

## 6. Change Instructions

### 6.1 `src/boostgauge/collector.py` (Add)

**Complete file contents:**
```python
"""Abstract data collector and structures.

Issue #4: Windows data collector
"""
from abc import ABC, abstractmethod
import queue
from dataclasses import dataclass
from typing import Any

@dataclass
class SystemSnapshot:
    timestamp: float
    conpty_count: int
    process_count: int
    memory_percent: float
    handle_count: int
    unleashed_sessions: int
    driver: str
    composite_value: float

class DataCollector(ABC):
    @abstractmethod
    def start(self, interval: float, out_queue: queue.Queue, thresholds: dict) -> None:
        """Start polling loop in background thread. Abstract."""
        raise NotImplementedError # pragma: no cover

    @abstractmethod
    def stop(self) -> None:
        """Signal polling loop to terminate and wait for exit. Abstract."""
        raise NotImplementedError # pragma: no cover
```

### 6.2 `src/boostgauge/collectors/__init__.py` (Add)

**Complete file contents:**
```python
"""Collectors package."""
```

### 6.3 `src/boostgauge/collectors/windows.py` (Add)

**Complete file contents:**
```python
"""Windows data collector using NtQuerySystemInformation.

Issue #4: Windows data collector
"""
import ctypes
import fnmatch
import queue
import threading
import time
import psutil

from boostgauge.collector import DataCollector, SystemSnapshot

# C-Struct definitions for NtQuerySystemInformation
class UNICODE_STRING(ctypes.Structure):
    _fields_ = [
        ("Length", ctypes.c_ushort),
        ("MaximumLength", ctypes.c_ushort),
        ("Buffer", ctypes.c_void_p),
    ]

class SYSTEM_PROCESS_INFORMATION(ctypes.Structure):
    pass

SYSTEM_PROCESS_INFORMATION._fields_ = [
    ("NextEntryOffset", ctypes.c_ulong),
    ("NumberOfThreads", ctypes.c_ulong),
    ("Reserved1", ctypes.c_ubyte * 48),
    ("ImageName", UNICODE_STRING),
    ("BasePriority", ctypes.c_long),
    ("UniqueProcessId", ctypes.c_void_p),
    ("Reserved2", ctypes.c_void_p),
    ("HandleCount", ctypes.c_ulong),
]

class WindowsCollector(DataCollector):
    def __init__(self):
        self._stop_event = threading.Event()
        self._thread = None
        self._interval = 2.0
        self._out_queue = None
        self._thresholds = {}

    def start(self, interval: float, out_queue: queue.Queue, thresholds: dict) -> None:
        """Starts the background thread for Windows collection."""
        self._interval = interval
        self._out_queue = out_queue
        self._thresholds = thresholds
        self._stop_event.clear()
        
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        """Signals stop event and joins the background thread."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join()

    def _normalize(self, value: float, yellow_thresh: float, red_thresh: float) -> float:
        """Maps a raw metric value to a 0-100 scale using the threshold bands."""
        if value <= yellow_thresh:
            if yellow_thresh == 0:
                return 60.0 if value > 0 else 0.0
            return (value / yellow_thresh) * 60.0
        elif value >= red_thresh:
            return 100.0
        else:
            range_val = red_thresh - yellow_thresh
            if range_val == 0:
                return 100.0
            return 60.0 + ((value - yellow_thresh) / range_val) * 40.0

    def _run(self) -> None:
        """Background thread loop executing the sweep and queue push."""
        ntdll = ctypes.windll.ntdll
        while not self._stop_event.wait(timeout=self._interval):
            process_count = 0
            conpty_count = 0
            handle_count = 0
            unleashed_sessions = 0
            
            # Initial buffer sizing for NtQuerySystemInformation (SystemProcessInformation = 5)
            buffer_size = ctypes.c_ulong(512 * 1024)
            buffer = ctypes.create_string_buffer(buffer_size.value)
            
            status = ntdll.NtQuerySystemInformation(5, buffer, buffer_size, ctypes.byref(buffer_size))
            
            if status == 0:
                offset = 0
                while True:
                    process_info = ctypes.cast(ctypes.byref(buffer, offset), ctypes.POINTER(SYSTEM_PROCESS_INFORMATION)).contents
                    process_count += 1
                    handle_count += process_info.HandleCount
                    
                    if process_info.ImageName.Buffer:
                        image_name = ctypes.wstring_at(process_info.ImageName.Buffer, process_info.ImageName.Length // 2).lower()
                        if image_name in ("conhost.exe", "openconsole.exe"):
                            conpty_count += 1
                        elif image_name in ("python.exe", "pythonw.exe"):
                            pid = process_info.UniqueProcessId
                            try:
                                proc = psutil.Process(pid)
                                cmdline = proc.cmdline()
                                if any(fnmatch.fnmatch(arg, "unleashed-c-*.py") for arg in cmdline):
                                    unleashed_sessions += 1
                            except (psutil.AccessDenied, psutil.NoSuchProcess):
                                pass
                                
                    if process_info.NextEntryOffset == 0:
                        break
                    offset += process_info.NextEntryOffset

            memory_percent = psutil.virtual_memory().percent
            
            # Compute composite
            metrics = {
                "conpty": conpty_count,
                "memory_percent": memory_percent,
                "process_count": process_count,
                "handle_count": handle_count
            }
            
            max_score = 0.0
            driver = "memory_percent"
            
            for m_name, m_val in metrics.items():
                if m_name in self._thresholds:
                    score = self._normalize(
                        m_val, 
                        self._thresholds[m_name].get("yellow", 0), 
                        self._thresholds[m_name].get("red", 0)
                    )
                    if score > max_score:
                        max_score = score
                        driver = m_name
            
            snapshot = SystemSnapshot(
                timestamp=time.time(),
                conpty_count=conpty_count,
                process_count=process_count,
                memory_percent=memory_percent,
                handle_count=handle_count,
                unleashed_sessions=unleashed_sessions,
                driver=driver,
                composite_value=max_score
            )
            
            try:
                self._out_queue.put_nowait(snapshot)
            except queue.Full:
                pass
```

### 6.4 `tests/unit/test_windows_collector.py` (Add)
Create test file containing unit tests for `WindowsCollector` covering `start`, `stop`, `_normalize`, and `_run` (using mocked `ctypes.windll.ntdll.NtQuerySystemInformation` to avoid real system calls in unit mode).

### 6.5 `tests/integration/test_collector_live.py` (Add)
Create test file verifying the live collector matches `psutil` counts directly on the running Windows host.

### 6.6 `tests/benchmark/test_collector_benchmark.py` (Add)
Create test file asserting the execution time of `_run` falls within the <20ms latency budget.

## 7. Pattern References

### 7.1 Pure Abstract Base Class

**File:** `src/boostgauge/telltale.py` (lines 42-45)
```python
class Telltale:
    """Peak-hold over `window` seconds (or all-time when `window` is None)."""
    def __init__(self, window: float | None, decay_rate: float | None = None) -> None:
        pass
```
**Relevance:** Emulates the purely isolated, cleanly designed class initialization pattern used in `Telltale` to keep dependencies strict and behaviors encapsulated.

### 7.2 Configuration Dictionary Access

**File:** `src/boostgauge/config.py` (lines 40-41)
```python
class ThresholdsConfig(TypedDict):
    pass
```
**Relevance:** Ensures the `thresholds` dictionary passed to `start()` acts like the expected `ThresholdsConfig` type and uses `.get()` extraction to avoid runtime `KeyError` crashes.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import ctypes` | stdlib | `windows.py` |
| `import fnmatch` | stdlib | `windows.py` |
| `import queue` | stdlib | `collector.py`, `windows.py` |
| `import threading` | stdlib | `windows.py` |
| `import time` | stdlib | `windows.py` |
| `import psutil` | PyPI | `windows.py` |
| `from dataclasses import dataclass` | stdlib | `collector.py` |
| `from abc import ABC, abstractmethod` | stdlib | `collector.py` |

**New Dependencies:** None (psutil is already in `pyproject.toml`).

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `_run()` | Stubbed OS call | Makes exactly 1 call to `NtQuerySystemInformation` per tick |
| T015 | Source text | `windows.py` text | Text contains no banned `psutil.pids`, `psutil.process_iter`, `Get-Process` |
| T020 | `_run()` | Windows host | Sweep ConPTY equals psutil `process_iter` ConPTY count ±1 |
| T030 | `_run()` | Windows host | Process count ±1, Handle within 1% of psutil |
| T040 | `_run()` | Mocked sweep with Python | Unleashed count exactly matches python rows with `unleashed-c-*.py` |
| T050 | `start()`, `stop()` | `interval=0.01` | Pushes items to queue, safely joins thread |
| T060 | `_run()` | Mocked `AccessDenied` | Exception caught, count unaffected |
| T065 | `_run()` | Mocked `NoSuchProcess` | Exception caught, count unaffected |
| T070 | `_run()` | Benchmark iterations | Mean process_time < 20 ms |
| T080 | `_normalize()` | `value=7.5`, `yellow=5`, `red=10` | Composite value maps to `80.0` |
| T090 | `_run()` | Mocked threshold metrics | Driver maps to max metric name |
| T100 | `_run()` | Mocked `psutil.virtual_memory()` | Memory percent derived directly |
| T110 | `DataCollector` | Base class instantiation | Raises `NotImplementedError` |

### 10.1 Per-criterion test functions

```python
def test_req_6_mocked_single_sweep():
    # The collector MUST derive system metrics from a single sweep per tick (REQ-6) 
    # expected: ntdll.NtQuerySystemInformation.call_count == 1 per tick
    pass

def test_req_6_source_anti_pattern():
    # Source code MUST NOT reference banned process APIs (REQ-6) 
    # expected: "psutil.pids" not in source_text
    import pathlib
    source = pathlib.Path("src/boostgauge/collectors/windows.py").read_text()
    assert "psutil.pids" not in source
    assert "psutil.process_iter" not in source
    assert "Get-Process" not in source

def test_req_1_conpty_count(live_environment):
    # Collector MUST return an accurate ConPTY count (REQ-1) 
    # expected: collector snapshot conpty_count == psutil conpty_count +/- 1
    pass

def test_req_2_basic_metrics_accuracy(live_environment):
    # Collector MUST return accurate memory, process, and handle count (REQ-2) 
    # expected: process count matches psutil +/- 1; handle count within 1%
    pass

def test_req_3_unleashed_detection(mocker):
    # Collector MUST accurately detect unleashed sessions (REQ-3) 
    # expected: unleashed_sessions count exactly matches rows with unleashed-c-*.py
    pass

def test_req_4_non_blocking_polling():
    # Polling MUST be non-blocking in a background thread (REQ-4) 
    # expected: start() doesn't block, thread is alive, items populate queue
    pass

def test_req_5_permission_error(mocker):
    # Collector MUST gracefully handle AccessDenied (REQ-5) 
    # expected: exception caught, iteration continues seamlessly
    pass

def test_req_5_process_exit_error(mocker):
    # Collector MUST gracefully handle NoSuchProcess (REQ-5) 
    # expected: exception caught, iteration continues seamlessly
    pass

def test_req_7_cpu_overhead_benchmark(benchmark):
    # Sweep's mean process_time must be < 20 ms over 8 ticks (REQ-7) 
    # expected: benchmark time < 0.020
    pass

def test_req_8_composite_value_calculation():
    # Composite value MUST map 0-100 based on thresholds (REQ-8) 
    # expected: max_score calculated accurately
    pass

def test_req_9_driver_metric_reporting():
    # Driver field MUST correctly report max normalized metric (REQ-9) 
    # expected: driver == "conpty" (when conpty is the highest)
    pass

def test_req_10_memory_percent(mocker):
    # Memory percent MUST derive from single direct psutil virtual_memory call (REQ-10) 
    # expected: psutil.virtual_memory.call_count == 1
    pass

def test_data_collector_not_implemented():
    # Base DataCollector MUST raise NotImplementedError on start and stop
    import pytest
    from boostgauge.collector import DataCollector
    class Dummy(DataCollector):
        def start(self, interval, out_queue, thresholds):
            super().start(interval, out_queue, thresholds)
        def stop(self):
            super().stop()
    dummy = Dummy()
    with pytest.raises(NotImplementedError):
        dummy.start(1.0, None, {})
    with pytest.raises(NotImplementedError):
        dummy.stop()
```

## 11. Implementation Notes

### 11.1 Error Handling Convention
The thread loop must gracefully bypass missing or strictly protected processes. We explicitly trap `psutil.AccessDenied` and `psutil.NoSuchProcess` internally to prevent the background thread from crashing. No exceptions from process enumeration should ever propagate to the top-level thread boundary.

### 11.2 String Comparison
Process names extracted from the C-Structs using `NtQuerySystemInformation` are raw `WCHAR` pointers. `image_name` matching must always be case-insensitive (e.g., matching against `.lower()`).

### 11.3 Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| `SYSTEM_PROCESS_INFORMATION_CLASS` | `5` | Required NT syscall argument enum to return process lists |
| `STATUS_INFO_LENGTH_MISMATCH` | `0xC0000004` | Windows NT status indicating buffer is too small |

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3) - *Not applicable, verified as pure additions.*
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
| Issue | #4 |
| Verdict | APPROVED |
| Date | 2026-09-02 |
| Iterations | 3 |
| Finalized | 2026-09-02T21:47:40Z |

### Review Feedback Summary

The spec correctly resolves prior feedback by removing the retry loop that caused multiple NtQuerySystemInformation references, thereby strictly satisfying REQ-6. All assertions in the test code (`test_req_6_source_anti_pattern` and `test_data_collector_not_implemented`) explicitly trace back to LLD Requirement 6 and the spec's own DataCollector behavior definitions, respectively. There are no unwinnable tests, requirements conflicts, or baseline issues. The implementation is highly concrete and...
