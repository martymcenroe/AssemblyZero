"""#2835: the design reviewer's own template is a readable verdict.

Run 14 on boostgauge #4 (`run-issue4-023537`, 2026-09-05) cleared the
requirements gate and the design draft, then the reviewer answered in the
0702c markdown template it had been handed as its instructions -- Identity
Confirmation, Pre-Flight Gate, Tier 1/2/3, a checked `[x] **REVISE**` -- and
`parse_structured_feedback` refused it for not being JSON. The run ended
with a usable verdict in the log. That response is the fixture here.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from assemblyzero.core.verdict_schema import (
    StructuredContractError,
    parse_markdown_feedback,
)
from assemblyzero.workflows.requirements.nodes.review import (
    _count_tier1_blocking_issues,
    _invoke_reviewer_with_feedback_schema,
)

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures" / "lld_review_shapes" / "run14-markdown-template.txt"
)
RUN14 = FIXTURE.read_text(encoding="utf-8")

APPROVED_TEMPLATE = """\
# LLD Review: #7

## Identity Confirmation
I am Gemini 3 Pro.

## Pre-Flight Gate
PASSED

## Review Summary
Clean.

## Open Questions Resolved
- [x] ~~Which config format?~~ **RESOLVED: TOML.**

## Tier 1: BLOCKING Issues

### Cost
- [ ] No issues found.

### Safety
- [ ] No issues found.

## Tier 2: HIGH PRIORITY Issues

### Architecture
- [ ] No issues found.

## Tier 3: SUGGESTIONS
- Consider a docstring.

## Verdict
[x] **APPROVED** - Ready for implementation
[ ] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision
"""


class TestRun14sAnswerIsAVerdict:
    def test_it_reads_as_revise_with_two_items(self):
        parsed = parse_markdown_feedback(RUN14)
        assert parsed is not None, "run 14's reviewer answer was thrown away"
        assert parsed["verdict"] == "REVISE"
        assert parsed["source"] == "markdown_template"
        assert len(parsed["feedback_items"]) == 2
        assert "Silent Failure" in parsed["feedback_items"][0]
        assert "Missing Logging Strategy" in parsed["feedback_items"][1]
        assert parsed["open_questions"] == []

    def test_the_rationale_carries_the_tier_headings_the_node_reads(self):
        parsed = parse_markdown_feedback(RUN14)
        assert parsed is not None
        assert "## Tier 1: BLOCKING Issues" in parsed["rationale"]
        assert "## Tier 2:" in parsed["rationale"]
        # #1511's own arithmetic on that rationale: one real Tier 1 issue,
        # so the node lands on BLOCKED and the revision loop runs.
        assert _count_tier1_blocking_issues(parsed["rationale"]) == 1

    def test_an_approved_template_is_approved_with_no_items(self):
        parsed = parse_markdown_feedback(APPROVED_TEMPLATE)
        assert parsed is not None
        assert parsed["verdict"] == "APPROVED"
        assert parsed["feedback_items"] == []
        assert parsed["open_questions"] == [
            {"text": "~~Which config format?~~ **RESOLVED: TOML.**", "resolved": True}
        ]
        assert _count_tier1_blocking_issues(parsed["rationale"]) == 0


class TestTheReaderDoesNotGuess:
    def test_no_checked_verdict_is_not_read(self):
        text = RUN14.replace("[x] **REVISE**", "[ ] **REVISE**")
        assert parse_markdown_feedback(text) is None

    def test_two_checked_verdicts_are_not_read(self):
        text = RUN14.replace("[ ] **APPROVED**", "[x] **APPROVED**")
        assert parse_markdown_feedback(text) is None

    @pytest.mark.parametrize("raw", ["", "   ", "just prose", "{\"verdict\": \"APPROVED\"}"])
    def test_nothing_template_shaped_is_none(self, raw):
        assert parse_markdown_feedback(raw) is None


class _Scripted:
    """A provider that answers from a list and counts its calls."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.calls: list[tuple[str, str]] = []

    def invoke(self, system, prompt, **_kwargs):
        self.calls.append((system, prompt))
        return SimpleNamespace(response=self.answers.pop(0))


JSON_ANSWER = json.dumps({
    "verdict": "APPROVED",
    "rationale": "## Tier 1: BLOCKING Issues\n- [ ] No issues found.\n## Tier 2: HIGH PRIORITY Issues\n- [ ] No issues found.",
    "feedback_items": [],
    "open_questions": [],
})


class TestTheHelperAsksAtMostTwice:
    def test_json_first_time_is_one_call(self):
        provider = _Scripted([JSON_ANSWER])
        result = _invoke_reviewer_with_feedback_schema(provider, "draft", "system")
        assert result["verdict"] == "APPROVED"
        assert len(provider.calls) == 1

    def test_the_template_first_time_is_one_call(self, capsys):
        provider = _Scripted([RUN14])
        result = _invoke_reviewer_with_feedback_schema(provider, "draft", "system")
        assert result["verdict"] == "REVISE"
        assert len(provider.calls) == 1
        assert "0702c review template" in capsys.readouterr().out

    def test_garbage_then_json_is_two_calls_and_the_second_names_the_defect(self):
        provider = _Scripted(["I decline to answer in any format.", JSON_ANSWER])
        result = _invoke_reviewer_with_feedback_schema(provider, "draft", "system")
        assert result["verdict"] == "APPROVED"
        assert len(provider.calls) == 2
        assert "ONLY that JSON object" in provider.calls[1][0]
        assert provider.calls[1][0].startswith("system")

    def test_garbage_then_template_is_read(self):
        provider = _Scripted(["nothing here", RUN14])
        result = _invoke_reviewer_with_feedback_schema(provider, "draft", "system")
        assert result["verdict"] == "REVISE"
        assert len(provider.calls) == 2

    def test_garbage_twice_is_still_rejected_and_never_a_third_call(self):
        provider = _Scripted(["nothing here", "still nothing"])
        with pytest.raises(StructuredContractError) as excinfo:
            _invoke_reviewer_with_feedback_schema(provider, "draft", "system")
        assert "unreadable twice" in str(excinfo.value)
        assert len(provider.calls) == 2
        assert provider.answers == []
