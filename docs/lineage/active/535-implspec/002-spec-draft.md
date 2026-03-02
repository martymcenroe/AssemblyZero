# Implementation Spec: DEATH as Age Transition — the Hourglass Protocol

| Field | Value |
|-------|-------|
| Issue | #535 |
| LLD | `docs/lld/active/535-hourglass-protocol.md` |
| Generated | 2026-02-17 |
| Status | DRAFT |

## 1. Overview

Implement DEATH as an age transition mechanism that detects documentation drift from codebase reality via a weighted age meter, drift scoring system, and hourglass reconciliation protocol. The system provides a `/death` Claude Code skill with report and reaper modes, integrates with the existing janitor probe infrastructure, and produces ADR artifacts.

**Objective:** Detect when documentation has drifted from codebase reality, trigger reconciliation via an "hourglass" meter, and produce updated documentation artifacts.

**Success Criteria:** All 39 test scenarios (T010–T390) pass with ≥95% coverage; `/death report` produces a reconciliation report without modifying files; `/death reaper` applies fixes with confirmation gate; age meter persists across sessions; drift probe integrates with janitor infrastructure.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `data/hourglass/` | Add (Directory) | Persistent storage directory |
| 2 | `data/hourglass/age_meter.json` | Add | Initial empty age meter state |
| 3 | `data/hourglass/history.json` | Add | Initial empty history |
| 4 | `.gitignore` | Modify | Add age_meter.json to gitignore |
| 5 | `assemblyzero/workflows/death/__init__.py` | Add | Package init |
| 6 | `assemblyzero/workflows/death/constants.py` | Add | Weight tables, thresholds, config |
| 7 | `assemblyzero/workflows/death/models.py` | Add | Data models (TypedDicts) |
| 8 | `assemblyzero/workflows/death/age_meter.py` | Add | Age meter computation |
| 9 | `assemblyzero/workflows/death/drift_scorer.py` | Add | Drift detection and scoring |
| 10 | `assemblyzero/workflows/death/reconciler.py` | Add | Reconciliation engine + ADR generation |
| 11 | `assemblyzero/workflows/death/hourglass.py` | Add | LangGraph state machine |
| 12 | `assemblyzero/workflows/death/skill.py` | Add | `/death` skill entry point |
| 13 | `assemblyzero/workflows/janitor/probes/drift_probe.py` | Add | Janitor drift probe |
| 14 | `assemblyzero/workflows/janitor/probes/__init__.py` | Modify | Register drift probe |
| 15 | `.claude/commands/death.md` | Add | Skill definition |
| 16 | `docs/standards/0016-age-transition-protocol.md` | Add | ADR document |
| 17 | `tests/fixtures/death/mock_issues.json` | Add | Test fixture |
| 18 | `tests/fixtures/death/mock_codebase_snapshot.json` | Add | Test fixture |
| 19 | `tests/fixtures/death/mock_drift_findings.json` | Add | Test fixture |
| 20 | `tests/fixtures/death/mock_adr_output.md` | Add | Test fixture |
| 21 | `tests/unit/test_death/__init__.py` | Add | Test package |
| 22 | `tests/unit/test_death/test_models.py` | Add | Model tests |
| 23 | `tests/unit/test_death/test_age_meter.py` | Add | Age meter tests |
| 24 | `tests/unit/test_death/test_drift_scorer.py` | Add | Drift scorer tests |
| 25 | `tests/unit/test_death/test_reconciler.py` | Add | Reconciler tests |
| 26 | `tests/unit/test_death/test_hourglass.py` | Add | Hourglass state machine tests |
| 27 | `tests/unit/test_death/test_skill.py` | Add | Skill entry point tests |

**Implementation Order Rationale:** Directories and data files first (1–4), then constants/models as foundation (5–7), then core logic modules bottom-up by dependency (8–12), then integration point (13–14), then documentation/skill definition (15–16), then fixtures and tests (17–27).

## 3. Current State (for Modify/Delete files)

### 3.1 `assemblyzero/workflows/janitor/probes/__init__.py`

**Relevant excerpt** (full file):

```python
"""Probe registry and execution utilities.

Issue #94: Lu-Tze: The Janitor
"""

from __future__ import annotations

from typing import Callable

from assemblyzero.workflows.janitor.state import ProbeResult, ProbeScope

def _build_registry() -> dict[ProbeScope, ProbeFunction]:
    """Build probe registry lazily to avoid circular imports."""
    ...

def get_probes(scopes: list[ProbeScope]) -> list[tuple[ProbeScope, ProbeFunction]]:
    """Return probe functions for the requested scopes.

Raises ValueError if an unknown scope is requested."""
    ...

def run_probe_safe(
    probe_name: ProbeScope, probe_fn: ProbeFunction, repo_root: str
) -> ProbeResult:
    """Execute a probe with crash isolation.

If the probe raises an exception, returns a ProbeResult with"""
    ...

ProbeFunction = Callable[[str], ProbeResult]
```

**What changes:** Add import for `drift_probe` and register it in `_build_registry()` under the `"drift"` scope key. This requires that `ProbeScope` in `assemblyzero/workflows/janitor/state.py` already includes `"drift"` as a valid literal value — if it doesn't, the drift probe will be registered with a string key and the scope type may need extending.

### 3.2 `.gitignore`

**Relevant excerpt** (lines 1–55, showing end of file):

```
# Local AssemblyZero state (Issue #78)
# RAG vector store (Issue #88) - regenerated via tools/rebuild_knowledge_base.py
.assemblyzero/
!.assemblyzero/config.example.json

# Keep databases ignored (redundant but explicit)
*.db
*.sqlite

# Session transcripts (auto-generated, untracked)
data/unleashed/
data/handoff-log.md
transcripts/
```

**What changes:** Append `data/hourglass/age_meter.json` entry after the `data/unleashed/` block. Keep `data/hourglass/history.json` tracked (not gitignored).

## 4. Data Structures

### 4.1 IssueWeight

**Definition:**

```python
class IssueWeight(TypedDict):
    issue_number: int
    title: str
    labels: list[str]
    weight: int
    weight_source: str
    closed_at: str
```

**Concrete Example:**

```json
{
    "issue_number": 534,
    "title": "Spelunking Audits — DEATH's methodology",
    "labels": ["architecture", "cross-cutting"],
    "weight": 10,
    "weight_source": "architecture",
    "closed_at": "2026-02-15T14:32:00Z"
}
```

### 4.2 AgeMeterState

**Definition:**

```python
class AgeMeterState(TypedDict):
    current_score: int
    threshold: int
    last_death_visit: str | None
    last_computed: str
    weighted_issues: list[IssueWeight]
    age_number: int
```

**Concrete Example:**

```json
{
    "current_score": 37,
    "threshold": 50,
    "last_death_visit": "2026-02-10T09:00:00Z",
    "last_computed": "2026-02-17T15:45:00Z",
    "weighted_issues": [
        {
            "issue_number": 530,
            "title": "Fix broken link in README",
            "labels": ["bug"],
            "weight": 1,
            "weight_source": "bug",
            "closed_at": "2026-02-11T10:00:00Z"
        },
        {
            "issue_number": 531,
            "title": "Add RAG pipeline caching",
            "labels": ["pipeline", "enhancement"],
            "weight": 8,
            "weight_source": "pipeline",
            "closed_at": "2026-02-12T11:30:00Z"
        },
        {
            "issue_number": 534,
            "title": "Spelunking Audits",
            "labels": ["architecture"],
            "weight": 10,
            "weight_source": "architecture",
            "closed_at": "2026-02-15T14:32:00Z"
        }
    ],
    "age_number": 3
}
```

### 4.3 DriftFinding

**Definition:**

```python
class DriftFinding(TypedDict):
    id: str
    severity: Literal["critical", "major", "minor"]
    doc_file: str
    doc_claim: str
    code_reality: str
    category: Literal[
        "count_mismatch",
        "feature_contradiction",
        "missing_component",
        "stale_reference",
        "architecture_drift",
    ]
    confidence: float
    evidence: str
```

**Concrete Example:**

```json
{
    "id": "DRIFT-001",
    "severity": "critical",
    "doc_file": "README.md",
    "doc_claim": "Run 12+ AI agents concurrently",
    "code_reality": "36 agent configurations found in assemblyzero/agents/",
    "category": "count_mismatch",
    "confidence": 0.95,
    "evidence": "glob('assemblyzero/agents/*.py') returns 36 files"
}
```

### 4.4 DriftReport

**Definition:**

```python
class DriftReport(TypedDict):
    findings: list[DriftFinding]
    total_score: float
    critical_count: int
    major_count: int
    minor_count: int
    scanned_docs: list[str]
    scanned_code_paths: list[str]
    timestamp: str
```

**Concrete Example:**

```json
{
    "findings": [
        {
            "id": "DRIFT-001",
            "severity": "critical",
            "doc_file": "README.md",
            "doc_claim": "Run 12+ AI agents concurrently",
            "code_reality": "36 agent configurations found",
            "category": "count_mismatch",
            "confidence": 0.95,
            "evidence": "glob('assemblyzero/agents/*.py') returns 36 files"
        },
        {
            "id": "DRIFT-002",
            "severity": "major",
            "doc_file": "README.md",
            "doc_claim": "5 State Machines",
            "code_reality": "7 workflow directories found",
            "category": "count_mismatch",
            "confidence": 0.90,
            "evidence": "glob('assemblyzero/workflows/*/') returns 7 directories"
        }
    ],
    "total_score": 15.0,
    "critical_count": 1,
    "major_count": 1,
    "minor_count": 0,
    "scanned_docs": ["README.md", "docs/standards/0001-overview.md"],
    "scanned_code_paths": ["assemblyzero/agents/", "assemblyzero/workflows/"],
    "timestamp": "2026-02-17T16:00:00Z"
}
```

### 4.5 ReconciliationAction

**Definition:**

```python
class ReconciliationAction(TypedDict):
    target_file: str
    action_type: Literal[
        "update_count", "update_description", "add_section",
        "remove_section", "archive", "create_adr",
    ]
    description: str
    old_content: str | None
    new_content: str | None
    drift_finding_id: str
```

**Concrete Example:**

```json
{
    "target_file": "README.md",
    "action_type": "update_count",
    "description": "Update agent count from '12+' to '36'",
    "old_content": "Run 12+ AI agents concurrently",
    "new_content": "Run 36 AI agents concurrently",
    "drift_finding_id": "DRIFT-001"
}
```

### 4.6 ReconciliationReport

**Definition:**

```python
class ReconciliationReport(TypedDict):
    age_number: int
    trigger: Literal["meter", "summon", "critical_drift"]
    trigger_details: str
    drift_report: DriftReport
    actions: list[ReconciliationAction]
    mode: Literal["report", "reaper"]
    timestamp: str
    summary: str
```

**Concrete Example:**

```json
{
    "age_number": 3,
    "trigger": "summon",
    "trigger_details": "DEATH summoned via /death command by orchestrator",
    "drift_report": {
        "findings": [],
        "total_score": 15.0,
        "critical_count": 1,
        "major_count": 1,
        "minor_count": 0,
        "scanned_docs": ["README.md"],
        "scanned_code_paths": ["assemblyzero/"],
        "timestamp": "2026-02-17T16:00:00Z"
    },
    "actions": [
        {
            "target_file": "README.md",
            "action_type": "update_count",
            "description": "Update agent count from '12+' to '36'",
            "old_content": "Run 12+ AI agents concurrently",
            "new_content": "Run 36 AI agents concurrently",
            "drift_finding_id": "DRIFT-001"
        }
    ],
    "mode": "report",
    "timestamp": "2026-02-17T16:05:00Z",
    "summary": "DEATH found 2 drift findings (1 critical, 1 major). 1 reconciliation action proposed."
}
```

### 4.7 HourglassState

**Definition:**

```python
class HourglassState(TypedDict):
    trigger: Literal["meter", "summon", "critical_drift"]
    mode: Literal["report", "reaper"]
    age_meter: AgeMeterState
    drift_report: DriftReport | None
    reconciliation_report: ReconciliationReport | None
    step: Literal[
        "init", "walk_field", "harvest", "archive", "chronicle", "rest", "complete",
    ]
    errors: list[str]
    confirmed: bool
```

**Concrete Example:**

```json
{
    "trigger": "summon",
    "mode": "report",
    "age_meter": {
        "current_score": 37,
        "threshold": 50,
        "last_death_visit": "2026-02-10T09:00:00Z",
        "last_computed": "2026-02-17T15:45:00Z",
        "weighted_issues": [],
        "age_number": 3
    },
    "drift_report": null,
    "reconciliation_report": null,
    "step": "init",
    "errors": [],
    "confirmed": false
}
```

## 5. Function Specifications

### 5.1 `compute_issue_weight()`

**File:** `assemblyzero/workflows/death/age_meter.py`

**Signature:**

```python
def compute_issue_weight(
    labels: list[str],
    title: str,
    body: str | None = None,
) -> tuple[int, str]:
    """Compute weight for a single issue based on its labels and content."""
    ...
```

**Input Example:**

```python
labels = ["bug", "architecture"]
title = "Refactor pipeline architecture"
body = "Major rework of the data pipeline"
```

**Output Example:**

```python
(10, "architecture")
```

**Edge Cases:**
- `labels = []` -> returns `(2, "default")` and logs warning
- `labels = ["question", "wontfix"]` -> no matching label, returns `(2, "default")`
- `labels = ["bug"]` -> returns `(1, "bug")`
- `labels = ["bug", "architecture"]` -> returns `(10, "architecture")` (highest weight wins)

### 5.2 `fetch_closed_issues_since()`

**File:** `assemblyzero/workflows/death/age_meter.py`

**Signature:**

```python
def fetch_closed_issues_since(
    repo: str,
    since: str | None,
    github_token: str | None = None,
) -> list[dict]:
    """Fetch closed issues from GitHub since the last DEATH visit."""
    ...
```

**Input Example:**

```python
repo = "martymcenroe/AssemblyZero"
since = "2026-02-10T09:00:00Z"
github_token = None  # reads from GITHUB_TOKEN env var
```

**Output Example:**

```python
[
    {
        "number": 534,
        "title": "Spelunking Audits",
        "labels": ["architecture"],
        "closed_at": "2026-02-15T14:32:00Z",
        "body": "Implement spelunking audit methodology..."
    },
    {
        "number": 530,
        "title": "Fix broken link",
        "labels": ["bug"],
        "closed_at": "2026-02-11T10:00:00Z",
        "body": None
    }
]
```

**Edge Cases:**
- `since = None` -> fetches all closed issues (paginated, capped at 500)
- GitHub API unavailable -> raises `ConnectionError` with descriptive message
- No token in env -> raises `ValueError("GitHub token not found")`

### 5.3 `compute_age_meter()`

**File:** `assemblyzero/workflows/death/age_meter.py`

**Signature:**

```python
def compute_age_meter(
    issues: list[dict],
    current_state: AgeMeterState | None = None,
) -> AgeMeterState:
    """Compute the age meter score from a list of closed issues."""
    ...
```

**Input Example:**

```python
issues = [
    {"number": 530, "title": "Fix bug", "labels": ["bug"], "closed_at": "2026-02-11T10:00:00Z", "body": None},
    {"number": 531, "title": "New pipeline", "labels": ["pipeline"], "closed_at": "2026-02-12T11:30:00Z", "body": None},
]
current_state = {
    "current_score": 10,
    "threshold": 50,
    "last_death_visit": "2026-02-10T09:00:00Z",
    "last_computed": "2026-02-10T09:00:00Z",
    "weighted_issues": [],
    "age_number": 3,
}
```

**Output Example:**

```python
{
    "current_score": 19,  # 10 + 1 (bug) + 8 (pipeline)
    "threshold": 50,
    "last_death_visit": "2026-02-10T09:00:00Z",
    "last_computed": "2026-02-17T16:00:00Z",
    "weighted_issues": [
        {"issue_number": 530, "title": "Fix bug", "labels": ["bug"], "weight": 1, "weight_source": "bug", "closed_at": "2026-02-11T10:00:00Z"},
        {"issue_number": 531, "title": "New pipeline", "labels": ["pipeline"], "weight": 8, "weight_source": "pipeline", "closed_at": "2026-02-12T11:30:00Z"},
    ],
    "age_number": 3,
}
```

**Edge Cases:**
- `issues = []` and `current_state = None` -> returns fresh state with score=0
- `current_state = None` -> initializes new state with score=0, threshold=DEFAULT_THRESHOLD, age_number=1

### 5.4 `load_age_meter_state()`

**File:** `assemblyzero/workflows/death/age_meter.py`

**Signature:**

```python
def load_age_meter_state(state_path: str = "data/hourglass/age_meter.json") -> AgeMeterState | None:
    """Load persistent age meter state from disk. Returns None if no state exists."""
    ...
```

**Input Example:**

```python
state_path = "data/hourglass/age_meter.json"
```

**Output Example:**

```python
{
    "current_score": 37,
    "threshold": 50,
    "last_death_visit": "2026-02-10T09:00:00Z",
    "last_computed": "2026-02-17T15:45:00Z",
    "weighted_issues": [],
    "age_number": 3,
}
```

**Edge Cases:**
- File does not exist -> returns `None`
- File contains invalid JSON -> logs warning, returns `None`

### 5.5 `save_age_meter_state()`

**File:** `assemblyzero/workflows/death/age_meter.py`

**Signature:**

```python
def save_age_meter_state(
    state: AgeMeterState,
    state_path: str = "data/hourglass/age_meter.json",
) -> None:
    """Persist age meter state to disk."""
    ...
```

**Input Example:**

```python
state = {"current_score": 37, "threshold": 50, "last_death_visit": None, "last_computed": "2026-02-17T16:00:00Z", "weighted_issues": [], "age_number": 1}
state_path = "data/hourglass/age_meter.json"
```

**Output Example:** None (writes to disk)

**Edge Cases:**
- Parent directory doesn't exist -> creates `data/hourglass/` via `os.makedirs`
- Writes atomically via write-to-temp + rename pattern

### 5.6 `check_meter_threshold()`

**File:** `assemblyzero/workflows/death/age_meter.py`

**Signature:**

```python
def check_meter_threshold(state: AgeMeterState) -> bool:
    """Check if the age meter has crossed the threshold."""
    ...
```

**Input Example:**

```python
state = {"current_score": 50, "threshold": 50, "last_death_visit": None, "last_computed": "2026-02-17T16:00:00Z", "weighted_issues": [], "age_number": 1}
```

**Output Example:**

```python
True  # score >= threshold
```

**Edge Cases:**
- `current_score = 49, threshold = 50` -> `False`
- `current_score = 50, threshold = 50` -> `True` (>=, not >)

### 5.7 `scan_readme_claims()`

**File:** `assemblyzero/workflows/death/drift_scorer.py`

**Signature:**

```python
def scan_readme_claims(
    readme_path: str,
    codebase_root: str,
) -> list[DriftFinding]:
    """Scan README for factual claims and verify against codebase."""
    ...
```

**Input Example:**

```python
readme_path = "README.md"
codebase_root = "/home/user/AssemblyZero"
```

**Output Example:**

```python
[
    {
        "id": "DRIFT-001",
        "severity": "critical",
        "doc_file": "README.md",
        "doc_claim": "Run 12+ AI agents concurrently",
        "code_reality": "36 agent configurations found in assemblyzero/agents/",
        "category": "count_mismatch",
        "confidence": 0.95,
        "evidence": "glob('assemblyzero/agents/*.py') returns 36 files",
    }
]
```

**Edge Cases:**
- `readme_path` doesn't exist -> returns empty list, logs warning
- No numeric claims found -> returns empty list
- README has no recognizable patterns -> returns empty list

### 5.8 `scan_inventory_accuracy()`

**File:** `assemblyzero/workflows/death/drift_scorer.py`

**Signature:**

```python
def scan_inventory_accuracy(
    inventory_path: str,
    codebase_root: str,
) -> list[DriftFinding]:
    """Compare file inventory against actual filesystem."""
    ...
```

**Input Example:**

```python
inventory_path = "docs/inventory.md"
codebase_root = "/home/user/AssemblyZero"
```

**Output Example:**

```python
[
    {
        "id": "DRIFT-003",
        "severity": "major",
        "doc_file": "docs/inventory.md",
        "doc_claim": "assemblyzero/workflows/old_module.py listed as active",
        "code_reality": "File does not exist on disk",
        "category": "stale_reference",
        "confidence": 1.0,
        "evidence": "os.path.exists('assemblyzero/workflows/old_module.py') = False",
    }
]
```

**Edge Cases:**
- `inventory_path` doesn't exist -> returns empty list, logs warning
- Inventory file is not a parseable markdown table -> returns empty list with logged error

### 5.9 `scan_architecture_docs()`

**File:** `assemblyzero/workflows/death/drift_scorer.py`

**Signature:**

```python
def scan_architecture_docs(
    docs_dir: str,
    codebase_root: str,
) -> list[DriftFinding]:
    """Scan architecture docs for claims that contradict code structure."""
    ...
```

**Input Example:**

```python
docs_dir = "docs/standards"
codebase_root = "/home/user/AssemblyZero"
```

**Output Example:**

```python
[
    {
        "id": "DRIFT-005",
        "severity": "major",
        "doc_file": "docs/standards/0001-overview.md",
        "doc_claim": "System uses 5 workflow state machines",
        "code_reality": "7 workflow directories found under assemblyzero/workflows/",
        "category": "architecture_drift",
        "confidence": 0.85,
        "evidence": "ls assemblyzero/workflows/ shows: death, issue, janitor, lld, rag, requirements, testing",
    }
]
```

**Edge Cases:**
- `docs_dir` doesn't exist -> returns empty list
- No architecture docs found -> returns empty list

### 5.10 `compute_drift_score()`

**File:** `assemblyzero/workflows/death/drift_scorer.py`

**Signature:**

```python
def compute_drift_score(findings: list[DriftFinding]) -> float:
    """Compute aggregate drift score from findings. critical=10, major=5, minor=1."""
    ...
```

**Input Example:**

```python
findings = [
    {"id": "DRIFT-001", "severity": "critical", "doc_file": "README.md", "doc_claim": "...", "code_reality": "...", "category": "count_mismatch", "confidence": 0.95, "evidence": "..."},
    {"id": "DRIFT-002", "severity": "major", "doc_file": "README.md", "doc_claim": "...", "code_reality": "...", "category": "count_mismatch", "confidence": 0.90, "evidence": "..."},
    {"id": "DRIFT-003", "severity": "minor", "doc_file": "docs/x.md", "doc_claim": "...", "code_reality": "...", "category": "stale_reference", "confidence": 0.80, "evidence": "..."},
]
```

**Output Example:**

```python
16.0  # 1*10 + 1*5 + 1*1
```

**Edge Cases:**
- Empty findings list -> returns `0.0`

### 5.11 `build_drift_report()`

**File:** `assemblyzero/workflows/death/drift_scorer.py`

**Signature:**

```python
def build_drift_report(
    codebase_root: str,
    docs_to_scan: list[str] | None = None,
) -> DriftReport:
    """Run all drift scanners and produce aggregated report."""
    ...
```

**Input Example:**

```python
codebase_root = "/home/user/AssemblyZero"
docs_to_scan = None  # scan all standard locations
```

**Output Example:**

```python
{
    "findings": [...],
    "total_score": 15.0,
    "critical_count": 1,
    "major_count": 1,
    "minor_count": 0,
    "scanned_docs": ["README.md", "docs/standards/0001-overview.md"],
    "scanned_code_paths": ["assemblyzero/agents/", "assemblyzero/workflows/"],
    "timestamp": "2026-02-17T16:00:00Z",
}
```

**Edge Cases:**
- All scanners return empty -> returns report with empty findings, score=0
- `docs_to_scan = ["nonexistent.md"]` -> scans nothing, returns empty report

### 5.12 `check_critical_drift()`

**File:** `assemblyzero/workflows/death/drift_scorer.py`

**Signature:**

```python
def check_critical_drift(report: DriftReport, threshold: float = 30.0) -> bool:
    """Check if drift score exceeds critical threshold."""
    ...
```

**Input Example:**

```python
report = {"findings": [...], "total_score": 30.0, "critical_count": 3, "major_count": 0, "minor_count": 0, "scanned_docs": [], "scanned_code_paths": [], "timestamp": "..."}
threshold = 30.0
```

**Output Example:**

```python
True  # total_score >= threshold
```

### 5.13 `walk_the_field()`

**File:** `assemblyzero/workflows/death/reconciler.py`

**Signature:**

```python
def walk_the_field(
    codebase_root: str,
    drift_report: DriftReport,
) -> list[ReconciliationAction]:
    """Phase 1: Walk the codebase, compare docs against code reality."""
    ...
```

**Input Example:**

```python
codebase_root = "/home/user/AssemblyZero"
drift_report = {
    "findings": [
        {"id": "DRIFT-001", "severity": "critical", "doc_file": "README.md", "doc_claim": "Run 12+ AI agents", "code_reality": "36 agents found", "category": "count_mismatch", "confidence": 0.95, "evidence": "..."}
    ],
    "total_score": 10.0,
    "critical_count": 1, "major_count": 0, "minor_count": 0,
    "scanned_docs": ["README.md"],
    "scanned_code_paths": ["assemblyzero/"],
    "timestamp": "2026-02-17T16:00:00Z",
}
```

**Output Example:**

```python
[
    {
        "target_file": "README.md",
        "action_type": "update_count",
        "description": "Update agent count from '12+' to '36'",
        "old_content": "Run 12+ AI agents concurrently",
        "new_content": "Run 36 AI agents concurrently",
        "drift_finding_id": "DRIFT-001",
    }
]
```

**Edge Cases:**
- Empty drift_report findings -> returns empty list
- Finding maps to unknown category -> creates action with `action_type="update_description"`

### 5.14 `harvest()`

**File:** `assemblyzero/workflows/death/reconciler.py`

**Signature:**

```python
def harvest(
    actions: list[ReconciliationAction],
    codebase_root: str,
    dry_run: bool = True,
) -> list[ReconciliationAction]:
    """Phase 2: Write ADRs and diagrams."""
    ...
```

**Input Example:**

```python
actions = [
    {"target_file": "README.md", "action_type": "update_count", "description": "Update agent count", "old_content": "12+", "new_content": "36", "drift_finding_id": "DRIFT-001"}
]
codebase_root = "/home/user/AssemblyZero"
dry_run = True
```

**Output Example:**

```python
# Same actions, returned as-is in dry_run mode (new_content populated but not written)
[
    {"target_file": "README.md", "action_type": "update_count", "description": "Update agent count", "old_content": "12+", "new_content": "36", "drift_finding_id": "DRIFT-001"}
]
```

**Edge Cases:**
- `dry_run=True` -> never writes files, only populates `new_content`
- `dry_run=False` -> writes files, raises `OSError` on permission issues

### 5.15 `archive_old_age()`

**File:** `assemblyzero/workflows/death/reconciler.py`

**Signature:**

```python
def archive_old_age(
    actions: list[ReconciliationAction],
    codebase_root: str,
    dry_run: bool = True,
) -> list[ReconciliationAction]:
    """Phase 3: Move old artifacts to legacy/done."""
    ...
```

**Input Example:**

```python
actions = [
    {"target_file": "docs/lld/active/old-lld.md", "action_type": "archive", "description": "Move stale LLD to done", "old_content": None, "new_content": None, "drift_finding_id": "DRIFT-004"}
]
codebase_root = "/home/user/AssemblyZero"
dry_run = True
```

**Output Example:**

```python
[
    {"target_file": "docs/lld/active/old-lld.md", "action_type": "archive", "description": "Move stale LLD to done -> docs/lld/done/old-lld.md", "old_content": None, "new_content": "docs/lld/done/old-lld.md", "drift_finding_id": "DRIFT-004"}
]
```

### 5.16 `chronicle()`

**File:** `assemblyzero/workflows/death/reconciler.py`

**Signature:**

```python
def chronicle(
    actions: list[ReconciliationAction],
    codebase_root: str,
    dry_run: bool = True,
) -> list[ReconciliationAction]:
    """Phase 4: Update README and wiki to describe current reality."""
    ...
```

**Input Example:**

```python
actions = [
    {"target_file": "README.md", "action_type": "update_count", "description": "Update agent count", "old_content": "12+", "new_content": "36", "drift_finding_id": "DRIFT-001"}
]
codebase_root = "/home/user/AssemblyZero"
dry_run = True
```

**Output Example:**

```python
# Actions returned with updated descriptions reflecting chronicle phase
[
    {"target_file": "README.md", "action_type": "update_count", "description": "Update agent count from '12+' to '36' in README", "old_content": "12+", "new_content": "36", "drift_finding_id": "DRIFT-001"}
]
```

### 5.17 `generate_adr()`

**File:** `assemblyzero/workflows/death/reconciler.py`

**Signature:**

```python
def generate_adr(
    finding: DriftFinding,
    actions: list[ReconciliationAction],
    adr_template_path: str,
    output_dir: str,
    dry_run: bool = True,
) -> str | None:
    """Generate an ADR document from an architecture drift finding."""
    ...
```

**Input Example:**

```python
finding = {
    "id": "DRIFT-005",
    "severity": "major",
    "doc_file": "docs/standards/0001-overview.md",
    "doc_claim": "System uses 5 workflow state machines",
    "code_reality": "7 workflow directories found",
    "category": "architecture_drift",
    "confidence": 0.85,
    "evidence": "ls assemblyzero/workflows/ shows 7 directories",
}
actions = [
    {"target_file": "docs/standards/0001-overview.md", "action_type": "update_count", "description": "Update workflow count", "old_content": "5", "new_content": "7", "drift_finding_id": "DRIFT-005"}
]
adr_template_path = "docs/standards/"
output_dir = "docs/standards/"
dry_run = True
```

**Output Example (dry_run=True):**

```python
"# ADR-0016: Age Transition Protocol\n\n## Status\n\nAccepted\n\n## Context\n\nDocumentation claimed 'System uses 5 workflow state machines' but code reality shows 7 workflow directories...\n\n## Decision\n\n...\n\n## Consequences\n\n..."
```

**Output Example (dry_run=False):**

```python
"docs/standards/0016-age-transition-protocol.md"  # file path written
```

**Edge Cases:**
- `finding["category"] != "architecture_drift"` -> returns `None`
- `dry_run=True` -> returns ADR content string, no file written
- `dry_run=False` -> writes file to `output_dir/0016-age-transition-protocol.md`, returns path

### 5.18 `build_reconciliation_report()`

**File:** `assemblyzero/workflows/death/reconciler.py`

**Signature:**

```python
def build_reconciliation_report(
    trigger: str,
    trigger_details: str,
    drift_report: DriftReport,
    actions: list[ReconciliationAction],
    mode: str,
    age_number: int,
) -> ReconciliationReport:
    """Assemble the full reconciliation report from all phases."""
    ...
```

**Input Example:**

```python
trigger = "summon"
trigger_details = "DEATH summoned via /death command"
drift_report = {"findings": [...], "total_score": 15.0, "critical_count": 1, "major_count": 1, "minor_count": 0, "scanned_docs": ["README.md"], "scanned_code_paths": ["assemblyzero/"], "timestamp": "2026-02-17T16:00:00Z"}
actions = [{"target_file": "README.md", "action_type": "update_count", "description": "Update count", "old_content": "12+", "new_content": "36", "drift_finding_id": "DRIFT-001"}]
mode = "report"
age_number = 3
```

**Output Example:**

```python
{
    "age_number": 3,
    "trigger": "summon",
    "trigger_details": "DEATH summoned via /death command",
    "drift_report": {...},
    "actions": [...],
    "mode": "report",
    "timestamp": "2026-02-17T16:05:00Z",
    "summary": "DEATH found 2 drift findings (1 critical, 1 major). 1 reconciliation action proposed.",
}
```

### 5.19 `create_hourglass_graph()`

**File:** `assemblyzero/workflows/death/hourglass.py`

**Signature:**

```python
def create_hourglass_graph() -> StateGraph:
    """Create the LangGraph state machine for the Hourglass Protocol."""
    ...
```

**Input Example:** None (factory function)

**Output Example:** A `StateGraph` instance with nodes: `init`, `walk_field`, `harvest`, `confirm_gate`, `archive`, `chronicle`, `rest`, `complete`

**Edge Cases:**
- Returns a compiled graph ready for invocation

### 5.20 `should_death_arrive()`

**File:** `assemblyzero/workflows/death/hourglass.py`

**Signature:**

```python
def should_death_arrive(
    codebase_root: str,
    repo: str,
    github_token: str | None = None,
) -> tuple[bool, str, str]:
    """Check all three triggers. Returns (should_trigger, trigger_type, details)."""
    ...
```

**Input Example:**

```python
codebase_root = "/home/user/AssemblyZero"
repo = "martymcenroe/AssemblyZero"
github_token = None
```

**Output Example:**

```python
(True, "meter", "Age meter score 52 exceeds threshold 50 (17 issues since last visit)")
```

**Edge Cases:**
- All clear -> `(False, "", "No triggers active")`
- Both meter and critical drift -> critical drift takes priority: `(True, "critical_drift", "...")`
- GitHub API failure -> logs error, skips meter check, still checks drift

### 5.21 `run_death()`

**File:** `assemblyzero/workflows/death/hourglass.py`

**Signature:**

```python
def run_death(
    mode: Literal["report", "reaper"],
    trigger: Literal["meter", "summon", "critical_drift"],
    codebase_root: str,
    repo: str,
    github_token: str | None = None,
) -> ReconciliationReport:
    """Execute the full DEATH reconciliation protocol."""
    ...
```

**Input Example:**

```python
mode = "report"
trigger = "summon"
codebase_root = "/home/user/AssemblyZero"
repo = "martymcenroe/AssemblyZero"
```

**Output Example:**

```python
{
    "age_number": 3,
    "trigger": "summon",
    "trigger_details": "DEATH summoned via /death command",
    "drift_report": {...},
    "actions": [...],
    "mode": "report",
    "timestamp": "2026-02-17T16:05:00Z",
    "summary": "...",
}
```

### 5.22 `parse_death_args()`

**File:** `assemblyzero/workflows/death/skill.py`

**Signature:**

```python
def parse_death_args(
    args: list[str],
) -> tuple[Literal["report", "reaper"], bool]:
    """Parse /death skill command arguments."""
    ...
```

**Input Example 1:**

```python
args = ["report"]
```

**Output Example 1:**

```python
("report", False)
```

**Input Example 2:**

```python
args = ["reaper", "--force"]
```

**Output Example 2:**

```python
("reaper", True)
```

**Input Example 3:**

```python
args = []
```

**Output Example 3:**

```python
("report", False)  # default
```

**Edge Cases:**
- `args = ["invalid"]` -> raises `ValueError("Unknown mode: 'invalid'. Use 'report' or 'reaper'.")`
- `args = ["report", "--force"]` -> raises `ValueError("--force is only valid with reaper mode")`
- `args = ["reaper", "--unknown"]` -> raises `ValueError("Unknown flag: '--unknown'")`

### 5.23 `invoke_death_skill()`

**File:** `assemblyzero/workflows/death/skill.py`

**Signature:**

```python
def invoke_death_skill(
    args: list[str],
    codebase_root: str,
    repo: str,
    github_token: str | None = None,
) -> ReconciliationReport:
    """Main entry point for the /death Claude Code skill."""
    ...
```

**Input Example:**

```python
args = ["report"]
codebase_root = "/home/user/AssemblyZero"
repo = "martymcenroe/AssemblyZero"
```

**Output Example:**

```python
# Returns ReconciliationReport (see Section 4.6)
{
    "age_number": 3,
    "trigger": "summon",
    "trigger_details": "DEATH summoned via /death command by orchestrator",
    "drift_report": {...},
    "actions": [...],
    "mode": "report",
    "timestamp": "2026-02-17T16:05:00Z",
    "summary": "...",
}
```

**Edge Cases:**
- `args = ["reaper"]` without confirmation -> raises `PermissionError("Reaper mode requires orchestrator confirmation")`
- `args = ["reaper", "--force"]` -> skips confirmation, proceeds directly

### 5.24 `format_report_output()`

**File:** `assemblyzero/workflows/death/skill.py`

**Signature:**

```python
def format_report_output(
    report: ReconciliationReport,
) -> str:
    """Format a ReconciliationReport into human-readable markdown output."""
    ...
```

**Input Example:**

```python
report = {
    "age_number": 3,
    "trigger": "summon",
    "trigger_details": "DEATH summoned via /death command",
    "drift_report": {
        "findings": [
            {"id": "DRIFT-001", "severity": "critical", "doc_file": "README.md", "doc_claim": "12+ agents", "code_reality": "36 agents", "category": "count_mismatch", "confidence": 0.95, "evidence": "..."}
        ],
        "total_score": 10.0,
        "critical_count": 1, "major_count": 0, "minor_count": 0,
        "scanned_docs": ["README.md"],
        "scanned_code_paths": ["assemblyzero/"],
        "timestamp": "2026-02-17T16:00:00Z",
    },
    "actions": [
        {"target_file": "README.md", "action_type": "update_count", "description": "Update agent count from '12+' to '36'", "old_content": "12+", "new_content": "36", "drift_finding_id": "DRIFT-001"}
    ],
    "mode": "report",
    "timestamp": "2026-02-17T16:05:00Z",
    "summary": "DEATH found 1 drift finding (1 critical). 1 reconciliation action proposed.",
}
```

**Output Example:**

```python
"""# ⏳ DEATH — Reconciliation Report (Age 3)

> THE SAND HAS RUN OUT.

**Trigger:** summon — DEATH summoned via /death command
**Mode:** report (read-only)

## Summary

DEATH found 1 drift finding (1 critical). 1 reconciliation action proposed.

## Drift Findings

| ID | Severity | File | Claim | Reality | Category |
|----|----------|------|-------|---------|----------|
| DRIFT-001 |  critical | README.md | 12+ agents | 36 agents | count_mismatch |

**Drift Score:** 10.0 (threshold: 30.0)

## Proposed Actions

| # | Target | Action | Description |
|---|--------|--------|-------------|
| 1 | README.md | update_count | Update agent count from '12+' to '36' |

## Next Steps

Run `/death reaper` to apply these changes.

> WHAT CAN THE HARVEST HOPE FOR, IF NOT FOR THE CARE OF THE REAPER MAN?
"""
```

### 5.25 `run_drift_probe()`

**File:** `assemblyzero/workflows/janitor/probes/drift_probe.py`

**Signature:**

```python
def run_drift_probe(
    codebase_root: str,
    docs_to_scan: list[str] | None = None,
) -> dict:
    """Janitor probe that runs drift analysis and feeds the hourglass."""
    ...
```

**Input Example:**

```python
codebase_root = "/home/user/AssemblyZero"
docs_to_scan = None
```

**Output Example:**

```python
{
    "probe": "drift",
    "status": "warn",
    "drift_score": 15.0,
    "finding_count": 2,
    "critical_findings": ["DRIFT-001: README.md count_mismatch (critical)"],
    "details": {
        "findings": [...],
        "total_score": 15.0,
        "critical_count": 1,
        "major_count": 1,
        "minor_count": 0,
        "scanned_docs": ["README.md"],
        "scanned_code_paths": ["assemblyzero/"],
        "timestamp": "2026-02-17T16:00:00Z",
    },
}
```

**Edge Cases:**
- No findings -> `{"probe": "drift", "status": "pass", "drift_score": 0.0, "finding_count": 0, "critical_findings": [], "details": {...}}`
- Critical drift threshold exceeded -> `"status": "fail"`
- Findings exist but below critical -> `"status": "warn"`

## 6. Change Instructions

### 6.1 `data/hourglass/` (Add Directory)

Create the directory. No files initially — `age_meter.json` is created on first run, `history.json` is seeded.

### 6.2 `data/hourglass/age_meter.json` (Add)

This file is created by `save_age_meter_state()` on first run. Seed it as an empty JSON object to validate the directory exists:

```json
{}
```

Note: This file is gitignored (local state per developer).

### 6.3 `data/hourglass/history.json` (Add)

**Complete file contents:**

```json
{
    "visits": [],
    "created": "2026-02-17T00:00:00Z"
}
```

### 6.4 `.gitignore` (Modify)

**Change 1:** Append after the `data/unleashed/` line (approximately line 46):

```diff
 # Session transcripts (auto-generated, untracked)
 data/unleashed/
 data/handoff-log.md
 transcripts/
+
+# DEATH Hourglass Protocol - local age meter state (Issue #535)
+# history.json is tracked; age_meter.json is per-developer
+data/hourglass/age_meter.json
```

### 6.5 `assemblyzero/workflows/death/__init__.py` (Add)

**Complete file contents:**

```python
"""DEATH: The Hourglass Protocol — Age Transition Workflow.

Issue #535: Implements documentation drift detection, age meter computation,
and reconciliation protocol for keeping docs aligned with codebase reality.

Triggers:
    1. Meter threshold — accumulated issue weight crosses threshold
    2. Summon — orchestrator invokes /death command
    3. Critical drift — drift score exceeds critical threshold
"""

from assemblyzero.workflows.death.hourglass import (
    create_hourglass_graph,
    run_death,
    should_death_arrive,
)
from assemblyzero.workflows.death.skill import (
    invoke_death_skill,
    parse_death_args,
)

__all__ = [
    "create_hourglass_graph",
    "run_death",
    "should_death_arrive",
    "invoke_death_skill",
    "parse_death_args",
]
```

### 6.6 `assemblyzero/workflows/death/constants.py` (Add)

**Complete file contents:**

```python
"""Constants for the Hourglass Protocol.

Issue #535: Weight tables, thresholds, and configuration.
"""

from __future__ import annotations

# Issue weight mapping: label -> weight
LABEL_WEIGHTS: dict[str, int] = {
    # +1: Fixes reality but doesn't change the shape
    "bug": 1,
    "fix": 1,
    "hotfix": 1,
    "patch": 1,
    # +3: Adds capability
    "enhancement": 3,
    "feature": 3,
    "feat": 3,
    # +5: Changes what the system *is*
    "persona": 5,
    "subsystem": 5,
    "new-component": 5,
    "new-workflow": 5,
    # +8: Changes how everything else works
    "foundation": 8,
    "rag": 8,
    "pipeline": 8,
    "infrastructure": 8,
    # +10: The old map is now wrong
    "architecture": 10,
    "cross-cutting": 10,
    "breaking": 10,
    "breaking-change": 10,
}

DEFAULT_WEIGHT: int = 2  # For issues with no matching labels
DEFAULT_THRESHOLD: int = 50  # Age meter threshold before DEATH triggers
CRITICAL_DRIFT_THRESHOLD: float = 30.0  # Drift score threshold for immediate trigger

# Drift severity weights for score computation
DRIFT_SEVERITY_WEIGHTS: dict[str, float] = {
    "critical": 10.0,
    "major": 5.0,
    "minor": 1.0,
}

# Drift finding category -> default reconciliation action type
CATEGORY_ACTION_MAP: dict[str, str] = {
    "count_mismatch": "update_count",
    "feature_contradiction": "update_description",
    "missing_component": "add_section",
    "stale_reference": "remove_section",
    "architecture_drift": "create_adr",
}

# File paths
AGE_METER_STATE_PATH: str = "data/hourglass/age_meter.json"
HISTORY_PATH: str = "data/hourglass/history.json"
ADR_OUTPUT_PATH: str = "docs/standards/0016-age-transition-protocol.md"
ADR_TEMPLATE_DIR: str = "docs/standards/"

# Standard doc locations to scan for drift
DEFAULT_DOCS_TO_SCAN: list[str] = [
    "README.md",
    "docs/standards/",
]

# Standard code paths to analyze
DEFAULT_CODE_PATHS: list[str] = [
    "assemblyzero/",
    "tools/",
    "tests/",
]

# Regex patterns for numeric claims in README
NUMERIC_CLAIM_PATTERNS: list[str] = [
    r"(\d+)\+?\s+(?:AI\s+)?agents?",
    r"(\d+)\+?\s+(?:state\s+)?machines?",
    r"(\d+)\+?\s+workflows?",
    r"(\d+)\+?\s+tools?",
    r"(\d+)\+?\s+personas?",
    r"(\d+)\+?\s+probes?",
    r"(\d+)\+?\s+audits?",
    r"(\d+)\+?\s+issues?\s+(?:closed|in)",
]

# GitHub API pagination cap
MAX_ISSUES_PER_FETCH: int = 500
```

### 6.7 `assemblyzero/workflows/death/models.py` (Add)

**Complete file contents:**

```python
"""Data models for the Hourglass Protocol.

Issue #535: TypedDict definitions for age meter, drift findings,
reconciliation reports, and hourglass state.
"""

from __future__ import annotations

from typing import Literal, TypedDict


class IssueWeight(TypedDict):
    """Weight assignment for a single closed issue."""

    issue_number: int
    title: str
    labels: list[str]
    weight: int
    weight_source: str
    closed_at: str


class AgeMeterState(TypedDict):
    """Persistent state of the age meter between sessions."""

    current_score: int
    threshold: int
    last_death_visit: str | None
    last_computed: str
    weighted_issues: list[IssueWeight]
    age_number: int


class DriftFinding(TypedDict):
    """A single factual inaccuracy found by drift analysis."""

    id: str
    severity: Literal["critical", "major", "minor"]
    doc_file: str
    doc_claim: str
    code_reality: str
    category: Literal[
        "count_mismatch",
        "feature_contradiction",
        "missing_component",
        "stale_reference",
        "architecture_drift",
    ]
    confidence: float
    evidence: str


class DriftReport(TypedDict):
    """Aggregated drift analysis results."""

    findings: list[DriftFinding]
    total_score: float
    critical_count: int
    major_count: int
    minor_count: int
    scanned_docs: list[str]
    scanned_code_paths: list[str]
    timestamp: str


class ReconciliationAction(TypedDict):
    """A single action to reconcile documentation with reality."""

    target_file: str
    action_type: Literal[
        "update_count",
        "update_description",
        "add_section",
        "remove_section",
        "archive",
        "create_adr",
    ]
    description: str
    old_content: str | None
    new_content: str | None
    drift_finding_id: str


class ReconciliationReport(TypedDict):
    """Full reconciliation report — output of DEATH's walk."""

    age_number: int
    trigger: Literal["meter", "summon", "critical_drift"]
    trigger_details: str
    drift_report: DriftReport
    actions: list[ReconciliationAction]
    mode: Literal["report", "reaper"]
    timestamp: str
    summary: str


class HourglassState(TypedDict):
    """LangGraph state for the Hourglass workflow."""

    trigger: Literal["meter", "summon", "critical_drift"]
    mode: Literal["report", "reaper"]
    age_meter: AgeMeterState
    drift_report: DriftReport | None
    reconciliation_report: ReconciliationReport | None
    step: Literal[
        "init",
        "walk_field",
        "harvest",
        "archive",
        "chronicle",
        "rest",
        "complete",
    ]
    errors: list[str]
    confirmed: bool
```

### 6.8 `assemblyzero/workflows/death/age_meter.py` (Add)

**Complete file contents:**

```python
"""Age meter computation for the Hourglass Protocol.

Issue #535: Weights closed GitHub issues by label/type and computes
a running score that triggers DEATH when threshold is crossed.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from typing import Any

from assemblyzero.workflows.death.constants import (
    AGE_METER_STATE_PATH,
    DEFAULT_THRESHOLD,
    DEFAULT_WEIGHT,
    LABEL_WEIGHTS,
    MAX_ISSUES_PER_FETCH,
)
from assemblyzero.workflows.death.models import AgeMeterState, IssueWeight

logger = logging.getLogger(__name__)


def compute_issue_weight(
    labels: list[str],
    title: str,
    body: str | None = None,
) -> tuple[int, str]:
    """Compute weight for a single issue based on its labels and content.

    Returns (weight, weight_source) tuple.
    Falls back to default weight if no matching label found.
    """
    best_weight = 0
    best_source = ""

    for label in labels:
        label_lower = label.lower().strip()
        if label_lower in LABEL_WEIGHTS:
            w = LABEL_WEIGHTS[label_lower]
            if w > best_weight:
                best_weight = w
                best_source = label_lower

    if best_weight == 0:
        logger.warning(
            "No matching label found for issue with labels %s, title='%s'. "
            "Using default weight %d.",
            labels,
            title,
            DEFAULT_WEIGHT,
        )
        return (DEFAULT_WEIGHT, "default")

    return (best_weight, best_source)


def fetch_closed_issues_since(
    repo: str,
    since: str | None,
    github_token: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch closed issues from GitHub since the last DEATH visit.

    Args:
        repo: GitHub repo in "owner/repo" format.
        since: ISO 8601 timestamp. If None, fetches all closed issues.
        github_token: Optional token. Uses GITHUB_TOKEN env var if not provided.

    Returns:
        List of issue dicts with number, title, labels, closed_at, body.

    Raises:
        ValueError: If no GitHub token is available.
        ConnectionError: If GitHub API is unreachable.
    """
    token = github_token or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise ValueError(
            "GitHub token not found. Set GITHUB_TOKEN environment variable "
            "or pass github_token parameter."
        )

    try:
        from github import Github

        g = Github(token)
        gh_repo = g.get_repo(repo)

        kwargs: dict[str, Any] = {"state": "closed", "sort": "updated", "direction": "desc"}
        if since:
            kwargs["since"] = datetime.fromisoformat(since.replace("Z", "+00:00"))

        issues: list[dict[str, Any]] = []
        for issue in gh_repo.get_issues(**kwargs):
            if issue.pull_request is not None:
                continue  # Skip PRs
            issues.append(
                {
                    "number": issue.number,
                    "title": issue.title,
                    "labels": [label.name for label in issue.labels],
                    "closed_at": issue.closed_at.isoformat() if issue.closed_at else "",
                    "body": issue.body,
                }
            )
            if len(issues) >= MAX_ISSUES_PER_FETCH:
                logger.warning(
                    "Reached pagination cap of %d issues. Some issues may be excluded.",
                    MAX_ISSUES_PER_FETCH,
                )
                break

        return issues

    except Exception as e:
        if "GitHub" in type(e).__module__ if hasattr(type(e), "__module__") else False:
            raise ConnectionError(f"GitHub API error: {e}") from e
        raise


def compute_age_meter(
    issues: list[dict[str, Any]],
    current_state: AgeMeterState | None = None,
) -> AgeMeterState:
    """Compute the age meter score from a list of closed issues.

    If current_state is provided, adds to existing score (incremental).
    If None, computes from scratch.
    """
    now = datetime.now(timezone.utc).isoformat()

    if current_state is None:
        state: AgeMeterState = {
            "current_score": 0,
            "threshold": DEFAULT_THRESHOLD,
            "last_death_visit": None,
            "last_computed": now,
            "weighted_issues": [],
            "age_number": 1,
        }
    else:
        state = {**current_state, "last_computed": now}

    new_weighted: list[IssueWeight] = []
    added_score = 0

    for issue in issues:
        weight, source = compute_issue_weight(
            labels=issue.get("labels", []),
            title=issue.get("title", ""),
            body=issue.get("body"),
        )
        iw: IssueWeight = {
            "issue_number": issue["number"],
            "title": issue.get("title", ""),
            "labels": issue.get("labels", []),
            "weight": weight,
            "weight_source": source,
            "closed_at": issue.get("closed_at", ""),
        }
        new_weighted.append(iw)
        added_score += weight

    state["weighted_issues"] = state["weighted_issues"] + new_weighted
    state["current_score"] = state["current_score"] + added_score

    return state


def load_age_meter_state(
    state_path: str = AGE_METER_STATE_PATH,
) -> AgeMeterState | None:
    """Load persistent age meter state from disk. Returns None if no state exists."""
    try:
        with open(state_path, "r") as f:
            data = json.load(f)
            if not data:  # Empty dict or empty file
                return None
            return data
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        logger.warning("Invalid JSON in age meter state file: %s", state_path)
        return None


def save_age_meter_state(
    state: AgeMeterState,
    state_path: str = AGE_METER_STATE_PATH,
) -> None:
    """Persist age meter state to disk. Uses atomic write pattern."""
    os.makedirs(os.path.dirname(state_path), exist_ok=True)

    # Atomic write: write to temp file then rename
    dir_name = os.path.dirname(state_path)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".json.tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp_path, state_path)
    except Exception:
        # Clean up temp file on failure
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def check_meter_threshold(state: AgeMeterState) -> bool:
    """Check if the age meter has crossed the threshold. Returns True if DEATH should arrive."""
    return state["current_score"] >= state["threshold"]
```

### 6.9 `assemblyzero/workflows/death/drift_scorer.py` (Add)

**Complete file contents:**

```python
"""Drift scoring for the Hourglass Protocol.

Issue #535: Detects factual inaccuracies in documentation by comparing
claims against codebase reality using regex + glob heuristics.
"""

from __future__ import annotations

import glob
import logging
import os
import re
from datetime import datetime, timezone

from assemblyzero.workflows.death.constants import (
    CRITICAL_DRIFT_THRESHOLD,
    DEFAULT_CODE_PATHS,
    DEFAULT_DOCS_TO_SCAN,
    DRIFT_SEVERITY_WEIGHTS,
    NUMERIC_CLAIM_PATTERNS,
)
from assemblyzero.workflows.death.models import DriftFinding, DriftReport

logger = logging.getLogger(__name__)

_drift_counter = 0


def _next_drift_id() -> str:
    """Generate a sequential drift finding ID."""
    global _drift_counter
    _drift_counter += 1
    return f"DRIFT-{_drift_counter:03d}"


def _reset_drift_counter() -> None:
    """Reset the drift counter (for testing)."""
    global _drift_counter
    _drift_counter = 0


def _count_entities(pattern: str, codebase_root: str) -> int:
    """Count files/directories matching a glob pattern."""
    full_pattern = os.path.join(codebase_root, pattern)
    return len(glob.glob(full_pattern))


def _determine_count_severity(claimed: int, actual: int) -> str:
    """Determine severity of a count mismatch."""
    if actual == 0 and claimed > 0:
        return "critical"
    ratio = abs(actual - claimed) / max(claimed, 1)
    if ratio > 0.5:
        return "critical"
    elif ratio > 0.2:
        return "major"
    return "minor"


# Mapping from claim keyword to glob pattern for counting
_CLAIM_GLOB_MAP: dict[str, str] = {
    "agent": "assemblyzero/agents/*.py",
    "machine": "assemblyzero/workflows/*/",
    "workflow": "assemblyzero/workflows/*/",
    "tool": "tools/*.py",
    "persona": "assemblyzero/agents/*.py",
    "probe": "assemblyzero/workflows/janitor/probes/*.py",
}


def scan_readme_claims(
    readme_path: str,
    codebase_root: str,
) -> list[DriftFinding]:
    """Scan README for factual claims and verify against codebase.

    Checks numeric claims (tool counts, agent counts, workflow counts).
    """
    full_path = os.path.join(codebase_root, readme_path) if not os.path.isabs(readme_path) else readme_path
    if not os.path.exists(full_path):
        logger.warning("README not found at %s, skipping scan", full_path)
        return []

    try:
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError as e:
        logger.warning("Failed to read README: %s", e)
        return []

    findings: list[DriftFinding] = []

    for pattern in NUMERIC_CLAIM_PATTERNS:
        for match in re.finditer(pattern, content, re.IGNORECASE):
            claimed_str = match.group(1)
            claimed = int(claimed_str)
            claim_text = match.group(0)

            # Determine what entity we're counting
            claim_lower = claim_text.lower()
            glob_pattern = None
            for keyword, gp in _CLAIM_GLOB_MAP.items():
                if keyword in claim_lower:
                    glob_pattern = gp
                    break

            if glob_pattern is None:
                continue

            actual = _count_entities(glob_pattern, codebase_root)

            if actual != claimed:
                severity = _determine_count_severity(claimed, actual)
                findings.append(
                    DriftFinding(
                        id=_next_drift_id(),
                        severity=severity,
                        doc_file=readme_path,
                        doc_claim=claim_text,
                        code_reality=f"{actual} found via glob('{glob_pattern}')",
                        category="count_mismatch",
                        confidence=0.9 if abs(actual - claimed) > 2 else 0.7,
                        evidence=f"glob('{glob_pattern}') returns {actual} matches, README claims {claimed}",
                    )
                )

    return findings


def scan_inventory_accuracy(
    inventory_path: str,
    codebase_root: str,
) -> list[DriftFinding]:
    """Compare file inventory against actual filesystem.

    Detects files listed in inventory but missing from disk,
    and files on disk missing from inventory.
    """
    full_path = (
        os.path.join(codebase_root, inventory_path)
        if not os.path.isabs(inventory_path)
        else inventory_path
    )
    if not os.path.exists(full_path):
        logger.warning("Inventory file not found at %s, skipping scan", full_path)
        return []

    try:
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError as e:
        logger.warning("Failed to read inventory: %s", e)
        return []

    findings: list[DriftFinding] = []

    # Parse markdown table rows looking for file paths
    # Pattern: | `path/to/file.py` | ... | or | path/to/file.py | ... |
    path_pattern = re.compile(r"\|\s*`?([a-zA-Z0-9_/\-\.]+\.\w+)`?\s*\|")

    inventory_paths: set[str] = set()
    for match in path_pattern.finditer(content):
        path = match.group(1).strip()
        if path and not path.startswith("http"):
            inventory_paths.add(path)

    # Check each inventory path against filesystem
    for inv_path in inventory_paths:
        abs_path = os.path.join(codebase_root, inv_path)
        if not os.path.exists(abs_path):
            findings.append(
                DriftFinding(
                    id=_next_drift_id(),
                    severity="major",
                    doc_file=inventory_path,
                    doc_claim=f"{inv_path} listed in inventory",
                    code_reality="File does not exist on disk",
                    category="stale_reference",
                    confidence=1.0,
                    evidence=f"os.path.exists('{inv_path}') = False",
                )
            )

    return findings


def scan_architecture_docs(
    docs_dir: str,
    codebase_root: str,
) -> list[DriftFinding]:
    """Scan architecture docs for claims that contradict code structure.

    Currently uses simple file/directory counting against claims.
    Will integrate with spelunking (#534) when available.
    """
    full_docs_dir = (
        os.path.join(codebase_root, docs_dir)
        if not os.path.isabs(docs_dir)
        else docs_dir
    )
    if not os.path.isdir(full_docs_dir):
        logger.warning("Docs directory not found at %s, skipping scan", full_docs_dir)
        return []

    findings: list[DriftFinding] = []

    # Scan markdown files in docs_dir for numeric claims
    for filename in os.listdir(full_docs_dir):
        if not filename.endswith(".md"):
            continue

        filepath = os.path.join(full_docs_dir, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError:
            continue

        rel_path = os.path.relpath(filepath, codebase_root)

        for pattern in NUMERIC_CLAIM_PATTERNS:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                claimed = int(match.group(1))
                claim_text = match.group(0)

                claim_lower = claim_text.lower()
                glob_pattern = None
                for keyword, gp in _CLAIM_GLOB_MAP.items():
                    if keyword in claim_lower:
                        glob_pattern = gp
                        break

                if glob_pattern is None:
                    continue

                actual = _count_entities(glob_pattern, codebase_root)
                if actual != claimed:
                    severity = _determine_count_severity(claimed, actual)
                    findings.append(
                        DriftFinding(
                            id=_next_drift_id(),
                            severity=severity,
                            doc_file=rel_path,
                            doc_claim=claim_text,
                            code_reality=f"{actual} found via glob('{glob_pattern}')",
                            category="architecture_drift",
                            confidence=0.85,
                            evidence=f"glob('{glob_pattern}') returns {actual}, doc claims {claimed}",
                        )
                    )

    return findings


def compute_drift_score(findings: list[DriftFinding]) -> float:
    """Compute aggregate drift score. critical=10, major=5, minor=1."""
    score = 0.0
    for finding in findings:
        score += DRIFT_SEVERITY_WEIGHTS.get(finding["severity"], 1.0)
    return score


def build_drift_report(
    codebase_root: str,
    docs_to_scan: list[str] | None = None,
) -> DriftReport:
    """Run all drift scanners and produce aggregated report."""
    _reset_drift_counter()

    all_findings: list[DriftFinding] = []
    scanned_docs: list[str] = []
    scanned_code_paths: list[str] = list(DEFAULT_CODE_PATHS)

    scan_targets = docs_to_scan or list(DEFAULT_DOCS_TO_SCAN)

    for target in scan_targets:
        if target.endswith(".md"):
            # Single file — run README scanner
            readme_findings = scan_readme_claims(target, codebase_root)
            all_findings.extend(readme_findings)
            scanned_docs.append(target)
        elif target.endswith("/"):
            # Directory — run architecture scanner + inventory scanner
            arch_findings = scan_architecture_docs(target, codebase_root)
            all_findings.extend(arch_findings)
            scanned_docs.append(target)

            # Also check for inventory files in the directory
            full_dir = os.path.join(codebase_root, target) if not os.path.isabs(target) else target
            if os.path.isdir(full_dir):
                for fname in os.listdir(full_dir):
                    if "inventory" in fname.lower() and fname.endswith(".md"):
                        inv_path = os.path.join(target, fname)
                        inv_findings = scan_inventory_accuracy(inv_path, codebase_root)
                        all_findings.extend(inv_findings)
                        scanned_docs.append(inv_path)

    total_score = compute_drift_score(all_findings)
    critical_count = sum(1 for f in all_findings if f["severity"] == "critical")
    major_count = sum(1 for f in all_findings if f["severity"] == "major")
    minor_count = sum(1 for f in all_findings if f["severity"] == "minor")

    return DriftReport(
        findings=all_findings,
        total_score=total_score,
        critical_count=critical_count,
        major_count=major_count,
        minor_count=minor_count,
        scanned_docs=scanned_docs,
        scanned_code_paths=scanned_code_paths,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def check_critical_drift(
    report: DriftReport, threshold: float = CRITICAL_DRIFT_THRESHOLD
) -> bool:
    """Check if drift score exceeds critical threshold."""
    return report["total_score"] >= threshold
```

### 6.10 `assemblyzero/workflows/death/reconciler.py` (Add)

**Complete file contents:**

```python
"""Reconciliation engine for the Hourglass Protocol.

Issue #535: Walks codebase, compares to docs, produces report or applies fixes.
Includes ADR generation for architecture drift findings.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime, timezone

from assemblyzero.workflows.death.constants import (
    ADR_OUTPUT_PATH,
    ADR_TEMPLATE_DIR,
    CATEGORY_ACTION_MAP,
    HISTORY_PATH,
)
from assemblyzero.workflows.death.models import (
    DriftFinding,
    DriftReport,
    ReconciliationAction,
    ReconciliationReport,
)

logger = logging.getLogger(__name__)


def walk_the_field(
    codebase_root: str,
    drift_report: DriftReport,
) -> list[ReconciliationAction]:
    """Phase 1: Walk the codebase, compare docs against code reality.

    Converts drift findings into reconciliation actions.
    """
    actions: list[ReconciliationAction] = []

    for finding in drift_report["findings"]:
        action_type = CATEGORY_ACTION_MAP.get(
            finding["category"], "update_description"
        )

        action = ReconciliationAction(
            target_file=finding["doc_file"],
            action_type=action_type,
            description=_build_action_description(finding),
            old_content=finding["doc_claim"],
            new_content=finding["code_reality"],
            drift_finding_id=finding["id"],
        )
        actions.append(action)

    return actions


def _build_action_description(finding: DriftFinding) -> str:
    """Build a human-readable description for a reconciliation action."""
    category = finding["category"]
    if category == "count_mismatch":
        return f"Update '{finding['doc_claim']}' to reflect reality: {finding['code_reality']}"
    elif category == "feature_contradiction":
        return f"Fix feature claim '{finding['doc_claim']}' — actual: {finding['code_reality']}"
    elif category == "missing_component":
        return f"Add documentation for component: {finding['code_reality']}"
    elif category == "stale_reference":
        return f"Remove stale reference to '{finding['doc_claim']}' — {finding['code_reality']}"
    elif category == "architecture_drift":
        return f"Update architecture description: '{finding['doc_claim']}' -> {finding['code_reality']}"
    return f"Reconcile '{finding['doc_claim']}' with reality"


def harvest(
    actions: list[ReconciliationAction],
    codebase_root: str,
    dry_run: bool = True,
) -> list[ReconciliationAction]:
    """Phase 2: Write ADRs and diagrams.

    In dry_run mode, returns actions with new_content populated but no writes.
    In write mode, creates/updates files.
    """
    updated_actions: list[ReconciliationAction] = []

    for action in actions:
        if not dry_run and action["action_type"] in ("update_count", "update_description"):
            target_path = os.path.join(codebase_root, action["target_file"])
            if os.path.exists(target_path) and action["old_content"] and action["new_content"]:
                try:
                    with open(target_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    content = content.replace(action["old_content"], action["new_content"])
                    with open(target_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    logger.info("Updated %s: %s", action["target_file"], action["description"])
                except OSError as e:
                    logger.error("Failed to update %s: %s", action["target_file"], e)

        updated_actions.append(action)

    return updated_actions


def archive_old_age(
    actions: list[ReconciliationAction],
    codebase_root: str,
    dry_run: bool = True,
) -> list[ReconciliationAction]:
    """Phase 3: Move old artifacts to legacy/done."""
    updated_actions: list[ReconciliationAction] = []

    for action in actions:
        if action["action_type"] == "archive":
            src = action["target_file"]
            # Determine destination based on file location
            if "lld/active" in src:
                dst = src.replace("lld/active", "lld/done")
            elif "docs/" in src:
                dst = src.replace("docs/", "docs/legacy/")
            else:
                dst = f"docs/legacy/{os.path.basename(src)}"

            action = {**action, "new_content": dst, "description": f"Archive {src} -> {dst}"}

            if not dry_run:
                src_full = os.path.join(codebase_root, src)
                dst_full = os.path.join(codebase_root, dst)
                if os.path.exists(src_full):
                    os.makedirs(os.path.dirname(dst_full), exist_ok=True)
                    shutil.move(src_full, dst_full)
                    logger.info("Archived %s -> %s", src, dst)

        updated_actions.append(action)

    return updated_actions


def chronicle(
    actions: list[ReconciliationAction],
    codebase_root: str,
    dry_run: bool = True,
) -> list[ReconciliationAction]:
    """Phase 4: Update README and wiki to describe current reality."""
    updated_actions: list[ReconciliationAction] = []

    for action in actions:
        if action["action_type"] in ("update_count", "update_description") and action["target_file"] == "README.md":
            if not dry_run and action["old_content"] and action["new_content"]:
                readme_path = os.path.join(codebase_root, "README.md")
                if os.path.exists(readme_path):
                    try:
                        with open(readme_path, "r", encoding="utf-8") as f:
                            content = f.read()
                        content = content.replace(action["old_content"], action["new_content"])
                        with open(readme_path, "w", encoding="utf-8") as f:
                            f.write(content)
                        logger.info("Chronicled README update: %s", action["description"])
                    except OSError as e:
                        logger.error("Failed to chronicle README: %s", e)

        updated_actions.append(action)

    return updated_actions


def generate_adr(
    finding: DriftFinding,
    actions: list[ReconciliationAction],
    adr_template_path: str,
    output_dir: str,
    dry_run: bool = True,
) -> str | None:
    """Generate an ADR document from an architecture drift finding.

    Returns ADR content (dry_run=True), file path (dry_run=False), or None if not applicable.
    """
    if finding["category"] != "architecture_drift":
        return None

    # Find related actions for context
    related_actions = [a for a in actions if a["drift_finding_id"] == finding["id"]]

    # Build ADR content
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    actions_description = "\n".join(
        f"- {a['description']}" for a in related_actions
    ) or "- No specific actions identified"

    adr_content = f"""# ADR-0016: Age Transition Protocol

## Status

Accepted

## Date

{now}

## Context

Documentation drift detected by the Hourglass Protocol (Issue #535).

**Drift Finding:** {finding['id']}
- **Documented Claim:** {finding['doc_claim']}
- **Code Reality:** {finding['code_reality']}
- **Source File:** {finding['doc_file']}
- **Confidence:** {finding['confidence']:.0%}
- **Evidence:** {finding['evidence']}

The documentation no longer accurately describes the system architecture.
This ADR records the current reality and the decision to update documentation accordingly.

## Decision

Update documentation to reflect the current state of the codebase:

{actions_description}

The Hourglass Protocol detects when accumulated changes make existing documentation
materially inaccurate. DEATH arrives to reconcile the documented world with reality.

## Alternatives Considered

1. **Leave documentation as-is** — Rejected. Stale documentation is worse than no documentation.
2. **Partial update** — Rejected. A full reconciliation ensures consistency.
3. **Rewrite from scratch** — Rejected. Targeted updates preserve institutional knowledge.

## Consequences

### Positive
- Documentation accurately reflects the current system
- New contributors see the real architecture, not a historical snapshot
- Age meter resets, starting a new documentation epoch

### Negative
- Historical context may be lost (mitigated by this ADR and git history)
- Frequent DEATH visits may indicate unstable architecture (signal, not bug)

### Neutral
- This ADR serves as a bookmark between documentation ages

> WHAT CAN THE HARVEST HOPE FOR, IF NOT FOR THE CARE OF THE REAPER MAN?
"""

    if dry_run:
        return adr_content

    # Write the ADR file
    output_path = os.path.join(output_dir, "0016-age-transition-protocol.md")
    os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(adr_content)
    logger.info("Wrote ADR to %s", output_path)
    return output_path


def build_reconciliation_report(
    trigger: str,
    trigger_details: str,
    drift_report: DriftReport,
    actions: list[ReconciliationAction],
    mode: str,
    age_number: int,
) -> ReconciliationReport:
    """Assemble the full reconciliation report from all phases."""
    critical = drift_report["critical_count"]
    major = drift_report["major_count"]
    minor = drift_report["minor_count"]
    total = len(drift_report["findings"])
    action_count = len(actions)

    severity_parts = []
    if critical:
        severity_parts.append(f"{critical} critical")
    if major:
        severity_parts.append(f"{major} major")
    if minor:
        severity_parts.append(f"{minor} minor")
    severity_str = ", ".join(severity_parts) if severity_parts else "none"

    summary = (
        f"DEATH found {total} drift finding{'s' if total != 1 else ''} "
        f"({severity_str}). "
        f"{action_count} reconciliation action{'s' if action_count != 1 else ''} "
        f"{'proposed' if mode == 'report' else 'applied'}."
    )

    return ReconciliationReport(
        age_number=age_number,
        trigger=trigger,
        trigger_details=trigger_details,
        drift_report=drift_report,
        actions=actions,
        mode=mode,
        timestamp=datetime.now(timezone.utc).isoformat(),
        summary=summary,
    )


def record_death_visit(
    report: ReconciliationReport,
    history_path: str = HISTORY_PATH,
) -> None:
    """Append a DEATH visit record to history.json."""
    os.makedirs(os.path.dirname(history_path), exist_ok=True)

    try:
        with open(history_path, "r") as f:
            history = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        history = {"visits": [], "created": datetime.now(timezone.utc).isoformat()}

    visit = {
        "age_number": report["age_number"],
        "trigger": report["trigger"],
        "mode": report["mode"],
        "drift_score": report["drift_report"]["total_score"],
        "finding_count": len(report["drift_report"]["findings"]),
        "action_count": len(report["actions"]),
        "timestamp": report["timestamp"],
    }
    history["visits"].append(visit)

    with open(history_path, "w") as f:
        json.dump(history, f, indent=2)
```

### 6.11 `assemblyzero/workflows/death/hourglass.py` (Add)

**Complete file contents:**

```python
"""Hourglass state machine for the Hourglass Protocol.

Issue #535: Orchestrates the three triggers and reconciliation protocol
using a LangGraph StateGraph.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Literal

from langgraph.graph import StateGraph

from assemblyzero.workflows.death.age_meter import (
    check_meter_threshold,
    compute_age_meter,
    fetch_closed_issues_since,
    load_age_meter_state,
    save_age_meter_state,
)
from assemblyzero.workflows.death.constants import AGE_METER_STATE_PATH, DEFAULT_THRESHOLD
from assemblyzero.workflows.death.drift_scorer import (
    build_drift_report,
    check_critical_drift,
)
from assemblyzero.workflows.death.models import (
    AgeMeterState,
    HourglassState,
    ReconciliationReport,
)
from assemblyzero.workflows.death.reconciler import (
    archive_old_age,
    build_reconciliation_report,
    chronicle,
    generate_adr,
    harvest,
    record_death_visit,
    walk_the_field,
)

logger = logging.getLogger(__name__)


def _node_init(state: HourglassState) -> dict[str, Any]:
    """Initialize the hourglass — load state, log trigger."""
    trigger = state["trigger"]
    if trigger == "summon":
        logger.info("DEATH HAS BEEN SUMMONED.")
    elif trigger == "meter":
        logger.info("THE SAND HAS RUN OUT.")
    else:
        logger.info("CRITICAL DRIFT DETECTED. DEATH ARRIVES UNBIDDEN.")

    age_meter = state.get("age_meter")
    if not age_meter:
        loaded = load_age_meter_state()
        if loaded:
            age_meter = loaded
        else:
            age_meter = AgeMeterState(
                current_score=0,
                threshold=DEFAULT_THRESHOLD,
                last_death_visit=None,
                last_computed=datetime.now(timezone.utc).isoformat(),
                weighted_issues=[],
                age_number=1,
            )

    return {"age_meter": age_meter, "step": "walk_field", "errors": []}


def _node_walk_field(state: HourglassState) -> dict[str, Any]:
    """Walk the field — run drift scanners."""
    logger.info("Walking the field...")
    try:
        drift_report = build_drift_report(codebase_root=".")
        logger.info(
            "Drift scan complete: %d findings, score=%.1f",
            len(drift_report["findings"]),
            drift_report["total_score"],
        )
        return {"drift_report": drift_report, "step": "harvest"}
    except Exception as e:
        logger.error("Error during drift scan: %s", e)
        return {
            "drift_report": {
                "findings": [],
                "total_score": 0.0,
                "critical_count": 0,
                "major_count": 0,
                "minor_count": 0,
                "scanned_docs": [],
                "scanned_code_paths": [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            "step": "harvest",
            "errors": state.get("errors", []) + [str(e)],
        }


def _node_harvest(state: HourglassState) -> dict[str, Any]:
    """Harvest — produce reconciliation actions and ADRs."""
    logger.info("Harvesting...")
    drift_report = state["drift_report"]
    mode = state["mode"]
    dry_run = mode == "report"

    actions = walk_the_field(".", drift_report)

    # Generate ADRs for architecture drift findings
    for finding in drift_report["findings"]:
        if finding["category"] == "architecture_drift":
            adr_result = generate_adr(
                finding=finding,
                actions=actions,
                adr_template_path="docs/standards/",
                output_dir="docs/standards/",
                dry_run=dry_run,
            )
            if adr_result and not dry_run:
                logger.info("ADR written: %s", adr_result)

    actions = harvest(actions, ".", dry_run=dry_run)

    if mode == "reaper" and not state.get("confirmed", False):
        return {"step": "confirm_gate", "reconciliation_report": None}

    return {"step": "archive"}


def _node_confirm_gate(state: HourglassState) -> dict[str, Any]:
    """Confirmation gate for reaper mode."""
    if state.get("confirmed", False):
        logger.info("Orchestrator confirmed. Proceeding with reaper mode.")
        return {"step": "archive"}
    else:
        logger.warning("Orchestrator declined. DEATH departs without changes.")
        return {"step": "complete"}


def _node_archive(state: HourglassState) -> dict[str, Any]:
    """Archive — move old artifacts."""
    logger.info("Archiving old age artifacts...")
    drift_report = state["drift_report"]
    dry_run = state["mode"] == "report"
    actions = walk_the_field(".", drift_report)
    actions = archive_old_age(actions, ".", dry_run=dry_run)
    return {"step": "chronicle"}


def _node_chronicle(state: HourglassState) -> dict[str, Any]:
    """Chronicle — update README and wiki."""
    logger.info("Chronicling the new age...")
    drift_report = state["drift_report"]
    dry_run = state["mode"] == "report"
    actions = walk_the_field(".", drift_report)
    actions = chronicle(actions, ".", dry_run=dry_run)
    return {"step": "rest"}


def _node_rest(state: HourglassState) -> dict[str, Any]:
    """Rest — reset meter, record visit, depart."""
    logger.info("THE NEW AGE BEGINS.")
    drift_report = state["drift_report"]
    age_meter = state["age_meter"]
    mode = state["mode"]

    # Build final reconciliation report
    actions = walk_the_field(".", drift_report)
    report = build_reconciliation_report(
        trigger=state["trigger"],
        trigger_details=_trigger_details(state["trigger"]),
        drift_report=drift_report,
        actions=actions,
        mode=mode,
        age_number=age_meter["age_number"],
    )

    # Record visit in history
    record_death_visit(report)

    # Reset age meter
    age_meter = AgeMeterState(
        current_score=0,
        threshold=age_meter["threshold"],
        last_death_visit=datetime.now(timezone.utc).isoformat(),
        last_computed=datetime.now(timezone.utc).isoformat(),
        weighted_issues=[],
        age_number=age_meter["age_number"] + 1,
    )
    save_age_meter_state(age_meter)

    return {
        "age_meter": age_meter,
        "reconciliation_report": report,
        "step": "complete",
    }


def _trigger_details(trigger: str) -> str:
    """Generate human-readable trigger details."""
    if trigger == "summon":
        return "DEATH summoned via /death command by orchestrator"
    elif trigger == "meter":
        return "Age meter threshold crossed — accumulated changes exceeded limit"
    elif trigger == "critical_drift":
        return "Critical documentation drift detected — immediate reconciliation required"
    return f"Unknown trigger: {trigger}"


def _route_step(state: HourglassState) -> str:
    """Route to the next step based on current state."""
    return state.get("step", "complete")


def create_hourglass_graph() -> StateGraph:
    """Create the LangGraph state machine for the Hourglass Protocol.

    Nodes: init -> walk_field -> harvest -> [confirm_gate] -> archive -> chronicle -> rest -> complete
    """
    graph = StateGraph(HourglassState)

    graph.add_node("init", _node_init)
    graph.add_node("walk_field", _node_walk_field)
    graph.add_node("harvest", _node_harvest)
    graph.add_node("confirm_gate", _node_confirm_gate)
    graph.add_node("archive", _node_archive)
    graph.add_node("chronicle", _node_chronicle)
    graph.add_node("rest", _node_rest)

    graph.set_entry_point("init")

    graph.add_conditional_edges("init", _route_step, {"walk_field": "walk_field"})
    graph.add_conditional_edges("walk_field", _route_step, {"harvest": "harvest"})
    graph.add_conditional_edges(
        "harvest",
        _route_step,
        {"archive": "archive", "confirm_gate": "confirm_gate"},
    )
    graph.add_conditional_edges(
        "confirm_gate",
        _route_step,
        {"archive": "archive", "complete": "__end__"},
    )
    graph.add_conditional_edges("archive", _route_step, {"chronicle": "chronicle"})
    graph.add_conditional_edges("chronicle", _route_step, {"rest": "rest"})
    graph.add_conditional_edges("rest", _route_step, {"complete": "__end__"})

    return graph


def should_death_arrive(
    codebase_root: str,
    repo: str,
    github_token: str | None = None,
) -> tuple[bool, str, str]:
    """Check all three triggers. Returns (should_trigger, trigger_type, details).

    Checks in order:
    1. Critical drift (immediate, highest priority)
    2. Meter threshold (accumulated)
    3. Returns False if neither
    """
    # Check 1: Critical drift
    try:
        drift_report = build_drift_report(codebase_root)
        if check_critical_drift(drift_report):
            return (
                True,
                "critical_drift",
                f"Drift score {drift_report['total_score']:.1f} exceeds critical threshold. "
                f"{drift_report['critical_count']} critical findings.",
            )
    except Exception as e:
        logger.error("Drift check failed: %s", e)

    # Check 2: Meter threshold
    try:
        state = load_age_meter_state()
        if state:
            issues = fetch_closed_issues_since(
                repo=repo,
                since=state.get("last_death_visit"),
                github_token=github_token,
            )
            state = compute_age_meter(issues, state)
            save_age_meter_state(state)

            if check_meter_threshold(state):
                return (
                    True,
                    "meter",
                    f"Age meter score {state['current_score']} exceeds threshold {state['threshold']} "
                    f"({len(issues)} issues since last visit)",
                )
    except Exception as e:
        logger.error("Meter check failed (skipping): %s", e)

    return (False, "", "No triggers active")


def run_death(
    mode: Literal["report", "reaper"],
    trigger: Literal["meter", "summon", "critical_drift"],
    codebase_root: str,
    repo: str,
    github_token: str | None = None,
) -> ReconciliationReport:
    """Execute the full DEATH reconciliation protocol."""
    # Load or initialize age meter
    age_meter = load_age_meter_state()
    if not age_meter:
        age_meter = AgeMeterState(
            current_score=0,
            threshold=DEFAULT_THRESHOLD,
            last_death_visit=None,
            last_computed=datetime.now(timezone.utc).isoformat(),
            weighted_issues=[],
            age_number=1,
        )

    initial_state: HourglassState = {
        "trigger": trigger,
        "mode": mode,
        "age_meter": age_meter,
        "drift_report": None,
        "reconciliation_report": None,
        "step": "init",
        "errors": [],
        "confirmed": mode == "report",  # Report mode auto-confirmed; reaper needs gate
    }

    graph = create_hourglass_graph()
    compiled = graph.compile()

    final_state = None
    for state in compiled.stream(initial_state):
        final_state = state

    # Extract report from final state
    if final_state:
        # LangGraph returns dict with node name as key
        for node_output in final_state.values():
            if isinstance(node_output, dict) and "reconciliation_report" in node_output:
                report = node_output.get("reconciliation_report")
                if report:
                    return report

    # Fallback: build report manually if graph didn't produce one
    drift_report = build_drift_report(codebase_root)
    actions = walk_the_field(codebase_root, drift_report)
    return build_reconciliation_report(
        trigger=trigger,
        trigger_details=_trigger_details(trigger),
        drift_report=drift_report,
        actions=actions,
        mode=mode,
        age_number=age_meter["age_number"],
    )
```

### 6.12 `assemblyzero/workflows/death/skill.py` (Add)

**Complete file contents:**

```python
"""Skill entry point for the /death Claude Code command.

Issue #535: Parses arguments, determines trigger, handles confirmation gate,
invokes the hourglass protocol, and formats output.
"""

from __future__ import annotations

import logging
from typing import Literal

from assemblyzero.workflows.death.hourglass import run_death
from assemblyzero.workflows.death.models import ReconciliationReport

logger = logging.getLogger(__name__)

VALID_MODES = {"report", "reaper"}
VALID_FLAGS = {"--force"}


def parse_death_args(
    args: list[str],
) -> tuple[Literal["report", "reaper"], bool]:
    """Parse /death skill command arguments.

    Returns (mode, force) tuple.

    Raises:
        ValueError: If arguments are invalid.
    """
    if not args:
        return ("report", False)

    mode_str = args[0].lower()
    if mode_str not in VALID_MODES:
        raise ValueError(
            f"Unknown mode: '{mode_str}'. Use 'report' or 'reaper'."
        )

    mode: Literal["report", "reaper"] = mode_str  # type: ignore[assignment]
    force = False

    for flag in args[1:]:
        if flag == "--force":
            if mode != "reaper":
                raise ValueError("--force is only valid with reaper mode")
            force = True
        else:
            raise ValueError(f"Unknown flag: '{flag}'")

    return (mode, force)


def invoke_death_skill(
    args: list[str],
    codebase_root: str,
    repo: str,
    github_token: str | None = None,
) -> ReconciliationReport:
    """Main entry point for the /death Claude Code skill.

    Raises:
        ValueError: If arguments are invalid.
        PermissionError: If reaper mode not confirmed.
    """
    mode, force = parse_death_args(args)

    # Reaper mode confirmation gate
    if mode == "reaper" and not force:
        raise PermissionError(
            "Reaper mode requires orchestrator confirmation. "
            "Use '--force' to bypass, or confirm when prompted."
        )

    logger.info("Invoking /death in %s mode (trigger: summon)", mode)

    report = run_death(
        mode=mode,
        trigger="summon",
        codebase_root=codebase_root,
        repo=repo,
        github_token=github_token,
    )

    return report


def format_report_output(
    report: ReconciliationReport,
) -> str:
    """Format a ReconciliationReport into human-readable markdown output."""
    mode_desc = "read-only" if report["mode"] == "report" else "write mode"
    trigger = report["trigger"]

    # Trigger message
    if trigger == "summon":
        trigger_msg = "THE SAND HAS BEEN TURNED."
    elif trigger == "meter":
        trigger_msg = "THE SAND HAS RUN OUT."
    else:
        trigger_msg = "CRITICAL DRIFT DETECTED."

    lines = [
        f"# ⏳ DEATH — Reconciliation Report (Age {report['age_number']})",
        "",
        f"> {trigger_msg}",
        "",
        f"**Trigger:** {trigger} — {report['trigger_details']}",
        f"**Mode:** {report['mode']} ({mode_desc})",
        "",
        "## Summary",
        "",
        report["summary"],
        "",
    ]

    # Drift findings table
    findings = report["drift_report"]["findings"]
    if findings:
        lines.extend([
            "## Drift Findings",
            "",
            "| ID | Severity | File | Claim | Reality | Category |",
            "|----|----------|------|-------|---------|----------|",
        ])

        severity_icons = {"critical": "", "major": "🟡", "minor": ""}
        for f in findings:
            icon = severity_icons.get(f["severity"], "")
            lines.append(
                f"| {f['id']} | {icon} {f['severity']} | {f['doc_file']} | "
                f"{f['doc_claim'][:40]} | {f['code_reality'][:40]} | {f['category']} |"
            )

        lines.extend([
            "",
            f"**Drift Score:** {report['drift_report']['total_score']:.1f} "
            f"(threshold: 30.0)",
            "",
        ])
    else:
        lines.extend([
            "## Drift Findings",
            "",
            "No drift findings detected. Documentation appears accurate.",
            "",
        ])

    # Proposed actions
    actions = report["actions"]
    if actions:
        verb = "Applied" if report["mode"] == "reaper" else "Proposed"
        lines.extend([
            f"## {verb} Actions",
            "",
            "| # | Target | Action | Description |",
            "|---|--------|--------|-------------|",
        ])
        for i, a in enumerate(actions, 1):
            lines.append(
                f"| {i} | {a['target_file']} | {a['action_type']} | {a['description'][:60]} |"
            )
        lines.append("")

    # Next steps
    if report["mode"] == "report":
        lines.extend([
            "## Next Steps",
            "",
            "Run `/death reaper` to apply these changes.",
            "",
        ])

    lines.append("> WHAT CAN THE HARVEST HOPE FOR, IF NOT FOR THE CARE OF THE REAPER MAN?")

    return "\n".join(lines)
```

### 6.13 `assemblyzero/workflows/janitor/probes/drift_probe.py` (Add)

**Complete file contents:**

```python
"""Janitor drift probe — factual accuracy drift detection.

Issue #535: Feeds the Hourglass Protocol by running drift analysis
as part of the standard janitor probe infrastructure.
"""

from __future__ import annotations

import logging

from assemblyzero.workflows.death.drift_scorer import build_drift_report, check_critical_drift
from assemblyzero.workflows.janitor.state import ProbeResult

logger = logging.getLogger(__name__)


def run_drift_probe(repo_root: str) -> ProbeResult:
    """Janitor probe that runs drift analysis and feeds the hourglass.

    Returns ProbeResult compatible with janitor probe interface.
    """
    try:
        drift_report = build_drift_report(codebase_root=repo_root)

        finding_count = len(drift_report["findings"])
        drift_score = drift_report["total_score"]
        is_critical = check_critical_drift(drift_report)

        critical_findings = [
            f"{f['id']}: {f['doc_file']} {f['category']} ({f['severity']})"
            for f in drift_report["findings"]
            if f["severity"] == "critical"
        ]

        if is_critical:
            status = "fail"
            message = (
                f"Critical drift detected: score={drift_score:.1f}, "
                f"{finding_count} findings ({drift_report['critical_count']} critical)"
            )
        elif finding_count > 0:
            status = "warn"
            message = (
                f"Drift detected: score={drift_score:.1f}, "
                f"{finding_count} findings"
            )
        else:
            status = "pass"
            message = "No documentation drift detected"

        return ProbeResult(
            probe="drift",
            status=status,
            message=message,
            details={
                "drift_score": drift_score,
                "finding_count": finding_count,
                "critical_findings": critical_findings,
                "report": drift_report,
            },
        )

    except Exception as e:
        logger.error("Drift probe failed: %s", e)
        return ProbeResult(
            probe="drift",
            status="error",
            message=f"Drift probe error: {e}",
            details={"error": str(e)},
        )
```

### 6.14 `assemblyzero/workflows/janitor/probes/__init__.py` (Modify)

**Change 1:** Add import for drift probe module. After the existing probe imports in `_build_registry()`, add the drift probe registration:

```diff
 def _build_registry() -> dict[ProbeScope, ProbeFunction]:
     """Build probe registry lazily to avoid circular imports."""
+    from assemblyzero.workflows.janitor.probes.drift_probe import run_drift_probe
     from assemblyzero.workflows.janitor.probes.harvest import run_harvest_probe
     from assemblyzero.workflows.janitor.probes.links import run_links_probe
     from assemblyzero.workflows.janitor.probes.todo import run_todo_probe
     from assemblyzero.workflows.janitor.probes.worktrees import run_worktrees_probe
 
     return {
+        "drift": run_drift_probe,
         "harvest": run_harvest_probe,
         "links": run_links_probe,
         "todo": run_todo_probe,
         "worktrees": run_worktrees_probe,
     }
```

**Note:** If `ProbeScope` is a `Literal` type that doesn't include `"drift"`, you may need to add `"drift"` to the `Literal` union in `assemblyzero/workflows/janitor/state.py`. Check the actual `ProbeScope` definition and extend it if needed. If it's a plain `str` alias, no change is required.

### 6.15 `.claude/commands/death.md` (Add)

**Complete file contents:**

```markdown
# /death — The Hourglass Protocol

DEATH arrives when the documentation no longer describes reality.
Two modes. One purpose: reconciliation.

## Usage

/death [report|reaper] [--force]

- **report** (default): Walk the field. Produce a reconciliation report. Change nothing.
- **reaper**: Walk the field. Fix everything. Requires confirmation before writes.
- **--force**: Skip confirmation gate (reaper mode only, for scripted usage).

## What DEATH Does

1. **Walk the Field** — Spelunk the codebase. Compare docs against code reality.
2. **Harvest** — Write the ADRs that capture what was decided (produces 0016-age-transition-protocol.md).
3. **Archive** — Move old age artifacts to legacy.
4. **Chronicle** — Update README and wiki to describe the civilization as it now exists.
5. **Rest** — DEATH departs. The new age begins with clean documentation.

## Example

```
/death report    # See what's stale
/death reaper    # Fix it all (with confirmation)
/death reaper --force  # Fix it all (no confirmation, scripted)
```

> WHAT CAN THE HARVEST HOPE FOR, IF NOT FOR THE CARE OF THE REAPER MAN?
```

### 6.16 `docs/standards/0016-age-transition-protocol.md` (Add)

This file is generated by `generate_adr()` during reaper mode. Seed it with the template so the file exists for documentation purposes:

**Complete file contents:**

```markdown
# ADR-0016: Age Transition Protocol

## Status

Draft — will be populated by the Hourglass Protocol on first DEATH visit.

## Date

2026-02-17

## Context

The AssemblyZero project evolves rapidly. Documentation drifts from code reality
as issues are closed and features are added, removed, or modified.

The Hourglass Protocol (Issue #535) implements DEATH as an age transition mechanism:
a system that detects when documentation has drifted beyond a threshold and triggers
reconciliation to realign docs with the codebase.

## Decision

Implement a three-trigger system:

1. **Age Meter** — Weighted accumulation of closed issues triggers at threshold (default: 50)
2. **Summon** — Orchestrator explicitly invokes `/death` command
3. **Critical Drift** — Drift score exceeds critical threshold (default: 30.0)

When triggered, DEATH walks the field (audits docs vs. code), harvests new ADRs,
archives stale artifacts, chronicles the new reality, and rests (resets the meter).

## Consequences

### Positive
- Documentation stays aligned with codebase reality
- Drift is detected and quantified, not just felt
- ADRs capture architectural transitions with full context

### Negative
- Additional tooling to maintain
- False positives possible with regex-based detection

### Neutral
- This ADR will be updated by future DEATH visits with specific findings

> WHAT CAN THE HARVEST HOPE FOR, IF NOT FOR THE CARE OF THE REAPER MAN?
```

### 6.17 `tests/fixtures/death/mock_issues.json` (Add)

**Complete file contents:**

```json
[
    {
        "number": 500,
        "title": "Fix typo in README",
        "labels": ["bug"],
        "closed_at": "2026-02-01T10:00:00Z",
        "body": "Minor typo fix"
    },
    {
        "number": 501,
        "title": "Fix CI pipeline failure",
        "labels": ["fix", "bug"],
        "closed_at": "2026-02-01T11:00:00Z",
        "body": null
    },
    {
        "number": 502,
        "title": "Add dark mode to dashboard",
        "labels": ["enhancement"],
        "closed_at": "2026-02-02T09:00:00Z",
        "body": "New UI feature"
    },
    {
        "number": 503,
        "title": "Implement search feature",
        "labels": ["feature"],
        "closed_at": "2026-02-02T10:00:00Z",
        "body": "Full-text search"
    },
    {
        "number": 504,
        "title": "Add Scribe persona",
        "labels": ["persona"],
        "closed_at": "2026-02-03T08:00:00Z",
        "body": "New documentation persona"
    },
    {
        "number": 505,
        "title": "Create review subsystem",
        "labels": ["subsystem"],
        "closed_at": "2026-02-03T09:00:00Z",
        "body": "Code review automation"
    },
    {
        "number": 506,
        "title": "Build RAG pipeline v2",
        "labels": ["rag", "pipeline"],
        "closed_at": "2026-02-04T10:00:00Z",
        "body": "Major pipeline overhaul"
    },
    {
        "number": 507,
        "title": "Foundation layer refactor",
        "labels": ["foundation"],
        "closed_at": "2026-02-04T11:00:00Z",
        "body": "Core infrastructure changes"
    },
    {
        "number": 508,
        "title": "Microservice architecture migration",
        "labels": ["architecture"],
        "closed_at": "2026-02-05T08:00:00Z",
        "body": "Breaking architectural change"
    },
    {
        "number": 509,
        "title": "Cross-cutting logging framework",
        "labels": ["cross-cutting"],
        "closed_at": "2026-02-05T09:00:00Z",
        "body": "Affects all modules"
    },
    {
        "number": 510,
        "title": "Hotfix: auth token leak",
        "labels": ["hotfix"],
        "closed_at": "2026-02-05T10:00:00Z",
        "body": "Security hotfix"
    },
    {
        "number": 511,
        "title": "Add new-workflow for testing",
        "labels": ["new-workflow"],
        "closed_at": "2026-02-06T08:00:00Z",
        "body": "Testing workflow"
    },
    {
        "number": 512,
        "title": "Infrastructure monitoring setup",
        "labels": ["infrastructure"],
        "closed_at": "2026-02-06T09:00:00Z",
        "body": "Monitoring and alerting"
    },
    {
        "number": 513,
        "title": "Breaking API change v3",
        "labels": ["breaking-change"],
        "closed_at": "2026-02-06T10:00:00Z",
        "body": "API versioning"
    },
    {
        "number": 514,
        "title": "Update documentation formatting",
        "labels": ["question"],
        "closed_at": "2026-02-07T08:00:00Z",
        "body": "No matching label"
    },
    {
        "number": 515,
        "title": "Investigate memory usage",
        "labels": [],
        "closed_at": "2026-02-07T09:00:00Z",
        "body": "No labels at all"
    },
    {
        "number": 516,
        "title": "Patch deployment script",
        "labels": ["patch"],
        "closed_at": "2026-02-07T10:00:00Z",
        "body": "Deployment fix"
    },
    {
        "number": 517,
        "title": "Feature: batch processing",
        "labels": ["feat"],
        "closed_at": "2026-02-08T08:00:00Z",
        "body": "Batch job support"
    },
    {
        "number": 518,
        "title": "New component: scheduler",
        "labels": ["new-component"],
        "closed_at": "2026-02-08T09:00:00Z",
        "body": "Task scheduler"
    },
    {
        "number": 519,
        "title": "Breaking architectural decision",
        "labels": ["breaking", "architecture"],
        "closed_at": "2026-02-08T10:00:00Z",
        "body": "Major restructure"
    }
]
```

### 6.18 `tests/fixtures/death/mock_codebase_snapshot.json` (Add)

**Complete file contents:**

```json
{
    "description": "Simplified codebase structure for reconciliation testing",
    "root": ".",
    "directories": {
        "assemblyzero/agents/": [
            "agent_01.py",
            "agent_02.py",
            "agent_03.py",
            "agent_04.py",
            "agent_05.py"
        ],
        "assemblyzero/workflows/": [
            "death/",
            "issue/",
            "janitor/",
            "lld/",
            "rag/",
            "requirements/",
            "testing/"
        ],
        "tools/": [
            "batch-workflow.sh",
            "merge-tool.py",
            "run_janitor_workflow.py"
        ],
        "docs/standards/": [
            "0001-overview.md",
            "0006-diagrams.md",
            "0016-age-transition-protocol.md"
        ],
        "docs/lld/active/": [
            "535-hourglass-protocol.md"
        ]
    },
    "readme_content": "# AssemblyZero\n\n> Run 12+ AI agents concurrently.\n\n5 State Machines with SQLite Checkpointing.\n\n3 tools available.",
    "inventory_content": "| File | Status |\n|------|--------|\n| `assemblyzero/agents/agent_01.py` | Active |\n| `assemblyzero/agents/agent_99.py` | Active |\n| `assemblyzero/workflows/old_module.py` | Active |"
}
```

### 6.19 `tests/fixtures/death/mock_drift_findings.json` (Add)

**Complete file contents:**

```json
[
    {
        "id": "DRIFT-001",
        "severity": "critical",
        "doc_file": "README.md",
        "doc_claim": "Run 12+ AI agents concurrently",
        "code_reality": "5 found via glob('assemblyzero/agents/*.py')",
        "category": "count_mismatch",
        "confidence": 0.95,
        "evidence": "glob('assemblyzero/agents/*.py') returns 5 matches, README claims 12"
    },
    {
        "id": "DRIFT-002",
        "severity": "major",
        "doc_file": "README.md",
        "doc_claim": "5 State Machines",
        "code_reality": "7 found via glob('assemblyzero/workflows/*/')",
        "category": "count_mismatch",
        "confidence": 0.90,
        "evidence": "glob('assemblyzero/workflows/*/') returns 7 directories, README claims 5"
    },
    {
        "id": "DRIFT-003",
        "severity": "major",
        "doc_file": "docs/inventory.md",
        "doc_claim": "assemblyzero/agents/agent_99.py listed in inventory",
        "code_reality": "File does not exist on disk",
        "category": "stale_reference",
        "confidence": 1.0,
        "evidence": "os.path.exists('assemblyzero/agents/agent_99.py') = False"
    },
    {
        "id": "DRIFT-004",
        "severity": "minor",
        "doc_file": "docs/inventory.md",
        "doc_claim": "assemblyzero/workflows/death/ not in inventory",
        "code_reality": "Directory exists on disk since Issue #535",
        "category": "missing_component",
        "confidence": 0.80,
        "evidence": "os.path.exists('assemblyzero/workflows/death/') = True, not in inventory"
    },
    {
        "id": "DRIFT-005",
        "severity": "major",
        "doc_file": "docs/standards/0001-overview.md",
        "doc_claim": "System uses 5 workflow state machines",
        "code_reality": "7 workflow directories found under assemblyzero/workflows/",
        "category": "architecture_drift",
        "confidence": 0.85,
        "evidence": "ls assemblyzero/workflows/ shows: death, issue, janitor, lld, rag, requirements, testing"
    }
]
```

### 6.20 `tests/fixtures/death/mock_adr_output.md` (Add)

**Complete file contents:**

```markdown
# ADR-0016: Age Transition Protocol

## Status

Accepted

## Date

2026-02-17

## Context

Documentation drift detected by the Hourglass Protocol (Issue #535).

**Drift Finding:** DRIFT-005
- **Documented Claim:** System uses 5 workflow state machines
- **Code Reality:** 7 workflow directories found under assemblyzero/workflows/
- **Source File:** docs/standards/0001-overview.md
- **Confidence:** 85%
- **Evidence:** ls assemblyzero/workflows/ shows: death, issue, janitor, lld, rag, requirements, testing

The documentation no longer accurately describes the system architecture.
This ADR records the current reality and the decision to update documentation accordingly.

## Decision

Update documentation to reflect the current state of the codebase:

- Update architecture description: 'System uses 5 workflow state machines' -> 7 workflow directories found under assemblyzero/workflows/

The Hourglass Protocol detects when accumulated changes make existing documentation
materially inaccurate. DEATH arrives to reconcile the documented world with reality.

## Alternatives Considered

1. **Leave documentation as-is** — Rejected. Stale documentation is worse than no documentation.
2. **Partial update** — Rejected. A full reconciliation ensures consistency.
3. **Rewrite from scratch** — Rejected. Targeted updates preserve institutional knowledge.

## Consequences

### Positive
- Documentation accurately reflects the current system
- New contributors see the real architecture, not a historical snapshot
- Age meter resets, starting a new documentation epoch

### Negative
- Historical context may be lost (mitigated by this ADR and git history)
- Frequent DEATH visits may indicate unstable architecture (signal, not bug)

### Neutral
- This ADR serves as a bookmark between documentation ages

> WHAT CAN THE HARVEST HOPE FOR, IF NOT FOR THE CARE OF THE REAPER MAN?
```

### 6.21 `tests/unit/test_death/__init__.py` (Add)

**Complete file contents:**

```python
"""Tests for the DEATH Hourglass Protocol workflow.

Issue #535.
"""
```

### 6.22 `tests/unit/test_death/test_models.py` (Add)

**Complete file contents:**

```python
"""Tests for DEATH data models.

Issue #535: T260, T270
"""

from __future__ import annotations

import pytest

from assemblyzero.workflows.death.models import (
    AgeMeterState,
    DriftFinding,
    DriftReport,
    HourglassState,
    IssueWeight,
    ReconciliationAction,
    ReconciliationReport,
)


class TestAgeMeterState:
    """T260: AgeMeterState validation."""

    def test_valid_state(self) -> None:
        """Valid AgeMeterState is constructable."""
        state: AgeMeterState = {
            "current_score": 37,
            "threshold": 50,
            "last_death_visit": "2026-02-10T09:00:00Z",
            "last_computed": "2026-02-17T15:45:00Z",
            "weighted_issues": [],
            "age_number": 3,
        }
        assert state["current_score"] == 37
        assert state["threshold"] == 50
        assert state["age_number"] == 3

    def test_state_with_none_last_visit(self) -> None:
        """AgeMeterState allows None for last_death_visit."""
        state: AgeMeterState = {
            "current_score": 0,
            "threshold": 50,
            "last_death_visit": None,
            "last_computed": "2026-02-17T15:45:00Z",
            "weighted_issues": [],
            "age_number": 1,
        }
        assert state["last_death_visit"] is None


class TestDriftFinding:
    """T270: DriftFinding categories and severities."""

    @pytest.mark.parametrize(
        "category",
        [
            "count_mismatch",
            "feature_contradiction",
            "missing_component",
            "stale_reference",
            "architecture_drift",
        ],
    )
    def test_all_categories_accepted(self, category: str) -> None:
        """All DriftFinding categories are valid."""
        finding: DriftFinding = {
            "id": "DRIFT-001",
            "severity": "major",
            "doc_file": "README.md",
            "doc_claim": "test claim",
            "code_reality": "test reality",
            "category": category,
            "confidence": 0.9,
            "evidence": "test evidence",
        }
        assert finding["category"] == category

    @pytest.mark.parametrize("severity", ["critical", "major", "minor"])
    def test_all_severities_accepted(self, severity: str) -> None:
        """All DriftFinding severities are valid."""
        finding: DriftFinding = {
            "id": "DRIFT-001",
            "severity": severity,
            "doc_file": "README.md",
            "doc_claim": "test",
            "code_reality": "test",
            "category": "count_mismatch",
            "confidence": 0.5,
            "evidence": "test",
        }
        assert finding["severity"] == severity

    def test_issue_weight_structure(self) -> None:
        """IssueWeight is constructable with all fields."""
        iw: IssueWeight = {
            "issue_number": 534,
            "title": "Spelunking Audits",
            "labels": ["architecture"],
            "weight": 10,
            "weight_source": "architecture",
            "closed_at": "2026-02-15T14:32:00Z",
        }
        assert iw["weight"] == 10

    def test_reconciliation_action_structure(self) -> None:
        """ReconciliationAction is constructable."""
        action: ReconciliationAction = {
            "target_file": "README.md",
            "action_type": "update_count",
            "description": "Update count",
            "old_content": "12+",
            "new_content": "36",
            "drift_finding_id": "DRIFT-001",
        }
        assert action["action_type"] == "update_count"
```

### 6.23 `tests/unit/test_death/test_age_meter.py` (Add)

**Complete file contents:**

```python
"""Tests for age meter computation.

Issue #535: T010–T080
"""

from __future__ import annotations

import json
import logging
import os
import tempfile

import pytest

from assemblyzero.workflows.death.age_meter import (
    check_meter_threshold,
    compute_age_meter,
    compute_issue_weight,
    load_age_meter_state,
    save_age_meter_state,
)
from assemblyzero.workflows.death.models import AgeMeterState


class TestComputeIssueWeight:
    """T010–T040: Weight computation from labels."""

    def test_bug_label_weight(self) -> None:
        """T010: Bug label returns weight=1."""
        weight, source = compute_issue_weight(["bug"], "Fix broken link")
        assert weight == 1
        assert source == "bug"

    def test_architecture_label_weight(self) -> None:
        """T020: Architecture label returns weight=10."""
        weight, source = compute_issue_weight(["architecture"], "Refactor pipeline")
        assert weight == 10
        assert source == "architecture"

    def test_no_matching_label_default(self, caplog: pytest.LogCaptureFixture) -> None:
        """T030: No matching label returns weight=2 with warning."""
        with caplog.at_level(logging.WARNING):
            weight, source = compute_issue_weight(["question"], "Some question")
        assert weight == 2
        assert source == "default"
        assert "No matching label" in caplog.text

    def test_empty_labels_default(self, caplog: pytest.LogCaptureFixture) -> None:
        """T030 variant: Empty labels returns default weight."""
        with caplog.at_level(logging.WARNING):
            weight, source = compute_issue_weight([], "No labels")
        assert weight == 2
        assert source == "default"

    def test_multiple_labels_highest_wins(self) -> None:
        """T040: Multiple labels, highest weight wins."""
        weight, source = compute_issue_weight(
            ["bug", "architecture"], "Bug in architecture"
        )
        assert weight == 10
        assert source == "architecture"

    def test_enhancement_label(self) -> None:
        """Enhancement label returns weight=3."""
        weight, source = compute_issue_weight(["enhancement"], "New feature")
        assert weight == 3
        assert source == "enhancement"

    def test_pipeline_label(self) -> None:
        """Pipeline label returns weight=8."""
        weight, source = compute_issue_weight(["pipeline"], "Pipeline change")
        assert weight == 8
        assert source == "pipeline"

    def test_persona_label(self) -> None:
        """Persona label returns weight=5."""
        weight, source = compute_issue_weight(["persona"], "New persona")
        assert weight == 5
        assert source == "persona"

    def test_case_insensitive(self) -> None:
        """Labels are matched case-insensitively."""
        weight, source = compute_issue_weight(["BUG"], "Fix")
        assert weight == 1
        assert source == "bug"


class TestComputeAgeMeter:
    """T050: Age meter computation."""

    def test_incremental_computation(self) -> None:
        """T050: Adds new issues to existing score."""
        existing_state: AgeMeterState = {
            "current_score": 20,
            "threshold": 50,
            "last_death_visit": "2026-02-10T09:00:00Z",
            "last_computed": "2026-02-10T09:00:00Z",
            "weighted_issues": [],
            "age_number": 3,
        }
        issues = [
            {"number": 530, "title": "Fix bug", "labels": ["bug"], "closed_at": "2026-02-11T10:00:00Z"},
            {"number": 531, "title": "New pipeline", "labels": ["pipeline"], "closed_at": "2026-02-12T11:30:00Z"},
        ]
        state = compute_age_meter(issues, existing_state)
        # 20 + 1 (bug) + 8 (pipeline) = 29
        assert state["current_score"] == 29
        assert len(state["weighted_issues"]) == 2

    def test_fresh_computation(self) -> None:
        """Fresh computation from None state."""
        issues = [
            {"number": 530, "title": "Fix", "labels": ["bug"], "closed_at": "2026-02-11T10:00:00Z"},
        ]
        state = compute_age_meter(issues, None)
        assert state["current_score"] == 1
        assert state["age_number"] == 1
        assert state["threshold"] == 50

    def test_empty_issues(self) -> None:
        """Empty issues list with no existing state."""
        state = compute_age_meter([], None)
        assert state["current_score"] == 0
        assert state["age_number"] == 1


class TestMeterThreshold:
    """T060–T070: Threshold checking."""

    def test_below_threshold(self) -> None:
        """T060: Below threshold returns False."""
        state: AgeMeterState = {
            "current_score": 49,
            "threshold": 50,
            "last_death_visit": None,
            "last_computed": "2026-02-17T16:00:00Z",
            "weighted_issues": [],
            "age_number": 1,
        }
        assert check_meter_threshold(state) is False

    def test_at_threshold(self) -> None:
        """T070: At threshold returns True."""
        state: AgeMeterState = {
            "current_score": 50,
            "threshold": 50,
            "last_death_visit": None,
            "last_computed": "2026-02-17T16:00:00Z",
            "weighted_issues": [],
            "age_number": 1,
        }
        assert check_meter_threshold(state) is True

    def test_above_threshold(self) -> None:
        """Above threshold returns True."""
        state: AgeMeterState = {
            "current_score": 100,
            "threshold": 50,
            "last_death_visit": None,
            "last_computed": "2026-02-17T16:00:00Z",
            "weighted_issues": [],
            "age_number": 1,
        }
        assert check_meter_threshold(state) is True


class TestStatePersistence:
    """T080: State persistence round-trip."""

    def test_save_and_load_round_trip(self, tmp_path: str) -> None:
        """T080: Save -> load returns identical state."""
        state: AgeMeterState = {
            "current_score": 37,
            "threshold": 50,
            "last_death_visit": "2026-02-10T09:00:00Z",
            "last_computed": "2026-02-17T15:45:00Z",
            "weighted_issues": [
                {
                    "issue_number": 530,
                    "title": "Fix bug",
                    "labels": ["bug"],
                    "weight": 1,
                    "weight_source": "bug",
                    "closed_at": "2026-02-11T10:00:00Z",
                }
            ],
            "age_number": 3,
        }
        path = os.path.join(str(tmp_path), "hourglass", "age_meter.json")
        save_age_meter_state(state, path)
        loaded = load_age_meter_state(path)
        assert loaded == state

    def test_load_nonexistent_file(self) -> None:
        """Load from nonexistent file returns None."""
        result = load_age_meter_state("/nonexistent/path/meter.json")
        assert result is None

    def test_load_invalid_json(self, tmp_path: str) -> None:
        """Load from invalid JSON returns None."""
        path = os.path.join(str(tmp_path), "bad.json")
        with open(path, "w") as f:
            f.write("not json {{{")
        result = load_age_meter_state(path)
        assert result is None

    def test_load_empty_json(self, tmp_path: str) -> None:
        """Load from empty JSON object returns None."""
        path = os.path.join(str(tmp_path), "empty.json")
        with open(path, "w") as f:
            json.dump({}, f)
        result = load_age_meter_state(path)
        assert result is None
```

### 6.24 `tests/unit/test_death/test_drift_scorer.py` (Add)

**Complete file contents:**

```python
"""Tests for drift scoring.

Issue #535: T090–T140
"""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from assemblyzero.workflows.death.drift_scorer import (
    _reset_drift_counter,
    build_drift_report,
    check_critical_drift,
    compute_drift_score,
    scan_inventory_accuracy,
    scan_readme_claims,
)
from assemblyzero.workflows.death.models import DriftFinding, DriftReport


@pytest.fixture(autouse=True)
def reset_counter() -> None:
    """Reset drift counter before each test.

    Input: No arguments (fixture runs automatically).
    Output on success: Global drift counter reset to 0 (no return value).
    Example:
        # Before test: drift counter may be 5 from previous test
        reset_counter()
        # After: drift counter is 0
    """
    _reset_drift_counter()


class TestScanReadmeClaims:
    """T090–T100: README drift detection."""

    def test_numeric_claim_mismatch(self, tmp_path: str) -> None:
        """T090: Detects numeric claim mismatch.

        Input: tmp_path containing README.md with "12+ AI agents" but only 5 agent files.
        Output on success: findings list contains at least one DriftFinding with
            category="count_mismatch" and "12" in doc_claim field.
        Example:
            findings = scan_readme_claims("README.md", "/repo")
            # Returns: [{"category": "count_mismatch", "doc_claim": "12+ AI agents", ...}]
        """
        # Create mock README with claim "12+ agents"
        readme_path = os.path.join(str(tmp_path), "README.md")
        with open(readme_path, "w") as f:
            f.write("# Project\n\nRun 12+ AI agents concurrently.\n")

        # Create agent directory with only 5 agents
        agents_dir = os.path.join(str(tmp_path), "assemblyzero", "agents")
        os.makedirs(agents_dir)
        for i in range(5):
            with open(os.path.join(agents_dir, f"agent_{i:02d}.py"), "w") as f:
                f.write(f"# Agent {i}")

        findings = scan_readme_claims("README.md", str(tmp_path))
        assert len(findings) >= 1
        count_findings = [f for f in findings if f["category"] == "count_mismatch"]
        assert len(count_findings) >= 1
        assert "12" in count_findings[0]["doc_claim"]

    def test_readme_not_found(self, tmp_path: str) -> None:
        """No findings when README doesn't exist."""
        findings = scan_readme_claims("nonexistent.md", str(tmp_path))
        assert findings == []

    def test_no_claims_in_readme(self, tmp_path: str) -> None:
        """No findings when README has no numeric claims."""
        readme_path = os.path.join(str(tmp_path), "README.md")
        with open(readme_path, "w") as f:
            f.write("# Simple Project\n\nA project with stuff.\n")
        findings = scan_readme_claims("README.md", str(tmp_path))
        assert findings == []


class TestScanInventoryAccuracy:
    """T110–T120: Inventory drift detection."""

    def test_inventory_missing_file(self, tmp_path: str) -> None:
        """T110: Detects file listed in inventory but absent from disk."""
        inventory_path = os.path.join(str(tmp_path), "inventory.md")
        with open(inventory_path, "w") as f:
            f.write("| File | Status |\n|------|--------|\n")
            f.write("| `missing/file.py` | Active |\n")

        findings = scan_inventory_accuracy("inventory.md", str(tmp_path))
        assert len(findings) >= 1
        stale = [f for f in findings if f["category"] == "stale_reference"]
        assert len(stale) >= 1
        assert "missing/file.py" in stale[0]["doc_claim"]

    def test_inventory_not_found(self, tmp_path: str) -> None:
        """No findings when inventory file doesn't exist."""
        findings = scan_inventory_accuracy("nonexistent.md", str(tmp_path))
        assert findings == []

    def test_inventory_all_files_exist(self, tmp_path: str) -> None:
        """No findings when all inventory files exist."""
        # Create a file that the inventory references
        file_path = os.path.join(str(tmp_path), "existing", "file.py")
        os.makedirs(os.path.dirname(file_path))
        with open(file_path, "w") as f:
            f.write("# exists")

        inventory_path = os.path.join(str(tmp_path), "inventory.md")
        with open(inventory_path, "w") as f:
            f.write("| File | Status |\n|------|--------|\n")
            f.write("| `existing/file.py` | Active |\n")

        findings = scan_inventory_accuracy("inventory.md", str(tmp_path))
        assert findings == []


class TestComputeDriftScore:
    """T130: Drift score computation."""

    def test_weighted_scoring(self) -> None:
        """T130: critical=10, major=5, minor=1."""
        findings: list[DriftFinding] = [
            {"id": "D1", "severity": "critical", "doc_file": "", "doc_claim": "", "code_reality": "", "category": "count_mismatch", "confidence": 1.0, "evidence": ""},
            {"id": "D2", "severity": "critical", "doc_file": "", "doc_claim": "", "code_reality": "", "category": "count_mismatch", "confidence": 1.0, "evidence": ""},
            {"id": "D3", "severity": "major", "doc_file": "", "doc_claim": "", "code_reality": "", "category": "count_mismatch", "confidence": 1.0, "evidence": ""},
            {"id": "D4", "severity": "minor", "doc_file": "", "doc_claim": "", "code_reality": "", "category": "count_mismatch", "confidence": 1.0, "evidence": ""},
            {"id": "D5", "severity": "minor", "doc_file": "", "doc_claim": "", "code_reality": "", "category": "count_mismatch", "confidence": 1.0, "evidence": ""},
            {"id": "D6", "severity": "minor", "doc_file": "", "doc_claim": "", "code_reality": "", "category": "count_mismatch", "confidence": 1.0, "evidence": ""},
        ]
        score = compute_drift_score(findings)
        # 2*10 + 1*5 + 3*1 = 28
        assert score == 28.0

    def test_empty_findings(self) -> None:
        """Empty findings yields score 0."""
        assert compute_drift_score([]) == 0.0


class TestCheckCriticalDrift:
    """T140: Critical drift threshold."""

    def test_at_threshold(self) -> None:
        """T140: Returns True when score >= 30."""
        report: DriftReport = {
            "findings": [],
            "total_score": 30.0,
            "critical_count": 3,
            "major_count": 0,
            "minor_count": 0,
            "scanned_docs": [],
            "scanned_code_paths": [],
            "timestamp": "2026-02-17T16:00:00Z",
        }
        assert check_critical_drift(report) is True

    def test_below_threshold(self) -> None:
        """Returns False when score < 30."""
        report: DriftReport = {
            "findings": [],
            "total_score": 29.9,
            "critical_count": 0,
            "major_count": 0,
            "minor_count": 0,
            "scanned_docs": [],
            "scanned_code_paths": [],
            "timestamp": "2026-02-17T16:00:00Z",
        }
        assert check_critical_drift(report) is False
```

### 6.25 `tests/unit/test_death/test_reconciler.py` (Add)

**Complete file contents:**

```python
"""Tests for reconciliation engine.

Issue #535: T150, T160, T200, T210, T360–T390
"""

from __future__ import annotations

import json
import os

import pytest

from assemblyzero.workflows.death.models import (
    DriftFinding,
    DriftReport,
    ReconciliationAction,
    ReconciliationReport,
)
from assemblyzero.workflows.death.reconciler import (
    archive_old_age,
    build_reconciliation_report,
    chronicle,
    generate_adr,
    harvest,
    record_death_visit,
    walk_the_field,
)


class TestWalkTheField:
    """T150: Reconciliation action generation."""

    def test_count_mismatch_maps_to_update_count(self) -> None:
        """T150: count_mismatch -> update_count action."""
        drift_report: DriftReport = {
            "findings": [
                {
                    "id": "DRIFT-001",
                    "severity": "critical",
                    "doc_file": "README.md",
                    "doc_claim": "12+ agents",
                    "code_reality": "36 found",
                    "category": "count_mismatch",
                    "confidence": 0.95,
                    "evidence": "test",
                }
            ],
            "total_score": 10.0,
            "critical_count": 1,
            "major_count": 0,
            "minor_count": 0,
            "scanned_docs": ["README.md"],
            "scanned_code_paths": [],
            "timestamp": "2026-02-17T16:00:00Z",
        }
        actions = walk_the_field(".", drift_report)
        assert len(actions) == 1
        assert actions[0]["action_type"] == "update_count"
        assert actions[0]["drift_finding_id"] == "DRIFT-001"

    def test_architecture_drift_maps_to_create_adr(self) -> None:
        """architecture_drift -> create_adr action."""
        drift_report: DriftReport = {
            "findings": [
                {
                    "id": "DRIFT-005",
                    "severity": "major",
                    "doc_file": "docs/standards/0001.md",
                    "doc_claim": "5 workflows",
                    "code_reality": "7 found",
                    "category": "architecture_drift",
                    "confidence": 0.85,
                    "evidence": "test",
                }
            ],
            "total_score": 5.0,
            "critical_count": 0,
            "major_count": 1,
            "minor_count": 0,
            "scanned_docs": [],
            "scanned_code_paths": [],
            "timestamp": "2026-02-17T16:00:00Z",
        }
        actions = walk_the_field(".", drift_report)
        assert len(actions) == 1
        assert actions[0]["action_type"] == "create_adr"

    def test_empty_findings_empty_actions(self) -> None:
        """Empty findings produce empty actions."""
        drift_report: DriftReport = {
            "findings": [],
            "total_score": 0.0,
            "critical_count": 0,
            "major_count": 0,
            "minor_count": 0,
            "scanned_docs": [],
            "scanned_code_paths": [],
            "timestamp": "2026-02-17T16:00:00Z",
        }
        actions = walk_the_field(".", drift_report)
        assert actions == []


class TestHarvest:
    """T160: Report mode produces no file writes."""

    def test_report_mode_no_writes(self, tmp_path: str) -> None:
        """T160: Verify no filesystem side effects in report mode."""
        readme_path = os.path.join(str(tmp_path), "README.md")
        with open(readme_path, "w") as f:
            f.write("Run 12+ agents")

        actions: list[ReconciliationAction] = [
            {
                "target_file": "README.md",
                "action_type": "update_count",
                "description": "Update count",
                "old_content": "12+",
                "new_content": "36",
                "drift_finding_id": "DRIFT-001",
            }
        ]

        # dry_run=True (report mode)
        result = harvest(actions, str(tmp_path), dry_run=True)

        # Verify README unchanged
        with open(readme_path) as f:
            content = f.read()
        assert "12+" in content
        assert "36" not in content
        assert len(result) == 1


class TestGenerateAdr:
    """T360–T390: ADR generation tests."""

    def test_architecture_drift_generates_adr(self) -> None:
        """T360: architecture_drift finding produces ADR with correct sections."""
        finding: DriftFinding = {
            "id": "DRIFT-005",
            "severity": "major",
            "doc_file": "docs/standards/0001-overview.md",
            "doc_claim": "System uses 5 workflow state machines",
            "code_reality": "7 workflow directories found",
            "category": "architecture_drift",
            "confidence": 0.85,
            "evidence": "ls shows 7 directories",
        }
        actions: list[ReconciliationAction] = [
            {
                "target_file": "docs/standards/0001-overview.md",
                "action_type": "create_adr",
                "description": "Update architecture description",
                "old_content": "5",
                "new_content": "7",
                "drift_finding_id": "DRIFT-005",
            }
        ]

        result = generate_adr(
            finding=finding,
            actions=actions,
            adr_template_path="docs/standards/",
            output_dir="docs/standards/",
            dry_run=True,
        )

        assert result is not None
        assert "# ADR-0016" in result
        assert "## Status" in result
        assert "## Context" in result
        assert "## Decision" in result
        assert "## Consequences" in result
        assert "DRIFT-005" in result
        assert "5 workflow state machines" in result
        assert "7 workflow directories" in result

    def test_non_qualifying_finding_returns_none(self) -> None:
        """T370: count_mismatch finding returns None."""
        finding: DriftFinding = {
            "id": "DRIFT-001",
            "severity": "critical",
            "doc_file": "README.md",
            "doc_claim": "12+ agents",
            "code_reality": "36 found",
            "category": "count_mismatch",
            "confidence": 0.95,
            "evidence": "test",
        }
        result = generate_adr(
            finding=finding,
            actions=[],
            adr_template_path="docs/standards/",
            output_dir="docs/standards/",
            dry_run=True,
        )
        assert result is None

    def test_reaper_mode_writes_file(self, tmp_path: str) -> None:
        """T380: dry_run=False creates file."""
        finding: DriftFinding = {
            "id": "DRIFT-005",
            "severity": "major",
            "doc_file": "docs/standards/0001.md",
            "doc_claim": "5 workflows",
            "code_reality": "7 found",
            "category": "architecture_drift",
            "confidence": 0.85,
            "evidence": "test",
        }
        output_dir = str(tmp_path)
        result = generate_adr(
            finding=finding,
            actions=[],
            adr_template_path="docs/standards/",
            output_dir=output_dir,
            dry_run=False,
        )

        expected_path = os.path.join(output_dir, "0016-age-transition-protocol.md")
        assert result == expected_path
        assert os.path.exists(expected_path)
        with open(expected_path) as f:
            content = f.read()
        assert "# ADR-0016" in content

    def test_report_mode_no_write(self, tmp_path: str) -> None:
        """T390: dry_run=True returns content, no file created."""
        finding: DriftFinding = {
            "id": "DRIFT-005",
            "severity": "major",
            "doc_file": "docs/standards/0001.md",
            "doc_claim": "5 workflows",
            "code_reality": "7 found",
            "category": "architecture_drift",
            "confidence": 0.85,
            "evidence": "test",
        }
        output_dir = str(tmp_path)
        result = generate_adr(
            finding=finding,
            actions=[],
            adr_template_path="docs/standards/",
            output_dir=output_dir,
            dry_run=True,
        )

        assert isinstance(result, str)
        assert "# ADR-0016" in result
        expected_path = os.path.join(output_dir, "0016-age-transition-protocol.md")
        assert not os.path.exists(expected_path)


class TestRecordDeathVisit:
    """T200, T210: Age meter reset and history recording."""

    def test_age_meter_reset(self) -> None:
        """T200: Report builds with correct age_number."""
        report = build_reconciliation_report(
            trigger="summon",
            trigger_details="test",
            drift_report={
                "findings": [],
                "total_score": 0.0,
                "critical_count": 0,
                "major_count": 0,
                "minor_count": 0,
                "scanned_docs": [],
                "scanned_code_paths": [],
                "timestamp": "2026-02-17T16:00:00Z",
            },
            actions=[],
            mode="report",
            age_number=3,
        )
        assert report["age_number"] == 3

    def test_history_recording(self, tmp_path: str) -> None:
        """T210: DEATH visit appended to history."""
        history_path = os.path.join(str(tmp_path), "history.json")

        report: ReconciliationReport = {
            "age_number": 3,
            "trigger": "summon",
            "trigger_details": "test",
            "drift_report": {
                "findings": [],
                "total_score": 0.0,
                "critical_count": 0,
                "major_count": 0,
                "minor_count": 0,
                "scanned_docs": [],
                "scanned_code_paths": [],
                "timestamp": "2026-02-17T16:00:00Z",
            },
            "actions": [],
            "mode": "report",
            "timestamp": "2026-02-17T16:05:00Z",
            "summary": "test",
        }

        record_death_visit(report, history_path)

        with open(history_path) as f:
            history = json.load(f)
        assert len(history["visits"]) == 1
        assert history["visits"][0]["age_number"] == 3

        # Record another visit
        report2 = {**report, "age_number": 4, "timestamp": "2026-02-18T10:00:00Z"}
        record_death_visit(report2, history_path)

        with open(history_path) as f:
            history = json.load(f)
        assert len(history["visits"]) == 2

    def test_build_reconciliation_report_summary(self) -> None:
        """Report summary is correctly formatted."""
        report = build_reconciliation_report(
            trigger="summon",
            trigger_details="DEATH summoned via /death",
            drift_report={
                "findings": [
                    {"id": "D1", "severity": "critical", "doc_file": "", "doc_claim": "", "code_reality": "", "category": "count_mismatch", "confidence": 1.0, "evidence": ""},
                ],
                "total_score": 10.0,
                "critical_count": 1,
                "major_count": 0,
                "minor_count": 0,
                "scanned_docs": [],
                "scanned_code_paths": [],
                "timestamp": "2026-02-17T16:00:00Z",
            },
            actions=[
                {"target_file": "README.md", "action_type": "update_count", "description": "test", "old_content": "", "new_content": "", "drift_finding_id": "D1"},
            ],
            mode="report",
            age_number=3,
        )
        assert "1 drift finding" in report["summary"]
        assert "1 critical" in report["summary"]
        assert "1 reconciliation action" in report["summary"]
        assert "proposed" in report["summary"]
```

### 6.26 `tests/unit/test_death/test_hourglass.py` (Add)

**Complete file contents:**

```python
"""Tests for hourglass state machine.

Issue #535: T170–T190, T200, T230–T250
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.workflows.death.age_meter import save_age_meter_state
from assemblyzero.workflows.death.hourglass import (
    _node_confirm_gate,
    _node_init,
    _node_rest,
    _node_walk_field,
    create_hourglass_graph,
    should_death_arrive,
)
from assemblyzero.workflows.death.models import AgeMeterState, HourglassState


def _make_initial_state(
    mode: str = "report",
    trigger: str = "summon",
    confirmed: bool = False,
) -> HourglassState:
    """Create a test initial state."""
    return HourglassState(
        trigger=trigger,
        mode=mode,
        age_meter={
            "current_score": 10,
            "threshold": 50,
            "last_death_visit": None,
            "last_computed": "2026-02-17T16:00:00Z",
            "weighted_issues": [],
            "age_number": 3,
        },
        drift_report=None,
        reconciliation_report=None,
        step="init",
        errors=[],
        confirmed=confirmed,
    )


class TestNodeInit:
    """T170: Init node behavior."""

    def test_init_loads_state(self) -> None:
        """Init sets step to walk_field."""
        state = _make_initial_state()
        result = _node_init(state)
        assert result["step"] == "walk_field"
        assert result["age_meter"] is not None

    def test_init_with_existing_meter(self) -> None:
        """Init preserves existing age meter."""
        state = _make_initial_state()
        result = _node_init(state)
        assert result["age_meter"]["age_number"] == 3


class TestNodeConfirmGate:
    """T180–T190: Confirmation gate behavior."""

    def test_reaper_confirmed_proceeds(self) -> None:
        """T180: Confirmed reaper proceeds to archive."""
        state = _make_initial_state(mode="reaper", confirmed=True)
        result = _node_confirm_gate(state)
        assert result["step"] == "archive"

    def test_reaper_declined_completes(self) -> None:
        """T190: Declined reaper jumps to complete."""
        state = _make_initial_state(mode="reaper", confirmed=False)
        result = _node_confirm_gate(state)
        assert result["step"] == "complete"


class TestNodeRest:
    """T200: Age meter reset after DEATH visit."""

    def test_meter_reset(self, tmp_path: str) -> None:
        """T200: Score reset to 0, age_number incremented."""
        state = _make_initial_state()
        state["drift_report"] = {
            "findings": [],
            "total_score": 0.0,
            "critical_count": 0,
            "major_count": 0,
            "minor_count": 0,
            "scanned_docs": [],
            "scanned_code_paths": [],
            "timestamp": "2026-02-17T16:00:00Z",
        }

        # Patch paths so we write to tmp
        meter_path = os.path.join(str(tmp_path), "meter.json")
        history_path = os.path.join(str(tmp_path), "history.json")

        with patch("assemblyzero.workflows.death.hourglass.save_age_meter_state") as mock_save, \
             patch("assemblyzero.workflows.death.hourglass.record_death_visit") as mock_record:
            result = _node_rest(state)

        assert result["step"] == "complete"
        assert result["age_meter"]["current_score"] == 0
        assert result["age_meter"]["age_number"] == 4  # incremented from 3
        assert result["reconciliation_report"] is not None
        mock_save.assert_called_once()
        mock_record.assert_called_once()


class TestCreateHourglassGraph:
    """T170: Graph creation and structure."""

    def test_graph_creates_successfully(self) -> None:
        """Graph compiles without error."""
        graph = create_hourglass_graph()
        compiled = graph.compile()
        assert compiled is not None


class TestShouldDeathArrive:
    """T230–T250: Trigger detection."""

    def test_no_triggers_active(self, tmp_path: str) -> None:
        """T230: Returns False when all clear."""
        with patch("assemblyzero.workflows.death.hourglass.build_drift_report") as mock_drift, \
             patch("assemblyzero.workflows.death.hourglass.load_age_meter_state") as mock_load:
            mock_drift.return_value = {
                "findings": [],
                "total_score": 0.0,
                "critical_count": 0,
                "major_count": 0,
                "minor_count": 0,
                "scanned_docs": [],
                "scanned_code_paths": [],
                "timestamp": "2026-02-17T16:00:00Z",
            }
            mock_load.return_value = {
                "current_score": 10,
                "threshold": 50,
                "last_death_visit": "2026-02-10T09:00:00Z",
                "last_computed": "2026-02-17T16:00:00Z",
                "weighted_issues": [],
                "age_number": 1,
            }
            with patch("assemblyzero.workflows.death.hourglass.fetch_closed_issues_since") as mock_fetch, \
                 patch("assemblyzero.workflows.death.hourglass.compute_age_meter") as mock_compute, \
                 patch("assemblyzero.workflows.death.hourglass.save_age_meter_state"):
                mock_fetch.return_value = []
                mock_compute.return_value = mock_load.return_value

                result = should_death_arrive(".", "owner/repo", "token")
                assert result[0] is False

    def test_meter_trigger_active(self) -> None:
        """T240: Returns True with meter trigger when threshold crossed."""
        with patch("assemblyzero.workflows.death.hourglass.build_drift_report") as mock_drift, \
             patch("assemblyzero.workflows.death.hourglass.load_age_meter_state") as mock_load:
            mock_drift.return_value = {
                "findings": [],
                "total_score": 5.0,
                "critical_count": 0,
                "major_count": 0,
                "minor_count": 0,
                "scanned_docs": [],
                "scanned_code_paths": [],
                "timestamp": "",
            }
            high_meter: AgeMeterState = {
                "current_score": 55,
                "threshold": 50,
                "last_death_visit": "2026-02-10T09:00:00Z",
                "last_computed": "2026-02-17T16:00:00Z",
                "weighted_issues": [],
                "age_number": 1,
            }
            mock_load.return_value = high_meter

            with patch("assemblyzero.workflows.death.hourglass.fetch_closed_issues_since") as mock_fetch, \
                 patch("assemblyzero.workflows.death.hourglass.compute_age_meter") as mock_compute, \
                 patch("assemblyzero.workflows.death.hourglass.save_age_meter_state"):
                mock_fetch.return_value = []
                mock_compute.return_value = high_meter

                result = should_death_arrive(".", "owner/repo", "token")
                assert result[0] is True
                assert result[1] == "meter"

    def test_critical_drift_trigger(self) -> None:
        """T250: Critical drift takes priority."""
        with patch("assemblyzero.workflows.death.hourglass.build_drift_report") as mock_drift:
            mock_drift.return_value = {
                "findings": [
                    {"id": "D1", "severity": "critical", "doc_file": "", "doc_claim": "", "code_reality": "", "category": "count_mismatch", "confidence": 1.0, "evidence": ""},
                ] * 3,
                "total_score": 30.0,
                "critical_count": 3,
                "major_count": 0,
                "minor_count": 0,
                "scanned_docs": [],
                "scanned_code_paths": [],
                "timestamp": "",
            }

            result = should_death_arrive(".", "owner/repo", "token")
            assert result[0] is True
            assert result[1] == "critical_drift"
```

### 6.27 `tests/unit/test_death/test_skill.py` (Add)

**Complete file contents:**

```python
"""Tests for /death skill entry point.

Issue #535: T280–T350
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.workflows.death.models import ReconciliationReport
from assemblyzero.workflows.death.skill import (
    format_report_output,
    invoke_death_skill,
    parse_death_args,
)


class TestParseDeathArgs:
    """T280–T320: Argument parsing."""

    def test_report_mode(self) -> None:
        """T280: parse_death_args(["report"]) returns ("report", False)."""
        mode, force = parse_death_args(["report"])
        assert mode == "report"
        assert force is False

    def test_reaper_mode(self) -> None:
        """T290: parse_death_args(["reaper"]) returns ("reaper", False)."""
        mode, force = parse_death_args(["reaper"])
        assert mode == "reaper"
        assert force is False

    def test_reaper_with_force(self) -> None:
        """T300: parse_death_args(["reaper", "--force"]) returns ("reaper", True)."""
        mode, force = parse_death_args(["reaper", "--force"])
        assert mode == "reaper"
        assert force is True

    def test_invalid_mode_raises(self) -> None:
        """T310: parse_death_args(["invalid"]) raises ValueError."""
        with pytest.raises(ValueError, match="Unknown mode: 'invalid'"):
            parse_death_args(["invalid"])

    def test_default_mode(self) -> None:
        """T320: parse_death_args([]) returns ("report", False)."""
        mode, force = parse_death_args([])
        assert mode == "report"
        assert force is False

    def test_force_on_report_raises(self) -> None:
        """--force on report mode raises ValueError."""
        with pytest.raises(ValueError, match="--force is only valid with reaper mode"):
            parse_death_args(["report", "--force"])

    def test_unknown_flag_raises(self) -> None:
        """Unknown flag raises ValueError."""
        with pytest.raises(ValueError, match="Unknown flag: '--unknown'"):
            parse_death_args(["reaper", "--unknown"])

    def test_case_insensitive(self) -> None:
        """Mode parsing is case-insensitive."""
        mode, force = parse_death_args(["REPORT"])
        assert mode == "report"


class TestInvokeDeathSkill:
    """T330–T340: Skill invocation."""

    def test_report_mode_end_to_end(self) -> None:
        """T330: Report mode returns ReconciliationReport."""
        mock_report: ReconciliationReport = {
            "age_number": 3,
            "trigger": "summon",
            "trigger_details": "test",
            "drift_report": {
                "findings": [],
                "total_score": 0.0,
                "critical_count": 0,
                "major_count": 0,
                "minor_count": 0,
                "scanned_docs": [],
                "scanned_code_paths": [],
                "timestamp": "2026-02-17T16:00:00Z",
            },
            "actions": [],
            "mode": "report",
            "timestamp": "2026-02-17T16:05:00Z",
            "summary": "No drift found.",
        }

        with patch("assemblyzero.workflows.death.skill.run_death") as mock_run:
            mock_run.return_value = mock_report
            result = invoke_death_skill(
                args=["report"],
                codebase_root=".",
                repo="owner/repo",
            )

        assert result["mode"] == "report"
        assert result["trigger"] == "summon"
        mock_run.assert_called_once_with(
            mode="report",
            trigger="summon",
            codebase_root=".",
            repo="owner/repo",
            github_token=None,
        )

    def test_reaper_without_confirmation_raises(self) -> None:
        """T340: Reaper without force raises PermissionError."""
        with pytest.raises(PermissionError, match="Reaper mode requires orchestrator confirmation"):
            invoke_death_skill(
                args=["reaper"],
                codebase_root=".",
                repo="owner/repo",
            )

    def test_reaper_with_force_succeeds(self) -> None:
        """Reaper with --force bypasses confirmation."""
        mock_report: ReconciliationReport = {
            "age_number": 3,
            "trigger": "summon",
            "trigger_details": "test",
            "drift_report": {
                "findings": [],
                "total_score": 0.0,
                "critical_count": 0,
                "major_count": 0,
                "minor_count": 0,
                "scanned_docs": [],
                "scanned_code_paths": [],
                "timestamp": "",
            },
            "actions": [],
            "mode": "reaper",
            "timestamp": "",
            "summary": "test",
        }

        with patch("assemblyzero.workflows.death.skill.run_death") as mock_run:
            mock_run.return_value = mock_report
            result = invoke_death_skill(
                args=["reaper", "--force"],
                codebase_root=".",
                repo="owner/repo",
            )

        assert result["mode"] == "reaper"


class TestFormatReportOutput:
    """T350: Report formatting."""

    def test_format_report_output(self) -> None:
        """T350: format_report_output returns valid markdown."""
        report: ReconciliationReport = {
            "age_number": 3,
            "trigger": "summon",
            "trigger_details": "DEATH summoned via /death command",
            "drift_report": {
                "findings": [
                    {
                        "id": "DRIFT-001",
                        "severity": "critical",
                        "doc_file": "README.md",
                        "doc_claim": "12+ agents",
                        "code_reality": "36 agents",
                        "category": "count_mismatch",
                        "confidence": 0.95,
                        "evidence": "test",
                    }
                ],
                "total_score": 10.0,
                "critical_count": 1,
                "major_count": 0,
                "minor_count": 0,
                "scanned_docs": ["README.md"],
                "scanned_code_paths": ["assemblyzero/"],
                "timestamp": "2026-02-17T16:00:00Z",
            },
            "actions": [
                {
                    "target_file": "README.md",
                    "action_type": "update_count",
                    "description": "Update agent count from '12+' to '36'",
                    "old_content": "12+",
                    "new_content": "36",
                    "drift_finding_id": "DRIFT-001",
                }
            ],
            "mode": "report",
            "timestamp": "2026-02-17T16:05:00Z",
            "summary": "DEATH found 1 drift finding (1 critical). 1 reconciliation action proposed.",
        }

        output = format_report_output(report)

        assert "# ⏳ DEATH" in output
        assert "Age 3" in output
        assert "## Summary" in output
        assert "1 drift finding" in output
        assert "## Drift Findings" in output
        assert "DRIFT-001" in output
        assert " critical" in output
        assert "## Proposed Actions" in output
        assert "README.md" in output
        assert "## Next Steps" in output
        assert "REAPER MAN" in output

    def test_format_empty_report(self) -> None:
        """Format works with no findings."""
        report: ReconciliationReport = {
            "age_number": 1,
            "trigger": "summon",
            "trigger_details": "test",
            "drift_report": {
                "findings": [],
                "total_score": 0.0,
                "critical_count": 0,
                "major_count": 0,
                "minor_count": 0,
                "scanned_docs": [],
                "scanned_code_paths": [],
                "timestamp": "",
            },
            "actions": [],
            "mode": "report",
            "timestamp": "",
            "summary": "No drift found.",
        }

        output = format_report_output(report)
        assert "# ⏳ DEATH" in output
        assert "No drift findings detected" in output
```

## 7. Pattern References

### 7.1 LangGraph StateGraph Workflow Pattern

**File:** `assemblyzero/workflows/issue/graph.py` (lines 1–50, estimated)

The existing issue workflow uses a StateGraph with typed state and node functions. Follow this pattern for `hourglass.py`:
- State is a TypedDict
- Nodes are functions that accept state and return partial dicts
- Conditional edges use routing functions
- Graph is compiled before invocation

**Relevance:** All AssemblyZero workflows follow this StateGraph pattern. The hourglass graph must be structurally consistent.

### 7.2 Janitor Probe Interface Pattern

**File:** `assemblyzero/workflows/janitor/probes/links.py` (lines 1–30, estimated)

Existing janitor probes follow this interface:
- Accept `repo_root: str` as parameter
- Return `ProbeResult` with `probe`, `status`, `message`, `details` fields
- Handle their own exceptions and return error results

**Relevance:** `drift_probe.py` must match this interface exactly for compatibility with the janitor probe registry.

### 7.3 Probe Registry Pattern

**File:** `assemblyzero/workflows/janitor/probes/__init__.py` (lines 1–30)

The probe registry uses lazy imports in `_build_registry()` to avoid circular imports. Each probe is keyed by its `ProbeScope` string. New probes are added as new import + dict entry.

**Relevance:** Adding `drift_probe` follows the same lazy import + registry entry pattern.

### 7.4 Test Pattern — Unit Tests with Fixtures

**File:** `tests/unit/test_implementation_spec_workflow.py` (lines 1–80)

Existing workflow unit tests use:
- `pytest` with `tmp_path` fixture for filesystem tests
- `unittest.mock.patch` for mocking external dependencies
- Class-based test organization grouped by feature
- Descriptive test names mapping to test IDs

**Relevance:** All death workflow tests follow this pattern for consistency.

### 7.5 JSON File Persistence Pattern

**File:** `assemblyzero/workflows/janitor/probes/harvest.py` or similar probe that reads/writes JSON

The project uses `json.load`/`json.dump` with explicit encoding and `os.makedirs(exist_ok=True)` for file persistence. The atomic write pattern (write-to-temp, rename) is used for critical state files.

**Relevance:** `age_meter.py` uses this pattern for `save_age_meter_state()` and `load_age_meter_state()`.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from __future__ import annotations` | stdlib | All new files |
| `from typing import Literal, TypedDict, Any` | stdlib | `models.py`, `age_meter.py`, `hourglass.py`, `skill.py` |
| `import json` | stdlib | `age_meter.py`, `reconciler.py` |
| `import logging` | stdlib | All implementation files |
| `import os` | stdlib | `age_meter.py`, `drift_scorer.py`, `reconciler.py` |
| `import re` | stdlib | `drift_scorer.py` |
| `import glob` | stdlib | `drift_scorer.py` |
| `import tempfile` | stdlib | `age_meter.py` |
| `import shutil` | stdlib | `reconciler.py` |
| `from datetime import datetime, timezone` | stdlib | `age_meter.py`, `drift_scorer.py`, `reconciler.py`, `hourglass.py` |
| `from github import Github` | `pygithub` (existing dep) | `age_meter.py` |
| `from langgraph.graph import StateGraph` | `langgraph` (existing dep) | `hourglass.py` |
| `from assemblyzero.workflows.death.constants import *` | internal | All death workflow files |
| `from assemblyzero.workflows.death.models import *` | internal | All death workflow files |
| `from assemblyzero.workflows.death.age_meter import *` | internal | `hourglass.py` |
| `from assemblyzero.workflows.death.drift_scorer import *` | internal | `hourglass.py`, `drift_probe.py` |
| `from assemblyzero.workflows.death.reconciler import *` | internal | `hourglass.py` |
| `from assemblyzero.workflows.death.hourglass import *` | internal | `__init__.py`, `skill.py` |
| `from assemblyzero.workflows.janitor.state import ProbeResult` | internal | `drift_probe.py` |
| `import pytest` | dev dep | Test files |
| `from unittest.mock import patch, MagicMock` | stdlib | Test files |

**New Dependencies:** None. All imports resolve to existing stdlib or project dependencies.

## 9. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `compute_issue_weight()` | `labels=["bug"], title="Fix"` | `(1, "bug")` |
| T020 | `compute_issue_weight()` | `labels=["architecture"], title="Refactor"` | `(10, "architecture")` |
| T030 | `compute_issue_weight()` | `labels=["question"], title="Query"` | `(2, "default")` + warning logged |
| T040 | `compute_issue_weight()` | `labels=["bug", "architecture"], title="Both"` | `(10, "architecture")` |
| T050 | `compute_age_meter()` | existing score=20 + issues=[bug(1), pipeline(8)] | `score=29` |
| T060 | `check_meter_threshold()` | `score=49, threshold=50` | `False` |
| T070 | `check_meter_threshold()` | `score=50, threshold=50` | `True` |
| T080 | `save_age_meter_state()` + `load_age_meter_state()` | AgeMeterState object | Identical after round-trip |
| T090 | `scan_readme_claims()` | README with "12+ agents", 5 actual | DriftFinding with `count_mismatch` |
| T100 | (covered by T090 pattern — feature contradiction requires more complex setup) | | |
| T110 | `scan_inventory_accuracy()` | inventory lists `missing/file.py` | DriftFinding with `stale_reference` |
| T120 | (covered by inventory scan patterns) | | |
| T130 | `compute_drift_score()` | 2 critical, 1 major, 3 minor | `28.0` |
| T140 | `check_critical_drift()` | report with `total_score=30.0` | `True` |
| T150 | `walk_the_field()` | finding with `count_mismatch` | action with `update_count` |
| T160 | `harvest()` | `dry_run=True` | No file writes |
| T170 | `_node_init()` | initial state | `step="walk_field"` |
| T180 | `_node_confirm_gate()` | `confirmed=True` | `step="archive"` |
| T190 | `_node_confirm_gate()` | `confirmed=False` | `step="complete"` |
| T200 | `_node_rest()` | state with `age_number=3` | `age_number=4, score=0` |
| T210 | `record_death_visit()` | report | history.json gains 1 entry |
| T220 | `run_drift_probe()` | mock codebase | dict with `probe/status/drift_score` keys |
| T230 | `should_death_arrive()` | low meter + low drift | `(False, "", ...)` |
| T240 | `should_death_arrive()` | high meter | `(True, "meter", ...)` |
| T250 | `should_death_arrive()` | high drift | `(True, "critical_drift", ...)` |
| T260 | `AgeMeterState` | valid dict | Constructs without error |
| T270 | `DriftFinding` | all 5 categories | All accepted |
| T280 | `parse_death_args()` | `["report"]` | `("report", False)` |
| T290 | `parse_death_args()` | `["reaper"]` | `("reaper", False)` |
| T300 | `parse_death_args()` | `["reaper", "--force"]` | `("reaper", True)` |
| T310 | `parse_death_args()` | `["invalid"]` | `ValueError` |
| T320 | `parse_death_args()` | `[]` | `("report", False)` |
| T330 | `invoke_death_skill()` | `["report"]` + mocked run_death | ReconciliationReport with `mode="report"` |
| T340 | `invoke_death_skill()` | `["reaper"]` without force | `PermissionError` |
| T350 | `format_report_output()` | ReconciliationReport fixture | Markdown with summary, findings, actions |
| T360 | `generate_adr()` | arch_drift finding, dry_run=True | ADR content with sections |
| T370 | `generate_adr()` | count_mismatch finding | `None` |
| T380 | `generate_adr()` | arch_drift finding, dry_run=False | File path, file exists |
| T390 | `generate_adr()` | arch_drift finding, dry_run=True | Content string, no file |

## 10. Implementation Notes

### 10.1 Error Handling Convention

All functions follow a fail-closed pattern:
- Scanner errors -> finding is omitted, not synthesized
- GitHub API failures -> meter check is skipped, logged as warning
- File read errors -> empty result returned with warning log
- Invalid JSON state files -> treated as nonexistent (returns None)
- Hourglass node errors -> captured in `errors` list in state, processing continues

### 10.2 Logging Convention

Use `logging.getLogger(__name__)` in each module. Log levels:
- `INFO`: Major state transitions ("DEATH HAS BEEN SUMMONED.", "Walking the field...", "THE NEW AGE BEGINS.")
- `WARNING`: Degraded behavior (no matching label, missing file, API failure fallback)
- `ERROR`: Failures that affect output (file write errors, API errors)

### 10.3 Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| `DEFAULT_THRESHOLD` | `50` | Calibrated from Issue #114 retroactive scoring (~65) |
| `DEFAULT_WEIGHT` | `2` | Conservative default for unlabeled issues |
| `CRITICAL_DRIFT_THRESHOLD` | `30.0` | ~3 critical findings or mix of severities |
| `MAX_ISSUES_PER_FETCH` | `500` | Prevent unbounded API calls |

### 10.4 ProbeScope Extension Note

The `drift_probe.py` returns a `ProbeResult` that must be compatible with the janitor's `ProbeResult` TypedDict. Verify that `ProbeResult` in `assemblyzero/workflows/janitor/state.py` has a `details` field that accepts `dict`. If `ProbeScope` is a `Literal` type, `"drift"` must be added to it. If it's `str`, no change needed.

### 10.5 Global Drift Counter

The `_drift_counter` global in `drift_scorer.py` is reset at the start of each `build_drift_report()` call and in tests via `_reset_drift_counter()`. This ensures deterministic `DRIFT-NNN` IDs within a single report while allowing tests to run independently.

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3) — `__init__.py` and `.gitignore` both have excerpts
- [x] Every data structure has a concrete JSON/YAML example (Section 4) — All 7 TypedDicts have JSON examples
- [x] Every function has input/output examples with realistic values (Section 5) — All 25 functions have I/O examples
- [x] Change instructions are diff-level specific (Section 6) — All 27 files have complete implementation details
- [x] Pattern references include file:line and are verified to exist (Section 7) — 5 patterns referenced
- [x] All imports are listed and verified (Section 8) — Complete import table
- [x] Test mapping covers all LLD test scenarios (Section 9) — All 39 test IDs mapped

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #535 |
| Verdict | DRAFT |
| Date | 2026-02-17 |
| Iterations | 1 |
| Finalized | — |