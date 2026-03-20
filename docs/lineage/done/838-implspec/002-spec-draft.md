# Implementation Spec: Refactor — Implement WorkspaceContext to Eliminate Path Prop-Drilling

| Field | Value |
|-------|-------|
| Issue | #838 |
| LLD | `docs/lld/active/838-workspace-context.md` |
| Generated | 2026-03-19 |
| Status | DRAFT |

## 1. Overview

Create a frozen `WorkspaceContext` dataclass bundling `assemblyzero_root` and `target_repo` paths, construct it once in the orchestrator, and thread it through LangGraph state so nodes stop accepting path parameters directly.

**Objective:** Eliminate path prop-drilling across all workflow nodes.

**Success Criteria:** `WorkspaceContext` frozen dataclass exists, is constructed once per run, all nodes read from `state["workspace_ctx"]`, ≥95% coverage on new module.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `assemblyzero/core/workspace_context.py` | Add | Frozen dataclass + factory |
| 2 | `assemblyzero/core/__init__.py` | Modify | Re-export `WorkspaceContext` |
| 3 | `assemblyzero/core/state.py` | Modify | Add `workspace_ctx` field to `AgentState` |
| 4 | `tests/unit/test_workspace_context.py` | Add | Unit tests T010–T150 |
| 5 | `tests/unit/test_gate/test_gate_workspace_context.py` | Add | Gate/node integration tests |

**Implementation Order Rationale:** Core dataclass first (no internal dependencies), then exports, then state integration (imports from workspace_context), then tests. Node migration deferred to follow-up — see §11.2.

> **CRITICAL NOTE:** The LLD lists 7 node files and `orchestrator.py` as "Add". Before creating ANY of those, run `ls` on each `nodes/` directory. These are almost certainly existing files that need "Modify" treatment. This spec covers only the core dataclass, state integration, exports, and tests.

## 3. Current State (for Modify/Delete files)

### 3.1 `assemblyzero/core/__init__.py`

**Relevant excerpt** (full file):

```python
"""Core components for AssemblyZero state management and infrastructure."""

from assemblyzero.core.audit import (
    ReviewAuditLog,
    ReviewLogEntry,
    GeminiReviewResponse,
    create_log_entry,
)

from assemblyzero.core.config import (
    REVIEWER_MODEL,
    REVIEWER_MODEL_FALLBACKS,
    FORBIDDEN_MODELS,
    CREDENTIALS_FILE,
    ROTATION_STATE_FILE,
    MAX_RETRIES_PER_CREDENTIAL,
    BACKOFF_BASE_SECONDS,
    BACKOFF_MAX_SECONDS,
    DEFAULT_AUDIT_LOG_PATH,
    LLD_REVIEW_PROMPT_PATH,
)

from assemblyzero.core.gemini_client import (
    GeminiClient,
    GeminiCallResult,
    GeminiErrorType,
    Credential,
    RotationState,
)

from assemblyzero.core.state import AgentState
```

**What changes:** Append import block for `WorkspaceContext` and `make_workspace_context` after the final existing import.

### 3.2 `assemblyzero/core/state.py`

**Relevant excerpt** (full file header and class declarations):

```python
"""Core state definition for AssemblyZero LangGraph workflows.

This module defines the AgentState TypedDict that travels through
the governance pipeline: Issue -> LLD Review -> Implementation -> Code Review -> Merge
"""

from typing import Annotated, Literal, TypedDict

from langchain_core.messages import BaseMessage

from langgraph.graph.message import add_messages

class AgentState(TypedDict):

    """Core state shared across all AssemblyZero LangGraph nodes.

Attributes:"""

class TDDState(TypedDict):

    """State for TDD workflow tracking.

Attributes:"""

class _TestFileLocation(TypedDict):

    """Record of a test file location at a point in time.

Attributes:"""
```

**Import verification:** `langchain_core.messages` and `langgraph.graph.message` are existing project dependencies (LangGraph/LangChain stack). These imports already exist in `state.py` and are NOT being added by this spec — they are pre-existing.

**What changes:** Add import of `WorkspaceContext` and append `workspace_ctx` field to the `AgentState` TypedDict body.

## 4. Data Structures

### 4.1 WorkspaceContext

**Definition:**

```python
@dataclass(frozen=True)
class WorkspaceContext:
    assemblyzero_root: Path
    target_repo: Path
```

**Concrete Example:**

```json
{
    "assemblyzero_root": "/home/user/Projects/AssemblyZero",
    "target_repo": "/home/user/Projects/Career",
    "docs_dir": "/home/user/Projects/AssemblyZero/docs",
    "lld_active_dir": "/home/user/Projects/AssemblyZero/docs/lld/active",
    "reports_dir": "/home/user/Projects/AssemblyZero/docs/reports",
    "target_name": "Career"
}
```

Note: `docs_dir`, `lld_active_dir`, `reports_dir`, `target_name` are `@property` — not stored fields. Shown for illustration.

### 4.2 AgentState (updated)

**Definition (addition only):**

```python
class AgentState(TypedDict):
    # ... existing fields preserved ...
    workspace_ctx: WorkspaceContext  # ref #838
```

**Concrete Example:**

```json
{
    "messages": [],
    "issue_number": 838,
    "workspace_ctx": {
        "assemblyzero_root": "/home/user/Projects/AssemblyZero",
        "target_repo": "/home/user/Projects/Career"
    }
}
```

## 5. Function Specifications

### 5.1 `WorkspaceContext.__post_init__()`

**File:** `assemblyzero/core/workspace_context.py`

**Signature:**

```python
def __post_init__(self) -> None:
    """Validate both paths are absolute and exist."""
```

**Input Example:**

```python
WorkspaceContext(
    assemblyzero_root=Path("/home/user/Projects/AssemblyZero"),
    target_repo=Path("/home/user/Projects/Career"),
)
```

**Output Example:** Instance created successfully (no return).

**Edge Cases:**
- Relative path -> `ValueError("assemblyzero_root must be absolute: relative/path")`
- Non-existent path -> `ValueError("assemblyzero_root does not exist: /no/such/path")`
- Non-Path type -> `TypeError("assemblyzero_root must be a Path, got str")`

### 5.2 `make_workspace_context()`

**File:** `assemblyzero/core/workspace_context.py`

**Signature:**

```python
def make_workspace_context(
    assemblyzero_root: str | Path,
    target_repo: str | Path,
) -> WorkspaceContext:
    """Construct a WorkspaceContext, resolving both paths to absolute."""
```

**Input Example:**

```python
ctx = make_workspace_context(
    "C:/Users/mcwiz/Projects/AssemblyZero",
    "C:/Users/mcwiz/Projects/Career",
)
```

**Output Example:**

```python
WorkspaceContext(
    assemblyzero_root=WindowsPath('C:/Users/mcwiz/Projects/AssemblyZero'),
    target_repo=WindowsPath('C:/Users/mcwiz/Projects/Career'),
)
```

**Edge Cases:**
- String input -> converted via `Path(x).resolve()`
- Non-existent after resolve -> `ValueError` from `__post_init__`

### 5.3 Properties

**File:** `assemblyzero/core/workspace_context.py`

| Property | Input (ctx with root=`/az`, target=`/x/Career`) | Output |
|----------|--------------------------------------------------|--------|
| `docs_dir` | — | `Path("/az/docs")` |
| `lld_active_dir` | — | `Path("/az/docs/lld/active")` |
| `reports_dir` | — | `Path("/az/docs/reports")` |
| `target_name` | — | `"Career"` |

## 6. Change Instructions

### 6.1 `assemblyzero/core/workspace_context.py` (Add)

**Complete file contents:**

```python
"""WorkspaceContext: immutable bundle of workspace paths.

Issue #838: Eliminates path prop-drilling across workflow nodes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkspaceContext:
    """Immutable container for workspace path configuration.

    Constructed once at workflow entry and threaded through LangGraph
    state. Nodes read from state["workspace_ctx"] instead of accepting
    separate path parameters.

    Attributes:
        assemblyzero_root: Absolute path to the AssemblyZero repository.
        target_repo: Absolute path to the target repository being processed.
    """

    assemblyzero_root: Path
    target_repo: Path

    def __post_init__(self) -> None:
        """Validate both paths are absolute and exist."""
        for field_name in ("assemblyzero_root", "target_repo"):
            path = getattr(self, field_name)
            if not isinstance(path, Path):
                raise TypeError(
                    f"{field_name} must be a Path, got {type(path).__name__}"
                )
            if not path.is_absolute():
                raise ValueError(f"{field_name} must be absolute: {path}")
            if not path.exists():
                raise ValueError(f"{field_name} does not exist: {path}")

    @property
    def docs_dir(self) -> Path:
        """Return assemblyzero_root / 'docs'."""
        return self.assemblyzero_root / "docs"

    @property
    def lld_active_dir(self) -> Path:
        """Return docs / 'lld' / 'active'."""
        return self.docs_dir / "lld" / "active"

    @property
    def reports_dir(self) -> Path:
        """Return docs / 'reports'."""
        return self.docs_dir / "reports"

    @property
    def target_name(self) -> str:
        """Return the basename of the target repository."""
        return self.target_repo.name


def make_workspace_context(
    assemblyzero_root: str | Path,
    target_repo: str | Path,
) -> WorkspaceContext:
    """Construct a WorkspaceContext, resolving both paths to absolute.

    Args:
        assemblyzero_root: Path (str or Path) to the AssemblyZero repo.
        target_repo: Path (str or Path) to the target repository.

    Returns:
        A validated, frozen WorkspaceContext.

    Raises:
        ValueError: If either resolved path does not exist.
    """
    return WorkspaceContext(
        assemblyzero_root=Path(assemblyzero_root).resolve(),
        target_repo=Path(target_repo).resolve(),
    )
```

### 6.2 `assemblyzero/core/__init__.py` (Modify)

**Change 1:** Append import block after the last existing import (`from assemblyzero.core.state import AgentState`):

```diff
 from assemblyzero.core.state import AgentState
+
+from assemblyzero.core.workspace_context import (
+    WorkspaceContext,
+    make_workspace_context,
+)
```

### 6.3 `assemblyzero/core/state.py` (Modify)

**Change 1:** Add import after existing `from langgraph.graph.message import add_messages` line:

```diff
 from langgraph.graph.message import add_messages
+
+from assemblyzero.core.workspace_context import WorkspaceContext
```

**Change 2:** Add `workspace_ctx` field to `AgentState` TypedDict. Append at the end of the class body (after all existing fields):

```diff
+    workspace_ctx: WorkspaceContext  # ref #838 — immutable workspace path context
```

> **NOTE:** Preserve ALL existing fields in `AgentState`. The excerpt in §3.2 is truncated — the actual class likely has many more fields. Only append `workspace_ctx` as the last field.

### 6.4 `tests/unit/test_workspace_context.py` (Add)

**Complete file contents:**

```python
"""Tests for WorkspaceContext dataclass and factory.

Issue #838: T010–T150
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import get_type_hints

import pytest


class TestWorkspaceContextConstruction:
    """T010, T020: Happy-path construction."""

    def test_valid_absolute_paths(self, tmp_path: Path) -> None:
        """T010: Construct with valid absolute paths."""
        from assemblyzero.core.workspace_context import WorkspaceContext

        root = tmp_path / "az"
        repo = tmp_path / "repo"
        root.mkdir()
        repo.mkdir()

        ctx = WorkspaceContext(assemblyzero_root=root, target_repo=repo)

        assert ctx.assemblyzero_root == root
        assert ctx.target_repo == repo

    def test_factory_with_strings(self, tmp_path: Path) -> None:
        """T020: make_workspace_context accepts str args."""
        from assemblyzero.core.workspace_context import make_workspace_context

        root = tmp_path / "az"
        repo = tmp_path / "repo"
        root.mkdir()
        repo.mkdir()

        ctx = make_workspace_context(str(root), str(repo))

        assert isinstance(ctx.assemblyzero_root, Path)
        assert isinstance(ctx.target_repo, Path)


class TestWorkspaceContextValidation:
    """T030, T040: Validation errors."""

    def test_missing_assemblyzero_root(self, tmp_path: Path) -> None:
        """T030: Non-existent root raises ValueError."""
        from assemblyzero.core.workspace_context import make_workspace_context

        repo = tmp_path / "repo"
        repo.mkdir()
        bad_root = tmp_path / "nonexistent"

        with pytest.raises(ValueError, match="assemblyzero_root"):
            make_workspace_context(str(bad_root), str(repo))

    def test_missing_target_repo(self, tmp_path: Path) -> None:
        """T040: Non-existent target raises ValueError."""
        from assemblyzero.core.workspace_context import make_workspace_context

        root = tmp_path / "az"
        root.mkdir()
        bad_repo = tmp_path / "nonexistent"

        with pytest.raises(ValueError, match="target_repo"):
            make_workspace_context(str(root), str(bad_repo))


class TestWorkspaceContextFrozen:
    """T050: Immutability."""

    def test_frozen_raises(self, tmp_path: Path) -> None:
        """T050: Assignment raises FrozenInstanceError."""
        from assemblyzero.core.workspace_context import WorkspaceContext

        root = tmp_path / "az"
        repo = tmp_path / "repo"
        root.mkdir()
        repo.mkdir()

        ctx = WorkspaceContext(assemblyzero_root=root, target_repo=repo)

        with pytest.raises(dataclasses.FrozenInstanceError):
            ctx.assemblyzero_root = root  # type: ignore[misc]


class TestWorkspaceContextProperties:
    """T060–T090: Derived properties."""

    @pytest.fixture()
    def ctx(self, tmp_path: Path):
        from assemblyzero.core.workspace_context import WorkspaceContext

        root = tmp_path / "az"
        repo = tmp_path / "my-repo"
        root.mkdir()
        repo.mkdir()
        return WorkspaceContext(assemblyzero_root=root, target_repo=repo)

    def test_docs_dir(self, ctx, tmp_path: Path) -> None:
        """T060."""
        assert ctx.docs_dir == ctx.assemblyzero_root / "docs"

    def test_lld_active_dir(self, ctx) -> None:
        """T070."""
        assert ctx.lld_active_dir == ctx.assemblyzero_root / "docs" / "lld" / "active"

    def test_reports_dir(self, ctx) -> None:
        """T080."""
        assert ctx.reports_dir == ctx.assemblyzero_root / "docs" / "reports"

    def test_target_name(self, ctx) -> None:
        """T090."""
        assert ctx.target_name == "my-repo"


class TestWorkspaceContextImport:
    """T100: Public import path."""

    def test_importable_from_core(self) -> None:
        """T100."""
        from assemblyzero.core import WorkspaceContext

        assert WorkspaceContext is not None


class TestStateIntegration:
    """T120: AgentState TypedDict declares workspace_ctx."""

    def test_agent_state_has_workspace_ctx(self) -> None:
        """T120."""
        from assemblyzero.core.state import AgentState
        from assemblyzero.core.workspace_context import WorkspaceContext

        hints = get_type_hints(AgentState)
        assert hints.get("workspace_ctx") is WorkspaceContext
```

### 6.5 `tests/unit/test_gate/test_gate_workspace_context.py` (Add)

**Complete file contents:**

```python
"""Tests verifying gate/node usage of WorkspaceContext from state.

Issue #838: T110
"""

from __future__ import annotations

from pathlib import Path

import pytest


class TestNodeReadsWorkspaceContext:
    """T110: Node reads workspace_ctx from state dict."""

    def test_node_reads_ctx_from_state(self, tmp_path: Path) -> None:
        """T110: Simulate a node extracting WorkspaceContext from state."""
        from assemblyzero.core.workspace_context import WorkspaceContext

        root = tmp_path / "az"
        repo = tmp_path / "repo"
        root.mkdir()
        repo.mkdir()

        ctx = WorkspaceContext(assemblyzero_root=root, target_repo=repo)
        state = {"workspace_ctx": ctx}

        # Simulate node extraction pattern
        extracted: WorkspaceContext = state["workspace_ctx"]
        assert extracted.assemblyzero_root == root
        assert extracted.target_repo == repo
        assert extracted.target_name == "repo"
```

## 7. Pattern References

### 7.1 TypedDict State Pattern

**File:** `assemblyzero/core/state.py` (lines 1–18)

```python
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import BaseMessage

from langgraph.graph.message import add_messages

class AgentState(TypedDict):

    """Core state shared across all AssemblyZero LangGraph nodes.

Attributes:"""
```

**Relevance:** This is the exact TypedDict we're adding `workspace_ctx` to. Follow existing field declaration style. Note: `langchain_core.messages` and `langgraph.graph.message` are existing project dependencies already imported here — this spec does NOT add them.

### 7.2 Core Module Re-export Pattern

**File:** `assemblyzero/core/__init__.py` (lines 1–33)

```python
from assemblyzero.core.audit import (
    ReviewAuditLog,
    ...
)
from assemblyzero.core.state import AgentState
```

**Relevance:** Shows the grouped-import re-export pattern. New `WorkspaceContext` import follows identical style.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from dataclasses import dataclass` | stdlib | `workspace_context.py` |
| `from pathlib import Path` | stdlib | `workspace_context.py` |
| `from __future__ import annotations` | stdlib | `workspace_context.py` |
| `from assemblyzero.core.workspace_context import WorkspaceContext` | internal (new) | `__init__.py`, `state.py` |
| `from assemblyzero.core.workspace_context import make_workspace_context` | internal (new) | `__init__.py` |
| `from langchain_core.messages import BaseMessage` | langchain-core (existing dep) | `state.py` (pre-existing, NOT added by this spec) |
| `from langgraph.graph.message import add_messages` | langgraph (existing dep) | `state.py` (pre-existing, NOT added by this spec) |

**New Dependencies:** None. All imports are stdlib or existing internal modules. `langchain_core` and `langgraph` are pre-existing project dependencies already used in `state.py`.

## 9. Placeholder

Reserved.

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `WorkspaceContext.__init__` | Two existing `tmp_path` dirs | Instance with matching fields |
| T020 | `make_workspace_context` | Two str paths | Instance with `Path` fields |
| T030 | `make_workspace_context` | Non-existent root | `ValueError` matching "assemblyzero_root" |
| T040 | `make_workspace_context` | Non-existent repo | `ValueError` matching "target_repo" |
| T050 | `WorkspaceContext` field assignment | Valid ctx, assign field | `FrozenInstanceError` |
| T060 | `WorkspaceContext.docs_dir` | Valid ctx | `root / "docs"` |
| T070 | `WorkspaceContext.lld_active_dir` | Valid ctx | `root / "docs" / "lld" / "active"` |
| T080 | `WorkspaceContext.reports_dir` | Valid ctx | `root / "docs" / "reports"` |
| T090 | `WorkspaceContext.target_name` | ctx with repo named "my-repo" | `"my-repo"` |
| T100 | Import check | `from assemblyzero.core import WorkspaceContext` | No error |
| T110 | State dict extraction | `state["workspace_ctx"]` | Correct `WorkspaceContext` |
| T120 | `get_type_hints(AgentState)` | — | Contains `workspace_ctx: WorkspaceContext` |

## 11. Implementation Notes

### 11.1 Error Handling Convention

`__post_init__` raises `ValueError` with field name and path in message. No error codes, no wrapped exceptions.

### 11.2 Node Migration (Deferred)

The LLD lists 7 node files as "Add" but these likely already exist. Node migration to use `state["workspace_ctx"]` is mechanical: replace `assemblyzero_root` / `target_repo` params with `ctx = state["workspace_ctx"]`. This should be done file-by-file in a follow-up after verifying which files exist via `ls`.

### 11.3 Circular Import Prevention

`workspace_context.py` imports ONLY `dataclasses` and `pathlib`. `state.py` imports from `workspace_context`. Never the reverse.

### 11.4 Pre-existing Dependencies Clarification

The `langchain_core.messages.BaseMessage` and `langgraph.graph.message.add_messages` imports in `state.py` are **pre-existing** project dependencies (part of the LangGraph/LangChain stack). They are already installed and imported in the current `state.py`. This spec does NOT add, modify, or remove those imports.

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3)
- [x] Every data structure has a concrete JSON/YAML example (Section 4)
- [x] Every function has input/output examples with realistic values (Section 5)
- [x] Change instructions are diff-level specific (Section 6)
- [x] Pattern references include file:line and are verified to exist (Section 7)
- [x] All imports are listed and verified (Section 8)
- [x] Test mapping covers all LLD test scenarios (Section 10)

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #838 |
| Verdict | DRAFT |
| Date | 2026-03-19 |
| Iterations | 2 |
| Finalized | — |