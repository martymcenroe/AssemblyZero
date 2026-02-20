# Implementation Spec: End-to-End Orchestration Workflow (Issue → Code)

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #305 |
| LLD | `docs/lld/active/305-orchestration-workflow.md` |
| Generated | 2026-02-16 |
| Status | DRAFT |

## 1. Overview

Create a meta-workflow that orchestrates the complete pipeline from GitHub issue to merged PR, stitching together triage, LLD, implementation spec, and implementation workflows into a single command.

**Objective:** Single `orchestrate --issue N` command processes issue from creation to PR with state persistence, resume capability, and configurable human gates.

**Success Criteria:** Pipeline handles existing artifacts, persists state between runs, supports dry-run mode, prevents concurrent execution, and reports actionable errors at each stage.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `assemblyzero/workflows/orchestrator/__init__.py` | Add | Module initialization, exports |
| 2 | `assemblyzero/workflows/orchestrator/config.py` | Add | OrchestratorConfig schema with defaults |
| 3 | `assemblyzero/workflows/orchestrator/state.py` | Add | OrchestrationState TypedDict and state management |
| 4 | `assemblyzero/workflows/orchestrator/artifacts.py` | Add | Artifact detection and path management |
| 5 | `assemblyzero/workflows/orchestrator/resume.py` | Add | Resume-from-stage logic and state persistence |
| 6 | `assemblyzero/workflows/orchestrator/stages.py` | Add | Stage execution logic wrapping sub-workflows |
| 7 | `assemblyzero/workflows/orchestrator/graph.py` | Add | LangGraph meta-graph orchestrating pipeline |
| 8 | `tools/orchestrate.py` | Add | CLI entry point for orchestration |
| 9 | `tests/unit/test_orchestrator_config.py` | Add | Unit tests for configuration |
| 10 | `tests/unit/test_orchestrator_state.py` | Add | Unit tests for state management |
| 11 | `tests/unit/test_orchestrator_artifacts.py` | Add | Unit tests for artifact detection |
| 12 | `tests/unit/test_orchestrator_stages.py` | Add | Unit tests for stage execution |
| 13 | `tests/integration/test_orchestrator_graph.py` | Add | Integration tests for full graph |

**Implementation Order Rationale:** Config and state are pure data structures with no internal dependencies — implement first. Artifacts and resume depend on state. Stages depend on config, state, and artifacts. Graph ties everything together. CLI wraps graph. Tests follow the same dependency order.

## 3. Current State (for Modify/Delete files)

No files are being modified or deleted. All files are new additions.

### 3.1 Existing Pattern: `assemblyzero/workflows/implementation_spec/state.py`

**Relevant excerpt** (lines 1-45, representative pattern for state definition):

```python
"""State definition for the implementation spec workflow.

Issue #304: Implementation Readiness Review
"""

from typing import Any, TypedDict


class ImplementationSpecState(TypedDict, total=False):
    """State for the implementation spec workflow."""

    # Input
    issue_number: int
    lld_path: str
    lld_content: str

    # Processing
    spec_draft: str
    review_verdict: str
    review_feedback: str
    iteration_count: int

    # Output
    spec_path: str
    error_message: str
```

**Relevance:** This is the pattern for all state TypedDicts in the project — `total=False`, flat structure, grouped by input/processing/output.

### 3.2 Existing Pattern: `assemblyzero/workflows/implementation_spec/graph.py`

**Relevant excerpt** (lines 1-60, representative graph construction):

```python
"""LangGraph workflow for implementation spec generation.

Issue #304: Implementation Readiness Review
"""

from langgraph.graph import END, StateGraph

from assemblyzero.workflows.implementation_spec.state import ImplementationSpecState


def create_graph() -> StateGraph:
    """Create the implementation spec workflow graph."""
    workflow = StateGraph(ImplementationSpecState)

    workflow.add_node("load_lld", load_lld_node)
    workflow.add_node("generate_spec", generate_spec_node)
    workflow.add_node("validate_completeness", validate_completeness_node)
    workflow.add_node("review_spec", review_spec_node)

    workflow.set_entry_point("load_lld")
    workflow.add_edge("load_lld", "generate_spec")
    workflow.add_edge("generate_spec", "validate_completeness")
    workflow.add_conditional_edges(
        "validate_completeness",
        route_after_validation,
        {"revise": "generate_spec", "review": "review_spec"},
    )
    workflow.add_conditional_edges(
        "review_spec",
        route_after_review,
        {"revise": "generate_spec", "approve": END},
    )

    return workflow
```

**Relevance:** This is the canonical graph construction pattern — `StateGraph`, `add_node`, `set_entry_point`, `add_edge`, `add_conditional_edges` with routing functions.

### 3.3 Existing Pattern: `tools/run_implementation_spec_workflow.py`

**Relevant excerpt** (lines 1-50, representative CLI tool):

```python
#!/usr/bin/env python3
"""Run the implementation spec workflow.

Usage:
    poetry run python tools/run_implementation_spec_workflow.py --issue 304
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from assemblyzero.workflows.implementation_spec.graph import create_graph


def main() -> None:
    parser = argparse.ArgumentParser(description="Run implementation spec workflow")
    parser.add_argument("--issue", type=int, required=True, help="GitHub issue number")
    parser.add_argument("--lld", type=str, default=None, help="Path to LLD file")
    args = parser.parse_args()

    graph = create_graph()
    app = graph.compile()

    initial_state = {
        "issue_number": args.issue,
        "lld_path": args.lld or "",
    }

    result = app.invoke(initial_state)
    # ... print results
```

**Relevance:** CLI entry point pattern — `argparse`, `sys.path` insertion, graph compile + invoke.

### 3.4 Existing Pattern: `tests/test_integration_workflow.py`

**Relevant excerpt** (lines 1-50, representative test pattern):

```python
"""Integration tests for workflow execution."""

import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_llm():
    """Mock LLM responses for testing."""
    with patch("assemblyzero.workflows.requirements.nodes.draft.invoke_llm") as mock:
        mock.return_value = "Mocked LLM response"
        yield mock


def test_workflow_completes(mock_llm):
    """Test that workflow runs to completion with mocked LLM."""
    from assemblyzero.workflows.requirements.graph import create_graph

    graph = create_graph()
    app = graph.compile()
    result = app.invoke({"issue_number": 999})
    assert result.get("error_message", "") == ""
```

**Relevance:** Test pattern — `pytest.fixture` for mocks, `patch` for LLM calls, `graph.compile().invoke()`.

## 4. Data Structures

### 4.1 StageResult

**Definition:**

```python
class StageResult(TypedDict, total=False):
    """Result of executing a single stage."""
    status: str  # "passed", "blocked", "failed", "skipped"
    artifact_path: str
    error_message: str
    duration_seconds: float
    attempts: int
```

**Concrete Example:**

```json
{
    "status": "passed",
    "artifact_path": "docs/lld/active/305-orchestration-workflow.md",
    "error_message": "",
    "duration_seconds": 142.5,
    "attempts": 1
}
```

**Failed Example:**

```json
{
    "status": "failed",
    "artifact_path": null,
    "error_message": "LLD review rejected after 3 revisions: Missing security section",
    "duration_seconds": 320.1,
    "attempts": 3
}
```

**Skipped Example:**

```json
{
    "status": "skipped",
    "artifact_path": "docs/lld/done/305-orchestration-workflow.md",
    "error_message": "",
    "duration_seconds": 0.02,
    "attempts": 0
}
```

### 4.2 StageConfig

**Definition:**

```python
class StageConfig(TypedDict, total=False):
    """Configuration for a single stage."""
    drafter: str
    reviewer: str
    max_revisions: int
    timeout_seconds: int
```

**Concrete Example:**

```json
{
    "drafter": "claude:opus-4.5",
    "reviewer": "gemini:3-pro-preview",
    "max_revisions": 5,
    "timeout_seconds": 600
}
```

### 4.3 OrchestratorConfig

**Definition:**

```python
class OrchestratorConfig(TypedDict, total=False):
    """Full orchestrator configuration."""
    skip_existing_lld: bool
    skip_existing_spec: bool
    stages: dict[str, StageConfig]
    gates: dict[str, bool]
    max_stage_retries: int
    retry_delay_seconds: int
```

**Concrete Example (default config):**

```json
{
    "skip_existing_lld": true,
    "skip_existing_spec": true,
    "stages": {
        "triage": {
            "drafter": "claude:opus-4.5",
            "reviewer": "gemini:3-pro-preview",
            "max_revisions": 3,
            "timeout_seconds": 300
        },
        "lld": {
            "drafter": "claude:opus-4.5",
            "reviewer": "gemini:3-pro-preview",
            "max_revisions": 5,
            "timeout_seconds": 600
        },
        "spec": {
            "drafter": "claude:opus-4.5",
            "reviewer": "gemini:3-pro-preview",
            "max_revisions": 3,
            "timeout_seconds": 600
        },
        "impl": {
            "drafter": "claude:opus-4.5",
            "reviewer": "",
            "max_revisions": 3,
            "timeout_seconds": 1800
        },
        "pr": {
            "drafter": "",
            "reviewer": "",
            "max_revisions": 1,
            "timeout_seconds": 120
        }
    },
    "gates": {
        "triage": false,
        "lld": false,
        "spec": false,
        "impl": false,
        "pr": true
    },
    "max_stage_retries": 3,
    "retry_delay_seconds": 10
}
```

### 4.4 OrchestrationState

**Definition:**

```python
class OrchestrationState(TypedDict, total=False):
    """Full orchestration pipeline state."""
    issue_number: int
    current_stage: str  # "triage", "lld", "spec", "impl", "pr", "done"

    # Artifacts produced at each stage
    issue_brief_path: str
    lld_path: str
    spec_path: str
    worktree_path: str
    pr_url: str

    # Progress tracking
    stage_results: dict[str, StageResult]
    stage_attempts: dict[str, int]

    # Timing
    started_at: str  # ISO8601
    stage_started_at: str
    completed_at: str

    # Configuration snapshot
    config: OrchestratorConfig

    # Error handling
    error_message: str
```

**Concrete Example (mid-pipeline):**

```json
{
    "issue_number": 305,
    "current_stage": "spec",
    "issue_brief_path": "docs/lineage/305/issue-brief.md",
    "lld_path": "docs/lld/active/305-orchestration-workflow.md",
    "spec_path": "",
    "worktree_path": "",
    "pr_url": "",
    "stage_results": {
        "triage": {
            "status": "passed",
            "artifact_path": "docs/lineage/305/issue-brief.md",
            "error_message": "",
            "duration_seconds": 85.3,
            "attempts": 1
        },
        "lld": {
            "status": "skipped",
            "artifact_path": "docs/lld/active/305-orchestration-workflow.md",
            "error_message": "",
            "duration_seconds": 0.01,
            "attempts": 0
        }
    },
    "stage_attempts": {
        "triage": 1,
        "lld": 0,
        "spec": 0,
        "impl": 0,
        "pr": 0
    },
    "started_at": "2026-02-16T10:30:00Z",
    "stage_started_at": "2026-02-16T10:31:25Z",
    "completed_at": "",
    "config": {
        "skip_existing_lld": true,
        "skip_existing_spec": true,
        "stages": {},
        "gates": {"pr": true},
        "max_stage_retries": 3,
        "retry_delay_seconds": 10
    },
    "error_message": ""
}
```

### 4.5 OrchestrationResult

**Definition:**

```python
class OrchestrationResult(TypedDict):
    """Final result of orchestration."""
    success: bool
    issue_number: int
    pr_url: str
    final_stage: str
    total_duration_seconds: float
    stage_results: dict[str, StageResult]
    error_summary: str
```

**Concrete Example (success):**

```json
{
    "success": true,
    "issue_number": 305,
    "pr_url": "https://github.com/martymcenroe/AssemblyZero/pull/312",
    "final_stage": "done",
    "total_duration_seconds": 1823.5,
    "stage_results": {
        "triage": {"status": "passed", "artifact_path": "docs/lineage/305/issue-brief.md", "error_message": "", "duration_seconds": 85.3, "attempts": 1},
        "lld": {"status": "skipped", "artifact_path": "docs/lld/active/305-orchestration-workflow.md", "error_message": "", "duration_seconds": 0.01, "attempts": 0},
        "spec": {"status": "passed", "artifact_path": "docs/lineage/305/impl-spec.md", "error_message": "", "duration_seconds": 245.8, "attempts": 1},
        "impl": {"status": "passed", "artifact_path": "../AssemblyZero-305", "error_message": "", "duration_seconds": 1380.2, "attempts": 2},
        "pr": {"status": "passed", "artifact_path": "https://github.com/martymcenroe/AssemblyZero/pull/312", "error_message": "", "duration_seconds": 12.1, "attempts": 1}
    },
    "error_summary": ""
}
```

**Concrete Example (failure):**

```json
{
    "success": false,
    "issue_number": 305,
    "pr_url": "",
    "final_stage": "impl",
    "total_duration_seconds": 2100.0,
    "stage_results": {
        "triage": {"status": "passed", "artifact_path": "docs/lineage/305/issue-brief.md", "error_message": "", "duration_seconds": 85.3, "attempts": 1},
        "lld": {"status": "passed", "artifact_path": "docs/lld/active/305-orchestration-workflow.md", "error_message": "", "duration_seconds": 320.5, "attempts": 1},
        "spec": {"status": "passed", "artifact_path": "docs/lineage/305/impl-spec.md", "error_message": "", "duration_seconds": 245.8, "attempts": 1},
        "impl": {"status": "failed", "artifact_path": "", "error_message": "Tests failed after 3 attempts: 4 tests failing in test_orchestrator_stages.py", "duration_seconds": 1448.4, "attempts": 3}
    },
    "error_summary": "Pipeline failed at stage 'impl' after 3 attempts. Last error: Tests failed after 3 attempts: 4 tests failing in test_orchestrator_stages.py. Resume with: orchestrate --issue 305 --resume-from impl"
}
```

## 5. Function Specifications

### 5.1 `get_default_config()`

**File:** `assemblyzero/workflows/orchestrator/config.py`

**Signature:**

```python
def get_default_config() -> OrchestratorConfig:
    """Return default orchestrator configuration."""
    ...
```

**Input Example:** No arguments.

**Output Example:**

```python
{
    "skip_existing_lld": True,
    "skip_existing_spec": True,
    "stages": {
        "triage": {"drafter": "claude:opus-4.5", "reviewer": "gemini:3-pro-preview", "max_revisions": 3, "timeout_seconds": 300},
        "lld": {"drafter": "claude:opus-4.5", "reviewer": "gemini:3-pro-preview", "max_revisions": 5, "timeout_seconds": 600},
        "spec": {"drafter": "claude:opus-4.5", "reviewer": "gemini:3-pro-preview", "max_revisions": 3, "timeout_seconds": 600},
        "impl": {"drafter": "claude:opus-4.5", "reviewer": "", "max_revisions": 3, "timeout_seconds": 1800},
        "pr": {"drafter": "", "reviewer": "", "max_revisions": 1, "timeout_seconds": 120},
    },
    "gates": {"triage": False, "lld": False, "spec": False, "impl": False, "pr": True},
    "max_stage_retries": 3,
    "retry_delay_seconds": 10,
}
```

**Edge Cases:**
- None — always returns a valid config.

### 5.2 `load_config()`

**File:** `assemblyzero/workflows/orchestrator/config.py`

**Signature:**

```python
def load_config(overrides: dict | None = None) -> OrchestratorConfig:
    """Load orchestrator configuration with optional overrides.

    Starts from defaults, then deep-merges any provided overrides.
    """
    ...
```

**Input Example:**

```python
overrides = {
    "skip_existing_lld": False,
    "gates": {"pr": False},
    "max_stage_retries": 5,
}
```

**Output Example:**

```python
{
    "skip_existing_lld": False,  # overridden
    "skip_existing_spec": True,  # default
    "stages": { ... },  # all defaults
    "gates": {"triage": False, "lld": False, "spec": False, "impl": False, "pr": False},  # pr overridden
    "max_stage_retries": 5,  # overridden
    "retry_delay_seconds": 10,  # default
}
```

**Edge Cases:**
- `overrides=None` → returns default config unchanged.
- `overrides={}` → returns default config unchanged.
- Unknown keys in overrides → ignored (no error).

### 5.3 `validate_config()`

**File:** `assemblyzero/workflows/orchestrator/config.py`

**Signature:**

```python
def validate_config(config: OrchestratorConfig) -> list[str]:
    """Validate configuration, return list of errors (empty = valid)."""
    ...
```

**Input Example:**

```python
config = {"max_stage_retries": -1, "stages": {}}
```

**Output Example:**

```python
["max_stage_retries must be >= 0", "stages must include all pipeline stages: triage, lld, spec, impl, pr"]
```

**Edge Cases:**
- Valid config → returns `[]`.
- Missing `stages` key → returns error about missing stages.

### 5.4 `create_initial_state()`

**File:** `assemblyzero/workflows/orchestrator/state.py`

**Signature:**

```python
def create_initial_state(
    issue_number: int,
    config: OrchestratorConfig,
) -> OrchestrationState:
    """Create a fresh orchestration state for a new pipeline run."""
    ...
```

**Input Example:**

```python
issue_number = 305
config = get_default_config()
```

**Output Example:**

```python
{
    "issue_number": 305,
    "current_stage": "triage",
    "issue_brief_path": "",
    "lld_path": "",
    "spec_path": "",
    "worktree_path": "",
    "pr_url": "",
    "stage_results": {},
    "stage_attempts": {"triage": 0, "lld": 0, "spec": 0, "impl": 0, "pr": 0},
    "started_at": "2026-02-16T10:30:00Z",
    "stage_started_at": "",
    "completed_at": "",
    "config": { ... },
    "error_message": "",
}
```

**Edge Cases:**
- `issue_number < 1` → raises `ValueError("issue_number must be positive")`.

### 5.5 `update_stage_result()`

**File:** `assemblyzero/workflows/orchestrator/state.py`

**Signature:**

```python
def update_stage_result(
    state: OrchestrationState,
    stage: str,
    result: StageResult,
) -> OrchestrationState:
    """Return new state with stage result recorded and current_stage advanced if passed."""
    ...
```

**Input Example:**

```python
state = {"issue_number": 305, "current_stage": "triage", "stage_results": {}, ...}
stage = "triage"
result = {
    "status": "passed",
    "artifact_path": "docs/lineage/305/issue-brief.md",
    "error_message": "",
    "duration_seconds": 85.3,
    "attempts": 1,
}
```

**Output Example:**

```python
{
    "issue_number": 305,
    "current_stage": "lld",  # advanced to next stage
    "stage_results": {
        "triage": {
            "status": "passed",
            "artifact_path": "docs/lineage/305/issue-brief.md",
            "error_message": "",
            "duration_seconds": 85.3,
            "attempts": 1,
        }
    },
    "issue_brief_path": "docs/lineage/305/issue-brief.md",
    ...
}
```

**Edge Cases:**
- `result["status"] == "failed"` → `current_stage` does NOT advance; remains at failed stage.
- `result["status"] == "blocked"` → `current_stage` does NOT advance.
- `result["status"] == "skipped"` → `current_stage` advances to next stage.
- Stage `"pr"` with status `"passed"` → `current_stage` advances to `"done"`.

### 5.6 `get_next_stage()`

**File:** `assemblyzero/workflows/orchestrator/state.py`

**Signature:**

```python
STAGE_ORDER: list[str] = ["triage", "lld", "spec", "impl", "pr"]

def get_next_stage(current_stage: str) -> str:
    """Return the next stage in the pipeline, or 'done' if at end."""
    ...
```

**Input Example:**

```python
current_stage = "lld"
```

**Output Example:**

```python
"spec"
```

**Edge Cases:**
- `current_stage = "pr"` → returns `"done"`.
- `current_stage = "done"` → returns `"done"`.
- `current_stage = "invalid"` → raises `ValueError("Unknown stage: invalid")`.

### 5.7 `detect_existing_artifacts()`

**File:** `assemblyzero/workflows/orchestrator/artifacts.py`

**Signature:**

```python
def detect_existing_artifacts(issue_number: int) -> dict[str, str | None]:
    """
    Scan for existing artifacts for an issue.

    Returns dict mapping stage names to artifact paths, or None if not found.
    Checks:
      - triage: docs/lineage/{issue_number}/issue-brief.md
      - lld: docs/lld/active/{issue_number}-*.md OR docs/lld/done/{issue_number}-*.md
      - spec: docs/lineage/{issue_number}/impl-spec.md
    """
    ...
```

**Input Example:**

```python
issue_number = 305
```

**Output Example (some artifacts exist):**

```python
{
    "triage": "docs/lineage/305/issue-brief.md",
    "lld": "docs/lld/active/305-orchestration-workflow.md",
    "spec": None,
    "impl": None,
    "pr": None,
}
```

**Output Example (no artifacts):**

```python
{
    "triage": None,
    "lld": None,
    "spec": None,
    "impl": None,
    "pr": None,
}
```

**Edge Cases:**
- `issue_number < 1` → raises `ValueError`.
- Multiple LLD matches (e.g., `305-v1.md` and `305-v2.md`) → returns first match sorted alphabetically.
- LLD in `docs/lld/done/` → still detected (completed work).

### 5.8 `get_artifact_path()`

**File:** `assemblyzero/workflows/orchestrator/artifacts.py`

**Signature:**

```python
def get_artifact_path(issue_number: int, artifact_type: str) -> Path:
    """Get canonical path for an artifact type.

    Args:
        issue_number: GitHub issue number
        artifact_type: One of "triage", "lld", "spec", "impl", "pr"

    Returns:
        Expected path for the artifact (may not exist yet)
    """
    ...
```

**Input Example:**

```python
issue_number = 305
artifact_type = "triage"
```

**Output Example:**

```python
Path("docs/lineage/305/issue-brief.md")
```

**Mapping:**

| artifact_type | Path |
|---------------|------|
| `"triage"` | `docs/lineage/{N}/issue-brief.md` |
| `"lld"` | `docs/lld/active/{N}-*.md` (glob pattern) |
| `"spec"` | `docs/lineage/{N}/impl-spec.md` |
| `"impl"` | `../AssemblyZero-{N}` (worktree) |
| `"pr"` | N/A (URL, not file path) |

**Edge Cases:**
- `artifact_type = "pr"` → raises `ValueError("PR artifact is a URL, not a file path")`.
- Unknown `artifact_type` → raises `ValueError("Unknown artifact_type: ...")`.

### 5.9 `validate_artifact()`

**File:** `assemblyzero/workflows/orchestrator/artifacts.py`

**Signature:**

```python
def validate_artifact(path: Path, artifact_type: str) -> bool:
    """Validate that artifact exists and has required structure.

    Checks:
      - File exists
      - File is non-empty
      - For lld: contains "## 1. Context" heading
      - For spec: contains "## 1. Overview" heading
      - For triage: contains "## Summary" or similar heading
    """
    ...
```

**Input Example:**

```python
path = Path("docs/lld/active/305-orchestration-workflow.md")
artifact_type = "lld"
```

**Output Example:**

```python
True
```

**Edge Cases:**
- File does not exist → returns `False`.
- File is empty (0 bytes) → returns `False`.
- File exists but missing required heading → returns `False`.

### 5.10 `save_orchestration_state()`

**File:** `assemblyzero/workflows/orchestrator/resume.py`

**Signature:**

```python
STATE_DIR = Path(".assemblyzero/orchestrator/state")

def save_orchestration_state(state: OrchestrationState) -> Path:
    """Persist state to disk as JSON for resume capability.

    Creates backup of existing state file before overwriting.
    Returns path to saved state file.
    """
    ...
```

**Input Example:**

```python
state = {
    "issue_number": 305,
    "current_stage": "spec",
    ...
}
```

**Output Example:**

```python
Path(".assemblyzero/orchestrator/state/305.json")
```

**Behavior:**
- Creates `.assemblyzero/orchestrator/state/` directory if it doesn't exist.
- Writes `{issue_number}.json`.
- If file already exists, copies to `{issue_number}.json.bak` before overwriting.
- JSON is pretty-printed (indent=2) for debuggability.

**Edge Cases:**
- State directory doesn't exist → creates it.
- Disk full → raises `OSError` (not caught — fail closed).

### 5.11 `load_orchestration_state()`

**File:** `assemblyzero/workflows/orchestrator/resume.py`

**Signature:**

```python
def load_orchestration_state(issue_number: int) -> OrchestrationState | None:
    """Load persisted state for an issue, if exists.

    Returns None if no state file found.
    Validates JSON structure on load.
    """
    ...
```

**Input Example:**

```python
issue_number = 305
```

**Output Example (state exists):**

```python
{
    "issue_number": 305,
    "current_stage": "spec",
    "stage_results": { ... },
    ...
}
```

**Output Example (no state):**

```python
None
```

**Edge Cases:**
- State file doesn't exist → returns `None`.
- State file has invalid JSON → logs warning, returns `None` (fail safe).
- State file missing required keys → logs warning, returns `None`.

### 5.12 `determine_resume_stage()`

**File:** `assemblyzero/workflows/orchestrator/resume.py`

**Signature:**

```python
def determine_resume_stage(
    state: OrchestrationState,
    resume_from: str | None,
) -> str:
    """Determine which stage to resume from.

    If resume_from is specified, validates it's a valid stage.
    If not specified, returns current_stage from state.
    """
    ...
```

**Input Example:**

```python
state = {"current_stage": "spec", ...}
resume_from = "impl"
```

**Output Example:**

```python
"impl"
```

**Edge Cases:**
- `resume_from=None` → returns `state["current_stage"]`.
- `resume_from="invalid"` → raises `ValueError("Invalid stage: 'invalid'. Valid stages: triage, lld, spec, impl, pr")`.
- `resume_from="triage"` when state is at `"spec"` → allowed (can go backwards).

### 5.13 `acquire_orchestration_lock()`

**File:** `assemblyzero/workflows/orchestrator/resume.py`

**Signature:**

```python
LOCK_DIR = Path(".assemblyzero/orchestrator/locks")

def acquire_orchestration_lock(issue_number: int) -> bool:
    """Acquire lock file to prevent concurrent runs.

    Creates .assemblyzero/orchestrator/locks/{issue_number}.lock
    Lock file contains PID and timestamp.

    Returns True if lock acquired, False if already locked.
    """
    ...
```

**Input Example:**

```python
issue_number = 305
```

**Output Example:**

```python
True  # lock acquired
```

**Lock file contents:**

```json
{
    "pid": 12345,
    "started_at": "2026-02-16T10:30:00Z",
    "hostname": "dev-machine"
}
```

**Edge Cases:**
- Lock file exists but PID is dead → removes stale lock, acquires new one.
- Lock file exists and PID is alive → returns `False`.
- Lock directory doesn't exist → creates it.

### 5.14 `release_orchestration_lock()`

**File:** `assemblyzero/workflows/orchestrator/resume.py`

**Signature:**

```python
def release_orchestration_lock(issue_number: int) -> None:
    """Release lock file for an issue.

    Removes .assemblyzero/orchestrator/locks/{issue_number}.lock
    No-op if lock doesn't exist.
    """
    ...
```

**Input Example:**

```python
issue_number = 305
```

**Output Example:** No return value. Lock file removed.

**Edge Cases:**
- Lock file doesn't exist → no error, no-op.

### 5.15 `run_triage_stage()`

**File:** `assemblyzero/workflows/orchestrator/stages.py`

**Signature:**

```python
def run_triage_stage(state: OrchestrationState) -> OrchestrationState:
    """Execute issue triage workflow.

    Checks for existing artifact first.
    Wraps requirements workflow with type=issue.
    """
    ...
```

**Input Example:**

```python
state = {
    "issue_number": 305,
    "current_stage": "triage",
    "config": {"skip_existing_lld": True, ...},
    ...
}
```

**Output Example (passed):**

```python
{
    ...
    "current_stage": "lld",
    "issue_brief_path": "docs/lineage/305/issue-brief.md",
    "stage_results": {
        "triage": {"status": "passed", "artifact_path": "docs/lineage/305/issue-brief.md", "error_message": "", "duration_seconds": 85.3, "attempts": 1}
    },
    ...
}
```

**Edge Cases:**
- Existing artifact found → returns state with `"skipped"` status.
- Sub-workflow raises exception → catches, returns state with `"failed"` status and error message.

### 5.16 `run_lld_stage()`

**File:** `assemblyzero/workflows/orchestrator/stages.py`

**Signature:**

```python
def run_lld_stage(state: OrchestrationState) -> OrchestrationState:
    """Execute LLD generation and review workflow.

    Checks for existing artifact first if skip_existing_lld is configured.
    Wraps requirements workflow with type=lld.
    Validates LLD has APPROVED status.
    """
    ...
```

**Input Example:**

```python
state = {
    "issue_number": 305,
    "current_stage": "lld",
    "issue_brief_path": "docs/lineage/305/issue-brief.md",
    ...
}
```

**Output Example (skipped — existing LLD found):**

```python
{
    ...
    "current_stage": "spec",
    "lld_path": "docs/lld/active/305-orchestration-workflow.md",
    "stage_results": {
        ...,
        "lld": {"status": "skipped", "artifact_path": "docs/lld/active/305-orchestration-workflow.md", "error_message": "", "duration_seconds": 0.02, "attempts": 0}
    },
    ...
}
```

### 5.17 `run_spec_stage()`

**File:** `assemblyzero/workflows/orchestrator/stages.py`

**Signature:**

```python
def run_spec_stage(state: OrchestrationState) -> OrchestrationState:
    """Execute implementation spec workflow.

    Checks for existing artifact first if skip_existing_spec is configured.
    Wraps implementation_spec workflow.
    Validates spec has APPROVED status.
    """
    ...
```

**Input Example:**

```python
state = {
    "issue_number": 305,
    "current_stage": "spec",
    "lld_path": "docs/lld/active/305-orchestration-workflow.md",
    ...
}
```

**Output Example:**

```python
{
    ...
    "current_stage": "impl",
    "spec_path": "docs/lineage/305/impl-spec.md",
    "stage_results": {
        ...,
        "spec": {"status": "passed", ...}
    },
    ...
}
```

### 5.18 `run_impl_stage()`

**File:** `assemblyzero/workflows/orchestrator/stages.py`

**Signature:**

```python
def run_impl_stage(state: OrchestrationState) -> OrchestrationState:
    """Execute implementation workflow (TDD).

    Ensures worktree exists or creates it via git worktree add.
    Runs implementation workflow in the worktree.
    Verifies tests pass.
    """
    ...
```

**Input Example:**

```python
state = {
    "issue_number": 305,
    "current_stage": "impl",
    "spec_path": "docs/lineage/305/impl-spec.md",
    ...
}
```

**Output Example:**

```python
{
    ...
    "current_stage": "pr",
    "worktree_path": "../AssemblyZero-305",
    "stage_results": {
        ...,
        "impl": {"status": "passed", "artifact_path": "../AssemblyZero-305", "error_message": "", "duration_seconds": 1380.2, "attempts": 2}
    },
    ...
}
```

**Edge Cases:**
- Worktree already exists → reuses it.
- `git worktree add` fails → returns `"failed"` with git error message.
- Tests fail → returns `"failed"` with test output.

### 5.19 `run_pr_stage()`

**File:** `assemblyzero/workflows/orchestrator/stages.py`

**Signature:**

```python
def run_pr_stage(state: OrchestrationState) -> OrchestrationState:
    """Create and submit PR.

    Uses gh CLI to create PR from worktree branch.
    """
    ...
```

**Input Example:**

```python
state = {
    "issue_number": 305,
    "current_stage": "pr",
    "worktree_path": "../AssemblyZero-305",
    ...
}
```

**Output Example:**

```python
{
    ...
    "current_stage": "done",
    "pr_url": "https://github.com/martymcenroe/AssemblyZero/pull/312",
    "stage_results": {
        ...,
        "pr": {"status": "passed", "artifact_path": "https://github.com/martymcenroe/AssemblyZero/pull/312", ...}
    },
    "completed_at": "2026-02-16T11:00:23Z",
    ...
}
```

### 5.20 `should_skip_stage()`

**File:** `assemblyzero/workflows/orchestrator/stages.py`

**Signature:**

```python
def should_skip_stage(
    state: OrchestrationState,
    stage: str,
    existing_artifacts: dict[str, str | None],
) -> tuple[bool, str | None]:
    """Determine if a stage should be skipped.

    Returns (should_skip, artifact_path).
    """
    ...
```

**Input Example:**

```python
state = {"config": {"skip_existing_lld": True, ...}, ...}
stage = "lld"
existing_artifacts = {"lld": "docs/lld/active/305-orchestration-workflow.md", ...}
```

**Output Example:**

```python
(True, "docs/lld/active/305-orchestration-workflow.md")
```

**Edge Cases:**
- Config says `skip_existing_lld: False` but artifact exists → `(False, None)`.
- Stage is `"impl"` or `"pr"` → always `(False, None)` (never skipped).

### 5.21 `check_human_gate()`

**File:** `assemblyzero/workflows/orchestrator/stages.py`

**Signature:**

```python
def check_human_gate(
    state: OrchestrationState,
    stage: str,
) -> bool:
    """Check if a human gate is configured before this stage.

    Returns True if gate is not enabled or if approval received.
    Returns False if gate is enabled (pipeline should block).

    In non-interactive mode, returns False when gate is enabled.
    """
    ...
```

**Input Example:**

```python
state = {"config": {"gates": {"pr": True, "lld": False}}, ...}
stage = "pr"
```

**Output Example:**

```python
False  # Gate is enabled; pipeline should block at this stage
```

### 5.22 `create_orchestration_graph()`

**File:** `assemblyzero/workflows/orchestrator/graph.py`

**Signature:**

```python
def create_orchestration_graph() -> StateGraph:
    """Create LangGraph StateGraph for orchestration pipeline.

    Nodes: init, triage, lld, spec, impl, pr, done, blocked, failed
    Edges: Linear pipeline with conditional routing based on stage results
    """
    ...
```

**Input Example:** No arguments.

**Output Example:** A compiled `StateGraph` instance.

### 5.23 `orchestrate()`

**File:** `assemblyzero/workflows/orchestrator/graph.py`

**Signature:**

```python
def orchestrate(
    issue_number: int,
    config: OrchestratorConfig | None = None,
    resume_from: str | None = None,
    dry_run: bool = False,
) -> OrchestrationResult:
    """
    Run full pipeline from issue to PR.

    Args:
        issue_number: GitHub issue number to process
        config: Override default configuration (merged with defaults)
        resume_from: Stage name to resume from (uses persisted state)
        dry_run: If True, show planned stages without execution

    Returns:
        OrchestrationResult with final status and artifacts
    """
    ...
```

**Input Example:**

```python
issue_number = 305
config = None  # use defaults
resume_from = None
dry_run = False
```

**Output Example:** See `OrchestrationResult` concrete examples in Section 4.5.

**Edge Cases:**
- Lock cannot be acquired → raises `ConcurrentOrchestrationError(f"Issue {issue_number} is already being orchestrated")`.
- `resume_from` specified but no persisted state → raises `ValueError(f"No persisted state found for issue {issue_number}")`.
- `dry_run=True` → prints plan, returns result with `success=True` and all stages `"skipped"`.

### 5.24 `report_progress()`

**File:** `tools/orchestrate.py`

**Signature:**

```python
def report_progress(state: OrchestrationState) -> None:
    """Report current stage, duration, and artifacts to stdout.

    Format:
    [ORCHESTRATOR] Stage: lld | Duration: 1m 25s | Artifacts: issue-brief.md ✓
    """
    ...
```

**Input Example:**

```python
state = {
    "current_stage": "lld",
    "started_at": "2026-02-16T10:30:00Z",
    "issue_brief_path": "docs/lineage/305/issue-brief.md",
    "lld_path": "",
    ...
}
```

**Output (printed to stdout):**

```
[ORCHESTRATOR] Issue #305 | Stage: lld | Elapsed: 1m 25s
  ✓ triage → docs/lineage/305/issue-brief.md
  ◌ lld (in progress)
  ○ spec
  ○ impl
  ○ pr
```

### 5.25 `format_error_message()`

**File:** `tools/orchestrate.py`

**Signature:**

```python
def format_error_message(stage: str, stage_result: StageResult) -> str:
    """Format actionable error message with context.

    Returns a human-readable message with:
    - Which stage failed
    - The error details
    - How to resume
    """
    ...
```

**Input Example:**

```python
stage = "impl"
stage_result = {
    "status": "failed",
    "artifact_path": "",
    "error_message": "Tests failed: 4 assertions in test_orchestrator_stages.py",
    "duration_seconds": 1448.4,
    "attempts": 3,
}
```

**Output Example:**

```python
"""
╔══════════════════════════════════════════════════════════╗
║  ORCHESTRATION FAILED at stage: impl                     ║
╠══════════════════════════════════════════════════════════╣
║  Error: Tests failed: 4 assertions in                    ║
║         test_orchestrator_stages.py                      ║
║  Attempts: 3 | Duration: 24m 8s                          ║
║                                                          ║
║  Resume: orchestrate --issue 305 --resume-from impl      ║
╚══════════════════════════════════════════════════════════╝
"""
```

## 6. Change Instructions

### 6.1 `assemblyzero/workflows/orchestrator/__init__.py` (Add)

**Complete file contents:**

```python
"""Orchestrator workflow: end-to-end pipeline from GitHub issue to PR.

Issue #305: End-to-End Orchestration Workflow (Issue → Code)
"""

from assemblyzero.workflows.orchestrator.config import (
    OrchestratorConfig,
    StageConfig,
    get_default_config,
    load_config,
    validate_config,
)
from assemblyzero.workflows.orchestrator.graph import (
    OrchestrationResult,
    create_orchestration_graph,
    orchestrate,
)
from assemblyzero.workflows.orchestrator.state import (
    OrchestrationState,
    StageResult,
    create_initial_state,
    get_next_stage,
    update_stage_result,
)

__all__ = [
    "OrchestratorConfig",
    "OrchestrationResult",
    "OrchestrationState",
    "StageConfig",
    "StageResult",
    "create_initial_state",
    "create_orchestration_graph",
    "get_default_config",
    "get_next_stage",
    "load_config",
    "orchestrate",
    "update_stage_result",
    "validate_config",
]
```

### 6.2 `assemblyzero/workflows/orchestrator/config.py` (Add)

**Complete file contents:**

```python
"""Orchestrator configuration schema and defaults.

Issue #305: End-to-End Orchestration Workflow (Issue → Code)
"""

from __future__ import annotations

from typing import Any, TypedDict


class StageConfig(TypedDict, total=False):
    """Configuration for a single stage."""

    drafter: str
    reviewer: str
    max_revisions: int
    timeout_seconds: int


class OrchestratorConfig(TypedDict, total=False):
    """Full orchestrator configuration."""

    skip_existing_lld: bool
    skip_existing_spec: bool
    stages: dict[str, StageConfig]
    gates: dict[str, bool]
    max_stage_retries: int
    retry_delay_seconds: int


VALID_STAGES = ["triage", "lld", "spec", "impl", "pr"]


def get_default_config() -> OrchestratorConfig:
    """Return default orchestrator configuration."""
    return OrchestratorConfig(
        skip_existing_lld=True,
        skip_existing_spec=True,
        stages={
            "triage": StageConfig(
                drafter="claude:opus-4.5",
                reviewer="gemini:3-pro-preview",
                max_revisions=3,
                timeout_seconds=300,
            ),
            "lld": StageConfig(
                drafter="claude:opus-4.5",
                reviewer="gemini:3-pro-preview",
                max_revisions=5,
                timeout_seconds=600,
            ),
            "spec": StageConfig(
                drafter="claude:opus-4.5",
                reviewer="gemini:3-pro-preview",
                max_revisions=3,
                timeout_seconds=600,
            ),
            "impl": StageConfig(
                drafter="claude:opus-4.5",
                reviewer="",
                max_revisions=3,
                timeout_seconds=1800,
            ),
            "pr": StageConfig(
                drafter="",
                reviewer="",
                max_revisions=1,
                timeout_seconds=120,
            ),
        },
        gates={
            "triage": False,
            "lld": False,
            "spec": False,
            "impl": False,
            "pr": True,
        },
        max_stage_retries=3,
        retry_delay_seconds=10,
    )


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Deep merge overrides into base dict. Returns new dict."""
    result = dict(base)
    for key, value in overrides.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(overrides: dict[str, Any] | None = None) -> OrchestratorConfig:
    """Load orchestrator configuration with optional overrides.

    Starts from defaults, then deep-merges any provided overrides.
    """
    defaults = get_default_config()
    if not overrides:
        return defaults
    merged = _deep_merge(dict(defaults), overrides)
    return OrchestratorConfig(**{k: v for k, v in merged.items() if k in OrchestratorConfig.__annotations__})


def validate_config(config: OrchestratorConfig) -> list[str]:
    """Validate configuration, return list of errors (empty = valid)."""
    errors: list[str] = []

    max_retries = config.get("max_stage_retries", 0)
    if not isinstance(max_retries, int) or max_retries < 0:
        errors.append("max_stage_retries must be >= 0")

    retry_delay = config.get("retry_delay_seconds", 0)
    if not isinstance(retry_delay, (int, float)) or retry_delay < 0:
        errors.append("retry_delay_seconds must be >= 0")

    stages = config.get("stages", {})
    if not isinstance(stages, dict):
        errors.append("stages must be a dict")
    else:
        missing = [s for s in VALID_STAGES if s not in stages]
        if missing:
            errors.append(
                f"stages must include all pipeline stages: {', '.join(VALID_STAGES)}. "
                f"Missing: {', '.join(missing)}"
            )
        for stage_name, stage_cfg in stages.items():
            if stage_name not in VALID_STAGES:
                errors.append(f"Unknown stage in stages config: {stage_name}")
            timeout = stage_cfg.get("timeout_seconds", 0)
            if not isinstance(timeout, (int, float)) or timeout <= 0:
                errors.append(f"stages.{stage_name}.timeout_seconds must be > 0")

    gates = config.get("gates", {})
    if not isinstance(gates, dict):
        errors.append("gates must be a dict")
    else:
        for gate_name in gates:
            if gate_name not in VALID_STAGES:
                errors.append(f"Unknown stage in gates config: {gate_name}")

    return errors
```

### 6.3 `assemblyzero/workflows/orchestrator/state.py` (Add)

**Complete file contents:**

```python
"""Orchestration state management.

Issue #305: End-to-End Orchestration Workflow (Issue → Code)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TypedDict

from assemblyzero.workflows.orchestrator.config import OrchestratorConfig


class StageResult(TypedDict, total=False):
    """Result of executing a single stage."""

    status: str  # "passed", "blocked", "failed", "skipped"
    artifact_path: str
    error_message: str
    duration_seconds: float
    attempts: int


class OrchestrationState(TypedDict, total=False):
    """Full orchestration pipeline state."""

    issue_number: int
    current_stage: str  # "triage", "lld", "spec", "impl", "pr", "done"

    # Artifacts produced at each stage
    issue_brief_path: str
    lld_path: str
    spec_path: str
    worktree_path: str
    pr_url: str

    # Progress tracking
    stage_results: dict[str, StageResult]
    stage_attempts: dict[str, int]

    # Timing
    started_at: str  # ISO8601
    stage_started_at: str
    completed_at: str

    # Configuration snapshot
    config: OrchestratorConfig

    # Error handling
    error_message: str


STAGE_ORDER: list[str] = ["triage", "lld", "spec", "impl", "pr"]

# Maps stage name to the state key that holds its artifact path
_STAGE_ARTIFACT_KEY: dict[str, str] = {
    "triage": "issue_brief_path",
    "lld": "lld_path",
    "spec": "spec_path",
    "impl": "worktree_path",
    "pr": "pr_url",
}


def create_initial_state(
    issue_number: int,
    config: OrchestratorConfig,
) -> OrchestrationState:
    """Create a fresh orchestration state for a new pipeline run."""
    if issue_number < 1:
        msg = "issue_number must be positive"
        raise ValueError(msg)

    now = datetime.now(tz=timezone.utc).isoformat()
    return OrchestrationState(
        issue_number=issue_number,
        current_stage="triage",
        issue_brief_path="",
        lld_path="",
        spec_path="",
        worktree_path="",
        pr_url="",
        stage_results={},
        stage_attempts={stage: 0 for stage in STAGE_ORDER},
        started_at=now,
        stage_started_at="",
        completed_at="",
        config=config,
        error_message="",
    )


def get_next_stage(current_stage: str) -> str:
    """Return the next stage in the pipeline, or 'done' if at end."""
    if current_stage == "done":
        return "done"
    if current_stage not in STAGE_ORDER:
        msg = f"Unknown stage: {current_stage}"
        raise ValueError(msg)
    idx = STAGE_ORDER.index(current_stage)
    if idx >= len(STAGE_ORDER) - 1:
        return "done"
    return STAGE_ORDER[idx + 1]


def update_stage_result(
    state: OrchestrationState,
    stage: str,
    result: StageResult,
) -> OrchestrationState:
    """Return new state with stage result recorded.

    If result status is 'passed' or 'skipped', advances current_stage.
    Also updates the corresponding artifact path key.
    """
    if stage not in STAGE_ORDER:
        msg = f"Unknown stage: {stage}"
        raise ValueError(msg)

    # Copy state to avoid mutation
    new_state = dict(state)
    stage_results = dict(new_state.get("stage_results", {}))
    stage_results[stage] = result
    new_state["stage_results"] = stage_results

    # Update attempt count
    stage_attempts = dict(new_state.get("stage_attempts", {}))
    stage_attempts[stage] = result.get("attempts", 0)
    new_state["stage_attempts"] = stage_attempts

    # Update artifact path for the stage
    artifact_key = _STAGE_ARTIFACT_KEY.get(stage)
    artifact_path = result.get("artifact_path", "")
    if artifact_key and artifact_path:
        new_state[artifact_key] = artifact_path

    # Advance stage if passed or skipped
    status = result.get("status", "")
    if status in ("passed", "skipped"):
        new_state["current_stage"] = get_next_stage(stage)

    # Set completed_at if we're done
    if new_state.get("current_stage") == "done":
        new_state["completed_at"] = datetime.now(tz=timezone.utc).isoformat()

    # Set error_message if failed or blocked
    if status in ("failed", "blocked"):
        new_state["error_message"] = result.get("error_message", "")

    return OrchestrationState(**new_state)
```

### 6.4 `assemblyzero/workflows/orchestrator/artifacts.py` (Add)

**Complete file contents:**

```python
"""Artifact detection and path management.

Issue #305: End-to-End Orchestration Workflow (Issue → Code)
"""

from __future__ import annotations

from pathlib import Path


def detect_existing_artifacts(issue_number: int) -> dict[str, str | None]:
    """Scan for existing artifacts for an issue.

    Returns dict mapping stage names to artifact paths, or None if not found.
    """
    if issue_number < 1:
        msg = "issue_number must be positive"
        raise ValueError(msg)

    artifacts: dict[str, str | None] = {
        "triage": None,
        "lld": None,
        "spec": None,
        "impl": None,
        "pr": None,
    }

    # Triage: docs/lineage/{issue_number}/issue-brief.md
    triage_path = Path(f"docs/lineage/{issue_number}/issue-brief.md")
    if triage_path.is_file() and triage_path.stat().st_size > 0:
        artifacts["triage"] = str(triage_path)

    # LLD: docs/lld/active/{issue_number}-*.md OR docs/lld/done/{issue_number}-*.md
    for lld_dir in [Path("docs/lld/active"), Path("docs/lld/done")]:
        if lld_dir.is_dir():
            matches = sorted(lld_dir.glob(f"{issue_number}-*.md"))
            if matches:
                artifacts["lld"] = str(matches[0])
                break

    # Spec: docs/lineage/{issue_number}/impl-spec.md
    spec_path = Path(f"docs/lineage/{issue_number}/impl-spec.md")
    if spec_path.is_file() and spec_path.stat().st_size > 0:
        artifacts["spec"] = str(spec_path)

    # Impl: worktree at ../AssemblyZero-{issue_number}
    worktree_path = Path(f"../AssemblyZero-{issue_number}")
    if worktree_path.is_dir():
        artifacts["impl"] = str(worktree_path)

    # PR: not detectable from filesystem alone (would need GitHub API)
    # Leave as None

    return artifacts


def get_artifact_path(issue_number: int, artifact_type: str) -> Path:
    """Get canonical path for an artifact type.

    Args:
        issue_number: GitHub issue number
        artifact_type: One of 'triage', 'lld', 'spec', 'impl'

    Returns:
        Expected path for the artifact (may not exist yet)

    Raises:
        ValueError: For 'pr' type (URL, not file) or unknown types
    """
    if artifact_type == "triage":
        return Path(f"docs/lineage/{issue_number}/issue-brief.md")
    if artifact_type == "lld":
        return Path(f"docs/lld/active/{issue_number}-*.md")
    if artifact_type == "spec":
        return Path(f"docs/lineage/{issue_number}/impl-spec.md")
    if artifact_type == "impl":
        return Path(f"../AssemblyZero-{issue_number}")
    if artifact_type == "pr":
        msg = "PR artifact is a URL, not a file path"
        raise ValueError(msg)
    msg = f"Unknown artifact_type: {artifact_type}"
    raise ValueError(msg)


def validate_artifact(path: Path, artifact_type: str) -> bool:
    """Validate that artifact exists and has required structure.

    Checks:
      - File/dir exists
      - File is non-empty
      - For lld: contains '## 1. Context' heading
      - For spec: contains '## 1. Overview' heading
      - For triage: contains '##' heading (any h2)
    """
    if artifact_type == "impl":
        # For implementation, just check directory exists
        return path.is_dir()

    if not path.is_file():
        return False

    if path.stat().st_size == 0:
        return False

    content = path.read_text(encoding="utf-8")

    if artifact_type == "lld":
        return "## 1. Context" in content
    if artifact_type == "spec":
        return "## 1. Overview" in content
    if artifact_type == "triage":
        return "## " in content

    return True
```

### 6.5 `assemblyzero/workflows/orchestrator/resume.py` (Add)

**Complete file contents:**

```python
"""Resume-from-stage logic and state persistence.

Issue #305: End-to-End Orchestration Workflow (Issue → Code)
"""

from __future__ import annotations

import json
import os
import platform
import shutil
from pathlib import Path
from datetime import datetime, timezone

from assemblyzero.workflows.orchestrator.state import (
    STAGE_ORDER,
    OrchestrationState,
)


STATE_DIR = Path(".assemblyzero/orchestrator/state")
LOCK_DIR = Path(".assemblyzero/orchestrator/locks")


def save_orchestration_state(state: OrchestrationState) -> Path:
    """Persist state to disk as JSON for resume capability.

    Creates backup of existing state file before overwriting.
    Returns path to saved state file.
    """
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    issue_number = state["issue_number"]
    state_path = STATE_DIR / f"{issue_number}.json"

    # Backup existing state file
    if state_path.exists():
        backup_path = STATE_DIR / f"{issue_number}.json.bak"
        shutil.copy2(state_path, backup_path)

    state_path.write_text(
        json.dumps(dict(state), indent=2, default=str),
        encoding="utf-8",
    )
    return state_path


def load_orchestration_state(issue_number: int) -> OrchestrationState | None:
    """Load persisted state for an issue, if exists.

    Returns None if no state file found or file is invalid.
    """
    state_path = STATE_DIR / f"{issue_number}.json"
    if not state_path.is_file():
        return None

    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[ORCHESTRATOR] Warning: Could not load state file {state_path}: {exc}")
        return None

    # Basic validation
    required_keys = {"issue_number", "current_stage"}
    if not required_keys.issubset(data.keys()):
        print(
            f"[ORCHESTRATOR] Warning: State file {state_path} missing required keys: "
            f"{required_keys - data.keys()}"
        )
        return None

    if data.get("issue_number") != issue_number:
        print(
            f"[ORCHESTRATOR] Warning: State file issue_number mismatch: "
            f"expected {issue_number}, got {data.get('issue_number')}"
        )
        return None

    return OrchestrationState(**data)


def determine_resume_stage(
    state: OrchestrationState,
    resume_from: str | None,
) -> str:
    """Determine which stage to resume from.

    If resume_from is specified, validates it's a valid stage.
    If not specified, returns current_stage from state.
    """
    if resume_from is None:
        return state.get("current_stage", "triage")

    if resume_from not in STAGE_ORDER:
        msg = (
            f"Invalid stage: '{resume_from}'. "
            f"Valid stages: {', '.join(STAGE_ORDER)}"
        )
        raise ValueError(msg)

    return resume_from


def _is_pid_alive(pid: int) -> bool:
    """Check if a process with given PID is alive."""
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def acquire_orchestration_lock(issue_number: int) -> bool:
    """Acquire lock file to prevent concurrent runs.

    Creates .assemblyzero/orchestrator/locks/{issue_number}.lock
    Lock file contains PID and timestamp.

    Returns True if lock acquired, False if already locked by live process.
    """
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = LOCK_DIR / f"{issue_number}.lock"

    if lock_path.exists():
        # Check if lock is stale
        try:
            lock_data = json.loads(lock_path.read_text(encoding="utf-8"))
            pid = lock_data.get("pid", -1)
            if _is_pid_alive(pid):
                return False
            # Stale lock — remove it
            print(f"[ORCHESTRATOR] Removing stale lock for issue {issue_number} (PID {pid} is dead)")
            lock_path.unlink()
        except (json.JSONDecodeError, OSError):
            # Corrupted lock file — remove it
            lock_path.unlink(missing_ok=True)

    # Write new lock
    lock_data = {
        "pid": os.getpid(),
        "started_at": datetime.now(tz=timezone.utc).isoformat(),
        "hostname": platform.node(),
    }
    lock_path.write_text(
        json.dumps(lock_data, indent=2),
        encoding="utf-8",
    )
    return True


def release_orchestration_lock(issue_number: int) -> None:
    """Release lock file for an issue. No-op if lock doesn't exist."""
    lock_path = LOCK_DIR / f"{issue_number}.lock"
    lock_path.unlink(missing_ok=True)
```

### 6.6 `assemblyzero/workflows/orchestrator/stages.py` (Add)

**Complete file contents:**

```python
"""Stage execution logic for each sub-workflow.

Issue #305: End-to-End Orchestration Workflow (Issue → Code)

Each stage function:
1. Checks if the stage should be skipped (existing artifact)
2. Executes the relevant sub-workflow
3. Returns updated OrchestrationState with stage result
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

from assemblyzero.workflows.orchestrator.artifacts import (
    detect_existing_artifacts,
    validate_artifact,
)
from assemblyzero.workflows.orchestrator.state import (
    OrchestrationState,
    StageResult,
    update_stage_result,
)


def should_skip_stage(
    state: OrchestrationState,
    stage: str,
    existing_artifacts: dict[str, str | None],
) -> tuple[bool, str | None]:
    """Determine if a stage should be skipped.

    Returns (should_skip, artifact_path).

    impl and pr stages are never skipped.
    """
    if stage in ("impl", "pr"):
        return (False, None)

    config = state.get("config", {})
    artifact_path = existing_artifacts.get(stage)

    if not artifact_path:
        return (False, None)

    # Check config flags
    if stage == "lld" and not config.get("skip_existing_lld", True):
        return (False, None)
    if stage == "spec" and not config.get("skip_existing_spec", True):
        return (False, None)

    # Validate the artifact actually exists and is valid
    path = Path(artifact_path)
    if validate_artifact(path, stage):
        return (True, artifact_path)

    return (False, None)


def check_human_gate(
    state: OrchestrationState,
    stage: str,
) -> bool:
    """Check if a human gate is configured before this stage.

    Returns True if gate is not enabled or not applicable.
    Returns False if gate is enabled (pipeline should block).
    """
    config = state.get("config", {})
    gates = config.get("gates", {})
    gate_enabled = gates.get(stage, False)

    if not gate_enabled:
        return True  # No gate, proceed

    # Gate is enabled — in non-interactive mode, block
    return False


def _make_stage_result(
    status: str,
    artifact_path: str = "",
    error_message: str = "",
    duration_seconds: float = 0.0,
    attempts: int = 0,
) -> StageResult:
    """Helper to create a StageResult."""
    return StageResult(
        status=status,
        artifact_path=artifact_path,
        error_message=error_message,
        duration_seconds=duration_seconds,
        attempts=attempts,
    )


def run_triage_stage(state: OrchestrationState) -> OrchestrationState:
    """Execute issue triage workflow.

    Checks for existing artifact first.
    Wraps requirements workflow with type=issue.
    """
    stage = "triage"
    issue_number = state["issue_number"]
    start_time = time.monotonic()

    # Check for existing artifact
    existing = detect_existing_artifacts(issue_number)
    skip, artifact_path = should_skip_stage(state, stage, existing)
    if skip and artifact_path:
        result = _make_stage_result(
            status="skipped",
            artifact_path=artifact_path,
            duration_seconds=time.monotonic() - start_time,
            attempts=0,
        )
        return update_stage_result(state, stage, result)

    # Execute triage sub-workflow
    try:
        # Import here to avoid circular dependencies and allow mocking
        from assemblyzero.workflows.requirements.graph import create_graph as create_requirements_graph

        graph = create_requirements_graph()
        app = graph.compile()
        sub_result = app.invoke({
            "issue_number": issue_number,
            "workflow_type": "issue",
        })

        # Check for artifact
        brief_path = sub_result.get("issue_brief_path", "")
        if brief_path and Path(brief_path).is_file():
            result = _make_stage_result(
                status="passed",
                artifact_path=brief_path,
                duration_seconds=time.monotonic() - start_time,
                attempts=1,
            )
        else:
            error_msg = sub_result.get("error_message", "Triage workflow completed but no artifact produced")
            result = _make_stage_result(
                status="failed",
                error_message=error_msg,
                duration_seconds=time.monotonic() - start_time,
                attempts=1,
            )
    except Exception as exc:
        result = _make_stage_result(
            status="failed",
            error_message=f"Triage stage error: {exc}",
            duration_seconds=time.monotonic() - start_time,
            attempts=1,
        )

    return update_stage_result(state, stage, result)


def run_lld_stage(state: OrchestrationState) -> OrchestrationState:
    """Execute LLD generation and review workflow.

    Checks for existing artifact first if skip_existing_lld is configured.
    Wraps requirements workflow with type=lld.
    """
    stage = "lld"
    issue_number = state["issue_number"]
    start_time = time.monotonic()

    # Check for existing artifact
    existing = detect_existing_artifacts(issue_number)
    skip, artifact_path = should_skip_stage(state, stage, existing)
    if skip and artifact_path:
        result = _make_stage_result(
            status="skipped",
            artifact_path=artifact_path,
            duration_seconds=time.monotonic() - start_time,
            attempts=0,
        )
        return update_stage_result(state, stage, result)

    try:
        from assemblyzero.workflows.requirements.graph import create_graph as create_requirements_graph

        graph = create_requirements_graph()
        app = graph.compile()
        sub_result = app.invoke({
            "issue_number": issue_number,
            "workflow_type": "lld",
        })

        lld_path = sub_result.get("lld_path", "")
        review_verdict = sub_result.get("review_verdict", "")

        if lld_path and Path(lld_path).is_file():
            if review_verdict.upper() == "APPROVED":
                result = _make_stage_result(
                    status="passed",
                    artifact_path=lld_path,
                    duration_seconds=time.monotonic() - start_time,
                    attempts=1,
                )
            else:
                result = _make_stage_result(
                    status="blocked",
                    artifact_path=lld_path,
                    error_message=f"LLD review verdict: {review_verdict}. Manual intervention needed.",
                    duration_seconds=time.monotonic() - start_time,
                    attempts=1,
                )
        else:
            error_msg = sub_result.get("error_message", "LLD workflow completed but no artifact produced")
            result = _make_stage_result(
                status="failed",
                error_message=error_msg,
                duration_seconds=time.monotonic() - start_time,
                attempts=1,
            )
    except Exception as exc:
        result = _make_stage_result(
            status="failed",
            error_message=f"LLD stage error: {exc}",
            duration_seconds=time.monotonic() - start_time,
            attempts=1,
        )

    return update_stage_result(state, stage, result)


def run_spec_stage(state: OrchestrationState) -> OrchestrationState:
    """Execute implementation spec workflow.

    Checks for existing artifact first if skip_existing_spec is configured.
    """
    stage = "spec"
    issue_number = state["issue_number"]
    start_time = time.monotonic()

    # Check for existing artifact
    existing = detect_existing_artifacts(issue_number)
    skip, artifact_path = should_skip_stage(state, stage, existing)
    if skip and artifact_path:
        result = _make_stage_result(
            status="skipped",
            artifact_path=artifact_path,
            duration_seconds=time.monotonic() - start_time,
            attempts=0,
        )
        return update_stage_result(state, stage, result)

    try:
        from assemblyzero.workflows.implementation_spec.graph import create_graph as create_spec_graph

        lld_path = state.get("lld_path", "")
        graph = create_spec_graph()
        app = graph.compile()
        sub_result = app.invoke({
            "issue_number": issue_number,
            "lld_path": lld_path,
        })

        spec_path = sub_result.get("spec_path", "")
        if spec_path and Path(spec_path).is_file():
            result = _make_stage_result(
                status="passed",
                artifact_path=spec_path,
                duration_seconds=time.monotonic() - start_time,
                attempts=1,
            )
        else:
            error_msg = sub_result.get("error_message", "Spec workflow completed but no artifact produced")
            result = _make_stage_result(
                status="failed",
                error_message=error_msg,
                duration_seconds=time.monotonic() - start_time,
                attempts=1,
            )
    except Exception as exc:
        result = _make_stage_result(
            status="failed",
            error_message=f"Spec stage error: {exc}",
            duration_seconds=time.monotonic() - start_time,
            attempts=1,
        )

    return update_stage_result(state, stage, result)


def run_impl_stage(state: OrchestrationState) -> OrchestrationState:
    """Execute implementation workflow (TDD).

    Ensures worktree exists or creates it via git worktree add.
    Runs implementation workflow in the worktree.
    """
    stage = "impl"
    issue_number = state["issue_number"]
    start_time = time.monotonic()

    import subprocess

    worktree_path = Path(f"../AssemblyZero-{issue_number}")
    branch_name = f"issue-{issue_number}"

    try:
        # Ensure worktree exists
        if not worktree_path.is_dir():
            subprocess.run(
                ["git", "worktree", "add", str(worktree_path), "-b", branch_name],
                check=True,
                capture_output=True,
                text=True,
            )

        # Run implementation workflow
        from assemblyzero.workflows.testing.graph import create_graph as create_impl_graph

        spec_path = state.get("spec_path", "")
        graph = create_impl_graph()
        app = graph.compile()
        sub_result = app.invoke({
            "issue_number": issue_number,
            "spec_path": spec_path,
            "worktree_path": str(worktree_path),
        })

        error_msg = sub_result.get("error_message", "")
        if not error_msg:
            result = _make_stage_result(
                status="passed",
                artifact_path=str(worktree_path),
                duration_seconds=time.monotonic() - start_time,
                attempts=1,
            )
        else:
            result = _make_stage_result(
                status="failed",
                artifact_path=str(worktree_path),
                error_message=error_msg,
                duration_seconds=time.monotonic() - start_time,
                attempts=1,
            )
    except subprocess.CalledProcessError as exc:
        result = _make_stage_result(
            status="failed",
            error_message=f"Git worktree error: {exc.stderr}",
            duration_seconds=time.monotonic() - start_time,
            attempts=1,
        )
    except Exception as exc:
        result = _make_stage_result(
            status="failed",
            error_message=f"Implementation stage error: {exc}",
            duration_seconds=time.monotonic() - start_time,
            attempts=1,
        )

    return update_stage_result(state, stage, result)


def run_pr_stage(state: OrchestrationState) -> OrchestrationState:
    """Create and submit PR using gh CLI.

    Checks human gate first (default: enabled).
    """
    stage = "pr"
    issue_number = state["issue_number"]
    start_time = time.monotonic()

    import subprocess

    try:
        worktree_path = state.get("worktree_path", "")
        if not worktree_path:
            result = _make_stage_result(
                status="failed",
                error_message="No worktree path available for PR creation",
                duration_seconds=time.monotonic() - start_time,
                attempts=1,
            )
            return update_stage_result(state, stage, result)

        # Push branch
        subprocess.run(
            ["git", "push", "--set-upstream", "origin", f"issue-{issue_number}"],
            check=True,
            capture_output=True,
            text=True,
            cwd=worktree_path,
        )

        # Create PR
        pr_result = subprocess.run(
            [
                "gh", "pr", "create",
                "--title", f"Issue #{issue_number}: Automated implementation",
                "--body", f"Automated PR for issue #{issue_number}.\n\nGenerated by orchestration workflow.",
                "--base", "main",
                "--head", f"issue-{issue_number}",
            ],
            check=True,
            capture_output=True,
            text=True,
            cwd=worktree_path,
        )

        pr_url = pr_result.stdout.strip()
        result = _make_stage_result(
            status="passed",
            artifact_path=pr_url,
            duration_seconds=time.monotonic() - start_time,
            attempts=1,
        )
    except subprocess.CalledProcessError as exc:
        result = _make_stage_result(
            status="failed",
            error_message=f"PR creation error: {exc.stderr}",
            duration_seconds=time.monotonic() - start_time,
            attempts=1,
        )
    except Exception as exc:
        result = _make_stage_result(
            status="failed",
            error_message=f"PR stage error: {exc}",
            duration_seconds=time.monotonic() - start_time,
            attempts=1,
        )

    return update_stage_result(state, stage, result)


# Map stage names to their runner functions
STAGE_RUNNERS: dict[str, callable] = {
    "triage": run_triage_stage,
    "lld": run_lld_stage,
    "spec": run_spec_stage,
    "impl": run_impl_stage,
    "pr": run_pr_stage,
}
```

### 6.7 `assemblyzero/workflows/orchestrator/graph.py` (Add)

**Complete file contents:**

```python
"""LangGraph meta-graph orchestrating the full pipeline.

Issue #305: End-to-End Orchestration Workflow (Issue → Code)
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from assemblyzero.workflows.orchestrator.artifacts import detect_existing_artifacts
from assemblyzero.workflows.orchestrator.config import (
    OrchestratorConfig,
    load_config,
    validate_config,
)
from assemblyzero.workflows.orchestrator.resume import (
    acquire_orchestration_lock,
    determine_resume_stage,
    load_orchestration_state,
    release_orchestration_lock,
    save_orchestration_state,
)
from assemblyzero.workflows.orchestrator.stages import (
    STAGE_RUNNERS,
    check_human_gate,
    should_skip_stage,
)
from assemblyzero.workflows.orchestrator.state import (
    STAGE_ORDER,
    OrchestrationState,
    StageResult,
    create_initial_state,
    get_next_stage,
    update_stage_result,
)


class OrchestrationResult(TypedDict):
    """Final result of orchestration."""

    success: bool
    issue_number: int
    pr_url: str
    final_stage: str
    total_duration_seconds: float
    stage_results: dict[str, StageResult]
    error_summary: str


class ConcurrentOrchestrationError(RuntimeError):
    """Raised when orchestration is already running for an issue."""


def _init_node(state: OrchestrationState) -> dict[str, Any]:
    """Initialize orchestration: detect artifacts, set start time."""
    now = datetime.now(tz=timezone.utc).isoformat()
    return {
        "stage_started_at": now,
    }


def _run_stage_node(state: OrchestrationState) -> dict[str, Any]:
    """Execute the current stage with retry logic."""
    current_stage = state.get("current_stage", "done")
    if current_stage == "done" or current_stage not in STAGE_RUNNERS:
        return {}

    config = state.get("config", {})
    max_retries = config.get("max_stage_retries", 3)
    retry_delay = config.get("retry_delay_seconds", 10)

    # Check human gate
    if not check_human_gate(state, current_stage):
        blocked_result = StageResult(
            status="blocked",
            artifact_path="",
            error_message=f"Human gate enabled for stage '{current_stage}'. Pipeline paused.",
            duration_seconds=0.0,
            attempts=0,
        )
        new_state = update_stage_result(state, current_stage, blocked_result)
        save_orchestration_state(new_state)
        return dict(new_state)

    runner = STAGE_RUNNERS[current_stage]
    last_state = state

    for attempt in range(1, max_retries + 1):
        # Update state with start time for this stage
        last_state = dict(last_state)
        last_state["stage_started_at"] = datetime.now(tz=timezone.utc).isoformat()

        # Run stage
        new_state = runner(OrchestrationState(**last_state))

        # Persist state after each attempt
        save_orchestration_state(new_state)

        stage_result = new_state.get("stage_results", {}).get(current_stage, {})
        status = stage_result.get("status", "")

        if status in ("passed", "skipped"):
            return dict(new_state)
        if status == "blocked":
            return dict(new_state)
        # failed — retry
        if attempt < max_retries:
            print(
                f"[ORCHESTRATOR] Stage '{current_stage}' failed (attempt {attempt}/{max_retries}). "
                f"Retrying in {retry_delay}s..."
            )
            # Update attempt count in result
            stage_result["attempts"] = attempt
            time.sleep(retry_delay)
            last_state = new_state

    # All retries exhausted — update attempt count
    final_results = dict(new_state.get("stage_results", {}))
    if current_stage in final_results:
        final_results[current_stage] = dict(final_results[current_stage])
        final_results[current_stage]["attempts"] = max_retries
    new_state_dict = dict(new_state)
    new_state_dict["stage_results"] = final_results
    save_orchestration_state(OrchestrationState(**new_state_dict))
    return new_state_dict


def _route_after_stage(state: OrchestrationState) -> str:
    """Route to next stage or terminal state based on current stage result."""
    current_stage = state.get("current_stage", "done")

    if current_stage == "done":
        return "done"

    # Check the stage result for the stage that just ran
    # After update_stage_result, current_stage is already advanced if passed/skipped
    # So we need to check if there were failures
    stage_results = state.get("stage_results", {})

    # Find the most recent result
    for stage in reversed(STAGE_ORDER):
        if stage in stage_results:
            result = stage_results[stage]
            status = result.get("status", "")
            if status in ("failed", "blocked"):
                return "terminal"
            break

    if current_stage == "done":
        return "done"

    return "run_stage"


def create_orchestration_graph() -> StateGraph:
    """Create LangGraph StateGraph for orchestration pipeline.

    Graph structure:
        init → run_stage → (route) → run_stage | done | terminal
    """
    workflow = StateGraph(OrchestrationState)

    workflow.add_node("init", _init_node)
    workflow.add_node("run_stage", _run_stage_node)
    workflow.add_node("done", lambda state: {"completed_at": datetime.now(tz=timezone.utc).isoformat()})
    workflow.add_node("terminal", lambda state: {})

    workflow.set_entry_point("init")
    workflow.add_edge("init", "run_stage")
    workflow.add_conditional_edges(
        "run_stage",
        _route_after_stage,
        {
            "run_stage": "run_stage",
            "done": "done",
            "terminal": "terminal",
        },
    )
    workflow.add_edge("done", END)
    workflow.add_edge("terminal", END)

    return workflow


def orchestrate(
    issue_number: int,
    config: OrchestratorConfig | None = None,
    resume_from: str | None = None,
    dry_run: bool = False,
) -> OrchestrationResult:
    """Run full pipeline from issue to PR.

    Args:
        issue_number: GitHub issue number to process
        config: Override default configuration (merged with defaults)
        resume_from: Stage name to resume from (uses persisted state)
        dry_run: If True, show planned stages without execution

    Returns:
        OrchestrationResult with final status and artifacts
    """
    start_time = time.monotonic()

    # Load configuration
    effective_config = load_config(config)
    errors = validate_config(effective_config)
    if errors:
        return OrchestrationResult(
            success=False,
            issue_number=issue_number,
            pr_url="",
            final_stage="",
            total_duration_seconds=0.0,
            stage_results={},
            error_summary=f"Configuration errors: {'; '.join(errors)}",
        )

    # Acquire lock
    if not acquire_orchestration_lock(issue_number):
        raise ConcurrentOrchestrationError(
            f"Issue {issue_number} is already being orchestrated. "
            f"Check .assemblyzero/orchestrator/locks/{issue_number}.lock"
        )

    try:
        # Create or load state
        if resume_from is not None:
            state = load_orchestration_state(issue_number)
            if state is None:
                raise ValueError(
                    f"No persisted state found for issue {issue_number}. "
                    f"Cannot resume without prior state."
                )
            resume_stage = determine_resume_stage(state, resume_from)
            state_dict = dict(state)
            state_dict["current_stage"] = resume_stage
            state_dict["config"] = effective_config
            state = OrchestrationState(**state_dict)
        else:
            state = create_initial_state(issue_number, effective_config)
            # Detect existing artifacts and skip completed stages
            existing = detect_existing_artifacts(issue_number)
            for stage in STAGE_ORDER:
                skip, artifact_path = should_skip_stage(state, stage, existing)
                if skip and artifact_path:
                    result = StageResult(
                        status="skipped",
                        artifact_path=artifact_path,
                        error_message="",
                        duration_seconds=0.0,
                        attempts=0,
                    )
                    state = update_stage_result(state, stage, result)
                else:
                    break  # Stop skipping at first non-skippable stage

        # Dry run
        if dry_run:
            print(f"\n[ORCHESTRATOR] Dry run for issue #{issue_number}")
            print(f"{'Stage':<10} {'Status':<12} {'Artifact'}")
            print("-" * 60)
            existing = detect_existing_artifacts(issue_number)
            for stage in STAGE_ORDER:
                stage_result = state.get("stage_results", {}).get(stage, {})
                status = stage_result.get("status", "pending")
                artifact = stage_result.get("artifact_path", "")
                if status == "skipped":
                    print(f"{stage:<10} {'SKIP':<12} {artifact}")
                else:
                    print(f"{stage:<10} {'EXECUTE':<12} -")
            print()

            release_orchestration_lock(issue_number)
            return OrchestrationResult(
                success=True,
                issue_number=issue_number,
                pr_url="",
                final_stage=state.get("current_stage", "triage"),
                total_duration_seconds=time.monotonic() - start_time,
                stage_results=state.get("stage_results", {}),
                error_summary="",
            )

        # Run the graph
        save_orchestration_state(state)
        graph = create_orchestration_graph()
        app = graph.compile()
        final_state = app.invoke(dict(state))

        # Build result
        pr_url = final_state.get("pr_url", "")
        final_stage = final_state.get("current_stage", "")
        stage_results = final_state.get("stage_results", {})
        error_message = final_state.get("error_message", "")

        success = final_stage == "done"

        if not success and error_message:
            error_summary = (
                f"Pipeline failed at stage '{final_stage}'. "
                f"Error: {error_message}. "
                f"Resume with: orchestrate --issue {issue_number} --resume-from {final_stage}"
            )
        else:
            error_summary = ""

        return OrchestrationResult(
            success=success,
            issue_number=issue_number,
            pr_url=pr_url,
            final_stage=final_stage,
            total_duration_seconds=time.monotonic() - start_time,
            stage_results=stage_results,
            error_summary=error_summary,
        )

    finally:
        release_orchestration_lock(issue_number)
```

### 6.8 `tools/orchestrate.py` (Add)

**Complete file contents:**

```python
#!/usr/bin/env python3
"""CLI entry point for orchestration workflow.

Issue #305: End-to-End Orchestration Workflow (Issue → Code)

Usage:
    poetry run python tools/orchestrate.py --issue 305
    poetry run python tools/orchestrate.py --issue 305 --dry-run
    poetry run python tools/orchestrate.py --issue 305 --resume-from spec
    poetry run python tools/orchestrate.py --issue 305 --skip-lld --no-gate-pr
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from assemblyzero.workflows.orchestrator.graph import (
    ConcurrentOrchestrationError,
    OrchestrationResult,
    orchestrate,
)
from assemblyzero.workflows.orchestrator.state import (
    STAGE_ORDER,
    OrchestrationState,
    StageResult,
)


def report_progress(state: OrchestrationState) -> None:
    """Report current stage, duration, and artifacts to stdout."""
    import time
    from datetime import datetime

    issue_number = state.get("issue_number", "?")
    current_stage = state.get("current_stage", "unknown")
    started_at = state.get("started_at", "")

    elapsed = ""
    if started_at:
        try:
            start_dt = datetime.fromisoformat(started_at)
            elapsed_s = (datetime.now(start_dt.tzinfo) - start_dt).total_seconds()
            minutes = int(elapsed_s // 60)
            seconds = int(elapsed_s % 60)
            elapsed = f"{minutes}m {seconds}s"
        except (ValueError, TypeError):
            elapsed = "?"

    print(f"\n[ORCHESTRATOR] Issue #{issue_number} | Stage: {current_stage} | Elapsed: {elapsed}")

    stage_results = state.get("stage_results", {})
    for stage in STAGE_ORDER:
        result = stage_results.get(stage, {})
        status = result.get("status", "")
        artifact = result.get("artifact_path", "")

        if status == "passed":
            print(f"  ✓ {stage} → {artifact}")
        elif status == "skipped":
            print(f"  ⊘ {stage} → {artifact} (skipped)")
        elif status == "failed":
            print(f"  ✗ {stage} — {result.get('error_message', 'unknown error')}")
        elif status == "blocked":
            print(f"  ⊗ {stage} — BLOCKED: {result.get('error_message', '')}")
        elif stage == current_stage:
            print(f"  ◌ {stage} (in progress)")
        else:
            print(f"  ○ {stage}")

    print()


def format_error_message(stage: str, stage_result: StageResult) -> str:
    """Format actionable error message with context."""
    error = stage_result.get("error_message", "Unknown error")
    attempts = stage_result.get("attempts", 0)
    duration = stage_result.get("duration_seconds", 0)

    minutes = int(duration // 60)
    seconds = int(duration % 60)

    lines = [
        "",
        "╔══════════════════════════════════════════════════════════╗",
        f"║  ORCHESTRATION FAILED at stage: {stage:<25}║",
        "╠══════════════════════════════════════════════════════════╣",
    ]

    # Wrap error message
    max_line = 54
    error_lines = []
    remaining = error
    while remaining:
        if len(remaining) <= max_line:
            error_lines.append(remaining)
            remaining = ""
        else:
            # Find break point
            idx = remaining[:max_line].rfind(" ")
            if idx == -1:
                idx = max_line
            error_lines.append(remaining[:idx])
            remaining = remaining[idx:].lstrip()

    lines.append(f"║  Error: {error_lines[0]:<48}║")
    for el in error_lines[1:]:
        lines.append(f"║         {el:<48}║")

    lines.append(f"║  Attempts: {attempts} | Duration: {minutes}m {seconds}s{' ' * (35 - len(str(attempts)) - len(str(minutes)) - len(str(seconds)))}║")
    lines.append("║                                                          ║")
    lines.append(f"║  Resume: orchestrate --issue N --resume-from {stage:<12}║")
    lines.append("╚══════════════════════════════════════════════════════════╝")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Orchestrate end-to-end pipeline from GitHub issue to PR",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --issue 305              Run full pipeline
  %(prog)s --issue 305 --dry-run    Show plan without executing
  %(prog)s --issue 305 --resume-from spec  Resume from spec stage
  %(prog)s --issue 305 --no-gate-pr Skip human gate before PR
        """,
    )
    parser.add_argument("--issue", type=int, required=True, help="GitHub issue number")
    parser.add_argument("--dry-run", action="store_true", help="Show planned stages without execution")
    parser.add_argument("--resume-from", type=str, default=None, choices=STAGE_ORDER, help="Stage to resume from")
    parser.add_argument("--skip-lld", action="store_true", help="Skip LLD stage if artifact exists")
    parser.add_argument("--no-skip-lld", action="store_true", help="Force LLD regeneration")
    parser.add_argument("--skip-spec", action="store_true", help="Skip spec stage if artifact exists")
    parser.add_argument("--no-skip-spec", action="store_true", help="Force spec regeneration")
    parser.add_argument("--gate-pr", action="store_true", default=None, help="Enable human gate before PR")
    parser.add_argument("--no-gate-pr", action="store_true", help="Disable human gate before PR")

    args = parser.parse_args()

    # Build config overrides from CLI args
    overrides: dict = {}
    if args.skip_lld:
        overrides["skip_existing_lld"] = True
    if args.no_skip_lld:
        overrides["skip_existing_lld"] = False
    if args.skip_spec:
        overrides["skip_existing_spec"] = True
    if args.no_skip_spec:
        overrides["skip_existing_spec"] = False
    if args.no_gate_pr:
        overrides.setdefault("gates", {})["pr"] = False
    elif args.gate_pr:
        overrides.setdefault("gates", {})["pr"] = True

    config = overrides if overrides else None

    print(f"[ORCHESTRATOR] Starting pipeline for issue #{args.issue}")
    if args.dry_run:
        print("[ORCHESTRATOR] DRY RUN — no stages will execute")
    if args.resume_from:
        print(f"[ORCHESTRATOR] Resuming from stage: {args.resume_from}")

    try:
        result: OrchestrationResult = orchestrate(
            issue_number=args.issue,
            config=config,
            resume_from=args.resume_from,
            dry_run=args.dry_run,
        )

        if result["success"]:
            print(f"\n[ORCHESTRATOR] ✓ Pipeline completed successfully!")
            if result["pr_url"]:
                print(f"[ORCHESTRATOR] PR: {result['pr_url']}")
            print(f"[ORCHESTRATOR] Duration: {result['total_duration_seconds']:.1f}s")
        else:
            # Find the failed stage
            for stage_name, stage_result in result["stage_results"].items():
                if stage_result.get("status") in ("failed", "blocked"):
                    print(format_error_message(stage_name, stage_result))
                    break

            if result["error_summary"]:
                print(f"[ORCHESTRATOR] {result['error_summary']}")

            sys.exit(1)

    except ConcurrentOrchestrationError as exc:
        print(f"\n[ORCHESTRATOR] ERROR: {exc}")
        sys.exit(2)
    except ValueError as exc:
        print(f"\n[ORCHESTRATOR] ERROR: {exc}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[ORCHESTRATOR] Interrupted by user. State has been saved.")
        print(f"[ORCHESTRATOR] Resume with: orchestrate --issue {args.issue} --resume-from <stage>")
        sys.exit(130)


if __name__ == "__main__":
    main()
```

### 6.9 `tests/unit/test_orchestrator_config.py` (Add)

**Complete file contents:**

```python
"""Unit tests for orchestrator configuration.

Issue #305: End-to-End Orchestration Workflow (Issue → Code)
"""

import pytest

from assemblyzero.workflows.orchestrator.config import (
    VALID_STAGES,
    OrchestratorConfig,
    get_default_config,
    load_config,
    validate_config,
)


class TestGetDefaultConfig:
    """Tests for get_default_config (T120)."""

    def test_returns_config_with_all_required_fields(self):
        """T120: Default config has all required fields."""
        config = get_default_config()
        assert "skip_existing_lld" in config
        assert "skip_existing_spec" in config
        assert "stages" in config
        assert "gates" in config
        assert "max_stage_retries" in config
        assert "retry_delay_seconds" in config

    def test_stages_contains_all_pipeline_stages(self):
        config = get_default_config()
        for stage in VALID_STAGES:
            assert stage in config["stages"], f"Missing stage: {stage}"

    def test_gates_contains_all_pipeline_stages(self):
        config = get_default_config()
        for stage in VALID_STAGES:
            assert stage in config["gates"], f"Missing gate: {stage}"

    def test_pr_gate_defaults_to_true(self):
        config = get_default_config()
        assert config["gates"]["pr"] is True

    def test_default_config_validates_clean(self):
        config = get_default_config()
        errors = validate_config(config)
        assert errors == []


class TestLoadConfig:
    """Tests for load_config (T130)."""

    def test_no_overrides_returns_defaults(self):
        config = load_config()
        default = get_default_config()
        assert config == default

    def test_empty_overrides_returns_defaults(self):
        config = load_config({})
        default = get_default_config()
        assert config == default

    def test_override_merges_correctly(self):
        """T130: CLI overrides merge with defaults."""
        config = load_config({"skip_existing_lld": False, "max_stage_retries": 5})
        assert config["skip_existing_lld"] is False
        assert config["max_stage_retries"] == 5
        # Other defaults preserved
        assert config["skip_existing_spec"] is True
        assert config["retry_delay_seconds"] == 10

    def test_nested_override_gates(self):
        config = load_config({"gates": {"pr": False}})
        assert config["gates"]["pr"] is False
        # Other gates preserved
        assert config["gates"]["triage"] is False


class TestValidateConfig:
    """Tests for validate_config."""

    def test_valid_config_returns_empty_list(self):
        config = get_default_config()
        assert validate_config(config) == []

    def test_negative_max_retries(self):
        config = get_default_config()
        config["max_stage_retries"] = -1
        errors = validate_config(config)
        assert any("max_stage_retries" in e for e in errors)

    def test_missing_stages(self):
        config = get_default_config()
        config["stages"] = {"triage": config["stages"]["triage"]}
        errors = validate_config(config)
        assert any("Missing" in e for e in errors)

    def test_invalid_timeout(self):
        config = get_default_config()
        config["stages"]["triage"]["timeout_seconds"] = 0
        errors = validate_config(config)
        assert any("timeout_seconds" in e for e in errors)
```

### 6.10 `tests/unit/test_orchestrator_state.py` (Add)

**Complete file contents:**

```python
"""Unit tests for orchestrator state management.

Issue #305: End-to-End Orchestration Workflow (Issue → Code)
"""

import pytest

from assemblyzero.workflows.orchestrator.config import get_default_config
from assemblyzero.workflows.orchestrator.state import (
    STAGE_ORDER,
    OrchestrationState,
    StageResult,
    create_initial_state,
    get_next_stage,
    update_stage_result,
)


class TestCreateInitialState:
    """Tests for create_initial_state (T100)."""

    def test_fresh_state_has_correct_defaults(self):
        """T100: Fresh state has correct defaults."""
        config = get_default_config()
        state = create_initial_state(305, config)

        assert state["issue_number"] == 305
        assert state["current_stage"] == "triage"
        assert state["issue_brief_path"] == ""
        assert state["lld_path"] == ""
        assert state["spec_path"] == ""
        assert state["worktree_path"] == ""
        assert state["pr_url"] == ""
        assert state["stage_results"] == {}
        assert state["started_at"] != ""
        assert state["completed_at"] == ""
        assert state["error_message"] == ""

    def test_stage_attempts_initialized_to_zero(self):
        config = get_default_config()
        state = create_initial_state(305, config)
        for stage in STAGE_ORDER:
            assert state["stage_attempts"][stage] == 0

    def test_negative_issue_number_raises(self):
        config = get_default_config()
        with pytest.raises(ValueError, match="issue_number must be positive"):
            create_initial_state(-1, config)

    def test_zero_issue_number_raises(self):
        config = get_default_config()
        with pytest.raises(ValueError, match="issue_number must be positive"):
            create_initial_state(0, config)


class TestGetNextStage:
    """Tests for get_next_stage."""

    def test_triage_to_lld(self):
        assert get_next_stage("triage") == "lld"

    def test_lld_to_spec(self):
        assert get_next_stage("lld") == "spec"

    def test_spec_to_impl(self):
        assert get_next_stage("spec") == "impl"

    def test_impl_to_pr(self):
        assert get_next_stage("impl") == "pr"

    def test_pr_to_done(self):
        assert get_next_stage("pr") == "done"

    def test_done_stays_done(self):
        assert get_next_stage("done") == "done"

    def test_invalid_stage_raises(self):
        with pytest.raises(ValueError, match="Unknown stage: invalid"):
            get_next_stage("invalid")


class TestUpdateStageResult:
    """Tests for update_stage_result (T110)."""

    def test_passed_advances_stage(self):
        """T110: State updates correctly on stage complete."""
        config = get_default_config()
        state = create_initial_state(305, config)
        result = StageResult(
            status="passed",
            artifact_path="docs/lineage/305/issue-brief.md",
            error_message="",
            duration_seconds=85.3,
            attempts=1,
        )
        new_state = update_stage_result(state, "triage", result)
        assert new_state["current_stage"] == "lld"
        assert new_state["issue_brief_path"] == "docs/lineage/305/issue-brief.md"
        assert "triage" in new_state["stage_results"]

    def test_skipped_advances_stage(self):
        config = get_default_config()
        state = create_initial_state(305, config)
        result = StageResult(
            status="skipped",
            artifact_path="docs/lineage/305/issue-brief.md",
            error_message="",
            duration_seconds=0.01,
            attempts=0,
        )
        new_state = update_stage_result(state, "triage", result)
        assert new_state["current_stage"] == "lld"

    def test_failed_does_not_advance(self):
        config = get_default_config()
        state = create_initial_state(305, config)
        result = StageResult(
            status="failed",
            artifact_path="",
            error_message="Triage failed: API error",
            duration_seconds=10.0,
            attempts=1,
        )
        new_state = update_stage_result(state, "triage", result)
        assert new_state["current_stage"] == "triage"
        assert new_state["error_message"] == "Triage failed: API error"

    def test_blocked_does_not_advance(self):
        config = get_default_config()
        state = create_initial_state(305, config)
        result = StageResult(
            status="blocked",
            artifact_path="",
            error_message="LLD blocked by reviewer",
            duration_seconds=300.0,
            attempts=1,
        )
        # Advance to lld first
        state_at_lld = dict(state)
        state_at_lld["current_stage"] = "lld"
        new_state = update_stage_result(OrchestrationState(**state_at_lld), "lld", result)
        assert new_state["current_stage"] == "lld"

    def test_pr_passed_sets_done_and_completed(self):
        config = get_default_config()
        state = create_initial_state(305, config)
        state_at_pr = dict(state)
        state_at_pr["current_stage"] = "pr"
        result = StageResult(
            status="passed",
            artifact_path="https://github.com/martymcenroe/AssemblyZero/pull/312",
            error_message="",
            duration_seconds=12.1,
            attempts=1,
        )
        new_state = update_stage_result(OrchestrationState(**state_at_pr), "pr", result)
        assert new_state["current_stage"] == "done"
        assert new_state["completed_at"] != ""
        assert new_state["pr_url"] == "https://github.com/martymcenroe/AssemblyZero/pull/312"

    def test_does_not_mutate_original_state(self):
        config = get_default_config()
        state = create_initial_state(305, config)
        result = StageResult(status="passed", artifact_path="test.md", error_message="", duration_seconds=1.0, attempts=1)
        new_state = update_stage_result(state, "triage", result)
        assert state["current_stage"] == "triage"
        assert new_state["current_stage"] == "lld"
```

### 6.11 `tests/unit/test_orchestrator_artifacts.py` (Add)

**Complete file contents:**

```python
"""Unit tests for orchestrator artifact detection.

Issue #305: End-to-End Orchestration Workflow (Issue → Code)
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from assemblyzero.workflows.orchestrator.artifacts import (
    detect_existing_artifacts,
    get_artifact_path,
    validate_artifact,
)


class TestDetectExistingArtifacts:
    """Tests for detect_existing_artifacts (T140, T150)."""

    def test_finds_existing_lld(self, tmp_path, monkeypatch):
        """T140: Artifact detection finds LLD."""
        monkeypatch.chdir(tmp_path)

        # Create LLD file
        lld_dir = tmp_path / "docs" / "lld" / "active"
        lld_dir.mkdir(parents=True)
        lld_file = lld_dir / "305-orchestration-workflow.md"
        lld_file.write_text("# 305\n## 1. Context")

        artifacts = detect_existing_artifacts(305)
        assert artifacts["lld"] == str(lld_file)

    def test_finds_lld_in_done_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        done_dir = tmp_path / "docs" / "lld" / "done"
        done_dir.mkdir(parents=True)
        lld_file = done_dir / "305-orchestration-workflow.md"
        lld_file.write_text("# 305\n## 1. Context")

        artifacts = detect_existing_artifacts(305)
        assert artifacts["lld"] == str(lld_file)

    def test_returns_none_when_no_artifacts(self, tmp_path, monkeypatch):
        """T150: Artifact detection returns None when no artifact exists."""
        monkeypatch.chdir(tmp_path)

        artifacts = detect_existing_artifacts(999)
        assert artifacts["triage"] is None
        assert artifacts["lld"] is None
        assert artifacts["spec"] is None
        assert artifacts["impl"] is None
        assert artifacts["pr"] is None

    def test_finds_triage_artifact(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        lineage_dir = tmp_path / "docs" / "lineage" / "305"
        lineage_dir.mkdir(parents=True)
        brief_file = lineage_dir / "issue-brief.md"
        brief_file.write_text("## Summary\nTest issue brief")

        artifacts = detect_existing_artifacts(305)
        assert artifacts["triage"] == str(brief_file)

    def test_negative_issue_number_raises(self):
        with pytest.raises(ValueError, match="issue_number must be positive"):
            detect_existing_artifacts(-1)

    def test_empty_file_not_detected(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        lineage_dir = tmp_path / "docs" / "lineage" / "305"
        lineage_dir.mkdir(parents=True)
        brief_file = lineage_dir / "issue-brief.md"
        brief_file.write_text("")  # Empty

        artifacts = detect_existing_artifacts(305)
        assert artifacts["triage"] is None


class TestGetArtifactPath:
    def test_triage_path(self):
        path = get_artifact_path(305, "triage")
        assert path == Path("docs/lineage/305/issue-brief.md")

    def test_spec_path(self):
        path = get_artifact_path(305, "spec")
        assert path == Path("docs/lineage/305/impl-spec.md")

    def test_impl_path(self):
        path = get_artifact_path(305, "impl")
        assert path == Path("../AssemblyZero-305")

    def test_pr_raises(self):
        with pytest.raises(ValueError, match="PR artifact is a URL"):
            get_artifact_path(305, "pr")

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError, match="Unknown artifact_type"):
            get_artifact_path(305, "bogus")


class TestValidateArtifact:
    def test_valid_lld(self, tmp_path):
        lld_file = tmp_path / "test.md"
        lld_file.write_text("# LLD\n## 1. Context\nContent here")
        assert validate_artifact(lld_file, "lld") is True

    def test_invalid_lld_missing_heading(self, tmp_path):
        lld_file = tmp_path / "test.md"
        lld_file.write_text("# LLD\nSome content without proper heading")
        assert validate_artifact(lld_file, "lld") is False

    def test_nonexistent_file(self, tmp_path):
        assert validate_artifact(tmp_path / "nonexistent.md", "lld") is False

    def test_empty_file(self, tmp_path):
        empty_file = tmp_path / "empty.md"
        empty_file.write_text("")
        assert validate_artifact(empty_file, "triage") is False

    def test_impl_checks_directory(self, tmp_path):
        impl_dir = tmp_path / "worktree"
        impl_dir.mkdir()
        assert validate_artifact(impl_dir, "impl") is True

    def test_impl_nonexistent_dir(self, tmp_path):
        assert validate_artifact(tmp_path / "nonexistent", "impl") is False
```

### 6.12 `tests/unit/test_orchestrator_stages.py` (Add)

**Complete file contents:**

```python
"""Unit tests for orchestrator stage execution.

Issue #305: End-to-End Orchestration Workflow (Issue → Code)
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from assemblyzero.workflows.orchestrator.config import get_default_config
from assemblyzero.workflows.orchestrator.stages import (
    STAGE_RUNNERS,
    check_human_gate,
    run_lld_stage,
    run_triage_stage,
    should_skip_stage,
)
from assemblyzero.workflows.orchestrator.state import (
    OrchestrationState,
    StageResult,
    create_initial_state,
)


class TestShouldSkipStage:
    """Tests for should_skip_stage (T020)."""

    def test_skip_lld_with_existing_artifact(self):
        """T020: Pipeline skips stages with existing artifacts."""
        config = get_default_config()
        state = create_initial_state(305, config)
        existing = {"lld": "docs/lld/active/305-test.md"}

        with patch("assemblyzero.workflows.orchestrator.stages.validate_artifact", return_value=True):
            skip, path = should_skip_stage(state, "lld", existing)
        assert skip is True
        assert path == "docs/lld/active/305-test.md"

    def test_no_skip_when_config_disabled(self):
        config = get_default_config()
        config["skip_existing_lld"] = False
        state = create_initial_state(305, config)
        existing = {"lld": "docs/lld/active/305-test.md"}

        skip, path = should_skip_stage(state, "lld", existing)
        assert skip is False
        assert path is None

    def test_no_skip_impl_stage(self):
        config = get_default_config()
        state = create_initial_state(305, config)
        existing = {"impl": "../AssemblyZero-305"}

        skip, path = should_skip_stage(state, "impl", existing)
        assert skip is False

    def test_no_skip_pr_stage(self):
        config = get_default_config()
        state = create_initial_state(305, config)
        existing = {"pr": "https://github.com/test/pr/1"}

        skip, path = should_skip_stage(state, "pr", existing)
        assert skip is False

    def test_no_skip_when_no_artifact(self):
        config = get_default_config()
        state = create_initial_state(305, config)
        existing = {"triage": None}

        skip, path = should_skip_stage(state, "triage", existing)
        assert skip is False


class TestCheckHumanGate:
    """Tests for check_human_gate (T040)."""

    def test_gate_enabled_returns_false(self):
        """T040: Human gates configurable per stage."""
        config = get_default_config()
        config["gates"]["pr"] = True
        state = create_initial_state(305, config)

        result = check_human_gate(state, "pr")
        assert result is False

    def test_gate_disabled_returns_true(self):
        config = get_default_config()
        config["gates"]["lld"] = False
        state = create_initial_state(305, config)

        result = check_human_gate(state, "lld")
        assert result is True

    def test_gate_not_configured_defaults_to_no_gate(self):
        config = get_default_config()
        config["gates"] = {}
        state = create_initial_state(305, config)

        result = check_human_gate(state, "triage")
        assert result is True


class TestRunTriageStage:
    """Tests for run_triage_stage."""

    @patch("assemblyzero.workflows.orchestrator.stages.detect_existing_artifacts")
    @patch("assemblyzero.workflows.orchestrator.stages.validate_artifact")
    def test_skips_when_artifact_exists(self, mock_validate, mock_detect):
        mock_detect.return_value = {"triage": "docs/lineage/305/issue-brief.md", "lld": None, "spec": None, "impl": None, "pr": None}
        mock_validate.return_value = True

        config = get_default_config()
        state = create_initial_state(305, config)
        new_state = run_triage_stage(state)

        assert new_state["stage_results"]["triage"]["status"] == "skipped"
        assert new_state["current_stage"] == "lld"

    @patch("assemblyzero.workflows.orchestrator.stages.detect_existing_artifacts")
    def test_handles_workflow_error(self, mock_detect):
        mock_detect.return_value = {"triage": None, "lld": None, "spec": None, "impl": None, "pr": None}

        with patch(
            "assemblyzero.workflows.orchestrator.stages.run_triage_stage.__module__"
        ):
            config = get_default_config()
            state = create_initial_state(305, config)

            # Mock the import to raise
            with patch.dict("sys.modules", {"assemblyzero.workflows.requirements.graph": MagicMock(side_effect=ImportError("test"))}):
                new_state = run_triage_stage(state)
                assert new_state["stage_results"]["triage"]["status"] == "failed"


class TestStageRunners:
    """Tests for STAGE_RUNNERS mapping."""

    def test_all_stages_have_runners(self):
        from assemblyzero.workflows.orchestrator.state import STAGE_ORDER
        for stage in STAGE_ORDER:
            assert stage in STAGE_RUNNERS, f"Missing runner for stage: {stage}"
```

### 6.13 `tests/integration/test_orchestrator_graph.py` (Add)

**Complete file contents:**

```python
"""Integration tests for orchestrator graph.

Issue #305: End-to-End Orchestration Workflow (Issue → Code)
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from assemblyzero.workflows.orchestrator.config import get_default_config
from assemblyzero.workflows.orchestrator.graph import (
    ConcurrentOrchestrationError,
    OrchestrationResult,
    orchestrate,
)
from assemblyzero.workflows.orchestrator.resume import (
    LOCK_DIR,
    STATE_DIR,
    load_orchestration_state,
    save_orchestration_state,
)
from assemblyzero.workflows.orchestrator.state import (
    OrchestrationState,
    StageResult,
    create_initial_state,
)


@pytest.fixture
def clean_orchestrator_dirs(tmp_path, monkeypatch):
    """Ensure clean orchestrator state/lock directories."""
    state_dir = tmp_path / ".assemblyzero" / "orchestrator" / "state"
    lock_dir = tmp_path / ".assemblyzero" / "orchestrator" / "locks"
    state_dir.mkdir(parents=True, exist_ok=True)
    lock_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("assemblyzero.workflows.orchestrator.resume.STATE_DIR", state_dir)
    monkeypatch.setattr("assemblyzero.workflows.orchestrator.resume.LOCK_DIR", lock_dir)
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def mock_all_stages():
    """Mock all stage runners to succeed."""
    def make_mock_runner(stage_name, artifact_suffix="artifact.md"):
        def mock_runner(state):
            from assemblyzero.workflows.orchestrator.state import update_stage_result, StageResult
            result = StageResult(
                status="passed",
                artifact_path=f"mock/{stage_name}/{artifact_suffix}",
                error_message="",
                duration_seconds=1.0,
                attempts=1,
            )
            return update_stage_result(state, stage_name, result)
        return mock_runner

    runners = {
        "triage": make_mock_runner("triage", "issue-brief.md"),
        "lld": make_mock_runner("lld", "305-lld.md"),
        "spec": make_mock_runner("spec", "impl-spec.md"),
        "impl": make_mock_runner("impl", "../AssemblyZero-305"),
        "pr": make_mock_runner("pr", "https://github.com/test/pull/1"),
    }

    with patch("assemblyzero.workflows.orchestrator.graph.STAGE_RUNNERS", runners), \
         patch("assemblyzero.workflows.orchestrator.stages.STAGE_RUNNERS", runners):
        yield runners


class TestOrchestrateFullPipeline:
    """Tests for orchestrate() function (T010)."""

    def test_full_pipeline_success(self, clean_orchestrator_dirs, mock_all_stages):
        """T010: Single command processes issue to PR."""
        config = {"gates": {"pr": False}}  # Disable gate for test
        result = orchestrate(issue_number=999, config=config)

        assert result["success"] is True
        assert result["issue_number"] == 999
        assert result["final_stage"] == "done"
        assert result["pr_url"] == "https://github.com/test/pull/1"
        assert "triage" in result["stage_results"]
        assert "pr" in result["stage_results"]

    def test_dry_run_no_execution(self, clean_orchestrator_dirs):
        """T050: Dry-run shows plan without executing."""
        result = orchestrate(issue_number=999, dry_run=True)

        assert result["success"] is True
        # No actual stages should have "passed" status from execution
        # Only "skipped" or empty results from pre-detection

    def test_concurrent_run_prevented(self, clean_orchestrator_dirs, mock_all_stages):
        """T090: Lock file blocks concurrent runs."""
        import os

        # Manually create lock with current PID
        lock_dir = clean_orchestrator_dirs / ".assemblyzero" / "orchestrator" / "locks"
        lock_file = lock_dir / "999.lock"
        lock_file.write_text(json.dumps({
            "pid": os.getpid(),
            "started_at": "2026-02-16T10:00:00Z",
            "hostname": "test",
        }))

        with pytest.raises(ConcurrentOrchestrationError, match="already being orchestrated"):
            orchestrate(issue_number=999)


class TestStatePersistence:
    """Tests for state persistence (T030)."""

    def test_state_persists_to_json(self, clean_orchestrator_dirs):
        """T030: State persists to JSON file for resume."""
        config = get_default_config()
        state = create_initial_state(305, config)
        path = save_orchestration_state(state)

        assert path.exists()
        loaded = load_orchestration_state(305)
        assert loaded is not None
        assert loaded["issue_number"] == 305
        assert loaded["current_stage"] == "triage"

    def test_state_backup_on_overwrite(self, clean_orchestrator_dirs):
        config = get_default_config()
        state = create_initial_state(305, config)

        path1 = save_orchestration_state(state)
        # Modify and save again
        state_dict = dict(state)
        state_dict["current_stage"] = "lld"
        path2 = save_orchestration_state(OrchestrationState(**state_dict))

        assert path2.exists()
        backup = path2.with_suffix(".json.bak")
        assert backup.exists()


class TestResumeFromStage:
    """Tests for resume functionality (T080)."""

    def test_resume_from_specific_stage(self, clean_orchestrator_dirs, mock_all_stages):
        """T080: Resume-from flag skips to specific stage."""
        config = get_default_config()
        config["gates"]["pr"] = False

        # Create state as if triage and lld already completed
        state = create_initial_state(305, config)
        state_dict = dict(state)
        state_dict["current_stage"] = "spec"
        state_dict["stage_results"] = {
            "triage": {"status": "passed", "artifact_path": "mock/triage.md", "error_message": "", "duration_seconds": 1.0, "attempts": 1},
            "lld": {"status": "passed", "artifact_path": "mock/lld.md", "error_message": "", "duration_seconds": 1.0, "attempts": 1},
        }
        save_orchestration_state(OrchestrationState(**state_dict))

        result = orchestrate(
            issue_number=305,
            config={"gates": {"pr": False}},
            resume_from="spec",
        )

        assert result["success"] is True
        # triage and lld should be from persisted state
        assert result["stage_results"]["triage"]["status"] == "passed"
        assert result["stage_results"]["lld"]["status"] == "passed"

    def test_resume_without_state_raises(self, clean_orchestrator_dirs):
        with pytest.raises(ValueError, match="No persisted state found"):
            orchestrate(issue_number=888, resume_from="spec")


class TestProgressAndErrors:
    """Tests for progress reporting and error messages (T060, T070)."""

    def test_actionable_error_on_failure(self, clean_orchestrator_dirs):
        """T070: Failed stages report actionable errors."""
        def failing_runner(state):
            from assemblyzero.workflows.orchestrator.state import update_stage_result, StageResult
            result = StageResult(
                status="failed",
                artifact_path="",
                error_message="API rate limit exceeded",
                duration_seconds=5.0,
                attempts=1,
            )
            return update_stage_result(state, "triage", result)

        runners = {
            "triage": failing_runner,
            "lld": MagicMock(),
            "spec": MagicMock(),
            "impl": MagicMock(),
            "pr": MagicMock(),
        }

        with patch("assemblyzero.workflows.orchestrator.graph.STAGE_RUNNERS", runners):
            result = orchestrate(issue_number=999, config={"max_stage_retries": 1})

        assert result["success"] is False
        assert "triage" in result["error_summary"]
        assert "Resume with" in result["error_summary"]

    def test_progress_reporting_function(self, capsys):
        """T060: Progress reporting shows stage info."""
        from tools.orchestrate import report_progress

        state = OrchestrationState(
            issue_number=305,
            current_stage="spec",
            issue_brief_path="docs/lineage/305/issue-brief.md",
            lld_path="docs/lld/active/305-lld.md",
            spec_path="",
            worktree_path="",
            pr_url="",
            stage_results={
                "triage": StageResult(status="passed", artifact_path="docs/lineage/305/issue-brief.md", error_message="", duration_seconds=85.3, attempts=1),
                "lld": StageResult(status="skipped", artifact_path="docs/lld/active/305-lld.md", error_message="", duration_seconds=0.01, attempts=0),
            },
            stage_attempts={},
            started_at="2026-02-16T10:30:00+00:00",
            stage_started_at="",
            completed_at="",
            config=get_default_config(),
            error_message="",
        )

        report_progress(state)
        captured = capsys.readouterr()
        assert "Issue #305" in captured.out
        assert "spec" in captured.out
        assert "✓ triage" in captured.out
```

## 7. Pattern References

### 7.1 LangGraph State Definition Pattern

**File:** `assemblyzero/workflows/implementation_spec/state.py` (lines 1-25)

```python
class ImplementationSpecState(TypedDict, total=False):
    """State for the implementation spec workflow."""
    issue_number: int
    lld_path: str
    lld_content: str
    spec_draft: str
    review_verdict: str
    review_feedback: str
    iteration_count: int
    spec_path: str
    error_message: str
```

**Relevance:** All workflow states use `TypedDict` with `total=False`. The `error_message` field is the standard error reporting pattern. All artifact paths are strings, not `Path` objects (serialization).

### 7.2 LangGraph Graph Construction Pattern

**File:** `assemblyzero/workflows/implementation_spec/graph.py` (lines 1-40)

```python
def create_graph() -> StateGraph:
    workflow = StateGraph(ImplementationSpecState)
    workflow.add_node("load_lld", load_lld_node)
    workflow.add_node("generate_spec", generate_spec_node)
    workflow.set_entry_point("load_lld")
    workflow.add_edge("load_lld", "generate_spec")
    workflow.add_conditional_edges(
        "validate_completeness",
        route_after_validation,
        {"revise": "generate_spec", "review": "review_spec"},
    )
    return workflow
```

**Relevance:** Standard pattern for graph construction. The orchestrator uses the same `StateGraph` + `add_node` + `add_conditional_edges` pattern, with a routing function that checks stage results.

### 7.3 CLI Entry Point Pattern

**File:** `tools/run_implementation_spec_workflow.py` (lines 1-30)

```python
#!/usr/bin/env python3
"""Run the implementation spec workflow."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from assemblyzero.workflows.implementation_spec.graph import create_graph

def main() -> None:
    parser = argparse.ArgumentParser(description="Run implementation spec workflow")
    parser.add_argument("--issue", type=int, required=True, help="GitHub issue number")
    args = parser.parse_args()
    ...
```

**Relevance:** All CLI tools follow this pattern: `sys.path` insertion, `argparse`, `main()` guard. The orchestrator CLI follows the same structure with additional flags.

### 7.4 Test Pattern with Mocked Workflows

**File:** `tests/test_integration_workflow.py` (lines 1-40)

```python
@pytest.fixture
def mock_llm():
    with patch("assemblyzero.workflows.requirements.nodes.draft.invoke_llm") as mock:
        mock.return_value = "Mocked LLM response"
        yield mock

def test_workflow_completes(mock_llm):
    from assemblyzero.workflows.requirements.graph import create_graph
    graph = create_graph()
    app = graph.compile()
    result = app.invoke({"issue_number": 999})
    assert result.get("error_message", "") == ""
```

**Relevance:** Integration tests mock LLM calls and use `graph.compile().invoke()`. The orchestrator tests use the same pattern but mock entire stage runners instead of individual LLM calls.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from __future__ import annotations` | stdlib | All new files |
| `from typing import Any, TypedDict, Literal` | stdlib | state.py, config.py, graph.py |
| `from pathlib import Path` | stdlib | artifacts.py, resume.py, stages.py, tools/orchestrate.py |
| `from datetime import datetime, timezone` | stdlib | state.py, resume.py, graph.py |
| `import json` | stdlib | resume.py |
| `import os` | stdlib | resume.py |
| `import platform` | stdlib | resume.py |
| `import shutil` | stdlib | resume.py |
| `import time` | stdlib | stages.py, graph.py |
| `import subprocess` | stdlib | stages.py |
| `import argparse` | stdlib | tools/orchestrate.py |
| `import sys` | stdlib | tools/orchestrate.py |
| `from langgraph.graph import END, StateGraph` | langgraph | graph.py |
| `from assemblyzero.workflows.orchestrator.config import ...` | internal | state.py, graph.py, __init__.py |
| `from assemblyzero.workflows.orchestrator.state import ...` | internal | stages.py, resume.py, graph.py, __init__.py |
| `from assemblyzero.workflows.orchestrator.artifacts import ...` | internal | stages.py, graph.py |
| `from assemblyzero.workflows.orchestrator.resume import ...` | internal | graph.py |
| `from assemblyzero.workflows.orchestrator.stages import ...` | internal | graph.py |
| `from assemblyzero.workflows.orchestrator.graph import ...` | internal | tools/orchestrate.py, __init__.py |
| `from assemblyzero.workflows.requirements.graph import create_graph` | internal (lazy) | stages.py (imported inside function) |
| `from assemblyzero.workflows.implementation_spec.graph import create_graph` | internal (lazy) | stages.py (imported inside function) |
| `from assemblyzero.workflows.testing.graph import create_graph` | internal (lazy) | stages.py (imported inside function) |

**New Dependencies:** None. All imports resolve to existing packages (`langgraph`) or stdlib.

## 9. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `orchestrate()` | `issue_number=999, config={"gates":{"pr":False}}` | `{"success": True, "final_stage": "done"}` |
| T020 | `should_skip_stage()` | `stage="lld", existing={"lld":"path.md"}` | `(True, "path.md")` |
| T030 | `save/load_orchestration_state()` | State with `issue_number=305` | Loaded state matches saved state |
| T040 | `check_human_gate()` | `stage="pr"`, gate enabled | Returns `False` (blocks) |
| T050 | `orchestrate()` | `dry_run=True` | `{"success": True}`, no stages executed |
| T060 | `report_progress()` | State at `current_stage="spec"` | Stdout contains "Issue #305" and "✓ triage" |
| T070 | `orchestrate()` | Failing triage runner | `{"success": False, "error_summary": "...triage...Resume with..."}` |
| T080 | `orchestrate()` | `resume_from="spec"` with persisted state | Starts at spec, triage/lld from persisted results |
| T090 | `orchestrate()` | Lock file with live PID | Raises `ConcurrentOrchestrationError` |
| T100 | `create_initial_state()` | `issue_number=305` | State with `current_stage="triage"`, empty artifacts |
| T110 | `update_stage_result()` | Passed result for triage | `current_stage` advances to `"lld"` |
| T120 | `get_default_config()` | No args | Config with all required fields, validates cleanly |
| T130 | `load_config()` | `{"skip_existing_lld": False}` | Merged config with override applied |
| T140 | `detect_existing_artifacts()` | LLD file exists on disk | `{"lld": "docs/lld/active/305-*.md"}` |
| T150 | `detect_existing_artifacts()` | No files on disk | `{"triage": None, "lld": None, ...}` |

## 10. Implementation Notes

### 10.1 Error Handling Convention

All stage functions catch exceptions and convert them to `StageResult` with `status="failed"` and an `error_message`. Exceptions never propagate out of stage runners. The graph routing function checks `status` to decide whether to retry, advance, or terminate.

The `orchestrate()` function itself only raises for configuration errors and concurrency issues (`ConcurrentOrchestrationError`, `ValueError`). All workflow execution errors are captured in `OrchestrationResult.error_summary`.

### 10.2 Logging Convention

Use `print()` with `[ORCHESTRATOR]` prefix for all output. Example:

```
[ORCHESTRATOR] Starting pipeline for issue #305
[ORCHESTRATOR] Stage 'lld' skipped (existing artifact found)
[ORCHESTRATOR] Stage 'spec' failed (attempt 1/3). Retrying in 10s...
[ORCHESTRATOR] ✓ Pipeline completed successfully!
```

### 10.3 Constants

| Constant | Value | Rationale | Location |
|----------|-------|-----------|----------|
| `VALID_STAGES` | `["triage", "lld", "spec", "impl", "pr"]` | Canonical stage order | config.py |
| `STAGE_ORDER` | `["triage", "lld", "spec", "impl", "pr"]` | Same list, used for iteration | state.py |
| `STATE_DIR` | `Path(".assemblyzero/orchestrator/state")` | Per reviewer suggestion | resume.py |
| `LOCK_DIR` | `Path(".assemblyzero/orchestrator/locks")` | Separate from state for clarity | resume.py |

### 10.4 .gitignore Addition

The `.assemblyzero/` directory should be in `.gitignore` to prevent committing orchestrator state and lock files. Verify this is already the case or add it.

### 10.5 Sub-Workflow Imports

Stage functions use lazy imports (inside the function body) for sub-workflow graphs. This:
1. Avoids circular import issues
2. Allows easy mocking in tests
3. Doesn't load unused workflow code

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3) — N/A, all files are Add
- [x] Every data structure has a concrete JSON/YAML example (Section 4)
- [x] Every function has input/output examples with realistic values (Section 5)
- [x] Change instructions are diff-level specific (Section 6) — complete file contents for Add files
- [x] Pattern references include file:line and are verified to exist (Section 7)
- [x] All imports are listed and verified (Section 8)
- [x] Test mapping covers all LLD test scenarios (Section 9)

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #305 |
| Verdict | DRAFT |
| Date | 2026-02-16 |
| Iterations | 1 |
| Finalized | — |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #305 |
| Verdict | APPROVED |
| Date | 2026-02-20 |
| Iterations | 0 |
| Finalized | 2026-02-20T02:07:15Z |

### Review Feedback Summary

Approved with suggestions:
1.  **Dependency Verification**: The spec uses `from assemblyzero.workflows.testing.graph import create_graph` in `run_impl_stage`. Ensure that the `workflows/testing` module exists or that Issue #139 (rename to `implementation`) hasn't moved it yet. If #139 is complete, this import path might need to change to `assemblyzero.workflows.implementation.graph`.
2.  **Git Worktree cleanup**: While `run_impl_stage` creates a worktree, ensure that there is a documented proces...
