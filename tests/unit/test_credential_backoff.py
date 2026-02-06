"""TDD tests for CredentialCoordinator rate-limit backoff.

Issue #149: Implement rate-limit backoff in CredentialCoordinator.

These tests verify the credential cooldown behavior:
1. Rate-limited credential is NOT immediately available
2. Credential becomes available after backoff expires
3. Multiple credentials can be in cooldown simultaneously
"""

import time
import threading
from unittest.mock import patch

import pytest

from assemblyzero.workflows.parallel import CredentialCoordinator


class TestCredentialBackoff:
    """Tests for rate-limit backoff functionality."""

    def test_rate_limited_credential_not_immediately_available(self):
        """Rate-limited credential should NOT be immediately available.

        When a credential is released with rate_limited=True, it should
        go into cooldown and not be acquirable until backoff expires.
        """
        # Arrange - single credential
        coordinator = CredentialCoordinator(["key1"])

        # Acquire the only credential
        key = coordinator.acquire(timeout=0.1)
        assert key == "key1"

        # Release with rate limit (30 second backoff)
        coordinator.release(key, rate_limited=True, backoff_seconds=30.0)

        # Act - Try to acquire again immediately
        result = coordinator.acquire(timeout=0.1)

        # Assert - Should NOT get the credential back immediately
        assert result is None, (
            "Rate-limited credential should NOT be immediately available. "
            "Current implementation adds it back to pool immediately."
        )

    def test_credential_available_after_backoff_expires(self):
        """Credential should become available after backoff period expires."""
        # Arrange - single credential with short backoff
        coordinator = CredentialCoordinator(["key1"])

        key = coordinator.acquire(timeout=0.1)
        assert key == "key1"

        # Release with very short backoff (0.2 seconds for testing)
        coordinator.release(key, rate_limited=True, backoff_seconds=0.2)

        # Act - Wait for backoff to expire
        time.sleep(0.3)

        # Try to acquire
        result = coordinator.acquire(timeout=0.1)

        # Assert - Should get credential after backoff
        assert result == "key1", (
            "Credential should become available after backoff expires"
        )

    def test_multiple_credentials_can_be_in_cooldown(self):
        """Multiple credentials can be in cooldown simultaneously."""
        # Arrange - multiple credentials
        coordinator = CredentialCoordinator(["key1", "key2", "key3"])

        # Acquire all credentials
        keys = []
        for _ in range(3):
            key = coordinator.acquire(timeout=0.1)
            assert key is not None
            keys.append(key)

        # Release all with rate limit
        for key in keys:
            coordinator.release(key, rate_limited=True, backoff_seconds=30.0)

        # Act - Try to acquire any credential immediately
        result = coordinator.acquire(timeout=0.1)

        # Assert - No credentials should be available
        assert result is None, (
            "No credentials should be available when all are in cooldown"
        )

    def test_non_rate_limited_release_immediately_available(self):
        """Non-rate-limited release should make credential immediately available."""
        # Arrange - single credential
        coordinator = CredentialCoordinator(["key1"])

        key = coordinator.acquire(timeout=0.1)
        assert key == "key1"

        # Release without rate limit
        coordinator.release(key, rate_limited=False)

        # Act - Try to acquire again immediately
        result = coordinator.acquire(timeout=0.1)

        # Assert - Should get credential back immediately
        assert result == "key1", (
            "Non-rate-limited credential should be immediately available"
        )

    def test_mixed_cooldown_and_available_credentials(self):
        """Some credentials in cooldown while others are available."""
        # Arrange
        coordinator = CredentialCoordinator(["key1", "key2"])

        # Acquire both
        key1 = coordinator.acquire(timeout=0.1)
        key2 = coordinator.acquire(timeout=0.1)
        assert key1 is not None
        assert key2 is not None

        # Release key1 with rate limit, key2 without
        coordinator.release(key1, rate_limited=True, backoff_seconds=30.0)
        coordinator.release(key2, rate_limited=False)

        # Act - Acquire should return the non-rate-limited one
        result = coordinator.acquire(timeout=0.1)

        # Assert - Should get key2 (the non-rate-limited one)
        assert result == key2, (
            "Should acquire non-rate-limited credential, not the one in cooldown"
        )

        # Second acquire should fail (key1 in cooldown)
        result2 = coordinator.acquire(timeout=0.1)
        assert result2 is None, (
            "Second acquire should fail as only rate-limited credential remains"
        )

    def test_cooldown_expires_at_correct_time(self):
        """Verify cooldown expires precisely when expected."""
        # Arrange
        coordinator = CredentialCoordinator(["key1"])

        key = coordinator.acquire(timeout=0.1)
        backoff = 0.5  # 500ms backoff

        # Release with rate limit
        coordinator.release(key, rate_limited=True, backoff_seconds=backoff)

        # Act - Check before expiry
        time.sleep(0.3)  # Wait 300ms (before 500ms expiry)
        result_before = coordinator.acquire(timeout=0.05)

        # Wait for expiry
        time.sleep(0.3)  # Total 600ms (after 500ms expiry)
        result_after = coordinator.acquire(timeout=0.05)

        # Assert
        assert result_before is None, "Credential should not be available before backoff expires"
        assert result_after == "key1", "Credential should be available after backoff expires"

    def test_thread_safety_during_cooldown_expiry(self):
        """Multiple threads waiting for cooldown-released credential."""
        # Arrange
        coordinator = CredentialCoordinator(["key1"])

        key = coordinator.acquire(timeout=0.1)

        # Release with short backoff
        coordinator.release(key, rate_limited=True, backoff_seconds=0.2)

        acquired_by = []
        lock = threading.Lock()

        def try_acquire(thread_id):
            result = coordinator.acquire(timeout=1.0)
            if result:
                with lock:
                    acquired_by.append(thread_id)

        # Act - Start multiple threads trying to acquire
        threads = [threading.Thread(target=try_acquire, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Assert - Exactly one thread should have acquired the credential
        assert len(acquired_by) == 1, (
            f"Exactly one thread should acquire the credential, but {len(acquired_by)} did"
        )


class TestCredentialBackoffEdgeCases:
    """Edge case tests for rate-limit backoff."""

    def test_zero_backoff_immediately_available(self):
        """Zero backoff should make credential immediately available."""
        # Arrange
        coordinator = CredentialCoordinator(["key1"])

        key = coordinator.acquire(timeout=0.1)

        # Release with rate limit but zero backoff
        coordinator.release(key, rate_limited=True, backoff_seconds=0.0)

        # Act
        result = coordinator.acquire(timeout=0.1)

        # Assert - Zero backoff means immediately available
        assert result == "key1", (
            "Zero backoff should make credential immediately available"
        )

    def test_very_long_backoff(self):
        """Very long backoff should keep credential unavailable."""
        # Arrange
        coordinator = CredentialCoordinator(["key1"])

        key = coordinator.acquire(timeout=0.1)

        # Release with very long backoff (1 hour)
        coordinator.release(key, rate_limited=True, backoff_seconds=3600.0)

        # Act - Try to acquire immediately
        result = coordinator.acquire(timeout=0.1)

        # Assert
        assert result is None, (
            "Credential with long backoff should not be available"
        )

    def test_backoff_with_notification_wakeup(self):
        """Threads should be notified when cooldown credentials expire."""
        # This tests that the implementation properly notifies waiting threads
        # when a credential comes out of cooldown

        # Arrange
        coordinator = CredentialCoordinator(["key1"])

        key = coordinator.acquire(timeout=0.1)
        coordinator.release(key, rate_limited=True, backoff_seconds=0.3)

        acquired = []

        def waiting_thread():
            # This thread should wait for the credential to become available
            result = coordinator.acquire(timeout=1.0)
            if result:
                acquired.append(result)

        # Act
        t = threading.Thread(target=waiting_thread)
        start = time.time()
        t.start()
        t.join(timeout=2.0)
        duration = time.time() - start

        # Assert
        assert len(acquired) == 1, "Thread should eventually acquire the credential"
        assert acquired[0] == "key1"
        # Should complete in roughly the backoff time, not the full timeout
        assert duration < 1.0, f"Should complete in ~0.3s, took {duration:.2f}s"
