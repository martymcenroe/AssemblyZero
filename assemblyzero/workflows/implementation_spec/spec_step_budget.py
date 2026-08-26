"""The implementation-spec graph's step budget, derived from its caps (#2382).

Same reasoning as `requirements/step_budget.py` (#2245), applied to the graph
#2382 lets run longer. LangGraph bounds a run by super-steps and raises
`GraphRecursionError` when the bound is spent -- an error naming no stage, no
loop and no document.

That matters here specifically. #2382 lets a *converging* review loop continue
past the base cap of three, and the spec stage invoked its graph with no
`config` at all, so it took LangGraph's default of 25. Raising the round ceiling
without raising the budget would have traded a halt that names the cap for a
recursion error that names nothing -- strictly worse than the behaviour being
fixed.

Costs, derived from the graph's own edges
-----------------------------------------

`create_implementation_spec_graph` wires the review loop as
``N5 -> N2 -> N3 -> N5``, plus ``N4`` when the human gate is enabled. A test
walks the compiled graph and re-derives these, so rewiring the loop fails a test
rather than silently eating headroom.

==========================================================  =====
a clean pass (N0, N1, N2, N3, N4, N5, N6)                       7
each review round (N2 -> N3 -> [N4] -> N5)                     +4
==========================================================  =====

The headroom term covers the paths not modelled above: `route_after_validation`
can send a failed validation back to N2 without a review round, `HALT` costs a
step, and `route_after_human_gate` can revise. Every loop that exists is counted
or named; the margin is not a guess that there might be more.
"""

from __future__ import annotations

from typing import Any

#: N0 load_lld, N1 analyze_codebase, N1b compile_manifest, N1c manifest_gate
#: (#2533), N2 generate_spec, N3 validate_completeness, N4 human_gate,
#: N5 review_spec, N6 finalize_spec.
CLEAN_RUN_STEPS = 9

#: One review round: the reviewer sends the draft back to N2, which costs
#: N2 -> N3 -> [N4] -> N5.
REVIEW_ROUND_STEPS = 4

#: Validation loop-backs, HALT, and the gated revise path.
HEADROOM_STEPS = 12


def recursion_limit(max_iterations: int = 3) -> int:
    """Super-steps to allow a review loop that runs to its hard ceiling.

    Sized against the CEILING rather than the base cap, because the ceiling is
    what the loop may now actually reach. Sized so the loop hits its own named
    halt -- the one that says which exit fired -- instead of a bound nothing
    states.
    """
    from assemblyzero.workflows.implementation_spec.review_progress import (
        hard_ceiling,
    )

    return (
        CLEAN_RUN_STEPS
        + hard_ceiling(max_iterations) * REVIEW_ROUND_STEPS
        + HEADROOM_STEPS
    )


def invoke_with_budget(
    app: Any, state: dict[str, Any], *, max_iterations: int = 3
) -> dict[str, Any]:
    """Run the compiled spec graph under an explicit, derived step budget."""
    return app.invoke(
        state, config={"recursion_limit": recursion_limit(max_iterations)}
    )
