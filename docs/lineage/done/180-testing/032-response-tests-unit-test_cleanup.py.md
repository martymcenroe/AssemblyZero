

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
