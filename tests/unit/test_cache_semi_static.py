"""Tests for Issue #490: Cache semi-static content (repo_structure).

Verifies that get_repo_structure() is computed once in load_input / analyze_codebase
and read from state in generate_draft / generate_spec, with inline fallback.
"""

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Test: load_input populates repo_structure
# ---------------------------------------------------------------------------

class TestLoadInputPopulatesRepoStructure:
    """Verify load_input computes repo_structure and returns it in state."""

    def test_lld_workflow_populates_repo_structure(self, tmp_path):
        """load_input for LLD workflow should include repo_structure in output."""
        from assemblyzero.workflows.requirements.nodes.load_input import load_input

        # Create a minimal repo dir
        target_repo = tmp_path / "repo"
        target_repo.mkdir()
        (target_repo / "src").mkdir()
        (target_repo / "tests").mkdir()

        state = {
            "workflow_type": "lld",
            "issue_number": 42,
            "target_repo": str(target_repo),
            "assemblyzero_root": str(tmp_path),
            "config_mock_mode": True,
            "context_files": [],
        }

        result = load_input(state)

        assert "repo_structure" in result
        assert isinstance(result["repo_structure"], str)
        assert len(result["repo_structure"]) > 0

    def test_issue_workflow_populates_repo_structure(self, tmp_path):
        """load_input for issue workflow should include repo_structure in output."""
        from assemblyzero.workflows.requirements.nodes.load_input import load_input

        target_repo = tmp_path / "repo"
        target_repo.mkdir()
        (target_repo / "src").mkdir()

        brief_file = target_repo / "brief.md"
        brief_file.write_text("# My Brief\n\nSome content", encoding="utf-8")

        state = {
            "workflow_type": "issue",
            "brief_file": str(brief_file),
            "target_repo": str(target_repo),
            "assemblyzero_root": str(tmp_path),
            "config_mock_mode": False,
        }

        result = load_input(state)

        assert "repo_structure" in result
        assert isinstance(result["repo_structure"], str)


# ---------------------------------------------------------------------------
# Test: generate_draft uses state repo_structure
# ---------------------------------------------------------------------------

class TestGenerateDraftUsesStateRepoStructure:
    """Verify generate_draft reads repo_structure from state instead of recomputing."""

    @patch("assemblyzero.workflows.requirements.nodes.generate_draft.get_repo_structure")
    @patch("assemblyzero.workflows.requirements.nodes.generate_draft.get_provider")
    def test_initial_draft_uses_state_repo_structure(
        self, mock_get_provider, mock_get_repo_structure, tmp_path
    ):
        """When repo_structure is in state, generate_draft should NOT call get_repo_structure."""
        from assemblyzero.workflows.requirements.nodes.generate_draft import _build_prompt

        cached_structure = "src/\ntests/\n  unit/"

        state = {
            "workflow_type": "lld",
            "target_repo": str(tmp_path),
            "issue_number": 42,
            "issue_title": "Test Issue",
            "issue_body": "Body",
            "context_content": "",
            "current_draft": "",
            "verdict_history": [],
            "user_feedback": "",
            "validation_errors": [],
            "repo_structure": cached_structure,
        }

        prompt = _build_prompt(state, "template content", "lld")

        # The cached structure should appear in the prompt
        assert cached_structure in prompt
        # get_repo_structure should NOT have been called
        mock_get_repo_structure.assert_not_called()

    @patch("assemblyzero.workflows.requirements.nodes.generate_draft.get_repo_structure")
    def test_fallback_when_missing(self, mock_get_repo_structure, tmp_path):
        """When repo_structure is NOT in state, should fall back to inline call."""
        from assemblyzero.workflows.requirements.nodes.generate_draft import _build_prompt

        mock_get_repo_structure.return_value = "fallback_structure/"

        state = {
            "workflow_type": "lld",
            "target_repo": str(tmp_path),
            "issue_number": 42,
            "issue_title": "Test Issue",
            "issue_body": "Body",
            "context_content": "",
            "current_draft": "",
            "verdict_history": [],
            "user_feedback": "",
            "validation_errors": [],
            # No repo_structure key
        }

        prompt = _build_prompt(state, "template content", "lld")

        assert "fallback_structure/" in prompt
        mock_get_repo_structure.assert_called_once()


# ---------------------------------------------------------------------------
# Test: analyze_codebase populates repo_structure
# ---------------------------------------------------------------------------

class TestAnalyzeCodebasePopulatesRepoStructure:
    """Verify analyze_codebase computes repo_structure and returns it."""

    def test_analyze_codebase_returns_repo_structure(self, tmp_path):
        """analyze_codebase should include repo_structure in its return dict."""
        from assemblyzero.workflows.implementation_spec.nodes.analyze_codebase import (
            analyze_codebase,
        )

        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / "assemblyzero").mkdir()
        (repo_root / "tests").mkdir()

        state = {
            "repo_root": str(repo_root),
            "lld_content": "# LLD\n\nSome content",
            "files_to_modify": [],
        }

        result = analyze_codebase(state)

        assert "repo_structure" in result
        assert isinstance(result["repo_structure"], str)


# ---------------------------------------------------------------------------
# Test: generate_spec uses state repo_structure in revision
# ---------------------------------------------------------------------------

class TestGenerateSpecUsesStateRepoStructure:
    """Verify _build_revision_prompt reads repo_structure from state."""

    @patch(
        "assemblyzero.workflows.implementation_spec.nodes.generate_spec.get_repo_structure"
    )
    def test_revision_uses_cached_repo_structure(
        self, mock_get_repo_structure, tmp_path
    ):
        """_build_revision_prompt should use state repo_structure, not recompute."""
        from assemblyzero.workflows.implementation_spec.nodes.generate_spec import (
            _build_revision_prompt,
        )

        cached_structure = "assemblyzero/\n  core/\n  workflows/"

        prompt = _build_revision_prompt(
            lld_content="# LLD",
            current_state={},
            patterns=[],
            template="template",
            issue_number=42,
            existing_draft="# Draft",
            review_feedback="Fix something",
            completeness_issues=["Missing excerpt for file.py"],
            repo_root=str(tmp_path),
            files_to_modify=[],
            repo_structure=cached_structure,
        )

        assert cached_structure in prompt
        mock_get_repo_structure.assert_not_called()

    @patch(
        "assemblyzero.workflows.implementation_spec.nodes.generate_spec.get_repo_structure"
    )
    def test_revision_falls_back_when_missing(
        self, mock_get_repo_structure, tmp_path
    ):
        """Without cached repo_structure, should fall back to get_repo_structure."""
        from assemblyzero.workflows.implementation_spec.nodes.generate_spec import (
            _build_revision_prompt,
        )

        mock_get_repo_structure.return_value = "fallback/"

        prompt = _build_revision_prompt(
            lld_content="# LLD",
            current_state={},
            patterns=[],
            template="template",
            issue_number=42,
            existing_draft="# Draft",
            review_feedback="Fix something",
            completeness_issues=["Missing excerpt"],
            repo_root=str(tmp_path),
            files_to_modify=[],
        )

        assert "fallback/" in prompt
        mock_get_repo_structure.assert_called_once()
