# Implementation Request: tests/unit/test_cleanup.py

## Task

Write the complete contents of `tests/unit/test_cleanup.py`.

Change type: Add
Description: Unit tests for N9 cleanup node

## LLD Specification

# Implementation Spec: N9 Cleanup Node - Worktree Removal, Lineage Archival, and Learning Summary

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #180 |
| LLD | `docs/lld/active/180-n9-cleanup-node.md` |
| Generated | 2026-02-25 |
| Status | DRAFT |

## 1. Overview

Add an N9_cleanup node to the TDD testing workflow that removes worktrees after PR merge, archives lineage from active/ to done/, and generates a deterministic learning summary for future learning agent consumption.

**Objective:** Automate post-implementation cleanup (worktree removal, lineage archival, learning summary generation) as a workflow node.

**Success Criteria:** N9 node added to graph; worktree removed only when PR merged; lineage archived conditionally; learning summary generated; all errors handled gracefully without failing the workflow.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `assemblyzero/workflows/testing/state.py` | Modify | Add `pr_url`, `pr_merged`, `learning_summary_path`, `cleanup_skipped_reason` fields |
| 2 | `assemblyzero/workflows/testing/nodes/cleanup_helpers.py` | Add | Pure-function helpers: worktree removal, lineage archival, summary generation |
| 3 | `assemblyzero/workflows/testing/nodes/cleanup.py` | Add | N9 cleanup node and route_after_document function |
| 4 | `assemblyzero/workflows/testing/nodes/__init__.py` | Modify | Export `cleanup` and `route_after_document` from new module |
| 5 | `assemblyzero/workflows/testing/graph.py` | Modify | Add N9_cleanup node, wire N8→N9 conditional edge, N9→END edge |
| 6 | `tests/fixtures/mock_lineage/001-lld.md` | Add | Minimal mock LLD artifact |
| 7 | `tests/fixtures/mock_lineage/005-test-scaffold.py` | Add | Minimal mock test scaffold |
| 8 | `tests/fixtures/mock_lineage/052-green-phase.txt` | Add | Minimal mock green phase artifact with coverage data |
| 9 | `tests/unit/test_cleanup_helpers.py` | Add | Unit tests for cleanup helper functions |
| 10 | `tests/unit/test_cleanup.py` | Add | Unit tests for N9 cleanup node |

**Implementation Order Rationale:** State must be extended first (other files depend on it). Helpers are pure functions with no dependency on the node. The node depends on helpers + state. The `__init__.py` export depends on the node existing. The graph depends on the node + export. Fixtures must exist before tests. Tests depend on everything else.

## 3. Current State (for Modify/Delete files)

### 3.1 `assemblyzero/workflows/testing/state.py`

**Relevant excerpt** (full TypedDict — showing the end of the class where new fields will be added):

```python
"""State definition for TDD Testing Workflow.

Issue #101: Test Plan Reviewer
Issue #102: TDD Initialization
Issue #93: N8 Documentation Node
Issue #335: Scaffold validation fields
Issue #147: Completeness gate fields (completeness_verdict, completeness_issues, review_materials)
Issue #292: pytest_exit_code for exit code routing

This TypedDict travels through nodes N0-N8, tracking the testing workflow
from LLD loading through test generation, implementation, E2E validation,
and documentation generation.
"""

from enum import Enum

from typing import Literal, TypedDict

class HumanDecision(str, Enum):

    """User choices at human gate nodes."""

class TestScenario(TypedDict):

class TestingWorkflowState(TypedDict, total=False):
```

**What changes:** Add four new optional fields at the end of `TestingWorkflowState`: `pr_url`, `pr_merged`, `learning_summary_path`, `cleanup_skipped_reason`. Update the module docstring to reference Issue #180.

### 3.2 `assemblyzero/workflows/testing/nodes/__init__.py`

**Relevant excerpt** (full file):

```python
"""Node implementations for TDD Testing Workflow.

Issue #101: Test Plan Reviewer
Issue #102: TDD Initialization
Issue #93: N8 Documentation Node
Issue #147: Implementation Completeness Gate (N4b)

Nodes:
- N0: load_lld - Load LLD and extract test plan
- N1: review_test_plan - Gemini reviews test plan coverage
- N2: scaffold_tests - Generate executable test stubs
- N3: verify_red_phase - Verify all tests fail
- N4: implement_code - Claude generates implementation
- N4b: completeness_gate - Verify implementation completeness
- N5: verify_green_phase - Verify all tests pass
- N6: e2e_validation - Run E2E tests in sandbox
- N7: finalize - Generate reports and complete
- N8: document - Auto-generate documentation artifacts
"""

from assemblyzero.workflows.testing.nodes.completeness_gate import (
    completeness_gate,
)

from assemblyzero.workflows.testing.nodes.document import document

from assemblyzero.workflows.testing.nodes.e2e_validation import e2e_validation

from assemblyzero.workflows.testing.nodes.finalize import finalize

from assemblyzero.workflows.testing.nodes.implement_code import implement_code

from assemblyzero.workflows.testing.nodes.load_lld import load_lld

from assemblyzero.workflows.testing.nodes.review_test_plan import review_test_plan

from assemblyzero.workflows.testing.nodes.scaffold_tests import scaffold_tests

from assemblyzero.workflows.testing.nodes.validate_commit_message import (
    validate_commit_message,
)

from assemblyzero.workflows.testing.nodes.verify_phases import (
    verify_green_phase,
    verify_red_phase,
)
```

**What changes:** Add import of `cleanup` and `route_after_document` from `cleanup` module. Update module docstring to list N9 node.

### 3.3 `assemblyzero/workflows/testing/graph.py`

**Relevant excerpt** (imports and build_testing_workflow function — showing the end of the function where N8 currently wires to END):

```python
"""StateGraph definition for TDD Testing Workflow.

Issue #101: Test Plan Reviewer
Issue #102: TDD Initialization
Issue #93: N8 Documentation Node
Issue #335: Add mechanical test validation node (N2.5)
Issue #147: Add completeness gate node (N4b) between N4 and N5
Issue #292: Exit code routing — N3/N5 can route to N2 on syntax/collection errors
...
"""

from typing import Literal

from langgraph.graph import END, StateGraph

from assemblyzero.workflows.testing.nodes import (
    document,
    e2e_validation,
    finalize,
    implement_code,
    load_lld,
    review_test_plan,
    scaffold_tests,
    verify_green_phase,
    verify_red_phase,
)

from assemblyzero.workflows.testing.nodes.completeness_gate import (
    completeness_gate,
    route_after_completeness_gate,
)

from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
    validate_tests_mechanical_node,
    should_regenerate,
)

from assemblyzero.workflows.testing.state import TestingWorkflowState

# ... routing functions ...

def route_after_finalize(
    state: TestingWorkflowState,
) -> Literal["N8_document", "end"]:
    """Route after N7 (finalize).

Args:"""
    ...

def build_testing_workflow() -> StateGraph:
    """Build the TDD testing workflow StateGraph.

Issue #147: Added N4b completeness gate between N4 and N5."""
    ...
```

**What changes:** Add import of `cleanup` and `route_after_document` from the cleanup module. Add `route_after_document` function definition. In `build_testing_workflow()`: add `N9_cleanup` node, replace the direct N8→END edge with a conditional edge via `route_after_document`, and add N9→END edge.

## 4. Data Structures

### 4.1 TestingWorkflowState (additions)

**Definition (new fields only):**

```python
class TestingWorkflowState(TypedDict, total=False):
    # ... existing fields ...
    pr_url: str                    # GitHub PR URL
    pr_merged: bool                # Set by N9 after checking merge status
    learning_summary_path: str     # Absolute path to generated learning summary
    cleanup_skipped_reason: str    # Reason cleanup was skipped
```

**Concrete Example (state dict at N9 entry):**

```json
{
    "issue_number": 180,
    "pr_url": "https://github.com/martymcenroe/AssemblyZero/pull/42",
    "worktree_path": "/home/user/Projects/AssemblyZero-180",
    "repo_root": "/home/user/Projects/AssemblyZero",
    "final_coverage": 96.5,
    "target_coverage": 95.0,
    "outcome": "SUCCESS"
}
```

**Concrete Example (state dict returned from N9 — PR merged):**

```json
{
    "pr_merged": true,
    "learning_summary_path": "/home/user/Projects/AssemblyZero/docs/lineage/done/180-testing/learning-summary.md",
    "cleanup_skipped_reason": ""
}
```

**Concrete Example (state dict returned from N9 — PR not merged):**

```json
{
    "pr_merged": false,
    "learning_summary_path": "/home/user/Projects/AssemblyZero/docs/lineage/active/180-testing/learning-summary.md",
    "cleanup_skipped_reason": "PR not yet merged"
}
```

### 4.2 IterationSnapshot

**Definition:**

```python
@dataclass
class IterationSnapshot:
    iteration: int
    coverage_pct: float
    missing_lines: list[str]
    root_cause: str
```

**Concrete Example:**

```json
{
    "iteration": 2,
    "coverage_pct": 85.0,
    "missing_lines": ["src/cleanup.py:42", "src/cleanup.py:55-60"],
    "root_cause": "Branch not covered in error handler"
}
```

### 4.3 LearningSummaryData

**Definition:**

```python
@dataclass
class LearningSummaryData:
    issue_number: int
    outcome: str
    final_coverage: float
    target_coverage: float
    total_iterations: int
    stall_detected: bool
    stall_iteration: int | None
    iteration_snapshots: list[IterationSnapshot]
    key_artifacts: list[tuple[str, str]]
    what_worked: list[str]
    what_didnt_work: list[str]
    recommendations: list[str]
```

**Concrete Example:**

```json
{
    "issue_number": 180,
    "outcome": "SUCCESS",
    "final_coverage": 96.5,
    "target_coverage": 95.0,
    "total_iterations": 3,
    "stall_detected": true,
    "stall_iteration": 2,
    "iteration_snapshots": [
        {"iteration": 1, "coverage_pct": 72.0, "missing_lines": ["cleanup.py:10-30"], "root_cause": ""},
        {"iteration": 2, "coverage_pct": 85.0, "missing_lines": ["cleanup.py:42"], "root_cause": ""},
        {"iteration": 3, "coverage_pct": 96.5, "missing_lines": [], "root_cause": ""}
    ],
    "key_artifacts": [
        ["001-lld.md", "Low-level design document"],
        ["005-test-scaffold.py", "Test scaffold with 33 test cases"],
        ["052-green-phase.txt", "Final green phase output"]
    ],
    "what_worked": ["TDD iteration loop converged in 3 iterations"],
    "what_didnt_work": ["Coverage stalled at iteration 2 at 85%"],
    "recommendations": ["Consider splitting complex error handlers into separate functions for easier testing"]
}
```

## 5. Function Specifications

### 5.1 `cleanup(state)`

**File:** `assemblyzero/workflows/testing/nodes/cleanup.py`

**Signature:**

```python
def cleanup(state: dict[str, Any]) -> dict[str, Any]:
    """N9: Post-implementation cleanup node.

    Orchestrates three cleanup tasks:
    1. Check PR merge status and remove worktree if merged
    2. Generate learning summary in active lineage directory
    3. Archive lineage from active/ to done/ ONLY if PR is merged

    Returns updated state fields: pr_merged, learning_summary_path,
    cleanup_skipped_reason.
    """
```

**Input Example:**

```python
state = {
    "issue_number": 180,
    "pr_url": "https://github.com/martymcenroe/AssemblyZero/pull/42",
    "worktree_path": "/home/user/Projects/AssemblyZero-180",
    "repo_root": "/home/user/Projects/AssemblyZero",
    "final_coverage": 96.5,
    "target_coverage": 95.0,
    "outcome": "SUCCESS",
}
```

**Output Example (PR merged):**

```python
{
    "pr_merged": True,
    "learning_summary_path": "/home/user/Projects/AssemblyZero/docs/lineage/done/180-testing/learning-summary.md",
    "cleanup_skipped_reason": "",
}
```

**Output Example (PR not merged):**

```python
{
    "pr_merged": False,
    "learning_summary_path": "/home/user/Projects/AssemblyZero/docs/lineage/active/180-testing/learning-summary.md",
    "cleanup_skipped_reason": "PR not yet merged",
}
```

**Output Example (no PR URL):**

```python
{
    "pr_merged": False,
    "learning_summary_path": "",
    "cleanup_skipped_reason": "No PR URL in state",
}
```

**Edge Cases:**
- No `pr_url` in state → skips worktree cleanup, sets `cleanup_skipped_reason`
- No `issue_number` → should not reach N9 (routing prevents it), but if it does, returns empty cleanup
- Subprocess errors (CalledProcessError, TimeoutExpired) → caught, logged, does not raise
- No active lineage dir → skips summary and archival, logs reason
- All exceptions wrapped in try/except → always returns a valid state dict

### 5.2 `route_after_document(state)`

**File:** `assemblyzero/workflows/testing/nodes/cleanup.py`

**Signature:**

```python
def route_after_document(state: dict[str, Any]) -> str:
    """Conditional routing from N8 to N9 or END.

    Returns "N9_cleanup" if state has valid issue_number,
    otherwise returns "end".
    """
```

**Input Example 1:**

```python
state = {"issue_number": 180, "pr_url": "https://github.com/martymcenroe/AssemblyZero/pull/42"}
```

**Output Example 1:**

```python
"N9_cleanup"
```

**Input Example 2:**

```python
state = {"lld_content": "some content"}  # no issue_number
```

**Output Example 2:**

```python
"end"
```

**Edge Cases:**
- `issue_number` is 0 → returns `"end"` (falsy value)
- `issue_number` is None → returns `"end"`
- `issue_number` is a valid positive int → returns `"N9_cleanup"`

### 5.3 `check_pr_merged(pr_url)`

**File:** `assemblyzero/workflows/testing/nodes/cleanup_helpers.py`

**Signature:**

```python
def check_pr_merged(pr_url: str) -> bool:
    """Check if a GitHub PR is merged using gh CLI.

    Raises:
        subprocess.CalledProcessError: If gh CLI invocation fails.
        subprocess.TimeoutExpired: If gh CLI exceeds SUBPROCESS_TIMEOUT.
        ValueError: If pr_url is empty or malformed.
    """
```

**Input Example:**

```python
pr_url = "https://github.com/martymcenroe/AssemblyZero/pull/42"
```

**Output Example (merged):**

```python
True
```

**Output Example (open):**

```python
False
```

**Edge Cases:**
- Empty string → raises `ValueError("pr_url cannot be empty")`
- URL without "github.com" → raises `ValueError("Malformed PR URL: ...")`
- `gh` command fails → raises `subprocess.CalledProcessError`
- `gh` command exceeds 10s → raises `subprocess.TimeoutExpired`

**Internal subprocess call:**

```python
subprocess.run(
    ["gh", "pr", "view", pr_url, "--json", "state", "--jq", ".state"],
    capture_output=True,
    text=True,
    check=True,
    timeout=SUBPROCESS_TIMEOUT,
)
```

Returns `True` if stdout.strip() == "MERGED", else `False`.

### 5.4 `remove_worktree(worktree_path)`

**File:** `assemblyzero/workflows/testing/nodes/cleanup_helpers.py`

**Signature:**

```python
def remove_worktree(worktree_path: str | Path) -> bool:
    """Remove a git worktree (without --force).

    Returns True if removed, False if path didn't exist.

    Raises:
        subprocess.CalledProcessError: If git worktree remove fails (e.g., dirty worktree).
        subprocess.TimeoutExpired: If git CLI exceeds SUBPROCESS_TIMEOUT.
    """
```

**Input Example:**

```python
worktree_path = Path("/home/user/Projects/AssemblyZero-180")
```

**Output Example (success):**

```python
True
```

**Output Example (nonexistent):**

```python
False
```

**Edge Cases:**
- Path doesn't exist → returns `False` without calling subprocess
- Dirty worktree → `git worktree remove` fails with CalledProcessError (no `--force`)
- Timeout → raises `TimeoutExpired`

### 5.5 `get_worktree_branch(worktree_path)`

**File:** `assemblyzero/workflows/testing/nodes/cleanup_helpers.py`

**Signature:**

```python
def get_worktree_branch(worktree_path: str | Path) -> str | None:
    """Extract the branch name associated with a worktree.

    Returns branch name string, or None if worktree not found.
    """
```

**Input Example:**

```python
worktree_path = Path("/home/user/Projects/AssemblyZero-180")
```

**Output Example (found):**

```python
"issue-180-cleanup-node"
```

**Output Example (not found):**

```python
None
```

**Internal logic:** Parses output of `git worktree list --porcelain`. The porcelain format is:

```
worktree /home/user/Projects/AssemblyZero-180
HEAD abc123def456
branch refs/heads/issue-180-cleanup-node

worktree /home/user/Projects/AssemblyZero
HEAD def789abc012
branch refs/heads/main
```

Iterates blocks, finds matching `worktree` line, extracts `branch` line, strips `refs/heads/` prefix.

### 5.6 `delete_local_branch(branch_name)`

**File:** `assemblyzero/workflows/testing/nodes/cleanup_helpers.py`

**Signature:**

```python
def delete_local_branch(branch_name: str) -> bool:
    """Delete a local git branch using -D (force).

    Returns True if deleted, False if branch didn't exist.

    Raises:
        subprocess.CalledProcessError: If git branch -D fails for reasons
            other than branch-not-found.
        subprocess.TimeoutExpired: If git CLI exceeds SUBPROCESS_TIMEOUT.
    """
```

**Input Example:**

```python
branch_name = "issue-180-cleanup-node"
```

**Output Example (success):**

```python
True
```

**Output Example (not found):**

```python
False
```

**Edge Cases:**
- Branch doesn't exist → stderr contains "not found" or "error: branch", returns `False`
- Current branch → CalledProcessError propagated (cannot delete checked-out branch)

### 5.7 `archive_lineage(repo_root, issue_number, lineage_suffix)`

**File:** `assemblyzero/workflows/testing/nodes/cleanup_helpers.py`

**Signature:**

```python
def archive_lineage(
    repo_root: Path,
    issue_number: int,
    lineage_suffix: str = "testing",
) -> Path | None:
    """Move lineage directory from active/ to done/.

    Returns Path to the new done/ directory, or None if active dir didn't exist.

    Raises:
        OSError: If move operation fails.
    """
```

**Input Example:**

```python
repo_root = Path("/home/user/Projects/AssemblyZero")
issue_number = 180
lineage_suffix = "testing"
```

**Output Example (success):**

```python
Path("/home/user/Projects/AssemblyZero/docs/lineage/done/180-testing")
```

**Output Example (no active dir):**

```python
None
```

**Edge Cases:**
- Active dir doesn't exist → returns `None`
- Done dir already exists → appends timestamp suffix: `180-testing-1708200000`
- Cross-filesystem → `shutil.move` handles this (falls back to copy+delete internally)
- Done parent dir doesn't exist → creates it with `mkdir(parents=True, exist_ok=True)`

### 5.8 `extract_iteration_data(lineage_dir)`

**File:** `assemblyzero/workflows/testing/nodes/cleanup_helpers.py`

**Signature:**

```python
def extract_iteration_data(lineage_dir: Path) -> list[IterationSnapshot]:
    """Parse lineage artifacts to extract per-iteration coverage data.

    Scans for files matching patterns like *green-phase*, *coverage*,
    *failed-response* to reconstruct iteration history.
    """
```

**Input Example:**

```python
lineage_dir = Path("/home/user/Projects/AssemblyZero/docs/lineage/active/180-testing")
# Directory contains: 052-green-phase.txt with "Coverage: 96.5%"
```

**Output Example:**

```python
[
    IterationSnapshot(
        iteration=1,
        coverage_pct=96.5,
        missing_lines=[],
        root_cause="",
    )
]
```

**Edge Cases:**
- Empty directory → returns `[]`
- No coverage data found in files → returns snapshots with `coverage_pct=0.0`
- Regex patterns: `r"[Cc]overage:\s*([\d.]+)%"` and `r"(\d+)%\s*coverage"`
- Files sorted by name (numeric prefix ordering)

### 5.9 `detect_stall(snapshots)`

**File:** `assemblyzero/workflows/testing/nodes/cleanup_helpers.py`

**Signature:**

```python
def detect_stall(snapshots: list[IterationSnapshot]) -> tuple[bool, int | None]:
    """Detect if coverage stalled (same coverage for 2+ consecutive iterations).

    Returns (stall_detected, stall_iteration_number).
    """
```

**Input Example 1:**

```python
snapshots = [
    IterationSnapshot(iteration=1, coverage_pct=80.0, missing_lines=[], root_cause=""),
    IterationSnapshot(iteration=2, coverage_pct=85.0, missing_lines=[], root_cause=""),
    IterationSnapshot(iteration=3, coverage_pct=85.0, missing_lines=[], root_cause=""),
]
```

**Output Example 1:**

```python
(True, 3)
```

**Input Example 2:**

```python
snapshots = [
    IterationSnapshot(iteration=1, coverage_pct=80.0, missing_lines=[], root_cause=""),
    IterationSnapshot(iteration=2, coverage_pct=90.0, missing_lines=[], root_cause=""),
]
```

**Output Example 2:**

```python
(False, None)
```

**Edge Cases:**
- Empty list → `(False, None)`
- Single snapshot → `(False, None)`
- All same coverage → `(True, 2)` (stall at second iteration)

### 5.10 `build_learning_summary(lineage_dir, issue_number, outcome, final_coverage, target_coverage)`

**File:** `assemblyzero/workflows/testing/nodes/cleanup_helpers.py`

**Signature:**

```python
def build_learning_summary(
    lineage_dir: Path,
    issue_number: int,
    outcome: str,
    final_coverage: float,
    target_coverage: float,
) -> LearningSummaryData:
    """Build structured learning summary data from lineage artifacts."""
```

**Input Example:**

```python
lineage_dir = Path("/tmp/test-lineage/180-testing")
issue_number = 180
outcome = "SUCCESS"
final_coverage = 96.5
target_coverage = 95.0
```

**Output Example:**

```python
LearningSummaryData(
    issue_number=180,
    outcome="SUCCESS",
    final_coverage=96.5,
    target_coverage=95.0,
    total_iterations=3,
    stall_detected=False,
    stall_iteration=None,
    iteration_snapshots=[...],
    key_artifacts=[("001-lld.md", "LLD document"), ...],
    what_worked=["Coverage target achieved in 3 iterations"],
    what_didnt_work=[],
    recommendations=["No recommendations - workflow completed successfully"],
)
```

### 5.11 `render_learning_summary(data)`

**File:** `assemblyzero/workflows/testing/nodes/cleanup_helpers.py`

**Signature:**

```python
def render_learning_summary(data: LearningSummaryData) -> str:
    """Render LearningSummaryData to markdown string.

    The output format is versioned (Format Version: 1.0) for stable
    consumption by future learning agents.
    """
```

**Input Example:**

```python
data = LearningSummaryData(
    issue_number=180,
    outcome="SUCCESS",
    final_coverage=96.5,
    target_coverage=95.0,
    total_iterations=3,
    stall_detected=True,
    stall_iteration=2,
    iteration_snapshots=[
        IterationSnapshot(1, 72.0, ["cleanup.py:10-30"], ""),
        IterationSnapshot(2, 85.0, ["cleanup.py:42"], ""),
        IterationSnapshot(3, 96.5, [], ""),
    ],
    key_artifacts=[("001-lld.md", "Low-level design"), ("052-green-phase.txt", "Final green phase")],
    what_worked=["TDD loop converged in 3 iterations"],
    what_didnt_work=["Coverage stalled at iteration 2"],
    recommendations=["Split complex error handlers for testability"],
)
```

**Output Example:**

```markdown
# Learning Summary — Issue #180

## Format Version: 1.0

## Outcome

- **Result:** SUCCESS
- **Final Coverage:** 96.5%
- **Target Coverage:** 95.0%
- **Total Iterations:** 3

## Coverage Gap Analysis

| Iteration | Coverage | Missing Lines |
|-----------|----------|---------------|
| 1 | 72.0% | cleanup.py:10-30 |
| 2 | 85.0% | cleanup.py:42 |
| 3 | 96.5% | — |

## Stall Analysis

- **Stall detected:** Yes
- **Stall iteration:** 2

## Key Artifacts

| File | Description |
|------|-------------|
| 001-lld.md | Low-level design |
| 052-green-phase.txt | Final green phase |

## What Worked

- TDD loop converged in 3 iterations

## What Didn't Work

- Coverage stalled at iteration 2

## Recommendations

- Split complex error handlers for testability
```

### 5.12 `write_learning_summary(lineage_dir, content)`

**File:** `assemblyzero/workflows/testing/nodes/cleanup_helpers.py`

**Signature:**

```python
def write_learning_summary(lineage_dir: Path, content: str) -> Path:
    """Write learning summary markdown to the lineage directory.

    Returns Path to the written learning-summary.md file.
    """
```

**Input Example:**

```python
lineage_dir = Path("/home/user/Projects/AssemblyZero/docs/lineage/active/180-testing")
content = "# Learning Summary — Issue #180\n\n## Format Version: 1.0\n..."
```

**Output Example:**

```python
Path("/home/user/Projects/AssemblyZero/docs/lineage/active/180-testing/learning-summary.md")
```

## 6. Change Instructions

### 6.1 `assemblyzero/workflows/testing/state.py` (Modify)

**Change 1:** Update module docstring to reference Issue #180

```diff
 """State definition for TDD Testing Workflow.
 
 Issue #101: Test Plan Reviewer
 Issue #102: TDD Initialization
 Issue #93: N8 Documentation Node
 Issue #335: Scaffold validation fields
 Issue #147: Completeness gate fields (completeness_verdict, completeness_issues, review_materials)
 Issue #292: pytest_exit_code for exit code routing
+Issue #180: N9 Cleanup node fields (pr_url, pr_merged, learning_summary_path, cleanup_skipped_reason)
 
 This TypedDict travels through nodes N0-N8, tracking the testing workflow
-from LLD loading through test generation, implementation, E2E validation,
-and documentation generation.
+from LLD loading through test generation, implementation, E2E validation,
+documentation generation, and post-implementation cleanup.
 """
```

**Change 2:** Add new fields at the end of the `TestingWorkflowState` class body. Locate the last field definition in the class and add after it:

```diff
+    # === N9: Cleanup (Issue #180) ===
+    pr_url: str                    # GitHub PR URL (e.g., "https://github.com/org/repo/pull/42")
+    pr_merged: bool                # Set by N9 after checking PR merge status
+    learning_summary_path: str     # Absolute path to generated learning summary
+    cleanup_skipped_reason: str    # Reason cleanup was skipped (e.g., "PR not merged")
```

### 6.2 `assemblyzero/workflows/testing/nodes/cleanup_helpers.py` (Add)

**Complete file contents:**

```python
"""Helper functions for N9 cleanup node.

Issue #180: N9 Cleanup Node - Worktree Removal, Lineage Archival, and Learning Summary

Pure-function helpers that are independently testable without mocking
LangGraph state machinery. All subprocess calls use SUBPROCESS_TIMEOUT
to prevent hanging.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

SUBPROCESS_TIMEOUT: int = 10  # seconds — max wait for gh/git CLI calls


@dataclass
class IterationSnapshot:
    """Captures coverage data from a single TDD iteration."""

    iteration: int
    coverage_pct: float
    missing_lines: list[str] = field(default_factory=list)
    root_cause: str = ""


@dataclass
class LearningSummaryData:
    """Structured data extracted from lineage artifacts before rendering to markdown."""

    issue_number: int
    outcome: str
    final_coverage: float
    target_coverage: float
    total_iterations: int
    stall_detected: bool
    stall_iteration: int | None
    iteration_snapshots: list[IterationSnapshot] = field(default_factory=list)
    key_artifacts: list[tuple[str, str]] = field(default_factory=list)
    what_worked: list[str] = field(default_factory=list)
    what_didnt_work: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


def check_pr_merged(pr_url: str) -> bool:
    """Check if a GitHub PR is merged using gh CLI.

    Args:
        pr_url: Full GitHub PR URL.

    Returns:
        True if PR state is MERGED, False otherwise.

    Raises:
        subprocess.CalledProcessError: If gh CLI invocation fails.
        subprocess.TimeoutExpired: If gh CLI exceeds SUBPROCESS_TIMEOUT.
        ValueError: If pr_url is empty or malformed.
    """
    if not pr_url:
        raise ValueError("pr_url cannot be empty")
    if "github.com" not in pr_url:
        raise ValueError(f"Malformed PR URL: {pr_url}")

    result = subprocess.run(
        ["gh", "pr", "view", pr_url, "--json", "state", "--jq", ".state"],
        capture_output=True,
        text=True,
        check=True,
        timeout=SUBPROCESS_TIMEOUT,
    )
    return result.stdout.strip() == "MERGED"


def remove_worktree(worktree_path: str | Path) -> bool:
    """Remove a git worktree (without --force).

    Args:
        worktree_path: Absolute path to the worktree directory.

    Returns:
        True if worktree was removed successfully, False if it didn't exist.

    Raises:
        subprocess.CalledProcessError: If git worktree remove fails
            (e.g., dirty worktree).
        subprocess.TimeoutExpired: If git CLI exceeds SUBPROCESS_TIMEOUT.
    """
    worktree_path = Path(worktree_path)
    if not worktree_path.exists():
        logger.info("[N9] Worktree path does not exist: %s", worktree_path)
        return False

    subprocess.run(
        ["git", "worktree", "remove", str(worktree_path)],
        capture_output=True,
        text=True,
        check=True,
        timeout=SUBPROCESS_TIMEOUT,
    )
    logger.info("[N9] Worktree removed: %s", worktree_path)
    return True


def get_worktree_branch(worktree_path: str | Path) -> str | None:
    """Extract the branch name associated with a worktree.

    Args:
        worktree_path: Absolute path to the worktree directory.

    Returns:
        Branch name string, or None if worktree not found in git worktree list.

    Raises:
        subprocess.TimeoutExpired: If git CLI exceeds SUBPROCESS_TIMEOUT.
    """
    worktree_path = str(Path(worktree_path).resolve())

    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
        timeout=SUBPROCESS_TIMEOUT,
    )

    if result.returncode != 0:
        logger.warning("[N9] git worktree list failed: %s", result.stderr)
        return None

    # Parse porcelain output: blocks separated by blank lines
    current_worktree = None
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            current_worktree = line[len("worktree "):]
        elif line.startswith("branch ") and current_worktree == worktree_path:
            branch_ref = line[len("branch "):]
            # Strip refs/heads/ prefix
            if branch_ref.startswith("refs/heads/"):
                return branch_ref[len("refs/heads/"):]
            return branch_ref

    return None


def delete_local_branch(branch_name: str) -> bool:
    """Delete a local git branch using -D (force, for squash-merged branches).

    Args:
        branch_name: Name of the branch to delete.

    Returns:
        True if deleted, False if branch didn't exist.

    Raises:
        subprocess.CalledProcessError: If git branch -D fails for reasons
            other than branch-not-found.
        subprocess.TimeoutExpired: If git CLI exceeds SUBPROCESS_TIMEOUT.
    """
    try:
        subprocess.run(
            ["git", "branch", "-D", branch_name],
            capture_output=True,
            text=True,
            check=True,
            timeout=SUBPROCESS_TIMEOUT,
        )
        logger.info("[N9] Deleted local branch: %s", branch_name)
        return True
    except subprocess.CalledProcessError as exc:
        if "not found" in exc.stderr.lower() or "error: branch" in exc.stderr.lower():
            logger.info("[N9] Branch not found (already deleted?): %s", branch_name)
            return False
        raise


def archive_lineage(
    repo_root: Path,
    issue_number: int,
    lineage_suffix: str = "testing",
) -> Path | None:
    """Move lineage directory from active/ to done/.

    Args:
        repo_root: Path to the repository root.
        issue_number: GitHub issue number.
        lineage_suffix: Subdirectory suffix (default "testing").

    Returns:
        Path to the new done/ directory, or None if active dir didn't exist.

    Raises:
        OSError: If move operation fails.
    """
    dir_name = f"{issue_number}-{lineage_suffix}"
    active_dir = repo_root / "docs" / "lineage" / "active" / dir_name
    done_base = repo_root / "docs" / "lineage" / "done"

    if not active_dir.exists():
        logger.info("[N9] Active lineage dir not found: %s", active_dir)
        return None

    done_base.mkdir(parents=True, exist_ok=True)
    done_dir = done_base / dir_name

    if done_dir.exists():
        # Collision: append timestamp suffix
        timestamp = int(time.time())
        dir_name_ts = f"{dir_name}-{timestamp}"
        done_dir = done_base / dir_name_ts
        logger.warning(
            "[N9] done/ directory already exists, using suffix: %s", dir_name_ts
        )

    shutil.move(str(active_dir), str(done_dir))
    logger.info("[N9] Lineage archived: %s -> %s", active_dir, done_dir)
    return done_dir


def extract_iteration_data(lineage_dir: Path) -> list[IterationSnapshot]:
    """Parse lineage artifacts to extract per-iteration coverage data.

    Scans for files matching patterns like *green-phase*, *coverage*,
    *failed-response* to reconstruct the iteration history.

    Args:
        lineage_dir: Path to the lineage directory (active or done).

    Returns:
        List of IterationSnapshot in chronological order.
    """
    if not lineage_dir.exists():
        return []

    coverage_pattern = re.compile(r"[Cc]overage:\s*([\d.]+)%")
    alt_coverage_pattern = re.compile(r"([\d.]+)%\s*coverage")
    missing_pattern = re.compile(r"[Mm]issing(?:\s+lines)?:\s*(.+)")

    snapshots: list[IterationSnapshot] = []
    iteration = 0

    # Sort files by name for chronological ordering (numeric prefix)
    files = sorted(lineage_dir.iterdir())

    for file_path in files:
        if not file_path.is_file():
            continue

        name_lower = file_path.name.lower()
        if "green-phase" not in name_lower and "coverage" not in name_lower:
            continue

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        # Extract coverage percentage
        coverage_pct = 0.0
        match = coverage_pattern.search(content)
        if not match:
            match = alt_coverage_pattern.search(content)
        if match:
            try:
                coverage_pct = float(match.group(1))
            except ValueError:
                coverage_pct = 0.0

        # Extract missing lines
        missing_lines: list[str] = []
        missing_match = missing_pattern.search(content)
        if missing_match:
            missing_lines = [
                line.strip()
                for line in missing_match.group(1).split(",")
                if line.strip()
            ]

        iteration += 1
        snapshots.append(
            IterationSnapshot(
                iteration=iteration,
                coverage_pct=coverage_pct,
                missing_lines=missing_lines,
                root_cause="",
            )
        )

    return snapshots


def detect_stall(snapshots: list[IterationSnapshot]) -> tuple[bool, int | None]:
    """Detect if coverage stalled (same coverage for 2+ consecutive iterations).

    Args:
        snapshots: Ordered list of iteration snapshots.

    Returns:
        Tuple of (stall_detected, stall_iteration_number).
        stall_iteration_number is None if no stall detected.
    """
    if len(snapshots) < 2:
        return (False, None)

    for i in range(1, len(snapshots)):
        if snapshots[i].coverage_pct == snapshots[i - 1].coverage_pct:
            return (True, snapshots[i].iteration)

    return (False, None)


def build_learning_summary(
    lineage_dir: Path,
    issue_number: int,
    outcome: str,
    final_coverage: float,
    target_coverage: float,
) -> LearningSummaryData:
    """Build structured learning summary data from lineage artifacts.

    Args:
        lineage_dir: Path to the lineage directory.
        issue_number: GitHub issue number.
        outcome: "SUCCESS" or "FAILURE".
        final_coverage: Final test coverage percentage.
        target_coverage: Target coverage percentage.

    Returns:
        Populated LearningSummaryData instance.
    """
    snapshots = extract_iteration_data(lineage_dir)
    stall_detected, stall_iteration = detect_stall(snapshots)

    # Collect key artifacts
    key_artifacts: list[tuple[str, str]] = []
    if lineage_dir.exists():
        for f in sorted(lineage_dir.iterdir()):
            if f.is_file() and f.name != "learning-summary.md":
                # Infer description from filename
                name_lower = f.name.lower()
                if "lld" in name_lower:
                    desc = "LLD document"
                elif "scaffold" in name_lower or "test" in name_lower:
                    desc = "Test scaffold"
                elif "green" in name_lower:
                    desc = "Green phase output"
                elif "red" in name_lower:
                    desc = "Red phase output"
                elif "coverage" in name_lower:
                    desc = "Coverage report"
                elif "failed" in name_lower:
                    desc = "Failed response"
                else:
                    desc = "Artifact"
                key_artifacts.append((f.name, desc))

    # Generate what_worked / what_didnt_work / recommendations
    what_worked: list[str] = []
    what_didnt_work: list[str] = []
    recommendations: list[str] = []

    total_iterations = len(snapshots) if snapshots else 0

    if outcome == "SUCCESS":
        what_worked.append(
            f"Coverage target achieved ({final_coverage}% >= {target_coverage}%)"
        )
        if total_iterations > 0:
            what_worked.append(
                f"TDD loop converged in {total_iterations} iteration(s)"
            )
    else:
        what_didnt_work.append(
            f"Coverage target not met ({final_coverage}% < {target_coverage}%)"
        )

    if stall_detected and stall_iteration is not None:
        what_didnt_work.append(
            f"Coverage stalled at iteration {stall_iteration}"
        )
        recommendations.append(
            "Consider splitting complex functions for easier testing when coverage stalls"
        )

    if total_iterations >= 3:
        recommendations.append(
            "High iteration count — consider improving test scaffold specificity"
        )

    if not recommendations:
        recommendations.append(
            "No specific recommendations — workflow completed as expected"
        )

    return LearningSummaryData(
        issue_number=issue_number,
        outcome=outcome,
        final_coverage=final_coverage,
        target_coverage=target_coverage,
        total_iterations=total_iterations,
        stall_detected=stall_detected,
        stall_iteration=stall_iteration,
        iteration_snapshots=snapshots,
        key_artifacts=key_artifacts,
        what_worked=what_worked,
        what_didnt_work=what_didnt_work,
        recommendations=recommendations,
    )


def render_learning_summary(data: LearningSummaryData) -> str:
    """Render LearningSummaryData to markdown string.

    The output format is versioned (Format Version: 1.0) and documented
    for stable consumption by future learning agents.

    Args:
        data: Structured learning summary data.

    Returns:
        Complete markdown string for learning-summary.md.
    """
    lines: list[str] = []

    lines.append(f"# Learning Summary — Issue #{data.issue_number}")
    lines.append("")
    lines.append("## Format Version: 1.0")
    lines.append("")
    lines.append("## Outcome")
    lines.append("")
    lines.append(f"- **Result:** {data.outcome}")
    lines.append(f"- **Final Coverage:** {data.final_coverage}%")
    lines.append(f"- **Target Coverage:** {data.target_coverage}%")
    lines.append(f"- **Total Iterations:** {data.total_iterations}")
    lines.append("")

    # Coverage Gap Analysis
    lines.append("## Coverage Gap Analysis")
    lines.append("")
    if data.iteration_snapshots:
        lines.append("| Iteration | Coverage | Missing Lines |")
        lines.append("|-----------|----------|---------------|")
        for snap in data.iteration_snapshots:
            missing = ", ".join(snap.missing_lines) if snap.missing_lines else "—"
            lines.append(f"| {snap.iteration} | {snap.coverage_pct}% | {missing} |")
    else:
        lines.append("No iteration data available.")
    lines.append("")

    # Stall Analysis
    lines.append("## Stall Analysis")
    lines.append("")
    lines.append(f"- **Stall detected:** {'Yes' if data.stall_detected else 'No'}")
    if data.stall_detected and data.stall_iteration is not None:
        lines.append(f"- **Stall iteration:** {data.stall_iteration}")
    lines.append("")

    # Key Artifacts
    lines.append("## Key Artifacts")
    lines.append("")
    if data.key_artifacts:
        lines.append("| File | Description |")
        lines.append("|------|-------------|")
        for filename, desc in data.key_artifacts:
            lines.append(f"| {filename} | {desc} |")
    else:
        lines.append("No artifacts found.")
    lines.append("")

    # What Worked
    lines.append("## What Worked")
    lines.append("")
    if data.what_worked:
        for item in data.what_worked:
            lines.append(f"- {item}")
    else:
        lines.append("- (none recorded)")
    lines.append("")

    # What Didn't Work
    lines.append("## What Didn't Work")
    lines.append("")
    if data.what_didnt_work:
        for item in data.what_didnt_work:
            lines.append(f"- {item}")
    else:
        lines.append("- (none recorded)")
    lines.append("")

    # Recommendations
    lines.append("## Recommendations")
    lines.append("")
    if data.recommendations:
        for item in data.recommendations:
            lines.append(f"- {item}")
    else:
        lines.append("- (none)")
    lines.append("")

    return "\n".join(lines)


def write_learning_summary(lineage_dir: Path, content: str) -> Path:
    """Write learning summary markdown to the lineage directory.

    Args:
        lineage_dir: Path to the lineage directory (active/ or done/).
        content: Markdown content string.

    Returns:
        Path to the written learning-summary.md file.
    """
    summary_path = lineage_dir / "learning-summary.md"
    summary_path.write_text(content, encoding="utf-8")
    logger.info("[N9] Learning summary written to: %s", summary_path)
    return summary_path
```

### 6.3 `assemblyzero/workflows/testing/nodes/cleanup.py` (Add)

**Complete file contents:**

```python
"""N9 Cleanup Node for TDD Testing Workflow.

Issue #180: N9 Cleanup Node - Worktree Removal, Lineage Archival, and Learning Summary

Orchestrates three cleanup tasks:
1. Check PR merge status and remove worktree if merged
2. Generate learning summary in active lineage directory
3. Archive lineage from active/ to done/ ONLY if PR is merged
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

from assemblyzero.workflows.testing.nodes.cleanup_helpers import (
    archive_lineage,
    build_learning_summary,
    check_pr_merged,
    delete_local_branch,
    get_worktree_branch,
    remove_worktree,
    render_learning_summary,
    write_learning_summary,
)

logger = logging.getLogger(__name__)


def route_after_document(state: dict[str, Any]) -> str:
    """Conditional routing from N8 to N9 or END.

    Returns "N9_cleanup" if state has valid issue_number,
    otherwise returns "end".
    """
    issue_number = state.get("issue_number")
    if issue_number:
        logger.info("[N9] Routing to N9_cleanup (issue_number=%s)", issue_number)
        return "N9_cleanup"
    logger.info("[N9] No issue_number — routing to end")
    return "end"


def cleanup(state: dict[str, Any]) -> dict[str, Any]:
    """N9: Post-implementation cleanup node.

    Orchestrates three cleanup tasks:
    1. Check PR merge status and remove worktree if merged
    2. Generate learning summary in active lineage directory
    3. Archive lineage from active/ to done/ ONLY if PR is merged

    If PR is not merged, the learning summary is written into active/
    so developers can inspect it during iteration.

    Returns updated state fields: pr_merged, learning_summary_path,
    cleanup_skipped_reason.
    """
    logger.info("[N9] Starting cleanup node")

    # Extract state
    pr_url = state.get("pr_url", "")
    worktree_path = state.get("worktree_path", "")
    issue_number = state.get("issue_number", 0)
    repo_root_str = state.get("repo_root", "")
    final_coverage = state.get("final_coverage", 0.0)
    target_coverage = state.get("target_coverage", 0.0)
    outcome = state.get("outcome", "UNKNOWN")

    # Initialize return fields
    pr_merged = False
    learning_summary_path = ""
    cleanup_skipped_reason = ""

    repo_root = Path(repo_root_str) if repo_root_str else Path.cwd()

    # === 1. WORKTREE CLEANUP ===
    if pr_url:
        try:
            pr_merged = check_pr_merged(pr_url)
            logger.info("[N9] PR merge status: %s", "MERGED" if pr_merged else "NOT MERGED")

            if pr_merged and worktree_path:
                try:
                    branch = get_worktree_branch(worktree_path)
                    remove_worktree(worktree_path)
                    if branch:
                        delete_local_branch(branch)
                    logger.info("[N9] Worktree and branch cleaned up")
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                    logger.warning("[N9] Worktree cleanup failed: %s", exc)
            elif not pr_merged:
                cleanup_skipped_reason = "PR not yet merged"
                logger.info("[N9] Skipping worktree removal — PR not merged")
            else:
                logger.info("[N9] PR merged but no worktree_path in state")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError) as exc:
            logger.warning("[N9] PR merge check failed: %s", exc)
            cleanup_skipped_reason = f"PR merge check failed: {exc}"
    else:
        cleanup_skipped_reason = "No PR URL in state"
        logger.info("[N9] No PR URL — skipping worktree cleanup")

    # === 2. LEARNING SUMMARY (generated in active/ first) ===
    active_dir = (
        repo_root / "docs" / "lineage" / "active" / f"{issue_number}-testing"
    )

    if active_dir.exists():
        try:
            summary_data = build_learning_summary(
                active_dir, issue_number, outcome, final_coverage, target_coverage
            )
            markdown = render_learning_summary(summary_data)
            write_learning_summary(active_dir, markdown)
            logger.info("[N9] Learning summary written to active/")
        except Exception as exc:
            logger.warning("[N9] Learning summary generation failed: %s", exc)
    else:
        logger.info("[N9] No active lineage directory found — skipping summary generation")

    # === 3. LINEAGE ARCHIVAL (only if PR merged) ===
    if active_dir.exists() and pr_merged:
        try:
            done_dir = archive_lineage(repo_root, issue_number)
            if done_dir:
                learning_summary_path = str(done_dir / "learning-summary.md")
                logger.info("[N9] Lineage archived to done/")
            else:
                logger.warning("[N9] archive_lineage returned None unexpectedly")
        except Exception as exc:
            logger.warning("[N9] Lineage archival failed: %s", exc)
    elif active_dir.exists() and not pr_merged:
        learning_summary_path = str(active_dir / "learning-summary.md")
        logger.info(
            "[N9] Lineage kept in active/ (PR not merged) — summary available for inspection"
        )
    else:
        logger.info("[N9] No lineage directory available — skipping archival")

    logger.info("[N9] Cleanup complete")

    return {
        "pr_merged": pr_merged,
        "learning_summary_path": learning_summary_path,
        "cleanup_skipped_reason": cleanup_skipped_reason,
    }
```

### 6.4 `assemblyzero/workflows/testing/nodes/__init__.py` (Modify)

**Change 1:** Update module docstring to add N9

```diff
 """Node implementations for TDD Testing Workflow.
 
 Issue #101: Test Plan Reviewer
 Issue #102: TDD Initialization
 Issue #93: N8 Documentation Node
 Issue #147: Implementation Completeness Gate (N4b)
+Issue #180: N9 Cleanup Node
 
 Nodes:
 - N0: load_lld - Load LLD and extract test plan
 - N1: review_test_plan - Gemini reviews test plan coverage
 - N2: scaffold_tests - Generate executable test stubs
 - N3: verify_red_phase - Verify all tests fail
 - N4: implement_code - Claude generates implementation
 - N4b: completeness_gate - Verify implementation completeness
 - N5: verify_green_phase - Verify all tests pass
 - N6: e2e_validation - Run E2E tests in sandbox
 - N7: finalize - Generate reports and complete
 - N8: document - Auto-generate documentation artifacts
+- N9: cleanup - Post-implementation cleanup (worktree, lineage, summary)
 """
```

**Change 2:** Add import for cleanup module (insert alphabetically with existing imports — after `completeness_gate` import block):

```diff
 from assemblyzero.workflows.testing.nodes.completeness_gate import (
     completeness_gate,
 )
 
+from assemblyzero.workflows.testing.nodes.cleanup import (
+    cleanup,
+    route_after_document,
+)
+
 from assemblyzero.workflows.testing.nodes.document import document
```

### 6.5 `assemblyzero/workflows/testing/graph.py` (Modify)

**Change 1:** Update module docstring to reference N9 and Issue #180:

```diff
 """StateGraph definition for TDD Testing Workflow.
 
 Issue #101: Test Plan Reviewer
 Issue #102: TDD Initialization
 Issue #93: N8 Documentation Node
 Issue #335: Add mechanical test validation node (N2.5)
 Issue #147: Add completeness gate node (N4b) between N4 and N5
 Issue #292: Exit code routing — N3/N5 can route to N2 on syntax/collection errors
+Issue #180: Add cleanup node (N9) after N8
```

Update the graph structure ASCII art in the docstring to reflect N8→N9→END:

```diff
-    N5_verify_green -> N6_e2e_validation -> N7_finalize -> N8_document -> END
+    N5_verify_green -> N6_e2e_validation -> N7_finalize -> N8_document -> N9_cleanup -> END
            |                  |                  |               |
            v                  v                  v               v
-       iteration          skip_e2e           complete       skip_docs
+       iteration          skip_e2e           complete    route_after_doc
            |                  |                                  |
            v                  v                                 / \
-          N4                 N7                                 END
+          N4                 N7                            N9     END
+                                                          |
+                                                          v
+                                                         END
```

**Change 2:** Add import for cleanup and route_after_document:

```diff
 from assemblyzero.workflows.testing.nodes import (
+    cleanup,
     document,
     e2e_validation,
     finalize,
     implement_code,
     load_lld,
+    route_after_document,
     review_test_plan,
     scaffold_tests,
     verify_green_phase,
     verify_red_phase,
 )
```

**Change 3:** Inside `build_testing_workflow()`, add the N9 node and replace the N8→END edge. Locate the section where `N8_document` is added as a node and its outgoing edge is defined. The current code will have something like:

```python
# Current (approximate — locate actual line in the function body):
graph.add_node("N8_document", document)
# ... and the edge from N8:
graph.add_conditional_edges(
    "N8_document",
    route_after_finalize_docs,  # or direct edge to END
    ...
)
# OR:
graph.add_edge("N8_document", END)
```

Replace with:

```python
graph.add_node("N8_document", document)
graph.add_node("N9_cleanup", cleanup)

# N8 → conditional routing to N9 or END
graph.add_conditional_edges(
    "N8_document",
    route_after_document,
    {
        "N9_cleanup": "N9_cleanup",
        "end": END,
    },
)

# N9 → END
graph.add_edge("N9_cleanup", END)
```

**Note:** The exact modification depends on how N8's outgoing edge is currently defined. If N8 currently has a `route_after_finalize` or similar routing function, the `route_after_document` replaces it. If N8 has a direct edge to END, that direct edge is removed and replaced with the conditional edge above. Inspect the actual `build_testing_workflow` function body to identify the exact lines. The key changes are:
1. Add `graph.add_node("N9_cleanup", cleanup)` after the N8 node addition
2. Replace whatever edge goes from N8 to END with the conditional edges via `route_after_document`
3. Add `graph.add_edge("N9_cleanup", END)`

### 6.6 `tests/fixtures/mock_lineage/001-lld.md` (Add)

**Complete file contents:**

```markdown
# 180 - Feature: N9 Cleanup Node

## 1. Context & Goal

Mock LLD for testing lineage extraction.

## 2. Proposed Changes

- Add cleanup node
- Archive lineage

## 3. Requirements

1. Cleanup after merge
2. Generate learning summary
```

### 6.7 `tests/fixtures/mock_lineage/005-test-scaffold.py` (Add)

**Complete file contents:**

```python
"""Mock test scaffold for testing lineage extraction.

Issue #180: N9 Cleanup Node
"""


def test_placeholder():
    """Placeholder test."""
    assert True
```

### 6.8 `tests/fixtures/mock_lineage/052-green-phase.txt` (Add)

**Complete file contents:**

```
Green Phase - Iteration 1
=========================

All tests passing.

Coverage: 96.5%
Missing lines: src/cleanup.py:42, src/cleanup.py:55

Test Results:
  33 passed, 0 failed, 0 errors
```

### 6.9 `tests/unit/test_cleanup_helpers.py` (Add)

**Complete file contents:**

```python
"""Unit tests for N9 cleanup helper functions.

Issue #180: N9 Cleanup Node - Worktree Removal, Lineage Archival, and Learning Summary

Tests: T070–T260 from LLD Section 10.0
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.workflows.testing.nodes.cleanup_helpers import (
    SUBPROCESS_TIMEOUT,
    IterationSnapshot,
    LearningSummaryData,
    archive_lineage,
    build_learning_summary,
    check_pr_merged,
    delete_local_branch,
    detect_stall,
    extract_iteration_data,
    get_worktree_branch,
    remove_worktree,
    render_learning_summary,
    write_learning_summary,
)


# === T070: check_pr_merged returns True ===
class TestCheckPrMerged:
    @patch("assemblyzero.workflows.testing.nodes.cleanup_helpers.subprocess.run")
    def test_check_pr_merged_returns_true(self, mock_run: MagicMock) -> None:
        """T070: gh returns MERGED state."""
        mock_run.return_value = MagicMock(
            stdout="MERGED\n", stderr="", returncode=0
        )
        result = check_pr_merged(
            "https://github.com/martymcenroe/AssemblyZero/pull/42"
        )
        assert result is True
        mock_run.assert_called_once_with(
            [
                "gh", "pr", "view",
                "https://github.com/martymcenroe/AssemblyZero/pull/42",
                "--json", "state", "--jq", ".state",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=SUBPROCESS_TIMEOUT,
        )

    # === T080: check_pr_merged returns False for OPEN ===
    @patch("assemblyzero.workflows.testing.nodes.cleanup_helpers.subprocess.run")
    def test_check_pr_merged_returns_false_open(self, mock_run: MagicMock) -> None:
        """T080: gh returns OPEN state."""
        mock_run.return_value = MagicMock(
            stdout="OPEN\n", stderr="", returncode=0
        )
        result = check_pr_merged(
            "https://github.com/martymcenroe/AssemblyZero/pull/42"
        )
        assert result is False

    # === T090: check_pr_merged invalid URL ===
    def test_check_pr_merged_invalid_url_empty(self) -> None:
        """T090: ValueError raised for empty URL."""
        with pytest.raises(ValueError, match="pr_url cannot be empty"):
            check_pr_merged("")

    def test_check_pr_merged_invalid_url_malformed(self) -> None:
        """T090: ValueError raised for malformed URL."""
        with pytest.raises(ValueError, match="Malformed PR URL"):
            check_pr_merged("not-a-url")

    # === T095: check_pr_merged timeout ===
    @patch("assemblyzero.workflows.testing.nodes.cleanup_helpers.subprocess.run")
    def test_check_pr_merged_timeout(self, mock_run: MagicMock) -> None:
        """T095: TimeoutExpired raised after 10s."""
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd=["gh"], timeout=SUBPROCESS_TIMEOUT
        )
        with pytest.raises(subprocess.TimeoutExpired):
            check_pr_merged(
                "https://github.com/martymcenroe/AssemblyZero/pull/42"
            )


# === T100/T110: remove_worktree ===
class TestRemoveWorktree:
    @patch("assemblyzero.workflows.testing.nodes.cleanup_helpers.subprocess.run")
    def test_remove_worktree_success(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """T100: git worktree remove succeeds, returns True."""
        worktree_dir = tmp_path / "worktree"
        worktree_dir.mkdir()
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = remove_worktree(worktree_dir)
        assert result is True
        mock_run.assert_called_once_with(
            ["git", "worktree", "remove", str(worktree_dir)],
            capture_output=True,
            text=True,
            check=True,
            timeout=SUBPROCESS_TIMEOUT,
        )

    def test_remove_worktree_nonexistent(self, tmp_path: Path) -> None:
        """T110: Worktree path doesn't exist, returns False."""
        result = remove_worktree(tmp_path / "nonexistent")
        assert result is False


# === T120/T130: get_worktree_branch ===
class TestGetWorktreeBranch:
    @patch("assemblyzero.workflows.testing.nodes.cleanup_helpers.subprocess.run")
    def test_get_worktree_branch_found(self, mock_run: MagicMock) -> None:
        """T120: Extracts branch name from git worktree list."""
        porcelain_output = (
            "worktree /home/user/Projects/AssemblyZero\n"
            "HEAD abc123\n"
            "branch refs/heads/main\n"
            "\n"
            "worktree /home/user/Projects/AssemblyZero-180\n"
            "HEAD def456\n"
            "branch refs/heads/issue-180-cleanup\n"
            "\n"
        )
        mock_run.return_value = MagicMock(
            stdout=porcelain_output, stderr="", returncode=0
        )
        result = get_worktree_branch("/home/user/Projects/AssemblyZero-180")
        assert result == "issue-180-cleanup"

    @patch("assemblyzero.workflows.testing.nodes.cleanup_helpers.subprocess.run")
    def test_get_worktree_branch_not_found(self, mock_run: MagicMock) -> None:
        """T130: Returns None for unknown path."""
        porcelain_output = (
            "worktree /home/user/Projects/AssemblyZero\n"
            "HEAD abc123\n"
            "branch refs/heads/main\n"
            "\n"
        )
        mock_run.return_value = MagicMock(
            stdout=porcelain_output, stderr="", returncode=0
        )
        result = get_worktree_branch("/home/user/Projects/unknown-worktree")
        assert result is None


# === T140/T150: delete_local_branch ===
class TestDeleteLocalBranch:
    @patch("assemblyzero.workflows.testing.nodes.cleanup_helpers.subprocess.run")
    def test_delete_local_branch_success(self, mock_run: MagicMock) -> None:
        """T140: git branch -D succeeds, returns True."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = delete_local_branch("issue-180-cleanup")
        assert result is True
        mock_run.assert_called_once_with(
            ["git", "branch", "-D", "issue-180-cleanup"],
            capture_output=True,
            text=True,
            check=True,
            timeout=SUBPROCESS_TIMEOUT,
        )

    @patch("assemblyzero.workflows.testing.nodes.cleanup_helpers.subprocess.run")
    def test_delete_local_branch_not_found(self, mock_run: MagicMock) -> None:
        """T150: Branch doesn't exist, returns False."""
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["git", "branch", "-D", "nonexistent"],
            stderr="error: branch 'nonexistent' not found.",
        )
        result = delete_local_branch("nonexistent")
        assert result is False


# === T160/T170/T180: archive_lineage ===
class TestArchiveLineage:
    def test_archive_lineage_moves_directory(self, tmp_path: Path) -> None:
        """T160: active/ moved to done/, returns done path."""
        repo_root = tmp_path / "repo"
        active_dir = repo_root / "docs" / "lineage" / "active" / "180-testing"
        active_dir.mkdir(parents=True)
        (active_dir / "001-lld.md").write_text("# LLD")

        result = archive_lineage(repo_root, 180)

        expected = repo_root / "docs" / "lineage" / "done" / "180-testing"
        assert result == expected
        assert expected.exists()
        assert (expected / "001-lld.md").read_text() == "# LLD"
        assert not active_dir.exists()

    def test_archive_lineage_active_not_found(self, tmp_path: Path) -> None:
        """T170: Returns None, no error."""
        result = archive_lineage(tmp_path, 999)
        assert result is None

    def test_archive_lineage_done_already_exists(self, tmp_path: Path) -> None:
        """T180: Appends timestamp suffix to avoid collision."""
        repo_root = tmp_path / "repo"
        active_dir = repo_root / "docs" / "lineage" / "active" / "180-testing"
        active_dir.mkdir(parents=True)
        (active_dir / "file.txt").write_text("data")

        # Pre-create done/ to cause collision
        done_dir = repo_root / "docs" / "lineage" / "done" / "180-testing"
        done_dir.mkdir(parents=True)

        result = archive_lineage(repo_root, 180)

        assert result is not None
        assert result != done_dir  # Different path (has timestamp suffix)
        assert result.exists()
        assert "180-testing-" in result.name
        assert not active_dir.exists()


# === T190/T200: extract_iteration_data ===
class TestExtractIterationData:
    def test_extract_iteration_data_parses_green_phase(
        self, tmp_path: Path
    ) -> None:
        """T190: Parses coverage from green-phase files."""
        lineage_dir = tmp_path / "180-testing"
        lineage_dir.mkdir()
        (lineage_dir / "052-green-phase.txt").write_text(
            "Green Phase\nCoverage: 98.5%\nMissing lines: src/x.py:10, src/x.py:20"
        )

        result = extract_iteration_data(lineage_dir)

        assert len(result) == 1
        assert result[0].iteration == 1
        assert result[0].coverage_pct == 98.5
        assert result[0].missing_lines == ["src/x.py:10", "src/x.py:20"]

    def test_extract_iteration_data_empty_dir(self, tmp_path: Path) -> None:
        """T200: Returns empty list for empty directory."""
        lineage_dir = tmp_path / "180-testing"
        lineage_dir.mkdir()

        result = extract_iteration_data(lineage_dir)
        assert result == []

    def test_extract_iteration_data_nonexistent_dir(self, tmp_path: Path) -> None:
        """Returns empty list for nonexistent directory."""
        result = extract_iteration_data(tmp_path / "nonexistent")
        assert result == []


# === T210/T220: detect_stall ===
class TestDetectStall:
    def test_detect_stall_found(self) -> None:
        """T210: Detects consecutive equal coverage."""
        snapshots = [
            IterationSnapshot(iteration=1, coverage_pct=85.0),
            IterationSnapshot(iteration=2, coverage_pct=85.0),
            IterationSnapshot(iteration=3, coverage_pct=88.0),
        ]
        result = detect_stall(snapshots)
        assert result == (True, 2)

    def test_detect_stall_not_found(self) -> None:
        """T220: Returns (False, None) for monotonic increase."""
        snapshots = [
            IterationSnapshot(iteration=1, coverage_pct=80.0),
            IterationSnapshot(iteration=2, coverage_pct=85.0),
            IterationSnapshot(iteration=3, coverage_pct=90.0),
            IterationSnapshot(iteration=4, coverage_pct=95.0),
        ]
        result = detect_stall(snapshots)
        assert result == (False, None)

    def test_detect_stall_empty(self) -> None:
        """Empty list returns no stall."""
        assert detect_stall([]) == (False, None)

    def test_detect_stall_single(self) -> None:
        """Single snapshot returns no stall."""
        assert detect_stall([IterationSnapshot(1, 80.0)]) == (False, None)


# === T230: build_learning_summary ===
class TestBuildLearningSummary:
    def test_build_learning_summary_full(self, tmp_path: Path) -> None:
        """T230: Builds complete LearningSummaryData from fixtures."""
        lineage_dir = tmp_path / "180-testing"
        lineage_dir.mkdir()
        (lineage_dir / "001-lld.md").write_text("# LLD")
        (lineage_dir / "005-test-scaffold.py").write_text("def test(): pass")
        (lineage_dir / "052-green-phase.txt").write_text(
            "Coverage: 96.5%\nMissing lines: cleanup.py:42"
        )

        result = build_learning_summary(
            lineage_dir,
            issue_number=180,
            outcome="SUCCESS",
            final_coverage=96.5,
            target_coverage=95.0,
        )

        assert result.issue_number == 180
        assert result.outcome == "SUCCESS"
        assert result.final_coverage == 96.5
        assert result.target_coverage == 95.0
        assert result.total_iterations == 1
        assert len(result.key_artifacts) == 3  # lld, scaffold, green-phase
        assert len(result.what_worked) > 0
        assert len(result.recommendations) > 0


# === T240/T250: render_learning_summary ===
class TestRenderLearningSummary:
    def test_render_learning_summary_markdown(self) -> None:
        """T240: Renders all sections to valid markdown including version header."""
        data = LearningSummaryData(
            issue_number=180,
            outcome="SUCCESS",
            final_coverage=96.5,
            target_coverage=95.0,
            total_iterations=3,
            stall_detected=False,
            stall_iteration=None,
            iteration_snapshots=[
                IterationSnapshot(1, 72.0, ["cleanup.py:10-30"], ""),
                IterationSnapshot(2, 85.0, ["cleanup.py:42"], ""),
                IterationSnapshot(3, 96.5, [], ""),
            ],
            key_artifacts=[("001-lld.md", "LLD document")],
            what_worked=["TDD loop converged"],
            what_didnt_work=[],
            recommendations=["No recommendations"],
        )

        result = render_learning_summary(data)

        assert "# Learning Summary — Issue #180" in result
        assert "## Format Version: 1.0" in result
        assert "## Outcome" in result
        assert "## Coverage Gap Analysis" in result
        assert "## Stall Analysis" in result
        assert "## Key Artifacts" in result
        assert "## What Worked" in result
        assert "## What Didn't Work" in result
        assert "## Recommendations" in result
        assert "96.5%" in result
        assert "SUCCESS" in result

    def test_render_learning_summary_with_stall(self) -> None:
        """T250: Stall info included in rendered output."""
        data = LearningSummaryData(
            issue_number=42,
            outcome="FAILURE",
            final_coverage=85.0,
            target_coverage=95.0,
            total_iterations=3,
            stall_detected=True,
            stall_iteration=2,
            iteration_snapshots=[
                IterationSnapshot(1, 85.0),
                IterationSnapshot(2, 85.0),
                IterationSnapshot(3, 85.0),
            ],
            key_artifacts=[],
            what_worked=[],
            what_didnt_work=["Coverage stalled"],
            recommendations=["Split functions"],
        )

        result = render_learning_summary(data)

        assert "Stall detected:** Yes" in result
        assert "Stall iteration:** 2" in result


# === T260: write_learning_summary ===
class TestWriteLearningSummary:
    def test_write_learning_summary_creates_file(self, tmp_path: Path) -> None:
        """T260: File written to correct path."""
        lineage_dir = tmp_path / "180-testing"
        lineage_dir.mkdir()
        content = "# Learning Summary — Issue #180\n\n## Format Version: 1.0\n"

        result = write_learning_summary(lineage_dir, content)

        expected_path = lineage_dir / "learning-summary.md"
        assert result == expected_path
        assert expected_path.exists()
        assert expected_path.read_text() == content
```

### 6.10 `tests/unit/test_cleanup.py` (Add)

**Complete file contents:**

```python
"""Unit tests for N9 cleanup node.

Issue #180: N9 Cleanup Node - Worktree Removal, Lineage Archival, and Learning Summary

Tests: T010–T040, T050–T060, T270–T320 from LLD Section 10.0
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.workflows.testing.nodes.cleanup import (
    cleanup,
    route_after_document,
)


# === T280/T290: route_after_document ===
class TestRouteAfterDocument:
    def test_route_has_issue(self) -> None:
        """T280: Returns 'N9_cleanup' when issue_number present."""
        state: dict[str, Any] = {"issue_number": 180}
        assert route_after_document(state) == "N9_cleanup"

    def test_route_no_issue(self) -> None:
        """T290: Returns 'end' when no issue_number."""
        state: dict[str, Any] = {"lld_content": "something"}
        assert route_after_document(state) == "end"

    def test_route_issue_zero(self) -> None:
        """Returns 'end' when issue_number is 0 (falsy)."""
        state: dict[str, Any] = {"issue_number": 0}
        assert route_after_document(state) == "end"

    def test_route_issue_none(self) -> None:
        """Returns 'end' when issue_number is None."""
        state: dict[str, Any] = {"issue_number": None}
        assert route_after_document(state) == "end"


# === T010: N9 node wired in graph ===
class TestGraphWiring:
    def test_cleanup_node_wired_in_graph(self) -> None:
        """T010: N9_cleanup node present in graph with correct edges."""
        from assemblyzero.workflows.testing.graph import build_testing_workflow

        graph = build_testing_workflow()
        compiled = graph.compile()

        # Check node exists
        node_names = [n for n in compiled.get_graph().nodes]
        assert "N9_cleanup" in node_names

        # Check edges exist: N8 -> N9 (via conditional), N9 -> END
        edges = compiled.get_graph().edges
        # N9 -> __end__ edge
        n9_to_end = any(
            e.source == "N9_cleanup" and e.target == "__end__"
            for e in edges
        )
        assert n9_to_end, f"Expected N9->END edge. Edges: {edges}"


# === T020: Happy path — PR merged ===
class TestCleanupHappyPath:
    @patch("assemblyzero.workflows.testing.nodes.cleanup.archive_lineage")
    @patch("assemblyzero.workflows.testing.nodes.cleanup.write_learning_summary")
    @patch("assemblyzero.workflows.testing.nodes.cleanup.render_learning_summary")
    @patch("assemblyzero.workflows.testing.nodes.cleanup.build_learning_summary")
    @patch("assemblyzero.workflows.testing.nodes.cleanup.delete_local_branch")
    @patch("assemblyzero.workflows.testing.nodes.cleanup.get_worktree_branch")
    @patch("assemblyzero.workflows.testing.nodes.cleanup.remove_worktree")
    @patch("assemblyzero.workflows.testing.nodes.cleanup.check_pr_merged")
    def test_cleanup_happy_path_pr_merged(
        self,
        mock_check: MagicMock,
        mock_remove_wt: MagicMock,
        mock_get_branch: MagicMock,
        mock_del_branch: MagicMock,
        mock_build: MagicMock,
        mock_render: MagicMock,
        mock_write: MagicMock,
        mock_archive: MagicMock,
        tmp_path: Path,
    ) -> None:
        """T020: Full cleanup: worktree removed, summary in active/, lineage archived."""
        # Set up active lineage dir
        repo_root = tmp_path / "repo"
        active_dir = repo_root / "docs" / "lineage" / "active" / "180-testing"
        active_dir.mkdir(parents=True)
        (active_dir / "001-lld.md").write_text("# LLD")

        done_dir = repo_root / "docs" / "lineage" / "done" / "180-testing"

        mock_check.return_value = True
        mock_get_branch.return_value = "issue-180-cleanup"
        mock_remove_wt.return_value = True
        mock_del_branch.return_value = True
        mock_build.return_value = MagicMock()
        mock_render.return_value = "# Summary"
        mock_write.return_value = active_dir / "learning-summary.md"
        mock_archive.return_value = done_dir

        state: dict[str, Any] = {
            "issue_number": 180,
            "pr_url": "https://github.com/martymcenroe/AssemblyZero/pull/42",
            "worktree_path": str(tmp_path / "worktree"),
            "repo_root": str(repo_root),
            "final_coverage": 96.5,
            "target_coverage": 95.0,
            "outcome": "SUCCESS",
        }

        result = cleanup(state)

        assert result["pr_merged"] is True
        assert "done" in result["learning_summary_path"]
        assert result["cleanup_skipped_reason"] == ""
        mock_check.assert_called_once()
        mock_remove_wt.assert_called_once()
        mock_del_branch.assert_called_once_with("issue-180-cleanup")
        mock_build.assert_called_once()
        mock_archive.assert_called_once()


# === T030: PR not merged ===
class TestCleanupPrNotMerged:
    @patch("assemblyzero.workflows.testing.nodes.cleanup.check_pr_merged")
    def test_cleanup_pr_not_merged_skips_worktree_keeps_active(
        self, mock_check: MagicMock, tmp_path: Path
    ) -> None:
        """T030: Worktree preserved, summary in active/, lineage NOT archived."""
        repo_root = tmp_path / "repo"
        active_dir = repo_root / "docs" / "lineage" / "active" / "180-testing"
        active_dir.mkdir(parents=True)
        (active_dir / "052-green-phase.txt").write_text("Coverage: 96.5%")

        mock_check.return_value = False

        state: dict[str, Any] = {
            "issue_number": 180,
            "pr_url": "https://github.com/martymcenroe/AssemblyZero/pull/42",
            "worktree_path": str(tmp_path / "worktree"),
            "repo_root": str(repo_root),
            "final_coverage": 96.5,
            "target_coverage": 95.0,
            "outcome": "SUCCESS",
        }

        result = cleanup(state)

        assert result["pr_merged"] is False
        assert "active" in result["learning_summary_path"]
        assert result["cleanup_skipped_reason"] == "PR not yet merged"
        # Verify summary was written in active
        assert (active_dir / "learning-summary.md").exists()
        # Verify lineage NOT moved
        assert active_dir.exists()


# === T040: No pr_url ===
class TestCleanupNoPrUrl:
    def test_cleanup_no_pr_url_skips_worktree(self, tmp_path: Path) -> None:
        """T040: No PR URL in state, worktree skipped gracefully."""
        repo_root = tmp_path / "repo"
        active_dir = repo_root / "docs" / "lineage" / "active" / "180-testing"
        active_dir.mkdir(parents=True)

        state: dict[str, Any] = {
            "issue_number": 180,
            "repo_root": str(repo_root),
            "final_coverage": 96.5,
            "target_coverage": 95.0,
            "outcome": "SUCCESS",
        }

        result = cleanup(state)

        assert result["pr_merged"] is False
        assert result["cleanup_skipped_reason"] == "No PR URL in state"


# === T050: No lineage directory ===
class TestCleanupNoLineageDir:
    @patch("assemblyzero.workflows.testing.nodes.cleanup.check_pr_merged")
    def test_cleanup_no_lineage_dir_skips_archival(
        self, mock_check: MagicMock, tmp_path: Path
    ) -> None:
        """T050: Missing active/ dir, summary skipped, no error."""
        mock_check.return_value = True

        state: dict[str, Any] = {
            "issue_number": 999,
            "pr_url": "https://github.com/martymcenroe/AssemblyZero/pull/42",
            "repo_root": str(tmp_path),
            "final_coverage": 96.5,
            "target_coverage": 95.0,
            "outcome": "SUCCESS",
        }

        result = cleanup(state)

        assert result["pr_merged"] is True
        assert result["learning_summary_path"] == ""


# === T060: Dirty worktree ===
class TestCleanupDirtyWorktree:
    @patch("assemblyzero.workflows.testing.nodes.cleanup.remove_worktree")
    @patch("assemblyzero.workflows.testing.nodes.cleanup.get_worktree_branch")
    @patch("assemblyzero.workflows.testing.nodes.cleanup.check_pr_merged")
    def test_cleanup_worktree_dirty_skips_removal(
        self,
        mock_check: MagicMock,
        mock_get_branch: MagicMock,
        mock_remove_wt: MagicMock,
        tmp_path: Path,
    ) -> None:
        """T060: Dirty worktree not force-removed, logged."""
        mock_check.return_value = True
        mock_get_branch.return_value = "issue-180-cleanup"
        mock_remove_wt.side_effect = subprocess.CalledProcessError(
            returncode=128,
            cmd=["git", "worktree", "remove"],
            stderr="fatal: 'path' contains modified or untracked files",
        )

        repo_root = tmp_path / "repo"
        active_dir = repo_root / "docs" / "lineage" / "active" / "180-testing"
        active_dir.mkdir(parents=True)

        state: dict[str, Any] = {
            "issue_number": 180,
            "pr_url": "https://github.com/martymcenroe/AssemblyZero/pull/42",
            "worktree_path": str(tmp_path / "dirty-worktree"),
            "repo_root": str(repo_root),
            "final_coverage": 96.5,
            "target_coverage": 95.0,
            "outcome": "SUCCESS",
        }

        # Should not raise — error caught gracefully
        result = cleanup(state)
        assert result["pr_merged"] is True


# === T270: All subprocess errors caught ===
class TestCleanupErrorHandling:
    @patch("assemblyzero.workflows.testing.nodes.cleanup.check_pr_merged")
    def test_cleanup_all_errors_caught(
        self, mock_check: MagicMock, tmp_path: Path
    ) -> None:
        """T270: Subprocess errors and timeouts logged, not raised."""
        mock_check.side_effect = subprocess.TimeoutExpired(
            cmd=["gh"], timeout=10
        )

        state: dict[str, Any] = {
            "issue_number": 180,
            "pr_url": "https://github.com/martymcenroe/AssemblyZero/pull/42",
            "repo_root": str(tmp_path),
            "final_coverage": 0.0,
            "target_coverage": 95.0,
            "outcome": "FAILURE",
        }

        # Should not raise
        result = cleanup(state)
        assert "cleanup_skipped_reason" in result
        assert "failed" in result["cleanup_skipped_reason"].lower() or "timeout" in result["cleanup_skipped_reason"].lower()

    @patch("assemblyzero.workflows.testing.nodes.cleanup.check_pr_merged")
    def test_cleanup_called_process_error_caught(
        self, mock_check: MagicMock, tmp_path: Path
    ) -> None:
        """T270b: CalledProcessError caught and logged."""
        mock_check.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd=["gh"], stderr="not found"
        )

        state: dict[str, Any] = {
            "issue_number": 180,
            "pr_url": "https://github.com/martymcenroe/AssemblyZero/pull/42",
            "repo_root": str(tmp_path),
            "final_coverage": 0.0,
            "target_coverage": 95.0,
            "outcome": "FAILURE",
        }

        result = cleanup(state)
        assert result["pr_merged"] is False
        assert result["cleanup_skipped_reason"] != ""


# === T300: State fields updated correctly ===
class TestCleanupStateFields:
    @patch("assemblyzero.workflows.testing.nodes.cleanup.check_pr_merged")
    def test_cleanup_state_fields_updated(
        self, mock_check: MagicMock, tmp_path: Path
    ) -> None:
        """T300: State contains pr_merged, learning_summary_path, cleanup_skipped_reason."""
        mock_check.return_value = False

        repo_root = tmp_path / "repo"
        active_dir = repo_root / "docs" / "lineage" / "active" / "180-testing"
        active_dir.mkdir(parents=True)
        (active_dir / "052-green-phase.txt").write_text("Coverage: 96.5%")

        state: dict[str, Any] = {
            "issue_number": 180,
            "pr_url": "https://github.com/martymcenroe/AssemblyZero/pull/42",
            "repo_root": str(repo_root),
            "final_coverage": 96.5,
            "target_coverage": 95.0,
            "outcome": "SUCCESS",
        }

        result = cleanup(state)

        assert "pr_merged" in result
        assert isinstance(result["pr_merged"], bool)
        assert "learning_summary_path" in result
        assert isinstance(result["learning_summary_path"], str)
        assert "cleanup_skipped_reason" in result
        assert isinstance(result["cleanup_skipped_reason"], str)


# === T310: PR not merged, summary in active ===
class TestCleanupSummaryPaths:
    @patch("assemblyzero.workflows.testing.nodes.cleanup.check_pr_merged")
    def test_cleanup_pr_not_merged_summary_in_active(
        self, mock_check: MagicMock, tmp_path: Path
    ) -> None:
        """T310: When PR not merged, learning_summary_path points to active/."""
        mock_check.return_value = False

        repo_root = tmp_path / "repo"
        active_dir = repo_root / "docs" / "lineage" / "active" / "180-testing"
        active_dir.mkdir(parents=True)
        (active_dir / "052-green-phase.txt").write_text("Coverage: 96.5%")

        state: dict[str, Any] = {
            "issue_number": 180,
            "pr_url": "https://github.com/martymcenroe/AssemblyZero/pull/42",
            "repo_root": str(repo_root),
            "final_coverage": 96.5,
            "target_coverage": 95.0,
            "outcome": "SUCCESS",
        }

        result = cleanup(state)
        assert "/active/" in result["learning_summary_path"]

    # === T320: PR merged, summary in done ===
    @patch("assemblyzero.workflows.testing.nodes.cleanup.archive_lineage")
    @patch("assemblyzero.workflows.testing.nodes.cleanup.write_learning_summary")
    @patch("assemblyzero.workflows.testing.nodes.cleanup.render_learning_summary")
    @patch("assemblyzero.workflows.testing.nodes.cleanup.build_learning_summary")
    @patch("assemblyzero.workflows.testing.nodes.cleanup.delete_local_branch")
    @patch("assemblyzero.workflows.testing.nodes.cleanup.get_worktree_branch")
    @patch("assemblyzero.workflows.testing.nodes.cleanup.remove_worktree")
    @patch("assemblyzero.workflows.testing.nodes.cleanup.check_pr_merged")
    def test_cleanup_pr_merged_summary_in_done(
        self,
        mock_check: MagicMock,
        mock_remove_wt: MagicMock,
        mock_get_branch: MagicMock,
        mock_del_branch: MagicMock,
        mock_build: MagicMock,
        mock_render: MagicMock,
        mock_write: MagicMock,
        mock_archive: MagicMock,
        tmp_path: Path,
    ) -> None:
        """T320: When PR merged, learning_summary_path points to done/."""
        repo_root = tmp_path / "repo"
        active_dir = repo_root / "docs" / "lineage" / "active" / "180-testing"
        active_dir.mkdir(parents=True)
        (active_dir / "001-lld.md").write_text("# LLD")

        done_dir = repo_root / "docs" / "lineage" / "done" / "180-testing"

        mock_check.return_value = True
        mock_get_branch.return_value = "issue-180"
        mock_remove_wt.return_value = True
        mock_del_branch.return_value = True
        mock_build.return_value = MagicMock()
        mock_render.return_value = "# Summary"
        mock_write.return_value = active_dir / "learning-summary.md"
        mock_archive.return_value = done_dir

        state: dict[str, Any] = {
            "issue_number": 180,
            "pr_url": "https://github.com/martymcenroe/AssemblyZero/pull/42",
            "worktree_path": str(tmp_path / "worktree"),
            "repo_root": str(repo_root),
            "final_coverage": 96.5,
            "target_coverage": 95.0,
            "outcome": "SUCCESS",
        }

        result = cleanup(state)
        assert "/done/" in result["learning_summary_path"]
```

## 7. Pattern References

### 7.1 Node Implementation Pattern (State Extraction + Return)

**File:** `assemblyzero/workflows/implementation_spec/nodes/analyze_codebase.py` (lines 1-50)

```python
# Pattern: Node function that extracts from state dict, does work, returns updated fields
def analyze_codebase(state: dict[str, Any]) -> dict[str, Any]:
    """Analyze the codebase for the implementation spec."""
    issue_number = state.get("issue_number", 0)
    lld_content = state.get("lld_content", "")
    # ... do work ...
    return {
        "codebase_analysis": analysis_result,
        "error_message": "",
    }
```

**Relevance:** The `cleanup()` node follows this exact pattern — extract state fields, perform operations, return a dict with updated fields. The framework handles state merging.

### 7.2 Graph Construction Pattern (Conditional Edges)

**File:** `assemblyzero/workflows/testing/graph.py` (lines containing `add_conditional_edges`)

```python
# Pattern: Conditional routing via a function that returns string keys
graph.add_conditional_edges(
    "N7_finalize",
    route_after_finalize,
    {
        "N8_document": "N8_document",
        "end": END,
    },
)
```

**Relevance:** The N8→N9 conditional edge follows this identical pattern. `route_after_document` returns either `"N9_cleanup"` or `"end"`, mapped to the corresponding node or END.

### 7.3 State Definition Pattern (TypedDict with total=False)

**File:** `assemblyzero/workflows/testing/state.py`

```python
class TestingWorkflowState(TypedDict, total=False):
    # All fields are optional (total=False)
    issue_number: int
    lld_content: str
    # ... more fields ...
```

**Relevance:** New fields (`pr_url`, `pr_merged`, `learning_summary_path`, `cleanup_skipped_reason`) follow the same optional-field pattern.

### 7.4 Node Export Pattern (__init__.py)

**File:** `assemblyzero/workflows/testing/nodes/__init__.py`

```python
from assemblyzero.workflows.testing.nodes.completeness_gate import (
    completeness_gate,
)
```

**Relevance:** The cleanup import follows this same pattern — import the function from the module, making it available via `from assemblyzero.workflows.testing.nodes import cleanup`.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from __future__ import annotations` | stdlib | `cleanup.py`, `cleanup_helpers.py`, both test files |
| `import json` | stdlib | `cleanup_helpers.py` (imported but used for potential future JSON parsing) |
| `import logging` | stdlib | `cleanup.py`, `cleanup_helpers.py` |
| `import re` | stdlib | `cleanup_helpers.py` |
| `import shutil` | stdlib | `cleanup_helpers.py` |
| `import subprocess` | stdlib | `cleanup_helpers.py`, `cleanup.py` |
| `import time` | stdlib | `cleanup_helpers.py` |
| `from dataclasses import dataclass, field` | stdlib | `cleanup_helpers.py` |
| `from pathlib import Path` | stdlib | `cleanup.py`, `cleanup_helpers.py` |
| `from typing import Any` | stdlib | `cleanup.py` |
| `from assemblyzero.workflows.testing.nodes.cleanup_helpers import (...)` | internal | `cleanup.py` |
| `from assemblyzero.workflows.testing.nodes.cleanup import cleanup, route_after_document` | internal | `__init__.py`, `graph.py` |
| `from langgraph.graph import END, StateGraph` | langgraph | `graph.py` (existing) |
| `import pytest` | dev-dep | test files |
| `from unittest.mock import MagicMock, patch` | stdlib | test files |

**New Dependencies:** None — all imports are stdlib or existing project dependencies.

## 9. Test Mapping

| Test ID | Tests Function | File | Input | Expected Output |
|---------|---------------|------|-------|-----------------|
| T010 | `build_testing_workflow()` graph structure | `test_cleanup.py` | Compiled graph | N9_cleanup node exists; N9→END edge exists |
| T020 | `cleanup()` | `test_cleanup.py` | State with merged PR, active lineage | pr_merged=True, summary in done/, worktree removed |
| T030 | `cleanup()` | `test_cleanup.py` | State with open PR, active lineage | pr_merged=False, summary in active/, lineage preserved |
| T040 | `cleanup()` | `test_cleanup.py` | State without pr_url | cleanup_skipped_reason="No PR URL in state" |
| T050 | `cleanup()` | `test_cleanup.py` | State with no active dir | learning_summary_path="" |
| T060 | `cleanup()` | `test_cleanup.py` | remove_worktree raises CalledProcessError | No exception propagated |
| T070 | `check_pr_merged()` | `test_cleanup_helpers.py` | gh returns "MERGED" | True |
| T080 | `check_pr_merged()` | `test_cleanup_helpers.py` | gh returns "OPEN" | False |
| T090 | `check_pr_merged()` | `test_cleanup_helpers.py` | Empty/malformed URL | ValueError |
| T095 | `check_pr_merged()` | `test_cleanup_helpers.py` | subprocess.TimeoutExpired | TimeoutExpired raised |
| T100 | `remove_worktree()` | `test_cleanup_helpers.py` | Existing path, git succeeds | True |
| T110 | `remove_worktree()` | `test_cleanup_helpers.py` | Nonexistent path | False |
| T120 | `get_worktree_branch()` | `test_cleanup_helpers.py` | Porcelain output with match | "issue-180-cleanup" |
| T130 | `get_worktree_branch()` | `test_cleanup_helpers.py` | Porcelain output without match | None |
| T140 | `delete_local_branch()` | `test_cleanup_helpers.py` | Branch exists | True |
| T150 | `delete_local_branch()` | `test_cleanup_helpers.py` | Branch "not found" in stderr | False |
| T160 | `archive_lineage()` | `test_cleanup_helpers.py` | active exists, done doesn't | Done path, active removed |
| T170 | `archive_lineage()` | `test_cleanup_helpers.py` | active doesn't exist | None |
| T180 | `archive_lineage()` | `test_cleanup_helpers.py` | done already exists | Timestamped path |
| T190 | `extract_iteration_data()` | `test_cleanup_helpers.py` | Dir with green-phase file | [IterationSnapshot(coverage=98.5)] |
| T200 | `extract_iteration_data()` | `test_cleanup_helpers.py` | Empty dir | [] |
| T210 | `detect_stall()` | `test_cleanup_helpers.py` | [85.0, 85.0, 88.0] | (True, 2) |
| T220 | `detect_stall()` | `test_cleanup_helpers.py` | [80.0, 85.0, 90.0, 95.0] | (False, None) |
| T230 | `build_learning_summary()` | `test_cleanup_helpers.py` | Dir with fixtures | LearningSummaryData fully populated |
| T240 | `render_learning_summary()` | `test_cleanup_helpers.py` | LearningSummaryData | Markdown with all sections |
| T250 | `render_learning_summary()` | `test_cleanup_helpers.py` | Data with stall_detected=True | "Stall detected: Yes" in output |
| T260 | `write_learning_summary()` | `test_cleanup_helpers.py` | Dir + content string | File exists at path |
| T270 | `cleanup()` | `test_cleanup.py` | TimeoutExpired + CalledProcessError | State returned, no exception |
| T280 | `route_after_document()` | `test_cleanup.py` | state with issue_number=180 | "N9_cleanup" |
| T290 | `route_after_document()` | `test_cleanup.py` | state without issue_number | "end" |
| T300 | `cleanup()` | `test_cleanup.py` | Full state | Result has pr_merged (bool), learning_summary_path (str), cleanup_skipped_reason (str) |
| T310 | `cleanup()` | `test_cleanup.py` | PR not merged + active dir | "/active/" in learning_summary_path |
| T320 | `cleanup()` | `test_cleanup.py` | PR merged + active dir | "/done/" in learning_summary_path |

## 10. Implementation Notes

### 10.1 Error Handling Convention

All operations in the `cleanup()` node are wrapped in try/except blocks. The node **never** raises exceptions — it always returns a valid state dict. Subprocess errors (`CalledProcessError`, `TimeoutExpired`) are caught and logged at WARNING level. The `cleanup_skipped_reason` field in the return state communicates what was skipped and why.

Helper functions in `cleanup_helpers.py` **do** raise exceptions (they are pure functions). The node function is responsible for catching them.

### 10.2 Logging Convention

Use `logging.getLogger(__name__)` with `[N9]` prefix in all log messages:
- `logger.info("[N9] Starting cleanup node")`
- `logger.warning("[N9] Worktree cleanup failed: %s", exc)`

This is consistent with how other nodes log (e.g., `[N8]` prefix in the document node).

### 10.3 Constants

| Constant | Value | Rationale | File |
|----------|-------|-----------|------|
| `SUBPROCESS_TIMEOUT` | `10` | Max seconds for gh/git CLI calls; prevents hanging on unreachable GitHub | `cleanup_helpers.py`, `cleanup.py` (via import) |

### 10.4 Note on `get_worktree_branch` Path Resolution

The `get_worktree_branch` function resolves the input path via `Path(worktree_path).resolve()` before comparing against `git worktree list --porcelain` output. This is necessary because git may store absolute resolved paths while the caller may pass a relative or symlinked path.

### 10.5 Note on `json` Import

The `json` module is imported in `cleanup_helpers.py` but not directly used in the initial implementation. It's imported as a forward-looking convenience for potential future enhancement where `gh pr view --json state` output parsing might switch from `--jq` to Python-side JSON parsing. If strict "no unused imports" linting is enforced, this import can be removed.

### 10.6 Note on `route_after_document` Placement

The `route_after_document` function is defined in `cleanup.py` (not `graph.py`) because it is conceptually part of the N9 cleanup feature. It is exported through `__init__.py` and imported in `graph.py`. This keeps the routing logic co-located with the node it gates.

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3) — `state.py`, `__init__.py`, `graph.py`
- [x] Every data structure has a concrete JSON/YAML example (Section 4) — `TestingWorkflowState`, `IterationSnapshot`, `LearningSummaryData`
- [x] Every function has input/output examples with realistic values (Section 5) — 12 function specs
- [x] Change instructions are diff-level specific (Section 6) — diffs for all 10 files
- [x] Pattern references include file:line and are verified to exist (Section 7) — 4 patterns
- [x] All imports are listed and verified (Section 8) — 16 imports
- [x] Test mapping covers all LLD test scenarios (Section 9) — 33 test IDs mapped

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #180 |
| Verdict | DRAFT |
| Date | 2026-02-25 |
| Iterations | 0 |
| Finalized | — |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #180 |
| Verdict | APPROVED |
| Date | 2026-02-26 |
| Iterations | 0 |
| Finalized | 2026-02-26T00:28:12Z |

### Review Feedback Summary

Approved with suggestions:
*   **Graph Wiring Robustness:** In `assemblyzero/workflows/testing/graph.py`, the instruction to "Replace whatever edge goes from N8 to END" is generally safe, but the implementing agent should verify if `route_after_finalize` (mentioned in context) is currently doing anything other than pointing to END/N8. Given the spec replaces the edge entirely, this logic holds up.
*   **Test Isolation:** The tests use `unittest.mock.patch` extensively for subprocess calls. This ...


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
    metrics/
    mock_lineage/
    mock_repo/
      src/
    scout/
    verdict_analyzer/
  harness/
  integration/
  security/
  tools/
  unit/
    test_gate/
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
  ... and 13 more files
assemblyzero/
  core/
    validation/
  graphs/
  hooks/
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
# From C:\Users\mcwiz\Projects\AssemblyZero\tests\unit\test_cleanup_helpers.py
"""Unit tests for N9 cleanup helper functions.

Issue #180: N9 Cleanup Node - Worktree Removal, Lineage Archival, and Learning Summary

Tests: T070–T260 from LLD Section 10.0
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.workflows.testing.nodes.cleanup_helpers import (
    SUBPROCESS_TIMEOUT,
    IterationSnapshot,
    LearningSummaryData,
    archive_lineage,
    build_learning_summary,
    check_pr_merged,
    delete_local_branch,
    detect_stall,
    extract_iteration_data,
    get_worktree_branch,
    remove_worktree,
    render_learning_summary,
    write_learning_summary,
)


# === T070: check_pr_merged returns True ===
class TestCheckPrMerged:
    @patch("assemblyzero.workflows.testing.nodes.cleanup_helpers.subprocess.run")
    def test_check_pr_merged_returns_true(self, mock_run: MagicMock) -> None:
        """T070: gh returns MERGED state."""
        mock_run.return_value = MagicMock(
            stdout="MERGED\n", stderr="", returncode=0
        )
        result = check_pr_merged(
            "https://github.com/martymcenroe/AssemblyZero/pull/42"
        )
        assert result is True
        mock_run.assert_called_once_with(
            [
                "gh", "pr", "view",
                "https://github.com/martymcenroe/AssemblyZero/pull/42",
                "--json", "state", "--jq", ".state",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=SUBPROCESS_TIMEOUT,
        )

    # === T080: check_pr_merged returns False for OPEN ===
    @patch("assemblyzero.workflows.testing.nodes.cleanup_helpers.subprocess.run")
    def test_check_pr_merged_returns_false_open(self, mock_run: MagicMock) -> None:
        """T080: gh returns OPEN state."""
        mock_run.return_value = MagicMock(
            stdout="OPEN\n", stderr="", returncode=0
        )
        result = check_pr_merged(
            "https://github.com/martymcenroe/AssemblyZero/pull/42"
        )
        assert result is False

    # === T090: check_pr_merged invalid URL ===
    def test_check_pr_merged_invalid_url_empty(self) -> None:
        """T090: ValueError raised for empty URL."""
        with pytest.raises(ValueError, match="pr_url cannot be empty"):
            check_pr_merged("")

    def test_check_pr_merged_invalid_url_malformed(self) -> None:
        """T090: ValueError raised for malformed URL."""
        with pytest.raises(ValueError, match="Malformed PR URL"):
            check_pr_merged("not-a-url")

    # === T095: check_pr_merged timeout ===
    @patch("assemblyzero.workflows.testing.nodes.cleanup_helpers.subprocess.run")
    def test_check_pr_merged_timeout(self, mock_run: MagicMock) -> None:
        """T095: TimeoutExpired raised after 10s."""
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd=["gh"], timeout=SUBPROCESS_TIMEOUT
        )
        with pytest.raises(subprocess.TimeoutExpired):
            check_pr_merged(
                "https://github.com/martymcenroe/AssemblyZero/pull/42"
            )


# === T100/T110: remove_worktree ===
class TestRemoveWorktree:
    @patch("assemblyzero.workflows.testing.nodes.cleanup_helpers.subprocess.run")
    def test_remove_worktree_success(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """T100: git worktree remove succeeds, returns True."""
        worktree_dir = tmp_path / "worktree"
        worktree_dir.mkdir()
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = remove_worktree(worktree_dir)
        assert result is True
        mock_run.assert_called_once_with(
            ["git", "worktree", "remove", str(worktree_dir)],
            capture_output=True,
            text=True,
            check=True,
            timeout=SUBPROCESS_TIMEOUT,
        )

    def test_remove_worktree_nonexistent(self, tmp_path: Path) -> None:
        """T110: Worktree path doesn't exist, returns False."""
        result = remove_worktree(tmp_path / "nonexistent")
        assert result is False


# === T120/T130: get_worktree_branch ===
class TestGetWorktreeBranch:
    @patch("assemblyzero.workflows.testing.nodes.cleanup_helpers.subprocess.run")
    def test_get_worktree_branch_found(self, mock_run: MagicMock) -> None:
        """T120: Extracts branch name from git worktree list."""
        porcelain_output = (
            "worktree /home/user/Projects/AssemblyZero\n"
            "HEAD abc123\n"
            "branch refs/heads/main\n"
            "\n"
            "worktree /home/user/Projects/AssemblyZero-180\n"
            "HEAD def456\n"
            "branch refs/heads/issue-180-cleanup\n"
            "\n"
        )
        mock_run.return_value = MagicMock(
            stdout=porcelain_output, stderr="", returncode=0
        )
        result = get_worktree_branch("/home/user/Projects/AssemblyZero-180")
        assert result == "issue-180-cleanup"

    @patch("assemblyzero.workflows.testing.nodes.cleanup_helpers.subprocess.run")
    def test_get_worktree_branch_not_found(self, mock_run: MagicMock) -> None:
        """T130: Returns None for unknown path."""
        porcelain_output = (
            "worktree /home/user/Projects/AssemblyZero\n"
            "HEAD abc123\n"
            "branch refs/heads/main\n"
            "\n"
        )
        mock_run.return_value = MagicMock(
            stdout=porcelain_output, stderr="", returncode=0
        )
        result = get_worktree_branch("/home/user/Projects/unknown-worktree")
        assert result is None


# === T140/T150: delete_local_branch ===
class TestDeleteLocalBranch:
    @patch("assemblyzero.workflows.testing.nodes.cleanup_helpers.subprocess.run")
    def test_delete_local_branch_success(self, mock_run: MagicMock) -> None:
        """T140: git branch -D succeeds, returns True."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = delete_local_branch("issue-180-cleanup")
        assert result is True
        mock_run.assert_called_once_with(
            ["git", "branch", "-D", "issue-180-cleanup"],
            capture_output=True,
            text=True,
            check=True,
            timeout=SUBPROCESS_TIMEOUT,
        )

    @patch("assemblyzero.workflows.testing.nodes.cleanup_helpers.subprocess.run")
    def test_delete_local_branch_not_found(self, mock_run: MagicMock) -> None:
        """T150: Branch doesn't exist, returns False."""
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["git", "branch", "-D", "nonexistent"],
            stderr="error: branch 'nonexistent' not found.",
        )
        result = delete_local_branch("nonexistent")
        assert result is False


# === T160/T170/T180: archive_lineage ===
class TestArchiveLineage:
    def test_archive_lineage_moves_directory(self, tmp_path: Path) -> None:
        """T160: active/ moved to done/, returns done path."""
        repo_root = tmp_path / "repo"
        active_dir = repo_root / "docs" / "lineage" / "active" / "180-testing"
        active_dir.mkdir(parents=True)
        (active_dir / "001-lld.md").write_text("# LLD")

        result = archive_lineage(repo_root, 180)

        expected = repo_root / "docs" / "lineage" / "done" / "180-testing"
        assert result == expected
        assert expected.exists()
        assert (expected / "001-lld.md").read_text() == "# LLD"
        assert not active_dir.exists()

    def test_archive_lineage_active_not_found(self, tmp_path: Path) -> None:
        """T170: Returns None, no error."""
        result = archive_lineage(tmp_path, 999)
        assert result is None

    def test_archive_lineage_done_already_exists(self, tmp_path: Path) -> None:
        """T180: Appends timestamp suffix to avoid collision."""
        repo_root = tmp_path / "repo"
        active_dir = repo_root / "docs" / "lineage" / "active" / "180-testing"
        active_dir.mkdir(parents=True)
        (active_dir / "file.txt").write_text("data")

        # Pre-create done/ to cause collision
        done_dir = repo_root / "docs" / "lineage" / "done" / "180-testing"
        done_dir.mkdir(parents=True)

        result = archive_lineage(repo_root, 180)

        assert result is not None
        assert result != done_dir  # Different path (has timestamp suffix)
        assert result.exists()
        assert "180-testing-" in result.name
        assert not active_dir.exists()


# === T190/T200: extract_iteration_data ===
class TestExtractIterationData:
    def test_extract_iteration_data_parses_green_phase(
        self, tmp_path: Path
    ) -> None:
        """T190: Parses coverage from green-phase files."""
        lineage_dir = tmp_path / "180-testing"
        lineage_dir.mkdir()
        (lineage_dir / "052-green-phase.txt").write_text(
            "Green Phase\nCoverage: 98.5%\nMissing lines: src/x.py:10, src/x.py:20"
        )

        result = extract_iteration_data(lineage_dir)

        assert len(result) == 1
        assert result[0].iteration == 1
        assert result[0].coverage_pct == 98.5
        assert result[0].missing_lines == ["src/x.py:10", "src/x.py:20"]

    def test_extract_iteration_data_empty_dir(self, tmp_path: Path) -> None:
        """T200: Returns empty list for empty directory."""
        lineage_dir = tmp_path / "180-testing"
        lineage_dir.mkdir()

        result = extract_iteration_data(lineage_dir)
        assert result == []

    def test_extract_iteration_data_nonexistent_dir(self, tmp_path: Path) -> None:
        """Returns empty list for nonexistent directory."""
        result = extract_iteration_data(tmp_path / "nonexistent")
        assert result == []


# === T210/T220: detect_stall ===
class TestDetectStall:
    def test_detect_stall_found(self) -> None:
        """T210: Detects consecutive equal coverage."""
        snapshots = [
            IterationSnapshot(iteration=1, coverage_pct=85.0),
            IterationSnapshot(iteration=2, coverage_pct=85.0),
            IterationSnapshot(iteration=3, coverage_pct=88.0),
        ]
        result = detect_stall(snapshots)
        assert result == (True, 2)

    def test_detect_stall_not_found(self) -> None:
        """T220: Returns (False, None) for monotonic increase."""
        snapshots = [
            IterationSnapshot(iteration=1, coverage_pct=80.0),
            IterationSnapshot(iteration=2, coverage_pct=85.0),
            IterationSnapshot(iteration=3, coverage_pct=90.0),
            IterationSnapshot(iteration=4, coverage_pct=95.0),
        ]
        result = detect_stall(snapshots)
        assert result == (False, None)

    def test_detect_stall_empty(self) -> None:
        """Empty list returns no stall."""
        assert detect_stall([]) == (False, None)

    def test_detect_stall_single(self) -> None:
        """Single snapshot returns no stall."""
        assert detect_stall([IterationSnapshot(1, 80.0)]) == (False, None)


# === T230: build_learning_summary ===
class TestBuildLearningSummary:
    def test_build_learning_summary_full(self, tmp_path: Path) -> None:
        """T230: Builds complete LearningSummaryData from fixtures."""
        lineage_dir = tmp_path / "180-testing"
        lineage_dir.mkdir()
        (lineage_dir / "001-lld.md").write_text("# LLD")
        (lineage_dir / "005-test-scaffold.py").write_text("def test(): pass")
        (lineage_dir / "052-green-phase.txt").write_text(
            "Coverage: 96.5%\nMissing lines: cleanup.py:42"
        )

        result = build_learning_summary(
            lineage_dir,
            issue_number=180,
            outcome="SUCCESS",
            final_coverage=96.5,
            target_coverage=95.0,
        )

        assert result.issue_number == 180
        assert result.outcome == "SUCCESS"
        assert result.final_coverage == 96.5
        assert result.target_coverage == 95.0
        assert result.total_iterations == 1
        assert len(result.key_artifacts) == 3  # lld, scaffold, green-phase
        assert len(result.what_worked) > 0
        assert len(result.recommendations) > 0


# === T240/T250: render_learning_summary ===
class TestRenderLearningSummary:
    def test_render_learning_summary_markdown(self) -> None:
        """T240: Renders all sections to valid markdown including version header."""
        data = LearningSummaryData(
            issue_number=180,
            outcome="SUCCESS",
            final_coverage=96.5,
            target_coverage=95.0,
            total_iterations=3,
            stall_detected=False,
            stall_iteration=None,
            iteration_snapshots=[
                IterationSnapshot(1, 72.0, ["cleanup.py:10-30"], ""),
                IterationSnapshot(2, 85.0, ["cleanup.py:42"], ""),
                IterationSnapshot(3, 96.5, [], ""),
            ],
            key_artifacts=[("001-lld.md", "LLD document")],
            what_worked=["TDD loop converged"],
            what_didnt_work=[],
            recommendations=["No recommendations"],
        )

        result = render_learning_summary(data)

        assert "# Learning Summary — Issue #180" in result
        assert "## Format Version: 1.0" in result
        assert "## Outcome" in result
        assert "## Coverage Gap Analysis" in result
        assert "## Stall Analysis" in result
        assert "## Key Artifacts" in result
        assert "## What Worked" in result
        assert "## What Didn't Work" in result
        assert "## Recommendations" in result
        assert "96.5%" in result
        assert "SUCCESS" in result

    def test_render_learning_summary_with_stall(self) -> None:
        """T250: Stall info included in rendered output."""
        data = LearningSummaryData(
            issue_number=42,
            outcome="FAILURE",
            final_coverage=85.0,
            target_coverage=95.0,
            total_iterations=3,
            stall_detected=True,
            stall_iteration=2,
            iteration_snapshots=[
                IterationSnapshot(1, 85.0),
                IterationSnapshot(2, 85.0),
                IterationSnapshot(3, 85.0),
            ],
            key_artifacts=[],
            what_worked=[],
            what_didnt_work=["Coverage stalled"],
            recommendations=["Split functions"],
        )

        result = render_learning_summary(data)

        assert "Stall detected:** Yes" in result
        assert "Stall iteration:** 2" in result


# === T260: write_learning_summary ===
class TestWriteLearningSummary:
    def test_write_learning_summary_creates_file(self, tmp_path: Path) -> None:
        """T260: File written to correct path."""
        lineage_dir = tmp_path / "180-testing"
        lineage_dir.mkdir()
        content = "# Learning Summary — Issue #180\n\n## Format Version: 1.0\n"

        result = write_learning_summary(lineage_dir, content)

        expected_path = lineage_dir / "learning-summary.md"
        assert result == expected_path
        assert expected_path.exists()
        assert expected_path.read_text() == content

# From C:\Users\mcwiz\Projects\AssemblyZero\tests\unit\test_cleanup.py
"""Unit tests for N9 cleanup node.

Issue #180: N9 Cleanup Node - Worktree Removal, Lineage Archival, and Learning Summary

Tests: T010–T040, T050–T060, T270–T320 from LLD Section 10.0
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.workflows.testing.nodes.cleanup import (
    cleanup,
    route_after_document,
)


# === T280/T290: route_after_document ===
class TestRouteAfterDocument:
    def test_route_has_issue(self) -> None:
        """T280: Returns 'N9_cleanup' when issue_number present."""
        state: dict[str, Any] = {"issue_number": 180}
        assert route_after_document(state) == "N9_cleanup"

    def test_route_no_issue(self) -> None:
        """T290: Returns 'end' when no issue_number."""
        state: dict[str, Any] = {"lld_content": "something"}
        assert route_after_document(state) == "end"

    def test_route_issue_zero(self) -> None:
        """Returns 'end' when issue_number is 0 (falsy)."""
        state: dict[str, Any] = {"issue_number": 0}
        assert route_after_document(state) == "end"

    def test_route_issue_none(self) -> None:
        """Returns 'end' when issue_number is None."""
        state: dict[str, Any] = {"issue_number": None}
        assert route_after_document(state) == "end"


# === T010: N9 node wired in graph ===
class TestGraphWiring:
    def test_cleanup_node_wired_in_graph(self) -> None:
        """T010: N9_cleanup node present in graph with correct edges."""
        from assemblyzero.workflows.testing.graph import build_testing_workflow

        graph = build_testing_workflow()
        compiled = graph.compile()

        # Check node exists
        node_names = [n for n in compiled.get_graph().nodes]
        assert "N9_cleanup" in node_names

        # Check edges exist: N8 -> N9 (via conditional), N9 -> END
        edges = compiled.get_graph().edges
        # N9 -> __end__ edge
        n9_to_end = any(
            e.source == "N9_cleanup" and e.target == "__end__"
            for e in edges
        )
        assert n9_to_end, f"Expected N9->END edge. Edges: {edges}"


# === T020: Happy path — PR merged ===
class TestCleanupHappyPath:
    @patch("assemblyzero.workflows.testing.nodes.cleanup.archive_lineage")
    @patch("assemblyzero.workflows.testing.nodes.cleanup.write_learning_summary")
    @patch("assemblyzero.workflows.testing.nodes.cleanup.render_learning_summary")
    @patch("assemblyzero.workflows.testing.nodes.cleanup.build_learning_summary")
    @patch("assemblyzero.workflows.testing.nodes.cleanup.delete_local_branch")
    @patch("assemblyzero.workflows.testing.nodes.cleanup.get_worktree_branch")
    @patch("assemblyzero.workflows.testing.nodes.cleanup.remove_worktree")
    @patch("assemblyzero.workflows.testing.nodes.cleanup.check_pr_merged")
    def test_cleanup_happy_path_pr_merged(
        self,
        mock_check: MagicMock,
        mock_remove_wt: MagicMock,
        mock_get_branch: MagicMock,
        mock_del_branch: MagicMock,
        mock_build: MagicMock,
        mock_render: MagicMock,
        mock_write: MagicMock,
        mock_archive: MagicMock,
        tmp_path: Path,
    ) -> None:
        """T020: Full cleanup: worktree removed, summary in active/, lineage archived."""
        # Set up active lineage dir
        repo_root = tmp_path / "repo"
        active_dir = repo_root / "docs" / "lineage" / "active" / "180-testing"
        active_dir.mkdir(parents=True)
        (active_dir / "001-lld.md").write_text("# LLD")

        done_dir = repo_root / "docs" / "lineage" / "done" / "180-testing"

        mock_check.return_value = True
        mock_get_branch.return_value = "issue-180-cleanup"
        mock_remove_wt.return_value = True
        mock_del_branch.return_value = True
        mock_build.return_value = MagicMock()
        mock_render.return_value = "# Summary"
        mock_write.return_value = active_dir / "learning-summary.md"
        mock_archive.return_value = done_dir

        state: dict[str, Any] = {
            "issue_number": 180,
            "pr_url": "https://github.com/martymcenroe/AssemblyZero/pull/42",
            "worktree_path": str(tmp_path / "worktree"),
            "repo_root": str(repo_root),
            "final_coverage": 96.5,
            "target_coverage": 95.0,
            "outcome": "SUCCESS",
        }

        result = cleanup(state)

        assert result["pr_merged"] is True
        assert "done" in result["learning_summary_path"]
        assert result["cleanup_skipped_reason"] == ""
        mock_check.assert_called_once()
        mock_remove_wt.assert_called_once()
        mock_del_branch.assert_called_once_with("issue-180-cleanup")
        mock_build.assert_called_once()
        mock_archive.assert_called_once()


# === T030: PR not merged ===
class TestCleanupPrNotMerged:
    @patch("assemblyzero.workflows.testing.nodes.cleanup.check_pr_merged")
    def test_cleanup_pr_not_merged_skips_worktree_keeps_active(
        self, mock_check: MagicMock, tmp_path: Path
    ) -> None:
        """T030: Worktree preserved, summary in active/, lineage NOT archived."""
        repo_root = tmp_path / "repo"
        active_dir = repo_root / "docs" / "lineage" / "active" / "180-testing"
        active_dir.mkdir(parents=True)
        (active_dir / "052-green-phase.txt").write_text("Coverage: 96.5%")

        mock_check.return_value = False

        state: dict[str, Any] = {
            "issue_number": 180,
            "pr_url": "https://github.com/martymcenroe/AssemblyZero/pull/42",
            "worktree_path": str(tmp_path / "worktree"),
            "repo_root": str(repo_root),
            "final_coverage": 96.5,
            "target_coverage": 95.0,
            "outcome": "SUCCESS",
        }

        result = cleanup(state)

        assert result["pr_merged"] is False
        assert "active" in result["learning_summary_path"]
        assert result["cleanup_skipped_reason"] == "PR not yet merged"
        # Verify summary was written in active
        assert (active_dir / "learning-summary.md").exists()
        # Verify lineage NOT moved
        assert active_dir.exists()


# === T040: No pr_url ===
class TestCleanupNoPrUrl:
    def test_cleanup_no_pr_url_skips_worktree(self, tmp_path: Path) -> None:
        """T040: No PR URL in state, worktree skipped gracefully."""
        repo_root = tmp_path / "repo"
        active_dir = repo_root / "docs" / "lineage" / "active" / "180-testing"
        active_dir.mkdir(parents=True)

        state: dict[str, Any] = {
            "issue_number": 180,
            "repo_root": str(repo_root),
            "final_coverage": 96.5,
            "target_coverage": 95.0,
            "outcome": "SUCCESS",
        }

        result = cleanup(state)

        assert result["pr_merged"] is False
        assert result["cleanup_skipped_reason"] == "No PR URL in state"


# === T050: No lineage directory ===
class TestCleanupNoLineageDir:
    @patch("assemblyzero.workflows.testing.nodes.cleanup.check_pr_merged")
    def test_cleanup_no_lineage_dir_skips_archival(
        self, mock_check: MagicMock, tmp_path: Path
    ) -> None:
        """T050: Missing active/ dir, summary skipped, no error."""
        mock_check.return_value = True

        state: dict[str, Any] = {
            "issue_number": 999,
            "pr_url": "https://github.com/martymcenroe/AssemblyZero/pull/42",
            "repo_root": str(tmp_path),
            "final_coverage": 96.5,
            "target_coverage": 95.0,
            "outcome": "SUCCESS",
        }

        result = cleanup(state)

        assert result["pr_merged"] is True
        assert result["learning_summary_path"] == ""


# === T060: Dirty worktree ===
class TestCleanupDirtyWorktree:
    @patch("assemblyzero.workflows.testing.nodes.cleanup.remove_worktree")
    @patch("assemblyzero.workflows.testing.nodes.cleanup.get_worktree_branch")
    @patch("assemblyzero.workflows.testing.nodes.cleanup.check_pr_merged")
    def test_cleanup_worktree_dirty_skips_removal(
        self,
        mock_check: MagicMock,
        mock_get_branch: MagicMock,
        mock_remove_wt: MagicMock,
        tmp_path: Path,
    ) -> None:
        """T060: Dirty worktree not force-removed, logged."""
        mock_check.return_value = True
        mock_get_branch.return_value = "issue-180-cleanup"
        mock_remove_wt.side_effect = subprocess.CalledProcessError(
            returncode=128,
            cmd=["git", "worktree", "remove"],
            stderr="fatal: 'path' contains modified or untracked files",
        )

        repo_root = tmp_path / "repo"
        active_dir = repo_root / "docs" / "lineage" / "active" / "180-testing"
        active_dir.mkdir(parents=True)

        state: dict[str, Any] = {
            "issue_number": 180,
            "pr_url": "https://github.com/martymcenroe/AssemblyZero/pull/42",
            "worktree_path": str(tmp_path / "dirty-worktree"),
            "repo_root": str(repo_root),
            "final_coverage": 96.5,
            "target_coverage": 95.0,
            "outcome": "SUCCESS",
        }

        # Should not raise — error caught gracefully
        result = cleanup(state)
        assert result["pr_merged"] is True


# === T270: All subprocess errors caught ===
class TestCleanupErrorHandling:
    @patch("assemblyzero.workflows.testing.nodes.cleanup.check_pr_merged")
    def test_cleanup_all_errors_caught(
        self, mock_check: MagicMock, tmp_path: Path
    ) -> None:
        """T270: Subprocess errors and timeouts logged, not raised."""
        mock_check.side_effect = subprocess.TimeoutExpired(
            cmd=["gh"], timeout=10
        )

        state: dict[str, Any] = {
            "issue_number": 180,
            "pr_url": "https://github.com/martymcenroe/AssemblyZero/pull/42",
            "repo_root": str(tmp_path),
            "final_coverage": 0.0,
            "target_coverage": 95.0,
            "outcome": "FAILURE",
        }

        # Should not raise
        result = cleanup(state)
        assert "cleanup_skipped_reason" in result
        assert "failed" in result["cleanup_skipped_reason"].lower() or "timeout" in result["cleanup_skipped_reason"].lower()

    @patch("assemblyzero.workflows.testing.nodes.cleanup.check_pr_merged")
    def test_cleanup_called_process_error_caught(
        self, mock_check: MagicMock, tmp_path: Path
    ) -> None:
        """T270b: CalledProcessError caught and logged."""
        mock_check.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd=["gh"], stderr="not found"
        )

        state: dict[str, Any] = {
            "issue_number": 180,
            "pr_url": "https://github.com/martymcenroe/AssemblyZero/pull/42",
            "repo_root": str(tmp_path),
            "final_coverage": 0.0,
            "target_coverage": 95.0,
            "outcome": "FAILURE",
        }

        result = cleanup(state)
        assert result["pr_merged"] is False
        assert result["cleanup_skipped_reason"] != ""


# === T300: State fields updated correctly ===
class TestCleanupStateFields:
    @patch("assemblyzero.workflows.testing.nodes.cleanup.check_pr_merged")
    def test_cleanup_state_fields_updated(
        self, mock_check: MagicMock, tmp_path: Path
    ) -> None:
        """T300: State contains pr_merged, learning_summary_path, cleanup_skipped_reason."""
        mock_check.return_value = False

        repo_root = tmp_path / "repo"
        active_dir = repo_root / "docs" / "lineage" / "active" / "180-testing"
        active_dir.mkdir(parents=True)
        (active_dir / "052-green-phase.txt").write_text("Coverage: 96.5%")

        state: dict[str, Any] = {
            "issue_number": 180,
            "pr_url": "https://github.com/martymcenroe/AssemblyZero/pull/42",
            "repo_root": str(repo_root),
            "final_coverage": 96.5,
            "target_coverage": 95.0,
            "outcome": "SUCCESS",
        }

        result = cleanup(state)

        assert "pr_merged" in result
        assert isinstance(result["pr_merged"], bool)
        assert "learning_summary_path" in result
        assert isinstance(result["learning_summary_path"], str)
        assert "cleanup_skipped_reason" in result
        assert isinstance(result["cleanup_skipped_reason"], str)


# === T310: PR not merged, summary in active ===
class TestCleanupSummaryPaths:
    @patch("assemblyzero.workflows.testing.nodes.cleanup.check_pr_merged")
    def test_cleanup_pr_not_merged_summary_in_active(
        self, mock_check: MagicMock, tmp_path: Path
    ) -> None:
        """T310: When PR not merged, learning_summary_path points to active/."""
        mock_check.return_value = False

        repo_root = tmp_path / "repo"
        active_dir = repo_root / "docs" / "lineage" / "active" / "180-testing"
        active_dir.mkdir(parents=True)
        (active_dir / "052-green-phase.txt").write_text("Coverage: 96.5%")

        state: dict[str, Any] = {
            "issue_number": 180,
            "pr_url": "https://github.com/martymcenroe/AssemblyZero/pull/42",
            "repo_root": str(repo_root),
            "final_coverage": 96.5,
            "target_coverage": 95.0,
            "outcome": "SUCCESS",
        }

        result = cleanup(state)
        assert "/active/" in result["learning_summary_path"]

    # === T320: PR merged, summary in done ===
    @patch("assemblyzero.workflows.testing.nodes.cleanup.archive_lineage")
    @patch("assemblyzero.workflows.testing.nodes.cleanup.write_learning_summary")
    @patch("assemblyzero.workflows.testing.nodes.cleanup.render_learning_summary")
    @patch("assemblyzero.workflows.testing.nodes.cleanup.build_learning_summary")
    @patch("assemblyzero.workflows.testing.nodes.cleanup.delete_local_branch")
    @patch("assemblyzero.workflows.testing.nodes.cleanup.get_worktree_branch")
    @patch("assemblyzero.workflows.testing.nodes.cleanup.remove_worktree")
    @patch("assemblyzero.workflows.testing.nodes.cleanup.check_pr_merged")
    def test_cleanup_pr_merged_summary_in_done(
        self,
        mock_check: MagicMock,
        mock_remove_wt: MagicMock,
        mock_get_branch: MagicMock,
        mock_del_branch: MagicMock,
        mock_build: MagicMock,
        mock_render: MagicMock,
        mock_write: MagicMock,
        mock_archive: MagicMock,
        tmp_path: Path,
    ) -> None:
        """T320: When PR merged, learning_summary_path points to done/."""
        repo_root = tmp_path / "repo"
        active_dir = repo_root / "docs" / "lineage" / "active" / "180-testing"
        active_dir.mkdir(parents=True)
        (active_dir / "001-lld.md").write_text("# LLD")

        done_dir = repo_root / "docs" / "lineage" / "done" / "180-testing"

        mock_check.return_value = True
        mock_get_branch.return_value = "issue-180"
        mock_remove_wt.return_value = True
        mock_del_branch.return_value = True
        mock_build.return_value = MagicMock()
        mock_render.return_value = "# Summary"
        mock_write.return_value = active_dir / "learning-summary.md"
        mock_archive.return_value = done_dir

        state: dict[str, Any] = {
            "issue_number": 180,
            "pr_url": "https://github.com/martymcenroe/AssemblyZero/pull/42",
            "worktree_path": str(tmp_path / "worktree"),
            "repo_root": str(repo_root),
            "final_coverage": 96.5,
            "target_coverage": 95.0,
            "outcome": "SUCCESS",
        }

        result = cleanup(state)
        assert "/done/" in result["learning_summary_path"]


```

## Previously Implemented Files

These files have already been implemented. Use them for imports and references:

### assemblyzero/workflows/testing/state.py (signatures)

```python
"""State definition for TDD Testing Workflow.

Issue #101: Test Plan Reviewer
Issue #102: TDD Initialization
Issue #93: N8 Documentation Node
Issue #335: Scaffold validation fields
Issue #147: Completeness gate fields (completeness_verdict, completeness_issues, review_materials)
Issue #292: pytest_exit_code for exit code routing
Issue #180: N9 Cleanup node fields (pr_url, pr_merged, learning_summary_path, cleanup_skipped_reason)

This TypedDict travels through nodes N0-N8, tracking the testing workflow
from LLD loading through test generation, implementation, E2E validation,
documentation generation, and post-implementation cleanup.
"""

from enum import Enum

from typing import Literal, TypedDict

class HumanDecision(str, Enum):

    """User choices at human gate nodes."""

class TestScenario(TypedDict):

class TestingWorkflowState(TypedDict, total=False):
```

### assemblyzero/workflows/testing/nodes/cleanup_helpers.py (signatures)

```python
"""Helper functions for N9 cleanup node.

Issue #180: N9 Cleanup Node - Worktree Removal, Lineage Archival, and Learning Summary

Pure-function helpers that are independently testable without mocking
LangGraph state machinery. All subprocess calls use SUBPROCESS_TIMEOUT
to prevent hanging.
"""

from __future__ import annotations

import logging

import re

import shutil

import subprocess

import time

from dataclasses import dataclass, field

from pathlib import Path

class IterationSnapshot:

    """Captures coverage data from a single TDD iteration."""

class LearningSummaryData:

    """Structured data extracted from lineage artifacts before rendering to markdown."""

def check_pr_merged(pr_url: str) -> bool:
    """Check if a GitHub PR is merged using gh CLI.

Args:"""
    ...

def remove_worktree(worktree_path: str | Path) -> bool:
    """Remove a git worktree (without --force).

Args:"""
    ...

def get_worktree_branch(worktree_path: str | Path) -> str | None:
    """Extract the branch name associated with a worktree.

Args:"""
    ...

def delete_local_branch(branch_name: str) -> bool:
    """Delete a local git branch using -D (force, for squash-merged branches).

Args:"""
    ...

def archive_lineage(
    repo_root: Path,
    issue_number: int,
    lineage_suffix: str = "testing",
) -> Path | None:
    """Move lineage directory from active/ to done/.

Args:"""
    ...

def extract_iteration_data(lineage_dir: Path) -> list[IterationSnapshot]:
    """Parse lineage artifacts to extract per-iteration coverage data.

Scans for files matching patterns like *green-phase*, *coverage*,"""
    ...

def detect_stall(snapshots: list[IterationSnapshot]) -> tuple[bool, int | None]:
    """Detect if coverage stalled (same coverage for 2+ consecutive iterations).

Args:"""
    ...

def build_learning_summary(
    lineage_dir: Path,
    issue_number: int,
    outcome: str,
    final_coverage: float,
    target_coverage: float,
) -> LearningSummaryData:
    """Build structured learning summary data from lineage artifacts.

Args:"""
    ...

def render_learning_summary(data: LearningSummaryData) -> str:
    """Render LearningSummaryData to markdown string.

The output format is versioned (Format Version: 1.0) and documented"""
    ...

def write_learning_summary(lineage_dir: Path, content: str) -> Path:
    """Write learning summary markdown to the lineage directory.

Args:"""
    ...

logger = logging.getLogger(__name__)
```

### assemblyzero/workflows/testing/nodes/cleanup.py (signatures)

```python
"""N9 Cleanup Node for TDD Testing Workflow.

Issue #180: N9 Cleanup Node - Worktree Removal, Lineage Archival, and Learning Summary

Orchestrates three cleanup tasks:
1. Check PR merge status and remove worktree if merged
2. Generate learning summary in active lineage directory
3. Archive lineage from active/ to done/ ONLY if PR is merged
"""

from __future__ import annotations

import logging

import subprocess

from pathlib import Path

from typing import Any

from assemblyzero.workflows.testing.nodes.cleanup_helpers import (
    archive_lineage,
    build_learning_summary,
    check_pr_merged,
    delete_local_branch,
    get_worktree_branch,
    remove_worktree,
    render_learning_summary,
    write_learning_summary,
)

def _posix_path_str(path: Path) -> str:
    """Convert a Path to a forward-slash string for cross-platform consistency."""
    ...

def route_after_document(state: dict[str, Any]) -> str:
    """Conditional routing from N8 to N9 or END.

Returns "N9_cleanup" if state has valid issue_number,"""
    ...

def cleanup(state: dict[str, Any]) -> dict[str, Any]:
    """N9: Post-implementation cleanup node.

Orchestrates three cleanup tasks:"""
    ...

logger = logging.getLogger(__name__)
```

### assemblyzero/workflows/testing/nodes/__init__.py (signatures)

```python
"""Node implementations for TDD Testing Workflow.

Issue #101: Test Plan Reviewer
Issue #102: TDD Initialization
Issue #93: N8 Documentation Node
Issue #147: Implementation Completeness Gate (N4b)
Issue #180: N9 Cleanup Node

Nodes:
- N0: load_lld - Load LLD and extract test plan
- N1: review_test_plan - Gemini reviews test plan coverage
- N2: scaffold_tests - Generate executable test stubs
- N3: verify_red_phase - Verify all tests fail
- N4: implement_code - Claude generates implementation
- N4b: completeness_gate - Verify implementation completeness
- N5: verify_green_phase - Verify all tests pass
- N6: e2e_validation - Run E2E tests in sandbox
- N7: finalize - Generate reports and complete
- N8: document - Auto-generate documentation artifacts
- N9: cleanup - Post-implementation cleanup (worktree, lineage, summary)
"""

from assemblyzero.workflows.testing.nodes.cleanup import (
    cleanup,
    route_after_document,
)

from assemblyzero.workflows.testing.nodes.completeness_gate import (
    completeness_gate,
)

from assemblyzero.workflows.testing.nodes.document import document

from assemblyzero.workflows.testing.nodes.e2e_validation import e2e_validation

from assemblyzero.workflows.testing.nodes.finalize import finalize

from assemblyzero.workflows.testing.nodes.implement_code import implement_code

from assemblyzero.workflows.testing.nodes.load_lld import load_lld

from assemblyzero.workflows.testing.nodes.review_test_plan import review_test_plan

from assemblyzero.workflows.testing.nodes.scaffold_tests import scaffold_tests

from assemblyzero.workflows.testing.nodes.validate_commit_message import (
    validate_commit_message,
)

from assemblyzero.workflows.testing.nodes.verify_phases import (
    verify_green_phase,
    verify_red_phase,
)
```

### assemblyzero/workflows/testing/graph.py (signatures)

```python
"""StateGraph definition for TDD Testing Workflow.

Issue #101: Test Plan Reviewer
Issue #102: TDD Initialization
Issue #93: N8 Documentation Node
Issue #335: Add mechanical test validation node (N2.5)
Issue #147: Add completeness gate node (N4b) between N4 and N5
Issue #292: Exit code routing — N3/N5 can route to N2 on syntax/collection errors
Issue #180: Add cleanup node (N9) after N8

Defines the compiled graph with:
- N0-N9 nodes (plus N2.5 for test validation, N4b for completeness gate)
- Conditional edges for routing
- Checkpoint support via SqliteSaver

Graph structure:
    N0_load_lld -> N1_review_test_plan -> N2_scaffold_tests -> N2_5_validate_tests
           |              |                     |                      |
           v              v                     v                      v
         error         BLOCKED              scaffold_only         validation
           |              |                     |                   result
           v              v                     v                      |
          END     loop back to LLD             END                    / \
                  (outside workflow)                                 /   \
                                                                pass   fail
                                                                 |       |
                                                                 v       v
    N2_5 (pass) -> N3_verify_red -> N4_implement_code ------> N2 (retry)
           |                |                   |               or escalate
           v                v                   v               to N4
        red OK          iteration          N4b_completeness
           |            loop back              |
           v                |                 / \
          N4               N4              PASS  BLOCK
                                            |      |
                                            v      v
                                           N5   N4 (iter<3)
                                                 or END (iter>=3)

    N5_verify_green -> N6_e2e_validation -> N7_finalize -> N8_document -> N9_cleanup -> END
           |                  |                  |               |
           v                  v                  v               v
       iteration          skip_e2e           complete    route_after_doc
       loop back              |                                  |
           |                  v                                 / \
          N4                 N7                            N9     END
                                                          |
                                                          v
                                                         END
"""

from typing import Literal

from langgraph.graph import END, StateGraph

from assemblyzero.workflows.testing.nodes import (
    cleanup,
    document,
    e2e_validation,
    finalize,
    implement_code,
    load_lld,
    route_after_document,
    review_test_plan,
    scaffold_tests,
    verify_green_phase,
    verify_red_phase,
)

from assemblyzero.workflows.testing.nodes.completeness_gate import (
    completeness_gate,
    route_after_completeness_gate,
)

from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
    validate_tests_mechanical_node,
    should_regenerate,
)

from assemblyzero.workflows.testing.state import TestingWorkflowState

def route_after_load(
    state: TestingWorkflowState,
) -> Literal["N1_review_test_plan", "end"]:
    """Route after N0 (load_lld).

Args:"""
    ...

def route_after_review(
    state: TestingWorkflowState,
) -> Literal["N2_scaffold_tests", "end"]:
    """Route after N1 (review_test_plan).

Args:"""
    ...

def route_after_scaffold(
    state: TestingWorkflowState,
) -> Literal["N2_5_validate_tests", "end"]:
    """Route after N2 (scaffold_tests).

Issue #335: Updated to route to validation node instead of verify_red."""
    ...

def route_after_validate(
    state: TestingWorkflowState,
) -> Literal["N3_verify_red", "N2_scaffold_tests", "N4_implement_code", "end"]:
    """Route after N2.5 (validate_tests_mechanical).

Issue #335: Routes based on test validation results."""
    ...

def route_after_red(
    state: TestingWorkflowState,
) -> Literal["N4_implement_code", "N2_scaffold_tests", "end"]:
    """Route after N3 (verify_red_phase).

Issue #292: Added N2_scaffold_tests route for exit codes 4/5."""
    ...

def route_after_implement(
    state: TestingWorkflowState,
) -> Literal["N4b_completeness_gate", "end"]:
    """Route after N4 (implement_code).

Issue #147: Routes to N4b completeness gate instead of directly to N5."""
    ...

def route_after_green(
    state: TestingWorkflowState,
) -> Literal["N6_e2e_validation", "N7_finalize", "N4_implement_code", "N2_scaffold_tests", "end"]:
    """Route after N5 (verify_green_phase).

Issue #292: Added N2_scaffold_tests route for exit codes 4/5."""
    ...

def route_after_e2e(
    state: TestingWorkflowState,
) -> Literal["N7_finalize", "N4_implement_code", "end"]:
    """Route after N6 (e2e_validation).

Args:"""
    ...

def route_after_finalize(
    state: TestingWorkflowState,
) -> Literal["N8_document", "end"]:
    """Route after N7 (finalize).

Args:"""
    ...

def build_testing_workflow() -> StateGraph:
    """Build the TDD testing workflow StateGraph.

Issue #147: Added N4b completeness gate between N4 and N5."""
    ...
```

### tests/fixtures/mock_lineage/001-lld.md (signatures)

```python
# 180 - Feature: N9 Cleanup Node

## 1. Context & Goal

Mock LLD for testing lineage extraction.

## 2. Proposed Changes

- Add cleanup node
- Archive lineage

## 3. Requirements

1. Cleanup after merge
2. Generate learning summary
# ... (truncated, syntax error in original)

```

### tests/fixtures/mock_lineage/005-test-scaffold.py (signatures)

```python
"""Mock test scaffold for testing lineage extraction.

Issue #180: N9 Cleanup Node
"""

def test_placeholder():
    """Placeholder test."""
    ...
```

### tests/fixtures/mock_lineage/052-green-phase.txt (signatures)

```python
Green Phase - Iteration 1
=========================

All tests passing.

Coverage: 96.5%
Missing lines: src/cleanup.py:42, src/cleanup.py:55

Test Results:
  33 passed, 0 failed, 0 errors
# ... (truncated, syntax error in original)

```

### tests/unit/test_cleanup_helpers.py (full)

```python
"""Unit tests for N9 cleanup helper functions.

Issue #180: N9 Cleanup Node - Worktree Removal, Lineage Archival, and Learning Summary

Tests: T070–T260 from LLD Section 10.0
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.workflows.testing.nodes.cleanup_helpers import (
    SUBPROCESS_TIMEOUT,
    IterationSnapshot,
    LearningSummaryData,
    archive_lineage,
    build_learning_summary,
    check_pr_merged,
    delete_local_branch,
    detect_stall,
    extract_iteration_data,
    get_worktree_branch,
    remove_worktree,
    render_learning_summary,
    write_learning_summary,
)


# === T070: check_pr_merged returns True ===
class TestCheckPrMerged:
    @patch("assemblyzero.workflows.testing.nodes.cleanup_helpers.subprocess.run")
    def test_check_pr_merged_returns_true(self, mock_run: MagicMock) -> None:
        """T070: gh returns MERGED state."""
        mock_run.return_value = MagicMock(
            stdout="MERGED\n", stderr="", returncode=0
        )
        result = check_pr_merged(
            "https://github.com/martymcenroe/AssemblyZero/pull/42"
        )
        assert result is True
        mock_run.assert_called_once_with(
            [
                "gh", "pr", "view",
                "https://github.com/martymcenroe/AssemblyZero/pull/42",
                "--json", "state", "--jq", ".state",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=SUBPROCESS_TIMEOUT,
        )

    # === T080: check_pr_merged returns False for OPEN ===
    @patch("assemblyzero.workflows.testing.nodes.cleanup_helpers.subprocess.run")
    def test_check_pr_merged_returns_false_open(self, mock_run: MagicMock) -> None:
        """T080: gh returns OPEN state."""
        mock_run.return_value = MagicMock(
            stdout="OPEN\n", stderr="", returncode=0
        )
        result = check_pr_merged(
            "https://github.com/martymcenroe/AssemblyZero/pull/42"
        )
        assert result is False

    # === T090: check_pr_merged invalid URL ===
    def test_check_pr_merged_invalid_url_empty(self) -> None:
        """T090: ValueError raised for empty URL."""
        with pytest.raises(ValueError, match="pr_url cannot be empty"):
            check_pr_merged("")

    def test_check_pr_merged_invalid_url_malformed(self) -> None:
        """T090: ValueError raised for malformed URL."""
        with pytest.raises(ValueError, match="Malformed PR URL"):
            check_pr_merged("not-a-url")

    # === T095: check_pr_merged timeout ===
    @patch("assemblyzero.workflows.testing.nodes.cleanup_helpers.subprocess.run")
    def test_check_pr_merged_timeout(self, mock_run: MagicMock) -> None:
        """T095: TimeoutExpired raised after 10s."""
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd=["gh"], timeout=SUBPROCESS_TIMEOUT
        )
        with pytest.raises(subprocess.TimeoutExpired):
            check_pr_merged(
                "https://github.com/martymcenroe/AssemblyZero/pull/42"
            )


# === T100/T110: remove_worktree ===
class TestRemoveWorktree:
    @patch("assemblyzero.workflows.testing.nodes.cleanup_helpers.subprocess.run")
    def test_remove_worktree_success(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """T100: git worktree remove succeeds, returns True."""
        worktree_dir = tmp_path / "worktree"
        worktree_dir.mkdir()
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = remove_worktree(worktree_dir)
        assert result is True
        mock_run.assert_called_once_with(
            ["git", "worktree", "remove", str(worktree_dir)],
            capture_output=True,
            text=True,
            check=True,
            timeout=SUBPROCESS_TIMEOUT,
        )

    def test_remove_worktree_nonexistent(self, tmp_path: Path) -> None:
        """T110: Worktree path doesn't exist, returns False."""
        result = remove_worktree(tmp_path / "nonexistent")
        assert result is False


# === T120/T130: get_worktree_branch ===
class TestGetWorktreeBranch:
    @patch("assemblyzero.workflows.testing.nodes.cleanup_helpers.subprocess.run")
    def test_get_worktree_branch_found(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """T120: Extracts branch name from git worktree list."""
        # Use a real tmp_path so Path.resolve() produces a stable result
        worktree_dir = tmp_path / "AssemblyZero-180"
        worktree_dir.mkdir()
        resolved_path = str(worktree_dir.resolve())

        main_dir = tmp_path / "AssemblyZero"
        main_dir.mkdir()
        resolved_main = str(main_dir.resolve())

        porcelain_output = (
            f"worktree {resolved_main}\n"
            "HEAD abc123\n"
            "branch refs/heads/main\n"
            "\n"
            f"worktree {resolved_path}\n"
            "HEAD def456\n"
            "branch refs/heads/issue-180-cleanup\n"
            "\n"
        )
        mock_run.return_value = MagicMock(
            stdout=porcelain_output, stderr="", returncode=0
        )
        result = get_worktree_branch(str(worktree_dir))
        assert result == "issue-180-cleanup"

    @patch("assemblyzero.workflows.testing.nodes.cleanup_helpers.subprocess.run")
    def test_get_worktree_branch_not_found(self, mock_run: MagicMock) -> None:
        """T130: Returns None for unknown path."""
        porcelain_output = (
            "worktree /home/user/Projects/AssemblyZero\n"
            "HEAD abc123\n"
            "branch refs/heads/main\n"
            "\n"
        )
        mock_run.return_value = MagicMock(
            stdout=porcelain_output, stderr="", returncode=0
        )
        result = get_worktree_branch("/home/user/Projects/unknown-worktree")
        assert result is None


# === T140/T150: delete_local_branch ===
class TestDeleteLocalBranch:
    @patch("assemblyzero.workflows.testing.nodes.cleanup_helpers.subprocess.run")
    def test_delete_local_branch_success(self, mock_run: MagicMock) -> None:
        """T140: git branch -D succeeds, returns True."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = delete_local_branch("issue-180-cleanup")
        assert result is True
        mock_run.assert_called_once_with(
            ["git", "branch", "-D", "issue-180-cleanup"],
            capture_output=True,
            text=True,
            check=True,
            timeout=SUBPROCESS_TIMEOUT,
        )

    @patch("assemblyzero.workflows.testing.nodes.cleanup_helpers.subprocess.run")
    def test_delete_local_branch_not_found(self, mock_run: MagicMock) -> None:
        """T150: Branch doesn't exist, returns False."""
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["git", "branch", "-D", "nonexistent"],
            stderr="error: branch 'nonexistent' not found.",
        )
        result = delete_local_branch("nonexistent")
        assert result is False


# === T160/T170/T180: archive_lineage ===
class TestArchiveLineage:
    def test_archive_lineage_moves_directory(self, tmp_path: Path) -> None:
        """T160: active/ moved to done/, returns done path."""
        repo_root = tmp_path / "repo"
        active_dir = repo_root / "docs" / "lineage" / "active" / "180-testing"
        active_dir.mkdir(parents=True)
        (active_dir / "001-lld.md").write_text("# LLD")

        result = archive_lineage(repo_root, 180)

        expected = repo_root / "docs" / "lineage" / "done" / "180-testing"
        assert result == expected
        assert expected.exists()
        assert (expected / "001-lld.md").read_text() == "# LLD"
        assert not active_dir.exists()

    def test_archive_lineage_active_not_found(self, tmp_path: Path) -> None:
        """T170: Returns None, no error."""
        result = archive_lineage(tmp_path, 999)
        assert result is None

    def test_archive_lineage_done_already_exists(self, tmp_path: Path) -> None:
        """T180: Appends timestamp suffix to avoid collision."""
        repo_root = tmp_path / "repo"
        active_dir = repo_root / "docs" / "lineage" / "active" / "180-testing"
        active_dir.mkdir(parents=True)
        (active_dir / "file.txt").write_text("data")

        # Pre-create done/ to cause collision
        done_dir = repo_root / "docs" / "lineage" / "done" / "180-testing"
        done_dir.mkdir(parents=True)

        result = archive_lineage(repo_root, 180)

        assert result is not None
        assert result != done_dir  # Different path (has timestamp suffix)
        assert result.exists()
        assert "180-testing-" in result.name
        assert not active_dir.exists()


# === T190/T200: extract_iteration_data ===
class TestExtractIterationData:
    def test_extract_iteration_data_parses_green_phase(
        self, tmp_path: Path
    ) -> None:
        """T190: Parses coverage from green-phase files."""
        lineage_dir = tmp_path / "180-testing"
        lineage_dir.mkdir()
        (lineage_dir / "052-green-phase.txt").write_text(
            "Green Phase\nCoverage: 98.5%\nMissing lines: src/x.py:10, src/x.py:20"
        )

        result = extract_iteration_data(lineage_dir)

        assert len(result) == 1
        assert result[0].iteration == 1
        assert result[0].coverage_pct == 98.5
        assert result[0].missing_lines == ["src/x.py:10", "src/x.py:20"]

    def test_extract_iteration_data_empty_dir(self, tmp_path: Path) -> None:
        """T200: Returns empty list for empty directory."""
        lineage_dir = tmp_path / "180-testing"
        lineage_dir.mkdir()

        result = extract_iteration_data(lineage_dir)
        assert result == []

    def test_extract_iteration_data_nonexistent_dir(self, tmp_path: Path) -> None:
        """Returns empty list for nonexistent directory."""
        result = extract_iteration_data(tmp_path / "nonexistent")
        assert result == []


# === T210/T220: detect_stall ===
class TestDetectStall:
    def test_detect_stall_found(self) -> None:
        """T210: Detects consecutive equal coverage."""
        snapshots = [
            IterationSnapshot(iteration=1, coverage_pct=85.0),
            IterationSnapshot(iteration=2, coverage_pct=85.0),
            IterationSnapshot(iteration=3, coverage_pct=88.0),
        ]
        result = detect_stall(snapshots)
        assert result == (True, 2)

    def test_detect_stall_not_found(self) -> None:
        """T220: Returns (False, None) for monotonic increase."""
        snapshots = [
            IterationSnapshot(iteration=1, coverage_pct=80.0),
            IterationSnapshot(iteration=2, coverage_pct=85.0),
            IterationSnapshot(iteration=3, coverage_pct=90.0),
            IterationSnapshot(iteration=4, coverage_pct=95.0),
        ]
        result = detect_stall(snapshots)
        assert result == (False, None)

    def test_detect_stall_empty(self) -> None:
        """Empty list returns no stall."""
        assert detect_stall([]) == (False, None)

    def test_detect_stall_single(self) -> None:
        """Single snapshot returns no stall."""
        assert detect_stall([IterationSnapshot(1, 80.0)]) == (False, None)


# === T230: build_learning_summary ===
class TestBuildLearningSummary:
    def test_build_learning_summary_full(self, tmp_path: Path) -> None:
        """T230: Builds complete LearningSummaryData from fixtures."""
        lineage_dir = tmp_path / "180-testing"
        lineage_dir.mkdir()
        (lineage_dir / "001-lld.md").write_text("# LLD")
        (lineage_dir / "005-test-scaffold.py").write_text("def test(): pass")
        (lineage_dir / "052-green-phase.txt").write_text(
            "Coverage: 96.5%\nMissing lines: cleanup.py:42"
        )

        result = build_learning_summary(
            lineage_dir,
            issue_number=180,
            outcome="SUCCESS",
            final_coverage=96.5,
            target_coverage=95.0,
        )

        assert result.issue_number == 180
        assert result.outcome == "SUCCESS"
        assert result.final_coverage == 96.5
        assert result.target_coverage == 95.0
        assert result.total_iterations == 1
        assert len(result.key_artifacts) == 3  # lld, scaffold, green-phase
        assert len(result.what_worked) > 0
        assert len(result.recommendations) > 0


# === T240/T250: render_learning_summary ===
class TestRenderLearningSummary:
    def test_render_learning_summary_markdown(self) -> None:
        """T240: Renders all sections to valid markdown including version header."""
        data = LearningSummaryData(
            issue_number=180,
            outcome="SUCCESS",
            final_coverage=96.5,
            target_coverage=95.0,
            total_iterations=3,
            stall_detected=False,
            stall_iteration=None,
            iteration_snapshots=[
                IterationSnapshot(1, 72.0, ["cleanup.py:10-30"], ""),
                IterationSnapshot(2, 85.0, ["cleanup.py:42"], ""),
                IterationSnapshot(3, 96.5, [], ""),
            ],
            key_artifacts=[("001-lld.md", "LLD document")],
            what_worked=["TDD loop converged"],
            what_didnt_work=[],
            recommendations=["No recommendations"],
        )

        result = render_learning_summary(data)

        assert "# Learning Summary" in result
        assert "Issue #180" in result
        assert "## Format Version: 1.0" in result
        assert "## Outcome" in result
        assert "## Coverage Gap Analysis" in result
        assert "## Stall Analysis" in result
        assert "## Key Artifacts" in result
        assert "## What Worked" in result
        assert "## What Didn't Work" in result
        assert "## Recommendations" in result
        assert "96.5%" in result
        assert "SUCCESS" in result

    def test_render_learning_summary_with_stall(self) -> None:
        """T250: Stall info included in rendered output."""
        data = LearningSummaryData(
            issue_number=42,
            outcome="FAILURE",
            final_coverage=85.0,
            target_coverage=95.0,
            total_iterations=3,
            stall_detected=True,
            stall_iteration=2,
            iteration_snapshots=[
                IterationSnapshot(1, 85.0),
                IterationSnapshot(2, 85.0),
                IterationSnapshot(3, 85.0),
            ],
            key_artifacts=[],
            what_worked=[],
            what_didnt_work=["Coverage stalled"],
            recommendations=["Split functions"],
        )

        result = render_learning_summary(data)

        assert "Stall detected:** Yes" in result
        assert "Stall iteration:** 2" in result


# === T260: write_learning_summary ===
class TestWriteLearningSummary:
    def test_write_learning_summary_creates_file(self, tmp_path: Path) -> None:
        """T260: File written to correct path."""
        lineage_dir = tmp_path / "180-testing"
        lineage_dir.mkdir()
        content = "# Learning Summary\n\n## Format Version: 1.0\n"

        result = write_learning_summary(lineage_dir, content)

        expected_path = lineage_dir / "learning-summary.md"
        assert result == expected_path
        assert expected_path.exists()
        assert expected_path.read_text(encoding="utf-8") == content
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
collecting ... collected 40 items

tests/unit/test_cleanup_helpers.py::TestCheckPrMerged::test_check_pr_merged_returns_true PASSED [  2%]
tests/unit/test_cleanup_helpers.py::TestCheckPrMerged::test_check_pr_merged_returns_false_open PASSED [  5%]
tests/unit/test_cleanup_helpers.py::TestCheckPrMerged::test_check_pr_merged_invalid_url_empty PASSED [  7%]
tests/unit/test_cleanup_helpers.py::TestCheckPrMerged::test_check_pr_merged_invalid_url_malformed PASSED [ 10%]
tests/unit/test_cleanup_helpers.py::TestCheckPrMerged::test_check_pr_merged_timeout PASSED [ 12%]
tests/unit/test_cleanup_helpers.py::TestRemoveWorktree::test_remove_worktree_success PASSED [ 15%]
tests/unit/test_cleanup_helpers.py::TestRemoveWorktree::test_remove_worktree_nonexistent PASSED [ 17%]
tests/unit/test_cleanup_helpers.py::TestGetWorktreeBranch::test_get_worktree_branch_found FAILED [ 20%]
tests/unit/test_cleanup_helpers.py::TestGetWorktreeBranch::test_get_worktree_branch_not_found PASSED [ 22%]
tests/unit/test_cleanup_helpers.py::TestDeleteLocalBranch::test_delete_local_branch_success PASSED [ 25%]
tests/unit/test_cleanup_helpers.py::TestDeleteLocalBranch::test_delete_local_branch_not_found PASSED [ 27%]
tests/unit/test_cleanup_helpers.py::TestArchiveLineage::test_archive_lineage_moves_directory PASSED [ 30%]
tests/unit/test_cleanup_helpers.py::TestArchiveLineage::test_archive_lineage_active_not_found PASSED [ 32%]
tests/unit/test_cleanup_helpers.py::TestArchiveLineage::test_archive_lineage_done_already_exists PASSED [ 35%]
tests/unit/test_cleanup_helpers.py::TestExtractIterationData::test_extract_iteration_data_parses_green_phase PASSED [ 37%]
tests/unit/test_cleanup_helpers.py::TestExtractIterationData::test_extract_iteration_data_empty_dir PASSED [ 40%]
tests/unit/test_cleanup_helpers.py::TestExtractIterationData::test_extract_iteration_data_nonexistent_dir PASSED [ 42%]
tests/unit/test_cleanup_helpers.py::TestDetectStall::test_detect_stall_found PASSED [ 45%]
tests/unit/test_cleanup_helpers.py::TestDetectStall::test_detect_stall_not_found PASSED [ 47%]
tests/unit/test_cleanup_helpers.py::TestDetectStall::test_detect_stall_empty PASSED [ 50%]
tests/unit/test_cleanup_helpers.py::TestDetectStall::test_detect_stall_single PASSED [ 52%]
tests/unit/test_cleanup_helpers.py::TestBuildLearningSummary::test_build_learning_summary_full PASSED [ 55%]
tests/unit/test_cleanup_helpers.py::TestRenderLearningSummary::test_render_learning_summary_markdown PASSED [ 57%]
tests/unit/test_cleanup_helpers.py::TestRenderLearningSummary::test_render_learning_summary_with_stall PASSED [ 60%]
tests/unit/test_cleanup_helpers.py::TestWriteLearningSummary::test_write_learning_summary_creates_file FAILED [ 62%]
tests/unit/test_cleanup.py::TestRouteAfterDocument::test_route_has_issue PASSED [ 65%]
tests/unit/test_cleanup.py::TestRouteAfterDocument::test_route_no_issue PASSED [ 67%]
tests/unit/test_cleanup.py::TestRouteAfterDocument::test_route_issue_zero PASSED [ 70%]
tests/unit/test_cleanup.py::TestRouteAfterDocument::test_route_issue_none PASSED [ 72%]
tests/unit/test_cleanup.py::TestGraphWiring::test_cleanup_node_wired_in_graph PASSED [ 75%]
tests/unit/test_cleanup.py::TestCleanupHappyPath::test_cleanup_happy_path_pr_merged PASSED [ 77%]
tests/unit/test_cleanup.py::TestCleanupPrNotMerged::test_cleanup_pr_not_merged_skips_worktree_keeps_active PASSED [ 80%]
tests/unit/test_cleanup.py::TestCleanupNoPrUrl::test_cleanup_no_pr_url_skips_worktree PASSED [ 82%]
tests/unit/test_cleanup.py::TestCleanupNoLineageDir::test_cleanup_no_lineage_dir_skips_archival PASSED [ 85%]
tests/unit/test_cleanup.py::TestCleanupDirtyWorktree::test_cleanup_worktree_dirty_skips_removal PASSED [ 87%]
tests/unit/test_cleanup.py::TestCleanupErrorHandling::test_cleanup_all_errors_caught PASSED [ 90%]
tests/unit/test_cleanup.py::TestCleanupErrorHandling::test_cleanup_called_process_error_caught PASSED [ 92%]
tests/unit/test_cleanup.py::TestCleanupStateFields::test_cleanup_state_fields_updated PASSED [ 95%]
tests/unit/test_cleanup.py::TestCleanupSummaryPaths::test_cleanup_pr_not_merged_summary_in_active FAILED [ 97%]
tests/unit/test_cleanup.py::TestCleanupSummaryPaths::test_cleanup_pr_merged_summary_in_done FAILED [100%]

================================== FAILURES ===================================
____________ TestGetWorktreeBranch.test_get_worktree_branch_found _____________
tests\unit\test_cleanup_helpers.py:139: in test_get_worktree_branch_found
    assert result == "issue-180-cleanup"
E   AssertionError: assert None == 'issue-180-cleanup'
______ TestWriteLearningSummary.test_write_learning_summary_creates_file ______
tests\unit\test_cleanup_helpers.py:399: in test_write_learning_summary_creates_file
    assert expected_path.read_text() == content
E   AssertionError: assert '# Learning S...ersion: 1.0\n' == '# Learning S...ersion: 1.0\n'
E     
E     - # Learning Summary � Issue #180
E     ?                    ^
E     + # Learning Summary — Issue #180
E     ?                    ^^^
E       
E       ## Format Version: 1.0
____ TestCleanupSummaryPaths.test_cleanup_pr_not_merged_summary_in_active _____
tests\unit\test_cleanup.py:357: in test_cleanup_pr_not_merged_summary_in_active
    assert "/active/" in result["learning_summary_path"]
E   AssertionError: assert '/active/' in 'C:\\Users\\mcwiz\\AppData\\Local\\Temp\\pytest-of-mcwiz\\pytest-901\\test_cleanup_pr_not_merged_sum0\\repo\\docs\\lineage\\active\\180-testing\\learning-summary.md'
_______ TestCleanupSummaryPaths.test_cleanup_pr_merged_summary_in_done ________
tests\unit\test_cleanup.py:408: in test_cleanup_pr_merged_summary_in_done
    assert "/done/" in result["learning_summary_path"]
E   AssertionError: assert '/done/' in 'C:\\Users\\mcwiz\\AppData\\Local\\Temp\\pytest-of-mcwiz\\pytest-901\\test_cleanup_pr_merged_summary0\\repo\\docs\\lineage\\done\\180-testing\\learning-summary.md'
============================== warnings summary ===============================
..\..\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\langchain_core\_api\deprecation.py:25
  C:\Users\mcwiz\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\langchain_core\_api\deprecation.py:25: UserWarning: Core Pydantic V1 functionality isn't compatible with Python 3.14 or greater.
    from pydantic.v1.fields import FieldInfo as FieldInfoV1

..\..\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\google\genai\types.py:43
  C:\Users\mcwiz\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\google\genai\types.py:43: DeprecationWarning: '_UnionGenericAlias' is deprecated and slated for removal in Python 3.17
    VersionedUnionType = Union[builtin_types.UnionType, _UnionGenericAlias]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=============================== tests coverage ================================
_______________ coverage: platform win32, python 3.14.0-final-0 _______________

Name                                      Stmts   Miss  Cover   Missing
-----------------------------------------------------------------------
assemblyzero\workflows\testing\state.py      13      0   100%
-----------------------------------------------------------------------
TOTAL                                        13      0   100%
Required test coverage of 95% reached. Total coverage: 100.00%
=========================== short test summary info ===========================
FAILED tests/unit/test_cleanup_helpers.py::TestGetWorktreeBranch::test_get_worktree_branch_found
FAILED tests/unit/test_cleanup_helpers.py::TestWriteLearningSummary::test_write_learning_summary_creates_file
FAILED tests/unit/test_cleanup.py::TestCleanupSummaryPaths::test_cleanup_pr_not_merged_summary_in_active
FAILED tests/unit/test_cleanup.py::TestCleanupSummaryPaths::test_cleanup_pr_merged_summary_in_done
================== 4 failed, 36 passed, 2 warnings in 1.36s ===================


```

Fix the issue in your implementation.

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
