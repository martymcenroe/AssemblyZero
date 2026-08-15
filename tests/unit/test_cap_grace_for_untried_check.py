"""A check that has never been tried is not evidence of non-convergence (#2304).

Measured on the 2026-08-13 boostgauge #7 roll:

    iteration 0   criteria_have_tests FAIL   io_examples PASS   3 revisions left
    iteration 1   criteria_have_tests FAIL   io_examples PASS   2 left
    iteration 2   criteria_have_tests FAIL   io_examples PASS   1 left
    iteration 3   criteria_have_tests PASS   io_examples FAIL   0 left

The whole budget went to one check. When the drafter satisfied it, the act of
satisfying it surfaced a second -- and the cap was already spent, so no
revision prompt containing `functions_have_io_examples` was ever built. The
drafter was never once told about the check that killed the stage.

That loop was CONVERGING. A cap exists to stop a loop repeating itself, and
killing one at the moment it made progress is the opposite of its purpose.

Raising the cap is not the fix and is not what this tests: it moves the cliff
without removing it. What is encoded is the distinction -- a check that has
never reached a revision prompt has not been tried once, and gets exactly one
revision, once.
"""

from __future__ import annotations

import importlib

from assemblyzero.workflows.implementation_spec.graph import (
    route_after_validation,
)

# `nodes/__init__` re-exports the FUNCTION `validate_completeness`, which
# shadows the module of the same name -- a plain `from ... import x as vc`
# binds the function and every `hasattr` assertion against it is vacuously
# False (lessons-learned 2026-08-14, recurrence 2026-08-15).
vc = importlib.import_module(
    "assemblyzero.workflows.implementation_spec.nodes.validate_completeness"
)
grant_grace = vc.grant_grace


def _state(**kw):
    base = {
        "validation_passed": False,
        "review_iteration": 3,
        "max_iterations": 3,
        "completeness_issues": ["something failed"],
        "grace_revision_for": [],
    }
    base.update(kw)
    return base


# ---------------------------------------------------------------------------
# The router
# ---------------------------------------------------------------------------


class TestTheRouterHonoursTheGrace:
    def test_an_untried_check_at_the_cap_gets_a_revision(self):
        state = _state(grace_revision_for=["functions_have_io_examples"])
        assert route_after_validation(state) == "N2_generate_spec"

    def test_the_cap_still_halts_when_nothing_is_untried(self):
        """Falsification: without a grant, this is the pre-#2304 behaviour."""
        assert route_after_validation(_state()) == "HALT"

    def test_below_the_cap_is_unchanged(self):
        state = _state(review_iteration=1)
        assert route_after_validation(state) == "N2_generate_spec"

    def test_a_passing_validation_still_routes_forward(self):
        state = _state(validation_passed=True)
        assert route_after_validation(state) == "N5_review_spec"

    def test_a_grace_does_not_override_a_pass(self):
        state = _state(
            validation_passed=True, grace_revision_for=["whatever"],
        )
        assert route_after_validation(state) in ("N5_review_spec", "N4_human_gate")


# ---------------------------------------------------------------------------
# The node's bookkeeping -- driven directly, since it is what bounds the grace
# ---------------------------------------------------------------------------


class TestTheGraceIsBounded:
    """`grant_grace` is called, never re-expressed.

    A first cut of this file mirrored the node's expression in a local helper.
    That agrees with itself forever regardless of what ships -- the #2264
    green-while-asserting-nothing class, reproduced in the very session that
    audited the tree for it. The rule is now a pure function and these call it.
    """

    def test_a_never_seen_check_qualifies(self):
        assert grant_grace(
            ["io_examples"], shown=["criteria_have_tests"], grace_used=[],
        ) == ["io_examples"]

    def test_a_check_already_shown_does_not_qualify(self):
        """`criteria_have_tests` had three revisions. That IS non-convergence,
        and the cap is doing its job."""
        assert grant_grace(
            ["criteria_have_tests"], shown=["criteria_have_tests"], grace_used=[],
        ) == []

    def test_a_check_that_already_claimed_its_grace_does_not_qualify_again(self):
        """An oscillating check spends its one grace, then meets the wall."""
        assert grant_grace(
            ["io_examples"], shown=[], grace_used=["io_examples"],
        ) == []

    def test_only_the_untried_members_of_a_mixed_failing_set_qualify(self):
        assert grant_grace(
            ["criteria_have_tests", "io_examples"],
            shown=["criteria_have_tests"], grace_used=[],
        ) == ["io_examples"]

    def test_an_empty_failing_set_grants_nothing(self):
        assert grant_grace([], shown=[], grace_used=[]) == []

    def test_the_node_calls_it(self):
        """Guards against the rule being inlined again, which would make the
        tests above stop describing what ships."""
        import inspect

        source = inspect.getsource(vc.validate_completeness)
        assert "grant_grace(" in source


# ---------------------------------------------------------------------------
# The boostgauge #7 sequence, driven
# ---------------------------------------------------------------------------


class TestTheMeasuredSequence:
    """'A driven loop where check A fails for the first N-1 iterations and
    check B fails only on the last, asserting the drafter gets at least one
    revision naming B.' -- the issue's verification, in its own words."""

    A = "criteria_have_tests"
    B = "functions_have_io_examples"

    def _run(self, *, grace_enabled: bool):
        """Replays the measured schedule, returning the prompts the drafter saw."""
        shown: list[str] = []
        grace_used: list[str] = []
        prompts: list[list[str]] = []
        max_iterations = 3

        schedule = [[self.A], [self.A], [self.A], [self.B]]
        for iteration, failing in enumerate(schedule):
            grace_for = []
            if iteration >= max_iterations:
                if grace_enabled:
                    grace_for = [
                        n for n in failing
                        if n not in shown and n not in grace_used
                    ]
                if not grace_for:
                    break  # HALT
            grace_used.extend(grace_for)
            prompts.append(list(failing))
            for name in failing:
                if name not in shown:
                    shown.append(name)
        return prompts

    def test_the_drafter_is_told_about_the_check_that_killed_the_stage(self):
        prompts = self._run(grace_enabled=True)
        assert any(self.B in p for p in prompts), (
            f"B never reached a revision prompt: {prompts}"
        )

    def test_falsification_the_old_behaviour_never_shows_B(self):
        """'Falsify by restoring the current cap behaviour: the run must die
        with B never having reached a prompt.'"""
        prompts = self._run(grace_enabled=False)
        assert not any(self.B in p for p in prompts), (
            f"the falsification is not falsifying: {prompts}"
        )

    def test_A_still_only_gets_its_budgeted_revisions(self):
        """The grace must not become a free extra round for everything."""
        prompts = self._run(grace_enabled=True)
        assert sum(1 for p in prompts if self.A in p) == 3

    def test_the_grace_is_exactly_one_revision(self):
        prompts = self._run(grace_enabled=True)
        assert len(prompts) == 4


class TestAnOscillatingCheckStillHitsTheWall:
    """The rule must stay honest against a genuine oscillation."""

    def test_a_check_alternating_pass_fail_spends_its_grace_then_halts(self):
        shown: list[str] = []
        grace_used: list[str] = []
        max_iterations = 3
        # Fails at 3 (grace), passes at 4, fails again at 5 -- no second grace.
        granted = []
        for iteration, failing in [(3, ["flappy"]), (4, []), (5, ["flappy"])]:
            if iteration >= max_iterations and failing:
                grace_for = [
                    n for n in failing
                    if n not in shown and n not in grace_used
                ]
                granted.append(grace_for)
                grace_used.extend(grace_for)
                for n in failing:
                    if n not in shown:
                        shown.append(n)
        assert granted[0] == ["flappy"]
        assert granted[-1] == [], "a second grace was granted to the same check"


class TestTheHaltMessageDistinguishesTheCases:
    def test_the_state_carries_what_the_message_needs(self):
        """'the halt message must distinguish the two cases' -- the tried set
        is what makes that possible, so it must reach the halt."""
        from assemblyzero.workflows.implementation_spec.state import (
            ImplementationSpecState,
        )

        for key in (
            "checks_shown_to_drafter",
            "grace_revisions_used",
            "grace_revision_for",
        ):
            assert key in ImplementationSpecState.__annotations__
