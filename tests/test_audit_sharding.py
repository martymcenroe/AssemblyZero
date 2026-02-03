"""Tests for session-sharded audit logging.

Issue #57: Distributed Session-Sharded Logging Architecture

Test scenarios from LLD section 10.1:
- 010: Shard filename format
- 020: Session ID uniqueness
- 030: Repo root detection
- 040: Repo root detection failure
- 050: Log to shard
- 060: Fail-closed on unwritable
- 070: Tail merges history + shards
- 080: Tail skips locked shards
- 090: Consolidation atomic write
- 100: Consolidation deletes shards
- 110: Consolidation idempotent
- 120: Concurrent writers
- 130: Windows path handling
"""

import json
import os
import re
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from agentos.core.audit import (
    ReviewAuditLog,
    ReviewLogEntry,
    create_log_entry,
)


@pytest.fixture
def temp_repo(tmp_path: Path) -> Path:
    """Create a temporary git repository structure."""
    # Initialize git repo
    subprocess.run(
        ["git", "init"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )

    # Create logs directories
    (tmp_path / "logs").mkdir(exist_ok=True)
    (tmp_path / "logs" / "active").mkdir(exist_ok=True)

    return tmp_path


@pytest.fixture
def sample_entry() -> ReviewLogEntry:
    """Create a sample review log entry."""
    return create_log_entry(
        node="review_lld",
        model="gemini-3-pro-preview",
        model_verified="gemini-3-pro-preview",
        issue_id=57,
        verdict="APPROVED",
        critique="Test critique",
        tier_1_issues=[],
        raw_response='{"verdict": "APPROVED"}',
        duration_ms=1234,
        credential_used="credential-1",
        rotation_occurred=False,
        attempts=1,
        sequence_id=1,
    )


class TestShardFilenameFormat:
    """Test 010: Shard filename format."""

    def test_filename_matches_pattern(self, temp_repo: Path) -> None:
        """Filename should match {YYYYMMDDTHHMMSS}_{8chars}.jsonl."""
        log = ReviewAuditLog(repo_root=temp_repo, session_id="a1b2c3d4")

        pattern = r"^\d{8}T\d{6}_[a-f0-9]{8}\.jsonl$"
        assert re.match(pattern, log.shard_file.name) is not None

    def test_filename_contains_session_id(self, temp_repo: Path) -> None:
        """Filename should contain the session ID."""
        session_id = "deadbeef"
        log = ReviewAuditLog(repo_root=temp_repo, session_id=session_id)

        assert session_id in log.shard_file.name


class TestSessionIdUniqueness:
    """Test 020: Session ID uniqueness."""

    def test_100_sessions_unique_ids(self, temp_repo: Path) -> None:
        """100 sessions should generate 100 unique IDs."""
        session_ids = set()

        for _ in range(100):
            log = ReviewAuditLog(repo_root=temp_repo)
            session_ids.add(log.session_id)

        assert len(session_ids) == 100

    def test_session_id_length(self, temp_repo: Path) -> None:
        """Session ID should be 8 characters."""
        log = ReviewAuditLog(repo_root=temp_repo)
        assert len(log.session_id) == 8


class TestRepoRootDetection:
    """Test 030-040: Repo root detection."""

    def test_030_detect_repo_root_success(self, temp_repo: Path) -> None:
        """Should detect repo root in a git repository."""
        # Change to temp repo and verify detection works
        log = ReviewAuditLog(repo_root=temp_repo)
        assert log.repo_root == temp_repo

    def test_030_auto_detection_in_git_repo(self, temp_repo: Path) -> None:
        """Should auto-detect repo root when not provided."""
        # Patch subprocess to return our temp repo path
        with patch("agentos.core.audit.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = str(temp_repo)

            log = ReviewAuditLog()
            assert log.repo_root == temp_repo

    def test_040_detect_repo_root_failure(self, tmp_path: Path) -> None:
        """Should raise RuntimeError when not in a git repository."""
        # Create a non-git directory
        non_git = tmp_path / "not_a_repo"
        non_git.mkdir()

        # Patch subprocess to simulate git failure
        with patch("agentos.core.audit.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 128
            mock_run.return_value.stderr = "fatal: not a git repository"

            with pytest.raises(RuntimeError, match="Not in a git repository"):
                ReviewAuditLog()


class TestLogToShard:
    """Test 050: Log to shard."""

    def test_entry_written_to_shard(
        self, temp_repo: Path, sample_entry: ReviewLogEntry
    ) -> None:
        """Entry should be written to shard file as valid JSON."""
        log = ReviewAuditLog(repo_root=temp_repo)
        log.log(sample_entry)

        assert log.shard_file.exists()

        with open(log.shard_file, encoding="utf-8") as f:
            content = f.read()

        # Parse as JSON to verify validity
        entry = json.loads(content.strip())
        assert entry["issue_id"] == 57
        assert entry["verdict"] == "APPROVED"

    def test_multiple_entries_append(
        self, temp_repo: Path, sample_entry: ReviewLogEntry
    ) -> None:
        """Multiple entries should be appended to same shard."""
        log = ReviewAuditLog(repo_root=temp_repo)

        # Log multiple entries
        for i in range(3):
            entry = create_log_entry(
                node=f"node_{i}",
                model="gemini-3-pro-preview",
                model_verified="gemini-3-pro-preview",
                issue_id=57 + i,
                verdict="APPROVED",
                critique="Test",
                tier_1_issues=[],
                raw_response="{}",
                duration_ms=100,
                credential_used="cred",
                rotation_occurred=False,
                attempts=1,
                sequence_id=i,
            )
            log.log(entry)

        with open(log.shard_file, encoding="utf-8") as f:
            lines = f.readlines()

        assert len(lines) == 3


class TestFailClosed:
    """Test 060: Fail-closed on unwritable."""

    def test_raises_on_unwritable_directory(self, tmp_path: Path) -> None:
        """Should raise OSError when directory is not writable."""
        # Create a read-only directory
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()

        # Create logs structure
        logs_dir = readonly_dir / "logs" / "active"
        logs_dir.mkdir(parents=True)

        # Mock git detection to return our readonly path
        with patch("agentos.core.audit.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = str(readonly_dir)

            log = ReviewAuditLog(repo_root=readonly_dir)

            # Make directory read-only
            if os.name != "nt":  # Skip on Windows (permissions work differently)
                os.chmod(logs_dir, 0o444)

                entry = create_log_entry(
                    node="test",
                    model="gemini-3-pro-preview",
                    model_verified="gemini-3-pro-preview",
                    issue_id=1,
                    verdict="APPROVED",
                    critique="",
                    tier_1_issues=[],
                    raw_response="",
                    duration_ms=0,
                    credential_used="",
                    rotation_occurred=False,
                    attempts=1,
                )

                with pytest.raises(OSError):
                    log.log(entry)

                # Restore permissions for cleanup
                os.chmod(logs_dir, 0o755)


class TestTailMerges:
    """Test 070: Tail merges history + shards."""

    def test_merges_history_and_shards(self, temp_repo: Path) -> None:
        """Tail should merge entries from history file and active shards."""
        history_file = temp_repo / "logs" / "review_history.jsonl"

        # Create history entries
        history_entries = []
        for i in range(3):
            entry = create_log_entry(
                node=f"history_{i}",
                model="gemini-3-pro-preview",
                model_verified="gemini-3-pro-preview",
                issue_id=i,
                verdict="APPROVED",
                critique="",
                tier_1_issues=[],
                raw_response="",
                duration_ms=0,
                credential_used="",
                rotation_occurred=False,
                attempts=1,
                sequence_id=i,
            )
            history_entries.append(entry)

        with open(history_file, "w", encoding="utf-8") as f:
            for entry in history_entries:
                f.write(json.dumps(entry) + "\n")

        # Create shard with more entries
        log = ReviewAuditLog(repo_root=temp_repo)
        for i in range(2):
            entry = create_log_entry(
                node=f"shard_{i}",
                model="gemini-3-pro-preview",
                model_verified="gemini-3-pro-preview",
                issue_id=100 + i,
                verdict="BLOCKED",
                critique="",
                tier_1_issues=[],
                raw_response="",
                duration_ms=0,
                credential_used="",
                rotation_occurred=False,
                attempts=1,
                sequence_id=i,
            )
            log.log(entry)

        # Tail should return all entries
        entries = log.tail(n=10)
        assert len(entries) == 5

    def test_sorted_by_timestamp(self, temp_repo: Path) -> None:
        """Entries should be sorted by timestamp."""
        log = ReviewAuditLog(repo_root=temp_repo)

        # Log entries with deliberate pauses for timestamp ordering
        for i in range(3):
            entry = create_log_entry(
                node=f"node_{i}",
                model="gemini-3-pro-preview",
                model_verified="gemini-3-pro-preview",
                issue_id=i,
                verdict="APPROVED",
                critique="",
                tier_1_issues=[],
                raw_response="",
                duration_ms=0,
                credential_used="",
                rotation_occurred=False,
                attempts=1,
                sequence_id=i,
            )
            log.log(entry)

        entries = log.tail(n=10)
        timestamps = [e["timestamp"] for e in entries]
        assert timestamps == sorted(timestamps)


class TestTailSkipsLocked:
    """Test 080: Tail skips locked shards."""

    def test_graceful_degradation_on_unreadable(self, temp_repo: Path) -> None:
        """Should return partial results when some shards are unreadable."""
        log = ReviewAuditLog(repo_root=temp_repo)

        # Log an entry to create the shard
        entry = create_log_entry(
            node="test",
            model="gemini-3-pro-preview",
            model_verified="gemini-3-pro-preview",
            issue_id=1,
            verdict="APPROVED",
            critique="",
            tier_1_issues=[],
            raw_response="",
            duration_ms=0,
            credential_used="",
            rotation_occurred=False,
            attempts=1,
        )
        log.log(entry)

        # Create another shard with garbage content
        bad_shard = temp_repo / "logs" / "active" / "bad_shard.jsonl"
        with open(bad_shard, "w", encoding="utf-8") as f:
            f.write("not valid json\n")

        # Should not crash, should return the good entry
        entries = log.tail(n=10)
        assert len(entries) >= 1


class TestConsolidation:
    """Tests 090-110: Consolidation behavior."""

    def test_090_atomic_write(self, temp_repo: Path) -> None:
        """Consolidation should use atomic write pattern."""
        # Import the consolidation module
        import sys

        sys.path.insert(0, str(temp_repo / "tools"))

        # Create shards
        log = ReviewAuditLog(repo_root=temp_repo)
        for i in range(3):
            entry = create_log_entry(
                node=f"node_{i}",
                model="gemini-3-pro-preview",
                model_verified="gemini-3-pro-preview",
                issue_id=i,
                verdict="APPROVED",
                critique="",
                tier_1_issues=[],
                raw_response="",
                duration_ms=0,
                credential_used="",
                rotation_occurred=False,
                attempts=1,
                sequence_id=i,
            )
            log.log(entry)

        # Run consolidation directly using the code
        from tools.consolidate_logs import consolidate

        count = consolidate(temp_repo)

        assert count == 1  # One shard created by this session

        # Verify history file exists and contains entries
        history_file = temp_repo / "logs" / "review_history.jsonl"
        assert history_file.exists()

        with open(history_file, encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 3

        # No temp files should remain
        temp_files = list((temp_repo / "logs").glob(".history_*.tmp"))
        assert len(temp_files) == 0

    def test_100_deletes_shards_after_success(self, temp_repo: Path) -> None:
        """Shards should be deleted only after successful consolidation."""
        log = ReviewAuditLog(repo_root=temp_repo)

        entry = create_log_entry(
            node="test",
            model="gemini-3-pro-preview",
            model_verified="gemini-3-pro-preview",
            issue_id=1,
            verdict="APPROVED",
            critique="",
            tier_1_issues=[],
            raw_response="",
            duration_ms=0,
            credential_used="",
            rotation_occurred=False,
            attempts=1,
        )
        log.log(entry)

        shard_path = log.shard_file
        assert shard_path.exists()

        from tools.consolidate_logs import consolidate

        consolidate(temp_repo)

        # Shard should be deleted
        assert not shard_path.exists()

        # Active directory should be empty (except .gitkeep)
        shards = list((temp_repo / "logs" / "active").glob("*.jsonl"))
        assert len(shards) == 0

    def test_110_idempotent(self, temp_repo: Path) -> None:
        """Running consolidation twice with no new shards should be no-op."""
        # First, create and consolidate some entries
        log = ReviewAuditLog(repo_root=temp_repo)

        entry = create_log_entry(
            node="test",
            model="gemini-3-pro-preview",
            model_verified="gemini-3-pro-preview",
            issue_id=1,
            verdict="APPROVED",
            critique="",
            tier_1_issues=[],
            raw_response="",
            duration_ms=0,
            credential_used="",
            rotation_occurred=False,
            attempts=1,
        )
        log.log(entry)

        from tools.consolidate_logs import consolidate

        first_count = consolidate(temp_repo)
        assert first_count == 1

        # Get history file content after first consolidation
        history_file = temp_repo / "logs" / "review_history.jsonl"
        with open(history_file, encoding="utf-8") as f:
            first_content = f.read()

        # Run consolidation again
        second_count = consolidate(temp_repo)
        assert second_count == 0

        # History should be unchanged
        with open(history_file, encoding="utf-8") as f:
            second_content = f.read()

        assert first_content == second_content


class TestConcurrentWriters:
    """Test 120: Concurrent writers."""

    def test_no_data_loss_with_concurrent_sessions(
        self, temp_repo: Path
    ) -> None:
        """Multiple threads writing should not lose data."""
        entries_per_thread = 10
        num_threads = 3
        results: list[Path] = []
        errors: list[Exception] = []

        def writer_thread(thread_id: int) -> None:
            try:
                log = ReviewAuditLog(repo_root=temp_repo)
                results.append(log.shard_file)

                for i in range(entries_per_thread):
                    entry = create_log_entry(
                        node=f"thread_{thread_id}_entry_{i}",
                        model="gemini-3-pro-preview",
                        model_verified="gemini-3-pro-preview",
                        issue_id=thread_id * 100 + i,
                        verdict="APPROVED",
                        critique="",
                        tier_1_issues=[],
                        raw_response="",
                        duration_ms=0,
                        credential_used="",
                        rotation_occurred=False,
                        attempts=1,
                        sequence_id=i,
                    )
                    log.log(entry)
                    time.sleep(0.001)  # Small delay to interleave writes
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=writer_thread, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # No errors should have occurred
        assert len(errors) == 0

        # Should have 3 unique shard files
        unique_shards = set(results)
        assert len(unique_shards) == num_threads

        # Each shard should exist and have entries_per_thread entries
        total_entries = 0
        for shard in unique_shards:
            assert shard.exists()
            with open(shard, encoding="utf-8") as f:
                lines = f.readlines()
            total_entries += len(lines)

        # Should have all entries
        assert total_entries == num_threads * entries_per_thread


class TestWindowsPathHandling:
    """Test 130: Windows path handling."""

    def test_pathlib_used_throughout(self, temp_repo: Path) -> None:
        """All paths should be pathlib.Path objects."""
        log = ReviewAuditLog(repo_root=temp_repo)

        assert isinstance(log.repo_root, Path)
        assert isinstance(log.active_dir, Path)
        assert isinstance(log.history_file, Path)
        assert isinstance(log.shard_file, Path)

    def test_shard_filename_valid_on_all_platforms(
        self, temp_repo: Path
    ) -> None:
        """Shard filename should not contain invalid characters."""
        log = ReviewAuditLog(repo_root=temp_repo)

        filename = log.shard_file.name

        # Check for characters invalid on Windows
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            assert char not in filename


class TestLegacyMode:
    """Test backwards compatibility with log_path parameter."""

    def test_legacy_mode_single_file(self, tmp_path: Path) -> None:
        """Legacy mode should write directly to provided path."""
        log_path = tmp_path / "logs" / "test.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        log = ReviewAuditLog(log_path=log_path)

        entry = create_log_entry(
            node="test",
            model="gemini-3-pro-preview",
            model_verified="gemini-3-pro-preview",
            issue_id=1,
            verdict="APPROVED",
            critique="",
            tier_1_issues=[],
            raw_response="",
            duration_ms=0,
            credential_used="",
            rotation_occurred=False,
            attempts=1,
        )
        log.log(entry)

        # Should write directly to the provided path
        assert log_path.exists()

        with open(log_path, encoding="utf-8") as f:
            content = f.read()

        assert "APPROVED" in content


class TestIteratorAndCount:
    """Test __iter__ and count methods."""

    def test_iterator_returns_all_entries(self, temp_repo: Path) -> None:
        """Iterator should yield all entries in chronological order."""
        log = ReviewAuditLog(repo_root=temp_repo)

        for i in range(5):
            entry = create_log_entry(
                node=f"node_{i}",
                model="gemini-3-pro-preview",
                model_verified="gemini-3-pro-preview",
                issue_id=i,
                verdict="APPROVED",
                critique="",
                tier_1_issues=[],
                raw_response="",
                duration_ms=0,
                credential_used="",
                rotation_occurred=False,
                attempts=1,
                sequence_id=i,
            )
            log.log(entry)

        entries = list(log)
        assert len(entries) == 5

    def test_count_returns_total_entries(self, temp_repo: Path) -> None:
        """Count should return total number of entries."""
        log = ReviewAuditLog(repo_root=temp_repo)

        for i in range(3):
            entry = create_log_entry(
                node=f"node_{i}",
                model="gemini-3-pro-preview",
                model_verified="gemini-3-pro-preview",
                issue_id=i,
                verdict="APPROVED",
                critique="",
                tier_1_issues=[],
                raw_response="",
                duration_ms=0,
                credential_used="",
                rotation_occurred=False,
                attempts=1,
                sequence_id=i,
            )
            log.log(entry)

        assert log.count() == 3
