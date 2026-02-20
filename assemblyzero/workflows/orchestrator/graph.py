"""LangGraph meta-graph orchestrating the full pipeline.

Issue #305: End-to-End Orchestration Workflow (Issue → Code)
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from assemblyzero.workflows.orchestrator.artifacts import detect_existing_artifacts
from assemblyzero.workflows.orchestrator.config import (
    OrchestratorConfig,
    load_config,
    validate_config,
)
from assemblyzero.workflows.orchestrator.resume import (
    acquire_orchestration_lock,
    determine_resume_stage,
    load_orchestration_state,
    release_orchestration_lock,
    save_orchestration_state,
)
from assemblyzero.workflows.orchestrator.stages import (
    STAGE_RUNNERS,
    check_human_gate,
    should_skip_stage,
)
from assemblyzero.workflows.orchestrator.state import (
    STAGE_ORDER,
    OrchestrationState,
    StageResult,
    create_initial_state,
    get_next_stage,
    update_stage_result,
)


class OrchestrationResult(TypedDict):
    """Final result of orchestration."""

    success: bool
    issue_number: int
    pr_url: str
    final_stage: str
    total_duration_seconds: float
    stage_results: dict[str, StageResult]
    error_summary: str


class ConcurrentOrchestrationError(RuntimeError):
    """Raised when orchestration is already running for an issue."""


def _init_node(state: OrchestrationState) -> dict[str, Any]:
    """Initialize orchestration: detect artifacts, set start time."""
    now = datetime.now(tz=timezone.utc).isoformat()
    return {
        "stage_started_at": now,
    }


def _run_stage_node(state: OrchestrationState) -> dict[str, Any]:
    """Execute the current stage with retry logic."""
    current_stage = state.get("current_stage", "done")
    if current_stage == "done" or current_stage not in STAGE_RUNNERS:
        return {}

    config = state.get("config", {})
    max_retries = config.get("max_stage_retries", 3)
    retry_delay = config.get("retry_delay_seconds", 10)

    # Check human gate
    if not check_human_gate(state, current_stage):
        blocked_result = StageResult(
            status="blocked",
            artifact_path="",
            error_message=f"Human gate enabled for stage '{current_stage}'. Pipeline paused.",
            duration_seconds=0.0,
            attempts=0,
        )
        new_state = update_stage_result(state, current_stage, blocked_result)
        save_orchestration_state(new_state)
        return dict(new_state)

    runner = STAGE_RUNNERS[current_stage]
    last_state = state

    for attempt in range(1, max_retries + 1):
        # Update state with start time for this stage
        last_state = dict(last_state)
        last_state["stage_started_at"] = datetime.now(tz=timezone.utc).isoformat()

        # Run stage
        new_state = runner(OrchestrationState(**last_state))

        # Persist state after each attempt
        save_orchestration_state(new_state)

        stage_result = new_state.get("stage_results", {}).get(current_stage, {})
        status = stage_result.get("status", "")

        if status in ("passed", "skipped"):
            return dict(new_state)
        if status == "blocked":
            return dict(new_state)
        # failed — retry
        if attempt < max_retries:
            print(
                f"[ORCHESTRATOR] Stage '{current_stage}' failed (attempt {attempt}/{max_retries}). "
                f"Retrying in {retry_delay}s..."
            )
            # Update attempt count in result
            stage_result["attempts"] = attempt
            time.sleep(retry_delay)
            last_state = new_state

    # All retries exhausted — update attempt count
    final_results = dict(new_state.get("stage_results", {}))
    if current_stage in final_results:
        final_results[current_stage] = dict(final_results[current_stage])
        final_results[current_stage]["attempts"] = max_retries
    new_state_dict = dict(new_state)
    new_state_dict["stage_results"] = final_results
    save_orchestration_state(OrchestrationState(**new_state_dict))
    return new_state_dict


def _route_after_stage(state: OrchestrationState) -> str:
    """Route to next stage or terminal state based on current stage result."""
    current_stage = state.get("current_stage", "done")

    if current_stage == "done":
        return "done"

    # Check the stage result for the stage that just ran
    # After update_stage_result, current_stage is already advanced if passed/skipped
    # So we need to check if there were failures
    stage_results = state.get("stage_results", {})

    # Find the most recent result
    for stage in reversed(STAGE_ORDER):
        if stage in stage_results:
            result = stage_results[stage]
            status = result.get("status", "")
            if status in ("failed", "blocked"):
                return "terminal"
            break

    if current_stage == "done":
        return "done"

    return "run_stage"


def create_orchestration_graph() -> StateGraph:
    """Create LangGraph StateGraph for orchestration pipeline.

    Graph structure:
        init → run_stage → (route) → run_stage | done | terminal
    """
    workflow = StateGraph(OrchestrationState)

    workflow.add_node("init", _init_node)
    workflow.add_node("run_stage", _run_stage_node)
    workflow.add_node("done", lambda state: {"completed_at": datetime.now(tz=timezone.utc).isoformat()})
    workflow.add_node("terminal", lambda state: {})

    workflow.set_entry_point("init")
    workflow.add_edge("init", "run_stage")
    workflow.add_conditional_edges(
        "run_stage",
        _route_after_stage,
        {
            "run_stage": "run_stage",
            "done": "done",
            "terminal": "terminal",
        },
    )
    workflow.add_edge("done", END)
    workflow.add_edge("terminal", END)

    return workflow


def orchestrate(
    issue_number: int,
    config: OrchestratorConfig | None = None,
    resume_from: str | None = None,
    dry_run: bool = False,
) -> OrchestrationResult:
    """Run full pipeline from issue to PR.

    Args:
        issue_number: GitHub issue number to process
        config: Override default configuration (merged with defaults)
        resume_from: Stage name to resume from (uses persisted state)
        dry_run: If True, show planned stages without execution

    Returns:
        OrchestrationResult with final status and artifacts
    """
    start_time = time.monotonic()

    # Load configuration
    effective_config = load_config(config)
    errors = validate_config(effective_config)
    if errors:
        return OrchestrationResult(
            success=False,
            issue_number=issue_number,
            pr_url="",
            final_stage="",
            total_duration_seconds=0.0,
            stage_results={},
            error_summary=f"Configuration errors: {'; '.join(errors)}",
        )

    # Acquire lock
    if not acquire_orchestration_lock(issue_number):
        raise ConcurrentOrchestrationError(
            f"Issue {issue_number} is already being orchestrated. "
            f"Check .assemblyzero/orchestrator/locks/{issue_number}.lock"
        )

    try:
        # Create or load state
        if resume_from is not None:
            state = load_orchestration_state(issue_number)
            if state is None:
                raise ValueError(
                    f"No persisted state found for issue {issue_number}. "
                    f"Cannot resume without prior state."
                )
            resume_stage = determine_resume_stage(state, resume_from)
            state_dict = dict(state)
            state_dict["current_stage"] = resume_stage
            state_dict["config"] = effective_config
            state = OrchestrationState(**state_dict)
        else:
            state = create_initial_state(issue_number, effective_config)
            # Detect existing artifacts and skip completed stages
            existing = detect_existing_artifacts(issue_number)
            for stage in STAGE_ORDER:
                skip, artifact_path = should_skip_stage(state, stage, existing)
                if skip and artifact_path:
                    result = StageResult(
                        status="skipped",
                        artifact_path=artifact_path,
                        error_message="",
                        duration_seconds=0.0,
                        attempts=0,
                    )
                    state = update_stage_result(state, stage, result)
                else:
                    break  # Stop skipping at first non-skippable stage

        # Dry run
        if dry_run:
            print(f"\n[ORCHESTRATOR] Dry run for issue #{issue_number}")
            print(f"{'Stage':<10} {'Status':<12} {'Artifact'}")
            print("-" * 60)
            existing = detect_existing_artifacts(issue_number)
            for stage in STAGE_ORDER:
                stage_result = state.get("stage_results", {}).get(stage, {})
                status = stage_result.get("status", "pending")
                artifact = stage_result.get("artifact_path", "")
                if status == "skipped":
                    print(f"{stage:<10} {'SKIP':<12} {artifact}")
                else:
                    print(f"{stage:<10} {'EXECUTE':<12} -")
            print()

            release_orchestration_lock(issue_number)
            return OrchestrationResult(
                success=True,
                issue_number=issue_number,
                pr_url="",
                final_stage=state.get("current_stage", "triage"),
                total_duration_seconds=time.monotonic() - start_time,
                stage_results=state.get("stage_results", {}),
                error_summary="",
            )

        # Run the graph
        save_orchestration_state(state)
        graph = create_orchestration_graph()
        app = graph.compile()
        final_state = app.invoke(dict(state))

        # Build result
        pr_url = final_state.get("pr_url", "")
        final_stage = final_state.get("current_stage", "")
        stage_results = final_state.get("stage_results", {})
        error_message = final_state.get("error_message", "")

        success = final_stage == "done"

        if not success and error_message:
            error_summary = (
                f"Pipeline failed at stage '{final_stage}'. "
                f"Error: {error_message}. "
                f"Resume with: orchestrate --issue {issue_number} --resume-from {final_stage}"
            )
        else:
            error_summary = ""

        return OrchestrationResult(
            success=success,
            issue_number=issue_number,
            pr_url=pr_url,
            final_stage=final_stage,
            total_duration_seconds=time.monotonic() - start_time,
            stage_results=stage_results,
            error_summary=error_summary,
        )

    finally:
        release_orchestration_lock(issue_number)
