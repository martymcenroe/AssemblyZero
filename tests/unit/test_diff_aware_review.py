"""Tests for Issue #491: Diff-aware review.

Verifies that:
1. First review sends full draft
2. Revision review sends diff when changes are small
3. Large diffs fall back to full draft
4. previous_draft is preserved across iterations
"""

import difflib

import pytest


class TestDiffAwareReviewContent:
    """Verify _build_diff_aware_content logic in review.py."""

    def test_first_review_sends_full(self):
        """Without previous_draft, should send full draft."""
        from assemblyzero.workflows.requirements.nodes.review import (
            _build_review_content,
        )

        content = _build_review_content(
            current_draft="# Draft\n\nFull content here",
            review_prompt="Review instructions",
            previous_draft="",
        )

        assert "Full content here" in content
        # Should NOT contain diff markers
        assert "@@" not in content

    def test_revision_review_sends_diff(self):
        """With previous_draft and small changes, should send diff format."""
        from assemblyzero.workflows.requirements.nodes.review import (
            _build_review_content,
        )

        previous = "# Draft\n\nLine 1\nLine 2\nLine 3\nLine 4\nLine 5\n" * 10
        current = previous.replace("Line 2", "Line 2 (modified)")

        content = _build_review_content(
            current_draft=current,
            review_prompt="Review instructions",
            previous_draft=previous,
        )

        # Should contain diff indicators
        assert "CHANGES SINCE LAST REVIEW" in content or "unified diff" in content.lower() or "---" in content

    def test_large_diff_sends_full(self):
        """When >20% of content changed, should send full draft."""
        from assemblyzero.workflows.requirements.nodes.review import (
            _build_review_content,
        )

        previous = "# Draft\n\nOriginal content\n" * 5
        # Change >50% of content
        current = "# Draft\n\nCompletely new content\n" * 5

        content = _build_review_content(
            current_draft=current,
            review_prompt="Review instructions",
            previous_draft=previous,
        )

        # Should contain the full current draft
        assert "Completely new content" in content


class TestPreviousDraftPreserved:
    """Verify generate_draft saves current_draft as previous_draft."""

    def test_generate_draft_returns_previous_draft(self):
        """generate_draft should return previous_draft = old current_draft."""
        from assemblyzero.workflows.requirements.nodes.generate_draft import (
            generate_draft,
        )
        from unittest.mock import patch, MagicMock

        mock_provider = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.response = "# New Draft\n\nNew content"
        mock_result.input_tokens = 100
        mock_result.output_tokens = 50
        mock_result.cost_usd = 0.01
        mock_provider.invoke.return_value = mock_result

        state = {
            "workflow_type": "lld",
            "assemblyzero_root": ".",
            "target_repo": ".",
            "config_drafter": "mock:draft",
            "config_mock_mode": True,
            "audit_dir": "/nonexistent",
            "draft_count": 1,
            "current_draft": "# Old Draft\n\nOld content",
            "verdict_history": ["REVISE"],
            "user_feedback": "",
            "iteration_count": 1,
            "issue_number": 42,
            "issue_title": "Test",
            "issue_body": "Body",
            "context_content": "",
            "validation_errors": [],
            "current_verdict": "REVISE feedback",
        }

        with patch(
            "assemblyzero.workflows.requirements.nodes.generate_draft.get_provider",
            return_value=mock_provider,
        ), patch(
            "assemblyzero.workflows.requirements.nodes.generate_draft.load_template",
            return_value="template",
        ):
            result = generate_draft(state)

        assert "previous_draft" in result
        assert result["previous_draft"] == "# Old Draft\n\nOld content"


class TestImplSpecPreviousDraft:
    """Verify generate_spec saves spec_draft as previous_spec_draft."""

    def test_generate_spec_returns_previous_spec_draft(self):
        """generate_spec should return previous_spec_draft = old spec_draft."""
        from assemblyzero.workflows.implementation_spec.nodes.generate_spec import (
            generate_spec,
        )
        from unittest.mock import patch, MagicMock

        mock_provider = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.response = "# New Spec\n\nNew content"
        mock_result.input_tokens = 100
        mock_result.output_tokens = 50
        mock_result.cost_usd = 0.01
        mock_provider.invoke.return_value = mock_result

        state = {
            "assemblyzero_root": ".",
            "repo_root": ".",
            "config_drafter": "mock:draft",
            "config_mock_mode": True,
            "config_reviewer": "mock:review",
            "audit_dir": "",
            "issue_number": 42,
            "lld_content": "# LLD",
            "current_state_snapshots": {},
            "pattern_references": [],
            "files_to_modify": [],
            "spec_draft": "# Old Spec\n\nOld content",
            "review_feedback": "Fix something",
            "completeness_issues": [],
            "review_iteration": 0,
            "max_iterations": 3,
            "project_context": "",
            "import_dependencies": "",
            "cost_budget_usd": 0.0,
        }

        with patch(
            "assemblyzero.workflows.implementation_spec.nodes.generate_spec.get_provider",
            return_value=mock_provider,
        ), patch(
            "assemblyzero.workflows.implementation_spec.nodes.generate_spec.load_template",
            return_value="template",
        ):
            result = generate_spec(state)

        assert "previous_spec_draft" in result
        assert result["previous_spec_draft"] == "# Old Spec\n\nOld content"


class TestDiffAwareReviewSpec:
    """Verify _build_review_content in review_spec.py supports diff-aware mode."""

    def test_review_spec_first_review_sends_full(self):
        """Without previous_spec_draft, should send full spec."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            _build_review_content,
        )

        content = _build_review_content(
            spec_draft="# Spec\n\nFull spec content",
            lld_content="# LLD",
            issue_number=42,
            review_iteration=0,
        )

        assert "Full spec content" in content

    def test_review_spec_revision_sends_diff(self):
        """With previous_spec_draft and small changes, should send diff."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            _build_review_content,
        )

        previous = "# Spec\n\nLine 1\nLine 2\nLine 3\nLine 4\nLine 5\n" * 10
        current = previous.replace("Line 2", "Line 2 (fixed)")

        content = _build_review_content(
            spec_draft=current,
            lld_content="# LLD",
            issue_number=42,
            review_iteration=1,
            previous_spec_draft=previous,
        )

        # Should contain diff markers or change summary
        assert "CHANGES SINCE LAST REVIEW" in content or "---" in content
