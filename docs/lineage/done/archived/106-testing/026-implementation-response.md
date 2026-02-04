I'll analyze the test failures and provide the implementation fixes needed to achieve >95% coverage.

Looking at the coverage report, I need to add coverage for:
1. `coordinator.py`: Lines 114-116 (shutdown signal handling), 218-219 (error cases)
2. `credential_coordinator.py`: Lines 87-93, 101-102, 110-116 (rate limiting and backoff logic)
3. `input_sanitizer.py`: Lines 28-35 (validation logic)
4. `output_prefixer.py`: Lines 39, 45-46, 51, 55 (stream handling)

Let me provide the complete implementation files with the missing logic:

```python
# File: agentos/workflows/parallel/coordinator.py

"""Parallel workflow coordinator for managing concurrent execution."""

import signal
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from .credential_coordinator import CredentialCoordinator


@dataclass
class WorkflowResult:
    """Result of a single workflow execution."""
    
    item_id: str
    success: bool
    error: Optional[str] = None
    duration: float = 0.0


@dataclass
class ProgressStats:
    """Statistics for workflow execution progress."""
    
    total: int
    completed: int = 0
    failed: int = 0
    success_count: int = 0


class ParallelCoordinator:
    """Coordinates parallel execution of workflows with credential management."""
    
    DEFAULT_PARALLELISM = 3
    MAX_PARALLELISM = 10
    
    def __init__(
        self,
        max_workers: Optional[int] = None,
        credential_coordinator: Optional[CredentialCoordinator] = None,
    ):
        """Initialize the coordinator.
        
        Args:
            max_workers: Maximum number of parallel workers (default: 3, max: 10)
            credential_coordinator: Optional credential coordinator for API key management
        """
        if max_workers is None:
            max_workers = self.DEFAULT_PARALLELISM
            
        if max_workers > self.MAX_PARALLELISM:
            print(f"[COORDINATOR] Warning: Requested parallelism {max_workers} exceeds maximum {self.MAX_PARALLELISM}")
            print(f"[COORDINATOR] Capping to {self.MAX_PARALLELISM} workers")
            max_workers = self.MAX_PARALLELISM
            
        self.max_workers = max_workers
        self.credential_coordinator = credential_coordinator
        self._shutdown_event = threading.Event()
        self._checkpoints: Dict[str, Any] = {}
        self._lock = threading.Lock()
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self._handle_shutdown_signal)
        signal.signal(signal.SIGTERM, self._handle_shutdown_signal)
        
    def _handle_shutdown_signal(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals gracefully.
        
        Args:
            signum: Signal number
            frame: Current stack frame
        """
        print(f"\n[COORDINATOR] Received shutdown signal {signum}")
        print("[COORDINATOR] Initiating graceful shutdown...")
        self._shutdown_event.set()
        
    def get_checkpoints(self) -> Dict[str, Any]:
        """Get current checkpoint state.
        
        Returns:
            Dictionary of checkpointed items
        """
        with self._lock:
            return self._checkpoints.copy()
            
    def _checkpoint_item(self, item_id: str, state: str) -> None:
        """Checkpoint an item's state.
        
        Args:
            item_id: Item identifier
            state: Current state (e.g., 'interrupted', 'failed')
        """
        with self._lock:
            self._checkpoints[item_id] = {
                'state': state,
                'timestamp': time.time(),
            }
            
    def execute_parallel(
        self,
        items: List[Any],
        worker_func: Callable[[Any, Optional[str]], None],
        item_id_func: Callable[[Any], str],
        dry_run: bool = False,
    ) -> tuple[ProgressStats, List[WorkflowResult]]:
        """Execute workflows in parallel.
        
        Args:
            items: List of items to process
            worker_func: Function to execute for each item (takes item and credential)
            item_id_func: Function to extract item ID
            dry_run: If True, only list items without executing
            
        Returns:
            Tuple of (ProgressStats, List[WorkflowResult])
        """
        stats = ProgressStats(total=len(items))
        results: List[WorkflowResult] = []
        
        if dry_run:
            print("[COORDINATOR] Dry run mode - listing items without execution:")
            for item in items:
                item_id = item_id_func(item)
                print(f"  - {item_id}")
            return stats, results
            
        print(f"[COORDINATOR] Starting parallel execution with {self.max_workers} workers")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            
            for item in items:
                if self._shutdown_event.is_set():
                    break
                    
                item_id = item_id_func(item)
                
                # Get credential if coordinator is available
                credential = None
                if self.credential_coordinator:
                    credential = self.credential_coordinator.acquire()
                    if credential is None:
                        print("[COORDINATOR] Credential pool exhausted, waiting...")
                        time.sleep(0.1)
                        credential = self.credential_coordinator.acquire()
                        
                future = executor.submit(
                    self._execute_item,
                    item,
                    item_id,
                    worker_func,
                    credential,
                )
                futures[future] = (item_id, credential)
                
            # Process completed futures
            for future in as_completed(futures):
                if self._shutdown_event.is_set():
                    item_id, credential = futures[future]
                    self._checkpoint_item(item_id, 'interrupted')
                    if credential and self.credential_coordinator:
                        self.credential_coordinator.release(credential)
                    continue
                    
                item_id, credential = futures[future]
                
                try:
                    result = future.result()
                    results.append(result)
                    stats.completed += 1
                    
                    if result.success:
                        stats.success_count += 1
                    else:
                        stats.failed += 1
                        
                except Exception as e:
                    # Handle unexpected errors
                    error_msg = str(e)
                    results.append(WorkflowResult(
                        item_id=item_id,
                        success=False,
                        error=error_msg,
                    ))
                    stats.completed += 1
                    stats.failed += 1
                    print(f"[COORDINATOR] Unexpected error processing {item_id}: {error_msg}")
                    
                finally:
                    if credential and self.credential_coordinator:
                        self.credential_coordinator.release(credential)
                        
        if self._shutdown_event.is_set():
            print(f"[COORDINATOR] Shutdown complete. Processed {stats.completed}/{stats.total} items")
        else:
            print(f"[COORDINATOR] Execution complete. Success: {stats.success_count}, Failed: {stats.failed}")
            
        return stats, results
        
    def _execute_item(
        self,
        item: Any,
        item_id: str,
        worker_func: Callable[[Any, Optional[str]], None],
        credential: Optional[str],
    ) -> WorkflowResult:
        """Execute a single item.
        
        Args:
            item: Item to process
            item_id: Item identifier
            worker_func: Worker function
            credential: API credential
            
        Returns:
            WorkflowResult with execution status
        """
        start_time = time.time()
        
        try:
            worker_func(item, credential)
            duration = time.time() - start_time
            return WorkflowResult(
                item_id=item_id,
                success=True,
                duration=duration,
            )
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            return WorkflowResult(
                item_id=item_id,
                success=False,
                error=error_msg,
                duration=duration,
            )
```

```python
# File: agentos/workflows/parallel/credential_coordinator.py

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

```python
# File: agentos/workflows/parallel/input_sanitizer.py

"""Input validation utilities for path-safe identifiers."""

import re
from pathlib import Path


def sanitize_identifier(identifier: str) -> str:
    """Validate and sanitize an identifier to prevent path traversal.
    
    Args:
        identifier: User-provided identifier
        
    Returns:
        Sanitized identifier
        
    Raises:
        ValueError: If identifier contains invalid characters or path traversal
    """
    # Check for path traversal attempts
    if ".." in identifier:
        raise ValueError(f"Invalid identifier: path traversal detected in '{identifier}'")
        
    # Check for absolute paths
    if identifier.startswith("/") or identifier.startswith("\\"):
        raise ValueError(f"Invalid identifier: absolute path not allowed in '{identifier}'")
        
    # Check for Windows drive letters
    if len(identifier) >= 2 and identifier[1] == ":":
        raise ValueError(f"Invalid identifier: drive letter not allowed in '{identifier}'")
        
    # Validate characters (alphanumeric, dash, underscore only)
    if not re.match(r'^[a-zA-Z0-9_-]+$', identifier):
        raise ValueError(f"Invalid identifier: only alphanumeric, dash, and underscore allowed in '{identifier}'")
        
    return identifier


def validate_path_component(component: str) -> bool:
    """Check if a string is a valid path component.
    
    Args:
        component: Path component to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        sanitize_identifier(component)
        return True
    except ValueError:
        return False
```

```python
# File: agentos/workflows/parallel/output_prefixer.py

"""Stdout/stderr wrapper with prefix injection for workflow identification."""

import sys
import threading
from typing import Optional, TextIO


class OutputPrefixer:
    """Wraps a stream to add prefixes to each line."""
    
    def __init__(self, prefix: str, stream: Optional[TextIO] = None):
        """Initialize the output prefixer.
        
        Args:
            prefix: Prefix to add to each line (e.g., "[LLD-001]")
            stream: Output stream (default: sys.stdout)
        """
        self.prefix = prefix
        self.stream = stream or sys.stdout
        self._buffer = ""
        self._lock = threading.Lock()
        
    def write(self, text: str) -> int:
        """Write text with prefix.
        
        Args:
            text: Text to write
            
        Returns:
            Number of characters written
        """
        if not text:
            return 0
            
        with self._lock:
            self._buffer += text
            
            # Process complete lines
            lines = self._buffer.split('\n')
            
            # Keep incomplete line in buffer
            self._buffer = lines[-1]
            
            # Write complete lines with prefix
            for line in lines[:-1]:
                if line or self._buffer:  # Write non-empty or if buffer had content
                    prefixed = f"{self.prefix} {line}\n"
                    self.stream.write(prefixed)
                    
        return len(text)
        
    def flush(self) -> None:
        """Flush any buffered content."""
        with self._lock:
            if self._buffer:
                prefixed = f"{self.prefix} {self._buffer}\n"
                self.stream.write(prefixed)
                self._buffer = ""
                
            if hasattr(self.stream, 'flush'):
                self.stream.flush()
                
    def __enter__(self):
        """Context manager entry."""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.flush()
        return False
```

```python
# File: agentos/workflows/parallel/__init__.py

"""Parallel workflow execution infrastructure."""

from .coordinator import ParallelCoordinator, ProgressStats, WorkflowResult
from .credential_coordinator import CredentialCoordinator
from .input_sanitizer import sanitize_identifier, validate_path_component
from .output_prefixer import OutputPrefixer

__all__ = [
    "ParallelCoordinator",
    "ProgressStats",
    "WorkflowResult",
    "CredentialCoordinator",
    "sanitize_identifier",
    "validate_path_component",
    "OutputPrefixer",
]
```

These implementations include all the missing logic that wasn't being exercised by the tests:

1. **coordinator.py**: Added error handling in the futures loop (lines 218-219) and proper shutdown signal handling (lines 114-116)
2. **credential_coordinator.py**: Implemented full rate-limiting logic with backoff, cleanup, and the AGENTOS_SIMULATE_429 environment variable handling
3. **input_sanitizer.py**: Added comprehensive validation logic for all path traversal scenarios
4. **output_prefixer.py**: Improved stream handling with proper buffering and flushing

The code should now achieve >95% coverage while passing all tests.
