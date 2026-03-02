"""Generic HALT node factory for LangGraph workflows.

Issue #486: Halt-and-Plan pattern — self-babysitting workflows.

Creates a LangGraph-compatible node that:
1. Saves full workflow state to disk
2. Classifies the error from state["error_message"]
3. Generates a structured recovery plan
4. Prints a human-readable summary
5. Returns paths for downstream consumption
"""

from pathlib import Path

from assemblyzero.core.errors import (
    AuthenticationError,
    CapacityError,
    RateLimitError,
    classify_http_status,
)
from assemblyzero.core.recovery_plan import generate_recovery_plan
from assemblyzero.core.state_persistence import STATE_DIR, save_state_snapshot


def classify_error(error_message: str) -> str:
    """Classify error type from the error_message string.

    Issue #546: Delegates to errors.py for HTTP-related classifications,
    preserving domain-specific patterns (stagnation, budget, preflight)
    that have no HTTP equivalent.

    Args:
        error_message: The error message from the workflow state.

    Returns:
        Classified error type string.
    """
    msg_lower = error_message.lower()

    # Domain-specific classifications first (no HTTP equivalent)
    if any(p in msg_lower for p in ("stagnation", "same issues", "same blocking", "two consecutive")):
        return "stagnation"
    if any(p in msg_lower for p in ("budget", "cost budget exceeded")):
        return "budget"
    if "preflight" in msg_lower:
        if "unavailable" in msg_lower or "exhausted" in msg_lower:
            return "quota_exhausted"
        return "preflight"

    # Try to extract an HTTP status code and delegate to errors.py
    import re
    status_match = re.search(r'\bstatus[=: ]*(\d{3})\b', msg_lower)
    if status_match:
        status_code = int(status_match.group(1))
        classified = classify_http_status(status_code, error_message)
        if isinstance(classified, CapacityError):
            return "capacity_exhausted"
        if isinstance(classified, RateLimitError):
            return "quota_exhausted"
        if isinstance(classified, AuthenticationError):
            return "auth"

    # Fallback: pattern matching for messages without status codes
    if any(p in msg_lower for p in ("capacity exhausted", "503", "529", "overloaded")):
        return "capacity_exhausted"
    if any(p in msg_lower for p in ("quota exhausted", "429", "all credentials exhausted")):
        return "quota_exhausted"
    if any(p in msg_lower for p in ("auth", "api_key_invalid", "permission_denied", "unauthenticated")):
        return "auth"

    return "unknown"


def create_halt_node(workflow_name: str):
    """Factory: returns a LangGraph-compatible node function.

    Args:
        workflow_name: The workflow this halt node belongs to
                       (requirements, implementation_spec, testing, orchestrator).

    Returns:
        A function(state: dict) -> dict suitable for graph.add_node("HALT", ...).
    """

    def halt_with_plan(state: dict) -> dict:
        """HALT node — saves state, generates recovery plan, prints summary.

        Args:
            state: The current LangGraph workflow state dict.

        Returns:
            Dict with recovery_plan_path and state_snapshot_path keys.
        """
        issue_number = state.get("issue_number", 0)
        error_message = state.get("error_message", "Unknown error")
        cost_budget = state.get("cost_budget_usd", 0.0)

        # 1. Classify the error
        error_type = classify_error(error_message)

        # 2. Determine which stage halted (from state context)
        stage = _infer_stage(state, workflow_name)

        # 3. Save full state to disk
        state_path = save_state_snapshot(
            workflow_name, issue_number, state, trigger="halt"
        )

        # 4. Generate recovery plan
        plan = generate_recovery_plan(
            issue_number=issue_number,
            workflow=workflow_name,
            stage=stage,
            error_type=error_type,
            error_message=error_message,
            state=state,
            cost_budget_usd=cost_budget,
        )
        plan.state_path = str(state_path)

        # 5. Save plan to same directory as state
        plan_path = plan.save(state_path.parent)

        # 6. Print human-readable summary
        plan.print_summary()

        return {
            "recovery_plan_path": str(plan_path),
            "state_snapshot_path": str(state_path),
        }

    return halt_with_plan


def _infer_stage(state: dict, workflow_name: str) -> str:
    """Infer which stage the workflow was in when it halted."""
    # Use review_iteration or iteration_count as hints
    if "review_iteration" in state:
        iteration = state.get("review_iteration", 0)
        if iteration > 0:
            return f"N5_review_iter{iteration}"
        return "N2_generate"
    elif "iteration_count" in state:
        iteration = state.get("iteration_count", 0)
        if state.get("current_verdict"):
            return f"N3_review_iter{iteration}"
        if state.get("current_draft"):
            return f"N1_draft_iter{iteration}"
        return f"N0_load"
    elif "next_node" in state:
        return state.get("next_node", "unknown")
    else:
        return f"{workflow_name}_unknown"
