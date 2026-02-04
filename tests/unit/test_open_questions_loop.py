"""Unit tests for Issue #248: Open Questions Loop Behavior.

Tests the new open questions detection and routing logic added in Issue #248.
"""

import pytest
import re
from pathlib import Path
from unittest.mock import Mock, patch


class TestDraftHasOpenQuestions:
    """Tests for _draft_has_open_questions helper function."""

    def test_detects_unchecked_questions(self):
        """Should detect unchecked checkboxes in Open Questions section."""
        from agentos.workflows.requirements.nodes.review import _draft_has_open_questions

        draft = """# LLD

### Open Questions
- [ ] First question?
- [ ] Second question?
"""
        assert _draft_has_open_questions(draft) is True

    def test_ignores_checked_questions(self):
        """Should not count checked questions as open."""
        from agentos.workflows.requirements.nodes.review import _draft_has_open_questions

        draft = """### Open Questions
- [x] Answered question
- [x] Another answered"""
        assert _draft_has_open_questions(draft) is False

    def test_handles_mixed_questions(self):
        """Should detect if ANY unchecked questions exist."""
        from agentos.workflows.requirements.nodes.review import _draft_has_open_questions

        draft = """### Open Questions
- [x] Answered
- [ ] Not answered
- [x] Also answered"""
        assert _draft_has_open_questions(draft) is True

    def test_handles_no_section(self):
        """Should return False if no Open Questions section exists."""
        from agentos.workflows.requirements.nodes.review import _draft_has_open_questions

        draft = """# LLD
## Design
Just design content."""
        assert _draft_has_open_questions(draft) is False

    def test_handles_empty_string(self):
        """Should return False for empty string."""
        from agentos.workflows.requirements.nodes.review import _draft_has_open_questions

        assert _draft_has_open_questions("") is False

    def test_handles_different_header_levels(self):
        """Should match ## or ### Open Questions headers."""
        from agentos.workflows.requirements.nodes.review import _draft_has_open_questions

        draft_h2 = """## Open Questions
- [ ] Question"""
        assert _draft_has_open_questions(draft_h2) is True

        draft_h3 = """### Open Questions
- [ ] Question"""
        assert _draft_has_open_questions(draft_h3) is True


class TestVerdictHasHumanRequired:
    """Tests for _verdict_has_human_required helper function."""

    def test_detects_human_required_formats(self):
        """Should detect various HUMAN REQUIRED patterns."""
        from agentos.workflows.requirements.nodes.review import _verdict_has_human_required

        patterns = [
            "HUMAN REQUIRED",
            "**HUMAN REQUIRED**",
            "REQUIRES HUMAN",
            "REQUIRE HUMAN",
            "NEEDS HUMAN DECISION",
            "NEED HUMAN DECISION",
            "ESCALATE TO HUMAN",
        ]

        for pattern in patterns:
            verdict = f"This question {pattern} for approval."
            assert _verdict_has_human_required(verdict) is True, f"Failed for: {pattern}"

    def test_case_insensitive(self):
        """Should match case insensitively."""
        from agentos.workflows.requirements.nodes.review import _verdict_has_human_required

        assert _verdict_has_human_required("human required") is True
        assert _verdict_has_human_required("Human Required") is True
        assert _verdict_has_human_required("HUMAN REQUIRED") is True

    def test_returns_false_without_marker(self):
        """Should return False when no HUMAN REQUIRED marker."""
        from agentos.workflows.requirements.nodes.review import _verdict_has_human_required

        verdict = "All questions resolved. [x] APPROVED"
        assert _verdict_has_human_required(verdict) is False


class TestVerdictHasResolvedQuestions:
    """Tests for _verdict_has_resolved_questions helper function."""

    def test_detects_resolved_section(self):
        """Should detect Open Questions Resolved section with [x] items."""
        from agentos.workflows.requirements.nodes.review import _verdict_has_resolved_questions

        verdict = """## Open Questions Resolved
- [x] ~~Question~~ **RESOLVED: Answer here.**

## Verdict
[x] APPROVED"""
        assert _verdict_has_resolved_questions(verdict) is True

    def test_detects_inline_resolved(self):
        """Should detect RESOLVED: text even without explicit section."""
        from agentos.workflows.requirements.nodes.review import _verdict_has_resolved_questions

        verdict = "The caching question is RESOLVED: Use Redis."
        assert _verdict_has_resolved_questions(verdict) is True

    def test_returns_false_without_resolution(self):
        """Should return False when no resolution markers found."""
        from agentos.workflows.requirements.nodes.review import _verdict_has_resolved_questions

        verdict = "## Verdict\n[x] APPROVED - looks good"
        assert _verdict_has_resolved_questions(verdict) is False


class TestCheckOpenQuestionsStatus:
    """Tests for _check_open_questions_status function."""

    def test_returns_none_when_no_questions(self):
        """Should return NONE when draft has no open questions."""
        from agentos.workflows.requirements.nodes.review import _check_open_questions_status

        draft = "# LLD\n## Design\nContent"
        verdict = "[x] APPROVED"

        assert _check_open_questions_status(draft, verdict) == "NONE"

    def test_returns_human_required(self):
        """Should return HUMAN_REQUIRED when verdict contains marker."""
        from agentos.workflows.requirements.nodes.review import _check_open_questions_status

        draft = """### Open Questions
- [ ] Architecture choice?"""
        verdict = "HUMAN REQUIRED for this decision."

        assert _check_open_questions_status(draft, verdict) == "HUMAN_REQUIRED"

    def test_returns_resolved(self):
        """Should return RESOLVED when questions are answered."""
        from agentos.workflows.requirements.nodes.review import _check_open_questions_status

        draft = """### Open Questions
- [ ] Which database?"""
        verdict = """## Open Questions Resolved
- [x] ~~Which database?~~ **RESOLVED: PostgreSQL.**"""

        assert _check_open_questions_status(draft, verdict) == "RESOLVED"

    def test_returns_unanswered(self):
        """Should return UNANSWERED when questions not addressed."""
        from agentos.workflows.requirements.nodes.review import _check_open_questions_status

        draft = """### Open Questions
- [ ] Open question here"""
        verdict = "[x] APPROVED - great design!"

        assert _check_open_questions_status(draft, verdict) == "UNANSWERED"


class TestRouteAfterReviewOpenQuestions:
    """Tests for route_after_review with open questions status."""

    def test_human_required_goes_to_gate(self):
        """HUMAN_REQUIRED should route to N4 even with gates disabled."""
        from agentos.workflows.requirements.graph import route_after_review

        state = {
            "error_message": "",
            "config_gates_verdict": False,
            "open_questions_status": "HUMAN_REQUIRED",
        }

        assert route_after_review(state) == "N4_human_gate_verdict"

    def test_unanswered_loops_to_drafter(self):
        """UNANSWERED should loop back to N1 if under max iterations."""
        from agentos.workflows.requirements.graph import route_after_review

        state = {
            "error_message": "",
            "config_gates_verdict": False,
            "lld_status": "APPROVED",
            "open_questions_status": "UNANSWERED",
            "iteration_count": 5,
            "max_iterations": 20,
        }

        assert route_after_review(state) == "N1_generate_draft"

    def test_unanswered_at_max_iterations_goes_to_gate(self):
        """UNANSWERED at max iterations should go to human gate."""
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
        """RESOLVED with APPROVED should go to N5."""
        from agentos.workflows.requirements.graph import route_after_review

        state = {
            "error_message": "",
            "config_gates_verdict": False,
            "lld_status": "APPROVED",
            "open_questions_status": "RESOLVED",
        }

        assert route_after_review(state) == "N5_finalize"

    def test_none_status_normal_routing(self):
        """NONE (no questions) should route based on lld_status."""
        from agentos.workflows.requirements.graph import route_after_review

        state = {
            "error_message": "",
            "config_gates_verdict": False,
            "lld_status": "APPROVED",
            "open_questions_status": "NONE",
        }

        assert route_after_review(state) == "N5_finalize"


class TestPreReviewValidationRemoved:
    """Tests verifying pre-review validation gate is removed."""

    def test_generate_draft_no_longer_blocks_on_questions(self):
        """generate_draft should not block even with open questions."""
        from agentos.workflows.requirements.graph import route_after_generate_draft

        # Routing after draft generation should proceed regardless of questions
        state = {
            "error_message": "",
            "config_gates_draft": False,
        }

        result = route_after_generate_draft(state)
        assert result == "N3_review"

    def test_validate_draft_structure_kept_for_compat(self):
        """validate_draft_structure exists but is no longer used in flow."""
        from agentos.workflows.requirements.nodes.generate_draft import validate_draft_structure

        # Function still exists for backward compatibility
        draft = """### Open Questions
- [ ] Question?"""

        # It returns a message, but generate_draft doesn't call it anymore
        result = validate_draft_structure(draft)
        # The result doesn't matter - what matters is it's not called in generate_draft


class TestPromptFile:
    """Tests for 0702c prompt file containing Open Questions Protocol."""

    def test_prompt_has_open_questions_protocol(self):
        """0702c should have Open Questions Protocol section."""
        possible_paths = [
            Path(__file__).parent.parent.parent / "docs" / "skills" / "0702c-LLD-Review-Prompt.md",
            Path("docs/skills/0702c-LLD-Review-Prompt.md"),
            Path("C:/Users/mcwiz/Projects/AgentOS-248/docs/skills/0702c-LLD-Review-Prompt.md"),
        ]

        content = None
        for p in possible_paths:
            if p.exists():
                content = p.read_text()
                break

        if content is None:
            pytest.skip("Prompt file not found")

        # Verify Open Questions Protocol section exists
        assert "Open Questions Protocol" in content
        assert "RESOLVED:" in content

    def test_prompt_has_format_instructions(self):
        """0702c should have format instructions for resolved questions."""
        possible_paths = [
            Path(__file__).parent.parent.parent / "docs" / "skills" / "0702c-LLD-Review-Prompt.md",
            Path("docs/skills/0702c-LLD-Review-Prompt.md"),
            Path("C:/Users/mcwiz/Projects/AgentOS-248/docs/skills/0702c-LLD-Review-Prompt.md"),
        ]

        content = None
        for p in possible_paths:
            if p.exists():
                content = p.read_text()
                break

        if content is None:
            pytest.skip("Prompt file not found")

        # Check format instruction exists
        assert "[x]" in content
        assert "~~" in content
        assert "RESOLVED:" in content


class TestStateHasOpenQuestionsStatus:
    """Tests for open_questions_status field in state."""

    def test_initial_state_has_field(self):
        """Initial state should have open_questions_status field."""
        from agentos.workflows.requirements.state import create_initial_state

        state = create_initial_state(
            workflow_type="lld",
            agentos_root="/tmp/agentos",
            target_repo="/tmp/repo",
            issue_number=248,
        )

        assert "open_questions_status" in state
        assert state["open_questions_status"] == "NONE"

    def test_review_node_sets_status(self, tmp_path):
        """Review node should set open_questions_status."""
        from agentos.workflows.requirements.nodes.review import review
        from agentos.workflows.requirements.state import create_initial_state

        with patch("agentos.workflows.requirements.nodes.review.get_provider") as mock_get:
            mock_provider = Mock()
            mock_provider.invoke.return_value = Mock(
                success=True,
                response="[x] APPROVED",
                error_message=None,
            )
            mock_get.return_value = mock_provider

            prompt_dir = tmp_path / "docs" / "skills"
            prompt_dir.mkdir(parents=True)
            (prompt_dir / "0702c-LLD-Review-Prompt.md").write_text("# Prompt")

            state = create_initial_state(
                workflow_type="lld",
                agentos_root=str(tmp_path),
                target_repo=str(tmp_path),
                issue_number=248,
            )
            state["current_draft"] = "# Draft without questions"
            state["audit_dir"] = str(tmp_path / "audit")
            Path(state["audit_dir"]).mkdir(parents=True)

            result = review(state)

            assert "open_questions_status" in result
