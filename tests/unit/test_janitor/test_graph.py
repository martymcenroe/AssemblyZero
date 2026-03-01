"""Tests for janitor graph construction and routing.

Issue #94: Lu-Tze: The Janitor
Test IDs: T190-T230, T310-T350
"""

from unittest.mock import MagicMock, patch

from assemblyzero.workflows.janitor.graph import (
    build_janitor_graph,
    route_after_fix,
    route_after_sweep,
)
from assemblyzero.workflows.janitor.state import (
    Finding,
    JanitorState,
)


class TestRouteAfterSweep:
    """Test conditional routing after sweep. T190-T210, T310-T330."""

    def test_no_findings_returns_end(self):
        """T190/T310: route_after_sweep returns __end__ when no findings."""
        state = {"all_findings": [], "auto_fix": True}
        assert route_after_sweep(state) == "__end__"

    def test_fixable_auto_fix_returns_fixer(self):
        """T200/T320: route_after_sweep returns n1_fixer with fixable findings + auto_fix."""
        state = {
            "all_findings": [
                Finding(probe="links", category="broken_link", message="m", severity="warning", fixable=True)
            ],
            "auto_fix": True,
        }
        assert route_after_sweep(state) == "n1_fixer"

    def test_fixable_no_auto_fix_returns_reporter(self):
        """route_after_sweep returns n2_reporter when fixable but auto_fix=False."""
        state = {
            "all_findings": [
                Finding(probe="links", category="broken_link", message="m", severity="warning", fixable=True)
            ],
            "auto_fix": False,
        }
        assert route_after_sweep(state) == "n2_reporter"

    def test_unfixable_only_returns_reporter(self):
        """T210/T330: route_after_sweep returns n2_reporter with only unfixable."""
        state = {
            "all_findings": [
                Finding(probe="todo", category="stale_todo", message="m", severity="info", fixable=False)
            ],
            "auto_fix": True,
        }
        assert route_after_sweep(state) == "n2_reporter"

    def test_mixed_fixable_and_unfixable_returns_fixer(self):
        """route_after_sweep returns n1_fixer when mixed findings + auto_fix."""
        state = {
            "all_findings": [
                Finding(probe="links", category="broken_link", message="m", severity="warning", fixable=True),
                Finding(probe="todo", category="stale_todo", message="m", severity="info", fixable=False),
            ],
            "auto_fix": True,
        }
        assert route_after_sweep(state) == "n1_fixer"


class TestRouteAfterFix:
    """Test conditional routing after fix. T220, T230, T340, T350."""

    def test_all_fixed_returns_end(self):
        """T220/T340: route_after_fix returns __end__ when unfixable list empty."""
        state = {"unfixable_findings": []}
        assert route_after_fix(state) == "__end__"

    def test_unfixable_remain_returns_reporter(self):
        """T230/T350: route_after_fix returns n2_reporter when unfixable exist."""
        state = {
            "unfixable_findings": [
                Finding(probe="todo", category="stale_todo", message="m", severity="info", fixable=False)
            ]
        }
        assert route_after_fix(state) == "n2_reporter"


class TestBuildJanitorGraph:
    """Test graph construction."""

    def test_build_janitor_graph_compiles(self):
        """build_janitor_graph returns a compiled graph."""
        graph = build_janitor_graph()
        # Compiled graph should be callable (has invoke method)
        assert hasattr(graph, "invoke")

    def test_graph_with_no_findings(self):
        """Graph exits cleanly with no findings (all probes return ok)."""
        with patch(
            "assemblyzero.workflows.janitor.graph.get_probes",
            return_value=[],
        ):
            graph = build_janitor_graph()
            initial_state: JanitorState = {
                "repo_root": "/fake/repo",
                "scope": [],
                "auto_fix": True,
                "dry_run": False,
                "silent": True,
                "create_pr": False,
                "reporter_type": "local",
                "probe_results": [],
                "all_findings": [],
                "fix_actions": [],
                "unfixable_findings": [],
                "report_url": None,
                "exit_code": 0,
            }
            final_state = graph.invoke(initial_state)

        assert final_state["all_findings"] == []
        assert final_state["exit_code"] == 0