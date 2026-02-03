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

    def test_status_blocked_when_reviewed_not_approved(self, tmp_path):
        """Test status is 'blocked' when has_gemini_review but not approved."""
        from agentos.workflows.requirements.audit import update_lld_status, load_lld_tracking

        update_lld_status(
            issue_number=42,
            lld_path="docs/lld/active/LLD-042.md",
            review_info={
                "has_gemini_review": True,
                "final_verdict": "BLOCKED",
                "review_count": 1,
            },
            target_repo=tmp_path,
        )

        tracking = load_lld_tracking(tmp_path)
        assert tracking["issues"]["42"]["status"] == "blocked"


class TestResolveRootsValidation:
    """Tests for resolve_roots validation."""

    def test_raises_for_empty_agentos_root(self, tmp_path):
        """Test raises ValueError for empty agentos_root."""
        from agentos.workflows.requirements.audit import resolve_roots

        with pytest.raises(ValueError) as exc_info:
            resolve_roots(
                agentos_root="",
                target_repo=str(tmp_path),
            )

        assert "agentos_root" in str(exc_info.value)

    def test_raises_for_whitespace_agentos_root(self, tmp_path):
        """Test raises ValueError for whitespace-only agentos_root."""
        from agentos.workflows.requirements.audit import resolve_roots

        with pytest.raises(ValueError) as exc_info:
            resolve_roots(
                agentos_root="   ",
                target_repo=str(tmp_path),
            )

        assert "agentos_root" in str(exc_info.value)

    def test_raises_for_empty_target_repo(self, tmp_path):
        """Test raises ValueError for empty target_repo."""
        from agentos.workflows.requirements.audit import resolve_roots

        with pytest.raises(ValueError) as exc_info:
            resolve_roots(
                agentos_root=str(tmp_path),
                target_repo="",
            )

        assert "target_repo" in str(exc_info.value)


class TestNextFileNumberEdgeCases:
    """Tests for next_file_number edge cases."""

    def test_returns_1_for_nonexistent_dir(self, tmp_path):
        """Test returns 1 for non-existent directory."""
        from agentos.workflows.requirements.audit import next_file_number

        nonexistent = tmp_path / "nonexistent"
        num = next_file_number(nonexistent)

        assert num == 1


class TestAssembleContextEdgeCases:
    """Tests for assemble_context edge cases."""

    def test_returns_empty_for_empty_list(self, tmp_path):
        """Test returns empty string for empty context_files list."""
        from agentos.workflows.requirements.audit import assemble_context

        context = assemble_context(context_files=[], target_repo=tmp_path)

        assert context == ""

    def test_assembles_directory_contents(self, tmp_path):
        """Test assembles files from a directory."""
        from agentos.workflows.requirements.audit import assemble_context

        # Create directory with multiple files
        ctx_dir = tmp_path / "context"
        ctx_dir.mkdir()
        (ctx_dir / "file1.md").write_text("# File 1")
        (ctx_dir / "file2.py").write_text("def func(): pass")
        (ctx_dir / "ignored.bin").write_bytes(b"\x00\x01\x02")  # Binary, should be ignored

        context = assemble_context(
            context_files=[str(ctx_dir)],
            target_repo=tmp_path,
        )

        assert "File 1" in context
        assert "def func()" in context

    def test_handles_oserror_in_directory_files(self, tmp_path):
        """Test handles OSError when reading files in directory."""
        from agentos.workflows.requirements.audit import assemble_context
        import os

        # Create directory with a file that will cause OSError
        ctx_dir = tmp_path / "context"
        ctx_dir.mkdir()

        # Create a readable file
        (ctx_dir / "readable.md").write_text("# Readable")

        # Create a file that's actually a directory (will fail to read)
        broken_file = ctx_dir / "broken.md"
        broken_file.mkdir()

        context = assemble_context(
            context_files=[str(ctx_dir)],
            target_repo=tmp_path,
        )

        # Should succeed with readable file, skip the broken one
        assert "Readable" in context

    def test_handles_file_read_oserror(self, tmp_path):
        """Test handles OSError when reading a single file."""
        from agentos.workflows.requirements.audit import assemble_context

        # Create a file path that's actually a directory
        bad_file = tmp_path / "file.md"
        bad_file.mkdir()  # Make it a directory instead of file

        context = assemble_context(
            context_files=[str(bad_file)],
            target_repo=tmp_path,
        )

        # Should return empty context since file can't be read
        assert context == ""


class TestLoadLLDTrackingErrors:
    """Tests for load_lld_tracking error handling."""

    def test_returns_empty_cache_for_json_decode_error(self, tmp_path):
        """Test returns empty cache when JSON is invalid."""
        from agentos.workflows.requirements.audit import load_lld_tracking

        status_file = tmp_path / "docs" / "lld" / "lld-status.json"
        status_file.parent.mkdir(parents=True)
        status_file.write_text("not valid json {")

        tracking = load_lld_tracking(tmp_path)

        assert tracking["issues"] == {}
        assert "version" in tracking

    def test_returns_empty_cache_for_oserror(self, tmp_path):
        """Test returns empty cache when file can't be read."""
        from agentos.workflows.requirements.audit import load_lld_tracking

        # Create a directory where the status file should be
        status_file = tmp_path / "docs" / "lld" / "lld-status.json"
        status_file.parent.mkdir(parents=True)
        status_file.mkdir()  # Directory, not file - will cause OSError

        tracking = load_lld_tracking(tmp_path)

        assert tracking["issues"] == {}


class TestUpdateLLDStatusPathHandling:
    """Tests for update_lld_status path handling."""

    def test_handles_absolute_path_outside_repo(self, tmp_path):
        """Test handles absolute path that's outside target_repo."""
        from agentos.workflows.requirements.audit import update_lld_status, load_lld_tracking

        # Use an absolute path that's not under target_repo
        other_path = tmp_path / "other-repo" / "LLD.md"
        other_path.parent.mkdir(parents=True)

        target_repo = tmp_path / "my-repo"
        target_repo.mkdir()

        update_lld_status(
            issue_number=42,
            lld_path=str(other_path),  # Absolute path outside repo
            review_info={"has_gemini_review": False},
            target_repo=target_repo,
        )

        tracking = load_lld_tracking(target_repo)
        # Path should be kept as-is since it's outside target_repo
        assert "42" in tracking["issues"]


class TestEmbedReviewEvidence:
    """Tests for embed_review_evidence function."""

    def test_updates_existing_status_field(self, tmp_path):
        """Test updates existing Status field in LLD."""
        from agentos.workflows.requirements.audit import embed_review_evidence

        lld_content = """# LLD Title

* **Status:** Draft
* **Author:** Test

## Content
"""
        result = embed_review_evidence(
            lld_content=lld_content,
            verdict="APPROVED",
            review_date="2024-01-15",
            review_count=1,
        )

        assert "Approved" in result
        assert "2024-01-15" in result

    def test_adds_review_entry_to_existing_table(self, tmp_path):
        """Test adds review entry to existing Review Summary table."""
        from agentos.workflows.requirements.audit import embed_review_evidence

        lld_content = """# LLD Title

## Content

### Review Summary

| Review | Date | Verdict | Model |
|--------|------|---------|-------|

**Final Status:** Draft
"""
        result = embed_review_evidence(
            lld_content=lld_content,
            verdict="APPROVED",
            review_date="2024-01-15",
            review_count=2,
        )

        assert "| 2 | 2024-01-15 | APPROVED |" in result

    def test_creates_review_summary_before_final_status(self, tmp_path):
        """Test creates Review Summary section before Final Status."""
        from agentos.workflows.requirements.audit import embed_review_evidence

        lld_content = """# LLD Title

## Content

**Final Status:** Draft
"""
        result = embed_review_evidence(
            lld_content=lld_content,
            verdict="APPROVED",
            review_date="2024-01-15",
            review_count=1,
        )

        assert "### Review Summary" in result
        # Review Summary should come before Final Status
        review_pos = result.find("### Review Summary")
        final_pos = result.find("**Final Status:**")
        assert review_pos < final_pos

    def test_updates_existing_final_status(self, tmp_path):
        """Test updates existing Final Status marker."""
        from agentos.workflows.requirements.audit import embed_review_evidence

        lld_content = """# LLD Title

## Content

**Final Status:** Draft
"""
        result = embed_review_evidence(
            lld_content=lld_content,
            verdict="APPROVED",
            review_date="2024-01-15",
            review_count=1,
        )

        assert "**Final Status:** APPROVED" in result

    def test_appends_final_status_if_missing(self, tmp_path):
        """Test appends Final Status if not present."""
        from agentos.workflows.requirements.audit import embed_review_evidence

        lld_content = """# LLD Title

## Content
"""
        result = embed_review_evidence(
            lld_content=lld_content,
            verdict="BLOCKED",
            review_date="2024-01-15",
            review_count=1,
        )

        assert "**Final Status:** BLOCKED" in result


class TestLoadReviewPrompt:
    """Tests for load_review_prompt function."""

    def test_loads_from_agentos_root(self, tmp_path):
        """Test prompt is loaded from agentos_root."""
        from agentos.workflows.requirements.audit import load_review_prompt

        agentos_root = tmp_path / "agentos"
        agentos_root.mkdir()
        prompt_dir = agentos_root / "docs" / "skills"
        prompt_dir.mkdir(parents=True)
        prompt_file = prompt_dir / "0702c-LLD-Review-Prompt.md"
        prompt_file.write_text("# Review Prompt\n\nInstructions here.")

        content = load_review_prompt(
            prompt_path=Path("docs/skills/0702c-LLD-Review-Prompt.md"),
            agentos_root=agentos_root,
        )

        assert "Review Prompt" in content

    def test_raises_on_missing_prompt(self, tmp_path):
        """Test raises FileNotFoundError when prompt missing."""
        from agentos.workflows.requirements.audit import load_review_prompt

        with pytest.raises(FileNotFoundError):
            load_review_prompt(
                prompt_path=Path("docs/skills/nonexistent.md"),
                agentos_root=tmp_path,
            )


class TestValidateContextPath:
    """Tests for validate_context_path function."""

    def test_resolves_relative_path(self, tmp_path):
        """Test resolves relative path to absolute."""
        from agentos.workflows.requirements.audit import validate_context_path

        # Create file
        ctx_file = tmp_path / "context.md"
        ctx_file.write_text("content")

        result = validate_context_path("context.md", tmp_path)

        assert result is not None
        assert result.is_absolute()

    def test_rejects_path_outside_repo(self, tmp_path):
        """Test rejects path outside target_repo."""
        from agentos.workflows.requirements.audit import validate_context_path

        result = validate_context_path("/etc/passwd", tmp_path)

        assert result is None

    def test_returns_none_for_nonexistent(self, tmp_path):
        """Test returns None for nonexistent file."""
        from agentos.workflows.requirements.audit import validate_context_path

        result = validate_context_path("nonexistent.md", tmp_path)

        assert result is None


class TestGenerateSlug:
    """Tests for generate_slug function."""

    def test_converts_spaces_to_hyphens(self):
        """Test converts spaces to hyphens."""
        from agentos.workflows.requirements.audit import generate_slug

        slug = generate_slug("My Feature Ideas.md")

        assert slug == "my-feature-ideas"

    def test_converts_underscores_to_hyphens(self):
        """Test converts underscores to hyphens."""
        from agentos.workflows.requirements.audit import generate_slug

        slug = generate_slug("my_feature_ideas.md")

        assert slug == "my-feature-ideas"

    def test_removes_non_alphanumeric(self):
        """Test removes non-alphanumeric characters."""
        from agentos.workflows.requirements.audit import generate_slug

        slug = generate_slug("Feature! Ideas @#$.md")

        assert slug == "feature-ideas"

    def test_collapses_multiple_hyphens(self):
        """Test collapses multiple consecutive hyphens."""
        from agentos.workflows.requirements.audit import generate_slug

        slug = generate_slug("my---feature---ideas.md")

        assert slug == "my-feature-ideas"

    def test_strips_leading_trailing_hyphens(self):
        """Test strips leading and trailing hyphens."""
        from agentos.workflows.requirements.audit import generate_slug

        slug = generate_slug("-my-feature-.md")

        assert slug == "my-feature"
