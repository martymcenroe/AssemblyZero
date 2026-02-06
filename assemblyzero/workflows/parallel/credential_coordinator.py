"""Thread-safe credential reservation system with rate-limit tracking."""

import threading
import time
from typing import List, Optional


class CredentialCoordinator:
    """Manages API credentials with thread-safe reservation and rate limiting."""
    
    def __init__(self, credentials: List[str]):
        """Initialize credential coordinator.

        Args:
            credentials: List of API keys/credentials
        """
        self.credentials = credentials
        self._available = set(credentials)
        self._in_use = set()
        self._cooldowns: dict[str, float] = {}  # credential -> expiry timestamp
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
    
    def _check_expired_cooldowns(self) -> None:
        """Move expired cooldowns back to available pool.

        Must be called while holding the lock.
        """
        current_time = time.time()
        expired = [
            cred for cred, expiry in self._cooldowns.items()
            if current_time >= expiry
        ]
        for cred in expired:
            del self._cooldowns[cred]
            self._available.add(cred)

    def _get_next_cooldown_expiry(self) -> Optional[float]:
        """Get the soonest cooldown expiry time.

        Must be called while holding the lock.
        Returns None if no cooldowns pending.
        """
        if not self._cooldowns:
            return None
        return min(self._cooldowns.values())

    def acquire(self, timeout: Optional[float] = None) -> Optional[str]:
        """Acquire an available credential.

        Args:
            timeout: Maximum time to wait for a credential (seconds)

        Returns:
            Credential string or None if timeout
        """
        with self._condition:
            start_time = time.time()

            while True:
                # Check for expired cooldowns
                self._check_expired_cooldowns()

                if self._available:
                    # Get a credential
                    credential = self._available.pop()
                    self._in_use.add(credential)
                    return credential

                # No available credentials - determine wait time
                # Check if we should print exhaustion message
                if len(self._in_use) + len(self._cooldowns) == len(self.credentials):
                    print("[COORDINATOR] Credential pool exhausted, waiting for release...")

                # Calculate how long to wait
                if timeout is not None:
                    remaining = timeout - (time.time() - start_time)
                    if remaining <= 0:
                        return None
                    wait_time = remaining
                else:
                    wait_time = None

                # If credentials are in cooldown, wait until soonest expiry
                next_expiry = self._get_next_cooldown_expiry()
                if next_expiry is not None:
                    cooldown_wait = next_expiry - time.time()
                    if cooldown_wait > 0:
                        if wait_time is None:
                            wait_time = cooldown_wait
                        else:
                            wait_time = min(wait_time, cooldown_wait)

                # Wait for notification or timeout
                if wait_time is not None and wait_time <= 0:
                    return None

                if wait_time is not None:
                    self._condition.wait(timeout=wait_time)
                else:
                    self._condition.wait()
    
    def release(
        self,
        credential: str,
        rate_limited: bool = False,
        backoff_seconds: float = 0,
    ) -> None:
        """Release a credential back to the pool.

        Args:
            credential: Credential to release
            rate_limited: Whether the credential hit a rate limit
            backoff_seconds: Backoff time before credential can be reused
        """
        with self._condition:
            if credential in self._in_use:
                self._in_use.remove(credential)

                if rate_limited and backoff_seconds > 0:
                    print(f"[CREDENTIAL] Key {credential[:8]}... is rate-limited, backoff: {backoff_seconds}s")
                    # Put credential in cooldown until backoff expires
                    self._cooldowns[credential] = time.time() + backoff_seconds
                else:
                    self._available.add(credential)

                self._condition.notify()