"""Unit tests for Wave 1 token-saving issues.

Issue #506: Extract verdict prose from state
Issue #495: Strip redundant Gemini checks from review prompts
Issue #500: Pass scaffold validation errors back to scaffold node
Issue #502: Hash scaffold output, skip Gemini when identical
"""

import hashlib
from pathlib import Path
from unittest.mock import Mock, patch

import pytest


# ===========================================================================
# Issue #506: Extract verdict prose from state
# ===========================================================================


class TestExtractActionableFeedback:
    """Tests for _extract_actionable_feedback in review.py."""

    def test_structured_approved_returns_summary(self):
        """Structured APPROVED verdict returns concise feedback."""
        from assemblyzero.workflows.requirements.nodes.review import (
            _extract_actionable_feedback,
        )

        structured = {
            "verdict": "APPROVED",
            "summary": "LLD is ready for implementation.",
            "blocking_issues": [],
            "suggestions": ["Consider adding metrics"],
        }
        result = _extract_actionable_feedback("raw...", "APPROVED", structured)

        assert "LLD is ready for implementation" in result
        assert "Consider adding metrics" in result
        # Should NOT contain raw full text
        assert "raw..." not in result

    def test_structured_blocked_returns_issues(self):
        """Structured BLOCKED verdict returns blocking issues."""
        from assemblyzero.workflows.requirements.nodes.review import (
            _extract_actionable_feedback,
        )

        structured = {
            "verdict": "BLOCKED",
            "summary": "Missing test coverage.",
            "blocking_issues": [
                {
                    "section": "Section 10",
                    "issue": "No integration tests",
                    "severity": "BLOCKING",
                }
            ],
            "suggestions": [],
        }
        result = _extract_actionable_feedback("raw...", "BLOCKED", structured)

        assert "Missing test coverage" in result
        assert "No integration tests" in result
        assert "BLOCKING" in result

    def test_unstructured_approved_extracts_suggestions(self):
        """Unstructured APPROVED verdict extracts only suggestions."""
        from assemblyzero.workflows.requirements.nodes.review import (
            _extract_actionable_feedback,
        )

        verdict = """## Review Summary
Good LLD.

## Tier 1: BLOCKING Issues
No blocking issues found.

## Tier 2: HIGH PRIORITY Issues
No high-priority issues found.

## Tier 3: SUGGESTIONS
- Consider adding metrics
- Add logging

## Verdict
[X] **APPROVED**
"""
        result = _extract_actionable_feedback(verdict, "APPROVED", None)

        assert "APPROVED" in result
        assert "Consider adding metrics" in result
        # Should NOT contain boilerplate sections
        assert "Identity Confirmation" not in result

    def test_unstructured_blocked_extracts_tiers(self):
        """Unstructured BLOCKED verdict extracts Tier 1 and Tier 2."""
        from assemblyzero.workflows.requirements.nodes.review import (
            _extract_actionable_feedback,
        )

        verdict = """## Identity Confirmation
I am Gemini 3 Pro.

## Pre-Flight Gate
PASSED

## Review Summary
LLD has safety issues.

## Tier 1: BLOCKING Issues
### Safety
- [ ] No worktree scope defined

## Tier 2: HIGH PRIORITY Issues
### Architecture
- [ ] Missing error handling

## Tier 3: SUGGESTIONS
- Add docs

## Verdict
[X] **REVISE**
"""
        result = _extract_actionable_feedback(verdict, "BLOCKED", None)

        assert "No worktree scope defined" in result
        assert "Missing error handling" in result
        assert "Add docs" in result
        # Should NOT include identity/pre-flight boilerplate
        assert "I am Gemini 3 Pro" not in result
        assert "Pre-Flight Gate" not in result

    def test_simple_verdict_falls_back_to_full(self):
        """Simple verdicts with no extractable sections return full text."""
        from assemblyzero.workflows.requirements.nodes.review import (
            _extract_actionable_feedback,
        )

        result = _extract_actionable_feedback(
            "BLOCKED: Missing tests", "BLOCKED", None
        )
        assert "Missing tests" in result

    def test_empty_verdict(self):
        """Empty verdict returns status only."""
        from assemblyzero.workflows.requirements.nodes.review import (
            _extract_actionable_feedback,
        )

        result = _extract_actionable_feedback("", "APPROVED", None)
        assert "APPROVED" in result

    def test_extract_section_helper(self):
        """_extract_section finds named sections."""
        from assemblyzero.workflows.requirements.nodes.review import _extract_section

        content = """## Review Summary
This is the summary.

## Tier 1: BLOCKING Issues
Safety problem here.

## Tier 2: HIGH PRIORITY
Architecture concern.
"""
        assert "This is the summary" in _extract_section(content, "Review Summary")
        assert "Safety problem here" in _extract_section(content, "Tier 1")
        assert _extract_section(content, "Nonexistent") == ""


class TestReviewNodeStoresExtractedFeedback:
    """Integration test: review node stores extracted feedback, not full prose."""

    @patch("assemblyzero.workflows.requirements.nodes.review.get_provider")
    def test_current_verdict_is_extracted(self, mock_get_provider, tmp_path):
        """current_verdict contains extracted feedback, not full prose."""
        from assemblyzero.workflows.requirements.nodes.review import review
        from assemblyzero.workflows.requirements.state import create_initial_state

        import json as _json
        full_verdict = """## Identity Confirmation
I am Gemini 3 Pro.

## Pre-Flight Gate
PASSED

## Review Summary
LLD looks good overall.

## Tier 1: BLOCKING Issues
No blocking issues found.

## Tier 3: SUGGESTIONS
- Consider caching

## Verdict
[X] **APPROVED**
"""
        mock_provider = Mock()
        mock_provider.invoke.return_value = Mock(
            success=True,
            content=_json.dumps({"verdict": "APPROVED", "rationale": "LLD looks good overall.", "feedback_items": [], "open_questions": []}),
            response=full_verdict,
            error_message=None,
            input_tokens=100,
            output_tokens=200,
        )
        mock_get_provider.return_value = mock_provider

        prompt_dir = tmp_path / "docs" / "skills"
        prompt_dir.mkdir(parents=True)
        (prompt_dir / "0702c-LLD-Review-Prompt.md").write_text("# Review Prompt")

        state = create_initial_state(
            workflow_type="lld",
            assemblyzero_root=str(tmp_path),
            target_repo=str(tmp_path),
            issue_number=42,
        )
        state["current_draft"] = "# LLD Content"
        state["audit_dir"] = str(tmp_path / "audit")
        Path(state["audit_dir"]).mkdir(parents=True)

        result = review(state)

        # current_verdict should NOT contain "I am Gemini 3 Pro" boilerplate
        cv = result.get("current_verdict", "")
        assert "I am Gemini 3 Pro" not in cv
        assert "Pre-Flight Gate" not in cv
        # #775: structured APPROVED with empty feedback_items returns ""
        # (no actionable feedback to store). Verdict confirmed via lld_status.
        assert result.get("lld_status") == "APPROVED"

    @patch("assemblyzero.workflows.requirements.nodes.review.get_provider")
    def test_audit_trail_has_structured_verdict(self, mock_get_provider, tmp_path):
        """Audit trail file contains structured verdict content (#775).

        Issue #775: Audit trail now writes structured feedback_result data
        (verdict + rationale + feedback_items), not raw LLM prose.
        """
        from assemblyzero.workflows.requirements.nodes.review import review
        from assemblyzero.workflows.requirements.state import create_initial_state

        import json as _json

        mock_provider = Mock()
        mock_provider.invoke.return_value = Mock(
            success=True,
            content=_json.dumps({"verdict": "APPROVED", "rationale": "Looks good", "feedback_items": ["Consider caching"], "open_questions": []}),
            response="raw prose",
            error_message=None,
            input_tokens=100,
            output_tokens=200,
        )
        mock_get_provider.return_value = mock_provider

        prompt_dir = tmp_path / "docs" / "skills"
        prompt_dir.mkdir(parents=True)
        (prompt_dir / "0702c-LLD-Review-Prompt.md").write_text("# Prompt")

        state = create_initial_state(
            workflow_type="lld",
            assemblyzero_root=str(tmp_path),
            target_repo=str(tmp_path),
            issue_number=42,
        )
        state["current_draft"] = "# LLD"
        state["audit_dir"] = str(tmp_path / "audit")
        Path(state["audit_dir"]).mkdir(parents=True)

        review(state)

        # Audit trail should have structured verdict content
        audit_files = list(Path(state["audit_dir"]).glob("*verdict*"))
        assert len(audit_files) == 1
        content = audit_files[0].read_text()
        assert "APPROVED" in content
        assert "Looks good" in content
        assert "Consider caching" in content


# ===========================================================================
# Issue #495: Strip redundant Gemini checks
# ===========================================================================


class TestPreValidatedPreamble:
    """Tests that review prompts contain pre-validated preambles."""

    def test_lld_review_prompt_has_preamble(self):
        """0702c LLD review prompt contains pre-validated section."""
        prompt_path = Path("docs/skills/0702c-LLD-Review-Prompt.md")
        if not prompt_path.exists():
            pytest.skip("Prompt file not found")
        content = prompt_path.read_text()
        assert "Pre-Validated" in content
        assert "Do NOT Re-Check" in content

    def test_lld_review_prompt_no_redundant_coverage_calc(self):
        """0702c LLD review prompt no longer asks for coverage calculation."""
        prompt_path = Path("docs/skills/0702c-LLD-Review-Prompt.md")
        if not prompt_path.exists():
            pytest.skip("Prompt file not found")
        content = prompt_path.read_text()
        # The removed mandatory coverage table instruction
        assert "Requirement Coverage Analysis (MANDATORY)" not in content

    def test_test_plan_review_prompt_has_preamble(self):
        """0706c test plan review prompt contains pre-validated section."""
        prompt_path = Path("docs/skills/0706c-Test-Plan-Review-Prompt.md")
        if not prompt_path.exists():
            pytest.skip("Prompt file not found")
        content = prompt_path.read_text()
        assert "Pre-Validated" in content
        assert "Do NOT Re-Check" in content

    def test_impl_spec_review_has_preamble(self):
        """review_spec.py embedded criteria contain pre-validated section."""
        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            _get_review_criteria,
        )

        criteria = _get_review_criteria()
        assert "Pre-Validated" in criteria
        assert "Do NOT Re-Check" in criteria
        # File Coverage section removed (now pre-validated)
        assert "File Coverage (BLOCKING)" not in criteria


# ===========================================================================
# Issue #500: Pass scaffold validation errors back
# ===========================================================================


class TestScaffoldValidationErrorPassback:
    """Tests that validation errors are passed back to scaffold node."""

    def test_validation_errors_in_state_on_failure(self):
        """Failed validation writes scaffold_validation_errors to state."""
        from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
            validate_tests_mechanical_node,
        )

        # Invalid test content (syntax error)
        state = {
            "generated_tests": "def test_foo():\n    assert",
            "parsed_scenarios": {"scenarios": []},
            "scaffold_attempts": 0,
        }

        result = validate_tests_mechanical_node(state)

        assert "scaffold_validation_errors" in result
        # Should have errors since the test has a syntax error
        assert len(result["scaffold_validation_errors"]) > 0

    def test_validation_errors_cleared_on_success(self):
        """Successful validation clears scaffold_validation_errors."""
        from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
            validate_tests_mechanical_node,
        )

        # Valid test content
        state = {
            "generated_tests": (
                'import pytest\n\n'
                'def test_example():\n'
                '    assert True\n'
            ),
            "parsed_scenarios": {"scenarios": []},
            "scaffold_attempts": 0,
        }

        result = validate_tests_mechanical_node(state)

        assert result.get("scaffold_validation_errors") == []


# ===========================================================================
# Issue #502: Hash scaffold output, skip identical regeneration
# ===========================================================================


class TestScaffoldHashStagnation:
    """Tests for hash-based stagnation detection in scaffold loop."""

    def test_identical_output_triggers_escalation(self):
        """Identical scaffold output across attempts escalates immediately."""
        from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
            should_regenerate,
        )

        test_content = "def test_foo():\n    assert False\n"
        content_hash = hashlib.sha256(test_content.encode()).hexdigest()

        state = {
            "validation_result": {"is_valid": False},
            "scaffold_attempts": 1,
            "generated_tests": test_content,
            "previous_scaffold_hash": content_hash,
        }

        assert should_regenerate(state) == "escalate"

    def test_different_output_allows_regeneration(self):
        """Different scaffold output allows normal regeneration."""
        from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
            should_regenerate,
        )

        state = {
            "validation_result": {"is_valid": False},
            "scaffold_attempts": 1,
            "generated_tests": "def test_foo():\n    assert False\n",
            "previous_scaffold_hash": "different_hash_value",
        }

        assert should_regenerate(state) == "regenerate"

    def test_first_attempt_no_hash_allows_regeneration(self):
        """First attempt (no previous hash) allows normal regeneration."""
        from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
            should_regenerate,
        )

        state = {
            "validation_result": {"is_valid": False},
            "scaffold_attempts": 1,
            "generated_tests": "def test_foo():\n    assert False\n",
        }

        assert should_regenerate(state) == "regenerate"

    def test_valid_output_continues(self):
        """Valid output always continues regardless of hash."""
        from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
            should_regenerate,
        )

        state = {
            "validation_result": {"is_valid": True},
            "scaffold_attempts": 0,
        }

        assert should_regenerate(state) == "continue"

    def test_hash_stored_in_validation_result(self):
        """Validation node stores hash for next iteration."""
        from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
            validate_tests_mechanical_node,
        )

        test_content = 'import pytest\n\ndef test_x():\n    assert True\n'
        state = {
            "generated_tests": test_content,
            "parsed_scenarios": {"scenarios": []},
            "scaffold_attempts": 0,
        }

        result = validate_tests_mechanical_node(state)

        expected_hash = hashlib.sha256(test_content.encode()).hexdigest()
        assert result.get("previous_scaffold_hash") == expected_hash

    def test_max_attempts_still_escalates(self):
        """Max attempts escalation still works even without hash match."""
        from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
            should_regenerate,
        )

        state = {
            "validation_result": {"is_valid": False},
            "scaffold_attempts": 3,
            "generated_tests": "different content",
            "previous_scaffold_hash": "some_hash",
        }

        assert should_regenerate(state) == "escalate"
