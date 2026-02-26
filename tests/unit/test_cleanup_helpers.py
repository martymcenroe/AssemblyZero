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