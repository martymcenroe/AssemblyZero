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