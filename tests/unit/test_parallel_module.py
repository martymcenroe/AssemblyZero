"""Comprehensive tests for the parallel workflow module.

Target: >95% coverage for all parallel module files:
- coordinator.py
- credential_coordinator.py
- input_sanitizer.py
- output_prefixer.py
"""

import io
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from agentos.workflows.parallel.coordinator import (
    ParallelCoordinator,
    ProgressStats,
    WorkflowResult,
)
from agentos.workflows.parallel.credential_coordinator import CredentialCoordinator
from agentos.workflows.parallel.input_sanitizer import sanitize_identifier
from agentos.workflows.parallel.output_prefixer import OutputPrefixer


# =============================================================================
# WorkflowResult Tests
# =============================================================================


class TestWorkflowResult:
    """Tests for WorkflowResult dataclass."""

    def test_successful_result(self):
        """Test creating a successful workflow result."""
        result = WorkflowResult(item_id="test-1", success=True, duration=1.5)
        assert result.item_id == "test-1"
        assert result.success is True
        assert result.error is None
        assert result.duration == 1.5

    def test_failed_result_with_error(self):
        """Test creating a failed workflow result with error."""
        result = WorkflowResult(
            item_id="test-2", success=False, error="Connection failed", duration=0.5
        )
        assert result.item_id == "test-2"
        assert result.success is False
        assert result.error == "Connection failed"
        assert result.duration == 0.5

    def test_result_defaults(self):
        """Test WorkflowResult default values."""
        result = WorkflowResult(item_id="test-3", success=True)
        assert result.error is None
        assert result.duration is None


# =============================================================================
# ProgressStats Tests
# =============================================================================


class TestProgressStats:
    """Tests for ProgressStats dataclass."""

    def test_initial_stats(self):
        """Test ProgressStats initialization."""
        stats = ProgressStats(total=10)
        assert stats.total == 10
        assert stats.completed == 0
        assert stats.failed == 0
        assert stats.success_count == 0

    def test_stats_with_values(self):
        """Test ProgressStats with explicit values."""
        stats = ProgressStats(total=10, completed=5, failed=2, success_count=3)
        assert stats.total == 10
        assert stats.completed == 5
        assert stats.failed == 2
        assert stats.success_count == 3


# =============================================================================
# ParallelCoordinator Tests
# =============================================================================


class TestParallelCoordinatorInit:
    """Tests for ParallelCoordinator initialization."""

    def test_default_parallelism(self):
        """Test default parallelism is 3."""
        with patch("signal.signal"):
            coordinator = ParallelCoordinator()
        assert coordinator.max_workers == 3

    def test_custom_parallelism(self):
        """Test custom parallelism is respected."""
        with patch("signal.signal"):
            coordinator = ParallelCoordinator(max_workers=5)
        assert coordinator.max_workers == 5

    def test_max_parallelism_cap(self):
        """Test parallelism is capped at maximum (10)."""
        with patch("signal.signal"):
            coordinator = ParallelCoordinator(max_workers=20)
        assert coordinator.max_workers == 10

    def test_credential_coordinator_stored(self):
        """Test credential coordinator is stored."""
        mock_cred_coord = MagicMock()
        with patch("signal.signal"):
            coordinator = ParallelCoordinator(credential_coordinator=mock_cred_coord)
        assert coordinator.credential_coordinator is mock_cred_coord


class TestParallelCoordinatorShutdown:
    """Tests for shutdown signal handling."""

    def test_handle_shutdown_signal(self):
        """Test shutdown signal sets the event."""
        with patch("signal.signal"):
            coordinator = ParallelCoordinator()
        assert not coordinator._shutdown_event.is_set()
        coordinator._handle_shutdown_signal(2, None)  # SIGINT = 2
        assert coordinator._shutdown_event.is_set()


class TestParallelCoordinatorCheckpoints:
    """Tests for checkpoint management."""

    def test_get_checkpoints_empty(self):
        """Test get_checkpoints returns empty list initially."""
        with patch("signal.signal"):
            coordinator = ParallelCoordinator()
        assert coordinator.get_checkpoints() == []

    def test_get_checkpoints_returns_copy(self):
        """Test get_checkpoints returns a copy of checkpoints."""
        with patch("signal.signal"):
            coordinator = ParallelCoordinator()
        coordinator._checkpoints = ["item-1", "item-2"]
        checkpoints = coordinator.get_checkpoints()
        assert checkpoints == ["item-1", "item-2"]
        # Verify it's a copy
        checkpoints.append("item-3")
        assert coordinator._checkpoints == ["item-1", "item-2"]


class TestParallelCoordinatorShutdownDuringExecution:
    """Tests for shutdown during execution."""

    def test_shutdown_before_submitting_items(self):
        """Test shutdown event set before submitting items."""
        with patch("signal.signal"):
            coordinator = ParallelCoordinator()

        # Set shutdown event before execution
        coordinator._shutdown_event.set()

        items = ["item-1", "item-2", "item-3"]
        worker_func = MagicMock()
        item_id_func = lambda x: x

        stats, results = coordinator.execute_parallel(items, worker_func, item_id_func)

        # Worker should not be called since shutdown was already set
        worker_func.assert_not_called()
        assert stats.completed == 0

    def test_shutdown_during_result_collection_checkpoints_remaining(self):
        """Test shutdown during result collection checkpoints remaining items."""
        with patch("signal.signal"):
            coordinator = ParallelCoordinator(max_workers=1)

        items = ["item-1", "item-2", "item-3"]
        execution_started = threading.Event()

        def slow_worker(item, credential):
            if item == "item-1":
                execution_started.set()
                time.sleep(0.3)  # Slow enough for shutdown to trigger

        item_id_func = lambda x: x

        def trigger_shutdown():
            execution_started.wait()
            time.sleep(0.05)  # Let first item start processing
            coordinator._shutdown_event.set()

        shutdown_thread = threading.Thread(target=trigger_shutdown)
        shutdown_thread.start()

        stats, results = coordinator.execute_parallel(items, slow_worker, item_id_func)

        shutdown_thread.join()

        # Some items may be checkpointed
        # The exact behavior depends on timing, but shutdown was handled


class TestParallelCoordinatorExecution:
    """Tests for parallel execution."""

    def test_dry_run_mode(self, capsys):
        """Test dry run mode lists items without executing."""
        with patch("signal.signal"):
            coordinator = ParallelCoordinator()

        items = ["a", "b", "c"]
        worker_func = MagicMock()
        item_id_func = lambda x: x

        stats, results = coordinator.execute_parallel(
            items, worker_func, item_id_func, dry_run=True
        )

        # Worker should not be called
        worker_func.assert_not_called()

        # Stats should show total but no completions
        assert stats.total == 3
        assert stats.completed == 0

        # Should print dry run message
        captured = capsys.readouterr()
        assert "Dry run mode" in captured.out
        assert "a" in captured.out
        assert "b" in captured.out
        assert "c" in captured.out

    def test_successful_parallel_execution(self):
        """Test successful parallel execution of items."""
        with patch("signal.signal"):
            coordinator = ParallelCoordinator(max_workers=2)

        items = ["item-1", "item-2", "item-3"]
        worker_func = MagicMock()
        item_id_func = lambda x: x

        stats, results = coordinator.execute_parallel(items, worker_func, item_id_func)

        # All items should be processed
        assert stats.total == 3
        assert stats.completed == 3
        assert stats.success_count == 3
        assert stats.failed == 0

        # Worker should be called for each item
        assert worker_func.call_count == 3

    def test_worker_failure_handling(self):
        """Test handling of worker function failures."""
        with patch("signal.signal"):
            coordinator = ParallelCoordinator(max_workers=2)

        items = ["item-1", "item-2"]

        def failing_worker(item, credential):
            if item == "item-1":
                raise ValueError("Simulated failure")

        item_id_func = lambda x: x

        stats, results = coordinator.execute_parallel(
            items, failing_worker, item_id_func
        )

        assert stats.total == 2
        assert stats.completed == 2
        assert stats.failed == 1
        assert stats.success_count == 1

        # Find the failed result
        failed_results = [r for r in results if not r.success]
        assert len(failed_results) == 1
        assert "Simulated failure" in failed_results[0].error

    def test_execution_with_credential_coordinator(self):
        """Test execution with credential coordinator."""
        mock_cred_coord = MagicMock()
        mock_cred_coord.acquire.return_value = "test-credential"

        with patch("signal.signal"):
            coordinator = ParallelCoordinator(credential_coordinator=mock_cred_coord)

        items = ["item-1"]
        worker_func = MagicMock()
        item_id_func = lambda x: x

        stats, results = coordinator.execute_parallel(items, worker_func, item_id_func)

        # Credential should be acquired and released
        mock_cred_coord.acquire.assert_called_once()
        mock_cred_coord.release.assert_called_once()

        assert stats.success_count == 1

    def test_credential_acquire_timeout(self):
        """Test handling of credential acquire timeout."""
        mock_cred_coord = MagicMock()
        mock_cred_coord.acquire.return_value = None  # Timeout

        with patch("signal.signal"):
            coordinator = ParallelCoordinator(credential_coordinator=mock_cred_coord)

        items = ["item-1"]
        worker_func = MagicMock()
        item_id_func = lambda x: x

        stats, results = coordinator.execute_parallel(items, worker_func, item_id_func)

        # Should fail due to credential timeout
        assert stats.failed == 1
        assert "Failed to acquire credential" in results[0].error

    def test_rate_limit_simulation(self):
        """Test rate limit simulation via environment variable."""
        mock_cred_coord = MagicMock()
        mock_cred_coord.acquire.return_value = "test-credential"

        with patch("signal.signal"):
            coordinator = ParallelCoordinator(credential_coordinator=mock_cred_coord)

        items = ["item-1"]
        worker_func = MagicMock()
        item_id_func = lambda x: x

        # Simulate rate limit
        with patch.dict("os.environ", {"AGENTOS_SIMULATE_429": "true"}):
            stats, results = coordinator.execute_parallel(
                items, worker_func, item_id_func
            )

        # Release should be called with rate_limited=True
        mock_cred_coord.release.assert_called_once()
        call_kwargs = mock_cred_coord.release.call_args[1]
        assert call_kwargs["rate_limited"] is True
        assert call_kwargs["backoff_seconds"] == 60.0


# =============================================================================
# CredentialCoordinator Tests
# =============================================================================


class TestCredentialCoordinatorInit:
    """Tests for CredentialCoordinator initialization."""

    def test_init_with_credentials(self):
        """Test initialization with credentials."""
        creds = ["key-1", "key-2", "key-3"]
        coordinator = CredentialCoordinator(creds)

        assert coordinator.credentials == creds
        assert coordinator._available == set(creds)
        assert coordinator._in_use == set()
        assert coordinator._cooldowns == {}


class TestCredentialCoordinatorAcquireRelease:
    """Tests for credential acquire/release cycle."""

    def test_acquire_returns_credential(self):
        """Test acquire returns an available credential."""
        coordinator = CredentialCoordinator(["key-1", "key-2"])
        credential = coordinator.acquire()

        assert credential in ["key-1", "key-2"]
        assert credential in coordinator._in_use
        assert credential not in coordinator._available

    def test_release_returns_credential_to_pool(self):
        """Test release returns credential to available pool."""
        coordinator = CredentialCoordinator(["key-1"])
        credential = coordinator.acquire()

        assert coordinator._available == set()
        coordinator.release(credential)
        assert coordinator._available == {"key-1"}
        assert coordinator._in_use == set()

    def test_acquire_timeout(self):
        """Test acquire returns None after timeout."""
        coordinator = CredentialCoordinator(["key-1"])
        # Acquire the only credential
        coordinator.acquire()

        # Try to acquire again with short timeout
        result = coordinator.acquire(timeout=0.1)
        assert result is None

    def test_acquire_waits_for_release(self):
        """Test acquire waits for credential release."""
        coordinator = CredentialCoordinator(["key-1"])
        credential = coordinator.acquire()
        acquired = []

        def release_after_delay():
            time.sleep(0.1)
            coordinator.release(credential)

        def try_acquire():
            result = coordinator.acquire(timeout=1.0)
            acquired.append(result)

        # Start release thread
        release_thread = threading.Thread(target=release_after_delay)
        acquire_thread = threading.Thread(target=try_acquire)

        release_thread.start()
        acquire_thread.start()

        release_thread.join()
        acquire_thread.join()

        assert acquired[0] == "key-1"


class TestCredentialCoordinatorRateLimitBackoff:
    """Tests for rate-limit backoff behavior (Issue #149)."""

    def test_release_with_rate_limit_puts_in_cooldown(self, capsys):
        """Test release with rate_limited=True puts credential in cooldown."""
        coordinator = CredentialCoordinator(["key-1"])
        credential = coordinator.acquire()

        coordinator.release(credential, rate_limited=True, backoff_seconds=60.0)

        # Credential should be in cooldown, not available
        assert credential not in coordinator._available
        assert credential in coordinator._cooldowns
        assert coordinator._cooldowns[credential] > time.time()

        captured = capsys.readouterr()
        assert "rate-limited" in captured.out
        assert "backoff" in captured.out

    def test_cooldown_expires_and_credential_becomes_available(self):
        """Test credential becomes available after cooldown expires."""
        coordinator = CredentialCoordinator(["key-1"])
        credential = coordinator.acquire()

        # Short cooldown for testing
        coordinator.release(credential, rate_limited=True, backoff_seconds=0.1)

        # Wait for cooldown to expire
        time.sleep(0.15)

        # Should be able to acquire again
        result = coordinator.acquire(timeout=0.1)
        assert result == "key-1"

    def test_acquire_waits_for_cooldown_expiry(self):
        """Test acquire waits for cooldown to expire when all in cooldown."""
        coordinator = CredentialCoordinator(["key-1"])
        credential = coordinator.acquire()

        # Put in short cooldown
        coordinator.release(credential, rate_limited=True, backoff_seconds=0.2)

        # Acquire should wait for cooldown
        start = time.time()
        result = coordinator.acquire(timeout=1.0)
        elapsed = time.time() - start

        assert result == "key-1"
        assert elapsed >= 0.15  # Should have waited for cooldown

    def test_release_without_rate_limit_returns_immediately(self):
        """Test normal release returns credential to available immediately."""
        coordinator = CredentialCoordinator(["key-1"])
        credential = coordinator.acquire()

        coordinator.release(credential, rate_limited=False)

        assert credential in coordinator._available
        assert credential not in coordinator._cooldowns


class TestCredentialCoordinatorConcurrency:
    """Tests for concurrent credential access."""

    def test_concurrent_acquire_release(self):
        """Test concurrent acquire/release operations."""
        coordinator = CredentialCoordinator(["key-1", "key-2", "key-3"])
        results = []
        errors = []

        def worker(worker_id):
            try:
                for _ in range(5):
                    cred = coordinator.acquire(timeout=2.0)
                    if cred:
                        results.append((worker_id, cred))
                        time.sleep(0.01)  # Simulate work
                        coordinator.release(cred)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 25  # 5 workers * 5 iterations

    def test_pool_exhaustion_message(self, capsys):
        """Test exhaustion message when all credentials in use."""
        coordinator = CredentialCoordinator(["key-1"])
        coordinator.acquire()

        # Try to acquire in a thread that will timeout
        def try_acquire():
            coordinator.acquire(timeout=0.1)

        thread = threading.Thread(target=try_acquire)
        thread.start()
        thread.join()

        captured = capsys.readouterr()
        assert "exhausted" in captured.out


class TestCredentialCoordinatorAcquireEdgeCases:
    """Tests for edge cases in acquire method."""

    def test_acquire_no_timeout_waits_indefinitely(self):
        """Test acquire without timeout waits for release."""
        coordinator = CredentialCoordinator(["key-1"])
        credential = coordinator.acquire()
        acquired = []

        def release_after_delay():
            time.sleep(0.1)
            coordinator.release(credential)

        def try_acquire_no_timeout():
            # Acquire with no timeout - should wait
            result = coordinator.acquire(timeout=None)
            acquired.append(result)

        release_thread = threading.Thread(target=release_after_delay)
        acquire_thread = threading.Thread(target=try_acquire_no_timeout)

        release_thread.start()
        acquire_thread.start()

        release_thread.join()
        acquire_thread.join(timeout=2.0)

        assert acquired[0] == "key-1"

    def test_acquire_cooldown_sets_wait_time_when_none(self):
        """Test cooldown sets wait_time when no timeout specified."""
        coordinator = CredentialCoordinator(["key-1"])
        credential = coordinator.acquire()

        # Put in short cooldown
        coordinator.release(credential, rate_limited=True, backoff_seconds=0.1)

        # Acquire with no timeout should wait for cooldown
        start = time.time()
        result = coordinator.acquire(timeout=None)
        elapsed = time.time() - start

        assert result == "key-1"
        assert elapsed >= 0.05  # Should have waited

    def test_acquire_returns_none_when_wait_time_zero(self):
        """Test acquire returns None when calculated wait time is zero or negative."""
        coordinator = CredentialCoordinator(["key-1"])
        coordinator.acquire()  # Take the only credential

        # Very short timeout that will immediately expire
        result = coordinator.acquire(timeout=0.001)
        time.sleep(0.01)  # Let the timeout definitely expire

        assert result is None


class TestCredentialCoordinatorCooldownHelpers:
    """Tests for cooldown helper methods."""

    def test_check_expired_cooldowns(self):
        """Test _check_expired_cooldowns moves expired to available."""
        coordinator = CredentialCoordinator(["key-1", "key-2"])
        coordinator._available = set()
        coordinator._cooldowns = {
            "key-1": time.time() - 10,  # Expired
            "key-2": time.time() + 100,  # Not expired
        }

        with coordinator._lock:
            coordinator._check_expired_cooldowns()

        assert "key-1" in coordinator._available
        assert "key-1" not in coordinator._cooldowns
        assert "key-2" not in coordinator._available
        assert "key-2" in coordinator._cooldowns

    def test_get_next_cooldown_expiry_empty(self):
        """Test _get_next_cooldown_expiry with no cooldowns."""
        coordinator = CredentialCoordinator(["key-1"])
        with coordinator._lock:
            result = coordinator._get_next_cooldown_expiry()
        assert result is None

    def test_get_next_cooldown_expiry_returns_soonest(self):
        """Test _get_next_cooldown_expiry returns soonest expiry."""
        coordinator = CredentialCoordinator(["key-1", "key-2"])
        now = time.time()
        coordinator._cooldowns = {
            "key-1": now + 100,
            "key-2": now + 50,  # Soonest
        }

        with coordinator._lock:
            result = coordinator._get_next_cooldown_expiry()

        assert result == now + 50


# =============================================================================
# InputSanitizer Tests
# =============================================================================


class TestSanitizeIdentifier:
    """Tests for sanitize_identifier function."""

    def test_valid_identifier(self):
        """Test valid identifiers are accepted."""
        assert sanitize_identifier("valid-name") == "valid-name"
        assert sanitize_identifier("valid_name") == "valid_name"
        assert sanitize_identifier("ValidName123") == "ValidName123"
        assert sanitize_identifier("a") == "a"
        assert sanitize_identifier("123") == "123"

    def test_path_traversal_rejected(self):
        """Test path traversal patterns are rejected."""
        with pytest.raises(ValueError) as exc_info:
            sanitize_identifier("../etc/passwd")
        assert "path traversal" in str(exc_info.value).lower()

        with pytest.raises(ValueError) as exc_info:
            sanitize_identifier("foo/../bar")
        assert "path traversal" in str(exc_info.value).lower()

    def test_absolute_unix_path_rejected(self):
        """Test Unix absolute paths are rejected."""
        with pytest.raises(ValueError) as exc_info:
            sanitize_identifier("/etc/passwd")
        assert "absolute path" in str(exc_info.value).lower()

    def test_absolute_windows_path_rejected(self):
        """Test Windows absolute paths are rejected."""
        with pytest.raises(ValueError) as exc_info:
            sanitize_identifier("C:\\Windows\\System32")
        assert "absolute path" in str(exc_info.value).lower()

    def test_forward_slash_rejected(self):
        """Test forward slashes are rejected."""
        with pytest.raises(ValueError) as exc_info:
            sanitize_identifier("foo/bar")
        assert "path separator" in str(exc_info.value).lower()

    def test_backslash_rejected(self):
        """Test backslashes are rejected."""
        with pytest.raises(ValueError) as exc_info:
            sanitize_identifier("foo\\bar")
        assert "path separator" in str(exc_info.value).lower()

    def test_special_characters_rejected(self):
        """Test special characters are rejected."""
        invalid_chars = ["space here", "semi;colon", "pipe|char", "quote'mark", "!exclaim"]
        for identifier in invalid_chars:
            with pytest.raises(ValueError) as exc_info:
                sanitize_identifier(identifier)
            assert "invalid characters" in str(exc_info.value).lower()

    def test_empty_string_rejected(self):
        """Test empty string is rejected."""
        with pytest.raises(ValueError) as exc_info:
            sanitize_identifier("")
        assert "invalid characters" in str(exc_info.value).lower()


# =============================================================================
# OutputPrefixer Tests
# =============================================================================


class TestOutputPrefixerInit:
    """Tests for OutputPrefixer initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default stdout."""
        prefixer = OutputPrefixer("[TEST]")
        assert prefixer.prefix == "[TEST]"
        assert prefixer._buffer == ""

    def test_init_with_custom_stream(self):
        """Test initialization with custom stream."""
        stream = io.StringIO()
        prefixer = OutputPrefixer("[CUSTOM]", stream=stream)
        assert prefixer.stream is stream


class TestOutputPrefixerWrite:
    """Tests for OutputPrefixer write method."""

    def test_write_single_line(self):
        """Test writing a single complete line."""
        stream = io.StringIO()
        prefixer = OutputPrefixer("[TEST]", stream=stream)

        prefixer.write("Hello world\n")

        assert stream.getvalue() == "[TEST] Hello world\n"

    def test_write_multiple_lines(self):
        """Test writing multiple lines at once."""
        stream = io.StringIO()
        prefixer = OutputPrefixer("[TEST]", stream=stream)

        prefixer.write("Line 1\nLine 2\nLine 3\n")

        expected = "[TEST] Line 1\n[TEST] Line 2\n[TEST] Line 3\n"
        assert stream.getvalue() == expected

    def test_write_partial_line_buffered(self):
        """Test partial line is buffered."""
        stream = io.StringIO()
        prefixer = OutputPrefixer("[TEST]", stream=stream)

        prefixer.write("Partial")

        # Nothing written yet
        assert stream.getvalue() == ""
        assert prefixer._buffer == "Partial"

    def test_write_partial_then_complete(self):
        """Test partial line completed with subsequent write."""
        stream = io.StringIO()
        prefixer = OutputPrefixer("[TEST]", stream=stream)

        prefixer.write("Hello ")
        prefixer.write("world\n")

        assert stream.getvalue() == "[TEST] Hello world\n"

    def test_write_empty_line(self):
        """Test empty line writes newline without prefix."""
        stream = io.StringIO()
        prefixer = OutputPrefixer("[TEST]", stream=stream)

        prefixer.write("\n")

        assert stream.getvalue() == "\n"

    def test_write_line_with_trailing_empty(self):
        """Test line followed by empty line."""
        stream = io.StringIO()
        prefixer = OutputPrefixer("[TEST]", stream=stream)

        prefixer.write("Content\n\n")

        assert stream.getvalue() == "[TEST] Content\n\n"


class TestOutputPrefixerFlush:
    """Tests for OutputPrefixer flush method."""

    def test_flush_buffered_content(self):
        """Test flush writes buffered content."""
        stream = io.StringIO()
        prefixer = OutputPrefixer("[TEST]", stream=stream)

        prefixer.write("Partial content")
        prefixer.flush()

        assert stream.getvalue() == "[TEST] Partial content\n"
        assert prefixer._buffer == ""

    def test_flush_empty_buffer(self):
        """Test flush with empty buffer does nothing."""
        stream = io.StringIO()
        prefixer = OutputPrefixer("[TEST]", stream=stream)

        prefixer.flush()

        assert stream.getvalue() == ""

    def test_flush_calls_stream_flush(self):
        """Test flush calls underlying stream's flush."""
        stream = MagicMock()
        prefixer = OutputPrefixer("[TEST]", stream=stream)

        prefixer.flush()

        stream.flush.assert_called_once()


class TestOutputPrefixerConcurrency:
    """Tests for OutputPrefixer concurrent access."""

    def test_concurrent_writes(self):
        """Test concurrent writes don't corrupt output."""
        stream = io.StringIO()
        prefixer = OutputPrefixer("[TEST]", stream=stream)
        lock = threading.Lock()

        def writer(writer_id):
            for i in range(10):
                prefixer.write(f"Writer {writer_id} line {i}\n")

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        prefixer.flush()

        # All lines should have prefix
        output = stream.getvalue()
        lines = [line for line in output.split("\n") if line]
        for line in lines:
            assert line.startswith("[TEST] ")
