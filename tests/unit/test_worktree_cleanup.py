"""Tests for pre-worktree-removal artifact archival.

Issue #189: Add pre-worktree-removal cleanup protocol to save audit artifacts.

TDD: Tests written first to define expected behavior.
"""

from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

# Add tools directory to path for import
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tools"))


class TestArchiveLineage:
    """Tests for archive_lineage function."""

    def test_archive_lineage_to_main(self, tmp_path):
        """Lineage files should be copied to archived/ before deletion."""
        # Create mock worktree structure
        worktree = tmp_path / "worktree"
        main_repo = tmp_path / "main"

        lineage_dir = worktree / "docs" / "lineage" / "active" / "42-testing"
        lineage_dir.mkdir(parents=True)
        (lineage_dir / "001-issue.md").write_text("# Issue content")
        (lineage_dir / "002-draft.md").write_text("# Draft content")

        main_repo.mkdir()

        from archive_worktree_lineage import archive_lineage

        archived = archive_lineage(worktree, 42, main_repo)

        # Verify files copied to archived/
        archived_dir = main_repo / "docs" / "lineage" / "archived" / "42-testing"
        assert archived_dir.exists(), "Archived directory should exist"
        assert (archived_dir / "001-issue.md").exists()
        assert (archived_dir / "002-draft.md").exists()
        assert len(archived) == 1

    def test_archive_creates_archived_directory(self, tmp_path):
        """Should create archived/ directory if it doesn't exist."""
        worktree = tmp_path / "worktree"
        main_repo = tmp_path / "main"

        lineage_dir = worktree / "docs" / "lineage" / "active" / "42-feature"
        lineage_dir.mkdir(parents=True)
        (lineage_dir / "001-issue.md").write_text("content")

        main_repo.mkdir()
        # archived/ does NOT exist initially

        from archive_worktree_lineage import archive_lineage

        archive_lineage(worktree, 42, main_repo)

        # Verify archived/ was created
        archived_parent = main_repo / "docs" / "lineage" / "archived"
        assert archived_parent.exists(), "archived/ directory should be created"

    def test_archive_preserves_directory_structure(self, tmp_path):
        """Archived files should maintain original structure."""
        worktree = tmp_path / "worktree"
        main_repo = tmp_path / "main"

        # Create nested structure
        lineage_dir = worktree / "docs" / "lineage" / "active" / "42-nested"
        (lineage_dir / "subdir").mkdir(parents=True)
        (lineage_dir / "001-issue.md").write_text("root file")
        (lineage_dir / "subdir" / "nested.md").write_text("nested file")

        main_repo.mkdir()

        from archive_worktree_lineage import archive_lineage

        archive_lineage(worktree, 42, main_repo)

        # Verify structure preserved
        archived_dir = main_repo / "docs" / "lineage" / "archived" / "42-nested"
        assert (archived_dir / "001-issue.md").exists()
        assert (archived_dir / "subdir" / "nested.md").exists()

    def test_no_archive_when_no_lineage(self, tmp_path):
        """Should handle missing lineage directory gracefully."""
        worktree = tmp_path / "worktree"
        main_repo = tmp_path / "main"

        worktree.mkdir()
        main_repo.mkdir()
        # No docs/lineage/active/ directory

        from archive_worktree_lineage import archive_lineage

        # Should not raise an error
        archived = archive_lineage(worktree, 42, main_repo)
        assert archived == []

    def test_archive_returns_list_of_archived_files(self, tmp_path):
        """Should return list of directories that were archived."""
        worktree = tmp_path / "worktree"
        main_repo = tmp_path / "main"

        # Create two matching directories
        for name in ["42-first", "42-second"]:
            lineage_dir = worktree / "docs" / "lineage" / "active" / name
            lineage_dir.mkdir(parents=True)
            (lineage_dir / "file.md").write_text("content")

        main_repo.mkdir()

        from archive_worktree_lineage import archive_lineage

        archived = archive_lineage(worktree, 42, main_repo)

        assert len(archived) == 2
        assert all(isinstance(p, Path) for p in archived)

    def test_archive_handles_existing_archived_dir(self, tmp_path):
        """Should overwrite existing archived directory."""
        worktree = tmp_path / "worktree"
        main_repo = tmp_path / "main"

        # Create source
        lineage_dir = worktree / "docs" / "lineage" / "active" / "42-test"
        lineage_dir.mkdir(parents=True)
        (lineage_dir / "new-file.md").write_text("new content")

        # Create existing archived dir with different content
        existing = main_repo / "docs" / "lineage" / "archived" / "42-test"
        existing.mkdir(parents=True)
        (existing / "old-file.md").write_text("old content")

        from archive_worktree_lineage import archive_lineage

        archive_lineage(worktree, 42, main_repo)

        archived_dir = main_repo / "docs" / "lineage" / "archived" / "42-test"
        assert (archived_dir / "new-file.md").exists()
        assert not (archived_dir / "old-file.md").exists()


class TestStageArchived:
    """Tests for stage_archived function."""

    @patch("subprocess.run")
    def test_stages_when_changes_exist(self, mock_run, tmp_path):
        """Should log staging success when there are staged changes."""
        main_repo = tmp_path / "main"
        main_repo.mkdir()

        # Mock: git add succeeds, git diff returns 1 (changes exist)
        mock_run.side_effect = [
            MagicMock(returncode=0),  # git add
            MagicMock(returncode=1),  # git diff --cached (changes exist)
        ]

        from archive_worktree_lineage import stage_archived

        stage_archived(main_repo, 42)

        assert mock_run.call_count == 2

    @patch("subprocess.run")
    def test_skips_stage_when_no_changes(self, mock_run, tmp_path):
        """Should skip when no staged changes."""
        main_repo = tmp_path / "main"
        main_repo.mkdir()

        # Mock: git add succeeds, git diff returns 0 (no changes)
        mock_run.side_effect = [
            MagicMock(returncode=0),  # git add
            MagicMock(returncode=0),  # git diff --cached (no changes)
        ]

        from archive_worktree_lineage import stage_archived

        stage_archived(main_repo, 42)

        assert mock_run.call_count == 2  # No commit call


class TestIntegration:
    """Integration tests for the full workflow."""

    def test_full_archive_workflow(self, tmp_path):
        """Test complete archive workflow without git commit.

        Built on a real worktree off a real main repository (#3528). The
        caches left in the worktree are asserted UNTOUCHED: since #3558 the
        tool deletes nothing, and `git worktree remove` takes them later.
        """
        import subprocess

        worktree = tmp_path / "worktree"
        main_repo = tmp_path / "main"
        main_repo.mkdir()
        for args in (
            ["init", "-q", "-b", "main"],
            ["config", "user.email", "t@example.com"],
            ["config", "user.name", "Test"],
            ["commit", "-q", "--allow-empty", "-m", "base"],
            ["worktree", "add", "-q", "--detach", str(worktree)],
        ):
            subprocess.run(["git", "-C", str(main_repo), *args], check=True,
                           capture_output=True)

        # Set up worktree with lineage and ephemeral files
        lineage_dir = worktree / "docs" / "lineage" / "active" / "99-integration"
        lineage_dir.mkdir(parents=True)
        (lineage_dir / "001-issue.md").write_text("# Issue")
        (lineage_dir / "002-lld.md").write_text("# LLD")

        coverage = worktree / ".coverage"
        coverage.write_text("coverage")

        pycache = worktree / "__pycache__"
        pycache.mkdir()

        from archive_worktree_lineage import archive_lineage

        # Archive
        archived = archive_lineage(worktree, 99, main_repo)
        assert len(archived) == 1

        # Verify archived
        assert (main_repo / "docs" / "lineage" / "archived" / "99-integration" / "001-issue.md").exists()

        # Verify nothing was deleted (#3558): the caches are git worktree
        # remove's to take, and the source lineage stays with the worktree.
        assert coverage.exists()
        assert pycache.exists()
        assert lineage_dir.exists()
