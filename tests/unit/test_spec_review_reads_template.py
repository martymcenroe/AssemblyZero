"""#2837: the spec reviewer's own output template is a readable verdict.

Run 15 on boostgauge #4 (`run-issue4-025552`, 2026-09-05) cleared every
gate up to the spec review, then the reviewer answered in the "Required
Output Format" `review_spec.py` hands it -- Summary, Blocking Issues, High
Priority Issues, Suggestions, `[X] **REVISE**` -- and the JSON parser refused
it. The verdict named run 11's tolerance defect on round 1. That response is
the fixture here.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from assemblyzero.core.verdict_schema import (
    parse_markdown_review_spec,
    parse_markdown_verdict,
)
from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
    _invoke_reviewer_with_spec_schema,
)

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures" / "spec_review_shapes" / "run15-markdown-template.txt"
)
RUN15 = FIXTURE.read_text(encoding="utf-8")

APPROVED_SPEC = """\
## Readiness Review: Issue #7

## Summary
The spec is concrete and every test is executable.

## Blocking Issues
No blocking issues found.

## High Priority Issues
No high-priority issues found.

## Suggestions
- Consider naming the fixture.

## Verdict
[X] **APPROVED** - Spec is ready for implementation
[ ] **REVISE** - Fix blocking/high-priority issues first
[ ] **BLOCKED** - Fundamental issues prevent implementation
"""

PLAN_TEMPLATE = """\
## Coverage Analysis
- Requirements covered: 7/7 (100%)
- Missing coverage: none

## Test Reality Issues
- none

## Verdict
[ ] **APPROVED** - Test plan is ready for implementation
[X] **BLOCKED** - Test plan needs revision

Mark EXACTLY ONE option with [X].

## Required Changes (if BLOCKED)
1. T030 must assert the memory field on a mocked virtual_memory().
2. T070 must assert exactly one NtQuerySystemInformation call.
"""


class TestRun15sAnswerIsAVerdict:
    def test_it_reads_as_revise_with_two_items(self):
        parsed = parse_markdown_review_spec(RUN15)
        assert parsed is not None, "run 15's reviewer answer was thrown away"
        assert parsed["verdict"] == "REVISE"
        assert parsed["source"] == "markdown_template"
        assert len(parsed["feedback_items"]) == 2
        first, second = parsed["feedback_items"]
        assert "test_req_020" in first and "<= 5" in first and "```python" in first
        assert "test_req_070" in second and "== 1" in second

    def test_the_rationale_is_the_summary(self):
        parsed = parse_markdown_review_spec(RUN15)
        assert parsed is not None
        assert parsed["rationale"].startswith("The revised spec correctly implements")
        assert "## Verdict" not in parsed["rationale"]

    def test_the_items_carry_the_spans_the_revision_lock_needs(self):
        parsed = parse_markdown_review_spec(RUN15)
        assert parsed is not None
        joined = "\n".join(parsed["feedback_items"])
        assert "`tests/integration/test_windows_collector.py`" in joined
        assert "`test_req_020`" in joined
        assert "`test_req_070`" in joined

    def test_an_approved_template_has_no_items(self):
        parsed = parse_markdown_review_spec(APPROVED_SPEC)
        assert parsed is not None
        assert parsed["verdict"] == "APPROVED"
        assert parsed["feedback_items"] == []
        assert parsed["rationale"] == "The spec is concrete and every test is executable."


class TestTheReaderDoesNotGuess:
    def test_no_checked_verdict_is_not_read(self):
        assert parse_markdown_review_spec(RUN15.replace("[X] **REVISE**", "[ ] **REVISE**")) is None

    def test_two_checked_verdicts_are_not_read(self):
        assert parse_markdown_review_spec(RUN15.replace("[ ] **APPROVED**", "[X] **APPROVED**")) is None

    @pytest.mark.parametrize("raw", ["", "prose", json.dumps({"verdict": "APPROVED"})])
    def test_nothing_template_shaped_is_none(self, raw):
        assert parse_markdown_review_spec(raw) is None
        assert parse_markdown_verdict(raw) is None


class TestTheTestPlanTemplate:
    def test_blocked_with_required_changes(self):
        parsed = parse_markdown_verdict(PLAN_TEMPLATE)
        assert parsed is not None
        assert parsed["verdict"] == "BLOCKED"
        assert parsed["source"] == "markdown_template"
        assert len(parsed["suggestions"]) == 2
        assert parsed["suggestions"][0].startswith("T030")

    def test_approved(self):
        text = PLAN_TEMPLATE.replace("[ ] **APPROVED**", "[X] **APPROVED**").replace(
            "[X] **BLOCKED**", "[ ] **BLOCKED**"
        )
        parsed = parse_markdown_verdict(text)
        assert parsed is not None
        assert parsed["verdict"] == "APPROVED"


class _Scripted:
    def __init__(self, answers):
        self.answers = list(answers)
        self.calls: list[tuple[str, str]] = []

    def invoke(self, system, prompt, **_kwargs):
        self.calls.append((system, prompt))
        return SimpleNamespace(success=True, response=self.answers.pop(0), error_message=None)


JSON_ANSWER = json.dumps({
    "verdict": "APPROVED", "rationale": "fine", "feedback_items": [],
})


class TestTheHelperAsksAtMostTwice:
    def test_json_first_time_is_one_call(self):
        provider = _Scripted([JSON_ANSWER])
        result, error = _invoke_reviewer_with_spec_schema(provider, "spec", "system")
        assert error == "" and result is not None and result["verdict"] == "APPROVED"
        assert len(provider.calls) == 1

    def test_the_template_first_time_is_one_call(self, capsys):
        provider = _Scripted([RUN15])
        result, error = _invoke_reviewer_with_spec_schema(provider, "spec", "system")
        assert error == "" and result is not None and result["verdict"] == "REVISE"
        assert len(provider.calls) == 1
        assert "own output template" in capsys.readouterr().out

    def test_garbage_then_json_is_two_calls_naming_the_defect(self):
        provider = _Scripted(["I would rather not.", JSON_ANSWER])
        result, error = _invoke_reviewer_with_spec_schema(provider, "spec", "system")
        assert error == "" and result is not None and result["verdict"] == "APPROVED"
        assert len(provider.calls) == 2
        assert "ONLY that JSON object" in provider.calls[1][0]

    def test_garbage_then_template_is_read(self):
        provider = _Scripted(["nothing", RUN15])
        result, error = _invoke_reviewer_with_spec_schema(provider, "spec", "system")
        assert error == "" and result is not None and result["verdict"] == "REVISE"
        assert len(provider.calls) == 2

    def test_garbage_twice_is_the_error_and_never_a_third_call(self):
        provider = _Scripted(["nothing", "still nothing"])
        result, error = _invoke_reviewer_with_spec_schema(provider, "spec", "system")
        assert result is None
        assert "unreadable twice" in error
        assert len(provider.calls) == 2
        assert provider.answers == []
