# File: agentos/workflows/parallel/__init__.py

```python
"""Parallel workflow execution infrastructure for AgentOS.

Provides:
- ParallelCoordinator: Manages worker pool and execution
- CredentialCoordinator: Thread-safe credential management
- OutputPrefixer: Prefixes output streams for workflow identification
- sanitize_identifier: Input validation for path-safe identifiers
"""

from agentos.workflows.parallel.coordinator import ParallelCoordinator, WorkflowResult, ProgressStats
from agentos.workflows.parallel.credential_coordinator import CredentialCoordinator
from agentos.workflows.parallel.output_prefixer import OutputPrefixer
from agentos.workflows.parallel.input_sanitizer import sanitize_identifier

__all__ = [
    "ParallelCoordinator",
    "WorkflowResult",
    "ProgressStats",
    "CredentialCoordinator",
    "OutputPrefixer",
    "sanitize_identifier",
]
```