"""How many super-steps the implementation stage may spend (#2790).

The implementation-spec stage derives its own step budget and spends it; this
stage passed none, so its ceiling was whatever LangGraph defaults to.

**That default is 10007**, read from the installed package rather than from
memory::

    langgraph/_internal/_config.py:32
    DEFAULT_RECURSION_LIMIT = int(getenv("LANGGRAPH_DEFAULT_RECURSION_LIMIT", "10007"))

#2790 was filed saying 25, which was wrong and made the case sound like a
converging run might trip an invisible ceiling. It cannot: 10007 is far above
anything a converging run needs. The real cost is the other direction. A loop
that escapes every internal cap runs **ten thousand super-steps** before
LangGraph stops it, and in this stage a super-step can be a model call. The
run then dies on `GraphRecursionError`, which carries no gate key, matches no
registry row, and lands in the report as `unclassified`.

So the budget here is not a safety margin for normal work. It is the distance
between "a bug costs a few dozen steps and a named halt" and "a bug costs ten
thousand steps and an exception nobody can attribute".

Derived, never typed. Every term below is imported from the constant that
actually bounds that loop, so raising a cap raises the budget with it and the
two cannot drift. The spec stage's helper states the principle this follows:
sized so the loop hits its own named halt -- the one that says which exit
fired -- instead of a bound nothing states.
"""

from __future__ import annotations

#: Slack for the paths this arithmetic does not enumerate: the HALT node, the
#: END edge, a resumed run re-entering mid-graph, and any single-node detour
#: added later that nobody remembers to count here. Deliberately generous --
#: being wrong high costs a few super-steps of a runaway, being wrong low
#: turns a legitimate run into a `GraphRecursionError`, which is the failure
#: this module exists to prevent.
HEADROOM_STEPS = 20


def recursion_limit(max_iterations: int | None = None) -> int:
    """Super-steps enough for every loop in the stage to reach its own cap.

    Sized against the sum of the stage's caps rather than a guess, so the
    first thing to stop a runaway is always a gate with a key.
    """
    from assemblyzero.workflows.testing.atlas import TOTAL_STEPS
    from assemblyzero.workflows.testing.graph import (
        MAX_COVERAGE_AUGMENT_ATTEMPTS,
    )
    from assemblyzero.workflows.testing.nodes.completeness_gate import (
        MAX_COMPLETENESS_ITERATIONS,
    )
    from assemblyzero.workflows.testing.nodes.revise_test_plan import (
        MAX_REVISION_CYCLES,
    )
    from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
        MAX_SCAFFOLD_ATTEMPTS,
    )
    from assemblyzero.workflows.testing.state import DEFAULT_MAX_ITERATIONS

    iterations = DEFAULT_MAX_ITERATIONS if max_iterations is None else max_iterations

    # The forward path, once: N0 through N9.
    total = TOTAL_STEPS

    # N1 -> N1.5 -> N1, once per test-plan revision.
    total += MAX_REVISION_CYCLES * 2

    # N3 -> N2 -> N2.5 -> N3, once per re-scaffold. #2767 made this loop
    # bounded by MAX_SCAFFOLD_ATTEMPTS; before that it was bounded by nothing.
    total += (MAX_SCAFFOLD_ATTEMPTS + 1) * 3

    # N4b -> N4 -> N4b, once per completeness re-implementation.
    total += MAX_COMPLETENESS_ITERATIONS * 2

    # N5 -> N4 -> N4b -> N5, once per green iteration.
    total += iterations * 3

    # N5 -> N4c -> N5, once per coverage-augment attempt.
    total += MAX_COVERAGE_AUGMENT_ATTEMPTS * 2

    # N6 -> N4 -> N4b -> N5 -> N6, once per e2e iteration. Bounded by the same
    # iteration cap the green loop reads.
    total += iterations * 4

    return total + HEADROOM_STEPS
