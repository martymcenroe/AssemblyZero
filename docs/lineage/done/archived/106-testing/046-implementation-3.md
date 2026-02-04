# File: agentos/workflows/parallel/credential_coordinator.py

```python
"""Thread-safe credential reservation system with rate-limit tracking."""

import threading
import time
from typing import List, Optional, Set
from dataclasses import dataclass, field


@dataclass
class CredentialStatus:
    """Track the status of a credential."""
    key: str
    in_use: bool = False
    rate_limited_until: float = 0.0
    
    def is_available(self) -> bool:
        """Check if credential is available for use."""
        if self.in_use:
            return False
        if self.rate_limited_until > time.time():
            return False
        return True


class CredentialCoordinator:
    """Manages a pool of API credentials with rate-limit tracking.
    
    Thread-safe credential reservation and release with automatic
    rate-limit backoff handling.
    """
    
    def __init__(self, credentials: List[str]):
        """Initialize the credential coordinator.
        
        Args:
            credentials: List of API credentials to manage
        """
        self._credentials = {
            key: CredentialStatus(key=key)
            for key in credentials
        }
        self._lock = threading.Lock()
        self._available = threading.Condition(self._lock)
    
    def acquire(self, timeout: Optional[float] = None) -> Optional[str]:
        """Acquire an available credential.
        
        Blocks until a credential is available or timeout expires.
        
        Args:
            timeout: Maximum time to wait for a credential (None = wait forever)
            
        Returns:
            The acquired credential key, or None if timeout expired
        """
        end_time = time.time() + timeout if timeout else None
        
        with self._available:
            while True:
                # Try to find an available credential
                for status in self._credentials.values():
                    if status.is_available():
                        status.in_use = True
                        return status.key
                
                # No credentials available
                print("[COORDINATOR] Credential pool exhausted, waiting...")
                
                # Calculate wait time
                if end_time:
                    wait_time = end_time - time.time()
                    if wait_time <= 0:
                        return None
                else:
                    wait_time = None
                
                # Wait for a credential to become available
                self._available.wait(timeout=wait_time)
    
    def release(self, key: str, rate_limited: bool = False, backoff_seconds: float = 60.0) -> None:
        """Release a credential back to the pool.
        
        Args:
            key: The credential key to release
            rate_limited: Whether the credential hit a rate limit
            backoff_seconds: How long to wait before retrying if rate limited
        """
        with self._available:
            if key in self._credentials:
                status = self._credentials[key]
                status.in_use = False
                
                if rate_limited:
                    status.rate_limited_until = time.time() + backoff_seconds
                    print(f"[COORDINATOR] Credential {key} rate-limited, backing off for {backoff_seconds}s")
                
                # Notify waiting threads
                self._available.notify_all()
    
    def mark_rate_limited(self, key: str, backoff_seconds: float = 60.0) -> None:
        """Mark a credential as rate-limited without releasing it.
        
        Args:
            key: The credential key to mark
            backoff_seconds: How long to wait before retrying
        """
        with self._lock:
            if key in self._credentials:
                self._credentials[key].rate_limited_until = time.time() + backoff_seconds
```