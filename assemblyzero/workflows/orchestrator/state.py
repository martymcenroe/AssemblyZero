"""Orchestration state management.

Issue #305: End-to-End Orchestration Workflow (Issue → Code)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TypedDict

from assemblyzero.workflows.orchestrator.config import OrchestratorConfig


class StageResult(TypedDict, total=False):
    """Result of executing a single stage."""

    status: str  # "passed", "blocked", "failed", "skipped"
    artifact_path: str
    error_message: str
    duration_seconds: float
    attempts: int


class OrchestrationState(TypedDict, total=False):
    """Full orchestration pipeline state."""

    issue_number: int
    current_stage: str  # "triage", "lld", "spec", "impl", "pr", "done"

    # Artifacts produced at each stage
    issue_brief_path: str
    lld_path: str
    spec_path: str
    worktree_path: str
    pr_url: str

    # Progress tracking
    stage_results: dict[str, StageResult]
    stage_attempts: dict[str, int]

    # Timing
    started_at: str  # ISO8601
    stage_started_at: str
    completed_at: str

    # Configuration snapshot
    config: OrchestratorConfig

    # Error handling
    error_message: str


STAGE_ORDER: list[str] = ["triage", "lld", "spec", "impl", "pr"]

# Maps stage name to the state key that holds its artifact path
_STAGE_ARTIFACT_KEY: dict[str, str] = {
    "triage": "issue_brief_path",
    "lld": "lld_path",
    "spec": "spec_path",
    "impl": "worktree_path",
    "pr": "pr_url",
}


def create_initial_state(
    issue_number: int,
    config: OrchestratorConfig,
) -> OrchestrationState:
    """Create a fresh orchestration state for a new pipeline run."""
    if issue_number < 1:
        msg = "issue_number must be positive"
        raise ValueError(msg)

    now = datetime.now(tz=timezone.utc).isoformat()
    return OrchestrationState(
        issue_number=issue_number,
        current_stage="triage",
        issue_brief_path="",
        lld_path="",
        spec_path="",
        worktree_path="",
        pr_url="",
        stage_results={},
        stage_attempts={stage: 0 for stage in STAGE_ORDER},
        started_at=now,
        stage_started_at="",
        completed_at="",
        config=config,
        error_message="",
    )


def get_next_stage(current_stage: str) -> str:
    """Return the next stage in the pipeline, or 'done' if at end."""
    if current_stage == "done":
        return "done"
    if current_stage not in STAGE_ORDER:
        msg = f"Unknown stage: {current_stage}"
        raise ValueError(msg)
    idx = STAGE_ORDER.index(current_stage)
    if idx >= len(STAGE_ORDER) - 1:
        return "done"
    return STAGE_ORDER[idx + 1]


def update_stage_result(
    state: OrchestrationState,
    stage: str,
    result: StageResult,
) -> OrchestrationState:
    """Return new state with stage result recorded.

    If result status is 'passed' or 'skipped', advances current_stage.
    Also updates the corresponding artifact path key.
    """
    if stage not in STAGE_ORDER:
        msg = f"Unknown stage: {stage}"
        raise ValueError(msg)

    # Copy state to avoid mutation
    new_state = dict(state)
    stage_results = dict(new_state.get("stage_results", {}))
    stage_results[stage] = result
    new_state["stage_results"] = stage_results

    # Update attempt count
    stage_attempts = dict(new_state.get("stage_attempts", {}))
    stage_attempts[stage] = result.get("attempts", 0)
    new_state["stage_attempts"] = stage_attempts

    # Update artifact path for the stage
    artifact_key = _STAGE_ARTIFACT_KEY.get(stage)
    artifact_path = result.get("artifact_path", "")
    if artifact_key and artifact_path:
        new_state[artifact_key] = artifact_path

    # Advance stage if passed or skipped
    status = result.get("status", "")
    if status in ("passed", "skipped"):
        new_state["current_stage"] = get_next_stage(stage)

    # Set completed_at if we're done
    if new_state.get("current_stage") == "done":
        new_state["completed_at"] = datetime.now(tz=timezone.utc).isoformat()

    # Set error_message if failed or blocked
    if status in ("failed", "blocked"):
        new_state["error_message"] = result.get("error_message", "")

    return OrchestrationState(**new_state)
