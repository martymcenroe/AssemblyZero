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

# Reason for xfail on rotation-dependent tests
_ROTATION_NOT_IMPLEMENTED = (
    "Log rotation not yet implemented — TDD RED phase "
    "(see TODO line 123 of tools/consolidate_logs.py)"
)


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

    @pytest.mark.xfail(reason=_ROTATION_NOT_IMPLEMENTED, strict=True)
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

    @pytest.mark.xfail(reason=_ROTATION_NOT_IMPLEMENTED, strict=True)
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

    @pytest.mark.xfail(reason=_ROTATION_NOT_IMPLEMENTED, strict=True)
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

    @pytest.mark.xfail(reason=_ROTATION_NOT_IMPLEMENTED, strict=True)
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

    @pytest.mark.xfail(reason=_ROTATION_NOT_IMPLEMENTED, strict=True)
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
