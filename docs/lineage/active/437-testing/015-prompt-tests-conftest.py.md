# Implementation Request: tests/conftest.py

## Task

Write the complete contents of `tests/conftest.py`.

Change type: Modify
Description: Add shared fixture for mocking file sizes

## LLD Specification

# Implementation Spec: Test: Large-File Consolidation Test for consolidate_logs.py

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #437 |
| LLD | `docs/lld/active/437-large-file-consolidation-test.md` |
| Generated | 2026-02-25 |
| Status | DRAFT |

## 1. Overview

Add a comprehensive unit test file covering >50MB history file consolidation and log rotation behavior in `consolidate_logs.py`. All tests use monkeypatched file sizes to avoid creating real large files on disk.

**Objective:** Close the test gap identified in issue #57 by adding unit tests for large-file consolidation and log rotation.

**Success Criteria:** 13 test scenarios pass, all execute in <5s total, no actual large files created on disk, all operations confined to `tmp_path`.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `tests/conftest.py` | Modify | Add shared fixture for mocking file sizes |
| 2 | `tests/unit/test_consolidate_logs_large_file.py` | Add | 13 unit tests for large-file consolidation and rotation |

**Implementation Order Rationale:** The shared fixture in `conftest.py` must exist before the test file can use it. The test file depends on the fixture and on the production module `consolidate_logs.py`.

## 3. Current State (for Modify/Delete files)

### 3.1 `tests/conftest.py`

**Relevant excerpt** (lines 1-11):

```python
"""Pytest configuration for test suite."""

import sys

from pathlib import Path

import pytest

def pytest_configure(config):
    """Configure pytest markers."""
    ...

tools_dir = Path(__file__).parent.parent / "tools"
```

**What changes:** Add a reusable `mock_file_size` fixture after the existing `tools_dir` line. This fixture provides a factory function that monkeypatches `os.path.getsize` to return a specified size for specific file paths while preserving real behavior for all other paths.

### 3.2 Production Module: `consolidate_logs.py` (Read-Only — NOT Modified)

> **CRITICAL:** Before implementing tests, the developer MUST read the actual `consolidate_logs.py` source to determine:
> 1. The exact import path (e.g., `assemblyzero.consolidate_logs` or `tools.consolidate_logs`)
> 2. How file size is checked (e.g., `os.path.getsize()`, `Path.stat().st_size`, or `os.stat()`)
> 3. The exact rotation suffix pattern (`.1`, `.2` vs. timestamps)
> 4. The public API function name (e.g., `consolidate_logs()`, `consolidate()`, `run()`)
> 5. The exact threshold value (50MB = 52_428_800 bytes, or a different value)
> 6. Whether the threshold check is `>` or `>=`
>
> The placeholders `CONSOLIDATE_MODULE`, `consolidate_function`, `SIZE_CHECK_TARGET`, and `ROTATION_SUFFIX` below must be replaced with actual values discovered from the source.

## 4. Data Structures

### 4.1 LargeFileFixture (Test-only concept)

**Definition:**

```python
# Not a formal class — conceptual structure for fixture return values
# Fixtures return Path objects; the "large" property is via monkeypatch
```

**Concrete Example:**

```json
{
    "path": "/tmp/pytest-of-user/pytest-42/test_rotation0/history.log",
    "actual_size_bytes": 512,
    "mocked_size_bytes": 52428800,
    "content_lines": 500,
    "sample_content": "line_0001\nline_0002\nline_0003\n...line_0500\n"
}
```

### 4.2 RotatedFileSet (Test verification structure)

**Definition:**

```python
# Conceptual — verified via assertions, not a formal class
# Represents the state of the log directory after rotation
```

**Concrete Example:**

```json
{
    "active_file": "/tmp/pytest-xxx/history.log",
    "active_file_size": 0,
    "backups": {
        "/tmp/pytest-xxx/history.log.1": {"lines": 500, "size": 512},
        "/tmp/pytest-xxx/history.log.2": {"lines": 300, "size": 307},
        "/tmp/pytest-xxx/history.log.3": {"lines": 200, "size": 205}
    },
    "total_lines_across_all_files": 1000
}
```

### 4.3 MonkeyPatchSizeMap

**Definition:**

```python
# Dict mapping file paths to mocked sizes
# Used by the mock_file_size fixture
size_overrides: dict[str, int]
```

**Concrete Example:**

```json
{
    "/tmp/pytest-xxx/history.log": 52428800,
    "/tmp/pytest-xxx/other.log": 10485760
}
```

## 5. Function Specifications

### 5.1 `mock_file_size` fixture (conftest.py)

**File:** `tests/conftest.py`

**Signature:**

```python
@pytest.fixture
def mock_file_size(monkeypatch):
    """Factory fixture: returns a function that patches os.path.getsize for specific paths.

    Usage: mock_file_size({"/path/to/file": 52_428_800})
    """
    def _mock(size_map: dict[str, int]) -> None:
        ...
    return _mock
```

**Input Example:**

```python
size_map = {
    str(tmp_path / "history.log"): 52_428_800
}
mock_file_size(size_map)
```

**Output Example:**

```python
# After calling mock_file_size(size_map):
os.path.getsize(str(tmp_path / "history.log"))  # Returns 52_428_800
os.path.getsize(str(tmp_path / "other.log"))     # Returns real size (unchanged)
```

**Edge Cases:**
- File not in `size_map` → delegates to real `os.path.getsize`
- File doesn't exist on disk but is in `size_map` → returns mocked size (no disk check)

### 5.2 `large_history_file` fixture

**File:** `tests/unit/test_consolidate_logs_large_file.py`

**Signature:**

```python
@pytest.fixture
def large_history_file(tmp_path: Path) -> Path:
    """Create a history file with 500 numbered lines. Actual size ~5KB.
    Caller must use mock_file_size to make it appear >50MB."""
    ...
```

**Input Example:**

```python
# Called by pytest automatically via fixture injection
path = large_history_file  # tmp_path / "history.log"
```

**Output Example:**

```python
# Returns: PosixPath('/tmp/pytest-xxx/test_yyy/history.log')
# File content:
# line_0001
# line_0002
# ...
# line_0500
```

**Edge Cases:**
- Always creates exactly 500 lines for deterministic integrity checking

### 5.3 `history_dir_with_rotated_files` fixture

**File:** `tests/unit/test_consolidate_logs_large_file.py`

**Signature:**

```python
@pytest.fixture
def history_dir_with_rotated_files(tmp_path: Path) -> Path:
    """Create a directory with active log + pre-existing .1 and .2 backup files.
    Returns the directory path."""
    ...
```

**Input Example:**

```python
# Called by pytest automatically
dir_path = history_dir_with_rotated_files
```

**Output Example:**

```python
# Returns: PosixPath('/tmp/pytest-xxx/test_yyy/')
# Contains:
#   history.log      (500 lines: line_0001..line_0500)
#   history.log.1    (300 lines: old_line_0001..old_line_0300)
#   history.log.2    (200 lines: older_line_0001..older_line_0200)
```

### 5.4 `small_history_file` fixture

**File:** `tests/unit/test_consolidate_logs_large_file.py`

**Signature:**

```python
@pytest.fixture
def small_history_file(tmp_path: Path) -> Path:
    """Create a small history file (100 lines, well under any threshold).
    No size mocking needed — this is a control case."""
    ...
```

**Input Example:**

```python
path = small_history_file
```

**Output Example:**

```python
# Returns: PosixPath('/tmp/pytest-xxx/test_yyy/history.log')
# 100 lines, actual size ~700 bytes
```

### 5.5 Test Functions

All test functions follow this pattern:

**Signature pattern:**

```python
def test_NAME(tmp_path: Path, mock_file_size, ...fixtures...) -> None:
    """Docstring describes what is being tested."""
    ...
```

No return values — tests assert or raise.

## 6. Change Instructions

### 6.1 `tests/conftest.py` (Modify)

**Change 1:** Add `os` import at top of file

```diff
 """Pytest configuration for test suite."""

 import sys
+import os

 from pathlib import Path

 import pytest
```

**Change 2:** Add `mock_file_size` fixture after the `tools_dir` line (at end of file)

```diff
 tools_dir = Path(__file__).parent.parent / "tools"
+
+
+@pytest.fixture
+def mock_file_size(monkeypatch):
+    """Factory fixture that patches os.path.getsize to return specified sizes for given paths.
+
+    Usage:
+        mock_file_size({"/path/to/file.log": 52_428_800})
+
+    Files not in the map delegate to the real os.path.getsize.
+    """
+    _original_getsize = os.path.getsize
+
+    def _mock(size_map: dict[str, int]) -> None:
+        def _patched_getsize(path):
+            str_path = str(path)
+            if str_path in size_map:
+                return size_map[str_path]
+            return _original_getsize(str_path)
+
+        monkeypatch.setattr("os.path.getsize", _patched_getsize)
+
+    return _mock
```

> **IMPORTANT:** If the production `consolidate_logs.py` uses `Path.stat().st_size` instead of `os.path.getsize`, the monkeypatch target must change. In that case, patch `pathlib.Path.stat` to return a mock `os.stat_result` with the desired `st_size`. See Section 10.1 for the alternative patching approach. The developer MUST check `consolidate_logs.py` source before implementing.

### 6.2 `tests/unit/test_consolidate_logs_large_file.py` (Add)

**Complete file contents:**

```python
"""Unit tests for large-file consolidation and log rotation in consolidate_logs.py.

Issue #437: Closes test gap identified in #57.

Tests verify:
- Files >50MB trigger log rotation
- Log rotation numbering cascade (.1 → .2 → .3)
- No data loss during rotation
- Boundary conditions (exactly 50MB)
- Error handling (permissions, disk full)
- No actual large files created on disk (monkeypatch only)
- All operations confined to tmp_path
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

# IMPORTANT: Replace this import with the actual module path and function name
# after reading consolidate_logs.py source code.
# Possible patterns:
#   from assemblyzero.consolidate_logs import consolidate_logs
#   from tools.consolidate_logs import consolidate_logs
#   from consolidate_logs import consolidate
# The developer MUST verify the actual import path.
from CONSOLIDATE_MODULE import consolidate_function  # PLACEHOLDER — REPLACE


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

THRESHOLD_50MB = 52_428_800  # 50 * 1024 * 1024
ABOVE_THRESHOLD = 52_428_801  # 1 byte over 50MB
BELOW_THRESHOLD = 10_485_760  # 10MB
LINE_COUNT = 500  # Number of lines in test files
MAX_TEST_FILE_SIZE = 1_048_576  # 1MB — no real file should exceed this


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def large_history_file(tmp_path: Path) -> Path:
    """Create a history file with LINE_COUNT numbered lines.

    Actual file size is ~5KB. Caller must use mock_file_size to simulate >50MB.

    Returns:
        Path to the created history.log file.
    """
    history_file = tmp_path / "history.log"
    lines = [f"line_{i:04d}\n" for i in range(1, LINE_COUNT + 1)]
    history_file.write_text("".join(lines))
    return history_file


@pytest.fixture
def small_history_file(tmp_path: Path) -> Path:
    """Create a small history file with 100 numbered lines.

    Well under any rotation threshold. No mocking needed.

    Returns:
        Path to the created history.log file.
    """
    history_file = tmp_path / "history.log"
    lines = [f"line_{i:04d}\n" for i in range(1, 101)]
    history_file.write_text("".join(lines))
    return history_file


@pytest.fixture
def history_dir_with_rotated_files(tmp_path: Path) -> Path:
    """Create a directory with an active log and pre-existing .1 and .2 backups.

    Active file: 500 lines (line_0001..line_0500)
    Backup .1:   300 lines (old_line_0001..old_line_0300)
    Backup .2:   200 lines (older_line_0001..older_line_0200)

    Returns:
        Path to the tmp_path directory containing the files.
    """
    # Active file
    active = tmp_path / "history.log"
    active.write_text("".join(f"line_{i:04d}\n" for i in range(1, 501)))

    # Pre-existing backup .1
    backup1 = tmp_path / "history.log.1"
    backup1.write_text("".join(f"old_line_{i:04d}\n" for i in range(1, 301)))

    # Pre-existing backup .2
    backup2 = tmp_path / "history.log.2"
    backup2.write_text("".join(f"older_line_{i:04d}\n" for i in range(1, 201)))

    return tmp_path


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _read_all_lines(path: Path) -> list[str]:
    """Read all non-empty lines from a file."""
    if not path.exists():
        return []
    return [line for line in path.read_text().splitlines() if line.strip()]


def _collect_all_lines_in_dir(directory: Path, base_name: str = "history.log") -> list[str]:
    """Collect all lines from the active file and all its rotated backups.

    Searches for base_name, base_name.1, base_name.2, etc.
    """
    all_lines = []
    # Active file
    active = directory / base_name
    all_lines.extend(_read_all_lines(active))

    # Rotated backups
    i = 1
    while True:
        backup = directory / f"{base_name}.{i}"
        if not backup.exists():
            break
        all_lines.extend(_read_all_lines(backup))
        i += 1

    return all_lines


# ---------------------------------------------------------------------------
# Test: Size threshold detection (T010, T020, T030)
# ---------------------------------------------------------------------------


class TestSizeThresholdDetection:
    """Tests for detecting files that exceed the 50MB rotation threshold."""

    def test_consolidate_detects_file_exceeding_threshold(
        self, tmp_path: Path, large_history_file: Path, mock_file_size
    ) -> None:
        """T010: File >50MB triggers rotation. Backup .1 should exist after."""
        mock_file_size({str(large_history_file): ABOVE_THRESHOLD})

        # PLACEHOLDER: Replace with actual function call.
        # The function may take a directory path, a file path, or a config dict.
        # Example possibilities:
        #   consolidate_function(directory=tmp_path)
        #   consolidate_function(large_history_file)
        #   consolidate_function(str(tmp_path))
        consolidate_function(tmp_path)  # REPLACE with actual call

        backup = tmp_path / "history.log.1"  # REPLACE suffix if timestamps are used
        assert backup.exists(), "Rotation should create a .1 backup file"

    def test_consolidate_skips_file_below_threshold(
        self, tmp_path: Path, small_history_file: Path, mock_file_size
    ) -> None:
        """T020: File <50MB is consolidated normally without rotation."""
        mock_file_size({str(small_history_file): BELOW_THRESHOLD})

        consolidate_function(tmp_path)  # REPLACE with actual call

        backup = tmp_path / "history.log.1"
        assert not backup.exists(), "No rotation should occur for small files"
        assert small_history_file.exists(), "Original file should remain"

    def test_consolidate_exact_threshold_boundary(
        self, tmp_path: Path, large_history_file: Path, mock_file_size
    ) -> None:
        """T030: Behavior at exactly 50MB. Verify consistent threshold semantics."""
        mock_file_size({str(large_history_file): THRESHOLD_50MB})

        consolidate_function(tmp_path)  # REPLACE with actual call

        # The assertion depends on whether threshold is > or >=.
        # REPLACE: After reading production code, assert the correct behavior.
        # If threshold is >=: backup should exist
        # If threshold is >:  backup should NOT exist
        backup = tmp_path / "history.log.1"
        # Assert one of:
        #   assert backup.exists(), "At exactly 50MB, rotation should trigger (>= threshold)"
        #   assert not backup.exists(), "At exactly 50MB, rotation should NOT trigger (> threshold)"
        # PLACEHOLDER — developer must verify which is correct
        assert True, "REPLACE: Check production code for >= vs > threshold semantics"


# ---------------------------------------------------------------------------
# Test: Log rotation mechanics (T040, T050, T060, T070)
# ---------------------------------------------------------------------------


class TestLogRotation:
    """Tests for log rotation numbering and content integrity."""

    def test_rotation_creates_numbered_backup(
        self, tmp_path: Path, large_history_file: Path, mock_file_size
    ) -> None:
        """T040: Rotation renames current file to .1 suffix."""
        original_content = large_history_file.read_text()
        mock_file_size({str(large_history_file): ABOVE_THRESHOLD})

        consolidate_function(tmp_path)  # REPLACE with actual call

        backup = tmp_path / "history.log.1"
        assert backup.exists(), "Backup .1 should be created"
        assert backup.read_text() == original_content, (
            "Backup .1 should contain the original file content"
        )

    def test_rotation_increments_existing_backups(
        self, history_dir_with_rotated_files: Path, mock_file_size
    ) -> None:
        """T050: Existing .1 → .2, .2 → .3 cascade before creating new .1."""
        dir_path = history_dir_with_rotated_files
        active_file = dir_path / "history.log"

        # Capture pre-rotation content
        original_active_content = active_file.read_text()
        original_backup1_content = (dir_path / "history.log.1").read_text()
        original_backup2_content = (dir_path / "history.log.2").read_text()

        mock_file_size({str(active_file): ABOVE_THRESHOLD})

        consolidate_function(dir_path)  # REPLACE with actual call

        # After rotation:
        # - active → .1 (new .1 has original active content)
        # - old .1 → .2 (new .2 has original .1 content)
        # - old .2 → .3 (new .3 has original .2 content)
        assert (dir_path / "history.log.1").read_text() == original_active_content
        assert (dir_path / "history.log.2").read_text() == original_backup1_content
        assert (dir_path / "history.log.3").exists()
        assert (dir_path / "history.log.3").read_text() == original_backup2_content

    def test_rotation_preserves_content_integrity(
        self, tmp_path: Path, large_history_file: Path, mock_file_size
    ) -> None:
        """T060: No data loss during rotation — all lines accounted for."""
        original_lines = set(_read_all_lines(large_history_file))
        assert len(original_lines) == LINE_COUNT, "Fixture should create exactly 500 lines"

        mock_file_size({str(large_history_file): ABOVE_THRESHOLD})

        consolidate_function(tmp_path)  # REPLACE with actual call

        all_lines_after = set(_collect_all_lines_in_dir(tmp_path))
        assert original_lines.issubset(all_lines_after), (
            f"Missing lines after rotation: {original_lines - all_lines_after}"
        )

    def test_rotation_creates_fresh_active_file(
        self, tmp_path: Path, large_history_file: Path, mock_file_size
    ) -> None:
        """T070: After rotation, active log file exists and is empty/small."""
        mock_file_size({str(large_history_file): ABOVE_THRESHOLD})

        consolidate_function(tmp_path)  # REPLACE with actual call

        active = tmp_path / "history.log"
        assert active.exists(), "Active file should exist after rotation"
        assert active.stat().st_size < 1024, (
            f"Active file should be empty or header-only after rotation, "
            f"but was {active.stat().st_size} bytes"
        )


# ---------------------------------------------------------------------------
# Test: Consolidation with large files (T080, T090)
# ---------------------------------------------------------------------------


class TestConsolidationWithLargeFiles:
    """Tests for consolidation behavior when combined with rotation triggers."""

    def test_consolidate_large_file_with_multiple_sources(
        self, tmp_path: Path, mock_file_size
    ) -> None:
        """T080: Consolidate multiple log sources when target exceeds threshold."""
        # Create multiple source files
        source1 = tmp_path / "source1.log"
        source1.write_text("".join(f"src1_line_{i:04d}\n" for i in range(1, 201)))

        source2 = tmp_path / "source2.log"
        source2.write_text("".join(f"src2_line_{i:04d}\n" for i in range(1, 201)))

        source3 = tmp_path / "source3.log"
        source3.write_text("".join(f"src3_line_{i:04d}\n" for i in range(1, 101)))

        # Create a target history file that will appear large after consolidation
        history = tmp_path / "history.log"
        history.write_text("".join(f"existing_line_{i:04d}\n" for i in range(1, 101)))

        # Mock the history file as exceeding threshold
        mock_file_size({str(history): ABOVE_THRESHOLD})

        # Collect all original lines
        all_original_lines = set()
        for f in [source1, source2, source3, history]:
            all_original_lines.update(_read_all_lines(f))

        consolidate_function(tmp_path)  # REPLACE with actual call

        # Verify all content preserved somewhere in the directory
        all_final_lines = set(_collect_all_lines_in_dir(tmp_path))
        # At minimum, the history lines should be preserved in rotation
        history_originals = {f"existing_line_{i:04d}" for i in range(1, 101)}
        assert history_originals.issubset(all_final_lines), (
            "Original history lines should be preserved after rotation"
        )

    def test_consolidate_handles_concurrent_rotation_gracefully(
        self, history_dir_with_rotated_files: Path, mock_file_size
    ) -> None:
        """T090: No crash if rotated file already exists (idempotency)."""
        dir_path = history_dir_with_rotated_files
        active_file = dir_path / "history.log"
        mock_file_size({str(active_file): ABOVE_THRESHOLD})

        # First rotation
        consolidate_function(dir_path)  # REPLACE with actual call

        # Mock the new active file as large again to trigger second rotation
        mock_file_size({str(active_file): ABOVE_THRESHOLD})

        # Second rotation — should not crash even with existing backups
        consolidate_function(dir_path)  # REPLACE with actual call

        # Verify no crash occurred and files exist
        assert active_file.exists() or (dir_path / "history.log.1").exists(), (
            "At least active file or backup should exist after double rotation"
        )


# ---------------------------------------------------------------------------
# Test: Error handling (T100, T110)
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Tests for graceful error handling during rotation."""

    def test_consolidate_large_file_read_only_filesystem(
        self, tmp_path: Path, large_history_file: Path, mock_file_size
    ) -> None:
        """T100: Graceful error when rotation fails due to permissions."""
        mock_file_size({str(large_history_file): ABOVE_THRESHOLD})

        # Make directory read-only to prevent rotation writes
        original_mode = tmp_path.stat().st_mode
        try:
            tmp_path.chmod(0o444)

            # REPLACE: The production code may raise a specific exception,
            # return an error code, or log an error. Adjust assertion accordingly.
            # Options:
            #   with pytest.raises(PermissionError):
            #   with pytest.raises(OSError):
            #   result = consolidate_function(tmp_path); assert result.error
            with pytest.raises((PermissionError, OSError)):
                consolidate_function(tmp_path)  # REPLACE with actual call

        finally:
            # Restore permissions for cleanup
            tmp_path.chmod(original_mode)

        # Verify original file is still intact
        assert large_history_file.exists(), "Original file should survive permission error"

    def test_consolidate_large_file_disk_full_simulation(
        self, tmp_path: Path, large_history_file: Path, mock_file_size
    ) -> None:
        """T110: Graceful error when disk is full during rotation."""
        mock_file_size({str(large_history_file): ABOVE_THRESHOLD})

        original_content = large_history_file.read_text()

        # Simulate disk full by patching shutil.move (or os.rename) to raise OSError
        # REPLACE: Patch the exact function used by production code for file rotation.
        # If production uses shutil.move:
        with patch("shutil.move", side_effect=OSError("No space left on device")):
            # REPLACE: Adjust exception type based on production error handling
            with pytest.raises(OSError):
                consolidate_function(tmp_path)  # REPLACE with actual call

        # Verify original file content is intact
        assert large_history_file.exists(), "Original file should survive disk full error"
        assert large_history_file.read_text() == original_content, (
            "Original file content should be unchanged after disk full error"
        )


# ---------------------------------------------------------------------------
# Test: Non-functional constraints (T120, T130)
# ---------------------------------------------------------------------------


class TestNonFunctionalConstraints:
    """Tests enforcing performance and isolation requirements."""

    def test_no_actual_large_files_created(
        self, tmp_path: Path, large_history_file: Path, mock_file_size
    ) -> None:
        """T120: All test files on disk are under 1MB — no real 50MB allocations.

        This test verifies that monkeypatching is working correctly and that
        no test accidentally creates real large files.
        """
        mock_file_size({str(large_history_file): ABOVE_THRESHOLD})

        consolidate_function(tmp_path)  # REPLACE with actual call

        # Walk all files in tmp_path and assert none exceed 1MB
        large_files = []
        for file_path in tmp_path.rglob("*"):
            if file_path.is_file():
                real_size = file_path.stat().st_size  # Real size, not mocked
                if real_size > MAX_TEST_FILE_SIZE:
                    large_files.append((str(file_path), real_size))

        assert not large_files, (
            f"Found files exceeding {MAX_TEST_FILE_SIZE} bytes on disk "
            f"(monkeypatch may not be working): {large_files}"
        )

    def test_operations_confined_to_tmp_path(
        self, tmp_path: Path, large_history_file: Path, mock_file_size
    ) -> None:
        """T130: Consolidation writes only within tmp_path, no leakage.

        Snapshots the parent directory before and after to detect any
        files written outside the test's tmp_path.
        """
        parent = tmp_path.parent

        # Snapshot parent directory contents before test
        before = set()
        for item in parent.iterdir():
            if item != tmp_path:
                before.add(item.name)

        mock_file_size({str(large_history_file): ABOVE_THRESHOLD})

        consolidate_function(tmp_path)  # REPLACE with actual call

        # Snapshot parent directory contents after test
        after = set()
        for item in parent.iterdir():
            if item != tmp_path:
                after.add(item.name)

        new_items = after - before
        assert not new_items, (
            f"Files written outside tmp_path detected: {new_items}"
        )
```

> **PLACEHOLDER REPLACEMENTS REQUIRED:**
>
> Before this file can be committed, the developer MUST:
>
> 1. **Line 31:** Replace `from CONSOLIDATE_MODULE import consolidate_function` with the actual import. Find it by running:
>    ```bash
>    find . -name "consolidate_logs.py" -not -path "*/test*"
>    ```
>    Then inspect the file for the public function name.
>
> 2. **All `consolidate_function(tmp_path)` calls:** Replace with the actual function invocation. The production function may require different arguments (e.g., a config object, a file path instead of directory, keyword arguments).
>
> 3. **Rotation suffix pattern:** If the production code uses timestamp suffixes (e.g., `history.log.2026-02-25`) instead of numeric (`.1`, `.2`), update all assertions that check for `.1`, `.2`, `.3` files.
>
> 4. **`mock_file_size` target:** If production code uses `Path.stat().st_size` instead of `os.path.getsize()`, update the fixture in `conftest.py`. See Section 10.1.
>
> 5. **Error handling pattern:** If production code doesn't raise exceptions but returns error codes or logs errors, update T100 and T110 assertions accordingly.
>
> 6. **Threshold boundary (T030):** Replace the placeholder assertion with the correct one after verifying `>` vs `>=` in production code.

## 7. Pattern References

### 7.1 Existing Test Structure Pattern

**File:** `tests/test_integration_workflow.py` (lines 1-80)

```python
# Reference this file for the overall test structure convention:
# - Module docstring describing what's being tested
# - Imports grouped (stdlib, third-party, local)
# - pytest fixtures for test setup
# - Test functions with descriptive names and docstrings
# - Assertions with descriptive failure messages
```

**Relevance:** All existing workflow tests follow this pattern. The new test file should use the same structure conventions (imports, docstrings, assertion messages).

### 7.2 Unit Test Directory Pattern

**File:** `tests/unit/test_implementation_spec_workflow.py` (lines 1-80)

```python
# Reference this file for unit test conventions in the tests/unit/ directory:
# - Located under tests/unit/
# - Uses pytest fixtures from conftest.py
# - Tests are function-scoped (independent)
```

**Relevance:** Confirms the `tests/unit/` directory convention and that shared fixtures from `conftest.py` are importable by tests in subdirectories.

### 7.3 Conftest Fixture Pattern

**File:** `tests/conftest.py` (lines 1-11)

```python
"""Pytest configuration for test suite."""

import sys

from pathlib import Path

import pytest

def pytest_configure(config):
    """Configure pytest markers."""
    ...

tools_dir = Path(__file__).parent.parent / "tools"
```

**Relevance:** Shows the existing `conftest.py` structure. New fixtures should be added after the existing code, following the same style (docstrings, type hints).

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from __future__ import annotations` | stdlib | `test_consolidate_logs_large_file.py` |
| `import os` | stdlib | `conftest.py`, `test_consolidate_logs_large_file.py` |
| `import shutil` | stdlib | `test_consolidate_logs_large_file.py` |
| `from pathlib import Path` | stdlib | Both files |
| `from unittest.mock import patch` | stdlib | `test_consolidate_logs_large_file.py` |
| `import pytest` | third-party (installed) | Both files |
| `from CONSOLIDATE_MODULE import consolidate_function` | internal | `test_consolidate_logs_large_file.py` — **MUST BE RESOLVED** |

**New Dependencies:** None. All imports are stdlib or already in `pyproject.toml` (`pytest`).

## 9. Test Mapping

| Test ID | Tests Function/Behavior | Input | Expected Output |
|---------|------------------------|-------|-----------------|
| T010 | `test_consolidate_detects_file_exceeding_threshold` | File with mocked size 52_428_801 | Backup `.1` exists, active file < threshold |
| T020 | `test_consolidate_skips_file_below_threshold` | File with mocked size 10_485_760 | No backup files, original file unchanged |
| T030 | `test_consolidate_exact_threshold_boundary` | File with mocked size 52_428_800 | Consistent with `>` or `>=` semantics |
| T040 | `test_rotation_creates_numbered_backup` | Large file, no existing backups | `history.log.1` exists with original content |
| T050 | `test_rotation_increments_existing_backups` | Large file + `.1` + `.2` | `.1`→`.2`→`.3` cascade, new `.1` = old active |
| T060 | `test_rotation_preserves_content_integrity` | 500 numbered lines, trigger rotation | All 500 lines present across all files |
| T070 | `test_rotation_creates_fresh_active_file` | Large file triggers rotation | Active file exists, size < 1024 bytes |
| T080 | `test_consolidate_large_file_with_multiple_sources` | 3 source files + large history | All source content preserved |
| T090 | `test_consolidate_handles_concurrent_rotation_gracefully` | Large file + existing backups, rotate twice | No crash, files exist |
| T100 | `test_consolidate_large_file_read_only_filesystem` | Read-only directory | `PermissionError` or `OSError` raised, original intact |
| T110 | `test_consolidate_large_file_disk_full_simulation` | `shutil.move` raises `OSError` | `OSError` raised, original file intact |
| T120 | `test_no_actual_large_files_created` | Post-rotation tmp_path walk | All files < 1MB on disk |
| T130 | `test_operations_confined_to_tmp_path` | Parent dir snapshot before/after | No new files outside tmp_path |

## 10. Implementation Notes

### 10.1 Critical: Determine Monkeypatch Target

The **most important implementation step** is determining how `consolidate_logs.py` checks file size. The monkeypatch must intercept the exact call.

**Scenario A:** Production uses `os.path.getsize(path)`

```python
# In conftest.py, patch as shown in Section 6.1
monkeypatch.setattr("os.path.getsize", _patched_getsize)
```

**Scenario B:** Production uses `from os.path import getsize` (local binding)

```python
# Must patch at the module level where it's imported
monkeypatch.setattr("CONSOLIDATE_MODULE.getsize", _patched_getsize)
```

**Scenario C:** Production uses `Path(file).stat().st_size`

```python
# Must patch pathlib.Path.stat to return a mock stat_result
import os as _os

_original_stat = Path.stat

def _patched_stat(self, *args, **kwargs):
    str_path = str(self)
    if str_path in size_map:
        real_stat = _original_stat(self, *args, **kwargs)
        # Create a new stat_result with modified st_size
        return _os.stat_result((
            real_stat.st_mode, real_stat.st_ino, real_stat.st_dev,
            real_stat.st_nlink, real_stat.st_uid, real_stat.st_gid,
            size_map[str_path],  # st_size overridden
            real_stat.st_atime, real_stat.st_mtime, real_stat.st_ctime,
        ))
    return _original_stat(self, *args, **kwargs)

monkeypatch.setattr("pathlib.Path.stat", _patched_stat)
```

**Scenario D:** Production uses `os.stat(path).st_size`

```python
# Patch os.stat similarly to Scenario C
monkeypatch.setattr("os.stat", _patched_os_stat)
```

**Developer Action:** Run this command to determine the approach:

```bash
grep -n "getsize\|\.stat()\|st_size\|os\.stat" $(find . -name "consolidate_logs.py" -not -path "*/test*")
```

### 10.2 Error Handling Convention

Tests in T100 and T110 assume the production code **raises exceptions** on failure. If the production code instead:

- **Returns an error code:** Change `pytest.raises(...)` to `result = consolidate_function(...); assert result.error` or similar
- **Logs and continues:** Change to capture log output with `caplog` fixture and assert error messages
- **Silently ignores:** These tests should still verify the original file is intact (the "file intact" assertions remain valid regardless)

### 10.3 Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| `THRESHOLD_50MB` | `52_428_800` | 50 * 1024 * 1024 — the assumed rotation threshold |
| `ABOVE_THRESHOLD` | `52_428_801` | 1 byte above threshold to unambiguously trigger rotation |
| `BELOW_THRESHOLD` | `10_485_760` | 10MB — clearly below threshold, no ambiguity |
| `LINE_COUNT` | `500` | Enough lines to verify integrity without being excessive |
| `MAX_TEST_FILE_SIZE` | `1_048_576` | 1MB — safety limit ensuring no real large files created |

### 10.4 Production Code Not Found Scenario

If `consolidate_logs.py` does not exist or has no rotation logic (the #57 TODO was never implemented):

1. The tests will fail at import time (module not found) or at assertion time (rotation never triggered)
2. This is the expected "RED" phase of TDD
3. The developer should add a comment on issue #437 noting: "Production rotation logic not yet implemented — tests are written and RED, awaiting implementation"
4. Do NOT implement the production rotation logic in this PR — that is a separate scope

### 10.5 Test Execution Verification

After implementation, verify with:

```bash
# All tests pass
poetry run pytest tests/unit/test_consolidate_logs_large_file.py -v

# Time budget: <5 seconds total
poetry run pytest tests/unit/test_consolidate_logs_large_file.py -v --durations=0

# Coverage of consolidate_logs module
poetry run pytest tests/unit/test_consolidate_logs_large_file.py -v --cov=assemblyzero --cov-report=term-missing

# Verify conftest.py changes don't break existing tests
poetry run pytest tests/ -v --co  # Dry-run collection — should find all tests
```

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3) — `tests/conftest.py` shown
- [x] Every data structure has a concrete JSON/YAML example (Section 4) — 3 structures with examples
- [x] Every function has input/output examples with realistic values (Section 5) — 4 fixtures + test pattern
- [x] Change instructions are diff-level specific (Section 6) — diffs for conftest.py, full file for test file
- [x] Pattern references include file:line and are verified to exist (Section 7) — 3 patterns referenced
- [x] All imports are listed and verified (Section 8) — 7 imports listed
- [x] Test mapping covers all LLD test scenarios (Section 9) — all 13 scenarios mapped

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #437 |
| Verdict | DRAFT |
| Date | 2026-02-25 |
| Iterations | 1 |
| Finalized | — |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #437 |
| Verdict | APPROVED |
| Date | 2026-02-26 |
| Iterations | 0 |
| Finalized | 2026-02-26T02:35:05Z |

### Review Feedback Summary

Approved with suggestions:
- **Dynamic Import Resolution**: The spec explicitly relies on the developer/agent to perform a `grep` or read of `consolidate_logs.py` to resolve `CONSOLIDATE_MODULE` and `consolidate_function`. Ensure this step is performed **before** writing the test file to avoid immediate import errors.
- **Rotation Suffix Check**: As noted in the spec, if the production code uses timestamped backups (e.g., `history.log.2025-01-01`), the assertions checking for `history.log.1` wil...


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
    mock_lineage/
    mock_repo/
      src/
    scout/
    scraper/
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

## Existing File Contents

The file currently contains:

```python
"""Pytest configuration for test suite."""

import os
import sys
from pathlib import Path

import pytest

# Ensure tools directory is importable
tools_dir = Path(__file__).parent.parent / "tools"
if str(tools_dir.parent) not in sys.path:
    sys.path.insert(0, str(tools_dir.parent))


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests (deselect with '-m \"not integration\"')"
    )
    config.addinivalue_line(
        "markers",
        "e2e: marks tests as end-to-end tests (require full environment)",
    )


@pytest.fixture
def mock_file_size(monkeypatch):
    """Factory fixture that patches os.path.getsize to return specified sizes for given paths.

    Usage:
        mock_file_size({"/path/to/file.log": 52_428_800})

    Files not in the map delegate to the real os.path.getsize.
    """
    _original_getsize = os.path.getsize

    def _mock(size_map: dict[str, int]) -> None:
        def _patched_getsize(path):
            str_path = str(path)
            if str_path in size_map:
                return size_map[str_path]
            return _original_getsize(str_path)

        monkeypatch.setattr("os.path.getsize", _patched_getsize)

    return _mock
```

Modify this file according to the LLD specification.

## Tests That Must Pass

```python
# From C:\Users\mcwiz\Projects\AssemblyZero\tests\unit\test_consolidate_logs_large_file.py
"""Unit tests for large-file consolidation and log rotation in consolidate_logs.py.

Issue #437: Closes test gap identified in #57.

Tests verify:
- Files >50MB trigger log rotation
- Log rotation numbering cascade (.1 → .2 → .3)
- No data loss during rotation
- Boundary conditions (exactly 50MB)
- Error handling (permissions, disk full)
- No actual large files created on disk (monkeypatch only)
- All operations confined to tmp_path

NOTE: Log rotation is not yet implemented in consolidate_logs.py (see TODO on
line 123 of tools/consolidate_logs.py). These tests are in the TDD RED phase —
they define the expected behavior for when rotation is implemented. Tests that
assert rotation behavior will fail until the production code is updated.
"""

from __future__ import annotations

import json
import os
import platform
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.consolidate_logs import consolidate

# The history file lives at repo_root / DEFAULT_AUDIT_LOG_PATH.
# Import the constant to stay in sync with production code.
from assemblyzero.core.config import DEFAULT_AUDIT_LOG_PATH, LOGS_ACTIVE_DIR


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

THRESHOLD_50MB = 52_428_800  # 50 * 1024 * 1024
ABOVE_THRESHOLD = 52_428_801  # 1 byte over 50MB
BELOW_THRESHOLD = 10_485_760  # 10MB
LINE_COUNT = 500  # Number of entries in large test files
MAX_TEST_FILE_SIZE = 1_048_576  # 1MB — no real file should exceed this


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(index: int, prefix: str = "line") -> dict:
    """Create a single JSONL entry with a deterministic timestamp."""
    return {
        "timestamp": f"2026-02-25T{index // 3600:02d}:{(index % 3600) // 60:02d}:{index % 60:02d}Z",
        "event": "test",
        "id": f"{prefix}_{index:04d}",
    }


def _make_jsonl(entries: list[dict]) -> str:
    """Serialize a list of dicts to JSONL text."""
    return "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries)


def _read_jsonl_entries(path: Path) -> list[dict]:
    """Read all valid JSONL entries from a file."""
    if not path.exists():
        return []
    entries = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if raw:
            entries.append(json.loads(raw))
    return entries


def _collect_all_entries(logs_dir: Path) -> list[dict]:
    """Collect entries from history file and all its rotated backups.

    Searches for review_history.jsonl, review_history.jsonl.1, .2, etc.
    """
    all_entries: list[dict] = []
    history = logs_dir / DEFAULT_AUDIT_LOG_PATH.name
    all_entries.extend(_read_jsonl_entries(history))

    i = 1
    while True:
        backup = logs_dir / f"{DEFAULT_AUDIT_LOG_PATH.name}.{i}"
        if not backup.exists():
            break
        all_entries.extend(_read_jsonl_entries(backup))
        i += 1

    return all_entries


def _entry_ids(entries: list[dict]) -> set[str]:
    """Extract the set of 'id' values from entries."""
    return {e["id"] for e in entries}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def repo_with_logs(tmp_path: Path) -> Path:
    """Set up minimal repo structure: logs/ and logs/active/ directories.

    Returns tmp_path acting as repo_root.
    """
    logs_dir = tmp_path / DEFAULT_AUDIT_LOG_PATH.parent
    logs_dir.mkdir(parents=True)
    active_dir = tmp_path / LOGS_ACTIVE_DIR
    active_dir.mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def large_history_file(repo_with_logs: Path) -> Path:
    """Create a history file with LINE_COUNT JSONL entries.

    Actual file size is ~40KB. Caller must use mock_file_size to simulate >50MB.
    Also creates a minimal shard so consolidate() processes something.

    Returns:
        Path to the created review_history.jsonl file.
    """
    history_file = repo_with_logs / DEFAULT_AUDIT_LOG_PATH
    entries = [_make_entry(i) for i in range(1, LINE_COUNT + 1)]
    history_file.write_text(_make_jsonl(entries), encoding="utf-8")

    # Create a shard so consolidation runs
    shard = repo_with_logs / LOGS_ACTIVE_DIR / "shard_001.jsonl"
    shard.write_text(_make_jsonl([_make_entry(9999, "shard")]), encoding="utf-8")

    return history_file


@pytest.fixture
def small_history_file(repo_with_logs: Path) -> Path:
    """Create a small history file with 100 entries, well under any threshold.

    No size mocking needed — this is a control case.

    Returns:
        Path to the created review_history.jsonl file.
    """
    history_file = repo_with_logs / DEFAULT_AUDIT_LOG_PATH
    entries = [_make_entry(i) for i in range(1, 101)]
    history_file.write_text(_make_jsonl(entries), encoding="utf-8")

    # Create a shard so consolidation runs
    shard = repo_with_logs / LOGS_ACTIVE_DIR / "shard_001.jsonl"
    shard.write_text(_make_jsonl([_make_entry(9999, "shard")]), encoding="utf-8")

    return history_file


@pytest.fixture
def history_dir_with_rotated_files(repo_with_logs: Path) -> Path:
    """Create a repo with active history + pre-existing .1 and .2 backup files.

    Active:    500 entries (line_0001..line_0500)
    Backup .1: 300 entries (old_0001..old_0300)
    Backup .2: 200 entries (older_0001..older_0200)

    Returns:
        repo_root path (tmp_path).
    """
    logs_dir = repo_with_logs / DEFAULT_AUDIT_LOG_PATH.parent

    # Active history
    history = logs_dir / DEFAULT_AUDIT_LOG_PATH.name
    history.write_text(
        _make_jsonl([_make_entry(i) for i in range(1, 501)]),
        encoding="utf-8",
    )

    # Pre-existing backup .1
    backup1 = logs_dir / f"{DEFAULT_AUDIT_LOG_PATH.name}.1"
    backup1.write_text(
        _make_jsonl([_make_entry(i, "old") for i in range(1, 301)]),
        encoding="utf-8",
    )

    # Pre-existing backup .2
    backup2 = logs_dir / f"{DEFAULT_AUDIT_LOG_PATH.name}.2"
    backup2.write_text(
        _make_jsonl([_make_entry(i, "older") for i in range(1, 201)]),
        encoding="utf-8",
    )

    # Create a shard so consolidation runs
    shard = repo_with_logs / LOGS_ACTIVE_DIR / "shard_001.jsonl"
    shard.write_text(_make_jsonl([_make_entry(9999, "shard")]), encoding="utf-8")

    return repo_with_logs


# ---------------------------------------------------------------------------
# Test: Size threshold detection (T010, T020, T030)
# ---------------------------------------------------------------------------


class TestSizeThresholdDetection:
    """Tests for detecting files that exceed the 50MB rotation threshold."""

    def test_consolidate_detects_file_exceeding_threshold(
        self, repo_with_logs: Path, large_history_file: Path, mock_file_size
    ) -> None:
        """T010: File >50MB triggers rotation. Backup .1 should exist after."""
        mock_file_size({str(large_history_file): ABOVE_THRESHOLD})

        consolidate(repo_with_logs)

        logs_dir = repo_with_logs / DEFAULT_AUDIT_LOG_PATH.parent
        backup = logs_dir / f"{DEFAULT_AUDIT_LOG_PATH.name}.1"
        assert backup.exists(), "Rotation should create a .1 backup file"

    def test_consolidate_skips_file_below_threshold(
        self, repo_with_logs: Path, small_history_file: Path, mock_file_size
    ) -> None:
        """T020: File <50MB is consolidated normally without rotation."""
        mock_file_size({str(small_history_file): BELOW_THRESHOLD})

        consolidate(repo_with_logs)

        logs_dir = repo_with_logs / DEFAULT_AUDIT_LOG_PATH.parent
        backup = logs_dir / f"{DEFAULT_AUDIT_LOG_PATH.name}.1"
        assert not backup.exists(), "No rotation should occur for small files"
        # History file should contain merged entries (original + shard)
        assert (logs_dir / DEFAULT_AUDIT_LOG_PATH.name).exists(), (
            "History file should remain after consolidation"
        )

    def test_consolidate_exact_threshold_boundary(
        self, repo_with_logs: Path, large_history_file: Path, mock_file_size
    ) -> None:
        """T030: Behavior at exactly 50MB. Verify consistent threshold semantics.

        The threshold check should use >= (at exactly 50MB, rotation triggers).
        This assertion must be updated if production code uses strict > instead.
        """
        mock_file_size({str(large_history_file): THRESHOLD_50MB})

        consolidate(repo_with_logs)

        logs_dir = repo_with_logs / DEFAULT_AUDIT_LOG_PATH.parent
        backup = logs_dir / f"{DEFAULT_AUDIT_LOG_PATH.name}.1"
        # Assuming >= semantics: at exactly 50MB, rotation should trigger.
        # If production uses >, change this to `assert not backup.exists()`.
        assert backup.exists(), (
            "At exactly 50MB, rotation should trigger (>= threshold)"
        )


# ---------------------------------------------------------------------------
# Test: Log rotation mechanics (T040, T050, T060, T070)
# ---------------------------------------------------------------------------


class TestLogRotation:
    """Tests for log rotation numbering and content integrity."""

    def test_rotation_creates_numbered_backup(
        self, repo_with_logs: Path, large_history_file: Path, mock_file_size
    ) -> None:
        """T040: Rotation renames current file to .1 suffix."""
        original_entries = _read_jsonl_entries(large_history_file)
        original_ids = _entry_ids(original_entries)
        mock_file_size({str(large_history_file): ABOVE_THRESHOLD})

        consolidate(repo_with_logs)

        logs_dir = repo_with_logs / DEFAULT_AUDIT_LOG_PATH.parent
        backup = logs_dir / f"{DEFAULT_AUDIT_LOG_PATH.name}.1"
        assert backup.exists(), "Backup .1 should be created"
        backup_ids = _entry_ids(_read_jsonl_entries(backup))
        assert original_ids == backup_ids, (
            "Backup .1 should contain exactly the original history entries"
        )

    def test_rotation_increments_existing_backups(
        self, history_dir_with_rotated_files: Path, mock_file_size
    ) -> None:
        """T050: Existing .1 → .2, .2 → .3 cascade before creating new .1."""
        repo_root = history_dir_with_rotated_files
        logs_dir = repo_root / DEFAULT_AUDIT_LOG_PATH.parent
        history_name = DEFAULT_AUDIT_LOG_PATH.name
        active_file = logs_dir / history_name

        # Capture pre-rotation content identifiers
        original_active_ids = _entry_ids(_read_jsonl_entries(active_file))
        original_backup1_ids = _entry_ids(_read_jsonl_entries(logs_dir / f"{history_name}.1"))
        original_backup2_ids = _entry_ids(_read_jsonl_entries(logs_dir / f"{history_name}.2"))

        mock_file_size({str(active_file): ABOVE_THRESHOLD})

        consolidate(repo_root)

        # After rotation:
        # - active → .1 (new .1 has original active entries)
        # - old .1 → .2 (new .2 has original .1 entries)
        # - old .2 → .3 (new .3 has original .2 entries)
        new_backup1_ids = _entry_ids(_read_jsonl_entries(logs_dir / f"{history_name}.1"))
        new_backup2_ids = _entry_ids(_read_jsonl_entries(logs_dir / f"{history_name}.2"))
        backup3 = logs_dir / f"{history_name}.3"

        assert new_backup1_ids == original_active_ids, (
            "New .1 should contain original active history entries"
        )
        assert new_backup2_ids == original_backup1_ids, (
            "New .2 should contain original .1 entries"
        )
        assert backup3.exists(), "Old .2 should cascade to .3"
        new_backup3_ids = _entry_ids(_read_jsonl_entries(backup3))
        assert new_backup3_ids == original_backup2_ids, (
            "New .3 should contain original .2 entries"
        )

    def test_rotation_preserves_content_integrity(
        self, repo_with_logs: Path, large_history_file: Path, mock_file_size
    ) -> None:
        """T060: No data loss during rotation — all entries accounted for."""
        original_ids = _entry_ids(_read_jsonl_entries(large_history_file))
        assert len(original_ids) == LINE_COUNT, (
            f"Fixture should create exactly {LINE_COUNT} entries"
        )

        mock_file_size({str(large_history_file): ABOVE_THRESHOLD})

        consolidate(repo_with_logs)

        logs_dir = repo_with_logs / DEFAULT_AUDIT_LOG_PATH.parent
        all_ids_after = _entry_ids(_collect_all_entries(logs_dir))
        assert original_ids.issubset(all_ids_after), (
            f"Missing entries after rotation: {original_ids - all_ids_after}"
        )

    def test_rotation_creates_fresh_active_file(
        self, repo_with_logs: Path, large_history_file: Path, mock_file_size
    ) -> None:
        """T070: After rotation, active history file exists and is empty/small."""
        mock_file_size({str(large_history_file): ABOVE_THRESHOLD})

        consolidate(repo_with_logs)

        active = repo_with_logs / DEFAULT_AUDIT_LOG_PATH
        assert active.exists(), "Active history file should exist after rotation"
        assert active.stat().st_size < 1024, (
            f"Active file should be empty or header-only after rotation, "
            f"but was {active.stat().st_size} bytes"
        )


# ---------------------------------------------------------------------------
# Test: Consolidation with large files (T080, T090)
# ---------------------------------------------------------------------------


class TestConsolidationWithLargeFiles:
    """Tests for consolidation behavior when combined with rotation triggers."""

    def test_consolidate_large_file_with_multiple_sources(
        self, repo_with_logs: Path, mock_file_size
    ) -> None:
        """T080: Consolidate multiple shard sources when history exceeds threshold."""
        logs_dir = repo_with_logs / DEFAULT_AUDIT_LOG_PATH.parent
        active_dir = repo_with_logs / LOGS_ACTIVE_DIR

        # Create multiple shard files
        shard1 = active_dir / "shard_001.jsonl"
        shard1.write_text(
            _make_jsonl([_make_entry(i, "src1") for i in range(1, 201)]),
            encoding="utf-8",
        )

        shard2 = active_dir / "shard_002.jsonl"
        shard2.write_text(
            _make_jsonl([_make_entry(i, "src2") for i in range(1, 201)]),
            encoding="utf-8",
        )

        shard3 = active_dir / "shard_003.jsonl"
        shard3.write_text(
            _make_jsonl([_make_entry(i, "src3") for i in range(1, 101)]),
            encoding="utf-8",
        )

        # Create a history file that will appear large
        history = logs_dir / DEFAULT_AUDIT_LOG_PATH.name
        history_entries = [_make_entry(i, "existing") for i in range(1, 101)]
        history.write_text(_make_jsonl(history_entries), encoding="utf-8")

        history_original_ids = _entry_ids(history_entries)
        mock_file_size({str(history): ABOVE_THRESHOLD})

        consolidate(repo_with_logs)

        # Verify original history entries preserved somewhere (in rotation backup)
        all_ids_after = _entry_ids(_collect_all_entries(logs_dir))
        assert history_original_ids.issubset(all_ids_after), (
            "Original history entries should be preserved after rotation"
        )

    def test_consolidate_handles_concurrent_rotation_gracefully(
        self, history_dir_with_rotated_files: Path, mock_file_size
    ) -> None:
        """T090: No crash if rotated file already exists (idempotency)."""
        repo_root = history_dir_with_rotated_files
        logs_dir = repo_root / DEFAULT_AUDIT_LOG_PATH.parent
        active_file = logs_dir / DEFAULT_AUDIT_LOG_PATH.name
        active_dir = repo_root / LOGS_ACTIVE_DIR

        mock_file_size({str(active_file): ABOVE_THRESHOLD})

        # First rotation
        consolidate(repo_root)

        # Re-create a shard for second consolidation
        shard = active_dir / "shard_002.jsonl"
        shard.write_text(
            _make_jsonl([_make_entry(9998, "shard2")]),
            encoding="utf-8",
        )

        # Mock the new active file as large again
        mock_file_size({str(active_file): ABOVE_THRESHOLD})

        # Second rotation — should not crash even with existing backups
        consolidate(repo_root)

        # Verify no crash: at least one file should exist
        assert active_file.exists() or (
            logs_dir / f"{DEFAULT_AUDIT_LOG_PATH.name}.1"
        ).exists(), (
            "At least active file or backup should exist after double rotation"
        )


# ---------------------------------------------------------------------------
# Test: Error handling (T100, T110)
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Tests for graceful error handling during rotation."""

    @pytest.mark.skipif(
        platform.system() == "Windows",
        reason="chmod read-only is unreliable on Windows",
    )
    def test_consolidate_large_file_read_only_filesystem(
        self, repo_with_logs: Path, large_history_file: Path, mock_file_size
    ) -> None:
        """T100: Graceful error when rotation fails due to permissions."""
        mock_file_size({str(large_history_file): ABOVE_THRESHOLD})

        logs_dir = repo_with_logs / DEFAULT_AUDIT_LOG_PATH.parent
        original_mode = logs_dir.stat().st_mode
        try:
            logs_dir.chmod(0o444)

            with pytest.raises((PermissionError, OSError)):
                consolidate(repo_with_logs)

        finally:
            # Restore permissions for cleanup
            logs_dir.chmod(original_mode)

        # Verify original file is still intact (permissions restored for read)
        assert large_history_file.exists(), (
            "Original file should survive permission error"
        )

    def test_consolidate_large_file_disk_full_simulation(
        self, repo_with_logs: Path, large_history_file: Path, mock_file_size
    ) -> None:
        """T110: Graceful error when disk is full during rotation."""
        mock_file_size({str(large_history_file): ABOVE_THRESHOLD})

        original_content = large_history_file.read_text(encoding="utf-8")

        # Simulate disk full by patching os.replace — the atomic write mechanism
        # used by consolidate(). When rotation is implemented, this may need to
        # patch the rotation-specific rename/move function instead.
        with patch("os.replace", side_effect=OSError("No space left on device")):
            with pytest.raises(OSError):
                consolidate(repo_with_logs)

        # Verify original file content is intact
        assert large_history_file.exists(), (
            "Original file should survive disk full error"
        )
        assert large_history_file.read_text(encoding="utf-8") == original_content, (
            "Original file content should be unchanged after disk full error"
        )


# ---------------------------------------------------------------------------
# Test: Non-functional constraints (T120, T130)
# ---------------------------------------------------------------------------


class TestNonFunctionalConstraints:
    """Tests enforcing performance and isolation requirements."""

    def test_no_actual_large_files_created(
        self, repo_with_logs: Path, large_history_file: Path, mock_file_size
    ) -> None:
        """T120: All test files on disk are under 1MB — no real 50MB allocations.

        Verifies monkeypatching is working correctly and no test accidentally
        creates real large files.
        """
        mock_file_size({str(large_history_file): ABOVE_THRESHOLD})

        consolidate(repo_with_logs)

        # Walk all files in tmp_path and assert none exceed 1MB
        large_files = []
        for file_path in repo_with_logs.rglob("*"):
            if file_path.is_file():
                real_size = file_path.stat().st_size  # Real size, not mocked
                if real_size > MAX_TEST_FILE_SIZE:
                    large_files.append((str(file_path), real_size))

        assert not large_files, (
            f"Found files exceeding {MAX_TEST_FILE_SIZE} bytes on disk "
            f"(monkeypatch may not be working): {large_files}"
        )

    def test_operations_confined_to_tmp_path(
        self, repo_with_logs: Path, large_history_file: Path, mock_file_size
    ) -> None:
        """T130: Consolidation writes only within tmp_path, no leakage.

        Snapshots the parent directory before and after to detect any
        files written outside the test's tmp_path.
        """
        parent = repo_with_logs.parent

        # Snapshot parent directory contents before test
        before = set()
        for item in parent.iterdir():
            if item != repo_with_logs:
                before.add(item.name)

        mock_file_size({str(large_history_file): ABOVE_THRESHOLD})

        consolidate(repo_with_logs)

        # Snapshot parent directory contents after test
        after = set()
        for item in parent.iterdir():
            if item != repo_with_logs:
                after.add(item.name)

        new_items = after - before
        assert not new_items, (
            f"Files written outside tmp_path detected: {new_items}"
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
collecting ... collected 13 items

tests/unit/test_consolidate_logs_large_file.py::TestSizeThresholdDetection::test_consolidate_detects_file_exceeding_threshold FAILED [  7%]
tests/unit/test_consolidate_logs_large_file.py::TestSizeThresholdDetection::test_consolidate_skips_file_below_threshold PASSED [ 15%]
tests/unit/test_consolidate_logs_large_file.py::TestSizeThresholdDetection::test_consolidate_exact_threshold_boundary FAILED [ 23%]
tests/unit/test_consolidate_logs_large_file.py::TestLogRotation::test_rotation_creates_numbered_backup FAILED [ 30%]
tests/unit/test_consolidate_logs_large_file.py::TestLogRotation::test_rotation_increments_existing_backups FAILED [ 38%]
tests/unit/test_consolidate_logs_large_file.py::TestLogRotation::test_rotation_preserves_content_integrity PASSED [ 46%]
tests/unit/test_consolidate_logs_large_file.py::TestLogRotation::test_rotation_creates_fresh_active_file FAILED [ 53%]
tests/unit/test_consolidate_logs_large_file.py::TestConsolidationWithLargeFiles::test_consolidate_large_file_with_multiple_sources PASSED [ 61%]
tests/unit/test_consolidate_logs_large_file.py::TestConsolidationWithLargeFiles::test_consolidate_handles_concurrent_rotation_gracefully PASSED [ 69%]
tests/unit/test_consolidate_logs_large_file.py::TestErrorHandling::test_consolidate_large_file_read_only_filesystem SKIPPED [ 76%]
tests/unit/test_consolidate_logs_large_file.py::TestErrorHandling::test_consolidate_large_file_disk_full_simulation PASSED [ 84%]
tests/unit/test_consolidate_logs_large_file.py::TestNonFunctionalConstraints::test_no_actual_large_files_created PASSED [ 92%]
tests/unit/test_consolidate_logs_large_file.py::TestNonFunctionalConstraints::test_operations_confined_to_tmp_path PASSED [100%]
ERROR: Coverage failure: total of 1 is less than fail-under=95


================================== FAILURES ===================================
_ TestSizeThresholdDetection.test_consolidate_detects_file_exceeding_threshold _
tests\unit\test_consolidate_logs_large_file.py:222: in test_consolidate_detects_file_exceeding_threshold
    assert backup.exists(), "Rotation should create a .1 backup file"
E   AssertionError: Rotation should create a .1 backup file
E   assert False
E    +  where False = exists()
E    +    where exists = WindowsPath('C:/Users/mcwiz/AppData/Local/Temp/pytest-of-mcwiz/pytest-906/test_consolidate_detects_file_0/logs/review_history.jsonl.1').exists
____ TestSizeThresholdDetection.test_consolidate_exact_threshold_boundary _____
tests\unit\test_consolidate_logs_large_file.py:256: in test_consolidate_exact_threshold_boundary
    assert backup.exists(), (
E   AssertionError: At exactly 50MB, rotation should trigger (>= threshold)
E   assert False
E    +  where False = exists()
E    +    where exists = WindowsPath('C:/Users/mcwiz/AppData/Local/Temp/pytest-of-mcwiz/pytest-906/test_consolidate_exact_thresho0/logs/review_history.jsonl.1').exists
____________ TestLogRotation.test_rotation_creates_numbered_backup ____________
tests\unit\test_consolidate_logs_large_file.py:281: in test_rotation_creates_numbered_backup
    assert backup.exists(), "Backup .1 should be created"
E   AssertionError: Backup .1 should be created
E   assert False
E    +  where False = exists()
E    +    where exists = WindowsPath('C:/Users/mcwiz/AppData/Local/Temp/pytest-of-mcwiz/pytest-906/test_rotation_creates_numbered0/logs/review_history.jsonl.1').exists
__________ TestLogRotation.test_rotation_increments_existing_backups __________
tests\unit\test_consolidate_logs_large_file.py:313: in test_rotation_increments_existing_backups
    assert new_backup1_ids == original_active_ids, (
E   AssertionError: New .1 should contain original active history entries
E   assert {'old_0001', ...ld_0006', ...} == {'line_0001',...ne_0006', ...}
E     
E     Extra items in the left set:
E     'old_0244'
E     'old_0014'
E     'old_0270'
E     'old_0070'
E     'old_0134'...
E     
E     ...Full output truncated (2200 lines hidden), use '-vv' to show
___________ TestLogRotation.test_rotation_creates_fresh_active_file ___________
tests\unit\test_consolidate_logs_large_file.py:354: in test_rotation_creates_fresh_active_file
    assert active.stat().st_size < 1024, (
E   AssertionError: Active file should be empty or header-only after rotation, but was 37576 bytes
E   assert 37576 < 1024
E    +  where 37576 = os.stat_result(st_mode=33206, st_ino=844424931694669, st_dev=17302997027815680700, st_nlink=1, st_uid=0, st_gid=0, st_size=37576, st_atime=1772074017, st_mtime=1772074017, st_ctime=1772074017).st_size
E    +    where os.stat_result(st_mode=33206, st_ino=844424931694669, st_dev=17302997027815680700, st_nlink=1, st_uid=0, st_gid=0, st_size=37576, st_atime=1772074017, st_mtime=1772074017, st_ctime=1772074017) = stat()
E    +      where stat = WindowsPath('C:/Users/mcwiz/AppData/Local/Temp/pytest-of-mcwiz/pytest-906/test_rotation_creates_fresh_ac0/logs/review_history.jsonl').stat
============================== warnings summary ===============================
..\..\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\google\genai\types.py:43
  C:\Users\mcwiz\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\google\genai\types.py:43: DeprecationWarning: '_UnionGenericAlias' is deprecated and slated for removal in Python 3.17
    VersionedUnionType = Union[builtin_types.UnionType, _UnionGenericAlias]

..\..\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\langchain_core\_api\deprecation.py:25
  C:\Users\mcwiz\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\langchain_core\_api\deprecation.py:25: UserWarning: Core Pydantic V1 functionality isn't compatible with Python 3.14 or greater.
    from pydantic.v1.fields import FieldInfo as FieldInfoV1

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
assemblyzero\core\llm_provider.py                                             322    322     0%   19-957
assemblyzero\core\state.py                                                      6      0   100%
assemblyzero\core\tdd_path_tracking.py                                         61     61     0%   9-190
assemblyzero\core\validation\__init__.py                                        2      2     0%   6-21
assemblyzero\core\validation\test_plan_validator.py                           168    168     0%   10-551
assemblyzero\graphs\__init__.py                                                 0      0   100%
assemblyzero\hooks\__init__.py                                                  5      5     0%   3-20
assemblyzero\hooks\cascade_action.py                                           34     34     0%   8-118
assemblyzero\hooks\cascade_detector.py                                         72     72     0%   9-195
assemblyzero\hooks\cascade_patterns.py                                         70     70     0%   9-292
assemblyzero\hooks\file_write_validator.py                                     40     40     0%   8-126
assemblyzero\hooks\types.py                                                    16     16     0%   9-33
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
assemblyzero\utils\__init__.py                                                  4      4     0%   3-27
assemblyzero\utils\codebase_reader.py                                         153    153     0%   12-372
assemblyzero\utils\file_type.py                                                12     12     0%   7-59
assemblyzero\utils\github_metrics_client.py                                    83     83     0%   9-243
assemblyzero\utils\lld_path_enforcer.py                                        79     79     0%   11-221
assemblyzero\utils\lld_verification.py                                         98     98     0%   14-361
assemblyzero\utils\metrics_aggregator.py                                      161    161     0%   9-447
assemblyzero\utils\metrics_config.py                                           78     78     0%   6-207
assemblyzero\utils\metrics_models.py                                           59     59     0%   6-97
assemblyzero\utils\pattern_scanner.py                                         185    185     0%   11-493
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
assemblyzero\workflows\requirements\__init__.py                                 4      4     0%   17-31
assemblyzero\workflows\requirements\audit.py                                  229    229     0%   20-855
assemblyzero\workflows\requirements\config.py                                  68     68     0%   11-241
assemblyzero\workflows\requirements\git_operations.py                          30     30     0%   6-101
assemblyzero\workflows\requirements\graph.py                                  119    119     0%   47-494
assemblyzero\workflows\requirements\nodes\__init__.py                           9      9     0%   20-38
assemblyzero\workflows\requirements\nodes\analyze_codebase.py                 229    229     0%   13-567
assemblyzero\workflows\requirements\nodes\finalize.py                         163    163     0%   7-402
assemblyzero\workflows\requirements\nodes\generate_draft.py                   156    156     0%   13-390
assemblyzero\workflows\requirements\nodes\human_gate.py                        88     88     0%   14-233
assemblyzero\workflows\requirements\nodes\load_input.py                       114    114     0%   14-321
assemblyzero\workflows\requirements\nodes\review.py                           117    117     0%   11-332
assemblyzero\workflows\requirements\nodes\validate_mechanical.py              429    429     0%   29-1345
assemblyzero\workflows\requirements\nodes\validate_test_plan.py                58     58     0%   13-142
assemblyzero\workflows\requirements\parsers\__init__.py                         3      3     0%   6-14
assemblyzero\workflows\requirements\parsers\draft_updater.py                  130    130     0%   8-315
assemblyzero\workflows\requirements\parsers\verdict_parser.py                  94     94     0%   8-295
assemblyzero\workflows\requirements\state.py                                   44     44     0%   18-391
assemblyzero\workflows\scout\__init__.py                                        3      3     0%   7-18
assemblyzero\workflows\scout\budget.py                                         21     21     0%   7-76
assemblyzero\workflows\scout\graph.py                                           5      5     0%   6-62
assemblyzero\workflows\scout\instrumentation.py                                40     40     0%   6-126
assemblyzero\workflows\scout\nodes.py                                         151    151     0%   6-345
assemblyzero\workflows\scout\prompts.py                                        11     11     0%   7-76
assemblyzero\workflows\scout\security.py                                       44     44     0%   6-132
assemblyzero\workflows\scout\templates.py                                      33     33     0%   6-124
assemblyzero\workflows\testing\__init__.py                                      3      3     0%   18-21
assemblyzero\workflows\testing\audit.py                                        88     88     0%   13-321
assemblyzero\workflows\testing\circuit_breaker.py                              46     46     0%   11-139
assemblyzero\workflows\testing\completeness\__init__.py                         3      3     0%   7-21
assemblyzero\workflows\testing\completeness\ast_analyzer.py                   280    280     0%   17-725
assemblyzero\workflows\testing\completeness\report_generator.py               129    129     0%   14-429
assemblyzero\workflows\testing\exit_code_router.py                             27     27     0%   17-92
assemblyzero\workflows\testing\graph.py                                       123    123     0%   52-479
assemblyzero\workflows\testing\knowledge\__init__.py                            2      2     0%   8-10
assemblyzero\workflows\testing\knowledge\patterns.py                           60     60     0%   7-193
assemblyzero\workflows\testing\nodes\__init__.py                               12     12     0%   23-45
assemblyzero\workflows\testing\nodes\cleanup.py                                76     76     0%   11-153
assemblyzero\workflows\testing\nodes\cleanup_helpers.py                       234    234     0%   10-526
assemblyzero\workflows\testing\nodes\completeness_gate.py                     115    115     0%   19-352
assemblyzero\workflows\testing\nodes\document.py                              140    140     0%   13-361
assemblyzero\workflows\testing\nodes\e2e_validation.py                        109    109     0%   9-359
assemblyzero\workflows\testing\nodes\finalize.py                              110    110     0%   10-261
assemblyzero\workflows\testing\nodes\implement_code.py                        626    626     0%   16-1677
assemblyzero\workflows\testing\nodes\load_lld.py                              315    315     0%   14-916
assemblyzero\workflows\testing\nodes\review_test_plan.py                      168    168     0%   13-566
assemblyzero\workflows\testing\nodes\scaffold_tests.py                        317    317     0%   16-774
assemblyzero\workflows\testing\nodes\validate_commit_message.py                12     12     0%   7-47
assemblyzero\workflows\testing\nodes\validate_tests_mechanical.py             114    114     0%   10-324
assemblyzero\workflows\testing\nodes\verify_phases.py                         242    242     0%   11-760
assemblyzero\workflows\testing\path_validator.py                               70     70     0%   7-181
assemblyzero\workflows\testing\state.py                                        13     13     0%   16-43
assemblyzero\workflows\testing\templates\__init__.py                            5      5     0%   12-23
assemblyzero\workflows\testing\templates\cp_docs.py                            73     73     0%   9-296
assemblyzero\workflows\testing\templates\lessons.py                           115    115     0%   8-304
assemblyzero\workflows\testing\templates\runbook.py                            94     94     0%   8-259
assemblyzero\workflows\testing\templates\wiki_page.py                          74     74     0%   8-207
---------------------------------------------------------------------------------------------------------
TOTAL                                                                       12002  11899     1%
FAIL Required test coverage of 95% not reached. Total coverage: 0.86%
=========================== short test summary info ===========================
FAILED tests/unit/test_consolidate_logs_large_file.py::TestSizeThresholdDetection::test_consolidate_detects_file_exceeding_threshold
FAILED tests/unit/test_consolidate_logs_large_file.py::TestSizeThresholdDetection::test_consolidate_exact_threshold_boundary
FAILED tests/unit/test_consolidate_logs_large_file.py::TestLogRotation::test_rotation_creates_numbered_backup
FAILED tests/unit/test_consolidate_logs_large_file.py::TestLogRotation::test_rotation_increments_existing_backups
FAILED tests/unit/test_consolidate_logs_large_file.py::TestLogRotation::test_rotation_creates_fresh_active_file
============= 5 failed, 7 passed, 1 skipped, 2 warnings in 3.41s ==============


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
