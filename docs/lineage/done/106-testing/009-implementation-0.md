# File: agentos/workflows/parallel/__init__.py

```python
"""Parallel workflow execution infrastructure."""

from .coordinator import ParallelCoordinator
from .credential_coordinator import CredentialCoordinator
from .output_prefixer import OutputPrefixer
from .input_sanitizer import sanitize_identifier

__all__ = [
    "ParallelCoordinator",
    "CredentialCoordinator",
    "OutputPrefixer",
    "sanitize_identifier",
]
```