"""The visual gate's pipeline seat (#2518): between lld and spec, resumable,
and invisible to every roll that declares no visual deliverable."""

from __future__ import annotations

import json
import sys
from pathlib import Path


from assemblyzero.workflows.orchestrator.stages import STAGE_RUNNERS, run_visual_stage
from assemblyzero.workflows.orchestrator.state import (
    STAGE_ORDER,
    _STAGE_ARTIFACT_KEY,
    create_initial_state,
    get_next_stage,
)

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import speedrun_roll  # noqa: E402


class TestTheSeat:
    def test_visual_sits_between_lld_and_spec(self):
        """The whole point: the eyeball artifact exists BEFORE the spec
        stage spends review rounds on how to test it."""
        assert STAGE_ORDER.index("visual") == STAGE_ORDER.index("lld") + 1
        assert STAGE_ORDER.index("spec") == STAGE_ORDER.index("visual") + 1

    def test_the_pipeline_routes_through_it(self):
        assert get_next_stage("lld") == "visual"
        assert get_next_stage("visual") == "spec"

    def test_it_has_a_runner_and_an_artifact_key(self):
        assert STAGE_RUNNERS["visual"] is run_visual_stage
        assert _STAGE_ARTIFACT_KEY["visual"] == "approved_render_path"

    def test_it_is_resumable(self):
        assert "visual" in speedrun_roll.RESUMABLE_STAGES

    def test_fresh_state_carries_the_artifact_field(self):
        state = create_initial_state(1, {})
        assert state["approved_render_path"] == ""


def _state(tmp_path, issue=331):
    state = create_initial_state(issue, {})
    state["target_repo"] = str(tmp_path)
    state["current_stage"] = "visual"
    return state


class TestNonVisualRollsAreUntouched:
    def test_a_repo_with_no_declaration_skips_in_milliseconds(self, tmp_path):
        new_state = run_visual_stage(_state(tmp_path))

        result = new_state["stage_results"]["visual"]
        assert result["status"] == "skipped"
        assert "declares no visual gate" in result["error_message"]

    def test_an_undeclared_issue_skips_too(self, tmp_path):
        cfg = tmp_path / "docs" / "design" / "visual-gate.json"
        cfg.parent.mkdir(parents=True)
        cfg.write_text(json.dumps({
            "issues": [999], "renderer_cmd": ["python", "x.py"],
            "contract": "docs/design/c.md", "separation_floor": 85,
        }), encoding="utf-8")

        new_state = run_visual_stage(_state(tmp_path, issue=331))

        result = new_state["stage_results"]["visual"]
        assert result["status"] == "skipped"
        assert "no visual deliverable declared" in result["error_message"]

    def test_a_skipped_gate_advances_the_pipeline(self, tmp_path):
        new_state = run_visual_stage(_state(tmp_path))
        assert new_state["current_stage"] == "spec"


class TestOptionalStageAbsenceIsNotAGap:
    """#2518 x #2422: state files written before `visual` joined STAGE_ORDER
    have no entry for it. That absence is history, not a gap that declines a
    killed-run resume -- while a RECORDED failure on it is still a stop."""

    def test_an_absent_visual_entry_does_not_decline_a_killed_resume(self):
        results = {
            "triage": {"status": "skipped"},
            "lld": {"status": "passed"},
            "spec": {"status": "passed"},
        }
        data = {"current_stage": "impl", "completed_at": ""}

        assert speedrun_roll._halted_stage(data, results) == "impl"

    def test_a_recorded_visual_failure_still_declines_it(self):
        results = {
            "triage": {"status": "skipped"},
            "lld": {"status": "passed"},
            "visual": {"status": "failed"},
            "spec": {"status": "passed"},
        }
        data = {"current_stage": "impl", "completed_at": ""}

        assert speedrun_roll._halted_stage(data, results) is None


class TestABrokenDeclarationNeverRollsUngated:
    def test_unreadable_json_fails_the_stage_loudly(self, tmp_path):
        cfg = tmp_path / "docs" / "design" / "visual-gate.json"
        cfg.parent.mkdir(parents=True)
        cfg.write_text("{not json", encoding="utf-8")

        new_state = run_visual_stage(_state(tmp_path))

        result = new_state["stage_results"]["visual"]
        assert result["status"] == "failed"
        assert result["transient"] is False
        assert "visual-gate declaration unreadable" in result["error_message"]


class TestAnApprovedGatePassesTheStage:
    def test_the_stamped_render_becomes_the_stage_artifact(self, tmp_path):
        """The cheapest full pass: an already-approved bundle (the resume
        shortcut) drives the stage runner end to end without a server."""
        cfg = tmp_path / "docs" / "design" / "visual-gate.json"
        cfg.parent.mkdir(parents=True)
        cfg.write_text(json.dumps({
            "issues": [331],
            "renderer_cmd": ["python", "tools/never_invoked.py"],
            "contract": "docs/design/c.md", "separation_floor": 85,
        }), encoding="utf-8")
        approved = tmp_path / "data" / "visual-gate" / "331" / "approved"
        approved.mkdir(parents=True)
        (approved / "approved.png").write_bytes(b"png")
        (approved / "approved.json").write_text("{}", encoding="utf-8")

        new_state = run_visual_stage(_state(tmp_path))

        result = new_state["stage_results"]["visual"]
        assert result["status"] == "passed"
        assert result["artifact_path"].endswith("approved.png")
        assert new_state["approved_render_path"].endswith("approved.png")
        assert new_state["current_stage"] == "spec"
