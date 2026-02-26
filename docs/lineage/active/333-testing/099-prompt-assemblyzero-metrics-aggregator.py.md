# Implementation Request: assemblyzero/metrics/aggregator.py

## Task

Write the complete contents of `assemblyzero/metrics/aggregator.py`.

Change type: Add
Description: Cross-project aggregation

## LLD Specification

# Implementation Spec: Cross-Project Metrics Aggregation for AssemblyZero Usage Tracking

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #333 |
| LLD | `docs/lld/active/333-cross-project-metrics-aggregation.md` |
| Generated | 2026-02-25 |
| Status | DRAFT |


## 1. Overview

**Objective:** Aggregate AssemblyZero usage metrics (issue velocity, workflow usage, Gemini review outcomes) across multiple configured repositories into a unified dashboard output via a CLI tool.

**Success Criteria:**
- Config loaded from `~/.assemblyzero/tracked_repos.json` with validation
- Per-repo metrics collected via GitHub API with caching and graceful degradation
- Cross-project aggregation produces JSON snapshots and markdown tables
- Exit codes distinguish full success (0), partial failure (1), and complete failure (2)
- ≥95% test coverage on all new code


## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `assemblyzero/metrics/__init__.py` | Add | Package init, exports public API |
| 2 | `assemblyzero/metrics/models.py` | Add | Typed data structures for metrics |
| 3 | `assemblyzero/metrics/config.py` | Add | Load/validate tracked repos config |
| 4 | `assemblyzero/metrics/cache.py` | Add | Disk-based cache layer |
| 5 | `assemblyzero/metrics/collector.py` | Add | Per-repo GitHub API collection |
| 6 | `assemblyzero/metrics/aggregator.py` | Add | Cross-project aggregation |
| 7 | `assemblyzero/metrics/formatters.py` | Add | JSON snapshot + markdown table output |
| 8 | `tools/collect-cross-project-metrics.py` | Add | CLI entry point |
| 9 | `docs/metrics/.gitkeep` | Add | Preserve empty output directory |
| 10 | `tests/fixtures/metrics/tracked_repos_valid.json` | Add | Valid config fixture |
| 11 | `tests/fixtures/metrics/tracked_repos_empty.json` | Add | Empty repos list fixture |
| 12 | `tests/fixtures/metrics/tracked_repos_malformed.json` | Add | Malformed JSON fixture |
| 13 | `tests/fixtures/metrics/mock_issues_response.json` | Add | Mock GitHub issues data |
| 14 | `tests/fixtures/metrics/mock_lineage_tree.json` | Add | Mock directory listing |
| 15 | `tests/fixtures/metrics/expected_aggregated_output.json` | Add | Gold file for aggregation |
| 16 | `tests/unit/test_metrics_models.py` | Add | Unit tests for data models |
| 17 | `tests/unit/test_metrics_config.py` | Add | Unit tests for config |
| 18 | `tests/unit/test_metrics_cache.py` | Add | Unit tests for cache |
| 19 | `tests/unit/test_metrics_collector.py` | Add | Unit tests for collector |
| 20 | `tests/unit/test_metrics_aggregator.py` | Add | Unit tests for aggregator |
| 21 | `tests/unit/test_metrics_formatters.py` | Add | Unit tests for formatters |
| 22 | `tests/unit/test_metrics_cli.py` | Add | Unit tests for CLI exit codes |

**Implementation Order Rationale:** Models first (no dependencies), then config (depends on models), cache (depends on models), collector (depends on models + cache), aggregator (depends on models), formatters (depends on models), CLI (depends on all). Test fixtures before test files. Test files in dependency order matching source.


## 3. Current State (for Modify/Delete files)

No existing files are being modified or deleted. All files in this spec are new additions.

**Directory existence verification:**
- `assemblyzero/` — exists (package root)
- `tools/` — exists (contains existing CLI tools like `run_audit.py`, `run_implement_from_lld.py`)
- `docs/` — exists (contains existing documentation)
- `tests/unit/` — exists (contains existing unit tests)
- `tests/fixtures/metrics/` — exists (empty or has other fixtures; only new files are added)

**Note on existing stubs:** The import dependency analysis found references to `assemblyzero.utils.metrics_aggregator` and `assemblyzero.utils.metrics_models`. The new implementation places all modules at `assemblyzero.metrics.*`. If stub files exist at `assemblyzero/utils/metrics_*.py`, they are not modified by this spec. The new package at `assemblyzero/metrics/` is independent.


## 4. Data Structures

### 4.1 TrackedReposConfig

**Definition:**

```python
class TrackedReposConfig(TypedDict):
    repos: list[str]
    cache_ttl_minutes: int
    github_token_env: str
```

**Concrete Example:**

```json
{
    "repos": [
        "martymcenroe/AssemblyZero",
        "martymcenroe/ProjectAlpha",
        "martymcenroe/ProjectBeta"
    ],
    "cache_ttl_minutes": 60,
    "github_token_env": "GITHUB_TOKEN"
}
```

### 4.2 RepoMetrics

**Definition:**

```python
class RepoMetrics(TypedDict):
    repo: str
    period_start: str
    period_end: str
    issues_created: int
    issues_closed: int
    issues_open: int
    workflows_used: dict[str, int]
    llds_generated: int
    gemini_reviews: int
    gemini_approvals: int
    gemini_blocks: int
    collection_timestamp: str
```

**Concrete Example:**

```json
{
    "repo": "martymcenroe/AssemblyZero",
    "period_start": "2026-01-26T00:00:00+00:00",
    "period_end": "2026-02-25T00:00:00+00:00",
    "issues_created": 42,
    "issues_closed": 35,
    "issues_open": 12,
    "workflows_used": {
        "requirements": 8,
        "tdd": 15,
        "implementation": 10
    },
    "llds_generated": 20,
    "gemini_reviews": 18,
    "gemini_approvals": 15,
    "gemini_blocks": 3,
    "collection_timestamp": "2026-02-25T14:30:00+00:00"
}
```

### 4.3 AggregatedMetrics

**Definition:**

```python
class AggregatedMetrics(TypedDict):
    repos_tracked: int
    repos_reachable: int
    period_start: str
    period_end: str
    total_issues_created: int
    total_issues_closed: int
    total_issues_open: int
    total_llds_generated: int
    total_gemini_reviews: int
    gemini_approval_rate: float
    workflows_by_type: dict[str, int]
    per_repo: list[RepoMetrics]
    generated_at: str
```

**Concrete Example:**

```json
{
    "repos_tracked": 3,
    "repos_reachable": 3,
    "period_start": "2026-01-26T00:00:00+00:00",
    "period_end": "2026-02-25T00:00:00+00:00",
    "total_issues_created": 87,
    "total_issues_closed": 72,
    "total_issues_open": 25,
    "total_llds_generated": 40,
    "total_gemini_reviews": 35,
    "gemini_approval_rate": 0.857,
    "workflows_by_type": {
        "requirements": 15,
        "tdd": 28,
        "implementation": 20
    },
    "per_repo": [
        {
            "repo": "martymcenroe/AssemblyZero",
            "period_start": "2026-01-26T00:00:00+00:00",
            "period_end": "2026-02-25T00:00:00+00:00",
            "issues_created": 42,
            "issues_closed": 35,
            "issues_open": 12,
            "workflows_used": {"requirements": 8, "tdd": 15, "implementation": 10},
            "llds_generated": 20,
            "gemini_reviews": 18,
            "gemini_approvals": 15,
            "gemini_blocks": 3,
            "collection_timestamp": "2026-02-25T14:30:00+00:00"
        },
        {
            "repo": "martymcenroe/ProjectAlpha",
            "period_start": "2026-01-26T00:00:00+00:00",
            "period_end": "2026-02-25T00:00:00+00:00",
            "issues_created": 25,
            "issues_closed": 20,
            "issues_open": 8,
            "workflows_used": {"requirements": 4, "tdd": 8, "implementation": 5},
            "llds_generated": 12,
            "gemini_reviews": 10,
            "gemini_approvals": 8,
            "gemini_blocks": 2,
            "collection_timestamp": "2026-02-25T14:30:15+00:00"
        },
        {
            "repo": "martymcenroe/ProjectBeta",
            "period_start": "2026-01-26T00:00:00+00:00",
            "period_end": "2026-02-25T00:00:00+00:00",
            "issues_created": 20,
            "issues_closed": 17,
            "issues_open": 5,
            "workflows_used": {"requirements": 3, "tdd": 5, "implementation": 5},
            "llds_generated": 8,
            "gemini_reviews": 7,
            "gemini_approvals": 7,
            "gemini_blocks": 0,
            "collection_timestamp": "2026-02-25T14:30:30+00:00"
        }
    ],
    "generated_at": "2026-02-25T14:31:00+00:00"
}
```

### 4.4 CacheEntry

**Definition:**

```python
class CacheEntry(TypedDict):
    repo: str
    metrics: RepoMetrics
    cached_at: str
    expires_at: str
```

**Concrete Example:**

```json
{
    "repo": "martymcenroe/AssemblyZero",
    "metrics": {
        "repo": "martymcenroe/AssemblyZero",
        "period_start": "2026-01-26T00:00:00+00:00",
        "period_end": "2026-02-25T00:00:00+00:00",
        "issues_created": 42,
        "issues_closed": 35,
        "issues_open": 12,
        "workflows_used": {"requirements": 8, "tdd": 15, "implementation": 10},
        "llds_generated": 20,
        "gemini_reviews": 18,
        "gemini_approvals": 15,
        "gemini_blocks": 3,
        "collection_timestamp": "2026-02-25T14:30:00+00:00"
    },
    "cached_at": "2026-02-25T14:30:00+00:00",
    "expires_at": "2026-02-25T15:30:00+00:00"
}
```

### 4.5 CacheFile (disk format)

**Concrete Example** (`~/.assemblyzero/metrics_cache.json`):

```json
{
    "martymcenroe/AssemblyZero": {
        "repo": "martymcenroe/AssemblyZero",
        "metrics": { "..." : "see CacheEntry.metrics above" },
        "cached_at": "2026-02-25T14:30:00+00:00",
        "expires_at": "2026-02-25T15:30:00+00:00"
    },
    "martymcenroe/ProjectAlpha": {
        "repo": "martymcenroe/ProjectAlpha",
        "metrics": { "..." : "see above" },
        "cached_at": "2026-02-25T14:30:15+00:00",
        "expires_at": "2026-02-25T15:30:15+00:00"
    }
}
```


## 5. Function Specifications

### 5.1 `load_config()`

**File:** `assemblyzero/metrics/config.py`

**Signature:**

```python
def load_config(config_path: Path | None = None) -> TrackedReposConfig:
    """Load and validate tracked repos config from disk."""
    ...
```

**Input Example:**

```python
config_path = Path("/home/user/.assemblyzero/tracked_repos.json")
# File contents: {"repos": ["martymcenroe/AssemblyZero", "martymcenroe/ProjectAlpha"], "cache_ttl_minutes": 60, "github_token_env": "GITHUB_TOKEN"}
```

**Output Example:**

```python
{
    "repos": ["martymcenroe/AssemblyZero", "martymcenroe/ProjectAlpha"],
    "cache_ttl_minutes": 60,
    "github_token_env": "GITHUB_TOKEN",
}
```

**Edge Cases:**
- `config_path` is `None` → uses `get_default_config_path()`
- File does not exist → raises `ConfigError("Config file not found: /home/user/.assemblyzero/tracked_repos.json")`
- File is invalid JSON → raises `ConfigError("Failed to parse config: Expecting value: line 1 column 1 (char 0)")`
- File has empty repos list → raises `ConfigError("repos list cannot be empty")`
- File missing `repos` key → raises `ConfigError("Missing required key: repos")`
- File has `cache_ttl_minutes` missing → defaults to `60`
- File has `github_token_env` missing → defaults to `"GITHUB_TOKEN"`

### 5.2 `validate_config()`

**File:** `assemblyzero/metrics/config.py`

**Signature:**

```python
def validate_config(config: dict[str, Any]) -> TrackedReposConfig:
    """Validate raw dict against TrackedReposConfig schema."""
    ...
```

**Input Example:**

```python
config = {
    "repos": ["martymcenroe/AssemblyZero"],
    "cache_ttl_minutes": 120,
    "github_token_env": "MY_GITHUB_TOKEN",
}
```

**Output Example:**

```python
{
    "repos": ["martymcenroe/AssemblyZero"],
    "cache_ttl_minutes": 120,
    "github_token_env": "MY_GITHUB_TOKEN",
}
```

**Edge Cases:**
- Repo name `"'; DROP TABLE--"` → raises `ConfigError("Invalid repo name: '; DROP TABLE--")`
- Repo name `"martymcenroe/AssemblyZero"` → accepted
- Repo name `"valid.org/my-repo_v2"` → accepted
- `cache_ttl_minutes` is negative → raises `ConfigError("cache_ttl_minutes must be non-negative")`
- `repos` is not a list → raises `ConfigError("repos must be a list")`

### 5.3 `validate_repo_name()`

**File:** `assemblyzero/metrics/config.py`

**Signature:**

```python
def validate_repo_name(name: str) -> bool:
    """Check if a repo name matches the allowed pattern."""
    ...
```

**Input/Output Examples:**

```python
validate_repo_name("martymcenroe/AssemblyZero")  # → True
validate_repo_name("org.name/repo-v2")            # → True
validate_repo_name("valid_org/valid_repo")         # → True
validate_repo_name("'; DROP TABLE--")              # → False
validate_repo_name("no-slash")                     # → False
validate_repo_name("")                             # → False
validate_repo_name("a/b/c")                        # → False
```

### 5.4 `get_default_config_path()`

**File:** `assemblyzero/metrics/config.py`

**Signature:**

```python
def get_default_config_path() -> Path:
    """Return ~/.assemblyzero/tracked_repos.json."""
    ...
```

**Input Example:** No arguments.

**Output Example:**

```python
Path("/home/user/.assemblyzero/tracked_repos.json")
# On macOS: Path("/Users/user/.assemblyzero/tracked_repos.json")
```

### 5.5 `collect_repo_metrics()`

**File:** `assemblyzero/metrics/collector.py`

**Signature:**

```python
def collect_repo_metrics(
    repo_full_name: str,
    github_token: str,
    period_days: int = 30,
) -> RepoMetrics:
    """Collect all metrics for a single repository."""
    ...
```

**Input Example:**

```python
repo_full_name = "martymcenroe/AssemblyZero"
github_token = "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
period_days = 30
```

**Output Example:**

```python
{
    "repo": "martymcenroe/AssemblyZero",
    "period_start": "2026-01-26T00:00:00+00:00",
    "period_end": "2026-02-25T00:00:00+00:00",
    "issues_created": 42,
    "issues_closed": 35,
    "issues_open": 12,
    "workflows_used": {"requirements": 8, "tdd": 15, "implementation": 10},
    "llds_generated": 20,
    "gemini_reviews": 18,
    "gemini_approvals": 15,
    "gemini_blocks": 3,
    "collection_timestamp": "2026-02-25T14:30:00+00:00",
}
```

**Edge Cases:**
- Repo not found → raises `CollectionError("Failed to access repo 'martymcenroe/NonExistent': 404 Not Found")`
- Auth failure → raises `CollectionError("Authentication failed for repo 'martymcenroe/Private': 401 Bad credentials")`
- Empty token string → `Github()` called without token arg (public repos only)
- `period_days=7` → `period_start` is 7 days before `period_end`

### 5.6 `count_issues_in_period()`

**File:** `assemblyzero/metrics/collector.py`

**Signature:**

```python
def count_issues_in_period(
    repo: Repository,
    period_start: datetime,
    period_end: datetime,
) -> tuple[int, int, int]:
    """Count issues created, closed, and currently open. Returns (created, closed, open_now)."""
    ...
```

**Input Example:**

```python
# repo = Mock PyGithub Repository
# period_start = datetime(2026, 1, 26, tzinfo=timezone.utc)
# period_end = datetime(2026, 2, 25, tzinfo=timezone.utc)
```

**Output Example:**

```python
(42, 35, 12)  # 42 created in period, 35 closed in period, 12 currently open
```

**Edge Cases:**
- No issues in period → `(0, 0, 0)`
- Issues created before period but closed within → `(0, 1, N)` (not counted as created, but counted as closed)

### 5.7 `detect_workflows_used()`

**File:** `assemblyzero/metrics/collector.py`

**Signature:**

```python
def detect_workflows_used(repo: Repository) -> dict[str, int]:
    """Detect workflow types from issue labels and LLD filenames."""
    ...
```

**Input Example:**

```python
# Mock repo with issues having labels:
#   issue #100: ["workflow:requirements", "priority:high"]
#   issue #101: ["workflow:requirements", "workflow:tdd"]
#   issue #102: ["workflow:tdd"]
#   issue #103: ["bug"]  (no workflow label)
```

**Output Example:**

```python
{"requirements": 2, "tdd": 2}
```

**Edge Cases:**
- No issues have workflow labels → falls back to heuristic (LLD filename patterns)
- Heuristic fallback: scans `docs/lld/active/` for filenames containing workflow keywords → `{"requirements": N}`
- Empty repo (no issues, no LLDs) → `{}`

### 5.8 `count_lineage_artifacts()`

**File:** `assemblyzero/metrics/collector.py`

**Signature:**

```python
def count_lineage_artifacts(repo: Repository) -> int:
    """Count LLD folders in docs/lld/active/ and docs/lld/done/ directories."""
    ...
```

**Input Example:**

```python
# Mock repo where get_contents("docs/lld/active") returns 3 items
# and get_contents("docs/lld/done") returns 2 items
```

**Output Example:**

```python
5  # 3 active + 2 done
```

**Edge Cases:**
- `docs/lld/active/` does not exist (404) → returns `0` (no error)
- `docs/lld/done/` does not exist (404) → counts only `active/` entries
- Both directories missing → returns `0`

### 5.9 `count_gemini_verdicts()`

**File:** `assemblyzero/metrics/collector.py`

**Signature:**

```python
def count_gemini_verdicts(repo: Repository) -> tuple[int, int, int]:
    """Count Gemini verdict files. Returns (total_reviews, approvals, blocks)."""
    ...
```

**Input Example:**

```python
# Mock repo with docs/reports/ containing:
#   333/gemini-review-333.md  → content includes "Verdict: APPROVE"
#   334/gemini-review-334.md  → content includes "Verdict: APPROVE"
#   335/gemini-review-335.md  → content includes "Status: BLOCK"
#   336/gemini-review-336.md  → content includes "Verdict: APPROVE"
```

**Output Example:**

```python
(4, 3, 1)  # 4 total, 3 approvals, 1 block
```

**Edge Cases:**
- `docs/reports/` doesn't exist → returns `(0, 0, 0)`
- Verdict file content matches neither APPROVE nor BLOCK → counted in total but not in approvals or blocks
- File content is binary/unreadable → skipped, logged as warning

### 5.10 `aggregate_metrics()`

**File:** `assemblyzero/metrics/aggregator.py`

**Signature:**

```python
def aggregate_metrics(
    repo_metrics: list[RepoMetrics],
    period_start: str,
    period_end: str,
) -> AggregatedMetrics:
    """Combine per-repo metrics into unified cross-project summary."""
    ...
```

**Input Example:**

```python
repo_metrics = [
    {
        "repo": "martymcenroe/AssemblyZero",
        "period_start": "2026-01-26T00:00:00+00:00",
        "period_end": "2026-02-25T00:00:00+00:00",
        "issues_created": 42, "issues_closed": 35, "issues_open": 12,
        "workflows_used": {"requirements": 8, "tdd": 15},
        "llds_generated": 20, "gemini_reviews": 18,
        "gemini_approvals": 15, "gemini_blocks": 3,
        "collection_timestamp": "2026-02-25T14:30:00+00:00",
    },
    {
        "repo": "martymcenroe/ProjectAlpha",
        "period_start": "2026-01-26T00:00:00+00:00",
        "period_end": "2026-02-25T00:00:00+00:00",
        "issues_created": 25, "issues_closed": 20, "issues_open": 8,
        "workflows_used": {"requirements": 4, "tdd": 8, "implementation": 5},
        "llds_generated": 12, "gemini_reviews": 10,
        "gemini_approvals": 8, "gemini_blocks": 2,
        "collection_timestamp": "2026-02-25T14:30:15+00:00",
    },
    {
        "repo": "martymcenroe/ProjectBeta",
        "period_start": "2026-01-26T00:00:00+00:00",
        "period_end": "2026-02-25T00:00:00+00:00",
        "issues_created": 20, "issues_closed": 17, "issues_open": 5,
        "workflows_used": {"requirements": 3, "tdd": 5, "implementation": 5},
        "llds_generated": 8, "gemini_reviews": 7,
        "gemini_approvals": 7, "gemini_blocks": 0,
        "collection_timestamp": "2026-02-25T14:30:30+00:00",
    },
]
period_start = "2026-01-26T00:00:00+00:00"
period_end = "2026-02-25T00:00:00+00:00"
```

**Output Example:**

```python
{
    "repos_tracked": 3,
    "repos_reachable": 3,
    "period_start": "2026-01-26T00:00:00+00:00",
    "period_end": "2026-02-25T00:00:00+00:00",
    "total_issues_created": 87,
    "total_issues_closed": 72,
    "total_issues_open": 25,
    "total_llds_generated": 40,
    "total_gemini_reviews": 35,
    "gemini_approval_rate": 0.857,
    "workflows_by_type": {"requirements": 15, "tdd": 28, "implementation": 10},
    "per_repo": [... same 3 items ...],
    "generated_at": "2026-02-25T14:31:00+00:00",
}
```

**Edge Cases:**
- Empty list → all numeric fields `0`, `repos_tracked=0`, `repos_reachable=0`, `gemini_approval_rate=0.0`, `per_repo=[]`
- Single repo → aggregated totals equal that repo's values

### 5.11 `compute_approval_rate()`

**File:** `assemblyzero/metrics/aggregator.py`

**Signature:**

```python
def compute_approval_rate(approvals: int, total: int) -> float:
    """Safely compute approval rate. Returns 0.0 if total is 0."""
    ...
```

**Input/Output Examples:**

```python
compute_approval_rate(30, 35)  # → 0.857 (rounded to 3 decimal places)
compute_approval_rate(0, 0)    # → 0.0
compute_approval_rate(10, 10)  # → 1.0
compute_approval_rate(0, 5)    # → 0.0
```

### 5.12 `get_cache_path()`

**File:** `assemblyzero/metrics/cache.py`

**Signature:**

```python
def get_cache_path() -> Path:
    """Return ~/.assemblyzero/metrics_cache.json."""
    ...
```

**Output Example:**

```python
Path("/home/user/.assemblyzero/metrics_cache.json")
```

### 5.13 `load_cached_metrics()`

**File:** `assemblyzero/metrics/cache.py`

**Signature:**

```python
def load_cached_metrics(repo: str, cache_path: Path | None = None) -> RepoMetrics | None:
    """Load cached metrics for a repo if not expired. Returns None on miss/error."""
    ...
```

**Input Example:**

```python
repo = "martymcenroe/AssemblyZero"
cache_path = Path("/home/user/.assemblyzero/metrics_cache.json")
# Cache file contains entry with expires_at in the future
```

**Output Example (cache hit):**

```python
{
    "repo": "martymcenroe/AssemblyZero",
    "period_start": "2026-01-26T00:00:00+00:00",
    "period_end": "2026-02-25T00:00:00+00:00",
    "issues_created": 42,
    "issues_closed": 35,
    "issues_open": 12,
    "workflows_used": {"requirements": 8, "tdd": 15, "implementation": 10},
    "llds_generated": 20,
    "gemini_reviews": 18,
    "gemini_approvals": 15,
    "gemini_blocks": 3,
    "collection_timestamp": "2026-02-25T14:30:00+00:00",
}
```

**Output Example (cache miss/expired):** `None`

**Edge Cases:**
- Cache file doesn't exist → returns `None`, no exception
- Cache file is corrupt JSON → returns `None`, logs warning
- Entry expired → returns `None`
- Repo not in cache → returns `None`

### 5.14 `save_cached_metrics()`

**File:** `assemblyzero/metrics/cache.py`

**Signature:**

```python
def save_cached_metrics(
    repo: str,
    metrics: RepoMetrics,
    ttl_minutes: int,
    cache_path: Path | None = None,
) -> None:
    """Save metrics to disk cache with TTL. Sets file permissions to 0o600."""
    ...
```

**Input Example:**

```python
repo = "martymcenroe/AssemblyZero"
metrics = {  # RepoMetrics dict as in 5.13
    "repo": "martymcenroe/AssemblyZero",
    "period_start": "2026-01-26T00:00:00+00:00",
    "period_end": "2026-02-25T00:00:00+00:00",
    "issues_created": 42, "issues_closed": 35, "issues_open": 12,
    "workflows_used": {"requirements": 8, "tdd": 15, "implementation": 10},
    "llds_generated": 20, "gemini_reviews": 18,
    "gemini_approvals": 15, "gemini_blocks": 3,
    "collection_timestamp": "2026-02-25T14:30:00+00:00",
}
ttl_minutes = 60
```

**Output:** None (side effect: writes cache file)

**Edge Cases:**
- Cache directory `~/.assemblyzero/` doesn't exist → creates it with `mkdir(parents=True, exist_ok=True)`
- File permission setting fails (Windows) → logs warning, continues

### 5.15 `invalidate_cache()`

**File:** `assemblyzero/metrics/cache.py`

**Signature:**

```python
def invalidate_cache(repo: str | None = None, cache_path: Path | None = None) -> None:
    """Invalidate cache for a specific repo, or all repos if repo is None."""
    ...
```

**Input/Output Examples:**

```python
# Invalidate single repo:
invalidate_cache(repo="martymcenroe/AssemblyZero")
# → Removes only that entry from cache file; other entries remain

# Invalidate all:
invalidate_cache(repo=None)
# → Removes all entries from cache file (writes empty dict)
```

**Edge Cases:**
- Cache file doesn't exist → no-op, no error
- Repo not in cache → no-op, no error

### 5.16 `format_json_snapshot()`

**File:** `assemblyzero/metrics/formatters.py`

**Signature:**

```python
def format_json_snapshot(metrics: AggregatedMetrics) -> str:
    """Serialize aggregated metrics to pretty-printed JSON string."""
    ...
```

**Input Example:** `AggregatedMetrics` dict as in Section 4.3.

**Output Example:**

```json
{
    "repos_tracked": 3,
    "repos_reachable": 3,
    "period_start": "2026-01-26T00:00:00+00:00",
    "period_end": "2026-02-25T00:00:00+00:00",
    "total_issues_created": 87,
    "total_issues_closed": 72,
    "total_issues_open": 25,
    "total_llds_generated": 40,
    "total_gemini_reviews": 35,
    "gemini_approval_rate": 0.857,
    "workflows_by_type": {"requirements": 15, "tdd": 28, "implementation": 10},
    "per_repo": ["..."],
    "generated_at": "2026-02-25T14:31:00+00:00"
}
```

### 5.17 `format_markdown_table()`

**File:** `assemblyzero/metrics/formatters.py`

**Signature:**

```python
def format_markdown_table(metrics: AggregatedMetrics) -> str:
    """Format aggregated metrics as a markdown report with tables."""
    ...
```

**Input Example:** `AggregatedMetrics` dict as in Section 4.3.

**Output Example:**

```markdown
# Cross-Project Metrics Report

**Period:** 2026-01-26 to 2026-02-25
**Repos Tracked:** 3 | **Repos Reachable:** 3

## Summary

| Metric | Value |
|--------|-------|
| Total Issues Created | 87 |
| Total Issues Closed | 72 |
| Total Issues Open | 25 |
| Total LLDs Generated | 40 |
| Total Gemini Reviews | 35 |
| Gemini Approval Rate | 85.7% |

## Workflows by Type

| Workflow | Count |
|----------|-------|
| requirements | 15 |
| tdd | 28 |
| implementation | 10 |

## Per-Repository Breakdown

| Repo | Created | Closed | Open | LLDs | Reviews | Approval Rate |
|------|---------|--------|------|------|---------|---------------|
| martymcenroe/AssemblyZero | 42 | 35 | 12 | 20 | 18 | 83.3% |
| martymcenroe/ProjectAlpha | 25 | 20 | 8 | 12 | 10 | 80.0% |
| martymcenroe/ProjectBeta | 20 | 17 | 5 | 8 | 7 | 100.0% |
```

### 5.18 `write_snapshot()`

**File:** `assemblyzero/metrics/formatters.py`

**Signature:**

```python
def write_snapshot(metrics: AggregatedMetrics, output_dir: Path) -> Path:
    """Write JSON snapshot to output_dir/cross-project-{date}.json. Returns written path."""
    ...
```

**Input Example:**

```python
metrics = { ... }  # AggregatedMetrics
output_dir = Path("docs/metrics")
```

**Output Example:**

```python
Path("docs/metrics/cross-project-2026-02-25.json")
```

**Edge Cases:**
- Output directory doesn't exist → creates it with `mkdir(parents=True, exist_ok=True)`
- File already exists → overwrites (date-stamped names make this rare)

### 5.19 `create_repo_metrics()`

**File:** `assemblyzero/metrics/models.py`

**Signature:**

```python
def create_repo_metrics(
    repo: str,
    period_start: str,
    period_end: str,
    issues_created: int,
    issues_closed: int,
    issues_open: int,
    workflows_used: dict[str, int],
    llds_generated: int,
    gemini_reviews: int,
    gemini_approvals: int,
    gemini_blocks: int,
    collection_timestamp: str,
) -> RepoMetrics:
    """Create and validate a RepoMetrics dict."""
    ...
```

**Input Example:**

```python
create_repo_metrics(
    repo="martymcenroe/AssemblyZero",
    period_start="2026-01-26T00:00:00+00:00",
    period_end="2026-02-25T00:00:00+00:00",
    issues_created=42,
    issues_closed=35,
    issues_open=12,
    workflows_used={"requirements": 8, "tdd": 15},
    llds_generated=20,
    gemini_reviews=18,
    gemini_approvals=15,
    gemini_blocks=3,
    collection_timestamp="2026-02-25T14:30:00+00:00",
)
```

**Output Example:** Same as the RepoMetrics in Section 4.2.

**Edge Cases:**
- `issues_created=-1` → raises `ValueError("issues_created must be non-negative, got -1")`
- `gemini_blocks=-5` → raises `ValueError("gemini_blocks must be non-negative, got -5")`
- `repo=""` → raises `ValueError("repo cannot be empty")`

### 5.20 `validate_repo_metrics()`

**File:** `assemblyzero/metrics/models.py`

**Signature:**

```python
def validate_repo_metrics(metrics: dict[str, Any]) -> None:
    """Validate a metrics dict. Raises ValueError on invalid data."""
    ...
```

**Input/Output Examples:**

```python
# Valid — no error raised
validate_repo_metrics({"repo": "a/b", "issues_created": 5, ...})

# Invalid — raises ValueError
validate_repo_metrics({"repo": "a/b", "issues_created": -1, ...})
# → ValueError("issues_created must be non-negative, got -1")
```

### 5.21 `main()` (CLI)

**File:** `tools/collect-cross-project-metrics.py`

**Signature:**

```python
def main() -> int:
    """CLI entry point. Returns 0/1/2."""
    ...
```

**Input Example (argv):**

```bash
python tools/collect-cross-project-metrics.py --config ~/.assemblyzero/tracked_repos.json --period-days 30 --output-dir docs/metrics --format both --verbose
```

**Output Example (stdout — JSON):**

```json
{
    "repos_tracked": 3,
    "repos_reachable": 3,
    "total_issues_created": 87,
    "..."
}
```

**Output Example (stderr — logging):**

```
[metrics] Loading config from /home/user/.assemblyzero/tracked_repos.json
[metrics] Collecting metrics for martymcenroe/AssemblyZero...
[metrics] Cache miss for martymcenroe/AssemblyZero
[metrics] Collecting metrics for martymcenroe/ProjectAlpha...
[metrics] Cache hit for martymcenroe/ProjectAlpha
[metrics] Collecting metrics for martymcenroe/ProjectBeta...
[metrics] Failed to collect martymcenroe/ProjectBeta: 404 Not Found
[metrics] Aggregating metrics for 2 of 3 repos
[metrics] Snapshot written to docs/metrics/cross-project-2026-02-25.json
```

**Return Values:**
- `0` — all repos collected successfully
- `1` — some repos failed (partial success)
- `2` — all repos failed OR config error


## 6. Change Instructions

### 6.1 `assemblyzero/metrics/__init__.py` (Add)

**Complete file contents:**

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

### 6.2 `assemblyzero/metrics/models.py` (Add)

**Complete file contents:**

```python
"""Data models for cross-project metrics.

Issue #333: Typed data structures for repo metrics, aggregated metrics, and config.
"""

from __future__ import annotations

from typing import Any, TypedDict


class TrackedReposConfig(TypedDict):
    """Configuration for tracked repositories."""

    repos: list[str]
    cache_ttl_minutes: int
    github_token_env: str


class RepoMetrics(TypedDict):
    """Metrics collected for a single repository."""

    repo: str
    period_start: str
    period_end: str
    issues_created: int
    issues_closed: int
    issues_open: int
    workflows_used: dict[str, int]
    llds_generated: int
    gemini_reviews: int
    gemini_approvals: int
    gemini_blocks: int
    collection_timestamp: str


class AggregatedMetrics(TypedDict):
    """Cross-project aggregated metrics."""

    repos_tracked: int
    repos_reachable: int
    period_start: str
    period_end: str
    total_issues_created: int
    total_issues_closed: int
    total_issues_open: int
    total_llds_generated: int
    total_gemini_reviews: int
    gemini_approval_rate: float
    workflows_by_type: dict[str, int]
    per_repo: list[RepoMetrics]
    generated_at: str


class CacheEntry(TypedDict):
    """A cached metrics entry with expiry."""

    repo: str
    metrics: RepoMetrics
    cached_at: str
    expires_at: str


_NON_NEGATIVE_INT_FIELDS: list[str] = [
    "issues_created",
    "issues_closed",
    "issues_open",
    "llds_generated",
    "gemini_reviews",
    "gemini_approvals",
    "gemini_blocks",
]


def validate_repo_metrics(metrics: dict[str, Any]) -> None:
    """Validate a metrics dict. Raises ValueError on invalid data.

    Checks that all integer fields are non-negative and repo is non-empty.
    """
    repo = metrics.get("repo", "")
    if not repo:
        msg = "repo cannot be empty"
        raise ValueError(msg)

    for field in _NON_NEGATIVE_INT_FIELDS:
        value = metrics.get(field)
        if value is not None and value < 0:
            msg = f"{field} must be non-negative, got {value}"
            raise ValueError(msg)


def create_repo_metrics(
    *,
    repo: str,
    period_start: str,
    period_end: str,
    issues_created: int,
    issues_closed: int,
    issues_open: int,
    workflows_used: dict[str, int],
    llds_generated: int,
    gemini_reviews: int,
    gemini_approvals: int,
    gemini_blocks: int,
    collection_timestamp: str,
) -> RepoMetrics:
    """Create and validate a RepoMetrics dict.

    Raises ValueError if any field is invalid.
    """
    result: RepoMetrics = {
        "repo": repo,
        "period_start": period_start,
        "period_end": period_end,
        "issues_created": issues_created,
        "issues_closed": issues_closed,
        "issues_open": issues_open,
        "workflows_used": workflows_used,
        "llds_generated": llds_generated,
        "gemini_reviews": gemini_reviews,
        "gemini_approvals": gemini_approvals,
        "gemini_blocks": gemini_blocks,
        "collection_timestamp": collection_timestamp,
    }
    validate_repo_metrics(result)
    return result
```

### 6.3 `assemblyzero/metrics/config.py` (Add)

**Complete file contents:**

```python
"""Configuration loading and validation for cross-project metrics.

Issue #333: Load tracked repos config from ~/.assemblyzero/tracked_repos.json.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import orjson

from assemblyzero.metrics.models import TrackedReposConfig

REPO_NAME_PATTERN: re.Pattern[str] = re.compile(
    r"^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$"
)

_DEFAULT_CACHE_TTL_MINUTES: int = 60
_DEFAULT_GITHUB_TOKEN_ENV: str = "GITHUB_TOKEN"


class ConfigError(Exception):
    """Raised when configuration loading or validation fails."""


def get_default_config_path() -> Path:
    """Return ~/.assemblyzero/tracked_repos.json."""
    return Path.home() / ".assemblyzero" / "tracked_repos.json"


def validate_repo_name(name: str) -> bool:
    """Check if a repo name matches the allowed owner/name pattern."""
    return bool(REPO_NAME_PATTERN.match(name))


def validate_config(config: dict[str, Any]) -> TrackedReposConfig:
    """Validate raw dict against TrackedReposConfig schema.

    Raises ConfigError on validation failure.
    Applies defaults for optional fields.
    """
    if "repos" not in config:
        msg = "Missing required key: repos"
        raise ConfigError(msg)

    repos = config["repos"]
    if not isinstance(repos, list):
        msg = "repos must be a list"
        raise ConfigError(msg)

    if len(repos) == 0:
        msg = "repos list cannot be empty"
        raise ConfigError(msg)

    for repo_name in repos:
        if not isinstance(repo_name, str) or not validate_repo_name(repo_name):
            msg = f"Invalid repo name: {repo_name}"
            raise ConfigError(msg)

    cache_ttl = config.get("cache_ttl_minutes", _DEFAULT_CACHE_TTL_MINUTES)
    if not isinstance(cache_ttl, int) or cache_ttl < 0:
        msg = "cache_ttl_minutes must be non-negative"
        raise ConfigError(msg)

    token_env = config.get("github_token_env", _DEFAULT_GITHUB_TOKEN_ENV)
    if not isinstance(token_env, str) or not token_env:
        msg = "github_token_env must be a non-empty string"
        raise ConfigError(msg)

    return TrackedReposConfig(
        repos=repos,
        cache_ttl_minutes=cache_ttl,
        github_token_env=token_env,
    )


def load_config(config_path: Path | None = None) -> TrackedReposConfig:
    """Load and validate tracked repos config from disk.

    Default path: ~/.assemblyzero/tracked_repos.json
    Raises ConfigError if file missing, malformed, or repos list empty.
    """
    path = config_path or get_default_config_path()

    if not path.exists():
        msg = f"Config file not found: {path}"
        raise ConfigError(msg)

    raw_bytes = path.read_bytes()
    try:
        raw_config = orjson.loads(raw_bytes)
    except orjson.JSONDecodeError as exc:
        msg = f"Failed to parse config: {exc}"
        raise ConfigError(msg) from exc

    if not isinstance(raw_config, dict):
        msg = "Config must be a JSON object"
        raise ConfigError(msg)

    return validate_config(raw_config)
```

### 6.4 `assemblyzero/metrics/cache.py` (Add)

**Complete file contents:**

```python
"""Disk-based cache layer for cross-project metrics.

Issue #333: Cache API responses to minimize GitHub API calls.
"""

from __future__ import annotations

import logging
import os
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import orjson

from assemblyzero.metrics.models import CacheEntry, RepoMetrics

logger = logging.getLogger(__name__)


def get_cache_path() -> Path:
    """Return ~/.assemblyzero/metrics_cache.json."""
    return Path.home() / ".assemblyzero" / "metrics_cache.json"


def _load_cache_file(cache_path: Path) -> dict[str, Any]:
    """Load and parse the cache file. Returns empty dict on any error."""
    if not cache_path.exists():
        return {}
    try:
        raw = cache_path.read_bytes()
        data = orjson.loads(raw)
        if not isinstance(data, dict):
            logger.warning("Cache file is not a JSON object, treating as empty")
            return {}
        return data
    except (orjson.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read cache file %s: %s", cache_path, exc)
        return {}


def _write_cache_file(cache_path: Path, data: dict[str, Any]) -> None:
    """Write cache data to disk with owner-only permissions."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    raw = orjson.dumps(data, option=orjson.OPT_INDENT_2)
    cache_path.write_bytes(raw)
    try:
        os.chmod(cache_path, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
    except OSError as exc:
        logger.warning("Could not set file permissions on %s: %s", cache_path, exc)


def load_cached_metrics(
    repo: str,
    cache_path: Path | None = None,
) -> RepoMetrics | None:
    """Load cached metrics for a repo if cache entry exists and is not expired.

    Returns None if no cache, expired, or cache file corrupt.
    """
    path = cache_path or get_cache_path()
    cache_data = _load_cache_file(path)

    entry = cache_data.get(repo)
    if entry is None:
        logger.debug("Cache miss for %s: no entry", repo)
        return None

    expires_at_str = entry.get("expires_at", "")
    try:
        expires_at = datetime.fromisoformat(expires_at_str)
    except (ValueError, TypeError):
        logger.warning("Invalid expires_at for %s, treating as expired", repo)
        return None

    now = datetime.now(tz=timezone.utc)
    if now >= expires_at:
        logger.debug("Cache miss for %s: expired at %s", repo, expires_at_str)
        return None

    logger.debug("Cache hit for %s", repo)
    return entry.get("metrics")


def save_cached_metrics(
    repo: str,
    metrics: RepoMetrics,
    ttl_minutes: int,
    cache_path: Path | None = None,
) -> None:
    """Save metrics to disk cache with TTL."""
    path = cache_path or get_cache_path()
    cache_data = _load_cache_file(path)

    now = datetime.now(tz=timezone.utc)
    expires_at = now + timedelta(minutes=ttl_minutes)

    entry: CacheEntry = {
        "repo": repo,
        "metrics": metrics,
        "cached_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
    }
    cache_data[repo] = entry
    _write_cache_file(path, cache_data)
    logger.debug("Cached metrics for %s (expires %s)", repo, expires_at.isoformat())


def invalidate_cache(
    repo: str | None = None,
    cache_path: Path | None = None,
) -> None:
    """Invalidate cache for a specific repo, or all repos if repo is None."""
    path = cache_path or get_cache_path()

    if repo is None:
        # Invalidate all
        if path.exists():
            _write_cache_file(path, {})
            logger.debug("Invalidated all cache entries")
        return

    cache_data = _load_cache_file(path)
    if repo in cache_data:
        del cache_data[repo]
        _write_cache_file(path, cache_data)
        logger.debug("Invalidated cache for %s", repo)
```

### 6.5 `assemblyzero/metrics/collector.py` (Add)

**Complete file contents:**

```python
"""Per-repo metrics collection via GitHub API.

Issue #333: Fetch issue data, lineage counts, and verdict files per repository.
"""

from __future__ import annotations

import base64
import logging
import re
from datetime import datetime, timedelta, timezone

from github import Github, GithubException, UnknownObjectException
from github.ContentFile import ContentFile
from github.Repository import Repository

from assemblyzero.metrics.models import RepoMetrics, create_repo_metrics

logger = logging.getLogger(__name__)

_WORKFLOW_LABEL_PREFIX: str = "workflow:"
_APPROVE_PATTERN: re.Pattern[str] = re.compile(
    r"(?:Verdict|Status):\s*APPROVE", re.IGNORECASE
)
_BLOCK_PATTERN: re.Pattern[str] = re.compile(
    r"(?:Verdict|Status):\s*BLOCK", re.IGNORECASE
)


class CollectionError(Exception):
    """Raised when metrics collection fails for a repository."""


def collect_repo_metrics(
    repo_full_name: str,
    github_token: str,
    period_days: int = 30,
) -> RepoMetrics:
    """Collect all metrics for a single repository.

    Fetches issues, scans for lineage folders and verdict files.
    Uses PyGithub for API access.
    Raises CollectionError if repo is unreachable.
    """
    try:
        if github_token:
            gh = Github(github_token)
        else:
            logger.warning("No GitHub token provided. Only public repos accessible.")
            gh = Github()

        repo = gh.get_repo(repo_full_name)
    except UnknownObjectException as exc:
        msg = f"Failed to access repo '{repo_full_name}': {exc.data.get('message', str(exc))}"
        raise CollectionError(msg) from exc
    except GithubException as exc:
        msg = f"GitHub API error for '{repo_full_name}': {exc.data.get('message', str(exc)) if hasattr(exc, 'data') and exc.data else str(exc)}"
        raise CollectionError(msg) from exc

    now = datetime.now(tz=timezone.utc)
    period_end = now
    period_start = now - timedelta(days=period_days)

    created, closed, open_now = count_issues_in_period(repo, period_start, period_end)
    workflows = detect_workflows_used(repo)
    llds = count_lineage_artifacts(repo)
    total_reviews, approvals, blocks = count_gemini_verdicts(repo)

    return create_repo_metrics(
        repo=repo_full_name,
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
        issues_created=created,
        issues_closed=closed,
        issues_open=open_now,
        workflows_used=workflows,
        llds_generated=llds,
        gemini_reviews=total_reviews,
        gemini_approvals=approvals,
        gemini_blocks=blocks,
        collection_timestamp=now.isoformat(),
    )


def count_issues_in_period(
    repo: Repository,
    period_start: datetime,
    period_end: datetime,
) -> tuple[int, int, int]:
    """Count issues created, closed, and currently open.

    Returns (created_in_period, closed_in_period, currently_open).
    Uses 'since' parameter to minimize API pages fetched.
    """
    created = 0
    closed = 0

    # Get issues created since period_start (all states)
    all_issues = repo.get_issues(state="all", since=period_start)
    for issue in all_issues:
        if issue.pull_request is not None:
            continue  # Skip PRs
        if issue.created_at and period_start <= issue.created_at <= period_end:
            created += 1
        if (
            issue.closed_at
            and period_start <= issue.closed_at <= period_end
        ):
            closed += 1

    # Count currently open issues
    open_issues = repo.get_issues(state="open")
    open_now = sum(1 for i in open_issues if i.pull_request is None)

    return (created, closed, open_now)


def detect_workflows_used(repo: Repository) -> dict[str, int]:
    """Detect workflow types by scanning issue labels and LLD filenames.

    Scans labels: 'workflow:requirements', 'workflow:tdd', etc.
    Falls back to heuristic: LLD filenames.
    """
    workflow_counts: dict[str, int] = {}

    # Primary: scan issue labels
    issues = repo.get_issues(state="all")
    for issue in issues:
        if issue.pull_request is not None:
            continue
        for label in issue.labels:
            label_name = label.name if hasattr(label, "name") else str(label)
            if label_name.startswith(_WORKFLOW_LABEL_PREFIX):
                workflow_type = label_name[len(_WORKFLOW_LABEL_PREFIX) :]
                workflow_counts[workflow_type] = workflow_counts.get(workflow_type, 0) + 1

    # Fallback: heuristic from LLD filenames if no labels found
    if not workflow_counts:
        workflow_counts = _detect_workflows_from_lld_filenames(repo)

    return workflow_counts


def _detect_workflows_from_lld_filenames(repo: Repository) -> dict[str, int]:
    """Heuristic fallback: detect workflows from LLD filenames."""
    workflow_counts: dict[str, int] = {}
    keyword_map = {
        "requirements": "requirements",
        "tdd": "tdd",
        "implementation": "implementation",
        "design": "requirements",
    }

    for dir_path in ("docs/lld/active", "docs/lld/done"):
        try:
            contents = repo.get_contents(dir_path)
            if not isinstance(contents, list):
                contents = [contents]
            for item in contents:
                name_lower = item.name.lower()
                for keyword, workflow_type in keyword_map.items():
                    if keyword in name_lower:
                        workflow_counts[workflow_type] = (
                            workflow_counts.get(workflow_type, 0) + 1
                        )
                        break  # One workflow type per file
        except (UnknownObjectException, GithubException):
            continue

    return workflow_counts


def count_lineage_artifacts(repo: Repository) -> int:
    """Count LLD folders in docs/lld/active/ and docs/lld/done/ directories.

    Returns 0 if directories don't exist.
    """
    count = 0
    for dir_path in ("docs/lld/active", "docs/lld/done"):
        try:
            contents = repo.get_contents(dir_path)
            if isinstance(contents, list):
                count += len(contents)
            else:
                count += 1
        except (UnknownObjectException, GithubException):
            logger.debug("Directory %s not found in %s", dir_path, repo.full_name)
            continue
    return count


def _get_file_content(content_file: ContentFile) -> str:
    """Decode file content from a GitHub ContentFile."""
    if content_file.content is not None:
        return base64.b64decode(content_file.content).decode("utf-8", errors="replace")
    return ""


def count_gemini_verdicts(repo: Repository) -> tuple[int, int, int]:
    """Count Gemini verdict files and their outcomes.

    Scans docs/reports/*/gemini-*.md files.
    Returns (total_reviews, approvals, blocks).
    """
    total = 0
    approvals = 0
    blocks = 0

    try:
        reports_contents = repo.get_contents("docs/reports")
        if not isinstance(reports_contents, list):
            reports_contents = [reports_contents]
    except (UnknownObjectException, GithubException):
        logger.debug("docs/reports/ not found in %s", repo.full_name)
        return (0, 0, 0)

    for item in reports_contents:
        if item.type != "dir":
            continue
        try:
            dir_contents = repo.get_contents(item.path)
            if not isinstance(dir_contents, list):
                dir_contents = [dir_contents]
            for file_item in dir_contents:
                if not file_item.name.startswith("gemini-") or not file_item.name.endswith(".md"):
                    continue
                total += 1
                try:
                    content = _get_file_content(file_item)
                    if _APPROVE_PATTERN.search(content):
                        approvals += 1
                    elif _BLOCK_PATTERN.search(content):
                        blocks += 1
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Could not read verdict file %s: %s", file_item.path, exc
                    )
        except (UnknownObjectException, GithubException):
            continue

    return (total, approvals, blocks)
```

### 6.6 `assemblyzero/metrics/aggregator.py` (Add)

**Complete file contents:**

```python
"""Cross-project metrics aggregation.

Issue #333: Combine per-repo metrics into unified summary.
"""

from __future__ import annotations

from datetime import datetime, timezone

from assemblyzero.metrics.models import AggregatedMetrics, RepoMetrics


def compute_approval_rate(approvals: int, total: int) -> float:
    """Safely compute approval rate, returning 0.0 if total is 0.

    Result is rounded to 3 decimal places.
    """
    if total == 0:
        return 0.0
    return round(approvals / total, 3)


def aggregate_metrics(
    repo_metrics: list[RepoMetrics],
    period_start: str,
    period_end: str,
) -> AggregatedMetrics:
    """Combine per-repo metrics into a unified cross-project summary."""
    total_created = 0
    total_closed = 0
    total_open = 0
    total_llds = 0
    total_reviews = 0
    total_approvals = 0
    workflows_combined: dict[str, int] = {}

    for rm in repo_metrics:
        total_created += rm["issues_created"]
        total_closed += rm["issues_closed"]
        total_open += rm["issues_open"]
        total_llds += rm["llds_generated"]
        total_reviews += rm["gemini_reviews"]
        total_approvals += rm["gemini_approvals"]
        for wf_type, count in rm["workflows_used"].items():
            workflows_combined[wf_type] = workflows_combined.get(wf_type, 0) + count

    return AggregatedMetrics(
        repos_tracked=len(repo_metrics),
        repos_reachable=len(repo_metrics),
        period_start=period_start,
        period_end=period_end,
        total_issues_created=total_created,
        total_issues_closed=total_closed,
        total_issues_open=total_open,
        total_llds_generated=total_llds,
        total_gemini_reviews=total_reviews,
        gemini_approval_rate=compute_approval_rate(total_approvals, total_reviews),
        workflows_by_type=workflows_combined,
        per_repo=list(repo_metrics),
        generated_at=datetime.now(tz=timezone.utc).isoformat(),
    )
```

### 6.7 `assemblyzero/metrics/formatters.py` (Add)

**Complete file contents:**

```python
"""Output formatters for cross-project metrics.

Issue #333: JSON snapshot and markdown table formatters.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import orjson

from assemblyzero.metrics.models import AggregatedMetrics


def format_json_snapshot(metrics: AggregatedMetrics) -> str:
    """Serialize aggregated metrics to pretty-printed JSON string."""
    raw = orjson.dumps(dict(metrics), option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS)
    return raw.decode("utf-8")


def format_markdown_table(metrics: AggregatedMetrics) -> str:
    """Format aggregated metrics as a markdown report with tables."""
    lines: list[str] = []
    lines.append("# Cross-Project Metrics Report")
    lines.append("")

    period_start = metrics["period_start"][:10]
    period_end = metrics["period_end"][:10]
    lines.append(
        f"**Period:** {period_start} to {period_end}"
    )
    lines.append(
        f"**Repos Tracked:** {metrics['repos_tracked']} | "
        f"**Repos Reachable:** {metrics['repos_reachable']}"
    )
    lines.append("")

    # Summary table
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total Issues Created | {metrics['total_issues_created']} |")
    lines.append(f"| Total Issues Closed | {metrics['total_issues_closed']} |")
    lines.append(f"| Total Issues Open | {metrics['total_issues_open']} |")
    lines.append(f"| Total LLDs Generated | {metrics['total_llds_generated']} |")
    lines.append(f"| Total Gemini Reviews | {metrics['total_gemini_reviews']} |")
    approval_pct = f"{metrics['gemini_approval_rate'] * 100:.1f}%"
    lines.append(f"| Gemini Approval Rate | {approval_pct} |")
    lines.append("")

    # Workflows table
    if metrics["workflows_by_type"]:
        lines.append("## Workflows by Type")
        lines.append("")
        lines.append("| Workflow | Count |")
        lines.append("|----------|-------|")
        for wf_type, count in sorted(metrics["workflows_by_type"].items()):
            lines.append(f"| {wf_type} | {count} |")
        lines.append("")

    # Per-repo table
    if metrics["per_repo"]:
        lines.append("## Per-Repository Breakdown")
        lines.append("")
        lines.append(
            "| Repo | Created | Closed | Open | LLDs | Reviews | Approval Rate |"
        )
        lines.append(
            "|------|---------|--------|------|------|---------|---------------|"
        )
        for rm in metrics["per_repo"]:
            if rm["gemini_reviews"] > 0:
                rate = f"{rm['gemini_approvals'] / rm['gemini_reviews'] * 100:.1f}%"
            else:
                rate = "N/A"
            lines.append(
                f"| {rm['repo']} | {rm['issues_created']} | {rm['issues_closed']} | "
                f"{rm['issues_open']} | {rm['llds_generated']} | "
                f"{rm['gemini_reviews']} | {rate} |"
            )
        lines.append("")

    return "\n".join(lines)


def write_snapshot(metrics: AggregatedMetrics, output_dir: Path) -> Path:
    """Write JSON snapshot to output_dir/cross-project-{date}.json.

    Returns the path of the written file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    filename = f"cross-project-{date_str}.json"
    output_path = output_dir / filename
    json_content = format_json_snapshot(metrics)
    output_path.write_text(json_content, encoding="utf-8")
    return output_path
```

### 6.8 `tools/collect-cross-project-metrics.py` (Add)

**Complete file contents:**

```python
#!/usr/bin/env python3
"""Collect cross-project metrics for AssemblyZero usage tracking.

Issue #333: CLI entry point for cross-project metrics aggregation.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

# Project root on sys.path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from assemblyzero.metrics.aggregator import aggregate_metrics
from assemblyzero.metrics.cache import (
    invalidate_cache,
    load_cached_metrics,
    save_cached_metrics,
)
from assemblyzero.metrics.collector import CollectionError, collect_repo_metrics
from assemblyzero.metrics.config import ConfigError, load_config
from assemblyzero.metrics.formatters import (
    format_json_snapshot,
    format_markdown_table,
    write_snapshot,
)
from assemblyzero.metrics.models import RepoMetrics

logger = logging.getLogger("metrics")


def _setup_logging(verbose: bool) -> None:
    """Configure logging to stderr with [metrics] prefix."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("[metrics] %(message)s"))
    level = logging.DEBUG if verbose else logging.INFO
    root_logger = logging.getLogger("metrics")
    root_logger.setLevel(level)
    root_logger.addHandler(handler)
    # Also configure the assemblyzero.metrics loggers
    lib_logger = logging.getLogger("assemblyzero.metrics")
    lib_logger.setLevel(level)
    lib_logger.addHandler(handler)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Collect cross-project AssemblyZero usage metrics.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Config file path (default: ~/.assemblyzero/tracked_repos.json)",
    )
    parser.add_argument(
        "--period-days",
        type=int,
        default=30,
        help="Lookback period in days (default: 30)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("docs/metrics"),
        help="Output directory (default: docs/metrics/)",
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown", "both"],
        default="both",
        dest="output_format",
        help="Output format (default: both)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Bypass cache, fetch fresh data",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Returns 0 on success, 1 on partial failure, 2 on complete failure.
    """
    args = _parse_args(argv)
    _setup_logging(args.verbose)

    # Load config
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        logger.error("Configuration error: %s", exc)
        return 2

    # Resolve GitHub token
    token_env = config["github_token_env"]
    github_token = os.environ.get(token_env, "")
    if not github_token:
        logger.warning(
            "No token found in env var '%s'. Only public repos will be accessible.",
            token_env,
        )

    # Collect per-repo metrics
    collected: list[RepoMetrics] = []
    failed_repos: list[str] = []

    for repo_name in config["repos"]:
        # Check cache unless --no-cache
        if not args.no_cache:
            cached = load_cached_metrics(repo_name)
            if cached is not None:
                logger.info("Cache hit for %s", repo_name)
                collected.append(cached)
                continue

        logger.info("Collecting metrics for %s...", repo_name)
        try:
            metrics = collect_repo_metrics(
                repo_name,
                github_token,
                period_days=args.period_days,
            )
            collected.append(metrics)
            # Save to cache
            if not args.no_cache:
                save_cached_metrics(
                    repo_name, metrics, config["cache_ttl_minutes"]
                )
        except CollectionError as exc:
            logger.warning("Failed to collect %s: %s", repo_name, exc)
            failed_repos.append(repo_name)

    # Check for complete failure
    if not collected:
        logger.error(
            "Complete failure: could not collect metrics from any of %d repos",
            len(config["repos"]),
        )
        return 2

    # Aggregate
    from datetime import datetime, timedelta, timezone

    now = datetime.now(tz=timezone.utc)
    period_start = (now - timedelta(days=args.period_days)).isoformat()
    period_end = now.isoformat()

    aggregated = aggregate_metrics(collected, period_start, period_end)
    # Adjust repos_tracked to include failed repos
    aggregated["repos_tracked"] = len(config["repos"])

    # Output
    if args.output_format in ("json", "both"):
        json_output = format_json_snapshot(aggregated)
        sys.stdout.write(json_output + "\n")
        snapshot_path = write_snapshot(aggregated, args.output_dir)
        logger.info("Snapshot written to %s", snapshot_path)

    if args.output_format in ("markdown", "both"):
        md_output = format_markdown_table(aggregated)
        md_path = args.output_dir / "cross-project-latest.md"
        args.output_dir.mkdir(parents=True, exist_ok=True)
        md_path.write_text(md_output, encoding="utf-8")
        logger.info("Markdown report written to %s", md_path)

    # Summary
    logger.info(
        "Collected %d of %d repos (%d failed)",
        len(collected),
        len(config["repos"]),
        len(failed_repos),
    )

    if failed_repos:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### 6.9 `docs/metrics/.gitkeep` (Add)

**Complete file contents:** Empty file (0 bytes).

### 6.10 Test Fixtures (Add)

#### `tests/fixtures/metrics/tracked_repos_valid.json`

```json
{
    "repos": [
        "martymcenroe/AssemblyZero",
        "martymcenroe/ProjectAlpha",
        "martymcenroe/ProjectBeta"
    ],
    "cache_ttl_minutes": 60,
    "github_token_env": "GITHUB_TOKEN"
}
```

#### `tests/fixtures/metrics/tracked_repos_empty.json`

```json
{
    "repos": [],
    "cache_ttl_minutes": 60,
    "github_token_env": "GITHUB_TOKEN"
}
```

#### `tests/fixtures/metrics/tracked_repos_malformed.json`

```
{this is not valid JSON at all!!!
```

#### `tests/fixtures/metrics/mock_issues_response.json`

```json
[
    {
        "number": 100,
        "title": "Add user authentication",
        "state": "closed",
        "created_at": "2026-02-01T10:00:00Z",
        "closed_at": "2026-02-10T15:00:00Z",
        "labels": ["workflow:requirements", "priority:high"],
        "pull_request": null
    },
    {
        "number": 101,
        "title": "Implement TDD workflow for parser",
        "state": "closed",
        "created_at": "2026-02-05T09:00:00Z",
        "closed_at": "2026-02-15T11:00:00Z",
        "labels": ["workflow:tdd"],
        "pull_request": null
    },
    {
        "number": 102,
        "title": "Fix deployment script",
        "state": "open",
        "created_at": "2026-02-20T14:00:00Z",
        "closed_at": null,
        "labels": ["bug"],
        "pull_request": null
    },
    {
        "number": 103,
        "title": "Update dependencies",
        "state": "open",
        "created_at": "2026-02-22T08:00:00Z",
        "closed_at": null,
        "labels": ["workflow:requirements"],
        "pull_request": null
    }
]
```

#### `tests/fixtures/metrics/mock_lineage_tree.json`

```json
{
    "docs/lld/active": [
        {"name": "333-cross-project-metrics", "type": "dir"},
        {"name": "334-auth-redesign", "type": "dir"},
        {"name": "335-tdd-workflow", "type": "dir"}
    ],
    "docs/lld/done": [
        {"name": "300-initial-setup", "type": "dir"},
        {"name": "301-ci-pipeline", "type": "dir"}
    ]
}
```

#### `tests/fixtures/metrics/expected_aggregated_output.json`

```json
{
    "repos_tracked": 3,
    "repos_reachable": 3,
    "period_start": "2026-01-26T00:00:00+00:00",
    "period_end": "2026-02-25T00:00:00+00:00",
    "total_issues_created": 87,
    "total_issues_closed": 72,
    "total_issues_open": 25,
    "total_llds_generated": 40,
    "total_gemini_reviews": 35,
    "gemini_approval_rate": 0.857,
    "workflows_by_type": {
        "requirements": 15,
        "tdd": 28,
        "implementation": 10
    },
    "per_repo": [],
    "generated_at": "2026-02-25T14:31:00+00:00"
}
```

### 6.11 `tests/unit/test_metrics_models.py` (Add)

**Complete file contents:**

```python
"""Unit tests for assemblyzero.metrics.models.

Issue #333: Tests for data model creation and validation.
"""

from __future__ import annotations

import pytest

from assemblyzero.metrics.models import (
    create_repo_metrics,
    validate_repo_metrics,
)


class TestValidateRepoMetrics:
    """Tests for validate_repo_metrics()."""

    def test_valid_metrics_no_error(self) -> None:
        """Valid metrics dict does not raise."""
        metrics = {
            "repo": "martymcenroe/AssemblyZero",
            "issues_created": 42,
            "issues_closed": 35,
            "issues_open": 12,
            "llds_generated": 20,
            "gemini_reviews": 18,
            "gemini_approvals": 15,
            "gemini_blocks": 3,
        }
        validate_repo_metrics(metrics)  # Should not raise

    def test_negative_issues_created_raises(self) -> None:
        """T240 (REQ-2): Negative issues_created raises ValueError."""
        metrics = {
            "repo": "martymcenroe/AssemblyZero",
            "issues_created": -1,
            "issues_closed": 0,
            "issues_open": 0,
            "llds_generated": 0,
            "gemini_reviews": 0,
            "gemini_approvals": 0,
            "gemini_blocks": 0,
        }
        with pytest.raises(ValueError, match="issues_created must be non-negative, got -1"):
            validate_repo_metrics(metrics)

    def test_negative_gemini_blocks_raises(self) -> None:
        """T240 (REQ-2): Negative gemini_blocks raises ValueError."""
        metrics = {
            "repo": "martymcenroe/AssemblyZero",
            "issues_created": 0,
            "issues_closed": 0,
            "issues_open": 0,
            "llds_generated": 0,
            "gemini_reviews": 0,
            "gemini_approvals": 0,
            "gemini_blocks": -5,
        }
        with pytest.raises(ValueError, match="gemini_blocks must be non-negative, got -5"):
            validate_repo_metrics(metrics)

    def test_empty_repo_raises(self) -> None:
        """T240 (REQ-2): Empty repo string raises ValueError."""
        metrics = {
            "repo": "",
            "issues_created": 0,
        }
        with pytest.raises(ValueError, match="repo cannot be empty"):
            validate_repo_metrics(metrics)


class TestCreateRepoMetrics:
    """Tests for create_repo_metrics()."""

    def test_creates_valid_metrics(self) -> None:
        """T240 (REQ-2): Creates a valid RepoMetrics dict."""
        result = create_repo_metrics(
            repo="martymcenroe/AssemblyZero",
            period_start="2026-01-26T00:00:00+00:00",
            period_end="2026-02-25T00:00:00+00:00",
            issues_created=42,
            issues_closed=35,
            issues_open=12,
            workflows_used={"requirements": 8, "tdd": 15},
            llds_generated=20,
            gemini_reviews=18,
            gemini_approvals=15,
            gemini_blocks=3,
            collection_timestamp="2026-02-25T14:30:00+00:00",
        )
        assert result["repo"] == "martymcenroe/AssemblyZero"
        assert result["issues_created"] == 42
        assert result["workflows_used"] == {"requirements": 8, "tdd": 15}

    def test_rejects_negative_value(self) -> None:
        """T240 (REQ-2): Rejects creation with negative value."""
        with pytest.raises(ValueError, match="issues_created must be non-negative"):
            create_repo_metrics(
                repo="martymcenroe/AssemblyZero",
                period_start="2026-01-26T00:00:00+00:00",
                period_end="2026-02-25T00:00:00+00:00",
                issues_created=-1,
                issues_closed=0,
                issues_open=0,
                workflows_used={},
                llds_generated=0,
                gemini_reviews=0,
                gemini_approvals=0,
                gemini_blocks=0,
                collection_timestamp="2026-02-25T14:30:00+00:00",
            )
```

### 6.12 `tests/unit/test_metrics_config.py` (Add)

**Complete file contents:**

```python
"""Unit tests for assemblyzero.metrics.config.

Issue #333: Tests for config loading and validation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from assemblyzero.metrics.config import (
    ConfigError,
    get_default_config_path,
    load_config,
    validate_config,
    validate_repo_name,
)

_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "metrics"


class TestLoadConfig:
    """Tests for load_config()."""

    def test_load_valid_config(self) -> None:
        """T010 (REQ-1): Valid config file returns TrackedReposConfig with 3 repos."""
        config = load_config(_FIXTURES_DIR / "tracked_repos_valid.json")
        assert len(config["repos"]) == 3
        assert config["repos"][0] == "martymcenroe/AssemblyZero"
        assert config["cache_ttl_minutes"] == 60
        assert config["github_token_env"] == "GITHUB_TOKEN"

    def test_load_missing_file_raises(self) -> None:
        """T020 (REQ-1): Missing file raises ConfigError with path."""
        missing = _FIXTURES_DIR / "nonexistent.json"
        with pytest.raises(ConfigError, match=str(missing)):
            load_config(missing)

    def test_load_malformed_json_raises(self) -> None:
        """T030 (REQ-1): Malformed JSON raises ConfigError."""
        with pytest.raises(ConfigError, match="Failed to parse"):
            load_config(_FIXTURES_DIR / "tracked_repos_malformed.json")

    def test_load_empty_repos_raises(self) -> None:
        """T040 (REQ-1): Empty repos list raises ConfigError."""
        with pytest.raises(ConfigError, match="repos list cannot be empty"):
            load_config(_FIXTURES_DIR / "tracked_repos_empty.json")


class TestGetDefaultConfigPath:
    """Tests for get_default_config_path()."""

    def test_default_path_resolution(self) -> None:
        """T050 (REQ-1): Default path ends with .assemblyzero/tracked_repos.json."""
        path = get_default_config_path()
        assert path.name == "tracked_repos.json"
        assert path.parent.name == ".assemblyzero"


class TestValidateConfig:
    """Tests for validate_config()."""

    def test_missing_repos_key(self) -> None:
        """T010 (REQ-1): Missing 'repos' key raises ConfigError."""
        with pytest.raises(ConfigError, match="Missing required key: repos"):
            validate_config({"cache_ttl_minutes": 60})

    def test_repos_not_a_list(self) -> None:
        """T010 (REQ-1): Non-list 'repos' raises ConfigError."""
        with pytest.raises(ConfigError, match="repos must be a list"):
            validate_config({"repos": "not-a-list"})

    def test_defaults_applied(self) -> None:
        """T010 (REQ-1): Defaults applied for optional fields."""
        config = validate_config({"repos": ["martymcenroe/AssemblyZero"]})
        assert config["cache_ttl_minutes"] == 60
        assert config["github_token_env"] == "GITHUB_TOKEN"

    def test_negative_ttl_raises(self) -> None:
        """T010 (REQ-1): Negative TTL raises ConfigError."""
        with pytest.raises(ConfigError, match="cache_ttl_minutes must be non-negative"):
            validate_config({"repos": ["a/b"], "cache_ttl_minutes": -1})


class TestValidateRepoName:
    """Tests for validate_repo_name()."""

    def test_valid_names(self) -> None:
        """T250 (REQ-1): Valid repo names are accepted."""
        assert validate_repo_name("martymcenroe/AssemblyZero") is True
        assert validate_repo_name("org.name/repo-v2") is True
        assert validate_repo_name("valid_org/valid_repo") is True

    def test_injection_strings_rejected(self) -> None:
        """T250 (REQ-1): Injection strings are rejected."""
        assert validate_repo_name("'; DROP TABLE--") is False
        assert validate_repo_name("") is False
        assert validate_repo_name("no-slash") is False
        assert validate_repo_name("a/b/c") is False
        assert validate_repo_name("a/ b") is False
```

### 6.13 `tests/unit/test_metrics_cache.py` (Add)

**Complete file contents:**

```python
"""Unit tests for assemblyzero.metrics.cache.

Issue #333: Tests for disk-based cache behavior.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from assemblyzero.metrics.cache import (
    invalidate_cache,
    load_cached_metrics,
    save_cached_metrics,
)
from assemblyzero.metrics.models import RepoMetrics


def _make_test_metrics(repo: str = "martymcenroe/AssemblyZero") -> RepoMetrics:
    """Create test RepoMetrics."""
    return RepoMetrics(
        repo=repo,
        period_start="2026-01-26T00:00:00+00:00",
        period_end="2026-02-25T00:00:00+00:00",
        issues_created=42,
        issues_closed=35,
        issues_open=12,
        workflows_used={"requirements": 8, "tdd": 15},
        llds_generated=20,
        gemini_reviews=18,
        gemini_approvals=15,
        gemini_blocks=3,
        collection_timestamp="2026-02-25T14:30:00+00:00",
    )


class TestCacheRoundTrip:
    """Tests for save and load cycle."""

    def test_save_and_load_round_trip(self, tmp_path: Path) -> None:
        """T160 (REQ-8): Saved metrics load back identically within TTL."""
        cache_path = tmp_path / "cache.json"
        metrics = _make_test_metrics()
        save_cached_metrics("martymcenroe/AssemblyZero", metrics, ttl_minutes=60, cache_path=cache_path)
        loaded = load_cached_metrics("martymcenroe/AssemblyZero", cache_path=cache_path)
        assert loaded is not None
        assert loaded["repo"] == "martymcenroe/AssemblyZero"
        assert loaded["issues_created"] == 42
        assert loaded["workflows_used"] == {"requirements": 8, "tdd": 15}


class TestCacheExpiry:
    """Tests for cache TTL."""

    def test_expired_entry_returns_none(self, tmp_path: Path) -> None:
        """T170 (REQ-8): Expired entry returns None."""
        cache_path = tmp_path / "cache.json"
        metrics = _make_test_metrics()
        save_cached_metrics("martymcenroe/AssemblyZero", metrics, ttl_minutes=0, cache_path=cache_path)
        time.sleep(0.1)  # Ensure expiry
        loaded = load_cached_metrics("martymcenroe/AssemblyZero", cache_path=cache_path)
        assert loaded is None


class TestCacheCorruption:
    """Tests for corrupt cache handling."""

    def test_corrupt_file_returns_none(self, tmp_path: Path) -> None:
        """T180 (REQ-8): Corrupt JSON file returns None."""
        cache_path = tmp_path / "cache.json"
        cache_path.write_text("{this is not valid json!!!", encoding="utf-8")
        loaded = load_cached_metrics("martymcenroe/AssemblyZero", cache_path=cache_path)
        assert loaded is None


class TestCacheInvalidation:
    """Tests for cache invalidation."""

    def test_invalidate_single_repo(self, tmp_path: Path) -> None:
        """T190 (REQ-8): Invalidate removes only specified repo."""
        cache_path = tmp_path / "cache.json"
        for name in ["test/a", "test/b", "test/c"]:
            save_cached_metrics(name, _make_test_metrics(name), ttl_minutes=60, cache_path=cache_path)
        invalidate_cache("test/b", cache_path=cache_path)
        assert load_cached_metrics("test/a", cache_path=cache_path) is not None
        assert load_cached_metrics("test/b", cache_path=cache_path) is None
        assert load_cached_metrics("test/c", cache_path=cache_path) is not None

    def test_invalidate_all(self, tmp_path: Path) -> None:
        """T200 (REQ-8): Invalidate all removes all entries."""
        cache_path = tmp_path / "cache.json"
        for name in ["test/a", "test/b", "test/c"]:
            save_cached_metrics(name, _make_test_metrics(name), ttl_minutes=60, cache_path=cache_path)
        invalidate_cache(repo=None, cache_path=cache_path)
        assert load_cached_metrics("test/a", cache_path=cache_path) is None
        assert load_cached_metrics("test/b", cache_path=cache_path) is None
        assert load_cached_metrics("test/c", cache_path=cache_path) is None
```

### 6.14 `tests/unit/test_metrics_collector.py` (Add)

**Complete file contents:**

```python
"""Unit tests for assemblyzero.metrics.collector.

Issue #333: Tests for per-repo collection logic.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from assemblyzero.metrics.collector import (
    CollectionError,
    collect_repo_metrics,
    count_gemini_verdicts,
    count_issues_in_period,
    count_lineage_artifacts,
    detect_workflows_used,
)
from github import UnknownObjectException


def _mock_issue(
    number: int,
    state: str,
    created_at: datetime,
    closed_at: datetime | None = None,
    labels: list[str] | None = None,
    is_pr: bool = False,
) -> MagicMock:
    """Create a mock PyGithub Issue."""
    issue = MagicMock()
    issue.number = number
    issue.state = state
    issue.created_at = created_at
    issue.closed_at = closed_at
    issue.pull_request = MagicMock() if is_pr else None
    mock_labels = []
    for label_name in (labels or []):
        lbl = MagicMock()
        lbl.name = label_name
        mock_labels.append(lbl)
    issue.labels = mock_labels
    return issue


def _mock_content_file(name: str, file_type: str = "dir", content: str | None = None) -> MagicMock:
    """Create a mock PyGithub ContentFile."""
    cf = MagicMock()
    cf.name = name
    cf.type = file_type
    cf.path = f"docs/reports/333/{name}" if file_type == "file" else f"docs/lld/active/{name}"
    if content is not None:
        import base64
        cf.content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    else:
        cf.content = None
    return cf


class TestCountIssuesInPeriod:
    """Tests for count_issues_in_period()."""

    def test_counts_issues_correctly(self) -> None:
        """T060 (REQ-2): Returns correct (created, closed, open) tuple."""
        repo = MagicMock()
        period_start = datetime(2026, 2, 1, tzinfo=timezone.utc)
        period_end = datetime(2026, 2, 25, tzinfo=timezone.utc)

        all_issues = [
            _mock_issue(1, "closed", datetime(2026, 2, 5, tzinfo=timezone.utc), datetime(2026, 2, 10, tzinfo=timezone.utc)),
            _mock_issue(2, "closed", datetime(2026, 2, 8, tzinfo=timezone.utc), datetime(2026, 2, 15, tzinfo=timezone.utc)),
            _mock_issue(3, "open", datetime(2026, 2, 12, tzinfo=timezone.utc)),
            _mock_issue(4, "open", datetime(2026, 2, 20, tzinfo=timezone.utc)),
        ]
        open_issues = [
            _mock_issue(3, "open", datetime(2026, 2, 12, tzinfo=timezone.utc)),
            _mock_issue(4, "open", datetime(2026, 2, 20, tzinfo=timezone.utc)),
        ]
        repo.get_issues.side_effect = lambda state, since=None: all_issues if state == "all" else open_issues

        created, closed, open_now = count_issues_in_period(repo, period_start, period_end)
        assert created == 4
        assert closed == 2
        assert open_now == 2

    def test_configurable_period_7_days(self) -> None:
        """T300 (REQ-2): Respects period_days for date range filtering."""
        repo = MagicMock()
        period_start = datetime(2026, 2, 18, tzinfo=timezone.utc)
        period_end = datetime(2026, 2, 25, tzinfo=timezone.utc)

        # Only issues in 7-day window
        all_issues = [
            _mock_issue(1, "open", datetime(2026, 2, 20, tzinfo=timezone.utc)),
            _mock_issue(2, "closed", datetime(2026, 2, 1, tzinfo=timezone.utc), datetime(2026, 2, 19, tzinfo=timezone.utc)),
        ]
        open_issues = [_mock_issue(1, "open", datetime(2026, 2, 20, tzinfo=timezone.utc))]
        repo.get_issues.side_effect = lambda state, since=None: all_issues if state == "all" else open_issues

        created, closed, open_now = count_issues_in_period(repo, period_start, period_end)
        assert created == 1  # Only issue #1 created in window
        assert closed == 1   # Issue #2 closed in window
        assert open_now == 1


class TestDetectWorkflowsUsed:
    """Tests for detect_workflows_used()."""

    def test_detects_from_labels(self) -> None:
        """T070 (REQ-3): Returns dict with correct workflow type counts."""
        repo = MagicMock()
        issues = [
            _mock_issue(1, "closed", datetime(2026, 2, 1, tzinfo=timezone.utc), labels=["workflow:requirements"]),
            _mock_issue(2, "open", datetime(2026, 2, 5, tzinfo=timezone.utc), labels=["workflow:requirements", "workflow:tdd"]),
            _mock_issue(3, "closed", datetime(2026, 2, 10, tzinfo=timezone.utc), labels=["workflow:tdd"]),
            _mock_issue(4, "open", datetime(2026, 2, 15, tzinfo=timezone.utc), labels=["bug"]),
        ]
        repo.get_issues.return_value = issues

        result = detect_workflows_used(repo)
        assert result == {"requirements": 2, "tdd": 2}

    def test_heuristic_fallback_from_filenames(self) -> None:
        """T310 (REQ-3): Detects workflows from LLD filenames when labels absent."""
        repo = MagicMock()
        # No workflow labels on issues
        issues = [
            _mock_issue(1, "open", datetime(2026, 2, 1, tzinfo=timezone.utc), labels=["bug"]),
        ]
        repo.get_issues.return_value = issues

        # LLD filenames contain workflow keywords
        active_contents = [
            _mock_content_file("333-requirements-analysis", "dir"),
            _mock_content_file("334-tdd-workflow", "dir"),
        ]
        done_contents = [
            _mock_content_file("300-requirements-setup", "dir"),
        ]
        repo.get_contents.side_effect = lambda path: (
            active_contents if "active" in path else done_contents
        )

        result = detect_workflows_used(repo)
        assert "requirements" in result
        assert result["requirements"] >= 2
        assert "tdd" in result


class TestCountLineageArtifacts:
    """Tests for count_lineage_artifacts()."""

    def test_counts_lld_folders(self) -> None:
        """T080 (REQ-4): Returns correct LLD count."""
        repo = MagicMock()
        active_contents = [
            _mock_content_file("333-metrics", "dir"),
            _mock_content_file("334-auth", "dir"),
        ]
        done_contents = [
            _mock_content_file("300-setup", "dir"),
            _mock_content_file("301-ci", "dir"),
            _mock_content_file("302-deploy", "dir"),
        ]
        repo.get_contents.side_effect = lambda path: (
            active_contents if "active" in path else done_contents
        )

        count = count_lineage_artifacts(repo)
        assert count == 5

    def test_missing_directory_returns_zero(self) -> None:
        """T110 (REQ-4): Returns 0 if docs/lld/ doesn't exist."""
        repo = MagicMock()
        repo.full_name = "test/repo"
        repo.get_contents.side_effect = UnknownObjectException(
            404, {"message": "Not Found"}, {}
        )

        count = count_lineage_artifacts(repo)
        assert count == 0


class TestCountGeminiVerdicts:
    """Tests for count_gemini_verdicts()."""

    def test_counts_verdicts_correctly(self) -> None:
        """T090 (REQ-5): Returns correct (total, approvals, blocks) tuple."""
        repo = MagicMock()
        repo.full_name = "test/repo"

        report_dirs = [
            _mock_content_file("333", "dir"),
            _mock_content_file("334", "dir"),
        ]
        dir_333_files = [
            _mock_content_file("gemini-review-333.md", "file", content="Verdict: APPROVE\nDetails..."),
            _mock_content_file("gemini-review-333-2.md", "file", content="Status: APPROVE\nOK"),
        ]
        dir_334_files = [
            _mock_content_file("gemini-review-334.md", "file", content="Verdict: BLOCK\nIssue found"),
            _mock_content_file("gemini-review-334-2.md", "file", content="Verdict: APPROVE\nGood"),
        ]

        def get_contents_side_effect(path: str) -> list[MagicMock]:
            if path == "docs/reports":
                return report_dirs
            if "333" in path:
                return dir_333_files
            if "334" in path:
                return dir_334_files
            return []

        repo.get_contents.side_effect = get_contents_side_effect

        total, approvals, blocks = count_gemini_verdicts(repo)
        assert total == 4
        assert approvals == 3
        assert blocks == 1


class TestCollectRepoMetrics:
    """Tests for collect_repo_metrics()."""

    @patch("assemblyzero.metrics.collector.Github")
    def test_unreachable_repo_raises_collection_error(self, mock_github_cls: MagicMock) -> None:
        """T100 (REQ-10): Raises CollectionError for unreachable repo."""
        mock_gh = MagicMock()
        mock_github_cls.return_value = mock_gh
        mock_gh.get_repo.side_effect = UnknownObjectException(
            404, {"message": "Not Found"}, {}
        )

        with pytest.raises(CollectionError, match="martymcenroe/NonExistent"):
            collect_repo_metrics("martymcenroe/NonExistent", "ghp_fake_token")

    @patch("assemblyzero.metrics.collector.Github")
    def test_token_passed_to_github(self, mock_github_cls: MagicMock) -> None:
        """T260 (REQ-9): Token passed to Github() constructor."""
        mock_gh = MagicMock()
        mock_github_cls.return_value = mock_gh
        mock_repo = MagicMock()
        mock_gh.get_repo.return_value = mock_repo
        # Stub out sub-functions
        mock_repo.get_issues.return_value = []
        mock_repo.get_contents.side_effect = UnknownObjectException(404, {"message": "Not Found"}, {})
        mock_repo.full_name = "martymcenroe/AssemblyZero"

        collect_repo_metrics("martymcenroe/AssemblyZero", "ghp_real_token", period_days=30)
        mock_github_cls.assert_called_once_with("ghp_real_token")

    @patch("assemblyzero.metrics.collector.Github")
    def test_empty_token_no_auth(self, mock_github_cls: MagicMock) -> None:
        """T270 (REQ-9): Empty token calls Github() without token."""
        mock_gh = MagicMock()
        mock_github_cls.return_value = mock_gh
        mock_repo = MagicMock()
        mock_gh.get_repo.return_value = mock_repo
        mock_repo.get_issues.return_value = []
        mock_repo.get_contents.side_effect = UnknownObjectException(404, {"message": "Not Found"}, {})
        mock_repo.full_name = "martymcenroe/PublicRepo"

        collect_repo_metrics("martymcenroe/PublicRepo", "", period_days=30)
        mock_github_cls.assert_called_once_with()
```

### 6.15 `tests/unit/test_metrics_aggregator.py` (Add)

**Complete file contents:**

```python
"""Unit tests for assemblyzero.metrics.aggregator.

Issue #333: Tests for cross-repo aggregation.
"""

from __future__ import annotations

from assemblyzero.metrics.aggregator import aggregate_metrics, compute_approval_rate
from assemblyzero.metrics.models import RepoMetrics


def _make_metrics(
    repo: str,
    created: int = 0,
    closed: int = 0,
    open_: int = 0,
    llds: int = 0,
    reviews: int = 0,
    approvals: int = 0,
    blocks: int = 0,
    workflows: dict[str, int] | None = None,
) -> RepoMetrics:
    """Create test RepoMetrics with specified values."""
    return RepoMetrics(
        repo=repo,
        period_start="2026-01-26T00:00:00+00:00",
        period_end="2026-02-25T00:00:00+00:00",
        issues_created=created,
        issues_closed=closed,
        issues_open=open_,
        workflows_used=workflows or {},
        llds_generated=llds,
        gemini_reviews=reviews,
        gemini_approvals=approvals,
        gemini_blocks=blocks,
        collection_timestamp="2026-02-25T14:30:00+00:00",
    )


class TestAggregateMetrics:
    """Tests for aggregate_metrics()."""

    def test_multi_repo_summation(self) -> None:
        """T120 (REQ-6): Sums totals correctly across 3 repos."""
        repos = [
            _make_metrics("a/x", created=42, closed=35, open_=12, llds=20, reviews=18, approvals=15, blocks=3, workflows={"req": 8, "tdd": 15}),
            _make_metrics("a/y", created=25, closed=20, open_=8, llds=12, reviews=10, approvals=8, blocks=2, workflows={"req": 4, "tdd": 8, "impl": 5}),
            _make_metrics("a/z", created=20, closed=17, open_=5, llds=8, reviews=7, approvals=7, blocks=0, workflows={"req": 3, "tdd": 5, "impl": 5}),
        ]
        result = aggregate_metrics(repos, "2026-01-26T00:00:00+00:00", "2026-02-25T00:00:00+00:00")
        assert result["total_issues_created"] == 87
        assert result["total_issues_closed"] == 72
        assert result["total_issues_open"] == 25
        assert result["total_llds_generated"] == 40
        assert result["total_gemini_reviews"] == 35
        assert result["gemini_approval_rate"] == 0.857
        assert result["workflows_by_type"]["req"] == 15
        assert result["workflows_by_type"]["tdd"] == 28
        assert result["workflows_by_type"]["impl"] == 10
        assert result["repos_tracked"] == 3
        assert len(result["per_repo"]) == 3

    def test_empty_input_zeroed(self) -> None:
        """T130 (REQ-6): Empty input produces zeroed output."""
        result = aggregate_metrics([], "2026-01-26T00:00:00+00:00", "2026-02-25T00:00:00+00:00")
        assert result["repos_tracked"] == 0
        assert result["total_issues_created"] == 0
        assert result["total_issues_closed"] == 0
        assert result["total_issues_open"] == 0
        assert result["total_llds_generated"] == 0
        assert result["total_gemini_reviews"] == 0
        assert result["gemini_approval_rate"] == 0.0
        assert result["workflows_by_type"] == {}
        assert result["per_repo"] == []

    def test_single_repo_identity(self) -> None:
        """T140 (REQ-6): Single repo aggregated equals that repo's values."""
        single = _make_metrics("a/x", created=42, closed=35, open_=12, llds=20, reviews=18, approvals=15, blocks=3)
        result = aggregate_metrics([single], "2026-01-26T00:00:00+00:00", "2026-02-25T00:00:00+00:00")
        assert result["total_issues_created"] == 42
        assert result["total_issues_closed"] == 35
        assert result["total_issues_open"] == 12
        assert result["total_llds_generated"] == 20
        assert result["total_gemini_reviews"] == 18
        assert result["repos_tracked"] == 1


class TestComputeApprovalRate:
    """Tests for compute_approval_rate()."""

    def test_zero_reviews_returns_zero(self) -> None:
        """T150 (REQ-6): Returns 0.0 when total is 0."""
        assert compute_approval_rate(0, 0) == 0.0

    def test_normal_rate(self) -> None:
        """T150 (REQ-6): Normal computation."""
        assert compute_approval_rate(30, 35) == 0.857

    def test_perfect_rate(self) -> None:
        """T150 (REQ-6): All approvals."""
        assert compute_approval_rate(10, 10) == 1.0

    def test_zero_approvals(self) -> None:
        """T150 (REQ-6): Zero approvals with some reviews."""
        assert compute_approval_rate(0, 5) == 0.0
```

### 6.16 `tests/unit/test_metrics_formatters.py` (Add)

**Complete file contents:**

```python
"""Unit tests for assemblyzero.metrics.formatters.

Issue #333: Tests for JSON and markdown output formatting.
"""

from __future__ import annotations

import json
from pathlib import Path

from assemblyzero.metrics.formatters import (
    format_json_snapshot,
    format_markdown_table,
    write_snapshot,
)
from assemblyzero.metrics.models import AggregatedMetrics, RepoMetrics


def _make_aggregated() -> AggregatedMetrics:
    """Create test AggregatedMetrics."""
    return AggregatedMetrics(
        repos_tracked=2,
        repos_reachable=2,
        period_start="2026-01-26T00:00:00+00:00",
        period_end="2026-02-25T00:00:00+00:00",
        total_issues_created=67,
        total_issues_closed=55,
        total_issues_open=20,
        total_llds_generated=32,
        total_gemini_reviews=28,
        gemini_approval_rate=0.857,
        workflows_by_type={"requirements": 12, "tdd": 23},
        per_repo=[
            RepoMetrics(
                repo="martymcenroe/AssemblyZero",
                period_start="2026-01-26T00:00:00+00:00",
                period_end="2026-02-25T00:00:00+00:00",
                issues_created=42,
                issues_closed=35,
                issues_open=12,
                workflows_used={"requirements": 8, "tdd": 15},
                llds_generated=20,
                gemini_reviews=18,
                gemini_approvals=15,
                gemini_blocks=3,
                collection_timestamp="2026-02-25T14:30:00+00:00",
            ),
            RepoMetrics(
                repo="martymcenroe/ProjectAlpha",
                period_start="2026-01-26T00:00:00+00:00",
                period_end="2026-02-25T00:00:00+00:00",
                issues_created=25,
                issues_closed=20,
                issues_open=8,
                workflows_used={"requirements": 4, "tdd": 8},
                llds_generated=12,
                gemini_reviews=10,
                gemini_approvals=8,
                gemini_blocks=2,
                collection_timestamp="2026-02-25T14:30:15+00:00",
            ),
        ],
        generated_at="2026-02-25T14:31:00+00:00",
    )


class TestFormatJsonSnapshot:
    """Tests for format_json_snapshot()."""

    def test_produces_valid_json(self) -> None:
        """T210 (REQ-7): Produces valid JSON with expected keys."""
        metrics = _make_aggregated()
        result = format_json_snapshot(metrics)
        parsed = json.loads(result)
        assert "repos_tracked" in parsed
        assert "total_issues_created" in parsed
        assert "gemini_approval_rate" in parsed
        assert "per_repo" in parsed
        assert parsed["repos_tracked"] == 2
        assert parsed["total_issues_created"] == 67


class TestFormatMarkdownTable:
    """Tests for format_markdown_table()."""

    def test_contains_table_headers(self) -> None:
        """T220 (REQ-7): Markdown output contains table with '| Repo |' header."""
        metrics = _make_aggregated()
        result = format_markdown_table(metrics)
        assert "# Cross-Project Metrics Report" in result
        assert "| Metric | Value |" in result
        assert "| Repo |" in result
        assert "martymcenroe/AssemblyZero" in result
        assert "martymcenroe/ProjectAlpha" in result
        assert "85.7%" in result  # Approval rate

    def test_summary_section_present(self) -> None:
        """T220 (REQ-7): Summary section contains all key metrics."""
        metrics = _make_aggregated()
        result = format_markdown_table(metrics)
        assert "Total Issues Created | 67" in result
        assert "Total Issues Closed | 55" in result
        assert "Total Gemini Reviews | 28" in result


class TestWriteSnapshot:
    """Tests for write_snapshot()."""

    def test_writes_file_with_correct_name(self, tmp_path: Path) -> None:
        """T230 (REQ-7): Creates file at cross-project-{date}.json."""
        metrics = _make_aggregated()
        result_path = write_snapshot(metrics, tmp_path)
        assert result_path.exists()
        assert result_path.name.startswith("cross-project-")
        assert result_path.name.endswith(".json")
        content = json.loads(result_path.read_text())
        assert content["repos_tracked"] == 2
```

### 6.17 `tests/unit/test_metrics_cli.py` (Add)

**Complete file contents:**

```python
"""Unit tests for CLI exit codes.

Issue #333: Tests for tools/collect-cross-project-metrics.py main() function.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import main from the CLI tool
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


from assemblyzero.metrics.collector import CollectionError
from assemblyzero.metrics.models import RepoMetrics


def _make_test_metrics(repo: str) -> RepoMetrics:
    """Create test RepoMetrics."""
    return RepoMetrics(
        repo=repo,
        period_start="2026-01-26T00:00:00+00:00",
        period_end="2026-02-25T00:00:00+00:00",
        issues_created=10,
        issues_closed=8,
        issues_open=2,
        workflows_used={"requirements": 3},
        llds_generated=5,
        gemini_reviews=4,
        gemini_approvals=3,
        gemini_blocks=1,
        collection_timestamp="2026-02-25T14:30:00+00:00",
    )


class TestCLIExitCodes:
    """Tests for CLI exit codes (T280, T290)."""

    @patch("assemblyzero.metrics.cache.load_cached_metrics", return_value=None)
    @patch("assemblyzero.metrics.collector.collect_repo_metrics")
    @patch("assemblyzero.metrics.config.load_config")
    def test_partial_failure_exit_code_1(
        self,
        mock_load_config: MagicMock,
        mock_collect: MagicMock,
        mock_cache: MagicMock,
        tmp_path: Path,
    ) -> None:
        """T280 (REQ-10): Partial failure returns exit code 1."""
        # Import here to avoid import-time side effects
        sys.path.insert(0, str(_project_root / "tools"))
        from importlib import import_module
        # Use dynamic import to handle hyphenated filename
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "collect_cross_project_metrics",
            _project_root / "tools" / "collect-cross-project-metrics.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        mock_load_config.return_value = {
            "repos": ["test/a", "test/b", "test/c"],
            "cache_ttl_minutes": 60,
            "github_token_env": "GITHUB_TOKEN",
        }
        mock_collect.side_effect = [
            _make_test_metrics("test/a"),
            _make_test_metrics("test/b"),
            CollectionError("unreachable"),
        ]

        with patch.dict("os.environ", {"GITHUB_TOKEN": "fake_token"}):
            exit_code = mod.main([
                "--no-cache",
                "--output-dir", str(tmp_path),
                "--format", "json",
            ])
        assert exit_code == 1

    @patch("assemblyzero.metrics.cache.load_cached_metrics", return_value=None)
    @patch("assemblyzero.metrics.collector.collect_repo_metrics")
    @patch("assemblyzero.metrics.config.load_config")
    def test_complete_failure_exit_code_2(
        self,
        mock_load_config: MagicMock,
        mock_collect: MagicMock,
        mock_cache: MagicMock,
        tmp_path: Path,
    ) -> None:
        """T290 (REQ-10): Complete failure returns exit code 2."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "collect_cross_project_metrics",
            _project_root / "tools" / "collect-cross-project-metrics.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        mock_load_config.return_value = {
            "repos": ["test/a", "test/b", "test/c"],
            "cache_ttl_minutes": 60,
            "github_token_env": "GITHUB_TOKEN",
        }
        mock_collect.side_effect = CollectionError("all unreachable")

        with patch.dict("os.environ", {"GITHUB_TOKEN": "fake_token"}):
            exit_code = mod.main([
                "--no-cache",
                "--output-dir", str(tmp_path),
                "--format", "json",
            ])
        assert exit_code == 2
```


## 7. Pattern References

### 7.1 CLI Tool Pattern

**File:** `tools/run_audit.py` (lines 1-60)

```python
#!/usr/bin/env python3
"""Run the audit workflow for a given issue."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Project root on sys.path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
```

**Relevance:** The `tools/collect-cross-project-metrics.py` CLI follows this exact pattern: shebang, docstring, `__future__` annotations import, argparse, sys.path manipulation, and project imports. The new tool mirrors this structure identically.

### 7.2 CLI Entry Point Pattern

**File:** `tools/run_implement_from_lld.py` (lines 1-60)

**Relevance:** Confirms the convention of placing CLI entry points in `tools/` with `if __name__ == "__main__": sys.exit(main())` and argparse-based argument parsing. Both patterns use the same project-root sys.path insertion.

### 7.3 Test Pattern

**File:** `tests/unit/test_implementation_spec_workflow.py` (lines 1-80)

**Relevance:** Existing unit test pattern showing class-based test organization with descriptive docstrings, fixture directories resolved via `Path(__file__).resolve().parent.parent / "fixtures"`, and `from __future__ import annotations`. All new test files follow this exact organization pattern.

### 7.4 Import Path Resolution

**File:** `tests/unit/test_metrics_aggregator.py` (if pre-existing stubs exist)

```python
# Analysis found potential imports from:
from assemblyzero.utils.metrics_aggregator import ...
from assemblyzero.utils.metrics_models import ...
```

**Relevance:** If stubs exist at `assemblyzero/utils/metrics_*`, the new implementation at `assemblyzero/metrics/*` is independent. New test files import from `assemblyzero.metrics.*` exclusively. No backward compatibility shims are needed since the `assemblyzero/utils/` stubs (if any) are not referenced by any production code paths.


## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from __future__ import annotations` | stdlib | All new files |
| `from typing import TypedDict, Any` | stdlib | `models.py` |
| `from pathlib import Path` | stdlib | `config.py`, `cache.py`, `formatters.py`, CLI |
| `from datetime import datetime, timedelta, timezone` | stdlib | `cache.py`, `collector.py`, `aggregator.py`, CLI |
| `import re` | stdlib | `config.py`, `collector.py` |
| `import os` | stdlib | `cache.py`, CLI |
| `import stat` | stdlib | `cache.py` |
| `import logging` | stdlib | `cache.py`, `collector.py`, CLI |
| `import argparse` | stdlib | CLI |
| `import sys` | stdlib | CLI |
| `import json` | stdlib | Test files (fixture loading, assertion parsing) |
| `import base64` | stdlib | `collector.py` (`_get_file_content`) |
| `import time` | stdlib | `test_metrics_cache.py` (expiry test) |
| `import orjson` | `pyproject.toml` (existing: `orjson>=3.11.7,<4.0.0`) | `config.py`, `cache.py`, `formatters.py` |
| `from github import Github, GithubException, UnknownObjectException` | `pyproject.toml` (existing: `pygithub>=2.8.1,<3.0.0`) | `collector.py` |
| `from github.Repository import Repository` | `pyproject.toml` (existing) | `collector.py` |
| `from github.ContentFile import ContentFile` | `pyproject.toml` (existing) | `collector.py` |
| `import pytest` | dev dependency (existing) | All test files |
| `from unittest.mock import MagicMock, patch` | stdlib | `test_metrics_collector.py`, `test_metrics_cli.py` |
| `import importlib.util` | stdlib | `test_metrics_cli.py` (dynamic import of hyphenated filename) |

**New Dependencies:** None. All imports resolve to existing stdlib or `pyproject.toml` dependencies.


## 9. Test Mapping

| Test ID | Tests Function | File | Input | Expected Output |
|---------|---------------|------|-------|-----------------|
| T010 | `load_config()` | `test_metrics_config.py` | `tracked_repos_valid.json` fixture | Config with 3 repos, `cache_ttl_minutes=60` |
| T020 | `load_config()` | `test_metrics_config.py` | Non-existent path | `ConfigError` with path in message |
| T030 | `load_config()` | `test_metrics_config.py` | `tracked_repos_malformed.json` fixture | `ConfigError("Failed to parse...")` |
| T040 | `load_config()` | `test_metrics_config.py` | `tracked_repos_empty.json` fixture | `ConfigError("repos list cannot be empty")` |
| T050 | `get_default_config_path()` | `test_metrics_config.py` | No args | Path ending in `.assemblyzero/tracked_repos.json` |
| T060 | `count_issues_in_period()` | `test_metrics_collector.py` | Mock repo: 4 created, 2 closed, 2 open | `(4, 2, 2)` |
| T070 | `detect_workflows_used()` | `test_metrics_collector.py` | Mock issues with `workflow:requirements` x2, `workflow:tdd` x2 | `{"requirements": 2, "tdd": 2}` |
| T080 | `count_lineage_artifacts()` | `test_metrics_collector.py` | Mock 2 active + 3 done dirs | `5` |
| T090 | `count_gemini_verdicts()` | `test_metrics_collector.py` | Mock 4 verdict files: 3 APPROVE, 1 BLOCK | `(4, 3, 1)` |
| T100 | `collect_repo_metrics()` | `test_metrics_collector.py` | Mock `UnknownObjectException` | `CollectionError` with repo name |
| T110 | `count_lineage_artifacts()` | `test_metrics_collector.py` | Mock 404 on both dirs | `0` |
| T120 | `aggregate_metrics()` | `test_metrics_aggregator.py` | 3 RepoMetrics | Sums: (87, 72, 25, 40, 35), rate=0.857 |
| T130 | `aggregate_metrics()` | `test_metrics_aggregator.py` | Empty list | All zeros, empty per_repo |
| T140 | `aggregate_metrics()` | `test_metrics_aggregator.py` | 1 RepoMetrics | Identity with single repo |
| T150 | `compute_approval_rate()` | `test_metrics_aggregator.py` | `(0, 0)` | `0.0` |
| T160 | `save_cached_metrics()` + `load_cached_metrics()` | `test_metrics_cache.py` | Save then load within TTL | Identical metrics dict |
| T170 | `load_cached_metrics()` | `test_metrics_cache.py` | TTL=0, sleep 0.1s | `None` |
| T180 | `load_cached_metrics()` | `test_metrics_cache.py` | Corrupt JSON file | `None` |
| T190 | `invalidate_cache()` | `test_metrics_cache.py` | 3 cached, invalidate 1 | 2 remain, 1 is None |
| T200 | `invalidate_cache()` | `test_metrics_cache.py` | 3 cached, invalidate all (`None`) | All 3 return None |
| T210 | `format_json_snapshot()` | `test_metrics_formatters.py` | AggregatedMetrics fixture | Valid JSON with all required keys |
| T220 | `format_markdown_table()` | `test_metrics_formatters.py` | AggregatedMetrics fixture | Markdown with `| Repo |` table, repo names, `85.7%` |
| T230 | `write_snapshot()` | `test_metrics_formatters.py` | AggregatedMetrics + tmp_path | File at `cross-project-{date}.json` with valid JSON |
| T240 | `validate_repo_metrics()` + `create_repo_metrics()` | `test_metrics_models.py` | `issues_created=-1` | `ValueError("issues_created must be non-negative, got -1")` |
| T250 | `validate_repo_name()` | `test_metrics_config.py` | `"martymcenroe/AssemblyZero"` valid, `"'; DROP TABLE--"` invalid | `True` / `False` |
| T260 | `collect_repo_metrics()` | `test_metrics_collector.py` | Mock with token `"ghp_real_token"` | `Github("ghp_real_token")` called |
| T270 | `collect_repo_metrics()` | `test_metrics_collector.py` | Empty token `""` | `Github()` called without args |
| T280 | `main()` | `test_metrics_cli.py` | 3 repos config, 1 unreachable | Exit code `1` |
| T290 | `main()` | `test_metrics_cli.py` | 3 repos config, all unreachable | Exit code `2` |
| T300 | `count_issues_in_period()` | `test_metrics_collector.py` | 7-day period, 2 issues | Correct filtering: 1 created, 1 closed |
| T310 | `detect_workflows_used()` | `test_metrics_collector.py` | No workflow labels, LLD filenames present | Dict populated via heuristic |


## 10. Implementation Notes

### 10.1 Error Handling Convention

All public functions follow this pattern:
- **Config errors:** Raise `ConfigError` (from `config.py`) — always includes the problematic path or field name
- **Collection errors:** Raise `CollectionError` (from `collector.py`) — always includes the repo name
- **Validation errors:** Raise `ValueError` (from `models.py`) — includes field name and invalid value
- **Cache errors:** Never raise — return `None` for misses/errors; log warnings via `logger.warning()`

The CLI (`main()`) catches `ConfigError` and `CollectionError` and translates them into exit codes and log messages. It never lets exceptions propagate to the caller.

### 10.2 Logging Convention

Use Python's `logging` module with `logger = logging.getLogger(__name__)` in library modules:
- All log output goes to `stderr` (via `StreamHandler(sys.stderr)` configured in CLI's `_setup_logging()`)
- Format: `[metrics] {message}` (set via `logging.Formatter("[metrics] %(message)s")`)
- Levels: `INFO` for progress, `WARNING` for non-fatal failures, `DEBUG` for cache hits/misses
- `--verbose` CLI flag sets level to `DEBUG`

This allows piping JSON output from stdout to `jq` while seeing logs on stderr.

### 10.3 Constants

| Constant | Value | Location | Rationale |
|----------|-------|----------|-----------|
| `_DEFAULT_CACHE_TTL_MINUTES` | `60` | `config.py` | 1 hour cache prevents redundant API calls |
| `_DEFAULT_GITHUB_TOKEN_ENV` | `"GITHUB_TOKEN"` | `config.py` | Standard env var name for GitHub tokens |
| `REPO_NAME_PATTERN` | `r"^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$"` | `config.py` | Security: prevent injection via repo names |
| `_WORKFLOW_LABEL_PREFIX` | `"workflow:"` | `collector.py` | Convention for AssemblyZero workflow labels |
| `_APPROVE_PATTERN` | `r"(?:Verdict\|Status):\s*APPROVE"` | `collector.py` | Matches Gemini verdict format (compiled `re.Pattern`) |
| `_BLOCK_PATTERN` | `r"(?:Verdict\|Status):\s*BLOCK"` | `collector.py` | Matches Gemini verdict format (compiled `re.Pattern`) |
| `_NON_NEGATIVE_INT_FIELDS` | `["issues_created", "issues_closed", ...]` | `models.py` | Fields validated as non-negative integers |

### 10.4 File Permissions

When writing `~/.assemblyzero/metrics_cache.json`, set permissions to `0o600` (owner read/write only) via `os.chmod(cache_path, stat.S_IRUSR | stat.S_IWUSR)`. The call is wrapped in `try/except OSError` for Windows compatibility where `chmod` may not work as expected. A warning is logged on failure.

### 10.5 orjson Usage Notes

`orjson.dumps()` returns `bytes`, not `str`. All usages that need a string must call `.decode("utf-8")` on the result. `orjson.loads()` accepts both `bytes` and `str`. The `orjson.OPT_INDENT_2` option produces human-readable output. `orjson.OPT_SORT_KEYS` is used in `format_json_snapshot()` for deterministic output.

### 10.6 TypedDict Construction

Since `TypedDict` classes are used, instances are created using the constructor syntax `TypedDict(key=value, ...)` or dict literal `{...}`. Both approaches are used throughout — constructor in aggregator/formatters for clarity, dict literal in collector for conciseness via `create_repo_metrics()`.


---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3) — N/A, all files are "Add"
- [x] Every data structure has a concrete JSON/YAML example (Section 4) — TrackedReposConfig, RepoMetrics, AggregatedMetrics, CacheEntry, CacheFile all have examples
- [x] Every function has input/output examples with realistic values (Section 5) — All 21 function specs include concrete I/O
- [x] Change instructions are diff-level specific (Section 6) — Complete file contents for all Add files
- [x] Pattern references include file:line and are verified to exist (Section 7) — 4 patterns referenced
- [x] All imports are listed and verified (Section 8) — 20 imports mapped
- [x] Test mapping covers all LLD test scenarios (Section 9) — All 31 tests (T010-T310) mapped

---


## Review Log

| Field | Value |
|-------|-------|
| Issue | #333 |
| Verdict | DRAFT |
| Date | 2026-02-25 |
| Iterations | 2 |
| Finalized | — |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #333 |
| Verdict | APPROVED |
| Date | 2026-02-26 |
| Iterations | 1 |
| Finalized | 2026-02-26T04:56:43Z |

### Review Feedback Summary

Approved with suggestions:
*   **Minor Optimization:** In `assemblyzero/metrics/collector.py`, the `_detect_workflows_from_lld_filenames` function iterates over `contents`. If `contents` is large, this is fine, but ensure `repo.get_contents` doesn't hit a recursive limit if directories are deep (though the spec uses specific paths `active`/`done`, so this is safe).
*   **CLI Usage:** The setup of `sys.path` in the CLI tool is robust and follows the project pattern correctly.


## Required File Paths (from LLD - do not deviate)

The following paths are specified in the LLD. Write ONLY to these paths:


Any files written to other paths will be rejected.

## Repository Structure

The actual directory layout of this repository:

```
tests/
  accessibility/
  benchmark/
  compliance/
  contract/
  e2e/
  fixtures/
    lld_tracking/
    metrics/
    mock_lineage/
    mock_repo/
      src/
    scout/
    scraper/
    verdict_analyzer/
  harness/
  integration/
  security/
  tools/
  unit/
    test_gate/
    test_metrics/
  visual/
  __init__.py
  conftest.py
  test_assemblyzero_config.py
  test_audit.py
  test_audit_sharding.py
  test_credentials.py
  test_designer.py
  test_gemini_client.py
  test_gemini_credentials_v2.py
  test_integration_workflow.py
  ... and 14 more files
assemblyzero/
  core/
    validation/
  graphs/
  hooks/
  metrics/
  nodes/
  telemetry/
  utils/
  workflow/
  workflows/
    implementation_spec/
      nodes/
    issue/
      nodes/
    orchestrator/
    parallel/
    requirements/
      nodes/
      parsers/
    scout/
    testing/
      completeness/
      knowledge/
      nodes/
      templates/
  __init__.py
  tracing.py
dashboard/
  src/
    client/
      components/
      pages/
  package.json
  tsconfig.client.json
  tsconfig.json
  tsconfig.worker.json
  wrangler.toml
data/
  unleashed/
  handoff-log.md
```

Use these real paths — do NOT invent paths that don't exist.

## Tests That Must Pass

```python
# From C:\Users\mcwiz\Projects\AssemblyZero\tests\test_issue_333.py
"""Test file for Issue #333.

Generated by AssemblyZero TDD Testing Workflow.
Tests will fail with ImportError until implementation exists (TDD RED phase).
"""

import pytest

# TDD: This import fails until implementation exists (RED phase)
# Once implemented, tests can run (GREEN phase)
from assemblyzero.metrics.models import *  # noqa: F401, F403


# Fixtures for mocking
@pytest.fixture
def mock_external_service():
    """Mock external service for isolation."""
    # TODO: Implement mock
    yield None


# Unit Tests
# -----------

def test_id():
    """
    Tests Function | File | Input | Expected Output
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_id works correctly
    assert False, 'TDD RED: test_id not implemented'


def test_t010():
    """
    `load_config()` | `test_metrics_config.py` |
    `tracked_repos_valid.json` fixture | Config with 3 repos,
    `cache_ttl_minutes=60`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t010 works correctly
    assert False, 'TDD RED: test_t010 not implemented'


def test_t020():
    """
    `load_config()` | `test_metrics_config.py` | Non-existent path |
    `ConfigError` with path in message
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t020 works correctly
    assert False, 'TDD RED: test_t020 not implemented'


def test_t030():
    """
    `load_config()` | `test_metrics_config.py` |
    `tracked_repos_malformed.json` fixture | `ConfigError("Failed to
    parse...")`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t030 works correctly
    assert False, 'TDD RED: test_t030 not implemented'


def test_t040():
    """
    `load_config()` | `test_metrics_config.py` |
    `tracked_repos_empty.json` fixture | `ConfigError("repos list cannot
    be empty")`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t040 works correctly
    assert False, 'TDD RED: test_t040 not implemented'


def test_t050():
    """
    `get_default_config_path()` | `test_metrics_config.py` | No args |
    Path ending in `.assemblyzero/tracked_repos.json`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t050 works correctly
    assert False, 'TDD RED: test_t050 not implemented'


def test_t060(mock_external_service):
    """
    `count_issues_in_period()` | `test_metrics_collector.py` | Mock repo:
    4 created, 2 closed, 2 open | `(4, 2, 2)`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t060 works correctly
    assert False, 'TDD RED: test_t060 not implemented'


def test_t070(mock_external_service):
    """
    `detect_workflows_used()` | `test_metrics_collector.py` | Mock issues
    with `workflow:requirements` x2, `workflow:tdd` x2 | `{"requirements":
    2, "tdd": 2}`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t070 works correctly
    assert False, 'TDD RED: test_t070 not implemented'


def test_t080(mock_external_service):
    """
    `count_lineage_artifacts()` | `test_metrics_collector.py` | Mock 2
    active + 3 done dirs | `5`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t080 works correctly
    assert False, 'TDD RED: test_t080 not implemented'


def test_t090(mock_external_service):
    """
    `count_gemini_verdicts()` | `test_metrics_collector.py` | Mock 4
    verdict files: 3 APPROVE, 1 BLOCK | `(4, 3, 1)`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t090 works correctly
    assert False, 'TDD RED: test_t090 not implemented'


def test_t100(mock_external_service):
    """
    `collect_repo_metrics()` | `test_metrics_collector.py` | Mock
    `UnknownObjectException` | `CollectionError` with repo name
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t100 works correctly
    assert False, 'TDD RED: test_t100 not implemented'


def test_t110(mock_external_service):
    """
    `count_lineage_artifacts()` | `test_metrics_collector.py` | Mock 404
    on both dirs | `0`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t110 works correctly
    assert False, 'TDD RED: test_t110 not implemented'


def test_t120():
    """
    `aggregate_metrics()` | `test_metrics_aggregator.py` | 3 RepoMetrics
    | Sums: (87, 72, 25, 40, 35), rate=0.857
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t120 works correctly
    assert False, 'TDD RED: test_t120 not implemented'


def test_t130():
    """
    `aggregate_metrics()` | `test_metrics_aggregator.py` | Empty list |
    All zeros, empty per_repo
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t130 works correctly
    assert False, 'TDD RED: test_t130 not implemented'


def test_t140():
    """
    `aggregate_metrics()` | `test_metrics_aggregator.py` | 1 RepoMetrics
    | Identity with single repo
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t140 works correctly
    assert False, 'TDD RED: test_t140 not implemented'


def test_t150():
    """
    `compute_approval_rate()` | `test_metrics_aggregator.py` | `(0, 0)` |
    `0.0`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t150 works correctly
    assert False, 'TDD RED: test_t150 not implemented'


def test_t160():
    """
    `save_cached_metrics()` + `load_cached_metrics()` |
    `test_metrics_cache.py` | Save then load within TTL | Identical
    metrics dict
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t160 works correctly
    assert False, 'TDD RED: test_t160 not implemented'


def test_t170():
    """
    `load_cached_metrics()` | `test_metrics_cache.py` | TTL=0, sleep 0.1s
    | `None`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t170 works correctly
    assert False, 'TDD RED: test_t170 not implemented'


def test_t180():
    """
    `load_cached_metrics()` | `test_metrics_cache.py` | Corrupt JSON file
    | `None`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t180 works correctly
    assert False, 'TDD RED: test_t180 not implemented'


def test_t190():
    """
    `invalidate_cache()` | `test_metrics_cache.py` | 3 cached, invalidate
    1 | 2 remain, 1 is None
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t190 works correctly
    assert False, 'TDD RED: test_t190 not implemented'


def test_t200():
    """
    `invalidate_cache()` | `test_metrics_cache.py` | 3 cached, invalidate
    all (`None`) | All 3 return None
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t200 works correctly
    assert False, 'TDD RED: test_t200 not implemented'


def test_t210():
    """
    `format_json_snapshot()` | `test_metrics_formatters.py` |
    AggregatedMetrics fixture | Valid JSON with all required keys
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t210 works correctly
    assert False, 'TDD RED: test_t210 not implemented'


def test_t220():
    """
    `format_markdown_table()` | `test_metrics_formatters.py` |
    AggregatedMetrics fixture | Markdown with ` | Repo | ` table, repo
    names, `85.7%`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t220 works correctly
    assert False, 'TDD RED: test_t220 not implemented'


def test_t230():
    """
    `write_snapshot()` | `test_metrics_formatters.py` | AggregatedMetrics
    + tmp_path | File at `cross-project-{date}.json` with valid JSON
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t230 works correctly
    assert False, 'TDD RED: test_t230 not implemented'


def test_t240():
    """
    `validate_repo_metrics()` + `create_repo_metrics()` |
    `test_metrics_models.py` | `issues_created=-1` |
    `ValueError("issues_created must be non-negative, got -1")`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t240 works correctly
    assert False, 'TDD RED: test_t240 not implemented'


def test_t250():
    """
    `validate_repo_name()` | `test_metrics_config.py` |
    `"martymcenroe/AssemblyZero"` valid, `"'; DROP TABLE--"` invalid |
    `True` / `False`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t250 works correctly
    assert False, 'TDD RED: test_t250 not implemented'


def test_t260(mock_external_service):
    """
    `collect_repo_metrics()` | `test_metrics_collector.py` | Mock with
    token `"ghp_real_token"` | `Github("ghp_real_token")` called
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t260 works correctly
    assert False, 'TDD RED: test_t260 not implemented'


def test_t270():
    """
    `collect_repo_metrics()` | `test_metrics_collector.py` | Empty token
    `""` | `Github()` called without args
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t270 works correctly
    assert False, 'TDD RED: test_t270 not implemented'


def test_t280():
    """
    `main()` | `test_metrics_cli.py` | 3 repos config, 1 unreachable |
    Exit code `1`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t280 works correctly
    assert False, 'TDD RED: test_t280 not implemented'


def test_t290():
    """
    `main()` | `test_metrics_cli.py` | 3 repos config, all unreachable |
    Exit code `2`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t290 works correctly
    assert False, 'TDD RED: test_t290 not implemented'


def test_t300():
    """
    `count_issues_in_period()` | `test_metrics_collector.py` | Correct
    filtering: 1 created, 1 closed
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t300 works correctly
    assert False, 'TDD RED: test_t300 not implemented'


def test_t310():
    """
    `detect_workflows_used()` | `test_metrics_collector.py` | No workflow
    labels, LLD filenames present | Dict populated via heuristic
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t310 works correctly
    assert False, 'TDD RED: test_t310 not implemented'




```

## Previously Implemented Files

These files have already been implemented. Use them for imports and references:

### assemblyzero/metrics/__init__.py (signatures)

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
```

### assemblyzero/metrics/models.py (signatures)

```python
"""Data models for cross-project metrics.

Issue #333: Typed data structures for repo metrics, aggregated metrics, and config.
"""

from __future__ import annotations

from typing import Any, TypedDict

class TrackedReposConfig(TypedDict):

    """Configuration for tracked repositories."""

class RepoMetrics(TypedDict):

    """Metrics collected for a single repository."""

class AggregatedMetrics(TypedDict):

    """Cross-project aggregated metrics."""

class CacheEntry(TypedDict):

    """A cached metrics entry with expiry."""

def validate_repo_metrics(metrics: dict[str, Any]) -> None:
    """Validate a metrics dict. Raises ValueError on invalid data.

Checks that all integer fields are non-negative and repo is non-empty."""
    ...

def create_repo_metrics(
    *,
    repo: str,
    period_start: str,
    period_end: str,
    issues_created: int,
    issues_closed: int,
    issues_open: int,
    workflows_used: dict[str, int],
    llds_generated: int,
    """Create and validate a RepoMetrics dict.

Raises ValueError if any field is invalid."""
    ...
```

### assemblyzero/metrics/config.py (signatures)

```python
"""Configuration loading and validation for cross-project metrics.

Issue #333: Load tracked repos config from ~/.assemblyzero/tracked_repos.json.
"""

from __future__ import annotations

import re

from pathlib import Path

from typing import Any

import orjson

from assemblyzero.metrics.models import TrackedReposConfig

class ConfigError(Exception):

    """Raised when configuration loading or validation fails."""

def get_default_config_path() -> Path:
    """Return ~/.assemblyzero/tracked_repos.json."""
    ...

def validate_repo_name(name: str) -> bool:
    """Check if a repo name matches the allowed owner/name pattern."""
    ...

def validate_config(config: dict[str, Any]) -> TrackedReposConfig:
    """Validate raw dict against TrackedReposConfig schema.

Raises ConfigError on validation failure."""
    ...

def load_config(config_path: Path | None = None) -> TrackedReposConfig:
    """Load and validate tracked repos config from disk.

Default path: ~/.assemblyzero/tracked_repos.json"""
    ...
```

### assemblyzero/metrics/cache.py (signatures)

```python
"""Disk-based cache layer for cross-project metrics.

Issue #333: Cache API responses to minimize GitHub API calls.
"""

from __future__ import annotations

import logging

import os

import stat

from datetime import datetime, timedelta, timezone

from pathlib import Path

from typing import Any

import orjson

from assemblyzero.metrics.models import CacheEntry, RepoMetrics

def get_cache_path() -> Path:
    """Return ~/.assemblyzero/metrics_cache.json."""
    ...

def _load_cache_file(cache_path: Path) -> dict[str, Any]:
    """Load and parse the cache file. Returns empty dict on any error."""
    ...

def _write_cache_file(cache_path: Path, data: dict[str, Any]) -> None:
    """Write cache data to disk with owner-only permissions."""
    ...

def load_cached_metrics(
    repo: str,
    cache_path: Path | None = None,
) -> RepoMetrics | None:
    """Load cached metrics for a repo if cache entry exists and is not expired.

Returns None if no cache, expired, or cache file corrupt."""
    ...

def save_cached_metrics(
    repo: str,
    metrics: RepoMetrics,
    ttl_minutes: int,
    cache_path: Path | None = None,
) -> None:
    """Save metrics to disk cache with TTL."""
    ...

def invalidate_cache(
    repo: str | None = None,
    cache_path: Path | None = None,
) -> None:
    """Invalidate cache for a specific repo, or all repos if repo is None."""
    ...

logger = logging.getLogger(__name__)
```

### assemblyzero/metrics/collector.py (full)

```python
"""Per-repo metrics collection via GitHub API.

Issue #333: Fetch issue data, lineage counts, and verdict files per repository.
"""

from __future__ import annotations

import base64
import logging
import re
from datetime import datetime, timedelta, timezone

from github import Github, GithubException, UnknownObjectException
from github.ContentFile import ContentFile
from github.Repository import Repository

from assemblyzero.metrics.models import RepoMetrics, create_repo_metrics

logger = logging.getLogger(__name__)

_WORKFLOW_LABEL_PREFIX: str = "workflow:"
_APPROVE_PATTERN: re.Pattern[str] = re.compile(
    r"(?:Verdict|Status):\s*APPROVE", re.IGNORECASE
)
_BLOCK_PATTERN: re.Pattern[str] = re.compile(
    r"(?:Verdict|Status):\s*BLOCK", re.IGNORECASE
)


class CollectionError(Exception):
    """Raised when metrics collection fails for a repository."""


def collect_repo_metrics(
    repo_full_name: str,
    github_token: str,
    period_days: int = 30,
) -> RepoMetrics:
    """Collect all metrics for a single repository.

    Fetches issues, scans for lineage folders and verdict files.
    Uses PyGithub for API access.
    Raises CollectionError if repo is unreachable.
    """
    try:
        if github_token:
            gh = Github(github_token)
        else:
            logger.warning("No GitHub token provided. Only public repos accessible.")
            gh = Github()

        repo = gh.get_repo(repo_full_name)
    except UnknownObjectException as exc:
        msg = f"Failed to access repo '{repo_full_name}': {exc.data.get('message', str(exc))}"
        raise CollectionError(msg) from exc
    except GithubException as exc:
        msg = f"GitHub API error for '{repo_full_name}': {exc.data.get('message', str(exc)) if hasattr(exc, 'data') and exc.data else str(exc)}"
        raise CollectionError(msg) from exc

    now = datetime.now(tz=timezone.utc)
    period_end = now
    period_start = now - timedelta(days=period_days)

    created, closed, open_now = count_issues_in_period(repo, period_start, period_end)
    workflows = detect_workflows_used(repo)
    llds = count_lineage_artifacts(repo)
    total_reviews, approvals, blocks = count_gemini_verdicts(repo)

    return create_repo_metrics(
        repo=repo_full_name,
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
        issues_created=created,
        issues_closed=closed,
        issues_open=open_now,
        workflows_used=workflows,
        llds_generated=llds,
        gemini_reviews=total_reviews,
        gemini_approvals=approvals,
        gemini_blocks=blocks,
        collection_timestamp=now.isoformat(),
    )


def count_issues_in_period(
    repo: Repository,
    period_start: datetime,
    period_end: datetime,
) -> tuple[int, int, int]:
    """Count issues created, closed, and currently open.

    Returns (created_in_period, closed_in_period, currently_open).
    Uses 'since' parameter to minimize API pages fetched.
    """
    created = 0
    closed = 0

    # Get issues created since period_start (all states)
    all_issues = repo.get_issues(state="all", since=period_start)
    for issue in all_issues:
        if issue.pull_request is not None:
            continue  # Skip PRs
        if issue.created_at and period_start <= issue.created_at <= period_end:
            created += 1
        if (
            issue.closed_at
            and period_start <= issue.closed_at <= period_end
        ):
            closed += 1

    # Count currently open issues
    open_issues = repo.get_issues(state="open")
    open_now = sum(1 for i in open_issues if i.pull_request is None)

    return (created, closed, open_now)


def detect_workflows_used(repo: Repository) -> dict[str, int]:
    """Detect workflow types by scanning issue labels and LLD filenames.

    Scans labels: 'workflow:requirements', 'workflow:tdd', etc.
    Falls back to heuristic: LLD filenames.
    """
    workflow_counts: dict[str, int] = {}

    # Primary: scan issue labels
    issues = repo.get_issues(state="all")
    for issue in issues:
        if issue.pull_request is not None:
            continue
        for label in issue.labels:
            label_name = label.name if hasattr(label, "name") else str(label)
            if label_name.startswith(_WORKFLOW_LABEL_PREFIX):
                workflow_type = label_name[len(_WORKFLOW_LABEL_PREFIX):]
                workflow_counts[workflow_type] = workflow_counts.get(workflow_type, 0) + 1

    # Fallback: heuristic from LLD filenames if no labels found
    if not workflow_counts:
        workflow_counts = _detect_workflows_from_lld_filenames(repo)

    return workflow_counts


def _detect_workflows_from_lld_filenames(repo: Repository) -> dict[str, int]:
    """Heuristic fallback: detect workflows from LLD filenames."""
    workflow_counts: dict[str, int] = {}
    keyword_map = {
        "requirements": "requirements",
        "tdd": "tdd",
        "implementation": "implementation",
        "design": "requirements",
    }

    for dir_path in ("docs/lld/active", "docs/lld/done"):
        try:
            contents = repo.get_contents(dir_path)
            if not isinstance(contents, list):
                contents = [contents]
            for item in contents:
                name_lower = item.name.lower()
                for keyword, workflow_type in keyword_map.items():
                    if keyword in name_lower:
                        workflow_counts[workflow_type] = (
                            workflow_counts.get(workflow_type, 0) + 1
                        )
                        break  # One workflow type per file
        except (UnknownObjectException, GithubException):
            continue

    return workflow_counts


def count_lineage_artifacts(repo: Repository) -> int:
    """Count LLD folders in docs/lld/active/ and docs/lld/done/ directories.

    Returns 0 if directories don't exist.
    """
    count = 0
    for dir_path in ("docs/lld/active", "docs/lld/done"):
        try:
            contents = repo.get_contents(dir_path)
            if isinstance(contents, list):
                count += len(contents)
            else:
                count += 1
        except (UnknownObjectException, GithubException):
            logger.debug("Directory %s not found in %s", dir_path, repo.full_name)
            continue
    return count


def _get_file_content(content_file: ContentFile) -> str:
    """Decode file content from a GitHub ContentFile."""
    if content_file.content is not None:
        return base64.b64decode(content_file.content).decode("utf-8", errors="replace")
    return ""


def count_gemini_verdicts(repo: Repository) -> tuple[int, int, int]:
    """Count Gemini verdict files and their outcomes.

    Scans docs/reports/*/gemini-*.md files.
    Returns (total_reviews, approvals, blocks).
    """
    total = 0
    approvals = 0
    blocks = 0

    try:
        reports_contents = repo.get_contents("docs/reports")
        if not isinstance(reports_contents, list):
            reports_contents = [reports_contents]
    except (UnknownObjectException, GithubException):
        logger.debug("docs/reports/ not found in %s", repo.full_name)
        return (0, 0, 0)

    for item in reports_contents:
        if item.type != "dir":
            continue
        try:
            dir_contents = repo.get_contents(item.path)
            if not isinstance(dir_contents, list):
                dir_contents = [dir_contents]
            for file_item in dir_contents:
                if not file_item.name.startswith("gemini-") or not file_item.name.endswith(".md"):
                    continue
                total += 1
                try:
                    content = _get_file_content(file_item)
                    if _APPROVE_PATTERN.search(content):
                        approvals += 1
                    elif _BLOCK_PATTERN.search(content):
                        blocks += 1
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Could not read verdict file %s: %s", file_item.path, exc
                    )
        except (UnknownObjectException, GithubException):
            continue

    return (total, approvals, blocks)
```

## Output Format

Output ONLY the file contents. No explanations, no markdown headers, just the Python code.

```python
# Your Python code here
```

IMPORTANT:
- Output the COMPLETE file contents
- Do NOT output a summary or description
- Do NOT say "I've implemented..."
- Just output the Python code in a single fenced code block
