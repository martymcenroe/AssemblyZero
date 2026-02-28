"""LangGraph workflow definition for Implementation Spec generation.

Issue #304: Implementation Readiness Review Workflow (LLD → Implementation Spec)

Creates a LangGraph StateGraph that connects:
- N0: load_lld (load and parse approved LLD)
- N1: analyze_codebase (extract current state from files)
- N2: generate_spec (generate Implementation Spec draft via Claude)
- N3: validate_completeness (mechanical completeness checks)
- N4: human_gate (optional human review checkpoint)
- N5: review_spec (Gemini readiness review)
- N6: finalize_spec (write final spec to docs/lld/drafts/)

Graph structure:
    START -> N0 -> N1 -> N2 -> N3 -> N4 -> N5 -> N6 -> END
                          ^         |              |
                          |         v              |
                          +---------+--------------+

Routing is controlled by:
- validation_passed: N3 result determines if spec meets completeness criteria
- review_verdict: N5 Gemini verdict (APPROVED / REVISE / BLOCKED)
- review_iteration: Current iteration count vs max_iterations
- human_gate_enabled: Whether N4 is active (default: disabled)
"""

from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from assemblyzero.workflows.implementation_spec.nodes.analyze_codebase import (
    analyze_codebase,
)
from assemblyzero.workflows.implementation_spec.nodes.finalize_spec import (
    finalize_spec,
)
from assemblyzero.workflows.implementation_spec.nodes.generate_spec import (
    generate_spec,
)
from assemblyzero.workflows.implementation_spec.nodes.human_gate import human_gate
from assemblyzero.workflows.implementation_spec.nodes.load_lld import load_lld
from assemblyzero.workflows.implementation_spec.nodes.review_spec import review_spec
from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
    validate_completeness,
)
from assemblyzero.workflows.implementation_spec.state import ImplementationSpecState
from assemblyzero.core.halt_node import create_halt_node

# =============================================================================
# Node Name Constants
# =============================================================================

N0_LOAD_LLD = "N0_load_lld"
N1_ANALYZE_CODEBASE = "N1_analyze_codebase"
N2_GENERATE_SPEC = "N2_generate_spec"
N3_VALIDATE_COMPLETENESS = "N3_validate_completeness"
N4_HUMAN_GATE = "N4_human_gate"
N5_REVIEW_SPEC = "N5_review_spec"
N6_FINALIZE_SPEC = "N6_finalize_spec"
HALT = "HALT"


# =============================================================================
# Routing Functions
# =============================================================================


def route_after_load(
    state: ImplementationSpecState,
) -> Literal["N1_analyze_codebase", "HALT"]:
    """Route after N0: load_lld.

    Routes to:
    - N1_analyze_codebase: LLD loaded successfully
    - HALT: Error loading LLD (Issue #486)

    Args:
        state: Current workflow state.

    Returns:
        Next node name.
    """
    if state.get("error_message"):
        return "HALT"
    return "N1_analyze_codebase"


def route_after_analyze(
    state: ImplementationSpecState,
) -> Literal["N2_generate_spec", "HALT"]:
    """Route after N1: analyze_codebase.

    Routes to:
    - N2_generate_spec: Codebase analysis complete
    - HALT: Error during analysis (Issue #486)

    Args:
        state: Current workflow state.

    Returns:
        Next node name.
    """
    if state.get("error_message"):
        return "HALT"
    return "N2_generate_spec"


def route_after_validation(
    state: ImplementationSpecState,
) -> Literal["N4_human_gate", "N5_review_spec", "N2_generate_spec", "HALT"]:
    """Route after N3: validate_completeness.

    Routes to:
    - N4_human_gate: Validation passed AND human_gate_enabled
    - N5_review_spec: Validation passed AND human gate disabled
    - N2_generate_spec: Validation failed, retry (if iterations remain)
    - HALT: Validation failed and max iterations exceeded (Issue #486)

    Args:
        state: Current workflow state.

    Returns:
        Next node name.
    """
    validation_passed = state.get("validation_passed", False)
    review_iteration = state.get("review_iteration", 0)
    max_iterations = state.get("max_iterations", 3)

    if validation_passed:
        if state.get("human_gate_enabled", False):
            return "N4_human_gate"
        return "N5_review_spec"

    # Validation failed
    if review_iteration < max_iterations:
        completeness_issues = state.get("completeness_issues", [])
        if completeness_issues:
            issue_summary = "; ".join(completeness_issues[:3])
            print(
                f"    [ROUTING] Completeness validation failed "
                f"(iteration {review_iteration}/{max_iterations}): {issue_summary}"
            )
        else:
            print(
                f"    [ROUTING] Completeness validation failed "
                f"(iteration {review_iteration}/{max_iterations})"
            )
        return "N2_generate_spec"

    print(
        f"    [ROUTING] Max iterations ({max_iterations}) reached "
        f"with validation failures - halting"
    )
    return "HALT"


def route_after_human_gate(
    state: ImplementationSpecState,
) -> Literal["N5_review_spec", "N2_generate_spec", "HALT", "END"]:
    """Route after N4: human_gate.

    Routes based on human decision:
    - N5_review_spec: Human approved, proceed to Gemini review
    - N2_generate_spec: Human requested revisions
    - HALT: Error (Issue #486)
    - END: Human rejected (normal exit)

    Args:
        state: Current workflow state.

    Returns:
        Next node name.
    """
    if state.get("error_message"):
        return "HALT"

    next_node = state.get("next_node", "")
    if next_node == "N5_review_spec":
        return "N5_review_spec"
    elif next_node == "N2_generate_spec":
        return "N2_generate_spec"
    return "END"


def route_after_review(
    state: ImplementationSpecState,
) -> Literal["N6_finalize_spec", "N2_generate_spec", "HALT"]:
    """Route after N5: review_spec.

    Issue #486: Error/blocked/max-iter routes to HALT. Two-strike stagnation.

    Routes to:
    - N6_finalize_spec: Gemini verdict is APPROVED
    - N2_generate_spec: Gemini verdict is REVISE (if iterations remain)
    - HALT: Error, BLOCKED, max iterations, or two-strike stagnation

    Args:
        state: Current workflow state.

    Returns:
        Next node name.
    """
    if state.get("error_message"):
        return "HALT"

    verdict = state.get("review_verdict", "BLOCKED")
    review_iteration = state.get("review_iteration", 0)
    max_iterations = state.get("max_iterations", 3)

    if verdict == "APPROVED":
        return "N6_finalize_spec"

    if verdict == "REVISE" and review_iteration < max_iterations:
        # Issue #486: Two-strike stagnation detection
        current_feedback = state.get("review_feedback", "")
        previous_feedback = state.get("previous_review_feedback", "")
        if previous_feedback and current_feedback:
            if _same_review_feedback(current_feedback, previous_feedback):
                print("    [HALT] Two consecutive REVISE verdicts with same feedback. Halting.")
                return "HALT"

        print(
            f"    [ROUTING] Gemini verdict REVISE "
            f"(iteration {review_iteration}/{max_iterations}) - regenerating spec"
        )
        return "N2_generate_spec"

    # BLOCKED or max iterations exceeded
    if review_iteration >= max_iterations:
        print(
            f"    [ROUTING] Max iterations ({max_iterations}) reached "
            f"with verdict {verdict} - halting"
        )
    else:
        print(f"    [ROUTING] Gemini verdict BLOCKED - halting workflow")
    return "HALT"


def _same_review_feedback(current: str, previous: str) -> bool:
    """Check if two REVISE verdicts have overlapping feedback.

    Issue #486: Two-strike stagnation detection for implementation spec.
    """
    if not current or not previous:
        return False

    current_lines = {
        line.strip().lower()
        for line in current.splitlines()
        if line.strip() and len(line.strip()) > 10
    }
    previous_lines = {
        line.strip().lower()
        for line in previous.splitlines()
        if line.strip() and len(line.strip()) > 10
    }

    if not current_lines:
        return False

    overlap = current_lines & previous_lines
    return len(overlap) / len(current_lines) > 0.5


# =============================================================================
# Graph Creation
# =============================================================================


def create_implementation_spec_graph() -> CompiledStateGraph:
    """Create the LangGraph workflow for Implementation Spec generation.

    Graph structure:
        START -> N0 -> N1 -> N2 -> N3 -> N4 -> N5 -> N6 -> END
                              ^         |              |
                              |         v              |
                              +---------+--------------+

    N4 (human gate) is optional and controlled by human_gate_enabled state.
    N3 validation failures loop back to N2 for regeneration.
    N5 REVISE verdicts loop back to N2 with feedback.
    Max iterations (default 3) prevent infinite loops.

    Returns:
        Compiled StateGraph ready for invocation.
    """
    # Create graph with state schema
    graph = StateGraph(ImplementationSpecState)

    # Add nodes
    graph.add_node(N0_LOAD_LLD, load_lld)
    graph.add_node(N1_ANALYZE_CODEBASE, analyze_codebase)
    graph.add_node(N2_GENERATE_SPEC, generate_spec)
    graph.add_node(N3_VALIDATE_COMPLETENESS, validate_completeness)
    graph.add_node(N4_HUMAN_GATE, human_gate)
    graph.add_node(N5_REVIEW_SPEC, review_spec)
    graph.add_node(N6_FINALIZE_SPEC, finalize_spec)
    graph.add_node(HALT, create_halt_node("implementation_spec"))  # Issue #486

    # START -> N0
    graph.add_edge(START, N0_LOAD_LLD)

    # HALT -> END (Issue #486: HALT processes error, then terminates)
    graph.add_edge(HALT, END)

    # N0 -> N1 or HALT (on error)
    graph.add_conditional_edges(
        N0_LOAD_LLD,
        route_after_load,
        {
            "N1_analyze_codebase": N1_ANALYZE_CODEBASE,
            "HALT": HALT,
        },
    )

    # N1 -> N2 or HALT (on error)
    graph.add_conditional_edges(
        N1_ANALYZE_CODEBASE,
        route_after_analyze,
        {
            "N2_generate_spec": N2_GENERATE_SPEC,
            "HALT": HALT,
        },
    )

    # N2 -> N3 (always proceeds to validation after generation)
    graph.add_edge(N2_GENERATE_SPEC, N3_VALIDATE_COMPLETENESS)

    # N3 -> N4 or N5 or N2 or HALT (based on validation result and config)
    graph.add_conditional_edges(
        N3_VALIDATE_COMPLETENESS,
        route_after_validation,
        {
            "N4_human_gate": N4_HUMAN_GATE,
            "N5_review_spec": N5_REVIEW_SPEC,
            "N2_generate_spec": N2_GENERATE_SPEC,
            "HALT": HALT,
        },
    )

    # N4 -> N5 or N2 or HALT or END (based on human decision)
    graph.add_conditional_edges(
        N4_HUMAN_GATE,
        route_after_human_gate,
        {
            "N5_review_spec": N5_REVIEW_SPEC,
            "N2_generate_spec": N2_GENERATE_SPEC,
            "HALT": HALT,
            "END": END,
        },
    )

    # N5 -> N6 or N2 or HALT (based on Gemini verdict, two-strike)
    graph.add_conditional_edges(
        N5_REVIEW_SPEC,
        route_after_review,
        {
            "N6_finalize_spec": N6_FINALIZE_SPEC,
            "N2_generate_spec": N2_GENERATE_SPEC,
            "HALT": HALT,
        },
    )

    # N6 -> END (workflow complete)
    graph.add_edge(N6_FINALIZE_SPEC, END)

    return graph.compile()