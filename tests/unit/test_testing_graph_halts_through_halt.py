"""An implementation-stage halt goes through the node that owns halting (#2756).

The testing graph declared a `HALT` node and nothing routed to it. Every stop
went straight to `END` carrying an `error_message`, which the orchestrator
relayed — so halting worked, and the node built to write the halt bundle never
ran. `create_halt_node` is what produces that bundle: the gate key, the work
still outstanding, and the command to resume, which #2725 spent a PR making
findable.

The acceptance is the bundle, not the routing: a halted roll of the REAL
compiled graph has to leave one on disk, with the same three things #2735
asserts for the other two graphs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import assemblyzero.core.halt_node as hn
import assemblyzero.core.state_persistence as sp
from assemblyzero.workflows.testing.graph import (
    build_testing_workflow,
    route_after_green,
    route_after_implement,
    route_after_load,
    route_after_scaffold,
)


@pytest.fixture
def state_dir(tmp_path, monkeypatch):
    """Redirect the halt's snapshot away from the real state directory.

    Patched on BOTH modules: `halt_node` imports `STATE_DIR` by value, and
    `save_state_snapshot` reads it from `state_persistence`.
    """
    target = tmp_path / "state"
    target.mkdir()
    monkeypatch.setattr(hn, "STATE_DIR", target, raising=False)
    monkeypatch.setattr(sp, "STATE_DIR", target, raising=False)
    return target


def _bundles(root: Path) -> list[Path]:
    return sorted(root.rglob("halt-evidence.json"))


class TestTheGraphReachesHalt:
    """The wiring, measured against the compiled graph rather than the source."""

    def test_halt_has_inbound_edges_now(self):
        graph = build_testing_workflow().compile().get_graph()
        inbound = sorted(e.source for e in graph.edges if e.target == "HALT")
        assert inbound, (
            "HALT has no inbound edge: the node that writes the halt bundle "
            "is stranded again (#2756)"
        )
        # Every router that can carry an error_message reaches it.
        assert set(inbound) == {
            "N0_load_lld",
            "N1_review_test_plan",
            "N2_scaffold_tests",
            "N2_5_validate_tests",
            "N3_verify_red",
            "N4_implement_code",
            "N4b_completeness_gate",
            "N5_verify_green",
            "N6_e2e_validation",
            "N7_finalize",
        }, inbound

    def test_halt_still_ends_the_run(self):
        graph = build_testing_workflow().compile().get_graph()
        assert [e.target for e in graph.edges if e.source == "HALT"] == ["__end__"]

    def test_a_recorded_reason_routes_to_halt_and_a_clean_finish_does_not(self):
        """The distinction the whole change rests on. `error_message` is the
        walker's own definition of a halt site, so routing on it is what makes
        the set of stops that reach HALT the set of registered halts."""
        assert route_after_load({"error_message": "boom"}) == "HALT"
        assert route_after_load({}) == "N1_review_test_plan"

        assert route_after_implement({"error_message": "boom"}) == "HALT"
        assert route_after_implement({}) == "N4b_completeness_gate"

        # A scaffold-only run finished; it did not fail, and there is no
        # reason to record. It must NOT produce a halt bundle.
        assert route_after_scaffold({"scaffold_only": True}) == "end"
        assert route_after_scaffold({"error_message": "boom"}) == "HALT"

        assert route_after_green({"error_message": "boom"}) == "HALT"


class TestAHaltedRollLeavesABundle:
    """#2735's three things, for this graph."""

    @pytest.fixture
    def halted(self, state_dir, tmp_path, monkeypatch):
        """Roll the real compiled graph to a halt at N0.

        N0 is the cheapest true halt in the graph -- no model call, no repo,
        no test run -- and it exercises the same wiring every other halt now
        uses, because they all reach HALT the same way.
        """
        audit = tmp_path / "lineage"
        audit.mkdir()
        (audit / "001-spec-draft.md").write_text("# Spec\n", encoding="utf-8")

        app = build_testing_workflow().compile()
        result = app.invoke({
            "issue_number": 4242,
            # No spec_path and no lld_content: load_lld records a reason.
            "spec_path": str(tmp_path / "does-not-exist.md"),
            "worktree_path": str(tmp_path),
            "repo_root": str(tmp_path),
            "audit_dir": str(audit),
            "max_iterations": 1,
        })
        return result, audit

    def test_the_roll_actually_halted(self, halted):
        result, _ = halted
        assert result.get("error_message"), (
            "the fixture did not reach a halt, so nothing below is evidence"
        )

    def test_the_halt_node_ran(self, halted):
        """`recovery_plan_path` is returned by `create_halt_node` and by
        nothing else, so its presence is proof the node executed rather than
        the run ending at END the way it did before #2756."""
        result, _ = halted
        assert result.get("recovery_plan_path"), (
            "no recovery plan: the run ended without passing through HALT"
        )

    def test_a_bundle_landed_in_the_audit_dir(self, halted):
        _, audit = halted
        assert (audit / "halt-evidence.json").is_file()
        assert (audit / "halt-evidence.md").is_file()

    def test_the_bundle_carries_the_gate_key_outstanding_and_resume(self, halted):
        _, audit = halted
        evidence = json.loads(
            (audit / "halt-evidence.json").read_text(encoding="utf-8")
        )
        assert evidence.get("gate_key"), "no gate key: the bundle cannot be joined"
        assert "outstanding" in evidence
        assert evidence.get("resume_command"), "no way back in"

        rendered = (audit / "halt-evidence.md").read_text(encoding="utf-8")
        assert "Gate: `" in rendered
        assert "## Resume" in rendered

    def test_the_bundle_is_not_written_over_the_shared_state_dir(
        self, halted, state_dir
    ):
        """#2725's finding, which this change could have re-created by
        multiplying the number of halts that write one: the copy beside the
        snapshot goes in a directory named for the halt, not straight into the
        state dir, which is global across every repo the fleet has rolled."""
        _, _audit = halted
        loose = state_dir / "halt-evidence.json"
        assert not loose.exists(), (
            "the bundle was written straight into the shared state directory, "
            "where the next halt of any repo overwrites it"
        )
        assert _bundles(state_dir), "no bundle beside the state snapshot at all"
