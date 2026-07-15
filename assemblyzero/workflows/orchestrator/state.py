"""Orchestration state management.

Issue #305: End-to-End Orchestration Workflow (Issue → Code)
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

from assemblyzero.workflows.orchestrator.config import OrchestratorConfig


class StageResult(TypedDict, total=False):
    """Result of executing a single stage."""

    status: str  # "passed", "blocked", "failed", "skipped"
    artifact_path: str
    error_message: str
    duration_seconds: float
    attempts: int
    # When False, the orchestrator's retry loop skips this stage — the failure
    # is known not to resolve on retry (e.g. sub-workflow halted with a
    # non-transient recovery plan). When True or absent, the retry loop runs
    # as today. Closes #1463.
    transient: bool


class OrchestrationState(TypedDict, total=False):
    """Full orchestration pipeline state."""

    issue_number: int
    current_stage: str  # "triage", "lld", "spec", "impl", "pr", "cleanup", "done"

    # Repo targeting (Issue #1374)
    target_repo: str  # Where the work happens (outputs, worktree, gh CLI)
    assemblyzero_root: str  # Where AssemblyZero lives (templates/prompts)
    # Attempt-branch model (#1755): the integration branch target_repo was
    # standing on at pipeline start. Every PR the pipeline opens targets
    # this branch — never a hardcoded main. Captured once in orchestrate().
    base_branch: str

    # Artifacts produced at each stage
    issue_brief_path: str
    lld_path: str
    spec_path: str
    worktree_path: str
    pr_url: str
    lld_pr_url: str  # Issue #1531: the LLD PR, captured so the terminal cleanup stage can merge it

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

    # #1443: Revise-with-context — carried across retries within a stage so
    # the sub-workflow's drafter can iterate on the prior attempt instead of
    # regenerating from scratch. The orchestrator's stage runner populates
    # these from the failed sub_result; the runner reads them on the next
    # attempt and threads them into the sub-workflow's app.invoke().
    previous_lld_draft_path: str
    previous_lld_verdict_text: str
    previous_triage_brief_path: str
    previous_triage_verdict_text: str
    previous_spec_draft_path: str
    previous_spec_verdict_text: str


# Issue #1628: a terminal "cleanup" stage runs after "pr" — it merges the LLD PR
# (#1531), deletes the now-redundant working-tree LLD/spec copies (#1624), and
# removes the LLD + impl worktrees (#1628). Best-effort housekeeping.
STAGE_ORDER: list[str] = ["triage", "lld", "spec", "impl", "pr", "cleanup"]

# Maps stage name to the state key that holds its artifact path
_STAGE_ARTIFACT_KEY: dict[str, str] = {
    "triage": "issue_brief_path",
    "lld": "lld_path",
    "spec": "spec_path",
    "impl": "worktree_path",
    "pr": "pr_url",
}


def default_assemblyzero_root() -> str:
    """Resolve the AssemblyZero repo root from this module's location.

    state.py lives at assemblyzero/workflows/orchestrator/state.py, so the
    repo root is three parents up from the package directory.
    """
    return str(Path(__file__).resolve().parents[3])


def create_initial_state(
    issue_number: int,
    config: OrchestratorConfig,
    target_repo: str | None = None,
    assemblyzero_root: str | None = None,
) -> OrchestrationState:
    """Create a fresh orchestration state for a new pipeline run.

    Issue #1374: ``target_repo`` is where the work happens (outputs, worktree,
    gh CLI); ``assemblyzero_root`` is where AssemblyZero lives (templates).
    Both default to the AssemblyZero root, so omitting them builds AssemblyZero
    (backward compatible).
    """
    if issue_number < 1:
        msg = "issue_number must be positive"
        raise ValueError(msg)

    resolved_root = assemblyzero_root or default_assemblyzero_root()
    resolved_target = target_repo or resolved_root

    now = datetime.now(tz=timezone.utc).isoformat()
    return OrchestrationState(
        issue_number=issue_number,
        current_stage="triage",
        target_repo=resolved_target,
        assemblyzero_root=resolved_root,
        issue_brief_path="",
        lld_path="",
        spec_path="",
        worktree_path="",
        pr_url="",
        lld_pr_url="",
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
