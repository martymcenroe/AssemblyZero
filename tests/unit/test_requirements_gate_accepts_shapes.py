"""#2830: the requirements gate reads a verdict wherever the model put it.

Run 13 on boostgauge #4 (`run-issue4-014806`, 2026-09-05) asked the gate's
question three times and got three well-formed JSON answers naming real
contradictions, each in a shape the parser refused: `{"issues": [...]}` with
`quote_1`/`quote_2`/`divergence`; a bare list with `quotes`/`explanation`;
`{"issues": [...]}` with `quotes`/`description`. The run paid 1,327 s for no
verdict. The three responses are the fixtures here, byte for byte, from the
run's call recording.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from assemblyzero.speedrun.must_resolve import unanswerable_reason
from assemblyzero.workflows.requirements.nodes.analyze_requirements import (
    _parse_analysis,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "requirements_gate_shapes"
RECORDED = sorted(FIXTURES.glob("run13-*.txt"))


class TestTheRecordedShapes:
    def test_three_recordings_are_present(self):
        assert [p.name for p in RECORDED] == [
            "run13-call1-fenced-issues-quote_1.txt",
            "run13-call2-bare-list-quotes.txt",
            "run13-call3-fenced-issues-quotes.txt",
        ]

    @pytest.mark.parametrize("path", RECORDED, ids=[p.stem for p in RECORDED])
    def test_each_recording_yields_one_conflict_the_filer_can_ask(self, path):
        parsed = _parse_analysis(path.read_text(encoding="utf-8"))
        assert parsed is not None, "the gate threw this answer away on 2026-09-05"
        assert parsed["is_consistent"] is False
        assert len(parsed["conflicts"]) == 1
        conflict = parsed["conflicts"][0]
        assert conflict["criterion_a"]
        assert conflict["criterion_b"]
        assert conflict["diverging_situation"]
        assert conflict["criterion_a"] != conflict["criterion_b"]
        # The filer's own contract (#2462): a conflict it can put to the operator.
        assert unanswerable_reason(conflict) is None

    def test_the_first_recording_carries_two_notes_that_are_not_conflicts(self):
        parsed = _parse_analysis(RECORDED[0].read_text(encoding="utf-8"))
        assert parsed is not None
        categories = [n["category"] for n in parsed["notes"]]
        assert categories == [
            "UNDEFINED OR MULTIPLY-DEFINED TERMS",
            "NON-DISCRIMINATING TESTS",
        ]
        for note in parsed["notes"]:
            assert not (note["criterion_a"] and note["criterion_b"])

    def test_the_first_recording_names_the_memory_criterion(self):
        parsed = _parse_analysis(RECORDED[0].read_text(encoding="utf-8"))
        assert parsed is not None
        conflict = parsed["conflicts"][0]
        assert "memory %" in conflict["criterion_a"].lower()
        assert "virtual_memory" in conflict["criterion_b"]

    def test_the_second_and_third_name_the_sweep_versus_the_tick(self):
        for path in RECORDED[1:]:
            parsed = _parse_analysis(path.read_text(encoding="utf-8"))
            assert parsed is not None
            conflict = parsed["conflicts"][0]
            assert "1% CPU" in conflict["criterion_a"]
            assert "sweep" in conflict["criterion_b"] or "sweep" in conflict["criterion_a"]


class TestTheCanonicalShapeIsUnchanged:
    def test_clean(self):
        parsed = _parse_analysis(json.dumps({"is_consistent": True, "conflicts": []}))
        assert parsed == {"is_consistent": True, "conflicts": [], "notes": []}

    def test_one_conflict(self):
        conflict = {
            "criterion_a": "floor = highest value still in the window",
            "criterion_b": "floor drifts toward the most recent value",
            "diverging_situation": "when the window maximum is not the latest sample",
        }
        parsed = _parse_analysis(json.dumps({"is_consistent": False, "conflicts": [conflict]}))
        assert parsed is not None
        assert parsed["is_consistent"] is False
        assert parsed["conflicts"] == [conflict]
        assert parsed["notes"] == []

    def test_fenced_canonical(self):
        text = "```json\n" + json.dumps({"is_consistent": True, "conflicts": []}) + "\n```"
        parsed = _parse_analysis(text)
        assert parsed is not None
        assert parsed["is_consistent"] is True

    def test_the_models_own_is_consistent_wins_over_the_derived_one(self):
        # It said inconsistent and listed nothing usable: the consumer already
        # treats "no conflicts" as clean, so the flag is kept as stated and the
        # consumer decides -- exactly as before #2830.
        parsed = _parse_analysis(json.dumps({"is_consistent": False, "conflicts": []}))
        assert parsed is not None
        assert parsed["is_consistent"] is False
        assert parsed["conflicts"] == []


class TestNoVerdictIsStillNoVerdict:
    @pytest.mark.parametrize("raw", [
        "",
        "not json at all",
        json.dumps({"verdict": "fine"}),
        json.dumps({"conflicts": "none"}),
        json.dumps(42),
    ])
    def test_nothing_to_read_is_none(self, raw):
        assert _parse_analysis(raw) is None

    def test_an_empty_list_is_a_clean_verdict(self):
        parsed = _parse_analysis("[]")
        assert parsed is not None
        assert parsed["is_consistent"] is True
        assert parsed["conflicts"] == []

    def test_a_finding_with_one_quote_is_a_note_not_a_conflict(self):
        parsed = _parse_analysis(json.dumps({
            "issues": [{"type": "CONFLICTING CRITERIA", "quotes": ["only one"],
                        "explanation": "half an answer"}],
        }))
        assert parsed is not None
        assert parsed["conflicts"] == []
        assert len(parsed["notes"]) == 1
        assert parsed["is_consistent"] is True
