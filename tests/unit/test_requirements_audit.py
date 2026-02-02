"""Unit tests for Requirements Audit Trail.

Issue #101: Unified Requirements Workflow

Tests for:
- Unified audit directory creation
- Sequential file numbering
- Audit file saving
- Path resolution (cross-repo)
- Finalization (issue filing vs LLD saving)
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import tempfile
import shutil


class TestCreateAuditDir:
    """Tests for create_audit_dir function."""

    def test_creates_issue_audit_dir(self, tmp_path):
        """Test creating audit directory for issue workflow."""
        from agentos.workflows.requirements.audit import create_audit_dir

        audit_dir = create_audit_dir(
            workflow_type="issue",
            slug="my-feature",
            target_repo=tmp_path,
        )

        assert audit_dir.exists()
        assert audit_dir.name == "my-feature"
        assert "lineage" in str(audit_dir)
        assert "active" in str(audit_dir)

    def test_creates_lld_audit_dir(self, tmp_path):
        """Test creating audit directory for LLD workflow."""
        from agentos.workflows.requirements.audit import create_audit_dir

        audit_dir = create_audit_dir(
            workflow_type="lld",
            issue_number=42,
            target_repo=tmp_path,
        )

        assert audit_dir.exists()
        assert "42-lld" in audit_dir.name
        assert "lineage" in str(audit_dir)

    def test_creates_parent_dirs(self, tmp_path):
        """Test that parent directories are created."""
        from agentos.workflows.requirements.audit import create_audit_dir

        audit_dir = create_audit_dir(
            workflow_type="lld",
            issue_number=99,
            target_repo=tmp_path,
        )

        # Parent dirs should be created
        assert audit_dir.parent.exists()


class TestNextFileNumber:
    """Tests for next_file_number function."""

    def test_returns_1_for_empty_dir(self, tmp_path):
        """Test returns 1 for empty directory."""
        from agentos.workflows.requirements.audit import next_file_number

        num = next_file_number(tmp_path)
        assert num == 1

    def test_returns_next_after_existing_files(self, tmp_path):
        """Test returns max + 1 after existing numbered files."""
        from agentos.workflows.requirements.audit import next_file_number

        # Create some numbered files
        (tmp_path / "001-issue.md").write_text("content")
        (tmp_path / "002-draft.md").write_text("content")
        (tmp_path / "003-verdict.md").write_text("content")

        num = next_file_number(tmp_path)
        assert num == 4

    def test_handles_non_sequential_numbers(self, tmp_path):
        """Test handles gaps in numbering."""
        from agentos.workflows.requirements.audit import next_file_number

        (tmp_path / "001-issue.md").write_text("content")
        (tmp_path / "005-draft.md").write_text("content")

        num = next_file_number(tmp_path)
        assert num == 6

    def test_ignores_non_numbered_files(self, tmp_path):
        """Test ignores files without NNN- prefix."""
        from agentos.workflows.requirements.audit import next_file_number

        (tmp_path / "001-draft.md").write_text("content")
        (tmp_path / "readme.md").write_text("content")
        (tmp_path / "notes.txt").write_text("content")

        num = next_file_number(tmp_path)
        assert num == 2


class TestSaveAuditFile:
    """Tests for save_audit_file function."""

    def test_saves_with_correct_numbering(self, tmp_path):
        """Test saves file with NNN- prefix."""
        from agentos.workflows.requirements.audit import save_audit_file

        path = save_audit_file(
            audit_dir=tmp_path,
            number=5,
            suffix="draft.md",
            content="# Draft Content",
        )

        assert path.name == "005-draft.md"
        assert path.read_text() == "# Draft Content"

    def test_saves_in_correct_directory(self, tmp_path):
        """Test saves in specified directory."""
        from agentos.workflows.requirements.audit import save_audit_file

        path = save_audit_file(
            audit_dir=tmp_path,
            number=1,
            suffix="issue.md",
            content="content",
        )

        assert path.parent == tmp_path


class TestGetAuditDirPath:
    """Tests for get_audit_dir_path function."""

    def test_issue_workflow_path(self, tmp_path):
        """Test path construction for issue workflow."""
        from agentos.workflows.requirements.audit import get_audit_dir_path

        path = get_audit_dir_path(
            workflow_type="issue",
            slug="my-feature",
            target_repo=tmp_path,
        )

        assert "lineage" in str(path)
        assert "active" in str(path)
        assert path.name == "my-feature"

    def test_lld_workflow_path(self, tmp_path):
        """Test path construction for LLD workflow."""
        from agentos.workflows.requirements.audit import get_audit_dir_path

        path = get_audit_dir_path(
            workflow_type="lld",
            issue_number=42,
            target_repo=tmp_path,
        )

        assert "lineage" in str(path)
        assert "42-lld" in str(path)


class TestResolveRoots:
    """Tests for resolve_roots function."""

    def test_explicit_agentos_root(self, tmp_path):
        """Test with explicit AgentOS root."""
        from agentos.workflows.requirements.audit import resolve_roots

        agentos_root, target_repo = resolve_roots(
            agentos_root=str(tmp_path / "agentos"),
            target_repo=str(tmp_path / "repo"),
        )

        assert agentos_root == tmp_path / "agentos"
        assert target_repo == tmp_path / "repo"

    def test_paths_are_resolved(self, tmp_path):
        """Test that paths are resolved to absolute paths."""
        from agentos.workflows.requirements.audit import resolve_roots

        agentos_root, target_repo = resolve_roots(
            agentos_root=str(tmp_path / "agentos"),
            target_repo=str(tmp_path / "repo"),
        )

        assert agentos_root.is_absolute()
        assert target_repo.is_absolute()


class TestLoadTemplateFromAgentOS:
    """Tests for load_template function with cross-repo paths."""

    def test_loads_from_agentos_root(self, tmp_path):
        """Test template is loaded from agentos_root, not target_repo."""
        from agentos.workflows.requirements.audit import load_template

        # Set up agentos_root with template
        agentos_root = tmp_path / "agentos"
        agentos_root.mkdir()
        template_dir = agentos_root / "docs" / "templates"
        template_dir.mkdir(parents=True)
        template_file = template_dir / "0102-feature-lld-template.md"
        template_file.write_text("# LLD Template\n\n{{CONTENT}}")

        # Target repo should NOT be used
        target_repo = tmp_path / "other-repo"
        target_repo.mkdir()

        content = load_template(
            template_path=Path("docs/templates/0102-feature-lld-template.md"),
            agentos_root=agentos_root,
        )

        assert "LLD Template" in content

    def test_raises_on_missing_template(self, tmp_path):
        """Test raises FileNotFoundError when template missing."""
        from agentos.workflows.requirements.audit import load_template

        with pytest.raises(FileNotFoundError):
            load_template(
                template_path=Path("docs/templates/nonexistent.md"),
                agentos_root=tmp_path,
            )


class TestSaveOutputToTargetRepo:
    """Tests for save functions that write to target_repo."""

    def test_lld_saved_to_target_repo(self, tmp_path):
        """Test LLD is saved to target_repo/docs/lld/active/."""
        from agentos.workflows.requirements.audit import save_final_lld

        target_repo = tmp_path / "my-project"
        target_repo.mkdir()

        # AgentOS root is different
        agentos_root = tmp_path / "agentos"
        agentos_root.mkdir()

        path = save_final_lld(
            issue_number=42,
            lld_content="# LLD Content",
            target_repo=target_repo,
        )

        assert target_repo in path.parents or path.parent.parent.parent == target_repo
        assert "docs" in str(path)
        assert "lld" in str(path)
        assert path.exists()
        assert "LLD Content" in path.read_text()

    def test_lld_not_saved_to_agentos_root(self, tmp_path):
        """Test LLD is NOT saved to AgentOS root."""
        from agentos.workflows.requirements.audit import save_final_lld

        target_repo = tmp_path / "my-project"
        target_repo.mkdir()

        agentos_root = tmp_path / "agentos"
        agentos_root.mkdir()

        save_final_lld(
            issue_number=42,
            lld_content="# LLD Content",
            target_repo=target_repo,
        )

        # Should NOT create anything in agentos_root
        agentos_lld_dir = agentos_root / "docs" / "lld" / "active"
        assert not agentos_lld_dir.exists()


class TestAssembleContext:
    """Tests for assemble_context function."""

    def test_assembles_multiple_files(self, tmp_path):
        """Test assembling context from multiple files."""
        from agentos.workflows.requirements.audit import assemble_context

        # Create context files
        (tmp_path / "file1.py").write_text("def hello(): pass")
        (tmp_path / "file2.md").write_text("# Documentation")

        context = assemble_context(
            context_files=[
                str(tmp_path / "file1.py"),
                str(tmp_path / "file2.md"),
            ],
            target_repo=tmp_path,
        )

        assert "def hello()" in context
        assert "Documentation" in context

    def test_skips_missing_files(self, tmp_path):
        """Test skips files that don't exist."""
        from agentos.workflows.requirements.audit import assemble_context

        (tmp_path / "exists.py").write_text("content")

        context = assemble_context(
            context_files=[
                str(tmp_path / "exists.py"),
                str(tmp_path / "missing.py"),
            ],
            target_repo=tmp_path,
        )

        assert "content" in context

    def test_validates_paths_within_repo(self, tmp_path):
        """Test rejects paths outside target_repo."""
        from agentos.workflows.requirements.audit import assemble_context

        context = assemble_context(
            context_files=["/etc/passwd"],
            target_repo=tmp_path,
        )

        # Should skip the invalid path and return empty or warning
        assert "/etc/passwd" not in context


class TestUpdateLLDStatus:
    """Tests for LLD status tracking."""

    def test_updates_status_file(self, tmp_path):
        """Test updates lld-status.json."""
        from agentos.workflows.requirements.audit import update_lld_status, load_lld_tracking

        update_lld_status(
            issue_number=42,
            lld_path="docs/lld/active/LLD-042.md",
            review_info={
                "has_gemini_review": True,
                "final_verdict": "APPROVED",
                "review_count": 1,
            },
            target_repo=tmp_path,
        )

        tracking = load_lld_tracking(tmp_path)
        assert "42" in tracking["issues"]
        assert tracking["issues"]["42"]["status"] == "approved"

    def test_creates_status_file_if_missing(self, tmp_path):
        """Test creates lld-status.json if it doesn't exist."""
        from agentos.workflows.requirements.audit import update_lld_status

        status_file = tmp_path / "docs" / "lld" / "lld-status.json"
        assert not status_file.exists()

        update_lld_status(
            issue_number=1,
            lld_path="docs/lld/active/LLD-001.md",
            review_info={"has_gemini_review": False},
            target_repo=tmp_path,
        )

        assert status_file.exists()
