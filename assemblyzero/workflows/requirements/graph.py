"""Parameterized StateGraph for Requirements Workflow.

Issue #101: Unified Requirements Workflow
Issue #248: Add conditional edge for question-loop after review
Issue #277: Add mechanical validation node before human gate
Issue #334: Print validation errors in route_after_validate function
Issue #166: Add test plan validation node (N1b) after mechanical validation
Issue #401: Add codebase analysis node (N0b) between load_input and generate_draft

Creates a LangGraph StateGraph that connects:
- N0: load_input (brief or issue loading)
- N0b: analyze_codebase (codebase context analysis - Issue #401, LLD only)
- N1: generate_draft (pluggable drafter)
- N1.5: validate_lld_mechanical (mechanical validation - Issue #277)
- N1b: validate_test_plan (test plan coverage validation - Issue #166)
- N2: human_gate_draft (human checkpoint)
- N3: review (pluggable reviewer)
- N4: human_gate_verdict (human checkpoint)
- N5: finalize (issue filing or LLD saving)

Graph structure (LLD workflow):
    START -> N0 -> N0b -> N1 -> N1.5 -> N1b -> N2 -> N3 -> N4 -> N5 -> END
                          ^                          |         |
                          |                          v         |
                          +----------<---------------+---------+

Issue #248 addition: After N3 (review), if open questions are UNANSWERED,
loop back to N3 with a followup prompt. If HUMAN_REQUIRED, force N4.

Issue #277 addition: N1.5 validates LLD structure mechanically (paths, sections)
before any human or LLM review. Blocks on errors, warns on issues.

Issue #334 addition: Validation errors are now printed to console in
route_after_validate_mechanical for immediate user feedback.

Issue #166 addition: N1b validates test plan coverage, vague assertions,
and human delegation before Gemini review.

Routing is controlled by:
- error_message: Non-empty routes to END
- config_gates_*: Whether human gates are enabled
- next_node: Set by human gate nodes for routing decisions
- lld_status: Used for auto-routing when gates disabled
- open_questions_status: Used for question-loop routing (Issue #248)
"""

from typing import Literal

from langgraph.graph import END, START, StateGraph

from assemblyzero.workflows.requirements.nodes import (
    analyze_codebase,
    finalize,
    generate_draft,
    human_gate_draft,
    human_gate_verdict,
    load_input,
    ponder_stibbons_node,
    review,
    validate_lld_mechanical,
    validate_test_plan_node,
)
from assemblyzero.workflows.requirements.nodes.validate_mechanical import (
    print_validation_errors,
)
from assemblyzero.workflows.requirements.state import RequirementsWorkflowState
from assemblyzero.core.halt_node import create_halt_node


# =============================================================================
# Node Name Constants
# =============================================================================

N0_LOAD_INPUT = "N0_load_input"
N0B_ANALYZE_CODEBASE = "N0b_analyze_codebase"  # Issue #401
N1_GENERATE_DRAFT = "N1_generate_draft"
N1_5_VALIDATE_MECHANICAL = "N1_5_validate_mechanical"  # Issue #277
N1B_VALIDATE_TEST_PLAN = "N1b_validate_test_plan"  # Issue #166
N_PONDER = "N_ponder_stibbons"  # Issue #307
N2_HUMAN_GATE_DRAFT = "N2_human_gate_draft"
N3_REVIEW = "N3_review"
N4_HUMAN_GATE_VERDICT = "N4_human_gate_verdict"
N5_FINALIZE = "N5_finalize"
HALT = "HALT"


# =============================================================================
# Routing Functions
# =============================================================================


def route_after_load_input(
    state: RequirementsWorkflowState,
) -> Literal["N0b_analyze_codebase", "N1_generate_draft", "HALT"]:
    """Route after load_input node.

    Issue #401: LLD workflows route through N0b (codebase analysis) first.
    Issue #486: Error routes to HALT instead of END.

    Routes to:
    - N0b_analyze_codebase: LLD workflow (Issue #401)
    - N1_generate_draft: Issue workflow
    - HALT: Error loading input

    Args:
        state: Current workflow state.

    Returns:
        Next node name.
    """
    if state.get("error_message"):
        return "HALT"
    # Issue #401: LLD workflows analyze codebase before drafting
    if state.get("workflow_type") == "lld":
        return "N0b_analyze_codebase"
    return "N1_generate_draft"


def route_after_generate_draft(
    state: RequirementsWorkflowState,
) -> Literal["N1_5_validate_mechanical", "N2_human_gate_draft", "N3_review", "HALT"]:
    """Route after generate_draft node.

    Routes to:
    - N1_5_validate_mechanical: LLD workflow (Issue #277)
    - N2_human_gate_draft: Issue workflow with gate enabled
    - N3_review: Issue workflow with gate disabled
    - HALT: Error generating draft (Issue #486)

    Issue #248: Pre-review validation gate removed. Drafts with open
    questions now proceed to review where Gemini can answer them.

    Issue #277: LLD workflows now go through mechanical validation first.

    Args:
        state: Current workflow state.

    Returns:
        Next node name.
    """
    if state.get("error_message"):
        return "HALT"

    # Issue #277: LLD workflows go through mechanical validation
    if state.get("workflow_type") == "lld":
        return "N1_5_validate_mechanical"

    # Issue workflows skip mechanical validation
    if state.get("config_gates_draft", True):
        return "N2_human_gate_draft"
    else:
        return "N3_review"


def route_after_validate_mechanical(
    state: RequirementsWorkflowState,
) -> Literal["N1b_validate_test_plan", "N1_generate_draft", "HALT"]:
    """Route after validate_lld_mechanical node.

    Issue #277: Routes based on validation result.
    Issue #334: Prints validation errors to console for immediate feedback.
    Issue #166: On pass, routes to N1b (test plan validation) instead of N2.
    Issue #486: Max iteration exits route to HALT.

    Routes to:
    - N1b_validate_test_plan: Validation passed (Issue #166)
    - N1_generate_draft: Validation failed (BLOCKED), return to drafter
    - HALT: Max iterations reached

    Args:
        state: Current workflow state.

    Returns:
        Next node name.
    """
    # Check for validation failure (BLOCKED status)
    if state.get("lld_status") == "BLOCKED":
        # Issue #334: Print validation errors to console for user visibility
        validation_errors = state.get("validation_errors", [])
        if validation_errors:
            print_validation_errors(validation_errors)

        # Check max iterations before looping back
        iteration_count = state.get("iteration_count", 0)
        max_iterations = state.get("max_iterations", 20)
        if iteration_count >= max_iterations:
            print(f"    [ROUTING] Max iterations ({max_iterations}) reached with validation errors - halting")
            return "HALT"
        print("    [ROUTING] Mechanical validation failed - returning to drafter")
        return "N1_generate_draft"

    # Issue #166: Validation passed - proceed to test plan validation
    return "N1b_validate_test_plan"


def route_after_validate_test_plan(
    state: RequirementsWorkflowState,
) -> Literal["N_ponder_stibbons", "N1_generate_draft", "HALT"]:
    """Route after validate_test_plan node.

    Issue #166: Routes based on test plan validation result.
    Issue #307: Pass now routes to Ponder (auto-fix) before N2/N3.
    Issue #486: Error/max-iteration routes to HALT.

    Routes to:
    - N_ponder_stibbons: Validation passed, apply auto-fixes
    - N1_generate_draft: Validation failed, return to drafter
    - HALT: Error or max iterations reached

    Args:
        state: Current workflow state.

    Returns:
        Next node name.
    """
    if state.get("error_message"):
        return "HALT"

    # Check if test plan validation failed (lld_status set to BLOCKED by node)
    result = state.get("test_plan_validation_result")
    if result and not result.get("passed", False):
        # Check max iterations before looping back
        iteration_count = state.get("iteration_count", 0)
        max_iterations = state.get("max_iterations", 20)
        if iteration_count >= max_iterations:
            print(f"    [ROUTING] Max iterations ({max_iterations}) reached with test plan errors - halting")
            return "HALT"
        print("    [ROUTING] Test plan validation failed - returning to drafter")
        return "N1_generate_draft"

    # Validation passed - route through Ponder for auto-fixes (Issue #307)
    return "N_ponder_stibbons"


def route_after_ponder(
    state: RequirementsWorkflowState,
) -> Literal["N2_human_gate_draft", "N3_review"]:
    """Route after Ponder Stibbons auto-fix node.

    Issue #307: After auto-fixes, proceed to human gate or review.
    Ponder never routes back to drafter — it only fixes mechanical issues.

    Args:
        state: Current workflow state.

    Returns:
        Next node name.
    """
    if state.get("config_gates_draft", True):
        return "N2_human_gate_draft"
    else:
        return "N3_review"


def route_from_human_gate_draft(
    state: RequirementsWorkflowState,
) -> Literal["N3_review", "N1_generate_draft", "END"]:
    """Route from human_gate_draft node.

    Routes based on next_node set by the gate:
    - N3_review: Send to review
    - N1_generate_draft: Revise draft
    - END: Manual handling (normal exit, not error — no HALT needed)

    Args:
        state: Current workflow state.

    Returns:
        Next node name.
    """
    next_node = state.get("next_node", "")

    if next_node == "N3_review":
        return "N3_review"
    elif next_node == "N1_generate_draft":
        return "N1_generate_draft"
    else:
        return "END"


def route_after_review(
    state: RequirementsWorkflowState,
) -> Literal["N4_human_gate_verdict", "N5_finalize", "N1_generate_draft", "N3_review", "HALT"]:
    """Route after review node.

    Issue #248: Extended routing for open questions loop.
    Issue #486: Error routes to HALT. Two-strike stagnation detection.

    Routes to:
    - N4_human_gate_verdict: Gate enabled OR open questions HUMAN_REQUIRED
    - N5_finalize: Gate disabled and approved
    - N1_generate_draft: Gate disabled and blocked (if iterations remain)
    - N3_review: Open questions UNANSWERED (loop back for followup)
    - HALT: Error in review, max iterations, or two-strike stagnation

    Args:
        state: Current workflow state.

    Returns:
        Next node name.
    """
    if state.get("error_message"):
        return "HALT"

    # Issue #248: Check open questions status first
    open_questions_status = state.get("open_questions_status", "NONE")

    # If HUMAN_REQUIRED, force human gate regardless of gate config
    if open_questions_status == "HUMAN_REQUIRED":
        print("    [ROUTING] Open questions marked HUMAN REQUIRED - escalating to human gate")
        return "N4_human_gate_verdict"

    # If UNANSWERED, loop back to review (not draft - this is a review followup)
    # But respect max_iterations to prevent infinite loops
    if open_questions_status == "UNANSWERED":
        iteration_count = state.get("iteration_count", 0)
        max_iterations = state.get("max_iterations", 20)
        if iteration_count >= max_iterations:
            print(f"    [ROUTING] Max iterations ({max_iterations}) reached with unanswered questions - going to human gate")
            return "N4_human_gate_verdict"
        print("    [ROUTING] Open questions unanswered - looping back to drafter for revision")
        return "N1_generate_draft"

    # Normal routing
    if state.get("config_gates_verdict", True):
        return "N4_human_gate_verdict"
    else:
        # Auto-route based on verdict
        lld_status = state.get("lld_status", "PENDING")
        if lld_status == "APPROVED":
            return "N5_finalize"
        else:
            # Issue #486: Two-strike stagnation detection
            if lld_status == "BLOCKED" and state.get("previous_review_feedback"):
                current_feedback = state.get("current_verdict", "")
                previous_feedback = state.get("previous_review_feedback", "")
                # Issue #503: Structured two-strike comparison
                from assemblyzero.core.verdict_schema import same_blocking_issues
                if same_blocking_issues(current_feedback, previous_feedback):
                    print("    [HALT] Two consecutive BLOCKED verdicts with same issues. Halting.")
                    return "HALT"

            # Check max iterations before looping back
            iteration_count = state.get("iteration_count", 0)
            max_iterations = state.get("max_iterations", 20)
            if iteration_count >= max_iterations:
                # Max iterations reached - finalize with current status
                return "N5_finalize"
            return "N1_generate_draft"


def _same_blocking_issues(current_feedback: str, previous_feedback: str) -> bool:
    """Check if two BLOCKED verdicts have overlapping blocking issues.

    Issue #486: Two-strike stagnation detection.
    Uses simple substring overlap heuristic: if >50% of lines from the
    current feedback appear in the previous feedback, it's stagnation.
    """
    if not current_feedback or not previous_feedback:
        return False

    current_lines = {
        line.strip().lower()
        for line in current_feedback.splitlines()
        if line.strip() and len(line.strip()) > 10  # Skip short/empty lines
    }
    previous_lines = {
        line.strip().lower()
        for line in previous_feedback.splitlines()
        if line.strip() and len(line.strip()) > 10
    }

    if not current_lines:
        return False

    overlap = current_lines & previous_lines
    overlap_ratio = len(overlap) / len(current_lines)
    return overlap_ratio > 0.5


def route_from_human_gate_verdict(
    state: RequirementsWorkflowState,
) -> Literal["N5_finalize", "N1_generate_draft", "END"]:
    """Route from human_gate_verdict node.

    Routes based on next_node set by the gate:
    - N5_finalize: Approve and finalize
    - N1_generate_draft: Revise draft
    - END: Manual handling

    Args:
        state: Current workflow state.

    Returns:
        Next node name.
    """
    next_node = state.get("next_node", "")

    if next_node == "N5_finalize":
        return "N5_finalize"
    elif next_node == "N1_generate_draft":
        return "N1_generate_draft"
    else:
        return "END"


def route_after_finalize(
    state: RequirementsWorkflowState,
) -> Literal["END"]:
    """Route after finalize node.

    Always routes to END (workflow complete).

    Args:
        state: Current workflow state.

    Returns:
        END.
    """
    return "END"


# =============================================================================
# Graph Creation
# =============================================================================


def create_requirements_graph() -> StateGraph:
    """Create the requirements workflow graph.

    Graph structure (LLD workflow):
        START -> N0 -> N0b -> N1 -> N1.5 -> N1b -> N2 -> N3 -> N4 -> N5 -> END
                              ^                          |         |
                              |                          v         |
                              +----------<---------------+---------+

    Issue #248: N3 can now loop back to N1 when open questions are
    unanswered, or force N4 when questions require human decision.

    Issue #166: N1b validates test plan coverage after structural validation.

    Issue #401: N0b analyzes target codebase for context (LLD workflows only).

    Returns:
        Uncompiled StateGraph.
    """
    # Create graph with state schema
    graph = StateGraph(RequirementsWorkflowState)

    # Add nodes
    graph.add_node(N0_LOAD_INPUT, load_input)
    graph.add_node(N0B_ANALYZE_CODEBASE, analyze_codebase)  # Issue #401
    graph.add_node(N1_GENERATE_DRAFT, generate_draft)
    graph.add_node(N1_5_VALIDATE_MECHANICAL, validate_lld_mechanical)  # Issue #277
    graph.add_node(N1B_VALIDATE_TEST_PLAN, validate_test_plan_node)  # Issue #166
    graph.add_node(N_PONDER, ponder_stibbons_node)  # Issue #307
    graph.add_node(N2_HUMAN_GATE_DRAFT, human_gate_draft)
    graph.add_node(N3_REVIEW, review)
    graph.add_node(N4_HUMAN_GATE_VERDICT, human_gate_verdict)
    graph.add_node(N5_FINALIZE, finalize)
    graph.add_node(HALT, create_halt_node("requirements"))  # Issue #486

    # Add edges
    # START -> N0
    graph.add_edge(START, N0_LOAD_INPUT)

    # HALT -> END (Issue #486: HALT processes error, then terminates)
    graph.add_edge(HALT, END)

    # N0 -> N0b (LLD) or N1 or HALT (on error)
    # Issue #401: LLD workflows go through codebase analysis
    graph.add_conditional_edges(
        N0_LOAD_INPUT,
        route_after_load_input,
        {
            "N0b_analyze_codebase": N0B_ANALYZE_CODEBASE,
            "N1_generate_draft": N1_GENERATE_DRAFT,
            "HALT": HALT,
        },
    )

    # N0b -> N1 (always proceeds to draft generation)
    graph.add_edge(N0B_ANALYZE_CODEBASE, N1_GENERATE_DRAFT)

    # N1 -> N1.5 (LLD) or N2 or N3 or HALT (based on workflow type, gates, error)
    # Issue #277: LLD workflows go through mechanical validation
    graph.add_conditional_edges(
        N1_GENERATE_DRAFT,
        route_after_generate_draft,
        {
            "N1_5_validate_mechanical": N1_5_VALIDATE_MECHANICAL,
            "N2_human_gate_draft": N2_HUMAN_GATE_DRAFT,
            "N3_review": N3_REVIEW,
            "HALT": HALT,
        },
    )

    # N1.5 -> N1b or N1 or HALT (based on validation result)
    # Issue #277: Mechanical validation routes based on BLOCKED status
    # Issue #166: On pass, routes to N1b (test plan validation)
    graph.add_conditional_edges(
        N1_5_VALIDATE_MECHANICAL,
        route_after_validate_mechanical,
        {
            "N1b_validate_test_plan": N1B_VALIDATE_TEST_PLAN,
            "N1_generate_draft": N1_GENERATE_DRAFT,
            "HALT": HALT,
        },
    )

    # N1b -> Ponder or N1 or HALT (based on test plan validation)
    # Issue #166: Test plan validation routes
    # Issue #307: Pass goes through Ponder before N2/N3
    graph.add_conditional_edges(
        N1B_VALIDATE_TEST_PLAN,
        route_after_validate_test_plan,
        {
            "N_ponder_stibbons": N_PONDER,
            "N1_generate_draft": N1_GENERATE_DRAFT,
            "HALT": HALT,
        },
    )

    # Ponder -> N2 or N3 (Issue #307: always proceeds after auto-fix)
    graph.add_conditional_edges(
        N_PONDER,
        route_after_ponder,
        {
            "N2_human_gate_draft": N2_HUMAN_GATE_DRAFT,
            "N3_review": N3_REVIEW,
        },
    )

    # N2 -> N3 or N1 or END (based on human decision)
    graph.add_conditional_edges(
        N2_HUMAN_GATE_DRAFT,
        route_from_human_gate_draft,
        {
            "N3_review": N3_REVIEW,
            "N1_generate_draft": N1_GENERATE_DRAFT,
            "END": END,
        },
    )

    # N3 -> N4 or N5 or N1 or N3 or HALT (based on gates, verdict, open questions, stagnation)
    # Issue #248: Added N3_review as possible target for open questions loop
    # Issue #486: Added HALT for error/stagnation
    graph.add_conditional_edges(
        N3_REVIEW,
        route_after_review,
        {
            "N4_human_gate_verdict": N4_HUMAN_GATE_VERDICT,
            "N5_finalize": N5_FINALIZE,
            "N1_generate_draft": N1_GENERATE_DRAFT,
            "N3_review": N3_REVIEW,
            "HALT": HALT,
        },
    )

    # N4 -> N5 or N1 or END (based on human decision)
    graph.add_conditional_edges(
        N4_HUMAN_GATE_VERDICT,
        route_from_human_gate_verdict,
        {
            "N5_finalize": N5_FINALIZE,
            "N1_generate_draft": N1_GENERATE_DRAFT,
            "END": END,
        },
    )

    # N5 -> END
    graph.add_edge(N5_FINALIZE, END)

    return graph
