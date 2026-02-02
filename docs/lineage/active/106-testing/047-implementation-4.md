# File: agentos/workflows/parallel/coordinator.py

```python
"""Coordinator managing worker pool, progress tracking, and graceful shutdown."""

import os
import signal
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, Dict
from agentos.workflows.parallel.credential_coordinator import CredentialCoordinator


@dataclass
class WorkflowResult:
    """Result of a single workflow execution."""
    item_id: str
    success: bool
    error: Optional[str] = None
    duration: float = 0.0


@dataclass
class ProgressStats:
    """Statistics for parallel execution progress."""
    total: int
    completed: int = 0
    failed: int = 0
    success_count: int = 0
    
    def increment_completed(self, success: bool) -> None:
        """Increment completion counters."""
        self.completed += 1
        if success:
            self.success_count += 1
        else:
            self.failed += 1


class ParallelCoordinator:
    """Manages parallel execution of workflows with credential coordination.
    
    Provides:
    - Worker pool management with configurable parallelism
    - Progress tracking and reporting
    - Graceful shutdown on SIGINT/SIGTERM
    - Credential coordination for API rate limiting
    - Checkpoint support for resumable execution
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
            max_workers: Maximum number of parallel workers (default: 3, max: 10)
            credential_coordinator: Optional credential coordinator for rate limiting
        """
        # Handle parallelism limits
        if max_workers is None:
            max_workers = self.DEFAULT_PARALLELISM
        elif max_workers > self.MAX_PARALLELISM:
            print(f"[COORDINATOR] Warning: Requested parallelism {max_workers} exceeds maximum {self.MAX_PARALLELISM}, capping to {self.MAX_PARALLELISM}")
            max_workers = self.MAX_PARALLELISM
        
        self.max_workers = max_workers
        self.credential_coordinator = credential_coordinator
        self._shutdown_event = threading.Event()
        self._checkpoints: Dict[str, Any] = {}
        self._checkpoint_lock = threading.Lock()
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self._handle_shutdown_signal)
        signal.signal(signal.SIGTERM, self._handle_shutdown_signal)
    
    def _handle_shutdown_signal(self, signum, frame):
        """Handle shutdown signals gracefully."""
        print(f"\n[COORDINATOR] Received signal {signum}, initiating graceful shutdown...")
        self._shutdown_event.set()
    
    def _save_checkpoint(self, item_id: str, state: Any) -> None:
        """Save checkpoint for an item."""
        with self._checkpoint_lock:
            self._checkpoints[item_id] = state
    
    def get_checkpoints(self) -> Dict[str, Any]:
        """Get all saved checkpoints."""
        with self._checkpoint_lock:
            return self._checkpoints.copy()
    
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
            worker_func: Function to execute for each item (item, credential) -> None
            item_id_func: Function to extract ID from item
            dry_run: If True, only list items without executing
            
        Returns:
            Tuple of (ProgressStats, List[WorkflowResult])
        """
        stats = ProgressStats(total=len(items))
        results: List[WorkflowResult] = []
        
        # Handle dry run
        if dry_run:
            print(f"[COORDINATOR] Dry run mode - would process {len(items)} items:")
            for item in items:
                item_id = item_id_func(item)
                print(f"  - {item_id}")
            return stats, results
        
        # Check for simulation mode
        simulate_429 = os.environ.get("AGENTOS_SIMULATE_429") == "true"
        
        def execute_item(item: Any) -> WorkflowResult:
            """Execute a single item with credential management."""
            item_id = item_id_func(item)
            credential = None
            start_time = time.time()
            
            try:
                # Check for shutdown
                if self._shutdown_event.is_set():
                    self._save_checkpoint(item_id, {"state": "interrupted"})
                    raise InterruptedError("Shutdown requested")
                
                # Acquire credential if coordinator exists
                if self.credential_coordinator:
                    credential = self.credential_coordinator.acquire(timeout=30.0)
                    if credential is None:
                        raise RuntimeError("Failed to acquire credential")
                
                # Simulate 429 if requested
                if simulate_429 and credential:
                    # Mark as rate limited and get a different one
                    self.credential_coordinator.mark_rate_limited(credential)
                    self.credential_coordinator.release(credential)
                    credential = self.credential_coordinator.acquire(timeout=30.0)
                
                # Execute the worker function
                worker_func(item, credential)
                
                duration = time.time() - start_time
                return WorkflowResult(
                    item_id=item_id,
                    success=True,
                    duration=duration,
                )
                
            except Exception as e:
                duration = time.time() - start_time
                return WorkflowResult(
                    item_id=item_id,
                    success=False,
                    error=str(e),
                    duration=duration,
                )
                
            finally:
                # Release credential
                if credential and self.credential_coordinator:
                    self.credential_coordinator.release(credential)
        
        # Execute in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_item = {
                executor.submit(execute_item, item): item
                for item in items
            }
            
            # Process results as they complete
            for future in as_completed(future_to_item):
                if self._shutdown_event.is_set():
                    # Cancel remaining futures
                    for f in future_to_item:
                        f.cancel()
                    break
                
                try:
                    result = future.result(timeout=1.0)
                    results.append(result)
                    stats.increment_completed(result.success)
                    
                    print(f"[COORDINATOR] Progress: {stats.completed}/{stats.total} "
                          f"(Success: {stats.success_count}, Failed: {stats.failed})")
                    
                except Exception as e:
                    # This shouldn't happen as exceptions are caught in execute_item
                    item = future_to_item[future]
                    item_id = item_id_func(item)
                    results.append(WorkflowResult(
                        item_id=item_id,
                        success=False,
                        error=str(e),
                    ))
                    stats.increment_completed(False)
        
        return stats, results
```