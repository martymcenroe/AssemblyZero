"""#4484: the requirements gate never reads a finding it cannot name as clean.

A finding was a conflict or it was a note, so one in keys the gate has no name for
became a note, and `is_consistent` came out true, or the model's own false was
overridden by `or not conflicts`. The answer went on to the drafter under the line
"Requirements internally consistent." The same hole is why adding a model's key to
`_FINDINGS_KEYS` would have turned every conflict in #4483's recorded answers into
a clean verdict; the shapes below are those answers with their text replaced.
"""

from __future__ import annotations

import importlib
import json

import pytest

from assemblyzero.core.llm_provider import LLMCallResult
from assemblyzero.workflows.requirements.graph import route_after_analyze_requirements

ar = importlib.import_module("assemblyzero.workflows.requirements.nodes.analyze_requirements")

UNNAMED = {
    "statement_1": "floor = highest value still in the window",
    "statement_2": "floor drifts toward the most recent value",
    "divergence_situation": "when the window maximum is not the latest sample",
}
NAMED = {
    "criterion_a": UNNAMED["statement_1"],
    "criterion_b": UNNAMED["statement_2"],
    "diverging_situation": UNNAMED["divergence_situation"],
}


def _result(answer) -> LLMCallResult:
    response = answer if isinstance(answer, str) else json.dumps(answer)
    return LLMCallResult(
        success=True, response=response, raw_response=response, error_message=None,
        provider="fake", model_used="fake-model", duration_ms=1, attempts=1,
    )


class _Provider:
    def __init__(self, *answers):
        self._answers = list(answers)
        self.calls = 0

    def invoke(self, **kwargs):
        self.calls += 1
        answer = self._answers.pop(0) if len(self._answers) > 1 else self._answers[0]
        return _result(answer)


@pytest.fixture
def gate(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        "assemblyzero.speedrun.must_resolve.file_all_conflicts",
        lambda repo, issue, conflicts, **k: None,
    )
    monkeypatch.setattr(
        "assemblyzero.speedrun.prompt_telemetry.record_failures", lambda *a, **k: None,
    )
    monkeypatch.setattr("assemblyzero.speedrun.must_resolve.run_context", lambda: ("run-1", None))
    monkeypatch.setattr(ar, "_sleep", lambda seconds: None)

    def run(*answers):
        provider = _Provider(*answers)
        monkeypatch.setattr(
            "assemblyzero.core.llm_provider.get_provider", lambda spec, *a, **k: provider,
        )
        out = ar.analyze_requirements({
            "issue_title": "t", "issue_body": "some requirement text",
            "issue_number": 332, "target_repo": str(tmp_path),
        })
        return out, provider.calls, capsys.readouterr().out

    return run


def _halted_unverified(out: dict) -> bool:
    return (
        bool(out.get("requirements_unverified"))
        and ar.REQUIREMENTS_UNVERIFIED_MARKER in out.get("error_message", "")
        and route_after_analyze_requirements(out) == "HALT"
    )


class TestTheCleanPath:
    def test_t1_model_says_false_with_a_finding_it_cannot_name(self, gate):
        out, _, printed = gate({"is_consistent": False, "conflicts": [UNNAMED]})

        assert _halted_unverified(out)
        assert "Requirements internally consistent" not in printed

    def test_t1_model_says_false_and_names_nothing(self, gate):
        out, calls, printed = gate({"is_consistent": False, "conflicts": []})

        assert _halted_unverified(out)
        assert calls == 3
        assert "named no conflict" in out["error_message"]
        assert "Requirements internally consistent" not in printed

    def test_t1_model_says_false_and_gives_only_notes(self, gate):
        answer = {"is_consistent": False, "issues": [{"term": "the floor"}]}

        out, _, printed = gate(answer)

        assert _halted_unverified(out)
        assert "Requirements internally consistent" not in printed

    def test_t1_a_conflict_quoted_in_full_beats_a_model_saying_true(self, gate):
        out, calls, printed = gate({"is_consistent": True, "conflicts": [NAMED]})

        assert ar.REQUIREMENTS_CONFLICT_MARKER in out["error_message"]
        assert calls == 2, "it reproduced on the confirming ask (#3747)"
        assert "Requirements internally consistent" not in printed

    def test_a_clean_answer_is_still_clean(self, gate):
        out, calls, printed = gate({"is_consistent": True, "conflicts": []})

        assert out == {}
        assert calls == 1
        assert "Requirements internally consistent" in printed


class TestAFindingTheGateCannotRead:
    def test_t2_it_retries_then_halts_and_quotes_the_finding(self, gate):
        out, calls, _ = gate({"conflicts": [UNNAMED]})

        assert _halted_unverified(out)
        assert calls == 3
        assert "a finding the gate cannot read" in out["error_message"]
        assert "statement_1" in out["error_message"]

    def test_t2_a_retry_that_answers_properly_reaches_a_verdict(self, gate):
        out, calls, _ = gate({"conflicts": [UNNAMED]}, {"is_consistent": True, "conflicts": []})

        assert out == {}
        assert calls == 2

    def test_a_category_that_says_conflict_does_not_rescue_it(self):
        finding = {"category": "CONFLICTING CRITERIA", **UNNAMED}

        assert ar._parse_analysis(json.dumps({"issues": [finding]})) is None


RECORDED_SHAPES = {
    "one conflict, divergence_situation": {
        "conflicting_criteria": [UNNAMED],
        "undefined_or_multiply_defined_terms": [{"term": "x", "ambiguity": "y"}],
        "non_discriminating_tests": [{"test_quote": "t", "reason": "r"}],
    },
    "one conflict, verbatim_usages": {
        "conflicting_criteria": [UNNAMED],
        "undefined_or_multiply_defined_terms": [{"term": "x", "verbatim_usages": ["y"]}],
        "non_discriminating_tests": [{"test_case": "t", "why_non_discriminating": "r"}],
    },
    "two conflicts, divergence": {
        "conflicting_criteria": [
            {"statement_1": "a", "statement_2": "b", "divergence": "c"},
            {"statement_1": "d", "statement_2": "e", "divergence": "f"},
        ],
        "undefined_or_multiply_defined_terms": [],
        "non_discriminating_tests": [],
    },
}


class TestTheKeyListIsNoLongerAFailOpen:
    @pytest.mark.parametrize("answer", RECORDED_SHAPES.values(), ids=RECORDED_SHAPES.keys())
    def test_t3_a_reported_conflict_is_never_clean_with_its_key_on_the_list(
        self, monkeypatch, answer,
    ):
        monkeypatch.setattr(ar, "_FINDINGS_KEYS", (*ar._FINDINGS_KEYS, "conflicting_criteria"))

        assert ar._verdict_of(_result(answer)) is None

    @pytest.mark.parametrize("answer", RECORDED_SHAPES.values(), ids=RECORDED_SHAPES.keys())
    def test_t3_today_they_are_no_verdict_too(self, answer):
        assert ar._verdict_of(_result(answer)) is None


class TestWhatStaysANote:
    @pytest.mark.parametrize("finding", [
        {"term": "the floor", "explanation": "used two ways"},
        {"category": "UNDEFINED OR MULTIPLY-DEFINED TERMS", "explanation": "x"},
        {"type": "NON-DISCRIMINATING TESTS", "description": "y"},
        {"type": "CONFLICTING CRITERIA", "quotes": ["only one"], "explanation": "half"},
    ])
    def test_t4_a_finding_the_gate_can_show_is_a_note(self, finding):
        parsed = ar._parse_analysis(json.dumps({"issues": [finding]}))

        assert parsed is not None
        assert parsed["conflicts"] == []
        assert len(parsed["notes"]) == 1
