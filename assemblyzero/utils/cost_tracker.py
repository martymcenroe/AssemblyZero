"""Per-node LLM cost tracking for workflow instrumentation.

Issue #511: Persist per-node LLM cost through audit trail, telemetry, and dashboard.

Provides a CostTracker context manager that captures the cost delta of LLM calls
within a scope, and data classes for aggregating cost data across workflow runs.

Usage:
    from assemblyzero.utils.cost_tracker import CostTracker

    cost_before = get_cumulative_cost()
    result = provider.invoke(...)
    node_cost = get_cumulative_cost() - cost_before

    # Or via context manager:
    with CostTracker("generate_draft") as ct:
        result = provider.invoke(...)
    # ct.summary has cost_usd, input_tokens, etc.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Optional

from assemblyzero.core.llm_provider import get_cumulative_cost


@dataclass
class CostSummary:
    """Captured cost delta for a single node execution."""

    node_name: str
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    llm_call_count: int = 0
    provider: Optional[str] = None


@dataclass
class WorkflowCostReport:
    """Aggregated cost for an entire workflow run."""

    total_cost_usd: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    cost_by_node: dict[str, float] = field(default_factory=dict)
    tokens_by_node: dict[str, dict[str, int]] = field(default_factory=dict)
    budget_usd: Optional[float] = None
    budget_utilization_pct: Optional[float] = None

    def to_dict(self) -> dict:
        """Serialize to a dict suitable for JSON audit trail / telemetry."""
        d: dict = {
            "total_cost_usd": round(self.total_cost_usd, 6),
            "cost_by_node": {k: round(v, 6) for k, v in self.cost_by_node.items()},
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
        }
        if self.budget_usd is not None:
            d["budget_usd"] = self.budget_usd
        if self.budget_utilization_pct is not None:
            d["budget_utilization_pct"] = round(self.budget_utilization_pct, 1)
        return d


def build_cost_report(
    node_costs: dict[str, float],
    node_tokens: dict[str, dict[str, int]] | None = None,
    budget_usd: float | None = None,
) -> WorkflowCostReport:
    """Build a WorkflowCostReport from accumulated node cost data.

    Args:
        node_costs: Mapping of node_name -> cost_usd.
        node_tokens: Optional mapping of node_name -> {"input": N, "output": N}.
        budget_usd: Optional budget limit for utilization calculation.

    Returns:
        Populated WorkflowCostReport.
    """
    total_cost = sum(node_costs.values())
    total_input = 0
    total_output = 0

    if node_tokens:
        for tokens in node_tokens.values():
            total_input += tokens.get("input", 0)
            total_output += tokens.get("output", 0)

    utilization = None
    if budget_usd and budget_usd > 0:
        utilization = (total_cost / budget_usd) * 100.0

    return WorkflowCostReport(
        total_cost_usd=total_cost,
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        cost_by_node=dict(node_costs),
        tokens_by_node=dict(node_tokens) if node_tokens else {},
        budget_usd=budget_usd,
        budget_utilization_pct=utilization,
    )


def accumulate_node_cost(
    state_node_costs: dict[str, float],
    node_name: str,
    cost_usd: float,
) -> dict[str, float]:
    """Add a node's cost to the accumulated cost dict, handling repeated node names.

    If the same node runs multiple times (e.g., revision loops), costs are summed.

    Args:
        state_node_costs: Existing node cost accumulator from state.
        node_name: Name of the node.
        cost_usd: Cost delta for this invocation.

    Returns:
        Updated copy of the node costs dict.
    """
    costs = dict(state_node_costs)
    costs[node_name] = costs.get(node_name, 0.0) + cost_usd
    return costs


def accumulate_node_tokens(
    state_node_tokens: dict[str, dict[str, int]],
    node_name: str,
    input_tokens: int,
    output_tokens: int,
) -> dict[str, dict[str, int]]:
    """Add a node's token counts to the accumulated tokens dict.

    Args:
        state_node_tokens: Existing node tokens accumulator from state.
        node_name: Name of the node.
        input_tokens: Input tokens for this invocation.
        output_tokens: Output tokens for this invocation.

    Returns:
        Updated copy of the node tokens dict.
    """
    tokens = {k: dict(v) for k, v in state_node_tokens.items()}
    existing = tokens.get(node_name, {"input": 0, "output": 0})
    tokens[node_name] = {
        "input": existing.get("input", 0) + input_tokens,
        "output": existing.get("output", 0) + output_tokens,
    }
    return tokens
