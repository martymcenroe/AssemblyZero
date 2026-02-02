# File: agentos/workflows/parallel/credential_coordinator.py

```python
"""Thread-safe credential reservation and rate-limit tracking."""

import os
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class CredentialState:
    """State tracking for a single credential."""
    key: str
    reserved_by: Optional[str] = None
    rate_limited_until: float = 0.0
    
    @property
    def is_available(self) -> bool:
        """Check if credential is available for use."""
        if self.reserved_by is not None:
            return False
        if self.rate_limited_until > time.time():
            return False
        return True


class CredentialCoordinator:
    """Manages thread-safe credential reservation with rate-limit tracking."""
    
    RATE_LIMIT_BACKOFF_SECONDS = 60
    
    def __init__(self, credentials: List[str]):
        """Initialize coordinator with list of credentials.
        
        Args:
            credentials: List of API keys or credential strings
        """
        self._credentials: Dict[str, CredentialState] = {
            key: CredentialState(key=key)
            for key in credentials
        }
        self._lock = threading.Lock()
    
    def reserve_credential(self, requester_id: str) -> Optional[str]:
        """Reserve an available credential for use.
        
        Args:
            requester_id: Identifier of the requester
            
        Returns:
            Reserved credential key or None if pool exhausted
        """
        with self._lock:
            # Check for simulated 429 error
            if os.environ.get("AGENTOS_SIMULATE_429") == "true":
                # Mark first credential as rate-limited
                first_key = list(self._credentials.keys())[0]
                self._credentials[first_key].rate_limited_until = time.time() + self.RATE_LIMIT_BACKOFF_SECONDS
                # Clear env var so it only triggers once
                del os.environ["AGENTOS_SIMULATE_429"]
            
            # Find available credential
            for state in self._credentials.values():
                if state.is_available:
                    state.reserved_by = requester_id
                    return state.key
            
            return None
    
    def release_credential(self, credential_key: str):
        """Release a reserved credential back to the pool.
        
        Args:
            credential_key: The credential key to release
        """
        with self._lock:
            if credential_key in self._credentials:
                self._credentials[credential_key].reserved_by = None
    
    def mark_rate_limited(self, credential_key: str, backoff_seconds: Optional[int] = None):
        """Mark a credential as rate-limited.
        
        Args:
            credential_key: The credential to mark
            backoff_seconds: Optional custom backoff duration
        """
        if backoff_seconds is None:
            backoff_seconds = self.RATE_LIMIT_BACKOFF_SECONDS
            
        with self._lock:
            if credential_key in self._credentials:
                self._credentials[credential_key].rate_limited_until = time.time() + backoff_seconds
                self._credentials[credential_key].reserved_by = None
    
    def get_available_count(self) -> int:
        """Get count of currently available credentials.
        
        Returns:
            Number of available credentials
        """
        with self._lock:
            return sum(1 for state in self._credentials.values() if state.is_available)
    
    def get_stats(self) -> Dict[str, int]:
        """Get current pool statistics.
        
        Returns:
            Dictionary with counts of available, reserved, and rate-limited credentials
        """
        with self._lock:
            available = sum(1 for state in self._credentials.values() if state.is_available)
            reserved = sum(1 for state in self._credentials.values() if state.reserved_by is not None)
            rate_limited = sum(1 for state in self._credentials.values() 
                             if state.rate_limited_until > time.time())
            
            return {
                "total": len(self._credentials),
                "available": available,
                "reserved": reserved,
                "rate_limited": rate_limited,
            }
```