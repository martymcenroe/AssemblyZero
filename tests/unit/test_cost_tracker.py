"""Unit tests for per-node LLM cost tracking.

Issue #511: Persist per-node LLM cost through audit trail, telemetry, and dashboard.
"""

import pytest

from assemblyzero.utils.cost_tracker import (
    CostSummary,
    WorkflowCostReport,
    accumulate_node_cost,
    accumulate_node_tokens,
    build_cost_report,
)


class TestCostSummary:
    """Tests for CostSummary dataclass."""

    def test_defaults(self):
        s = CostSummary(node_name="test_node")
        assert s.node_name == "test_node"
        assert s.cost_usd == 0.0
        assert s.input_tokens == 0
        assert s.output_tokens == 0
        assert s.cache_read_tokens == 0
        assert s.cache_creation_tokens == 0
        assert s.llm_call_count == 0
        assert s.provider is None

    def test_populated(self):
        s = CostSummary(
            node_name="generate_draft",
            cost_usd=0.47,
            input_tokens=5000,
            output_tokens=12000,
            cache_read_tokens=100,
            cache_creation_tokens=200,
            llm_call_count=1,
            provider="anthropic",
        )
        assert s.cost_usd == 0.47
        assert s.input_tokens == 5000
        assert s.provider == "anthropic"


class TestWorkflowCostReport:
    """Tests for WorkflowCostReport dataclass."""

    def test_defaults(self):
        r = WorkflowCostReport()
        assert r.total_cost_usd == 0.0
        assert r.cost_by_node == {}
        assert r.budget_usd is None

    def test_to_dict_minimal(self):
        r = WorkflowCostReport(total_cost_usd=0.5)
        d = r.to_dict()
        assert d["total_cost_usd"] == 0.5
        assert "budget_usd" not in d

    def test_to_dict_with_budget(self):
        r = WorkflowCostReport(
            total_cost_usd=0.47,
            cost_by_node={"generate_draft": 0.35, "review": 0.12},
            budget_usd=1.0,
            budget_utilization_pct=47.0,
        )
        d = r.to_dict()
        assert d["total_cost_usd"] == 0.47
        assert d["cost_by_node"]["generate_draft"] == 0.35
        assert d["budget_usd"] == 1.0
        assert d["budget_utilization_pct"] == 47.0

    def test_to_dict_rounds_values(self):
        r = WorkflowCostReport(
            total_cost_usd=0.123456789,
            cost_by_node={"draft": 0.123456789},
        )
        d = r.to_dict()
        assert d["total_cost_usd"] == 0.123457  # 6 decimal places
        assert d["cost_by_node"]["draft"] == 0.123457


class TestBuildCostReport:
    """Tests for build_cost_report helper."""

    def test_basic(self):
        report = build_cost_report({"draft": 0.28, "review": 0.12})
        assert report.total_cost_usd == pytest.approx(0.40)
        assert report.cost_by_node == {"draft": 0.28, "review": 0.12}
        assert report.budget_usd is None
        assert report.budget_utilization_pct is None

    def test_with_tokens(self):
        report = build_cost_report(
            {"draft": 0.28},
            node_tokens={"draft": {"input": 5000, "output": 12000}},
        )
        assert report.total_input_tokens == 5000
        assert report.total_output_tokens == 12000

    def test_with_budget(self):
        report = build_cost_report(
            {"draft": 0.28, "review": 0.12},
            budget_usd=1.0,
        )
        assert report.budget_usd == 1.0
        assert report.budget_utilization_pct == pytest.approx(40.0)

    def test_empty(self):
        report = build_cost_report({})
        assert report.total_cost_usd == 0.0
        assert report.cost_by_node == {}


class TestAccumulateNodeCost:
    """Tests for accumulate_node_cost helper."""

    def test_new_node(self):
        result = accumulate_node_cost({}, "draft", 0.28)
        assert result == {"draft": 0.28}

    def test_existing_node_sums(self):
        """Same node called multiple times (revision loops) — costs sum."""
        existing = {"draft": 0.28}
        result = accumulate_node_cost(existing, "draft", 0.15)
        assert result["draft"] == pytest.approx(0.43)

    def test_different_nodes(self):
        existing = {"draft": 0.28}
        result = accumulate_node_cost(existing, "review", 0.12)
        assert result == {"draft": 0.28, "review": 0.12}

    def test_does_not_mutate_input(self):
        existing = {"draft": 0.28}
        result = accumulate_node_cost(existing, "review", 0.12)
        assert "review" not in existing  # Original unchanged
        assert "review" in result

    def test_zero_cost(self):
        result = accumulate_node_cost({}, "draft", 0.0)
        assert result == {"draft": 0.0}


class TestAccumulateNodeTokens:
    """Tests for accumulate_node_tokens helper."""

    def test_new_node(self):
        result = accumulate_node_tokens({}, "draft", 5000, 12000)
        assert result == {"draft": {"input": 5000, "output": 12000}}

    def test_existing_node_sums(self):
        existing = {"draft": {"input": 5000, "output": 12000}}
        result = accumulate_node_tokens(existing, "draft", 3000, 8000)
        assert result["draft"]["input"] == 8000
        assert result["draft"]["output"] == 20000

    def test_different_nodes(self):
        existing = {"draft": {"input": 5000, "output": 12000}}
        result = accumulate_node_tokens(existing, "review", 2000, 500)
        assert result["draft"] == {"input": 5000, "output": 12000}
        assert result["review"] == {"input": 2000, "output": 500}

    def test_does_not_mutate_input(self):
        existing = {"draft": {"input": 5000, "output": 12000}}
        result = accumulate_node_tokens(existing, "review", 2000, 500)
        assert "review" not in existing  # Original unchanged
        # Also verify deep copy (inner dict not mutated)
        assert existing["draft"]["input"] == 5000
