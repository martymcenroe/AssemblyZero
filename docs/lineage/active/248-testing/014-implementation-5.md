# File: tests/unit/test_open_questions_loop.py

```python
"""Unit tests for Issue #248 open questions loop behavior.

Tests the new open questions handling:
- Post-review status parsing
- Loop routing logic
- HUMAN_REQUIRED escalation
- Max iterations safety
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch


class TestOpenQuestionsStatusParsing:
    """Tests for _check_open_questions_status function."""

    def test_returns_none_when_no_questions(self):
        """No Open Questions section returns NONE."""
        from agentos.workflows.requirements.nodes.review import _check_open_questions_status

        draft = "# LLD\n## Implementation\nDetails."
        verdict = "APPROVED"

        result = _check_open_questions_status(draft, verdict)
        assert result == "NONE"

    def test_returns_resolved_when_all_answered(self):
        """All questions answered returns RESOLVED."""
        from agentos.workflows.requirements.nodes.review import _check_open_questions_status

        draft = """# LLD
### Open Questions
- [ ] Question 1?
"""
        verdict = """## Open Questions Resolved
- [x] ~~Question 1?~~ **RESOLVED: Answer here.**
"""
        result = _check_open_questions_status(draft, verdict)
        assert result == "RESOLVED"

    def test_returns_human_required_when_marked(self):
        """HUMAN REQUIRED in verdict returns HUMAN_REQUIRED."""
        from agentos.workflows.requirements.nodes.review import _check_open_questions_status

        draft = """# LLD
### Open Questions
- [ ] Business question?
"""
        verdict = "This needs HUMAN REQUIRED decision from stakeholders."

        result = _check_open_questions_status(draft, verdict)
        assert result == "HUMAN_REQUIRED"

    def test_returns_unanswered_when_not_addressed(self):
        """Questions not addressed returns UNANSWERED."""
        from agentos.workflows.requirements.nodes.review import _check_open_questions_status

        draft = """# LLD
### Open Questions
- [ ] Ignored question?
"""
        verdict = "APPROVED: Looks good overall."

        result = _check_open_questions_status(draft, verdict)
        assert result == "UNANSWERED"


class TestDraftHasOpenQuestions:
    """Tests for _draft_has_open_questions function."""

    def test_empty_content(self):
        """Empty content returns False."""
        from agentos.workflows.requirements.nodes.review import _draft_has_open_questions

        assert not _draft_has_open_questions("")

    def test_no_open_questions_section(self):
        """No Open Questions section returns False."""
        from agentos.workflows.requirements.nodes.review import _draft_has_open_questions

        content = "# LLD\n## Implementation"
        assert not _draft_has_open_questions(content)

    def test_all_checked_questions(self):
        """All checked questions returns False."""
        from agentos.workflows.requirements.nodes.review import _draft_has_open_questions

        content = """# LLD
### Open Questions
- [x] Resolved 1
- [x] Resolved 2
"""
        assert not _draft_has_open_questions(content)

    def test_unchecked_questions(self):
        """Unchecked questions returns True."""
        from agentos.workflows.requirements.nodes.review import _draft_has_open_questions

        content = """# LLD
### Open Questions
- [ ] Unresolved
- [x] Resolved
"""
        assert _draft_has_open_questions(content)

    def test_nested_heading_format(self):
        """Works with different heading levels."""
        from agentos.workflows.requirements.nodes.review import _draft_has_open_questions

        content = """# LLD
## Open Questions
- [ ] Question
"""
        assert _draft_has_open_questions(content)


class TestVerdictHasHumanRequired:
    """Tests for _verdict_has_human_required function."""

    def test_human_required_uppercase(self):
        """Detects HUMAN REQUIRED."""
        from agentos.workflows.requirements.nodes.review import _verdict_has_human_required

        assert _verdict_has_human_required("HUMAN REQUIRED")

    def test_human_required_mixed_case(self):
        """Detects Human Required."""
        from agentos.workflows.requirements.nodes.review import _verdict_has_human_required

        assert _verdict_has_human_required("Human Required")

    def test_human_required_with_markdown(self):
        """Detects **HUMAN REQUIRED**."""
        from agentos.workflows.requirements.nodes.review import _verdict_has_human_required

        assert _verdict_has_human_required("**HUMAN REQUIRED**")

    def test_requires_human(self):
        """Detects REQUIRES HUMAN."""
        from agentos.workflows.requirements.nodes.review import _verdict_has_human_required

        assert _verdict_has_human_required("This REQUIRES HUMAN input")

    def test_needs_human_decision(self):
        """Detects NEEDS HUMAN DECISION."""
        from agentos.workflows.requirements.nodes.review import _verdict_has_human_required

        assert _verdict_has_human_required("NEEDS HUMAN DECISION")

    def test_escalate_to_human(self):
        """Detects ESCALATE TO HUMAN."""
        from agentos.workflows.requirements.nodes.review import _verdict_has_human_required

        assert _verdict_has_human_required("ESCALATE TO HUMAN")

    def test_normal_verdict(self):
        """Normal verdict returns False."""
        from agentos.workflows.requirements.nodes.review import _verdict_has_human_required

        assert not _verdict_has_human_required("APPROVED: All good")
        assert not _verdict_has_human_required("BLOCKED: Missing tests")


class TestVerdictHasResolvedQuestions:
    """Tests for _verdict_has_resolved_questions function."""

    def test_with_resolved_section(self):
        """Detects resolved questions in proper section."""
        from agentos.workflows.requirements.nodes.review import _verdict_has_resolved_questions

        verdict = """## Open Questions Resolved
- [x] ~~Question~~ **RESOLVED: Answer.**
"""
        assert _verdict_has_resolved_questions(verdict)

    def test_without_resolved_section(self):
        """Returns False when no resolved section."""
        from agentos.workflows.requirements.nodes.review import _verdict_has_resolved_questions

        verdict = "APPROVED: No questions to resolve."
        assert not _verdict_has_resolved_questions(verdict)

    def test_resolved_keyword_in_verdict(self):
        """Detects RESOLVED: keyword anywhere."""
        from agentos.workflows.requirements.nodes.review import _verdict_has_resolved_questions

        verdict = "The question was RESOLVED: Use Redis."
        assert _verdict_has_resolved_questions(verdict)


class TestRouteAfterReviewOpenQuestions:
    """Tests for route_after_review with open questions."""

    def test_human_required_forces_gate(self):
        """HUMAN_REQUIRED forces human gate even when disabled."""
        from agentos.workflows.requirements.graph import route_after_review

        state = {
            "error_message": "",
            "config_gates_verdict": False,
            "lld_status": "APPROVED",
            "open_questions_status": "HUMAN_REQUIRED",
            "iteration_count": 1,
            "max_iterations": 20,
        }

        assert route_after_review(state) == "N4_human_gate_verdict"

    def test_unanswered_loops_to_drafter(self):
        """UNANSWERED loops back to drafter."""
        from agentos.workflows.requirements.graph import route_after_review

        state = {
            "error_message": "",
            "config_gates_verdict": False,
            "lld_status": "APPROVED",
            "open_questions_status": "UNANSWERED",
            "iteration_count": 1,
            "max_iterations": 20,
        }

        assert route_after_review(state) == "N1_generate_draft"

    def test_unanswered_at_max_iterations_goes_to_gate(self):
        """UNANSWERED at max iterations goes to human gate."""
        from agentos.workflows.requirements.graph import route_after_review

        state = {
            "error_message": "",
            "config_gates_verdict": False,
            "lld_status": "APPROVED",
            "open_questions_status": "UNANSWERED",
            "iteration_count": 20,
            "max_iterations": 20,
        }

        assert route_after_review(state) == "N4_human_gate_verdict"

    def test_resolved_proceeds_to_finalize(self):
        """RESOLVED with APPROVED proceeds to finalize."""
        from agentos.workflows.requirements.graph import route_after_review

        state = {
            "error_message": "",
            "config_gates_verdict": False,
            "lld_status": "APPROVED",
            "open_questions_status": "RESOLVED",
            "iteration_count": 1,
            "max_iterations": 20,
        }

        assert route_after_review(state) == "N5_finalize"

    def test_none_status_normal_routing(self):
        """NONE status uses normal routing."""
        from agentos.workflows.requirements.graph import route_after_review

        state = {
            "error_message": "",
            "config_gates_verdict": False,
            "lld_status": "APPROVED",
            "open_questions_status": "NONE",
            "iteration_count": 1,
            "max_iterations": 20,
        }

        assert route_after_review(state) == "N5_finalize"


class TestGenerateDraftNoPreValidation:
    """Tests that generate_draft no longer blocks on open questions."""

    @patch("agentos.workflows.requirements.nodes.generate_draft.get_provider")
    def test_draft_with_questions_succeeds(self, mock_get_provider, tmp_path):
        """Draft with open questions should not be blocked."""
        from agentos.workflows.requirements.nodes.generate_draft import generate_draft
        from agentos.workflows.requirements.state import create_initial_state

        mock_provider = Mock()
        mock_provider.invoke.return_value = Mock(
            success=True,
            response="""# LLD
### Open Questions
- [ ] Unchecked question 1
- [ ] Unchecked question 2
""",
            error_message=None,
        )
        mock_get_provider.return_value = mock_provider

        template_dir = tmp_path / "docs" / "templates"
        template_dir.mkdir(parents=True)
        (template_dir / "0102-feature-lld-template.md").write_text("# Template")

        state = create_initial_state(
            workflow_type="lld",
            agentos_root=str(tmp_path),
            target_repo=str(tmp_path),
            issue_number=248,
        )
        state["issue_title"] = "Test"
        state["issue_body"] = "Body"
        state["audit_dir"] = str(tmp_path / "audit")
        Path(state["audit_dir"]).mkdir(parents=True)

        result = generate_draft(state)

        # Should NOT have error message
        assert result.get("error_message", "") == ""
        # Should have the draft with unchecked questions
        assert "- [ ]" in result.get("current_draft", "")


class TestReviewSetsOpenQuestionsStatus:
    """Tests that review properly sets open_questions_status."""

    @patch("agentos.workflows.requirements.nodes.review.get_provider")
    def test_review_sets_resolved_status(self, mock_get_provider, tmp_path):
        """Review sets RESOLVED when questions answered."""
        from agentos.workflows.requirements.nodes.review import review
        from agentos.workflows.requirements.state import create_initial_state

        mock_provider = Mock()
        mock_provider.invoke.return_value = Mock(
            success=True,
            response="""## Open Questions Resolved
- [x] ~~Question~~ **RESOLVED: Answer.**

[x] **APPROVED**
""",
            error_message=None,
        )
        mock_get_provider.return_value = mock_provider

        prompt_dir = tmp_path / "docs" / "skills"
        prompt_dir.mkdir(parents=True)
        (prompt_dir / "0702c-LLD-Review-Prompt.md").write_text("# Prompt")

        state = create_initial_state(
            workflow_type="lld",
            agentos_root=str(tmp_path),
            target_repo=str(tmp_path),
            issue_number=248,
        )
        state["current_draft"] = """### Open Questions
- [ ] Question?
"""
        state["audit_dir"] = str(tmp_path / "audit")
        Path(state["audit_dir"]).mkdir(parents=True)

        result = review(state)

        assert result.get("open_questions_status") == "RESOLVED"

    @patch("agentos.workflows.requirements.nodes.review.get_provider")
    def test_review_sets_human_required_status(self, mock_get_provider, tmp_path):
        """Review sets HUMAN_REQUIRED when marked in verdict."""
        from agentos.workflows.requirements.nodes.review import review
        from agentos.workflows.requirements.state import create_initial_state

        mock_provider = Mock()
        mock_provider.invoke.return_value = Mock(
            success=True,
            response="This needs HUMAN REQUIRED decision.",
            error_message=None,
        )
        mock_get_provider.return_value = mock_provider

        prompt_dir = tmp_path / "docs" / "skills"
        prompt_dir.mkdir(parents=True)
        (prompt_dir / "0702c-LLD-Review-Prompt.md").write_text("# Prompt")

        state = create_initial_state(
            workflow_type="lld",
            agentos_root=str(tmp_path),
            target_repo=str(tmp_path),
            issue_number=248,
        )
        state["current_draft"] = """### Open Questions
- [ ] Business question?
"""
        state["audit_dir"] = str(tmp_path / "audit")
        Path(state["audit_dir"]).mkdir(parents=True)

        result = review(state)

        assert result.get("open_questions_status") == "HUMAN_REQUIRED"
```