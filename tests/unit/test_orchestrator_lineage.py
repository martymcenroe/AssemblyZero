"""Every orchestrated sub-workflow must leave its lineage on disk.

Closes #2250. The implementation-spec workflow persists drafts and verdicts only
when its caller hands it an ``audit_dir``: ``generate_spec``, ``review_spec`` and
``finalize_spec`` each guard on ``state.get("audit_dir", "")`` and skip the write
when it is empty. ``tools/run_implementation_spec_workflow.py`` sets it;
``run_spec_stage`` did not. So every orchestrated spec run -- which is every
speedrun roll -- existed only in memory and was gone when the stage ended.

The cost is measured, not hypothetical: ``run-issue7-082047`` (boostgauge,
2026-08-12) spent three revision iterations in the spec stage and died at the
cap, and not one of its four drafts survives. Fleet-wide, exactly one spec
markdown exists anywhere under ``Projects/``, and only because a human copied it
into a scratch directory during an unrelated investigation.

The two sibling sub-workflows never had the gap because they provision their own
lineage internally -- requirements in ``nodes/load_input.py``, testing in
``nodes/load_lld.py``. implementation_spec is the only one that delegates the
decision to its caller, which is why it is the only one that lost everything.

``TestEveryOrchestratedSubWorkflowPersistsLineage`` is the audit #2250 asks to be
a test rather than a one-time read: it walks the ``app.invoke`` payloads in
stages.py and requires each sub-workflow to be covered by one mechanism or the
other. A fourth stage added tomorrow with neither fails it.
"""

import ast
import re
from pathlib import Path

import pytest

from assemblyzero.workflows.orchestrator import stages
from assemblyzero.workflows.orchestrator.config import get_default_config
from assemblyzero.workflows.orchestrator.stages import run_spec_stage
from assemblyzero.workflows.orchestrator.state import create_initial_state

STAGES_PY = Path(stages.__file__)
WORKFLOWS_ROOT = STAGES_PY.parent.parent

# Which sub-workflow package each orchestrator stage drives. Stages absent from
# this map invoke no sub-graph: `triage` writes its own brief directly since
# #1770, and `pr` / `cleanup` are shell work.
STAGE_TO_SUBWORKFLOW = {
    "run_lld_stage": "requirements",
    "run_spec_stage": "implementation_spec",
    "run_impl_stage": "testing",
}

# A node that calls create_audit_dir / create_testing_audit_dir provisions its
# own lineage and needs nothing from the orchestrator. The `def` filter keeps
# the *definition* in requirements/audit.py from counting as a call site.
_PROVISION_CALL = re.compile(r"(?<!def )\bcreate_\w*audit_dir\s*\(")


def _invoke_payload_keys_by_stage(source: Path) -> dict[str, set[str]]:
    """Map each `run_*_stage` function to the literal keys of the dict it
    passes to `app.invoke({...})`."""
    tree = ast.parse(source.read_text(encoding="utf-8"))
    found: dict[str, set[str]] = {}

    for func in ast.walk(tree):
        if not isinstance(func, ast.FunctionDef):
            continue
        for node in ast.walk(func):
            if not isinstance(node, ast.Call):
                continue
            callee = node.func
            if not (isinstance(callee, ast.Attribute) and callee.attr == "invoke"):
                continue
            if not (isinstance(callee.value, ast.Name) and callee.value.id == "app"):
                continue
            if not (node.args and isinstance(node.args[0], ast.Dict)):
                continue
            found.setdefault(func.name, set()).update(
                k.value
                for k in node.args[0].keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)
            )
    return found


def _self_provisions_lineage(subworkflow: str) -> bool:
    """True when the sub-workflow creates its own audit dir in one of its nodes."""
    package = WORKFLOWS_ROOT / subworkflow
    return any(
        _PROVISION_CALL.search(py.read_text(encoding="utf-8"))
        for py in package.rglob("*.py")
    )


class TestSpecStageHandsDownAnAuditDir:
    """The specific regression: the payload had no `audit_dir`, so every write
    downstream was a no-op and the run left nothing behind."""

    def test_payload_carries_a_real_audit_dir(self, tmp_path):
        target = tmp_path / "target"
        target.mkdir()

        captured: dict[str, dict] = {}

        class _StubApp:
            def invoke(self, payload: dict) -> dict:
                captured["payload"] = payload
                return {"spec_path": "", "error_message": "stub"}

        state = create_initial_state(
            7,
            get_default_config(),
            target_repo=str(target),
            assemblyzero_root=str(tmp_path / "az"),
        )

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "assemblyzero.workflows.implementation_spec.graph."
                "create_implementation_spec_graph",
                lambda: _StubApp(),
            )
            run_spec_stage(state)

        payload = captured.get("payload", {})
        audit_dir = payload.get("audit_dir", "")

        assert audit_dir, (
            "run_spec_stage passed no audit_dir. generate_spec, review_spec and "
            "finalize_spec all guard on it being non-empty, so the whole spec "
            "run leaves nothing on disk -- the #2250 defect exactly."
        )
        assert Path(audit_dir).is_dir(), (
            f"audit_dir {audit_dir!r} must exist before the graph runs: "
            "generate_spec and finalize_spec both additionally guard on "
            "audit_dir.exists() and skip the write when it does not."
        )

    def test_audit_dir_is_under_the_target_repo_lineage_tree(self, tmp_path):
        """Lineage belongs beside the LLD's, in the target repo -- that is where
        the archiver, the metrics collector and a human all look for it."""
        target = tmp_path / "target"
        target.mkdir()

        captured: dict[str, dict] = {}

        class _StubApp:
            def invoke(self, payload: dict) -> dict:
                captured["payload"] = payload
                return {"spec_path": "", "error_message": "stub"}

        state = create_initial_state(
            7,
            get_default_config(),
            target_repo=str(target),
            assemblyzero_root=str(tmp_path / "az"),
        )

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "assemblyzero.workflows.implementation_spec.graph."
                "create_implementation_spec_graph",
                lambda: _StubApp(),
            )
            run_spec_stage(state)

        audit_dir = Path(captured["payload"]["audit_dir"])
        active = target / "docs" / "lineage" / "active"

        assert active in audit_dir.parents, (
            f"{audit_dir} must live under {active}, where move_lineage_to_done "
            "and detect_existing_artifacts expect it"
        )
        assert "7-implspec" in audit_dir.parts, (
            "the dir must be keyed to the issue and the workflow, matching the "
            f"standalone runner's {{issue}}-implspec; got {audit_dir.parts}"
        )

    def test_two_runs_of_one_issue_do_not_share_a_directory(self, tmp_path):
        """Run-scoped for the reason #1467 scoped the LLD's: generate_spec
        recovers a draft by globbing *-spec-draft.md out of this directory and
        skips the LLM call when it hits. An unscoped dir would let a previous
        roll's draft be recovered into a fresh run."""
        target = tmp_path / "target"
        target.mkdir()

        seen: list[str] = []

        class _StubApp:
            def invoke(self, payload: dict) -> dict:
                seen.append(payload.get("audit_dir", ""))
                return {"spec_path": "", "error_message": "stub"}

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "assemblyzero.workflows.implementation_spec.graph."
                "create_implementation_spec_graph",
                lambda: _StubApp(),
            )
            for _ in range(2):
                run_spec_stage(
                    create_initial_state(
                        7,
                        get_default_config(),
                        target_repo=str(target),
                        assemblyzero_root=str(tmp_path / "az"),
                    )
                )

        assert len(seen) == 2 and all(seen)
        assert seen[0] != seen[1], (
            "two runs of issue 7 were handed the same lineage dir; the second "
            "would recover the first's draft and skip its own drafting"
        )


class TestDraftsSurviveAFailedStage:
    """#2250's second criterion. The drafts matter most exactly when the stage
    dies -- that is the run someone needs to reproduce."""

    def test_iteration_cap_death_leaves_every_draft_on_disk(self, tmp_path):
        target = tmp_path / "target"
        target.mkdir()

        class _StubApp:
            """Stands in for a spec graph that drafts three times, is told to
            revise each time, and dies at the cap without a final spec."""

            def invoke(self, payload: dict) -> dict:
                audit = Path(payload["audit_dir"])
                for i in (1, 2, 3):
                    (audit / f"{i:03d}-spec-draft.md").write_text(
                        f"# draft {i}", encoding="utf-8"
                    )
                    (audit / f"{i:03d}-readiness-verdict.md").write_text(
                        "REVISE", encoding="utf-8"
                    )
                return {
                    "spec_path": "",
                    "error_message": "Spec review did not converge after 3 iterations",
                }

        state = create_initial_state(
            7,
            get_default_config(),
            target_repo=str(target),
            assemblyzero_root=str(tmp_path / "az"),
        )

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "assemblyzero.workflows.implementation_spec.graph."
                "create_implementation_spec_graph",
                lambda: _StubApp(),
            )
            result = run_spec_stage(state)

        assert result["stage_results"]["spec"]["status"] == "failed"

        drafts = sorted((target / "docs" / "lineage").rglob("*-spec-draft.md"))
        verdicts = sorted((target / "docs" / "lineage").rglob("*-readiness-verdict.md"))

        assert len(drafts) == 3, (
            f"a stage that died at the cap left {len(drafts)} drafts, not 3. "
            "The failing run is the one worth keeping -- run-issue7-082047 "
            "burned three iterations and left nothing to diagnose."
        )
        assert len(verdicts) == 3


class TestEveryOrchestratedSubWorkflowPersistsLineage:
    """The audit, as a test rather than a one-time read (#2250 criterion 3).

    A sub-workflow is covered when the orchestrator hands it an `audit_dir` or
    when it provisions one itself. Neither means its run vanishes.
    """

    @pytest.mark.parametrize(
        ("stage_fn", "subworkflow"), sorted(STAGE_TO_SUBWORKFLOW.items())
    )
    def test_sub_workflow_lineage_is_provisioned(self, stage_fn, subworkflow):
        payloads = _invoke_payload_keys_by_stage(STAGES_PY)

        assert stage_fn in payloads, (
            f"{stage_fn} no longer invokes a sub-graph via `app.invoke`. If it "
            "was rewired, update STAGE_TO_SUBWORKFLOW -- do not delete the case, "
            "or the stage stops being audited."
        )

        passed_in = "audit_dir" in payloads[stage_fn]
        self_provisions = _self_provisions_lineage(subworkflow)

        assert passed_in or self_provisions, (
            f"{stage_fn} drives the {subworkflow} workflow, which neither "
            f"receives an audit_dir from the orchestrator nor creates one in "
            f"its own nodes. Every draft and verdict it produces will be "
            f"discarded when the stage ends -- silently, the way #2250 arrived."
        )

    def test_every_invoking_stage_is_accounted_for(self):
        """A new stage that invokes a sub-graph must be added to the map, so it
        cannot slip past the audit above just by being unlisted."""
        invoking = set(_invoke_payload_keys_by_stage(STAGES_PY))
        unmapped = invoking - set(STAGE_TO_SUBWORKFLOW)

        assert not unmapped, (
            f"stages.py invokes sub-graphs from {sorted(unmapped)}, which "
            "STAGE_TO_SUBWORKFLOW does not cover, so their lineage is unaudited."
        )


class TestTheAuditActuallyInspectsSomething:
    """A guard that parsed nothing, or matched everything, would pass forever."""

    def test_the_ast_scan_finds_the_real_payloads(self):
        payloads = _invoke_payload_keys_by_stage(STAGES_PY)
        assert set(payloads) == set(STAGE_TO_SUBWORKFLOW), (
            f"expected exactly the three invoking stages, found {sorted(payloads)}"
        )
        # Sentinel keys that have been in these payloads for many issues.
        assert "issue_number" in payloads["run_spec_stage"]
        assert "workflow_type" in payloads["run_lld_stage"]
        assert "spec_path" in payloads["run_impl_stage"]

    def test_the_spec_workflow_is_still_the_one_that_cannot_self_provision(self):
        """Pins the asymmetry the fix rests on. If implementation_spec ever
        grows its own create_audit_dir call, the orchestrator's hand-down stops
        being load-bearing and this file's reasoning needs revisiting."""
        assert _self_provisions_lineage("requirements")
        assert _self_provisions_lineage("testing")
        assert not _self_provisions_lineage("implementation_spec"), (
            "implementation_spec now provisions its own lineage. That is a fine "
            "thing to do, but TestSpecStageHandsDownAnAuditDir above is written "
            "on the premise that it does not -- reconcile the two."
        )

    def test_the_provision_regex_does_not_count_the_definition(self):
        """requirements/audit.py *defines* create_audit_dir. If the pattern
        counted definitions, every package vendoring that module would look
        self-provisioning and the audit would wave everything through."""
        assert not _PROVISION_CALL.search("def create_audit_dir(target_repo):")
        assert _PROVISION_CALL.search("    audit_dir = create_audit_dir(")
        assert _PROVISION_CALL.search("audit_dir = create_testing_audit_dir(7, root)")
