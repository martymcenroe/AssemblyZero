"""Parallel workflow coordinator with graceful shutdown and progress tracking."""

import signal
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, List, Optional, Any, Tuple


@dataclass
class WorkflowResult:
    """Result from a single workflow execution."""
    item_id: str
    success: bool
    error: Optional[str] = None
    duration: Optional[float] = None


@dataclass
class ProgressStats:
    """Progress statistics for parallel execution."""
    total: int
    completed: int = 0
    failed: int = 0
    success_count: int = 0


class ParallelCoordinator:
    """Coordinator for parallel workflow execution."""
    
    DEFAULT_PARALLELISM = 3
    MAX_PARALLELISM = 10
    
    def __init__(
        self,
        max_workers: Optional[int] = None,
        credential_coordinator: Optional[Any] = None,
    ):
        """Initialize coordinator.
        
        Args:
            max_workers: Maximum number of parallel workers (default: 3, max: 10)
            credential_coordinator: Optional credential coordinator for API key management
        """
        if max_workers is None:
            max_workers = self.DEFAULT_PARALLELISM
        
        if max_workers > self.MAX_PARALLELISM:
            print(f"Warning: Requested parallelism {max_workers} exceeds maximum {self.MAX_PARALLELISM}, capping to {self.MAX_PARALLELISM}")
            max_workers = self.MAX_PARALLELISM
        
        self.max_workers = max_workers
        self.credential_coordinator = credential_coordinator
        self._shutdown_event = threading.Event()
        self._checkpoints: List[str] = []
        self._lock = threading.Lock()
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self._handle_shutdown_signal)
        signal.signal(signal.SIGTERM, self._handle_shutdown_signal)
    
    def _handle_shutdown_signal(self, signum, frame):
        """Handle shutdown signals gracefully."""
        print(f"\n[COORDINATOR] Received signal {signum}, initiating graceful shutdown...")
        self._shutdown_event.set()
    
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
    ) -> Tuple[ProgressStats, List[WorkflowResult]]:
        """Execute workflows in parallel.
        
        Args:
            items: List of items to process
            worker_func: Function to execute for each item (takes item and credential)
            item_id_func: Function to extract item ID for logging
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
        
        # Execute in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            
            for item in items:
                if self._shutdown_event.is_set():
                    break
                
                future = executor.submit(self._execute_item, item, worker_func, item_id_func)
                futures[future] = item
            
            # Collect results
            for future in as_completed(futures):
                if self._shutdown_event.is_set():
                    # Checkpoint remaining items
                    with self._lock:
                        for remaining_future, remaining_item in futures.items():
                            if not remaining_future.done():
                                self._checkpoints.append(item_id_func(remaining_item))
                    break
                
                result = future.result()
                results.append(result)
                
                stats.completed += 1
                if result.success:
                    stats.success_count += 1
                else:
                    stats.failed += 1
        
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
            worker_func: Worker function
            item_id_func: Function to extract item ID
        
        Returns:
            WorkflowResult
        """
        item_id = item_id_func(item)
        start_time = time.time()
        credential = None
        
        try:
            # Acquire credential if coordinator available
            if self.credential_coordinator:
                credential = self.credential_coordinator.acquire(timeout=30.0)
                if credential is None:
                    raise RuntimeError("Failed to acquire credential after timeout")
            
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
                # Check for simulated rate limit
                import os
                rate_limited = os.environ.get("AGENTOS_SIMULATE_429") == "true"
                self.credential_coordinator.release(
                    credential,
                    rate_limited=rate_limited,
                    backoff_seconds=60.0 if rate_limited else 0,
                )