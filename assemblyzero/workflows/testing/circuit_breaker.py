"""Circuit breaker for TDD workflow token budget enforcement.

Estimates token consumption per iteration and trips the breaker
when the next iteration would exceed the configured budget.

Token estimation is approximate (1 token ~ 4 chars) since actual
usage happens inside Claude Code subprocesses. The goal is
order-of-magnitude protection against runaway loops, not precision.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from assemblyzero.workflows.testing.state import TestingWorkflowState


# Rough conversion: 1 token ~ 4 characters
CHARS_PER_TOKEN = 4

# Base overhead per iteration (system prompt, routing, pytest invocation)
BASE_TOKENS_PER_ITERATION = 5_000


def estimate_iteration_cost(state: "TestingWorkflowState") -> int:
    """Estimate token cost for one implementation iteration.

    Components:
    - Base overhead (system prompts, routing)
    - LLD content (sent as context each iteration)
    - Completed files (accumulated context)
    - Context files (injected via --context)
    - Output estimate (~30% of input)

    Args:
        state: Current workflow state.

    Returns:
        Estimated tokens for one iteration.
    """
    input_chars = 0

    # LLD content
    lld_content = state.get("lld_content", "")
    input_chars += len(lld_content)

    # Completed files (context accumulation)
    for _filepath, content in state.get("completed_files", []):
        input_chars += len(content)

    # Context files
    context_content = state.get("context_content", "")
    input_chars += len(context_content)

    # Test output (fed back as error context)
    green_output = state.get("green_phase_output", "")
    input_chars += len(green_output)

    input_tokens = input_chars // CHARS_PER_TOKEN
    output_estimate = int(input_tokens * 0.3)

    return BASE_TOKENS_PER_ITERATION + input_tokens + output_estimate


def check_circuit_breaker(
    state: "TestingWorkflowState",
) -> tuple[bool, str]:
    """Check if the next iteration would exceed the token budget.

    Args:
        state: Current workflow state.

    Returns:
        Tuple of (should_trip, reason_message).
        should_trip is False when no budget is set or budget not exceeded.
    """
    token_budget = state.get("token_budget", 0)
    if token_budget <= 0:
        return False, ""

    estimated_used = state.get("estimated_tokens_used", 0)
    next_cost = estimate_iteration_cost(state)

    if estimated_used + next_cost > token_budget:
        reason = (
            f"[CIRCUIT] Token budget would be exceeded: "
            f"{estimated_used:,} used + {next_cost:,} next iteration = "
            f"{estimated_used + next_cost:,} > {token_budget:,} budget"
        )
        return True, reason

    return False, ""


def record_iteration_cost(state: "TestingWorkflowState") -> int:
    """Record estimated token cost for the current iteration.

    Call this at the start of implement_code to track running total.

    Args:
        state: Current workflow state.

    Returns:
        Updated estimated_tokens_used value (for state update).
    """
    current = state.get("estimated_tokens_used", 0)
    cost = estimate_iteration_cost(state)
    return current + cost


def budget_summary(state: "TestingWorkflowState") -> str:
    """Generate a human-readable budget summary for the final report.

    Args:
        state: Current workflow state.

    Returns:
        Formatted summary string, or empty string if no budget was set.
    """
    token_budget = state.get("token_budget", 0)
    estimated_used = state.get("estimated_tokens_used", 0)

    if token_budget <= 0 and estimated_used <= 0:
        return ""

    lines = ["## Token Budget Summary", ""]
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Estimated tokens used | {estimated_used:,} |")

    if token_budget > 0:
        pct = (estimated_used / token_budget) * 100 if token_budget else 0
        lines.append(f"| Token budget | {token_budget:,} |")
        lines.append(f"| Budget used | {pct:.1f}% |")
    else:
        lines.append(f"| Token budget | unlimited |")

    return "\n".join(lines)
