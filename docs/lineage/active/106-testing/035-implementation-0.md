# File: agentos/workflows/parallel/coordinator.py

```python
"""Parallel workflow coordinator for managing concurrent execution."""

import signal
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, Dict

from .credential_coordinator import CredentialCoordinator


@dataclass
class WorkflowResult:
    """Result of a single workflow execution."""
    item_id: str
    success: bool
    error: Optional[str] = None
    duration: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProgressStats:
    """Statistics for workflow execution progress."""
    total: int
    completed: int = 0
    failed: int = 0
    success_count: int = 0
    start_time: float = field(default_factory=time.time)
    
    @property
    def elapsed(self) -> float:
        """Return elapsed time in seconds."""
        return time.time() - self.start_time
    
    @property
    def completion_rate(self) -> float:
        """Return completion percentage."""
        if self.total == 0:
            return 0.0
        return (self.completed / self.total) * 100


class ParallelCoordinator:
    """Coordinates parallel execution of workflows."""
    
    DEFAULT_PARALLELISM = 3
    MAX_PARALLELISM = 10
    
    def __init__(
        self,
        max_workers: Optional[int] = None,
        credential_coordinator: Optional[CredentialCoordinator] = None,
    ):
        """Initialize the parallel coordinator.
        
        Args:
            max_workers: Maximum number of parallel workers (default: 3, max: 10)
            credential_coordinator: Optional credential manager for API keys
        """
        if max_workers is None:
            max_workers = self.DEFAULT_PARALLELISM
        elif max_workers > self.MAX_PARALLELISM:
            print(f"Warning: Requested parallelism {max_workers} exceeds maximum {self.MAX_PARALLELISM}. Capping to {self.MAX_PARALLELISM}.")
            max_workers = self.MAX_PARALLELISM
        
        self.max_workers = max_workers
        self.credential_coordinator = credential_coordinator
        self._shutdown_event = threading.Event()
        self._checkpoints: List[str] = []
        self._checkpoint_lock = threading.Lock()
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self._handle_shutdown_signal)
        signal.signal(signal.SIGTERM, self._handle_shutdown_signal)
    
    def _handle_shutdown_signal(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals gracefully.
        
        Args:
            signum: Signal number
            frame: Current stack frame
        """
        print(f"\n[COORDINATOR] Received signal {signum}, initiating graceful shutdown...")
        self._shutdown_event.set()
    
    def _add_checkpoint(self, item_id: str) -> None:
        """Add an item to checkpoints for recovery.
        
        Args:
            item_id: Identifier of the interrupted item
        """
        with self._checkpoint_lock:
            self._checkpoints.append(item_id)
    
    def get_checkpoints(self) -> List[str]:
        """Return list of checkpointed items.
        
        Returns:
            List of item IDs that were interrupted
        """
        with self._checkpoint_lock:
            return self._checkpoints.copy()
    
    def _execute_worker(
        self,
        item: Any,
        worker_func: Callable[[Any, Optional[str]], None],
        item_id: str,
    ) -> WorkflowResult:
        """Execute a single workflow item.
        
        Args:
            item: The item to process
            worker_func: Function to execute with (item, credential)
            item_id: Identifier for the item
            
        Returns:
            WorkflowResult with execution details
        """
        start_time = time.time()
        credential = None
        
        try:
            # Check for shutdown signal
            if self._shutdown_event.is_set():
                self._add_checkpoint(item_id)
                return WorkflowResult(
                    item_id=item_id,
                    success=False,
                    error="Interrupted by shutdown signal",
                    duration=time.time() - start_time,
                )
            
            # Acquire credential if coordinator is available
            if self.credential_coordinator:
                credential = self._acquire_credential_with_retry(item_id)
                if credential is None:
                    return WorkflowResult(
                        item_id=item_id,
                        success=False,
                        error="Failed to acquire credential",
                        duration=time.time() - start_time,
                    )
            
            # Execute the worker function
            worker_func(item, credential)
            
            return WorkflowResult(
                item_id=item_id,
                success=True,
                duration=time.time() - start_time,
            )
            
        except Exception as e:
            return WorkflowResult(
                item_id=item_id,
                success=False,
                error=str(e),
                duration=time.time() - start_time,
            )
        finally:
            # Release credential if we acquired one
            if credential and self.credential_coordinator:
                self.credential_coordinator.release_credential(credential)
    
    def _acquire_credential_with_retry(self, item_id: str, max_retries: int = 5) -> Optional[str]:
        """Acquire a credential with retry logic.
        
        Args:
            item_id: Identifier for logging
            max_retries: Maximum number of retry attempts
            
        Returns:
            Credential string or None if failed
        """
        for attempt in range(max_retries):
            if self._shutdown_event.is_set():
                return None
                
            credential = self.credential_coordinator.acquire_credential()
            if credential:
                return credential
            
            # Pool exhausted
            if attempt == 0:
                print(f"[COORDINATOR] Credential pool exhausted, waiting for release...")
            
            time.sleep(0.5)  # Wait before retry
        
        return None
    
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
            worker_func: Function to execute for each item (item, credential)
            item_id_func: Function to extract item ID from item
            dry_run: If True, only list items without executing
            
        Returns:
            Tuple of (ProgressStats, List[WorkflowResult])
        """
        stats = ProgressStats(total=len(items))
        results: List[WorkflowResult] = []
        
        if dry_run:
            print(f"[COORDINATOR] Dry run mode - would process {len(items)} items:")
            for item in items:
                print(f"  - {item_id_func(item)}")
            return stats, results
        
        # Reset shutdown event
        self._shutdown_event.clear()
        self._checkpoints.clear()
        
        print(f"[COORDINATOR] Starting parallel execution of {len(items)} items with {self.max_workers} workers")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_item = {
                executor.submit(
                    self._execute_worker,
                    item,
                    worker_func,
                    item_id_func(item),
                ): item
                for item in items
            }
            
            # Process completed tasks
            for future in as_completed(future_to_item):
                if self._shutdown_event.is_set():
                    # Cancel remaining futures
                    for f in future_to_item:
                        if not f.done():
                            f.cancel()
                    break
                
                result = future.result()
                results.append(result)
                
                stats.completed += 1
                if result.success:
                    stats.success_count += 1
                else:
                    stats.failed += 1
                
                # Progress update
                print(f"[COORDINATOR] Progress: {stats.completed}/{stats.total} ({stats.completion_rate:.1f}%)")
        
        # Final summary
        print(f"\n[COORDINATOR] Execution complete:")
        print(f"  Total: {stats.total}")
        print(f"  Succeeded: {stats.success_count}")
        print(f"  Failed: {stats.failed}")
        print(f"  Duration: {stats.elapsed:.2f}s")
        
        return stats, results
```