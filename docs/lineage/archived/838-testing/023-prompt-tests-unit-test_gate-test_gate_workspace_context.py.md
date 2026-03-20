# Implementation Request: tests/unit/test_gate/test_gate_workspace_context.py

## Task

Write the complete contents of `tests/unit/test_gate/test_gate_workspace_context.py`.

Change type: Add
Description: Gate/node integration tests

## Previously Implemented Files

These files have already been implemented. Use them for imports and references:

### assemblyzero/core/workspace_context.py (signatures)

```python
"""WorkspaceContext: immutable bundle of workspace paths.

Issue #838: Eliminates path prop-drilling across workflow nodes.
"""

from __future__ import annotations

from dataclasses import dataclass

from pathlib import Path

class WorkspaceContext:

    """Immutable container for workspace path configuration.

Constructed once at workflow entry and threaded through LangGraph"""

    def __post_init__(self) -> None:
    """Validate both paths are absolute and exist."""
    ...

    def docs_dir(self) -> Path:
    """Return assemblyzero_root / 'docs'."""
    ...

    def lld_active_dir(self) -> Path:
    """Return docs / 'lld' / 'active'."""
    ...

    def reports_dir(self) -> Path:
    """Return docs / 'reports'."""
    ...

    def target_name(self) -> str:
    """Return the basename of the target repository."""
    ...

def make_workspace_context(
    assemblyzero_root: str | Path,
    target_repo: str | Path,
) -> WorkspaceContext:
    """Construct a WorkspaceContext, resolving both paths to absolute.

Args:"""
    ...
```

### assemblyzero/core/__init__.py (signatures)

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

from assemblyzero.core.workspace_context import (
    WorkspaceContext,
    make_workspace_context,
)
```

### assemblyzero/core/state.py (signatures)

```python
"""Core state definition for AssemblyZero LangGraph workflows.

This module defines the AgentState TypedDict that travels through
the governance pipeline: Issue -> LLD Review -> Implementation -> Code Review -> Merge
"""

from typing import Annotated, Literal, TypedDict

from assemblyzero.core.workspace_context import WorkspaceContext

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

### tests/unit/test_workspace_context.py (full)

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

    def test_docs_dir(self, ctx) -> None:
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
    """T110, T120: State dict and AgentState TypedDict."""

    def test_node_reads_ctx_from_state(self, tmp_path: Path) -> None:
        """T110: Simulate a node extracting WorkspaceContext from state."""
        from assemblyzero.core.workspace_context import WorkspaceContext

        root = tmp_path / "az"
        repo = tmp_path / "repo"
        root.mkdir()
        repo.mkdir()

        ctx = WorkspaceContext(assemblyzero_root=root, target_repo=repo)
        state = {"workspace_ctx": ctx}

        extracted: WorkspaceContext = state["workspace_ctx"]
        assert extracted.assemblyzero_root == root
        assert extracted.target_repo == repo
        assert extracted.target_name == "repo"

    def test_agent_state_has_workspace_ctx(self) -> None:
        """T120."""
        from assemblyzero.core.state import AgentState
        from assemblyzero.core.workspace_context import WorkspaceContext

        hints = get_type_hints(AgentState)
        assert hints.get("workspace_ctx") is WorkspaceContext
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
