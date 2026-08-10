"""Tests for draft open-questions extraction in generate_draft node.

Standard 0028 reframed this surface: the drafter's response is a markdown
DOCUMENT ("emit ONLY the revised markdown"), so open-questions extraction is
a deterministic scan of the document's ``## Open Questions`` section —
`scan_open_questions_section` — not a structured-JSON parse with a regex
fallback. The pre-0028 code also sent DRAFT_QUESTIONS_SCHEMA as the response
schema on the SAME call whose prompt demanded prose — two contradictory
contracts on one ask; the schema is gone and these tests pin the scan.
"""

from unittest.mock import MagicMock

from assemblyzero.workflows.requirements.nodes.generate_draft import (
    _extract_open_questions,
)


DRAFT_WITH_QUESTIONS = """# LLD-042: Widget Design

## 1. Summary
A widget.

## Open Questions
- [ ] What is the timeout?
- [x] Rate limit decided
- [ ] Another unresolved?

## 11. Rollback
Revert the PR.
"""

DRAFT_WITHOUT_SECTION = """# LLD-042: Widget Design

## 1. Summary
A widget with no questions section at all.
"""


class TestExtractOpenQuestionsDocumentScan:
    def test_scans_unchecked_and_checked(self):
        result = _extract_open_questions(MagicMock(), DRAFT_WITH_QUESTIONS, "")
        by_text = {q["text"]: q["resolved"] for q in result["open_questions"]}
        assert by_text["What is the timeout?"] is False
        assert by_text["Rate limit decided"] is True
        assert by_text["Another unresolved?"] is False

    def test_source_is_document_scan(self):
        result = _extract_open_questions(MagicMock(), DRAFT_WITH_QUESTIONS, "")
        assert result["source"] == "document_scan"

    def test_no_section_yields_empty(self):
        result = _extract_open_questions(MagicMock(), DRAFT_WITHOUT_SECTION, "")
        assert result["open_questions"] == []

    def test_empty_response_yields_empty(self):
        result = _extract_open_questions(MagicMock(), "", "")
        assert result["open_questions"] == []

    def test_scan_never_calls_the_provider(self):
        """Extraction is a local document scan — no LLM call, ever."""
        provider = MagicMock()
        _extract_open_questions(provider, DRAFT_WITH_QUESTIONS, "system prompt")
        provider.invoke.assert_not_called()

    def test_result_shape(self):
        result = _extract_open_questions(MagicMock(), DRAFT_WITH_QUESTIONS, "")
        assert "open_questions" in result
        assert "source" in result

    def test_scan_stops_at_next_section(self):
        doc = (
            "## Open Questions\n- [ ] Real?\n"
            "## Definition of Done\n- [ ] Not a question\n"
        )
        result = _extract_open_questions(MagicMock(), doc, "")
        assert len(result["open_questions"]) == 1
        assert result["open_questions"][0]["text"] == "Real?"
