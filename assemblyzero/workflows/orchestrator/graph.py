"""LangGraph meta-graph orchestrating the full pipeline.

Issue #305: End-to-End Orchestration Workflow (Issue → Code)
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from assemblyzero.core.retry_mode import RESUMED, retry_mode_for
from assemblyzero.utils.git import (
    GitBranchError,
    current_branch,
    validate_integration_branch,
)
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
    MOCK_FORBIDDEN_STAGES,
    STAGE_RUNNERS,
    check_human_gate,
    mock_mode,
    should_skip_stage,
)
from assemblyzero.workflows.orchestrator.state import (
    STAGE_ORDER,
    OrchestrationState,
    StageResult,
    create_initial_state,
    default_assemblyzero_root,
    get_next_stage,
    update_stage_result,
)
from assemblyzero.core.errors import is_capacity_message
from assemblyzero.core.halt_node import create_halt_node
from assemblyzero.core.stage_watchdog import StageWatchdog


class OrchestrationResult(TypedDict):
    """Final result of orchestration."""

    success: bool
    issue_number: int
    pr_url: str
    final_stage: str
    total_duration_seconds: float
    stage_results: dict[str, StageResult]
    error_summary: str
    #: #2289: a dry run reports success for having rehearsed, which is not the
    #: same claim as a pipeline that passed. The caller must be able to tell
    #: them apart before printing a banner, because the sentences differ.
    dry_run: bool


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

    # #2288: refused at the dispatch point rather than inside each runner, so
    # the guard holds for a stage nobody remembers to check. These stages exist
    # to reach outward and have no mock form.
    if mock_mode(state) and current_stage in MOCK_FORBIDDEN_STAGES:
        print(
            f"[ORCHESTRATOR] Mock run: stage '{current_stage}' not entered. "
            f"It opens or merges pull requests, which a rehearsal must not do."
        )
        refused = StageResult(
            status="skipped",
            artifact_path="",
            error_message=(
                f"mock mode: '{current_stage}' performs outward effects "
                f"(branch push, PR creation, PR merge) and is never rehearsed"
            ),
            duration_seconds=0.0,
            attempts=0,
        )
        new_state = update_stage_result(state, current_stage, refused)
        save_orchestration_state(new_state)
        return dict(new_state)

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

        # Run stage. #1886: a stall must be visible while it is stalling —
        # the 17.5-minute hang of 2026-07-28 looked identical to normal
        # progress in the log until a human compared it against nominal.
        with StageWatchdog(current_stage):
            new_state = runner(OrchestrationState(**last_state))

        # Persist state after each attempt
        save_orchestration_state(new_state)

        stage_result = new_state.get("stage_results", {}).get(current_stage, {})
        status = stage_result.get("status", "")

        if status in ("passed", "skipped"):
            return dict(new_state)
        if status == "blocked":
            return dict(new_state)
        # failed — retry only when the failure is transient or unmarked
        # (preserve current behavior for non-halt failures). Closes #1463.
        transient = stage_result.get("transient", True)
        if attempt < max_retries and transient:
            # #1909: capacity storms outlast a flat delay — the 2026-07-29
            # phase-4 run burned attempts 1-3 inside ~2 minutes while the
            # provider's 503 storm ran for several. Escalate delays for
            # capacity-class failures; everything else keeps retry_delay.
            if is_capacity_message(stage_result.get("error_message", "")):
                delays = config.get("capacity_retry_delays", [10, 60, 300])
                delay = delays[min(attempt - 1, len(delays) - 1)]
                flavor = " [capacity storm — escalated backoff]"
            else:
                delay = retry_delay
                flavor = ""
            print(
                f"[ORCHESTRATOR] Stage '{current_stage}' failed (attempt {attempt}/{max_retries}). "
                f"Retrying in {delay}s...{flavor}"
            )
            # Update attempt count in result
            stage_result["attempts"] = attempt

            # #1941: decide whether the NEXT attempt may reuse this one's
            # artifacts. Replaying a deterministic failure against the same
            # worktree reproduces it exactly -- run11b's attempt 2 logged
            # "Skipped (already exists)" for every file and returned the
            # identical outcome. Recorded on the result so the stage table
            # says which happened without anyone reading transcripts.
            mode = retry_mode_for(stage_result)
            stage_result["retry_mode"] = mode
            # #2337: this used to say REGENERATED "discards the previous
            # attempt's generated files". It discards nothing. The mode's only
            # effect is to stop N4 SKIPPING files that already exist
            # (implementation/orchestrator.py), and on run-issue7-192332 N4 was
            # never reached -- the red phase saw the surviving implementation
            # and ended the stage first. A reader diagnosing that run would
            # have believed the files were gone.
            # #2346: and it described the IMPLEMENTATION stage's semantics
            # whatever stage had failed. On run-issue7-231606's pr failure it
            # announced "rewriting generated files" for a retry that rewrites
            # nothing -- a pr retry re-attempts a push and a PR creation. Only
            # the stages that actually generate files get that wording.
            if current_stage in ("impl", "lld", "spec"):
                detail = (
                    "reusing generated files where they exist" if mode == RESUMED
                    else "rewriting generated files rather than skipping them"
                )
            else:
                detail = f"re-running the {current_stage} stage"
            print(
                f"[ORCHESTRATOR] Next attempt will be {mode.lower()} ({detail})."
            )
            time.sleep(delay)
            last_state = dict(new_state)
            last_state["retry_mode"] = mode
        else:
            if not transient:
                print(
                    f"[ORCHESTRATOR] Stage '{current_stage}' halted non-transient — "
                    f"skipping retry. Use the sub-workflow's Resume hint above."
                )
            break

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
    workflow.add_node("terminal", create_halt_node("orchestrator"))  # Issue #486

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


#: What a dry run can say about one stage. NOT_REACHED is a fact -- the graph
#: enters at `current_stage` and walks forward, so an earlier stage is never
#: entered. RUNS is also a fact, but a narrower one than it looks: see
#: format_dry_run_plan's closing note.
NOT_REACHED = "not reached"
RUNS = "RUNS"


def dry_run_plan(state: OrchestrationState) -> list[dict]:
    """What a launch would actually do, stage by stage (#2289).

    The previous display mapped every status that was not the literal string
    ``"skipped"`` onto ``EXECUTE``, so a resumed run whose LLD had passed
    announced that the LLD would be redrawn -- the single most expensive stage,
    and the one the operator runs a dry run to confirm is being reused. The
    same command's second table said ``lld passed 327.4s`` directly underneath.

    The graph enters at ``current_stage`` and routes forward from there, so
    position relative to that stage is what decides whether a stage is entered
    at all. The recorded status is reported as itself rather than translated,
    because a status is what the operator is asking about.
    """
    start = state.get("current_stage") or STAGE_ORDER[0]
    start_index = STAGE_ORDER.index(start) if start in STAGE_ORDER else 0
    results = state.get("stage_results", {}) or {}

    plan = []
    for index, stage in enumerate(STAGE_ORDER):
        result = results.get(stage) or {}
        plan.append(
            {
                "stage": stage,
                "recorded": result.get("status", "pending"),
                "action": NOT_REACHED if index < start_index else RUNS,
                "artifact": result.get("artifact_path", ""),
            }
        )
    return plan


def format_dry_run_plan(state: OrchestrationState, issue_number: int) -> str:
    """Render the plan, including what a dry run cannot settle."""
    start = state.get("current_stage") or STAGE_ORDER[0]
    plan = dry_run_plan(state)

    lines = [
        f"\n[ORCHESTRATOR] Dry run for issue #{issue_number}",
        f"[ORCHESTRATOR] Execution begins at: {start}",
        "",
        f"{'Stage':<10} {'Recorded':<12} {'Plan':<12} Artifact",
        "-" * 70,
    ]
    for row in plan:
        lines.append(
            f"{row['stage']:<10} {row['recorded']:<12} "
            f"{row['action']:<12} {row['artifact'] or '-'}"
        )

    lines += [
        "",
        "A stage marked RUNS is entered. Whether it repeats work already done",
        "depends on artifact detection at the time it runs, which a dry run",
        "cannot settle. A stage marked 'not reached' is never entered at all.",
        "",
    ]
    return "\n".join(lines)


def format_stage_table(stage_results: dict) -> str:
    """#1785: per-stage run record — the summary IS the evidence.

    Replaces the blanket 'completed successfully' banner that run 6 of the
    boostgauge#96 campaign proved could assert success over a halted,
    untested implementation (#1779). Pure function; unit-tested.
    """
    from assemblyzero.workflows.orchestrator.state import STAGE_ORDER

    lines = [
        f"{'STAGE':<9} {'VERDICT':<9} {'TIME':>7}  ARTIFACT / ERROR",
        "-" * 70,
    ]
    for stage in STAGE_ORDER:
        r = stage_results.get(stage)
        if not r:
            lines.append(f"{stage:<9} {'-':<9} {'-':>7}")
            continue
        status = r.get("status", "?")
        secs = r.get("duration_seconds", 0.0)
        detail = r.get("error_message") or r.get("artifact_path") or ""
        lines.append(f"{stage:<9} {status:<9} {secs:>6.1f}s  {detail[:60]}")
    return "\n".join(lines)


def _write_run_record(issue_number: int, table: str, success: bool) -> None:
    """Persist the per-run record next to the resume state (#1785)."""
    from assemblyzero.workflows.orchestrator.resume import STATE_DIR

    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        outcome = "SUCCESS" if success else "FAILED"
        (STATE_DIR / f"{issue_number}-record.md").write_text(
            f"# Run record — issue #{issue_number} — {outcome}\n\n"
            f"```\n{table}\n```\n",
            encoding="utf-8",
        )
    except OSError:
        pass  # the console table already showed it; never fail a run on this


def orchestrate(
    issue_number: int,
    config: OrchestratorConfig | None = None,
    resume_from: str | None = None,
    dry_run: bool = False,
    target_repo: str | None = None,
    assemblyzero_root: str | None = None,
    base_branch: str | None = None,
) -> OrchestrationResult:
    """Run full pipeline from issue to PR.

    Args:
        issue_number: GitHub issue number to process
        config: Override default configuration (merged with defaults)
        resume_from: Stage name to resume from (uses persisted state)
        dry_run: If True, show planned stages without execution
        target_repo: Repo the pipeline builds (outputs, worktree, gh CLI).
            Defaults to the AssemblyZero root, so omitting it builds
            AssemblyZero (Issue #1374).
        assemblyzero_root: Where AssemblyZero lives (templates). Defaults to
            the resolved AssemblyZero root.
        base_branch: Integration branch every pipeline PR targets (#1755
            attempt-branch model). Defaults to the branch target_repo is
            checked out on — never a hardcoded main.

    Returns:
        OrchestrationResult with final status and artifacts
    """
    start_time = time.monotonic()

    # Resolve repo targeting once (Issue #1374). target_repo defaults to the
    # AssemblyZero root, so omitting --repo builds AssemblyZero.
    resolved_root = assemblyzero_root or default_assemblyzero_root()
    resolved_target = target_repo or resolved_root

    # #1755 attempt-branch model: capture the integration branch ONCE at
    # pipeline start, before any stage runs or the lock is taken. Every PR
    # the pipeline opens targets this branch — never a hardcoded main. A
    # generated work branch or detached HEAD fails loudly here, before any
    # LLM quota is burned.
    try:
        resolved_base = base_branch or current_branch(resolved_target)
        validate_integration_branch(resolved_base)
    except GitBranchError as e:
        return OrchestrationResult(
            success=False,
            issue_number=issue_number,
            pr_url="",
            final_stage="",
            total_duration_seconds=0.0,
            stage_results={},
            error_summary=f"Base-branch resolution failed: {e}",
            dry_run=False,
        )

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
            dry_run=False,
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
            # #2383: set from THIS invocation, never inherited from the loaded
            # state -- a stale marker would make an ordinary later run believe
            # it was resuming and adopt a previous run's lineage.
            state_dict["resumed_from"] = resume_stage
            state_dict["config"] = effective_config
            # Repo targeting on resume: explicit arg wins, else keep what was
            # persisted, else fall back to the default (Issue #1374).
            state_dict["assemblyzero_root"] = (
                assemblyzero_root or state_dict.get("assemblyzero_root") or resolved_root
            )
            state_dict["target_repo"] = (
                target_repo or state_dict.get("target_repo") or state_dict["assemblyzero_root"]
            )
            # Base branch on resume (#1755): explicit arg wins, else keep
            # what was persisted, else the freshly-detected branch.
            state_dict["base_branch"] = (
                base_branch or state_dict.get("base_branch") or resolved_base
            )
            state = OrchestrationState(**state_dict)
        else:
            state = create_initial_state(
                issue_number, effective_config, resolved_target, resolved_root
            )
            state["base_branch"] = resolved_base
            # #2383: explicit on the fresh path too, so the field is never
            # merely absent and a reader cannot mistake missing for "unknown".
            state["resumed_from"] = ""
            # Detect existing artifacts and skip completed stages
            existing = detect_existing_artifacts(issue_number, state.get("target_repo", ""))
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
            print(format_dry_run_plan(state, issue_number), end="")

            release_orchestration_lock(issue_number)
            return OrchestrationResult(
                success=True,
                issue_number=issue_number,
                pr_url="",
                final_stage=state.get("current_stage", "triage"),
                total_duration_seconds=time.monotonic() - start_time,
                stage_results=state.get("stage_results", {}),
                error_summary="",
                dry_run=True,
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

        # #1785: every run leaves a readable record beside its resume state.
        _write_run_record(
            issue_number, format_stage_table(stage_results), success
        )

        return OrchestrationResult(
            success=success,
            issue_number=issue_number,
            pr_url=pr_url,
            final_stage=final_stage,
            total_duration_seconds=time.monotonic() - start_time,
            stage_results=stage_results,
            error_summary=error_summary,
            dry_run=False,
        )

    finally:
        release_orchestration_lock(issue_number)
