"""A halted workflow is never a passed stage, and a halt says why (#2297, #2299).

The 2026-08-13 boostgauge #7 roll recorded `spec passed 287.5s` against a HALT
block from the same run, then ran impl against a spec that was never finalized
and died there with the true failure five screens up.

The cause was not the hypothesized empty `error_message`. `run_spec_stage`
accepted the stage when `spec_path` named an existing file, and `generate_spec`
wrote every DRAFT's audit path into `spec_path`. Before #2250 orchestrated runs
had no `audit_dir`, so that value was "" and a cap-halt correctly failed; the
lineage repair made the draft a real file and turned the correct failure into a
false success.

Two paths leave `error_message` empty on purpose and must never read alike:
a finalize repair in flight (#2233) and a successful finalize. Neither is a
halt, and `workflow_status` is what separates all three.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from assemblyzero.core.recovery_plan import RecoveryPlan
from assemblyzero.workflows.orchestrator import stages as stages_mod


# ---------------------------------------------------------------------------
# #2299 — the halt block's Error field
# ---------------------------------------------------------------------------


def _plan(**over) -> RecoveryPlan:
    base = dict(
        issue_number=7,
        workflow="implementation_spec",
        stage="N5_review_iter3",
        error_type="unknown",
        error_message=(
            "Iteration cap: 3 revision(s) ended with 1 unresolved completeness "
            "check(s). Unfixed: Functions missing input/output examples: "
            "`test_req_10()`, `test_req_11()`"
        ),
        is_transient=False,
        state_path="/tmp/state.json",
        cost_spent_usd=0.0,
        cost_budget_usd=0.0,
        halted_at="2026-08-13T16:07:00Z",
        resume_command="orchestrate --issue 7 --resume-from spec",
        earliest_retry="",
        recommendation="Fix the unresolved checks and re-run.",
    )
    base.update(over)
    return RecoveryPlan(**base)


class TestTheHaltBlockPrintsTheReason:
    def test_the_error_field_carries_the_real_reason(self, capsys):
        _plan().print_summary()
        out = capsys.readouterr().out

        assert "Error:     Iteration cap: 3 revision(s)" in out, (
            "the Error field must print the reason, not the classifier's bucket"
        )

    def test_the_classification_is_still_shown_but_not_as_the_error(self, capsys):
        _plan().print_summary()
        out = capsys.readouterr().out

        assert "Class:     unknown" in out
        # The exact string #2299 was filed about must not reappear.
        assert "Error:     unknown" not in out

    def test_a_genuinely_absent_reason_says_so_in_words(self, capsys):
        _plan(error_message="").print_summary()
        out = capsys.readouterr().out

        assert "no reason recorded" in out
        assert "Error:     unknown" not in out

    def test_a_long_reason_is_bounded_so_the_block_stays_a_block(self, capsys):
        _plan(error_message="x" * 5000).print_summary()
        line = next(
            ln for ln in capsys.readouterr().out.splitlines()
            if ln.startswith("  Error:")
        )

        assert len(line) < RecoveryPlan.ERROR_LINE_LIMIT + 60
        assert line.endswith("...")

    def test_only_the_first_line_is_used(self, capsys):
        _plan(error_message="the real reason\nstack frame 1\nstack frame 2").print_summary()
        out = capsys.readouterr().out

        assert "Error:     the real reason" in out
        assert "stack frame 1" not in out.split("Class:")[0]


# ---------------------------------------------------------------------------
# #2297 — the stage verdict
# ---------------------------------------------------------------------------


class _FakeApp:
    def __init__(self, result):
        self._result = result

    def invoke(self, state):
        return self._result


def _run_spec_stage(tmp_path, sub_result):
    repo = tmp_path / "repo"
    (repo / "docs" / "lld" / "active").mkdir(parents=True, exist_ok=True)
    lld = repo / "docs" / "lld" / "active" / "LLD-007.md"
    lld.write_text("# LLD\n", encoding="utf-8")

    state = {
        "issue_number": 7,
        "lld_path": str(lld),
        "target_repo": str(repo),
        "assemblyzero_root": str(Path(__file__).resolve().parents[2]),
        "base_branch": "hardening-run-17",
        "config": {"stages": {"spec": {}}, "gates": {}, "skip_existing_spec": False},
        "stage_results": {},
    }

    import assemblyzero.workflows.implementation_spec.graph as specgraph

    with patch.object(
        specgraph, "create_implementation_spec_graph", lambda: _FakeApp(sub_result)
    ), patch.object(stages_mod, "_ride_spec_on_lld_pr", lambda **k: None), \
            patch.object(stages_mod, "_record_spec_convergence_failure", lambda *a, **k: None):
        out = stages_mod.run_spec_stage(state)
    return out["stage_results"]["spec"]


class TestAHaltedWorkflowIsNeverAPassedStage:
    def test_the_roll_ending_case(self, tmp_path):
        """The exact shape of the 2026-08-13 roll: a halt that still left a
        real draft file behind in the audit trail."""
        draft = tmp_path / "008-spec-draft.md"
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text("# draft\n", encoding="utf-8")

        result = _run_spec_stage(tmp_path, {
            "workflow_status": "halted",
            "spec_path": str(draft),          # a real file, as after #2250
            "error_message": "Iteration cap: 3 revision(s) ended with 1 unresolved check",
        })

        assert result["status"] == "failed", (
            "a halted workflow was recorded as a passed stage -- the defect "
            "that sent the roll on to impl"
        )
        assert "Iteration cap" in result["error_message"]

    def test_a_halt_with_no_artifact_also_fails(self, tmp_path):
        result = _run_spec_stage(tmp_path, {
            "workflow_status": "halted", "spec_path": "", "error_message": "",
        })

        assert result["status"] == "failed"
        assert "halted before finalizing" in result["error_message"]

    def test_a_completed_workflow_with_its_artifact_passes(self, tmp_path):
        spec = tmp_path / "spec-0007.md"
        spec.write_text("# spec\n", encoding="utf-8")

        result = _run_spec_stage(tmp_path, {
            "workflow_status": "completed",
            "spec_path": str(spec),
            "error_message": "",
        })

        assert result["status"] == "passed"
        assert result["artifact_path"] == str(spec)

    def test_the_2233_empty_error_success_path_still_passes(self, tmp_path):
        """#2233 leaves error_message empty ON PURPOSE on the repaired-finalize
        path. That emptiness must keep meaning success, while the halt path's
        emptiness means failure -- the two can no longer read alike because the
        verdict is `workflow_status`, not the message."""
        spec = tmp_path / "spec-0007.md"
        spec.write_text("# spec\n", encoding="utf-8")

        repaired = _run_spec_stage(tmp_path, {
            "workflow_status": "completed", "spec_path": str(spec), "error_message": "",
        })
        halted = _run_spec_stage(tmp_path, {
            "workflow_status": "halted", "spec_path": str(spec), "error_message": "",
        })

        assert repaired["status"] == "passed"
        assert halted["status"] == "failed"

    def test_a_draft_path_alone_cannot_pass_the_stage(self, tmp_path):
        """generate_spec no longer writes a draft into spec_path, but the stage
        must not depend on that: an unfinalized run reports no spec_path at all."""
        result = _run_spec_stage(tmp_path, {
            "workflow_status": "",
            "spec_draft_path": str(tmp_path / "008-spec-draft.md"),
            "spec_path": "",
        })

        assert result["status"] == "failed"


class TestTheResumeHintNamesTheFailedStage:
    """The hint inherited the lie: with spec recorded as passed, the roll died
    at impl and told the operator to resume from impl -- straight back into the
    same missing-spec wall. It is derived from the failed stage, so fixing the
    verdict fixes the hint; this pins that it stays derived."""

    def test_the_hint_names_spec_when_spec_failed(self):
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
        from orchestrate import format_error_message

        rendered = format_error_message("spec", {
            "status": "failed",
            "error_message": "Iteration cap: 3 revision(s) ended with 1 unresolved check",
            "attempts": 1,
            "duration_seconds": 287.5,
        })

        assert "--resume-from spec" in rendered
        assert "--resume-from impl" not in rendered
        assert "ORCHESTRATION FAILED at stage: spec" in rendered


class TestGenerateSpecKeepsTheFieldsApart:
    def test_the_draft_goes_to_the_draft_field(self, tmp_path):
        """The regression in one assertion: a draft written to `spec_path` is
        what let an existing file stand in for a finalized spec."""
        # The package re-exports the FUNCTION under the module's name, so the
        # module has to be imported explicitly.
        import importlib

        gs = importlib.import_module(
            "assemblyzero.workflows.implementation_spec.nodes.generate_spec"
        )

        audit = tmp_path / "audit"
        audit.mkdir()
        (audit / "001-spec-draft.md").write_text("# recovered draft\n" * 5, encoding="utf-8")

        out = gs.generate_spec({
            "audit_dir": str(audit),
            "spec_draft": "",
            "review_iteration": 0,
            "lld_content": "# LLD\n",
            "repo_root": str(tmp_path),
            "assemblyzero_root": str(Path(__file__).resolve().parents[2]),
        })

        assert out.get("spec_draft_path", "").endswith("001-spec-draft.md")
        assert not out.get("spec_path"), (
            "generate_spec must never set spec_path -- state.py reserves it for "
            "the finalized spec, and finalize_spec is its only writer"
        )
