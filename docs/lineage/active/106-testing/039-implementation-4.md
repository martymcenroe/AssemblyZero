# File: agentos/workflows/parallel/__init__.py

```python
"""Parallel workflow execution infrastructure."""

from .coordinator import ParallelCoordinator, WorkflowResult, ProgressStats
from .credential_coordinator import CredentialCoordinator
from .input_sanitizer import sanitize_identifier, sanitize_path, validate_workflow_id
from .output_prefixer import OutputPrefixer

__all__ = [
    "ParallelCoordinator",
    "WorkflowResult",
    "ProgressStats",
    "CredentialCoordinator",
    "sanitize_identifier",
    "sanitize_path",
    "validate_workflow_id",
    "OutputPrefixer",
]
```