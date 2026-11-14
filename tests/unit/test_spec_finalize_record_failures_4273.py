"""#4273: N6's audit save and lineage move stop the run through HALT.

``finalize_spec`` saved the final spec to the audit trail and moved the lineage
from active/ to done/ with no handler, so a failure in either raised out of N6
as an unhandled exception instead of returning an ``error_message`` that
``route_after_finalize`` sends to HALT, which alerts. Each now returns an
``error_message`` naming the path and the cause.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from langgraph.graph import END, StateGraph

from assemblyzero.core.halt_node import create_halt_node
from assemblyzero.workflows.implementation_spec import graph as g
from assemblyzero.workflows.implementation_spec.nodes.finalize_spec import finalize_spec
from assemblyzero.workflows.implementation_spec.state import ImplementationSpecState

SPEC = "# Implementation Spec\n\n" + ("Content line\n" * 50)

needs_posix_permissions = pytest.mark.skipif(
    sys.platform == "win32" or (hasattr(os, "geteuid") and os.geteuid() == 0),
    reason="a read-only directory refuses writes only on POSIX, and not to root",
)


def _state(repo: Path, audit_dir: Path | None = None, **overrides) -> dict:
    if audit_dir is None:
        audit_dir = repo / "docs" / "lineage" / "active" / "7-implspec" / "20261114T000000Z"
    audit_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "issue_number": 7,
        "spec_draft": SPEC,
        "review_verdict": "APPROVED",
        "review_feedback": "",
        "review_iteration": 1,
        "repo_root": str(repo),
        "audit_dir": str(audit_dir),
    }
    state.update(overrides)
    return state


def _halts(result: dict, *fragments: str) -> None:
    message = result["error_message"]
    assert message, "N6 must return an error_message"
    assert result["spec_path"] == ""
    assert "workflow_status" not in result
    for fragment in fragments:
        assert fragment in message, f"{fragment!r} not in {message!r}"
    assert g.route_after_finalize(result) == g.HALT


def _run_n6_through_the_graph(state: dict) -> list[str]:
    """Run the real N6 through the real router into the real HALT node.

    The edge map is the one the real graph compiles, read from its builder, so
    this cannot drift from what ships. Returns the nodes reached after N6.
    """
    real = g.create_implementation_spec_graph().builder.branches[g.N6_FINALIZE_SPEC]
    (branch,) = real.values()
    assert getattr(branch.path, "func", branch.path) is g.route_after_finalize

    visited: list[str] = []

    def halt(inner):
        def node(s):
            visited.append(g.HALT)
            return inner(s)
        return node

    graph = StateGraph(ImplementationSpecState)
    graph.add_node(g.N6_FINALIZE_SPEC, finalize_spec)
    graph.add_node(g.HALT, halt(create_halt_node("implementation_spec")))
    graph.add_edge(g.HALT, END)
    graph.set_entry_point(g.N6_FINALIZE_SPEC)
    graph.add_conditional_edges(g.N6_FINALIZE_SPEC, g.route_after_finalize, dict(branch.ends))
    graph.compile().invoke(state)
    return visited


class TestTheAuditSave:
    @needs_posix_permissions
    def test_t1_an_unwritable_audit_directory_halts_through_the_graph(
        self, tmp_path, operator_alerts
    ):
        state = _state(tmp_path)
        audit_dir = Path(state["audit_dir"])
        audit_dir.chmod(0o500)
        try:
            result = finalize_spec(dict(state))
            _halts(result, "#7", str(audit_dir / "001-final-spec.md"), "PermissionError")

            visited = _run_n6_through_the_graph(dict(state))
        finally:
            audit_dir.chmod(0o700)
        assert visited == [g.HALT]
        assert any(str(audit_dir) in alert["cause"] for alert in operator_alerts)

    def test_a_directory_on_the_audit_file_name_halts(self, tmp_path):
        """The same handler, on every platform: the save cannot write its file."""
        state = _state(tmp_path)
        squatter = Path(state["audit_dir"]) / "001-final-spec.md"
        squatter.mkdir()
        _halts(finalize_spec(state), "#7", str(squatter), "audit trail")

    def test_a_failed_save_leaves_the_lineage_in_active(self, tmp_path):
        state = _state(tmp_path)
        (Path(state["audit_dir"]) / "001-final-spec.md").mkdir()
        finalize_spec(state)
        assert Path(state["audit_dir"]).is_dir()
        assert not (tmp_path / "docs" / "lineage" / "done").exists()


class TestTheLineageMove:
    def test_a_move_that_cannot_make_its_destination_halts(self, tmp_path, operator_alerts):
        state = _state(tmp_path)
        blocker = tmp_path / "docs" / "lineage" / "done" / "7-implspec"
        blocker.parent.mkdir(parents=True)
        blocker.write_text("a file where the done/ directory must go\n", encoding="utf-8")

        result = finalize_spec(dict(state))
        _halts(result, "#7", state["audit_dir"], str(tmp_path), "FileExistsError")

        assert _run_n6_through_the_graph(dict(state)) == [g.HALT]

    def test_a_lineage_outside_active_halts(self, tmp_path):
        """move_lineage_to_done refuses a directory outside docs/lineage/active/."""
        outside = tmp_path / "elsewhere" / "7-implspec"
        state = _state(tmp_path, audit_dir=outside)
        _halts(finalize_spec(state), "#7", str(outside), "LineageSourceError")


def test_a_clean_finalize_still_reaches_end(tmp_path):
    state = _state(tmp_path)
    result = finalize_spec(dict(state))
    assert result["error_message"] == ""
    assert result["workflow_status"] == "completed"
    assert g.route_after_finalize(result) == "END"
    assert (tmp_path / "docs" / "lineage" / "done" / "7-implspec" / "20261114T000000Z"
            / "001-final-spec.md").is_file()
