# Implementation Request: assemblyzero/workflows/janitor/fixers.py

## Task

Write the complete contents of `assemblyzero/workflows/janitor/fixers.py`.

Change type: Add
Description: Auto-fix implementations for links and worktrees

## LLD Specification

# Implementation Spec: Lu-Tze: The Janitor - Automated Repository Hygiene Workflow

| Field | Value |
|-------|-------|
| Issue | #94 |
| LLD | `docs/lld/active/94-janitor-workflow.md` |
| Generated | 2026-03-02 |
| Status | DRAFT |

## 1. Overview

Implement an automated repository hygiene workflow ("The Janitor") as a LangGraph state machine with three nodes: Sweeper (runs probes to detect issues), Fixer (auto-fixes broken links and stale worktrees), and Reporter (creates/updates GitHub issues or local reports). The workflow supports four probes (links, worktrees, harvest, todo) with crash isolation, deterministic commit messages, and configurable reporting backends.

**Objective:** Automated detection and remediation of repository hygiene issues (broken links, stale worktrees, cross-project drift, stale TODOs) via a LangGraph workflow.

**Success Criteria:** All 12 requirements from LLD Section 3 pass, ≥95% test coverage, exit codes 0/1/2 reflect workflow outcome.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `assemblyzero/workflows/janitor/__init__.py` | Add | Package init, exports `build_janitor_graph` |
| 2 | `assemblyzero/workflows/janitor/state.py` | Add | `JanitorState` TypedDict + `Finding`, `ProbeResult`, `FixAction` dataclasses |
| 3 | `assemblyzero/workflows/janitor/probes/__init__.py` | Add | Probe registry, `get_probes`, `run_probe_safe` |
| 4 | `assemblyzero/workflows/janitor/probes/links.py` | Add | Broken internal markdown link detection |
| 5 | `assemblyzero/workflows/janitor/probes/worktrees.py` | Add | Stale/detached git worktree detection |
| 6 | `assemblyzero/workflows/janitor/probes/harvest.py` | Add | Cross-project drift via `assemblyzero-harvest.py` |
| 7 | `assemblyzero/workflows/janitor/probes/todo.py` | Add | Stale TODO scanner (>30 days) |
| 8 | `assemblyzero/workflows/janitor/fixers.py` | Add | Auto-fix implementations for links and worktrees |
| 9 | `assemblyzero/workflows/janitor/reporter.py` | Add | `ReporterInterface` ABC, `GitHubReporter`, `LocalFileReporter` |
| 10 | `assemblyzero/workflows/janitor/graph.py` | Add | LangGraph `StateGraph` with nodes + conditional edges |
| 11 | `tools/run_janitor_workflow.py` | Add | CLI entry point with argparse |
| 12 | `.gitignore` | Modify | Add `janitor-reports/` entry |
| 13 | `tests/fixtures/janitor/mock_repo/README.md` | Add | Mock README with broken and valid links |
| 14 | `tests/fixtures/janitor/mock_repo/docs/guide.md` | Add | Mock guide document for valid link testing |
| 15 | `tests/fixtures/janitor/mock_repo/docs/stale-todo.py` | Add | Mock Python file with TODO comments |
| 16 | `tests/unit/test_janitor/__init__.py` | Add | Test package init |
| 17 | `tests/unit/test_janitor/test_state.py` | Add | Tests for state structures |
| 18 | `tests/unit/test_janitor/test_probes.py` | Add | Tests for all four probes |
| 19 | `tests/unit/test_janitor/test_fixers.py` | Add | Tests for fixer logic |
| 20 | `tests/unit/test_janitor/test_reporter.py` | Add | Tests for reporter implementations |
| 21 | `tests/unit/test_janitor/test_graph.py` | Add | Tests for graph construction and routing |
| 22 | `tests/unit/test_janitor/test_cli.py` | Add | Tests for CLI argument parsing |
| 23 | `tests/integration/test_janitor_workflow.py` | Add | Integration test with `LocalFileReporter` |
| 24 | `docs/adrs/0204-janitor-probe-plugin-system.md` | Add | ADR for probe plugin architecture |

**Implementation Order Rationale:** State definitions first (no dependencies), then probes (depend on state), then fixers (depend on state + probes), then reporter (depend on state), then graph (depends on all), then CLI (depends on graph), then modify existing files, then tests, then ADR.

## 3. Current State (for Modify/Delete files)

### 3.1 `.gitignore`

**Relevant excerpt** (lines 44-52, end of file):

```gitignore
# Session transcripts (auto-generated, untracked)
data/unleashed/
data/handoff-log.md
transcripts/
```

**What changes:** Append a new section for janitor report artifacts before the session transcripts block.

## 4. Data Structures

### 4.1 `Severity` (Literal type alias)

**Definition:**

```python
Severity = Literal["info", "warning", "critical"]
```

**Concrete Example:**

```json
"warning"
```

### 4.2 `ProbeScope` (Literal type alias)

**Definition:**

```python
ProbeScope = Literal["links", "worktrees", "harvest", "todo"]
```

**Concrete Example:**

```json
"links"
```

### 4.3 `Finding`

**Definition:**

```python
@dataclass
class Finding:
    probe: ProbeScope
    category: str
    message: str
    severity: Severity
    fixable: bool
    file_path: str | None = None
    line_number: int | None = None
    fix_data: dict | None = None
```

**Concrete Example (fixable broken link):**

```json
{
    "probe": "links",
    "category": "broken_link",
    "message": "Broken link in README.md line 15: ./docs/old-guide.md does not exist",
    "severity": "warning",
    "fixable": true,
    "file_path": "README.md",
    "line_number": 15,
    "fix_data": {
        "old_link": "./docs/old-guide.md",
        "new_link": "./docs/guide.md"
    }
}
```

**Concrete Example (unfixable stale TODO):**

```json
{
    "probe": "todo",
    "category": "stale_todo",
    "message": "TODO comment in tools/helper.py line 42 is 45 days old: 'TODO: refactor this function'",
    "severity": "info",
    "fixable": false,
    "file_path": "tools/helper.py",
    "line_number": 42,
    "fix_data": null
}
```

### 4.4 `ProbeResult`

**Definition:**

```python
@dataclass
class ProbeResult:
    probe: ProbeScope
    status: Literal["ok", "findings", "error"]
    findings: list[Finding] = field(default_factory=list)
    error_message: str | None = None
```

**Concrete Example (findings found):**

```json
{
    "probe": "links",
    "status": "findings",
    "findings": [
        {
            "probe": "links",
            "category": "broken_link",
            "message": "Broken link in README.md line 15: ./docs/old-guide.md does not exist",
            "severity": "warning",
            "fixable": true,
            "file_path": "README.md",
            "line_number": 15,
            "fix_data": {"old_link": "./docs/old-guide.md", "new_link": "./docs/guide.md"}
        }
    ],
    "error_message": null
}
```

**Concrete Example (probe error):**

```json
{
    "probe": "harvest",
    "status": "error",
    "findings": [],
    "error_message": "RuntimeError: harvest script crashed with exit code 1"
}
```

**Concrete Example (clean):**

```json
{
    "probe": "worktrees",
    "status": "ok",
    "findings": [],
    "error_message": null
}
```

### 4.5 `FixAction`

**Definition:**

```python
@dataclass
class FixAction:
    category: str
    description: str
    files_modified: list[str]
    commit_message: str
    applied: bool
```

**Concrete Example:**

```json
{
    "category": "broken_link",
    "description": "Fixed broken link in README.md: ./docs/old-guide.md → ./docs/guide.md",
    "files_modified": ["README.md"],
    "commit_message": "chore: fix 1 broken markdown link(s) (ref #94)",
    "applied": true
}
```

**Concrete Example (dry-run):**

```json
{
    "category": "stale_worktree",
    "description": "Would prune stale worktree at /home/user/projects/AssemblyZero-42",
    "files_modified": [],
    "commit_message": "chore: prune 1 stale worktree(s) (ref #94)",
    "applied": false
}
```

### 4.6 `JanitorState`

**Definition:**

```python
class JanitorState(TypedDict):
    repo_root: str
    scope: list[ProbeScope]
    auto_fix: bool
    dry_run: bool
    silent: bool
    create_pr: bool
    reporter_type: Literal["github", "local"]
    probe_results: list[ProbeResult]
    all_findings: list[Finding]
    fix_actions: list[FixAction]
    unfixable_findings: list[Finding]
    report_url: str | None
    exit_code: int
```

**Concrete Example (initial state):**

```json
{
    "repo_root": "/home/user/projects/AssemblyZero",
    "scope": ["links", "worktrees", "harvest", "todo"],
    "auto_fix": true,
    "dry_run": false,
    "silent": false,
    "create_pr": false,
    "reporter_type": "github",
    "probe_results": [],
    "all_findings": [],
    "fix_actions": [],
    "unfixable_findings": [],
    "report_url": null,
    "exit_code": 0
}
```

**Concrete Example (after sweeper):**

```json
{
    "repo_root": "/home/user/projects/AssemblyZero",
    "scope": ["links", "worktrees"],
    "auto_fix": true,
    "dry_run": false,
    "silent": false,
    "create_pr": false,
    "reporter_type": "local",
    "probe_results": [
        {"probe": "links", "status": "findings", "findings": [{"probe": "links", "category": "broken_link", "message": "...", "severity": "warning", "fixable": true, "file_path": "README.md", "line_number": 15, "fix_data": {"old_link": "./docs/old-guide.md", "new_link": "./docs/guide.md"}}], "error_message": null},
        {"probe": "worktrees", "status": "ok", "findings": [], "error_message": null}
    ],
    "all_findings": [
        {"probe": "links", "category": "broken_link", "message": "...", "severity": "warning", "fixable": true, "file_path": "README.md", "line_number": 15, "fix_data": {"old_link": "./docs/old-guide.md", "new_link": "./docs/guide.md"}}
    ],
    "fix_actions": [],
    "unfixable_findings": [],
    "report_url": null,
    "exit_code": 0
}
```

## 5. Function Specifications

### 5.1 `build_janitor_graph()`

**File:** `assemblyzero/workflows/janitor/graph.py`

**Signature:**

```python
from langgraph.graph import StateGraph, END

def build_janitor_graph() -> StateGraph:
    """Build and compile the LangGraph state graph for the janitor workflow."""
    ...
```

**Input Example:** No inputs.

**Output Example:** Compiled `StateGraph` with nodes `n0_sweeper`, `n1_fixer`, `n2_reporter` and conditional edges.

**Edge Cases:**
- Always succeeds — pure graph definition, no I/O.

### 5.2 `n0_sweeper()`

**File:** `assemblyzero/workflows/janitor/graph.py`

**Signature:**

```python
def n0_sweeper(state: JanitorState) -> dict:
    """Execute all probes in scope and collect findings."""
    ...
```

**Input Example:**

```python
state = {
    "repo_root": "/home/user/projects/AssemblyZero",
    "scope": ["links", "worktrees"],
    "auto_fix": True,
    "dry_run": False,
    "silent": False,
    "create_pr": False,
    "reporter_type": "local",
    "probe_results": [],
    "all_findings": [],
    "fix_actions": [],
    "unfixable_findings": [],
    "report_url": None,
    "exit_code": 0,
}
```

**Output Example:**

```python
{
    "probe_results": [
        ProbeResult(probe="links", status="findings", findings=[...], error_message=None),
        ProbeResult(probe="worktrees", status="ok", findings=[], error_message=None),
    ],
    "all_findings": [
        Finding(probe="links", category="broken_link", message="...", severity="warning", fixable=True, file_path="README.md", line_number=15, fix_data={"old_link": "./docs/old-guide.md", "new_link": "./docs/guide.md"}),
    ],
}
```

**Edge Cases:**
- Empty `scope` list → returns empty `probe_results` and `all_findings`
- Probe crashes → `run_probe_safe` catches it; error `ProbeResult` included

### 5.3 `n1_fixer()`

**File:** `assemblyzero/workflows/janitor/graph.py`

**Signature:**

```python
def n1_fixer(state: JanitorState) -> dict:
    """Apply auto-fixes for all fixable findings."""
    ...
```

**Input Example:**

```python
state = {
    "repo_root": "/home/user/projects/AssemblyZero",
    "dry_run": False,
    "create_pr": False,
    "all_findings": [
        Finding(probe="links", category="broken_link", message="...", severity="warning", fixable=True, file_path="README.md", line_number=15, fix_data={"old_link": "./docs/old-guide.md", "new_link": "./docs/guide.md"}),
        Finding(probe="todo", category="stale_todo", message="...", severity="info", fixable=False, file_path="tools/helper.py", line_number=42, fix_data=None),
    ],
    # ... other fields
}
```

**Output Example:**

```python
{
    "fix_actions": [
        FixAction(category="broken_link", description="Fixed broken link in README.md: ./docs/old-guide.md → ./docs/guide.md", files_modified=["README.md"], commit_message="chore: fix 1 broken markdown link(s) (ref #94)", applied=True),
    ],
    "unfixable_findings": [
        Finding(probe="todo", category="stale_todo", message="...", severity="info", fixable=False, file_path="tools/helper.py", line_number=42, fix_data=None),
    ],
}
```

**Edge Cases:**
- No fixable findings → `fix_actions=[]`, all findings go to `unfixable_findings`
- `dry_run=True` → `FixAction.applied=False`, no file writes or git commits
- `create_pr=True` → creates branch and PR via `create_fix_pr`

### 5.4 `n2_reporter()`

**File:** `assemblyzero/workflows/janitor/graph.py`

**Signature:**

```python
def n2_reporter(state: JanitorState) -> dict:
    """Report unfixable findings via the configured reporter backend."""
    ...
```

**Input Example:**

```python
state = {
    "repo_root": "/home/user/projects/AssemblyZero",
    "reporter_type": "local",
    "unfixable_findings": [
        Finding(probe="todo", category="stale_todo", message="TODO in helper.py:42 is 45 days old", severity="info", fixable=False, file_path="tools/helper.py", line_number=42, fix_data=None),
    ],
    "fix_actions": [],
    "probe_results": [...],
    # ... other fields
}
```

**Output Example:**

```python
{
    "report_url": "/home/user/projects/AssemblyZero/janitor-reports/janitor-report-2026-03-02-143022.md",
    "exit_code": 1,
}
```

**Edge Cases:**
- `reporter_type="github"` → uses `GitHubReporter`; if `gh` CLI fails, raises appropriate error
- Empty `unfixable_findings` → should not reach this node (routing should send to END)

### 5.5 `route_after_sweep()`

**File:** `assemblyzero/workflows/janitor/graph.py`

**Signature:**

```python
def route_after_sweep(state: JanitorState) -> str:
    """Conditional routing after n0_sweeper completes."""
    ...
```

**Input/Output Examples:**

```python
# No findings
state = {"all_findings": [], "auto_fix": True}
route_after_sweep(state)  # → "__end__"

# Fixable findings + auto_fix=True
state = {"all_findings": [Finding(..., fixable=True)], "auto_fix": True}
route_after_sweep(state)  # → "n1_fixer"

# Fixable findings + auto_fix=False
state = {"all_findings": [Finding(..., fixable=True)], "auto_fix": False}
route_after_sweep(state)  # → "n2_reporter"

# Only unfixable findings
state = {"all_findings": [Finding(..., fixable=False)], "auto_fix": True}
route_after_sweep(state)  # → "n2_reporter"
```

### 5.6 `route_after_fix()`

**File:** `assemblyzero/workflows/janitor/graph.py`

**Signature:**

```python
def route_after_fix(state: JanitorState) -> str:
    """Conditional routing after n1_fixer completes."""
    ...
```

**Input/Output Examples:**

```python
# All fixed
state = {"unfixable_findings": []}
route_after_fix(state)  # → "__end__"

# Unfixable remain
state = {"unfixable_findings": [Finding(..., fixable=False)]}
route_after_fix(state)  # → "n2_reporter"
```

### 5.7 `get_probes()`

**File:** `assemblyzero/workflows/janitor/probes/__init__.py`

**Signature:**

```python
from typing import Callable
from assemblyzero.workflows.janitor.state import ProbeResult, ProbeScope

ProbeFunction = Callable[[str], ProbeResult]

def get_probes(scopes: list[ProbeScope]) -> list[tuple[ProbeScope, ProbeFunction]]:
    """Return probe functions for the requested scopes."""
    ...
```

**Input Example:**

```python
scopes = ["links", "worktrees"]
```

**Output Example:**

```python
[("links", probe_links), ("worktrees", probe_worktrees)]
```

**Edge Cases:**
- `scopes = ["invalid"]` → raises `ValueError("Unknown probe scope: invalid")`
- `scopes = []` → returns `[]`

### 5.8 `run_probe_safe()`

**File:** `assemblyzero/workflows/janitor/probes/__init__.py`

**Signature:**

```python
def run_probe_safe(probe_name: ProbeScope, probe_fn: ProbeFunction, repo_root: str) -> ProbeResult:
    """Execute a probe with crash isolation."""
    ...
```

**Input Example:**

```python
probe_name = "links"
probe_fn = probe_links  # or a function that raises RuntimeError
repo_root = "/home/user/projects/AssemblyZero"
```

**Output Example (success):**

```python
ProbeResult(probe="links", status="findings", findings=[...], error_message=None)
```

**Output Example (crash):**

```python
ProbeResult(probe="links", status="error", findings=[], error_message="RuntimeError: file not found")
```

### 5.9 `probe_links()`

**File:** `assemblyzero/workflows/janitor/probes/links.py`

**Signature:**

```python
def probe_links(repo_root: str) -> ProbeResult:
    """Scan all markdown files for broken internal links."""
    ...
```

**Input Example:**

```python
repo_root = "/home/user/projects/AssemblyZero"
```

**Output Example (findings):**

```python
ProbeResult(
    probe="links",
    status="findings",
    findings=[
        Finding(
            probe="links",
            category="broken_link",
            message="Broken link in README.md line 15: ./docs/old-guide.md does not exist",
            severity="warning",
            fixable=True,
            file_path="README.md",
            line_number=15,
            fix_data={"old_link": "./docs/old-guide.md", "new_link": "./docs/guide.md"},
        )
    ],
    error_message=None,
)
```

**Output Example (clean):**

```python
ProbeResult(probe="links", status="ok", findings=[], error_message=None)
```

**Edge Cases:**
- No `.md` files in repo → returns `status="ok"`, empty findings
- External URLs (http/https) → skipped, not checked

### 5.10 `find_markdown_files()`

**File:** `assemblyzero/workflows/janitor/probes/links.py`

**Signature:**

```python
def find_markdown_files(repo_root: str) -> list[str]:
    """Find all .md files in repo, respecting .gitignore patterns."""
    ...
```

**Input Example:**

```python
repo_root = "/home/user/projects/AssemblyZero"
```

**Output Example:**

```python
[
    "/home/user/projects/AssemblyZero/README.md",
    "/home/user/projects/AssemblyZero/docs/guide.md",
    "/home/user/projects/AssemblyZero/docs/adrs/0001-example.md",
]
```

**Implementation Note:** Use `subprocess.run(["git", "ls-files", "*.md"], ...)` to respect `.gitignore`.

### 5.11 `extract_internal_links()`

**File:** `assemblyzero/workflows/janitor/probes/links.py`

**Signature:**

```python
def extract_internal_links(file_path: str) -> list[tuple[int, str, str]]:
    """Extract internal links from a markdown file.
    Returns list of (line_number, link_text, link_target) tuples.
    Only returns relative links (not http/https URLs).
    """
    ...
```

**Input Example:**

```python
file_path = "/home/user/projects/AssemblyZero/README.md"
# File contents:
# Line 1: # README
# Line 2: See the [guide](./docs/guide.md) for details.
# Line 3: Visit [website](https://example.com) for more.
# Line 4: ![diagram](./images/arch.png)
```

**Output Example:**

```python
[
    (2, "guide", "./docs/guide.md"),
    (4, "diagram", "./images/arch.png"),
]
# Note: line 3 excluded (external URL)
```

**Implementation Note:** Use regex pattern `r'\[([^\]]*)\]\(([^)]+)\)'` and filter out targets starting with `http://`, `https://`, or `#` (anchor-only links handled separately).

### 5.12 `resolve_link()`

**File:** `assemblyzero/workflows/janitor/probes/links.py`

**Signature:**

```python
def resolve_link(source_file: str, link_target: str, repo_root: str) -> bool:
    """Check if a relative link target resolves to an existing file."""
    ...
```

**Input/Output Examples:**

```python
# Link exists
resolve_link("/repo/README.md", "./docs/guide.md", "/repo")  # → True

# Link broken
resolve_link("/repo/README.md", "./docs/old-guide.md", "/repo")  # → False

# Anchor link (contains #)
resolve_link("/repo/README.md", "./docs/guide.md#section", "/repo")  # → True (file part exists)
```

**Implementation Note:** Use `pathlib.Path` to resolve relative to source file's directory. Strip anchor fragments (`#...`) before checking existence.

### 5.13 `find_likely_target()`

**File:** `assemblyzero/workflows/janitor/probes/links.py`

**Signature:**

```python
def find_likely_target(broken_target: str, repo_root: str) -> str | None:
    """Attempt to find the intended target of a broken link.
    Returns relative path to best match, or None if ambiguous/not found.
    """
    ...
```

**Input/Output Examples:**

```python
# Unique match found
find_likely_target("./docs/old-guide.md", "/repo")
# → "./docs/guide.md" (found guide.md in docs/)

# No match
find_likely_target("./docs/nonexistent.md", "/repo")
# → None

# Multiple matches (ambiguous)
find_likely_target("./README.md", "/repo")
# → None (multiple README.md files found)
```

**Implementation:** Extract basename from `broken_target`, search for files with same basename using `git ls-files`. If exactly one match found, return it. If zero or multiple, return `None`.

### 5.14 `probe_worktrees()`

**File:** `assemblyzero/workflows/janitor/probes/worktrees.py`

**Signature:**

```python
def probe_worktrees(repo_root: str) -> ProbeResult:
    """Detect stale and detached git worktrees."""
    ...
```

**Input Example:**

```python
repo_root = "/home/user/projects/AssemblyZero"
```

**Output Example:**

```python
ProbeResult(
    probe="worktrees",
    status="findings",
    findings=[
        Finding(
            probe="worktrees",
            category="stale_worktree",
            message="Stale worktree at /home/user/projects/AssemblyZero-42: branch feature/old-thing merged to main, last commit 15 days ago",
            severity="warning",
            fixable=True,
            file_path="/home/user/projects/AssemblyZero-42",
            line_number=None,
            fix_data={"worktree_path": "/home/user/projects/AssemblyZero-42", "branch": "feature/old-thing"},
        )
    ],
    error_message=None,
)
```

### 5.15 `list_worktrees()`

**File:** `assemblyzero/workflows/janitor/probes/worktrees.py`

**Signature:**

```python
def list_worktrees(repo_root: str) -> list[dict]:
    """Parse output of `git worktree list --porcelain`."""
    ...
```

**Input Example:**

```python
repo_root = "/home/user/projects/AssemblyZero"
# git worktree list --porcelain output:
# worktree /home/user/projects/AssemblyZero
# HEAD abc123def456
# branch refs/heads/main
#
# worktree /home/user/projects/AssemblyZero-42
# HEAD def789abc012
# branch refs/heads/feature/old-thing
#
```

**Output Example:**

```python
[
    {"path": "/home/user/projects/AssemblyZero", "HEAD": "abc123def456", "branch": "refs/heads/main", "bare": False, "detached": False},
    {"path": "/home/user/projects/AssemblyZero-42", "HEAD": "def789abc012", "branch": "refs/heads/feature/old-thing", "bare": False, "detached": False},
]
```

**Edge Cases:**
- Detached HEAD worktree → `"branch"` key absent, `"detached": True`
- Bare worktree → `"bare": True`
- Main worktree (first entry) should be filtered out from stale checks

### 5.16 `get_branch_last_commit_date()`

**File:** `assemblyzero/workflows/janitor/probes/worktrees.py`

**Signature:**

```python
from datetime import datetime

def get_branch_last_commit_date(repo_root: str, branch: str) -> datetime | None:
    """Get the date of the most recent commit on a branch."""
    ...
```

**Input/Output Examples:**

```python
get_branch_last_commit_date("/repo", "feature/old-thing")
# → datetime(2026, 2, 15, 10, 30, 0)

get_branch_last_commit_date("/repo", "nonexistent-branch")
# → None
```

**Implementation:** Use `subprocess.run(["git", "log", "-1", "--format=%aI", branch], ...)` and parse ISO 8601 date.

### 5.17 `is_branch_merged()`

**File:** `assemblyzero/workflows/janitor/probes/worktrees.py`

**Signature:**

```python
def is_branch_merged(repo_root: str, branch: str, target: str = "main") -> bool:
    """Check if branch has been merged into target branch."""
    ...
```

**Input/Output Examples:**

```python
is_branch_merged("/repo", "feature/old-thing", "main")  # → True
is_branch_merged("/repo", "feature/active-work", "main")  # → False
```

**Implementation:** Use `subprocess.run(["git", "branch", "--merged", target], ...)` and check if branch name appears in output.

### 5.18 `probe_harvest()`

**File:** `assemblyzero/workflows/janitor/probes/harvest.py`

**Signature:**

```python
def probe_harvest(repo_root: str) -> ProbeResult:
    """Run assemblyzero-harvest.py and parse output for cross-project drift."""
    ...
```

**Input Example:**

```python
repo_root = "/home/user/projects/AssemblyZero"
```

**Output Example (script not found):**

```python
ProbeResult(
    probe="harvest",
    status="findings",
    findings=[
        Finding(
            probe="harvest",
            category="harvest_missing",
            message="assemblyzero-harvest.py not found in repository",
            severity="info",
            fixable=False,
            file_path=None,
            line_number=None,
            fix_data=None,
        )
    ],
    error_message=None,
)
```

**Output Example (drift found):**

```python
ProbeResult(
    probe="harvest",
    status="findings",
    findings=[
        Finding(
            probe="harvest",
            category="cross_project_drift",
            message="DRIFT: assemblyzero-tools/pyproject.toml version mismatch with upstream",
            severity="warning",
            fixable=False,
            file_path=None,
            line_number=None,
            fix_data=None,
        )
    ],
    error_message=None,
)
```

### 5.19 `find_harvest_script()`

**File:** `assemblyzero/workflows/janitor/probes/harvest.py`

**Signature:**

```python
def find_harvest_script(repo_root: str) -> str | None:
    """Locate the assemblyzero-harvest.py script."""
    ...
```

**Input/Output Examples:**

```python
find_harvest_script("/repo")
# → "/repo/assemblyzero-harvest.py" (if exists)
# → "/repo/tools/assemblyzero-harvest.py" (if exists in tools/)
# → None (not found)
```

### 5.20 `parse_harvest_output()`

**File:** `assemblyzero/workflows/janitor/probes/harvest.py`

**Signature:**

```python
def parse_harvest_output(output: str) -> list[Finding]:
    """Parse harvest script stdout into structured findings."""
    ...
```

**Input Example:**

```python
output = """DRIFT: assemblyzero-tools/pyproject.toml version mismatch
OK: assemblyzero/workflows/issue/state.py in sync
DRIFT: docs/standards/0001-naming.md outdated by 3 versions"""
```

**Output Example:**

```python
[
    Finding(probe="harvest", category="cross_project_drift", message="DRIFT: assemblyzero-tools/pyproject.toml version mismatch", severity="warning", fixable=False, file_path=None, line_number=None, fix_data=None),
    Finding(probe="harvest", category="cross_project_drift", message="DRIFT: docs/standards/0001-naming.md outdated by 3 versions", severity="warning", fixable=False, file_path=None, line_number=None, fix_data=None),
]
```

**Implementation:** Filter lines starting with `DRIFT:`, create one `Finding` per drift line. Lines starting with `OK:` are ignored.

### 5.21 `probe_todo()`

**File:** `assemblyzero/workflows/janitor/probes/todo.py`

**Signature:**

```python
def probe_todo(repo_root: str) -> ProbeResult:
    """Scan source files for TODO comments older than 30 days."""
    ...
```

**Input Example:**

```python
repo_root = "/home/user/projects/AssemblyZero"
```

**Output Example:**

```python
ProbeResult(
    probe="todo",
    status="findings",
    findings=[
        Finding(
            probe="todo",
            category="stale_todo",
            message="Stale TODO in tools/helper.py line 42 (45 days old): 'TODO: refactor this function'",
            severity="info",
            fixable=False,
            file_path="tools/helper.py",
            line_number=42,
            fix_data=None,
        )
    ],
    error_message=None,
)
```

### 5.22 `find_source_files()`

**File:** `assemblyzero/workflows/janitor/probes/todo.py`

**Signature:**

```python
def find_source_files(repo_root: str) -> list[str]:
    """Find all tracked source files (*.py, *.md, *.ts, *.js)."""
    ...
```

**Implementation:** Use `subprocess.run(["git", "ls-files", "*.py", "*.md", "*.ts", "*.js"], ...)`.

**Input/Output Examples:**

```python
find_source_files("/repo")
# → ["tools/helper.py", "README.md", "assemblyzero/workflows/janitor/state.py", ...]
```

### 5.23 `extract_todos()`

**File:** `assemblyzero/workflows/janitor/probes/todo.py`

**Signature:**

```python
def extract_todos(file_path: str) -> list[tuple[int, str]]:
    """Extract TODO/FIXME/HACK/XXX comments from a file."""
    ...
```

**Input Example:**

```python
file_path = "/repo/tools/helper.py"
# File contents:
# Line 1: def func():
# Line 2:     # TODO: refactor this function
# Line 3:     pass
# Line 4:     # FIXME: handle edge case
```

**Output Example:**

```python
[(2, "# TODO: refactor this function"), (4, "# FIXME: handle edge case")]
```

**Implementation:** Use regex `r'#\s*(TODO|FIXME|HACK|XXX)\b.*'` (case-insensitive).

### 5.24 `get_line_date()`

**File:** `assemblyzero/workflows/janitor/probes/todo.py`

**Signature:**

```python
def get_line_date(repo_root: str, file_path: str, line_number: int) -> datetime | None:
    """Use git blame to determine when a specific line was last modified."""
    ...
```

**Input/Output Examples:**

```python
get_line_date("/repo", "tools/helper.py", 42)
# → datetime(2026, 1, 15, 14, 30, 0)

get_line_date("/repo", "untracked-file.py", 1)
# → None
```

**Implementation:** Use `subprocess.run(["git", "blame", "-L", f"{line_number},{line_number}", "--porcelain", file_path], ...)` and parse `author-time` field.

### 5.25 `fix_broken_links()`

**File:** `assemblyzero/workflows/janitor/fixers.py`

**Signature:**

```python
def fix_broken_links(findings: list[Finding], repo_root: str, dry_run: bool) -> list[FixAction]:
    """Fix broken markdown links by updating references."""
    ...
```

**Input Example:**

```python
findings = [
    Finding(
        probe="links", category="broken_link",
        message="...", severity="warning", fixable=True,
        file_path="README.md", line_number=15,
        fix_data={"old_link": "./docs/old-guide.md", "new_link": "./docs/guide.md"},
    )
]
repo_root = "/home/user/projects/AssemblyZero"
dry_run = False
```

**Output Example:**

```python
[
    FixAction(
        category="broken_link",
        description="Fixed broken link in README.md: ./docs/old-guide.md → ./docs/guide.md",
        files_modified=["README.md"],
        commit_message="chore: fix 1 broken markdown link(s) (ref #94)",
        applied=True,
    )
]
```

**Edge Cases:**
- `dry_run=True` → reads files, produces `FixAction(applied=False)`, does not write
- Multiple broken links in same file → single file read/write, multiple `FixAction` entries
- `fix_data` missing `new_link` → skip (shouldn't happen, but defensive)

### 5.26 `fix_stale_worktrees()`

**File:** `assemblyzero/workflows/janitor/fixers.py`

**Signature:**

```python
def fix_stale_worktrees(findings: list[Finding], repo_root: str, dry_run: bool) -> list[FixAction]:
    """Prune stale git worktrees."""
    ...
```

**Input Example:**

```python
findings = [
    Finding(
        probe="worktrees", category="stale_worktree",
        message="...", severity="warning", fixable=True,
        file_path="/home/user/projects/AssemblyZero-42", line_number=None,
        fix_data={"worktree_path": "/home/user/projects/AssemblyZero-42", "branch": "feature/old-thing"},
    )
]
repo_root = "/home/user/projects/AssemblyZero"
dry_run = False
```

**Output Example:**

```python
[
    FixAction(
        category="stale_worktree",
        description="Pruned stale worktree at /home/user/projects/AssemblyZero-42 (branch: feature/old-thing)",
        files_modified=[],
        commit_message="chore: prune 1 stale worktree(s) (ref #94)",
        applied=True,
    )
]
```

**Implementation:** Use `subprocess.run(["git", "worktree", "remove", worktree_path], ...)`. In dry-run, skip subprocess call.

### 5.27 `create_fix_commit()`

**File:** `assemblyzero/workflows/janitor/fixers.py`

**Signature:**

```python
def create_fix_commit(repo_root: str, category: str, files: list[str], message: str) -> None:
    """Stage modified files and create a git commit."""
    ...
```

**Input Example:**

```python
repo_root = "/home/user/projects/AssemblyZero"
category = "broken_link"
files = ["README.md"]
message = "chore: fix 1 broken markdown link(s) (ref #94)"
```

**Implementation:**

```python
subprocess.run(["git", "add"] + files, cwd=repo_root, check=True)
subprocess.run(["git", "commit", "-m", message], cwd=repo_root, check=True)
```

**Edge Cases:**
- Empty `files` list → do nothing (no-op, idempotent)
- No changes staged after `git add` → `git commit` will fail; catch and ignore

### 5.28 `generate_commit_message()`

**File:** `assemblyzero/workflows/janitor/fixers.py`

**Signature:**

```python
def generate_commit_message(category: str, count: int, details: list[str]) -> str:
    """Generate a deterministic commit message from templates."""
    ...
```

**Input/Output Examples:**

```python
generate_commit_message("broken_link", 3, ["README.md", "docs/guide.md"])
# → "chore: fix 3 broken markdown link(s) (ref #94)"

generate_commit_message("stale_worktree", 1, ["/path/to/wt"])
# → "chore: prune 1 stale worktree(s) (ref #94)"

generate_commit_message("broken_link", 1, ["README.md"])
# → "chore: fix 1 broken markdown link(s) (ref #94)"
```

**Implementation:**

```python
COMMIT_TEMPLATES = {
    "broken_link": "chore: fix {count} broken markdown link(s) (ref #94)",
    "stale_worktree": "chore: prune {count} stale worktree(s) (ref #94)",
}

def generate_commit_message(category: str, count: int, details: list[str]) -> str:
    template = COMMIT_TEMPLATES.get(category, f"chore: janitor fix {count} {category} issue(s) (ref #94)")
    return template.format(count=count)
```

### 5.29 `create_fix_pr()`

**File:** `assemblyzero/workflows/janitor/fixers.py`

**Signature:**

```python
def create_fix_pr(repo_root: str, branch_name: str, commit_message: str) -> str | None:
    """Create a PR from the current fix branch."""
    ...
```

**Input Example:**

```python
repo_root = "/home/user/projects/AssemblyZero"
branch_name = "janitor/fix-links-2026-03-02"
commit_message = "chore: fix 3 broken markdown link(s) (ref #94)"
```

**Output Example:**

```python
"https://github.com/martymcenroe/AssemblyZero/pull/95"
# or None if gh pr create fails
```

**Implementation:**

```python
subprocess.run(["git", "checkout", "-b", branch_name], cwd=repo_root, check=True)
subprocess.run(["git", "push", "-u", "origin", branch_name], cwd=repo_root, check=True)
result = subprocess.run(
    ["gh", "pr", "create", "--title", commit_message, "--body", "Automated janitor fixes. See commit history for details.", "--label", "maintenance"],
    cwd=repo_root, capture_output=True, text=True
)
return result.stdout.strip() if result.returncode == 0 else None
```

### 5.30 `ReporterInterface` (ABC)

**File:** `assemblyzero/workflows/janitor/reporter.py`

**Signature:**

```python
import abc
from assemblyzero.workflows.janitor.state import Severity

class ReporterInterface(abc.ABC):
    @abc.abstractmethod
    def find_existing_report(self) -> str | None: ...

    @abc.abstractmethod
    def create_report(self, title: str, body: str, severity: Severity) -> str: ...

    @abc.abstractmethod
    def update_report(self, identifier: str, body: str, severity: Severity) -> str: ...
```

### 5.31 `GitHubReporter`

**File:** `assemblyzero/workflows/janitor/reporter.py`

**Signature and key methods:**

```python
class GitHubReporter(ReporterInterface):
    def __init__(self, repo_root: str) -> None:
        self.repo_root = repo_root
        self._validate_gh_cli()

    def _validate_gh_cli(self) -> None:
        """Check gh CLI is available and authenticated."""
        ...

    def find_existing_report(self) -> str | None:
        """Search for open issues with 'Janitor Report' title."""
        ...

    def create_report(self, title: str, body: str, severity: Severity) -> str:
        """Create new GitHub issue."""
        ...

    def update_report(self, identifier: str, body: str, severity: Severity) -> str:
        """Update existing GitHub issue."""
        ...
```

**`_validate_gh_cli` implementation:**

```python
def _validate_gh_cli(self) -> None:
    result = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True, cwd=self.repo_root)
    if result.returncode != 0:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise RuntimeError("gh CLI not authenticated and GITHUB_TOKEN not set")
```

**`find_existing_report` Input/Output:**

```python
# Uses: gh issue list --search "Janitor Report in:title" --state open --json url --limit 1
# Output if found: "https://github.com/martymcenroe/AssemblyZero/issues/42"
# Output if not found: None
```

**`create_report` Input/Output:**

```python
create_report("Janitor Report", "# Summary\n...", "warning")
# → "https://github.com/martymcenroe/AssemblyZero/issues/43"
```

**`update_report` Input/Output:**

```python
update_report("https://github.com/martymcenroe/AssemblyZero/issues/42", "# Updated Summary\n...", "warning")
# → "https://github.com/martymcenroe/AssemblyZero/issues/42"
```

### 5.32 `LocalFileReporter`

**File:** `assemblyzero/workflows/janitor/reporter.py`

**Signature and key methods:**

```python
class LocalFileReporter(ReporterInterface):
    def __init__(self, repo_root: str) -> None:
        self.repo_root = repo_root
        self.report_dir = Path(repo_root) / "janitor-reports"
        self.report_dir.mkdir(exist_ok=True)

    def find_existing_report(self) -> str | None:
        """Check for existing report file from today."""
        ...

    def create_report(self, title: str, body: str, severity: Severity) -> str:
        """Write report to a new markdown file."""
        ...

    def update_report(self, identifier: str, body: str, severity: Severity) -> str:
        """Overwrite existing report file."""
        ...
```

**`find_existing_report` implementation detail:**

```python
from datetime import datetime

def find_existing_report(self) -> str | None:
    today_prefix = f"janitor-report-{datetime.now().strftime('%Y-%m-%d')}"
    for f in sorted(self.report_dir.glob(f"{today_prefix}*.md")):
        return str(f)
    return None
```

**`create_report` Input/Output:**

```python
create_report("Janitor Report", "# Summary\n...", "warning")
# → "/home/user/projects/AssemblyZero/janitor-reports/janitor-report-2026-03-02-143022.md"
```

**`update_report` Input/Output:**

```python
update_report("/home/user/projects/AssemblyZero/janitor-reports/janitor-report-2026-03-02-143022.md", "# Updated\n...", "warning")
# → "/home/user/projects/AssemblyZero/janitor-reports/janitor-report-2026-03-02-143022.md"
```

### 5.33 `build_report_body()`

**File:** `assemblyzero/workflows/janitor/reporter.py`

**Signature:**

```python
def build_report_body(
    unfixable_findings: list[Finding],
    fix_actions: list[FixAction],
    probe_results: list[ProbeResult],
) -> str:
    """Build a structured markdown report body."""
    ...
```

**Input Example:**

```python
unfixable_findings = [
    Finding(probe="todo", category="stale_todo", message="Stale TODO in helper.py:42", severity="info", fixable=False, file_path="tools/helper.py", line_number=42, fix_data=None),
]
fix_actions = [
    FixAction(category="broken_link", description="Fixed link in README.md", files_modified=["README.md"], commit_message="chore: fix 1 broken markdown link(s) (ref #94)", applied=True),
]
probe_results = [
    ProbeResult(probe="links", status="findings", findings=[...], error_message=None),
    ProbeResult(probe="todo", status="findings", findings=[...], error_message=None),
    ProbeResult(probe="harvest", status="error", findings=[], error_message="Script not found"),
]
```

**Output Example:**

```markdown
# Janitor Report

## Summary

| Severity | Count |
|----------|-------|
| Critical | 0 |
| Warning | 0 |
| Info | 1 |

## Auto-Fixed Issues

- ✅ Fixed link in README.md

## Requires Human Attention

### stale_todo

- ⚠️ Stale TODO in helper.py:42 (tools/helper.py:42)

## Probe Errors

- ❌ **harvest**: Script not found
```

### 5.34 `get_reporter()`

**File:** `assemblyzero/workflows/janitor/reporter.py`

**Signature:**

```python
from typing import Literal

def get_reporter(reporter_type: Literal["github", "local"], repo_root: str) -> ReporterInterface:
    """Factory function to instantiate the correct reporter."""
    ...
```

**Input/Output Examples:**

```python
get_reporter("github", "/repo")  # → GitHubReporter("/repo")
get_reporter("local", "/repo")   # → LocalFileReporter("/repo")
```

### 5.35 `parse_args()`

**File:** `tools/run_janitor_workflow.py`

**Signature:**

```python
import argparse

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    ...
```

**Input/Output Examples:**

```python
# Defaults
args = parse_args([])
# args.scope == "all"
# args.auto_fix == True
# args.dry_run == False
# args.silent == False
# args.create_pr == False
# args.reporter == "github"

# All flags
args = parse_args(["--scope", "links", "--dry-run", "--silent", "--create-pr", "--reporter", "local"])
# args.scope == "links"
# args.auto_fix == True  (default)
# args.dry_run == True
# args.silent == True
# args.create_pr == True
# args.reporter == "local"

# Invalid scope
parse_args(["--scope", "invalid"])  # → SystemExit (argparse error)
```

### 5.36 `build_initial_state()`

**File:** `tools/run_janitor_workflow.py`

**Signature:**

```python
from assemblyzero.workflows.janitor.state import JanitorState

def build_initial_state(args: argparse.Namespace) -> JanitorState:
    """Convert parsed CLI args into initial JanitorState."""
    ...
```

**Input Example:**

```python
args = argparse.Namespace(
    scope="links",
    auto_fix=True,
    dry_run=False,
    silent=False,
    create_pr=False,
    reporter="local",
)
```

**Output Example:**

```python
{
    "repo_root": "/home/user/projects/AssemblyZero",  # os.getcwd() or git rev-parse --show-toplevel
    "scope": ["links"],
    "auto_fix": True,
    "dry_run": False,
    "silent": False,
    "create_pr": False,
    "reporter_type": "local",
    "probe_results": [],
    "all_findings": [],
    "fix_actions": [],
    "unfixable_findings": [],
    "report_url": None,
    "exit_code": 0,
}
```

**Implementation Note:** If `args.scope == "all"`, set `scope = ["links", "worktrees", "harvest", "todo"]`. Use `subprocess.run(["git", "rev-parse", "--show-toplevel"], ...)` to find repo root.

### 5.37 `main()`

**File:** `tools/run_janitor_workflow.py`

**Signature:**

```python
def main(argv: list[str] | None = None) -> int:
    """Entry point. Build graph, execute, return exit code."""
    ...
```

**Input/Output Examples:**

```python
main([])          # → 0 (all clean or all fixed)
main([])          # → 1 (unfixable issues remain)
main([])          # → 2 (fatal error, e.g., not in git repo)
main(["--silent"])  # → 0 (no stdout)
```

**Implementation:**

```python
def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    # Validate git repo
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        if not args.silent:
            print("Error: not a git repository", file=sys.stderr)
        return 2

    try:
        initial_state = build_initial_state(args)
        graph = build_janitor_graph()
        final_state = graph.invoke(initial_state)

        if not args.silent:
            _print_summary(final_state)

        return final_state["exit_code"]
    except Exception as e:
        if not args.silent:
            print(f"Fatal error: {e}", file=sys.stderr)
        return 2
```

## 6. Change Instructions

### 6.1 `assemblyzero/workflows/janitor/__init__.py` (Add)

**Complete file contents:**

```python
"""Janitor workflow: Automated repository hygiene.

Issue #94: Lu-Tze: The Janitor
"""

from assemblyzero.workflows.janitor.graph import build_janitor_graph

__all__ = ["build_janitor_graph"]
```

### 6.2 `assemblyzero/workflows/janitor/state.py` (Add)

**Complete file contents:**

```python
"""State definitions for the Janitor workflow.

Issue #94: Lu-Tze: The Janitor
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, TypedDict


# --- Type aliases ---
Severity = Literal["info", "warning", "critical"]
ProbeScope = Literal["links", "worktrees", "harvest", "todo"]


@dataclass
class Finding:
    """A single issue discovered by a probe."""

    probe: ProbeScope
    category: str
    message: str
    severity: Severity
    fixable: bool
    file_path: str | None = None
    line_number: int | None = None
    fix_data: dict | None = None


@dataclass
class ProbeResult:
    """Structured result from a single probe execution."""

    probe: ProbeScope
    status: Literal["ok", "findings", "error"]
    findings: list[Finding] = field(default_factory=list)
    error_message: str | None = None


@dataclass
class FixAction:
    """Record of a fix that was applied (or would be applied in dry-run)."""

    category: str
    description: str
    files_modified: list[str]
    commit_message: str
    applied: bool


class JanitorState(TypedDict):
    """LangGraph state for the janitor workflow."""

    # Configuration (set at graph entry)
    repo_root: str
    scope: list[ProbeScope]
    auto_fix: bool
    dry_run: bool
    silent: bool
    create_pr: bool
    reporter_type: Literal["github", "local"]

    # Probe results (populated by N0_Sweeper)
    probe_results: list[ProbeResult]
    all_findings: list[Finding]

    # Fix results (populated by N1_Fixer)
    fix_actions: list[FixAction]
    unfixable_findings: list[Finding]

    # Reporter results (populated by N2_Reporter)
    report_url: str | None
    exit_code: int
```

### 6.3 `assemblyzero/workflows/janitor/probes/__init__.py` (Add)

**Complete file contents:**

```python
"""Probe registry and execution utilities.

Issue #94: Lu-Tze: The Janitor
"""

from __future__ import annotations

from typing import Callable

from assemblyzero.workflows.janitor.state import ProbeResult, ProbeScope

# Type alias for probe callables
ProbeFunction = Callable[[str], ProbeResult]


def _build_registry() -> dict[ProbeScope, ProbeFunction]:
    """Build probe registry lazily to avoid circular imports."""
    from assemblyzero.workflows.janitor.probes.harvest import probe_harvest
    from assemblyzero.workflows.janitor.probes.links import probe_links
    from assemblyzero.workflows.janitor.probes.todo import probe_todo
    from assemblyzero.workflows.janitor.probes.worktrees import probe_worktrees

    return {
        "links": probe_links,
        "worktrees": probe_worktrees,
        "harvest": probe_harvest,
        "todo": probe_todo,
    }


def get_probes(scopes: list[ProbeScope]) -> list[tuple[ProbeScope, ProbeFunction]]:
    """Return probe functions for the requested scopes.

    Raises ValueError if an unknown scope is requested.
    """
    registry = _build_registry()
    result: list[tuple[ProbeScope, ProbeFunction]] = []
    for scope in scopes:
        if scope not in registry:
            raise ValueError(f"Unknown probe scope: {scope}")
        result.append((scope, registry[scope]))
    return result


def run_probe_safe(
    probe_name: ProbeScope, probe_fn: ProbeFunction, repo_root: str
) -> ProbeResult:
    """Execute a probe with crash isolation.

    If the probe raises an exception, returns a ProbeResult with
    status='error' instead of propagating the exception.
    """
    try:
        return probe_fn(repo_root)
    except Exception as e:
        return ProbeResult(
            probe=probe_name,
            status="error",
            findings=[],
            error_message=f"{type(e).__name__}: {e}",
        )
```

### 6.4 `assemblyzero/workflows/janitor/probes/links.py` (Add)

**Complete file contents:**

```python
"""Broken internal markdown link detection probe.

Issue #94: Lu-Tze: The Janitor
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from assemblyzero.workflows.janitor.state import Finding, ProbeResult


def probe_links(repo_root: str) -> ProbeResult:
    """Scan all markdown files for broken internal links.

    Checks relative file links, anchor links, and image references.
    Does NOT check external HTTP(S) URLs or absolute paths.
    """
    md_files = find_markdown_files(repo_root)
    findings: list[Finding] = []

    for md_file in md_files:
        links = extract_internal_links(md_file)
        for line_number, link_text, link_target in links:
            if not resolve_link(md_file, link_target, repo_root):
                # Try to find a likely replacement
                likely = find_likely_target(link_target, repo_root)
                rel_file = os.path.relpath(md_file, repo_root)
                findings.append(
                    Finding(
                        probe="links",
                        category="broken_link",
                        message=f"Broken link in {rel_file} line {line_number}: {link_target} does not exist",
                        severity="warning",
                        fixable=likely is not None,
                        file_path=rel_file,
                        line_number=line_number,
                        fix_data=(
                            {"old_link": link_target, "new_link": likely}
                            if likely
                            else None
                        ),
                    )
                )

    if findings:
        return ProbeResult(probe="links", status="findings", findings=findings)
    return ProbeResult(probe="links", status="ok")


def find_markdown_files(repo_root: str) -> list[str]:
    """Find all .md files in repo, respecting .gitignore patterns.

    Uses git ls-files to only return tracked files.
    """
    result = subprocess.run(
        ["git", "ls-files", "*.md"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    files = result.stdout.strip().splitlines()
    return [os.path.join(repo_root, f) for f in files if f]


# Regex for markdown links: [text](target) and ![alt](target)
_LINK_PATTERN = re.compile(r"!?\[([^\]]*)\]\(([^)]+)\)")


def extract_internal_links(file_path: str) -> list[tuple[int, str, str]]:
    """Extract internal links from a markdown file.

    Returns list of (line_number, link_text, link_target) tuples.
    Only returns relative links (not http/https URLs).
    """
    results: list[tuple[int, str, str]] = []
    try:
        with open(file_path, encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                for match in _LINK_PATTERN.finditer(line):
                    link_text = match.group(1)
                    link_target = match.group(2)
                    # Skip external URLs
                    if link_target.startswith(("http://", "https://", "mailto:")):
                        continue
                    # Skip pure anchor links (just #heading)
                    if link_target.startswith("#"):
                        continue
                    results.append((line_num, link_text, link_target))
    except OSError:
        pass
    return results


def resolve_link(source_file: str, link_target: str, repo_root: str) -> bool:
    """Check if a relative link target resolves to an existing file.

    Strips anchor fragments before checking.
    """
    # Strip anchor fragment
    target_path = link_target.split("#")[0]
    if not target_path:
        # Pure anchor link (e.g., #heading) — assume valid within file
        return True

    source_dir = Path(source_file).parent
    resolved = (source_dir / target_path).resolve()

    # Security: ensure resolved path is within repo_root
    repo_root_resolved = Path(repo_root).resolve()
    try:
        resolved.relative_to(repo_root_resolved)
    except ValueError:
        return False

    return resolved.exists()


def find_likely_target(broken_target: str, repo_root: str) -> str | None:
    """Attempt to find the intended target of a broken link.

    Searches for files with the same basename in the repository.
    Returns the relative path to the best match, or None if ambiguous/not found.
    """
    # Strip anchor and get basename
    target_no_anchor = broken_target.split("#")[0]
    basename = os.path.basename(target_no_anchor)
    if not basename:
        return None

    # Search for files with same basename
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None

    candidates = [
        f
        for f in result.stdout.strip().splitlines()
        if os.path.basename(f) == basename
    ]

    if len(candidates) == 1:
        # Build relative path matching original link style
        candidate = candidates[0]
        # Preserve leading ./ if original had it
        if broken_target.startswith("./"):
            return f"./{candidate}"
        return candidate

    return None
```

### 6.5 `assemblyzero/workflows/janitor/probes/worktrees.py` (Add)

**Complete file contents:**

```python
"""Stale and detached git worktree detection probe.

Issue #94: Lu-Tze: The Janitor
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timedelta, timezone

from assemblyzero.workflows.janitor.state import Finding, ProbeResult

# Worktrees with no commits in this many days AND branch merged are considered stale
STALE_DAYS_THRESHOLD = 14


def probe_worktrees(repo_root: str) -> ProbeResult:
    """Detect stale and detached git worktrees.

    A worktree is considered stale if:
    - No commits on its branch in 14+ days AND branch is merged to main, OR
    - The branch has been deleted (detached HEAD with no branch)
    """
    worktrees = list_worktrees(repo_root)
    findings: list[Finding] = []

    for wt in worktrees:
        # Skip the main worktree (first entry is always the primary)
        if wt.get("bare"):
            continue

        branch = wt.get("branch")
        wt_path = wt["path"]

        # Skip main worktree (the repo root itself)
        if branch and branch.endswith("/main"):
            continue

        if wt.get("detached"):
            # Detached HEAD — branch deleted
            findings.append(
                Finding(
                    probe="worktrees",
                    category="stale_worktree",
                    message=f"Detached worktree at {wt_path}: branch deleted",
                    severity="warning",
                    fixable=True,
                    file_path=wt_path,
                    line_number=None,
                    fix_data={"worktree_path": wt_path, "branch": None},
                )
            )
            continue

        if not branch:
            continue

        # Extract short branch name from refs/heads/...
        short_branch = branch.replace("refs/heads/", "")

        last_commit = get_branch_last_commit_date(repo_root, short_branch)
        if last_commit is None:
            continue

        now = datetime.now(timezone.utc)
        age_days = (now - last_commit).days

        if age_days >= STALE_DAYS_THRESHOLD and is_branch_merged(
            repo_root, short_branch
        ):
            findings.append(
                Finding(
                    probe="worktrees",
                    category="stale_worktree",
                    message=(
                        f"Stale worktree at {wt_path}: branch {short_branch} "
                        f"merged to main, last commit {age_days} days ago"
                    ),
                    severity="warning",
                    fixable=True,
                    file_path=wt_path,
                    line_number=None,
                    fix_data={
                        "worktree_path": wt_path,
                        "branch": short_branch,
                    },
                )
            )

    if findings:
        return ProbeResult(probe="worktrees", status="findings", findings=findings)
    return ProbeResult(probe="worktrees", status="ok")


def list_worktrees(repo_root: str) -> list[dict]:
    """Parse output of `git worktree list --porcelain`.

    Returns list of dicts with keys: path, HEAD, branch, bare, detached.
    """
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []

    worktrees: list[dict] = []
    current: dict = {}

    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            if current:
                current.setdefault("bare", False)
                current.setdefault("detached", False)
                worktrees.append(current)
                current = {}
            continue

        if line.startswith("worktree "):
            current["path"] = line[len("worktree ") :]
        elif line.startswith("HEAD "):
            current["HEAD"] = line[len("HEAD ") :]
        elif line.startswith("branch "):
            current["branch"] = line[len("branch ") :]
        elif line == "bare":
            current["bare"] = True
        elif line == "detached":
            current["detached"] = True

    # Don't forget the last entry
    if current:
        current.setdefault("bare", False)
        current.setdefault("detached", False)
        worktrees.append(current)

    return worktrees


def get_branch_last_commit_date(
    repo_root: str, branch: str
) -> datetime | None:
    """Get the date of the most recent commit on a branch.

    Returns None if the branch doesn't exist.
    """
    result = subprocess.run(
        ["git", "log", "-1", "--format=%aI", branch],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None

    date_str = result.stdout.strip()
    if not date_str:
        return None

    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        return None


def is_branch_merged(
    repo_root: str, branch: str, target: str = "main"
) -> bool:
    """Check if branch has been merged into target branch."""
    result = subprocess.run(
        ["git", "branch", "--merged", target],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False

    merged_branches = [b.strip().lstrip("* ") for b in result.stdout.splitlines()]
    return branch in merged_branches
```

### 6.6 `assemblyzero/workflows/janitor/probes/harvest.py` (Add)

**Complete file contents:**

```python
"""Cross-project drift detection via assemblyzero-harvest.py.

Issue #94: Lu-Tze: The Janitor
"""

from __future__ import annotations

import os
import subprocess

from assemblyzero.workflows.janitor.state import Finding, ProbeResult


def probe_harvest(repo_root: str) -> ProbeResult:
    """Run assemblyzero-harvest.py and parse output for cross-project drift.

    Shells out to the harvest script and parses its stdout.
    If the harvest script is not found, returns a single info-level finding.
    All findings from harvest are unfixable (require human judgment).
    """
    script_path = find_harvest_script(repo_root)
    if script_path is None:
        return ProbeResult(
            probe="harvest",
            status="findings",
            findings=[
                Finding(
                    probe="harvest",
                    category="harvest_missing",
                    message="assemblyzero-harvest.py not found in repository",
                    severity="info",
                    fixable=False,
                )
            ],
        )

    try:
        result = subprocess.run(
            ["python", script_path],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        findings = parse_harvest_output(result.stdout)
        if findings:
            return ProbeResult(
                probe="harvest", status="findings", findings=findings
            )
        return ProbeResult(probe="harvest", status="ok")
    except subprocess.TimeoutExpired:
        return ProbeResult(
            probe="harvest",
            status="error",
            error_message="Harvest script timed out after 120 seconds",
        )
    except Exception as e:
        return ProbeResult(
            probe="harvest",
            status="error",
            error_message=f"{type(e).__name__}: {e}",
        )


def find_harvest_script(repo_root: str) -> str | None:
    """Locate the assemblyzero-harvest.py script.

    Searches in repo_root and tools/ directory.
    Returns absolute path or None.
    """
    candidates = [
        os.path.join(repo_root, "assemblyzero-harvest.py"),
        os.path.join(repo_root, "tools", "assemblyzero-harvest.py"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def parse_harvest_output(output: str) -> list[Finding]:
    """Parse harvest script stdout into structured findings.

    Looks for lines starting with 'DRIFT:' and creates findings for each.
    Lines starting with 'OK:' are ignored.
    """
    findings: list[Finding] = []
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("DRIFT:"):
            findings.append(
                Finding(
                    probe="harvest",
                    category="cross_project_drift",
                    message=line,
                    severity="warning",
                    fixable=False,
                )
            )
    return findings
```

### 6.7 `assemblyzero/workflows/janitor/probes/todo.py` (Add)

**Complete file contents:**

```python
"""Stale TODO comment scanner.

Detects TODO/FIXME/HACK/XXX comments older than 30 days using git blame.

Issue #94: Lu-Tze: The Janitor
"""

from __future__ import annotations

import os
import re
import subprocess
from datetime import datetime, timedelta, timezone

from assemblyzero.workflows.janitor.state import Finding, ProbeResult

# TODOs older than this many days are flagged
STALE_TODO_DAYS = 30

# Pattern to detect TODO-like comments
_TODO_PATTERN = re.compile(r"#\s*(TODO|FIXME|HACK|XXX)\b.*", re.IGNORECASE)


def probe_todo(repo_root: str) -> ProbeResult:
    """Scan source files for TODO comments older than 30 days.

    Uses git blame to determine when each TODO line was added.
    Only scans tracked files (respects .gitignore).
    Findings are unfixable (require human decision).
    """
    source_files = find_source_files(repo_root)
    findings: list[Finding] = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=STALE_TODO_DAYS)

    for rel_path in source_files:
        abs_path = os.path.join(repo_root, rel_path)
        todos = extract_todos(abs_path)
        for line_number, comment_text in todos:
            line_date = get_line_date(repo_root, rel_path, line_number)
            if line_date is None:
                continue
            if line_date < cutoff:
                age_days = (datetime.now(timezone.utc) - line_date).days
                findings.append(
                    Finding(
                        probe="todo",
                        category="stale_todo",
                        message=(
                            f"Stale TODO in {rel_path} line {line_number} "
                            f"({age_days} days old): '{comment_text.strip()}'"
                        ),
                        severity="info",
                        fixable=False,
                        file_path=rel_path,
                        line_number=line_number,
                    )
                )

    if findings:
        return ProbeResult(probe="todo", status="findings", findings=findings)
    return ProbeResult(probe="todo", status="ok")


def find_source_files(repo_root: str) -> list[str]:
    """Find all tracked source files (*.py, *.md, *.ts, *.js).

    Uses `git ls-files` to respect .gitignore.
    """
    result = subprocess.run(
        ["git", "ls-files", "*.py", "*.md", "*.ts", "*.js"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [f for f in result.stdout.strip().splitlines() if f]


def extract_todos(file_path: str) -> list[tuple[int, str]]:
    """Extract TODO/FIXME/HACK/XXX comments from a file.

    Returns list of (line_number, comment_text) tuples.
    """
    results: list[tuple[int, str]] = []
    try:
        with open(file_path, encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                match = _TODO_PATTERN.search(line)
                if match:
                    results.append((line_num, match.group(0)))
    except OSError:
        pass
    return results


def get_line_date(
    repo_root: str, file_path: str, line_number: int
) -> datetime | None:
    """Use git blame to determine when a specific line was last modified.

    Returns None if file is not tracked or blame fails.
    """
    result = subprocess.run(
        [
            "git",
            "blame",
            "-L",
            f"{line_number},{line_number}",
            "--porcelain",
            file_path,
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None

    for line in result.stdout.splitlines():
        if line.startswith("author-time "):
            try:
                timestamp = int(line[len("author-time ") :])
                return datetime.fromtimestamp(timestamp, tz=timezone.utc)
            except (ValueError, OSError):
                return None

    return None
```

### 6.8 `assemblyzero/workflows/janitor/fixers.py` (Add)

**Complete file contents:**

```python
"""Auto-fix implementations for broken links and stale worktrees.

Issue #94: Lu-Tze: The Janitor
"""

from __future__ import annotations

import os
import subprocess
from collections import defaultdict
from datetime import datetime

from assemblyzero.workflows.janitor.state import Finding, FixAction

# Deterministic commit message templates — no LLM usage
COMMIT_TEMPLATES: dict[str, str] = {
    "broken_link": "chore: fix {count} broken markdown link(s) (ref #94)",
    "stale_worktree": "chore: prune {count} stale worktree(s) (ref #94)",
}


def fix_broken_links(
    findings: list[Finding], repo_root: str, dry_run: bool
) -> list[FixAction]:
    """Fix broken markdown links by updating references.

    Groups fixes by source file. In dry-run mode, reads files but
    does not write changes.
    """
    actions: list[FixAction] = []

    # Group findings by file
    by_file: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        if f.file_path and f.fix_data and "old_link" in f.fix_data and "new_link" in f.fix_data:
            by_file[f.file_path].append(f)

    files_modified: list[str] = []

    for rel_path, file_findings in by_file.items():
        abs_path = os.path.join(repo_root, rel_path)
        try:
            with open(abs_path, encoding="utf-8") as fh:
                content = fh.read()
        except OSError:
            continue

        original_content = content
        for finding in file_findings:
            old_link = finding.fix_data["old_link"]  # type: ignore[index]
            new_link = finding.fix_data["new_link"]  # type: ignore[index]
            content = content.replace(f"]({old_link})", f"]({new_link})")

        if content != original_content:
            if not dry_run:
                with open(abs_path, "w", encoding="utf-8") as fh:
                    fh.write(content)
            files_modified.append(rel_path)

            for finding in file_findings:
                old_link = finding.fix_data["old_link"]  # type: ignore[index]
                new_link = finding.fix_data["new_link"]  # type: ignore[index]
                actions.append(
                    FixAction(
                        category="broken_link",
                        description=f"Fixed broken link in {rel_path}: {old_link} → {new_link}",
                        files_modified=[rel_path],
                        commit_message=generate_commit_message(
                            "broken_link", len(file_findings), [rel_path]
                        ),
                        applied=not dry_run,
                    )
                )

    return actions


def fix_stale_worktrees(
    findings: list[Finding], repo_root: str, dry_run: bool
) -> list[FixAction]:
    """Prune stale git worktrees.

    Runs `git worktree remove <path>` for each stale worktree.
    In dry-run mode, returns actions without executing.
    """
    actions: list[FixAction] = []

    for finding in findings:
        if not finding.fix_data or "worktree_path" not in finding.fix_data:
            continue

        wt_path = finding.fix_data["worktree_path"]
        branch = finding.fix_data.get("branch", "unknown")

        if not dry_run:
            subprocess.run(
                ["git", "worktree", "remove", wt_path],
                cwd=repo_root,
                capture_output=True,
                text=True,
            )

        actions.append(
            FixAction(
                category="stale_worktree",
                description=(
                    f"{'Pruned' if not dry_run else 'Would prune'} stale worktree "
                    f"at {wt_path} (branch: {branch})"
                ),
                files_modified=[],
                commit_message=generate_commit_message(
                    "stale_worktree", 1, [wt_path]
                ),
                applied=not dry_run,
            )
        )

    return actions


def create_fix_commit(
    repo_root: str, category: str, files: list[str], message: str
) -> None:
    """Stage modified files and create a git commit.

    Uses `git add` for specific files and `git commit -m`.
    Does nothing if no files are provided (idempotent).
    """
    if not files:
        return

    subprocess.run(["git", "add"] + files, cwd=repo_root, check=True)
    result = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    # Ignore "nothing to commit" errors
    if result.returncode != 0 and "nothing to commit" not in result.stdout:
        result.check_returncode()


def generate_commit_message(
    category: str, count: int, details: list[str]
) -> str:
    """Generate a deterministic commit message from templates.

    No LLM usage — pure string formatting.
    """
    template = COMMIT_TEMPLATES.get(
        category, "chore: janitor fix {count} {category} issue(s) (ref #94)"
    )
    return template.format(count=count, category=category)


def create_fix_pr(
    repo_root: str, branch_name: str, commit_message: str
) -> str | None:
    """Create a PR from the current fix branch.

    Creates a new branch, pushes, and uses `gh pr create`.
    Returns the PR URL or None if creation fails.
    """
    try:
        subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "push", "-u", "origin", branch_name],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
        result = subprocess.run(
            [
                "gh",
                "pr",
                "create",
                "--title",
                commit_message,
                "--body",
                "Automated janitor fixes. See commit history for details.",
                "--label",
                "maintenance",
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except Exception:
        return None
```

### 6.9 `assemblyzero/workflows/janitor/reporter.py` (Add)

**Complete file contents:**

```python
"""Reporter implementations for janitor workflow output.

Issue #94: Lu-Tze: The Janitor
"""

from __future__ import annotations

import abc
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Literal

from assemblyzero.workflows.janitor.state import (
    Finding,
    FixAction,
    ProbeResult,
    Severity,
)


class ReporterInterface(abc.ABC):
    """Abstract base class for janitor report backends."""

    @abc.abstractmethod
    def find_existing_report(self) -> str | None:
        """Find existing open Janitor Report. Returns identifier or None."""
        ...

    @abc.abstractmethod
    def create_report(self, title: str, body: str, severity: Severity) -> str:
        """Create a new report. Returns identifier."""
        ...

    @abc.abstractmethod
    def update_report(
        self, identifier: str, body: str, severity: Severity
    ) -> str:
        """Update an existing report. Returns identifier."""
        ...


class GitHubReporter(ReporterInterface):
    """Reporter that creates/updates GitHub issues via `gh` CLI."""

    def __init__(self, repo_root: str) -> None:
        """Initialize with repo root for gh CLI execution context."""
        self.repo_root = repo_root
        self._validate_gh_cli()

    def _validate_gh_cli(self) -> None:
        """Check gh CLI is available and authenticated.

        Falls back to GITHUB_TOKEN env var if interactive auth fails.
        """
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            cwd=self.repo_root,
        )
        if result.returncode != 0:
            token = os.environ.get("GITHUB_TOKEN")
            if not token:
                raise RuntimeError(
                    "gh CLI not authenticated and GITHUB_TOKEN not set. "
                    "Run 'gh auth login' or set GITHUB_TOKEN environment variable."
                )

    def find_existing_report(self) -> str | None:
        """Search for open issues with title matching 'Janitor Report'."""
        result = subprocess.run(
            [
                "gh",
                "issue",
                "list",
                "--search",
                "Janitor Report in:title",
                "--state",
                "open",
                "--json",
                "url",
                "--limit",
                "1",
            ],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return None

        try:
            issues = json.loads(result.stdout)
            if issues:
                return issues[0]["url"]
        except (json.JSONDecodeError, KeyError, IndexError):
            pass
        return None

    def create_report(
        self, title: str, body: str, severity: Severity
    ) -> str:
        """Create a new GitHub issue."""
        result = subprocess.run(
            [
                "gh",
                "issue",
                "create",
                "--title",
                title,
                "--body",
                body,
                "--label",
                "maintenance",
            ],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to create GitHub issue: {result.stderr}")
        return result.stdout.strip()

    def update_report(
        self, identifier: str, body: str, severity: Severity
    ) -> str:
        """Update an existing GitHub issue body.

        Extracts issue number from URL for gh issue edit.
        """
        # Extract issue number from URL like https://github.com/user/repo/issues/42
        issue_number = identifier.rstrip("/").split("/")[-1]
        result = subprocess.run(
            [
                "gh",
                "issue",
                "edit",
                issue_number,
                "--body",
                body,
            ],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to update GitHub issue: {result.stderr}")
        return identifier


class LocalFileReporter(ReporterInterface):
    """Reporter that writes reports to local files. No API calls.

    Output directory: {repo_root}/janitor-reports/
    File naming: janitor-report-{YYYY-MM-DD-HHMMSS}.md
    """

    def __init__(self, repo_root: str) -> None:
        """Initialize with repo root; creates janitor-reports/ if needed."""
        self.repo_root = repo_root
        self.report_dir = Path(repo_root) / "janitor-reports"
        self.report_dir.mkdir(exist_ok=True)

    def find_existing_report(self) -> str | None:
        """Check for existing report file from today."""
        today_prefix = f"janitor-report-{datetime.now().strftime('%Y-%m-%d')}"
        for f in sorted(self.report_dir.glob(f"{today_prefix}*.md")):
            return str(f)
        return None

    def create_report(
        self, title: str, body: str, severity: Severity
    ) -> str:
        """Write report to a new markdown file. Returns file path."""
        timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        filename = f"janitor-report-{timestamp}.md"
        file_path = self.report_dir / filename
        file_path.write_text(body, encoding="utf-8")
        return str(file_path)

    def update_report(
        self, identifier: str, body: str, severity: Severity
    ) -> str:
        """Overwrite existing report file. Returns file path."""
        Path(identifier).write_text(body, encoding="utf-8")
        return identifier


def build_report_body(
    unfixable_findings: list[Finding],
    fix_actions: list[FixAction],
    probe_results: list[ProbeResult],
) -> str:
    """Build a structured markdown report body.

    Sections:
    - Summary (counts by severity)
    - Auto-Fixed Issues (what was resolved)
    - Requires Human Attention (grouped by category)
    - Probe Errors (any probes that crashed)
    """
    lines: list[str] = []
    lines.append("# Janitor Report")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    severity_counts = {"critical": 0, "warning": 0, "info": 0}
    for f in unfixable_findings:
        severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1
    lines.append("| Severity | Count |")
    lines.append("|----------|-------|")
    lines.append(f"| Critical | {severity_counts['critical']} |")
    lines.append(f"| Warning | {severity_counts['warning']} |")
    lines.append(f"| Info | {severity_counts['info']} |")
    lines.append("")

    # Auto-Fixed Issues
    lines.append("## Auto-Fixed Issues")
    lines.append("")
    if fix_actions:
        for action in fix_actions:
            status = "✅" if action.applied else "🔲"
            lines.append(f"- {status} {action.description}")
    else:
        lines.append("No auto-fixes applied.")
    lines.append("")

    # Requires Human Attention
    lines.append("## Requires Human Attention")
    lines.append("")
    if unfixable_findings:
        # Group by category
        by_category: dict[str, list[Finding]] = {}
        for f in unfixable_findings:
            by_category.setdefault(f.category, []).append(f)

        for category, findings in by_category.items():
            lines.append(f"### {category}")
            lines.append("")
            for f in findings:
                location = ""
                if f.file_path:
                    location = f" ({f.file_path}"
                    if f.line_number:
                        location += f":{f.line_number}"
                    location += ")"
                lines.append(f"- ⚠️ {f.message}{location}")
            lines.append("")
    else:
        lines.append("No issues require human attention.")
        lines.append("")

    # Probe Errors
    error_probes = [pr for pr in probe_results if pr.status == "error"]
    if error_probes:
        lines.append("## Probe Errors")
        lines.append("")
        for pr in error_probes:
            lines.append(f"- ❌ **{pr.probe}**: {pr.error_message}")
        lines.append("")

    return "\n".join(lines)


def get_reporter(
    reporter_type: Literal["github", "local"], repo_root: str
) -> ReporterInterface:
    """Factory function to instantiate the correct reporter."""
    if reporter_type == "github":
        return GitHubReporter(repo_root)
    elif reporter_type == "local":
        return LocalFileReporter(repo_root)
    else:
        raise ValueError(f"Unknown reporter type: {reporter_type}")
```

### 6.10 `assemblyzero/workflows/janitor/graph.py` (Add)

**Complete file contents:**

```python
"""LangGraph StateGraph definition for the Janitor workflow.

Issue #94: Lu-Tze: The Janitor

Graph nodes:
  n0_sweeper  - Run probes, collect findings
  n1_fixer    - Apply auto-fixes for fixable findings
  n2_reporter - Report unfixable findings via selected backend

Conditional edges:
  n0_sweeper → END          if no findings
  n0_sweeper → n1_fixer     if fixable findings exist and auto_fix=True
  n0_sweeper → n2_reporter  if only unfixable findings
  n1_fixer   → n2_reporter  if unfixable findings remain
  n1_fixer   → END          if all findings fixed
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from langgraph.graph import END, StateGraph

from assemblyzero.workflows.janitor.fixers import (
    create_fix_commit,
    create_fix_pr,
    fix_broken_links,
    fix_stale_worktrees,
    generate_commit_message,
)
from assemblyzero.workflows.janitor.probes import get_probes, run_probe_safe
from assemblyzero.workflows.janitor.reporter import (
    build_report_body,
    get_reporter,
)
from assemblyzero.workflows.janitor.state import (
    Finding,
    FixAction,
    JanitorState,
)


def n0_sweeper(state: JanitorState) -> dict:
    """Execute all probes in scope and collect findings."""
    probes = get_probes(state["scope"])
    probe_results = []

    for probe_name, probe_fn in probes:
        result = run_probe_safe(probe_name, probe_fn, state["repo_root"])
        probe_results.append(result)

    # Flatten all findings
    all_findings: list[Finding] = []
    for pr in probe_results:
        all_findings.extend(pr.findings)

    return {
        "probe_results": probe_results,
        "all_findings": all_findings,
    }


def n1_fixer(state: JanitorState) -> dict:
    """Apply auto-fixes for all fixable findings."""
    repo_root = state["repo_root"]
    dry_run = state["dry_run"]
    create_pr = state.get("create_pr", False)

    fixable = [f for f in state["all_findings"] if f.fixable]
    unfixable = [f for f in state["all_findings"] if not f.fixable]

    fix_actions: list[FixAction] = []

    # Group fixable findings by category
    by_category: dict[str, list[Finding]] = defaultdict(list)
    for f in fixable:
        by_category[f.category].append(f)

    for category, findings in by_category.items():
        if category == "broken_link":
            actions = fix_broken_links(findings, repo_root, dry_run)
            fix_actions.extend(actions)
        elif category == "stale_worktree":
            actions = fix_stale_worktrees(findings, repo_root, dry_run)
            fix_actions.extend(actions)

    # Create commits for file-modifying fixes (not worktree prunes)
    if not dry_run and not create_pr:
        # Group committed files by category
        for category, findings in by_category.items():
            if category == "broken_link":
                files = list(
                    {f.file_path for f in findings if f.file_path}
                )
                if files:
                    msg = generate_commit_message(
                        category, len(findings), files
                    )
                    create_fix_commit(repo_root, category, files, msg)

    if not dry_run and create_pr:
        branch_name = f"janitor/fixes-{datetime.now().strftime('%Y-%m-%d-%H%M%S')}"
        msg = f"chore: janitor auto-fixes (ref #94)"
        pr_url = create_fix_pr(repo_root, branch_name, msg)
        if pr_url:
            # Add PR URL info (will be picked up by reporter if needed)
            pass

    return {
        "fix_actions": fix_actions,
        "unfixable_findings": unfixable,
    }


def n2_reporter(state: JanitorState) -> dict:
    """Report unfixable findings via the configured reporter backend."""
    reporter = get_reporter(state["reporter_type"], state["repo_root"])
    body = build_report_body(
        state["unfixable_findings"],
        state["fix_actions"],
        state["probe_results"],
    )

    # Determine max severity
    max_severity = "info"
    for f in state["unfixable_findings"]:
        if f.severity == "critical":
            max_severity = "critical"
            break
        if f.severity == "warning":
            max_severity = "warning"

    existing = reporter.find_existing_report()
    if existing:
        report_url = reporter.update_report(existing, body, max_severity)  # type: ignore[arg-type]
    else:
        report_url = reporter.create_report("Janitor Report", body, max_severity)  # type: ignore[arg-type]

    return {
        "report_url": report_url,
        "exit_code": 1,  # Unfixable issues remain
    }


def route_after_sweep(state: JanitorState) -> str:
    """Conditional routing after n0_sweeper completes."""
    all_findings = state.get("all_findings", [])
    if not all_findings:
        return "__end__"

    has_fixable = any(f.fixable for f in all_findings)
    auto_fix = state.get("auto_fix", False)

    if has_fixable and auto_fix:
        return "n1_fixer"

    return "n2_reporter"


def route_after_fix(state: JanitorState) -> str:
    """Conditional routing after n1_fixer completes."""
    unfixable = state.get("unfixable_findings", [])
    if unfixable:
        return "n2_reporter"
    return "__end__"


def build_janitor_graph() -> StateGraph:
    """Build and compile the LangGraph state graph for the janitor workflow."""
    graph = StateGraph(JanitorState)

    # Add nodes
    graph.add_node("n0_sweeper", n0_sweeper)
    graph.add_node("n1_fixer", n1_fixer)
    graph.add_node("n2_reporter", n2_reporter)

    # Set entry point
    graph.set_entry_point("n0_sweeper")

    # Add conditional edge after sweeper
    graph.add_conditional_edges(
        "n0_sweeper",
        route_after_sweep,
        {
            "n1_fixer": "n1_fixer",
            "n2_reporter": "n2_reporter",
            "__end__": END,
        },
    )

    # Add conditional edge after fixer
    graph.add_conditional_edges(
        "n1_fixer",
        route_after_fix,
        {
            "n2_reporter": "n2_reporter",
            "__end__": END,
        },
    )

    # Reporter always goes to END
    graph.add_edge("n2_reporter", END)

    return graph.compile()
```

### 6.11 `tools/run_janitor_workflow.py` (Add)

**Complete file contents:**

```python
#!/usr/bin/env python3
"""CLI entry point for the Janitor workflow.

Usage:
    python tools/run_janitor_workflow.py [OPTIONS]

Options:
    --scope {all|links|worktrees|harvest|todo}  Probes to run (default: all)
    --auto-fix {true|false}                     Apply auto-fixes (default: true)
    --dry-run                                   Preview mode, no modifications
    --silent                                    Suppress stdout on success
    --create-pr                                 Create PR instead of direct commit
    --reporter {github|local}                   Report backend (default: github)

Issue #94: Lu-Tze: The Janitor
"""

from __future__ import annotations

import argparse
import subprocess
import sys

from assemblyzero.workflows.janitor.graph import build_janitor_graph
from assemblyzero.workflows.janitor.state import JanitorState, ProbeScope

ALL_SCOPES: list[ProbeScope] = ["links", "worktrees", "harvest", "todo"]
VALID_SCOPES = ["all"] + ALL_SCOPES


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Janitor: Automated repository hygiene workflow"
    )
    parser.add_argument(
        "--scope",
        choices=VALID_SCOPES,
        default="all",
        help="Which probes to run (default: all)",
    )
    parser.add_argument(
        "--auto-fix",
        type=lambda v: v.lower() in ("true", "1", "yes"),
        default=True,
        help="Apply auto-fixes (default: true)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Preview mode — no file modifications or issue creation",
    )
    parser.add_argument(
        "--silent",
        action="store_true",
        default=False,
        help="Suppress stdout output on success",
    )
    parser.add_argument(
        "--create-pr",
        action="store_true",
        default=False,
        help="Create PR instead of direct commit",
    )
    parser.add_argument(
        "--reporter",
        choices=["github", "local"],
        default="github",
        help="Report backend (default: github)",
    )
    return parser.parse_args(argv)


def build_initial_state(args: argparse.Namespace) -> JanitorState:
    """Convert parsed CLI args into initial JanitorState."""
    # Determine repo root
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    repo_root = result.stdout.strip()

    # Determine scope
    scope: list[ProbeScope] = (
        ALL_SCOPES if args.scope == "all" else [args.scope]
    )

    return JanitorState(
        repo_root=repo_root,
        scope=scope,
        auto_fix=args.auto_fix,
        dry_run=args.dry_run,
        silent=args.silent,
        create_pr=args.create_pr,
        reporter_type=args.reporter,
        probe_results=[],
        all_findings=[],
        fix_actions=[],
        unfixable_findings=[],
        report_url=None,
        exit_code=0,
    )


def _print_summary(state: JanitorState) -> None:
    """Print a human-readable summary to stdout."""
    findings_count = len(state.get("all_findings", []))
    fix_count = len(state.get("fix_actions", []))
    unfixable_count = len(state.get("unfixable_findings", []))
    report_url = state.get("report_url")

    print(f"\n🧹 Janitor Summary:")
    print(f"   Findings:  {findings_count}")
    print(f"   Fixed:     {fix_count}")
    print(f"   Unfixable: {unfixable_count}")

    if report_url:
        print(f"   Report:    {report_url}")

    exit_code = state.get("exit_code", 0)
    if exit_code == 0:
        print("   Status:    ✅ All clean")
    else:
        print("   Status:    ⚠️ Unfixable issues remain")


def main(argv: list[str] | None = None) -> int:
    """Entry point. Build graph, execute, return exit code.

    Returns:
        0 if all issues fixed or no issues found
        1 if unfixable issues remain
        2 if a fatal error occurred
    """
    args = parse_args(argv)

    # Validate git repo
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        if not args.silent:
            print("Error: not a git repository", file=sys.stderr)
        return 2

    try:
        initial_state = build_initial_state(args)
        graph = build_janitor_graph()
        final_state = graph.invoke(initial_state)

        if not args.silent:
            _print_summary(final_state)

        return final_state.get("exit_code", 0)
    except Exception as e:
        if not args.silent:
            print(f"Fatal error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
```

### 6.12 `.gitignore` (Modify)

**Change 1:** Add `janitor-reports/` entry after the harvest artifacts section (after line ~40)

```diff
 # Harvest artifacts (generated reports)
 harvest-*.json
 harvest-*.xlsx
+
+# Janitor reports (generated by tools/run_janitor_workflow.py, Issue #94)
+janitor-reports/

 # Blog drafts (not ready for public)
 docs/blog/
```

### 6.13 `tests/fixtures/janitor/mock_repo/README.md` (Add)

**Complete file contents:**

```markdown
# Mock Project

This is a mock project for testing the Janitor workflow.

## Links

- Valid link: [Guide](./docs/guide.md)
- Broken link: [Old Guide](./docs/old-guide.md)
- External link: [Example](https://example.com)
- Image: ![Logo](./images/logo.png)
- Anchor link: [Section](#links)
```

### 6.14 `tests/fixtures/janitor/mock_repo/docs/guide.md` (Add)

**Complete file contents:**

```markdown
# Guide

This is the guide document.

## Section One

Content for section one.

## Section Two

Content for section two.
```

### 6.15 `tests/fixtures/janitor/mock_repo/docs/stale-todo.py` (Add)

**Complete file contents:**

```python
"""Mock file with TODO comments for testing."""


def old_function():
    # TODO: refactor this function
    pass


def new_function():
    # TODO: add error handling
    return True


# FIXME: this constant should be configurable
MAX_RETRIES = 3
```

### 6.16 `tests/unit/test_janitor/__init__.py` (Add)

**Complete file contents:**

```python
"""Test package for janitor workflow tests."""
```

### 6.17 `tests/unit/test_janitor/test_state.py` (Add)

**Complete file contents:**

```python
"""Tests for janitor state structures.

Issue #94: Lu-Tze: The Janitor
Test IDs: T010, T390
"""

from assemblyzero.workflows.janitor.state import (
    Finding,
    FixAction,
    JanitorState,
    ProbeResult,
)


class TestFinding:
    """Test Finding dataclass."""

    def test_finding_creation_with_defaults(self):
        """Finding can be created with minimal fields."""
        f = Finding(
            probe="links",
            category="broken_link",
            message="test message",
            severity="warning",
            fixable=True,
        )
        assert f.probe == "links"
        assert f.file_path is None
        assert f.line_number is None
        assert f.fix_data is None

    def test_finding_creation_with_all_fields(self):
        """Finding can be created with all fields."""
        f = Finding(
            probe="links",
            category="broken_link",
            message="Broken link",
            severity="warning",
            fixable=True,
            file_path="README.md",
            line_number=15,
            fix_data={"old_link": "./old.md", "new_link": "./new.md"},
        )
        assert f.file_path == "README.md"
        assert f.line_number == 15
        assert f.fix_data["old_link"] == "./old.md"


class TestProbeResult:
    """Test ProbeResult dataclass."""

    def test_probe_result_ok(self):
        """ProbeResult with ok status has empty findings."""
        pr = ProbeResult(probe="links", status="ok")
        assert pr.findings == []
        assert pr.error_message is None

    def test_probe_result_error(self):
        """ProbeResult with error status has error message."""
        pr = ProbeResult(
            probe="links", status="error", error_message="RuntimeError: boom"
        )
        assert pr.status == "error"
        assert pr.error_message == "RuntimeError: boom"


class TestFixAction:
    """Test FixAction dataclass."""

    def test_fix_action_applied(self):
        """FixAction records applied fix."""
        fa = FixAction(
            category="broken_link",
            description="Fixed link",
            files_modified=["README.md"],
            commit_message="chore: fix 1 broken markdown link(s) (ref #94)",
            applied=True,
        )
        assert fa.applied is True
        assert fa.files_modified == ["README.md"]

    def test_fix_action_dry_run(self):
        """FixAction records dry-run (not applied)."""
        fa = FixAction(
            category="broken_link",
            description="Would fix link",
            files_modified=["README.md"],
            commit_message="chore: fix 1 broken markdown link(s) (ref #94)",
            applied=False,
        )
        assert fa.applied is False


class TestJanitorState:
    """Test JanitorState TypedDict. T010, T390."""

    def test_initial_state_construction(self):
        """JanitorState can be constructed with all required keys. T390."""
        state: JanitorState = {
            "repo_root": "/home/user/projects/repo",
            "scope": ["links", "worktrees"],
            "auto_fix": True,
            "dry_run": False,
            "silent": False,
            "create_pr": False,
            "reporter_type": "local",
            "probe_results": [],
            "all_findings": [],
            "fix_actions": [],
            "unfixable_findings": [],
            "report_url": None,
            "exit_code": 0,
        }
        assert state["repo_root"] == "/home/user/projects/repo"
        assert state["scope"] == ["links", "worktrees"]
        assert state["exit_code"] == 0
```

### 6.18 `tests/unit/test_janitor/test_probes.py` (Add)

**Complete file contents:**

```python
"""Tests for janitor probes.

Issue #94: Lu-Tze: The Janitor
Test IDs: T020-T100, T150-T220
"""

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, mock_open, patch

import pytest

from assemblyzero.workflows.janitor.probes import run_probe_safe
from assemblyzero.workflows.janitor.probes.harvest import (
    find_harvest_script,
    parse_harvest_output,
    probe_harvest,
)
from assemblyzero.workflows.janitor.probes.links import (
    extract_internal_links,
    find_likely_target,
    find_markdown_files,
    probe_links,
    resolve_link,
)
from assemblyzero.workflows.janitor.probes.todo import (
    extract_todos,
    get_line_date,
    probe_todo,
)
from assemblyzero.workflows.janitor.probes.worktrees import (
    get_branch_last_commit_date,
    is_branch_merged,
    list_worktrees,
    probe_worktrees,
)
from assemblyzero.workflows.janitor.state import ProbeResult


FIXTURES_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "fixtures", "janitor", "mock_repo"
)


class TestProbeLinkDetection:
    """Test broken link detection. T020, T030, T040, T150, T160, T170."""

    def test_probe_links_detects_broken_link(self, tmp_path):
        """T020/T150: probe_links returns fixable finding for resolvable broken link."""
        # Create mock repo with broken link
        readme = tmp_path / "README.md"
        readme.write_text("[guide](./docs/old-guide.md)\n")
        docs = tmp_path / "docs"
        docs.mkdir()
        guide = docs / "guide.md"
        guide.write_text("# Guide\n")

        with patch(
            "assemblyzero.workflows.janitor.probes.links.find_markdown_files",
            return_value=[str(readme)],
        ), patch(
            "assemblyzero.workflows.janitor.probes.links.find_likely_target",
            return_value="./docs/guide.md",
        ):
            result = probe_links(str(tmp_path))

        assert result.status == "findings"
        assert len(result.findings) == 1
        assert result.findings[0].fixable is True
        assert result.findings[0].fix_data["new_link"] == "./docs/guide.md"

    def test_probe_links_ignores_external_urls(self, tmp_path):
        """T030/T160: probe_links skips http/https links."""
        readme = tmp_path / "README.md"
        readme.write_text("[example](https://example.com)\n[other](http://other.com)\n")

        with patch(
            "assemblyzero.workflows.janitor.probes.links.find_markdown_files",
            return_value=[str(readme)],
        ):
            result = probe_links(str(tmp_path))

        assert result.status == "ok"
        assert result.findings == []

    def test_probe_links_handles_valid_links(self, tmp_path):
        """T040/T170: probe_links returns ok for all valid links."""
        docs = tmp_path / "docs"
        docs.mkdir()
        guide = docs / "guide.md"
        guide.write_text("# Guide\n")
        readme = tmp_path / "README.md"
        readme.write_text("[guide](./docs/guide.md)\n")

        with patch(
            "assemblyzero.workflows.janitor.probes.links.find_markdown_files",
            return_value=[str(readme)],
        ):
            result = probe_links(str(tmp_path))

        assert result.status == "ok"

    def test_extract_internal_links(self, tmp_path):
        """extract_internal_links returns relative links only."""
        md = tmp_path / "test.md"
        md.write_text(
            "# Test\n"
            "[guide](./docs/guide.md)\n"
            "[ext](https://example.com)\n"
            "![img](./images/pic.png)\n"
            "[anchor](#heading)\n"
        )
        links = extract_internal_links(str(md))
        assert len(links) == 2
        assert links[0] == (2, "guide", "./docs/guide.md")
        assert links[1] == (4, "img", "./images/pic.png")

    def test_resolve_link_existing(self, tmp_path):
        """resolve_link returns True for existing file."""
        docs = tmp_path / "docs"
        docs.mkdir()
        guide = docs / "guide.md"
        guide.write_text("# Guide\n")
        readme = tmp_path / "README.md"
        readme.write_text("")
        assert resolve_link(str(readme), "./docs/guide.md", str(tmp_path)) is True

    def test_resolve_link_missing(self, tmp_path):
        """resolve_link returns False for missing file."""
        readme = tmp_path / "README.md"
        readme.write_text("")
        assert resolve_link(str(readme), "./docs/nonexistent.md", str(tmp_path)) is False

    def test_resolve_link_with_anchor(self, tmp_path):
        """resolve_link strips anchor before checking."""
        docs = tmp_path / "docs"
        docs.mkdir()
        guide = docs / "guide.md"
        guide.write_text("# Guide\n")
        readme = tmp_path / "README.md"
        readme.write_text("")
        assert resolve_link(str(readme), "./docs/guide.md#section", str(tmp_path)) is True

    def test_find_likely_target_unique_match(self, tmp_path):
        """find_likely_target returns match when exactly one file with same basename."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="docs/guide.md\n"
            )
            result = find_likely_target("./docs/old-guide.md", str(tmp_path))
            # basename of old-guide.md is old-guide.md, no match for guide.md
            assert result is None

    def test_find_likely_target_no_match(self, tmp_path):
        """find_likely_target returns None when no files match."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="docs/guide.md\nREADME.md\n"
            )
            result = find_likely_target("./nonexistent.md", str(tmp_path))
            assert result is None


class TestProbeWorktrees:
    """Test worktree detection. T050, T060, T180, T190."""

    def test_probe_worktrees_detects_stale(self):
        """T050/T180: probe_worktrees returns finding for stale merged worktree."""
        past_date = datetime.now(timezone.utc) - timedelta(days=15)

        with patch(
            "assemblyzero.workflows.janitor.probes.worktrees.list_worktrees",
            return_value=[
                {
                    "path": "/repo",
                    "HEAD": "abc123",
                    "branch": "refs/heads/main",
                    "bare": False,
                    "detached": False,
                },
                {
                    "path": "/repo-42",
                    "HEAD": "def456",
                    "branch": "refs/heads/feature/old",
                    "bare": False,
                    "detached": False,
                },
            ],
        ), patch(
            "assemblyzero.workflows.janitor.probes.worktrees.get_branch_last_commit_date",
            return_value=past_date,
        ), patch(
            "assemblyzero.workflows.janitor.probes.worktrees.is_branch_merged",
            return_value=True,
        ):
            result = probe_worktrees("/repo")

        assert result.status == "findings"
        assert len(result.findings) == 1
        assert result.findings[0].category == "stale_worktree"
        assert result.findings[0].fixable is True

    def test_probe_worktrees_ignores_active(self):
        """T060/T190: probe_worktrees returns no finding for active worktree."""
        recent_date = datetime.now(timezone.utc) - timedelta(days=1)

        with patch(
            "assemblyzero.workflows.janitor.probes.worktrees.list_worktrees",
            return_value=[
                {
                    "path": "/repo",
                    "HEAD": "abc123",
                    "branch": "refs/heads/main",
                    "bare": False,
                    "detached": False,
                },
                {
                    "path": "/repo-42",
                    "HEAD": "def456",
                    "branch": "refs/heads/feature/active",
                    "bare": False,
                    "detached": False,
                },
            ],
        ), patch(
            "assemblyzero.workflows.janitor.probes.worktrees.get_branch_last_commit_date",
            return_value=recent_date,
        ):
            result = probe_worktrees("/repo")

        assert result.status == "ok"
        assert result.findings == []

    def test_list_worktrees_parses_porcelain(self):
        """list_worktrees parses git porcelain output correctly."""
        porcelain_output = (
            "worktree /home/user/repo\n"
            "HEAD abc123def456\n"
            "branch refs/heads/main\n"
            "\n"
            "worktree /home/user/repo-42\n"
            "HEAD def789abc012\n"
            "branch refs/heads/feature/thing\n"
            "\n"
        )
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout=porcelain_output
            )
            wts = list_worktrees("/repo")

        assert len(wts) == 2
        assert wts[0]["path"] == "/home/user/repo"
        assert wts[0]["branch"] == "refs/heads/main"
        assert wts[1]["path"] == "/home/user/repo-42"

    def test_list_worktrees_detached(self):
        """list_worktrees parses detached worktree correctly."""
        porcelain_output = (
            "worktree /home/user/repo\n"
            "HEAD abc123def456\n"
            "branch refs/heads/main\n"
            "\n"
            "worktree /home/user/repo-42\n"
            "HEAD def789abc012\n"
            "detached\n"
            "\n"
        )
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout=porcelain_output
            )
            wts = list_worktrees("/repo")

        assert wts[1]["detached"] is True
        assert "branch" not in wts[1]

    def test_get_branch_last_commit_date(self):
        """get_branch_last_commit_date parses ISO 8601 date."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="2026-02-15T10:30:00+00:00\n"
            )
            dt = get_branch_last_commit_date("/repo", "feature/thing")

        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 2
        assert dt.day == 15

    def test_get_branch_last_commit_date_nonexistent(self):
        """get_branch_last_commit_date returns None for nonexistent branch."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=128, stdout="")
            dt = get_branch_last_commit_date("/repo", "nonexistent")

        assert dt is None

    def test_is_branch_merged(self):
        """is_branch_merged returns True for merged branch."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="  feature/old\n* main\n"
            )
            assert is_branch_merged("/repo", "feature/old") is True

    def test_is_branch_not_merged(self):
        """is_branch_merged returns False for unmerged branch."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="* main\n"
            )
            assert is_branch_merged("/repo", "feature/active") is False


class TestProbeTodo:
    """Test TODO detection. T070, T080, T200, T210."""

    def test_probe_todo_finds_stale(self):
        """T070/T200: probe_todo returns finding for TODO older than 30 days."""
        past_date = datetime.now(timezone.utc) - timedelta(days=45)

        with patch(
            "assemblyzero.workflows.janitor.probes.todo.find_source_files",
            return_value=["tools/helper.py"],
        ), patch(
            "assemblyzero.workflows.janitor.probes.todo.extract_todos",
            return_value=[(42, "# TODO: refactor this function")],
        ), patch(
            "assemblyzero.workflows.janitor.probes.todo.get_line_date",
            return_value=past_date,
        ):
            result = probe_todo("/repo")

        assert result.status == "findings"
        assert len(result.findings) == 1
        assert result.findings[0].category == "stale_todo"
        assert result.findings[0].fixable is False

    def test_probe_todo_ignores_recent(self):
        """T080/T210: probe_todo returns no finding for recent TODO."""
        recent_date = datetime.now(timezone.utc) - timedelta(days=1)

        with patch(
            "assemblyzero.workflows.janitor.probes.todo.find_source_files",
            return_value=["tools/helper.py"],
        ), patch(
            "assemblyzero.workflows.janitor.probes.todo.extract_todos",
            return_value=[(42, "# TODO: add this feature")],
        ), patch(
            "assemblyzero.workflows.janitor.probes.todo.get_line_date",
            return_value=recent_date,
        ):
            result = probe_todo("/repo")

        assert result.status == "ok"
        assert result.findings == []

    def test_extract_todos(self, tmp_path):
        """extract_todos finds TODO/FIXME/HACK/XXX patterns."""
        f = tmp_path / "test.py"
        f.write_text(
            "def func():\n"
            "    # TODO: refactor this\n"
            "    pass\n"
            "    # FIXME: handle error\n"
            "    # Regular comment\n"
            "    # HACK: workaround for bug\n"
        )
        todos = extract_todos(str(f))
        assert len(todos) == 3
        assert todos[0] == (2, "# TODO: refactor this")
        assert todos[1] == (4, "# FIXME: handle error")
        assert todos[2] == (6, "# HACK: workaround for bug")

    def test_get_line_date_parses_blame(self):
        """get_line_date parses author-time from git blame porcelain."""
        blame_output = (
            "abc123 42 42 1\n"
            "author Test User\n"
            "author-mail <test@example.com>\n"
            "author-time 1737936000\n"  # 2025-01-27T00:00:00Z
            "author-tz +0000\n"
        )
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout=blame_output
            )
            dt = get_line_date("/repo", "test.py", 42)

        assert dt is not None
        assert dt.year == 2025

    def test_get_line_date_untracked(self):
        """get_line_date returns None for untracked file."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=128, stdout="")
            dt = get_line_date("/repo", "untracked.py", 1)

        assert dt is None


class TestProbeHarvest:
    """Test harvest detection. T090, T220."""

    def test_probe_harvest_missing_script(self):
        """T090/T220: probe_harvest returns info finding when script not found."""
        with patch(
            "assemblyzero.workflows.janitor.probes.harvest.find_harvest_script",
            return_value=None,
        ):
            result = probe_harvest("/repo")

        assert result.status == "findings"
        assert len(result.findings) == 1
        assert result.findings[0].category == "harvest_missing"
        assert result.findings[0].severity == "info"
        assert result.findings[0].fixable is False

    def test_parse_harvest_output_drift_lines(self):
        """parse_harvest_output extracts DRIFT lines."""
        output = (
            "OK: assemblyzero/state.py in sync\n"
            "DRIFT: pyproject.toml version mismatch\n"
            "OK: tools/audit.py in sync\n"
            "DRIFT: docs/standards/0001.md outdated\n"
        )
        findings = parse_harvest_output(output)
        assert len(findings) == 2
        assert findings[0].category == "cross_project_drift"
        assert "pyproject.toml" in findings[0].message

    def test_parse_harvest_output_no_drift(self):
        """parse_harvest_output returns empty list for clean output."""
        output = "OK: everything in sync\n"
        findings = parse_harvest_output(output)
        assert findings == []

    def test_find_harvest_script_in_root(self, tmp_path):
        """find_harvest_script finds script in repo root."""
        script = tmp_path / "assemblyzero-harvest.py"
        script.write_text("# script")
        assert find_harvest_script(str(tmp_path)) == str(script)

    def test_find_harvest_script_in_tools(self, tmp_path):
        """find_harvest_script finds script in tools/."""
        tools = tmp_path / "tools"
        tools.mkdir()
        script = tools / "assemblyzero-harvest.py"
        script.write_text("# script")
        assert find_harvest_script(str(tmp_path)) == str(script)

    def test_find_harvest_script_not_found(self, tmp_path):
        """find_harvest_script returns None when not found."""
        assert find_harvest_script(str(tmp_path)) is None


class TestProbeIsolation:
    """Test probe crash isolation. T100."""

    def test_run_probe_safe_catches_exception(self):
        """T100: run_probe_safe returns error ProbeResult on exception."""

        def crashing_probe(repo_root: str) -> ProbeResult:
            raise RuntimeError("Probe exploded!")

        result = run_probe_safe("links", crashing_probe, "/repo")
        assert result.status == "error"
        assert result.probe == "links"
        assert "RuntimeError: Probe exploded!" in result.error_message

    def test_run_probe_safe_passes_through_success(self):
        """run_probe_safe returns normal result on success."""
        expected = ProbeResult(probe="links", status="ok")

        def good_probe(repo_root: str) -> ProbeResult:
            return expected

        result = run_probe_safe("links", good_probe, "/repo")
        assert result.status == "ok"
        assert result is expected
```

### 6.19 `tests/unit/test_janitor/test_fixers.py` (Add)

**Complete file contents:**

```python
"""Tests for janitor fixers.

Issue #94: Lu-Tze: The Janitor
Test IDs: T110-T140, T230-T260
"""

from unittest.mock import MagicMock, call, patch

from assemblyzero.workflows.janitor.fixers import (
    create_fix_commit,
    fix_broken_links,
    fix_stale_worktrees,
    generate_commit_message,
)
from assemblyzero.workflows.janitor.state import Finding


class TestFixBrokenLinks:
    """Test broken link fixer. T110, T120, T230, T240."""

    def test_fix_broken_links_updates_file(self, tmp_path):
        """T110/T230: fix_broken_links replaces broken link with correct target."""
        readme = tmp_path / "README.md"
        readme.write_text("[guide](./docs/old-guide.md)\n[other](./valid.md)\n")

        findings = [
            Finding(
                probe="links",
                category="broken_link",
                message="Broken link",
                severity="warning",
                fixable=True,
                file_path="README.md",
                line_number=1,
                fix_data={"old_link": "./docs/old-guide.md", "new_link": "./docs/guide.md"},
            )
        ]

        actions = fix_broken_links(findings, str(tmp_path), dry_run=False)

        assert len(actions) == 1
        assert actions[0].applied is True
        content = readme.read_text()
        assert "./docs/guide.md" in content
        assert "./docs/old-guide.md" not in content
        assert "./valid.md" in content  # Other links untouched

    def test_fix_broken_links_dry_run(self, tmp_path):
        """T120/T240: fix_broken_links with dry_run=True does not modify files."""
        readme = tmp_path / "README.md"
        original_content = "[guide](./docs/old-guide.md)\n"
        readme.write_text(original_content)

        findings = [
            Finding(
                probe="links",
                category="broken_link",
                message="Broken link",
                severity="warning",
                fixable=True,
                file_path="README.md",
                line_number=1,
                fix_data={"old_link": "./docs/old-guide.md", "new_link": "./docs/guide.md"},
            )
        ]

        actions = fix_broken_links(findings, str(tmp_path), dry_run=True)

        assert len(actions) == 1
        assert actions[0].applied is False
        assert readme.read_text() == original_content

    def test_fix_broken_links_no_fix_data(self, tmp_path):
        """fix_broken_links skips findings without fix_data."""
        findings = [
            Finding(
                probe="links",
                category="broken_link",
                message="Broken link",
                severity="warning",
                fixable=True,
                file_path="README.md",
                line_number=1,
                fix_data=None,
            )
        ]
        actions = fix_broken_links(findings, str(tmp_path), dry_run=False)
        assert actions == []


class TestFixStaleWorktrees:
    """Test stale worktree fixer. T130, T250."""

    def test_fix_stale_worktrees_calls_git_remove(self):
        """T130/T250: fix_stale_worktrees invokes git worktree remove."""
        findings = [
            Finding(
                probe="worktrees",
                category="stale_worktree",
                message="Stale worktree",
                severity="warning",
                fixable=True,
                file_path="/home/user/repo-42",
                line_number=None,
                fix_data={"worktree_path": "/home/user/repo-42", "branch": "feature/old"},
            )
        ]

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            actions = fix_stale_worktrees(findings, "/home/user/repo", dry_run=False)

        assert len(actions) == 1
        assert actions[0].applied is True
        assert actions[0].category == "stale_worktree"
        mock_run.assert_called_once_with(
            ["git", "worktree", "remove", "/home/user/repo-42"],
            cwd="/home/user/repo",
            capture_output=True,
            text=True,
        )

    def test_fix_stale_worktrees_dry_run(self):
        """fix_stale_worktrees in dry-run does not call subprocess."""
        findings = [
            Finding(
                probe="worktrees",
                category="stale_worktree",
                message="Stale worktree",
                severity="warning",
                fixable=True,
                file_path="/home/user/repo-42",
                line_number=None,
                fix_data={"worktree_path": "/home/user/repo-42", "branch": "feature/old"},
            )
        ]

        with patch("subprocess.run") as mock_run:
            actions = fix_stale_worktrees(findings, "/home/user/repo", dry_run=True)

        assert len(actions) == 1
        assert actions[0].applied is False
        mock_run.assert_not_called()


class TestCommitMessage:
    """Test commit message generation. T140, T260."""

    def test_links_commit_message(self):
        """T140/T260: generate_commit_message produces expected template for links."""
        msg = generate_commit_message("broken_link", 3, ["README.md", "docs/guide.md"])
        assert msg == "chore: fix 3 broken markdown link(s) (ref #94)"

    def test_worktrees_commit_message(self):
        """generate_commit_message produces expected template for worktrees."""
        msg = generate_commit_message("stale_worktree", 1, ["/path/to/wt"])
        assert msg == "chore: prune 1 stale worktree(s) (ref #94)"

    def test_single_link_commit_message(self):
        """generate_commit_message works for single link fix."""
        msg = generate_commit_message("broken_link", 1, ["README.md"])
        assert msg == "chore: fix 1 broken markdown link(s) (ref #94)"

    def test_unknown_category_fallback(self):
        """generate_commit_message uses fallback for unknown categories."""
        msg = generate_commit_message("unknown_thing", 2, [])
        assert "janitor fix" in msg
        assert "2" in msg


class TestCreateFixCommit:
    """Test git commit creation."""

    def test_create_fix_commit_stages_and_commits(self):
        """create_fix_commit calls git add and git commit."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            create_fix_commit("/repo", "broken_link", ["README.md"], "chore: fix links")

        assert mock_run.call_count == 2
        mock_run.assert_any_call(
            ["git", "add", "README.md"], cwd="/repo", check=True
        )

    def test_create_fix_commit_empty_files_noop(self):
        """create_fix_commit does nothing with empty files list."""
        with patch("subprocess.run") as mock_run:
            create_fix_commit("/repo", "broken_link", [], "chore: fix links")
        mock_run.assert_not_called()
```

### 6.20 `tests/unit/test_janitor/test_reporter.py` (Add)

**Complete file contents:**

```python
"""Tests for janitor reporters.

Issue #94: Lu-Tze: The Janitor
Test IDs: T150-T180, T270-T300, T360-T380
"""

import json
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.workflows.janitor.reporter import (
    GitHubReporter,
    LocalFileReporter,
    build_report_body,
    get_reporter,
)
from assemblyzero.workflows.janitor.state import (
    Finding,
    FixAction,
    ProbeResult,
)


class TestLocalFileReporter:
    """Test LocalFileReporter. T150-T170, T270-T290, T380."""

    def test_create_report(self, tmp_path):
        """T150/T270/T380: create_report writes markdown file to janitor-reports/."""
        reporter = LocalFileReporter(str(tmp_path))
        result = reporter.create_report(
            "Janitor Report", "# Test Report\nContent here", "warning"
        )

        assert result.startswith(str(tmp_path / "janitor-reports"))
        assert result.endswith(".md")
        assert Path(result).exists()
        assert "# Test Report" in Path(result).read_text()

    def test_update_report(self, tmp_path):
        """T160/T280: update_report overwrites existing file."""
        reporter = LocalFileReporter(str(tmp_path))
        path = reporter.create_report("Janitor Report", "# Original", "info")

        updated_path = reporter.update_report(path, "# Updated", "warning")

        assert updated_path == path
        assert Path(path).read_text() == "# Updated"

    def test_find_existing_report_today(self, tmp_path):
        """T170/T290: find_existing_report returns path for today's report."""
        reporter = LocalFileReporter(str(tmp_path))
        created_path = reporter.create_report("Janitor Report", "# Test", "info")

        found = reporter.find_existing_report()

        assert found is not None
        assert found == created_path

    def test_find_existing_report_none(self, tmp_path):
        """find_existing_report returns None when no report exists."""
        reporter = LocalFileReporter(str(tmp_path))
        assert reporter.find_existing_report() is None

    def test_creates_janitor_reports_dir(self, tmp_path):
        """LocalFileReporter creates janitor-reports/ directory on init."""
        reporter = LocalFileReporter(str(tmp_path))
        assert (tmp_path / "janitor-reports").is_dir()


class TestGitHubReporter:
    """Test GitHubReporter. T360, T370."""

    def test_init_with_gh_auth(self):
        """GitHubReporter initializes successfully with gh auth."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            reporter = GitHubReporter("/repo")
        assert reporter.repo_root == "/repo"

    def test_init_with_github_token(self):
        """T360: GitHubReporter falls back to GITHUB_TOKEN."""
        with patch("subprocess.run") as mock_run, patch.dict(
            os.environ, {"GITHUB_TOKEN": "ghp_test123"}
        ):
            mock_run.return_value = MagicMock(returncode=1)
            reporter = GitHubReporter("/repo")
        assert reporter.repo_root == "/repo"

    def test_init_no_auth_raises(self):
        """GitHubReporter raises RuntimeError without auth."""
        with patch("subprocess.run") as mock_run, patch.dict(
            os.environ, {}, clear=True
        ):
            # Remove GITHUB_TOKEN if set
            os.environ.pop("GITHUB_TOKEN", None)
            mock_run.return_value = MagicMock(returncode=1)
            with pytest.raises(RuntimeError, match="gh CLI not authenticated"):
                GitHubReporter("/repo")

    def test_find_existing_report(self):
        """T370: find_existing_report returns existing issue URL."""
        with patch("subprocess.run") as mock_run:
            # First call: gh auth status (success)
            # Second call: gh issue list (returns issue)
            mock_run.side_effect = [
                MagicMock(returncode=0),  # auth
                MagicMock(
                    returncode=0,
                    stdout=json.dumps(
                        [{"url": "https://github.com/user/repo/issues/42"}]
                    ),
                ),
            ]
            reporter = GitHubReporter("/repo")
            result = reporter.find_existing_report()

        assert result == "https://github.com/user/repo/issues/42"

    def test_find_existing_report_none(self):
        """find_existing_report returns None when no matching issue."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0),  # auth
                MagicMock(returncode=0, stdout="[]"),  # no issues
            ]
            reporter = GitHubReporter("/repo")
            result = reporter.find_existing_report()

        assert result is None

    def test_create_report(self):
        """create_report calls gh issue create."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0),  # auth
                MagicMock(
                    returncode=0,
                    stdout="https://github.com/user/repo/issues/43\n",
                ),
            ]
            reporter = GitHubReporter("/repo")
            url = reporter.create_report("Janitor Report", "# Body", "warning")

        assert url == "https://github.com/user/repo/issues/43"

    def test_update_report(self):
        """update_report calls gh issue edit."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0),  # auth
                MagicMock(returncode=0),  # edit
            ]
            reporter = GitHubReporter("/repo")
            url = reporter.update_report(
                "https://github.com/user/repo/issues/42", "# Updated", "warning"
            )

        assert url == "https://github.com/user/repo/issues/42"
        # Verify gh issue edit was called with correct issue number
        edit_call = mock_run.call_args_list[1]
        assert "42" in edit_call.args[0]


class TestBuildReportBody:
    """Test report body generation. T180, T300."""

    def test_build_report_body_all_sections(self):
        """T180/T300: build_report_body produces markdown with all sections."""
        unfixable = [
            Finding(
                probe="todo",
                category="stale_todo",
                message="Stale TODO in helper.py:42",
                severity="info",
                fixable=False,
                file_path="tools/helper.py",
                line_number=42,
            )
        ]
        fix_actions = [
            FixAction(
                category="broken_link",
                description="Fixed link in README.md",
                files_modified=["README.md"],
                commit_message="chore: fix 1 broken markdown link(s) (ref #94)",
                applied=True,
            )
        ]
        probe_results = [
            ProbeResult(probe="links", status="findings", findings=[]),
            ProbeResult(probe="harvest", status="error", error_message="Script not found"),
        ]

        body = build_report_body(unfixable, fix_actions, probe_results)

        assert "# Janitor Report" in body
        assert "## Summary" in body
        assert "## Auto-Fixed Issues" in body
        assert "Fixed link in README.md" in body
        assert "## Requires Human Attention" in body
        assert "stale_todo" in body
        assert "## Probe Errors" in body
        assert "harvest" in body
        assert "Script not found" in body

    def test_build_report_body_no_unfixable(self):
        """build_report_body handles empty unfixable findings."""
        body = build_report_body([], [], [])
        assert "No issues require human attention" in body
        assert "No auto-fixes applied" in body

    def test_build_report_body_severity_counts(self):
        """build_report_body counts severities correctly."""
        unfixable = [
            Finding(probe="links", category="c1", message="m1", severity="warning", fixable=False),
            Finding(probe="links", category="c2", message="m2", severity="critical", fixable=False),
            Finding(probe="links", category="c3", message="m3", severity="info", fixable=False),
        ]
        body = build_report_body(unfixable, [], [])
        assert "| Critical | 1 |" in body
        assert "| Warning | 1 |" in body
        assert "| Info | 1 |" in body


class TestGetReporter:
    """Test reporter factory."""

    def test_get_reporter_local(self, tmp_path):
        """get_reporter returns LocalFileReporter for 'local'."""
        reporter = get_reporter("local", str(tmp_path))
        assert isinstance(reporter, LocalFileReporter)

    def test_get_reporter_github(self):
        """get_reporter returns GitHubReporter for 'github'."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            reporter = get_reporter("github", "/repo")
        assert isinstance(reporter, GitHubReporter)
```

### 6.21 `tests/unit/test_janitor/test_graph.py` (Add)

**Complete file contents:**

```python
"""Tests for janitor graph construction and routing.

Issue #94: Lu-Tze: The Janitor
Test IDs: T190-T230, T310-T350
"""

from unittest.mock import MagicMock, patch

from assemblyzero.workflows.janitor.graph import (
    build_janitor_graph,
    route_after_fix,
    route_after_sweep,
)
from assemblyzero.workflows.janitor.state import (
    Finding,
    JanitorState,
)


class TestRouteAfterSweep:
    """Test conditional routing after sweep. T190-T210, T310-T330."""

    def test_no_findings_returns_end(self):
        """T190/T310: route_after_sweep returns __end__ when no findings."""
        state = {"all_findings": [], "auto_fix": True}
        assert route_after_sweep(state) == "__end__"

    def test_fixable_auto_fix_returns_fixer(self):
        """T200/T320: route_after_sweep returns n1_fixer with fixable findings + auto_fix."""
        state = {
            "all_findings": [
                Finding(probe="links", category="broken_link", message="m", severity="warning", fixable=True)
            ],
            "auto_fix": True,
        }
        assert route_after_sweep(state) == "n1_fixer"

    def test_fixable_no_auto_fix_returns_reporter(self):
        """route_after_sweep returns n2_reporter when fixable but auto_fix=False."""
        state = {
            "all_findings": [
                Finding(probe="links", category="broken_link", message="m", severity="warning", fixable=True)
            ],
            "auto_fix": False,
        }
        assert route_after_sweep(state) == "n2_reporter"

    def test_unfixable_only_returns_reporter(self):
        """T210/T330: route_after_sweep returns n2_reporter with only unfixable."""
        state = {
            "all_findings": [
                Finding(probe="todo", category="stale_todo", message="m", severity="info", fixable=False)
            ],
            "auto_fix": True,
        }
        assert route_after_sweep(state) == "n2_reporter"

    def test_mixed_fixable_and_unfixable_returns_fixer(self):
        """route_after_sweep returns n1_fixer when mixed findings + auto_fix."""
        state = {
            "all_findings": [
                Finding(probe="links", category="broken_link", message="m", severity="warning", fixable=True),
                Finding(probe="todo", category="stale_todo", message="m", severity="info", fixable=False),
            ],
            "auto_fix": True,
        }
        assert route_after_sweep(state) == "n1_fixer"


class TestRouteAfterFix:
    """Test conditional routing after fix. T220, T230, T340, T350."""

    def test_all_fixed_returns_end(self):
        """T220/T340: route_after_fix returns __end__ when unfixable list empty."""
        state = {"unfixable_findings": []}
        assert route_after_fix(state) == "__end__"

    def test_unfixable_remain_returns_reporter(self):
        """T230/T350: route_after_fix returns n2_reporter when unfixable exist."""
        state = {
            "unfixable_findings": [
                Finding(probe="todo", category="stale_todo", message="m", severity="info", fixable=False)
            ]
        }
        assert route_after_fix(state) == "n2_reporter"


class TestBuildJanitorGraph:
    """Test graph construction."""

    def test_build_janitor_graph_compiles(self):
        """build_janitor_graph returns a compiled graph."""
        graph = build_janitor_graph()
        # Compiled graph should be callable (has invoke method)
        assert hasattr(graph, "invoke")

    def test_graph_with_no_findings(self):
        """Graph exits cleanly with no findings (all probes return ok)."""
        with patch(
            "assemblyzero.workflows.janitor.graph.get_probes",
            return_value=[],
        ):
            graph = build_janitor_graph()
            initial_state: JanitorState = {
                "repo_root": "/fake/repo",
                "scope": [],
                "auto_fix": True,
                "dry_run": False,
                "silent": True,
                "create_pr": False,
                "reporter_type": "local",
                "probe_results": [],
                "all_findings": [],
                "fix_actions": [],
                "unfixable_findings": [],
                "report_url": None,
                "exit_code": 0,
            }
            final_state = graph.invoke(initial_state)

        assert final_state["all_findings"] == []
        assert final_state["exit_code"] == 0
```

### 6.22 `tests/unit/test_janitor/test_cli.py` (Add)

**Complete file contents:**

```python
"""Tests for janitor CLI argument parsing.

Issue #94: Lu-Tze: The Janitor
Test IDs: T240-T260, T360-T380
"""

import io
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

from tools.run_janitor_workflow import (
    build_initial_state,
    main,
    parse_args,
)


class TestParseArgs:
    """Test CLI argument parsing. T240, T250, T260, T360, T370."""

    def test_defaults(self):
        """T240/T360: parse_args with no args returns correct defaults."""
        args = parse_args([])
        assert args.scope == "all"
        assert args.auto_fix is True
        assert args.dry_run is False
        assert args.silent is False
        assert args.create_pr is False
        assert args.reporter == "github"

    def test_all_flags(self):
        """T250/T370: parse_args handles all flag combinations."""
        args = parse_args([
            "--scope", "links",
            "--dry-run",
            "--silent",
            "--create-pr",
            "--reporter", "local",
        ])
        assert args.scope == "links"
        assert args.dry_run is True
        assert args.silent is True
        assert args.create_pr is True
        assert args.reporter == "local"

    def test_invalid_scope(self):
        """T260/T380: parse_args with invalid scope raises SystemExit."""
        with pytest.raises(SystemExit):
            parse_args(["--scope", "invalid"])

    def test_scope_worktrees(self):
        """parse_args accepts worktrees scope."""
        args = parse_args(["--scope", "worktrees"])
        assert args.scope == "worktrees"

    def test_scope_harvest(self):
        """parse_args accepts harvest scope."""
        args = parse_args(["--scope", "harvest"])
        assert args.scope == "harvest"

    def test_scope_todo(self):
        """parse_args accepts todo scope."""
        args = parse_args(["--scope", "todo"])
        assert args.scope == "todo"

    def test_reporter_local(self):
        """parse_args accepts local reporter."""
        args = parse_args(["--reporter", "local"])
        assert args.reporter == "local"

    def test_auto_fix_false(self):
        """parse_args handles --auto-fix false."""
        args = parse_args(["--auto-fix", "false"])
        assert args.auto_fix is False


class TestBuildInitialState:
    """Test state construction from CLI args. T010, T390."""

    def test_build_initial_state_scope_all(self):
        """T010/T390: build_initial_state converts 'all' scope to full list."""
        args = parse_args(["--reporter", "local"])

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="/home/user/repo\n"
            )
            state = build_initial_state(args)

        assert state["scope"] == ["links", "worktrees", "harvest", "todo"]
        assert state["repo_root"] == "/home/user/repo"
        assert state["reporter_type"] == "local"
        assert state["probe_results"] == []
        assert state["exit_code"] == 0

    def test_build_initial_state_single_scope(self):
        """build_initial_state converts single scope correctly."""
        args = parse_args(["--scope", "links", "--dry-run"])

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="/repo\n"
            )
            state = build_initial_state(args)

        assert state["scope"] == ["links"]
        assert state["dry_run"] is True


class TestMainEntryPoint:
    """Test main() entry point. T270-T350."""

    def test_exit_code_2_not_git_repo(self):
        """T350: main() returns 2 when not in a git repo."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=128, stdout="", stderr="not a git repo")
            code = main(["--silent"])
        assert code == 2

    def test_exit_code_0_clean_run(self):
        """T270: main() returns 0 when no findings."""
        with patch("subprocess.run") as mock_git, patch(
            "tools.run_janitor_workflow.build_janitor_graph"
        ) as mock_graph:
            mock_git.return_value = MagicMock(returncode=0, stdout="/repo\n")
            mock_compiled = MagicMock()
            mock_compiled.invoke.return_value = {
                "repo_root": "/repo",
                "scope": [],
                "auto_fix": True,
                "dry_run": False,
                "silent": True,
                "create_pr": False,
                "reporter_type": "local",
                "probe_results": [],
                "all_findings": [],
                "fix_actions": [],
                "unfixable_findings": [],
                "report_url": None,
                "exit_code": 0,
            }
            mock_graph.return_value = mock_compiled
            code = main(["--silent", "--reporter", "local"])
        assert code == 0

    def test_exit_code_1_unfixable(self):
        """T280: main() returns 1 when unfixable findings remain."""
        with patch("subprocess.run") as mock_git, patch(
            "tools.run_janitor_workflow.build_janitor_graph"
        ) as mock_graph:
            mock_git.return_value = MagicMock(returncode=0, stdout="/repo\n")
            mock_compiled = MagicMock()
            mock_compiled.invoke.return_value = {
                "exit_code": 1,
                "all_findings": [],
                "fix_actions": [],
                "unfixable_findings": [],
                "report_url": None,
            }
            mock_graph.return_value = mock_compiled
            code = main(["--silent", "--reporter", "local"])
        assert code == 1

    def test_silent_no_stdout(self, capsys):
        """T340: main with --silent produces no stdout on clean run."""
        with patch("subprocess.run") as mock_git, patch(
            "tools.run_janitor_workflow.build_janitor_graph"
        ) as mock_graph:
            mock_git.return_value = MagicMock(returncode=0, stdout="/repo\n")
            mock_compiled = MagicMock()
            mock_compiled.invoke.return_value = {
                "exit_code": 0,
                "all_findings": [],
                "fix_actions": [],
                "unfixable_findings": [],
                "report_url": None,
            }
            mock_graph.return_value = mock_compiled
            code = main(["--silent", "--reporter", "local"])

        captured = capsys.readouterr()
        assert captured.out == ""
        assert code == 0

    def test_fatal_exception_returns_2(self):
        """main() returns 2 on unhandled exception."""
        with patch("subprocess.run") as mock_git, patch(
            "tools.run_janitor_workflow.build_janitor_graph"
        ) as mock_graph:
            mock_git.return_value = MagicMock(returncode=0, stdout="/repo\n")
            mock_graph.side_effect = RuntimeError("Graph build failed")
            code = main(["--silent", "--reporter", "local"])
        assert code == 2
```

### 6.23 `tests/integration/test_janitor_workflow.py` (Add)

**Complete file contents:**

```python
"""Integration test for full janitor workflow using LocalFileReporter.

Issue #94: Lu-Tze: The Janitor
Test IDs: T290, T300, T310, T320, T330, T400
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.workflows.janitor.graph import build_janitor_graph
from assemblyzero.workflows.janitor.state import (
    Finding,
    JanitorState,
    ProbeResult,
)


def _make_initial_state(tmp_path: Path, **overrides) -> JanitorState:
    """Helper to build a test JanitorState."""
    defaults: JanitorState = {
        "repo_root": str(tmp_path),
        "scope": ["links"],
        "auto_fix": True,
        "dry_run": False,
        "silent": True,
        "create_pr": False,
        "reporter_type": "local",
        "probe_results": [],
        "all_findings": [],
        "fix_actions": [],
        "unfixable_findings": [],
        "report_url": None,
        "exit_code": 0,
    }
    defaults.update(overrides)
    return defaults


class TestFullWorkflowIntegration:
    """Integration tests for complete janitor workflow. T290, T400."""

    def test_clean_run_exits_zero(self, tmp_path):
        """T290/T400: Full workflow with no findings exits cleanly."""
        mock_probe = MagicMock(return_value=ProbeResult(probe="links", status="ok"))

        with patch(
            "assemblyzero.workflows.janitor.graph.get_probes",
            return_value=[("links", mock_probe)],
        ):
            graph = build_janitor_graph()
            state = _make_initial_state(tmp_path)
            final = graph.invoke(state)

        assert final["exit_code"] == 0
        assert final["all_findings"] == []

    def test_unfixable_findings_create_local_report(self, tmp_path):
        """Integration: unfixable findings create local report file."""
        unfixable_finding = Finding(
            probe="todo",
            category="stale_todo",
            message="Stale TODO in helper.py:42",
            severity="info",
            fixable=False,
            file_path="tools/helper.py",
            line_number=42,
        )
        mock_probe = MagicMock(
            return_value=ProbeResult(
                probe="todo", status="findings", findings=[unfixable_finding]
            )
        )

        with patch(
            "assemblyzero.workflows.janitor.graph.get_probes",
            return_value=[("todo", mock_probe)],
        ):
            graph = build_janitor_graph()
            state = _make_initial_state(tmp_path, scope=["todo"])
            final = graph.invoke(state)

        assert final["exit_code"] == 1
        assert final["report_url"] is not None
        assert Path(final["report_url"]).exists()
        report_content = Path(final["report_url"]).read_text()
        assert "Janitor Report" in report_content
        assert "stale_todo" in report_content

    def test_fixable_findings_auto_fixed(self, tmp_path):
        """T320: Broken link auto-fixed with unique target."""
        # Create mock repo
        readme = tmp_path / "README.md"
        readme.write_text("[guide](./docs/old-guide.md)\n")
        docs = tmp_path / "docs"
        docs.mkdir()
        guide = docs / "guide.md"
        guide.write_text("# Guide\n")

        fixable_finding = Finding(
            probe="links",
            category="broken_link",
            message="Broken link",
            severity="warning",
            fixable=True,
            file_path="README.md",
            line_number=1,
            fix_data={"old_link": "./docs/old-guide.md", "new_link": "./docs/guide.md"},
        )
        mock_probe = MagicMock(
            return_value=ProbeResult(
                probe="links", status="findings", findings=[fixable_finding]
            )
        )

        with patch(
            "assemblyzero.workflows.janitor.graph.get_probes",
            return_value=[("links", mock_probe)],
        ), patch(
            "assemblyzero.workflows.janitor.fixers.create_fix_commit"
        ):
            graph = build_janitor_graph()
            state = _make_initial_state(tmp_path)
            final = graph.invoke(state)

        assert final["exit_code"] == 0
        assert len(final["fix_actions"]) > 0
        assert final["fix_actions"][0].applied is True
        # Verify file was actually modified
        assert "./docs/guide.md" in readme.read_text()

    def test_dry_run_no_modifications(self, tmp_path):
        """T310: Dry-run prevents file modification."""
        readme = tmp_path / "README.md"
        original = "[guide](./docs/old-guide.md)\n"
        readme.write_text(original)

        fixable_finding = Finding(
            probe="links",
            category="broken_link",
            message="Broken link",
            severity="warning",
            fixable=True,
            file_path="README.md",
            line_number=1,
            fix_data={"old_link": "./docs/old-guide.md", "new_link": "./docs/guide.md"},
        )
        mock_probe = MagicMock(
            return_value=ProbeResult(
                probe="links", status="findings", findings=[fixable_finding]
            )
        )

        with patch(
            "assemblyzero.workflows.janitor.graph.get_probes",
            return_value=[("links", mock_probe)],
        ):
            graph = build_janitor_graph()
            state = _make_initial_state(tmp_path, dry_run=True)
            final = graph.invoke(state)

        # File should not be modified in dry-run
        assert readme.read_text() == original
        assert len(final["fix_actions"]) > 0
        assert final["fix_actions"][0].applied is False

    def test_mixed_findings_fix_then_report(self, tmp_path):
        """T330: Mixed fixable/unfixable → fix, then report unfixable."""
        readme = tmp_path / "README.md"
        readme.write_text("[guide](./docs/old-guide.md)\n")
        docs = tmp_path / "docs"
        docs.mkdir()
        guide = docs / "guide.md"
        guide.write_text("# Guide\n")

        fixable = Finding(
            probe="links", category="broken_link", message="Broken",
            severity="warning", fixable=True, file_path="README.md",
            line_number=1,
            fix_data={"old_link": "./docs/old-guide.md", "new_link": "./docs/guide.md"},
        )
        unfixable = Finding(
            probe="todo", category="stale_todo", message="Old TODO",
            severity="info", fixable=False, file_path="helper.py", line_number=10,
        )
        mock_probe = MagicMock(
            return_value=ProbeResult(
                probe="links", status="findings", findings=[fixable, unfixable]
            )
        )

        with patch(
            "assemblyzero.workflows.janitor.graph.get_probes",
            return_value=[("links", mock_probe)],
        ), patch(
            "assemblyzero.workflows.janitor.fixers.create_fix_commit"
        ):
            graph = build_janitor_graph()
            state = _make_initial_state(tmp_path)
            final = graph.invoke(state)

        assert final["exit_code"] == 1  # Unfixable remain
        assert len(final["fix_actions"]) > 0
        assert len(final["unfixable_findings"]) == 1
        assert final["report_url"] is not None
```

### 6.24 `docs/adrs/0204-janitor-probe-plugin-system.md` (Add)

**Complete file contents:**

```markdown
# ADR 0204: Janitor Probe Plugin System

## Status

Accepted

## Context

Issue #94 introduces the Janitor workflow with four built-in probes (links, worktrees, harvest, todo). We need a pattern for organizing probes that allows:

1. Easy addition of new probes without modifying core workflow code
2. Crash isolation — one probe failure doesn't affect others
3. Consistent data structures across all probes

## Decision

We adopt a **registry-based probe system** with the following characteristics:

- **Probe Interface:** Each probe is a function `(repo_root: str) -> ProbeResult`
- **Registry:** `PROBE_REGISTRY` dict maps `ProbeScope` names to probe functions
- **Isolation:** `run_probe_safe()` wraps each probe in try/except, converting crashes to error-status `ProbeResult` objects
- **Discovery:** Probes are registered in `assemblyzero/workflows/janitor/probes/__init__.py` via lazy import

### Adding a New Probe

1. Create `assemblyzero/workflows/janitor/probes/new_probe.py`
2. Implement `probe_new(repo_root: str) -> ProbeResult`
3. Add to `ProbeScope` literal type in `state.py`
4. Register in `_build_registry()` in `probes/__init__.py`
5. Add CLI scope option in `tools/run_janitor_workflow.py`

## Alternatives Considered

- **Class-based plugins with auto-discovery:** More complex, not needed at current scale
- **Entry points / setuptools plugins:** Over-engineered for internal-only probes
- **Simple function list:** No type safety on scope names

## Consequences

- New probes require changes to 3 files (probe module, state.py, probes/__init__.py)
- All probes share the same `ProbeResult` contract
- Crash isolation is guaranteed by the `run_probe_safe` wrapper
- Scope validation happens at parse time via the `ProbeScope` literal type
```

## 7. Pattern References

### 7.1 State TypedDict Pattern

**File:** `assemblyzero/workflows/implementation_spec/state.py` (lines 1-50)

```python
class ImplementationSpecState(TypedDict):
    """State for the implementation spec workflow."""
    issue_number: int
    lld_path: str
    lld_content: str
    # ... more fields
```

**Relevance:** Same TypedDict pattern used for `JanitorState`. All workflow states in the project follow this convention — TypedDict with field grouping comments.

### 7.2 Graph Construction Pattern

**File:** `assemblyzero/workflows/implementation_spec/graph.py` (lines 1-60)

```python
from langgraph.graph import StateGraph, END

def build_implementation_spec_graph() -> StateGraph:
    graph = StateGraph(ImplementationSpecState)
    graph.add_node("n0_load", n0_load)
    graph.add_node("n1_generate", n1_generate)
    # ...
    graph.set_entry_point("n0_load")
    graph.add_edge("n0_load", "n1_generate")
    # ...
    return graph.compile()
```

**Relevance:** Exact same pattern for `build_janitor_graph()` — `StateGraph` construction, `add_node`, `set_entry_point`, `add_edge`/`add_conditional_edges`, `compile()`.

### 7.3 CLI Tool Pattern

**File:** `tools/run_audit.py` (lines 1-40)

```python
#!/usr/bin/env python3
"""CLI description."""
import argparse
import sys

def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="...")
    parser.add_argument(...)
    return parser.parse_args(argv)

def main(argv=None):
    args = parse_args(argv)
    # ... workflow execution
    return exit_code

if __name__ == "__main__":
    sys.exit(main())
```

**Relevance:** Same CLI structure for `tools/run_janitor_workflow.py` — `parse_args`, `main`, `if __name__` guard.

### 7.4 Workflow Test Pattern

**File:** `tests/e2e/test_issue_workflow_mock.py` (lines 1-60)

```python
from unittest.mock import MagicMock, patch

def test_workflow_clean_run():
    with patch("...") as mock_thing:
        mock_thing.return_value = MagicMock(...)
        graph = build_graph()
        state = {...}
        final = graph.invoke(state)
    assert final["exit_code"] == 0
```

**Relevance:** Same pattern for janitor graph tests — mock external dependencies, invoke graph, assert on final state.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from __future__ import annotations` | stdlib | All new files |
| `from typing import TypedDict, Literal, Callable` | stdlib | `state.py`, `probes/__init__.py` |
| `from dataclasses import dataclass, field` | stdlib | `state.py` |
| `import abc` | stdlib | `reporter.py` |
| `import argparse` | stdlib | `run_janitor_workflow.py` |
| `import json` | stdlib | `reporter.py` |
| `import os` | stdlib | Multiple files |
| `import re` | stdlib | `probes/links.py`, `probes/todo.py` |
| `import subprocess` | stdlib | Multiple files (git/gh CLI calls) |
| `import sys` | stdlib | `run_janitor_workflow.py` |
| `from collections import defaultdict` | stdlib | `graph.py`, `fixers.py` |
| `from datetime import datetime, timedelta, timezone` | stdlib | `probes/worktrees.py`, `probes/todo.py`, `reporter.py` |
| `from pathlib import Path` | stdlib | `probes/links.py`, `reporter.py` |
| `from langgraph.graph import StateGraph, END` | langgraph (in pyproject.toml) | `graph.py` |
| `from assemblyzero.workflows.janitor.state import *` | internal | All janitor modules |
| `from assemblyzero.workflows.janitor.probes import *` | internal | `graph.py` |
| `from assemblyzero.workflows.janitor.fixers import *` | internal | `graph.py` |
| `from assemblyzero.workflows.janitor.reporter import *` | internal | `graph.py` |
| `from assemblyzero.workflows.janitor.graph import build_janitor_graph` | internal | `__init__.py`, `run_janitor_workflow.py` |

**New Dependencies:** None — all packages already in `pyproject.toml`.

## 9. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `build_initial_state()` | `parse_args(["--reporter", "local"])` | `JanitorState` with `scope=["links","worktrees","harvest","todo"]`, `reporter_type="local"` |
| T020 | `probe_links()` | mock repo with broken `./docs/old-guide.md` link | `ProbeResult(status="findings")` with `fixable=True` finding |
| T030 | `probe_links()` | mock README with `https://example.com` only | `ProbeResult(status="ok")`, no findings |
| T040 | `probe_links()` | mock repo with valid `./docs/guide.md` link | `ProbeResult(status="ok")` |
| T050 | `probe_worktrees()` | mocked 15-day-old merged worktree | `ProbeResult(status="findings")` with `fixable=True` |
| T060 | `probe_worktrees()` | mocked 1-day-old active worktree | `ProbeResult(status="ok")` |
| T070 | `probe_todo()` | mocked TODO 45 days old | `ProbeResult(status="findings")` with `fixable=False` |
| T080 | `probe_todo()` | mocked TODO added today | `ProbeResult(status="ok")` |
| T090 | `probe_harvest()` | no harvest script in repo | `ProbeResult(status="findings")` with `harvest_missing` info |
| T100 | `run_probe_safe()` | probe raises `RuntimeError` | `ProbeResult(status="error", error_message="RuntimeError: ...")` |
| T110 | `fix_broken_links()` | finding + real file, `dry_run=False` | File updated, `FixAction(applied=True)` |
| T120 | `fix_broken_links()` | finding + real file, `dry_run=True` | File unchanged, `FixAction(applied=False)` |
| T130 | `fix_stale_worktrees()` | worktree finding, `dry_run=False` | `subprocess.run` called with `git worktree remove` |
| T140 | `generate_commit_message()` | `"broken_link"`, `3` | `"chore: fix 3 broken markdown link(s) (ref #94)"` |
| T150 | `LocalFileReporter.create_report()` | title, body, severity | File created in `janitor-reports/` |
| T160 | `LocalFileReporter.update_report()` | existing path, new body | File overwritten |
| T170 | `LocalFileReporter.find_existing_report()` | report from today exists | Returns file path |
| T180 | `build_report_body()` | mixed findings + actions | Markdown with all sections |
| T190 | `route_after_sweep()` | `{"all_findings": []}` | `"__end__"` |
| T200 | `route_after_sweep()` | fixable finding + `auto_fix=True` | `"n1_fixer"` |
| T210 | `route_after_sweep()` | unfixable only | `"n2_reporter"` |
| T220 | `route_after_fix()` | `{"unfixable_findings": []}` | `"__end__"` |
| T230 | `route_after_fix()` | non-empty unfixable | `"n2_reporter"` |
| T240 | `parse_args()` | `[]` | defaults: scope=all, auto_fix=True, etc. |
| T250 | `parse_args()` | all flags | all values parsed correctly |
| T260 | `parse_args()` | `["--scope", "invalid"]` | `SystemExit` |
| T270 | `main()` | mocked clean run | return `0` |
| T280 | `main()` | mocked unfixable findings | return `1` |
| T290 | `graph.invoke()` | integration with `LocalFileReporter` | report created, correct exit code |
| T300 | `main()` | mocked probes returning mixed | sweeper→fixer→reporter chain executes |
| T310 | `graph.invoke()` | `dry_run=True` with fixable | `FixAction(applied=False)`, file unchanged |
| T320 | `graph.invoke()` | broken link finding + real file | file updated, commit mocked |
| T330 | `graph.invoke()` | mixed findings | fix applied + report for unfixable |
| T340 | `main()` | `["--silent"]` + clean | no stdout |
| T350 | `main()` | not in git repo | return `2` |
| T360 | `GitHubReporter.__init__()` | `GITHUB_TOKEN` set, gh auth fails | reporter initializes successfully |
| T370 | `GitHubReporter.find_existing_report()` | existing issue found | returns URL, `update_report` would be called |
| T380 | `LocalFileReporter.create_report()` | standard inputs | file in `janitor-reports/` |

## 10. Implementation Notes

### 10.1 Error Handling Convention

- **Probes:** Never raise to caller. `run_probe_safe()` catches all exceptions and converts to `ProbeResult(status="error")`.
- **Fixers:** May raise `subprocess.CalledProcessError` for git operations. The fixer functions catch and log these.
- **Reporter:** `GitHubReporter` raises `RuntimeError` on auth failure. `LocalFileReporter` raises `OSError` on file I/O failure.
- **CLI main():** Top-level try/except catches all exceptions and returns exit code 2.

### 10.2 Logging Convention

- Use `print()` for user-facing output (respects `--silent` flag).
- No logging framework — keep it simple. Print statements are guarded by `if not state["silent"]:`.
- Error output goes to `sys.stderr`.

### 10.3 Constants

| Constant | Value | Rationale | File |
|----------|-------|-----------|------|
| `STALE_DAYS_THRESHOLD` | `14` | Worktrees inactive for 14+ days with merged branch are stale | `probes/worktrees.py` |
| `STALE_TODO_DAYS` | `30` | TODOs older than 30 days are flagged | `probes/todo.py` |
| `COMMIT_TEMPLATES` | dict of 2 templates | Deterministic commit messages, no LLM | `fixers.py` |
| `ALL_SCOPES` | `["links", "worktrees", "harvest", "todo"]` | Full list for `--scope all` | `run_janitor_workflow.py` |

### 10.4 Subprocess Safety

All `subprocess.run()` calls use **list-form arguments** (never `shell=True`) to prevent command injection:

```python
# CORRECT:
subprocess.run(["git", "worktree", "remove", path], cwd=repo_root, capture_output=True, text=True)

# NEVER:
subprocess.run(f"git worktree remove {path}", shell=True)
```

### 10.5 Path Handling

Use `pathlib.Path` and `os.path` throughout for Windows compatibility. Never hardcode `/` as path separator. Key patterns:

```python
from pathlib import Path

# Resolve relative to source file's directory
resolved = (Path(source_file).parent / link_target).resolve()

# Ensure path is within repo root (security)
resolved.relative_to(Path(repo_root).resolve())  # Raises ValueError if not within

# Cross-platform path joining
os.path.join(repo_root, relative_path)
```

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3 — `.gitignore`)
- [x] Every data structure has a concrete JSON/YAML example (Section 4 — all 6 structures)
- [x] Every function has input/output examples with realistic values (Section 5 — all 37 functions)
- [x] Change instructions are diff-level specific (Section 6 — all 24 files)
- [x] Pattern references include file:line and are verified to exist (Section 7 — 4 patterns)
- [x] All imports are listed and verified (Section 8 — all imports)
- [x] Test mapping covers all LLD test scenarios (Section 9 — T010-T380)

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #94 |
| Verdict | DRAFT |
| Date | 2026-03-02 |
| Iterations | 1 |
| Finalized | — |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #94 |
| Verdict | APPROVED |
| Date | 2026-03-01 |
| Iterations | 0 |
| Finalized | 2026-03-01T14:48:15Z |

### Review Feedback Summary

The implementation spec is exceptionally thorough and provides nearly 100% of the code required for implementation. It correctly utilizes LangGraph patterns, implements robust isolation for probes, and provides comprehensive test suites that match the LLD requirements.

## Suggestions
- In the n1_fixer implementation within graph.py, the pr_url returned by create_fix_pr is currently discarded; consider adding a field to JanitorState to store this URL so the reporter or CLI summary can display it...


## Required File Paths (from LLD - do not deviate)

The following paths are specified in the LLD. Write ONLY to these paths:


Any files written to other paths will be rejected.

## Repository Structure

The actual directory layout of this repository:

```
tests/
  accessibility/
  adversarial/
  benchmark/
  compliance/
  contract/
  e2e/
  fixtures/
    issue_workflow/
    janitor/
      mock_repo/
    lld_tracking/
    metrics/
    mock_lineage/
    mock_repo/
      src/
    rag/
    scout/
    scraper/
    verdict_analyzer/
  harness/
  integration/
  security/
  tools/
  unit/
    test_gate/
    test_janitor/
    test_metrics/
    test_rag/
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
  metrics/
  nodes/
  rag/
  telemetry/
  utils/
  workflow/
  workflows/
    implementation_spec/
      nodes/
    issue/
      nodes/
    janitor/
      probes/
    lld/
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
      runners/
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
# From C:\Users\mcwiz\Projects\AssemblyZero\tests\unit\test_janitor\test_state.py
"""Tests for janitor state structures.

Issue #94: Lu-Tze: The Janitor
Test IDs: T010, T390
"""

from assemblyzero.workflows.janitor.state import (
    Finding,
    FixAction,
    JanitorState,
    ProbeResult,
)


class TestFinding:
    """Test Finding dataclass."""

    def test_finding_creation_with_defaults(self):
        """Finding can be created with minimal fields."""
        f = Finding(
            probe="links",
            category="broken_link",
            message="test message",
            severity="warning",
            fixable=True,
        )
        assert f.probe == "links"
        assert f.file_path is None
        assert f.line_number is None
        assert f.fix_data is None

    def test_finding_creation_with_all_fields(self):
        """Finding can be created with all fields."""
        f = Finding(
            probe="links",
            category="broken_link",
            message="Broken link",
            severity="warning",
            fixable=True,
            file_path="README.md",
            line_number=15,
            fix_data={"old_link": "./old.md", "new_link": "./new.md"},
        )
        assert f.file_path == "README.md"
        assert f.line_number == 15
        assert f.fix_data["old_link"] == "./old.md"


class TestProbeResult:
    """Test ProbeResult dataclass."""

    def test_probe_result_ok(self):
        """ProbeResult with ok status has empty findings."""
        pr = ProbeResult(probe="links", status="ok")
        assert pr.findings == []
        assert pr.error_message is None

    def test_probe_result_error(self):
        """ProbeResult with error status has error message."""
        pr = ProbeResult(
            probe="links", status="error", error_message="RuntimeError: boom"
        )
        assert pr.status == "error"
        assert pr.error_message == "RuntimeError: boom"


class TestFixAction:
    """Test FixAction dataclass."""

    def test_fix_action_applied(self):
        """FixAction records applied fix."""
        fa = FixAction(
            category="broken_link",
            description="Fixed link",
            files_modified=["README.md"],
            commit_message="chore: fix 1 broken markdown link(s) (ref #94)",
            applied=True,
        )
        assert fa.applied is True
        assert fa.files_modified == ["README.md"]

    def test_fix_action_dry_run(self):
        """FixAction records dry-run (not applied)."""
        fa = FixAction(
            category="broken_link",
            description="Would fix link",
            files_modified=["README.md"],
            commit_message="chore: fix 1 broken markdown link(s) (ref #94)",
            applied=False,
        )
        assert fa.applied is False


class TestJanitorState:
    """Test JanitorState TypedDict. T010, T390."""

    def test_initial_state_construction(self):
        """JanitorState can be constructed with all required keys. T390."""
        state: JanitorState = {
            "repo_root": "/home/user/projects/repo",
            "scope": ["links", "worktrees"],
            "auto_fix": True,
            "dry_run": False,
            "silent": False,
            "create_pr": False,
            "reporter_type": "local",
            "probe_results": [],
            "all_findings": [],
            "fix_actions": [],
            "unfixable_findings": [],
            "report_url": None,
            "exit_code": 0,
        }
        assert state["repo_root"] == "/home/user/projects/repo"
        assert state["scope"] == ["links", "worktrees"]
        assert state["exit_code"] == 0

# From C:\Users\mcwiz\Projects\AssemblyZero\tests\unit\test_janitor\test_probes.py
"""Tests for janitor probes.

Issue #94: Lu-Tze: The Janitor
Test IDs: T020-T100, T150-T220
"""

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, mock_open, patch

import pytest

from assemblyzero.workflows.janitor.probes import run_probe_safe
from assemblyzero.workflows.janitor.probes.harvest import (
    find_harvest_script,
    parse_harvest_output,
    probe_harvest,
)
from assemblyzero.workflows.janitor.probes.links import (
    extract_internal_links,
    find_likely_target,
    find_markdown_files,
    probe_links,
    resolve_link,
)
from assemblyzero.workflows.janitor.probes.todo import (
    extract_todos,
    get_line_date,
    probe_todo,
)
from assemblyzero.workflows.janitor.probes.worktrees import (
    get_branch_last_commit_date,
    is_branch_merged,
    list_worktrees,
    probe_worktrees,
)
from assemblyzero.workflows.janitor.state import ProbeResult


FIXTURES_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "fixtures", "janitor", "mock_repo"
)


class TestProbeLinkDetection:
    """Test broken link detection. T020, T030, T040, T150, T160, T170."""

    def test_probe_links_detects_broken_link(self, tmp_path):
        """T020/T150: probe_links returns fixable finding for resolvable broken link."""
        # Create mock repo with broken link
        readme = tmp_path / "README.md"
        readme.write_text("[guide](./docs/old-guide.md)\n")
        docs = tmp_path / "docs"
        docs.mkdir()
        guide = docs / "guide.md"
        guide.write_text("# Guide\n")

        with patch(
            "assemblyzero.workflows.janitor.probes.links.find_markdown_files",
            return_value=[str(readme)],
        ), patch(
            "assemblyzero.workflows.janitor.probes.links.find_likely_target",
            return_value="./docs/guide.md",
        ):
            result = probe_links(str(tmp_path))

        assert result.status == "findings"
        assert len(result.findings) == 1
        assert result.findings[0].fixable is True
        assert result.findings[0].fix_data["new_link"] == "./docs/guide.md"

    def test_probe_links_ignores_external_urls(self, tmp_path):
        """T030/T160: probe_links skips http/https links."""
        readme = tmp_path / "README.md"
        readme.write_text("[example](https://example.com)\n[other](http://other.com)\n")

        with patch(
            "assemblyzero.workflows.janitor.probes.links.find_markdown_files",
            return_value=[str(readme)],
        ):
            result = probe_links(str(tmp_path))

        assert result.status == "ok"
        assert result.findings == []

    def test_probe_links_handles_valid_links(self, tmp_path):
        """T040/T170: probe_links returns ok for all valid links."""
        docs = tmp_path / "docs"
        docs.mkdir()
        guide = docs / "guide.md"
        guide.write_text("# Guide\n")
        readme = tmp_path / "README.md"
        readme.write_text("[guide](./docs/guide.md)\n")

        with patch(
            "assemblyzero.workflows.janitor.probes.links.find_markdown_files",
            return_value=[str(readme)],
        ):
            result = probe_links(str(tmp_path))

        assert result.status == "ok"

    def test_extract_internal_links(self, tmp_path):
        """extract_internal_links returns relative links only."""
        md = tmp_path / "test.md"
        md.write_text(
            "# Test\n"
            "[guide](./docs/guide.md)\n"
            "[ext](https://example.com)\n"
            "![img](./images/pic.png)\n"
            "[anchor](#heading)\n"
        )
        links = extract_internal_links(str(md))
        assert len(links) == 2
        assert links[0] == (2, "guide", "./docs/guide.md")
        assert links[1] == (4, "img", "./images/pic.png")

    def test_resolve_link_existing(self, tmp_path):
        """resolve_link returns True for existing file."""
        docs = tmp_path / "docs"
        docs.mkdir()
        guide = docs / "guide.md"
        guide.write_text("# Guide\n")
        readme = tmp_path / "README.md"
        readme.write_text("")
        assert resolve_link(str(readme), "./docs/guide.md", str(tmp_path)) is True

    def test_resolve_link_missing(self, tmp_path):
        """resolve_link returns False for missing file."""
        readme = tmp_path / "README.md"
        readme.write_text("")
        assert resolve_link(str(readme), "./docs/nonexistent.md", str(tmp_path)) is False

    def test_resolve_link_with_anchor(self, tmp_path):
        """resolve_link strips anchor before checking."""
        docs = tmp_path / "docs"
        docs.mkdir()
        guide = docs / "guide.md"
        guide.write_text("# Guide\n")
        readme = tmp_path / "README.md"
        readme.write_text("")
        assert resolve_link(str(readme), "./docs/guide.md#section", str(tmp_path)) is True

    def test_find_likely_target_unique_match(self, tmp_path):
        """find_likely_target returns match when exactly one file with same basename."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="docs/guide.md\n"
            )
            result = find_likely_target("./docs/old-guide.md", str(tmp_path))
            # basename of old-guide.md is old-guide.md, no match for guide.md
            assert result is None

    def test_find_likely_target_no_match(self, tmp_path):
        """find_likely_target returns None when no files match."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="docs/guide.md\nREADME.md\n"
            )
            result = find_likely_target("./nonexistent.md", str(tmp_path))
            assert result is None


class TestProbeWorktrees:
    """Test worktree detection. T050, T060, T180, T190."""

    def test_probe_worktrees_detects_stale(self):
        """T050/T180: probe_worktrees returns finding for stale merged worktree."""
        past_date = datetime.now(timezone.utc) - timedelta(days=15)

        with patch(
            "assemblyzero.workflows.janitor.probes.worktrees.list_worktrees",
            return_value=[
                {
                    "path": "/repo",
                    "HEAD": "abc123",
                    "branch": "refs/heads/main",
                    "bare": False,
                    "detached": False,
                },
                {
                    "path": "/repo-42",
                    "HEAD": "def456",
                    "branch": "refs/heads/feature/old",
                    "bare": False,
                    "detached": False,
                },
            ],
        ), patch(
            "assemblyzero.workflows.janitor.probes.worktrees.get_branch_last_commit_date",
            return_value=past_date,
        ), patch(
            "assemblyzero.workflows.janitor.probes.worktrees.is_branch_merged",
            return_value=True,
        ):
            result = probe_worktrees("/repo")

        assert result.status == "findings"
        assert len(result.findings) == 1
        assert result.findings[0].category == "stale_worktree"
        assert result.findings[0].fixable is True

    def test_probe_worktrees_ignores_active(self):
        """T060/T190: probe_worktrees returns no finding for active worktree."""
        recent_date = datetime.now(timezone.utc) - timedelta(days=1)

        with patch(
            "assemblyzero.workflows.janitor.probes.worktrees.list_worktrees",
            return_value=[
                {
                    "path": "/repo",
                    "HEAD": "abc123",
                    "branch": "refs/heads/main",
                    "bare": False,
                    "detached": False,
                },
                {
                    "path": "/repo-42",
                    "HEAD": "def456",
                    "branch": "refs/heads/feature/active",
                    "bare": False,
                    "detached": False,
                },
            ],
        ), patch(
            "assemblyzero.workflows.janitor.probes.worktrees.get_branch_last_commit_date",
            return_value=recent_date,
        ):
            result = probe_worktrees("/repo")

        assert result.status == "ok"
        assert result.findings == []

    def test_list_worktrees_parses_porcelain(self):
        """list_worktrees parses git porcelain output correctly."""
        porcelain_output = (
            "worktree /home/user/repo\n"
            "HEAD abc123def456\n"
            "branch refs/heads/main\n"
            "\n"
            "worktree /home/user/repo-42\n"
            "HEAD def789abc012\n"
            "branch refs/heads/feature/thing\n"
            "\n"
        )
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout=porcelain_output
            )
            wts = list_worktrees("/repo")

        assert len(wts) == 2
        assert wts[0]["path"] == "/home/user/repo"
        assert wts[0]["branch"] == "refs/heads/main"
        assert wts[1]["path"] == "/home/user/repo-42"

    def test_list_worktrees_detached(self):
        """list_worktrees parses detached worktree correctly."""
        porcelain_output = (
            "worktree /home/user/repo\n"
            "HEAD abc123def456\n"
            "branch refs/heads/main\n"
            "\n"
            "worktree /home/user/repo-42\n"
            "HEAD def789abc012\n"
            "detached\n"
            "\n"
        )
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout=porcelain_output
            )
            wts = list_worktrees("/repo")

        assert wts[1]["detached"] is True
        assert "branch" not in wts[1]

    def test_get_branch_last_commit_date(self):
        """get_branch_last_commit_date parses ISO 8601 date."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="2026-02-15T10:30:00+00:00\n"
            )
            dt = get_branch_last_commit_date("/repo", "feature/thing")

        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 2
        assert dt.day == 15

    def test_get_branch_last_commit_date_nonexistent(self):
        """get_branch_last_commit_date returns None for nonexistent branch."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=128, stdout="")
            dt = get_branch_last_commit_date("/repo", "nonexistent")

        assert dt is None

    def test_is_branch_merged(self):
        """is_branch_merged returns True for merged branch."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="  feature/old\n* main\n"
            )
            assert is_branch_merged("/repo", "feature/old") is True

    def test_is_branch_not_merged(self):
        """is_branch_merged returns False for unmerged branch."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="* main\n"
            )
            assert is_branch_merged("/repo", "feature/active") is False


class TestProbeTodo:
    """Test TODO detection. T070, T080, T200, T210."""

    def test_probe_todo_finds_stale(self):
        """T070/T200: probe_todo returns finding for TODO older than 30 days."""
        past_date = datetime.now(timezone.utc) - timedelta(days=45)

        with patch(
            "assemblyzero.workflows.janitor.probes.todo.find_source_files",
            return_value=["tools/helper.py"],
        ), patch(
            "assemblyzero.workflows.janitor.probes.todo.extract_todos",
            return_value=[(42, "# TODO: refactor this function")],
        ), patch(
            "assemblyzero.workflows.janitor.probes.todo.get_line_date",
            return_value=past_date,
        ):
            result = probe_todo("/repo")

        assert result.status == "findings"
        assert len(result.findings) == 1
        assert result.findings[0].category == "stale_todo"
        assert result.findings[0].fixable is False

    def test_probe_todo_ignores_recent(self):
        """T080/T210: probe_todo returns no finding for recent TODO."""
        recent_date = datetime.now(timezone.utc) - timedelta(days=1)

        with patch(
            "assemblyzero.workflows.janitor.probes.todo.find_source_files",
            return_value=["tools/helper.py"],
        ), patch(
            "assemblyzero.workflows.janitor.probes.todo.extract_todos",
            return_value=[(42, "# TODO: add this feature")],
        ), patch(
            "assemblyzero.workflows.janitor.probes.todo.get_line_date",
            return_value=recent_date,
        ):
            result = probe_todo("/repo")

        assert result.status == "ok"
        assert result.findings == []

    def test_extract_todos(self, tmp_path):
        """extract_todos finds TODO/FIXME/HACK/XXX patterns."""
        f = tmp_path / "test.py"
        f.write_text(
            "def func():\n"
            "    # TODO: refactor this\n"
            "    pass\n"
            "    # FIXME: handle error\n"
            "    # Regular comment\n"
            "    # HACK: workaround for bug\n"
        )
        todos = extract_todos(str(f))
        assert len(todos) == 3
        assert todos[0] == (2, "# TODO: refactor this")
        assert todos[1] == (4, "# FIXME: handle error")
        assert todos[2] == (6, "# HACK: workaround for bug")

    def test_get_line_date_parses_blame(self):
        """get_line_date parses author-time from git blame porcelain."""
        blame_output = (
            "abc123 42 42 1\n"
            "author Test User\n"
            "author-mail <test@example.com>\n"
            "author-time 1737936000\n"  # 2025-01-27T00:00:00Z
            "author-tz +0000\n"
        )
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout=blame_output
            )
            dt = get_line_date("/repo", "test.py", 42)

        assert dt is not None
        assert dt.year == 2025

    def test_get_line_date_untracked(self):
        """get_line_date returns None for untracked file."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=128, stdout="")
            dt = get_line_date("/repo", "untracked.py", 1)

        assert dt is None


class TestProbeHarvest:
    """Test harvest detection. T090, T220."""

    def test_probe_harvest_missing_script(self):
        """T090/T220: probe_harvest returns info finding when script not found."""
        with patch(
            "assemblyzero.workflows.janitor.probes.harvest.find_harvest_script",
            return_value=None,
        ):
            result = probe_harvest("/repo")

        assert result.status == "findings"
        assert len(result.findings) == 1
        assert result.findings[0].category == "harvest_missing"
        assert result.findings[0].severity == "info"
        assert result.findings[0].fixable is False

    def test_parse_harvest_output_drift_lines(self):
        """parse_harvest_output extracts DRIFT lines."""
        output = (
            "OK: assemblyzero/state.py in sync\n"
            "DRIFT: pyproject.toml version mismatch\n"
            "OK: tools/audit.py in sync\n"
            "DRIFT: docs/standards/0001.md outdated\n"
        )
        findings = parse_harvest_output(output)
        assert len(findings) == 2
        assert findings[0].category == "cross_project_drift"
        assert "pyproject.toml" in findings[0].message

    def test_parse_harvest_output_no_drift(self):
        """parse_harvest_output returns empty list for clean output."""
        output = "OK: everything in sync\n"
        findings = parse_harvest_output(output)
        assert findings == []

    def test_find_harvest_script_in_root(self, tmp_path):
        """find_harvest_script finds script in repo root."""
        script = tmp_path / "assemblyzero-harvest.py"
        script.write_text("# script")
        assert find_harvest_script(str(tmp_path)) == str(script)

    def test_find_harvest_script_in_tools(self, tmp_path):
        """find_harvest_script finds script in tools/."""
        tools = tmp_path / "tools"
        tools.mkdir()
        script = tools / "assemblyzero-harvest.py"
        script.write_text("# script")
        assert find_harvest_script(str(tmp_path)) == str(script)

    def test_find_harvest_script_not_found(self, tmp_path):
        """find_harvest_script returns None when not found."""
        assert find_harvest_script(str(tmp_path)) is None


class TestProbeIsolation:
    """Test probe crash isolation. T100."""

    def test_run_probe_safe_catches_exception(self):
        """T100: run_probe_safe returns error ProbeResult on exception."""

        def crashing_probe(repo_root: str) -> ProbeResult:
            raise RuntimeError("Probe exploded!")

        result = run_probe_safe("links", crashing_probe, "/repo")
        assert result.status == "error"
        assert result.probe == "links"
        assert "RuntimeError: Probe exploded!" in result.error_message

    def test_run_probe_safe_passes_through_success(self):
        """run_probe_safe returns normal result on success."""
        expected = ProbeResult(probe="links", status="ok")

        def good_probe(repo_root: str) -> ProbeResult:
            return expected

        result = run_probe_safe("links", good_probe, "/repo")
        assert result.status == "ok"
        assert result is expected

# From C:\Users\mcwiz\Projects\AssemblyZero\tests\unit\test_janitor\test_fixers.py
"""Tests for janitor fixers.

Issue #94: Lu-Tze: The Janitor
Test IDs: T110-T140, T230-T260
"""

from unittest.mock import MagicMock, call, patch

from assemblyzero.workflows.janitor.fixers import (
    create_fix_commit,
    fix_broken_links,
    fix_stale_worktrees,
    generate_commit_message,
)
from assemblyzero.workflows.janitor.state import Finding


class TestFixBrokenLinks:
    """Test broken link fixer. T110, T120, T230, T240."""

    def test_fix_broken_links_updates_file(self, tmp_path):
        """T110/T230: fix_broken_links replaces broken link with correct target."""
        readme = tmp_path / "README.md"
        readme.write_text("[guide](./docs/old-guide.md)\n[other](./valid.md)\n")

        findings = [
            Finding(
                probe="links",
                category="broken_link",
                message="Broken link",
                severity="warning",
                fixable=True,
                file_path="README.md",
                line_number=1,
                fix_data={"old_link": "./docs/old-guide.md", "new_link": "./docs/guide.md"},
            )
        ]

        actions = fix_broken_links(findings, str(tmp_path), dry_run=False)

        assert len(actions) == 1
        assert actions[0].applied is True
        content = readme.read_text()
        assert "./docs/guide.md" in content
        assert "./docs/old-guide.md" not in content
        assert "./valid.md" in content  # Other links untouched

    def test_fix_broken_links_dry_run(self, tmp_path):
        """T120/T240: fix_broken_links with dry_run=True does not modify files."""
        readme = tmp_path / "README.md"
        original_content = "[guide](./docs/old-guide.md)\n"
        readme.write_text(original_content)

        findings = [
            Finding(
                probe="links",
                category="broken_link",
                message="Broken link",
                severity="warning",
                fixable=True,
                file_path="README.md",
                line_number=1,
                fix_data={"old_link": "./docs/old-guide.md", "new_link": "./docs/guide.md"},
            )
        ]

        actions = fix_broken_links(findings, str(tmp_path), dry_run=True)

        assert len(actions) == 1
        assert actions[0].applied is False
        assert readme.read_text() == original_content

    def test_fix_broken_links_no_fix_data(self, tmp_path):
        """fix_broken_links skips findings without fix_data."""
        findings = [
            Finding(
                probe="links",
                category="broken_link",
                message="Broken link",
                severity="warning",
                fixable=True,
                file_path="README.md",
                line_number=1,
                fix_data=None,
            )
        ]
        actions = fix_broken_links(findings, str(tmp_path), dry_run=False)
        assert actions == []

    def test_fix_broken_links_multiple_in_same_file(self, tmp_path):
        """fix_broken_links handles multiple broken links in the same file."""
        readme = tmp_path / "README.md"
        readme.write_text(
            "[guide](./docs/old-guide.md)\n"
            "[api](./docs/old-api.md)\n"
        )

        findings = [
            Finding(
                probe="links",
                category="broken_link",
                message="Broken link 1",
                severity="warning",
                fixable=True,
                file_path="README.md",
                line_number=1,
                fix_data={"old_link": "./docs/old-guide.md", "new_link": "./docs/guide.md"},
            ),
            Finding(
                probe="links",
                category="broken_link",
                message="Broken link 2",
                severity="warning",
                fixable=True,
                file_path="README.md",
                line_number=2,
                fix_data={"old_link": "./docs/old-api.md", "new_link": "./docs/api.md"},
            ),
        ]

        actions = fix_broken_links(findings, str(tmp_path), dry_run=False)

        assert len(actions) == 2
        content = readme.read_text()
        assert "./docs/guide.md" in content
        assert "./docs/api.md" in content
        assert "./docs/old-guide.md" not in content
        assert "./docs/old-api.md" not in content

    def test_fix_broken_links_missing_new_link(self, tmp_path):
        """fix_broken_links skips findings with fix_data missing new_link."""
        findings = [
            Finding(
                probe="links",
                category="broken_link",
                message="Broken link",
                severity="warning",
                fixable=True,
                file_path="README.md",
                line_number=1,
                fix_data={"old_link": "./docs/old-guide.md"},
            )
        ]
        actions = fix_broken_links(findings, str(tmp_path), dry_run=False)
        assert actions == []

    def test_fix_broken_links_nonexistent_file(self, tmp_path):
        """fix_broken_links handles missing source file gracefully."""
        findings = [
            Finding(
                probe="links",
                category="broken_link",
                message="Broken link",
                severity="warning",
                fixable=True,
                file_path="nonexistent.md",
                line_number=1,
                fix_data={"old_link": "./old.md", "new_link": "./new.md"},
            )
        ]
        actions = fix_broken_links(findings, str(tmp_path), dry_run=False)
        assert actions == []


class TestFixStaleWorktrees:
    """Test stale worktree fixer. T130, T250."""

    def test_fix_stale_worktrees_calls_git_remove(self):
        """T130/T250: fix_stale_worktrees invokes git worktree remove."""
        findings = [
            Finding(
                probe="worktrees",
                category="stale_worktree",
                message="Stale worktree",
                severity="warning",
                fixable=True,
                file_path="/home/user/repo-42",
                line_number=None,
                fix_data={"worktree_path": "/home/user/repo-42", "branch": "feature/old"},
            )
        ]

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            actions = fix_stale_worktrees(findings, "/home/user/repo", dry_run=False)

        assert len(actions) == 1
        assert actions[0].applied is True
        assert actions[0].category == "stale_worktree"
        mock_run.assert_called_once_with(
            ["git", "worktree", "remove", "/home/user/repo-42"],
            cwd="/home/user/repo",
            capture_output=True,
            text=True,
        )

    def test_fix_stale_worktrees_dry_run(self):
        """fix_stale_worktrees in dry-run does not call subprocess."""
        findings = [
            Finding(
                probe="worktrees",
                category="stale_worktree",
                message="Stale worktree",
                severity="warning",
                fixable=True,
                file_path="/home/user/repo-42",
                line_number=None,
                fix_data={"worktree_path": "/home/user/repo-42", "branch": "feature/old"},
            )
        ]

        with patch("subprocess.run") as mock_run:
            actions = fix_stale_worktrees(findings, "/home/user/repo", dry_run=True)

        assert len(actions) == 1
        assert actions[0].applied is False
        mock_run.assert_not_called()

    def test_fix_stale_worktrees_description_applied(self):
        """fix_stale_worktrees description says 'Pruned' when applied."""
        findings = [
            Finding(
                probe="worktrees",
                category="stale_worktree",
                message="Stale worktree",
                severity="warning",
                fixable=True,
                file_path="/home/user/repo-42",
                line_number=None,
                fix_data={"worktree_path": "/home/user/repo-42", "branch": "feature/old"},
            )
        ]

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            actions = fix_stale_worktrees(findings, "/home/user/repo", dry_run=False)

        assert "Pruned" in actions[0].description
        assert "feature/old" in actions[0].description

    def test_fix_stale_worktrees_description_dry_run(self):
        """fix_stale_worktrees description says 'Would prune' in dry-run."""
        findings = [
            Finding(
                probe="worktrees",
                category="stale_worktree",
                message="Stale worktree",
                severity="warning",
                fixable=True,
                file_path="/home/user/repo-42",
                line_number=None,
                fix_data={"worktree_path": "/home/user/repo-42", "branch": "feature/old"},
            )
        ]

        with patch("subprocess.run") as mock_run:
            actions = fix_stale_worktrees(findings, "/home/user/repo", dry_run=True)

        assert "Would prune" in actions[0].description

    def test_fix_stale_worktrees_missing_fix_data(self):
        """fix_stale_worktrees skips findings without fix_data."""
        findings = [
            Finding(
                probe="worktrees",
                category="stale_worktree",
                message="Stale worktree",
                severity="warning",
                fixable=True,
                file_path="/home/user/repo-42",
                line_number=None,
                fix_data=None,
            )
        ]

        with patch("subprocess.run") as mock_run:
            actions = fix_stale_worktrees(findings, "/home/user/repo", dry_run=False)

        assert actions == []
        mock_run.assert_not_called()

    def test_fix_stale_worktrees_multiple(self):
        """fix_stale_worktrees handles multiple worktrees."""
        findings = [
            Finding(
                probe="worktrees",
                category="stale_worktree",
                message="Stale worktree 1",
                severity="warning",
                fixable=True,
                file_path="/home/user/repo-42",
                line_number=None,
                fix_data={"worktree_path": "/home/user/repo-42", "branch": "feature/old"},
            ),
            Finding(
                probe="worktrees",
                category="stale_worktree",
                message="Stale worktree 2",
                severity="warning",
                fixable=True,
                file_path="/home/user/repo-99",
                line_number=None,
                fix_data={"worktree_path": "/home/user/repo-99", "branch": "feature/ancient"},
            ),
        ]

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            actions = fix_stale_worktrees(findings, "/home/user/repo", dry_run=False)

        assert len(actions) == 2
        assert mock_run.call_count == 2


class TestCommitMessage:
    """Test commit message generation. T140, T260."""

    def test_links_commit_message(self):
        """T140/T260: generate_commit_message produces expected template for links."""
        msg = generate_commit_message("broken_link", 3, ["README.md", "docs/guide.md"])
        assert msg == "chore: fix 3 broken markdown link(s) (ref #94)"

    def test_worktrees_commit_message(self):
        """generate_commit_message produces expected template for worktrees."""
        msg = generate_commit_message("stale_worktree", 1, ["/path/to/wt"])
        assert msg == "chore: prune 1 stale worktree(s) (ref #94)"

    def test_single_link_commit_message(self):
        """generate_commit_message works for single link fix."""
        msg = generate_commit_message("broken_link", 1, ["README.md"])
        assert msg == "chore: fix 1 broken markdown link(s) (ref #94)"

    def test_unknown_category_fallback(self):
        """generate_commit_message uses fallback for unknown categories."""
        msg = generate_commit_message("unknown_thing", 2, [])
        assert "janitor fix" in msg
        assert "2" in msg

    def test_commit_message_deterministic(self):
        """generate_commit_message is deterministic (same input -> same output)."""
        msg1 = generate_commit_message("broken_link", 5, ["a.md", "b.md"])
        msg2 = generate_commit_message("broken_link", 5, ["a.md", "b.md"])
        assert msg1 == msg2

    def test_commit_message_includes_ref(self):
        """generate_commit_message always includes issue reference."""
        msg = generate_commit_message("broken_link", 1, [])
        assert "ref #94" in msg

        msg2 = generate_commit_message("stale_worktree", 1, [])
        assert "ref #94" in msg2

        msg3 = generate_commit_message("custom_category", 1, [])
        assert "ref #94" in msg3


class TestCreateFixCommit:
    """Test git commit creation."""

    def test_create_fix_commit_stages_and_commits(self):
        """create_fix_commit calls git add and git commit."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            create_fix_commit("/repo", "broken_link", ["README.md"], "chore: fix links")

        assert mock_run.call_count == 2
        mock_run.assert_any_call(
            ["git", "add", "README.md"], cwd="/repo", check=True
        )

    def test_create_fix_commit_empty_files_noop(self):
        """create_fix_commit does nothing with empty files list."""
        with patch("subprocess.run") as mock_run:
            create_fix_commit("/repo", "broken_link", [], "chore: fix links")
        mock_run.assert_not_called()

    def test_create_fix_commit_multiple_files(self):
        """create_fix_commit stages multiple files in single git add."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            create_fix_commit(
                "/repo", "broken_link",
                ["README.md", "docs/guide.md"],
                "chore: fix links"
            )

        add_call = mock_run.call_args_list[0]
        assert add_call == call(
            ["git", "add", "README.md", "docs/guide.md"], cwd="/repo", check=True
        )

    def test_create_fix_commit_message_passed(self):
        """create_fix_commit passes correct commit message."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            create_fix_commit("/repo", "broken_link", ["README.md"], "chore: fix 1 broken markdown link(s) (ref #94)")

        commit_call = mock_run.call_args_list[1]
        assert commit_call == call(
            ["git", "commit", "-m", "chore: fix 1 broken markdown link(s) (ref #94)"],
            cwd="/repo",
            capture_output=True,
            text=True,
        )

# From C:\Users\mcwiz\Projects\AssemblyZero\tests\unit\test_janitor\test_reporter.py
"""Tests for janitor reporters.

Issue #94: Lu-Tze: The Janitor
Test IDs: T150-T180, T270-T300, T360-T380
"""

import json
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.workflows.janitor.reporter import (
    GitHubReporter,
    LocalFileReporter,
    build_report_body,
    get_reporter,
)
from assemblyzero.workflows.janitor.state import (
    Finding,
    FixAction,
    ProbeResult,
)


class TestLocalFileReporter:
    """Test LocalFileReporter. T150-T170, T270-T290, T380."""

    def test_create_report(self, tmp_path):
        """T150/T270/T380: create_report writes markdown file to janitor-reports/."""
        reporter = LocalFileReporter(str(tmp_path))
        result = reporter.create_report(
            "Janitor Report", "# Test Report\nContent here", "warning"
        )

        assert result.startswith(str(tmp_path / "janitor-reports"))
        assert result.endswith(".md")
        assert Path(result).exists()
        assert "# Test Report" in Path(result).read_text()

    def test_update_report(self, tmp_path):
        """T160/T280: update_report overwrites existing file."""
        reporter = LocalFileReporter(str(tmp_path))
        path = reporter.create_report("Janitor Report", "# Original", "info")

        updated_path = reporter.update_report(path, "# Updated", "warning")

        assert updated_path == path
        assert Path(path).read_text() == "# Updated"

    def test_find_existing_report_today(self, tmp_path):
        """T170/T290: find_existing_report returns path for today's report."""
        reporter = LocalFileReporter(str(tmp_path))
        created_path = reporter.create_report("Janitor Report", "# Test", "info")

        found = reporter.find_existing_report()

        assert found is not None
        assert found == created_path

    def test_find_existing_report_none(self, tmp_path):
        """find_existing_report returns None when no report exists."""
        reporter = LocalFileReporter(str(tmp_path))
        assert reporter.find_existing_report() is None

    def test_creates_janitor_reports_dir(self, tmp_path):
        """LocalFileReporter creates janitor-reports/ directory on init."""
        reporter = LocalFileReporter(str(tmp_path))
        assert (tmp_path / "janitor-reports").is_dir()

    def test_create_report_filename_format(self, tmp_path):
        """create_report uses correct filename format with timestamp."""
        reporter = LocalFileReporter(str(tmp_path))
        result = reporter.create_report("Janitor Report", "# Test", "info")

        filename = Path(result).name
        assert filename.startswith("janitor-report-")
        assert filename.endswith(".md")
        # Should contain date in YYYY-MM-DD format
        today = datetime.now().strftime("%Y-%m-%d")
        assert today in filename

    def test_create_report_preserves_body_content(self, tmp_path):
        """create_report writes the exact body content provided."""
        reporter = LocalFileReporter(str(tmp_path))
        body = "# Janitor Report\n\n## Summary\n\nSome content here.\n"
        result = reporter.create_report("Janitor Report", body, "critical")

        assert Path(result).read_text() == body

    def test_update_report_preserves_path(self, tmp_path):
        """update_report returns the same path it was given."""
        reporter = LocalFileReporter(str(tmp_path))
        path = reporter.create_report("Janitor Report", "# Original", "info")

        result = reporter.update_report(path, "# New Content", "warning")
        assert result == path

    def test_find_existing_report_returns_first_sorted(self, tmp_path):
        """find_existing_report returns the first report alphabetically for today."""
        reporter = LocalFileReporter(str(tmp_path))
        # Create two reports - they'll have slightly different timestamps
        path1 = reporter.create_report("Report 1", "# First", "info")
        # Manually create a second report with a later timestamp
        today = datetime.now().strftime("%Y-%m-%d")
        report_dir = tmp_path / "janitor-reports"
        second = report_dir / f"janitor-report-{today}-235959.md"
        second.write_text("# Second")

        found = reporter.find_existing_report()
        assert found is not None
        # Should return the first one sorted
        assert found == path1


class TestGitHubReporter:
    """Test GitHubReporter. T360, T370."""

    def test_init_with_gh_auth(self):
        """GitHubReporter initializes successfully with gh auth."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            reporter = GitHubReporter("/repo")
        assert reporter.repo_root == "/repo"

    def test_init_with_github_token(self):
        """T360: GitHubReporter falls back to GITHUB_TOKEN."""
        with patch("subprocess.run") as mock_run, patch.dict(
            os.environ, {"GITHUB_TOKEN": "ghp_test123"}
        ):
            mock_run.return_value = MagicMock(returncode=1)
            reporter = GitHubReporter("/repo")
        assert reporter.repo_root == "/repo"

    def test_init_no_auth_raises(self):
        """GitHubReporter raises RuntimeError without auth."""
        with patch("subprocess.run") as mock_run, patch.dict(
            os.environ, {}, clear=True
        ):
            # Remove GITHUB_TOKEN if set
            os.environ.pop("GITHUB_TOKEN", None)
            mock_run.return_value = MagicMock(returncode=1)
            with pytest.raises(RuntimeError, match="gh CLI not authenticated"):
                GitHubReporter("/repo")

    def test_find_existing_report(self):
        """T370: find_existing_report returns existing issue URL."""
        with patch("subprocess.run") as mock_run:
            # First call: gh auth status (success)
            # Second call: gh issue list (returns issue)
            mock_run.side_effect = [
                MagicMock(returncode=0),  # auth
                MagicMock(
                    returncode=0,
                    stdout=json.dumps(
                        [{"url": "https://github.com/user/repo/issues/42"}]
                    ),
                ),
            ]
            reporter = GitHubReporter("/repo")
            result = reporter.find_existing_report()

        assert result == "https://github.com/user/repo/issues/42"

    def test_find_existing_report_none(self):
        """find_existing_report returns None when no matching issue."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0),  # auth
                MagicMock(returncode=0, stdout="[]"),  # no issues
            ]
            reporter = GitHubReporter("/repo")
            result = reporter.find_existing_report()

        assert result is None

    def test_create_report(self):
        """create_report calls gh issue create."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0),  # auth
                MagicMock(
                    returncode=0,
                    stdout="https://github.com/user/repo/issues/43\n",
                ),
            ]
            reporter = GitHubReporter("/repo")
            url = reporter.create_report("Janitor Report", "# Body", "warning")

        assert url == "https://github.com/user/repo/issues/43"

    def test_create_report_failure_raises(self):
        """create_report raises RuntimeError on gh CLI failure."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0),  # auth
                MagicMock(returncode=1, stderr="Permission denied"),  # create fails
            ]
            reporter = GitHubReporter("/repo")
            with pytest.raises(RuntimeError, match="Failed to create GitHub issue"):
                reporter.create_report("Janitor Report", "# Body", "warning")

    def test_update_report(self):
        """update_report calls gh issue edit."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0),  # auth
                MagicMock(returncode=0),  # edit
            ]
            reporter = GitHubReporter("/repo")
            url = reporter.update_report(
                "https://github.com/user/repo/issues/42", "# Updated", "warning"
            )

        assert url == "https://github.com/user/repo/issues/42"
        # Verify gh issue edit was called with correct issue number
        edit_call = mock_run.call_args_list[1]
        assert "42" in edit_call.args[0]

    def test_update_report_failure_raises(self):
        """update_report raises RuntimeError on gh CLI failure."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0),  # auth
                MagicMock(returncode=1, stderr="Not found"),  # edit fails
            ]
            reporter = GitHubReporter("/repo")
            with pytest.raises(RuntimeError, match="Failed to update GitHub issue"):
                reporter.update_report(
                    "https://github.com/user/repo/issues/42", "# Updated", "warning"
                )

    def test_find_existing_report_gh_failure(self):
        """find_existing_report returns None when gh CLI fails."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0),  # auth
                MagicMock(returncode=1, stdout=""),  # list fails
            ]
            reporter = GitHubReporter("/repo")
            result = reporter.find_existing_report()

        assert result is None

    def test_find_existing_report_invalid_json(self):
        """find_existing_report returns None on invalid JSON response."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0),  # auth
                MagicMock(returncode=0, stdout="not valid json"),  # bad json
            ]
            reporter = GitHubReporter("/repo")
            result = reporter.find_existing_report()

        assert result is None

    def test_update_report_extracts_issue_number_from_url(self):
        """update_report correctly extracts issue number from various URL formats."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0),  # auth
                MagicMock(returncode=0),  # edit
            ]
            reporter = GitHubReporter("/repo")
            reporter.update_report(
                "https://github.com/martymcenroe/AssemblyZero/issues/99",
                "# Body",
                "info",
            )

        edit_call = mock_run.call_args_list[1]
        assert "99" in edit_call.args[0]

    def test_create_report_includes_maintenance_label(self):
        """create_report passes --label maintenance to gh issue create."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0),  # auth
                MagicMock(returncode=0, stdout="https://github.com/user/repo/issues/1\n"),
            ]
            reporter = GitHubReporter("/repo")
            reporter.create_report("Janitor Report", "# Body", "warning")

        create_call = mock_run.call_args_list[1]
        cmd = create_call.args[0]
        assert "--label" in cmd
        label_idx = cmd.index("--label")
        assert cmd[label_idx + 1] == "maintenance"


class TestBuildReportBody:
    """Test report body generation. T180, T300."""

    def test_build_report_body_all_sections(self):
        """T180/T300: build_report_body produces markdown with all sections."""
        unfixable = [
            Finding(
                probe="todo",
                category="stale_todo",
                message="Stale TODO in helper.py:42",
                severity="info",
                fixable=False,
                file_path="tools/helper.py",
                line_number=42,
            )
        ]
        fix_actions = [
            FixAction(
                category="broken_link",
                description="Fixed link in README.md",
                files_modified=["README.md"],
                commit_message="chore: fix 1 broken markdown link(s) (ref #94)",
                applied=True,
            )
        ]
        probe_results = [
            ProbeResult(probe="links", status="findings", findings=[]),
            ProbeResult(probe="harvest", status="error", error_message="Script not found"),
        ]

        body = build_report_body(unfixable, fix_actions, probe_results)

        assert "# Janitor Report" in body
        assert "## Summary" in body
        assert "## Auto-Fixed Issues" in body
        assert "Fixed link in README.md" in body
        assert "## Requires Human Attention" in body
        assert "stale_todo" in body
        assert "## Probe Errors" in body
        assert "harvest" in body
        assert "Script not found" in body

    def test_build_report_body_no_unfixable(self):
        """build_report_body handles empty unfixable findings."""
        body = build_report_body([], [], [])
        assert "No issues require human attention" in body
        assert "No auto-fixes applied" in body

    def test_build_report_body_severity_counts(self):
        """build_report_body counts severities correctly."""
        unfixable = [
            Finding(probe="links", category="c1", message="m1", severity="warning", fixable=False),
            Finding(probe="links", category="c2", message="m2", severity="critical", fixable=False),
            Finding(probe="links", category="c3", message="m3", severity="info", fixable=False),
        ]
        body = build_report_body(unfixable, [], [])
        assert "| Critical | 1 |" in body
        assert "| Warning | 1 |" in body
        assert "| Info | 1 |" in body

    def test_build_report_body_no_probe_errors(self):
        """build_report_body omits Probe Errors section when no errors."""
        unfixable = [
            Finding(probe="todo", category="stale_todo", message="m", severity="info", fixable=False),
        ]
        probe_results = [
            ProbeResult(probe="todo", status="findings", findings=[]),
            ProbeResult(probe="links", status="ok", findings=[]),
        ]
        body = build_report_body(unfixable, [], probe_results)
        assert "## Probe Errors" not in body

    def test_build_report_body_fix_actions_with_checkmarks(self):
        """build_report_body shows checkmark for applied fixes."""
        fix_actions = [
            FixAction(
                category="broken_link",
                description="Fixed link in README.md",
                files_modified=["README.md"],
                commit_message="chore: fix 1 broken markdown link(s) (ref #94)",
                applied=True,
            ),
            FixAction(
                category="broken_link",
                description="Would fix link in docs/guide.md",
                files_modified=["docs/guide.md"],
                commit_message="chore: fix 1 broken markdown link(s) (ref #94)",
                applied=False,
            ),
        ]
        body = build_report_body([], fix_actions, [])
        assert "[PASS]" in body
        assert "" in body

    def test_build_report_body_groups_by_category(self):
        """build_report_body groups unfixable findings by category."""
        unfixable = [
            Finding(probe="todo", category="stale_todo", message="TODO 1", severity="info", fixable=False, file_path="a.py", line_number=1),
            Finding(probe="harvest", category="cross_project_drift", message="DRIFT 1", severity="warning", fixable=False),
            Finding(probe="todo", category="stale_todo", message="TODO 2", severity="info", fixable=False, file_path="b.py", line_number=2),
        ]
        body = build_report_body(unfixable, [], [])
        assert "### stale_todo" in body
        assert "### cross_project_drift" in body
        assert "TODO 1" in body
        assert "TODO 2" in body
        assert "DRIFT 1" in body

    def test_build_report_body_finding_with_location(self):
        """build_report_body includes file path and line number in findings."""
        unfixable = [
            Finding(
                probe="todo",
                category="stale_todo",
                message="Stale TODO",
                severity="info",
                fixable=False,
                file_path="tools/helper.py",
                line_number=42,
            )
        ]
        body = build_report_body(unfixable, [], [])
        assert "tools/helper.py:42" in body

    def test_build_report_body_finding_without_line_number(self):
        """build_report_body handles findings with file_path but no line_number."""
        unfixable = [
            Finding(
                probe="harvest",
                category="cross_project_drift",
                message="DRIFT: something",
                severity="warning",
                fixable=False,
                file_path="pyproject.toml",
                line_number=None,
            )
        ]
        body = build_report_body(unfixable, [], [])
        assert "(pyproject.toml)" in body

    def test_build_report_body_multiple_probe_errors(self):
        """build_report_body lists all probe errors."""
        probe_results = [
            ProbeResult(probe="links", status="error", error_message="File not found"),
            ProbeResult(probe="harvest", status="error", error_message="Script crashed"),
            ProbeResult(probe="todo", status="ok", findings=[]),
        ]
        body = build_report_body([], [], probe_results)
        assert "## Probe Errors" in body
        assert "links" in body
        assert "File not found" in body
        assert "harvest" in body
        assert "Script crashed" in body


class TestGetReporter:
    """Test reporter factory."""

    def test_get_reporter_local(self, tmp_path):
        """get_reporter returns LocalFileReporter for 'local'."""
        reporter = get_reporter("local", str(tmp_path))
        assert isinstance(reporter, LocalFileReporter)

    def test_get_reporter_github(self):
        """get_reporter returns GitHubReporter for 'github'."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            reporter = get_reporter("github", "/repo")
        assert isinstance(reporter, GitHubReporter)

# From C:\Users\mcwiz\Projects\AssemblyZero\tests\unit\test_janitor\test_graph.py
"""Tests for janitor graph construction and routing.

Issue #94: Lu-Tze: The Janitor
Test IDs: T190-T230, T310-T350
"""

from unittest.mock import MagicMock, patch

from assemblyzero.workflows.janitor.graph import (
    build_janitor_graph,
    route_after_fix,
    route_after_sweep,
)
from assemblyzero.workflows.janitor.state import (
    Finding,
    JanitorState,
)


class TestRouteAfterSweep:
    """Test conditional routing after sweep. T190-T210, T310-T330."""

    def test_no_findings_returns_end(self):
        """T190/T310: route_after_sweep returns __end__ when no findings."""
        state = {"all_findings": [], "auto_fix": True}
        assert route_after_sweep(state) == "__end__"

    def test_fixable_auto_fix_returns_fixer(self):
        """T200/T320: route_after_sweep returns n1_fixer with fixable findings + auto_fix."""
        state = {
            "all_findings": [
                Finding(probe="links", category="broken_link", message="m", severity="warning", fixable=True)
            ],
            "auto_fix": True,
        }
        assert route_after_sweep(state) == "n1_fixer"

    def test_fixable_no_auto_fix_returns_reporter(self):
        """route_after_sweep returns n2_reporter when fixable but auto_fix=False."""
        state = {
            "all_findings": [
                Finding(probe="links", category="broken_link", message="m", severity="warning", fixable=True)
            ],
            "auto_fix": False,
        }
        assert route_after_sweep(state) == "n2_reporter"

    def test_unfixable_only_returns_reporter(self):
        """T210/T330: route_after_sweep returns n2_reporter with only unfixable."""
        state = {
            "all_findings": [
                Finding(probe="todo", category="stale_todo", message="m", severity="info", fixable=False)
            ],
            "auto_fix": True,
        }
        assert route_after_sweep(state) == "n2_reporter"

    def test_mixed_fixable_and_unfixable_returns_fixer(self):
        """route_after_sweep returns n1_fixer when mixed findings + auto_fix."""
        state = {
            "all_findings": [
                Finding(probe="links", category="broken_link", message="m", severity="warning", fixable=True),
                Finding(probe="todo", category="stale_todo", message="m", severity="info", fixable=False),
            ],
            "auto_fix": True,
        }
        assert route_after_sweep(state) == "n1_fixer"


class TestRouteAfterFix:
    """Test conditional routing after fix. T220, T230, T340, T350."""

    def test_all_fixed_returns_end(self):
        """T220/T340: route_after_fix returns __end__ when unfixable list empty."""
        state = {"unfixable_findings": []}
        assert route_after_fix(state) == "__end__"

    def test_unfixable_remain_returns_reporter(self):
        """T230/T350: route_after_fix returns n2_reporter when unfixable exist."""
        state = {
            "unfixable_findings": [
                Finding(probe="todo", category="stale_todo", message="m", severity="info", fixable=False)
            ]
        }
        assert route_after_fix(state) == "n2_reporter"


class TestBuildJanitorGraph:
    """Test graph construction."""

    def test_build_janitor_graph_compiles(self):
        """build_janitor_graph returns a compiled graph."""
        graph = build_janitor_graph()
        # Compiled graph should be callable (has invoke method)
        assert hasattr(graph, "invoke")

    def test_graph_with_no_findings(self):
        """Graph exits cleanly with no findings (all probes return ok)."""
        with patch(
            "assemblyzero.workflows.janitor.graph.get_probes",
            return_value=[],
        ):
            graph = build_janitor_graph()
            initial_state: JanitorState = {
                "repo_root": "/fake/repo",
                "scope": [],
                "auto_fix": True,
                "dry_run": False,
                "silent": True,
                "create_pr": False,
                "reporter_type": "local",
                "probe_results": [],
                "all_findings": [],
                "fix_actions": [],
                "unfixable_findings": [],
                "report_url": None,
                "exit_code": 0,
            }
            final_state = graph.invoke(initial_state)

        assert final_state["all_findings"] == []
        assert final_state["exit_code"] == 0

# From C:\Users\mcwiz\Projects\AssemblyZero\tests\unit\test_janitor\test_cli.py
"""Tests for janitor CLI argument parsing.

Issue #94: Lu-Tze: The Janitor
Test IDs: T240-T260, T360-T380
"""

import io
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

from tools.run_janitor_workflow import (
    build_initial_state,
    main,
    parse_args,
)


class TestParseArgs:
    """Test CLI argument parsing. T240, T250, T260, T360, T370."""

    def test_defaults(self):
        """T240/T360: parse_args with no args returns correct defaults."""
        args = parse_args([])
        assert args.scope == "all"
        assert args.auto_fix is True
        assert args.dry_run is False
        assert args.silent is False
        assert args.create_pr is False
        assert args.reporter == "github"

    def test_all_flags(self):
        """T250/T370: parse_args handles all flag combinations."""
        args = parse_args([
            "--scope", "links",
            "--dry-run",
            "--silent",
            "--create-pr",
            "--reporter", "local",
        ])
        assert args.scope == "links"
        assert args.dry_run is True
        assert args.silent is True
        assert args.create_pr is True
        assert args.reporter == "local"

    def test_invalid_scope(self):
        """T260/T380: parse_args with invalid scope raises SystemExit."""
        with pytest.raises(SystemExit):
            parse_args(["--scope", "invalid"])

    def test_scope_worktrees(self):
        """parse_args accepts worktrees scope."""
        args = parse_args(["--scope", "worktrees"])
        assert args.scope == "worktrees"

    def test_scope_harvest(self):
        """parse_args accepts harvest scope."""
        args = parse_args(["--scope", "harvest"])
        assert args.scope == "harvest"

    def test_scope_todo(self):
        """parse_args accepts todo scope."""
        args = parse_args(["--scope", "todo"])
        assert args.scope == "todo"

    def test_reporter_local(self):
        """parse_args accepts local reporter."""
        args = parse_args(["--reporter", "local"])
        assert args.reporter == "local"

    def test_auto_fix_false(self):
        """parse_args handles --auto-fix false."""
        args = parse_args(["--auto-fix", "false"])
        assert args.auto_fix is False


class TestBuildInitialState:
    """Test state construction from CLI args. T010, T390."""

    def test_build_initial_state_scope_all(self):
        """T010/T390: build_initial_state converts 'all' scope to full list."""
        args = parse_args(["--reporter", "local"])

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="/home/user/repo\n"
            )
            state = build_initial_state(args)

        assert state["scope"] == ["links", "worktrees", "harvest", "todo"]
        assert state["repo_root"] == "/home/user/repo"
        assert state["reporter_type"] == "local"
        assert state["probe_results"] == []
        assert state["exit_code"] == 0

    def test_build_initial_state_single_scope(self):
        """build_initial_state converts single scope correctly."""
        args = parse_args(["--scope", "links", "--dry-run"])

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="/repo\n"
            )
            state = build_initial_state(args)

        assert state["scope"] == ["links"]
        assert state["dry_run"] is True


class TestMainEntryPoint:
    """Test main() entry point. T270-T350."""

    def test_exit_code_2_not_git_repo(self):
        """T350: main() returns 2 when not in a git repo."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=128, stdout="", stderr="not a git repo")
            code = main(["--silent"])
        assert code == 2

    def test_exit_code_0_clean_run(self):
        """T270: main() returns 0 when no findings."""
        with patch("subprocess.run") as mock_git, patch(
            "tools.run_janitor_workflow.build_janitor_graph"
        ) as mock_graph:
            mock_git.return_value = MagicMock(returncode=0, stdout="/repo\n")
            mock_compiled = MagicMock()
            mock_compiled.invoke.return_value = {
                "repo_root": "/repo",
                "scope": [],
                "auto_fix": True,
                "dry_run": False,
                "silent": True,
                "create_pr": False,
                "reporter_type": "local",
                "probe_results": [],
                "all_findings": [],
                "fix_actions": [],
                "unfixable_findings": [],
                "report_url": None,
                "exit_code": 0,
            }
            mock_graph.return_value = mock_compiled
            code = main(["--silent", "--reporter", "local"])
        assert code == 0

    def test_exit_code_1_unfixable(self):
        """T280: main() returns 1 when unfixable findings remain."""
        with patch("subprocess.run") as mock_git, patch(
            "tools.run_janitor_workflow.build_janitor_graph"
        ) as mock_graph:
            mock_git.return_value = MagicMock(returncode=0, stdout="/repo\n")
            mock_compiled = MagicMock()
            mock_compiled.invoke.return_value = {
                "exit_code": 1,
                "all_findings": [],
                "fix_actions": [],
                "unfixable_findings": [],
                "report_url": None,
            }
            mock_graph.return_value = mock_compiled
            code = main(["--silent", "--reporter", "local"])
        assert code == 1

    def test_silent_no_stdout(self, capsys):
        """T340: main with --silent produces no stdout on clean run."""
        with patch("subprocess.run") as mock_git, patch(
            "tools.run_janitor_workflow.build_janitor_graph"
        ) as mock_graph:
            mock_git.return_value = MagicMock(returncode=0, stdout="/repo\n")
            mock_compiled = MagicMock()
            mock_compiled.invoke.return_value = {
                "exit_code": 0,
                "all_findings": [],
                "fix_actions": [],
                "unfixable_findings": [],
                "report_url": None,
            }
            mock_graph.return_value = mock_compiled
            code = main(["--silent", "--reporter", "local"])

        captured = capsys.readouterr()
        assert captured.out == ""
        assert code == 0

    def test_fatal_exception_returns_2(self):
        """main() returns 2 on unhandled exception."""
        with patch("subprocess.run") as mock_git, patch(
            "tools.run_janitor_workflow.build_janitor_graph"
        ) as mock_graph:
            mock_git.return_value = MagicMock(returncode=0, stdout="/repo\n")
            mock_graph.side_effect = RuntimeError("Graph build failed")
            code = main(["--silent", "--reporter", "local"])
        assert code == 2

# From C:\Users\mcwiz\Projects\AssemblyZero\tests\integration\test_janitor_workflow.py
"""Integration test for full janitor workflow using LocalFileReporter.

Issue #94: Lu-Tze: The Janitor
Test IDs: T290, T300, T310, T320, T330, T400
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.workflows.janitor.graph import build_janitor_graph
from assemblyzero.workflows.janitor.state import (
    Finding,
    JanitorState,
    ProbeResult,
)


def _make_initial_state(tmp_path: Path, **overrides) -> JanitorState:
    """Helper to build a test JanitorState."""
    defaults: JanitorState = {
        "repo_root": str(tmp_path),
        "scope": ["links"],
        "auto_fix": True,
        "dry_run": False,
        "silent": True,
        "create_pr": False,
        "reporter_type": "local",
        "probe_results": [],
        "all_findings": [],
        "fix_actions": [],
        "unfixable_findings": [],
        "report_url": None,
        "exit_code": 0,
    }
    defaults.update(overrides)
    return defaults


class TestFullWorkflowIntegration:
    """Integration tests for complete janitor workflow. T290, T400."""

    def test_clean_run_exits_zero(self, tmp_path):
        """T290/T400: Full workflow with no findings exits cleanly."""
        mock_probe = MagicMock(return_value=ProbeResult(probe="links", status="ok"))

        with patch(
            "assemblyzero.workflows.janitor.graph.get_probes",
            return_value=[("links", mock_probe)],
        ):
            graph = build_janitor_graph()
            state = _make_initial_state(tmp_path)
            final = graph.invoke(state)

        assert final["exit_code"] == 0
        assert final["all_findings"] == []

    def test_unfixable_findings_create_local_report(self, tmp_path):
        """Integration: unfixable findings create local report file."""
        unfixable_finding = Finding(
            probe="todo",
            category="stale_todo",
            message="Stale TODO in helper.py:42",
            severity="info",
            fixable=False,
            file_path="tools/helper.py",
            line_number=42,
        )
        mock_probe = MagicMock(
            return_value=ProbeResult(
                probe="todo", status="findings", findings=[unfixable_finding]
            )
        )

        with patch(
            "assemblyzero.workflows.janitor.graph.get_probes",
            return_value=[("todo", mock_probe)],
        ):
            graph = build_janitor_graph()
            state = _make_initial_state(tmp_path, scope=["todo"])
            final = graph.invoke(state)

        assert final["exit_code"] == 1
        assert final["report_url"] is not None
        assert Path(final["report_url"]).exists()
        report_content = Path(final["report_url"]).read_text()
        assert "Janitor Report" in report_content
        assert "stale_todo" in report_content

    def test_fixable_findings_auto_fixed(self, tmp_path):
        """T320: Broken link auto-fixed with unique target."""
        # Create mock repo
        readme = tmp_path / "README.md"
        readme.write_text("[guide](./docs/old-guide.md)\n")
        docs = tmp_path / "docs"
        docs.mkdir()
        guide = docs / "guide.md"
        guide.write_text("# Guide\n")

        fixable_finding = Finding(
            probe="links",
            category="broken_link",
            message="Broken link",
            severity="warning",
            fixable=True,
            file_path="README.md",
            line_number=1,
            fix_data={"old_link": "./docs/old-guide.md", "new_link": "./docs/guide.md"},
        )
        mock_probe = MagicMock(
            return_value=ProbeResult(
                probe="links", status="findings", findings=[fixable_finding]
            )
        )

        with patch(
            "assemblyzero.workflows.janitor.graph.get_probes",
            return_value=[("links", mock_probe)],
        ), patch(
            "assemblyzero.workflows.janitor.fixers.create_fix_commit"
        ):
            graph = build_janitor_graph()
            state = _make_initial_state(tmp_path)
            final = graph.invoke(state)

        assert final["exit_code"] == 0
        assert len(final["fix_actions"]) > 0
        assert final["fix_actions"][0].applied is True
        # Verify file was actually modified
        assert "./docs/guide.md" in readme.read_text()

    def test_dry_run_no_modifications(self, tmp_path):
        """T310: Dry-run prevents file modification."""
        readme = tmp_path / "README.md"
        original = "[guide](./docs/old-guide.md)\n"
        readme.write_text(original)

        fixable_finding = Finding(
            probe="links",
            category="broken_link",
            message="Broken link",
            severity="warning",
            fixable=True,
            file_path="README.md",
            line_number=1,
            fix_data={"old_link": "./docs/old-guide.md", "new_link": "./docs/guide.md"},
        )
        mock_probe = MagicMock(
            return_value=ProbeResult(
                probe="links", status="findings", findings=[fixable_finding]
            )
        )

        with patch(
            "assemblyzero.workflows.janitor.graph.get_probes",
            return_value=[("links", mock_probe)],
        ):
            graph = build_janitor_graph()
            state = _make_initial_state(tmp_path, dry_run=True)
            final = graph.invoke(state)

        # File should not be modified in dry-run
        assert readme.read_text() == original
        assert len(final["fix_actions"]) > 0
        assert final["fix_actions"][0].applied is False

    def test_mixed_findings_fix_then_report(self, tmp_path):
        """T330: Mixed fixable/unfixable -> fix, then report unfixable."""
        readme = tmp_path / "README.md"
        readme.write_text("[guide](./docs/old-guide.md)\n")
        docs = tmp_path / "docs"
        docs.mkdir()
        guide = docs / "guide.md"
        guide.write_text("# Guide\n")

        fixable = Finding(
            probe="links", category="broken_link", message="Broken",
            severity="warning", fixable=True, file_path="README.md",
            line_number=1,
            fix_data={"old_link": "./docs/old-guide.md", "new_link": "./docs/guide.md"},
        )
        unfixable = Finding(
            probe="todo", category="stale_todo", message="Old TODO",
            severity="info", fixable=False, file_path="helper.py", line_number=10,
        )
        mock_probe = MagicMock(
            return_value=ProbeResult(
                probe="links", status="findings", findings=[fixable, unfixable]
            )
        )

        with patch(
            "assemblyzero.workflows.janitor.graph.get_probes",
            return_value=[("links", mock_probe)],
        ), patch(
            "assemblyzero.workflows.janitor.fixers.create_fix_commit"
        ):
            graph = build_janitor_graph()
            state = _make_initial_state(tmp_path)
            final = graph.invoke(state)

        assert final["exit_code"] == 1  # Unfixable remain
        assert len(final["fix_actions"]) > 0
        assert len(final["unfixable_findings"]) == 1
        assert final["report_url"] is not None


```

## Previously Implemented Files

These files have already been implemented. Use them for imports and references:

### assemblyzero/workflows/janitor/__init__.py (signatures)

```python
"""Janitor workflow: Automated repository hygiene.

Issue #94: Lu-Tze: The Janitor
"""

from assemblyzero.workflows.janitor.graph import build_janitor_graph

__all__ = ["build_janitor_graph"]
```

### assemblyzero/workflows/janitor/state.py (signatures)

```python
"""State definitions for the Janitor workflow.

Issue #94: Lu-Tze: The Janitor
"""

from __future__ import annotations

from dataclasses import dataclass, field

from typing import Literal, TypedDict

class Finding:

    """A single issue discovered by a probe."""

class ProbeResult:

    """Structured result from a single probe execution."""

class FixAction:

    """Record of a fix that was applied (or would be applied in dry-run)."""

class JanitorState(TypedDict):

    """LangGraph state for the janitor workflow."""

Severity = Literal["info", "warning", "critical"]

ProbeScope = Literal["links", "worktrees", "harvest", "todo"]
```

### assemblyzero/workflows/janitor/probes/__init__.py (signatures)

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

### assemblyzero/workflows/janitor/probes/links.py (signatures)

```python
"""Broken internal markdown link detection probe.

Issue #94: Lu-Tze: The Janitor
"""

from __future__ import annotations

import os

import re

import subprocess

from pathlib import Path

from assemblyzero.workflows.janitor.state import Finding, ProbeResult

def probe_links(repo_root: str) -> ProbeResult:
    """Scan all markdown files for broken internal links.

Checks relative file links, anchor links, and image references."""
    ...

def find_markdown_files(repo_root: str) -> list[str]:
    """Find all .md files in repo, respecting .gitignore patterns.

Uses git ls-files to only return tracked files."""
    ...

def extract_internal_links(file_path: str) -> list[tuple[int, str, str]]:
    """Extract internal links from a markdown file.

Returns list of (line_number, link_text, link_target) tuples."""
    ...

def resolve_link(source_file: str, link_target: str, repo_root: str) -> bool:
    """Check if a relative link target resolves to an existing file.

Strips anchor fragments before checking."""
    ...

def find_likely_target(broken_target: str, repo_root: str) -> str | None:
    """Attempt to find the intended target of a broken link.

Searches for files with the same basename in the repository."""
    ...

_LINK_PATTERN = re.compile(r"!?\[([^\]]*)\]\(([^)]+)\)")
```

### assemblyzero/workflows/janitor/probes/worktrees.py (signatures)

```python
"""Stale and detached git worktree detection probe.

Issue #94: Lu-Tze: The Janitor
"""

from __future__ import annotations

import subprocess

from datetime import datetime, timedelta, timezone

from assemblyzero.workflows.janitor.state import Finding, ProbeResult

def probe_worktrees(repo_root: str) -> ProbeResult:
    """Detect stale and detached git worktrees.

A worktree is considered stale if:"""
    ...

def list_worktrees(repo_root: str) -> list[dict]:
    """Parse output of `git worktree list --porcelain`.

Returns list of dicts with keys: path, HEAD, branch, bare, detached."""
    ...

def get_branch_last_commit_date(
    repo_root: str, branch: str
) -> datetime | None:
    """Get the date of the most recent commit on a branch.

Returns None if the branch doesn't exist."""
    ...

def is_branch_merged(
    repo_root: str, branch: str, target: str = "main"
) -> bool:
    """Check if branch has been merged into target branch."""
    ...

STALE_DAYS_THRESHOLD = 14
```

### assemblyzero/workflows/janitor/probes/harvest.py (signatures)

```python
"""Cross-project drift detection via assemblyzero-harvest.py.

Issue #94: Lu-Tze: The Janitor
"""

from __future__ import annotations

import os

import subprocess

from assemblyzero.workflows.janitor.state import Finding, ProbeResult

def probe_harvest(repo_root: str) -> ProbeResult:
    """Run assemblyzero-harvest.py and parse output for cross-project drift.

Shells out to the harvest script and parses its stdout."""
    ...

def find_harvest_script(repo_root: str) -> str | None:
    """Locate the assemblyzero-harvest.py script.

Searches in repo_root and tools/ directory."""
    ...

def parse_harvest_output(output: str) -> list[Finding]:
    """Parse harvest script stdout into structured findings.

Looks for lines starting with 'DRIFT:' and creates findings for each."""
    ...
```

### assemblyzero/workflows/janitor/probes/todo.py (full)

```python
"""Stale TODO comment scanner.

Detects TODO/FIXME/HACK/XXX comments older than 30 days using git blame.

Issue #94: Lu-Tze: The Janitor
"""

from __future__ import annotations

import os
import re
import subprocess
from datetime import datetime, timedelta, timezone

from assemblyzero.workflows.janitor.state import Finding, ProbeResult

# TODOs older than this many days are flagged
STALE_TODO_DAYS = 30

# Pattern to detect TODO-like comments
_TODO_PATTERN = re.compile(r"#\s*(TODO|FIXME|HACK|XXX)\b.*", re.IGNORECASE)


def probe_todo(repo_root: str) -> ProbeResult:
    """Scan source files for TODO comments older than 30 days.

    Uses git blame to determine when each TODO line was added.
    Only scans tracked files (respects .gitignore).
    Findings are unfixable (require human decision).
    """
    source_files = find_source_files(repo_root)
    findings: list[Finding] = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=STALE_TODO_DAYS)

    for rel_path in source_files:
        abs_path = os.path.join(repo_root, rel_path)
        todos = extract_todos(abs_path)
        for line_number, comment_text in todos:
            line_date = get_line_date(repo_root, rel_path, line_number)
            if line_date is None:
                continue
            if line_date < cutoff:
                age_days = (datetime.now(timezone.utc) - line_date).days
                findings.append(
                    Finding(
                        probe="todo",
                        category="stale_todo",
                        message=(
                            f"Stale TODO in {rel_path} line {line_number} "
                            f"({age_days} days old): '{comment_text.strip()}'"
                        ),
                        severity="info",
                        fixable=False,
                        file_path=rel_path,
                        line_number=line_number,
                    )
                )

    if findings:
        return ProbeResult(probe="todo", status="findings", findings=findings)
    return ProbeResult(probe="todo", status="ok")


def find_source_files(repo_root: str) -> list[str]:
    """Find all tracked source files (*.py, *.md, *.ts, *.js).

    Uses `git ls-files` to respect .gitignore.
    """
    result = subprocess.run(
        ["git", "ls-files", "*.py", "*.md", "*.ts", "*.js"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [f for f in result.stdout.strip().splitlines() if f]


def extract_todos(file_path: str) -> list[tuple[int, str]]:
    """Extract TODO/FIXME/HACK/XXX comments from a file.

    Returns list of (line_number, comment_text) tuples.
    """
    results: list[tuple[int, str]] = []
    try:
        with open(file_path, encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                match = _TODO_PATTERN.search(line)
                if match:
                    results.append((line_num, match.group(0)))
    except OSError:
        pass
    return results


def get_line_date(
    repo_root: str, file_path: str, line_number: int
) -> datetime | None:
    """Use git blame to determine when a specific line was last modified.

    Returns None if file is not tracked or blame fails.
    """
    result = subprocess.run(
        [
            "git",
            "blame",
            "-L",
            f"{line_number},{line_number}",
            "--porcelain",
            file_path,
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None

    for line in result.stdout.splitlines():
        if line.startswith("author-time "):
            try:
                timestamp = int(line[len("author-time ") :])
                return datetime.fromtimestamp(timestamp, tz=timezone.utc)
            except (ValueError, OSError):
                return None

    return None
```

## Previous Attempt Failed — Fix These Specific Errors

The previous implementation failed these tests:

```
FAILED tests/unit/test_janitor/test_reporter.py::TestBuildReportBody::test_build_report_body_fix_actions_with_checkmarks
FAILED tests/integration/test_janitor_workflow.py::TestFullWorkflowIntegration::test_unfixable_findings_create_local_report
FAILED tests/integration/test_janitor_workflow.py::TestFullWorkflowIntegration::test_fixable_findings_auto_fixed
FAILED tests/integration/test_janitor_workflow.py::TestFullWorkflowIntegration::test_mixed_findings_fix_then_report
4 failed, 117 passed, 3 warnings in 0.78s
```

Read the error messages carefully and fix the root cause in your implementation.

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
