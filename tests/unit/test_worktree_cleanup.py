"""Tests for pre-worktree-removal artifact archival.

Issue #189: Add pre-worktree-removal cleanup protocol to save audit artifacts.

TDD: Tests written first to define expected behavior.
"""

import pytest
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


class TestCleanEphemeral:
    """Tests for clean_ephemeral function."""

    def test_removes_coverage_file(self, tmp_path):
        """Should remove .coverage file."""
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        coverage_file = worktree / ".coverage"
        coverage_file.write_text("coverage data")

        from archive_worktree_lineage import clean_ephemeral

        clean_ephemeral(worktree)

        assert not coverage_file.exists()

    def test_removes_pycache_directory(self, tmp_path):
        """Should remove __pycache__ directory."""
        worktree = tmp_path / "worktree"
        pycache = worktree / "__pycache__"
        pycache.mkdir(parents=True)
        (pycache / "module.pyc").write_text("bytecode")

        from archive_worktree_lineage import clean_ephemeral

        clean_ephemeral(worktree)

        assert not pycache.exists()

    def test_removes_pytest_cache(self, tmp_path):
        """Should remove .pytest_cache directory."""
        worktree = tmp_path / "worktree"
        pytest_cache = worktree / ".pytest_cache"
        pytest_cache.mkdir(parents=True)
        (pytest_cache / "v" / "cache").mkdir(parents=True)

        from archive_worktree_lineage import clean_ephemeral

        clean_ephemeral(worktree)

        assert not pytest_cache.exists()

    def test_removes_assemblyzero_audit(self, tmp_path):
        """Should remove .assemblyzero/audit directory."""
        worktree = tmp_path / "worktree"
        audit_dir = worktree / ".assemblyzero" / "audit"
        audit_dir.mkdir(parents=True)
        (audit_dir / "trace.log").write_text("execution trace")

        from archive_worktree_lineage import clean_ephemeral

        clean_ephemeral(worktree)

        assert not audit_dir.exists()

    def test_handles_missing_ephemeral_files(self, tmp_path):
        """Should not error when ephemeral files don't exist."""
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        # No ephemeral files exist

        from archive_worktree_lineage import clean_ephemeral

        # Should not raise
        clean_ephemeral(worktree)


class TestCommitArchived:
    """Tests for commit_archived function."""

    @patch("subprocess.run")
    def test_commits_when_changes_exist(self, mock_run, tmp_path):
        """Should commit when there are staged changes."""
        main_repo = tmp_path / "main"
        main_repo.mkdir()

        # Mock: git add succeeds, git diff returns 1 (changes exist), git commit succeeds
        mock_run.side_effect = [
            MagicMock(returncode=0),  # git add
            MagicMock(returncode=1),  # git diff --cached (changes exist)
            MagicMock(returncode=0),  # git commit
        ]

        from archive_worktree_lineage import commit_archived

        commit_archived(main_repo, 42)

        assert mock_run.call_count == 3
        # Verify commit was called
        commit_call = mock_run.call_args_list[2]
        assert "commit" in commit_call[0][0]
        assert "#42" in commit_call[0][0][-1]

    @patch("subprocess.run")
    def test_skips_commit_when_no_changes(self, mock_run, tmp_path):
        """Should skip commit when no staged changes."""
        main_repo = tmp_path / "main"
        main_repo.mkdir()

        # Mock: git add succeeds, git diff returns 0 (no changes)
        mock_run.side_effect = [
            MagicMock(returncode=0),  # git add
            MagicMock(returncode=0),  # git diff --cached (no changes)
        ]

        from archive_worktree_lineage import commit_archived

        commit_archived(main_repo, 42)

        assert mock_run.call_count == 2  # No commit call


class TestIntegration:
    """Integration tests for the full workflow."""

    def test_full_archive_workflow(self, tmp_path):
        """Test complete archive workflow without git commit."""
        worktree = tmp_path / "worktree"
        main_repo = tmp_path / "main"

        # Set up worktree with lineage and ephemeral files
        lineage_dir = worktree / "docs" / "lineage" / "active" / "99-integration"
        lineage_dir.mkdir(parents=True)
        (lineage_dir / "001-issue.md").write_text("# Issue")
        (lineage_dir / "002-lld.md").write_text("# LLD")

        coverage = worktree / ".coverage"
        coverage.write_text("coverage")

        pycache = worktree / "__pycache__"
        pycache.mkdir()

        main_repo.mkdir()

        from archive_worktree_lineage import archive_lineage, clean_ephemeral

        # Archive
        archived = archive_lineage(worktree, 99, main_repo)
        assert len(archived) == 1

        # Clean
        clean_ephemeral(worktree)

        # Verify archived
        assert (main_repo / "docs" / "lineage" / "archived" / "99-integration" / "001-issue.md").exists()

        # Verify cleaned
        assert not coverage.exists()
        assert not pycache.exists()

        # Verify source still exists (we don't delete worktree)
        assert lineage_dir.exists()
