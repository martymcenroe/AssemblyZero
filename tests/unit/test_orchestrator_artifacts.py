"""Unit tests for orchestrator artifact detection.

Issue #305: End-to-End Orchestration Workflow (Issue → Code)
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from assemblyzero.workflows.orchestrator.artifacts import (
    detect_existing_artifacts,
    get_artifact_path,
    validate_artifact,
)


class TestDetectExistingArtifacts:
    """Tests for detect_existing_artifacts (T140, T150)."""

    def test_finds_existing_lld(self, tmp_path, monkeypatch):
        """T140: Artifact detection finds LLD."""
        monkeypatch.chdir(tmp_path)

        # Create LLD file
        lld_dir = tmp_path / "docs" / "lld" / "active"
        lld_dir.mkdir(parents=True)
        lld_file = lld_dir / "LLD-305.md"
        lld_file.write_text("# 305\n## 1. Context")

        artifacts = detect_existing_artifacts(305)
        assert artifacts["lld"] is not None
        assert Path(artifacts["lld"]).name == "LLD-305.md"

    def test_finds_lld_in_done_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        done_dir = tmp_path / "docs" / "lld" / "done"
        done_dir.mkdir(parents=True)
        lld_file = done_dir / "LLD-305.md"
        lld_file.write_text("# 305\n## 1. Context")

        artifacts = detect_existing_artifacts(305)
        assert artifacts["lld"] is not None
        assert Path(artifacts["lld"]).name == "LLD-305.md"

    def test_finds_lld_with_number_prefix(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        lld_dir = tmp_path / "docs" / "lld" / "active"
        lld_dir.mkdir(parents=True)
        lld_file = lld_dir / "305-orchestration-workflow.md"
        lld_file.write_text("# 305\n## 1. Context")

        artifacts = detect_existing_artifacts(305)
        assert artifacts["lld"] is not None
        assert Path(artifacts["lld"]).name == "305-orchestration-workflow.md"

    def test_returns_none_when_no_artifacts(self, tmp_path, monkeypatch):
        """T150: Artifact detection returns None when no artifact exists."""
        monkeypatch.chdir(tmp_path)

        artifacts = detect_existing_artifacts(999)
        assert artifacts["triage"] is None
        assert artifacts["lld"] is None
        assert artifacts["spec"] is None
        assert artifacts["impl"] is None
        assert artifacts["pr"] is None

    def test_finds_triage_artifact(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        lineage_dir = tmp_path / "docs" / "lineage" / "305"
        lineage_dir.mkdir(parents=True)
        brief_file = lineage_dir / "issue-brief.md"
        brief_file.write_text("## Summary\nTest issue brief")

        artifacts = detect_existing_artifacts(305)
        assert artifacts["triage"] is not None
        assert Path(artifacts["triage"]).name == "issue-brief.md"

    def test_negative_issue_number_raises(self):
        with pytest.raises(ValueError, match="issue_number must be positive"):
            detect_existing_artifacts(-1)

    def test_empty_file_not_detected(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        lineage_dir = tmp_path / "docs" / "lineage" / "305"
        lineage_dir.mkdir(parents=True)
        brief_file = lineage_dir / "issue-brief.md"
        brief_file.write_text("")  # Empty

        artifacts = detect_existing_artifacts(305)
        assert artifacts["triage"] is None


class TestGetArtifactPath:
    def test_triage_path(self):
        path = get_artifact_path(305, "triage")
        assert path == Path("docs/lineage/305/issue-brief.md")

    def test_spec_path(self):
        path = get_artifact_path(305, "spec")
        assert path == Path("docs/lineage/305/impl-spec.md")

    def test_impl_path(self):
        path = get_artifact_path(305, "impl")
        assert path == Path("../AssemblyZero-305")

    def test_pr_raises(self):
        with pytest.raises(ValueError, match="PR artifact is a URL"):
            get_artifact_path(305, "pr")

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError, match="Unknown artifact_type"):
            get_artifact_path(305, "bogus")


class TestValidateArtifact:
    def test_valid_lld(self, tmp_path):
        lld_file = tmp_path / "test.md"
        lld_file.write_text("# LLD\n## 1. Context\nContent here")
        assert validate_artifact(lld_file, "lld") is True

    def test_invalid_lld_missing_heading(self, tmp_path):
        lld_file = tmp_path / "test.md"
        lld_file.write_text("# LLD\nSome content without proper heading")
        assert validate_artifact(lld_file, "lld") is False

    def test_nonexistent_file(self, tmp_path):
        assert validate_artifact(tmp_path / "nonexistent.md", "lld") is False

    def test_empty_file(self, tmp_path):
        empty_file = tmp_path / "empty.md"
        empty_file.write_text("")
        assert validate_artifact(empty_file, "triage") is False

    def test_impl_checks_directory(self, tmp_path):
        impl_dir = tmp_path / "worktree"
        impl_dir.mkdir()
        assert validate_artifact(impl_dir, "impl") is True

    def test_impl_nonexistent_dir(self, tmp_path):
        assert validate_artifact(tmp_path / "nonexistent", "impl") is False
