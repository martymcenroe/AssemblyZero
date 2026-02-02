# File: agentos/workflows/parallel/credential_coordinator.py

```python
"""Thread-safe credential reservation system with rate-limit tracking."""

import os
import threading
import time
from typing import Dict, List, Optional


class CredentialCoordinator:
    """Manages API credential pool with rate-limit tracking."""
    
    RATE_LIMIT_BACKOFF_SECONDS = 60
    
    def __init__(self, credentials: List[str]):
        """Initialize the credential coordinator.
        
        Args:
            credentials: List of API credentials
        """
        self.credentials = credentials
        self._available = set(credentials)
        self._in_use = set()
        self._rate_limited: Dict[str, float] = {}
        self._lock = threading.Lock()
        
    def acquire(self, timeout: float = 30.0) -> Optional[str]:
        """Acquire an available credential.
        
        Args:
            timeout: Maximum time to wait for a credential (seconds)
            
        Returns:
            Credential string or None if exhausted
        """
        start_time = time.time()
        simulate_429 = os.environ.get("AGENTOS_SIMULATE_429") == "true"
        
        while time.time() - start_time < timeout:
            with self._lock:
                # Clean up expired rate limits
                self._cleanup_rate_limits()
                
                # Find available credential
                available = self._available - self._rate_limited.keys()
                
                if available:
                    credential = available.pop()
                    self._available.remove(credential)
                    self._in_use.add(credential)
                    
                    # Simulate rate limit for testing
                    if simulate_429:
                        self._mark_rate_limited(credential)
                        self._in_use.remove(credential)
                        self._available.add(credential)
                        # Try again with different credential
                        available = self._available - self._rate_limited.keys()
                        if available:
                            credential = available.pop()
                            self._available.remove(credential)
                            self._in_use.add(credential)
                            return credential
                    
                    return credential
                    
            # Wait a bit before retrying
            time.sleep(0.1)
            
        return None
        
    def release(self, credential: str) -> None:
        """Release a credential back to the pool.
        
        Args:
            credential: Credential to release
        """
        with self._lock:
            if credential in self._in_use:
                self._in_use.remove(credential)
                self._available.add(credential)
                
    def mark_rate_limited(self, credential: str) -> None:
        """Mark a credential as rate-limited.
        
        Args:
            credential: Credential that hit rate limit
        """
        with self._lock:
            self._mark_rate_limited(credential)
            
    def _mark_rate_limited(self, credential: str) -> None:
        """Internal method to mark credential as rate-limited.
        
        Args:
            credential: Credential that hit rate limit
        """
        self._rate_limited[credential] = time.time() + self.RATE_LIMIT_BACKOFF_SECONDS
        print(f"[CREDENTIAL] Credential rate-limited, backoff until {self._rate_limited[credential]}")
        
    def _cleanup_rate_limits(self) -> None:
        """Remove expired rate limits."""
        current_time = time.time()
        expired = [
            cred for cred, expiry in self._rate_limited.items()
            if current_time >= expiry
        ]
        for cred in expired:
            del self._rate_limited[cred]
            
    def get_stats(self) -> Dict[str, int]:
        """Get current pool statistics.
        
        Returns:
            Dictionary with pool stats
        """
        with self._lock:
            return {
                'total': len(self.credentials),
                'available': len(self._available - self._rate_limited.keys()),
                'in_use': len(self._in_use),
                'rate_limited': len(self._rate_limited),
            }
```