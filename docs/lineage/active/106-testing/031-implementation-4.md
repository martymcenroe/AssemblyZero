# File: agentos/workflows/parallel/__init__.py

```python
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