"""A gate that judges model output may advise; the budget ends the run (#2723).

Operator ruling 2026-09-02. The evidence: of boostgauge's 135 banner-bearing
kills, 59 were a gate refusing the drafter's own output, and 19 of those were
the stagnation guards. One of the 19 is `run-issue4-172600` -- the furthest any
run has reached, green phase with three passing at 72% coverage -- killed by the
coverage guard with four iterations unspent.

This file pins the half of the policy that landed: the five stagnation rows are
advisory, they still SEE what they saw, and nothing on the way to them ends a
run that a budget would not have ended anyway. The other fourteen model-output
halt rows are not yet moved; `test_the_ratchet_records_what_is_left` is what
keeps that number honest and falling.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from assemblyzero.core.gate_registry import (
    ACTION_ADVISE,
    ACTION_HALT,
    GATE_REGISTRY,
    JUDGES_BUDGET,
    JUDGES_INFRASTRUCTURE,
    JUDGES_MODEL_OUTPUT,
    advised,
    gate_key_of,
    halt_counts,
    registry_by_key,
)

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "tests" / "fixtures" / "gate_registry_baseline.json"

STAGNATION_KEYS = (
    "impl.stagnation.coverage",
    "impl.stagnation.test_count",
    "impl.stagnation.test_identity",
    "impl.stagnation.full_suite",
    "impl.stagnation.e2e",
)


class TestTheStagnationGuardsNoLongerEndARun:
    @pytest.mark.parametrize("key", STAGNATION_KEYS)
    def test_the_row_advises(self, key):
        assert registry_by_key()[key].action == ACTION_ADVISE

    @pytest.mark.parametrize("key", STAGNATION_KEYS)
    def test_the_row_names_no_halt_site(self, key):
        """An advisory row with a halt site would mean the walker found code
        that still ends a run under a key that says it does not."""
        assert registry_by_key()[key].sites == ()
        assert registry_by_key()[key].decided_in, (
            "a row with no sites must say where it lives, or it is unfindable"
        )

    @pytest.mark.parametrize("key", STAGNATION_KEYS)
    def test_the_row_still_judges_model_output(self, key):
        """The classification is a fact about the gate and does not change
        because its consequence did. Rewriting `judges` to make the
        model-output count fall would be cooking the number the policy is
        measured by."""
        assert registry_by_key()[key].judges == JUDGES_MODEL_OUTPUT


class TestAdvised:
    def test_it_carries_the_gate_key_like_a_halt_does(self):
        message = advised("impl.stagnation.coverage", "Coverage stagnant: 72 -> 70.")
        assert gate_key_of(message) == "impl.stagnation.coverage"

    def test_it_says_the_run_continues(self):
        """The identical sentence was terminal for as long as these guards have
        existed, and a reader will remember it that way."""
        message = advised("impl.stagnation.e2e", "E2E stagnant: 2 -> 2 passed.")
        assert "Continuing; the budget decides." in message

    def test_it_refuses_a_key_whose_row_still_halts(self):
        """An advisory printed by a gate that then ends the run anyway is the
        worst of both: a log that says the run continued and a run that did
        not."""
        with pytest.raises(ValueError, match="halt row"):
            advised("impl.green.iteration_cap", "Green phase failed after 5.")

    def test_it_refuses_an_unregistered_key(self):
        with pytest.raises(KeyError):
            advised("impl.not.a.gate", "x")


class TestOnlyABudgetOrTheEnvironmentEndsTheGreenLoop:
    """The policy's real claim, checked against the registry rather than
    asserted: everything that can still end the implement-iterate loop is a
    spending limit or a broken environment."""

    LOOP_ENDERS = (
        "impl.green.iteration_cap",
        "impl.circuit_breaker",
        "impl.e2e_cap",
        "impl.e2e_safety_limit",
    )

    @pytest.mark.parametrize("key", LOOP_ENDERS)
    def test_each_one_is_a_budget_or_the_environment(self, key):
        row = registry_by_key()[key]
        assert row.action == ACTION_HALT
        assert row.judges in (JUDGES_BUDGET, JUDGES_INFRASTRUCTURE), (
            f"{key} ends the loop while judging {row.judges}"
        )


class TestTheRatchet:
    def test_the_baseline_matches_the_registry(self):
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
        assert halt_counts() == baseline["halt_rows_per_stage"]

    def test_the_denominator_matches_what_it_was_measured_against(self):
        """`measured_against` exists so a reader can see the denominator
        without re-running anything, which only works while it is true (#2780).

        The enforced counts were asserted and this block was not, so it could
        only be right by accident of who last regenerated the baseline: #2736
        wrote it against 184 walked files, #2733 then added
        `workflows/testing/atlas.py` -- walked, no halt site in it -- and the
        stated denominator quietly became wrong while every enforced number
        stayed right.

        Asserted by re-walking rather than against a literal, or this becomes
        one more number nobody updates.
        """
        from pathlib import Path

        from assemblyzero.core.gate_registry import GATE_REGISTRY, scan_halt_sites

        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
        sites, coverage = scan_halt_sites(Path(__file__).resolve().parents[2])
        assert baseline["measured_against"] == {
            "files_scanned": coverage.files_scanned,
            "halt_sites": len(sites),
            "gates": len(GATE_REGISTRY),
        }, (
            "the baseline's stated denominator no longer matches the tree it "
            "claims to describe; regenerate with "
            "`tools/audit_halt_sites.py --write-baseline`"
        )

    def test_the_ratchet_records_what_is_left(self):
        """3 model-output rows still halt. The number is pinned so it can only
        fall: #2723 took it from 24 to 19 by retiring the five stagnation
        guards, #2736 took it to 18 by making `impl.path_enforcement` advisory
        on the operator's ruling of 2026-09-04, and that day's three routing
        rulings take it down in three steps -- 12 for the six retry-budget
        rows whose halt belongs to the cap that decided it (#2759, #2760,
        #2762, #2763, #2764, #2774), 8 for the four rows judging output nobody
        in the loop can revise (#2768, #2769, #2770, #2771), and 5 for the
        three guards against an impossible state (#2765, #2772, #2773).

        #2753 then took it to 4 by retiring `impl.test_file_validation` with
        the unreachable node its only site lived in. That one is a fall the
        ratchet should read carefully: the count dropped without any gate
        softening, because the row had never been able to fire at all.

        #2775 then took it to 3, and that one is worth reading carefully too.
        `impl.test_plan_revision_incomplete` judged model output only because
        it fired on the FIRST short revision. It could not, in fact, fire at
        all: N1 clears `error_message` one node later (#1490), so the reason
        it recorded never reached a router, and the run spent its whole
        revision allowance before ending at `end` with no bundle. With the
        edge out of N1.5 made conditional and the reason recorded only at the
        cap, what is left is the allowance running out -- a budget, under
        ruling 1 of #2723.

        The three that remain are the routing policy's actual scope:
        `impl.red.import_errors` (#2766), `impl.red_phase_failed` (#2796),
        and the green half of `impl.deterministic_failure`, which has never
        fired in 180 runs and has no path to it today.

        The literal is deliberate, and is a second pin on the same claim. The
        baseline file is regenerated by a tool; this number is not, so a PR
        that moves the count has to say so here, in prose, in the diff."""
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
        remaining = [
            gate for gate in GATE_REGISTRY
            if gate.action == ACTION_HALT and gate.judges == JUDGES_MODEL_OUTPUT
        ]
        assert len(remaining) == baseline["model_output_halt_rows"] == 3

    def test_no_stagnation_row_is_among_them(self):
        remaining = {
            gate.key for gate in GATE_REGISTRY
            if gate.action == ACTION_HALT and gate.judges == JUDGES_MODEL_OUTPUT
        }
        assert remaining.isdisjoint(STAGNATION_KEYS)
