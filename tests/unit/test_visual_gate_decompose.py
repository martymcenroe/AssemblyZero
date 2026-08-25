"""Feedback decomposition against the worked example (#2518).

The design comment maps the operator's actual five-part 2026-08-25 message
onto gate actions; that table is the acceptance scenario. The transport is a
fake returning the decomposition the design specifies -- what these tests
exercise is OUR half: prompt construction, parsing, validation, and the
plan the guardrails produce from the five items. The model's half is judged
by the operator every time the loop runs.
"""

from __future__ import annotations

import json

import pytest

from assemblyzero.visual_gate.modify import (
    build_prompt,
    decompose,
    parse_items,
    plan_from_items,
)

OPERATOR_MESSAGE = (
    "needle is awesome. red bar should be thinner, start further from "
    "center. do we specify rings/zones... i think that should be specific. "
    "BOOSTGAUGE should be much lower, in line with the 0 and 100 tickmarks. "
    "the red seems like a brick red, not really the red of a tachometer"
)

#: The design table's decomposition, as the model pass should return it.
WORKED_EXAMPLE_RESPONSE = json.dumps([
    {"kind": "approve-element", "key": "needle_rgb", "value": None,
     "note": "needle is awesome"},
    {"kind": "modify-geometry", "key": "band_inner", "value": 0.88,
     "note": "red bar should be thinner, start further from center"},
    {"kind": "contract-gap", "key": None, "value": None,
     "note": "rings/zones should be specified"},
    {"kind": "modify-geometry", "key": "wordmark_y", "value": 0.67,
     "note": "BOOSTGAUGE in line with the 0 and 100 tickmarks "
             "(computed from the tick geometry, not guessed)"},
    {"kind": "modify-colour", "key": "band_rgb", "value": None,
     "candidates": [[170, 15, 25], [130, 10, 20], [150, 20, 60]],
     "note": "brick reads as brown, wants a tachometer red"},
])

MANIFEST = {
    "values": {
        "band_inner": {"value": 0.80, "source": "contract"},
        "band_rgb": {"value": [155, 48, 32], "source": "contract"},
        "needle_rgb": {"value": [247, 57, 35], "source": "ruling #228", "ruled": True},
        "wordmark_y": {"value": 0.55, "source": "contract"},
    },
    "palette": {
        "needle": [247, 57, 35],
        "white": [255, 255, 255],
        "face": [10, 10, 12],
    },
}


def fake_transport(system: str, content: str) -> str:
    fake_transport.calls.append((system, content))
    return WORKED_EXAMPLE_RESPONSE


fake_transport.calls = []


@pytest.fixture(autouse=True)
def _reset_calls():
    fake_transport.calls = []


class TestThePromptCarriesWhatTheModelNeeds:
    def test_the_manifest_keys_and_values_are_in_the_prompt(self):
        _, content = build_prompt(OPERATOR_MESSAGE, MANIFEST)
        for key in ("band_inner", "band_rgb", "needle_rgb", "wordmark_y"):
            assert key in content

    def test_ruled_values_are_marked_so_the_model_knows_the_pins(self):
        _, content = build_prompt(OPERATOR_MESSAGE, MANIFEST)
        assert "needle_rgb" in content
        assert "[RULED" in content

    def test_the_operators_words_travel_verbatim(self):
        _, content = build_prompt(OPERATOR_MESSAGE, MANIFEST)
        assert OPERATOR_MESSAGE in content

    def test_the_system_prompt_forbids_invented_keys_and_demands_candidates(self):
        system, _ = build_prompt(OPERATOR_MESSAGE, MANIFEST)
        assert "never invent a contract key" in system
        assert "candidates" in system


class TestTheWorkedExampleDecomposes:
    def test_five_items_come_back_with_the_designs_classes(self):
        items = decompose(OPERATOR_MESSAGE, MANIFEST, fake_transport)

        assert [item.kind for item in items] == [
            "approve-element", "modify-geometry", "contract-gap",
            "modify-geometry", "modify-colour",
        ]

    def test_the_plan_takes_the_designs_machine_actions(self):
        """Row by row: pin the needle; band 0.80 -> 0.88; record the zone
        gap; wordmark 0.55 -> 0.67 anchored; tachometer red becomes in-floor
        candidates for a second look, never a single guess."""
        items = decompose(OPERATOR_MESSAGE, MANIFEST, fake_transport)
        plan = plan_from_items(items, MANIFEST, separation_floor=85.0, ruled={})

        assert plan.pinned == ["needle_rgb"]
        assert plan.deltas == {"band_inner": 0.88, "wordmark_y": 0.67}
        assert "rings/zones" in plan.gaps[0]
        assert set(map(tuple, plan.candidate_sets["band_rgb"])) == {
            (170, 15, 25), (130, 10, 20), (150, 20, 60),
        }
        assert not plan.halted_on_ruling
        assert plan.floor_refusals == []

    def test_the_pinned_needle_would_refuse_a_later_delta(self):
        """approve-element means excluded from further deltas -- the design's
        first row, enforced within the same pass."""
        items = decompose(OPERATOR_MESSAGE, MANIFEST, fake_transport)
        from assemblyzero.visual_gate.modify import FeedbackItem
        items.append(FeedbackItem(
            kind="modify-colour", key="needle_rgb", value=[130, 10, 20],
            note="darker needle after all",
        ))

        plan = plan_from_items(items, MANIFEST, separation_floor=85.0, ruled={})

        assert "needle_rgb" not in plan.deltas
        assert "needle_rgb" not in plan.candidate_sets


class TestParsingIsStrict:
    def test_garbage_raises_rather_than_rendering_nobodys_intent(self):
        with pytest.raises(ValueError):
            parse_items("I think you should make it nicer.")

    def test_an_unknown_kind_raises(self):
        with pytest.raises(ValueError):
            parse_items('[{"kind": "vibe-shift", "key": null}]')

    def test_a_json_array_inside_prose_is_still_found(self):
        items = parse_items(
            "Here is the decomposition you asked for:\n"
            '[{"kind": "contract-gap", "key": null, "value": null, '
            '"note": "zones unspecified"}]\nLet me know if you need more.'
        )
        assert len(items) == 1
        assert items[0].kind == "contract-gap"
