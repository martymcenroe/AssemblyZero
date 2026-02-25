# Implementation Request: tests/fixtures/metrics/tracked_repos.json

## Task

Write the complete contents of `tests/fixtures/metrics/tracked_repos.json`.

Change type: Add
Description: Sample config fixture with 3 repos

## LLD Specification

# Implementation Spec: Cross-Project Metrics Aggregation for AssemblyZero Usage Tracking

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #333 |
| LLD | `docs/lld/active/333-cross-project-metrics-aggregation.md` |
| Generated | 2026-02-24 |
| Status | DRAFT |

## 1. Overview

Build a cross-project metrics aggregation system that collects issue velocity, workflow usage, and Gemini review outcomes across all repositories using AssemblyZero governance workflows, outputting unified metrics dashboards as JSON files.

**Objective:** Produce a single CLI-driven pipeline that reads a config of tracked repos, queries GitHub API for each, aggregates per-repo and cross-project metrics, and writes dated JSON output with a human-readable summary.

**Success Criteria:** All 34 test scenarios (T010–T340) pass with ≥95% coverage; `python tools/collect_cross_project_metrics.py --config ./tracked_repos.json` produces valid JSON output and stdout summary; partial repo failures degrade gracefully.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `docs/metrics/.gitkeep` | Add | Empty placeholder to ensure output directory is tracked |
| 2 | `tests/fixtures/metrics/tracked_repos.json` | Add | Sample config fixture with 3 repos |
| 3 | `tests/fixtures/metrics/mock_issues_assemblyzero.json` | Add | 15 mock GitHub issues for AssemblyZero repo |
| 4 | `tests/fixtures/metrics/mock_issues_rca_pdf.json` | Add | 8 mock GitHub issues for RCA-PDF repo |
| 5 | `tests/fixtures/metrics/expected_aggregated_output.json` | Add | Snapshot of expected CrossProjectMetrics |
| 6 | `assemblyzero/utils/metrics_models.py` | Add | TypedDict data structures for all metrics entities |
| 7 | `assemblyzero/utils/metrics_config.py` | Add | Configuration loader and validator |
| 8 | `assemblyzero/utils/github_metrics_client.py` | Add | GitHub API client with caching and retry |
| 9 | `assemblyzero/utils/metrics_aggregator.py` | Add | Aggregation engine combining per-repo data |
| 10 | `tools/collect_cross_project_metrics.py` | Add | Main CLI entry point |
| 11 | `tests/unit/test_metrics_config.py` | Add | Unit tests for config loading/validation |
| 12 | `tests/unit/test_github_metrics_client.py` | Add | Unit tests for GitHub client with mocks |
| 13 | `tests/unit/test_metrics_aggregator.py` | Add | Unit tests for aggregation logic |
| 14 | `tests/unit/test_collect_cross_project_metrics.py` | Add | Unit tests for CLI orchestration |
| 15 | `tests/integration/test_github_metrics_integration.py` | Add | Integration tests hitting real GitHub API |

**Implementation Order Rationale:** Directories and fixtures first (no dependencies). Then data models (depended on by everything). Then config (depended on by client and aggregator). Then client (depended on by aggregator). Then aggregator (depended on by CLI). Then CLI. Then tests (which import all modules). Integration tests last.

## 3. Current State (for Modify/Delete files)

No files are being modified or deleted. All files in this spec are new additions. This section is intentionally empty per the LLD's note that there are no "Modify" or "Delete" operations.

## 4. Data Structures

### 4.1 TrackedRepoConfig

**Definition:**

```python
class TrackedRepoConfig(TypedDict):
    owner: str
    name: str
    full_name: str
    enabled: bool
```

**Concrete Example:**

```json
{
    "owner": "martymcenroe",
    "name": "AssemblyZero",
    "full_name": "martymcenroe/AssemblyZero",
    "enabled": true
}
```

### 4.2 MetricsCollectionConfig

**Definition:**

```python
class MetricsCollectionConfig(TypedDict):
    repos: list[TrackedRepoConfig]
    lookback_days: int
    output_dir: str
    cache_ttl_seconds: int
    github_token_env: str
```

**Concrete Example:**

```json
{
    "repos": [
        {
            "owner": "martymcenroe",
            "name": "AssemblyZero",
            "full_name": "martymcenroe/AssemblyZero",
            "enabled": true
        },
        {
            "owner": "martymcenroe",
            "name": "RCA-PDF",
            "full_name": "martymcenroe/RCA-PDF",
            "enabled": true
        },
        {
            "owner": "martymcenroe",
            "name": "archived-project",
            "full_name": "martymcenroe/archived-project",
            "enabled": false
        }
    ],
    "lookback_days": 30,
    "output_dir": "docs/metrics",
    "cache_ttl_seconds": 300,
    "github_token_env": "GITHUB_TOKEN"
}
```

### 4.3 RepoIssueMetrics

**Definition:**

```python
class RepoIssueMetrics(TypedDict):
    repo: str
    period_start: str
    period_end: str
    issues_opened: int
    issues_closed: int
    issues_open_current: int
    avg_close_time_hours: Optional[float]
    issues_by_label: dict[str, int]
```

**Concrete Example:**

```json
{
    "repo": "martymcenroe/AssemblyZero",
    "period_start": "2026-01-25",
    "period_end": "2026-02-24",
    "issues_opened": 45,
    "issues_closed": 38,
    "issues_open_current": 12,
    "avg_close_time_hours": 14.7,
    "issues_by_label": {
        "bug": 8,
        "feature": 15,
        "requirements": 10,
        "implementation": 12,
        "tdd": 6,
        "lld": 9
    }
}
```

### 4.4 RepoWorkflowMetrics

**Definition:**

```python
class RepoWorkflowMetrics(TypedDict):
    repo: str
    lld_count: int
    requirements_workflows: int
    implementation_workflows: int
    tdd_workflows: int
    report_count: int
```

**Concrete Example:**

```json
{
    "repo": "martymcenroe/AssemblyZero",
    "lld_count": 23,
    "requirements_workflows": 10,
    "implementation_workflows": 12,
    "tdd_workflows": 6,
    "report_count": 15
}
```

### 4.5 RepoGeminiMetrics

**Definition:**

```python
class RepoGeminiMetrics(TypedDict):
    repo: str
    total_reviews: int
    approvals: int
    blocks: int
    approval_rate: Optional[float]
```

**Concrete Example:**

```json
{
    "repo": "martymcenroe/AssemblyZero",
    "total_reviews": 18,
    "approvals": 15,
    "blocks": 3,
    "approval_rate": 0.833
}
```

### 4.6 PerRepoMetrics

**Definition:**

```python
class PerRepoMetrics(TypedDict):
    repo: str
    issues: RepoIssueMetrics
    workflows: RepoWorkflowMetrics
    gemini: RepoGeminiMetrics
```

**Concrete Example:**

```json
{
    "repo": "martymcenroe/AssemblyZero",
    "issues": {
        "repo": "martymcenroe/AssemblyZero",
        "period_start": "2026-01-25",
        "period_end": "2026-02-24",
        "issues_opened": 45,
        "issues_closed": 38,
        "issues_open_current": 12,
        "avg_close_time_hours": 14.7,
        "issues_by_label": {"bug": 8, "feature": 15, "requirements": 10}
    },
    "workflows": {
        "repo": "martymcenroe/AssemblyZero",
        "lld_count": 23,
        "requirements_workflows": 10,
        "implementation_workflows": 12,
        "tdd_workflows": 6,
        "report_count": 15
    },
    "gemini": {
        "repo": "martymcenroe/AssemblyZero",
        "total_reviews": 18,
        "approvals": 15,
        "blocks": 3,
        "approval_rate": 0.833
    }
}
```

### 4.7 AggregateTotals

**Definition:**

```python
class AggregateTotals(TypedDict):
    issues_opened: int
    issues_closed: int
    issues_open_current: int
    avg_close_time_hours: Optional[float]
    lld_count: int
    total_workflows: int
    gemini_reviews: int
    gemini_approval_rate: Optional[float]
    report_count: int
```

**Concrete Example:**

```json
{
    "issues_opened": 53,
    "issues_closed": 44,
    "issues_open_current": 17,
    "avg_close_time_hours": 16.2,
    "lld_count": 28,
    "total_workflows": 41,
    "gemini_reviews": 22,
    "gemini_approval_rate": 0.818,
    "report_count": 19
}
```

### 4.8 CrossProjectMetrics

**Definition:**

```python
class CrossProjectMetrics(TypedDict):
    generated_at: str
    period_start: str
    period_end: str
    repos_tracked: int
    repos_collected: int
    repos_failed: list[str]
    totals: AggregateTotals
    per_repo: list[PerRepoMetrics]
```

**Concrete Example:**

```json
{
    "generated_at": "2026-02-24T15:30:00Z",
    "period_start": "2026-01-25",
    "period_end": "2026-02-24",
    "repos_tracked": 2,
    "repos_collected": 2,
    "repos_failed": [],
    "totals": {
        "issues_opened": 53,
        "issues_closed": 44,
        "issues_open_current": 17,
        "avg_close_time_hours": 16.2,
        "lld_count": 28,
        "total_workflows": 41,
        "gemini_reviews": 22,
        "gemini_approval_rate": 0.818,
        "report_count": 19
    },
    "per_repo": [
        {
            "repo": "martymcenroe/AssemblyZero",
            "issues": {"repo": "martymcenroe/AssemblyZero", "period_start": "2026-01-25", "period_end": "2026-02-24", "issues_opened": 45, "issues_closed": 38, "issues_open_current": 12, "avg_close_time_hours": 14.7, "issues_by_label": {"bug": 8}},
            "workflows": {"repo": "martymcenroe/AssemblyZero", "lld_count": 23, "requirements_workflows": 10, "implementation_workflows": 12, "tdd_workflows": 6, "report_count": 15},
            "gemini": {"repo": "martymcenroe/AssemblyZero", "total_reviews": 18, "approvals": 15, "blocks": 3, "approval_rate": 0.833}
        }
    ]
}
```

## 5. Function Specifications

### 5.1 `load_config()`

**File:** `assemblyzero/utils/metrics_config.py`

**Signature:**

```python
def load_config(config_path: str | None = None) -> MetricsCollectionConfig:
    """Load and validate tracked repos configuration from file."""
    ...
```

**Input Example:**

```python
config_path = "tests/fixtures/metrics/tracked_repos.json"
```

**Output Example:**

```python
{
    "repos": [
        {"owner": "martymcenroe", "name": "AssemblyZero", "full_name": "martymcenroe/AssemblyZero", "enabled": True},
        {"owner": "martymcenroe", "name": "RCA-PDF", "full_name": "martymcenroe/RCA-PDF", "enabled": True},
        {"owner": "martymcenroe", "name": "archived-project", "full_name": "martymcenroe/archived-project", "enabled": False},
    ],
    "lookback_days": 30,
    "output_dir": "docs/metrics",
    "cache_ttl_seconds": 300,
    "github_token_env": "GITHUB_TOKEN",
}
```

**Edge Cases:**
- `config_path=None` and no env var set and no default files exist → raises `FileNotFoundError("No config file found. Searched: ...")`
- Config file is empty or not valid JSON → raises `ValueError("Config file is malformed: ...")`
- Config missing optional keys → defaults applied: `lookback_days=30`, `output_dir="docs/metrics"`, `cache_ttl_seconds=300`, `github_token_env="GITHUB_TOKEN"`

### 5.2 `validate_config()`

**File:** `assemblyzero/utils/metrics_config.py`

**Signature:**

```python
def validate_config(config: dict) -> MetricsCollectionConfig:
    """Validate raw config dict against expected schema."""
    ...
```

**Input Example:**

```python
config = {
    "repos": ["martymcenroe/AssemblyZero", "martymcenroe/RCA-PDF"],
    "lookback_days": 30,
}
```

**Output Example:**

```python
{
    "repos": [
        {"owner": "martymcenroe", "name": "AssemblyZero", "full_name": "martymcenroe/AssemblyZero", "enabled": True},
        {"owner": "martymcenroe", "name": "RCA-PDF", "full_name": "martymcenroe/RCA-PDF", "enabled": True},
    ],
    "lookback_days": 30,
    "output_dir": "docs/metrics",
    "cache_ttl_seconds": 300,
    "github_token_env": "GITHUB_TOKEN",
}
```

**Edge Cases:**
- `config = {"repos": []}` → raises `ValueError("'repos' must be a non-empty list")`
- `config = {}` → raises `ValueError("'repos' key is required")`
- `config = {"repos": ["invalid"]}` → raises `ValueError("Invalid repo format: 'invalid'. Expected 'owner/name'.")`
- `config = {"repos": ["a/b"], "lookback_days": -1}` → raises `ValueError("'lookback_days' must be a positive integer")`
- Repos can be strings (`"owner/name"`) or dicts (`{"owner": "x", "name": "y", ...}`); strings are auto-converted via `parse_repo_string`

### 5.3 `parse_repo_string()`

**File:** `assemblyzero/utils/metrics_config.py`

**Signature:**

```python
def parse_repo_string(repo_str: str) -> TrackedRepoConfig:
    """Parse 'owner/name' string into TrackedRepoConfig."""
    ...
```

**Input Example:**

```python
repo_str = "martymcenroe/AssemblyZero"
```

**Output Example:**

```python
{"owner": "martymcenroe", "name": "AssemblyZero", "full_name": "martymcenroe/AssemblyZero", "enabled": True}
```

**Edge Cases:**
- `repo_str = "invalid"` → raises `ValueError("Invalid repo format: 'invalid'. Expected 'owner/name'.")`
- `repo_str = ""` → raises `ValueError("Invalid repo format: ''. Expected 'owner/name'.")`
- `repo_str = "a/b/c"` → raises `ValueError("Invalid repo format: 'a/b/c'. Expected 'owner/name'.")`
- `repo_str = "valid-owner/valid.repo-name_123"` → succeeds (alphanumeric, dots, hyphens, underscores allowed)

### 5.4 `GitHubMetricsClient.__init__()`

**File:** `assemblyzero/utils/github_metrics_client.py`

**Signature:**

```python
def __init__(self, token: str | None = None, cache_ttl: int = 300) -> None:
    """Initialize client with optional token and cache TTL."""
    ...
```

**Input Example:**

```python
client = GitHubMetricsClient(token="ghp_abc123def456", cache_ttl=300)
# or
client = GitHubMetricsClient()  # reads from GITHUB_TOKEN / GH_TOKEN env vars
```

**Internal State After Init:**

```python
self._github = Github(login_or_token="ghp_abc123def456")  # or Github() if no token
self._cache: dict[str, tuple[float, Any]] = {}  # key -> (timestamp, data)
self._cache_ttl = 300
self._token = "ghp_abc123def456"  # or None
```

**Edge Cases:**
- No token provided and env vars not set → `self._token = None`, `self._github = Github()` (unauthenticated, 60 req/hour)
- Token provided → authenticated mode (5000 req/hour)

### 5.5 `GitHubMetricsClient._resolve_token()`

**File:** `assemblyzero/utils/github_metrics_client.py`

**Signature:**

```python
def _resolve_token(self, token: str | None) -> str | None:
    """Resolve GitHub token from argument or environment variables."""
    ...
```

**Input Example:**

```python
# With explicit token:
self._resolve_token("ghp_explicit123") → "ghp_explicit123"

# With GITHUB_TOKEN env var set:
# os.environ["GITHUB_TOKEN"] = "ghp_env456"
self._resolve_token(None) → "ghp_env456"

# With GH_TOKEN fallback:
# os.environ["GH_TOKEN"] = "ghp_fallback789"
self._resolve_token(None) → "ghp_fallback789"

# No token anywhere:
self._resolve_token(None) → None
```

**Edge Cases:**
- Explicit token always wins, even if env vars are set
- GITHUB_TOKEN takes priority over GH_TOKEN
- Returns None (not raises) when no token found — caller decides if that's an error

### 5.6 `GitHubMetricsClient.fetch_issues()`

**File:** `assemblyzero/utils/github_metrics_client.py`

**Signature:**

```python
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=30))
def fetch_issues(
    self,
    repo_full_name: str,
    since: str,
    state: str = "all",
) -> list[dict]:
    """Fetch issues from a repository within a date range."""
    ...
```

**Input Example:**

```python
repo_full_name = "martymcenroe/AssemblyZero"
since = "2026-01-25T00:00:00Z"
state = "all"
```

**Output Example:**

```python
[
    {
        "number": 333,
        "title": "Feature: Cross-Project Metrics Aggregation",
        "state": "open",
        "created_at": "2026-02-17T10:00:00Z",
        "closed_at": None,
        "labels": ["feature", "implementation"],
        "is_pull_request": False,
    },
    {
        "number": 320,
        "title": "Bug: Fix workflow state persistence",
        "state": "closed",
        "created_at": "2026-02-10T08:30:00Z",
        "closed_at": "2026-02-12T14:15:00Z",
        "labels": ["bug", "tdd"],
        "is_pull_request": False,
    },
]
```

**Edge Cases:**
- Repo doesn't exist or is private without auth → `github.UnknownObjectException` raised (caught by caller)
- Rate limited (HTTP 429) → tenacity retries up to 3 times with exponential backoff
- Response includes PRs → filtered out by `_filter_issues_only()`

### 5.7 `GitHubMetricsClient.fetch_repo_contents()`

**File:** `assemblyzero/utils/github_metrics_client.py`

**Signature:**

```python
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=30))
def fetch_repo_contents(
    self,
    repo_full_name: str,
    path: str,
) -> list[dict]:
    """Fetch directory contents from a repository."""
    ...
```

**Input Example:**

```python
repo_full_name = "martymcenroe/AssemblyZero"
path = "docs/lld/active"
```

**Output Example:**

```python
[
    {"name": "333-cross-project-metrics.md", "type": "file", "path": "docs/lld/active/333-cross-project-metrics.md", "size": 15234},
    {"name": "304-implementation-readiness.md", "type": "file", "path": "docs/lld/active/304-implementation-readiness.md", "size": 8921},
]
```

**Edge Cases:**
- Path doesn't exist (404) → returns empty list `[]` (does NOT raise)
- Path is a file not a directory → returns single-element list with file info
- Rate limited → tenacity retries

### 5.8 `GitHubMetricsClient.get_rate_limit_remaining()`

**File:** `assemblyzero/utils/github_metrics_client.py`

**Signature:**

```python
def get_rate_limit_remaining(self) -> dict:
    """Get current GitHub API rate limit status."""
    ...
```

**Input Example:** (no args beyond self)

**Output Example:**

```python
{"remaining": 4823, "limit": 5000, "reset_at": "2026-02-24T16:30:00Z"}
```

**Edge Cases:**
- Unauthenticated → `{"remaining": 55, "limit": 60, "reset_at": "..."}`
- API error → returns `{"remaining": 0, "limit": 0, "reset_at": "unknown"}`

### 5.9 `GitHubMetricsClient._get_cache_key()`

**File:** `assemblyzero/utils/github_metrics_client.py`

**Signature:**

```python
def _get_cache_key(self, repo_full_name: str, endpoint: str, params: dict) -> str:
    """Generate a deterministic cache key for a given request."""
    ...
```

**Input Example:**

```python
repo_full_name = "martymcenroe/AssemblyZero"
endpoint = "issues"
params = {"since": "2026-01-25T00:00:00Z", "state": "all"}
```

**Output Example:**

```python
"martymcenroe/AssemblyZero:issues:since=2026-01-25T00:00:00Z&state=all"
```

**Edge Cases:**
- Empty params → `"martymcenroe/AssemblyZero:issues:"`
- Params with different ordering → sorted by key to ensure determinism

### 5.10 `GitHubMetricsClient._is_cache_valid()`

**File:** `assemblyzero/utils/github_metrics_client.py`

**Signature:**

```python
def _is_cache_valid(self, cache_key: str) -> bool:
    """Check whether a cached entry exists and has not expired."""
    ...
```

**Input Example:**

```python
cache_key = "martymcenroe/AssemblyZero:issues:since=2026-01-25T00:00:00Z&state=all"
# self._cache[cache_key] = (1740412200.0, [...data...])  # timestamp + data
# current time = 1740412400.0 (200 seconds later, within 300s TTL)
```

**Output Example:**

```python
True  # 200s < 300s TTL
```

**Edge Cases:**
- Key not in cache → `False`
- Key expired (current_time - stored_time > TTL) → `False`

### 5.11 `GitHubMetricsClient._filter_issues_only()`

**File:** `assemblyzero/utils/github_metrics_client.py`

**Signature:**

```python
def _filter_issues_only(self, items: list[dict]) -> list[dict]:
    """Filter out pull requests from issue list."""
    ...
```

**Input Example:**

```python
items = [
    {"number": 333, "title": "Feature X", "pull_request": None},  # Issue (PR key is None)
    {"number": 334, "title": "PR: Fix Y", "pull_request": {"url": "https://..."}},  # PR
    {"number": 335, "title": "Bug Z"},  # Issue (no PR key)
]
```

**Output Example:**

```python
[
    {"number": 333, "title": "Feature X", "pull_request": None},
    {"number": 335, "title": "Bug Z"},
]
```

**Edge Cases:**
- GitHub's REST API includes a `pull_request` key on PRs — filter items where `pull_request` key exists AND its value is not `None`
- Empty input → empty output

### 5.12 `MetricsAggregator.__init__()`

**File:** `assemblyzero/utils/metrics_aggregator.py`

**Signature:**

```python
def __init__(self, client: GitHubMetricsClient, config: MetricsCollectionConfig) -> None:
    """Initialize aggregator with API client and config."""
    ...
```

**Input Example:**

```python
client = GitHubMetricsClient(token="ghp_abc123")
config = {
    "repos": [...],
    "lookback_days": 30,
    "output_dir": "docs/metrics",
    "cache_ttl_seconds": 300,
    "github_token_env": "GITHUB_TOKEN",
}
aggregator = MetricsAggregator(client=client, config=config)
```

**Internal State After Init:**

```python
self._client = client
self._config = config
```

### 5.13 `MetricsAggregator.collect_repo_metrics()`

**File:** `assemblyzero/utils/metrics_aggregator.py`

**Signature:**

```python
def collect_repo_metrics(self, repo: TrackedRepoConfig) -> PerRepoMetrics:
    """Collect all metrics for a single repository."""
    ...
```

**Input Example:**

```python
repo = {"owner": "martymcenroe", "name": "AssemblyZero", "full_name": "martymcenroe/AssemblyZero", "enabled": True}
```

**Output Example:**

```python
{
    "repo": "martymcenroe/AssemblyZero",
    "issues": {
        "repo": "martymcenroe/AssemblyZero",
        "period_start": "2026-01-25",
        "period_end": "2026-02-24",
        "issues_opened": 45,
        "issues_closed": 38,
        "issues_open_current": 12,
        "avg_close_time_hours": 14.7,
        "issues_by_label": {"bug": 8, "feature": 15}
    },
    "workflows": {
        "repo": "martymcenroe/AssemblyZero",
        "lld_count": 23,
        "requirements_workflows": 10,
        "implementation_workflows": 12,
        "tdd_workflows": 6,
        "report_count": 15
    },
    "gemini": {
        "repo": "martymcenroe/AssemblyZero",
        "total_reviews": 18,
        "approvals": 15,
        "blocks": 3,
        "approval_rate": 0.833
    }
}
```

**Edge Cases:**
- If `collect_issue_metrics()` fails → issues section returns zero/empty defaults, does NOT propagate exception
- If `collect_workflow_metrics()` fails → workflows section returns zero defaults
- If `collect_gemini_metrics()` fails → gemini section returns zero defaults, `None` approval_rate

### 5.14 `MetricsAggregator.collect_issue_metrics()`

**File:** `assemblyzero/utils/metrics_aggregator.py`

**Signature:**

```python
def collect_issue_metrics(
    self, repo_full_name: str, since: str, until: str
) -> RepoIssueMetrics:
    """Collect issue velocity metrics for a repository."""
    ...
```

**Input Example:**

```python
repo_full_name = "martymcenroe/AssemblyZero"
since = "2026-01-25"
until = "2026-02-24"
```

**Output Example:**

```python
{
    "repo": "martymcenroe/AssemblyZero",
    "period_start": "2026-01-25",
    "period_end": "2026-02-24",
    "issues_opened": 45,
    "issues_closed": 38,
    "issues_open_current": 12,
    "avg_close_time_hours": 14.7,
    "issues_by_label": {"bug": 8, "feature": 15, "requirements": 10, "implementation": 12}
}
```

**Edge Cases:**
- Zero issues → `issues_opened=0, issues_closed=0, issues_open_current=0, avg_close_time_hours=None, issues_by_label={}`
- Issues with no `closed_at` → excluded from avg_close_time calculation
- avg_close_time = sum of (closed_at - created_at) for closed issues / number of closed issues, in hours

### 5.15 `MetricsAggregator.collect_workflow_metrics()`

**File:** `assemblyzero/utils/metrics_aggregator.py`

**Signature:**

```python
def collect_workflow_metrics(self, repo_full_name: str) -> RepoWorkflowMetrics:
    """Collect workflow usage metrics by inspecting repo contents."""
    ...
```

**Input Example:**

```python
repo_full_name = "martymcenroe/AssemblyZero"
```

**Output Example:**

```python
{
    "repo": "martymcenroe/AssemblyZero",
    "lld_count": 23,
    "requirements_workflows": 10,
    "implementation_workflows": 12,
    "tdd_workflows": 6,
    "report_count": 15
}
```

**Edge Cases:**
- `docs/lld/active/` doesn't exist → try `docs/lld/` → if neither exists, `lld_count=0`
- `docs/reports/` doesn't exist → `report_count=0`
- Workflow label counts come from the issues already fetched (can reuse cached data)

### 5.16 `MetricsAggregator.collect_gemini_metrics()`

**File:** `assemblyzero/utils/metrics_aggregator.py`

**Signature:**

```python
def collect_gemini_metrics(self, repo_full_name: str) -> RepoGeminiMetrics:
    """Collect Gemini review outcome metrics."""
    ...
```

**Input Example:**

```python
repo_full_name = "martymcenroe/AssemblyZero"
```

**Output Example:**

```python
{
    "repo": "martymcenroe/AssemblyZero",
    "total_reviews": 18,
    "approvals": 15,
    "blocks": 3,
    "approval_rate": 0.833
}
```

**Edge Cases:**
- No verdict files found → `{"total_reviews": 0, "approvals": 0, "blocks": 0, "approval_rate": None}`
- Verdict file with neither APPROVE nor BLOCK → skipped (not counted)
- `approval_rate` computed as `approvals / total_reviews`, rounded to 3 decimal places

### 5.17 `MetricsAggregator.aggregate()`

**File:** `assemblyzero/utils/metrics_aggregator.py`

**Signature:**

```python
def aggregate(self, per_repo_results: list[PerRepoMetrics]) -> CrossProjectMetrics:
    """Aggregate per-repo metrics into cross-project totals."""
    ...
```

**Input Example:**

```python
per_repo_results = [
    {
        "repo": "martymcenroe/AssemblyZero",
        "issues": {"repo": "martymcenroe/AssemblyZero", "period_start": "2026-01-25", "period_end": "2026-02-24", "issues_opened": 45, "issues_closed": 38, "issues_open_current": 12, "avg_close_time_hours": 14.7, "issues_by_label": {}},
        "workflows": {"repo": "martymcenroe/AssemblyZero", "lld_count": 23, "requirements_workflows": 10, "implementation_workflows": 12, "tdd_workflows": 6, "report_count": 15},
        "gemini": {"repo": "martymcenroe/AssemblyZero", "total_reviews": 18, "approvals": 15, "blocks": 3, "approval_rate": 0.833}
    },
    {
        "repo": "martymcenroe/RCA-PDF",
        "issues": {"repo": "martymcenroe/RCA-PDF", "period_start": "2026-01-25", "period_end": "2026-02-24", "issues_opened": 8, "issues_closed": 6, "issues_open_current": 5, "avg_close_time_hours": 20.3, "issues_by_label": {}},
        "workflows": {"repo": "martymcenroe/RCA-PDF", "lld_count": 5, "requirements_workflows": 3, "implementation_workflows": 2, "tdd_workflows": 1, "report_count": 4},
        "gemini": {"repo": "martymcenroe/RCA-PDF", "total_reviews": 4, "approvals": 3, "blocks": 1, "approval_rate": 0.75}
    }
]
```

**Output Example:**

```python
{
    "generated_at": "2026-02-24T15:30:00Z",
    "period_start": "2026-01-25",
    "period_end": "2026-02-24",
    "repos_tracked": 2,
    "repos_collected": 2,
    "repos_failed": [],
    "totals": {
        "issues_opened": 53,
        "issues_closed": 44,
        "issues_open_current": 17,
        "avg_close_time_hours": 16.2,
        "lld_count": 28,
        "total_workflows": 34,
        "gemini_reviews": 22,
        "gemini_approval_rate": 0.818,
        "report_count": 19
    },
    "per_repo": [...]
}
```

**Edge Cases:**
- Empty `per_repo_results` list → totals are all zeros, `avg_close_time_hours=None`, `gemini_approval_rate=None`
- `total_workflows` = sum of (requirements_workflows + implementation_workflows + tdd_workflows) across repos
- Weighted average close time: `sum(avg_hours * closed_count per repo) / sum(closed_count)` — None if no closed issues

### 5.18 `MetricsAggregator._calculate_aggregate_close_time()`

**File:** `assemblyzero/utils/metrics_aggregator.py`

**Signature:**

```python
def _calculate_aggregate_close_time(
    self, per_repo: list[PerRepoMetrics]
) -> float | None:
    """Calculate weighted average close time across repos."""
    ...
```

**Input Example:**

```python
# Repo A: avg_close_time_hours=14.7, issues_closed=38
# Repo B: avg_close_time_hours=20.3, issues_closed=6
# Weighted avg = (14.7*38 + 20.3*6) / (38+6) = (558.6 + 121.8) / 44 = 15.46
```

**Output Example:**

```python
15.46  # rounded to 2 decimal places
```

**Edge Cases:**
- All repos have `avg_close_time_hours=None` → returns `None`
- One repo has None, others have values → skip None repos in weighted calc
- No closed issues anywhere → returns `None`

### 5.19 `main()`

**File:** `tools/collect_cross_project_metrics.py`

**Signature:**

```python
def main(
    config_path: str | None = None,
    output_path: str | None = None,
    lookback_days: int | None = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> int:
    """Main entry point for cross-project metrics collection."""
    ...
```

**Input Example:**

```python
exit_code = main(config_path="tracked_repos.json", lookback_days=7, verbose=True)
```

**Output Example:**

```python
0  # success - all repos collected
1  # partial failure - some repos failed
2  # total failure - all repos failed or config error
```

**Edge Cases:**
- `dry_run=True` → loads config, prints summary, returns 0 without making any API calls
- `config_path` points to nonexistent file → returns 2
- All repos fail → returns 2 and does NOT write output file
- `lookback_days` from CLI overrides config value

### 5.20 `write_metrics_output()`

**File:** `tools/collect_cross_project_metrics.py`

**Signature:**

```python
def write_metrics_output(
    metrics: CrossProjectMetrics,
    output_dir: str,
    output_path: str | None = None,
) -> str:
    """Write aggregated metrics to JSON file."""
    ...
```

**Input Example:**

```python
metrics = {"generated_at": "2026-02-24T15:30:00Z", ...}
output_dir = "docs/metrics"
```

**Output Example:**

```python
"docs/metrics/cross-project-2026-02-24.json"
# Also creates/overwrites: docs/metrics/cross-project-latest.json
```

**Edge Cases:**
- `output_path` explicitly set → writes to that exact path, still creates `latest.json` in same dir
- `output_dir` doesn't exist → raises `OSError("Output directory does not exist: ...")`
- Uses `orjson.dumps()` with `orjson.OPT_INDENT_2` for pretty-printed JSON

### 5.21 `format_summary_table()`

**File:** `tools/collect_cross_project_metrics.py`

**Signature:**

```python
def format_summary_table(metrics: CrossProjectMetrics) -> str:
    """Format metrics as a human-readable summary table for stdout."""
    ...
```

**Input Example:**

```python
metrics = {
    "repos_tracked": 2,
    "repos_collected": 2,
    "repos_failed": [],
    "totals": {"issues_opened": 53, "issues_closed": 44, ...},
    "per_repo": [
        {"repo": "martymcenroe/AssemblyZero", "issues": {"issues_opened": 45, ...}, ...},
        {"repo": "martymcenroe/RCA-PDF", "issues": {"issues_opened": 8, ...}, ...},
    ]
}
```

**Output Example:**

```python
"""
Cross-Project Metrics Summary (2026-01-25 to 2026-02-24)
=========================================================
Repository                     Opened  Closed  Open  Avg Close (h)  LLDs  Reviews  Approval%
martymcenroe/AssemblyZero          45      38    12          14.70    23       18      83.3%
martymcenroe/RCA-PDF                8       6     5          20.30     5        4      75.0%
------------------------------------------------------------------------------------------
TOTALS                             53      44    17          16.20    28       22      81.8%

Repos tracked: 2 | Collected: 2 | Failed: 0
"""
```

**Edge Cases:**
- `repos_failed` non-empty → adds a "Failed repos:" line listing them
- `approval_rate` is None → displayed as "N/A"
- `avg_close_time_hours` is None → displayed as "N/A"

### 5.22 `parse_args()`

**File:** `tools/collect_cross_project_metrics.py`

**Signature:**

```python
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    ...
```

**Input Example:**

```python
argv = ["--config", "my_repos.json", "--output", "/tmp/out.json", "--lookback-days", "7", "--dry-run", "--verbose"]
```

**Output Example:**

```python
Namespace(config_path="my_repos.json", output="/tmp/out.json", lookback_days=7, dry_run=True, verbose=True)
```

**Edge Cases:**
- No args → `Namespace(config_path=None, output=None, lookback_days=None, dry_run=False, verbose=False)`
- `--lookback-days` must be a positive integer → argparse `type=int` handles validation

## 6. Change Instructions

### 6.1 `docs/metrics/.gitkeep` (Add)

**Complete file contents:**

```
```

(Empty file — zero bytes.)

### 6.2 `tests/fixtures/metrics/tracked_repos.json` (Add)

**Complete file contents:**

```json
{
    "repos": [
        "martymcenroe/AssemblyZero",
        "martymcenroe/RCA-PDF",
        {
            "owner": "martymcenroe",
            "name": "archived-project",
            "full_name": "martymcenroe/archived-project",
            "enabled": false
        }
    ],
    "lookback_days": 30,
    "output_dir": "docs/metrics",
    "cache_ttl_seconds": 300,
    "github_token_env": "GITHUB_TOKEN"
}
```

### 6.3 `tests/fixtures/metrics/mock_issues_assemblyzero.json` (Add)

**Complete file contents:**

```json
[
    {
        "number": 333,
        "title": "Feature: Cross-Project Metrics Aggregation",
        "state": "open",
        "created_at": "2026-02-17T10:00:00Z",
        "closed_at": null,
        "labels": ["feature", "implementation"],
        "pull_request": null
    },
    {
        "number": 320,
        "title": "Bug: Fix workflow state persistence",
        "state": "closed",
        "created_at": "2026-02-10T08:30:00Z",
        "closed_at": "2026-02-12T14:15:00Z",
        "labels": ["bug", "tdd"],
        "pull_request": null
    },
    {
        "number": 315,
        "title": "Feature: Add LLD review workflow",
        "state": "closed",
        "created_at": "2026-02-08T09:00:00Z",
        "closed_at": "2026-02-09T16:45:00Z",
        "labels": ["feature", "requirements", "lld"],
        "pull_request": null
    },
    {
        "number": 310,
        "title": "Docs: Update testing strategy",
        "state": "closed",
        "created_at": "2026-02-06T11:00:00Z",
        "closed_at": "2026-02-06T18:30:00Z",
        "labels": ["documentation"],
        "pull_request": null
    },
    {
        "number": 308,
        "title": "Feature: Implementation spec generation",
        "state": "closed",
        "created_at": "2026-02-05T14:00:00Z",
        "closed_at": "2026-02-07T10:00:00Z",
        "labels": ["feature", "implementation"],
        "pull_request": null
    },
    {
        "number": 305,
        "title": "PR: Fix import cycle",
        "state": "closed",
        "created_at": "2026-02-04T16:00:00Z",
        "closed_at": "2026-02-04T17:30:00Z",
        "labels": ["bug"],
        "pull_request": {"url": "https://api.github.com/repos/martymcenroe/AssemblyZero/pulls/305"}
    },
    {
        "number": 304,
        "title": "Feature: Implementation readiness checks",
        "state": "closed",
        "created_at": "2026-02-03T09:00:00Z",
        "closed_at": "2026-02-05T11:00:00Z",
        "labels": ["feature", "requirements"],
        "pull_request": null
    },
    {
        "number": 300,
        "title": "Bug: SQLite checkpoint corruption",
        "state": "open",
        "created_at": "2026-02-02T10:00:00Z",
        "closed_at": null,
        "labels": ["bug"],
        "pull_request": null
    },
    {
        "number": 295,
        "title": "Feature: Gemini model selection",
        "state": "closed",
        "created_at": "2026-01-31T08:00:00Z",
        "closed_at": "2026-02-01T15:00:00Z",
        "labels": ["feature"],
        "pull_request": null
    },
    {
        "number": 290,
        "title": "PR: Add retry logic to API calls",
        "state": "closed",
        "created_at": "2026-01-30T12:00:00Z",
        "closed_at": "2026-01-30T14:00:00Z",
        "labels": ["enhancement"],
        "pull_request": {"url": "https://api.github.com/repos/martymcenroe/AssemblyZero/pulls/290"}
    },
    {
        "number": 285,
        "title": "Feature: TDD workflow support",
        "state": "closed",
        "created_at": "2026-01-29T09:00:00Z",
        "closed_at": "2026-01-30T17:00:00Z",
        "labels": ["feature", "tdd"],
        "pull_request": null
    },
    {
        "number": 280,
        "title": "Feature: Mermaid diagram quality gate",
        "state": "open",
        "created_at": "2026-01-28T11:00:00Z",
        "closed_at": null,
        "labels": ["feature", "implementation"],
        "pull_request": null
    },
    {
        "number": 277,
        "title": "Feature: Mechanical validation",
        "state": "closed",
        "created_at": "2026-01-27T10:00:00Z",
        "closed_at": "2026-01-28T09:00:00Z",
        "labels": ["feature", "requirements"],
        "pull_request": null
    },
    {
        "number": 275,
        "title": "PR: Refactor workflow state types",
        "state": "closed",
        "created_at": "2026-01-27T08:00:00Z",
        "closed_at": "2026-01-27T10:00:00Z",
        "labels": ["refactor"],
        "pull_request": {"url": "https://api.github.com/repos/martymcenroe/AssemblyZero/pulls/275"}
    },
    {
        "number": 270,
        "title": "Bug: Audit report generation failure",
        "state": "open",
        "created_at": "2026-01-26T14:00:00Z",
        "closed_at": null,
        "labels": ["bug"],
        "pull_request": null
    }
]
```

### 6.4 `tests/fixtures/metrics/mock_issues_rca_pdf.json` (Add)

**Complete file contents:**

```json
[
    {
        "number": 45,
        "title": "Feature: PDF table extraction",
        "state": "closed",
        "created_at": "2026-02-15T09:00:00Z",
        "closed_at": "2026-02-17T12:00:00Z",
        "labels": ["feature", "implementation"],
        "pull_request": null
    },
    {
        "number": 42,
        "title": "Bug: OCR accuracy on scanned docs",
        "state": "open",
        "created_at": "2026-02-12T10:00:00Z",
        "closed_at": null,
        "labels": ["bug"],
        "pull_request": null
    },
    {
        "number": 40,
        "title": "Feature: RCA template generation",
        "state": "closed",
        "created_at": "2026-02-10T08:00:00Z",
        "closed_at": "2026-02-11T14:30:00Z",
        "labels": ["feature", "requirements"],
        "pull_request": null
    },
    {
        "number": 38,
        "title": "PR: Update PDF parser dependency",
        "state": "closed",
        "created_at": "2026-02-08T16:00:00Z",
        "closed_at": "2026-02-08T17:00:00Z",
        "labels": ["dependencies"],
        "pull_request": {"url": "https://api.github.com/repos/martymcenroe/RCA-PDF/pulls/38"}
    },
    {
        "number": 35,
        "title": "Feature: Multi-page PDF support",
        "state": "closed",
        "created_at": "2026-02-05T09:00:00Z",
        "closed_at": "2026-02-07T16:00:00Z",
        "labels": ["feature", "tdd"],
        "pull_request": null
    },
    {
        "number": 33,
        "title": "Docs: API documentation update",
        "state": "closed",
        "created_at": "2026-02-03T11:00:00Z",
        "closed_at": "2026-02-03T15:00:00Z",
        "labels": ["documentation"],
        "pull_request": null
    },
    {
        "number": 30,
        "title": "Feature: Batch PDF processing",
        "state": "open",
        "created_at": "2026-01-30T10:00:00Z",
        "closed_at": null,
        "labels": ["feature", "implementation"],
        "pull_request": null
    },
    {
        "number": 28,
        "title": "Bug: Memory leak in large PDFs",
        "state": "closed",
        "created_at": "2026-01-28T14:00:00Z",
        "closed_at": "2026-01-29T10:00:00Z",
        "labels": ["bug"],
        "pull_request": null
    }
]
```

### 6.5 `tests/fixtures/metrics/expected_aggregated_output.json` (Add)

**Complete file contents:**

This fixture represents the expected output when processing the two mock issue fixtures above with `lookback_days=30`, period ending `2026-02-24`. The exact `generated_at` will vary; tests should compare structure and numeric values, not timestamps.

```json
{
    "generated_at": "IGNORED_IN_COMPARISON",
    "period_start": "2026-01-25",
    "period_end": "2026-02-24",
    "repos_tracked": 2,
    "repos_collected": 2,
    "repos_failed": [],
    "totals": {
        "issues_opened": 19,
        "issues_closed": 14,
        "issues_open_current": 5,
        "avg_close_time_hours": null,
        "lld_count": 0,
        "total_workflows": 0,
        "gemini_reviews": 0,
        "gemini_approval_rate": null,
        "report_count": 0
    },
    "per_repo": [
        {
            "repo": "martymcenroe/AssemblyZero",
            "issues": {
                "repo": "martymcenroe/AssemblyZero",
                "period_start": "2026-01-25",
                "period_end": "2026-02-24",
                "issues_opened": 12,
                "issues_closed": 8,
                "issues_open_current": 4,
                "avg_close_time_hours": null,
                "issues_by_label": {}
            },
            "workflows": {
                "repo": "martymcenroe/AssemblyZero",
                "lld_count": 0,
                "requirements_workflows": 0,
                "implementation_workflows": 0,
                "tdd_workflows": 0,
                "report_count": 0
            },
            "gemini": {
                "repo": "martymcenroe/AssemblyZero",
                "total_reviews": 0,
                "approvals": 0,
                "blocks": 0,
                "approval_rate": null
            }
        },
        {
            "repo": "martymcenroe/RCA-PDF",
            "issues": {
                "repo": "martymcenroe/RCA-PDF",
                "period_start": "2026-01-25",
                "period_end": "2026-02-24",
                "issues_opened": 7,
                "issues_closed": 6,
                "issues_open_current": 1,
                "avg_close_time_hours": null,
                "issues_by_label": {}
            },
            "workflows": {
                "repo": "martymcenroe/RCA-PDF",
                "lld_count": 0,
                "requirements_workflows": 0,
                "implementation_workflows": 0,
                "tdd_workflows": 0,
                "report_count": 0
            },
            "gemini": {
                "repo": "martymcenroe/RCA-PDF",
                "total_reviews": 0,
                "approvals": 0,
                "blocks": 0,
                "approval_rate": null
            }
        }
    ]
}
```

**Note:** The `avg_close_time_hours` and label-based fields in this fixture are set to null/0/empty because the expected_aggregated_output is a structural reference. The actual test assertions in `test_metrics_aggregator.py` will provide precise computed values using mock data with known timestamps.

### 6.6 `assemblyzero/utils/metrics_models.py` (Add)

**Complete file contents:**

```python
"""Data models for cross-project metrics aggregation.

Issue #333: Cross-Project Metrics Aggregation for AssemblyZero Usage Tracking.
"""

from __future__ import annotations

from typing import Optional, TypedDict


class TrackedRepoConfig(TypedDict):
    """Configuration for a single tracked repository."""

    owner: str
    name: str
    full_name: str
    enabled: bool


class MetricsCollectionConfig(TypedDict):
    """Top-level configuration for the metrics collector."""

    repos: list[TrackedRepoConfig]
    lookback_days: int
    output_dir: str
    cache_ttl_seconds: int
    github_token_env: str


class RepoIssueMetrics(TypedDict):
    """Issue velocity metrics for a single repository."""

    repo: str
    period_start: str
    period_end: str
    issues_opened: int
    issues_closed: int
    issues_open_current: int
    avg_close_time_hours: Optional[float]
    issues_by_label: dict[str, int]


class RepoWorkflowMetrics(TypedDict):
    """Workflow usage metrics for a single repository."""

    repo: str
    lld_count: int
    requirements_workflows: int
    implementation_workflows: int
    tdd_workflows: int
    report_count: int


class RepoGeminiMetrics(TypedDict):
    """Gemini review outcome metrics for a single repository."""

    repo: str
    total_reviews: int
    approvals: int
    blocks: int
    approval_rate: Optional[float]


class PerRepoMetrics(TypedDict):
    """Combined metrics for a single repository."""

    repo: str
    issues: RepoIssueMetrics
    workflows: RepoWorkflowMetrics
    gemini: RepoGeminiMetrics


class AggregateTotals(TypedDict):
    """Aggregate totals across all repos."""

    issues_opened: int
    issues_closed: int
    issues_open_current: int
    avg_close_time_hours: Optional[float]
    lld_count: int
    total_workflows: int
    gemini_reviews: int
    gemini_approval_rate: Optional[float]
    report_count: int


class CrossProjectMetrics(TypedDict):
    """Aggregated metrics across all tracked repositories."""

    generated_at: str
    period_start: str
    period_end: str
    repos_tracked: int
    repos_collected: int
    repos_failed: list[str]
    totals: AggregateTotals
    per_repo: list[PerRepoMetrics]
```

### 6.7 `assemblyzero/utils/metrics_config.py` (Add)

**Complete file contents:**

```python
"""Configuration loader for cross-project metrics collection.

Issue #333: Cross-Project Metrics Aggregation for AssemblyZero Usage Tracking.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from assemblyzero.utils.metrics_models import (
    MetricsCollectionConfig,
    TrackedRepoConfig,
)

_REPO_PATTERN = re.compile(r"^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$")

_DEFAULT_CONFIG: dict = {
    "lookback_days": 30,
    "output_dir": "docs/metrics",
    "cache_ttl_seconds": 300,
    "github_token_env": "GITHUB_TOKEN",
}

_CONFIG_SEARCH_LOCATIONS = [
    lambda: os.environ.get("ASSEMBLYZERO_METRICS_CONFIG"),
    lambda: str(Path.home() / ".assemblyzero" / "tracked_repos.json"),
    lambda: "tracked_repos.json",
]


def load_config(config_path: str | None = None) -> MetricsCollectionConfig:
    """Load and validate tracked repos configuration.

    Searches in order:
    1. Explicit config_path argument
    2. ASSEMBLYZERO_METRICS_CONFIG environment variable
    3. ~/.assemblyzero/tracked_repos.json
    4. ./tracked_repos.json (project root)

    Raises:
        FileNotFoundError: If no config file found at any location.
        ValueError: If config file is malformed or fails validation.
    """
    resolved_path = _resolve_config_path(config_path)
    if resolved_path is None:
        searched = _get_searched_paths(config_path)
        raise FileNotFoundError(
            f"No config file found. Searched: {', '.join(searched)}"
        )

    try:
        raw_text = Path(resolved_path).read_text(encoding="utf-8")
    except OSError as exc:
        raise FileNotFoundError(
            f"Cannot read config file at '{resolved_path}': {exc}"
        ) from exc

    try:
        raw_config = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Config file is malformed: {exc}") from exc

    if not isinstance(raw_config, dict):
        raise ValueError("Config file must contain a JSON object at the top level")

    return validate_config(raw_config)


def validate_config(config: dict) -> MetricsCollectionConfig:
    """Validate raw config dict against expected schema.

    Checks:
    - 'repos' key exists and is a non-empty list
    - Each repo entry has owner/name or full_name (or is a string)
    - lookback_days is positive integer
    - output_dir is a string

    Raises:
        ValueError: On validation failure with descriptive message.
    """
    if "repos" not in config:
        raise ValueError("'repos' key is required")

    repos_raw = config["repos"]
    if not isinstance(repos_raw, list) or len(repos_raw) == 0:
        raise ValueError("'repos' must be a non-empty list")

    parsed_repos: list[TrackedRepoConfig] = []
    for entry in repos_raw:
        if isinstance(entry, str):
            parsed_repos.append(parse_repo_string(entry))
        elif isinstance(entry, dict):
            # Validate dict-format repo entry
            if "full_name" in entry:
                full_name = entry["full_name"]
                if not _REPO_PATTERN.match(full_name):
                    raise ValueError(
                        f"Invalid repo format: '{full_name}'. Expected 'owner/name'."
                    )
                owner, name = full_name.split("/", 1)
                parsed_repos.append(
                    TrackedRepoConfig(
                        owner=entry.get("owner", owner),
                        name=entry.get("name", name),
                        full_name=full_name,
                        enabled=entry.get("enabled", True),
                    )
                )
            elif "owner" in entry and "name" in entry:
                full_name = f"{entry['owner']}/{entry['name']}"
                parsed_repos.append(
                    TrackedRepoConfig(
                        owner=entry["owner"],
                        name=entry["name"],
                        full_name=full_name,
                        enabled=entry.get("enabled", True),
                    )
                )
            else:
                raise ValueError(
                    f"Repo entry must have 'full_name' or both 'owner' and 'name': {entry}"
                )
        else:
            raise ValueError(
                f"Invalid repo entry type: {type(entry).__name__}. Expected string or dict."
            )

    # Validate lookback_days
    lookback_days = config.get("lookback_days", _DEFAULT_CONFIG["lookback_days"])
    if not isinstance(lookback_days, int) or lookback_days < 1:
        raise ValueError("'lookback_days' must be a positive integer")

    output_dir = config.get("output_dir", _DEFAULT_CONFIG["output_dir"])
    cache_ttl_seconds = config.get(
        "cache_ttl_seconds", _DEFAULT_CONFIG["cache_ttl_seconds"]
    )
    github_token_env = config.get(
        "github_token_env", _DEFAULT_CONFIG["github_token_env"]
    )

    return MetricsCollectionConfig(
        repos=parsed_repos,
        lookback_days=lookback_days,
        output_dir=output_dir,
        cache_ttl_seconds=cache_ttl_seconds,
        github_token_env=github_token_env,
    )


def parse_repo_string(repo_str: str) -> TrackedRepoConfig:
    """Parse 'owner/name' string into TrackedRepoConfig.

    Args:
        repo_str: Repository identifier like 'martymcenroe/AssemblyZero'

    Returns:
        TrackedRepoConfig with owner, name, full_name, enabled=True

    Raises:
        ValueError: If string doesn't match 'owner/name' format.
    """
    if not _REPO_PATTERN.match(repo_str):
        raise ValueError(
            f"Invalid repo format: '{repo_str}'. Expected 'owner/name'."
        )

    owner, name = repo_str.split("/", 1)
    return TrackedRepoConfig(
        owner=owner,
        name=name,
        full_name=repo_str,
        enabled=True,
    )


def _resolve_config_path(config_path: str | None) -> str | None:
    """Resolve the actual config file path from search locations.

    Returns the first path that exists, or None.
    """
    if config_path is not None:
        if Path(config_path).is_file():
            return config_path
        return None

    for location_fn in _CONFIG_SEARCH_LOCATIONS:
        candidate = location_fn()
        if candidate and Path(candidate).is_file():
            return candidate

    return None


def _get_searched_paths(config_path: str | None) -> list[str]:
    """Return the list of paths that were searched for config."""
    paths: list[str] = []
    if config_path is not None:
        paths.append(config_path)
    else:
        for location_fn in _CONFIG_SEARCH_LOCATIONS:
            candidate = location_fn()
            if candidate:
                paths.append(candidate)
    return paths
```

### 6.8 `assemblyzero/utils/github_metrics_client.py` (Add)

**Complete file contents:**

```python
"""GitHub API client wrapper for cross-project metrics collection.

Issue #333: Cross-Project Metrics Aggregation for AssemblyZero Usage Tracking.

Provides caching, retry-with-backoff, and rate-limit awareness for
fetching issues, repo contents, and review verdicts via PyGithub.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

from github import Github, GithubException, UnknownObjectException
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class GitHubMetricsClient:
    """GitHub API client for metrics collection with caching and rate-limit awareness."""

    def __init__(self, token: str | None = None, cache_ttl: int = 300) -> None:
        """Initialize client with optional token and cache TTL.

        Args:
            token: GitHub personal access token. If None, reads from
                   GITHUB_TOKEN or GH_TOKEN environment variables.
            cache_ttl: Cache time-to-live in seconds.
        """
        self._token = self._resolve_token(token)
        self._cache_ttl = cache_ttl
        self._cache: dict[str, tuple[float, Any]] = {}

        if self._token:
            self._github = Github(login_or_token=self._token)
            logger.debug("GitHub client initialized in authenticated mode")
        else:
            self._github = Github()
            logger.debug(
                "GitHub client initialized in unauthenticated mode "
                "(60 requests/hour limit)"
            )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=30))
    def fetch_issues(
        self,
        repo_full_name: str,
        since: str,
        state: str = "all",
    ) -> list[dict]:
        """Fetch issues from a repository within a date range.

        Args:
            repo_full_name: 'owner/name' format
            since: ISO 8601 date string for lookback start
            state: 'open', 'closed', or 'all'

        Returns:
            List of issue dicts with: number, title, state, created_at,
            closed_at, labels, is_pull_request.

        Raises:
            github.GithubException: On API errors after retries exhausted.
        """
        cache_key = self._get_cache_key(
            repo_full_name, "issues", {"since": since, "state": state}
        )
        if self._is_cache_valid(cache_key):
            logger.debug("Cache hit for issues: %s", cache_key)
            return self._cache[cache_key][1]

        since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        if since_dt.tzinfo is None:
            since_dt = since_dt.replace(tzinfo=timezone.utc)

        repo = self._github.get_repo(repo_full_name)
        issues_paged = repo.get_issues(state=state, since=since_dt, sort="created")

        raw_items: list[dict] = []
        for issue in issues_paged:
            raw_items.append(
                {
                    "number": issue.number,
                    "title": issue.title,
                    "state": issue.state,
                    "created_at": (
                        issue.created_at.isoformat() if issue.created_at else None
                    ),
                    "closed_at": (
                        issue.closed_at.isoformat() if issue.closed_at else None
                    ),
                    "labels": [label.name for label in issue.labels],
                    "pull_request": issue.pull_request,
                }
            )

        filtered = self._filter_issues_only(raw_items)

        self._cache[cache_key] = (time.time(), filtered)
        return filtered

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=30))
    def fetch_repo_contents(
        self,
        repo_full_name: str,
        path: str,
    ) -> list[dict]:
        """Fetch directory contents from a repository.

        Args:
            repo_full_name: 'owner/name' format
            path: Repository-relative path (e.g., 'docs/lld/active')

        Returns:
            List of content dicts with: name, type, path, size.
            Returns empty list if path doesn't exist (404).
        """
        cache_key = self._get_cache_key(
            repo_full_name, "contents", {"path": path}
        )
        if self._is_cache_valid(cache_key):
            logger.debug("Cache hit for contents: %s", cache_key)
            return self._cache[cache_key][1]

        try:
            repo = self._github.get_repo(repo_full_name)
            contents = repo.get_contents(path)
        except UnknownObjectException:
            logger.debug("Path not found (404): %s/%s", repo_full_name, path)
            result: list[dict] = []
            self._cache[cache_key] = (time.time(), result)
            return result

        # get_contents returns a single ContentFile or a list
        if not isinstance(contents, list):
            contents = [contents]

        result = [
            {
                "name": item.name,
                "type": item.type,
                "path": item.path,
                "size": item.size,
            }
            for item in contents
        ]

        self._cache[cache_key] = (time.time(), result)
        return result

    def get_rate_limit_remaining(self) -> dict:
        """Get current GitHub API rate limit status.

        Returns:
            Dict with 'remaining', 'limit', 'reset_at' keys.
        """
        try:
            rate_limit = self._github.get_rate_limit()
            core = rate_limit.core
            return {
                "remaining": core.remaining,
                "limit": core.limit,
                "reset_at": core.reset.isoformat() if core.reset else "unknown",
            }
        except GithubException:
            logger.warning("Failed to fetch rate limit status")
            return {"remaining": 0, "limit": 0, "reset_at": "unknown"}

    def _get_cache_key(
        self, repo_full_name: str, endpoint: str, params: dict
    ) -> str:
        """Generate a deterministic cache key for a given request.

        Args:
            repo_full_name: 'owner/name' format
            endpoint: API endpoint identifier (e.g., 'issues', 'contents')
            params: Request parameters dict

        Returns:
            String cache key.
        """
        sorted_params = "&".join(
            f"{k}={v}" for k, v in sorted(params.items())
        )
        return f"{repo_full_name}:{endpoint}:{sorted_params}"

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check whether a cached entry exists and has not expired.

        Args:
            cache_key: Key returned by _get_cache_key.

        Returns:
            True if cache hit is valid (exists and within TTL), False otherwise.
        """
        if cache_key not in self._cache:
            return False

        stored_time, _ = self._cache[cache_key]
        return (time.time() - stored_time) < self._cache_ttl

    def _filter_issues_only(self, items: list[dict]) -> list[dict]:
        """Filter out pull requests from issue list.

        GitHub API returns PRs in the issues endpoint. This filters them out
        by checking for the 'pull_request' key having a truthy value.
        """
        return [
            item
            for item in items
            if not item.get("pull_request")
        ]

    def _resolve_token(self, token: str | None) -> str | None:
        """Resolve GitHub token from argument or environment variables.

        Checks in order:
        1. Explicit token argument
        2. GITHUB_TOKEN environment variable
        3. GH_TOKEN environment variable

        Args:
            token: Explicitly provided token, or None.

        Returns:
            Resolved token string, or None if no token found.
        """
        if token is not None:
            return token

        github_token = os.environ.get("GITHUB_TOKEN")
        if github_token:
            return github_token

        gh_token = os.environ.get("GH_TOKEN")
        if gh_token:
            return gh_token

        return None
```

### 6.9 `assemblyzero/utils/metrics_aggregator.py` (Add)

**Complete file contents:**

```python
"""Aggregation engine for cross-project metrics.

Issue #333: Cross-Project Metrics Aggregation for AssemblyZero Usage Tracking.

Combines per-repo data collected via GitHubMetricsClient into unified
cross-project metrics with aggregate totals.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from assemblyzero.utils.github_metrics_client import GitHubMetricsClient
from assemblyzero.utils.metrics_models import (
    AggregateTotals,
    CrossProjectMetrics,
    MetricsCollectionConfig,
    PerRepoMetrics,
    RepoGeminiMetrics,
    RepoIssueMetrics,
    RepoWorkflowMetrics,
    TrackedRepoConfig,
)

logger = logging.getLogger(__name__)

# Labels that indicate specific workflow types
_REQUIREMENTS_LABELS = {"requirements", "lld"}
_IMPLEMENTATION_LABELS = {"implementation"}
_TDD_LABELS = {"tdd", "testing"}


class MetricsAggregator:
    """Aggregates per-repo metrics into cross-project totals."""

    def __init__(
        self, client: GitHubMetricsClient, config: MetricsCollectionConfig
    ) -> None:
        """Initialize aggregator with API client and config.

        Args:
            client: Configured GitHubMetricsClient instance.
            config: Validated MetricsCollectionConfig.
        """
        self._client = client
        self._config = config

    def collect_repo_metrics(self, repo: TrackedRepoConfig) -> PerRepoMetrics:
        """Collect all metrics for a single repository.

        Orchestrates calls to collect issue, workflow, and Gemini metrics.
        If any sub-collection fails, that section returns zero/empty values
        rather than failing the entire repo collection.

        Args:
            repo: Repository configuration.

        Returns:
            PerRepoMetrics with all collected data.
        """
        repo_full_name = repo["full_name"]
        now = datetime.now(tz=timezone.utc)
        period_end = now.strftime("%Y-%m-%d")
        period_start = (
            now - timedelta(days=self._config["lookback_days"])
        ).strftime("%Y-%m-%d")

        # Collect issue metrics with fault isolation
        try:
            issues = self.collect_issue_metrics(repo_full_name, period_start, period_end)
        except Exception:
            logger.warning(
                "Failed to collect issue metrics for %s", repo_full_name, exc_info=True
            )
            issues = _empty_issue_metrics(repo_full_name, period_start, period_end)

        # Collect workflow metrics with fault isolation
        try:
            workflows = self.collect_workflow_metrics(repo_full_name)
        except Exception:
            logger.warning(
                "Failed to collect workflow metrics for %s",
                repo_full_name,
                exc_info=True,
            )
            workflows = _empty_workflow_metrics(repo_full_name)

        # Collect Gemini metrics with fault isolation
        try:
            gemini = self.collect_gemini_metrics(repo_full_name)
        except Exception:
            logger.warning(
                "Failed to collect Gemini metrics for %s",
                repo_full_name,
                exc_info=True,
            )
            gemini = _empty_gemini_metrics(repo_full_name)

        return PerRepoMetrics(
            repo=repo_full_name,
            issues=issues,
            workflows=workflows,
            gemini=gemini,
        )

    def collect_issue_metrics(
        self, repo_full_name: str, since: str, until: str
    ) -> RepoIssueMetrics:
        """Collect issue velocity metrics for a repository.

        Args:
            repo_full_name: 'owner/name' format
            since: Period start (ISO 8601 date, e.g. '2026-01-25')
            until: Period end (ISO 8601 date, e.g. '2026-02-24')

        Returns:
            RepoIssueMetrics with counts, averages, and label breakdowns.
        """
        since_iso = f"{since}T00:00:00Z"
        issues = self._client.fetch_issues(repo_full_name, since=since_iso, state="all")

        issues_opened = 0
        issues_closed = 0
        issues_open_current = 0
        close_times_hours: list[float] = []
        label_counts: dict[str, int] = {}

        for issue in issues:
            created_at = issue.get("created_at")
            closed_at = issue.get("closed_at")
            state = issue.get("state", "")
            labels = issue.get("labels", [])

            # Count opened (all issues in the period)
            issues_opened += 1

            # Count currently open
            if state == "open":
                issues_open_current += 1

            # Count closed and compute close time
            if state == "closed" and closed_at:
                issues_closed += 1
                if created_at:
                    try:
                        created_dt = datetime.fromisoformat(
                            created_at.replace("Z", "+00:00")
                        )
                        closed_dt = datetime.fromisoformat(
                            closed_at.replace("Z", "+00:00")
                        )
                        delta_hours = (
                            closed_dt - created_dt
                        ).total_seconds() / 3600.0
                        close_times_hours.append(delta_hours)
                    except (ValueError, TypeError):
                        pass

            # Count labels
            for label in labels:
                label_lower = label.lower() if isinstance(label, str) else str(label)
                label_counts[label_lower] = label_counts.get(label_lower, 0) + 1

        avg_close_time: Optional[float] = None
        if close_times_hours:
            avg_close_time = round(
                sum(close_times_hours) / len(close_times_hours), 2
            )

        return RepoIssueMetrics(
            repo=repo_full_name,
            period_start=since,
            period_end=until,
            issues_opened=issues_opened,
            issues_closed=issues_closed,
            issues_open_current=issues_open_current,
            avg_close_time_hours=avg_close_time,
            issues_by_label=label_counts,
        )

    def collect_workflow_metrics(self, repo_full_name: str) -> RepoWorkflowMetrics:
        """Collect workflow usage metrics by inspecting repo contents.

        Checks for:
        - docs/lld/active/ or docs/lld/ (LLD files)
        - docs/reports/ (report directories)
        - Workflow labels on issues (requirements, implementation, tdd)

        Args:
            repo_full_name: 'owner/name' format

        Returns:
            RepoWorkflowMetrics with counts per workflow type.
        """
        # Count LLD files
        lld_contents = self._client.fetch_repo_contents(
            repo_full_name, "docs/lld/active"
        )
        if not lld_contents:
            lld_contents = self._client.fetch_repo_contents(
                repo_full_name, "docs/lld"
            )
        lld_count = sum(
            1
            for item in lld_contents
            if item.get("type") == "file" and item.get("name", "").endswith(".md")
        )

        # Count report directories
        report_contents = self._client.fetch_repo_contents(
            repo_full_name, "docs/reports"
        )
        report_count = sum(
            1 for item in report_contents if item.get("type") == "dir"
        )

        # Count workflow labels from cached issues
        # Use the latest cached issue data if available
        requirements_count = 0
        implementation_count = 0
        tdd_count = 0

        # Fetch issues to count workflow labels (will use cache if available)
        now = datetime.now(tz=timezone.utc)
        since = (
            now - timedelta(days=self._config["lookback_days"])
        ).strftime("%Y-%m-%dT00:00:00Z")

        try:
            issues = self._client.fetch_issues(repo_full_name, since=since, state="all")
            for issue in issues:
                labels = {
                    lbl.lower() if isinstance(lbl, str) else str(lbl)
                    for lbl in issue.get("labels", [])
                }
                if labels & _REQUIREMENTS_LABELS:
                    requirements_count += 1
                if labels & _IMPLEMENTATION_LABELS:
                    implementation_count += 1
                if labels & _TDD_LABELS:
                    tdd_count += 1
        except Exception:
            logger.debug(
                "Could not fetch issues for workflow label counting: %s",
                repo_full_name,
            )

        return RepoWorkflowMetrics(
            repo=repo_full_name,
            lld_count=lld_count,
            requirements_workflows=requirements_count,
            implementation_workflows=implementation_count,
            tdd_workflows=tdd_count,
            report_count=report_count,
        )

    def collect_gemini_metrics(self, repo_full_name: str) -> RepoGeminiMetrics:
        """Collect Gemini review outcome metrics.

        Inspects verdict files in the repository for APPROVE/BLOCK counts.
        Looks in standard locations:
        - docs/reports/ subdirectories for gemini-verdict* files
        - .gemini-reviews/ (if present)

        Args:
            repo_full_name: 'owner/name' format

        Returns:
            RepoGeminiMetrics with review counts and approval rate.
        """
        approvals = 0
        blocks = 0

        # Check docs/reports/ for verdict files
        report_dirs = self._client.fetch_repo_contents(
            repo_full_name, "docs/reports"
        )
        for report_dir in report_dirs:
            if report_dir.get("type") != "dir":
                continue
            dir_path = report_dir.get("path", "")
            dir_contents = self._client.fetch_repo_contents(
                repo_full_name, dir_path
            )
            for item in dir_contents:
                name = item.get("name", "").lower()
                if "gemini-verdict" in name or "gemini_verdict" in name:
                    # Attempt to parse verdict from file name conventions
                    # In AssemblyZero, verdict files typically contain
                    # "APPROVED" or "BLOCKED" in their names or content
                    if "approve" in name or "approved" in name:
                        approvals += 1
                    elif "block" in name or "blocked" in name:
                        blocks += 1
                    else:
                        # Count as a review but verdict unknown from name alone
                        # For content-based parsing, we'd need to fetch file contents
                        # For v1, we count by filename convention
                        approvals += 1  # Default to approval if verdict file exists

        # Check .gemini-reviews/ directory
        gemini_dir_contents = self._client.fetch_repo_contents(
            repo_full_name, ".gemini-reviews"
        )
        for item in gemini_dir_contents:
            name = item.get("name", "").lower()
            if "approve" in name or "approved" in name:
                approvals += 1
            elif "block" in name or "blocked" in name:
                blocks += 1

        total_reviews = approvals + blocks
        approval_rate: Optional[float] = None
        if total_reviews > 0:
            approval_rate = round(approvals / total_reviews, 3)

        return RepoGeminiMetrics(
            repo=repo_full_name,
            total_reviews=total_reviews,
            approvals=approvals,
            blocks=blocks,
            approval_rate=approval_rate,
        )

    def aggregate(
        self,
        per_repo_results: list[PerRepoMetrics],
        repos_failed: list[str] | None = None,
    ) -> CrossProjectMetrics:
        """Aggregate per-repo metrics into cross-project totals.

        Args:
            per_repo_results: List of successfully collected repo metrics.
            repos_failed: List of repo full_names that failed collection.

        Returns:
            CrossProjectMetrics with totals and per-repo breakdown.
        """
        if repos_failed is None:
            repos_failed = []

        now = datetime.now(tz=timezone.utc)
        period_end = now.strftime("%Y-%m-%d")
        period_start = (
            now - timedelta(days=self._config["lookback_days"])
        ).strftime("%Y-%m-%d")

        total_opened = sum(r["issues"]["issues_opened"] for r in per_repo_results)
        total_closed = sum(r["issues"]["issues_closed"] for r in per_repo_results)
        total_open = sum(
            r["issues"]["issues_open_current"] for r in per_repo_results
        )
        total_lld = sum(r["workflows"]["lld_count"] for r in per_repo_results)
        total_workflows = sum(
            r["workflows"]["requirements_workflows"]
            + r["workflows"]["implementation_workflows"]
            + r["workflows"]["tdd_workflows"]
            for r in per_repo_results
        )
        total_gemini = sum(r["gemini"]["total_reviews"] for r in per_repo_results)
        total_approvals = sum(r["gemini"]["approvals"] for r in per_repo_results)
        total_reports = sum(r["workflows"]["report_count"] for r in per_repo_results)

        avg_close_time = self._calculate_aggregate_close_time(per_repo_results)

        gemini_approval_rate: Optional[float] = None
        if total_gemini > 0:
            gemini_approval_rate = round(total_approvals / total_gemini, 3)

        totals = AggregateTotals(
            issues_opened=total_opened,
            issues_closed=total_closed,
            issues_open_current=total_open,
            avg_close_time_hours=avg_close_time,
            lld_count=total_lld,
            total_workflows=total_workflows,
            gemini_reviews=total_gemini,
            gemini_approval_rate=gemini_approval_rate,
            report_count=total_reports,
        )

        repos_tracked = len(per_repo_results) + len(repos_failed)

        return CrossProjectMetrics(
            generated_at=now.isoformat(),
            period_start=period_start,
            period_end=period_end,
            repos_tracked=repos_tracked,
            repos_collected=len(per_repo_results),
            repos_failed=repos_failed,
            totals=totals,
            per_repo=per_repo_results,
        )

    def _calculate_aggregate_close_time(
        self, per_repo: list[PerRepoMetrics]
    ) -> float | None:
        """Calculate weighted average close time across repos.

        Weights by number of closed issues per repo.
        Returns None if no closed issues across all repos.
        """
        total_weighted_hours = 0.0
        total_closed_count = 0

        for repo_metrics in per_repo:
            avg_hours = repo_metrics["issues"]["avg_close_time_hours"]
            closed_count = repo_metrics["issues"]["issues_closed"]
            if avg_hours is not None and closed_count > 0:
                total_weighted_hours += avg_hours * closed_count
                total_closed_count += closed_count

        if total_closed_count == 0:
            return None

        return round(total_weighted_hours / total_closed_count, 2)


def _empty_issue_metrics(
    repo: str, period_start: str, period_end: str
) -> RepoIssueMetrics:
    """Return zeroed-out issue metrics for fault isolation."""
    return RepoIssueMetrics(
        repo=repo,
        period_start=period_start,
        period_end=period_end,
        issues_opened=0,
        issues_closed=0,
        issues_open_current=0,
        avg_close_time_hours=None,
        issues_by_label={},
    )


def _empty_workflow_metrics(repo: str) -> RepoWorkflowMetrics:
    """Return zeroed-out workflow metrics for fault isolation."""
    return RepoWorkflowMetrics(
        repo=repo,
        lld_count=0,
        requirements_workflows=0,
        implementation_workflows=0,
        tdd_workflows=0,
        report_count=0,
    )


def _empty_gemini_metrics(repo: str) -> RepoGeminiMetrics:
    """Return zeroed-out Gemini metrics for fault isolation."""
    return RepoGeminiMetrics(
        repo=repo,
        total_reviews=0,
        approvals=0,
        blocks=0,
        approval_rate=None,
    )
```

### 6.10 `tools/collect_cross_project_metrics.py` (Add)

**Complete file contents:**

```python
#!/usr/bin/env python3
"""Cross-project metrics collection tool.

Issue #333: Cross-Project Metrics Aggregation for AssemblyZero Usage Tracking.

Usage:
    python tools/collect_cross_project_metrics.py --config tracked_repos.json
    python tools/collect_cross_project_metrics.py --config tracked_repos.json --dry-run
    python tools/collect_cross_project_metrics.py --config tracked_repos.json --lookback-days 7 --verbose
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import orjson

from assemblyzero.utils.github_metrics_client import GitHubMetricsClient
from assemblyzero.utils.metrics_aggregator import MetricsAggregator
from assemblyzero.utils.metrics_config import load_config

if TYPE_CHECKING:
    from assemblyzero.utils.metrics_models import CrossProjectMetrics

logger = logging.getLogger(__name__)

_RATE_LIMIT_WARN_THRESHOLD = 100
_ESTIMATED_CALLS_PER_REPO = 10


def main(
    config_path: str | None = None,
    output_path: str | None = None,
    lookback_days: int | None = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> int:
    """Main entry point for cross-project metrics collection.

    Args:
        config_path: Override config file location.
        output_path: Override output file location.
        lookback_days: Override lookback period from config.
        dry_run: If True, print config and exit without collecting.
        verbose: If True, enable detailed logging output.

    Returns:
        Exit code: 0 for success, 1 for partial failure, 2 for total failure.
    """
    # Configure logging
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Load config
    try:
        config = load_config(config_path)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Configuration error: %s", exc)
        return 2

    # Override lookback_days from CLI if provided
    if lookback_days is not None:
        config["lookback_days"] = lookback_days

    # Filter to enabled repos only
    enabled_repos = [r for r in config["repos"] if r.get("enabled", True)]

    if not enabled_repos:
        logger.error("No enabled repos in configuration")
        return 2

    # Dry-run mode
    if dry_run:
        print("=== Dry Run Mode ===")
        print(f"Config loaded with {len(enabled_repos)} enabled repos:")
        for repo in enabled_repos:
            print(f"  - {repo['full_name']}")
        print(f"Lookback days: {config['lookback_days']}")
        print(f"Output dir: {config['output_dir']}")
        print(f"Cache TTL: {config['cache_ttl_seconds']}s")
        return 0

    # Initialize client
    client = GitHubMetricsClient(cache_ttl=config["cache_ttl_seconds"])

    # Pre-flight rate limit check
    rate_info = client.get_rate_limit_remaining()
    remaining = rate_info.get("remaining", 0)
    estimated_calls = len(enabled_repos) * _ESTIMATED_CALLS_PER_REPO
    logger.info(
        "Rate limit: %d/%d remaining (estimated need: %d)",
        remaining,
        rate_info.get("limit", 0),
        estimated_calls,
    )
    if remaining < _RATE_LIMIT_WARN_THRESHOLD:
        logger.warning(
            "Low rate limit budget: %d remaining. "
            "Collection may be rate-limited.",
            remaining,
        )

    # Collect metrics per repo
    aggregator = MetricsAggregator(client=client, config=config)
    per_repo_results = []
    repos_failed: list[str] = []

    for repo in enabled_repos:
        repo_name = repo["full_name"]
        logger.info("Collecting metrics for %s...", repo_name)
        try:
            metrics = aggregator.collect_repo_metrics(repo)
            per_repo_results.append(metrics)
            logger.info("  ✓ %s collected successfully", repo_name)
        except Exception:
            logger.warning(
                "  ✗ Failed to collect %s", repo_name, exc_info=verbose
            )
            repos_failed.append(repo_name)

    # Check for total failure
    if not per_repo_results:
        logger.error(
            "All repos failed collection. Failed: %s",
            ", ".join(repos_failed),
        )
        return 2

    # Aggregate
    cross_project = aggregator.aggregate(per_repo_results, repos_failed=repos_failed)

    # Write output
    try:
        written_path = write_metrics_output(
            cross_project, config["output_dir"], output_path
        )
        logger.info("Metrics written to: %s", written_path)
    except OSError as exc:
        logger.error("Failed to write output: %s", exc)
        return 2

    # Print summary
    summary = format_summary_table(cross_project)
    print(summary)

    # Return exit code
    if repos_failed:
        return 1
    return 0


def write_metrics_output(
    metrics: CrossProjectMetrics,
    output_dir: str,
    output_path: str | None = None,
) -> str:
    """Write aggregated metrics to JSON file.

    Default filename: cross-project-{YYYY-MM-DD}.json
    Also writes/overwrites cross-project-latest.json as a copy.

    Args:
        metrics: Aggregated cross-project metrics.
        output_dir: Base directory for output.
        output_path: Explicit full path override.

    Returns:
        Path to the written file.

    Raises:
        OSError: If output directory is not writable.
    """
    out_dir = Path(output_dir)
    if not out_dir.is_dir():
        raise OSError(f"Output directory does not exist: {output_dir}")

    if output_path:
        dated_path = Path(output_path)
    else:
        date_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        dated_path = out_dir / f"cross-project-{date_str}.json"

    # Serialize with orjson for speed and pretty printing
    json_bytes = orjson.dumps(metrics, option=orjson.OPT_INDENT_2)
    dated_path.write_bytes(json_bytes)

    # Create/overwrite latest.json
    latest_path = dated_path.parent / "cross-project-latest.json"
    shutil.copy2(str(dated_path), str(latest_path))

    return str(dated_path)


def format_summary_table(metrics: CrossProjectMetrics) -> str:
    """Format metrics as a human-readable summary table for stdout.

    Args:
        metrics: Aggregated cross-project metrics.

    Returns:
        Formatted multi-line string with aligned columns.
    """
    lines: list[str] = []
    period = f"{metrics['period_start']} to {metrics['period_end']}"
    lines.append(f"\nCross-Project Metrics Summary ({period})")
    lines.append("=" * 90)

    # Header
    header = (
        f"{'Repository':<35} {'Opened':>7} {'Closed':>7} {'Open':>5} "
        f"{'Avg Close (h)':>14} {'LLDs':>5} {'Reviews':>8} {'Approval%':>10}"
    )
    lines.append(header)

    # Per-repo rows
    for repo_data in metrics["per_repo"]:
        repo_name = repo_data["repo"]
        issues = repo_data["issues"]
        workflows = repo_data["workflows"]
        gemini = repo_data["gemini"]

        avg_close = (
            f"{issues['avg_close_time_hours']:.2f}"
            if issues["avg_close_time_hours"] is not None
            else "N/A"
        )
        approval = (
            f"{gemini['approval_rate'] * 100:.1f}%"
            if gemini["approval_rate"] is not None
            else "N/A"
        )

        row = (
            f"{repo_name:<35} {issues['issues_opened']:>7} "
            f"{issues['issues_closed']:>7} {issues['issues_open_current']:>5} "
            f"{avg_close:>14} {workflows['lld_count']:>5} "
            f"{gemini['total_reviews']:>8} {approval:>10}"
        )
        lines.append(row)

    # Separator
    lines.append("-" * 90)

    # Totals row
    totals = metrics["totals"]
    avg_close_total = (
        f"{totals['avg_close_time_hours']:.2f}"
        if totals["avg_close_time_hours"] is not None
        else "N/A"
    )
    approval_total = (
        f"{totals['gemini_approval_rate'] * 100:.1f}%"
        if totals["gemini_approval_rate"] is not None
        else "N/A"
    )
    totals_row = (
        f"{'TOTALS':<35} {totals['issues_opened']:>7} "
        f"{totals['issues_closed']:>7} {totals['issues_open_current']:>5} "
        f"{avg_close_total:>14} {totals['lld_count']:>5} "
        f"{totals['gemini_reviews']:>8} {approval_total:>10}"
    )
    lines.append(totals_row)

    # Footer
    lines.append("")
    tracked = metrics["repos_tracked"]
    collected = metrics["repos_collected"]
    failed = len(metrics["repos_failed"])
    lines.append(
        f"Repos tracked: {tracked} | Collected: {collected} | Failed: {failed}"
    )

    if metrics["repos_failed"]:
        lines.append(f"Failed repos: {', '.join(metrics['repos_failed'])}")

    lines.append("")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Supports: --config, --output, --lookback-days, --dry-run, --verbose

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        Parsed namespace with config_path, output, lookback_days, dry_run, verbose.
    """
    parser = argparse.ArgumentParser(
        description="Collect cross-project metrics for AssemblyZero repositories.",
        prog="collect_cross_project_metrics",
    )
    parser.add_argument(
        "--config",
        dest="config_path",
        type=str,
        default=None,
        help="Path to tracked repos JSON configuration file",
    )
    parser.add_argument(
        "--output",
        dest="output",
        type=str,
        default=None,
        help="Override output file path",
    )
    parser.add_argument(
        "--lookback-days",
        dest="lookback_days",
        type=int,
        default=None,
        help="Override lookback period in days (default: from config or 30)",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=False,
        help="Print config summary and exit without collecting",
    )
    parser.add_argument(
        "--verbose",
        dest="verbose",
        action="store_true",
        default=False,
        help="Enable detailed debug logging",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_args()
    exit_code = main(
        config_path=args.config_path,
        output_path=args.output,
        lookback_days=args.lookback_days,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )
    sys.exit(exit_code)
```

### 6.11 `tests/unit/test_metrics_config.py` (Add)

**Complete file contents:**

```python
"""Unit tests for metrics configuration loading and validation.

Issue #333: Cross-Project Metrics Aggregation.
Tests: T010, T020, T030, T040, T050
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest import mock

import pytest

from assemblyzero.utils.metrics_config import (
    load_config,
    parse_repo_string,
    validate_config,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "metrics"


class TestLoadConfig:
    """Tests for load_config()."""

    def test_t010_load_from_explicit_path(self) -> None:
        """T010: Config loading from explicit path returns valid config."""
        config_path = str(FIXTURES_DIR / "tracked_repos.json")
        config = load_config(config_path)

        assert "repos" in config
        assert len(config["repos"]) == 3
        assert config["lookback_days"] == 30
        assert config["output_dir"] == "docs/metrics"

    def test_t020_load_from_env_var(self, tmp_path: Path) -> None:
        """T020: Config loading fallback to ASSEMBLYZERO_METRICS_CONFIG env var."""
        config_data = {
            "repos": ["martymcenroe/AssemblyZero"],
            "lookback_days": 14,
        }
        config_file = tmp_path / "env_config.json"
        config_file.write_text(json.dumps(config_data))

        with mock.patch.dict(
            os.environ, {"ASSEMBLYZERO_METRICS_CONFIG": str(config_file)}
        ):
            config = load_config()

        assert len(config["repos"]) == 1
        assert config["lookback_days"] == 14

    def test_load_file_not_found(self) -> None:
        """Config loading raises FileNotFoundError when no config found."""
        with mock.patch.dict(os.environ, {}, clear=True):
            with pytest.raises(FileNotFoundError, match="No config file found"):
                load_config("/nonexistent/path/config.json")

    def test_load_malformed_json(self, tmp_path: Path) -> None:
        """Config loading raises ValueError on malformed JSON."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json {{{")

        with pytest.raises(ValueError, match="Config file is malformed"):
            load_config(str(bad_file))


class TestValidateConfig:
    """Tests for validate_config()."""

    def test_t030_rejects_empty_repos(self) -> None:
        """T030: Config validation rejects empty repos list."""
        with pytest.raises(ValueError, match="non-empty list"):
            validate_config({"repos": []})

    def test_t040_rejects_invalid_repo_format(self) -> None:
        """T040: Config validation rejects malformed repo string."""
        with pytest.raises(ValueError, match="Invalid repo format"):
            validate_config({"repos": ["invalid"]})

    def test_rejects_missing_repos_key(self) -> None:
        """Config validation rejects missing repos key."""
        with pytest.raises(ValueError, match="'repos' key is required"):
            validate_config({})

    def test_rejects_negative_lookback_days(self) -> None:
        """Config validation rejects negative lookback_days."""
        with pytest.raises(ValueError, match="positive integer"):
            validate_config({"repos": ["a/b"], "lookback_days": -1})

    def test_accepts_string_repos(self) -> None:
        """Config validation accepts string-format repos and converts them."""
        config = validate_config({"repos": ["owner/repo"]})
        assert config["repos"][0]["owner"] == "owner"
        assert config["repos"][0]["name"] == "repo"
        assert config["repos"][0]["full_name"] == "owner/repo"
        assert config["repos"][0]["enabled"] is True

    def test_accepts_dict_repos_with_full_name(self) -> None:
        """Config validation accepts dict-format repos with full_name."""
        config = validate_config(
            {"repos": [{"full_name": "owner/repo", "enabled": False}]}
        )
        assert config["repos"][0]["enabled"] is False
        assert config["repos"][0]["owner"] == "owner"

    def test_accepts_dict_repos_with_owner_name(self) -> None:
        """Config validation accepts dict-format repos with owner+name."""
        config = validate_config(
            {"repos": [{"owner": "org", "name": "project"}]}
        )
        assert config["repos"][0]["full_name"] == "org/project"

    def test_applies_defaults(self) -> None:
        """Config validation applies defaults for optional fields."""
        config = validate_config({"repos": ["a/b"]})
        assert config["lookback_days"] == 30
        assert config["output_dir"] == "docs/metrics"
        assert config["cache_ttl_seconds"] == 300
        assert config["github_token_env"] == "GITHUB_TOKEN"


class TestParseRepoString:
    """Tests for parse_repo_string()."""

    def test_t050_parse_valid_input(self) -> None:
        """T050: parse_repo_string parses valid 'owner/name' format."""
        result = parse_repo_string("martymcenroe/AssemblyZero")
        assert result["owner"] == "martymcenroe"
        assert result["name"] == "AssemblyZero"
        assert result["full_name"] == "martymcenroe/AssemblyZero"
        assert result["enabled"] is True

    def test_parse_with_special_chars(self) -> None:
        """parse_repo_string handles dots, hyphens, underscores."""
        result = parse_repo_string("my-org/my_repo.v2")
        assert result["owner"] == "my-org"
        assert result["name"] == "my_repo.v2"

    def test_parse_rejects_no_slash(self) -> None:
        """parse_repo_string rejects string without slash."""
        with pytest.raises(ValueError, match="Invalid repo format"):
            parse_repo_string("noslash")

    def test_parse_rejects_empty(self) -> None:
        """parse_repo_string rejects empty string."""
        with pytest.raises(ValueError, match="Invalid repo format"):
            parse_repo_string("")

    def test_parse_rejects_multiple_slashes(self) -> None:
        """parse_repo_string rejects strings with multiple slashes."""
        with pytest.raises(ValueError, match="Invalid repo format"):
            parse_repo_string("a/b/c")
```

### 6.12 `tests/unit/test_github_metrics_client.py` (Add)

**Complete file contents:**

```python
"""Unit tests for GitHub metrics client.

Issue #333: Cross-Project Metrics Aggregation.
Tests: T060, T070, T080, T230, T240, T250, T260, T310, T320, T330, T340
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from unittest import mock
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from github import GithubException, UnknownObjectException

from assemblyzero.utils.github_metrics_client import GitHubMetricsClient


class TestFilterIssuesOnly:
    """Tests for _filter_issues_only()."""

    def test_t060_filters_out_prs(self) -> None:
        """T060: Client filters out pull requests from issue list."""
        client = GitHubMetricsClient.__new__(GitHubMetricsClient)
        items = [
            {"number": 1, "title": "Issue", "pull_request": None},
            {"number": 2, "title": "PR", "pull_request": {"url": "https://..."}},
            {"number": 3, "title": "Issue 2"},
            {"number": 4, "title": "PR 2", "pull_request": {"url": "https://..."}},
            {"number": 5, "title": "PR null", "pull_request": None},
        ]
        result = client._filter_issues_only(items)
        assert len(result) == 3
        assert all(
            not item.get("pull_request") for item in result
        )
        assert {item["number"] for item in result} == {1, 3, 5}


class TestFetchRepoContents:
    """Tests for fetch_repo_contents()."""

    @patch("assemblyzero.utils.github_metrics_client.Github")
    def test_t070_handles_404_gracefully(self, mock_github_cls: MagicMock) -> None:
        """T070: Client returns empty list for missing content (404)."""
        mock_repo = MagicMock()
        mock_repo.get_contents.side_effect = UnknownObjectException(
            404, {"message": "Not Found"}, {}
        )
        mock_github_instance = MagicMock()
        mock_github_instance.get_repo.return_value = mock_repo
        mock_github_cls.return_value = mock_github_instance

        client = GitHubMetricsClient(token="ghp_test")
        result = client.fetch_repo_contents("owner/repo", "nonexistent/path")
        assert result == []


class TestRetryBehavior:
    """Tests for retry-on-429 behavior."""

    @patch("assemblyzero.utils.github_metrics_client.Github")
    def test_t080_retries_on_rate_limit(self, mock_github_cls: MagicMock) -> None:
        """T080: Client retries on 429 rate limit error and succeeds."""
        # Create mock issue
        mock_issue = MagicMock()
        mock_issue.number = 1
        mock_issue.title = "Test"
        mock_issue.state = "open"
        mock_issue.created_at = datetime(2026, 2, 1, tzinfo=timezone.utc)
        mock_issue.closed_at = None
        mock_issue.labels = []
        mock_issue.pull_request = None

        mock_repo = MagicMock()
        # First call raises 429, second succeeds
        mock_repo.get_issues.side_effect = [
            GithubException(429, {"message": "rate limit"}, {}),
            [mock_issue],
        ]

        mock_github_instance = MagicMock()
        mock_github_instance.get_repo.return_value = mock_repo
        mock_github_cls.return_value = mock_github_instance

        client = GitHubMetricsClient(token="ghp_test")
        # Clear cache to ensure fresh call
        client._cache = {}

        result = client.fetch_issues("owner/repo", "2026-01-01T00:00:00Z")
        assert len(result) == 1
        assert result[0]["number"] == 1
        assert mock_repo.get_issues.call_count == 2


class TestRateLimit:
    """Tests for rate limit checking."""

    @patch("assemblyzero.utils.github_metrics_client.Github")
    def test_t230_rate_limit_warning(
        self, mock_github_cls: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """T230: Logs warning when remaining rate limit is low."""
        mock_core = MagicMock()
        mock_core.remaining = 50
        mock_core.limit = 5000
        mock_core.reset = datetime(2026, 2, 24, 16, 30, tzinfo=timezone.utc)

        mock_rate_limit = MagicMock()
        mock_rate_limit.core = mock_core

        mock_github_instance = MagicMock()
        mock_github_instance.get_rate_limit.return_value = mock_rate_limit
        mock_github_cls.return_value = mock_github_instance

        client = GitHubMetricsClient(token="ghp_test")
        result = client.get_rate_limit_remaining()

        assert result["remaining"] == 50
        assert result["limit"] == 5000


class TestCaching:
    """Tests for caching behavior."""

    def test_t240_cache_key_deterministic(self) -> None:
        """T240: Same inputs produce same cache key."""
        client = GitHubMetricsClient.__new__(GitHubMetricsClient)
        key1 = client._get_cache_key("owner/repo", "issues", {"since": "2026-01-01", "state": "all"})
        key2 = client._get_cache_key("owner/repo", "issues", {"since": "2026-01-01", "state": "all"})
        assert key1 == key2

        # Different param order should produce same key (sorted)
        key3 = client._get_cache_key("owner/repo", "issues", {"state": "all", "since": "2026-01-01"})
        assert key1 == key3

    def test_t250_cache_hit_within_ttl(self) -> None:
        """T250: Cached response returned within TTL, no duplicate API call."""
        client = GitHubMetricsClient.__new__(GitHubMetricsClient)
        client._cache_ttl = 300
        client._cache = {}

        cache_key = "owner/repo:issues:since=2026-01-01&state=all"
        cached_data = [{"number": 1, "title": "Cached"}]
        client._cache[cache_key] = (time.time(), cached_data)

        assert client._is_cache_valid(cache_key) is True

    def test_t260_cache_expires_after_ttl(self) -> None:
        """T260: Expired cache entry returns False for validity check."""
        client = GitHubMetricsClient.__new__(GitHubMetricsClient)
        client._cache_ttl = 300
        client._cache = {}

        cache_key = "owner/repo:issues:since=2026-01-01&state=all"
        # Stored 500 seconds ago (past 300s TTL)
        client._cache[cache_key] = (time.time() - 500, [{"number": 1}])

        assert client._is_cache_valid(cache_key) is False

    def test_cache_miss_for_unknown_key(self) -> None:
        """Cache returns False for unknown key."""
        client = GitHubMetricsClient.__new__(GitHubMetricsClient)
        client._cache_ttl = 300
        client._cache = {}
        assert client._is_cache_valid("nonexistent") is False


class TestTokenResolution:
    """Tests for token resolution."""

    def test_t310_authenticates_with_github_token(self) -> None:
        """T310: Client resolves token from GITHUB_TOKEN env var."""
        client = GitHubMetricsClient.__new__(GitHubMetricsClient)
        with mock.patch.dict(
            os.environ, {"GITHUB_TOKEN": "ghp_test123"}, clear=False
        ):
            token = client._resolve_token(None)
        assert token == "ghp_test123"

    def test_t320_falls_back_to_gh_token(self) -> None:
        """T320: Client falls back to GH_TOKEN when GITHUB_TOKEN not set."""
        client = GitHubMetricsClient.__new__(GitHubMetricsClient)
        env = {"GH_TOKEN": "ghp_fallback456"}
        # Ensure GITHUB_TOKEN is not set
        with mock.patch.dict(os.environ, env, clear=False):
            with mock.patch.dict(os.environ, {}, clear=False):
                # Remove GITHUB_TOKEN if present
                os.environ.pop("GITHUB_TOKEN", None)
                token = client._resolve_token(None)
        assert token == "ghp_fallback456"

    def test_explicit_token_wins(self) -> None:
        """Explicit token argument takes priority over env vars."""
        client = GitHubMetricsClient.__new__(GitHubMetricsClient)
        with mock.patch.dict(
            os.environ, {"GITHUB_TOKEN": "ghp_env"}, clear=False
        ):
            token = client._resolve_token("ghp_explicit")
        assert token == "ghp_explicit"

    def test_no_token_returns_none(self) -> None:
        """Returns None when no token available."""
        client = GitHubMetricsClient.__new__(GitHubMetricsClient)
        with mock.patch.dict(os.environ, {}, clear=True):
            token = client._resolve_token(None)
        assert token is None

    @patch("assemblyzero.utils.github_metrics_client.Github")
    def test_t330_authenticated_fetches_private_repo(
        self, mock_github_cls: MagicMock
    ) -> None:
        """T330: Authenticated client fetches private repo issues."""
        mock_issue = MagicMock()
        mock_issue.number = 10
        mock_issue.title = "Private issue"
        mock_issue.state = "open"
        mock_issue.created_at = datetime(2026, 2, 1, tzinfo=timezone.utc)
        mock_issue.closed_at = None
        mock_issue.labels = []
        mock_issue.pull_request = None

        mock_repo = MagicMock()
        mock_repo.get_issues.return_value = [mock_issue]
        mock_github_instance = MagicMock()
        mock_github_instance.get_repo.return_value = mock_repo
        mock_github_cls.return_value = mock_github_instance

        client = GitHubMetricsClient(token="ghp_private_access")
        result = client.fetch_issues("owner/private-repo", "2026-01-01T00:00:00Z")
        assert len(result) == 1
        assert result[0]["title"] == "Private issue"

    @patch("assemblyzero.utils.github_metrics_client.Github")
    def test_t340_unauthenticated_404_on_private_repo(
        self, mock_github_cls: MagicMock
    ) -> None:
        """T340: Unauthenticated client gets 404 on private repo."""
        mock_github_instance = MagicMock()
        mock_github_instance.get_repo.side_effect = UnknownObjectException(
            404, {"message": "Not Found"}, {}
        )
        mock_github_cls.return_value = mock_github_instance

        client = GitHubMetricsClient(token=None)

        with pytest.raises(UnknownObjectException):
            client.fetch_issues("owner/private-repo", "2026-01-01T00:00:00Z")
```

### 6.13 `tests/unit/test_metrics_aggregator.py` (Add)

**Complete file contents:**

```python
"""Unit tests for metrics aggregation logic.

Issue #333: Cross-Project Metrics Aggregation.
Tests: T090, T100, T110, T120, T130, T140, T150, T160
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.utils.metrics_aggregator import MetricsAggregator
from assemblyzero.utils.metrics_models import (
    MetricsCollectionConfig,
    PerRepoMetrics,
    RepoGeminiMetrics,
    RepoIssueMetrics,
    RepoWorkflowMetrics,
    TrackedRepoConfig,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "metrics"


def _make_config(lookback_days: int = 30) -> MetricsCollectionConfig:
    """Create a test config."""
    return MetricsCollectionConfig(
        repos=[],
        lookback_days=lookback_days,
        output_dir="docs/metrics",
        cache_ttl_seconds=300,
        github_token_env="GITHUB_TOKEN",
    )


def _make_mock_client() -> MagicMock:
    """Create a mock GitHubMetricsClient."""
    return MagicMock()


class TestCollectIssueMetrics:
    """Tests for collect_issue_metrics()."""

    def test_t090_happy_path(self) -> None:
        """T090: Issue metrics with mix of open/closed issues."""
        mock_client = _make_mock_client()
        mock_client.fetch_issues.return_value = [
            {
                "number": 1,
                "state": "closed",
                "created_at": "2026-02-10T08:00:00Z",
                "closed_at": "2026-02-10T20:00:00Z",
                "labels": ["bug", "tdd"],
            },
            {
                "number": 2,
                "state": "closed",
                "created_at": "2026-02-11T10:00:00Z",
                "closed_at": "2026-02-12T10:00:00Z",
                "labels": ["feature", "implementation"],
            },
            {
                "number": 3,
                "state": "open",
                "created_at": "2026-02-13T09:00:00Z",
                "closed_at": None,
                "labels": ["feature"],
            },
        ]

        agg = MetricsAggregator(client=mock_client, config=_make_config())
        result = agg.collect_issue_metrics(
            "owner/repo", "2026-02-01", "2026-02-24"
        )

        assert result["issues_opened"] == 3
        assert result["issues_closed"] == 2
        assert result["issues_open_current"] == 1
        # Issue 1: 12 hours, Issue 2: 24 hours -> avg = 18.0
        assert result["avg_close_time_hours"] == 18.0
        assert result["issues_by_label"]["bug"] == 1
        assert result["issues_by_label"]["feature"] == 2
        assert result["issues_by_label"]["tdd"] == 1
        assert result["issues_by_label"]["implementation"] == 1

    def test_t100_zero_issues(self) -> None:
        """T100: Issue metrics with zero issues returns zeroed values."""
        mock_client = _make_mock_client()
        mock_client.fetch_issues.return_value = []

        agg = MetricsAggregator(client=mock_client, config=_make_config())
        result = agg.collect_issue_metrics(
            "owner/repo", "2026-02-01", "2026-02-24"
        )

        assert result["issues_opened"] == 0
        assert result["issues_closed"] == 0
        assert result["issues_open_current"] == 0
        assert result["avg_close_time_hours"] is None
        assert result["issues_by_label"] == {}


class TestWorkflowDetection:
    """Tests for collect_workflow_metrics()."""

    def test_t110_from_labels(self) -> None:
        """T110: Workflow detection from issue labels."""
        mock_client = _make_mock_client()
        # No content files
        mock_client.fetch_repo_contents.return_value = []
        # Issues with workflow labels
        mock_client.fetch_issues.return_value = [
            {"number": 1, "labels": ["requirements"], "state": "open"},
            {"number": 2, "labels": ["lld"], "state": "closed"},
            {"number": 3, "labels": ["implementation"], "state": "closed"},
            {"number": 4, "labels": ["tdd"], "state": "open"},
            {"number": 5, "labels": ["implementation", "requirements"], "state": "closed"},
        ]

        agg = MetricsAggregator(client=mock_client, config=_make_config())
        result = agg.collect_workflow_metrics("owner/repo")

        assert result["requirements_workflows"] == 3  # issues 1, 2, 5
        assert result["implementation_workflows"] == 2  # issues 3, 5
        assert result["tdd_workflows"] == 1  # issue 4

    def test_t120_from_content_listing(self) -> None:
        """T120: Workflow detection from content listing (LLD files)."""
        mock_client = _make_mock_client()

        def mock_contents(repo: str, path: str) -> list[dict]:
            if path == "docs/lld/active":
                return [
                    {"name": "001.md", "type": "file", "path": "docs/lld/active/001.md", "size": 100},
                    {"name": "002.md", "type": "file", "path": "docs/lld/active/002.md", "size": 200},
                    {"name": "003.md", "type": "file", "path": "docs/lld/active/003.md", "size": 150},
                    {"name": "readme.txt", "type": "file", "path": "docs/lld/active/readme.txt", "size": 50},
                    {"name": "004.md", "type": "file", "path": "docs/lld/active/004.md", "size": 300},
                    {"name": "archive", "type": "dir", "path": "docs/lld/active/archive", "size": 0},
                ]
            if path == "docs/reports":
                return [
                    {"name": "333", "type": "dir", "path": "docs/reports/333", "size": 0},
                    {"name": "320", "type": "dir", "path": "docs/reports/320", "size": 0},
                ]
            return []

        mock_client.fetch_repo_contents.side_effect = mock_contents
        mock_client.fetch_issues.return_value = []

        agg = MetricsAggregator(client=mock_client, config=_make_config())
        result = agg.collect_workflow_metrics("owner/repo")

        assert result["lld_count"] == 4  # 4 .md files (not .txt, not dir)
        assert result["report_count"] == 2  # 2 dirs


class TestGeminiMetrics:
    """Tests for collect_gemini_metrics()."""

    def test_t130_verdict_counting(self) -> None:
        """T130: Gemini metrics correctly count APPROVE and BLOCK."""
        mock_client = _make_mock_client()

        def mock_contents(repo: str, path: str) -> list[dict]:
            if path == "docs/reports":
                return [
                    {"name": "333", "type": "dir", "path": "docs/reports/333", "size": 0},
                    {"name": "320", "type": "dir", "path": "docs/reports/320", "size": 0},
                ]
            if path == "docs/reports/333":
                return [
                    {"name": "gemini-verdict-approved.json", "type": "file", "path": "docs/reports/333/gemini-verdict-approved.json", "size": 50},
                ]
            if path == "docs/reports/320":
                return [
                    {"name": "gemini-verdict-blocked.json", "type": "file", "path": "docs/reports/320/gemini-verdict-blocked.json", "size": 50},
                ]
            if path == ".gemini-reviews":
                return [
                    {"name": "review-approved-1.json", "type": "file", "path": ".gemini-reviews/review-approved-1.json", "size": 30},
                    {"name": "review-approved-2.json", "type": "file", "path": ".gemini-reviews/review-approved-2.json", "size": 30},
                    {"name": "review-blocked-1.json", "type": "file", "path": ".gemini-reviews/review-blocked-1.json", "size": 30},
                ]
            return []

        mock_client.fetch_repo_contents.side_effect = mock_contents

        agg = MetricsAggregator(client=mock_client, config=_make_config())
        result = agg.collect_gemini_metrics("owner/repo")

        assert result["approvals"] == 3  # 1 from reports/333 + 2 from .gemini-reviews
        assert result["blocks"] == 2  # 1 from reports/320 + 1 from .gemini-reviews
        assert result["total_reviews"] == 5
        assert result["approval_rate"] == 0.6

    def test_t140_no_verdicts(self) -> None:
        """T140: Gemini metrics with no verdicts returns zeros."""
        mock_client = _make_mock_client()
        mock_client.fetch_repo_contents.return_value = []

        agg = MetricsAggregator(client=mock_client, config=_make_config())
        result = agg.collect_gemini_metrics("owner/repo")

        assert result["total_reviews"] == 0
        assert result["approvals"] == 0
        assert result["blocks"] == 0
        assert result["approval_rate"] is None


class TestAggregation:
    """Tests for aggregate()."""

    def test_t150_cross_repo_aggregation(self) -> None:
        """T150: Aggregation across multiple repos sums correctly."""
        mock_client = _make_mock_client()
        config = _make_config()
        agg = MetricsAggregator(client=mock_client, config=config)

        repo_a = PerRepoMetrics(
            repo="owner/repo-a",
            issues=RepoIssueMetrics(
                repo="owner/repo-a", period_start="2026-01-25", period_end="2026-02-24",
                issues_opened=10, issues_closed=8, issues_open_current=2,
                avg_close_time_hours=12.0, issues_by_label={"bug": 3},
            ),
            workflows=RepoWorkflowMetrics(
                repo="owner/repo-a", lld_count=5,
                requirements_workflows=3, implementation_workflows=4,
                tdd_workflows=2, report_count=6,
            ),
            gemini=RepoGeminiMetrics(
                repo="owner/repo-a", total_reviews=10,
                approvals=8, blocks=2, approval_rate=0.8,
            ),
        )
        repo_b = PerRepoMetrics(
            repo="owner/repo-b",
            issues=RepoIssueMetrics(
                repo="owner/repo-b", period_start="2026-01-25", period_end="2026-02-24",
                issues_opened=5, issues_closed=3, issues_open_current=4,
                avg_close_time_hours=24.0, issues_by_label={"feature": 2},
            ),
            workflows=RepoWorkflowMetrics(
                repo="owner/repo-b", lld_count=2,
                requirements_workflows=1, implementation_workflows=1,
                tdd_workflows=0, report_count=3,
            ),
            gemini=RepoGeminiMetrics(
                repo="owner/repo-b", total_reviews=4,
                approvals=3, blocks=1, approval_rate=0.75,
            ),
        )

        result = agg.aggregate([repo_a, repo_b])

        assert result["totals"]["issues_opened"] == 15
        assert result["totals"]["issues_closed"] == 11
        assert result["totals"]["issues_open_current"] == 6
        assert result["totals"]["lld_count"] == 7
        # total_workflows = (3+4+2) + (1+1+0) = 11
        assert result["totals"]["total_workflows"] == 11
        assert result["totals"]["gemini_reviews"] == 14
        # gemini_approval_rate = (8+3) / (10+4) = 11/14 ≈ 0.786
        assert result["totals"]["gemini_approval_rate"] == 0.786
        assert result["totals"]["report_count"] == 9
        # weighted avg close time = (12*8 + 24*3) / (8+3) = (96+72)/11 ≈ 15.27
        assert result["totals"]["avg_close_time_hours"] == 15.27
        assert result["repos_collected"] == 2
        assert result["repos_failed"] == []
        assert len(result["per_repo"]) == 2

    def test_t160_aggregation_with_failed_repos(self) -> None:
        """T160: Failed repos listed, successful ones aggregated."""
        mock_client = _make_mock_client()
        config = _make_config()
        agg = MetricsAggregator(client=mock_client, config=config)

        repo_a = PerRepoMetrics(
            repo="owner/repo-a",
            issues=RepoIssueMetrics(
                repo="owner/repo-a", period_start="2026-01-25", period_end="2026-02-24",
                issues_opened=5, issues_closed=3, issues_open_current=2,
                avg_close_time_hours=10.0, issues_by_label={},
            ),
            workflows=RepoWorkflowMetrics(
                repo="owner/repo-a", lld_count=1,
                requirements_workflows=1, implementation_workflows=1,
                tdd_workflows=0, report_count=1,
            ),
            gemini=RepoGeminiMetrics(
                repo="owner/repo-a", total_reviews=2,
                approvals=2, blocks=0, approval_rate=1.0,
            ),
        )

        result = agg.aggregate([repo_a], repos_failed=["owner/failed-repo"])

        assert result["repos_tracked"] == 2  # 1 success + 1 failed
        assert result["repos_collected"] == 1
        assert result["repos_failed"] == ["owner/failed-repo"]
        assert result["totals"]["issues_opened"] == 5
```

### 6.14 `tests/unit/test_collect_cross_project_metrics.py` (Add)

**Complete file contents:**

```python
"""Unit tests for the main collector CLI orchestration.

Issue #333: Cross-Project Metrics Aggregation.
Tests: T170, T180, T190, T200, T210, T220, T270, T280, T290, T300
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest

from tools.collect_cross_project_metrics import (
    format_summary_table,
    main,
    parse_args,
    write_metrics_output,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "metrics"


class TestParseArgs:
    """Tests for parse_args()."""

    def test_t270_all_flags(self) -> None:
        """T270: CLI parses all supported flags."""
        args = parse_args([
            "--config", "f.json",
            "--output", "o/out.json",
            "--lookback-days", "7",
            "--dry-run",
            "--verbose",
        ])
        assert args.config_path == "f.json"
        assert args.output == "o/out.json"
        assert args.lookback_days == 7
        assert args.dry_run is True
        assert args.verbose is True

    def test_no_args_defaults(self) -> None:
        """CLI with no args uses defaults."""
        args = parse_args([])
        assert args.config_path is None
        assert args.output is None
        assert args.lookback_days is None
        assert args.dry_run is False
        assert args.verbose is False


class TestDryRun:
    """Tests for dry-run mode."""

    @patch("tools.collect_cross_project_metrics.load_config")
    def test_t170_dry_run(self, mock_load: MagicMock, capsys: pytest.CaptureFixture) -> None:
        """T170: Dry-run prints config and exits 0 without API calls."""
        mock_load.return_value = {
            "repos": [
                {"owner": "a", "name": "b", "full_name": "a/b", "enabled": True},
            ],
            "lookback_days": 30,
            "output_dir": "docs/metrics",
            "cache_ttl_seconds": 300,
            "github_token_env": "GITHUB_TOKEN",
        }

        exit_code = main(config_path="test.json", dry_run=True)
        assert exit_code == 0

        captured = capsys.readouterr()
        assert "Dry Run Mode" in captured.out
        assert "a/b" in captured.out


class TestExitCodes:
    """Tests for exit codes on partial/total failure."""

    @patch("tools.collect_cross_project_metrics.write_metrics_output")
    @patch("tools.collect_cross_project_metrics.MetricsAggregator")
    @patch("tools.collect_cross_project_metrics.GitHubMetricsClient")
    @patch("tools.collect_cross_project_metrics.load_config")
    def test_t180_partial_failure(
        self,
        mock_load: MagicMock,
        mock_client_cls: MagicMock,
        mock_agg_cls: MagicMock,
        mock_write: MagicMock,
    ) -> None:
        """T180: Returns 1 when some repos fail."""
        mock_load.return_value = {
            "repos": [
                {"owner": "a", "name": "good", "full_name": "a/good", "enabled": True},
                {"owner": "a", "name": "bad", "full_name": "a/bad", "enabled": True},
            ],
            "lookback_days": 30,
            "output_dir": "docs/metrics",
            "cache_ttl_seconds": 300,
            "github_token_env": "GITHUB_TOKEN",
        }

        mock_client_instance = MagicMock()
        mock_client_instance.get_rate_limit_remaining.return_value = {
            "remaining": 5000, "limit": 5000, "reset_at": "2026-02-24T16:00:00Z"
        }
        mock_client_cls.return_value = mock_client_instance

        mock_agg_instance = MagicMock()
        # First repo succeeds, second fails
        good_metrics = {
            "repo": "a/good",
            "issues": {"repo": "a/good", "period_start": "2026-01-25", "period_end": "2026-02-24", "issues_opened": 5, "issues_closed": 3, "issues_open_current": 2, "avg_close_time_hours": 10.0, "issues_by_label": {}},
            "workflows": {"repo": "a/good", "lld_count": 1, "requirements_workflows": 1, "implementation_workflows": 0, "tdd_workflows": 0, "report_count": 0},
            "gemini": {"repo": "a/good", "total_reviews": 0, "approvals": 0, "blocks": 0, "approval_rate": None},
        }
        mock_agg_instance.collect_repo_metrics.side_effect = [
            good_metrics,
            Exception("API error on bad repo"),
        ]
        mock_agg_instance.aggregate.return_value = {
            "generated_at": "2026-02-24T15:30:00Z",
            "period_start": "2026-01-25",
            "period_end": "2026-02-24",
            "repos_tracked": 2,
            "repos_collected": 1,
            "repos_failed": ["a/bad"],
            "totals": {"issues_opened": 5, "issues_closed": 3, "issues_open_current": 2, "avg_close_time_hours": 10.0, "lld_count": 1, "total_workflows": 1, "gemini_reviews": 0, "gemini_approval_rate": None, "report_count": 0},
            "per_repo": [good_metrics],
        }
        mock_agg_cls.return_value = mock_agg_instance
        mock_write.return_value = "docs/metrics/test.json"

        exit_code = main(config_path="test.json")
        assert exit_code == 1

    @patch("tools.collect_cross_project_metrics.GitHubMetricsClient")
    @patch("tools.collect_cross_project_metrics.load_config")
    def test_t190_total_failure(
        self,
        mock_load: MagicMock,
        mock_client_cls: MagicMock,
    ) -> None:
        """T190: Returns 2 when all repos fail."""
        mock_load.return_value = {
            "repos": [
                {"owner": "a", "name": "bad1", "full_name": "a/bad1", "enabled": True},
                {"owner": "a", "name": "bad2", "full_name": "a/bad2", "enabled": True},
            ],
            "lookback_days": 30,
            "output_dir": "docs/metrics",
            "cache_ttl_seconds": 300,
            "github_token_env": "GITHUB_TOKEN",
        }

        mock_client_instance = MagicMock()
        mock_client_instance.get_rate_limit_remaining.return_value = {
            "remaining": 5000, "limit": 5000, "reset_at": "2026-02-24T16:00:00Z"
        }
        mock_client_cls.return_value = mock_client_instance

        with patch("tools.collect_cross_project_metrics.MetricsAggregator") as mock_agg_cls:
            mock_agg_instance = MagicMock()
            mock_agg_instance.collect_repo_metrics.side_effect = Exception("fail")
            mock_agg_cls.return_value = mock_agg_instance

            exit_code = main(config_path="test.json")

        assert exit_code == 2


class TestOutputWriting:
    """Tests for write_metrics_output()."""

    def test_t200_output_file_naming(self, tmp_path: Path) -> None:
        """T200: Output file uses date-stamped naming."""
        metrics = {
            "generated_at": "2026-02-24T15:30:00Z",
            "period_start": "2026-01-25",
            "period_end": "2026-02-24",
            "repos_tracked": 1,
            "repos_collected": 1,
            "repos_failed": [],
            "totals": {"issues_opened": 5, "issues_closed": 3, "issues_open_current": 2, "avg_close_time_hours": 10.0, "lld_count": 1, "total_workflows": 1, "gemini_reviews": 0, "gemini_approval_rate": None, "report_count": 0},
            "per_repo": [],
        }

        result_path = write_metrics_output(metrics, str(tmp_path))
        assert "cross-project-" in result_path
        assert result_path.endswith(".json")
        assert Path(result_path).exists()

    def test_t210_latest_json_creation(self, tmp_path: Path) -> None:
        """T210: cross-project-latest.json is created alongside dated file."""
        metrics = {
            "generated_at": "2026-02-24T15:30:00Z",
            "period_start": "2026-01-25",
            "period_end": "2026-02-24",
            "repos_tracked": 0,
            "repos_collected": 0,
            "repos_failed": [],
            "totals": {"issues_opened": 0, "issues_closed": 0, "issues_open_current": 0, "avg_close_time_hours": None, "lld_count": 0, "total_workflows": 0, "gemini_reviews": 0, "gemini_approval_rate": None, "report_count": 0},
            "per_repo": [],
        }

        write_metrics_output(metrics, str(tmp_path))
        latest = tmp_path / "cross-project-latest.json"
        assert latest.exists()

    def test_output_dir_not_exist(self) -> None:
        """write_metrics_output raises OSError if dir doesn't exist."""
        with pytest.raises(OSError, match="does not exist"):
            write_metrics_output({}, "/nonexistent/dir/path")

    def test_t300_custom_output_path(self, tmp_path: Path) -> None:
        """T300: CLI --output overrides default output path."""
        metrics = {
            "generated_at": "2026-02-24T15:30:00Z",
            "period_start": "2026-01-25",
            "period_end": "2026-02-24",
            "repos_tracked": 0,
            "repos_collected": 0,
            "repos_failed": [],
            "totals": {"issues_opened": 0, "issues_closed": 0, "issues_open_current": 0, "avg_close_time_hours": None, "lld_count": 0, "total_workflows": 0, "gemini_reviews": 0, "gemini_approval_rate": None, "report_count": 0},
            "per_repo": [],
        }
        custom_path = str(tmp_path / "custom-metrics.json")
        result = write_metrics_output(metrics, str(tmp_path), output_path=custom_path)
        assert result == custom_path
        assert Path(custom_path).exists()


class TestSummaryTable:
    """Tests for format_summary_table()."""

    def test_t220_summary_formatting(self) -> None:
        """T220: Summary table contains repo names and totals."""
        metrics = {
            "generated_at": "2026-02-24T15:30:00Z",
            "period_start": "2026-01-25",
            "period_end": "2026-02-24",
            "repos_tracked": 2,
            "repos_collected": 2,
            "repos_failed": [],
            "totals": {"issues_opened": 15, "issues_closed": 11, "issues_open_current": 6, "avg_close_time_hours": 15.27, "lld_count": 7, "total_workflows": 11, "gemini_reviews": 14, "gemini_approval_rate": 0.786, "report_count": 9},
            "per_repo": [
                {
                    "repo": "owner/repo-a",
                    "issues": {"repo": "owner/repo-a", "period_start": "2026-01-25", "period_end": "2026-02-24", "issues_opened": 10, "issues_closed": 8, "issues_open_current": 2, "avg_close_time_hours": 12.0, "issues_by_label": {}},
                    "workflows": {"repo": "owner/repo-a", "lld_count": 5, "requirements_workflows": 3, "implementation_workflows": 4, "tdd_workflows": 2, "report_count": 6},
                    "gemini": {"repo": "owner/repo-a", "total_reviews": 10, "approvals": 8, "blocks": 2, "approval_rate": 0.8},
                },
                {
                    "repo": "owner/repo-b",
                    "issues": {"repo": "owner/repo-b", "period_start": "2026-01-25", "period_end": "2026-02-24", "issues_opened": 5, "issues_closed": 3, "issues_open_current": 4, "avg_close_time_hours": 24.0, "issues_by_label": {}},
                    "workflows": {"repo": "owner/repo-b", "lld_count": 2, "requirements_workflows": 1, "implementation_workflows": 1, "tdd_workflows": 0, "report_count": 3},
                    "gemini": {"repo": "owner/repo-b", "total_reviews": 4, "approvals": 3, "blocks": 1, "approval_rate": 0.75},
                },
            ],
        }

        table = format_summary_table(metrics)
        assert "owner/repo-a" in table
        assert "owner/repo-b" in table
        assert "TOTALS" in table
        assert "15" in table  # total opened
        assert "Repos tracked: 2" in table

    def test_summary_with_failed_repos(self) -> None:
        """Summary table shows failed repos when present."""
        metrics = {
            "generated_at": "2026-02-24T15:30:00Z",
            "period_start": "2026-01-25",
            "period_end": "2026-02-24",
            "repos_tracked": 2,
            "repos_collected": 1,
            "repos_failed": ["owner/bad-repo"],
            "totals": {"issues_opened": 5, "issues_closed": 3, "issues_open_current": 2, "avg_close_time_hours": 10.0, "lld_count": 0, "total_workflows": 0, "gemini_reviews": 0, "gemini_approval_rate": None, "report_count": 0},
            "per_repo": [
                {
                    "repo": "owner/good-repo",
                    "issues": {"repo": "owner/good-repo", "period_start": "2026-01-25", "period_end": "2026-02-24", "issues_opened": 5, "issues_closed": 3, "issues_open_current": 2, "avg_close_time_hours": 10.0, "issues_by_label": {}},
                    "workflows": {"repo": "owner/good-repo", "lld_count": 0, "requirements_workflows": 0, "implementation_workflows": 0, "tdd_workflows": 0, "report_count": 0},
                    "gemini": {"repo": "owner/good-repo", "total_reviews": 0, "approvals": 0, "blocks": 0, "approval_rate": None},
                },
            ],
        }
        table = format_summary_table(metrics)
        assert "Failed repos: owner/bad-repo" in table
        assert "N/A" in table  # approval_rate is None


class TestVerboseAndOverrides:
    """Tests for verbose mode and CLI overrides."""

    @patch("tools.collect_cross_project_metrics.write_metrics_output")
    @patch("tools.collect_cross_project_metrics.MetricsAggregator")
    @patch("tools.collect_cross_project_metrics.GitHubMetricsClient")
    @patch("tools.collect_cross_project_metrics.load_config")
    def test_t280_verbose_enables_debug(
        self,
        mock_load: MagicMock,
        mock_client_cls: MagicMock,
        mock_agg_cls: MagicMock,
        mock_write: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """T280: Verbose flag produces DEBUG-level log output."""
        mock_load.return_value = {
            "repos": [
                {"owner": "a", "name": "b", "full_name": "a/b", "enabled": True},
            ],
            "lookback_days": 30,
            "output_dir": "docs/metrics",
            "cache_ttl_seconds": 300,
            "github_token_env": "GITHUB_TOKEN",
        }
        mock_client_instance = MagicMock()
        mock_client_instance.get_rate_limit_remaining.return_value = {
            "remaining": 5000, "limit": 5000, "reset_at": "2026-02-24T16:00:00Z"
        }
        mock_client_cls.return_value = mock_client_instance

        mock_agg_instance = MagicMock()
        mock_agg_instance.collect_repo_metrics.return_value = {
            "repo": "a/b",
            "issues": {"repo": "a/b", "period_start": "2026-01-25", "period_end": "2026-02-24", "issues_opened": 0, "issues_closed": 0, "issues_open_current": 0, "avg_close_time_hours": None, "issues_by_label": {}},
            "workflows": {"repo": "a/b", "lld_count": 0, "requirements_workflows": 0, "implementation_workflows": 0, "tdd_workflows": 0, "report_count": 0},
            "gemini": {"repo": "a/b", "total_reviews": 0, "approvals": 0, "blocks": 0, "approval_rate": None},
        }
        mock_agg_instance.aggregate.return_value = {
            "generated_at": "2026-02-24T15:30:00Z", "period_start": "2026-01-25", "period_end": "2026-02-24",
            "repos_tracked": 1, "repos_collected": 1, "repos_failed": [],
            "totals": {"issues_opened": 0, "issues_closed": 0, "issues_open_current": 0, "avg_close_time_hours": None, "lld_count": 0, "total_workflows": 0, "gemini_reviews": 0, "gemini_approval_rate": None, "report_count": 0},
            "per_repo": [],
        }
        mock_agg_cls.return_value = mock_agg_instance
        mock_write.return_value = "/tmp/test.json"

        with caplog.at_level(logging.DEBUG):
            exit_code = main(config_path="test.json", verbose=True)

        assert exit_code == 0

    @patch("tools.collect_cross_project_metrics.write_metrics_output")
    @patch("tools.collect_cross_project_metrics.MetricsAggregator")
    @patch("tools.collect_cross_project_metrics.GitHubMetricsClient")
    @patch("tools.collect_cross_project_metrics.load_config")
    def test_t290_lookback_override(
        self,
        mock_load: MagicMock,
        mock_client_cls: MagicMock,
        mock_agg_cls: MagicMock,
        mock_write: MagicMock,
    ) -> None:
        """T290: CLI --lookback-days overrides config value."""
        config = {
            "repos": [
                {"owner": "a", "name": "b", "full_name": "a/b", "enabled": True},
            ],
            "lookback_days": 30,
            "output_dir": "docs/metrics",
            "cache_ttl_seconds": 300,
            "github_token_env": "GITHUB_TOKEN",
        }
        mock_load.return_value = config

        mock_client_instance = MagicMock()
        mock_client_instance.get_rate_limit_remaining.return_value = {
            "remaining": 5000, "limit": 5000, "reset_at": "2026-02-24T16:00:00Z"
        }
        mock_client_cls.return_value = mock_client_instance

        mock_agg_instance = MagicMock()
        mock_agg_instance.collect_repo_metrics.return_value = {
            "repo": "a/b",
            "issues": {"repo": "a/b", "period_start": "2026-02-17", "period_end": "2026-02-24", "issues_opened": 0, "issues_closed": 0, "issues_open_current": 0, "avg_close_time_hours": None, "issues_by_label": {}},
            "workflows": {"repo": "a/b", "lld_count": 0, "requirements_workflows": 0, "implementation_workflows": 0, "tdd_workflows": 0, "report_count": 0},
            "gemini": {"repo": "a/b", "total_reviews": 0, "approvals": 0, "blocks": 0, "approval_rate": None},
        }
        mock_agg_instance.aggregate.return_value = {
            "generated_at": "2026-02-24T15:30:00Z", "period_start": "2026-02-17", "period_end": "2026-02-24",
            "repos_tracked": 1, "repos_collected": 1, "repos_failed": [],
            "totals": {"issues_opened": 0, "issues_closed": 0, "issues_open_current": 0, "avg_close_time_hours": None, "lld_count": 0, "total_workflows": 0, "gemini_reviews": 0, "gemini_approval_rate": None, "report_count": 0},
            "per_repo": [],
        }
        mock_agg_cls.return_value = mock_agg_instance
        mock_write.return_value = "/tmp/test.json"

        main(config_path="test.json", lookback_days=7)

        # Verify config was modified to use CLI override
        assert config["lookback_days"] == 7
```

### 6.15 `tests/integration/test_github_metrics_integration.py` (Add)

**Complete file contents:**

```python
"""Integration tests for GitHub metrics collection against real API.

Issue #333: Cross-Project Metrics Aggregation.

These tests hit the real GitHub API and require a valid GITHUB_TOKEN.
Run with: poetry run pytest tests/integration/ -v -m integration
"""

from __future__ import annotations

import os

import pytest

from assemblyzero.utils.github_metrics_client import GitHubMetricsClient


pytestmark = pytest.mark.integration


@pytest.fixture()
def github_client() -> GitHubMetricsClient:
    """Create an authenticated GitHub client for integration tests."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        pytest.skip("GITHUB_TOKEN or GH_TOKEN not set")
    return GitHubMetricsClient(token=token, cache_ttl=60)


class TestGitHubIntegration:
    """Integration tests against real GitHub API."""

    def test_rate_limit_check(self, github_client: GitHubMetricsClient) -> None:
        """Verify rate limit endpoint returns valid data."""
        result = github_client.get_rate_limit_remaining()
        assert "remaining" in result
        assert "limit" in result
        assert isinstance(result["remaining"], int)
        assert result["remaining"] >= 0

    def test_fetch_public_repo_issues(
        self, github_client: GitHubMetricsClient
    ) -> None:
        """Fetch issues from a known public repo."""
        issues = github_client.fetch_issues(
            "octocat/Hello-World", since="2020-01-01T00:00:00Z", state="all"
        )
        assert isinstance(issues, list)
        # Hello-World repo has issues
        if issues:
            assert "number" in issues[0]
            assert "title" in issues[0]
            assert "state" in issues[0]

    def test_fetch_public_repo_contents(
        self, github_client: GitHubMetricsClient
    ) -> None:
        """Fetch contents from a known public repo."""
        contents = github_client.fetch_repo_contents("octocat/Hello-World", ".")
        assert isinstance(contents, list)
        assert len(contents) > 0
        assert "name" in contents[0]

    def test_fetch_nonexistent_path_returns_empty(
        self, github_client: GitHubMetricsClient
    ) -> None:
        """Fetching a nonexistent path returns empty list."""
        contents = github_client.fetch_repo_contents(
            "octocat/Hello-World", "nonexistent/path/here"
        )
        assert contents == []
```

## 7. Pattern References

### 7.1 CLI Tool Pattern

**File:** `tools/run_audit.py` (lines 1-60)

```python
#!/usr/bin/env python3
"""Run audit workflow for a specified issue."""

import argparse
import sys

def main():
    parser = argparse.ArgumentParser(description="Run audit workflow")
    parser.add_argument("--issue", type=int, required=True)
    # ... argument parsing and execution
```

**Relevance:** The `collect_cross_project_metrics.py` CLI follows the same pattern: `argparse` for argument parsing, a `main()` function that returns an exit code, and `if __name__ == "__main__":` entry point with `sys.exit()`. This is the standard CLI tool pattern in the project.

### 7.2 Another CLI Tool Pattern

**File:** `tools/run_implement_from_lld.py` (lines 1-60)

```python
#!/usr/bin/env python3
"""Run implementation from LLD workflow."""

import argparse
import sys

def main():
    parser = argparse.ArgumentParser(description="Run implementation from LLD")
    # ...
```

**Relevance:** Confirms the consistent pattern of CLI tools in the `tools/` directory. All tools use argparse, return integer exit codes, and handle errors with logging.

### 7.3 Test Pattern

**File:** `tests/unit/test_implementation_spec_workflow.py` (lines 1-80)

```python
"""Unit tests for implementation spec workflow."""

import pytest
from unittest.mock import MagicMock, patch

# Test classes organized by component
class TestNodeFunction:
    def test_happy_path(self):
        ...
    def test_error_case(self):
        ...
```

**Relevance:** Our test files follow this same structure: docstring with issue reference, pytest imports, test classes organized by component/function, `MagicMock` and `patch` for mocking. The test naming convention `test_tXXX_description` maps to LLD test IDs.

### 7.4 Workflow Test Pattern

**File:** `tests/test_integration_workflow.py` (lines 1-80)

```python
"""Integration workflow tests."""

import pytest

# Integration tests that test end-to-end behavior
class TestWorkflowIntegration:
    ...
```

**Relevance:** The integration test file follows the same pattern with `pytestmark` for test markers and fixture-based client setup. Our `test_github_metrics_integration.py` uses the `integration` marker similarly.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from __future__ import annotations` | stdlib | All new files |
| `from typing import TypedDict, Optional` | stdlib | `metrics_models.py` |
| `import json` | stdlib | `metrics_config.py` |
| `import os` | stdlib | `metrics_config.py`, `github_metrics_client.py` |
| `import re` | stdlib | `metrics_config.py` |
| `from pathlib import Path` | stdlib | `metrics_config.py`, `collect_cross_project_metrics.py` |
| `import logging` | stdlib | `github_metrics_client.py`, `metrics_aggregator.py`, `collect_cross_project_metrics.py` |
| `import time` | stdlib | `github_metrics_client.py` |
| `from datetime import datetime, timedelta, timezone` | stdlib | `github_metrics_client.py`, `metrics_aggregator.py`, `collect_cross_project_metrics.py` |
| `import argparse` | stdlib | `collect_cross_project_metrics.py` |
| `import shutil` | stdlib | `collect_cross_project_metrics.py` |
| `import sys` | stdlib | `collect_cross_project_metrics.py` |
| `from github import Github, GithubException, UnknownObjectException` | `pygithub` (existing) | `github_metrics_client.py` |
| `from tenacity import retry, stop_after_attempt, wait_exponential` | `tenacity` (existing) | `github_metrics_client.py` |
| `import orjson` | `orjson` (existing) | `collect_cross_project_metrics.py` |
| `import pytest` | dev dependency (existing) | All test files |
| `from unittest.mock import MagicMock, patch, mock` | stdlib | All test files |
| `from assemblyzero.utils.metrics_models import *` | internal (new) | `metrics_config.py`, `metrics_aggregator.py`, `collect_cross_project_metrics.py` |
| `from assemblyzero.utils.metrics_config import load_config, ...` | internal (new) | `collect_cross_project_metrics.py`, tests |
| `from assemblyzero.utils.github_metrics_client import GitHubMetricsClient` | internal (new) | `metrics_aggregator.py`, `collect_cross_project_metrics.py`, tests |
| `from assemblyzero.utils.metrics_aggregator import MetricsAggregator` | internal (new) | `collect_cross_project_metrics.py`, tests |

**New Dependencies:** None. All packages (`pygithub`, `orjson`, `tenacity`) are already in `pyproject.toml`.

## 9. Test Mapping

| Test ID | Tests Function | File | Input Summary | Expected Output |
|---------|---------------|------|---------------|-----------------|
| T010 | `load_config()` | `test_metrics_config.py` | Explicit path to fixture | Valid config with 3 repos |
| T020 | `load_config()` | `test_metrics_config.py` | Env var path | Config from env var |
| T030 | `validate_config()` | `test_metrics_config.py` | `{"repos": []}` | `ValueError` |
| T040 | `validate_config()` | `test_metrics_config.py` | `{"repos": ["invalid"]}` | `ValueError` |
| T050 | `parse_repo_string()` | `test_metrics_config.py` | `"martymcenroe/AssemblyZero"` | Correct `TrackedRepoConfig` |
| T060 | `_filter_issues_only()` | `test_github_metrics_client.py` | 5 items (3 issues, 2 PRs) | 3 items |
| T070 | `fetch_repo_contents()` | `test_github_metrics_client.py` | Mock 404 | `[]` |
| T080 | `fetch_issues()` | `test_github_metrics_client.py` | Mock 429 then 200 | Success after retry |
| T090 | `collect_issue_metrics()` | `test_metrics_aggregator.py` | 3 mock issues | Correct counts, avg=18.0 |
| T100 | `collect_issue_metrics()` | `test_metrics_aggregator.py` | Empty list | All zeros, None avg |
| T110 | `collect_workflow_metrics()` | `test_metrics_aggregator.py` | Issues with workflow labels | Label counts match |
| T120 | `collect_workflow_metrics()` | `test_metrics_aggregator.py` | Mock content listing | lld_count=4, report_count=2 |
| T130 | `collect_gemini_metrics()` | `test_metrics_aggregator.py` | Mock verdict files | approvals=3, blocks=2, rate=0.6 |
| T140 | `collect_gemini_metrics()` | `test_metrics_aggregator.py` | Empty contents | All zeros, None rate |
| T150 | `aggregate()` | `test_metrics_aggregator.py` | 2 PerRepoMetrics | Correct summed totals |
| T160 | `aggregate()` | `test_metrics_aggregator.py` | 1 success, 1 failed | Failed listed, totals from success |
| T170 | `main()` | `test_collect_cross_project_metrics.py` | `dry_run=True` | Exit code 0, config printed |
| T180 | `main()` | `test_collect_cross_project_metrics.py` | 1 success, 1 exception | Exit code 1 |
| T190 | `main()` | `test_collect_cross_project_metrics.py` | All exceptions | Exit code 2 |
| T200 | `write_metrics_output()` | `test_collect_cross_project_metrics.py` | Valid metrics, tmp_path | Date-stamped file |
| T210 | `write_metrics_output()` | `test_collect_cross_project_metrics.py` | Valid metrics | `latest.json` exists |
| T220 | `format_summary_table()` | `test_collect_cross_project_metrics.py` | 2-repo metrics | Table with repos + TOTALS |
| T230 | `get_rate_limit_remaining()` | `test_github_metrics_client.py` | Mock remaining=50 | `{"remaining": 50}` |
| T240 | `_get_cache_key()` | `test_github_metrics_client.py` | Same params twice | Equal keys |
| T250 | `_is_cache_valid()` | `test_github_metrics_client.py` | Fresh cache entry | `True` |
| T260 | `_is_cache_valid()` | `test_github_metrics_client.py` | Expired entry | `False` |
| T270 | `parse_args()` | `test_collect_cross_project_metrics.py` | All flags | Correct namespace |
| T280 | `main()` | `test_collect_cross_project_metrics.py` | `verbose=True` | DEBUG logs emitted |
| T290 | `main()` | `test_collect_cross_project_metrics.py` | `lookback_days=7` | Config overridden |
| T300 | `write_metrics_output()` | `test_collect_cross_project_metrics.py` | Custom output_path | File at custom path |
| T310 | `_resolve_token()` | `test_github_metrics_client.py` | GITHUB_TOKEN env set | Token from env |
| T320 | `_resolve_token()` | `test_github_metrics_client.py` | GH_TOKEN fallback | Token from GH_TOKEN |
| T330 | `fetch_issues()` | `test_github_metrics_client.py` | Mock authenticated client | Issues returned |
| T340 | `fetch_issues()` | `test_github_metrics_client.py` | Mock 404 on private repo | `UnknownObjectException` |

## 10. Implementation Notes

### 10.1 Error Handling Convention

All public methods use the fault-isolation pattern: per-repo and per-subsystem errors are caught and logged, not propagated. The `collect_repo_metrics()` method catches exceptions from each sub-collector and returns zeroed defaults. The `main()` function catches per-repo exceptions and tracks them in `repos_failed`. Exit codes signal severity: 0=success, 1=partial, 2=total failure.

### 10.2 Logging Convention

Use Python's `logging` module throughout. Each module creates its own logger with `logger = logging.getLogger(__name__)`. Log levels:
- `DEBUG`: Cache hits/misses, token resolution, detailed API response info
- `INFO`: Per-repo collection status, rate limit status, output file path
- `WARNING`: Failed repo collection, low rate limit, missing directories
- `ERROR`: Configuration errors, total failure, output write failures

The `--verbose` flag sets root logger to `DEBUG`; default is `INFO`.

### 10.3 Constants

| Constant | Value | Location | Rationale |
|----------|-------|----------|-----------|
| `_REPO_PATTERN` | `r"^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$"` | `metrics_config.py` | Validates owner/name format |
| `_RATE_LIMIT_WARN_THRESHOLD` | `100` | `collect_cross_project_metrics.py` | Warn if fewer than 100 API calls remaining |
| `_ESTIMATED_CALLS_PER_REPO` | `10` | `collect_cross_project_metrics.py` | Budget estimation: 1 issues + ~4 contents + buffer |
| `_REQUIREMENTS_LABELS` | `{"requirements", "lld"}` | `metrics_aggregator.py` | Labels indicating requirements workflow usage |
| `_IMPLEMENTATION_LABELS` | `{"implementation"}` | `metrics_aggregator.py` | Labels indicating implementation workflow usage |
| `_TDD_LABELS` | `{"tdd", "testing"}` | `metrics_aggregator.py` | Labels indicating TDD workflow usage |
| Default `lookback_days` | `30` | `metrics_config.py` | Config default if not specified |
| Default `cache_ttl_seconds` | `300` | `metrics_config.py` | 5-minute cache TTL |
| Default `output_dir` | `"docs/metrics"` | `metrics_config.py` | Standard output directory |
| Retry config | `stop=3, wait=exp(1,30)` | `github_metrics_client.py` | 3 attempts, exponential backoff capped at 30s |

### 10.4 Directory Creation

The following directories need to exist before files can be created:
- `docs/metrics/` — created by adding `.gitkeep` (implementation order 1)
- `tests/fixtures/metrics/` — this is a new subdirectory; create it as part of fixture file creation

### 10.5 Python Path Considerations

`tools/collect_cross_project_metrics.py` imports from `assemblyzero.utils.*`. This works when run from the project root with `poetry run python tools/collect_cross_project_metrics.py` because poetry ensures the project is on `sys.path`. The `if __name__ == "__main__"` block uses this assumption.

For test files that import from `tools.collect_cross_project_metrics`, the `tools/` directory needs to be importable. This works because the project root (containing `tools/`) is typically on `sys.path` in the test environment. If needed, add a `tools/__init__.py` (empty) or adjust the import in tests to use `sys.path` manipulation — but prefer the simpler import approach first.

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3) — N/A, no Modify files
- [x] Every data structure has a concrete JSON/YAML example (Section 4) — All 8 TypedDicts have JSON examples
- [x] Every function has input/output examples with realistic values (Section 5) — All 22 functions specified
- [x] Change instructions are diff-level specific (Section 6) — Complete file contents for all 15 new files
- [x] Pattern references include file:line and are verified to exist (Section 7) — 4 patterns referenced
- [x] All imports are listed and verified (Section 8) — 26 imports mapped
- [x] Test mapping covers all LLD test scenarios (Section 9) — All 34 tests (T010–T340) mapped

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #333 |
| Verdict | DRAFT |
| Date | 2026-02-24 |
| Iterations | 1 |
| Finalized | — |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #333 |
| Verdict | APPROVED |
| Date | 2026-02-24 |
| Iterations | 0 |
| Finalized | 2026-02-24T20:34:51Z |

### Review Feedback Summary

Approved with suggestions:
1.  **Gemini Metrics Simplification:** The spec implementation of `collect_gemini_metrics` checks `docs/reports/` and `.gemini-reviews/` based on filename conventions, but omits the `docs/lld/active/*.md` embedded verdict check mentioned in the LLD. This is a reasonable simplification for V1 to avoid complex Markdown parsing, but strictly speaking, it diverges slightly from the LLD text. The provided code is concrete and functional, so no change is required for readine...


## Required File Paths (from LLD - do not deviate)

The following paths are specified in the LLD. Write ONLY to these paths:


Any files written to other paths will be rejected.

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
from assemblyzero.utils.metrics_models import *  # noqa: F401, F403


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
    Tests Function | File | Input Summary | Expected Output
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
    `load_config()` | `test_metrics_config.py` | Explicit path to fixture
    | Valid config with 3 repos
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
    `load_config()` | `test_metrics_config.py` | Env var path | Config
    from env var
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
    `validate_config()` | `test_metrics_config.py` | `{"repos": []}` |
    `ValueError`
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
    `validate_config()` | `test_metrics_config.py` | `{"repos":
    ["invalid"]}` | `ValueError`
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
    `parse_repo_string()` | `test_metrics_config.py` |
    `"martymcenroe/AssemblyZero"` | Correct `TrackedRepoConfig`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t050 works correctly
    assert False, 'TDD RED: test_t050 not implemented'


def test_t060():
    """
    `_filter_issues_only()` | `test_github_metrics_client.py` | 5 items
    (3 issues, 2 PRs) | 3 items
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
    `fetch_repo_contents()` | `test_github_metrics_client.py` | Mock 404
    | `[]`
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
    `fetch_issues()` | `test_github_metrics_client.py` | Mock 429 then
    200 | Success after retry
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
    `collect_issue_metrics()` | `test_metrics_aggregator.py` | 3 mock
    issues | Correct counts, avg=18.0
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t090 works correctly
    assert False, 'TDD RED: test_t090 not implemented'


def test_t100():
    """
    `collect_issue_metrics()` | `test_metrics_aggregator.py` | Empty list
    | All zeros, None avg
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t100 works correctly
    assert False, 'TDD RED: test_t100 not implemented'


def test_t110():
    """
    `collect_workflow_metrics()` | `test_metrics_aggregator.py` | Issues
    with workflow labels | Label counts match
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t110 works correctly
    assert False, 'TDD RED: test_t110 not implemented'


def test_t120(mock_external_service):
    """
    `collect_workflow_metrics()` | `test_metrics_aggregator.py` | Mock
    content listing | lld_count=4, report_count=2
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t120 works correctly
    assert False, 'TDD RED: test_t120 not implemented'


def test_t130(mock_external_service):
    """
    `collect_gemini_metrics()` | `test_metrics_aggregator.py` | Mock
    verdict files | approvals=3, blocks=2, rate=0.6
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
    `collect_gemini_metrics()` | `test_metrics_aggregator.py` | Empty
    contents | All zeros, None rate
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
    `aggregate()` | `test_metrics_aggregator.py` | 2 PerRepoMetrics |
    Correct summed totals
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
    `aggregate()` | `test_metrics_aggregator.py` | 1 success, 1 failed |
    Failed listed, totals from success
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
    `main()` | `test_collect_cross_project_metrics.py` | `dry_run=True` |
    Exit code 0, config printed
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
    `main()` | `test_collect_cross_project_metrics.py` | 1 success, 1
    exception | Exit code 1
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
    `main()` | `test_collect_cross_project_metrics.py` | All exceptions |
    Exit code 2
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
    `write_metrics_output()` | `test_collect_cross_project_metrics.py` |
    Valid metrics, tmp_path | Date-stamped file
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
    `write_metrics_output()` | `test_collect_cross_project_metrics.py` |
    Valid metrics | `latest.json` exists
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
    `format_summary_table()` | `test_collect_cross_project_metrics.py` |
    Table with repos + TOTALS
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t220 works correctly
    assert False, 'TDD RED: test_t220 not implemented'


def test_t230(mock_external_service):
    """
    `get_rate_limit_remaining()` | `test_github_metrics_client.py` | Mock
    remaining=50 | `{"remaining": 50}`
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
    `_get_cache_key()` | `test_github_metrics_client.py` | Same params
    twice | Equal keys
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
    `_is_cache_valid()` | `test_github_metrics_client.py` | Fresh cache
    entry | `True`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t250 works correctly
    assert False, 'TDD RED: test_t250 not implemented'


def test_t260():
    """
    `_is_cache_valid()` | `test_github_metrics_client.py` | Expired entry
    | `False`
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
    `parse_args()` | `test_collect_cross_project_metrics.py` | All flags
    | Correct namespace
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
    `main()` | `test_collect_cross_project_metrics.py` | `verbose=True` |
    DEBUG logs emitted
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
    `main()` | `test_collect_cross_project_metrics.py` |
    `lookback_days=7` | Config overridden
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
    `write_metrics_output()` | `test_collect_cross_project_metrics.py` |
    Custom output_path | File at custom path
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
    `_resolve_token()` | `test_github_metrics_client.py` | GITHUB_TOKEN
    env set | Token from env
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t310 works correctly
    assert False, 'TDD RED: test_t310 not implemented'


def test_t320():
    """
    `_resolve_token()` | `test_github_metrics_client.py` | GH_TOKEN
    fallback | Token from GH_TOKEN
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t320 works correctly
    assert False, 'TDD RED: test_t320 not implemented'


def test_t330(mock_external_service):
    """
    `fetch_issues()` | `test_github_metrics_client.py` | Mock
    authenticated client | Issues returned
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t330 works correctly
    assert False, 'TDD RED: test_t330 not implemented'


def test_t340(mock_external_service):
    """
    `fetch_issues()` | `test_github_metrics_client.py` | Mock 404 on
    private repo | `UnknownObjectException`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t340 works correctly
    assert False, 'TDD RED: test_t340 not implemented'




```

## Previously Implemented Files

These files have already been implemented. Use them for imports and references:

### docs/metrics/.gitkeep (full)

```python

```

## Previous Attempt Failed

The previous implementation had this error:

```
============================= test session starts =============================
platform win32 -- Python 3.14.0, pytest-9.0.2, pluggy-1.6.0 -- C:\Users\mcwiz\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Scripts\python.exe
cachedir: .pytest_cache
benchmark: 5.2.3 (defaults: timer=time.perf_counter disable_gc=False min_rounds=5 min_time=0.000005 max_time=1.0 calibration_precision=10 warmup=False warmup_iterations=100000)
rootdir: C:\Users\mcwiz\Projects\AssemblyZero
configfile: pyproject.toml
plugins: anyio-4.12.1, langsmith-0.6.9, benchmark-5.2.3, cov-7.0.0
collecting ... collected 35 items

tests/test_issue_333.py::test_id FAILED                                  [  2%]
tests/test_issue_333.py::test_t010 FAILED                                [  5%]
tests/test_issue_333.py::test_t020 FAILED                                [  8%]
tests/test_issue_333.py::test_t030 FAILED                                [ 11%]
tests/test_issue_333.py::test_t040 FAILED                                [ 14%]
tests/test_issue_333.py::test_t050 FAILED                                [ 17%]
tests/test_issue_333.py::test_t060 FAILED                                [ 20%]
tests/test_issue_333.py::test_t070 FAILED                                [ 22%]
tests/test_issue_333.py::test_t080 FAILED                                [ 25%]
tests/test_issue_333.py::test_t090 FAILED                                [ 28%]
tests/test_issue_333.py::test_t100 FAILED                                [ 31%]
tests/test_issue_333.py::test_t110 FAILED                                [ 34%]
tests/test_issue_333.py::test_t120 FAILED                                [ 37%]
tests/test_issue_333.py::test_t130 FAILED                                [ 40%]
tests/test_issue_333.py::test_t140 FAILED                                [ 42%]
tests/test_issue_333.py::test_t150 FAILED                                [ 45%]
tests/test_issue_333.py::test_t160 FAILED                                [ 48%]
tests/test_issue_333.py::test_t170 FAILED                                [ 51%]
tests/test_issue_333.py::test_t180 FAILED                                [ 54%]
tests/test_issue_333.py::test_t190 FAILED                                [ 57%]
tests/test_issue_333.py::test_t200 FAILED                                [ 60%]
tests/test_issue_333.py::test_t210 FAILED                                [ 62%]
tests/test_issue_333.py::test_t220 FAILED                                [ 65%]
tests/test_issue_333.py::test_t230 FAILED                                [ 68%]
tests/test_issue_333.py::test_t240 FAILED                                [ 71%]
tests/test_issue_333.py::test_t250 FAILED                                [ 74%]
tests/test_issue_333.py::test_t260 FAILED                                [ 77%]
tests/test_issue_333.py::test_t270 FAILED                                [ 80%]
tests/test_issue_333.py::test_t280 FAILED                                [ 82%]
tests/test_issue_333.py::test_t290 FAILED                                [ 85%]
tests/test_issue_333.py::test_t300 FAILED                                [ 88%]
tests/test_issue_333.py::test_t310 FAILED                                [ 91%]
tests/test_issue_333.py::test_t320 FAILED                                [ 94%]
tests/test_issue_333.py::test_t330 FAILED                                [ 97%]
tests/test_issue_333.py::test_t340 FAILED                                [100%]

================================== FAILURES ===================================
___________________________________ test_id ___________________________________
tests\test_issue_333.py:37: in test_id
    assert False, 'TDD RED: test_id not implemented'
E   AssertionError: TDD RED: test_id not implemented
E   assert False
__________________________________ test_t010 __________________________________
tests\test_issue_333.py:53: in test_t010
    assert False, 'TDD RED: test_t010 not implemented'
E   AssertionError: TDD RED: test_t010 not implemented
E   assert False
__________________________________ test_t020 __________________________________
tests\test_issue_333.py:69: in test_t020
    assert False, 'TDD RED: test_t020 not implemented'
E   AssertionError: TDD RED: test_t020 not implemented
E   assert False
__________________________________ test_t030 __________________________________
tests\test_issue_333.py:85: in test_t030
    assert False, 'TDD RED: test_t030 not implemented'
E   AssertionError: TDD RED: test_t030 not implemented
E   assert False
__________________________________ test_t040 __________________________________
tests\test_issue_333.py:101: in test_t040
    assert False, 'TDD RED: test_t040 not implemented'
E   AssertionError: TDD RED: test_t040 not implemented
E   assert False
__________________________________ test_t050 __________________________________
tests\test_issue_333.py:117: in test_t050
    assert False, 'TDD RED: test_t050 not implemented'
E   AssertionError: TDD RED: test_t050 not implemented
E   assert False
__________________________________ test_t060 __________________________________
tests\test_issue_333.py:133: in test_t060
    assert False, 'TDD RED: test_t060 not implemented'
E   AssertionError: TDD RED: test_t060 not implemented
E   assert False
__________________________________ test_t070 __________________________________
tests\test_issue_333.py:149: in test_t070
    assert False, 'TDD RED: test_t070 not implemented'
E   AssertionError: TDD RED: test_t070 not implemented
E   assert False
__________________________________ test_t080 __________________________________
tests\test_issue_333.py:165: in test_t080
    assert False, 'TDD RED: test_t080 not implemented'
E   AssertionError: TDD RED: test_t080 not implemented
E   assert False
__________________________________ test_t090 __________________________________
tests\test_issue_333.py:181: in test_t090
    assert False, 'TDD RED: test_t090 not implemented'
E   AssertionError: TDD RED: test_t090 not implemented
E   assert False
__________________________________ test_t100 __________________________________
tests\test_issue_333.py:197: in test_t100
    assert False, 'TDD RED: test_t100 not implemented'
E   AssertionError: TDD RED: test_t100 not implemented
E   assert False
__________________________________ test_t110 __________________________________
tests\test_issue_333.py:213: in test_t110
    assert False, 'TDD RED: test_t110 not implemented'
E   AssertionError: TDD RED: test_t110 not implemented
E   assert False
__________________________________ test_t120 __________________________________
tests\test_issue_333.py:229: in test_t120
    assert False, 'TDD RED: test_t120 not implemented'
E   AssertionError: TDD RED: test_t120 not implemented
E   assert False
__________________________________ test_t130 __________________________________
tests\test_issue_333.py:245: in test_t130
    assert False, 'TDD RED: test_t130 not implemented'
E   AssertionError: TDD RED: test_t130 not implemented
E   assert False
__________________________________ test_t140 __________________________________
tests\test_issue_333.py:261: in test_t140
    assert False, 'TDD RED: test_t140 not implemented'
E   AssertionError: TDD RED: test_t140 not implemented
E   assert False
__________________________________ test_t150 __________________________________
tests\test_issue_333.py:277: in test_t150
    assert False, 'TDD RED: test_t150 not implemented'
E   AssertionError: TDD RED: test_t150 not implemented
E   assert False
__________________________________ test_t160 __________________________________
tests\test_issue_333.py:293: in test_t160
    assert False, 'TDD RED: test_t160 not implemented'
E   AssertionError: TDD RED: test_t160 not implemented
E   assert False
__________________________________ test_t170 __________________________________
tests\test_issue_333.py:309: in test_t170
    assert False, 'TDD RED: test_t170 not implemented'
E   AssertionError: TDD RED: test_t170 not implemented
E   assert False
__________________________________ test_t180 __________________________________
tests\test_issue_333.py:325: in test_t180
    assert False, 'TDD RED: test_t180 not implemented'
E   AssertionError: TDD RED: test_t180 not implemented
E   assert False
__________________________________ test_t190 __________________________________
tests\test_issue_333.py:341: in test_t190
    assert False, 'TDD RED: test_t190 not implemented'
E   AssertionError: TDD RED: test_t190 not implemented
E   assert False
__________________________________ test_t200 __________________________________
tests\test_issue_333.py:357: in test_t200
    assert False, 'TDD RED: test_t200 not implemented'
E   AssertionError: TDD RED: test_t200 not implemented
E   assert False
__________________________________ test_t210 __________________________________
tests\test_issue_333.py:373: in test_t210
    assert False, 'TDD RED: test_t210 not implemented'
E   AssertionError: TDD RED: test_t210 not implemented
E   assert False
__________________________________ test_t220 __________________________________
tests\test_issue_333.py:389: in test_t220
    assert False, 'TDD RED: test_t220 not implemented'
E   AssertionError: TDD RED: test_t220 not implemented
E   assert False
__________________________________ test_t230 __________________________________
tests\test_issue_333.py:405: in test_t230
    assert False, 'TDD RED: test_t230 not implemented'
E   AssertionError: TDD RED: test_t230 not implemented
E   assert False
__________________________________ test_t240 __________________________________
tests\test_issue_333.py:421: in test_t240
    assert False, 'TDD RED: test_t240 not implemented'
E   AssertionError: TDD RED: test_t240 not implemented
E   assert False
__________________________________ test_t250 __________________________________
tests\test_issue_333.py:437: in test_t250
    assert False, 'TDD RED: test_t250 not implemented'
E   AssertionError: TDD RED: test_t250 not implemented
E   assert False
__________________________________ test_t260 __________________________________
tests\test_issue_333.py:453: in test_t260
    assert False, 'TDD RED: test_t260 not implemented'
E   AssertionError: TDD RED: test_t260 not implemented
E   assert False
__________________________________ test_t270 __________________________________
tests\test_issue_333.py:469: in test_t270
    assert False, 'TDD RED: test_t270 not implemented'
E   AssertionError: TDD RED: test_t270 not implemented
E   assert False
__________________________________ test_t280 __________________________________
tests\test_issue_333.py:485: in test_t280
    assert False, 'TDD RED: test_t280 not implemented'
E   AssertionError: TDD RED: test_t280 not implemented
E   assert False
__________________________________ test_t290 __________________________________
tests\test_issue_333.py:501: in test_t290
    assert False, 'TDD RED: test_t290 not implemented'
E   AssertionError: TDD RED: test_t290 not implemented
E   assert False
__________________________________ test_t300 __________________________________
tests\test_issue_333.py:517: in test_t300
    assert False, 'TDD RED: test_t300 not implemented'
E   AssertionError: TDD RED: test_t300 not implemented
E   assert False
__________________________________ test_t310 __________________________________
tests\test_issue_333.py:533: in test_t310
    assert False, 'TDD RED: test_t310 not implemented'
E   AssertionError: TDD RED: test_t310 not implemented
E   assert False
__________________________________ test_t320 __________________________________
tests\test_issue_333.py:549: in test_t320
    assert False, 'TDD RED: test_t320 not implemented'
E   AssertionError: TDD RED: test_t320 not implemented
E   assert False
__________________________________ test_t330 __________________________________
tests\test_issue_333.py:565: in test_t330
    assert False, 'TDD RED: test_t330 not implemented'
E   AssertionError: TDD RED: test_t330 not implemented
E   assert False
__________________________________ test_t340 __________________________________
tests\test_issue_333.py:581: in test_t340
    assert False, 'TDD RED: test_t340 not implemented'
E   AssertionError: TDD RED: test_t340 not implemented
E   assert False
=============================== tests coverage ================================
_______________ coverage: platform win32, python 3.14.0-final-0 _______________

Name                                   Stmts   Miss  Cover   Missing
--------------------------------------------------------------------
assemblyzero\utils\metrics_models.py      59      0   100%
--------------------------------------------------------------------
TOTAL                                     59      0   100%
Required test coverage of 95% reached. Total coverage: 100.00%
=========================== short test summary info ===========================
FAILED tests/test_issue_333.py::test_id - AssertionError: TDD RED: test_id no...
FAILED tests/test_issue_333.py::test_t010 - AssertionError: TDD RED: test_t01...
FAILED tests/test_issue_333.py::test_t020 - AssertionError: TDD RED: test_t02...
FAILED tests/test_issue_333.py::test_t030 - AssertionError: TDD RED: test_t03...
FAILED tests/test_issue_333.py::test_t040 - AssertionError: TDD RED: test_t04...
FAILED tests/test_issue_333.py::test_t050 - AssertionError: TDD RED: test_t05...
FAILED tests/test_issue_333.py::test_t060 - AssertionError: TDD RED: test_t06...
FAILED tests/test_issue_333.py::test_t070 - AssertionError: TDD RED: test_t07...
FAILED tests/test_issue_333.py::test_t080 - AssertionError: TDD RED: test_t08...
FAILED tests/test_issue_333.py::test_t090 - AssertionError: TDD RED: test_t09...
FAILED tests/test_issue_333.py::test_t100 - AssertionError: TDD RED: test_t10...
FAILED tests/test_issue_333.py::test_t110 - AssertionError: TDD RED: test_t11...
FAILED tests/test_issue_333.py::test_t120 - AssertionError: TDD RED: test_t12...
FAILED tests/test_issue_333.py::test_t130 - AssertionError: TDD RED: test_t13...
FAILED tests/test_issue_333.py::test_t140 - AssertionError: TDD RED: test_t14...
FAILED tests/test_issue_333.py::test_t150 - AssertionError: TDD RED: test_t15...
FAILED tests/test_issue_333.py::test_t160 - AssertionError: TDD RED: test_t16...
FAILED tests/test_issue_333.py::test_t170 - AssertionError: TDD RED: test_t17...
FAILED tests/test_issue_333.py::test_t180 - AssertionError: TDD RED: test_t18...
FAILED tests/test_issue_333.py::test_t190 - AssertionError: TDD RED: test_t19...
FAILED tests/test_issue_333.py::test_t200 - AssertionError: TDD RED: test_t20...
FAILED tests/test_issue_333.py::test_t210 - AssertionError: TDD RED: test_t21...
FAILED tests/test_issue_333.py::test_t220 - AssertionError: TDD RED: test_t22...
FAILED tests/test_issue_333.py::test_t230 - AssertionError: TDD RED: test_t23...
FAILED tests/test_issue_333.py::test_t240 - AssertionError: TDD RED: test_t24...
FAILED tests/test_issue_333.py::test_t250 - AssertionError: TDD RED: test_t25...
FAILED tests/test_issue_333.py::test_t260 - AssertionError: TDD RED: test_t26...
FAILED tests/test_issue_333.py::test_t270 - AssertionError: TDD RED: test_t27...
FAILED tests/test_issue_333.py::test_t280 - AssertionError: TDD RED: test_t28...
FAILED tests/test_issue_333.py::test_t290 - AssertionError: TDD RED: test_t29...
FAILED tests/test_issue_333.py::test_t300 - AssertionError: TDD RED: test_t30...
FAILED tests/test_issue_333.py::test_t310 - AssertionError: TDD RED: test_t31...
FAILED tests/test_issue_333.py::test_t320 - AssertionError: TDD RED: test_t32...
FAILED tests/test_issue_333.py::test_t330 - AssertionError: TDD RED: test_t33...
FAILED tests/test_issue_333.py::test_t340 - AssertionError: TDD RED: test_t34...
============================= 35 failed in 0.14s ==============================


```

Fix the issue in your implementation.



## Previous Attempt Failed (Attempt 2/3)

Your previous response had an error:

```
No code block found in response
```

Please fix this issue and provide the corrected, complete file contents.
IMPORTANT: Output the ENTIRE file, not just the fix.

## Output Format

Output ONLY the file contents. No explanations, no markdown headers, just the code.

```python
# Your implementation here
```

IMPORTANT:
- Output the COMPLETE file contents
- Do NOT output a summary or description
- Do NOT say "I've implemented..."
- Just output the code in a single code block
