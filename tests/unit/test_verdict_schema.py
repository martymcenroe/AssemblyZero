"""Unit tests for assemblyzero/core/verdict_schema.py.

Issue #775 introduced the schemas and parse helpers; standard 0028
(operator ruling 2026-08-10) made the parsers strict — a structured ask
either parses and validates or raises StructuredContractError, and the
regex fallback scrapers are retired. Document scans of the pipeline's own
markdown (scan_open_questions_section, scan_residual_questions) replace
the two "parsers" whose inputs were never model JSON.
"""

import json

import pytest

from assemblyzero.core.verdict_schema import (
    DRAFT_QUESTIONS_SCHEMA,
    FEEDBACK_SCHEMA,
    FINALIZE_QUESTIONS_SCHEMA,
    REVIEW_SPEC_SCHEMA,
    VERDICT_SCHEMA,
    DraftQuestionsResult,
    FeedbackResult,
    FinalizeQuestionsResult,
    ReviewSpecResult,
    StructuredContractError,
    VerdictResult,
    _validate_enum,
    _validate_required_keys,
    parse_structured_feedback,
    parse_structured_review_spec,
    parse_structured_verdict,
    scan_open_questions_section,
    scan_residual_questions,
)


# ---------------------------------------------------------------------------
# Schema shape tests
# ---------------------------------------------------------------------------

class TestSchemaConstants:
    def test_verdict_schema_has_verdict_and_rationale(self):
        assert "verdict" in VERDICT_SCHEMA["properties"]
        assert "rationale" in VERDICT_SCHEMA["properties"]

    def test_feedback_schema_required_fields(self):
        required = FEEDBACK_SCHEMA["required"]
        assert "verdict" in required
        assert "rationale" in required
        assert "feedback_items" in required
        assert "open_questions" in required

    def test_feedback_schema_verdict_enum(self):
        enum = FEEDBACK_SCHEMA["properties"]["verdict"]["enum"]
        assert set(enum) == {"APPROVED", "REVISE", "DISCUSS"}

    def test_review_spec_schema_required_fields(self):
        required = REVIEW_SPEC_SCHEMA["required"]
        assert "verdict" in required
        assert "rationale" in required
        assert "feedback_items" in required

    def test_review_spec_schema_verdict_enum(self):
        enum = REVIEW_SPEC_SCHEMA["properties"]["verdict"]["enum"]
        assert set(enum) == {"APPROVED", "REVISE", "BLOCKED"}

    def test_draft_questions_schema_required(self):
        assert "open_questions" in DRAFT_QUESTIONS_SCHEMA["required"]

    def test_finalize_questions_schema_required(self):
        required = FINALIZE_QUESTIONS_SCHEMA["required"]
        assert "has_open_questions" in required
        assert "question_count" in required
        assert "questions" in required


# ---------------------------------------------------------------------------
# _validate_required_keys
# ---------------------------------------------------------------------------

class TestValidateRequiredKeys:
    def test_all_present(self):
        assert _validate_required_keys({"a": 1, "b": 2}, ["a", "b"]) is True

    def test_missing_key(self):
        assert _validate_required_keys({"a": 1}, ["a", "b"]) is False

    def test_empty_required(self):
        assert _validate_required_keys({}, []) is True

    def test_extra_keys_ok(self):
        assert _validate_required_keys({"a": 1, "b": 2, "c": 3}, ["a"]) is True


# ---------------------------------------------------------------------------
# _validate_enum
# ---------------------------------------------------------------------------

class TestValidateEnum:
    def test_valid_list(self):
        assert _validate_enum("APPROVED", ["APPROVED", "REVISE"]) is True

    def test_invalid_list(self):
        assert _validate_enum("BLOCKED", ["APPROVED", "REVISE"]) is False

    def test_valid_set(self):
        assert _validate_enum("REVISE", {"APPROVED", "REVISE", "DISCUSS"}) is True

    def test_case_sensitive(self):
        assert _validate_enum("approved", {"APPROVED"}) is False


# ---------------------------------------------------------------------------
# parse_structured_verdict (lenient by design: returns None, caller rejects)
# ---------------------------------------------------------------------------

class TestParseStructuredVerdict:
    def test_valid_json_returns_dict(self):
        raw = json.dumps({"verdict": "APPROVED", "rationale": "LGTM"})
        result = parse_structured_verdict(raw)
        assert result is not None
        assert result["verdict"] == "APPROVED"

    def test_invalid_json_returns_none(self):
        assert parse_structured_verdict("not json") is None

    def test_missing_verdict_key_returns_none(self):
        raw = json.dumps({"rationale": "ok"})
        assert parse_structured_verdict(raw) is None

    def test_empty_string_returns_none(self):
        assert parse_structured_verdict("") is None

    def test_fenced_json_recovered(self):
        raw = "```json\n" + json.dumps({"verdict": "REVISE", "rationale": "x"}) + "\n```"
        result = parse_structured_verdict(raw)
        assert result is not None
        assert result["verdict"] == "REVISE"


# ---------------------------------------------------------------------------
# parse_structured_feedback — strict (standard 0028)
# ---------------------------------------------------------------------------

class TestParseStructuredFeedback:
    def test_valid_json_structured_source(self):
        raw = json.dumps({
            "verdict": "REVISE",
            "rationale": "Missing tests",
            "feedback_items": ["Add T040"],
            "open_questions": [{"text": "Timeout?", "resolved": False}],
            "resolved_issues": [],
        })
        result = parse_structured_feedback(raw)
        assert result["verdict"] == "REVISE"
        assert result["rationale"] == "Missing tests"
        assert result["feedback_items"] == ["Add T040"]
        assert result["open_questions"] == [{"text": "Timeout?", "resolved": False}]
        assert result["source"] == "structured"

    def test_valid_json_all_required_fields_present(self):
        raw = json.dumps({
            "verdict": "APPROVED",
            "rationale": "LGTM",
            "feedback_items": [],
            "open_questions": [],
        })
        result = parse_structured_feedback(raw)
        assert result["source"] == "structured"
        assert "resolved_issues" in result

    def test_fenced_json_is_recovered_as_structured(self):
        """JSON recovery (fences) is not scraping — standard 0028 §2."""
        payload = json.dumps({
            "verdict": "APPROVED",
            "rationale": "LGTM",
            "feedback_items": [],
            "open_questions": [],
        })
        result = parse_structured_feedback(f"```json\n{payload}\n```")
        assert result["source"] == "structured"
        assert result["verdict"] == "APPROVED"

    def test_prose_wrapped_json_is_recovered_as_structured(self):
        payload = json.dumps({
            "verdict": "DISCUSS",
            "rationale": "needs a decision",
            "feedback_items": [],
            "open_questions": [],
        })
        result = parse_structured_feedback(f"Here is my verdict: {payload}")
        assert result["source"] == "structured"
        assert result["verdict"] == "DISCUSS"

    def test_missing_verdict_rejects(self):
        raw = json.dumps({"rationale": "ok", "feedback_items": [], "open_questions": []})
        with pytest.raises(StructuredContractError):
            parse_structured_feedback(raw)

    def test_invalid_verdict_enum_rejects(self):
        raw = json.dumps({
            "verdict": "NOTAVERDICT",
            "rationale": "x",
            "feedback_items": [],
            "open_questions": [],
        })
        with pytest.raises(StructuredContractError):
            parse_structured_feedback(raw)

    def test_markdown_checkbox_response_rejects(self):
        """The old regex fallback read this; now it is a contract violation."""
        raw = "[X] **REVISE**\n\n## Feedback\n- Fix something\n"
        with pytest.raises(StructuredContractError):
            parse_structured_feedback(raw)

    def test_empty_string_rejects(self):
        with pytest.raises(StructuredContractError):
            parse_structured_feedback("")

    def test_missing_open_questions_rejects(self):
        raw = json.dumps({
            "verdict": "APPROVED",
            "rationale": "ok",
            "feedback_items": [],
        })
        with pytest.raises(StructuredContractError):
            parse_structured_feedback(raw)

    def test_rejection_names_parser_and_carries_excerpt(self):
        with pytest.raises(StructuredContractError) as exc_info:
            parse_structured_feedback("Approved, ship it, great work all around")
        err = exc_info.value
        assert err.parser == "feedback"
        assert "feedback" in str(err)
        assert "Approved, ship it" in str(err)


# ---------------------------------------------------------------------------
# parse_structured_review_spec — strict (standard 0028)
# ---------------------------------------------------------------------------

class TestParseStructuredReviewSpec:
    def test_valid_json_structured_source(self):
        raw = json.dumps({
            "verdict": "APPROVED",
            "rationale": "Spec is complete",
            "feedback_items": [],
        })
        result = parse_structured_review_spec(raw)
        assert result["verdict"] == "APPROVED"
        assert result["source"] == "structured"

    def test_blocked_verdict_valid_in_review_spec(self):
        raw = json.dumps({
            "verdict": "BLOCKED",
            "rationale": "Cannot implement",
            "feedback_items": ["Missing API"],
        })
        result = parse_structured_review_spec(raw)
        assert result["verdict"] == "BLOCKED"

    def test_fenced_json_is_recovered_as_structured(self):
        payload = json.dumps({
            "verdict": "REVISE",
            "rationale": "fix the tests",
            "feedback_items": ["T010 is vague"],
        })
        result = parse_structured_review_spec(f"```json\n{payload}\n```")
        assert result["source"] == "structured"

    def test_markdown_response_rejects(self):
        with pytest.raises(StructuredContractError):
            parse_structured_review_spec("[X] **APPROVED**\nNice spec.")

    def test_missing_keys_rejects(self):
        with pytest.raises(StructuredContractError):
            parse_structured_review_spec(json.dumps({"verdict": "APPROVED"}))

    def test_invalid_enum_rejects(self):
        raw = json.dumps({
            "verdict": "DISCUSS",  # not in REVIEW_SPEC enum
            "rationale": "x",
            "feedback_items": [],
        })
        with pytest.raises(StructuredContractError):
            parse_structured_review_spec(raw)

    def test_rejection_names_parser(self):
        with pytest.raises(StructuredContractError) as exc_info:
            parse_structured_review_spec("")
        assert exc_info.value.parser == "review_spec"


# ---------------------------------------------------------------------------
# scan_open_questions_section — document scan, not a parser (0028 §3)
# ---------------------------------------------------------------------------

class TestScanOpenQuestionsSection:
    DOC = (
        "# LLD-042\n\n"
        "## Summary\nDesign.\n\n"
        "## Open Questions\n"
        "- [ ] Should the collector support IPv6?\n"
        "- [x] Is 2s polling acceptable?\n"
        "- [X] Uppercase checkbox too?\n\n"
        "## 11. Rollback\nRevert.\n"
    )

    def test_extracts_unchecked_and_checked(self):
        result = scan_open_questions_section(self.DOC)
        texts = {q["text"]: q["resolved"] for q in result["open_questions"]}
        assert texts["Should the collector support IPv6?"] is False
        assert texts["Is 2s polling acceptable?"] is True
        assert texts["Uppercase checkbox too?"] is True

    def test_source_is_document_scan(self):
        assert scan_open_questions_section(self.DOC)["source"] == "document_scan"

    def test_no_section_returns_empty(self):
        result = scan_open_questions_section("# Doc\n\n## Summary\nText.\n")
        assert result["open_questions"] == []

    def test_empty_text_returns_empty(self):
        assert scan_open_questions_section("")["open_questions"] == []

    def test_heading_with_parenthetical_suffix(self):
        doc = "## Open Questions (2 remaining)\n- [ ] One?\n"
        result = scan_open_questions_section(doc)
        assert len(result["open_questions"]) == 1

    def test_scan_stops_at_next_heading(self):
        doc = (
            "## Open Questions\n- [ ] Real question?\n"
            "## Notes\n- [ ] Not a question, different section\n"
        )
        result = scan_open_questions_section(doc)
        assert len(result["open_questions"]) == 1

    def test_json_input_has_no_section(self):
        """The scanner reads documents; JSON is not a document with sections."""
        raw = json.dumps({"open_questions": [{"text": "Q?", "resolved": False}]})
        assert scan_open_questions_section(raw)["open_questions"] == []


# ---------------------------------------------------------------------------
# scan_residual_questions — document scan, not a parser (0028 §3)
# ---------------------------------------------------------------------------

class TestScanResidualQuestions:
    def test_detects_question_lines(self):
        text = "All good.\nBut what about the frobnicator?\nDone."
        result = scan_residual_questions(text)
        assert result["has_open_questions"] is True
        assert "But what about the frobnicator?" in result["questions"]

    def test_short_question_mark_filtered(self):
        result = scan_residual_questions("Why?\nAll good.")
        assert result["has_open_questions"] is False

    def test_detects_todo_markers(self):
        result = scan_residual_questions("Line one.\nTODO: wire up the collector\n")
        assert result["has_open_questions"] is True
        assert any("TODO" in q for q in result["questions"])

    def test_clean_text_has_none(self):
        result = scan_residual_questions("Everything is finished.\nShip it.")
        assert result["has_open_questions"] is False
        assert result["question_count"] == 0

    def test_empty_text(self):
        result = scan_residual_questions("")
        assert result["has_open_questions"] is False
        assert result["source"] == "document_scan"

    def test_question_count_matches_list(self):
        text = "Is this right?\nWhat about that other thing?\nTODO: check"
        result = scan_residual_questions(text)
        assert result["question_count"] == len(result["questions"])


# ---------------------------------------------------------------------------
# StructuredContractError
# ---------------------------------------------------------------------------

class TestStructuredContractError:
    def test_carries_parser_reason_excerpt(self):
        err = StructuredContractError("feedback", "Missing required keys", "raw body here")
        assert err.parser == "feedback"
        assert err.reason == "Missing required keys"
        assert "raw body here" in str(err)

    def test_empty_raw_says_so(self):
        err = StructuredContractError("feedback", "no JSON object found", "")
        assert "response empty" in str(err)

    def test_excerpt_is_bounded(self):
        err = StructuredContractError("feedback", "reason", "x" * 500)
        assert len(err.excerpt) == 160


# ---------------------------------------------------------------------------
# TypedDict structures
# ---------------------------------------------------------------------------

class TestTypedDictStructures:
    def test_verdict_result_fields(self):
        result = VerdictResult(verdict="APPROVED", rationale="ok", source="structured")
        assert result["verdict"] == "APPROVED"

    def test_feedback_result_fields(self):
        result = FeedbackResult(
            verdict="REVISE", rationale="r", feedback_items=[],
            open_questions=[], resolved_issues=[], source="structured",
        )
        assert result["source"] == "structured"

    def test_review_spec_result_fields(self):
        result = ReviewSpecResult(
            verdict="BLOCKED", rationale="r", feedback_items=["x"], source="structured",
        )
        assert result["feedback_items"] == ["x"]

    def test_draft_questions_result_fields(self):
        result = DraftQuestionsResult(open_questions=[], source="document_scan")
        assert result["open_questions"] == []

    def test_finalize_questions_result_fields(self):
        result = FinalizeQuestionsResult(
            has_open_questions=False, question_count=0, questions=[],
            source="document_scan",
        )
        assert result["question_count"] == 0
