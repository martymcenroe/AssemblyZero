# Implementation Spec: Issue #4 - Feature: Windows data collector — ConPTY, processes, memory, handles

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #4 |
| LLD | `docs/lld/done/004-windows-data-collector.md` |
| Generated | 2026-09-02 |
| Status | APPROVED |

## 1. Overview

**Objective:** Build a Windows-specific data collector that polls system metrics (ConPTY, processes, memory, handles) via a single `NtQuerySystemInformation` sweep per tick and feeds them to the gauge.

**Success Criteria:**
- The collector must run on a background thread pushing `SystemSnapshot` objects to a queue.
- All process-derived metrics MUST be gathered from a single `NtQuerySystemInformation` API call per tick, without using `psutil.process_iter`.
- The collector must identify ConPTY counts (`conhost.exe`, `OpenConsole.exe`), memory percentage, total process counts, total handle counts, and unleashed sessions from Python command line arguments.
- It must calculate a normalized 0-100 composite metric and identify the driver metric causing the highest load, executing with < 1% CPU overhead.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/boostgauge/collector.py` | Add | Abstract base class `DataCollector` and `SystemSnapshot` dataclass |
| 2 | `src/boostgauge/collectors/__init__.py` | Add | Package init for platform collectors |
| 3 | `src/boostgauge/collectors/windows.py` | Add | Windows implementation using `NtQuerySystemInformation` and `psutil` |
| 4 | `tests/unit/test_windows_collector.py` | Add | Unit tests asserting single-call behavior via mocked `ctypes` |
| 5 | `tests/integration/test_windows_collector_live.py` | Add | Live cross-checks against `psutil` on the running machine |
| 6 | `tests/benchmark/test_windows_collector_perf.py` | Add | Performance benchmarks asserting execution time |

**Implementation Order Rationale:** The core domain types (`collector.py`) must be built first, followed by the platform-specific implementation (`windows.py`). Tests are ordered unit -> integration -> benchmark to progressively prove functionality and performance.

## 3. Current State (for Modify/Delete files)

*No existing files are modified or deleted in this issue. All files are new additions.*

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
    "timestamp": 1709664532.123,
    "conpty_count": 5,
    "process_count": 312,
    "memory_percent": 68.4,
    "handle_count": 84300,
    "unleashed_sessions": 2,
    "driver": "memory_percent",
    "composite_value": 68.4
}
```

## 5. Function Specifications

### 5.1 `DataCollector.__init__()`

**File:** `src/boostgauge/collector.py`

**Signature:**

```python
def __init__(self, output_queue: Queue, thresholds: dict, poll_interval: float = 2.0):
    """Initialize the background thread collector."""
    ...
```

**Input Example:**

```python
import queue
output_queue = queue.Queue()
thresholds = {
    "conpty": {"yellow": 60, "red": 80},
    "memory_percent": {"yellow": 60, "red": 80},
    "process_count": {"yellow": 400, "red": 500},
    "handle_count": {"yellow": 80000, "red": 100000}
}
poll_interval = 2.0
```

**Output Example:**

```python
# Constructor returns None, object is initialized
None
```

**Edge Cases:**
- `poll_interval <= 0` -> sets to a minimum safe limit (e.g., 0.1) or proceeds if caller intentionally forces fast polling for tests.
- Empty `thresholds` -> valid, but forces `_normalize` to return 0.0.

### 5.2 `DataCollector._normalize()`

**File:** `src/boostgauge/collector.py`

**Signature:**

```python
def _normalize(self, value: float, thresholds: dict) -> float:
    """Map raw value to 0-100 based on yellow/red thresholds."""
    ...
```

**Input Example:**

```python
value = 65.0
thresholds = {"yellow": 60.0, "red": 80.0}
```

**Output Example:**

```python
65.0 # Interpolates linearly between 60(yellow)->60 and 80(red)->80.
```

**Edge Cases:**
- `thresholds` missing "yellow" or "red" -> gracefully handles by returning 0.0 or avoiding divide-by-zero.
- `value > red` -> clamps result to maximum 100.0.

### 5.3 `WindowsCollector._take_snapshot()`

**File:** `src/boostgauge/collectors/windows.py`

**Signature:**

```python
def _take_snapshot(self) -> SystemSnapshot:
    """Sweep the process table exactly once and calculate all metrics."""
    ...
```

**Input Example:**

```python
# No arguments other than self. Requires a live OS or mocked ctypes behavior.
```

**Output Example:**

```python
SystemSnapshot(
    timestamp=1709664532.123, 
    conpty_count=2, 
    process_count=150, 
    memory_percent=45.0, 
    handle_count=12000, 
    unleashed_sessions=1, 
    driver='memory_percent', 
    composite_value=45.0
)
```

**Edge Cases:**
- `NtQuerySystemInformation` buffer resizing -> automatically handles `STATUS_INFO_LENGTH_MISMATCH` by expanding the buffer and retrying.
- `psutil.AccessDenied` when querying command lines -> catches exception and proceeds without adding to the unleashed session count, ensuring the sweep continues.

## 6. Change Instructions

### 6.1 `src/boostgauge/collector.py` (Add)

**Complete file contents:**

```python
"""Data collector base classes and data structures.

Issue #4: Windows data collector — ConPTY, processes, memory, handles
"""

import abc
import time
import logging
from dataclasses import dataclass
from threading import Thread, Event
from queue import Queue

logger = logging.getLogger(__name__)

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

class DataCollector(abc.ABC):
    """Background thread that polls system metrics into a queue."""

    def __init__(self, output_queue: Queue, thresholds: dict, poll_interval: float = 2.0):
        self.output_queue = output_queue
        self.thresholds = thresholds
        self.poll_interval = poll_interval
        self._stop_event = Event()
        self._thread = None

    def start(self) -> None:
        """Start the background polling thread."""
        self._stop_event.clear()
        self._thread = Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Signal the thread to stop and wait for it."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join()

    def _run_loop(self) -> None:
        while not self._stop_event.wait(self.poll_interval):
            try:
                snapshot = self._take_snapshot()
                self.output_queue.put(snapshot)
            except Exception as e:
                logger.error(f"Error taking snapshot: {e}")

    @abc.abstractmethod
    def _take_snapshot(self) -> SystemSnapshot:
        """Take a single snapshot of the system state."""
        pass

    def _normalize(self, value: float, thresholds: dict) -> float:
        """Map raw value to 0-100 based on yellow/red thresholds."""
        if not thresholds:
            return 0.0
        
        yellow = thresholds.get("yellow", 0)
        red = thresholds.get("red", 0)
        
        if yellow == 0 and red == 0:
            return 0.0
            
        if value < yellow:
            return (value / yellow) * 60 if yellow > 0 else 0
        elif value < red:
            return 60 + ((value - yellow) / (red - yellow)) * 20 if red > yellow else 80
        else:
            val = 80 + ((value - red) / (red - yellow)) * 20 if red > yellow else 100.0
            return min(val, 100.0)
```

### 6.2 `src/boostgauge/collectors/__init__.py` (Add)

**Complete file contents:**

```python
"""Platform specific data collectors.

Issue #4: Windows data collector — ConPTY, processes, memory, handles
"""
```

### 6.3 `src/boostgauge/collectors/windows.py` (Add)

**Complete file contents:**

```python
"""Windows specific collector utilizing NtQuerySystemInformation.

Issue #4: Windows data collector — ConPTY, processes, memory, handles
"""

import ctypes
from ctypes import wintypes
import time
import psutil
import logging

from boostgauge.collector import DataCollector, SystemSnapshot

logger = logging.getLogger(__name__)

class UNICODE_STRING(ctypes.Structure):
    _fields_ = [
        ("Length", wintypes.USHORT),
        ("MaximumLength", wintypes.USHORT),
        ("Buffer", wintypes.LPWSTR),
    ]

class SYSTEM_PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("NextEntryOffset", wintypes.ULONG),
        ("NumberOfThreads", wintypes.ULONG),
        ("WorkingSetPrivateSize", ctypes.c_int64),
        ("HardFaultCount", wintypes.ULONG),
        ("NumberOfThreadsHighWatermark", wintypes.ULONG),
        ("CycleTime", ctypes.c_uint64),
        ("CreateTime", ctypes.c_int64),
        ("UserTime", ctypes.c_int64),
        ("KernelTime", ctypes.c_int64),
        ("ImageName", UNICODE_STRING),
        ("BasePriority", ctypes.c_int32),
        ("UniqueProcessId", ctypes.c_void_p),
        ("InheritedFromUniqueProcessId", ctypes.c_void_p),
        ("HandleCount", wintypes.ULONG),
    ]

ntdll = ctypes.WinDLL("ntdll.dll")
SystemProcessInformation = 5
STATUS_INFO_LENGTH_MISMATCH = 0xC0000004


class WindowsCollector(DataCollector):
    """Windows specific collector utilizing NtQuerySystemInformation."""

    def _take_snapshot(self) -> SystemSnapshot:
        """Sweep the process table exactly once and calculate all metrics."""
        memory_percent = psutil.virtual_memory().percent
        
        buffer_size = ctypes.c_ulong(1024 * 1024)
        buffer = ctypes.create_string_buffer(buffer_size.value)
        
        while True:
            status = ntdll.NtQuerySystemInformation(
                SystemProcessInformation,
                buffer,
                buffer_size,
                ctypes.byref(buffer_size)
            )
            # Handle STATUS_INFO_LENGTH_MISMATCH (overflow integer matching)
            if status == STATUS_INFO_LENGTH_MISMATCH or status == -1073741820:
                buffer = ctypes.create_string_buffer(buffer_size.value)
            elif status >= 0:
                break
            else:
                logger.error(f"NtQuerySystemInformation failed with status: {status}")
                return SystemSnapshot(time.time(), 0, 0, memory_percent, 0, 0, "memory_percent", 0.0)
                
        conpty_count = 0
        process_count = 0
        handle_count = 0
        unleashed_sessions = 0
        
        offset = 0
        while True:
            process_info = ctypes.cast(
                ctypes.addressof(buffer) + offset,
                ctypes.POINTER(SYSTEM_PROCESS_INFORMATION)
            ).contents
            
            process_count += 1
            handle_count += process_info.HandleCount
            
            if process_info.ImageName.Buffer:
                try:
                    image_name = ctypes.wstring_at(process_info.ImageName.Buffer, process_info.ImageName.Length // 2)
                    image_name_lower = image_name.lower()
                    
                    if image_name_lower in ('conhost.exe', 'openconsole.exe'):
                        conpty_count += 1
                        
                    elif image_name_lower in ('python.exe', 'pythonw.exe'):
                        pid = process_info.UniqueProcessId
                        if pid:
                            try:
                                proc = psutil.Process(pid)
                                cmdline = proc.cmdline()
                                if any(arg.startswith('unleashed-c-') and arg.endswith('.py') for arg in cmdline):
                                    unleashed_sessions += 1
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                logger.debug("Process access denied")
                except ValueError:
                    logger.debug("Invalid buffer")
            
            if process_info.NextEntryOffset == 0:
                break
                
            offset += process_info.NextEntryOffset

        metrics = {
            "memory_percent": memory_percent,
            "conpty": conpty_count,
            "process_count": process_count,
            "handle_count": handle_count
        }
        
        max_val = -1.0
        driver = "memory_percent"
        
        for metric, val in metrics.items():
            norm = self._normalize(val, self.thresholds.get(metric, {}))
            if norm > max_val:
                max_val = norm
                driver = metric
                
        return SystemSnapshot(
            timestamp=time.time(),
            conpty_count=conpty_count,
            process_count=process_count,
            memory_percent=memory_percent,
            handle_count=handle_count,
            unleashed_sessions=unleashed_sessions,
            driver=driver,
            composite_value=max_val
        )
```

### 6.4 `tests/unit/test_windows_collector.py` (Add)

**Complete file contents:**

```python
import pytest
from queue import Queue
from boostgauge.collectors.windows import WindowsCollector

# Mocking tests for the scenarios
```

### 6.5 `tests/integration/test_windows_collector_live.py` (Add)

**Complete file contents:**

```python
import pytest
from queue import Queue
from boostgauge.collectors.windows import WindowsCollector

# Live execution tests mapping to scenarios
```

### 6.6 `tests/benchmark/test_windows_collector_perf.py` (Add)

**Complete file contents:**

```python
import pytest
from queue import Queue
from boostgauge.collectors.windows import WindowsCollector

# Benchmark tests mapping to scenarios
```

## 7. Pattern References

### 7.1 Class Initialization and Pure Functions
**File:** `src/boostgauge/telltale.py` (lines 44-55)

```python
class Telltale:
    """Peak-hold over `window` seconds (or all-time when `window` is None)."""
    def __init__(self, window: float | None, decay_rate: float | None = None) -> None:
        pass
```

**Relevance:** Demonstrates class-based encapsulation and pure function semantics used across the project to maintain state without unnecessary external dependencies.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import abc` | stdlib | `collector.py` |
| `import time` | stdlib | `collector.py`, `windows.py` |
| `from dataclasses import dataclass` | stdlib | `collector.py` |
| `from threading import Thread, Event` | stdlib | `collector.py` |
| `from queue import Queue` | stdlib | `collector.py` |
| `import ctypes` | stdlib | `windows.py` |
| `from ctypes import wintypes` | stdlib | `windows.py` |
| `import psutil` | PyPI | `windows.py` |
| `import logging` | stdlib | `collector.py`, `windows.py` |

**New Dependencies:** None (psutil is already in project requirements)

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| 010 | `test_req_010_mocked_sweep()` | Mocked buffer with 10 procs, 2 ConPTY | `process_count==10`, `conpty_count==2` |
| 020 | `test_req_020_case_insensitive_conpty()` | Mocked buffer with "CoNHoST.eXe" | `conpty_count==1` |
| 030 | `test_req_030_memory_percentage()` | Mocked `virtual_memory()` returns 45.0 | `memory_percent==45.0` |
| 040 | `test_req_040_exact_process_count()` | Mocked buffer of 14 processes | `process_count==14` |
| 050 | `test_req_050_handle_count()` | Mocked buffer with handles summing 8500 | `handle_count==8500` |
| 060 | `test_req_060_unleashed_matching()` | Mocked "notepad.exe" with python args | `unleashed_sessions==0` |
| 070 | `test_req_070_graceful_access_denied()` | Mocked python process throws AccessDenied | Tick completes without failure |
| 080 | `test_req_080_composite_calculation()` | Thresholds dict producing varying norms | `driver=='memory_percent'` and `composite_value==75.0` |
| 090 | `test_req_090_live_process_count()` | Live OS execution | Match of `psutil.process_iter()` len within tolerance |
| 100 | `test_req_100_live_conpty_count()` | Live OS execution | Match of `psutil` conhost search within tolerance |
| 110 | `test_req_110_live_handle_count()` | Live OS execution | Match of `psutil` handle sum within tolerance |
| 120 | `test_req_120_background_threading()` | Initialize with poll interval 0.01s | Queue receives >3 snapshots |
| 130 | `test_req_130_performance_baseline()` | Live OS benchmark 8 ticks | Mean execution time < 20ms |

### 10.1 Per-criterion test functions

```python
def test_req_010_mocked_sweep(monkeypatch):
    # Happy path object creation and metric extraction via mocked ctypes (REQ-2) -- expected: conpty_count == 2, process_count == 10
    from boostgauge.collectors.windows import WindowsCollector
    from queue import Queue
    import ctypes
    
    monkeypatch.setattr("psutil.virtual_memory", lambda: type("vmem", (), {"percent": 50.0})())
    monkeypatch.setattr("boostgauge.collectors.windows.ntdll.NtQuerySystemInformation", lambda *args: 0)
    
    class MockProcessInfo:
        def __init__(self, name, next_offset, idx):
            self.HandleCount = 5
            self.NextEntryOffset = next_offset
            self.UniqueProcessId = 123
            self.ImageName = type("MockName", (), {"Buffer": idx, "Length": len(name) * 2})()
            self._name = name
            
    procs = [MockProcessInfo("conhost.exe", 100, i+1) for i in range(2)]
    procs += [MockProcessInfo("other.exe", 100, i+1) for i in range(2, 9)]
    procs += [MockProcessInfo("other.exe", 0, 10)]
    mock_iter = iter(procs)
    
    monkeypatch.setattr(ctypes, "cast", lambda *args: type("MockPointer", (), {"contents": next(mock_iter)})())
    monkeypatch.setattr(ctypes, "wstring_at", lambda buf, length: procs[buf-1]._name)
    
    c = WindowsCollector(Queue(), {})
    snap = c._take_snapshot()
    assert snap.process_count == 10
    assert snap.conpty_count == 2

def test_req_020_case_insensitive_conpty(monkeypatch):
    # ConPTY process counting strictly case-insensitive (REQ-3) -- expected: conpty_count == 1
    from boostgauge.collectors.windows import WindowsCollector
    from queue import Queue
    import ctypes
    
    monkeypatch.setattr("psutil.virtual_memory", lambda: type("vmem", (), {"percent": 50.0})())
    monkeypatch.setattr("boostgauge.collectors.windows.ntdll.NtQuerySystemInformation", lambda *args: 0)
    
    proc = type("MockProcessInfo", (), {"HandleCount": 5, "NextEntryOffset": 0, "UniqueProcessId": 123, "ImageName": type("MockName", (), {"Buffer": 1, "Length": 22})()})()
    monkeypatch.setattr(ctypes, "cast", lambda *args: type("MockPointer", (), {"contents": proc})())
    monkeypatch.setattr(ctypes, "wstring_at", lambda buf, length: "CoNHoST.eXe")
    
    c = WindowsCollector(Queue(), {})
    snap = c._take_snapshot()
    assert snap.conpty_count == 1

def test_req_030_memory_percentage(monkeypatch):
    # Memory percentage read passes directly through (REQ-4) -- expected: memory_percent == 45.0
    from boostgauge.collectors.windows import WindowsCollector
    from queue import Queue
    import ctypes
    
    monkeypatch.setattr("psutil.virtual_memory", lambda: type("vmem", (), {"percent": 45.0})())
    monkeypatch.setattr("boostgauge.collectors.windows.ntdll.NtQuerySystemInformation", lambda *args: 0)
    
    proc = type("MockProcessInfo", (), {"HandleCount": 5, "NextEntryOffset": 0, "UniqueProcessId": 123, "ImageName": type("MockName", (), {"Buffer": None, "Length": 0})()})()
    monkeypatch.setattr(ctypes, "cast", lambda *args: type("MockPointer", (), {"contents": proc})())
    
    c = WindowsCollector(Queue(), {})
    snap = c._take_snapshot()
    assert snap.memory_percent == 45.0
    
def test_req_040_exact_process_count(monkeypatch):
    # Process count is exact row length of sweep buffer (REQ-5) -- expected: process_count == 14
    from boostgauge.collectors.windows import WindowsCollector
    from queue import Queue
    import ctypes
    
    monkeypatch.setattr("psutil.virtual_memory", lambda: type("vmem", (), {"percent": 50.0})())
    monkeypatch.setattr("boostgauge.collectors.windows.ntdll.NtQuerySystemInformation", lambda *args: 0)
    
    procs = [type("MockProcessInfo", (), {"HandleCount": 1, "NextEntryOffset": 100, "UniqueProcessId": 123, "ImageName": type("MockName", (), {"Buffer": None, "Length": 0})()})() for _ in range(13)]
    procs.append(type("MockProcessInfo", (), {"HandleCount": 1, "NextEntryOffset": 0, "UniqueProcessId": 123, "ImageName": type("MockName", (), {"Buffer": None, "Length": 0})()})())
    mock_iter = iter(procs)
    
    monkeypatch.setattr(ctypes, "cast", lambda *args: type("MockPointer", (), {"contents": next(mock_iter)})())
    
    c = WindowsCollector(Queue(), {})
    snap = c._take_snapshot()
    assert snap.process_count == 14
    
def test_req_050_handle_count(monkeypatch):
    # Total handle count matches exact sum of rows (REQ-6) -- expected: handle_count == 8500
    from boostgauge.collectors.windows import WindowsCollector
    from queue import Queue
    import ctypes
    
    monkeypatch.setattr("psutil.virtual_memory", lambda: type("vmem", (), {"percent": 50.0})())
    monkeypatch.setattr("boostgauge.collectors.windows.ntdll.NtQuerySystemInformation", lambda *args: 0)
    
    procs = [
        type("MockProcessInfo", (), {"HandleCount": 4000, "NextEntryOffset": 100, "UniqueProcessId": 123, "ImageName": type("MockName", (), {"Buffer": None, "Length": 0})()})(),
        type("MockProcessInfo", (), {"HandleCount": 4500, "NextEntryOffset": 0, "UniqueProcessId": 124, "ImageName": type("MockName", (), {"Buffer": None, "Length": 0})()})()
    ]
    mock_iter = iter(procs)
    
    monkeypatch.setattr(ctypes, "cast", lambda *args: type("MockPointer", (), {"contents": next(mock_iter)})())
    
    c = WindowsCollector(Queue(), {})
    snap = c._take_snapshot()
    assert snap.handle_count == 8500
    
def test_req_060_unleashed_matching(monkeypatch):
    # Unleashed matching ignores non-Python processes with matching string (REQ-7) -- expected: unleashed_sessions == 0
    from boostgauge.collectors.windows import WindowsCollector
    from queue import Queue
    import ctypes
    import psutil
    
    monkeypatch.setattr("psutil.virtual_memory", lambda: type("vmem", (), {"percent": 50.0})())
    monkeypatch.setattr("boostgauge.collectors.windows.ntdll.NtQuerySystemInformation", lambda *args: 0)
    
    proc = type("MockProcessInfo", (), {"HandleCount": 5, "NextEntryOffset": 0, "UniqueProcessId": 999, "ImageName": type("MockName", (), {"Buffer": 1, "Length": 22})()})()
    monkeypatch.setattr(ctypes, "cast", lambda *args: type("MockPointer", (), {"contents": proc})())
    monkeypatch.setattr(ctypes, "wstring_at", lambda buf, length: "notepad.exe")
    
    monkeypatch.setattr(psutil, "Process", lambda pid: type("MockProc", (), {"cmdline": lambda: ["unleashed-c-123.py"]})())
    
    c = WindowsCollector(Queue(), {})
    snap = c._take_snapshot()
    assert snap.unleashed_sessions == 0
    
def test_req_070_graceful_access_denied(monkeypatch, caplog):
    # Graceful degradation on AccessDenied during cmdline read and ValueError on wstring_at (REQ-8) -- expected: Tick completes successfully
    from boostgauge.collectors.windows import WindowsCollector
    from queue import Queue
    import ctypes
    import psutil
    import logging
    
    caplog.set_level(logging.DEBUG)
    monkeypatch.setattr("psutil.virtual_memory", lambda: type("vmem", (), {"percent": 50.0})())
    monkeypatch.setattr("boostgauge.collectors.windows.ntdll.NtQuerySystemInformation", lambda *args: 0)
    
    proc1 = type("MockProcessInfo", (), {"HandleCount": 5, "NextEntryOffset": 100, "UniqueProcessId": 998, "ImageName": type("MockName", (), {"Buffer": 1, "Length": 20})()})()
    proc2 = type("MockProcessInfo", (), {"HandleCount": 5, "NextEntryOffset": 0, "UniqueProcessId": 999, "ImageName": type("MockName", (), {"Buffer": 2, "Length": 20})()})()
    
    mock_iter = iter([proc1, proc2])
    monkeypatch.setattr(ctypes, "cast", lambda *args: type("MockPointer", (), {"contents": next(mock_iter)})())
    
    def mock_wstring_at(buf, length):
        if buf == 1:
            raise ValueError("Buffer invalid")
        return "python.exe"
    monkeypatch.setattr(ctypes, "wstring_at", mock_wstring_at)
    
    def mock_process(pid):
        raise psutil.AccessDenied()
    monkeypatch.setattr(psutil, "Process", mock_process)
    
    c = WindowsCollector(Queue(), {})
    snap = c._take_snapshot()
    assert snap is not None
    assert snap.unleashed_sessions == 0
    assert "Invalid buffer" in caplog.text
    assert "Process access denied" in caplog.text
    
def test_req_080_composite_calculation(monkeypatch):
    # Composite value calculation selects correct highest driver (REQ-9) -- expected: driver == 'memory_percent', composite_value == 75.0
    from boostgauge.collectors.windows import WindowsCollector
    from queue import Queue
    import ctypes
    
    monkeypatch.setattr("psutil.virtual_memory", lambda: type("vmem", (), {"percent": 75.0})())
    monkeypatch.setattr("boostgauge.collectors.windows.ntdll.NtQuerySystemInformation", lambda *args: 0)
    
    proc = type("MockProcessInfo", (), {"HandleCount": 5, "NextEntryOffset": 0, "UniqueProcessId": 123, "ImageName": type("MockName", (), {"Buffer": None, "Length": 0})()})()
    monkeypatch.setattr(ctypes, "cast", lambda *args: type("MockPointer", (), {"contents": proc})())
    
    thresholds = {
        "memory_percent": {"yellow": 60, "red": 80},
        "process_count": {"yellow": 400, "red": 500},
        "handle_count": {"yellow": 80000, "red": 100000}
    }
    
    c = WindowsCollector(Queue(), thresholds)
    snap = c._take_snapshot()
    assert snap.driver == 'memory_percent'
    assert snap.composite_value == 75.0
    
def test_req_090_live_process_count():
    # Live cross check of process counting against psutil (REQ-5) -- expected: count matches psutil.process_iter() within tolerance
    from boostgauge.collectors.windows import WindowsCollector
    import psutil
    from queue import Queue
    c = WindowsCollector(Queue(), {})
    snap = c._take_snapshot()
    expected = len(list(psutil.process_iter()))
    assert abs(snap.process_count - expected) <= 5
    
def test_req_100_live_conpty_count():
    # Live cross check of ConPTY counting against psutil (REQ-3) -- expected: matches psutil console hosts within tolerance
    from boostgauge.collectors.windows import WindowsCollector
    import psutil
    from queue import Queue
    c = WindowsCollector(Queue(), {})
    snap = c._take_snapshot()
    expected = len([p for p in psutil.process_iter(['name']) if p.info['name'] and p.info['name'].lower() in ('conhost.exe', 'openconsole.exe')])
    assert abs(snap.conpty_count - expected) <= 2
    
def test_req_110_live_handle_count():
    # Live cross check of handle counting against psutil (REQ-6) -- expected: matches psutil num_handles sum within tolerance
    from boostgauge.collectors.windows import WindowsCollector
    import psutil
    from queue import Queue
    c = WindowsCollector(Queue(), {})
    snap = c._take_snapshot()
    
    psutil_handles = 0
    for p in psutil.process_iter():
        try:
            psutil_handles += p.num_handles()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
            
    assert abs(snap.handle_count - psutil_handles) <= 500
    
def test_req_120_background_threading(monkeypatch, caplog):
    # Background threading executes ticks without blocking (REQ-1) -- expected: Queue populated with >3 items, coverage for exception
    from boostgauge.collectors.windows import WindowsCollector
    from queue import Queue
    import time
    q = Queue()
    c = WindowsCollector(q, {}, poll_interval=0.01)
    
    original_take = c._take_snapshot
    fail_state = [True]
    def mock_take_snapshot():
        if fail_state[0]:
            fail_state[0] = False
            raise Exception("Simulate snapshot error")
        return original_take()
    monkeypatch.setattr(c, "_take_snapshot", mock_take_snapshot)
    
    c.start()
    time.sleep(0.1)
    c.stop()
    assert q.qsize() > 3
    assert "Simulate snapshot error" in caplog.text
    
def test_req_130_performance_baseline():
    # CPU Performance baseline (REQ-10) -- expected: Mean process_time < 20ms
    from boostgauge.collectors.windows import WindowsCollector
    from queue import Queue
    import time
    c = WindowsCollector(Queue(), {})
    
    times = []
    for _ in range(8):
        start = time.process_time()
        c._take_snapshot()
        times.append(time.process_time() - start)
        
    mean_time = sum(times) / len(times)
    assert mean_time < 0.02
```

## 11. Implementation Notes

### 11.1 Windows `NtQuerySystemInformation` Buffer Strategy

The `NtQuerySystemInformation` buffer requires a specific resizing loop because the process list changes rapidly in a real OS. If the allocated buffer is slightly too small by the time the kernel writes to it, the kernel returns `STATUS_INFO_LENGTH_MISMATCH` (often mapped to `-1073741820` or `0xC0000004`). We loop on this condition, expanding the string buffer allocation to match the size hinted by the kernel via `byref(buffer_size)`, up until a successful sweep occurs.

### 11.2 Error Handling Strategy

`psutil.NoSuchProcess` and `psutil.AccessDenied` are expected exceptions when reading `cmdline()` from another process, even if identified as a Python process. We catch these locally during the tick and simply `pass` rather than aborting the loop, acting as a skip on that specific session.

### 11.3 Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| `STATUS_INFO_LENGTH_MISMATCH` | `0xC0000004` | Standard Windows NT kernel response indicating the buffer must be enlarged |
| `SystemProcessInformation` | `5` | Required flag for system process iteration under NtQuerySystemInformation |

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3) - N/A (all files are additions)
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
| Iterations | 1 |
| Finalized | 2026-09-02T18:44:48-05:00 |