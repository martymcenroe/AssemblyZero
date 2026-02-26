

```python
"""Cross-project metrics aggregation for AssemblyZero usage tracking.

Issue #333: Aggregate usage metrics across multiple configured repositories.
"""

from __future__ import annotations

from assemblyzero.metrics.aggregator import aggregate_metrics, compute_approval_rate
from assemblyzero.metrics.cache import (
    get_cache_path,
    invalidate_cache,
    load_cached_metrics,
    save_cached_metrics,
)
from assemblyzero.metrics.collector import (
    CollectionError,
    collect_repo_metrics,
    count_gemini_verdicts,
    count_issues_in_period,
    count_lineage_artifacts,
    detect_workflows_used,
)
from assemblyzero.metrics.config import (
    ConfigError,
    get_default_config_path,
    load_config,
    validate_config,
    validate_repo_name,
)
from assemblyzero.metrics.formatters import (
    format_json_snapshot,
    format_markdown_table,
    write_snapshot,
)
from assemblyzero.metrics.models import (
    AggregatedMetrics,
    CacheEntry,
    RepoMetrics,
    TrackedReposConfig,
    create_repo_metrics,
    validate_repo_metrics,
)

__all__ = [
    "AggregatedMetrics",
    "CacheEntry",
    "CollectionError",
    "ConfigError",
    "RepoMetrics",
    "TrackedReposConfig",
    "aggregate_metrics",
    "collect_repo_metrics",
    "compute_approval_rate",
    "count_gemini_verdicts",
    "count_issues_in_period",
    "count_lineage_artifacts",
    "create_repo_metrics",
    "detect_workflows_used",
    "format_json_snapshot",
    "format_markdown_table",
    "get_cache_path",
    "get_default_config_path",
    "invalidate_cache",
    "load_cached_metrics",
    "load_config",
    "save_cached_metrics",
    "validate_config",
    "validate_repo_metrics",
    "validate_repo_name",
    "write_snapshot",
]
```
