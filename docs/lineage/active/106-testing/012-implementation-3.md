# File: agentos/workflows/parallel/credential_coordinator.py

```python
"""Thread-safe credential reservation system with rate-limit tracking."""

import os
import threading
import time
from typing import Optional, Set
from dataclasses import dataclass, field


@dataclass
class CredentialState:
    """State for a single credential (API key)."""
    key_id: str
    in_use: bool = False
    rate_limited_until: Optional[float] = None
    

class CredentialCoordinator:
    """Thread-safe credential pool manager with rate-limit tracking.
    
    Manages a pool of API credentials, ensuring:
    1. Only one worker uses a credential at a time
    2. Rate-limited credentials are not assigned until backoff expires
    3. Workers can wait for available credentials
    """
    
    def __init__(self, credentials: list[str]):
        """Initialize the credential coordinator.
        
        Args:
            credentials: List of API keys/credentials to manage
        """
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._credentials = {
            cred: CredentialState(key_id=cred)
            for cred in credentials
        }
        
    def reserve(self, timeout: Optional[float] = None) -> Optional[str]:
        """Reserve an available credential.
        
        Args:
            timeout: Maximum time to wait for a credential (None = wait forever)
            
        Returns:
            The reserved credential key, or None if timeout expired
        """
        start_time = time.time()
        
        with self._condition:
            while True:
                # Check for available credentials
                now = time.time()
                for cred_id, state in self._credentials.items():
                    # Skip if in use
                    if state.in_use:
                        continue
                        
                    # Skip if rate limited
                    if state.rate_limited_until and state.rate_limited_until > now:
                        continue
                        
                    # Found available credential
                    state.in_use = True
                    state.rate_limited_until = None
                    return cred_id
                
                # No credentials available
                print("[COORDINATOR] Credential pool exhausted")
                
                # Check timeout
                if timeout is not None:
                    elapsed = time.time() - start_time
                    if elapsed >= timeout:
                        return None
                    remaining = timeout - elapsed
                    self._condition.wait(timeout=remaining)
                else:
                    self._condition.wait()
                    
    def release(self, credential: str):
        """Release a credential back to the pool.
        
        Args:
            credential: The credential to release
        """
        with self._condition:
            if credential in self._credentials:
                self._credentials[credential].in_use = False
                self._condition.notify_all()
                
    def mark_rate_limited(self, credential: str, backoff_seconds: float = 60.0):
        """Mark a credential as rate-limited.
        
        Args:
            credential: The credential that hit rate limit
            backoff_seconds: How long to wait before using this credential again
        """
        with self._condition:
            if credential in self._credentials:
                state = self._credentials[credential]
                state.rate_limited_until = time.time() + backoff_seconds
                state.in_use = False
                self._condition.notify_all()
                
    def get_available_count(self) -> int:
        """Get the number of currently available credentials.
        
        Returns:
            Number of credentials that can be reserved right now
        """
        with self._lock:
            now = time.time()
            return sum(
                1 for state in self._credentials.values()
                if not state.in_use and (
                    state.rate_limited_until is None or 
                    state.rate_limited_until <= now
                )
            )
```