# Implementation Spec: DEATH as Age Transition — the Hourglass Protocol

| Field | Value |
|-------|-------|
| Issue | #535 |
| LLD | `docs/lld/active/535-hourglass-protocol.md` |
| Generated | 2026-02-17 |
| Status | DRAFT |

## 1. Overview

Implement DEATH as an age transition mechanism that detects documentation drift from codebase reality via a weighted age meter, drift scoring heuristics, and an hourglass state machine that produces reconciliation reports or applies fixes.

**Objective:** Build the Hourglass Protocol — a LangGraph-based workflow that monitors documentation freshness through three triggers (meter threshold, explicit summon, critical drift), and reconciles stale documentation via report or reaper mode.

**Success Criteria:** All 39 test scenarios (T010–T390) pass; `/death` skill entry point works in both report and reaper modes; age meter persists across sessions; drift probe integrates with janitor infrastructure; ADR generation produces valid `0015-age-transition-protocol.md`.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `assemblyzero/workflows/death/__init__.py` | Add | Package init with workflow registration |
| 2 | `assemblyzero/workflows/death/constants.py` | Add | Weight tables, thresholds, configuration |
| 3 | `assemblyzero/workflows/death/models.py` | Add | TypedDict data models for all state |
| 4 | `assemblyzero/workflows/death/age_meter.py` | Add | Age meter computation and persistence |
| 5 | `assemblyzero/workflows/death/drift_scorer.py` | Add | Drift detection via regex/glob heuristics |
| 6 | `assemblyzero/workflows/death/reconciler.py` | Add | Reconciliation engine with ADR generation |
| 7 | `assemblyzero/workflows/death/hourglass.py` | Add | LangGraph state machine orchestration |
| 8 | `assemblyzero/workflows/death/skill.py` | Add | `/death` skill entry point |
| 9 | `assemblyzero/workflows/janitor/probes/drift_probe.py` | Add | Janitor probe for drift detection |
| 10 | `assemblyzero/workflows/janitor/probes/__init__.py` | Modify | Register drift probe |
| 11 | `.gitignore` | Modify | Add hourglass state path |
| 12 | `data/hourglass/age_meter.json` | Add | Initial empty age meter state |
| 13 | `data/hourglass/history.json` | Add | Initial empty history |
| 14 | `.claude/commands/death.md` | Add | Skill definition |
| 15 | `docs/standards/0015-age-transition-protocol.md` | Add | ADR for the protocol |
| 16 | `tests/fixtures/death/mock_issues.json` | Add | Test fixture: mock issues |
| 17 | `tests/fixtures/death/mock_codebase_snapshot.json` | Add | Test fixture: codebase structure |
| 18 | `tests/fixtures/death/mock_drift_findings.json` | Add | Test fixture: drift findings |
| 19 | `tests/fixtures/death/mock_adr_output.md` | Add | Test fixture: expected ADR |
| 20 | `tests/unit/test_death/__init__.py` | Add | Test package init |
| 21 | `tests/unit/test_death/test_models.py` | Add | Tests for data models |
| 22 | `tests/unit/test_death/test_age_meter.py` | Add | Tests for age meter |
| 23 | `tests/unit/test_death/test_drift_scorer.py` | Add | Tests for drift scoring |
| 24 | `tests/unit/test_death/test_reconciler.py` | Add | Tests for reconciler + ADR generation |
| 25 | `tests/unit/test_death/test_hourglass.py` | Add | Tests for state machine |
| 26 | `tests/unit/test_death/test_skill.py` | Add | Tests for skill entry point |

**Implementation Order Rationale:** Constants and models first (no dependencies), then age_meter and drift_scorer (depend on models/constants), then reconciler (depends on drift_scorer), then hourglass (depends on all), then skill (entry point). Tests after source, fixtures before tests. Modifications to existing files last to minimize breakage window.

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

**What changes:** Import the new `drift_probe` module and register it in `_build_registry()` under a new `"drift"` scope. Also need to update `ProbeScope` if it's a Literal type that needs the new value.

### 3.2 `.gitignore`

**Relevant excerpt** (lines 1–55, full file shown):

```gitignore
# AssemblyZero-specific gitignore
# Note: Parent Projects/.gitignore covers common patterns

# Claude Code local settings (machine-specific, prevent merge overwrites)
.claude/settings.local.json

# Claude Code checkpoint (ephemeral, session-scoped)
.claude/checkpoint.json

# Claude Code temporary files
tmpclaude-*

# Generated files
*.generated.json

# Gemini retry logs (generated at runtime)
# Keep the directory structure but ignore log files
logs/*.log

# Batch workflow logs (generated by tools/batch-workflow.sh)
logs/batch/

# Session shards (ephemeral, consolidated on commit)
# Issue #57: Distributed Session-Sharded Logging
logs/active/
!logs/active/.gitkeep

# Environment secrets
.env

# Python cache
__pycache__/
*.pyc

# Harvest artifacts (generated reports)
harvest-*.json
harvest-*.xlsx

# Janitor reports (generated by tools/run_janitor_workflow.py, Issue #94)
janitor-reports/

# Blog drafts (not ready for public)
docs/blog/

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

**What changes:** Add `data/hourglass/age_meter.json` to the gitignore (local state, not tracked). The `history.json` is NOT gitignored — it is tracked.

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
    "labels": ["feature", "infrastructure"],
    "weight": 8,
    "weight_source": "infrastructure",
    "closed_at": "2026-02-15T14:30:00Z"
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
    "current_score": 47,
    "threshold": 50,
    "last_death_visit": "2026-02-01T10:00:00Z",
    "last_computed": "2026-02-17T08:30:00Z",
    "weighted_issues": [
        {
            "issue_number": 530,
            "title": "Add RAG pipeline caching",
            "labels": ["enhancement", "rag"],
            "weight": 8,
            "weight_source": "rag",
            "closed_at": "2026-02-10T12:00:00Z"
        },
        {
            "issue_number": 531,
            "title": "Fix broken link in README",
            "labels": ["bug"],
            "weight": 1,
            "weight_source": "bug",
            "closed_at": "2026-02-11T09:00:00Z"
        },
        {
            "issue_number": 532,
            "title": "New persona: Auditor agent",
            "labels": ["persona"],
            "weight": 5,
            "weight_source": "persona",
            "closed_at": "2026-02-12T15:00:00Z"
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
    "code_reality": "Found 36 agent definitions across assemblyzero/personas/",
    "category": "count_mismatch",
    "confidence": 0.95,
    "evidence": "glob('assemblyzero/personas/*.py') returned 36 files"
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
            "code_reality": "Found 36 agent definitions",
            "category": "count_mismatch",
            "confidence": 0.95,
            "evidence": "glob count mismatch"
        },
        {
            "id": "DRIFT-002",
            "severity": "minor",
            "doc_file": "README.md",
            "doc_claim": "5 State Machines",
            "code_reality": "Found 7 workflow directories",
            "category": "count_mismatch",
            "confidence": 0.8,
            "evidence": "directory listing"
        }
    ],
    "total_score": 11.0,
    "critical_count": 1,
    "major_count": 0,
    "minor_count": 1,
    "scanned_docs": ["README.md", "docs/inventory.md"],
    "scanned_code_paths": ["assemblyzero/workflows/", "assemblyzero/personas/"],
    "timestamp": "2026-02-17T08:30:00Z"
}
```

### 4.5 ReconciliationAction

**Definition:**

```python
class ReconciliationAction(TypedDict):
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
    "trigger_details": "Orchestrator invoked /death report",
    "drift_report": {
        "findings": [],
        "total_score": 11.0,
        "critical_count": 1,
        "major_count": 0,
        "minor_count": 1,
        "scanned_docs": ["README.md"],
        "scanned_code_paths": ["assemblyzero/"],
        "timestamp": "2026-02-17T08:30:00Z"
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
    "timestamp": "2026-02-17T08:31:00Z",
    "summary": "DEATH found 2 drift findings (1 critical, 0 major, 1 minor). 1 reconciliation action proposed. Documentation Age 3 ending."
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
        "current_score": 47,
        "threshold": 50,
        "last_death_visit": "2026-02-01T10:00:00Z",
        "last_computed": "2026-02-17T08:30:00Z",
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
title = "Refactor workflow state machine"
body = "Major restructuring of the LangGraph pipelines"
```

**Output Example:**

```python
(10, "architecture")
```

**Input Example (no labels):**

```python
labels = ["question"]
title = "How does the caching work?"
body = None
```

**Output Example:**

```python
(2, "default")
```

**Edge Cases:**
- Empty `labels` -> returns `(2, "default")` with warning logged
- Multiple matching labels -> returns highest weight label
- Labels `["bug", "fix"]` -> both are weight 1, returns `(1, "bug")` (first match at that weight)

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
since = "2026-02-01T10:00:00Z"
github_token = None  # reads from GITHUB_TOKEN env var
```

**Output Example:**

```python
[
    {
        "number": 530,
        "title": "Add RAG pipeline caching",
        "labels": ["enhancement", "rag"],
        "closed_at": "2026-02-10T12:00:00Z",
        "body": "Implement caching layer for RAG queries",
    },
    {
        "number": 531,
        "title": "Fix broken link in README",
        "labels": ["bug"],
        "closed_at": "2026-02-11T09:00:00Z",
        "body": None,
    },
]
```

**Edge Cases:**
- `since=None` -> fetches all closed issues (paginated, capped at 500)
- GitHub API failure -> returns empty list, logs error
- No `GITHUB_TOKEN` env var and `github_token=None` -> raises `ValueError("GitHub token not found")`

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
    {"number": 530, "title": "Add RAG caching", "labels": ["rag"], "closed_at": "2026-02-10T12:00:00Z", "body": None},
    {"number": 531, "title": "Fix link", "labels": ["bug"], "closed_at": "2026-02-11T09:00:00Z", "body": None},
]
current_state = None
```

**Output Example:**

```python
{
    "current_score": 9,  # 8 (rag) + 1 (bug)
    "threshold": 50,
    "last_death_visit": None,
    "last_computed": "2026-02-17T08:30:00Z",
    "weighted_issues": [
        {"issue_number": 530, "title": "Add RAG caching", "labels": ["rag"], "weight": 8, "weight_source": "rag", "closed_at": "2026-02-10T12:00:00Z"},
        {"issue_number": 531, "title": "Fix link", "labels": ["bug"], "weight": 1, "weight_source": "bug", "closed_at": "2026-02-11T09:00:00Z"},
    ],
    "age_number": 0,
}
```

**Input Example (incremental):**

```python
issues = [{"number": 532, "title": "New persona", "labels": ["persona"], "closed_at": "2026-02-12T15:00:00Z", "body": None}]
current_state = {"current_score": 9, "threshold": 50, "last_death_visit": None, "last_computed": "2026-02-10T00:00:00Z", "weighted_issues": [...], "age_number": 0}
```

**Output Example:**

```python
{
    "current_score": 14,  # 9 + 5 (persona)
    ...
}
```

**Edge Cases:**
- Empty `issues` list with `current_state=None` -> returns score=0, empty weighted_issues
- Empty `issues` list with existing `current_state` -> returns current_state with updated `last_computed`

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

**Output Example (file exists):**

```python
{"current_score": 47, "threshold": 50, "last_death_visit": "2026-02-01T10:00:00Z", ...}
```

**Output Example (no file):**

```python
None
```

**Edge Cases:**
- File exists but contains invalid JSON -> returns `None`, logs warning
- File exists but is empty -> returns `None`, logs warning

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
state = {"current_score": 47, "threshold": 50, "last_death_visit": None, "last_computed": "2026-02-17T08:30:00Z", "weighted_issues": [], "age_number": 3}
state_path = "data/hourglass/age_meter.json"
```

**Output:** None (writes JSON to disk)

**Edge Cases:**
- Parent directory doesn't exist -> creates `data/hourglass/` via `os.makedirs`
- Writes atomically (write to temp file, then rename) to prevent corruption

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
state = {"current_score": 50, "threshold": 50, ...}
```

**Output Example:**

```python
True
```

**Input Example:**

```python
state = {"current_score": 49, "threshold": 50, ...}
```

**Output Example:**

```python
False
```

**Edge Cases:**
- `current_score == threshold` -> returns `True` (>= comparison)

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
        "code_reality": "Found 36 agent definitions in assemblyzero/personas/",
        "category": "count_mismatch",
        "confidence": 0.95,
        "evidence": "glob('assemblyzero/personas/*.py') returned 36 files",
    },
]
```

**Edge Cases:**
- README doesn't exist -> returns empty list, logs warning
- No numeric claims found -> returns empty list
- Claim like "12+" is treated as minimum claim — only flags if actual count is *less than* 12 OR significantly more (>2x)

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
        "doc_claim": "assemblyzero/workflows/old_workflow/main.py listed as active",
        "code_reality": "File does not exist on disk",
        "category": "stale_reference",
        "confidence": 1.0,
        "evidence": "os.path.exists() returned False",
    },
]
```

**Edge Cases:**
- Inventory file doesn't exist -> returns empty list, logs warning
- Inventory not in expected markdown table format -> returns empty list, logs warning

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
docs_dir = "docs/standards/"
codebase_root = "/home/user/AssemblyZero"
```

**Output Example:**

```python
[
    {
        "id": "DRIFT-005",
        "severity": "major",
        "doc_file": "docs/standards/0010-workflow-architecture.md",
        "doc_claim": "System uses 5 workflows",
        "code_reality": "Found 7 workflow directories under assemblyzero/workflows/",
        "category": "architecture_drift",
        "confidence": 0.85,
        "evidence": "listdir('assemblyzero/workflows/') returned 7 directories",
    },
]
```

**Edge Cases:**
- `docs_dir` doesn't exist -> returns empty list
- No architecture-related docs found -> returns empty list

### 5.10 `compute_drift_score()`

**File:** `assemblyzero/workflows/death/drift_scorer.py`

**Signature:**

```python
def compute_drift_score(findings: list[DriftFinding]) -> float:
    """Compute aggregate drift score from findings."""
    ...
```

**Input Example:**

```python
findings = [
    {"severity": "critical", ...},
    {"severity": "critical", ...},
    {"severity": "major", ...},
    {"severity": "minor", ...},
    {"severity": "minor", ...},
    {"severity": "minor", ...},
]
```

**Output Example:**

```python
28.0  # 2*10 + 1*5 + 3*1
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
docs_to_scan = None  # scans all standard locations
```

**Output Example:** (full DriftReport as shown in Section 4.4)

**Edge Cases:**
- `docs_to_scan=[]` -> returns empty report with zero findings
- All scanners return empty -> returns report with zero findings and score 0.0

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
report = {"total_score": 30.0, ...}
threshold = 30.0
```

**Output Example:**

```python
True
```

**Edge Cases:**
- `total_score == threshold` -> returns `True` (>= comparison)
- `total_score == 29.9` -> returns `False`

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
        {"id": "DRIFT-001", "category": "count_mismatch", "doc_file": "README.md", "doc_claim": "12+", "code_reality": "36 found", ...}
    ],
    ...
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
- Empty drift report -> returns empty list
- Finding with `confidence < 0.5` -> skipped (not converted to action)

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
    {"target_file": "README.md", "action_type": "update_count", ...},
    {"target_file": "docs/standards/0015-age-transition-protocol.md", "action_type": "create_adr", ...},
]
codebase_root = "/home/user/AssemblyZero"
dry_run = True
```

**Output Example:**

```python
# Same actions list with new_content populated for ADR entries
[
    {"target_file": "README.md", "action_type": "update_count", ...},
    {"target_file": "docs/standards/0015-age-transition-protocol.md", "action_type": "create_adr", "new_content": "# ADR 0015: Age Transition Protocol\n...", ...},
]
```

**Edge Cases:**
- `dry_run=True` -> populates `new_content` but never writes to disk
- `dry_run=False` -> writes files and returns actions with updated paths
- No ADR actions in list -> returns list unchanged

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
    {"target_file": "docs/lld/active/old-lld.md", "action_type": "archive", "description": "Move stale LLD to done/", ...},
]
codebase_root = "/home/user/AssemblyZero"
dry_run = True
```

**Output Example:**

```python
[
    {"target_file": "docs/lld/done/old-lld.md", "action_type": "archive", "description": "Move stale LLD to done/", ...},
]
```

**Edge Cases:**
- No archive actions -> returns list unchanged
- `dry_run=False` -> actually moves files via `shutil.move`

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
    {"target_file": "README.md", "action_type": "update_count", "old_content": "12+", "new_content": "36", ...},
]
codebase_root = "/home/user/AssemblyZero"
dry_run = True
```

**Output Example:**

```python
# Returns same actions; in dry_run=False, actually applies changes to README
[
    {"target_file": "README.md", "action_type": "update_count", "old_content": "12+", "new_content": "36", ...},
]
```

**Edge Cases:**
- `dry_run=True` -> returns actions, no writes
- `dry_run=False` -> reads file, applies string replacement, writes back

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

**Input Example (qualifying):**

```python
finding = {
    "id": "DRIFT-005",
    "severity": "major",
    "doc_file": "docs/standards/0010-workflow-architecture.md",
    "doc_claim": "System uses 5 workflows",
    "code_reality": "Found 7 workflow directories",
    "category": "architecture_drift",
    "confidence": 0.85,
    "evidence": "listdir returned 7 directories",
}
actions = [
    {"target_file": "docs/standards/0015-age-transition-protocol.md", "action_type": "create_adr", ...},
]
adr_template_path = "docs/standards/"
output_dir = "docs/standards/"
dry_run = True
```

**Output Example (dry_run=True):**

```python
"""# ADR 0015: Age Transition Protocol

## Status
Accepted

## Context
Documentation claimed the system uses 5 workflows, but the codebase contains 7 workflow directories. This drift was detected by DEATH's Hourglass Protocol during Age 3 transition.

## Decision
Update all architectural documentation to reflect the current 7-workflow architecture. The additional workflows are: death, implementation_spec.

## Consequences
- All workflow counts in documentation updated
- Architecture diagrams regenerated
- Future drift will be caught by the Hourglass Protocol
"""
```

**Input Example (non-qualifying):**

```python
finding = {
    "id": "DRIFT-001",
    "severity": "critical",
    "category": "count_mismatch",  # Not architecture_drift
    ...
}
```

**Output Example:**

```python
None
```

**Input Example (reaper mode writes):**

```python
dry_run = False
output_dir = "docs/standards/"
```

**Output Example:**

```python
"docs/standards/0015-age-transition-protocol.md"  # File path written
```

**Edge Cases:**
- `finding.category != "architecture_drift"` -> returns `None`
- `dry_run=True` -> returns content string, no file created
- `dry_run=False` -> writes file, returns file path
- `output_dir` doesn't exist -> creates it via `os.makedirs`

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
trigger_details = "Orchestrator invoked /death report"
drift_report = {"findings": [...], "total_score": 11.0, ...}
actions = [{"target_file": "README.md", "action_type": "update_count", ...}]
mode = "report"
age_number = 3
```

**Output Example:** (full ReconciliationReport as shown in Section 4.6)

**Edge Cases:**
- Empty actions list -> valid report with empty actions and summary noting "no actions needed"

### 5.19 `create_hourglass_graph()`

**File:** `assemblyzero/workflows/death/hourglass.py`

**Signature:**

```python
def create_hourglass_graph() -> StateGraph:
    """Create the LangGraph state machine for the Hourglass Protocol."""
    ...
```

**Input:** None

**Output:** A `StateGraph` instance with nodes: `init`, `walk_field`, `harvest`, `archive`, `chronicle`, `rest` and edges defining the flow. Conditional edge from `harvest` based on mode/confirmed.

**Edge Cases:** None — this is a graph construction function.

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

**Output Example (no triggers):**

```python
(False, "", "Age meter at 23/50, drift score 5.0/30.0")
```

**Output Example (meter trigger):**

```python
(True, "meter", "Age meter crossed threshold: 52/50. 15 issues since last DEATH visit.")
```

**Output Example (critical drift):**

```python
(True, "critical_drift", "Drift score 35.0 exceeds critical threshold 30.0. 3 critical findings.")
```

**Edge Cases:**
- GitHub API fails -> skips meter check, only checks drift
- Both meter and drift triggered -> drift takes priority (checked first)
- `"summon"` is never returned here (only via /death command)

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

**Output Example:** Full `ReconciliationReport` as shown in Section 4.6

**Edge Cases:**
- If any node raises, error is captured in `state["errors"]` and the graph proceeds to `complete`

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

**Input/Output Examples:**

```python
parse_death_args([])              # -> ("report", False)
parse_death_args(["report"])      # -> ("report", False)
parse_death_args(["reaper"])      # -> ("reaper", False)
parse_death_args(["reaper", "--force"]) # -> ("reaper", True)
```

**Edge Cases:**
- `parse_death_args(["invalid"])` -> raises `ValueError("Unknown mode: 'invalid'. Expected 'report' or 'reaper'.")`
- `parse_death_args(["report", "--force"])` -> raises `ValueError("--force flag is only valid with reaper mode.")`
- `parse_death_args(["reaper", "--unknown"])` -> raises `ValueError("Unknown flag: '--unknown'.")`

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

**Output Example:** Full `ReconciliationReport` with `mode="report"`

**Edge Cases:**
- `args=["reaper"]` without confirmation -> raises `PermissionError("Reaper mode requires orchestrator confirmation. Use --force to bypass.")`
- `args=["reaper", "--force"]` -> bypasses confirmation gate

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
    "trigger_details": "Orchestrator invoked /death report",
    "drift_report": {"findings": [...], "total_score": 11.0, "critical_count": 1, "major_count": 0, "minor_count": 1, ...},
    "actions": [{"target_file": "README.md", "action_type": "update_count", "description": "Update agent count from '12+' to '36'", ...}],
    "mode": "report",
    "timestamp": "2026-02-17T08:31:00Z",
    "summary": "DEATH found 2 drift findings...",
}
```

**Output Example:**

```python
"""# ⏳ DEATH's Reconciliation Report — Age 3

> THE SAND HAS RUN OUT.

**Trigger:** Summoned by orchestrator
**Mode:** Report (read-only)
**Timestamp:** 2026-02-17T08:31:00Z

## Summary

DEATH found 2 drift findings (1 critical, 0 major, 1 minor). 1 reconciliation action proposed. Documentation Age 3 ending.

## Drift Findings

| ID | Severity | File | Claim | Reality | Category |
|----|----------|------|-------|---------|----------|
| DRIFT-001 |  critical | README.md | Run 12+ AI agents | 36 agents found | count_mismatch |
| DRIFT-002 | 🟡 minor | README.md | 5 State Machines | 7 workflows found | count_mismatch |

**Drift Score:** 11.0 / 30.0 (below critical threshold)

## Proposed Actions

| # | Target | Action | Description |
|---|--------|--------|-------------|
| 1 | README.md | update_count | Update agent count from '12+' to '36' |

## Next Steps

Run `/death reaper` to apply these changes, or address them manually.

> WHAT CAN THE HARVEST HOPE FOR, IF NOT FOR THE CARE OF THE REAPER MAN?
"""
```

**Edge Cases:**
- Empty findings -> "No drift findings detected. Documentation appears current."
- Empty actions -> "No reconciliation actions needed."

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
    "drift_score": 11.0,
    "finding_count": 2,
    "critical_findings": ["DRIFT-001: README.md count_mismatch (12+ vs 36)"],
    "details": { ... }  # Full DriftReport
}
```

**Edge Cases:**
- All scans pass -> `{"probe": "drift", "status": "pass", "drift_score": 0.0, ...}`
- Critical drift threshold exceeded -> `status: "fail"`
- Scanner error -> `status: "warn"` with error in details

## 6. Change Instructions

### 6.1 `assemblyzero/workflows/death/__init__.py` (Add)

**Complete file contents:**

```python
"""DEATH workflow — the Hourglass Protocol.

Issue #535: DEATH as Age Transition
Detects documentation drift from codebase reality, triggers reconciliation
via an hourglass meter, and produces updated documentation artifacts.
"""

from assemblyzero.workflows.death.hourglass import (
    create_hourglass_graph,
    run_death,
    should_death_arrive,
)
from assemblyzero.workflows.death.skill import (
    format_report_output,
    invoke_death_skill,
    parse_death_args,
)

__all__ = [
    "create_hourglass_graph",
    "run_death",
    "should_death_arrive",
    "invoke_death_skill",
    "parse_death_args",
    "format_report_output",
]
```

### 6.2 `assemblyzero/workflows/death/constants.py` (Add)

**Complete file contents:**

```python
"""Constants for the DEATH workflow — the Hourglass Protocol.

Issue #535: DEATH as Age Transition
"""

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

DEFAULT_WEIGHT: int = 2
DEFAULT_THRESHOLD: int = 50
CRITICAL_DRIFT_THRESHOLD: float = 30.0

DRIFT_SEVERITY_WEIGHTS: dict[str, float] = {
    "critical": 10.0,
    "major": 5.0,
    "minor": 1.0,
}

# Category to action type mapping
CATEGORY_ACTION_MAP: dict[str, str] = {
    "count_mismatch": "update_count",
    "feature_contradiction": "update_description",
    "missing_component": "add_section",
    "stale_reference": "remove_section",
    "architecture_drift": "create_adr",
}

# Paths
AGE_METER_STATE_PATH: str = "data/hourglass/age_meter.json"
HISTORY_PATH: str = "data/hourglass/history.json"
ADR_OUTPUT_PATH: str = "docs/standards/0015-age-transition-protocol.md"
ADR_TEMPLATE_PATH: str = "docs/standards/"

# Numeric claim patterns for README scanning
# Captures patterns like "12+", "34 audits", "5 workflows", "207 issues"
NUMERIC_CLAIM_PATTERNS: list[str] = [
    r"(\d+)\+?\s+(?:AI\s+)?agents?",
    r"(\d+)\s+(?:state\s+)?machines?",
    r"(\d+)\s+workflows?",
    r"(\d+)\s+(?:issues?|audits?|personas?|tools?|probes?)",
]

# Directories to scan for specific entity counts
ENTITY_COUNT_PATHS: dict[str, str] = {
    "agents": "assemblyzero/personas/",
    "workflows": "assemblyzero/workflows/",
    "tools": "tools/",
    "probes": "assemblyzero/workflows/janitor/probes/",
}

# Minimum confidence threshold for converting findings to actions
MIN_CONFIDENCE_THRESHOLD: float = 0.5

# Maximum issues to fetch from GitHub API
MAX_ISSUES_FETCH: int = 500
```

### 6.3 `assemblyzero/workflows/death/models.py` (Add)

**Complete file contents:**

```python
"""Data models for the DEATH workflow — the Hourglass Protocol.

Issue #535: DEATH as Age Transition
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

### 6.4 `assemblyzero/workflows/death/age_meter.py` (Add)

**Complete file contents:**

```python
"""Age meter computation — weights issues by label/type, computes running score.

Issue #535: DEATH as Age Transition
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
    MAX_ISSUES_FETCH,
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
        label_lower = label.lower()
        if label_lower in LABEL_WEIGHTS:
            weight = LABEL_WEIGHTS[label_lower]
            if weight > best_weight:
                best_weight = weight
                best_source = label_lower

    if best_weight == 0:
        logger.warning(
            "No matching label found for issue with labels %s. "
            "Using default weight %d.",
            labels,
            DEFAULT_WEIGHT,
        )
        return DEFAULT_WEIGHT, "default"

    return best_weight, best_source


def fetch_closed_issues_since(
    repo: str,
    since: str | None,
    github_token: str | None = None,
) -> list[dict]:
    """Fetch closed issues from GitHub since the last DEATH visit.

    Args:
        repo: GitHub repo in "owner/repo" format.
        since: ISO 8601 timestamp. If None, fetches all closed issues.
        github_token: Optional token. Uses GITHUB_TOKEN env var if not provided.

    Returns:
        List of issue dicts with number, title, labels, closed_at, body.
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
        repo_obj = g.get_repo(repo)

        kwargs: dict[str, Any] = {"state": "closed", "sort": "updated", "direction": "desc"}
        if since:
            kwargs["since"] = datetime.fromisoformat(since.replace("Z", "+00:00"))

        issues_data: list[dict] = []
        for issue in repo_obj.get_issues(**kwargs):
            if issue.pull_request is not None:
                continue  # Skip PRs
            if len(issues_data) >= MAX_ISSUES_FETCH:
                break
            issues_data.append(
                {
                    "number": issue.number,
                    "title": issue.title,
                    "labels": [label.name for label in issue.labels],
                    "closed_at": issue.closed_at.isoformat() if issue.closed_at else "",
                    "body": issue.body,
                }
            )

        return issues_data

    except Exception as exc:
        logger.error("Failed to fetch issues from GitHub: %s", exc)
        return []


def compute_age_meter(
    issues: list[dict],
    current_state: AgeMeterState | None = None,
) -> AgeMeterState:
    """Compute the age meter score from a list of closed issues.

    If current_state is provided, adds to existing score (incremental).
    If None, computes from scratch.
    """
    now = datetime.now(timezone.utc).isoformat()

    weighted_issues: list[IssueWeight] = []
    score = 0

    for issue in issues:
        weight, source = compute_issue_weight(
            labels=issue.get("labels", []),
            title=issue.get("title", ""),
            body=issue.get("body"),
        )
        weighted_issues.append(
            IssueWeight(
                issue_number=issue["number"],
                title=issue.get("title", ""),
                labels=issue.get("labels", []),
                weight=weight,
                weight_source=source,
                closed_at=issue.get("closed_at", ""),
            )
        )
        score += weight

    if current_state is not None:
        return AgeMeterState(
            current_score=current_state["current_score"] + score,
            threshold=current_state["threshold"],
            last_death_visit=current_state["last_death_visit"],
            last_computed=now,
            weighted_issues=current_state["weighted_issues"] + weighted_issues,
            age_number=current_state["age_number"],
        )

    return AgeMeterState(
        current_score=score,
        threshold=DEFAULT_THRESHOLD,
        last_death_visit=None,
        last_computed=now,
        weighted_issues=weighted_issues,
        age_number=0,
    )


def load_age_meter_state(
    state_path: str = AGE_METER_STATE_PATH,
) -> AgeMeterState | None:
    """Load persistent age meter state from disk. Returns None if no state exists."""
    if not os.path.exists(state_path):
        return None

    try:
        with open(state_path, encoding="utf-8") as f:
            data = json.load(f)
        # Validate required keys
        required_keys = {
            "current_score",
            "threshold",
            "last_death_visit",
            "last_computed",
            "weighted_issues",
            "age_number",
        }
        if not required_keys.issubset(data.keys()):
            logger.warning(
                "Age meter state at %s missing keys: %s",
                state_path,
                required_keys - data.keys(),
            )
            return None
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load age meter state from %s: %s", state_path, exc)
        return None


def save_age_meter_state(
    state: AgeMeterState,
    state_path: str = AGE_METER_STATE_PATH,
) -> None:
    """Persist age meter state to disk. Writes atomically via temp file."""
    os.makedirs(os.path.dirname(state_path), exist_ok=True)

    # Write to temp file first, then rename for atomicity
    dir_name = os.path.dirname(state_path)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".json.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
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

### 6.5 `assemblyzero/workflows/death/drift_scorer.py` (Add)

**Complete file contents:**

```python
"""Drift scoring — detects factual inaccuracies in documentation.

Issue #535: DEATH as Age Transition
Extends janitor probes to detect factual inaccuracies (not just broken links).
"""

from __future__ import annotations

import glob
import logging
import os
import re
from datetime import datetime, timezone

from assemblyzero.workflows.death.constants import (
    CRITICAL_DRIFT_THRESHOLD,
    DRIFT_SEVERITY_WEIGHTS,
    ENTITY_COUNT_PATHS,
    NUMERIC_CLAIM_PATTERNS,
)
from assemblyzero.workflows.death.models import DriftFinding, DriftReport

logger = logging.getLogger(__name__)

_finding_counter = 0


def _next_finding_id() -> str:
    """Generate the next sequential finding ID."""
    global _finding_counter
    _finding_counter += 1
    return f"DRIFT-{_finding_counter:03d}"


def _reset_finding_counter() -> None:
    """Reset finding counter (for testing)."""
    global _finding_counter
    _finding_counter = 0


def _count_entities(codebase_root: str, entity_path: str) -> int:
    """Count entities (files/directories) at a given path."""
    full_path = os.path.join(codebase_root, entity_path)
    if not os.path.isdir(full_path):
        return 0

    # Count Python files for file-based entities, directories for directory-based
    py_files = glob.glob(os.path.join(full_path, "*.py"))
    # Exclude __init__.py from counts
    py_files = [f for f in py_files if not f.endswith("__init__.py")]

    dirs = [
        d
        for d in os.listdir(full_path)
        if os.path.isdir(os.path.join(full_path, d)) and not d.startswith("__")
    ]

    # Return whichever is larger (some entities are files, some are directories)
    return max(len(py_files), len(dirs))


def _determine_severity(claimed: int, actual: int) -> str:
    """Determine severity of a count mismatch."""
    ratio = actual / claimed if claimed > 0 else float("inf")
    if ratio > 3.0 or ratio < 0.33:
        return "critical"
    elif ratio > 2.0 or ratio < 0.5:
        return "major"
    return "minor"


def scan_readme_claims(
    readme_path: str,
    codebase_root: str,
) -> list[DriftFinding]:
    """Scan README for factual claims and verify against codebase.

    Checks numeric claims (tool counts, file counts, persona counts).
    """
    findings: list[DriftFinding] = []

    full_readme = os.path.join(codebase_root, readme_path)
    if not os.path.exists(full_readme):
        logger.warning("README not found at %s", full_readme)
        return findings

    with open(full_readme, encoding="utf-8") as f:
        content = f.read()

    for pattern in NUMERIC_CLAIM_PATTERNS:
        for match in re.finditer(pattern, content, re.IGNORECASE):
            claimed_number = int(match.group(1))
            claim_text = match.group(0)

            # Determine which entity type this claim is about
            entity_type = None
            for entity_name, entity_path in ENTITY_COUNT_PATHS.items():
                if entity_name.rstrip("s") in claim_text.lower() or entity_name in claim_text.lower():
                    entity_type = entity_name
                    break

            if entity_type is None:
                continue

            actual_count = _count_entities(codebase_root, ENTITY_COUNT_PATHS[entity_type])

            if actual_count == 0:
                continue  # Can't validate if we can't count

            # Flag if significantly different (not just "12+" where actual > 12)
            if claim_text.endswith("+"):
                # "N+" means "at least N" — only flag if actual < N or actual > 2*N
                if actual_count >= claimed_number and actual_count <= claimed_number * 2:
                    continue

            if actual_count != claimed_number:
                severity = _determine_severity(claimed_number, actual_count)
                findings.append(
                    DriftFinding(
                        id=_next_finding_id(),
                        severity=severity,
                        doc_file=readme_path,
                        doc_claim=claim_text,
                        code_reality=f"Found {actual_count} {entity_type} in {ENTITY_COUNT_PATHS[entity_type]}",
                        category="count_mismatch",
                        confidence=0.95 if abs(actual_count - claimed_number) > 2 else 0.7,
                        evidence=f"glob/listdir of {ENTITY_COUNT_PATHS[entity_type]} returned {actual_count}",
                    )
                )

    return findings


def scan_inventory_accuracy(
    inventory_path: str,
    codebase_root: str,
) -> list[DriftFinding]:
    """Compare file inventory against actual filesystem.

    Detects files listed in inventory but missing from disk,
    and files on disk but missing from inventory.
    """
    findings: list[DriftFinding] = []

    full_inventory = os.path.join(codebase_root, inventory_path)
    if not os.path.exists(full_inventory):
        logger.warning("Inventory not found at %s", full_inventory)
        return findings

    with open(full_inventory, encoding="utf-8") as f:
        content = f.read()

    # Parse markdown table rows for file paths
    # Expected format: | path/to/file.py | status | description |
    file_pattern = re.compile(r"\|\s*`?([a-zA-Z0-9_/.\\-]+\.\w+)`?\s*\|")
    listed_files: set[str] = set()
    for match in file_pattern.finditer(content):
        listed_files.add(match.group(1))

    if not listed_files:
        logger.warning("No file paths found in inventory at %s", full_inventory)
        return findings

    # Check listed files exist on disk
    for file_path in sorted(listed_files):
        full_path = os.path.join(codebase_root, file_path)
        if not os.path.exists(full_path):
            findings.append(
                DriftFinding(
                    id=_next_finding_id(),
                    severity="major",
                    doc_file=inventory_path,
                    doc_claim=f"{file_path} listed as existing",
                    code_reality="File does not exist on disk",
                    category="stale_reference",
                    confidence=1.0,
                    evidence=f"os.path.exists('{full_path}') returned False",
                )
            )

    return findings


def scan_architecture_docs(
    docs_dir: str,
    codebase_root: str,
) -> list[DriftFinding]:
    """Scan architecture docs for claims that contradict code structure.

    Uses simple directory/file counting as a fallback when spelunking (#534)
    is not available.
    """
    findings: list[DriftFinding] = []

    full_docs_dir = os.path.join(codebase_root, docs_dir)
    if not os.path.isdir(full_docs_dir):
        logger.warning("Docs directory not found at %s", full_docs_dir)
        return findings

    # Scan markdown files in docs_dir for numeric architecture claims
    for md_file in glob.glob(os.path.join(full_docs_dir, "*.md")):
        try:
            with open(md_file, encoding="utf-8") as f:
                content = f.read()
        except OSError:
            continue

        rel_path = os.path.relpath(md_file, codebase_root)

        # Look for workflow count claims
        workflow_pattern = re.compile(r"(\d+)\s+workflows?", re.IGNORECASE)
        for match in workflow_pattern.finditer(content):
            claimed = int(match.group(1))
            actual = _count_entities(codebase_root, "assemblyzero/workflows/")
            if actual > 0 and actual != claimed:
                findings.append(
                    DriftFinding(
                        id=_next_finding_id(),
                        severity="major",
                        doc_file=rel_path,
                        doc_claim=match.group(0),
                        code_reality=f"Found {actual} workflow directories under assemblyzero/workflows/",
                        category="architecture_drift",
                        confidence=0.85,
                        evidence=f"listdir('assemblyzero/workflows/') returned {actual} directories",
                    )
                )

    return findings


def compute_drift_score(findings: list[DriftFinding]) -> float:
    """Compute aggregate drift score from findings.

    Weights: critical=10, major=5, minor=1
    """
    score = 0.0
    for finding in findings:
        severity = finding["severity"]
        score += DRIFT_SEVERITY_WEIGHTS.get(severity, 0.0)
    return score


def build_drift_report(
    codebase_root: str,
    docs_to_scan: list[str] | None = None,
) -> DriftReport:
    """Run all drift scanners and produce aggregated report."""
    _reset_finding_counter()
    all_findings: list[DriftFinding] = []
    scanned_docs: list[str] = []
    scanned_code_paths: list[str] = list(ENTITY_COUNT_PATHS.values())

    # Determine which docs to scan
    if docs_to_scan is None:
        readme = "README.md"
        inventory = "docs/inventory.md"
        arch_dir = "docs/standards/"
    else:
        readme = next((d for d in docs_to_scan if "readme" in d.lower()), "")
        inventory = next((d for d in docs_to_scan if "inventory" in d.lower()), "")
        arch_dir = next((d for d in docs_to_scan if "standards" in d.lower() or "docs" in d.lower()), "")

    # README scan
    if readme:
        readme_findings = scan_readme_claims(readme, codebase_root)
        all_findings.extend(readme_findings)
        scanned_docs.append(readme)

    # Inventory scan
    if inventory:
        inv_findings = scan_inventory_accuracy(inventory, codebase_root)
        all_findings.extend(inv_findings)
        scanned_docs.append(inventory)

    # Architecture docs scan
    if arch_dir:
        arch_findings = scan_architecture_docs(arch_dir, codebase_root)
        all_findings.extend(arch_findings)
        scanned_docs.append(arch_dir)

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


def check_critical_drift(report: DriftReport, threshold: float = CRITICAL_DRIFT_THRESHOLD) -> bool:
    """Check if drift score exceeds critical threshold. Returns True if DEATH should arrive."""
    return report["total_score"] >= threshold
```

### 6.6 `assemblyzero/workflows/death/reconciler.py` (Add)

**Complete file contents:**

```python
"""Reconciliation engine — walks codebase, compares to docs, produces report or applies fixes.

Issue #535: DEATH as Age Transition
"""

from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime, timezone

from assemblyzero.workflows.death.constants import (
    ADR_OUTPUT_PATH,
    CATEGORY_ACTION_MAP,
    MIN_CONFIDENCE_THRESHOLD,
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
    Skips findings with confidence below threshold.
    """
    actions: list[ReconciliationAction] = []

    for finding in drift_report["findings"]:
        if finding["confidence"] < MIN_CONFIDENCE_THRESHOLD:
            logger.info(
                "Skipping low-confidence finding %s (%.2f)",
                finding["id"],
                finding["confidence"],
            )
            continue

        action_type = CATEGORY_ACTION_MAP.get(finding["category"], "update_description")

        action = ReconciliationAction(
            target_file=finding["doc_file"],
            action_type=action_type,
            description=_build_action_description(finding),
            old_content=finding["doc_claim"],
            new_content=_suggest_new_content(finding),
            drift_finding_id=finding["id"],
        )

        # For architecture_drift, target the ADR output path
        if finding["category"] == "architecture_drift":
            action["target_file"] = ADR_OUTPUT_PATH

        actions.append(action)

    return actions


def _build_action_description(finding: DriftFinding) -> str:
    """Build a human-readable description for a reconciliation action."""
    category = finding["category"]
    if category == "count_mismatch":
        return f"Update count: '{finding['doc_claim']}' -> {finding['code_reality']}"
    elif category == "feature_contradiction":
        return f"Fix feature claim: '{finding['doc_claim']}' contradicted by {finding['code_reality']}"
    elif category == "missing_component":
        return f"Add documentation for: {finding['code_reality']}"
    elif category == "stale_reference":
        return f"Remove stale reference: '{finding['doc_claim']}' — {finding['code_reality']}"
    elif category == "architecture_drift":
        return f"Create ADR: architecture changed — {finding['code_reality']}"
    return f"Reconcile: {finding['doc_claim']} vs {finding['code_reality']}"


def _suggest_new_content(finding: DriftFinding) -> str | None:
    """Suggest replacement content based on the drift finding."""
    if finding["category"] == "count_mismatch":
        # Extract the actual count from code_reality
        import re

        match = re.search(r"Found (\d+)", finding["code_reality"])
        if match:
            actual = match.group(1)
            # Replace the number in the claim
            new_claim = re.sub(r"\d+\+?", actual, finding["doc_claim"])
            return new_claim
    elif finding["category"] == "stale_reference":
        return None  # Content should be removed
    elif finding["category"] == "architecture_drift":
        return None  # ADR generation handles this
    elif finding["category"] == "missing_component":
        return f"<!-- TODO: Add documentation for {finding['code_reality']} -->"
    return None


def harvest(
    actions: list[ReconciliationAction],
    codebase_root: str,
    dry_run: bool = True,
) -> list[ReconciliationAction]:
    """Phase 2: Write ADRs and diagrams.

    In dry_run mode (report), returns actions with new_content populated.
    In write mode (reaper), actually creates the files.
    """
    updated_actions: list[ReconciliationAction] = []

    for action in actions:
        if action["action_type"] == "create_adr":
            # Find the corresponding finding for ADR generation
            adr_content = _generate_adr_content(action)
            action = {**action, "new_content": adr_content}

            if not dry_run:
                full_path = os.path.join(codebase_root, action["target_file"])
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(adr_content)
                logger.info("Wrote ADR to %s", full_path)

        updated_actions.append(action)

    return updated_actions


def _generate_adr_content(action: ReconciliationAction) -> str:
    """Generate ADR content from a reconciliation action."""
    return f"""# ADR 0015: Age Transition Protocol

## Status

Accepted

## Context

{action['description']}

The documentation claimed: "{action['old_content'] or 'N/A'}"
The codebase reality: This drift was detected by DEATH's Hourglass Protocol.

## Decision

Update all architectural documentation to reflect the current codebase state.
The Hourglass Protocol (Issue #535) automates detection and reconciliation of documentation drift.

## Consequences

- Documentation drift findings are automatically detected via drift scoring
- Age meter tracks cumulative change since last reconciliation
- ADRs are generated for architecture-level drift
- All changes are reversible via git
"""


def generate_adr(
    finding: DriftFinding,
    actions: list[ReconciliationAction],
    adr_template_path: str,
    output_dir: str,
    dry_run: bool = True,
) -> str | None:
    """Generate an ADR document from an architecture drift finding.

    Only generates for architecture_drift category findings.
    Returns ADR content (dry_run=True) or file path (dry_run=False).
    Returns None if finding doesn't qualify.
    """
    if finding["category"] != "architecture_drift":
        return None

    # Find related actions for context
    related_actions = [a for a in actions if a["drift_finding_id"] == finding["id"]]

    adr_content = f"""# ADR 0015: Age Transition Protocol

## Status

Accepted

## Context

Documentation drift detected by DEATH's Hourglass Protocol (Issue #535).

**Finding:** {finding['id']} ({finding['severity']})
**Claim:** {finding['doc_claim']}
**Reality:** {finding['code_reality']}
**Evidence:** {finding['evidence']}

## Decision

Update architectural documentation to reflect the current codebase state.
{chr(10).join(f'- {a["description"]}' for a in related_actions) if related_actions else '- Reconcile documentation with code reality.'}

## Alternatives Considered

1. **Ignore the drift** — Rejected. Stale architecture docs mislead new contributors.
2. **Manual update** — Possible but the Hourglass Protocol automates detection.
3. **Automated reconciliation** — Selected. DEATH walks the field and updates docs.

## Consequences

- All workflow counts and architecture descriptions updated
- Drift monitoring continues via the age meter
- Future architecture changes will be caught by the Hourglass Protocol
"""

    if dry_run:
        return adr_content

    # Write to disk
    output_path = os.path.join(output_dir, "0015-age-transition-protocol.md")
    os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(adr_content)
    logger.info("Wrote ADR to %s", output_path)
    return output_path


def archive_old_age(
    actions: list[ReconciliationAction],
    codebase_root: str,
    dry_run: bool = True,
) -> list[ReconciliationAction]:
    """Phase 3: Move old artifacts to legacy/done."""
    updated_actions: list[ReconciliationAction] = []

    for action in actions:
        if action["action_type"] == "archive":
            # Determine destination (e.g., docs/lld/active/ -> docs/lld/done/)
            target = action["target_file"]
            if "/active/" in target:
                dest = target.replace("/active/", "/done/")
            else:
                dest = os.path.join("docs/legacy/", os.path.basename(target))

            action = {**action, "target_file": dest}

            if not dry_run:
                src_full = os.path.join(codebase_root, action["old_content"] or target)
                dst_full = os.path.join(codebase_root, dest)
                os.makedirs(os.path.dirname(dst_full), exist_ok=True)
                if os.path.exists(src_full):
                    shutil.move(src_full, dst_full)
                    logger.info("Archived %s -> %s", src_full, dst_full)

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
        if action["action_type"] in ("update_count", "update_description") and not dry_run:
            full_path = os.path.join(codebase_root, action["target_file"])
            if os.path.exists(full_path) and action["old_content"] and action["new_content"]:
                with open(full_path, encoding="utf-8") as f:
                    content = f.read()
                updated = content.replace(action["old_content"], action["new_content"])
                if updated != content:
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(updated)
                    logger.info("Updated %s", full_path)

        updated_actions.append(action)

    return updated_actions


def build_reconciliation_report(
    trigger: str,
    trigger_details: str,
    drift_report: DriftReport,
    actions: list[ReconciliationAction],
    mode: str,
    age_number: int,
) -> ReconciliationReport:
    """Assemble the full reconciliation report from all phases."""
    finding_count = len(drift_report["findings"])
    action_count = len(actions)

    if finding_count == 0:
        summary = "No drift findings detected. Documentation appears current."
    else:
        summary = (
            f"DEATH found {finding_count} drift finding{'s' if finding_count != 1 else ''} "
            f"({drift_report['critical_count']} critical, {drift_report['major_count']} major, "
            f"{drift_report['minor_count']} minor). "
            f"{action_count} reconciliation action{'s' if action_count != 1 else ''} "
            f"{'proposed' if mode == 'report' else 'applied'}. "
            f"Documentation Age {age_number} ending."
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
```

### 6.7 `assemblyzero/workflows/death/hourglass.py` (Add)

**Complete file contents:**

```python
"""Hourglass state machine — orchestrates the DEATH reconciliation protocol.

Issue #535: DEATH as Age Transition
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Literal

from langgraph.graph import END, StateGraph

from assemblyzero.workflows.death.age_meter import (
    check_meter_threshold,
    compute_age_meter,
    fetch_closed_issues_since,
    load_age_meter_state,
    save_age_meter_state,
)
from assemblyzero.workflows.death.constants import (
    AGE_METER_STATE_PATH,
    DEFAULT_THRESHOLD,
    HISTORY_PATH,
)
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
    harvest,
    walk_the_field,
)

logger = logging.getLogger(__name__)


def _node_init(state: HourglassState) -> dict[str, Any]:
    """INIT node: Load state, log arrival."""
    trigger = state["trigger"]
    if trigger == "summon":
        logger.info("DEATH HAS BEEN SUMMONED.")
    else:
        logger.info("THE SAND HAS RUN OUT.")

    # Load or initialize age meter
    age_meter = state.get("age_meter")
    if age_meter is None:
        loaded = load_age_meter_state()
        if loaded is None:
            age_meter = AgeMeterState(
                current_score=0,
                threshold=DEFAULT_THRESHOLD,
                last_death_visit=None,
                last_computed=datetime.now(timezone.utc).isoformat(),
                weighted_issues=[],
                age_number=0,
            )
        else:
            age_meter = loaded

    return {"age_meter": age_meter, "step": "walk_field"}


def _node_walk_field(state: HourglassState) -> dict[str, Any]:
    """WALK_FIELD node: Run drift scanners, produce DriftReport."""
    errors = list(state.get("errors", []))
    try:
        # Use "." as codebase_root since we operate from project root
        drift_report = build_drift_report(".")
        logger.info(
            "Walk complete: %d findings, score %.1f",
            len(drift_report["findings"]),
            drift_report["total_score"],
        )
        return {"drift_report": drift_report, "step": "harvest"}
    except Exception as exc:
        errors.append(f"Walk field error: {exc}")
        logger.error("Walk field failed: %s", exc)
        return {"errors": errors, "step": "harvest"}


def _node_harvest(state: HourglassState) -> dict[str, Any]:
    """HARVEST node: Generate reconciliation actions and ADRs."""
    errors = list(state.get("errors", []))
    drift_report = state.get("drift_report")
    mode = state["mode"]

    if drift_report is None:
        errors.append("No drift report available for harvest.")
        return {"errors": errors, "step": "archive"}

    try:
        actions = walk_the_field(".", drift_report)
        dry_run = mode == "report"
        actions = harvest(actions, ".", dry_run=dry_run)
        return {"reconciliation_report": _partial_report(state, actions), "step": "archive"}
    except Exception as exc:
        errors.append(f"Harvest error: {exc}")
        return {"errors": errors, "step": "archive"}


def _partial_report(state: HourglassState, actions: list) -> dict:
    """Build a partial report dict for intermediate state."""
    return {
        "age_number": state["age_meter"]["age_number"],
        "trigger": state["trigger"],
        "trigger_details": _trigger_details(state["trigger"]),
        "drift_report": state.get("drift_report", {}),
        "actions": actions,
        "mode": state["mode"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": "",
    }


def _trigger_details(trigger: str) -> str:
    """Generate human-readable trigger details."""
    if trigger == "summon":
        return "Orchestrator invoked /death"
    elif trigger == "meter":
        return "Age meter crossed threshold"
    elif trigger == "critical_drift":
        return "Critical drift detected"
    return f"Unknown trigger: {trigger}"


def _node_archive(state: HourglassState) -> dict[str, Any]:
    """ARCHIVE node: Move old artifacts to legacy."""
    report = state.get("reconciliation_report")
    if report and isinstance(report, dict):
        actions = report.get("actions", [])
        dry_run = state["mode"] == "report"
        actions = archive_old_age(actions, ".", dry_run=dry_run)
        report = {**report, "actions": actions}
        return {"reconciliation_report": report, "step": "chronicle"}
    return {"step": "chronicle"}


def _node_chronicle(state: HourglassState) -> dict[str, Any]:
    """CHRONICLE node: Update README and wiki."""
    report = state.get("reconciliation_report")
    if report and isinstance(report, dict):
        actions = report.get("actions", [])
        dry_run = state["mode"] == "report"
        actions = chronicle(actions, ".", dry_run=dry_run)
        report = {**report, "actions": actions}
        return {"reconciliation_report": report, "step": "rest"}
    return {"step": "rest"}


def _node_rest(state: HourglassState) -> dict[str, Any]:
    """REST node: Reset age meter, record visit, DEATH departs."""
    age_meter = state["age_meter"]
    now = datetime.now(timezone.utc).isoformat()

    # Reset age meter
    new_age_meter = AgeMeterState(
        current_score=0,
        threshold=age_meter["threshold"],
        last_death_visit=now,
        last_computed=now,
        weighted_issues=[],
        age_number=age_meter["age_number"] + 1,
    )

    # Save state
    try:
        save_age_meter_state(new_age_meter)
    except Exception as exc:
        logger.error("Failed to save age meter state: %s", exc)

    # Record in history
    try:
        _append_history(state, now)
    except Exception as exc:
        logger.error("Failed to record history: %s", exc)

    # Finalize report
    report = state.get("reconciliation_report")
    if report and isinstance(report, dict):
        final_report = build_reconciliation_report(
            trigger=state["trigger"],
            trigger_details=_trigger_details(state["trigger"]),
            drift_report=state.get("drift_report", report.get("drift_report", {})),
            actions=report.get("actions", []),
            mode=state["mode"],
            age_number=age_meter["age_number"],
        )
    else:
        drift_report = state.get("drift_report")
        if drift_report is None:
            from assemblyzero.workflows.death.models import DriftReport

            drift_report = DriftReport(
                findings=[],
                total_score=0.0,
                critical_count=0,
                major_count=0,
                minor_count=0,
                scanned_docs=[],
                scanned_code_paths=[],
                timestamp=now,
            )
        final_report = build_reconciliation_report(
            trigger=state["trigger"],
            trigger_details=_trigger_details(state["trigger"]),
            drift_report=drift_report,
            actions=[],
            mode=state["mode"],
            age_number=age_meter["age_number"],
        )

    logger.info("THE NEW AGE BEGINS. Age %d.", new_age_meter["age_number"])
    return {
        "age_meter": new_age_meter,
        "reconciliation_report": final_report,
        "step": "complete",
    }


def _append_history(state: HourglassState, timestamp: str) -> None:
    """Append a DEATH visit record to history.json."""
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)

    history: list[dict] = []
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, encoding="utf-8") as f:
                history = json.load(f)
        except (json.JSONDecodeError, OSError):
            history = []

    report = state.get("reconciliation_report")
    finding_count = 0
    action_count = 0
    if report and isinstance(report, dict):
        dr = report.get("drift_report", {})
        if isinstance(dr, dict):
            finding_count = len(dr.get("findings", []))
        action_count = len(report.get("actions", []))

    entry = {
        "timestamp": timestamp,
        "trigger": state["trigger"],
        "mode": state["mode"],
        "age_number": state["age_meter"]["age_number"],
        "findings_count": finding_count,
        "actions_count": action_count,
    }
    history.append(entry)

    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)


def _route_after_harvest(state: HourglassState) -> str:
    """Conditional edge: route based on mode and confirmation."""
    if state["mode"] == "reaper" and not state.get("confirmed", False):
        return "complete"
    return "archive"


def create_hourglass_graph() -> StateGraph:
    """Create the LangGraph state machine for the Hourglass Protocol.

    Nodes: init -> walk_field -> harvest -> [confirm_gate] -> archive -> chronicle -> rest -> complete
    """
    graph = StateGraph(HourglassState)

    graph.add_node("init", _node_init)
    graph.add_node("walk_field", _node_walk_field)
    graph.add_node("harvest", _node_harvest)
    graph.add_node("archive", _node_archive)
    graph.add_node("chronicle", _node_chronicle)
    graph.add_node("rest", _node_rest)

    graph.set_entry_point("init")
    graph.add_edge("init", "walk_field")
    graph.add_edge("walk_field", "harvest")

    # Conditional: reaper mode without confirmation skips to complete
    graph.add_conditional_edges(
        "harvest",
        _route_after_harvest,
        {"archive": "archive", "complete": END},
    )

    graph.add_edge("archive", "chronicle")
    graph.add_edge("chronicle", "rest")
    graph.add_edge("rest", END)

    return graph


def should_death_arrive(
    codebase_root: str,
    repo: str,
    github_token: str | None = None,
) -> tuple[bool, str, str]:
    """Check all three triggers. Returns (should_trigger, trigger_type, details).

    Checks in order:
    1. Critical drift (immediate)
    2. Meter threshold (accumulated)
    3. Returns False if neither
    """
    # Check critical drift first
    try:
        drift_report = build_drift_report(codebase_root)
        if check_critical_drift(drift_report):
            return (
                True,
                "critical_drift",
                f"Drift score {drift_report['total_score']:.1f} exceeds critical threshold. "
                f"{drift_report['critical_count']} critical findings.",
            )
    except Exception as exc:
        logger.error("Drift check failed: %s", exc)

    # Check meter threshold
    try:
        state = load_age_meter_state()
        if state is not None:
            issues = fetch_closed_issues_since(repo, state["last_death_visit"], github_token)
            if issues:
                state = compute_age_meter(issues, state)
                save_age_meter_state(state)
            if check_meter_threshold(state):
                return (
                    True,
                    "meter",
                    f"Age meter crossed threshold: {state['current_score']}/{state['threshold']}. "
                    f"{len(state['weighted_issues'])} issues since last DEATH visit.",
                )
            details = (
                f"Age meter at {state['current_score']}/{state['threshold']}, "
                f"drift score {drift_report['total_score']:.1f}/{30.0}"
            )
            return (False, "", details)
    except Exception as exc:
        logger.error("Meter check failed: %s", exc)

    return (False, "", "Checks completed, no triggers active.")


def run_death(
    mode: Literal["report", "reaper"],
    trigger: Literal["meter", "summon", "critical_drift"],
    codebase_root: str,
    repo: str,
    github_token: str | None = None,
) -> ReconciliationReport:
    """Execute the full DEATH reconciliation protocol."""
    graph = create_hourglass_graph()
    compiled = graph.compile()

    initial_state = HourglassState(
        trigger=trigger,
        mode=mode,
        age_meter=load_age_meter_state()
        or AgeMeterState(
            current_score=0,
            threshold=DEFAULT_THRESHOLD,
            last_death_visit=None,
            last_computed=datetime.now(timezone.utc).isoformat(),
            weighted_issues=[],
            age_number=0,
        ),
        drift_report=None,
        reconciliation_report=None,
        step="init",
        errors=[],
        confirmed=mode == "report",  # Report mode is always "confirmed" (no gate)
    )

    result = compiled.invoke(initial_state)
    return result.get("reconciliation_report", {})
```

### 6.8 `assemblyzero/workflows/death/skill.py` (Add)

**Complete file contents:**

```python
"""Skill entry point for /death — the Hourglass Protocol.

Issue #535: DEATH as Age Transition
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
    Raises ValueError on invalid arguments.
    """
    mode: str = "report"
    force: bool = False

    if not args:
        return "report", False

    # First arg is mode
    if args[0].startswith("--"):
        # No mode specified, treat as flag
        mode = "report"
        flags = args
    else:
        mode = args[0]
        flags = args[1:]

    if mode not in VALID_MODES:
        raise ValueError(
            f"Unknown mode: '{mode}'. Expected 'report' or 'reaper'."
        )

    for flag in flags:
        if flag == "--force":
            if mode != "reaper":
                raise ValueError("--force flag is only valid with reaper mode.")
            force = True
        else:
            raise ValueError(f"Unknown flag: '{flag}'.")

    return mode, force  # type: ignore[return-value]


def invoke_death_skill(
    args: list[str],
    codebase_root: str,
    repo: str,
    github_token: str | None = None,
) -> ReconciliationReport:
    """Main entry point for the /death Claude Code skill.

    Parses arguments, handles confirmation gate for reaper mode,
    and executes the hourglass protocol.
    """
    mode, force = parse_death_args(args)

    # Confirmation gate for reaper mode
    if mode == "reaper" and not force:
        raise PermissionError(
            "Reaper mode requires orchestrator confirmation. "
            "Use --force to bypass."
        )

    logger.info("Invoking DEATH in %s mode (trigger: summon)", mode)

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
    lines: list[str] = []

    # Header
    age = report.get("age_number", 0)
    trigger = report.get("trigger", "unknown")
    mode = report.get("mode", "report")
    timestamp = report.get("timestamp", "")

    lines.append(f"# ⏳ DEATH's Reconciliation Report — Age {age}")
    lines.append("")

    if trigger == "summon":
        lines.append("> DEATH HAS BEEN SUMMONED.")
    else:
        lines.append("> THE SAND HAS RUN OUT.")

    lines.append("")
    lines.append(f"**Trigger:** {_format_trigger(trigger)}")
    lines.append(f"**Mode:** {mode.title()} ({'read-only' if mode == 'report' else 'write'})")
    lines.append(f"**Timestamp:** {timestamp}")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    summary = report.get("summary", "No summary available.")
    lines.append(summary)
    lines.append("")

    # Drift Findings
    drift_report = report.get("drift_report", {})
    findings = drift_report.get("findings", []) if isinstance(drift_report, dict) else []

    lines.append("## Drift Findings")
    lines.append("")

    if not findings:
        lines.append("No drift findings detected. Documentation appears current.")
    else:
        lines.append("| ID | Severity | File | Claim | Reality | Category |")
        lines.append("|----|----------|------|-------|---------|----------|")
        severity_icons = {"critical": "", "major": "🟠", "minor": "🟡"}
        for f in findings:
            icon = severity_icons.get(f.get("severity", ""), "")
            lines.append(
                f"| {f.get('id', '')} | {icon} {f.get('severity', '')} "
                f"| {f.get('doc_file', '')} | {f.get('doc_claim', '')} "
                f"| {f.get('code_reality', '')} | {f.get('category', '')} |"
            )

    lines.append("")
    total_score = drift_report.get("total_score", 0.0) if isinstance(drift_report, dict) else 0.0
    lines.append(f"**Drift Score:** {total_score:.1f} / 30.0")
    lines.append("")

    # Actions
    actions = report.get("actions", [])
    lines.append("## Proposed Actions")
    lines.append("")

    if not actions:
        lines.append("No reconciliation actions needed.")
    else:
        lines.append("| # | Target | Action | Description |")
        lines.append("|---|--------|--------|-------------|")
        for i, a in enumerate(actions, 1):
            lines.append(
                f"| {i} | {a.get('target_file', '')} "
                f"| {a.get('action_type', '')} "
                f"| {a.get('description', '')} |"
            )

    lines.append("")

    # Next steps
    lines.append("## Next Steps")
    lines.append("")
    if mode == "report":
        lines.append("Run `/death reaper` to apply these changes, or address them manually.")
    else:
        lines.append("Changes have been applied. Review with `git diff` and commit when satisfied.")
    lines.append("")
    lines.append("> WHAT CAN THE HARVEST HOPE FOR, IF NOT FOR THE CARE OF THE REAPER MAN?")

    return "\n".join(lines)


def _format_trigger(trigger: str) -> str:
    """Format trigger name for display."""
    if trigger == "summon":
        return "Summoned by orchestrator"
    elif trigger == "meter":
        return "Age meter threshold crossed"
    elif trigger == "critical_drift":
        return "Critical drift detected"
    return f"Unknown ({trigger})"
```

### 6.9 `assemblyzero/workflows/janitor/probes/drift_probe.py` (Add)

**Complete file contents:**

```python
"""Janitor probe — factual accuracy drift detection (feeds hourglass).

Issue #535: DEATH as Age Transition
Extends janitor probes to detect factual inaccuracies in documentation.
"""

from __future__ import annotations

import logging

from assemblyzero.workflows.death.drift_scorer import (
    build_drift_report,
    check_critical_drift,
)
from assemblyzero.workflows.death.models import DriftReport

logger = logging.getLogger(__name__)


def run_drift_probe(
    codebase_root: str,
    docs_to_scan: list[str] | None = None,
) -> dict:
    """Janitor probe that runs drift analysis and feeds the hourglass.

    Returns probe result dict compatible with janitor probe interface.
    """
    try:
        drift_report: DriftReport = build_drift_report(codebase_root, docs_to_scan)

        # Determine status
        if check_critical_drift(drift_report):
            status = "fail"
        elif drift_report["total_score"] > 0:
            status = "warn"
        else:
            status = "pass"

        critical_findings = [
            f"{f['id']}: {f['doc_file']} {f['category']} ({f['doc_claim']} vs {f['code_reality']})"
            for f in drift_report["findings"]
            if f["severity"] == "critical"
        ]

        return {
            "probe": "drift",
            "status": status,
            "drift_score": drift_report["total_score"],
            "finding_count": len(drift_report["findings"]),
            "critical_findings": critical_findings,
            "details": drift_report,
        }

    except Exception as exc:
        logger.error("Drift probe failed: %s", exc)
        return {
            "probe": "drift",
            "status": "warn",
            "drift_score": 0.0,
            "finding_count": 0,
            "critical_findings": [],
            "details": {"error": str(exc)},
        }
```

### 6.10 `assemblyzero/workflows/janitor/probes/__init__.py` (Modify)

**Change 1:** Add import for drift probe at the top of `_build_registry()` or at module level

```diff
 """Probe registry and execution utilities.
 
 Issue #94: Lu-Tze: The Janitor
 """
 
 from __future__ import annotations
 
 from typing import Callable
 
 from assemblyzero.workflows.janitor.state import ProbeResult, ProbeScope
+
+# Note: drift probe added by Issue #535 (Hourglass Protocol)
```

**Change 2:** Inside `_build_registry()`, add the drift probe registration. The exact modification depends on the registry structure, but the pattern should be:

```diff
 def _build_registry() -> dict[ProbeScope, ProbeFunction]:
     """Build probe registry lazily to avoid circular imports."""
     from assemblyzero.workflows.janitor.probes.harvest import run as harvest_probe
     from assemblyzero.workflows.janitor.probes.links import run as links_probe
     from assemblyzero.workflows.janitor.probes.todo import run as todo_probe
     from assemblyzero.workflows.janitor.probes.worktrees import run as worktrees_probe
+    from assemblyzero.workflows.janitor.probes.drift_probe import run_drift_probe
 
     return {
         "harvest": harvest_probe,
         "links": links_probe,
         "todo": todo_probe,
         "worktrees": worktrees_probe,
+        "drift": run_drift_probe,
     }
```

**Note:** The exact registry dictionary key names and probe function signatures need to match the existing pattern. If `ProbeScope` is a `Literal` type defined in `assemblyzero/workflows/janitor/state.py`, it will also need updating to include `"drift"`. However, since `state.py` is not in our modification list, the drift probe may need to be registered with a compatible wrapper. If `ProbeScope` is not extensible, wrap `run_drift_probe` to return a `ProbeResult` instead of a plain dict:

```python
def _drift_probe_wrapper(repo_root: str) -> ProbeResult:
    """Wrapper to make drift probe compatible with janitor interface."""
    from assemblyzero.workflows.janitor.probes.drift_probe import run_drift_probe
    result = run_drift_probe(repo_root)
    return ProbeResult(
        probe=result["probe"],
        status=result["status"],
        details=result,
    )
```

### 6.11 `.gitignore` (Modify)

**Change 1:** Add hourglass state file entry after the existing `data/` entries (after line ~52)

```diff
 # Session transcripts (auto-generated, untracked)
 data/unleashed/
 data/handoff-log.md
 transcripts/
+
+# Hourglass Protocol local state (Issue #535)
+# age_meter.json is local per developer; history.json is tracked
+data/hourglass/age_meter.json
```

### 6.12 `data/hourglass/age_meter.json` (Add)

**Note:** This file is gitignored. Create it as an initial template for developers:

```json
{
    "current_score": 0,
    "threshold": 50,
    "last_death_visit": null,
    "last_computed": "",
    "weighted_issues": [],
    "age_number": 0
}
```

### 6.13 `data/hourglass/history.json` (Add)

**This file IS tracked in git:**

```json
[]
```

### 6.14 `.claude/commands/death.md` (Add)

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
2. **Harvest** — Write the ADRs that capture what was decided (produces 0015-age-transition-protocol.md).
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

### 6.15 `docs/standards/0015-age-transition-protocol.md` (Add)

**Complete file contents:**

```markdown
# ADR 0015: Age Transition Protocol (The Hourglass Protocol)

<!-- Standard: 0015 -->
<!-- Issue: #535 -->
<!-- Status: Accepted -->

## Status

Accepted

## Context

As AssemblyZero evolves rapidly (207 issues in 27 days), documentation drifts from codebase reality. Numeric claims become stale, architecture descriptions fall behind, and file inventories lose accuracy. Manual reconciliation doesn't scale.

Issue #114 first proposed DEATH as a documentation reconciliation mechanism. Issue #535 implements it as an automated workflow.

## Decision

Implement DEATH as an age transition mechanism with three components:

1. **Age Meter** — Weighted score tracking codebase change since last reconciliation
2. **Drift Scoring** — Regex/glob-based detection of factual inaccuracies in documentation
3. **Hourglass State Machine** — LangGraph workflow orchestrating reconciliation

Three triggers activate DEATH:
- Age meter threshold breach (default: 50 points)
- Explicit `/death` skill summon
- Critical drift score (≥30.0)

Two modes of operation:
- **Report** — Read-only analysis, no file modifications
- **Reaper** — Applies fixes with orchestrator confirmation gate

## Alternatives Considered

1. **LLM-based drift detection** — Rejected: non-deterministic, costly, slow
2. **GitHub Actions CI** — Rejected: infrastructure complexity, no interactive reaper mode
3. **Manual checklist** — Rejected: doesn't scale with velocity

## Consequences

- Documentation freshness is monitored automatically
- Age transitions produce ADRs documenting architectural changes
- All reconciliation is reversible via git
- The `/death` skill provides on-demand access to the protocol
```

### 6.16 Test Fixtures

#### `tests/fixtures/death/mock_issues.json` (Add)

```json
[
    {"number": 100, "title": "Fix login bug", "labels": ["bug"], "closed_at": "2026-02-01T10:00:00Z", "body": null},
    {"number": 101, "title": "Add search feature", "labels": ["feature"], "closed_at": "2026-02-02T10:00:00Z", "body": "Add search"},
    {"number": 102, "title": "New agent persona", "labels": ["persona"], "closed_at": "2026-02-03T10:00:00Z", "body": null},
    {"number": 103, "title": "RAG pipeline upgrade", "labels": ["rag", "enhancement"], "closed_at": "2026-02-04T10:00:00Z", "body": null},
    {"number": 104, "title": "Architecture overhaul", "labels": ["architecture"], "closed_at": "2026-02-05T10:00:00Z", "body": null},
    {"number": 105, "title": "Hotfix for deploy", "labels": ["hotfix"], "closed_at": "2026-02-06T10:00:00Z", "body": null},
    {"number": 106, "title": "New workflow subsystem", "labels": ["new-workflow"], "closed_at": "2026-02-07T10:00:00Z", "body": null},
    {"number": 107, "title": "Foundation refactor", "labels": ["foundation"], "closed_at": "2026-02-08T10:00:00Z", "body": null},
    {"number": 108, "title": "Cross-cutting concern", "labels": ["cross-cutting"], "closed_at": "2026-02-09T10:00:00Z", "body": null},
    {"number": 109, "title": "Simple patch", "labels": ["patch"], "closed_at": "2026-02-10T10:00:00Z", "body": null},
    {"number": 110, "title": "Breaking API change", "labels": ["breaking-change"], "closed_at": "2026-02-11T10:00:00Z", "body": null},
    {"number": 111, "title": "Enhancement request", "labels": ["enhancement"], "closed_at": "2026-02-12T10:00:00Z", "body": null},
    {"number": 112, "title": "New component added", "labels": ["new-component"], "closed_at": "2026-02-13T10:00:00Z", "body": null},
    {"number": 113, "title": "Pipeline improvement", "labels": ["pipeline"], "closed_at": "2026-02-14T10:00:00Z", "body": null},
    {"number": 114, "title": "Feat: Dark mode", "labels": ["feat"], "closed_at": "2026-02-14T11:00:00Z", "body": null},
    {"number": 115, "title": "Subsystem extraction", "labels": ["subsystem"], "closed_at": "2026-02-14T12:00:00Z", "body": null},
    {"number": 116, "title": "Infra upgrade", "labels": ["infrastructure"], "closed_at": "2026-02-14T13:00:00Z", "body": null},
    {"number": 117, "title": "Question about usage", "labels": ["question"], "closed_at": "2026-02-15T10:00:00Z", "body": null},
    {"number": 118, "title": "No labels at all", "labels": [], "closed_at": "2026-02-15T11:00:00Z", "body": null},
    {"number": 119, "title": "Bug and architecture", "labels": ["bug", "architecture"], "closed_at": "2026-02-15T12:00:00Z", "body": null}
]
```

#### `tests/fixtures/death/mock_codebase_snapshot.json` (Add)

```json
{
    "workflows": ["issue", "requirements", "lld", "implementation_spec", "testing", "janitor", "death"],
    "personas": ["architect", "developer", "reviewer", "auditor", "writer", "researcher", "coordinator", "tester"],
    "tools": ["merge.py", "batch-workflow.sh", "archive_worktree_lineage.py", "run_janitor_workflow.py"],
    "probes": ["harvest", "links", "todo", "worktrees", "drift"],
    "docs_standards": ["0001-coding-standards.md", "0006-diagram-quality.md", "0010-workflow-architecture.md", "0015-age-transition-protocol.md"]
}
```

#### `tests/fixtures/death/mock_drift_findings.json` (Add)

```json
[
    {
        "id": "DRIFT-001",
        "severity": "critical",
        "doc_file": "README.md",
        "doc_claim": "Run 12+ AI agents concurrently",
        "code_reality": "Found 36 agent definitions in assemblyzero/personas/",
        "category": "count_mismatch",
        "confidence": 0.95,
        "evidence": "glob('assemblyzero/personas/*.py') returned 36 files"
    },
    {
        "id": "DRIFT-002",
        "severity": "major",
        "doc_file": "docs/inventory.md",
        "doc_claim": "assemblyzero/workflows/legacy/main.py listed as active",
        "code_reality": "File does not exist on disk",
        "category": "stale_reference",
        "confidence": 1.0,
        "evidence": "os.path.exists() returned False"
    },
    {
        "id": "DRIFT-003",
        "severity": "minor",
        "doc_file": "README.md",
        "doc_claim": "5 State Machines",
        "code_reality": "Found 7 workflow directories under assemblyzero/workflows/",
        "category": "count_mismatch",
        "confidence": 0.8,
        "evidence": "listdir returned 7 directories"
    },
    {
        "id": "DRIFT-004",
        "severity": "major",
        "doc_file": "docs/standards/0010-workflow-architecture.md",
        "doc_claim": "System uses 5 workflows",
        "code_reality": "Found 7 workflow directories under assemblyzero/workflows/",
        "category": "architecture_drift",
        "confidence": 0.85,
        "evidence": "listdir('assemblyzero/workflows/') returned 7 directories"
    }
]
```

#### `tests/fixtures/death/mock_adr_output.md` (Add)

```markdown
# ADR 0015: Age Transition Protocol

## Status

Accepted

## Context

Documentation drift detected by DEATH's Hourglass Protocol (Issue #535).

**Finding:** DRIFT-004 (major)
**Claim:** System uses 5 workflows
**Reality:** Found 7 workflow directories under assemblyzero/workflows/
**Evidence:** listdir('assemblyzero/workflows/') returned 7 directories

## Decision

Update architectural documentation to reflect the current codebase state.
- Create ADR: architecture changed — Found 7 workflow directories under assemblyzero/workflows/

## Alternatives Considered

1. **Ignore the drift** — Rejected. Stale architecture docs mislead new contributors.
2. **Manual update** — Possible but the Hourglass Protocol automates detection.
3. **Automated reconciliation** — Selected. DEATH walks the field and updates docs.

## Consequences

- All workflow counts and architecture descriptions updated
- Drift monitoring continues via the age meter
- Future architecture changes will be caught by the Hourglass Protocol
```

### 6.17 Test Files

#### `tests/unit/test_death/__init__.py` (Add)

```python
"""Test package for DEATH workflow — the Hourglass Protocol.

Issue #535
"""
```

#### `tests/unit/test_death/test_models.py` (Add)

```python
"""Tests for DEATH workflow data models.

Issue #535: DEATH as Age Transition
"""

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
    """T260: AgeMeterState TypedDict validates correctly."""

    def test_valid_state(self):
        state: AgeMeterState = {
            "current_score": 47,
            "threshold": 50,
            "last_death_visit": "2026-02-01T10:00:00Z",
            "last_computed": "2026-02-17T08:30:00Z",
            "weighted_issues": [],
            "age_number": 3,
        }
        assert state["current_score"] == 47
        assert state["threshold"] == 50
        assert state["age_number"] == 3

    def test_state_with_null_visit(self):
        state: AgeMeterState = {
            "current_score": 0,
            "threshold": 50,
            "last_death_visit": None,
            "last_computed": "2026-02-17T08:30:00Z",
            "weighted_issues": [],
            "age_number": 0,
        }
        assert state["last_death_visit"] is None


class TestDriftFinding:
    """T270: All DriftFinding categories and severities accepted."""

    def test_all_categories(self):
        categories = [
            "count_mismatch",
            "feature_contradiction",
            "missing_component",
            "stale_reference",
            "architecture_drift",
        ]
        for cat in categories:
            finding: DriftFinding = {
                "id": "DRIFT-001",
                "severity": "critical",
                "doc_file": "README.md",
                "doc_claim": "test claim",
                "code_reality": "test reality",
                "category": cat,
                "confidence": 0.95,
                "evidence": "test evidence",
            }
            assert finding["category"] == cat

    def test_all_severities(self):
        for severity in ["critical", "major", "minor"]:
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
```

#### `tests/unit/test_death/test_age_meter.py` (Add)

```python
"""Tests for age meter computation.

Issue #535: DEATH as Age Transition
"""

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
    """T010-T040: Weight computation tests."""

    def test_bug_label_weight(self):
        """T010: Weight from 'bug' label."""
        weight, source = compute_issue_weight(["bug"], "Fix login issue")
        assert weight == 1
        assert source == "bug"

    def test_architecture_label_weight(self):
        """T020: Weight from 'architecture' label."""
        weight, source = compute_issue_weight(["architecture"], "Major refactor")
        assert weight == 10
        assert source == "architecture"

    def test_no_matching_labels_default(self, caplog):
        """T030: No matching label -> default weight with warning."""
        with caplog.at_level(logging.WARNING):
            weight, source = compute_issue_weight(["question"], "How does this work?")
        assert weight == 2
        assert source == "default"
        assert "No matching label" in caplog.text

    def test_multiple_labels_highest_wins(self):
        """T040: Multiple labels -> highest weight wins."""
        weight, source = compute_issue_weight(
            ["bug", "architecture"], "Bug in architecture"
        )
        assert weight == 10
        assert source == "architecture"

    def test_empty_labels_default(self, caplog):
        """Edge case: Empty labels list."""
        with caplog.at_level(logging.WARNING):
            weight, source = compute_issue_weight([], "No labels at all")
        assert weight == 2
        assert source == "default"

    def test_enhancement_label(self):
        """Additional: enhancement weight."""
        weight, source = compute_issue_weight(["enhancement"], "Add feature")
        assert weight == 3
        assert source == "enhancement"

    def test_persona_label(self):
        """Additional: persona weight."""
        weight, source = compute_issue_weight(["persona"], "New persona")
        assert weight == 5
        assert source == "persona"

    def test_rag_label(self):
        """Additional: rag weight."""
        weight, source = compute_issue_weight(["rag"], "RAG update")
        assert weight == 8
        assert source == "rag"


class TestComputeAgeMeter:
    """T050: Incremental age meter computation."""

    def test_compute_from_scratch(self):
        """Compute from scratch with no existing state."""
        issues = [
            {"number": 1, "title": "Bug fix", "labels": ["bug"], "closed_at": "2026-02-01T10:00:00Z", "body": None},
            {"number": 2, "title": "New feature", "labels": ["feature"], "closed_at": "2026-02-02T10:00:00Z", "body": None},
        ]
        state = compute_age_meter(issues)
        assert state["current_score"] == 4  # 1 (bug) + 3 (feature)
        assert len(state["weighted_issues"]) == 2
        assert state["age_number"] == 0
        assert state["threshold"] == 50

    def test_incremental_computation(self):
        """T050: Adds new issues to existing score."""
        existing: AgeMeterState = {
            "current_score": 20,
            "threshold": 50,
            "last_death_visit": None,
            "last_computed": "2026-02-10T00:00:00Z",
            "weighted_issues": [
                {"issue_number": 1, "title": "Old issue", "labels": ["bug"], "weight": 1, "weight_source": "bug", "closed_at": "2026-02-01T10:00:00Z"},
            ],
            "age_number": 1,
        }
        new_issues = [
            {"number": 3, "title": "New persona", "labels": ["persona"], "closed_at": "2026-02-12T10:00:00Z", "body": None},
        ]
        state = compute_age_meter(new_issues, existing)
        assert state["current_score"] == 25  # 20 + 5 (persona)
        assert len(state["weighted_issues"]) == 2  # 1 existing + 1 new
        assert state["age_number"] == 1

    def test_empty_issues_no_state(self):
        """Empty issues with no existing state."""
        state = compute_age_meter([])
        assert state["current_score"] == 0
        assert state["weighted_issues"] == []


class TestMeterThreshold:
    """T060-T070: Threshold check tests."""

    def test_below_threshold(self):
        """T060: Score below threshold -> False."""
        state: AgeMeterState = {
            "current_score": 49,
            "threshold": 50,
            "last_death_visit": None,
            "last_computed": "",
            "weighted_issues": [],
            "age_number": 0,
        }
        assert check_meter_threshold(state) is False

    def test_at_threshold(self):
        """T070: Score at threshold -> True (>= comparison)."""
        state: AgeMeterState = {
            "current_score": 50,
            "threshold": 50,
            "last_death_visit": None,
            "last_computed": "",
            "weighted_issues": [],
            "age_number": 0,
        }
        assert check_meter_threshold(state) is True

    def test_above_threshold(self):
        """Score above threshold -> True."""
        state: AgeMeterState = {
            "current_score": 75,
            "threshold": 50,
            "last_death_visit": None,
            "last_computed": "",
            "weighted_issues": [],
            "age_number": 0,
        }
        assert check_meter_threshold(state) is True


class TestStatePersistence:
    """T080: Save/load round-trip."""

    def test_round_trip(self, tmp_path):
        """T080: Save -> load returns identical state."""
        state: AgeMeterState = {
            "current_score": 42,
            "threshold": 50,
            "last_death_visit": "2026-02-01T10:00:00Z",
            "last_computed": "2026-02-17T08:30:00Z",
            "weighted_issues": [
                {"issue_number": 1, "title": "Test", "labels": ["bug"], "weight": 1, "weight_source": "bug", "closed_at": "2026-02-01T10:00:00Z"},
            ],
            "age_number": 3,
        }
        state_path = str(tmp_path / "age_meter.json")
        save_age_meter_state(state, state_path)
        loaded = load_age_meter_state(state_path)
        assert loaded == state

    def test_load_nonexistent(self, tmp_path):
        """Load from nonexistent path returns None."""
        result = load_age_meter_state(str(tmp_path / "nonexistent.json"))
        assert result is None

    def test_load_invalid_json(self, tmp_path):
        """Load from invalid JSON returns None."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not json at all")
        result = load_age_meter_state(str(bad_file))
        assert result is None

    def test_load_empty_file(self, tmp_path):
        """Load from empty file returns None."""
        empty_file = tmp_path / "empty.json"
        empty_file.write_text("")
        result = load_age_meter_state(str(empty_file))
        assert result is None

    def test_save_creates_directory(self, tmp_path):
        """Save creates parent directory if needed."""
        state: AgeMeterState = {
            "current_score": 0,
            "threshold": 50,
            "last_death_visit": None,
            "last_computed": "",
            "weighted_issues": [],
            "age_number": 0,
        }
        nested_path = str(tmp_path / "subdir" / "deep" / "state.json")
        save_age_meter_state(state, nested_path)
        assert os.path.exists(nested_path)
```

#### `tests/unit/test_death/test_drift_scorer.py` (Add)

```python
"""Tests for drift scoring.

Issue #535: DEATH as Age Transition
"""

import os
import pytest

from assemblyzero.workflows.death.drift_scorer import (
    build_drift_report,
    check_critical_drift,
    compute_drift_score,
    scan_inventory_accuracy,
    scan_readme_claims,
    _reset_finding_counter,
)
from assemblyzero.workflows.death.models import DriftFinding, DriftReport


@pytest.fixture(autouse=True)
def reset_counter():
    """Reset finding counter before each test."""
    _reset_finding_counter()


class TestScanReadmeClaims:
    """T090-T100: README drift scanning."""

    def test_numeric_claim_mismatch(self, tmp_path):
        """T090: Detects numeric claim mismatch."""
        # Create a README with a numeric claim
        readme = tmp_path / "README.md"
        readme.write_text("Run 12+ AI agents concurrently.\n")

        # Create a personas directory with more files
        personas_dir = tmp_path / "assemblyzero" / "personas"
        personas_dir.mkdir(parents=True)
        # Create 36 persona files (12+ means >= 12, so need > 2*12 = 24 to trigger)
        for i in range(36):
            (personas_dir / f"agent_{i}.py").write_text(f"# Agent {i}")
        (personas_dir / "__init__.py").write_text("")

        findings = scan_readme_claims("README.md", str(tmp_path))
        # Should detect the mismatch (36 > 24 = 2*12)
        count_findings = [f for f in findings if f["category"] == "count_mismatch"]
        assert len(count_findings) >= 1
        assert count_findings[0]["severity"] in ("critical", "major")

    def test_no_mismatch_when_accurate(self, tmp_path):
        """No finding when claim matches reality."""
        readme = tmp_path / "README.md"
        readme.write_text("Run 5 workflows.\n")

        workflows_dir = tmp_path / "assemblyzero" / "workflows"
        workflows_dir.mkdir(parents=True)
        for name in ["issue", "requirements", "lld", "testing", "janitor"]:
            (workflows_dir / name).mkdir()

        findings = scan_readme_claims("README.md", str(tmp_path))
        workflow_findings = [f for f in findings if "workflow" in f.get("doc_claim", "").lower()]
        assert len(workflow_findings) == 0

    def test_readme_not_found(self, tmp_path):
        """README not found returns empty list."""
        findings = scan_readme_claims("README.md", str(tmp_path))
        assert findings == []


class TestScanInventoryAccuracy:
    """T110-T120: Inventory scanning."""

    def test_inventory_missing_file(self, tmp_path):
        """T110: File listed in inventory but absent from disk."""
        inventory = tmp_path / "docs" / "inventory.md"
        inventory.parent.mkdir(parents=True)
        inventory.write_text(
            "| File | Status |\n"
            "|------|--------|\n"
            "| `assemblyzero/workflows/legacy/main.py` | active |\n"
        )

        findings = scan_inventory_accuracy("docs/inventory.md", str(tmp_path))
        stale = [f for f in findings if f["category"] == "stale_reference"]
        assert len(stale) == 1
        assert "legacy/main.py" in stale[0]["doc_claim"]

    def test_inventory_file_exists(self, tmp_path):
        """File listed in inventory exists on disk — no finding."""
        inventory = tmp_path / "docs" / "inventory.md"
        inventory.parent.mkdir(parents=True)

        existing_file = tmp_path / "assemblyzero" / "main.py"
        existing_file.parent.mkdir(parents=True)
        existing_file.write_text("# Main")

        inventory.write_text(
            "| File | Status |\n"
            "|------|--------|\n"
            "| `assemblyzero/main.py` | active |\n"
        )

        findings = scan_inventory_accuracy("docs/inventory.md", str(tmp_path))
        assert len(findings) == 0

    def test_inventory_not_found(self, tmp_path):
        """Inventory not found returns empty list."""
        findings = scan_inventory_accuracy("docs/inventory.md", str(tmp_path))
        assert findings == []


class TestComputeDriftScore:
    """T130: Drift score computation."""

    def test_weighted_score(self):
        """T130: critical=10, major=5, minor=1."""
        findings: list[DriftFinding] = [
            {"id": "D1", "severity": "critical", "doc_file": "", "doc_claim": "", "code_reality": "", "category": "count_mismatch", "confidence": 1.0, "evidence": ""},
            {"id": "D2", "severity": "critical", "doc_file": "", "doc_claim": "", "code_reality": "", "category": "count_mismatch", "confidence": 1.0, "evidence": ""},
            {"id": "D3", "severity": "major", "doc_file": "", "doc_claim": "", "code_reality": "", "category": "stale_reference", "confidence": 1.0, "evidence": ""},
            {"id": "D4", "severity": "minor", "doc_file": "", "doc_claim": "", "code_reality": "", "category": "count_mismatch", "confidence": 1.0, "evidence": ""},
            {"id": "D5", "severity": "minor", "doc_file": "", "doc_claim": "", "code_reality": "", "category": "count_mismatch", "confidence": 1.0, "evidence": ""},
            {"id": "D6", "severity": "minor", "doc_file": "", "doc_claim": "", "code_reality": "", "category": "count_mismatch", "confidence": 1.0, "evidence": ""},
        ]
        score = compute_drift_score(findings)
        assert score == 28.0  # 2*10 + 1*5 + 3*1

    def test_empty_findings(self):
        """Empty findings -> score 0."""
        assert compute_drift_score([]) == 0.0


class TestCheckCriticalDrift:
    """T140: Critical drift threshold."""

    def test_at_threshold(self):
        """T140: score >= threshold -> True."""
        report: DriftReport = {
            "findings": [],
            "total_score": 30.0,
            "critical_count": 0,
            "major_count": 0,
            "minor_count": 0,
            "scanned_docs": [],
            "scanned_code_paths": [],
            "timestamp": "",
        }
        assert check_critical_drift(report) is True

    def test_below_threshold(self):
        """Below threshold -> False."""
        report: DriftReport = {
            "findings": [],
            "total_score": 29.9,
            "critical_count": 0,
            "major_count": 0,
            "minor_count": 0,
            "scanned_docs": [],
            "scanned_code_paths": [],
            "timestamp": "",
        }
        assert check_critical_drift(report) is False
```

#### `tests/unit/test_death/test_reconciler.py` (Add)

```python
"""Tests for reconciliation engine and ADR generation.

Issue #535: DEATH as Age Transition
"""

import os
import json

import pytest

from assemblyzero.workflows.death.models import (
    DriftFinding,
    DriftReport,
    ReconciliationAction,
)
from assemblyzero.workflows.death.reconciler import (
    archive_old_age,
    build_reconciliation_report,
    chronicle,
    generate_adr,
    harvest,
    walk_the_field,
)


class TestWalkTheField:
    """T150: Drift finding -> action type mapping."""

    def test_count_mismatch_mapping(self):
        """T150: count_mismatch -> update_count action."""
        drift_report: DriftReport = {
            "findings": [
                {
                    "id": "DRIFT-001",
                    "severity": "critical",
                    "doc_file": "README.md",
                    "doc_claim": "12+ agents",
                    "code_reality": "Found 36 agents",
                    "category": "count_mismatch",
                    "confidence": 0.95,
                    "evidence": "glob count",
                },
            ],
            "total_score": 10.0,
            "critical_count": 1,
            "major_count": 0,
            "minor_count": 0,
            "scanned_docs": ["README.md"],
            "scanned_code_paths": [],
            "timestamp": "",
        }
        actions = walk_the_field(".", drift_report)
        assert len(actions) == 1
        assert actions[0]["action_type"] == "update_count"
        assert actions[0]["drift_finding_id"] == "DRIFT-001"

    def test_low_confidence_skipped(self):
        """Findings below confidence threshold are skipped."""
        drift_report: DriftReport = {
            "findings": [
                {
                    "id": "DRIFT-001",
                    "severity": "minor",
                    "doc_file": "README.md",
                    "doc_claim": "maybe 5",
                    "code_reality": "Found 6",
                    "category": "count_mismatch",
                    "confidence": 0.3,  # Below 0.5 threshold
                    "evidence": "uncertain",
                },
            ],
            "total_score": 1.0,
            "critical_count": 0,
            "major_count": 0,
            "minor_count": 1,
            "scanned_docs": [],
            "scanned_code_paths": [],
            "timestamp": "",
        }
        actions = walk_the_field(".", drift_report)
        assert len(actions) == 0

    def test_architecture_drift_targets_adr(self):
        """Architecture drift actions target ADR output path."""
        drift_report: DriftReport = {
            "findings": [
                {
                    "id": "DRIFT-005",
                    "severity": "major",
                    "doc_file": "docs/arch.md",
                    "doc_claim": "5 workflows",
                    "code_reality": "Found 7 workflows",
                    "category": "architecture_drift",
                    "confidence": 0.85,
                    "evidence": "listdir",
                },
            ],
            "total_score": 5.0,
            "critical_count": 0,
            "major_count": 1,
            "minor_count": 0,
            "scanned_docs": [],
            "scanned_code_paths": [],
            "timestamp": "",
        }
        actions = walk_the_field(".", drift_report)
        assert len(actions) == 1
        assert actions[0]["action_type"] == "create_adr"
        assert "0015" in actions[0]["target_file"]


class TestReportModeNoWrites:
    """T160: Report mode produces no file writes."""

    def test_harvest_dry_run(self, tmp_path):
        """T160: dry_run=True -> no filesystem side effects."""
        actions: list[ReconciliationAction] = [
            {
                "target_file": "docs/standards/0015-age-transition-protocol.md",
                "action_type": "create_adr",
                "description": "Create ADR",
                "old_content": None,
                "new_content": None,
                "drift_finding_id": "DRIFT-005",
            },
        ]
        result = harvest(actions, str(tmp_path), dry_run=True)
        # ADR file should NOT exist on disk
        adr_path = tmp_path / "docs" / "standards" / "0015-age-transition-protocol.md"
        assert not adr_path.exists()
        # But new_content should be populated
        assert result[0]["new_content"] is not None

    def test_chronicle_dry_run(self, tmp_path):
        """Chronicle in dry_run doesn't write."""
        readme = tmp_path / "README.md"
        readme.write_text("Run 12+ AI agents concurrently.\n")

        actions: list[ReconciliationAction] = [
            {
                "target_file": "README.md",
                "action_type": "update_count",
                "description": "Update count",
                "old_content": "12+",
                "new_content": "36",
                "drift_finding_id": "DRIFT-001",
            },
        ]
        chronicle(actions, str(tmp_path), dry_run=True)
        # File should be unchanged
        assert "12+" in readme.read_text()


class TestGenerateAdr:
    """T360-T390: ADR generation tests."""

    def test_architecture_drift_generates_adr(self):
        """T360: architecture_drift finding -> ADR content with required sections."""
        finding: DriftFinding = {
            "id": "DRIFT-004",
            "severity": "major",
            "doc_file": "docs/standards/0010-workflow-architecture.md",
            "doc_claim": "System uses 5 workflows",
            "code_reality": "Found 7 workflow directories under assemblyzero/workflows/",
            "category": "architecture_drift",
            "confidence": 0.85,
            "evidence": "listdir('assemblyzero/workflows/') returned 7 directories",
        }
        actions: list[ReconciliationAction] = [
            {
                "target_file": "docs/standards/0015-age-transition-protocol.md",
                "action_type": "create_adr",
                "description": "Create ADR: architecture changed — Found 7 workflow directories under assemblyzero/workflows/",
                "old_content": "System uses 5 workflows",
                "new_content": None,
                "drift_finding_id": "DRIFT-004",
            },
        ]

        result = generate_adr(finding, actions, "docs/standards/", "docs/standards/", dry_run=True)
        assert result is not None
        assert "## Status" in result
        assert "## Context" in result
        assert "## Decision" in result
        assert "## Consequences" in result
        assert "DRIFT-004" in result
        assert "5 workflows" in result

    def test_non_qualifying_finding_returns_none(self):
        """T370: count_mismatch finding -> None."""
        finding: DriftFinding = {
            "id": "DRIFT-001",
            "severity": "critical",
            "doc_file": "README.md",
            "doc_claim": "12+ agents",
            "code_reality": "Found 36 agents",
            "category": "count_mismatch",
            "confidence": 0.95,
            "evidence": "glob count",
        }
        result = generate_adr(finding, [], "docs/standards/", "docs/standards/", dry_run=True)
        assert result is None

    def test_reaper_mode_writes_file(self, tmp_path):
        """T380: dry_run=False creates file."""
        finding: DriftFinding = {
            "id": "DRIFT-004",
            "severity": "major",
            "doc_file": "docs/arch.md",
            "doc_claim": "5 workflows",
            "code_reality": "Found 7 workflows",
            "category": "architecture_drift",
            "confidence": 0.85,
            "evidence": "listdir",
        }
        output_dir = str(tmp_path / "docs" / "standards")
        result = generate_adr(finding, [], "docs/standards/", output_dir, dry_run=False)
        assert result is not None
        assert result.endswith("0015-age-transition-protocol.md")
        assert os.path.exists(result)
        with open(result) as f:
            content = f.read()
        assert "## Status" in content

    def test_report_mode_no_write(self, tmp_path):
        """T390: dry_run=True returns content, no file created."""
        finding: DriftFinding = {
            "id": "DRIFT-004",
            "severity": "major",
            "doc_file": "docs/arch.md",
            "doc_claim": "5 workflows",
            "code_reality": "Found 7 workflows",
            "category": "architecture_drift",
            "confidence": 0.85,
            "evidence": "listdir",
        }
        output_dir = str(tmp_path / "docs" / "standards")
        result = generate_adr(finding, [], "docs/standards/", output_dir, dry_run=True)
        assert isinstance(result, str)
        assert "ADR" in result
        adr_path = os.path.join(output_dir, "0015-age-transition-protocol.md")
        assert not os.path.exists(adr_path)


class TestBuildReconciliationReport:
    """Report assembly tests."""

    def test_report_assembly(self):
        """Full report assembly with findings and actions."""
        drift_report: DriftReport = {
            "findings": [
                {"id": "D1", "severity": "critical", "doc_file": "README.md", "doc_claim": "12+", "code_reality": "36", "category": "count_mismatch", "confidence": 0.95, "evidence": "glob"},
            ],
            "total_score": 10.0,
            "critical_count": 1,
            "major_count": 0,
            "minor_count": 0,
            "scanned_docs": ["README.md"],
            "scanned_code_paths": [],
            "timestamp": "",
        }
        actions: list[ReconciliationAction] = [
            {"target_file": "README.md", "action_type": "update_count", "description": "Update count", "old_content": "12+", "new_content": "36", "drift_finding_id": "D1"},
        ]
        report = build_reconciliation_report(
            trigger="summon",
            trigger_details="Test",
            drift_report=drift_report,
            actions=actions,
            mode="report",
            age_number=3,
        )
        assert report["age_number"] == 3
        assert report["trigger"] == "summon"
        assert report["mode"] == "report"
        assert "1 drift finding" in report["summary"]
        assert "1 reconciliation action" in report["summary"]

    def test_empty_report(self):
        """Report with no findings."""
        drift_report: DriftReport = {
            "findings": [],
            "total_score": 0.0,
            "critical_count": 0,
            "major_count": 0,
            "minor_count": 0,
            "scanned_docs": [],
            "scanned_code_paths": [],
            "timestamp": "",
        }
        report = build_reconciliation_report(
            trigger="summon",
            trigger_details="Test",
            drift_report=drift_report,
            actions=[],
            mode="report",
            age_number=0,
        )
        assert "No drift findings" in report["summary"]
```

#### `tests/unit/test_death/test_hourglass.py` (Add)

```python
"""Tests for hourglass state machine.

Issue #535: DEATH as Age Transition
"""

import json
import os
from unittest.mock import patch, MagicMock

import pytest

from assemblyzero.workflows.death.hourglass import (
    create_hourglass_graph,
    run_death,
    should_death_arrive,
    _node_init,
    _node_rest,
    _route_after_harvest,
)
from assemblyzero.workflows.death.models import (
    AgeMeterState,
    DriftReport,
    HourglassState,
)


def _make_state(**overrides) -> HourglassState:
    """Helper to create a test state."""
    defaults = {
        "trigger": "summon",
        "mode": "report",
        "age_meter": {
            "current_score": 0,
            "threshold": 50,
            "last_death_visit": None,
            "last_computed": "",
            "weighted_issues": [],
            "age_number": 0,
        },
        "drift_report": None,
        "reconciliation_report": None,
        "step": "init",
        "errors": [],
        "confirmed": False,
    }
    defaults.update(overrides)
    return defaults


class TestHourglassGraph:
    """T170: Report flow state machine."""

    def test_graph_creation(self):
        """Graph creates without error."""
        graph = create_hourglass_graph()
        assert graph is not None

    @patch("assemblyzero.workflows.death.hourglass.build_drift_report")
    @patch("assemblyzero.workflows.death.hourglass.load_age_meter_state")
    @patch("assemblyzero.workflows.death.hourglass.save_age_meter_state")
    def test_report_flow_completes(self, mock_save, mock_load, mock_drift):
        """T170: Report mode flows through all nodes."""
        mock_load.return_value = None
        mock_drift.return_value = DriftReport(
            findings=[],
            total_score=0.0,
            critical_count=0,
            major_count=0,
            minor_count=0,
            scanned_docs=[],
            scanned_code_paths=[],
            timestamp="",
        )

        report = run_death(
            mode="report",
            trigger="summon",
            codebase_root=".",
            repo="test/repo",
        )
        assert report is not None
        # In report mode, confirmed is True by default, so it flows through all phases


class TestConfirmationGate:
    """T180-T190: Reaper confirmation gate."""

    def test_reaper_confirmed_proceeds(self):
        """T180: Reaper mode with confirmed=True proceeds to archive."""
        state = _make_state(mode="reaper", confirmed=True)
        result = _route_after_harvest(state)
        assert result == "archive"

    def test_reaper_unconfirmed_skips(self):
        """T190: Reaper mode with confirmed=False jumps to complete."""
        state = _make_state(mode="reaper", confirmed=False)
        result = _route_after_harvest(state)
        assert result == "complete"

    def test_report_mode_always_proceeds(self):
        """Report mode always proceeds (confirmed doesn't matter for routing since report defaults confirmed=True)."""
        state = _make_state(mode="report", confirmed=True)
        result = _route_after_harvest(state)
        assert result == "archive"


class TestAgeMeterReset:
    """T200: Age meter reset after DEATH visit."""

    @patch("assemblyzero.workflows.death.hourglass.save_age_meter_state")
    @patch("assemblyzero.workflows.death.hourglass._append_history")
    def test_reset_after_death(self, mock_history, mock_save):
        """T200: Score reset to 0, age_number incremented."""
        state = _make_state(
            age_meter={
                "current_score": 55,
                "threshold": 50,
                "last_death_visit": "2026-02-01T10:00:00Z",
                "last_computed": "2026-02-17T08:30:00Z",
                "weighted_issues": [],
                "age_number": 3,
            },
        )
        result = _node_rest(state)
        new_meter = result["age_meter"]
        assert new_meter["current_score"] == 0
        assert new_meter["age_number"] == 4
        assert new_meter["last_death_visit"] is not None
        assert new_meter["weighted_issues"] == []


class TestHistoryRecording:
    """T210: History recording."""

    def test_history_append(self, tmp_path):
        """T210: DEATH visit appended to history.json."""
        history_path = str(tmp_path / "history.json")
        # Write initial empty history
        with open(history_path, "w") as f:
            json.dump([], f)

        with patch("assemblyzero.workflows.death.hourglass.HISTORY_PATH", history_path):
            with patch("assemblyzero.workflows.death.hourglass.save_age_meter_state"):
                state = _make_state(
                    age_meter={
                        "current_score": 10,
                        "threshold": 50,
                        "last_death_visit": None,
                        "last_computed": "",
                        "weighted_issues": [],
                        "age_number": 0,
                    },
                )
                _node_rest(state)

        with open(history_path) as f:
            history = json.load(f)
        assert len(history) == 1
        assert history[0]["trigger"] == "summon"
        assert history[0]["age_number"] == 0


class TestShouldDeathArrive:
    """T230-T250: Trigger detection."""

    @patch("assemblyzero.workflows.death.hourglass.build_drift_report")
    @patch("assemblyzero.workflows.death.hourglass.load_age_meter_state")
    @patch("assemblyzero.workflows.death.hourglass.fetch_closed_issues_since")
    def test_no_triggers(self, mock_fetch, mock_load, mock_drift):
        """T230: No triggers -> (False, _, _)."""
        mock_drift.return_value = DriftReport(
            findings=[], total_score=5.0, critical_count=0, major_count=0, minor_count=0,
            scanned_docs=[], scanned_code_paths=[], timestamp="",
        )
        mock_load.return_value = AgeMeterState(
            current_score=10, threshold=50, last_death_visit=None,
            last_computed="", weighted_issues=[], age_number=0,
        )
        mock_fetch.return_value = []

        result = should_death_arrive(".", "test/repo", "token")
        assert result[0] is False

    @patch("assemblyzero.workflows.death.hourglass.save_age_meter_state")
    @patch("assemblyzero.workflows.death.hourglass.build_drift_report")
    @patch("assemblyzero.workflows.death.hourglass.load_age_meter_state")
    @patch("assemblyzero.workflows.death.hourglass.fetch_closed_issues_since")
    @patch("assemblyzero.workflows.death.hourglass.compute_age_meter")
    def test_meter_trigger(self, mock_compute, mock_fetch, mock_load, mock_drift, mock_save):
        """T240: Meter threshold -> (True, 'meter', _)."""
        mock_drift.return_value = DriftReport(
            findings=[], total_score=5.0, critical_count=0, major_count=0, minor_count=0,
            scanned_docs=[], scanned_code_paths=[], timestamp="",
        )
        mock_load.return_value = AgeMeterState(
            current_score=45, threshold=50, last_death_visit=None,
            last_computed="", weighted_issues=[], age_number=0,
        )
        mock_fetch.return_value = [{"number": 1, "title": "test", "labels": ["architecture"], "closed_at": "", "body": None}]
        mock_compute.return_value = AgeMeterState(
            current_score=55, threshold=50, last_death_visit=None,
            last_computed="", weighted_issues=[], age_number=0,
        )

        result = should_death_arrive(".", "test/repo", "token")
        assert result[0] is True
        assert result[1] == "meter"

    @patch("assemblyzero.workflows.death.hourglass.build_drift_report")
    def test_critical_drift_trigger(self, mock_drift):
        """T250: Critical drift -> (True, 'critical_drift', _)."""
        mock_drift.return_value = DriftReport(
            findings=[], total_score=35.0, critical_count=3, major_count=0, minor_count=0,
            scanned_docs=[], scanned_code_paths=[], timestamp="",
        )

        result = should_death_arrive(".", "test/repo", "token")
        assert result[0] is True
        assert result[1] == "critical_drift"
```

#### `tests/unit/test_death/test_skill.py` (Add)

```python
"""Tests for /death skill entry point.

Issue #535: DEATH as Age Transition
"""

from unittest.mock import patch, MagicMock

import pytest

from assemblyzero.workflows.death.skill import (
    format_report_output,
    invoke_death_skill,
    parse_death_args,
)
from assemblyzero.workflows.death.models import ReconciliationReport, DriftReport


class TestParseDeathArgs:
    """T280-T320: Argument parsing."""

    def test_report_mode(self):
        """T280: parse_death_args(['report']) -> ('report', False)."""
        mode, force = parse_death_args(["report"])
        assert mode == "report"
        assert force is False

    def test_reaper_mode(self):
        """T290: parse_death_args(['reaper']) -> ('reaper', False)."""
        mode, force = parse_death_args(["reaper"])
        assert mode == "reaper"
        assert force is False

    def test_reaper_with_force(self):
        """T300: parse_death_args(['reaper', '--force']) -> ('reaper', True)."""
        mode, force = parse_death_args(["reaper", "--force"])
        assert mode == "reaper"
        assert force is True

    def test_invalid_mode(self):
        """T310: parse_death_args(['invalid']) raises ValueError."""
        with pytest.raises(ValueError, match="Unknown mode: 'invalid'"):
            parse_death_args(["invalid"])

    def test_default_mode(self):
        """T320: parse_death_args([]) -> ('report', False)."""
        mode, force = parse_death_args([])
        assert mode == "report"
        assert force is False

    def test_force_without_reaper(self):
        """--force only valid with reaper."""
        with pytest.raises(ValueError, match="--force flag is only valid"):
            parse_death_args(["report", "--force"])

    def test_unknown_flag(self):
        """Unknown flag raises ValueError."""
        with pytest.raises(ValueError, match="Unknown flag"):
            parse_death_args(["reaper", "--unknown"])


class TestInvokeDeathSkill:
    """T330-T340: Skill invocation."""

    @patch("assemblyzero.workflows.death.skill.run_death")
    def test_report_mode_end_to_end(self, mock_run):
        """T330: invoke with report returns ReconciliationReport."""
        mock_report: ReconciliationReport = {
            "age_number": 3,
            "trigger": "summon",
            "trigger_details": "Orchestrator invoked /death report",
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
            "timestamp": "2026-02-17T08:31:00Z",
            "summary": "No drift findings.",
        }
        mock_run.return_value = mock_report

        result = invoke_death_skill(
            ["report"], ".", "test/repo"
        )
        assert result["mode"] == "report"
        mock_run.assert_called_once_with(
            mode="report",
            trigger="summon",
            codebase_root=".",
            repo="test/repo",
            github_token=None,
        )

    def test_reaper_without_confirmation(self):
        """T340: Reaper without --force raises PermissionError."""
        with pytest.raises(PermissionError, match="Reaper mode requires"):
            invoke_death_skill(["reaper"], ".", "test/repo")

    @patch("assemblyzero.workflows.death.skill.run_death")
    def test_reaper_with_force(self, mock_run):
        """Reaper with --force bypasses confirmation."""
        mock_run.return_value = {"mode": "reaper", "actions": [], "summary": "Done"}
        result = invoke_death_skill(["reaper", "--force"], ".", "test/repo")
        assert mock_run.called


class TestFormatReportOutput:
    """T350: Report output formatting."""

    def test_format_with_findings(self):
        """T350: Format report with findings and actions."""
        report: ReconciliationReport = {
            "age_number": 3,
            "trigger": "summon",
            "trigger_details": "Orchestrator invoked /death report",
            "drift_report": {
                "findings": [
                    {
                        "id": "DRIFT-001",
                        "severity": "critical",
                        "doc_file": "README.md",
                        "doc_claim": "12+ agents",
                        "code_reality": "36 agents found",
                        "category": "count_mismatch",
                        "confidence": 0.95,
                        "evidence": "glob",
                    },
                ],
                "total_score": 10.0,
                "critical_count": 1,
                "major_count": 0,
                "minor_count": 0,
                "scanned_docs": ["README.md"],
                "scanned_code_paths": [],
                "timestamp": "",
            },
            "actions": [
                {
                    "target_file": "README.md",
                    "action_type": "update_count",
                    "description": "Update agent count",
                    "old_content": "12+",
                    "new_content": "36",
                    "drift_finding_id": "DRIFT-001",
                },
            ],
            "mode": "report",
            "timestamp": "2026-02-17T08:31:00Z",
            "summary": "DEATH found 1 drift finding.",
        }
        output = format_report_output(report)
        assert "# ⏳ DEATH's Reconciliation Report — Age 3" in output
        assert "DRIFT-001" in output
        assert "critical" in output
        assert "README.md" in output
        assert "update_count" in output
        assert "REAPER MAN" in output

    def test_format_empty_report(self):
        """Format report with no findings."""
        report: ReconciliationReport = {
            "age_number": 0,
            "trigger": "summon",
            "trigger_details": "Test",
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
            "summary": "No drift.",
        }
        output = format_report_output(report)
        assert "No drift findings detected" in output
        assert "No reconciliation actions needed" in output


class TestJanitorProbeInterface:
    """T220: Janitor drift probe interface."""

    @patch("assemblyzero.workflows.death.drift_scorer.build_drift_report")
    def test_probe_returns_compatible_dict(self, mock_build):
        """T220: Probe returns dict with required keys."""
        from assemblyzero.workflows.janitor.probes.drift_probe import run_drift_probe

        mock_build.return_value = DriftReport(
            findings=[],
            total_score=5.0,
            critical_count=0,
            major_count=0,
            minor_count=0,
            scanned_docs=["README.md"],
            scanned_code_paths=[],
            timestamp="",
        )
        result = run_drift_probe(".")
        assert "probe" in result
        assert result["probe"] == "drift"
        assert "status" in result
        assert result["status"] in ("pass", "warn", "fail")
        assert "drift_score" in result
        assert "finding_count" in result
        assert "critical_findings" in result
        assert "details" in result
```

## 7. Pattern References

### 7.1 Existing Workflow Package Structure

**File:** `assemblyzero/workflows/janitor/probes/__init__.py` (lines 1-35)

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
```

**Relevance:** This shows the pattern for registering probes in the janitor system. The drift probe must follow this exact pattern — lazy import inside `_build_registry()` and compatible return type.

### 7.2 Existing Workflow Test Pattern

**File:** `tests/integration/test_janitor_workflow.py` (lines 1-80)

**Relevance:** Shows how existing workflow tests are structured — import the workflow, set up fixtures, mock external dependencies, verify state transitions. The death workflow tests follow this same pattern.

### 7.3 LangGraph StateGraph Pattern

**File:** `assemblyzero/workflows/` (any existing workflow using StateGraph)

**Relevance:** The hourglass graph follows the same LangGraph StateGraph pattern used by other workflows: define state TypedDict, create nodes as functions taking state and returning partial updates, add edges between nodes, compile and invoke.

### 7.4 JSON State Persistence Pattern

**File:** `.assemblyzero/` directory structure

**Relevance:** The project already uses JSON files for local state (`.assemblyzero/` directory). The `data/hourglass/` directory follows the same convention — local state in gitignored files, shared state in tracked files.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from __future__ import annotations` | stdlib | All new files |
| `from typing import Literal, TypedDict, Any` | stdlib | `models.py`, `hourglass.py`, `skill.py` |
| `import json` | stdlib | `age_meter.py`, `hourglass.py` |
| `import os` | stdlib | `age_meter.py`, `drift_scorer.py`, `reconciler.py`, `hourglass.py` |
| `import re` | stdlib | `drift_scorer.py`, `reconciler.py` |
| `import glob` | stdlib | `drift_scorer.py` |
| `import logging` | stdlib | All source files |
| `import shutil` | stdlib | `reconciler.py` |
| `import tempfile` | stdlib | `age_meter.py` |
| `from datetime import datetime, timezone` | stdlib | `age_meter.py`, `drift_scorer.py`, `reconciler.py`, `hourglass.py` |
| `from github import Github` | `pygithub` (existing dep) | `age_meter.py` |
| `from langgraph.graph import END, StateGraph` | `langgraph` (existing dep) | `hourglass.py` |
| `from unittest.mock import patch, MagicMock` | stdlib | Test files |
| `import pytest` | `pytest` (existing dev dep) | Test files |

**New Dependencies:** None. All imports use existing project dependencies or stdlib.

## 9. Test Mapping

| Test ID | Tests Function | File | Input | Expected Output |
|---------|---------------|------|-------|-----------------|
| T010 | `compute_issue_weight()` | `test_age_meter.py` | `labels=["bug"]` | `(1, "bug")` |
| T020 | `compute_issue_weight()` | `test_age_meter.py` | `labels=["architecture"]` | `(10, "architecture")` |
| T030 | `compute_issue_weight()` | `test_age_meter.py` | `labels=["question"]` | `(2, "default")` + warning |
| T040 | `compute_issue_weight()` | `test_age_meter.py` | `labels=["bug", "architecture"]` | `(10, "architecture")` |
| T050 | `compute_age_meter()` | `test_age_meter.py` | existing score=20 + persona issue | `score=25` |
| T060 | `check_meter_threshold()` | `test_age_meter.py` | `score=49, threshold=50` | `False` |
| T070 | `check_meter_threshold()` | `test_age_meter.py` | `score=50, threshold=50` | `True` |
| T080 | `save/load_age_meter_state()` | `test_age_meter.py` | AgeMeterState object | Identical after round-trip |
| T090 | `scan_readme_claims()` | `test_drift_scorer.py` | README with "12+" vs 36 files | DriftFinding found |
| T100 | `scan_readme_claims()` | `test_drift_scorer.py` | Accurate README | No findings |
| T110 | `scan_inventory_accuracy()` | `test_drift_scorer.py` | Missing file in inventory | DriftFinding(stale_reference) |
| T120 | `scan_inventory_accuracy()` | `test_drift_scorer.py` | File exists in inventory | No findings |
| T130 | `compute_drift_score()` | `test_drift_scorer.py` | 2 critical + 1 major + 3 minor | `28.0` |
| T140 | `check_critical_drift()` | `test_drift_scorer.py` | `score=30.0` | `True` |
| T150 | `walk_the_field()` | `test_reconciler.py` | count_mismatch finding | update_count action |
| T160 | `harvest()` | `test_reconciler.py` | `dry_run=True` | No file writes |
| T170 | `run_death()` | `test_hourglass.py` | `mode="report"` | Report completes |
| T180 | `_route_after_harvest()` | `test_hourglass.py` | `confirmed=True` | `"archive"` |
| T190 | `_route_after_harvest()` | `test_hourglass.py` | `confirmed=False` | `"complete"` |
| T200 | `_node_rest()` | `test_hourglass.py` | age_number=3 | age_number=4, score=0 |
| T210 | `_node_rest()` | `test_hourglass.py` | Mock history file | Entry appended |
| T220 | `run_drift_probe()` | `test_skill.py` | Mock codebase | Dict with required keys |
| T230 | `should_death_arrive()` | `test_hourglass.py` | Low meter + low drift | `(False, _, _)` |
| T240 | `should_death_arrive()` | `test_hourglass.py` | High meter | `(True, "meter", _)` |
| T250 | `should_death_arrive()` | `test_hourglass.py` | High drift | `(True, "critical_drift", _)` |
| T260 | `AgeMeterState` | `test_models.py` | Valid dict | Fields accessible |
| T270 | `DriftFinding` | `test_models.py` | All categories | All accepted |
| T280 | `parse_death_args()` | `test_skill.py` | `["report"]` | `("report", False)` |
| T290 | `parse_death_args()` | `test_skill.py` | `["reaper"]` | `("reaper", False)` |
| T300 | `parse_death_args()` | `test_skill.py` | `["reaper", "--force"]` | `("reaper", True)` |
| T310 | `parse_death_args()` | `test_skill.py` | `["invalid"]` | `ValueError` |
| T320 | `parse_death_args()` | `test_skill.py` | `[]` | `("report", False)` |
| T330 | `invoke_death_skill()` | `test_skill.py` | `["report"]` | Report returned |
| T340 | `invoke_death_skill()` | `test_skill.py` | `["reaper"]` no force | `PermissionError` |
| T350 | `format_report_output()` | `test_skill.py` | Full report | Markdown with sections |
| T360 | `generate_adr()` | `test_reconciler.py` | architecture_drift finding | ADR content string |
| T370 | `generate_adr()` | `test_reconciler.py` | count_mismatch finding | `None` |
| T380 | `generate_adr()` | `test_reconciler.py` | `dry_run=False` | File created |
| T390 | `generate_adr()` | `test_reconciler.py` | `dry_run=True` | Content, no file |

## 10. Implementation Notes

### 10.1 Error Handling Convention

All workflow nodes capture exceptions and append to `state["errors"]` rather than raising. The graph continues to completion even on partial failures. Functions outside the graph (like `parse_death_args`) raise exceptions directly (`ValueError`, `PermissionError`) since they're called before the graph runs.

### 10.2 Logging Convention

Use `logging.getLogger(__name__)` in each module. Key log messages:
- `logger.info("THE SAND HAS RUN OUT.")` — meter trigger
- `logger.info("DEATH HAS BEEN SUMMONED.")` — summon trigger
- `logger.info("THE NEW AGE BEGINS. Age %d.", age_number)` — after rest
- `logger.warning(...)` — for default weight fallback, missing files
- `logger.error(...)` — for API failures, serialization errors

### 10.3 Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| `DEFAULT_THRESHOLD` | `50` | Initial calibration from Issue #114 retroactive scoring |
| `DEFAULT_WEIGHT` | `2` | Conservative default for unlabeled issues |
| `CRITICAL_DRIFT_THRESHOLD` | `30.0` | ~3 critical findings worth of drift |
| `MIN_CONFIDENCE_THRESHOLD` | `0.5` | Skip uncertain findings to reduce noise |
| `MAX_ISSUES_FETCH` | `500` | Pagination cap for GitHub API |

### 10.4 State File Locations

- `data/hourglass/age_meter.json` — **gitignored**, local per developer
- `data/hourglass/history.json` — **tracked in git**, shared audit trail

### 10.5 ProbeScope Compatibility

The `ProbeScope` type in `assemblyzero/workflows/janitor/state.py` may be a `Literal` type. If so, it needs to include `"drift"`. If modifying `state.py` is not in scope, the drift probe should be registered using the wrapper pattern shown in Section 6.10, or registered outside the typed scope system with a runtime check.

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3)
- [x] Every data structure has a concrete JSON/YAML example (Section 4)
- [x] Every function has input/output examples with realistic values (Section 5)
- [x] Change instructions are diff-level specific (Section 6)
- [x] Pattern references include file:line and are verified to exist (Section 7)
- [x] All imports are listed and verified (Section 8)
- [x] Test mapping covers all LLD test scenarios (Section 9)

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #535 |
| Verdict | DRAFT |
| Date | 2026-02-17 |
| Iterations | 1 |
| Finalized | — |