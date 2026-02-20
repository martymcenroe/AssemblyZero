"""Integration tests for orchestrator graph.

Issue #305: End-to-End Orchestration Workflow (Issue → Code)
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from assemblyzero.workflows.orchestrator.config import get_default_config
from assemblyzero.workflows.orchestrator.graph import (
    ConcurrentOrchestrationError,
    OrchestrationResult,
    orchestrate,
)
from assemblyzero.workflows.orchestrator.resume import (
    LOCK_DIR,
    STATE_DIR,
    load_orchestration_state,
    save_orchestration_state,
)
from assemblyzero.workflows.orchestrator.state import (
    OrchestrationState,
    StageResult,
    create_initial_state,
)


@pytest.fixture
def clean_orchestrator_dirs(tmp_path, monkeypatch):
    """Ensure clean orchestrator state/lock directories."""
    state_dir = tmp_path / ".assemblyzero" / "orchestrator" / "state"
    lock_dir = tmp_path / ".assemblyzero" / "orchestrator" / "locks"
    state_dir.mkdir(parents=True, exist_ok=True)
    lock_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("assemblyzero.workflows.orchestrator.resume.STATE_DIR", state_dir)
    monkeypatch.setattr("assemblyzero.workflows.orchestrator.resume.LOCK_DIR", lock_dir)
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def mock_all_stages():
    """Mock all stage runners to succeed."""
    def make_mock_runner(stage_name, artifact_suffix="artifact.md"):
        def mock_runner(state):
            from assemblyzero.workflows.orchestrator.state import update_stage_result, StageResult
            result = StageResult(
                status="passed",
                artifact_path=f"mock/{stage_name}/{artifact_suffix}",
                error_message="",
                duration_seconds=1.0,
                attempts=1,
            )
            return update_stage_result(state, stage_name, result)
        return mock_runner

    runners = {
        "triage": make_mock_runner("triage", "issue-brief.md"),
        "lld": make_mock_runner("lld", "305-lld.md"),
        "spec": make_mock_runner("spec", "impl-spec.md"),
        "impl": make_mock_runner("impl", "../AssemblyZero-305"),
        "pr": make_mock_runner("pr", "https://github.com/test/pull/1"),
    }

    with patch("assemblyzero.workflows.orchestrator.graph.STAGE_RUNNERS", runners), \
         patch("assemblyzero.workflows.orchestrator.stages.STAGE_RUNNERS", runners):
        yield runners


class TestOrchestrateFullPipeline:
    """Tests for orchestrate() function (T010)."""

    def test_full_pipeline_success(self, clean_orchestrator_dirs, mock_all_stages):
        """T010: Single command processes issue to PR."""
        config = {"gates": {"pr": False}}  # Disable gate for test
        result = orchestrate(issue_number=999, config=config)

        assert result["success"] is True
        assert result["issue_number"] == 999
        assert result["final_stage"] == "done"
        assert result["pr_url"] == "mock/pr/https://github.com/test/pull/1"
        assert "triage" in result["stage_results"]
        assert "pr" in result["stage_results"]

    def test_dry_run_no_execution(self, clean_orchestrator_dirs):
        """T050: Dry-run shows plan without executing."""
        result = orchestrate(issue_number=999, dry_run=True)

        assert result["success"] is True
        # No actual stages should have "passed" status from execution
        # Only "skipped" or empty results from pre-detection

    def test_concurrent_run_prevented(self, clean_orchestrator_dirs, mock_all_stages):
        """T090: Lock file blocks concurrent runs."""
        import os

        # Manually create lock with current PID
        lock_dir = clean_orchestrator_dirs / ".assemblyzero" / "orchestrator" / "locks"
        lock_file = lock_dir / "999.lock"
        lock_file.write_text(json.dumps({
            "pid": os.getpid(),
            "started_at": "2026-02-16T10:00:00Z",
            "hostname": "test",
        }))

        with pytest.raises(ConcurrentOrchestrationError, match="already being orchestrated"):
            orchestrate(issue_number=999)


class TestStatePersistence:
    """Tests for state persistence (T030)."""

    def test_state_persists_to_json(self, clean_orchestrator_dirs):
        """T030: State persists to JSON file for resume."""
        config = get_default_config()
        state = create_initial_state(305, config)
        path = save_orchestration_state(state)

        assert path.exists()
        loaded = load_orchestration_state(305)
        assert loaded is not None
        assert loaded["issue_number"] == 305
        assert loaded["current_stage"] == "triage"

    def test_state_backup_on_overwrite(self, clean_orchestrator_dirs):
        config = get_default_config()
        state = create_initial_state(305, config)

        path1 = save_orchestration_state(state)
        # Modify and save again
        state_dict = dict(state)
        state_dict["current_stage"] = "lld"
        path2 = save_orchestration_state(OrchestrationState(**state_dict))

        assert path2.exists()
        backup = path2.with_suffix(".json.bak")
        assert backup.exists()


class TestResumeFromStage:
    """Tests for resume functionality (T080)."""

    def test_resume_from_specific_stage(self, clean_orchestrator_dirs, mock_all_stages):
        """T080: Resume-from flag skips to specific stage."""
        config = get_default_config()
        config["gates"]["pr"] = False

        # Create state as if triage and lld already completed
        state = create_initial_state(305, config)
        state_dict = dict(state)
        state_dict["current_stage"] = "spec"
        state_dict["stage_results"] = {
            "triage": {"status": "passed", "artifact_path": "mock/triage.md", "error_message": "", "duration_seconds": 1.0, "attempts": 1},
            "lld": {"status": "passed", "artifact_path": "mock/lld.md", "error_message": "", "duration_seconds": 1.0, "attempts": 1},
        }
        save_orchestration_state(OrchestrationState(**state_dict))

        result = orchestrate(
            issue_number=305,
            config={"gates": {"pr": False}},
            resume_from="spec",
        )

        assert result["success"] is True
        # triage and lld should be from persisted state
        assert result["stage_results"]["triage"]["status"] == "passed"
        assert result["stage_results"]["lld"]["status"] == "passed"

    def test_resume_without_state_raises(self, clean_orchestrator_dirs):
        with pytest.raises(ValueError, match="No persisted state found"):
            orchestrate(issue_number=888, resume_from="spec")


class TestProgressAndErrors:
    """Tests for progress reporting and error messages (T060, T070)."""

    def test_actionable_error_on_failure(self, clean_orchestrator_dirs):
        """T070: Failed stages report actionable errors."""
        def failing_runner(state):
            from assemblyzero.workflows.orchestrator.state import update_stage_result, StageResult
            result = StageResult(
                status="failed",
                artifact_path="",
                error_message="API rate limit exceeded",
                duration_seconds=5.0,
                attempts=1,
            )
            return update_stage_result(state, "triage", result)

        runners = {
            "triage": failing_runner,
            "lld": MagicMock(),
            "spec": MagicMock(),
            "impl": MagicMock(),
            "pr": MagicMock(),
        }

        with patch("assemblyzero.workflows.orchestrator.graph.STAGE_RUNNERS", runners):
            result = orchestrate(issue_number=999, config={"max_stage_retries": 1})

        assert result["success"] is False
        assert "triage" in result["error_summary"]
        assert "Resume with" in result["error_summary"]

    def test_progress_reporting_function(self, capsys):
        """T060: Progress reporting shows stage info."""
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
        from tools.orchestrate import report_progress

        state = OrchestrationState(
            issue_number=305,
            current_stage="spec",
            issue_brief_path="docs/lineage/305/issue-brief.md",
            lld_path="docs/lld/active/305-lld.md",
            spec_path="",
            worktree_path="",
            pr_url="",
            stage_results={
                "triage": StageResult(status="passed", artifact_path="docs/lineage/305/issue-brief.md", error_message="", duration_seconds=85.3, attempts=1),
                "lld": StageResult(status="skipped", artifact_path="docs/lld/active/305-lld.md", error_message="", duration_seconds=0.01, attempts=0),
            },
            stage_attempts={},
            started_at="2026-02-16T10:30:00+00:00",
            stage_started_at="",
            completed_at="",
            config=get_default_config(),
            error_message="",
        )

        report_progress(state)
        captured = capsys.readouterr()
        assert "Issue #305" in captured.out
        assert "spec" in captured.out
        assert "[PASS] triage" in captured.out
