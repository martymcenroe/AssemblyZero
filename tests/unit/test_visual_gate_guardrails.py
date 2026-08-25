"""The two non-negotiable guardrails (#2518): the separation floor by
computation, and no silent override of a landed ruling."""

from __future__ import annotations


from assemblyzero.visual_gate.floor import floor_violations, rgb_distance
from assemblyzero.visual_gate.modify import FeedbackItem, plan_from_items

PALETTE = {
    "needle": [247, 57, 35],     # candy-apple, ruling #228
    "white": [255, 255, 255],
    "face": [10, 10, 12],
}
FLOOR = 85.0

MANIFEST = {
    "values": {
        "band_inner": {"value": 0.80, "source": "contract"},
        "band_rgb": {"value": [155, 48, 32], "source": "contract"},
        "needle_rgb": {"value": [247, 57, 35], "source": "ruling #228", "ruled": True},
    },
    "palette": PALETTE,
}


class TestTheFloorIsComputedNotEyeballed:
    def test_the_live_sessions_distance_is_reproduced(self):
        """Crimson sits 88 from candy-apple -- the number the contract quotes."""
        assert round(rgb_distance((170, 15, 25), (247, 57, 35))) == 88

    def test_an_under_floor_candidate_is_refused_with_the_arithmetic(self):
        close_to_needle = (240, 60, 40)  # ~9 from candy-apple

        findings = floor_violations(close_to_needle, PALETTE, FLOOR)

        assert len(findings) == 1
        assert "'needle'" in findings[0]
        assert "separation floor of 85" in findings[0]

    def test_the_replaced_entry_is_exempt_from_its_own_floor(self):
        """A colour may sit anywhere relative to the value it replaces."""
        palette = dict(PALETTE, band=[155, 48, 32])
        near_old_band = (150, 50, 30)

        assert floor_violations(near_old_band, palette, FLOOR, replacing="band") == []

    def test_exactly_at_the_floor_passes(self):
        """The contract says no two entries are CLOSER than the floor."""
        a, b = (0, 0, 0), (85, 0, 0)
        assert rgb_distance(a, b) == 85.0
        assert floor_violations(b, {"a": a}, 85.0) == []


class TestAnUnderFloorDeltaNeverRenders:
    def test_the_plan_refuses_it_and_records_why(self):
        items = [FeedbackItem(
            kind="modify-colour", key="band_rgb", value=[240, 60, 40],
            note="redder please",
        )]

        plan = plan_from_items(items, MANIFEST, separation_floor=FLOOR, ruled={})

        assert plan.deltas == {}
        assert plan.candidate_sets == {}
        assert len(plan.floor_refusals) == 1
        assert "under the contract's separation floor" in plan.floor_refusals[0]

    def test_only_in_floor_candidates_survive_an_adjectival_ask(self):
        items = [FeedbackItem(
            kind="modify-colour", key="band_rgb", value=None,
            candidates=((170, 15, 25), (240, 60, 40), (130, 10, 20)),
            note="a real tachometer red",
        )]

        plan = plan_from_items(items, MANIFEST, separation_floor=FLOOR, ruled={})

        assert plan.candidate_sets == {"band_rgb": [[170, 15, 25], [130, 10, 20]]}
        assert len(plan.floor_refusals) == 1, "the under-floor one is named"


class TestARulingIsNeverSilentlyOverridden:
    def test_a_delta_on_a_manifest_ruled_value_halts(self):
        items = [FeedbackItem(
            kind="modify-colour", key="needle_rgb", value=[200, 0, 0],
            note="make the needle darker",
        )]

        plan = plan_from_items(items, MANIFEST, separation_floor=FLOOR, ruled={})

        assert plan.halted_on_ruling
        assert plan.deltas == {}
        assert "'needle_rgb'" in plan.ruling_conflicts[0]
        assert "landed ruling" in plan.ruling_conflicts[0]

    def test_a_delta_on_a_config_ruled_value_halts(self):
        items = [FeedbackItem(
            kind="modify-geometry", key="band_inner", value=0.5,
            note="band nearly to the center",
        )]

        plan = plan_from_items(
            items, MANIFEST, separation_floor=FLOOR, ruled={"band_inner": 0.88},
        )

        assert plan.halted_on_ruling
        assert "'band_inner'" in plan.ruling_conflicts[0]

    def test_every_contradiction_is_named_in_one_pass(self):
        """The operator rules once, not once per relaunch."""
        items = [
            FeedbackItem(kind="modify-colour", key="needle_rgb",
                         value=[200, 0, 0], note="darker needle"),
            FeedbackItem(kind="modify-geometry", key="band_inner",
                         value=0.5, note="wider band"),
        ]

        plan = plan_from_items(
            items, MANIFEST, separation_floor=FLOOR, ruled={"band_inner": 0.88},
        )

        assert len(plan.ruling_conflicts) == 2

    def test_restating_the_ruled_value_is_not_a_contradiction(self):
        items = [FeedbackItem(
            kind="modify-geometry", key="band_inner", value=0.88,
            note="keep the band as approved",
        )]

        plan = plan_from_items(
            items, MANIFEST, separation_floor=FLOOR, ruled={"band_inner": 0.88},
        )

        assert not plan.halted_on_ruling
        assert plan.deltas == {"band_inner": 0.88}


class TestPinsAndGaps:
    def test_an_approved_element_takes_no_further_deltas(self):
        items = [
            FeedbackItem(kind="approve-element", key="band_rgb", value=None,
                         note="the band is right now"),
            FeedbackItem(kind="modify-colour", key="band_rgb",
                         value=[130, 10, 20], note="darker band"),
        ]

        plan = plan_from_items(items, MANIFEST, separation_floor=FLOOR, ruled={})

        assert plan.pinned == ["band_rgb"]
        assert plan.deltas == {}

    def test_a_contract_gap_is_recorded_not_guessed_at(self):
        items = [FeedbackItem(
            kind="contract-gap", key=None, value=None,
            note="rings/zones should be specified",
        )]

        plan = plan_from_items(items, MANIFEST, separation_floor=FLOOR, ruled={})

        assert plan.gaps == ["rings/zones should be specified"]
        assert plan.deltas == {}
