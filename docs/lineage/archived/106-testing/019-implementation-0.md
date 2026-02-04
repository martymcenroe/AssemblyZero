# File: agentos/workflows/parallel/__init__.py

```python
"""Parallel workflow execution infrastructure."""

from agentos.workflows.parallel.coordinator import ParallelCoordinator
from agentos.workflows.parallel.credential_coordinator import CredentialCoordinator
from agentos.workflows.parallel.output_prefixer import OutputPrefixer
from agentos.workflows.parallel.input_sanitizer import sanitize_identifier

__all__ = [
    'ParallelCoordinator',
    'CredentialCoordinator',
    'OutputPrefixer',
    'sanitize_identifier',
]
```