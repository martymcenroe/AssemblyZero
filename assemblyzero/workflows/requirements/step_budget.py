"""The requirements graph's step budget, in one place (#2245).

LangGraph bounds a run by super-steps. Exhausting that bound raises
``GraphRecursionError``, which names no stage, no loop and no document -- the
opposite of the halts this graph is otherwise careful to produce.

Before this module the two callers disagreed and neither sized the bound against
what the loops cost. ``run_lld_stage`` passed no ``config`` at all, so every
orchestrated roll -- the path that matters most -- silently took LangGraph's
default of 25. ``tools/run_requirements_workflow.py`` computed
``(max_iterations * 4) + 10``, which is 22 at the default cap: *smaller* than the
default it was presumably raising.

Measured costs
--------------

Driving the real compiled graph with every model call stubbed and counting
super-steps (``app.stream``, one count per step). ``TestStepBudget`` in
``tests/unit/test_step_budget.py`` re-measures all of these, so a node added to
any loop fails a test instead of silently eating headroom:

===========================================  =====
a clean pass, no loops                           9
each reviewer revise round (N3 -> N1 -> N3)     +5
each finalize repair round trip                 +6
===========================================  =====

They are additive: two revise rounds and two repairs measured 31, and
``9 + 2*5 + 2*6`` is 31.

Why a headroom term
-------------------

The three numbers above cover the ungated LLD path. The human gates add a step
each when enabled, ``HALT`` adds one, and the issue-drafting path differs. Rather
than model every combination -- which would rot the first time the graph is
rewired -- the derivation carries a stated margin. It is not a fudge factor for
"maybe there are more loops": every loop that exists is counted above.
"""

from __future__ import annotations

from typing import Any

#: A clean LLD pass: load, codebase, requirements, draft, ponder, mechanical,
#: test-plan, review, finalize.
CLEAN_RUN_STEPS = 9

#: One reviewer REVISE round: N3 sends the draft back to N1, which costs
#: N1 -> Ponder -> N1.5 -> N1b -> N3.
REVISE_ROUND_STEPS = 5

#: One finalize repair round trip: N1, Ponder, N1.5, N1b, N3, N5.
FINALIZE_REPAIR_STEPS = 6

#: The human gates when enabled, HALT, and the issue-drafting path's shape.
HEADROOM_STEPS = 10

#: What the graph itself falls back to (`state.get("max_iterations", 3)` in
#: every router). Kept here so a caller that does not set the cap still sizes
#: the budget against the cap the graph will actually enforce.
DEFAULT_MAX_ITERATIONS = 3


def recursion_limit(
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    max_finalize_repairs: int | None = None,
) -> int:
    """Super-steps to allow a run whose loops all run to their caps.

    Sized so that every loop reaches ITS OWN halt -- the one that names the
    document and the unfixed errors -- rather than being cut off by a bound
    nothing states.
    """
    if max_finalize_repairs is None:
        from assemblyzero.workflows.requirements.nodes.finalize import (
            MAX_FINALIZE_REPAIRS,
        )
        max_finalize_repairs = MAX_FINALIZE_REPAIRS

    try:
        iterations = max(0, int(max_iterations))
    except (TypeError, ValueError):
        iterations = DEFAULT_MAX_ITERATIONS

    return (
        CLEAN_RUN_STEPS
        + iterations * REVISE_ROUND_STEPS
        + max(0, int(max_finalize_repairs)) * FINALIZE_REPAIR_STEPS
        + HEADROOM_STEPS
    )


def describe_budget_exhaustion(
    state: dict[str, Any], limit: int, steps: int, stage: str
) -> str:
    """Say which loop spent the budget, in the register the other halts use.

    The counters are already on the state -- ``verdict_count`` is incremented
    once per review, ``finalize_repair_count`` once per repair -- so the run can
    name what it was doing instead of reporting a bare recursion error.
    """
    revise_rounds = state.get("verdict_count", 0) or 0
    repairs = state.get("finalize_repair_count", 0) or 0
    drafts = state.get("draft_count", 0) or 0

    if repairs and revise_rounds > 1:
        culprit = "the reviewer revise loop and the finalize repair loop together"
    elif repairs:
        culprit = "the finalize repair loop"
    elif revise_rounds > 1:
        culprit = "the reviewer revise loop"
    else:
        culprit = "a loop that reported no round counter"

    return (
        f"BLOCKED: the {stage} stage ran out of graph steps after {steps} of "
        f"{limit}, spent by {culprit}.\n"
        f"  drafts generated: {drafts}\n"
        f"  reviewer verdicts: {revise_rounds} (each revise round costs "
        f"{REVISE_ROUND_STEPS} steps)\n"
        f"  finalize repairs: {repairs} (each costs {FINALIZE_REPAIR_STEPS} steps)\n"
        "\n"
        "  This is a loop that did not converge, not a crash. The document and "
        "every draft are in the run's lineage directory. If the loop legitimately "
        "needs more room, raise the cap that bounds it rather than the step "
        "budget -- the budget is derived from the caps in "
        "assemblyzero/workflows/requirements/step_budget.py."
    )


def invoke_with_budget(
    app: Any,
    state: dict[str, Any],
    *,
    stage: str = "lld",
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    max_finalize_repairs: int | None = None,
) -> dict[str, Any]:
    """Run the compiled graph under an explicit, derived step budget.

    Streams rather than invokes so that when the budget IS exhausted the last
    state is still in hand and the halt can name what consumed it. The final
    streamed value is the same object ``invoke`` would have returned; a test
    pins that equivalence, because the whole caller contract rests on it.
    """
    from langgraph.errors import GraphRecursionError

    limit = recursion_limit(max_iterations, max_finalize_repairs)

    last: dict[str, Any] = {}
    steps = 0
    try:
        for values in app.stream(
            state, config={"recursion_limit": limit}, stream_mode="values"
        ):
            last = values
            steps += 1
    except GraphRecursionError:
        halt = describe_budget_exhaustion(last, limit, steps, stage)
        print(halt)
        return {**last, "error_message": halt}

    return last
