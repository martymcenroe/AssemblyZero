# File: agentos/workflows/parallel/credential_coordinator.py

```python
"""Thread-safe credential management for parallel workflows."""

import os
import threading
import time
from typing import List, Optional, Set


class CredentialCoordinator:
    """Manages credential pool for parallel API access."""
    
    RATE_LIMIT_BACKOFF_SECONDS = 60
    
    def __init__(self, credentials: List[str]):
        """Initialize credential coordinator.
        
        Args:
            credentials: List of API keys/credentials
            
        Raises:
            ValueError: If no credentials provided
        """
        if not credentials:
            raise ValueError("At least one credential is required")
        
        self._all_credentials = credentials.copy()
        self._available_credentials = credentials.copy()
        self._in_use_credentials: Set[str] = set()
        self._rate_limited_credentials: dict[str, float] = {}
        self._lock = threading.Lock()
    
    def acquire_credential(self) -> Optional[str]:
        """Acquire an available credential.
        
        Returns:
            Credential string or None if pool is exhausted
        """
        with self._lock:
            # Remove expired rate limits
            self._cleanup_rate_limits()
            
            # Check for simulated 429 (testing)
            if os.environ.get("AGENTOS_SIMULATE_429") == "true":
                return self._handle_simulated_rate_limit()
            
            # Try to get an available credential
            if self._available_credentials:
                credential = self._available_credentials.pop(0)
                self._in_use_credentials.add(credential)
                return credential
            
            return None
    
    def release_credential(self, credential: str) -> None:
        """Release a credential back to the pool.
        
        Args:
            credential: The credential to release
            
        Raises:
            ValueError: If credential was not in use
        """
        with self._lock:
            if credential not in self._in_use_credentials:
                raise ValueError(f"Credential was not in use: {credential}")
            
            self._in_use_credentials.remove(credential)
            
            # Only return to available pool if not rate-limited
            if credential not in self._rate_limited_credentials:
                self._available_credentials.append(credential)
    
    def mark_rate_limited(self, credential: str) -> None:
        """Mark a credential as rate-limited.
        
        Args:
            credential: The credential that hit rate limit
            
        Raises:
            ValueError: If credential is not recognized
        """
        with self._lock:
            if credential not in self._all_credentials:
                raise ValueError(f"Unknown credential: {credential}")
            
            # Remove from available pool if present
            if credential in self._available_credentials:
                self._available_credentials.remove(credential)
            
            # Mark with backoff timestamp
            self._rate_limited_credentials[credential] = (
                time.time() + self.RATE_LIMIT_BACKOFF_SECONDS
            )
            
            print(f"[CREDENTIAL] Marked {credential[:8]}... as rate-limited for {self.RATE_LIMIT_BACKOFF_SECONDS}s")
    
    def _cleanup_rate_limits(self) -> None:
        """Remove expired rate limits and return credentials to pool."""
        current_time = time.time()
        expired = []
        
        for credential, expiry_time in self._rate_limited_credentials.items():
            if current_time >= expiry_time:
                expired.append(credential)
        
        for credential in expired:
            del self._rate_limited_credentials[credential]
            # Only add back if not currently in use
            if credential not in self._in_use_credentials:
                self._available_credentials.append(credential)
                print(f"[CREDENTIAL] Rate limit expired for {credential[:8]}..., returned to pool")
    
    def _handle_simulated_rate_limit(self) -> Optional[str]:
        """Handle simulated 429 for testing.
        
        Returns:
            Credential string or None
        """
        # Simulate rate limiting the first credential
        if self._available_credentials:
            first_cred = self._available_credentials[0]
            if first_cred not in self._rate_limited_credentials:
                self.mark_rate_limited(first_cred)
            
            # Try to get a different credential
            remaining = [
                c for c in self._available_credentials
                if c not in self._rate_limited_credentials
            ]
            if remaining:
                credential = remaining[0]
                self._available_credentials.remove(credential)
                self._in_use_credentials.add(credential)
                return credential
        
        return None
    
    def get_status(self) -> dict:
        """Get current credential pool status.
        
        Returns:
            Dictionary with pool statistics
        """
        with self._lock:
            self._cleanup_rate_limits()
            return {
                "total": len(self._all_credentials),
                "available": len(self._available_credentials),
                "in_use": len(self._in_use_credentials),
                "rate_limited": len(self._rate_limited_credentials),
            }
```