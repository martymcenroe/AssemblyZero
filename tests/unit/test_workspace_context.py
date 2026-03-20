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