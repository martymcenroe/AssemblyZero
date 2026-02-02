# File: agentos/workflows/parallel/coordinator.py

```python
"""Coordinator managing worker pool, progress tracking, and graceful shutdown."""

import signal
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, TypeVar

from .credential_coordinator import CredentialCoordinator


T = TypeVar('T')


@dataclass
class WorkflowResult:
    """Result of a single workflow execution."""
    item_id: str
    success: bool
    error: Optional[Exception] = None
    duration: float = 0.0
    

@dataclass
class ProgressStats:
    """Progress statistics for parallel execution."""
    total: int
    completed: int = 0
    failed: int = 0
    in_progress: int = 0
    
    @property
    def success_count(self) -> int:
        """Number of successful completions."""
        return self.completed - self.failed
        

class ParallelCoordinator:
    """Coordinates parallel workflow execution with progress tracking and shutdown.
    
    Features:
    - Worker pool management with configurable parallelism
    - Progress tracking and reporting
    - Graceful shutdown on SIGINT with checkpoint support
    - Integration with credential coordinator
    """
    
    MAX_PARALLELISM = 10
    DEFAULT_PARALLELISM = 3
    
    def __init__(
        self,
        max_workers: Optional[int] = None,
        credential_coordinator: Optional[CredentialCoordinator] = None,
    ):
        """Initialize the parallel coordinator.
        
        Args:
            max_workers: Maximum number of parallel workers (None = use default)
            credential_coordinator: Optional credential manager
        """
        # Apply parallelism limits
        if max_workers is None:
            max_workers = self.DEFAULT_PARALLELISM
        elif max_workers > self.MAX_PARALLELISM:
            print(f"[COORDINATOR] Warning: max_workers={max_workers} exceeds limit of {self.MAX_PARALLELISM}, capping to {self.MAX_PARALLELISM}")
            max_workers = self.MAX_PARALLELISM
            
        self.max_workers = max_workers
        self.credential_coordinator = credential_coordinator
        self._shutdown_requested = False
        self._lock = threading.Lock()
        self._checkpoints: dict[str, Any] = {}
        
        # Set up signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_shutdown_signal)
        
    def _handle_shutdown_signal(self, signum, frame):
        """Handle SIGINT for graceful shutdown."""
        print("\n[COORDINATOR] Shutdown signal received, waiting for workers to checkpoint...")
        with self._lock:
            self._shutdown_requested = True
            
    def execute_parallel(
        self,
        items: list[T],
        worker_func: Callable[[T, Optional[str]], Any],
        item_id_func: Callable[[T], str],
        dry_run: bool = False,
    ) -> tuple[ProgressStats, list[WorkflowResult]]:
        """Execute a workflow function in parallel across multiple items.
        
        Args:
            items: List of items to process
            worker_func: Function to execute for each item (receives item and optional credential)
            item_id_func: Function to extract ID string from an item
            dry_run: If True, just list items without executing
            
        Returns:
            Tuple of (progress stats, list of results)
        """
        stats = ProgressStats(total=len(items))
        results: list[WorkflowResult] = []
        
        # Dry run mode - just list items
        if dry_run:
            print(f"[COORDINATOR] Dry run mode - would process {len(items)} items:")
            for item in items:
                item_id = item_id_func(item)
                print(f"  - {item_id}")
            return stats, results
            
        # Execute in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_item: dict[Future, T] = {}
            for item in items:
                future = executor.submit(self._execute_single_item, item, worker_func, item_id_func)
                future_to_item[future] = item
                
            # Process results as they complete
            for future in as_completed(future_to_item):
                if self._shutdown_requested:
                    print("[COORDINATOR] Shutdown in progress, waiting for workers...")
                    # Give workers time to checkpoint (up to 5s each)
                    time.sleep(0.1)
                    
                result = future.result()
                results.append(result)
                
                # Update stats
                stats.completed += 1
                if not result.success:
                    stats.failed += 1
                    
        # Final progress report
        print(f"\n[COORDINATOR] Execution complete: {stats.success_count}/{stats.total} succeeded, {stats.failed} failed")
        
        return stats, results
        
    def _execute_single_item(
        self,
        item: T,
        worker_func: Callable[[T, Optional[str]], Any],
        item_id_func: Callable[[T], str],
    ) -> WorkflowResult:
        """Execute workflow for a single item with credential management.
        
        Args:
            item: The item to process
            worker_func: The worker function
            item_id_func: Function to get item ID
            
        Returns:
            Result of the workflow execution
        """
        item_id = item_id_func(item)
        start_time = time.time()
        credential: Optional[str] = None
        
        try:
            # Reserve credential if coordinator available
            if self.credential_coordinator:
                credential = self.credential_coordinator.reserve(timeout=300)
                if credential is None:
                    raise TimeoutError("Failed to reserve credential within timeout")
                    
            # Check for shutdown before starting work
            if self._shutdown_requested:
                # Save checkpoint
                self._checkpoints[item_id] = {"status": "interrupted"}
                raise InterruptedError("Shutdown requested")
                
            # Check for simulated 429
            if os.environ.get("AGENTOS_SIMULATE_429") == "true" and credential:
                # Simulate rate limit on first credential
                if self.credential_coordinator:
                    self.credential_coordinator.mark_rate_limited(credential, backoff_seconds=1.0)
                    self.credential_coordinator.release(credential)
                    credential = None
                    
                    # Try to get another credential
                    credential = self.credential_coordinator.reserve(timeout=5)
                    
            # Execute the workflow
            worker_func(item, credential)
            
            duration = time.time() - start_time
            return WorkflowResult(
                item_id=item_id,
                success=True,
                duration=duration,
            )
            
        except Exception as e:
            duration = time.time() - start_time
            
            # Save checkpoint on shutdown
            if isinstance(e, InterruptedError):
                self._checkpoints[item_id] = {"status": "interrupted", "error": str(e)}
                
            return WorkflowResult(
                item_id=item_id,
                success=False,
                error=e,
                duration=duration,
            )
            
        finally:
            # Release credential
            if credential and self.credential_coordinator:
                self.credential_coordinator.release(credential)
                
    def get_checkpoints(self) -> dict[str, Any]:
        """Get all saved checkpoints.
        
        Returns:
            Dictionary of item_id -> checkpoint data
        """
        with self._lock:
            return self._checkpoints.copy()
```