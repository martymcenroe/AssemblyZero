"""Completion must be as explicit as failure (#2677).

`run-issue384-044442`: the testing workflow stopped at N2.5 on an exhausted
scaffolder, set no `error_message`, and the orchestrator recorded `impl passed
3.5s`. The red phase, the implementation loop, the green phase and the
full-suite regression check had none of them run, and a PR carrying an
assertion-free stub and no code was opened and merged from that verdict.

The stage's rule had been `not error_message` -> passed, patched twice with one
more negative check each time (#1779's BLOCK verdict, #2344's unresolved
failures). Enumerating the ways a workflow can end badly cannot terminate: any
new route to END that forgets to set an error re-creates the class. #2297
settled the negative direction for the spec stage -- `halted` is authoritative
-- and this is the same reading positively: the workflow says it finished, in
one place, and the stage requires the claim.

These tests own the WORKFLOW half. The stage half lives in
`test_orchestrator_stages.py::TestCompletionMustBeAsExplicitAsFailure`.
"""

from __future__ import annotations

import re
from pathlib import Path

from assemblyzero.workflows.testing.state import TestingWorkflowState

TESTING_PKG = (
    Path(__file__).resolve().parents[2]
    / "assemblyzero" / "workflows" / "testing"
)


class TestTheMarkerSurvivesTheGraphMerge:
    """#2679's lesson: a key a node returns but the schema does not declare is
    dropped by the merge, so the orchestrator would never see it."""

    def test_workflow_status_is_declared_in_the_state_schema(self) -> None:
        assert "workflow_status" in TestingWorkflowState.__annotations__

    def test_it_is_declared_as_a_string(self) -> None:
        assert TestingWorkflowState.__annotations__["workflow_status"] is str


class TestFinalizeIsTheOnlyPlaceItIsSet:
    """"Set in exactly one place" as a program, not a comment (rule 6).

    The guarantee the orchestrator leans on is not that finalize sets the
    marker -- it is that NOTHING ELSE does. A second writer anywhere in the
    testing package would restore the false-success hole silently, and no
    behavioural test would notice, because every such test would still pass.
    """

    def _writers(self) -> dict[str, list[str]]:
        pattern = re.compile(r"""["']workflow_status["']\s*:""")
        found: dict[str, list[str]] = {}
        for path in TESTING_PKG.rglob("*.py"):
            hits = [
                line.strip()
                for line in path.read_text(encoding="utf-8").splitlines()
                if pattern.search(line)
            ]
            if hits:
                found[path.name] = hits
        return found

    def test_only_finalize_assigns_it(self) -> None:
        writers = self._writers()

        assert set(writers) == {"finalize.py"}, (
            f"workflow_status is assigned in {sorted(writers)}; the "
            f"orchestrator's guarantee is that only N7 finalize sets it"
        )

    def test_it_is_assigned_exactly_once(self) -> None:
        assert len(self._writers()["finalize.py"]) == 1

    def test_the_scanner_can_actually_find_an_assignment(self) -> None:
        """Guards the two tests above from passing vacuously.

        A regex that matched nothing would make both assertions above trivially
        satisfiable by deleting the marker entirely.
        """
        assert self._writers(), "the scan found no assignment anywhere"


class TestFinalizeSetsIt:
    def test_the_return_carries_completed(self) -> None:
        """Read from the node's own return, at the line that emits it."""
        source = (TESTING_PKG / "nodes" / "finalize.py").read_text(
            encoding="utf-8"
        )

        assert '"workflow_status": "completed",' in source

    def test_the_marker_sits_inside_finalize(self) -> None:
        """Not in a helper that some other route could reach."""
        source = (TESTING_PKG / "nodes" / "finalize.py").read_text(
            encoding="utf-8"
        )
        marker_at = source.index('"workflow_status": "completed"')
        defs_before = [
            m.group(1)
            for m in re.finditer(r"^def (\w+)", source[:marker_at], re.M)
        ]

        assert defs_before[-1] == "finalize", defs_before[-1]


class TestEveryOtherTerminalLeavesItUnset:
    """The complement of the guarantee, read off the graph's own wiring.

    Every route to END other than through N7 is a failure, a halt, or
    `scaffold_only` -- which the orchestrator's impl stage never sets. This
    asserts the routers that can reach END are the ones we believe they are,
    so a new terminal added later shows up here rather than as another
    `passed 3.5s`.
    """

    def test_finalize_is_the_only_node_that_reports_completion(self) -> None:
        graph_source = (TESTING_PKG / "graph.py").read_text(encoding="utf-8")

        assert '"N7_finalize"' in graph_source
        assert "workflow_status" not in graph_source, (
            "routing must not set the completion marker; only N7 does"
        )

    def test_scaffold_only_is_never_set_by_the_impl_stage(self) -> None:
        """The one non-failure route to END that bypasses N7."""
        stages = (
            Path(__file__).resolve().parents[2]
            / "assemblyzero" / "workflows" / "orchestrator" / "stages.py"
        ).read_text(encoding="utf-8")

        assert '"scaffold_only"' not in stages


class TestARealRunStillPasses:
    """The safety half, and the one that matters most.

    A gate that refuses the observed failure is worthless if it also refuses
    every good run. This drives the actual graph end to end in mock mode --
    every node, every router, the real merge -- and asserts the marker is
    present in the state the orchestrator receives.

    `app.invoke` rather than `app.stream`: the stream yields one node's output
    at a time, so the neighbouring test that keeps the last event sees N9's
    return and could never observe a field N7 set. The merged state is what
    `run_impl_stage` actually reads.
    """

    def _mock_run(self, tmp_path: Path) -> dict:
        from assemblyzero.workflows.testing.graph import build_testing_workflow

        lld_dir = tmp_path / "docs" / "lld" / "active"
        lld_dir.mkdir(parents=True)
        (lld_dir / "LLD-042.md").write_text(
            "# LLD-042: Mock Feature\n\n"
            "## 1. Context\n* **Status:** Approved (Gemini Review, 2026-01-30)\n\n"
            "## 3. Requirements\n1. REQ-1: User login\n"
            "2. REQ-2: Input validation\n\n"
            "## 10. Test Plan\n\n### test_login\nVerify login works.\n"
            "Requirement: REQ-1\n\n**Final Status:** APPROVED\n"
        )
        (tmp_path / "tests").mkdir()
        (tmp_path / "docs" / "lineage" / "active").mkdir(parents=True)

        app = build_testing_workflow().compile()
        return app.invoke(
            {
                "issue_number": 42,
                "repo_root": str(tmp_path),
                "mock_mode": True,
                "skip_e2e": True,
                "auto_mode": True,
            },
            {"recursion_limit": 50},
        )

    def test_the_marker_reaches_the_orchestrator(self, tmp_path) -> None:
        final_state = self._mock_run(tmp_path)

        assert final_state.get("workflow_status") == "completed", (
            f"a completed run must carry the marker; got "
            f"{final_state.get('workflow_status')!r}"
        )

    def test_the_stage_would_record_it_as_passed(self, tmp_path) -> None:
        """The two halves joined: this state passes the stage's own rule."""
        final_state = self._mock_run(tmp_path)

        assert final_state.get("error_message", "") == ""
        assert final_state.get("workflow_status") == "completed"
