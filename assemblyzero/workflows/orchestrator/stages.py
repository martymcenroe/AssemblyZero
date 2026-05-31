"""Stage execution logic for each sub-workflow.

Issue #305: End-to-End Orchestration Workflow (Issue → Code)

Each stage function:
1. Checks if the stage should be skipped (existing artifact)
2. Executes the relevant sub-workflow
3. Returns updated OrchestrationState with stage result
"""

from __future__ import annotations

from assemblyzero.utils.shell import run_command
import time
from pathlib import Path

from assemblyzero.workflows.orchestrator.artifacts import (
    detect_existing_artifacts,
    validate_artifact,
    worktree_path_for,
)
from assemblyzero.workflows.orchestrator.state import (
    OrchestrationState,
    StageResult,
    update_stage_result,
)


def should_skip_stage(
    state: OrchestrationState,
    stage: str,
    existing_artifacts: dict[str, str | None],
) -> tuple[bool, str | None]:
    """Determine if a stage should be skipped.

    Returns (should_skip, artifact_path).

    impl and pr stages are never skipped.
    """
    if stage in ("impl", "pr"):
        return (False, None)

    config = state.get("config", {})
    artifact_path = existing_artifacts.get(stage)

    if not artifact_path:
        return (False, None)

    # Check config flags
    if stage == "lld" and not config.get("skip_existing_lld", True):
        return (False, None)
    if stage == "spec" and not config.get("skip_existing_spec", True):
        return (False, None)

    # Validate the artifact actually exists and is valid
    path = Path(artifact_path)
    if validate_artifact(path, stage):
        return (True, artifact_path)

    return (False, None)


def check_human_gate(
    state: OrchestrationState,
    stage: str,
) -> bool:
    """Check if a human gate is configured before this stage.

    Returns True if gate is not enabled or not applicable.
    Returns False if gate is enabled (pipeline should block).
    """
    config = state.get("config", {})
    gates = config.get("gates", {})
    gate_enabled = gates.get(stage, False)

    if not gate_enabled:
        return True  # No gate, proceed

    # Gate is enabled — in non-interactive mode, block
    return False


def _make_stage_result(
    status: str,
    artifact_path: str = "",
    error_message: str = "",
    duration_seconds: float = 0.0,
    attempts: int = 0,
) -> StageResult:
    """Helper to create a StageResult."""
    return StageResult(
        status=status,
        artifact_path=artifact_path,
        error_message=error_message,
        duration_seconds=duration_seconds,
        attempts=attempts,
    )


def run_triage_stage(state: OrchestrationState) -> OrchestrationState:
    """Execute issue triage workflow.

    Checks for existing artifact first.
    Wraps requirements workflow with type=issue.
    """
    stage = "triage"
    issue_number = state["issue_number"]
    start_time = time.monotonic()

    # Check for existing artifact
    existing = detect_existing_artifacts(issue_number, state.get("target_repo", ""))
    skip, artifact_path = should_skip_stage(state, stage, existing)
    if skip and artifact_path:
        result = _make_stage_result(
            status="skipped",
            artifact_path=artifact_path,
            duration_seconds=time.monotonic() - start_time,
            attempts=0,
        )
        return update_stage_result(state, stage, result)

    # Execute triage sub-workflow
    try:
        # Import here to avoid circular dependencies and allow mocking
        from assemblyzero.workflows.requirements.graph import create_requirements_graph

        # #1440: Plumb orchestrator config into the sub-workflow state.
        config = state.get("config", {})
        stage_cfg = config.get("stages", {}).get("triage", {})
        gate_enabled = bool(config.get("gates", {}).get("triage", False))

        graph = create_requirements_graph()
        app = graph.compile()
        sub_result = app.invoke({
            "issue_number": issue_number,
            "workflow_type": "issue",
            "target_repo": state.get("target_repo", ""),
            "assemblyzero_root": state.get("assemblyzero_root", ""),
            "config_drafter": stage_cfg.get("drafter", ""),
            "config_reviewer": stage_cfg.get("reviewer", ""),
            "config_effort": stage_cfg.get("effort", ""),
            "config_gates_draft": gate_enabled,
            "config_gates_verdict": gate_enabled,
        })

        # Check for artifact
        brief_path = sub_result.get("issue_brief_path", "")
        if brief_path and Path(brief_path).is_file():
            result = _make_stage_result(
                status="passed",
                artifact_path=brief_path,
                duration_seconds=time.monotonic() - start_time,
                attempts=1,
            )
        else:
            error_msg = sub_result.get("error_message", "Triage workflow completed but no artifact produced")
            result = _make_stage_result(
                status="failed",
                error_message=error_msg,
                duration_seconds=time.monotonic() - start_time,
                attempts=1,
            )
    except Exception as exc:
        result = _make_stage_result(
            status="failed",
            error_message=f"Triage stage error: {exc}",
            duration_seconds=time.monotonic() - start_time,
            attempts=1,
        )

    return update_stage_result(state, stage, result)


def run_lld_stage(state: OrchestrationState) -> OrchestrationState:
    """Execute LLD generation and review workflow.

    Checks for existing artifact first if skip_existing_lld is configured.
    Wraps requirements workflow with type=lld.
    """
    stage = "lld"
    issue_number = state["issue_number"]
    start_time = time.monotonic()

    # Check for existing artifact
    existing = detect_existing_artifacts(issue_number, state.get("target_repo", ""))
    skip, artifact_path = should_skip_stage(state, stage, existing)
    if skip and artifact_path:
        result = _make_stage_result(
            status="skipped",
            artifact_path=artifact_path,
            duration_seconds=time.monotonic() - start_time,
            attempts=0,
        )
        return update_stage_result(state, stage, result)

    try:
        from assemblyzero.workflows.requirements.graph import create_requirements_graph

        # #1440: Plumb orchestrator config into the sub-workflow state.
        config = state.get("config", {})
        stage_cfg = config.get("stages", {}).get("lld", {})
        gate_enabled = bool(config.get("gates", {}).get("lld", False))

        graph = create_requirements_graph()
        app = graph.compile()
        sub_result = app.invoke({
            "issue_number": issue_number,
            "workflow_type": "lld",
            "target_repo": state.get("target_repo", ""),
            "assemblyzero_root": state.get("assemblyzero_root", ""),
            "config_drafter": stage_cfg.get("drafter", ""),
            "config_reviewer": stage_cfg.get("reviewer", ""),
            "config_effort": stage_cfg.get("effort", ""),
            "config_gates_draft": gate_enabled,
            "config_gates_verdict": gate_enabled,
        })

        lld_path = sub_result.get("lld_path", "")
        review_verdict = sub_result.get("review_verdict", "")

        if lld_path and Path(lld_path).is_file():
            if review_verdict.upper() == "APPROVED":
                result = _make_stage_result(
                    status="passed",
                    artifact_path=lld_path,
                    duration_seconds=time.monotonic() - start_time,
                    attempts=1,
                )
            else:
                result = _make_stage_result(
                    status="blocked",
                    artifact_path=lld_path,
                    error_message=f"LLD review verdict: {review_verdict}. Manual intervention needed.",
                    duration_seconds=time.monotonic() - start_time,
                    attempts=1,
                )
        else:
            error_msg = sub_result.get("error_message", "LLD workflow completed but no artifact produced")
            result = _make_stage_result(
                status="failed",
                error_message=error_msg,
                duration_seconds=time.monotonic() - start_time,
                attempts=1,
            )
    except Exception as exc:
        result = _make_stage_result(
            status="failed",
            error_message=f"LLD stage error: {exc}",
            duration_seconds=time.monotonic() - start_time,
            attempts=1,
        )

    return update_stage_result(state, stage, result)


def run_spec_stage(state: OrchestrationState) -> OrchestrationState:
    """Execute implementation spec workflow.

    Checks for existing artifact first if skip_existing_spec is configured.
    """
    stage = "spec"
    issue_number = state["issue_number"]
    start_time = time.monotonic()

    # Check for existing artifact
    existing = detect_existing_artifacts(issue_number, state.get("target_repo", ""))
    skip, artifact_path = should_skip_stage(state, stage, existing)
    if skip and artifact_path:
        result = _make_stage_result(
            status="skipped",
            artifact_path=artifact_path,
            duration_seconds=time.monotonic() - start_time,
            attempts=0,
        )
        return update_stage_result(state, stage, result)

    try:
        from assemblyzero.workflows.implementation_spec.graph import create_implementation_spec_graph as create_spec_graph

        lld_path = state.get("lld_path", "")
        # #1440: Plumb orchestrator config into the sub-workflow state.
        config = state.get("config", {})
        stage_cfg = config.get("stages", {}).get("spec", {})
        gate_enabled = bool(config.get("gates", {}).get("spec", False))

        graph = create_spec_graph()
        app = graph.compile()
        sub_result = app.invoke({
            "issue_number": issue_number,
            "lld_path": lld_path,
            "repo_root": state.get("target_repo", ""),
            "assemblyzero_root": state.get("assemblyzero_root", ""),
            "config_drafter": stage_cfg.get("drafter", ""),
            "config_reviewer": stage_cfg.get("reviewer", ""),
            "config_effort": stage_cfg.get("effort", ""),
            "config_mock_mode": False,
            "human_gate_enabled": gate_enabled,
        })

        spec_path = sub_result.get("spec_path", "")
        if spec_path and Path(spec_path).is_file():
            result = _make_stage_result(
                status="passed",
                artifact_path=spec_path,
                duration_seconds=time.monotonic() - start_time,
                attempts=1,
            )
        else:
            error_msg = sub_result.get("error_message", "Spec workflow completed but no artifact produced")
            result = _make_stage_result(
                status="failed",
                error_message=error_msg,
                duration_seconds=time.monotonic() - start_time,
                attempts=1,
            )
    except Exception as exc:
        result = _make_stage_result(
            status="failed",
            error_message=f"Spec stage error: {exc}",
            duration_seconds=time.monotonic() - start_time,
            attempts=1,
        )

    return update_stage_result(state, stage, result)


def run_impl_stage(state: OrchestrationState) -> OrchestrationState:
    """Execute implementation workflow (TDD).

    Ensures worktree exists or creates it via git worktree add.
    Runs implementation workflow in the worktree.
    """
    stage = "impl"
    issue_number = state["issue_number"]
    start_time = time.monotonic()

    import subprocess

    target_repo = state.get("target_repo", "")
    worktree_path = worktree_path_for(issue_number, target_repo or None)
    branch_name = f"issue-{issue_number}"

    try:
        # Ensure the worktree exists, carved from the TARGET repo (Issue #1374).
        # `git -C {target_repo}` makes the worktree belong to the target, not
        # the orchestrator's own cwd. Without target_repo we fall back to the
        # orchestrator's repo (AssemblyZero self-build).
        if not worktree_path.is_dir():
            add_cmd = ["git"]
            if target_repo:
                add_cmd += ["-C", target_repo]
            add_cmd += ["worktree", "add", str(worktree_path), "-b", branch_name]
            run_command(
                add_cmd,
                check=True,
                capture_output=True,
                text=True,
            )

        # Run implementation workflow
        from assemblyzero.workflows.testing.graph import build_testing_workflow as create_impl_graph

        spec_path = state.get("spec_path", "")
        # #1440: Plumb orchestrator config into the sub-workflow state.
        config = state.get("config", {})
        stage_cfg = config.get("stages", {}).get("impl", {})

        graph = create_impl_graph()
        app = graph.compile()
        sub_result = app.invoke({
            "issue_number": issue_number,
            "spec_path": spec_path,
            "worktree_path": str(worktree_path),
            "repo_root": target_repo,
            "original_repo_root": target_repo,
            "config_drafter": stage_cfg.get("drafter", ""),
            "config_reviewer": stage_cfg.get("reviewer", ""),
            "config_effort": stage_cfg.get("effort", ""),
        })

        error_msg = sub_result.get("error_message", "")
        if not error_msg:
            result = _make_stage_result(
                status="passed",
                artifact_path=str(worktree_path),
                duration_seconds=time.monotonic() - start_time,
                attempts=1,
            )
        else:
            result = _make_stage_result(
                status="failed",
                artifact_path=str(worktree_path),
                error_message=error_msg,
                duration_seconds=time.monotonic() - start_time,
                attempts=1,
            )
    except subprocess.CalledProcessError as exc:
        result = _make_stage_result(
            status="failed",
            error_message=f"Git worktree error: {exc.stderr}",
            duration_seconds=time.monotonic() - start_time,
            attempts=1,
        )
    except Exception as exc:
        result = _make_stage_result(
            status="failed",
            error_message=f"Implementation stage error: {exc}",
            duration_seconds=time.monotonic() - start_time,
            attempts=1,
        )

    return update_stage_result(state, stage, result)


def run_pr_stage(state: OrchestrationState) -> OrchestrationState:
    """Create and submit the PR via the gh CLI.

    The head branch is derived from the branch actually checked out in the
    worktree (not a hardcoded ``issue-{N}``); both the PR title and body carry
    ``Closes #N`` so the fleet pr-sentinel accepts the PR and it can reach
    ``mergeable_state: clean``.
    """
    stage = "pr"
    issue_number = state["issue_number"]
    start_time = time.monotonic()

    import subprocess

    try:
        worktree_path = state.get("worktree_path", "")
        if not worktree_path:
            result = _make_stage_result(
                status="failed",
                error_message="No worktree path available for PR creation",
                duration_seconds=time.monotonic() - start_time,
                attempts=1,
            )
            return update_stage_result(state, stage, result)

        # Derive the branch actually checked out in the worktree rather than
        # assuming `issue-{N}`: the worktree may have been created on a
        # differently-named branch (e.g. `{N}-short-desc`), and pushing or
        # opening the PR against the wrong branch breaks the run.
        branch_result = run_command(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            cwd=worktree_path,
        )
        branch = branch_result.stdout.strip()

        # Push branch
        run_command(
            ["git", "push", "--set-upstream", "origin", branch],
            check=True,
            capture_output=True,
            text=True,
            cwd=worktree_path,
        )

        # Create PR. pr-sentinel validates the PR *body* for `Closes #N`
        # (commit message / title alone are not sufficient); the universal rule
        # also requires `Closes #N` in the title. Without it the PR is marked
        # action_required/blocked and never reaches `mergeable_state: clean`.
        pr_title = f"Resolve issue via orchestrated implementation (Closes #{issue_number})"
        pr_body = (
            f"Closes #{issue_number}\n\n"
            "Automated PR generated by the orchestration workflow."
        )
        pr_result = run_command(
            [
                "gh", "pr", "create",
                "--title", pr_title,
                "--body", pr_body,
                "--base", "main",
                "--head", branch,
            ],
            check=True,
            capture_output=True,
            text=True,
            cwd=worktree_path,
        )

        pr_url = pr_result.stdout.strip()
        result = _make_stage_result(
            status="passed",
            artifact_path=pr_url,
            duration_seconds=time.monotonic() - start_time,
            attempts=1,
        )
    except subprocess.CalledProcessError as exc:
        result = _make_stage_result(
            status="failed",
            error_message=f"PR creation error: {exc.stderr}",
            duration_seconds=time.monotonic() - start_time,
            attempts=1,
        )
    except Exception as exc:
        result = _make_stage_result(
            status="failed",
            error_message=f"PR stage error: {exc}",
            duration_seconds=time.monotonic() - start_time,
            attempts=1,
        )

    return update_stage_result(state, stage, result)


# Map stage names to their runner functions
STAGE_RUNNERS: dict[str, callable] = {
    "triage": run_triage_stage,
    "lld": run_lld_stage,
    "spec": run_spec_stage,
    "impl": run_impl_stage,
    "pr": run_pr_stage,
}
