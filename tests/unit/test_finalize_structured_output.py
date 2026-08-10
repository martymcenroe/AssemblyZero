"""Tests for finalize residual-question detection.

Standard 0028 reframed this surface: finalize validates its OWN generated
artifact, so `_detect_open_questions` is a deterministic document scan
(`scan_residual_questions`) — never a structured parse of model output and
never a "fallback." JSON content is just text to the scan; the pre-0028
structured branch (which read JSON verdict-shaped content) is retired with
its parser.
"""

from assemblyzero.workflows.requirements.nodes.finalize import (
    _detect_open_questions,
    validate_lld_final,
)


class TestDetectOpenQuestionsScan:
    def test_markdown_content_with_question(self):
        content = "## Requirements\n\nWhat timeout value?\nThe system shall process requests.\n"
        result = _detect_open_questions(content)
        assert result["has_open_questions"] is True
        assert "What timeout value?" in result["questions"]

    def test_markdown_content_with_todo(self):
        content = "## Design\n\nTODO: decide on retry policy\nDone otherwise.\n"
        result = _detect_open_questions(content)
        assert result["has_open_questions"] is True
        assert any("TODO" in q for q in result["questions"])

    def test_markdown_content_with_both(self):
        content = "Is this the right approach?\nTODO: verify\n"
        result = _detect_open_questions(content)
        assert result["has_open_questions"] is True
        assert result["question_count"] == len(result["questions"])
        assert result["question_count"] >= 2

    def test_clean_content_no_issues(self):
        content = "## Design\n\nEverything is decided.\nShip it.\n"
        result = _detect_open_questions(content)
        assert result["has_open_questions"] is False
        assert result["question_count"] == 0

    def test_empty_content(self):
        result = _detect_open_questions("")
        assert result["has_open_questions"] is False
        assert result["questions"] == []

    def test_short_question_mark_not_detected(self):
        result = _detect_open_questions("Why?\nAll settled.\n")
        assert result["has_open_questions"] is False

    def test_longer_question_detected(self):
        result = _detect_open_questions("Should we use asyncio here?\n")
        assert result["has_open_questions"] is True

    def test_todo_case_insensitive(self):
        result = _detect_open_questions("todo: lowercase marker\n")
        assert result["has_open_questions"] is True

    def test_source_is_document_scan(self):
        result = _detect_open_questions("Anything at all.\n")
        assert result["source"] == "document_scan"

    def test_json_content_is_just_text_to_the_scan(self):
        """The retired structured branch read verdict-shaped JSON; the scan
        treats JSON as text — no line ends with '?' so nothing is found."""
        content = '{"has_open_questions": true, "question_count": 1, "questions": ["What timeout value?"]}'
        result = _detect_open_questions(content)
        assert result["has_open_questions"] is False


class TestValidateLldFinalStillUsesScan:
    def test_clean_lld_passes(self):
        content = (
            "# LLD-001\n\n## Summary\nDone.\n\n"
            "## Open Questions\n- [x] Decided already\n"
        )
        errors = validate_lld_final(content)
        assert errors == []

    def test_unchecked_question_flagged(self):
        content = (
            "# LLD-001\n\n## Summary\nDone.\n\n"
            "## Open Questions\n- [ ] Still undecided thing\n"
        )
        errors = validate_lld_final(content)
        assert errors, "an unchecked open question must flag"

    def test_resolved_by_reviewer_skips_check(self):
        content = (
            "# LLD-001\n\n## Summary\nDone.\n\n"
            "## Open Questions\n- [ ] Still undecided thing\n"
        )
        errors = validate_lld_final(content, open_questions_resolved=True)
        assert errors == []
