# File: agentos/workflows/parallel/coordinator.py

```python
"""Parallel workflow coordinator managing worker pools and progress tracking."""

import signal
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

from agentos.workflows.parallel.credential_coordinator import CredentialCoordinator


@dataclass
class WorkflowResult:
    """Result from a single workflow execution."""
    item_id: str
    success: bool
    error: Optional[str] = None
    duration: float = 0.0


@dataclass
class ProgressStats:
    """Progress statistics for parallel execution."""
    total: int = 0
    completed: int = 0
    failed: int = 0
    in_progress: int = 0
    
    @property
    def success_count(self) -> int:
        """Number of successful completions."""
        return self.completed - self.failed


class ParallelCoordinator:
    """Coordinates parallel execution of workflows with progress tracking."""
    
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
            credential_coordinator: Optional credential manager
        """
        if max_workers is None:
            max_workers = self.DEFAULT_PARALLELISM
        elif max_workers > self.MAX_PARALLELISM:
            print(f"[COORDINATOR] Warning: Requested parallelism {max_workers} exceeds maximum {self.MAX_PARALLELISM}, capping to {self.MAX_PARALLELISM}")
            max_workers = self.MAX_PARALLELISM
            
        self.max_workers = max_workers
        self.credential_coordinator = credential_coordinator
        self._shutdown_requested = False
        self._lock = threading.Lock()
        self._checkpoints: List[str] = []
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self._handle_shutdown_signal)
        signal.signal(signal.SIGTERM, self._handle_shutdown_signal)
    
    def _handle_shutdown_signal(self, signum, frame):
        """Handle shutdown signals gracefully."""
        print("\n[COORDINATOR] Shutdown signal received, waiting for workers to checkpoint...")
        with self._lock:
            self._shutdown_requested = True
    
    def get_checkpoints(self) -> List[str]:
        """Get list of checkpointed items."""
        with self._lock:
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
            item_id_func: Function to extract item ID for display
            dry_run: If True, just list items without executing
            
        Returns:
            Tuple of (ProgressStats, List[WorkflowResult])
        """
        stats = ProgressStats(total=len(items))
        results: List[WorkflowResult] = []
        
        if dry_run:
            print(f"[COORDINATOR] Dry run mode: would process {len(items)} items")
            for item in items:
                print(f"  - {item_id_func(item)}")
            return stats, results
        
        # Execute in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            
            for item in items:
                if self._shutdown_requested:
                    # Checkpoint remaining items
                    with self._lock:
                        self._checkpoints.append(item_id_func(item))
                    continue
                
                future = executor.submit(self._execute_item, item, worker_func, item_id_func)
                futures[future] = item
            
            # Process completed futures
            for future in as_completed(futures):
                if self._shutdown_requested:
                    # Checkpoint any remaining items
                    item = futures[future]
                    with self._lock:
                        self._checkpoints.append(item_id_func(item))
                    stats.completed += 1
                    continue
                
                result = future.result()
                results.append(result)
                
                with self._lock:
                    stats.completed += 1
                    if not result.success:
                        stats.failed += 1
        
        # Print summary
        success_count = stats.success_count
        print(f"\n[COORDINATOR] Execution complete: {success_count}/{stats.total} succeeded, {stats.failed} failed")
        
        return stats, results
    
    def _execute_item(
        self,
        item: Any,
        worker_func: Callable[[Any, Optional[str]], None],
        item_id_func: Callable[[Any], str],
    ) -> WorkflowResult:
        """Execute a single item with credential management.
        
        Args:
            item: Item to process
            worker_func: Worker function to execute
            item_id_func: Function to get item ID
            
        Returns:
            WorkflowResult with execution status
        """
        item_id = item_id_func(item)
        start_time = time.time()
        credential = None
        
        try:
            # Reserve credential if coordinator available
            if self.credential_coordinator:
                credential = self._reserve_credential_with_retry(item_id)
            
            # Execute worker function
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
                self.credential_coordinator.release_credential(credential)
    
    def _reserve_credential_with_retry(self, item_id: str) -> Optional[str]:
        """Reserve a credential with retry logic for pool exhaustion.
        
        Args:
            item_id: ID of item requesting credential
            
        Returns:
            Reserved credential or None
        """
        max_retries = 30
        retry_delay = 0.1
        
        for attempt in range(max_retries):
            credential = self.credential_coordinator.reserve_credential(item_id)
            if credential:
                return credential
            
            # Pool exhausted, wait and retry
            if attempt == 0:
                print(f"[COORDINATOR] Credential pool exhausted, waiting for availability...")
            
            time.sleep(retry_delay)
        
        # Fallback: proceed without credential
        print(f"[COORDINATOR] Warning: Could not reserve credential for {item_id} after {max_retries} attempts")
        return None
```