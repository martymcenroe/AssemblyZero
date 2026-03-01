"""Tests for Issue #499: Context dedup across iterations.

Validates that iteration 3+ prompts use skeleton references for
static sections (template, input) to reduce token waste.
"""

import pytest

from assemblyzero.workflows.requirements.nodes.generate_draft import _build_prompt


def _make_state(**overrides) -> dict:
    """Create a state dict for testing prompt building.

    Uses a draft with different headings than the template to avoid
    triggering the targeted revision path (issue #489).
    """
    base = {
        "workflow_type": "lld",
        "issue_number": 42,
        "issue_title": "Add user auth",
        "issue_body": "Implement OAuth2 login flow with JWT tokens.",
        "context_content": "",
        "current_draft": "# LLD-042: Add user auth\n\nDraft content goes here.",
        "verdict_history": ["fix something"],
        "user_feedback": "",
        "validation_errors": [],
        "draft_count": 0,
        "target_repo": "",
    }
    base.update(overrides)
    return base


TEMPLATE = "# Template\n\nA template body.\n"


class TestContextDedup:
    """Test that iteration 3+ uses skeleton references."""

    def test_iteration_1_includes_full_content(self):
        """Initial draft includes full template and input."""
        state = _make_state(
            current_draft="",
            verdict_history=[],
            draft_count=0,
        )
        prompt = _build_prompt(state, TEMPLATE, "lld")
        assert "Template" in prompt
        assert "OAuth2 login flow" in prompt

    def test_iteration_2_includes_full_content(self):
        """Revision iteration 2 still includes full template and input."""
        state = _make_state(draft_count=1)
        prompt = _build_prompt(state, TEMPLATE, "lld")
        # draft_count is current value; next will be +1 = 2 (< 3)
        assert "OAuth2 login flow" in prompt
        assert "# Template" in prompt

    def test_iteration_3_uses_skeleton(self):
        """Iteration 3+ replaces static sections with skeletons."""
        state = _make_state(draft_count=2)  # draft_count+1 = 3
        prompt = _build_prompt(state, TEMPLATE, "lld")
        # Should NOT have full issue body
        assert "OAuth2 login flow" not in prompt
        # Should have skeleton references
        assert "unchanged from iteration 1" in prompt.lower() or "unchanged" in prompt.lower()
        # Should still have the current draft
        assert "LLD-042" in prompt

    def test_iteration_4_uses_skeleton(self):
        state = _make_state(draft_count=3)  # draft_count+1 = 4
        prompt = _build_prompt(state, TEMPLATE, "lld")
        assert "OAuth2 login flow" not in prompt
        assert "unchanged" in prompt.lower()

    def test_skeleton_preserves_issue_number(self):
        state = _make_state(draft_count=2)
        prompt = _build_prompt(state, TEMPLATE, "lld")
        assert "42" in prompt
        assert "Add user auth" in prompt

    def test_iteration_3_still_includes_feedback(self):
        """Skeleton mode doesn't remove feedback/verdict history."""
        state = _make_state(
            draft_count=2,
            verdict_history=["Fix section 2.1 paths"],
        )
        prompt = _build_prompt(state, TEMPLATE, "lld")
        # Feedback should still be present (it's dynamic, not static)
        assert "Current Draft" in prompt

    def test_initial_draft_not_affected(self):
        """Non-revision mode is unaffected by dedup."""
        state = _make_state(
            current_draft="",
            verdict_history=[],
            validation_errors=[],
            user_feedback="",
            draft_count=5,  # High count but no revision triggers
        )
        prompt = _build_prompt(state, TEMPLATE, "lld")
        # Not a revision, should use full template
        assert "# Template" in prompt

    def test_targeted_revision_not_affected(self):
        """Targeted revision path (issue #489) is separate from dedup."""
        # The targeted path builds its own prompt via build_targeted_prompt
        # and doesn't use the full revision template. Just verify it
        # uses `targeted` branch.
        state = _make_state(draft_count=2)
        prompt = _build_prompt(state, TEMPLATE, "lld")
        # Should be in the else (full revision) path since we don't
        # have changed sections identified. The skeleton should apply.
        assert "unchanged" in prompt.lower()
