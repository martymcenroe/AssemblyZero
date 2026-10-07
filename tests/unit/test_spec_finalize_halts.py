"""N6 finalize's failures reach HALT (#3887, #3891; ADR 0236).

N6 reached END by an unconditional edge, so every error it returned ended the
run with no HALT record and no alert. It also wrote the spec under the
process's working directory when repo_root was empty, skipped the lineage save
when audit_dir was missing, and passed when the durable hand-off copy could
not be written.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.workflows.implementation_spec.graph import (
    create_implementation_spec_graph,
    route_after_finalize,
)
from assemblyzero.workflows.implementation_spec.nodes.finalize_spec import finalize_spec

SPEC = "# Implementation Spec\n\n" + ("Content line\n" * 50)


def _state(repo: Path, **overrides) -> dict:
    audit_dir = repo / "docs" / "lineage" / "active" / "7-implspec" / "20261007T000000Z"
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
    assert result["spec_path"] == ""
    for fragment in fragments:
        assert fragment in result["error_message"]
    assert route_after_finalize(result) == "HALT"


def test_the_graph_routes_n6_through_a_router():
    """The unconditional N6 -> END edge is gone; N6 has HALT as a successor."""
    graph = create_implementation_spec_graph()
    successors = {edge.target for edge in graph.get_graph().edges if edge.source == "N6_finalize_spec"}
    assert successors == {"HALT", "__end__"}


@pytest.mark.parametrize("state_change, fragment", [
    ({"spec_draft": ""}, "empty spec draft"),
    ({"review_verdict": "REVISE"}, "verdict 'REVISE'"),
    ({"issue_number": 0}, "Invalid issue number"),
])
def test_each_guard_routes_to_halt(tmp_path, state_change, fragment):
    _halts(finalize_spec(_state(tmp_path, **state_change)), fragment)


def test_a_missing_repo_root_halts(tmp_path):
    """It used to write the spec under the process's working directory."""
    _halts(finalize_spec(_state(tmp_path, repo_root="")), "repo_root is not set")


def test_a_missing_audit_dir_halts(tmp_path):
    """It used to skip the lineage save and the move to done/ without a word."""
    _halts(finalize_spec(_state(tmp_path, audit_dir=str(tmp_path / "gone"))), "audit directory", "gone")


def test_an_unwritable_handoff_copy_halts(tmp_path):
    """It used to print a warning and pass, leaving a relaunch unable to find the spec."""
    real_write = Path.write_text

    def refuse_handoff(self, *args, **kwargs):
        if self.name.endswith("-final-spec.md") and "lineage" in self.parts and "done" not in self.parts:
            raise OSError("disk full")
        return real_write(self, *args, **kwargs)

    with patch.object(Path, "write_text", refuse_handoff):
        result = finalize_spec(_state(tmp_path))
    _halts(result, "durable hand-off copy", "disk full")


def test_a_clean_finalize_ends_normally(tmp_path):
    result = finalize_spec(_state(tmp_path))
    assert result["error_message"] == ""
    assert Path(result["spec_path"]).is_file()
    assert route_after_finalize(result) == "END"
