"""A converging review loop is not a stagnating one (#2382).

run-issue1-152716 died at the spec review cap after three REVISE verdicts that
were the OPPOSITE of stagnation: each round resolved the previous round's list
and surfaced a distinct, deeper one. The fixed cap of three ended it with
exactly the verdict three rounds of identical failure would have earned.

The three verdicts are fixtures here, captured verbatim from that run's lineage.
They are the whole point: a convergence detector tuned on synthetic text proves
nothing about the documents this loop actually sees.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from assemblyzero.workflows.implementation_spec import review_progress as rp  # noqa: E402
from assemblyzero.workflows.implementation_spec import spec_step_budget as budget  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "spec_review"


def verdict(n: str) -> str:
    return (FIXTURES / f"run-issue1-152716-{n}-readiness-verdict.md").read_text(
        encoding="utf-8"
    )


@pytest.fixture(scope="module")
def rounds() -> list[str]:
    return [verdict("006"), verdict("009"), verdict("012")]


class TestTheRealRunClassifiesAsConverging:
    """#2382's acceptance: these three verdicts must read as converging."""

    def test_all_three_were_captured(self, rounds):
        assert len(rounds) == 3
        for text in rounds:
            assert text.startswith("Verdict: REVISE"), (
                "all three were REVISE -- that is what made the cap fire"
            )

    def test_round_two_is_distinct_from_round_one(self, rounds):
        assert rp.classify(rounds[1], rounds[:1]) == rp.CONVERGING

    def test_round_three_is_distinct_from_both_earlier_rounds(self, rounds):
        assert rp.classify(rounds[2], rounds[:2]) == rp.CONVERGING

    def test_the_third_round_earns_a_fourth(self, rounds):
        """The exact decision the run needed and did not get. At round 3 with a
        base cap of 3, today's rule halts; converging, it continues."""
        decision = rp.decide(
            review_iteration=3,
            max_iterations=3,
            current_feedback=rounds[2],
            prior_feedbacks=rounds[:2],
        )
        assert decision.should_continue is True
        assert decision.exit_name == rp.CONTINUE
        assert "past the base cap" in decision.detail

    def test_the_run_would_not_have_been_cut_at_any_of_its_three_rounds(
        self, rounds
    ):
        for index in range(3):
            decision = rp.decide(
                review_iteration=index + 1,
                max_iterations=3,
                current_feedback=rounds[index],
                prior_feedbacks=rounds[:index],
            )
            assert decision.should_continue, (
                f"round {index + 1} was cut: {decision.exit_name}"
            )


class TestStagnationStillHaltsAtTheBaseCap:
    """The opposite process must keep dying exactly as it does today."""

    def test_a_repeated_verdict_is_stagnation(self, rounds):
        assert rp.classify(rounds[0], [rounds[0]]) == rp.STAGNATING

    def test_stagnation_halts_even_inside_the_base_cap(self, rounds):
        decision = rp.decide(
            review_iteration=1,
            max_iterations=3,
            current_feedback=rounds[0],
            prior_feedbacks=[rounds[0]],
        )
        assert decision.should_continue is False
        assert decision.exit_name == rp.EXIT_STAGNATION

    def test_an_objection_that_skips_a_round_is_still_stagnation(self, rounds):
        """A loop alternating between two objections repeats without ever
        repeating consecutively, which is what comparing only against the
        previous round misses."""
        decision = rp.decide(
            review_iteration=3,
            max_iterations=3,
            current_feedback=rounds[0],
            prior_feedbacks=[rounds[0], rounds[1]],
        )
        assert decision.exit_name == rp.EXIT_STAGNATION

    def test_empty_feedback_halts_rather_than_looping_on_nothing(self):
        decision = rp.decide(
            review_iteration=1,
            max_iterations=3,
            current_feedback="   ",
            prior_feedbacks=[],
        )
        assert decision.should_continue is False
        assert decision.exit_name == rp.EXIT_EMPTY


class TestTheHardCeiling:
    def test_it_is_a_multiple_of_the_base_cap(self):
        assert rp.hard_ceiling(3) == 3 * rp.CEILING_MULTIPLIER
        assert rp.hard_ceiling(1) == rp.CEILING_MULTIPLIER

    def test_it_is_well_above_the_base(self):
        assert rp.hard_ceiling(3) > 3

    def test_a_converging_loop_stops_at_the_ceiling(self, rounds):
        decision = rp.decide(
            review_iteration=rp.hard_ceiling(3),
            max_iterations=3,
            current_feedback=rounds[2],
            prior_feedbacks=rounds[:2],
        )
        assert decision.should_continue is False
        assert decision.exit_name == rp.EXIT_CEILING

    def test_the_ceiling_halt_says_the_loop_was_still_converging(self, rounds):
        """Otherwise it reads as 'the spec was bad' when it means 'we ran out
        of budget on a spec that was getting better'."""
        decision = rp.decide(
            review_iteration=rp.hard_ceiling(3),
            max_iterations=3,
            current_feedback=rounds[2],
            prior_feedbacks=rounds[:2],
        )
        assert "still converging" in decision.detail
        assert "#2383" in decision.detail, "point at the resume that keeps the work"

    def test_a_garbage_cap_does_not_crash_the_ceiling(self):
        assert rp.hard_ceiling("nonsense") == 3 * rp.CEILING_MULTIPLIER
        assert rp.hard_ceiling(-4) == 0


class TestTheHaltNamesWhichExitFired:
    """#2382's fourth acceptance box."""

    @pytest.mark.parametrize(
        "exit_name",
        [rp.EXIT_STAGNATION, rp.EXIT_CEILING, rp.EXIT_EMPTY, rp.EXIT_BASE_CAP],
    )
    def test_every_exit_has_a_distinct_name(self, exit_name):
        assert exit_name and exit_name != rp.CONTINUE

    def test_the_exit_names_are_all_different(self):
        names = {
            rp.CONTINUE,
            rp.EXIT_STAGNATION,
            rp.EXIT_CEILING,
            rp.EXIT_EMPTY,
            rp.EXIT_BASE_CAP,
        }
        assert len(names) == 5

    def test_the_description_carries_the_name_and_the_reason(self, rounds):
        decision = rp.decide(
            review_iteration=1,
            max_iterations=3,
            current_feedback=rounds[0],
            prior_feedbacks=[rounds[0]],
        )
        text = rp.describe_exit(decision, 3)
        assert rp.EXIT_STAGNATION in text
        assert decision.detail in text


class TestTheStepBudgetReachesTheCeiling:
    """Raising the round ceiling without raising the budget would trade a halt
    that names the cap for a GraphRecursionError that names nothing -- strictly
    worse than the behaviour being fixed."""

    def test_the_default_langgraph_limit_could_not_reach_the_ceiling(self):
        """The measurement that makes the budget necessary rather than tidy."""
        rounds_at_ceiling = rp.hard_ceiling(3)
        needed = (
            budget.CLEAN_RUN_STEPS + rounds_at_ceiling * budget.REVIEW_ROUND_STEPS
        )
        assert needed > 25, (
            f"a ceiling of {rounds_at_ceiling} rounds needs {needed} super-steps "
            "before headroom; LangGraph's default is 25"
        )

    def test_the_derived_limit_covers_the_ceiling_with_headroom(self):
        limit = budget.recursion_limit(3)
        needed = (
            budget.CLEAN_RUN_STEPS
            + rp.hard_ceiling(3) * budget.REVIEW_ROUND_STEPS
        )
        assert limit >= needed + budget.HEADROOM_STEPS

    def test_it_scales_with_the_cap(self):
        assert budget.recursion_limit(5) > budget.recursion_limit(3)

    def test_the_round_cost_matches_the_graph_the_loop_actually_walks(self):
        """N5 -> N2 -> N3 -> [N4] -> N5. Derived from the graph's own edges, so
        rewiring the loop fails here instead of silently eating headroom."""
        from assemblyzero.workflows.implementation_spec import graph as g

        loop_nodes = {
            g.N2_GENERATE_SPEC,
            g.N3_VALIDATE_COMPLETENESS,
            g.N4_HUMAN_GATE,
            g.N5_REVIEW_SPEC,
        }
        assert budget.REVIEW_ROUND_STEPS == len(loop_nodes)

    def test_the_clean_run_cost_matches_the_node_count(self):
        from assemblyzero.workflows.implementation_spec import graph as g

        clean_path = {
            g.N0_LOAD_LLD,
            g.N1_ANALYZE_CODEBASE,
            g.N1B_COMPILE_MANIFEST,  # #2533: manifest compiles before the drafter
            g.N1C_MANIFEST_GATE,     # #2533: and gates before any spend
            g.N2_GENERATE_SPEC,
            g.N3_VALIDATE_COMPLETENESS,
            g.N4_HUMAN_GATE,
            g.N5_REVIEW_SPEC,
            g.N6_FINALIZE_SPEC,
        }
        assert budget.CLEAN_RUN_STEPS == len(clean_path)


class TestTheDecisionIsMadeInOnePlace:
    """N5 decides and the router reads. A router's state writes are discarded
    at the graph boundary (#2018), which is why #2197 had to move the cap
    MESSAGE into the node -- leaving the decision behind is how the node came
    to write one rule's message while the router applied another."""

    def test_the_router_reads_the_nodes_verdict_rather_than_recomputing(self):
        source = (
            ROOT / "assemblyzero" / "workflows" / "implementation_spec" / "graph.py"
        ).read_text(encoding="utf-8")
        router = source.split("def route_after_review", 1)[1].split("\ndef ", 1)[0]
        assert 'state.get("review_exit"' in router
        assert "same_blocking_issues" not in router, (
            "the router must not re-decide; N5 already did, against all history"
        )

    def test_the_node_records_the_exit_and_the_history(self):
        source = (
            ROOT
            / "assemblyzero"
            / "workflows"
            / "implementation_spec"
            / "nodes"
            / "review_spec.py"
        ).read_text(encoding="utf-8")
        assert '"review_exit": review_exit' in source
        assert '"review_feedback_history": prior_feedbacks + [feedback]' in source

    def test_a_state_without_an_exit_falls_back_to_the_base_cap(self):
        """A missing key must not read as permission to loop. Any future state
        that forgets to set it would otherwise loop until the step budget ran
        out and report a recursion error naming nothing."""
        from assemblyzero.workflows.implementation_spec.graph import (
            route_after_review,
        )

        at_cap = {
            "error_message": "",
            "review_verdict": "REVISE",
            "review_iteration": 3,
            "max_iterations": 3,
        }
        assert route_after_review(at_cap) == "HALT"

        under_cap = {**at_cap, "review_iteration": 1}
        assert route_after_review(under_cap) == "N2_generate_spec"

    def test_an_explicit_exit_overrides_the_fallback(self):
        """A converging round past the base cap continues -- which the fallback
        alone would have halted. This is the whole behaviour change."""
        from assemblyzero.workflows.implementation_spec.graph import (
            route_after_review,
        )

        past_cap_converging = {
            "error_message": "",
            "review_verdict": "REVISE",
            "review_iteration": 3,
            "max_iterations": 3,
            "review_exit": rp.CONTINUE,
        }
        assert route_after_review(past_cap_converging) == "N2_generate_spec"

        stagnating = {**past_cap_converging, "review_exit": rp.EXIT_STAGNATION}
        assert route_after_review(stagnating) == "HALT"

    def test_the_node_guard_bounds_on_the_ceiling_not_the_base_cap(self):
        """Otherwise the guard BLOCKS the very rounds the convergence exit
        grants, by synthesizing a verdict no reviewer issued -- the defect
        #1775 removed from this same guard."""
        source = (
            ROOT
            / "assemblyzero"
            / "workflows"
            / "implementation_spec"
            / "nodes"
            / "review_spec.py"
        ).read_text(encoding="utf-8")
        assert "if review_iteration > ceiling:" in source
        assert "if review_iteration > max_iterations:" not in source
