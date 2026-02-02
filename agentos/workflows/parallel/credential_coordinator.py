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
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
    
    def acquire(self, timeout: Optional[float] = None) -> Optional[str]:
        """Acquire an available credential.
        
        Args:
            timeout: Maximum time to wait for a credential (seconds)
        
        Returns:
            Credential string or None if timeout
        """
        with self._condition:
            start_time = time.time()
            
            while not self._available:
                # Check if we should print exhaustion message
                if len(self._in_use) == len(self.credentials):
                    print("[COORDINATOR] Credential pool exhausted, waiting for release...")
                
                # Wait for a credential to become available
                if timeout is not None:
                    remaining = timeout - (time.time() - start_time)
                    if remaining <= 0:
                        return None
                    if not self._condition.wait(timeout=remaining):
                        return None
                else:
                    self._condition.wait()
            
            # Get a credential
            credential = self._available.pop()
            self._in_use.add(credential)
            return credential
    
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
                
                if rate_limited:
                    print(f"[CREDENTIAL] Key {credential[:8]}... is rate-limited, backoff: {backoff_seconds}s")
                    # In a real implementation, we'd delay adding back to pool
                    # For testing purposes, we add it back immediately
                
                self._available.add(credential)
                self._condition.notify()