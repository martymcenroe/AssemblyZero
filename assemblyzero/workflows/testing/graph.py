"""StateGraph definition for TDD Testing Workflow.

Issue #101: Test Plan Reviewer
Issue #102: TDD Initialization
Issue #93: N8 Documentation Node
Issue #335: Add mechanical test validation node (N2.5)
Issue #147: Add completeness gate node (N4b) between N4 and N5
Issue #292: Exit code routing — N3/N5 can route to N2 on syntax/collection errors
Issue #180: Add cleanup node (N9) after N8
Issue #352: Add adversarial testing node (N7.5) between N7 and N8

Defines the compiled graph with:
- N0-N9 nodes (plus N2.5 for test validation, N4b for completeness gate,
  N7.5 for adversarial testing)
- Conditional edges for routing
- Checkpoint support via SqliteSaver

Graph structure:
    N0_load_lld -> N1_review_test_plan -> N2_scaffold_tests -> N2_5_validate_tests
           |              |                     |                      |
           v              v                     v                      v
         error         BLOCKED              scaffold_only         validation
           |              |                     |                   result
           v              v                     v                      |
          HALT     N1.5 revise, HALT           END                    / \\
                   when revisions are                                /   \\
                   spent (#3585)                                pass   fail
                                                                 |       |
                                                                 v       v
    N2_5 (pass) -> N3_verify_red -> N4_implement_code ------> N2 (retry)
           |                |                   |               or escalate
           v                v                   v               to N4
        red OK          iteration          N4b_completeness
           |            loop back              |
           v                |                 / \\
          N4               N4              PASS  BLOCK
                                            |      |
                                            v      v
                                           N5   N4 (iter<3)
                                                 or HALT (iter>=3, stagnant,
                                                 or the gate could not check)

    N5_verify_green -> N6_e2e_validation -> N7_finalize -> N7_5_adversarial
           |                  |                  |               |
           v                  v                  v               v
       iteration          skip_e2e           complete    route_after_adversarial
       loop back              |                                  |
           |                  v                                  v
          N4                 N7                            N8_document
                                                               |
                                                               v
                                                      route_after_doc
                                                               |
                                                              / \\
                                                         N9     END
                                                          |
                                                          v
                                                         END

#3585 (ADR 0236): every stop a router decides goes to HALT, which alerts. The
routers used to end the run at END for an iteration cap, a spent budget, a
BLOCKED test plan or a route nobody named; END writes no halt bundle and tells
no one, and the stage read the empty error_message as a pass. A router's own
state writes are discarded at the graph boundary (#2018), so the node in front
of it records the reason (`_records_its_stop`), and HALT's alert carries it.
"""

import sys
from typing import Any, Callable, Literal

from langgraph.graph import END, StateGraph

from assemblyzero.workflows.testing.checkpoints import commit_checkpoint
from assemblyzero.workflows.testing.nodes import (
    cleanup,
    document,
    e2e_validation,
    finalize,
    implement_code_under_profile,
    mechanical_hooks,
    load_lld,
    route_after_document,
    review_test_plan,
    scaffold_tests,
    verify_green_phase,
    verify_red_phase,
)


from assemblyzero.workflows.testing.nodes.augment_tests import (
    augment_tests_for_coverage,
)
from assemblyzero.workflows.testing.nodes.completeness_gate import (
    completeness_gate,
    route_after_completeness_gate,
)
from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
    validate_tests_mechanical_node,
    should_regenerate,
)
from assemblyzero.workflows.testing.state import (
    DEFAULT_MAX_ITERATIONS,
    TestingWorkflowState,
)

from assemblyzero.workflows.testing.nodes.revise_test_plan import revise_test_plan  # Issue #1072

from assemblyzero.workflows.testing.nodes.adversarial_node import (
    run_adversarial_node,
)
from assemblyzero.core.halt_node import create_halt_node
from assemblyzero.core.llm_provider import get_cumulative_cost


class CheckpointFailed(RuntimeError):
    """A git checkpoint after a node failed, and the run stops (#3585)."""


def _wrap_with_checkpoint(node_fn: Callable[..., dict[str, Any]],
                            ckpt_name: str) -> Callable[..., dict[str, Any]]:
    """Wrap a TDD node so it triggers a git checkpoint after it returns.

    Pulls worktree_path and issue_number out of the workflow state.

    Issue #689 -- 2026-01-31 lost 6,114 lines because TDD nodes didn't
    commit between phases.

    #3585 (ledger 0908, graph.py:128): a checkpoint that raises stops the
    run. This wrapper used to print the error and carry on, so a run went on
    with its work uncommitted and nobody was told. It now says the failure at
    ERROR on stderr, naming the checkpoint, the node, the worktree and the
    issue, and raises CheckpointFailed from it. The run's caller alerts once:
    the entry point's main handler, or the orchestrator's impl stage, whose
    failed result routes to its HALT.
    """
    def wrapped(state: dict[str, Any]) -> dict[str, Any]:
        result = node_fn(state)
        worktree = state.get("worktree_path") or state.get("repo_path")
        issue_obj = state.get("issue") or {}
        issue_n = (
            state.get("issue_number")
            or (issue_obj.get("number") if isinstance(issue_obj, dict) else None)
        )
        try:
            commit_checkpoint(worktree, issue_n, ckpt_name)
        except Exception as e:
            message = (
                f"the [CP:{ckpt_name}] git checkpoint after "
                f"{getattr(node_fn, '__name__', 'the node')} failed in {worktree} "
                f"(issue {issue_n}): {type(e).__name__}: {e}; the run stops, and "
                f"the node's work is in the worktree uncommitted"
            )
            print(f"ERROR [CP:{ckpt_name}] {message}", file=sys.stderr)
            raise CheckpointFailed(message) from e
        return result

    # #2813: the same carry `narrated` performs, for the same reason. This
    # wrapper stands between a node function and the graph for six nodes;
    # without it they report their module as `graph`, and nothing can ask
    # which file supplies a node -- the question that catches a module
    # imported but wired to nothing (#2787).
    wrapped.__name__ = getattr(node_fn, "__name__", "wrapped")
    wrapped.__module__ = getattr(node_fn, "__module__", wrapped.__module__)
    wrapped.__wrapped__ = node_fn
    return wrapped


def _records_its_stop(
    node_fn: Callable[..., dict[str, Any]],
    stop: Callable[[dict[str, Any]], dict[str, str]],
    label: str,
) -> Callable[..., dict[str, Any]]:
    """Wrap a node so a stop its router will take is recorded as its reason.

    #3585: the router after this node halts on a condition the node did not
    record (an iteration cap, a budget, a BLOCKED plan, a route it did not
    name). A router cannot write state, so without this HALT's alert would
    carry a reason synthesized from nothing. `stop` is the same function the
    router consults, so the two cannot disagree about when the run stops. A
    reason the node recorded itself is left as it is.
    """
    def records_stop(state: dict[str, Any]) -> dict[str, Any]:
        result = node_fn(state)
        if (result or {}).get("error_message"):
            return result
        halt = stop({**state, **(result or {})})
        if not halt:
            return result
        print(f"ERROR [{label}] {halt['error_message']}", file=sys.stderr)
        return {**(result or {}), **halt}

    # Same identity carry as _wrap_with_checkpoint (#2813).
    records_stop.__name__ = getattr(node_fn, "__name__", "records_stop")
    records_stop.__module__ = getattr(node_fn, "__module__", records_stop.__module__)
    records_stop.__wrapped__ = node_fn
    return records_stop


def _halt_unrecorded(label: str, halt: dict[str, str]) -> Literal["HALT"]:
    """Say a stop the node did not record, at ERROR on stderr, and halt.

    In the built graph the node's `_records_its_stop` has already recorded it
    and the router halts on error_message first; this is the router alone.
    """
    print(f"ERROR [{label}] {halt['error_message']}", file=sys.stderr)
    return "HALT"


def _issue(state: dict[str, Any]) -> Any:
    return state.get("issue_number") or "?"


def _stop_after_review(state: dict[str, Any]) -> dict[str, str]:
    """The halt a BLOCKED test plan takes, or {} while it can be revised.

    #3585 (ledger 0908, graph.py:227, :232, :245): a BLOCKED verdict is a gate
    that failed. Under auto_mode (which `--review none`, the default, sets) or
    test_plan_policy=auto it used to be walked past to N2; under strict, and
    when the revisions were spent, it ended at END with a print. It is now
    revised while revisions remain, whatever the policy says about auto, and
    halts when none remain. Strict allows none.
    """
    from assemblyzero.workflows.testing.nodes.revise_test_plan import (
        MAX_REVISION_CYCLES,
    )

    if state.get("test_plan_status") != "BLOCKED":
        return {}
    verdict = state.get("test_plan_verdict") or "BLOCKED"
    if state.get("test_plan_policy", "revise") == "strict":
        return {"error_message": (
            f"Test plan revision budget spent: test_plan_policy=strict allows "
            f"no revision, and N1 returned BLOCKED for issue {_issue(state)}: "
            f"{verdict}"
        )}
    if state.get("test_plan_revision_count", 0) >= MAX_REVISION_CYCLES:
        return {"error_message": (
            f"Test plan revision budget spent: the plan for issue "
            f"{_issue(state)} is still BLOCKED after {MAX_REVISION_CYCLES} "
            f"revision cycle(s): {verdict}"
        )}
    return {}


def _stop_after_validate(state: dict[str, Any]) -> dict[str, str]:
    """The halt N2.5's carried route takes, or {} when it continues or retries.

    #3585 (ledger 0908, graph.py:318): an exhausted scaffold names its own halt
    (#2331). A carried "escalate" with no reason, or a route the graph does not
    know, used to end at END. No carried route (a state from before #2676) is
    left to the router's `should_regenerate`.
    """
    route = state.get("scaffold_route", "")
    if route in ("", "continue", "regenerate"):
        return {}
    if route == "escalate":
        return {"error_message": (
            f"N2.5: the generated test suite cannot be used for issue "
            f"{_issue(state)}, and regeneration is exhausted; the node carried "
            f"route 'escalate' without naming the halt"
        )}
    return {"error_message": (
        f"Unrecognised route after N2.5: validate_tests_mechanical carried "
        f"scaffold_route {route!r} for issue {_issue(state)}, and the graph has "
        f"no such edge"
    )}


#: The routes N3 names, each an edge of the graph.
_RED_ROUTES = ("N4_implement_code", "N5_verify_green", "N2_scaffold_tests")


def _stop_after_red(state: dict[str, Any]) -> dict[str, str]:
    """The halt for a route N3 did not name, or {}.

    #3585 (ledger 0908, graph.py:355): every stop N3 makes records a reason,
    so a next_node outside its routes is a broken contract. It ended at END
    silently, and the stage read the empty error_message as a pass.
    """
    next_node = state.get("next_node", "")
    if next_node in _RED_ROUTES:
        return {}
    return {"error_message": (
        f"Unrecognised route after N3: verify_red_phase named next_node "
        f"{next_node!r} for issue {_issue(state)} and recorded no reason; the "
        f"graph has no such edge"
    )}


def _stop_after_green(state: dict[str, Any]) -> dict[str, str]:
    """The halt N5's route takes, or {} when the route stands.

    #3585 (ledger 0908, graph.py:438, :447, :451, :471, :478, :488): the
    iteration cap, the spent coverage attempts, the cost budget and a route
    N5 did not name each ended the run at END. #2344 made the first say so on
    stdout; none reached HALT, so none alerted and the empty error_message read
    as a pass.
    """
    next_node = state.get("next_node", "")
    if next_node in ("N2_scaffold_tests", "N6_e2e_validation", "N7_finalize"):
        return {}
    iteration = state.get("iteration_count", 0)
    max_iterations = state.get("max_iterations", DEFAULT_MAX_ITERATIONS)
    budget = state.get("cost_budget_usd", 0.0)

    # #2327: a green-but-under-covered result routes to test additions, never
    # to implementation revision. Bounded by the same iteration and budget
    # limits as the implement loop, and additionally by its own attempt count
    # -- an LLM that cannot reach the target will not be asked forever.
    if next_node == "N4c_augment_tests":
        if iteration >= max_iterations:
            return {"error_message": (
                f"Green phase failed after {iteration} iteration(s): coverage "
                f"for issue {_issue(state)} is under its target and the "
                f"iteration cap of {max_iterations} is reached, so no further "
                f"tests can be added"
            )}
        if state.get("coverage_augment_attempts", 0) >= MAX_COVERAGE_AUGMENT_ATTEMPTS:
            return {"error_message": (
                f"Coverage test additions spent: {MAX_COVERAGE_AUGMENT_ATTEMPTS} "
                f"attempt(s) to add tests for issue {_issue(state)} did not "
                f"reach the coverage target. The run halts rather than route "
                f"to implementation: the uncovered lines are a test gap, and "
                f"revising the implementation to close it would reward "
                f"deleting the code that is not covered"
            )}
        if budget > 0 and (cumulative := get_cumulative_cost()) > budget:
            return {"error_message": (
                f"[BUDGET] cost ${cumulative:.2f} exceeds the ${budget:.2f} "
                f"cost budget for issue {_issue(state)} before N4c could add "
                f"tests"
            )}
        return {}

    if next_node == "N4_implement_code":
        if iteration >= max_iterations:
            # #2344: N5 asked for another revision and cannot have one. That
            # is a failure of the loop, not a quiet finish.
            return {"error_message": (
                f"Green phase failed after {iteration} iteration(s): N5 asked "
                f"for another implementation revision for issue "
                f"{_issue(state)} and the cap of {max_iterations} is reached. "
                f"The last result stands, and it is not a pass"
            )}
        # Issue #640: Budget check before looping back
        if budget > 0 and (cumulative := get_cumulative_cost()) > budget:
            return {"error_message": (
                f"[BUDGET] cost ${cumulative:.2f} exceeds the ${budget:.2f} "
                f"cost budget for issue {_issue(state)} before another "
                f"implementation revision"
            )}
        return {}

    return {"error_message": (
        f"Unrecognised route after N5: verify_green_phase named next_node "
        f"{next_node!r} for issue {_issue(state)} and recorded no reason; the "
        f"graph has no such edge"
    )}


def _stop_after_e2e(state: dict[str, Any]) -> dict[str, str]:
    """The halt at the e2e iteration cap, or {}.

    #3585 (ledger 0908, graph.py:513): an E2E failure that asks for another
    revision at the cap ended at END silently.
    """
    if state.get("next_node", "") != "N4_implement_code":
        return {}
    iteration = state.get("iteration_count", 0)
    max_iterations = state.get("max_iterations", DEFAULT_MAX_ITERATIONS)
    if iteration >= max_iterations:
        return {"error_message": (
            f"E2E failed after {iteration} iteration(s): N6 asked for another "
            f"implementation revision for issue {_issue(state)} and the cap of "
            f"{max_iterations} is reached"
        )}
    return {}


def route_after_load(
    state: TestingWorkflowState,
) -> Literal["N1_review_test_plan", "HALT"]:
    """Route after N0 (load_lld).

    Args:
        state: Current workflow state.

    Returns:
        Next node name, or HALT when the node recorded a reason (#2756).
    """
    error = state.get("error_message", "")
    if error:
        return "HALT"
    return "N1_review_test_plan"


def route_after_revision(
    state: TestingWorkflowState,
) -> Literal["N1_review_test_plan", "HALT"]:
    """Route after N1.5 (revise_test_plan). #2775.

    This edge was unconditional, and N1's BLOCKED return sets
    `error_message` to "" -- deliberately, per #1490, so that a blocked plan
    is revised rather than ending the run. Between the two, every reason
    N1.5 recorded was erased by the next node before `route_after_review`
    could read it. All three of N1.5's registered halt rows --
    `impl.test_plan_no_requirements`, `impl.revisor_failed` and
    `impl.test_plan_revision_incomplete` -- named a halt that could not
    happen: the run spent its remaining revision cycles asking a question
    that had already failed, then ended at `end` with no bundle.

    #2793's rule applies here as it does at every other node: a recorded
    reason routes to HALT. Nothing else about the loop changes -- a
    revision that records no reason still always goes back to N1.
    """
    if (state.get("error_message") or "").strip():
        return "HALT"
    return "N1_review_test_plan"


def route_after_review(
    state: TestingWorkflowState,
) -> Literal["N2_scaffold_tests", "N1_5_revise_test_plan", "HALT"]:
    """Route after N1 (review_test_plan).

    Issue #1072: BLOCKED no longer terminates by default; it is revised up to
    MAX_REVISION_CYCLES times.

    #3585 (ADR 0236; ledger 0908, graph.py:217, :227, :232, :245): a BLOCKED
    plan is never walked past and never ends the run quietly.

    - Any recorded reason halts. Under auto_mode, which `--review none` (the
      default) sets, an N1 error used to be ignored and the run went on to N2.
    - "revise" (default) and "auto": revise up to MAX_REVISION_CYCLES, then
      HALT. "auto" and the legacy auto_mode flag used to continue to N2 past
      the BLOCKED verdict; they now revise, as "revise" does.
    - "strict": HALT on BLOCKED. It used to end at END with no alert.

    The halts are recorded by N1's `_records_its_stop` from
    `_stop_after_review`, so HALT's alert carries the verdict.

    Args:
        state: Current workflow state.

    Returns:
        Next node name, or HALT.
    """
    from assemblyzero.workflows.testing.nodes.revise_test_plan import (
        MAX_REVISION_CYCLES,
    )

    if (state.get("error_message") or "").strip():
        return "HALT"

    if state.get("test_plan_status") == "BLOCKED":
        halt = _stop_after_review(state)
        if halt:
            return _halt_unrecorded("N1", halt)
        revision_count = state.get("test_plan_revision_count", 0)
        # Closes #1493: ASCII-only print (Windows cp1252).
        print(
            f"    [REVISE] BLOCKED -> N1.5 revise cycle "
            f"{revision_count + 1}/{MAX_REVISION_CYCLES}"
        )
        return "N1_5_revise_test_plan"

    return "N2_scaffold_tests"


def route_after_scaffold(
    state: TestingWorkflowState,
) -> Literal["N2_5_validate_tests", "end", "HALT"]:
    """Route after N2 (scaffold_tests).

    Issue #335: Updated to route to validation node instead of verify_red.

    Args:
        state: Current workflow state.

    Returns:
        Next node name, END for a scaffold-only run, or HALT when the node
        recorded a reason (#2756).
    """
    error = state.get("error_message", "")
    if error:
        return "HALT"

    # scaffold_only mode - stop after scaffolding. A finish, not a halt:
    # nothing failed and there is no reason to record (#2756).
    if state.get("scaffold_only"):
        return "end"

    return "N2_5_validate_tests"


def route_after_validate(
    state: TestingWorkflowState,
) -> Literal["N3_verify_red", "N2_scaffold_tests", "HALT"]:
    """Route after N2.5 (validate_tests_mechanical).

    Issue #335: Routes based on test validation results.

    Routes to:
    - N3_verify_red: Validation passed, continue normal flow
    - N2_scaffold_tests: Validation failed, attempts remain, retry
    - HALT: an error, or validation failed and regeneration is exhausted.
      #3585 (ledger 0908, graph.py:318): an exhaustion that recorded no
      reason, or a route the graph does not know, used to end at END; N2.5's
      `_records_its_stop` now records it from `_stop_after_validate`.

    #2331: this used to route an exhausted scaffold to N4_implement_code, and
    the comment there said "escalate to Claude". It escalated to nothing. A
    suite the validator had just judged unusable entered implementation
    HAVING SKIPPED verify_red, so it arrived with one fewer check than a suite
    that passed, and the implementation loop then spent its budget against
    tests no code could satisfy.

    The name promised a stronger test generator and the graph has none, so the
    honest route is to stop. The node writes a DETERMINISTIC FAILURE naming
    the tests as the wrong side, which is also what keeps the orchestrator
    from retrying a deterministic scaffolder.

    Args:
        state: Current workflow state.

    Returns:
        Next node name, or HALT.
    """
    error = state.get("error_message", "")
    if error:
        return "HALT"

    halt = _stop_after_validate(state)
    if halt:
        return _halt_unrecorded("N2.5", halt)

    # Use the should_regenerate function from validate_tests_mechanical
    decision = should_regenerate(state)

    if decision == "continue":
        return "N3_verify_red"
    elif decision == "regenerate":
        return "N2_scaffold_tests"

    # A state from before #2676 carries no route, and its recomputed decision
    # escalated without a recorded reason.
    return _halt_unrecorded("N2.5", {"error_message": (
        f"N2.5: the generated test suite cannot be used for issue "
        f"{_issue(state)}; should_regenerate decided {decision!r} and no "
        f"reason was recorded"
    )})


def route_after_red(
    state: TestingWorkflowState,
) -> Literal[
    "N4_implement_code", "N2_scaffold_tests", "N5_verify_green", "HALT",
]:
    """Route after N3 (verify_red_phase).

    Issue #292: Added N2_scaffold_tests route for exit codes 4/5.

    Args:
        state: Current workflow state.

    Returns:
        Next node name, or HALT when the node recorded a reason (#2756) or
        named a route the graph does not have (#3585, ledger 0908,
        graph.py:355; it used to end at END silently).
    """
    error = state.get("error_message", "")
    next_node = state.get("next_node", "")

    if error:
        return "HALT"

    halt = _stop_after_red(state)
    if halt:
        return _halt_unrecorded("N3", halt)

    if next_node == "N4_implement_code":
        return "N4_implement_code"

    # #2337: a retry whose implementation survived is not a failed red phase.
    # The tests and the implementation agree, which is the state N4 exists to
    # reach, so the coverage gate judges it rather than the stage ending.
    if next_node == "N5_verify_green":
        return "N5_verify_green"

    # Issue #292: Exit code 4/5 routes back to scaffold
    return "N2_scaffold_tests"


def route_after_implement(
    state: TestingWorkflowState,
) -> Literal["N4b_completeness_gate", "HALT"]:
    """Route after N4 (implement_code).

    Issue #147: Routes to N4b completeness gate instead of directly to N5.

    Args:
        state: Current workflow state.

    Returns:
        Next node name, or HALT when the node recorded a reason (#2756).
    """
    error = state.get("error_message", "")
    if error:
        return "HALT"
    return "N4b_completeness_gate"


def route_after_mechanical_hooks(
    state: TestingWorkflowState,
) -> Literal["N5_verify_green", "HALT"]:
    """Route after N4.5 (mechanical hooks).

    #3706: a hook that failed, or a `.unleashed.json` that could not be read,
    leaves `error_message` set, and the run halts there. Nothing is tested
    against a build that did not build.

    Args:
        state: Current workflow state.

    Returns:
        N5 when the hook succeeded or there was none; HALT on a recorded reason.
    """
    if state.get("error_message", ""):
        return "HALT"
    return "N5_verify_green"


#: #2327: how many times to ask for coverage-targeting test additions before
#: halting. Each attempt is an LLM call; if two rounds of tests aimed at named
#: uncovered lines have not reached the gate, a third is unlikely to, and the
#: honest outcome is a halt that says so rather than a route to implementation.
MAX_COVERAGE_AUGMENT_ATTEMPTS = 2


def route_after_augment(
    state: TestingWorkflowState,
) -> Literal["N5_verify_green", "HALT"]:
    """Route after N4c (augment_tests_for_coverage) (#4246).

    N4c returns to verification, and never to implementation (#2327). A
    recorded reason halts: coverage that could not be measured, or a gap in a
    framework N4c cannot write tests for. The edge used to go back to N5
    unconditionally, and N5's next result overwrote the reason.
    """
    if state.get("error_message", ""):
        return "HALT"
    return "N5_verify_green"


def route_after_green(
    state: TestingWorkflowState,
) -> Literal[
    "N6_e2e_validation", "N7_finalize", "N4_implement_code",
    "N4c_augment_tests", "N2_scaffold_tests", "HALT",
]:
    """Route after N5 (verify_green_phase).

    Issue #292: Added N2_scaffold_tests route for exit codes 4/5.

    #3585 (ADR 0236; ledger 0908, graph.py:438, :447, :451, :471, :478,
    :488): the iteration cap, the spent coverage attempts, the cost budget and
    a route N5 did not name halt. Each used to end at END, and the stage read
    the empty error_message as a pass. N5's `_records_its_stop` records the
    reason from `_stop_after_green`, so HALT's alert carries it.

    Args:
        state: Current workflow state.

    Returns:
        Next node name, or HALT.
    """
    error = state.get("error_message", "")
    next_node = state.get("next_node", "")

    if error:
        return "HALT"

    halt = _stop_after_green(state)
    if halt:
        return _halt_unrecorded("N5", halt)

    # Issue #292: Exit code 4/5 routes back to scaffold
    if next_node == "N2_scaffold_tests":
        return "N2_scaffold_tests"
    # #2327: test additions, never implementation revision, for coverage.
    if next_node == "N4c_augment_tests":
        return "N4c_augment_tests"
    if next_node == "N4_implement_code":
        return "N4_implement_code"
    if next_node == "N6_e2e_validation":
        return "N6_e2e_validation"
    # Skip E2E - go directly to finalize
    return "N7_finalize"


def route_after_e2e(
    state: TestingWorkflowState,
) -> Literal["N7_finalize", "N4_implement_code", "HALT"]:
    """Route after N6 (e2e_validation).

    #3585 (ledger 0908, graph.py:513): an E2E failure at the iteration cap
    halts; it ended at END silently. N6's `_records_its_stop` records it.

    Args:
        state: Current workflow state.

    Returns:
        Next node name, or HALT.
    """
    error = state.get("error_message", "")
    next_node = state.get("next_node", "")

    if error:
        return "HALT"

    halt = _stop_after_e2e(state)
    if halt:
        return _halt_unrecorded("N6", halt)

    # E2E failure may loop back to implement
    if next_node == "N4_implement_code":
        return "N4_implement_code"

    return "N7_finalize"


def route_after_finalize(
    state: TestingWorkflowState,
) -> Literal["N7_5_adversarial", "end", "HALT"]:
    """Route after N7 (finalize).

    Issue #352: Now routes to adversarial node instead of directly to N8.

    Args:
        state: Current workflow state.

    Returns:
        Next node name or END.
    """
    error = state.get("error_message", "")
    if error:
        return "HALT"

    # Skip documentation if flag is set. A finish, not a halt (#2756).
    if state.get("skip_docs"):
        return "end"

    return "N7_5_adversarial"


def route_after_adversarial(
    state: TestingWorkflowState,
) -> Literal["N8_document", "HALT"]:
    """Route after N7.5 (adversarial node).

    #3725: a review that could not run, or ran and produced no valid tests,
    sets error_message and halts; HALT alerts (#3724). It used to route to N8
    whatever happened, so the PR proceeded unreviewed (ADR 0236).

    Args:
        state: The current workflow state.

    Returns:
        "HALT" on error_message, otherwise "N8_document".
    """
    if state.get("error_message"):
        return "HALT"
    return "N8_document"


def build_testing_workflow() -> StateGraph:
    """Build the TDD testing workflow StateGraph.

    Issue #147: Added N4b completeness gate between N4 and N5.
    Issue #180: Added N9 cleanup node after N8.
    Issue #352: Added N7.5 adversarial testing node between N7 and N8.

    Returns:
        StateGraph ready for compilation.
    """
    # Create graph with state type
    workflow = StateGraph(TestingWorkflowState)

    # #2158/#2733: every node narrates its graph position on entry and writes
    # its entry to the convergence record, sourced from the atlas (#2157) so
    # neither can drift from the real graph. This stage was the last of the
    # three without one, which is why the report still had to grep node
    # markers out of a prose log to say how far into implementation a run got
    # -- in the stage where runs get furthest and most often die.
    from assemblyzero.workflows.narration import narrated
    from assemblyzero.workflows.testing.atlas import ATLAS, TOTAL_STEPS

    def _add(name, fn):
        workflow.add_node(name, narrated(name, fn, ATLAS, TOTAL_STEPS, stage="impl"))

    # Add nodes. #3585: a node whose router can halt on a condition the node
    # does not record is wrapped by `_records_its_stop`, so the reason reaches
    # HALT's alert.
    _add("N0_load_lld", load_lld)
    _add("N1_review_test_plan",
         _records_its_stop(review_test_plan, _stop_after_review, "N1"))
    _add("N1_5_revise_test_plan", revise_test_plan)  # Issue #1072
    # Issue #689: checkpoint after N2/N4/N5 so a crash between phases
    # doesn't lose generated tests / implementation code.
    _add("N2_scaffold_tests", _wrap_with_checkpoint(scaffold_tests, "post-scaffold"))
    _add("N2_5_validate_tests",  # Issue #335
         _records_its_stop(validate_tests_mechanical_node, _stop_after_validate, "N2.5"))
    _add("N3_verify_red", _records_its_stop(verify_red_phase, _stop_after_red, "N3"))
    # #3563: N4 runs under the run's model profile.
    _add("N4_implement_code", _wrap_with_checkpoint(implement_code_under_profile, "post-impl"))
    _add("N4b_completeness_gate", completeness_gate)  # Issue #147
    _add("N4_5_mechanical_hooks", mechanical_hooks)
    _add("N4c_augment_tests", augment_tests_for_coverage)  # #2327
    _add("N5_verify_green", _wrap_with_checkpoint(
        _records_its_stop(verify_green_phase, _stop_after_green, "N5"), "post-green"))
    _add("N6_e2e_validation", _records_its_stop(e2e_validation, _stop_after_e2e, "N6"))
    # Issue #1626: checkpoint after N7 so the test/implementation reports written
    # and archived by finalize() are committed to the impl worktree (and thus
    # land on target main when the impl PR squash-merges) instead of being left
    # untracked. Mirrors the N2/N4/N5 checkpoint pattern.
    _add("N7_finalize", _wrap_with_checkpoint(finalize, "post-finalize"))
    _add("N7_5_adversarial", run_adversarial_node)  # Issue #352
    # Issue #1631: checkpoint after N8 so the wiki/runbook/README the document
    # node generates are committed to the impl worktree (and land on target main
    # via the impl PR) instead of being left untracked. The 907/908 c/p docs are
    # suppressed for external repos upstream (#1627), so this stages only the
    # keeper docs there.
    _add("N8_document", _wrap_with_checkpoint(document, "post-document"))
    _add("N9_cleanup", cleanup)  # Issue #180
    _add("HALT", create_halt_node("testing"))  # Issue #486

    # Set entry point
    workflow.set_entry_point("N0_load_lld")

    # Add edges: N0 -> N1 (with error check)
    workflow.add_conditional_edges(
        "N0_load_lld",
        route_after_load,
        {
            "N1_review_test_plan": "N1_review_test_plan",
            # #2756: no "end" -- this router's only stop is an error, and it
            # now goes to HALT. Leaving the entry would declare an edge
            # nothing can take, which is the defect this issue is about.
            "HALT": "HALT",
        },
    )

    # N1 -> N2 / N1.5 / HALT (Issue #1072: revise on BLOCKED). #3585: no
    # "end"; a BLOCKED plan with no revision left halts.
    workflow.add_conditional_edges(
        "N1_review_test_plan",
        route_after_review,
        {
            "N2_scaffold_tests": "N2_scaffold_tests",
            "N1_5_revise_test_plan": "N1_5_revise_test_plan",
            "HALT": "HALT",  # #2756
        },
    )

    # N1.5 -> N1, or HALT when the revision recorded a reason (#2775)
    workflow.add_conditional_edges(
        "N1_5_revise_test_plan",
        route_after_revision,
        {
            "N1_review_test_plan": "N1_review_test_plan",
            "HALT": "HALT",
        },
    )

    # N2 -> N2.5 (with scaffold_only check) - Issue #335
    workflow.add_conditional_edges(
        "N2_scaffold_tests",
        route_after_scaffold,
        {
            "N2_5_validate_tests": "N2_5_validate_tests",
            "end": END,
            "HALT": "HALT",  # #2756
        },
    )

    # N2.5 -> N3 or N2 (retry) or N4 (escalate) - Issue #335. #3585: no
    # "end"; an exhausted scaffold halts.
    workflow.add_conditional_edges(
        "N2_5_validate_tests",
        route_after_validate,
        {
            "N3_verify_red": "N3_verify_red",
            "N2_scaffold_tests": "N2_scaffold_tests",
            "N4_implement_code": "N4_implement_code",
            "HALT": "HALT",  # #2756
        },
    )

    # N3 -> N4 or N2 (exit code routing) - Issue #292. #3585: no "end"; a
    # route N3 did not name halts.
    workflow.add_conditional_edges(
        "N3_verify_red",
        route_after_red,
        {
            "N4_implement_code": "N4_implement_code",
            "N5_verify_green": "N5_verify_green",  # #2337
            "N2_scaffold_tests": "N2_scaffold_tests",
            "HALT": "HALT",  # #2756
        },
    )

    # N4 -> N4b (with error check) - Issue #147
    workflow.add_conditional_edges(
        "N4_implement_code",
        route_after_implement,
        {
            "N4b_completeness_gate": "N4b_completeness_gate",
            # #2756: no "end" -- see route_after_load.
            "HALT": "HALT",
        },
    )

    # N4b -> N5, N4 (re-implement) or HALT - Issue #147. A BLOCK at the
    # iteration cap, or a stagnant one, halts with a reason (#3811).
    workflow.add_conditional_edges(
        "N4b_completeness_gate",
        route_after_completeness_gate,
        {
            "N4_5_mechanical_hooks": "N4_5_mechanical_hooks",
            "N4_implement_code": "N4_implement_code",
            "HALT": "HALT",  # #2756
        },
    )

    # N5 -> N6 or N7 (skip E2E) or N4 (iteration loop) or N2 (exit code routing) - Issue #292
    # #3585: no "end"; a cap, a budget or an unnamed route halts.
    workflow.add_conditional_edges(
        "N5_verify_green",
        route_after_green,
        {
            "N6_e2e_validation": "N6_e2e_validation",
            "N7_finalize": "N7_finalize",
            "N4_implement_code": "N4_implement_code",
            "N4c_augment_tests": "N4c_augment_tests",  # #2327
            "N2_scaffold_tests": "N2_scaffold_tests",
            "HALT": "HALT",  # #2756
        },
    )

    # #2327: test additions return to verification. The node never routes to
    # implementation, so a coverage shortfall cannot become an implementation
    # edit by any path. #4246: a recorded reason halts instead; the edge back
    # to N5 was unconditional, so N4c's error was overwritten by the next
    # measurement (ledger 0908, graph.py:732).
    workflow.add_conditional_edges(
        "N4c_augment_tests",
        route_after_augment,
        {
            "N5_verify_green": "N5_verify_green",
            "HALT": "HALT",
        },
    )

    # #3706: a failed build hook halts; the green phase never runs on it.
    workflow.add_conditional_edges(
        "N4_5_mechanical_hooks",
        route_after_mechanical_hooks,
        {
            "N5_verify_green": "N5_verify_green",
            "HALT": "HALT",
        },
    )

    # N6 -> N7 or N4 (iteration loop). #3585: no "end"; the cap halts.
    workflow.add_conditional_edges(
        "N6_e2e_validation",
        route_after_e2e,
        {
            "N7_finalize": "N7_finalize",
            "N4_implement_code": "N4_implement_code",
            "HALT": "HALT",  # #2756
        },
    )

    # N7 -> N7.5 (adversarial) or END (with skip_docs check) - Issue #352
    workflow.add_conditional_edges(
        "N7_finalize",
        route_after_finalize,
        {
            "N7_5_adversarial": "N7_5_adversarial",
            "end": END,
            "HALT": "HALT",  # #2756
        },
    )

    # N7.5 -> N8, or HALT when the review failed (#3725)
    workflow.add_conditional_edges(
        "N7_5_adversarial",
        route_after_adversarial,
        {
            "N8_document": "N8_document",
            "HALT": "HALT",
        },
    )

    # N8 -> N9 (conditional routing) or END - Issue #180
    workflow.add_conditional_edges(
        "N8_document",
        route_after_document,
        {
            "N9_cleanup": "N9_cleanup",
            "end": END,
        },
    )

    # HALT -> END (Issue #486: HALT processes error, then terminates)
    workflow.add_edge("HALT", END)

    # N9 -> END
    workflow.add_edge("N9_cleanup", END)

    return workflow