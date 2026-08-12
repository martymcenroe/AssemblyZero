"""A live watch must never advertise a stop that cannot happen (Closes #2188).

During a watched roll (boostgauge, 2026-08-10 ~01:00) the follower's NEXT line
at the adversarial-review node read:

    NEXT human gate: verdict (the verdict gate is on, or a question needs a
    human) | finalize (approved with the verdict gate off) | ...

The campaign runs every roll with the verdict gate off. Operator ruling: no
human gates, ever -- and an operator reading "human gate: verdict" during a live
watch is being told the roll might stop and wait for them, which it never will.

The edge is deliberately NOT hidden. It is genuinely reachable: a reviewer
marking a question HUMAN_REQUIRED routes there whatever the config says
(`route_after_review`). What was wrong is calling a pass-through a gate --
with the gate off, `human_gate_verdict` auto-routes on the verdict and returns
without asking anything. Hiding a live edge would trade this misreading for a
worse one.
"""

import pytest

from assemblyzero.workflows.narration import (
    GATE_NODES,
    GATE_OFF_NOTE,
    _line_for,
    narrated,
)
from assemblyzero.workflows.requirements.atlas import ATLAS, TOTAL_STEPS

GATES_OFF = {"config_gates_draft": False, "config_gates_verdict": False}
GATES_ON = {"config_gates_draft": True, "config_gates_verdict": True}


def _render(node_id: str, state) -> str:
    return "\n".join(_line_for(node_id, ATLAS, TOTAL_STEPS, state))


class TestTheReviewNodesNextLine:
    """The exact line the operator was reading."""

    def test_it_no_longer_advertises_a_stop(self):
        out = _render("N3_review", GATES_OFF)

        assert "the verdict gate is on, or a question needs a human" not in out, (
            "half that condition cannot happen with the gate off, and the "
            "operator read the whole line as 'this may stop and wait for me'"
        )
        assert GATE_OFF_NOTE in out

    def test_the_edge_is_still_shown(self):
        """Reachable via HUMAN_REQUIRED whatever the config says. Hiding it
        would be the same defect pointed the other way."""
        assert "human gate: verdict" in _render("N3_review", GATES_OFF)

    def test_the_live_branches_are_untouched(self):
        out = _render("N3_review", GATES_OFF)
        assert "approved with the verdict gate off" in out
        assert "blocked or unanswered questions; revise" in out


class TestEnteringAConfigDeadGate:
    """Filtering NEXT alone is not enough: the run can still ENTER the node,
    and its own NODE line called it a human checkpoint."""

    def test_the_node_line_says_it_does_not_wait(self):
        out = _render("N4_human_gate_verdict", GATES_OFF)
        assert GATE_OFF_NOTE in out

    def test_with_the_gate_on_it_is_described_as_a_gate(self):
        out = _render("N4_human_gate_verdict", GATES_ON)
        assert GATE_OFF_NOTE not in out
        assert "optional human checkpoint" in out


class TestTheDraftGateToo:
    def test_the_draft_gate_is_annotated_when_off(self):
        assert GATE_OFF_NOTE in _render("N1b_validate_test_plan", GATES_OFF)

    def test_and_not_when_on(self):
        assert GATE_OFF_NOTE not in _render("N1b_validate_test_plan", GATES_ON)


class TestUnknownIsNotOff:
    """Announcing OFF on a run that might actually stop is the same defect
    pointed the other way, so an absent key changes nothing."""

    def test_an_absent_key_leaves_the_atlas_description(self):
        out = _render("N3_review", {})
        assert GATE_OFF_NOTE not in out
        assert "the verdict gate is on, or a question needs a human" in out

    def test_no_state_at_all_leaves_it_alone(self):
        out = "\n".join(_line_for("N3_review", ATLAS, TOTAL_STEPS))
        assert GATE_OFF_NOTE not in out

    @pytest.mark.parametrize("state", [None, {}, 0, "not a mapping"])
    def test_a_useless_state_never_raises(self, state):
        assert _line_for("N3_review", ATLAS, TOTAL_STEPS, state)


class TestNarrationStillNeverCostsARun:
    def test_a_node_still_runs_when_narration_explodes(self, capsys):
        class _Exploding:
            def __contains__(self, _key):
                raise RuntimeError("state is on fire")

        ran = []
        wrapped = narrated(
            "N3_review", lambda s: ran.append(s) or {"ok": True}, ATLAS, TOTAL_STEPS
        )
        out = wrapped(_Exploding())
        capsys.readouterr()

        assert out == {"ok": True}
        assert len(ran) == 1

    def test_the_node_still_narrates_normally(self, capsys):
        wrapped = narrated("N3_review", lambda s: {}, ATLAS, TOTAL_STEPS)
        wrapped(GATES_OFF)

        printed = capsys.readouterr().out
        assert "NODE" in printed and "NEXT" in printed
        assert GATE_OFF_NOTE in printed


class TestTheMapMatchesTheGraph:
    def test_every_gate_node_is_in_the_atlas(self):
        """A renamed node would silently stop being annotated."""
        from assemblyzero.workflows.implementation_spec.atlas import (
            ATLAS as SPEC_ATLAS,
        )

        known = set(ATLAS) | set(SPEC_ATLAS)
        missing = set(GATE_NODES) - known
        assert not missing, (
            f"GATE_NODES names {sorted(missing)}, which no atlas declares -- "
            "so those gates would never be annotated"
        )

    def test_every_atlas_gate_node_is_covered(self):
        """A gate added later must not quietly go back to advertising a stop."""
        gates = {n for n in ATLAS if "human_gate" in n}
        assert gates <= set(GATE_NODES), (
            f"{sorted(gates - set(GATE_NODES))} is a human gate the narration "
            "does not know how to describe when it is switched off"
        )
