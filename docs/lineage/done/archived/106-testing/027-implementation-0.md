# File: agentos/workflows/parallel/coordinator.py

```python
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