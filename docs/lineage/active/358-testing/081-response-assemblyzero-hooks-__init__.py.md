

```python
"""Hooks for workflow validation and enforcement."""

from assemblyzero.hooks.cascade_action import (
    format_block_message,
    handle_cascade_detection,
)
from assemblyzero.hooks.cascade_detector import (
    CascadeDetectionResult,
    CascadeRiskLevel,
    compute_risk_score,
    detect_cascade_risk,
    is_permission_prompt,
)
from assemblyzero.hooks.cascade_patterns import (
    CascadePattern,
    load_default_patterns,
    load_user_patterns,
    merge_patterns,
)

__all__ = [
    "CascadeDetectionResult",
    "CascadePattern",
    "CascadeRiskLevel",
    "compute_risk_score",
    "detect_cascade_risk",
    "format_block_message",
    "handle_cascade_detection",
    "is_permission_prompt",
    "load_default_patterns",
    "load_user_patterns",
    "merge_patterns",
]
```
