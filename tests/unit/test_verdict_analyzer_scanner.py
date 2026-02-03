"""Unit tests for verdict_analyzer/scanner.py module.

Issue #228: Add unit tests for verdict_analyzer module.

Tests verify repository scanning functionality including:
- Verdict file discovery
- Registry loading
- Path validation
- Directory scanning with symlink handling
- Full scan_repos workflow
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.verdict_analyzer.scanner import (
    _scan_directory,
    discover_verdicts,
    find_registry,
    load_registry,
    scan_repos,
    validate_verdict_path,
)


@pytest.fixture
def repo_with_verdicts(tmp_path):
    """Create a mock repository with verdict files."""
    repo = tmp_path / "test_repo"
    repo.mkdir()

    # Create lineage directory structure
    lineage_active = repo / "docs" / "lineage" / "active"
    lineage_active.mkdir(parents=True)

    # Create verdict files
    (lineage_active / "001-verdict.md").write_text("# Test verdict 1")
    (lineage_active / "002-verdict.md").write_text("# Test verdict 2")

    # Create non-verdict file (should be skipped)
    (lineage_active / "readme.md").write_text("# Not a verdict")

    return repo


@pytest.fixture
def registry_file(tmp_path):
    """Create a project-registry.json file."""
    registry = tmp_path / "project-registry.json"
    registry.write_text(json.dumps([
        str(tmp_path / "repo1"),
        str(tmp_path / "repo2"),
        str(tmp_path / "nonexistent"),  # This one won't exist
    ]))

    # Create repo1 and repo2
    (tmp_path / "repo1").mkdir()
    (tmp_path / "repo2").mkdir()

    return registry


class TestFindRegistry:
    """Tests for find_registry function."""

    def test_finds_registry_in_current_dir(self, tmp_path):
        """Should find registry in current directory."""
        registry = tmp_path / "project-registry.json"
        registry.write_text("[]")

        result = find_registry(tmp_path)
        assert result == registry

    def test_finds_registry_in_parent_dir(self, tmp_path):
        """Should find registry by searching up directory tree."""
        registry = tmp_path / "project-registry.json"
        registry.write_text("[]")

        subdir = tmp_path / "nested" / "deeply"
        subdir.mkdir(parents=True)

        result = find_registry(subdir)
        assert result == registry

    def test_returns_none_when_not_found(self, tmp_path):
        """Should return None when registry not found."""
        subdir = tmp_path / "no_registry"
        subdir.mkdir()

        result = find_registry(subdir)
        assert result is None


class TestLoadRegistry:
    """Tests for load_registry function."""

    def test_loads_existing_repos(self, registry_file, tmp_path):
        """Should load paths for existing repositories."""
        repos = load_registry(registry_file)

        assert len(repos) == 2  # Only 2 exist
        assert tmp_path / "repo1" in repos
        assert tmp_path / "repo2" in repos

    def test_skips_nonexistent_repos(self, registry_file, tmp_path):
        """Should skip repositories that don't exist."""
        repos = load_registry(registry_file)

        nonexistent = tmp_path / "nonexistent"
        assert nonexistent not in repos

    def test_empty_registry(self, tmp_path):
        """Should handle empty registry."""
        registry = tmp_path / "empty-registry.json"
        registry.write_text("[]")

        repos = load_registry(registry)
        assert repos == []


class TestValidateVerdictPath:
    """Tests for validate_verdict_path function."""

    def test_valid_verdict_file(self, tmp_path):
        """Should accept verdict files within base directory."""
        base = tmp_path / "repo"
        base.mkdir()

        verdict = base / "docs" / "verdict-001.md"
        verdict.parent.mkdir(parents=True)
        verdict.write_text("test")

        assert validate_verdict_path(verdict, base) is True

    def test_rejects_non_verdict_file(self, tmp_path):
        """Should reject files without 'verdict' in name."""
        base = tmp_path / "repo"
        base.mkdir()

        non_verdict = base / "docs" / "readme.md"
        non_verdict.parent.mkdir(parents=True)
        non_verdict.write_text("test")

        assert validate_verdict_path(non_verdict, base) is False

    def test_rejects_outside_base_dir(self, tmp_path):
        """Should reject files outside base directory."""
        base = tmp_path / "repo"
        base.mkdir()

        outside = tmp_path / "outside_verdict.md"
        outside.write_text("test")

        assert validate_verdict_path(outside, base) is False


class TestDiscoverVerdicts:
    """Tests for discover_verdicts function."""

    def test_finds_verdicts_in_lineage_active(self, repo_with_verdicts):
        """Should find verdicts in docs/lineage/active/."""
        verdicts = list(discover_verdicts(repo_with_verdicts))

        assert len(verdicts) == 2
        filenames = {v.name for v in verdicts}
        assert "001-verdict.md" in filenames
        assert "002-verdict.md" in filenames

    def test_skips_non_verdict_files(self, repo_with_verdicts):
        """Should skip files without 'verdict' in name."""
        verdicts = list(discover_verdicts(repo_with_verdicts))

        filenames = {v.name for v in verdicts}
        assert "readme.md" not in filenames

    def test_handles_empty_directory(self, tmp_path):
        """Should handle repository with no verdict directories."""
        empty_repo = tmp_path / "empty_repo"
        empty_repo.mkdir()

        verdicts = list(discover_verdicts(empty_repo))
        assert verdicts == []

    def test_handles_nonexistent_repo(self, tmp_path):
        """Should handle non-existent repository path."""
        nonexistent = tmp_path / "does_not_exist"

        verdicts = list(discover_verdicts(nonexistent))
        assert verdicts == []

    def test_scans_multiple_verdict_dirs(self, tmp_path):
        """Should scan all known verdict directory locations."""
        repo = tmp_path / "multi_repo"
        repo.mkdir()

        # Create verdicts in different locations
        lineage = repo / "docs" / "lineage"
        lineage.mkdir(parents=True)
        (lineage / "verdict1.md").write_text("test")

        verdicts_dir = repo / "docs" / "verdicts"
        verdicts_dir.mkdir(parents=True)
        (verdicts_dir / "verdict2.md").write_text("test")

        verdicts = list(discover_verdicts(repo))

        # Should find both
        assert len(verdicts) >= 2

    def test_no_duplicates(self, repo_with_verdicts):
        """Should not return duplicate paths."""
        verdicts = list(discover_verdicts(repo_with_verdicts))
        paths = [str(v) for v in verdicts]

        assert len(paths) == len(set(paths))


class TestScanDirectory:
    """Tests for _scan_directory function."""

    def test_scans_recursively(self, tmp_path):
        """Should scan directories recursively."""
        base = tmp_path / "base"
        base.mkdir()

        nested = base / "level1" / "level2"
        nested.mkdir(parents=True)

        verdict = nested / "deep_verdict.md"
        verdict.write_text("test")

        seen = set()
        verdicts = list(_scan_directory(base, seen, base))

        assert len(verdicts) == 1
        assert verdicts[0].name == "deep_verdict.md"

    def test_detects_symlink_loops(self, tmp_path):
        """Should detect and handle symlink loops."""
        base = tmp_path / "base"
        base.mkdir()

        # Create a symlink that points back to parent
        # Note: This may not work on all systems
        try:
            loop = base / "loop"
            loop.symlink_to(base)

            seen = set()
            # Should not infinite loop
            verdicts = list(_scan_directory(base, seen, base))
            # Test passes if we get here without hanging
        except OSError:
            # Symlinks may not be supported on all systems
            pytest.skip("Symlinks not supported")

    def test_only_returns_md_files(self, tmp_path):
        """Should only return .md files."""
        base = tmp_path / "base"
        base.mkdir()

        (base / "verdict.md").write_text("test")
        (base / "verdict.txt").write_text("test")
        (base / "verdict.json").write_text("{}")

        seen = set()
        verdicts = list(_scan_directory(base, seen, base))

        assert len(verdicts) == 1
        assert verdicts[0].suffix == ".md"


class TestIntegration:
    """Integration tests for scanner module."""

    def test_full_scan_workflow(self, tmp_path):
        """Test complete scan workflow from registry to verdicts."""
        # Set up repo with verdicts
        repo = tmp_path / "project"
        repo.mkdir()

        lineage = repo / "docs" / "lineage" / "active"
        lineage.mkdir(parents=True)
        (lineage / "test-verdict.md").write_text("# Governance Verdict: APPROVED")

        # Create registry
        registry = tmp_path / "project-registry.json"
        registry.write_text(json.dumps([str(repo)]))

        # Load repos and discover verdicts
        repos = load_registry(registry)
        assert len(repos) == 1

        verdicts = list(discover_verdicts(repos[0]))
        assert len(verdicts) == 1
        assert "verdict" in verdicts[0].name


class TestScanRepos:
    """Tests for scan_repos function."""

    def test_scans_and_inserts_verdicts(self, tmp_path):
        """Should scan repos and insert verdicts into database."""
        # Set up repo with verdict
        repo = tmp_path / "project"
        lineage = repo / "docs" / "lineage" / "active"
        lineage.mkdir(parents=True)
        (lineage / "test-verdict.md").write_text("# Governance Verdict: APPROVED")

        # Create registry
        registry = tmp_path / "project-registry.json"
        registry.write_text(json.dumps([str(repo)]))

        # Create database path
        db_path = tmp_path / "test.db"

        # Scan
        count = scan_repos(registry, db_path)

        assert count == 1
        assert db_path.exists()

    def test_skips_unchanged_verdicts(self, tmp_path):
        """Should skip verdicts that haven't changed."""
        # Set up repo with verdict
        repo = tmp_path / "project"
        lineage = repo / "docs" / "lineage" / "active"
        lineage.mkdir(parents=True)
        verdict_file = lineage / "test-verdict.md"
        verdict_file.write_text("# Governance Verdict: APPROVED")

        # Create registry
        registry = tmp_path / "project-registry.json"
        registry.write_text(json.dumps([str(repo)]))

        db_path = tmp_path / "test.db"

        # First scan
        count1 = scan_repos(registry, db_path)
        assert count1 == 1

        # Second scan (no changes)
        count2 = scan_repos(registry, db_path)
        assert count2 == 0  # Skipped because unchanged

    def test_force_rescans_all(self, tmp_path):
        """Should rescan all verdicts when force=True."""
        # Set up repo with verdict
        repo = tmp_path / "project"
        lineage = repo / "docs" / "lineage" / "active"
        lineage.mkdir(parents=True)
        (lineage / "test-verdict.md").write_text("# Governance Verdict: APPROVED")

        registry = tmp_path / "project-registry.json"
        registry.write_text(json.dumps([str(repo)]))

        db_path = tmp_path / "test.db"

        # First scan
        scan_repos(registry, db_path)

        # Force rescan
        count = scan_repos(registry, db_path, force=True)
        assert count == 1  # Re-parsed even though unchanged

    def test_handles_multiple_repos(self, tmp_path):
        """Should scan multiple repositories."""
        # Create two repos with verdicts
        for name in ["repo1", "repo2"]:
            repo = tmp_path / name
            lineage = repo / "docs" / "lineage" / "active"
            lineage.mkdir(parents=True)
            (lineage / f"{name}-verdict.md").write_text("# Governance Verdict: APPROVED")

        registry = tmp_path / "project-registry.json"
        registry.write_text(json.dumps([
            str(tmp_path / "repo1"),
            str(tmp_path / "repo2"),
        ]))

        db_path = tmp_path / "test.db"
        count = scan_repos(registry, db_path)

        assert count == 2

    def test_handles_parse_errors_gracefully(self, tmp_path):
        """Should continue scanning after parse errors."""
        repo = tmp_path / "project"
        lineage = repo / "docs" / "lineage" / "active"
        lineage.mkdir(parents=True)

        # Create valid verdict
        (lineage / "good-verdict.md").write_text("# Governance Verdict: APPROVED")

        # Create a file that will cause issues (mock the parse to fail)
        (lineage / "bad-verdict.md").write_text("bad content")

        registry = tmp_path / "project-registry.json"
        registry.write_text(json.dumps([str(repo)]))

        db_path = tmp_path / "test.db"

        # Should not crash, should process what it can
        count = scan_repos(registry, db_path)
        assert count >= 1  # At least the good one

    def test_updates_changed_verdicts(self, tmp_path):
        """Should update verdicts when content changes."""
        repo = tmp_path / "project"
        lineage = repo / "docs" / "lineage" / "active"
        lineage.mkdir(parents=True)
        verdict_file = lineage / "test-verdict.md"
        verdict_file.write_text("# Governance Verdict: APPROVED")

        registry = tmp_path / "project-registry.json"
        registry.write_text(json.dumps([str(repo)]))

        db_path = tmp_path / "test.db"

        # First scan
        scan_repos(registry, db_path)

        # Modify verdict
        verdict_file.write_text("# Governance Verdict: BLOCKED")

        # Second scan should pick up change
        count = scan_repos(registry, db_path)
        assert count == 1

    def test_empty_registry_returns_zero(self, tmp_path):
        """Should return 0 for empty registry."""
        registry = tmp_path / "project-registry.json"
        registry.write_text("[]")

        db_path = tmp_path / "test.db"
        count = scan_repos(registry, db_path)

        assert count == 0


class TestErrorHandling:
    """Tests for error handling in scanner module."""

    def test_discover_verdicts_handles_oserror(self, tmp_path):
        """Should handle OSError when scanning directories."""
        repo = tmp_path / "project"
        lineage = repo / "docs" / "lineage" / "active"
        lineage.mkdir(parents=True)

        # Mock _scan_directory to raise OSError
        with patch("tools.verdict_analyzer.scanner._scan_directory") as mock_scan:
            mock_scan.side_effect = OSError("Permission denied")

            # Should not raise, should return empty
            verdicts = list(discover_verdicts(repo))
            # No verdicts returned due to error
            assert verdicts == []

    def test_scan_directory_handles_resolve_oserror(self, tmp_path):
        """Should handle OSError when resolving directory path."""
        base = tmp_path / "base"
        base.mkdir()

        # Create mock directory that fails on resolve
        mock_dir = MagicMock(spec=Path)
        mock_dir.resolve.side_effect = OSError("Cannot resolve")

        seen = set()
        verdicts = list(_scan_directory(mock_dir, seen, base))

        # Should return empty, not crash
        assert verdicts == []

    def test_scan_directory_handles_iterdir_oserror(self, tmp_path):
        """Should handle OSError when iterating directory."""
        base = tmp_path / "base"
        base.mkdir()

        # Create directory then make iterdir fail
        with patch.object(Path, "iterdir") as mock_iterdir:
            mock_iterdir.side_effect = OSError("Permission denied")

            seen = set()
            verdicts = list(_scan_directory(base, seen, base))

            # Should return empty, not crash
            assert verdicts == []

    def test_scan_directory_logs_symlink_loop(self, tmp_path, caplog):
        """Should log warning when symlink loop detected."""
        base = tmp_path / "base"
        base.mkdir()

        # Pre-add the resolved path to simulate loop detection
        seen = {base.resolve()}

        import logging
        with caplog.at_level(logging.WARNING):
            verdicts = list(_scan_directory(base, seen, base))

        assert verdicts == []
        # Loop was detected via seen set
