"""The implementation-spec graph under standard 0034 (#3585).

N3 returns an ``error_message`` when a check cannot run (#3767) and at the
iteration cap (#2197). ``route_after_validation`` keyed its halt on
``completeness_cannot_check`` alone, so the loud-failure check listed N3 as a
node whose error no router sends to HALT: an N3 error without that field went
to N2, or on to review. Every N3 error now halts, and HALT alerts.

``graph.py``'s two ledger rows (lines 265 and 513, at ``79e18ad1``) were fixed
by #3887 before this sweep reached the file; the tests named for them pin that.
"""
from __future__ import annotations

from pathlib import Path

from langgraph.graph import END, StateGraph

from assemblyzero.core.halt_node import create_halt_node
from assemblyzero.core.loud_failure_check import scan_graphs
from assemblyzero.workflows.implementation_spec import graph as g
from assemblyzero.workflows.implementation_spec.state import ImplementationSpecState

REPO_ROOT = Path(__file__).resolve().parents[2]
CANNOT_RUN = "N3 completeness gate cannot run: something N3 needs is missing"


def _failed(**kw) -> dict:
    state = {
        "validation_passed": False,
        "review_iteration": 0,
        "max_iterations": 3,
        "completeness_issues": ["a check failed"],
        "grace_revision_for": [],
        "repo_root": str(REPO_ROOT),
    }
    state.update(kw)
    return state


class TestTheN3RouterReadsTheError:
    def test_n3_unrouted_error_an_error_below_the_cap_halts(self):
        """Without completeness_cannot_check this used to go back to N2."""
        assert g.route_after_validation(_failed(error_message=CANNOT_RUN)) == g.HALT

    def test_n3_unrouted_error_an_error_beside_a_pass_halts(self):
        """An error is never carried on into review."""
        state = _failed(validation_passed=True, error_message=CANNOT_RUN)
        assert g.route_after_validation(state) == g.HALT

    def test_n3_unrouted_error_an_error_beside_a_grace_halts(self):
        """N3 never writes both; a state carrying both halts rather than spend
        a revision past the cap."""
        state = _failed(
            review_iteration=3, grace_revision_for=["x"], error_message=CANNOT_RUN,
        )
        assert g.route_after_validation(state) == g.HALT

    def test_a_failure_below_the_cap_with_no_error_still_revises(self):
        """Kept: an ordinary completeness failure is a revision, not a halt."""
        assert g.route_after_validation(_failed(error_message="")) == g.N2_GENERATE_SPEC

    def test_a_grace_at_the_cap_with_no_error_still_revises(self):
        """Kept (#2304): N3 grants a grace with an empty error_message."""
        state = _failed(review_iteration=3, grace_revision_for=["x"], error_message="")
        assert g.route_after_validation(state) == g.N2_GENERATE_SPEC

    def test_the_cap_with_no_grace_still_halts(self):
        """Kept (#486)."""
        assert g.route_after_validation(_failed(review_iteration=3)) == g.HALT


class TestTheLoudFailureCheck:
    def test_n3_unrouted_error_the_check_finds_n3_routed(self):
        builders = (("assemblyzero.workflows.implementation_spec.graph",
                     "create_implementation_spec_graph"),)
        findings = scan_graphs(REPO_ROOT, builders)
        assert [f.key for f in findings] == []


def _halts_from_n3(state: dict) -> list[str]:
    """Run a stub N3 through the real router into the real HALT node.

    The edge map is the one the real graph compiles, read from its builder,
    so this cannot drift from what ships.
    """
    real = g.create_implementation_spec_graph().builder.branches[g.N3_VALIDATE_COMPLETENESS]
    (branch,) = real.values()
    assert getattr(branch.path, "func", branch.path) is g.route_after_validation

    visited: list[str] = []

    def stub(name):
        def node(_state):
            visited.append(name)
            return {}
        return node

    graph = StateGraph(ImplementationSpecState)
    graph.add_node(g.N3_VALIDATE_COMPLETENESS, lambda _s: state)
    for name in (g.N2_GENERATE_SPEC, g.N4_HUMAN_GATE, g.N5_REVIEW_SPEC):
        graph.add_node(name, stub(name))
        graph.add_edge(name, END)
    graph.add_node(g.HALT, create_halt_node("implementation_spec"))
    graph.add_edge(g.HALT, END)
    graph.set_entry_point(g.N3_VALIDATE_COMPLETENESS)
    graph.add_conditional_edges(
        g.N3_VALIDATE_COMPLETENESS, g.route_after_validation, dict(branch.ends),
    )
    graph.compile().invoke({"issue_number": 3585})
    return visited


class TestThroughTheGraph:
    def test_n3_unrouted_error_reaches_halt_which_alerts(self, operator_alerts):
        visited = _halts_from_n3(_failed(error_message=CANNOT_RUN))

        assert visited == []
        assert len(operator_alerts) == 1
        assert CANNOT_RUN in operator_alerts[0]["cause"]

    def test_a_revision_does_not_alert(self, operator_alerts):
        """Kept: a failure with no error reaches N2 and nobody is paged."""
        visited = _halts_from_n3(_failed(error_message=""))

        assert visited == [g.N2_GENERATE_SPEC]
        assert operator_alerts == []


class TestTheRowsFixedBy3887:
    def test_265_an_empty_or_unknown_human_gate_decision_halts(self):
        assert g.route_after_human_gate({"next_node": ""}) == g.HALT
        assert g.route_after_human_gate({"next_node": "N9_nowhere"}) == g.HALT
        assert g.route_after_human_gate({"next_node": "END"}) == "END"

    def test_513_a_finalize_error_reaches_halt(self):
        assert g.route_after_finalize({"error_message": "write failed"}) == g.HALT
        assert g.route_after_finalize({"error_message": ""}) == "END"
        branches = g.create_implementation_spec_graph().builder.branches
        (branch,) = branches[g.N6_FINALIZE_SPEC].values()
        assert dict(branch.ends)[g.HALT] == g.HALT
