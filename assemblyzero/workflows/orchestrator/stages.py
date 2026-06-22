"""Stage execution logic for each sub-workflow.

Issue #305: End-to-End Orchestration Workflow (Issue → Code)

Each stage function:
1. Checks if the stage should be skipped (existing artifact)
2. Executes the relevant sub-workflow
3. Returns updated OrchestrationState with stage result
"""

from __future__ import annotations

from assemblyzero.utils.shell import run_command
import json
import os
import shutil
import subprocess
import tempfile
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
    transient: bool | None = None,
) -> StageResult:
    """Helper to create a StageResult.

    transient: Pass False to mark this failure as non-transient so the
    orchestrator's retry loop skips it (Closes #1463). Pass True to force
    a retry attempt. Leave None to use the retry-default (current behavior:
    retry up to max_retries). Only meaningful for status="failed" results.
    """
    result: StageResult = StageResult(
        status=status,
        artifact_path=artifact_path,
        error_message=error_message,
        duration_seconds=duration_seconds,
        attempts=attempts,
    )
    if transient is not None:
        result["transient"] = transient
    return result


def _is_non_transient_halt(sub_result: dict) -> bool:
    """Sub-workflow halts write a recovery_plan_path. Non-transient by default
    since the resume command — not a 10-second retry — is the recovery path.
    Closes #1463.

    Kept for backward compatibility; new call sites should prefer
    _classify_halt_transience (Closes #1478) which reads the recovery plan
    JSON for the actual is_transient classification.
    """
    return bool(sub_result.get("recovery_plan_path", ""))


def _classify_halt_transience(sub_result: dict) -> bool | None:
    """Read the sub-workflow's recovery plan JSON and classify transience.

    Returns:
        - True  -> halt is transient (quota exhausted, capacity, 5xx/429
                   classes per core/recovery_plan.py:TRANSIENT_ERROR_TYPES)
                   -> retry per existing retry loop
        - False -> halt occurred but is non-transient (code bug, exhausted
                   iterations, etc.) -> skip retry
        - None  -> no halt detected (no recovery_plan_path); leave the
                   StageResult.transient field unset -> preserve current
                   behavior for non-halt failures (e.g. gh CLI flakes)

    Closes #1478.
    """
    import json
    plan_path = sub_result.get("recovery_plan_path", "")
    if not plan_path:
        return None
    try:
        plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # Halt occurred but plan unreadable. Conservatively non-transient —
        # the operator's resume hint is still the right recovery path.
        return False
    return bool(plan.get("is_transient", False))


def _fetch_issue_body_to_temp_brief(
    issue_number: int,
    target_repo: str,
) -> tuple[str, str]:
    """Closes #1508: fetch the GitHub issue body and write it to a temp file
    so the triage workflow has a `brief_file` to feed `_load_brief`.

    The triage sub-workflow (workflow_type=\"issue\") requires `brief_file`
    in its state. When the operator pre-authored `docs/lineage/{N}/issue-brief.md`,
    `detect_existing_artifacts` finds it and `should_skip_stage` returns
    early — the sub-workflow is never invoked. When no such brief exists
    (the fresh-external-issue case observed on Chiron #37), the
    sub-workflow IS invoked but `_load_brief` short-circuits with
    \"No brief file specified\" and the stage halts in 0 seconds.

    This helper plugs the gap: synthesize a brief from the GitHub issue
    body itself, write it to a temp file, and pass that file path as
    `brief_file`. The operator-authored Michelle-voice brief still
    overrides via `should_skip_stage` when present.

    Returns:
        (temp_path, error_message). Exactly one is non-empty.
    """
    if not target_repo:
        return ("", "target_repo not specified — cannot resolve issue from gh")

    try:
        result = subprocess.run(
            ["gh", "issue", "view", str(issue_number), "--json", "title,body"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            cwd=target_repo,
        )
    except subprocess.SubprocessError as exc:
        return ("", f"gh issue view failed for #{issue_number}: {exc}")

    if result.returncode != 0:
        return ("", f"gh issue view #{issue_number} non-zero: {result.stderr.strip()}")
    if not result.stdout:
        return ("", f"empty response from gh issue view #{issue_number}")

    try:
        issue_data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return ("", f"failed to parse gh issue view JSON: {exc}")

    issue_title = issue_data.get("title", "").strip()
    issue_body = issue_data.get("body", "")
    if not issue_body.strip():
        return ("", f"issue #{issue_number} body is empty — no content to synthesize a brief from")

    # Minimal brief: just the title + body. The triage sub-workflow's
    # drafter/reviewer process this further; we are NOT pre-Michelle-voice
    # rewriting here — the operator's hand-authored brief at
    # docs/lineage/{N}/issue-brief.md remains the override path.
    brief_content = f"# {issue_title}\n\n{issue_body}\n"

    fd, temp_path = tempfile.mkstemp(
        prefix=f"orchestrator-issue-{issue_number}-",
        suffix=".md",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(brief_content)
    except OSError as exc:
        return ("", f"failed to write temp brief: {exc}")

    return (temp_path, "")


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

    # Closes #1508: when no operator-authored brief exists at
    # docs/lineage/{N}/issue-brief.md, synthesize one from the GitHub issue
    # body and pass it as `brief_file` so `_load_brief` doesn't halt with
    # "No brief file specified."
    brief_file, brief_err = _fetch_issue_body_to_temp_brief(
        issue_number, state.get("target_repo", ""),
    )
    if brief_err:
        result = _make_stage_result(
            status="failed",
            error_message=(
                "Triage stage: cannot synthesize brief from GitHub issue — "
                f"{brief_err}. Workaround: hand-author "
                f"docs/lineage/{issue_number}/issue-brief.md in the target "
                "repo and re-run."
            ),
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
            "brief_file": brief_file,  # Closes #1508
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
                transient=_classify_halt_transience(sub_result),
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

        # #1443: Revise-with-context. On retry, state carries the prior
        # attempt's draft and reviewer feedback so the drafter can iterate
        # instead of starting fresh.
        previous_draft_path = state.get("previous_lld_draft_path", "")
        previous_verdict_text = state.get("previous_lld_verdict_text", "")

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
            "previous_draft_path": previous_draft_path,
            "previous_verdict_text": previous_verdict_text,
        })

        # The requirements workflow's finalize node writes the saved LLD
        # path as `final_lld_path` and the verdict as `final_verdict`
        # (see assemblyzero/workflows/requirements/nodes/finalize.py
        # lines 340, 368). The orchestrator previously read `lld_path` /
        # `review_verdict` which were never set — every reviewer-APPROVED
        # run was misclassified as `status="failed"` and retried 3/3.
        # Fall back to the legacy names for mock_mode and any future
        # alternate writers.
        lld_path = (
            sub_result.get("final_lld_path", "")
            or sub_result.get("lld_path", "")
        )
        review_verdict = (
            sub_result.get("final_verdict", "")
            or sub_result.get("review_verdict", "")
        )

        # #1443: Capture this attempt's outputs onto orchestrator state so
        # the NEXT retry (if any) sees them as previous_*. We snapshot the
        # sub-workflow's current_verdict (actionable feedback) and the LLD
        # path so retry can revise rather than regenerate.
        state = dict(state)
        if lld_path:
            state["previous_lld_draft_path"] = lld_path
        verdict_for_next = sub_result.get("current_verdict", "") or sub_result.get(
            "verdict_text", ""
        )
        if verdict_for_next:
            state["previous_lld_verdict_text"] = verdict_for_next
        state = OrchestrationState(**state)

        if lld_path and Path(lld_path).is_file():
            # #1440 (extended): When the human verdict gate is bypassed
            # (config_gates_verdict=False), the reviewer's verdict becomes
            # ADVISORY — not authoritative. A finalized LLD on disk means the
            # sub-workflow's finalize step ran to completion; that's stage
            # success. Without this guard, the orchestrator considers every
            # bypassed-gate run BLOCKED whenever the reviewer says REVISE,
            # which is the dominant outcome when reviewer-context-bleed
            # (#1441) makes the reviewer wrong.
            if review_verdict.upper() == "APPROVED" or not gate_enabled:
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
                transient=_classify_halt_transience(sub_result),
            )
    except Exception as exc:
        result = _make_stage_result(
            status="failed",
            error_message=f"LLD stage error: {exc}",
            duration_seconds=time.monotonic() - start_time,
            attempts=1,
        )

    return update_stage_result(state, stage, result)


def _ride_spec_on_lld_pr(
    spec_path: str,
    target_repo: str,
    issue_number: int,
) -> bool:
    """Closes #1625. Mirror the implementation spec into the existing ``{N}-lld``
    worktree and commit + push it, so the spec rides the LLD PR (which merges per
    ADR 0221) and lands on target main instead of being orphaned on the working
    tree.

    Best-effort: never raises. If the ``{N}-lld`` worktree is absent (e.g. the
    LLD stage was skipped because a pre-existing LLD was found, so there is no LLD
    PR to ride), the spec is left on the working tree and a note is logged — the
    terminal cleanup only deletes the working-tree copy after the LLD PR merges,
    so an un-ridden spec stays put rather than being lost.

    Returns True iff the spec was committed to the LLD worktree.
    """
    if not target_repo or not spec_path:
        return False
    from assemblyzero.workflows.requirements.git_operations import (
        lld_worktree_path_for,
    )

    worktree = lld_worktree_path_for(target_repo, issue_number)
    if not worktree.is_dir():
        print(
            f"    [spec] no LLD worktree at {worktree} — spec stays on the working "
            f"tree (no LLD PR to ride); terminal cleanup will not delete it"
        )
        return False

    src = Path(spec_path)
    try:
        rel = src.relative_to(Path(target_repo))
    except ValueError:
        return False

    try:
        dst = worktree / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

        add = run_command(
            ["git", "add", str(rel)], cwd=str(worktree),
            capture_output=True, text=True,
        )
        if add.returncode != 0:
            print(f"    [spec] git add failed (non-fatal): {add.stderr.strip()}")
            return False

        msg = (
            f"docs: add implementation spec for issue #{issue_number}\n\n"
            f"Ref #{issue_number}"
        )
        commit = run_command(
            ["git", "commit", "-m", msg], cwd=str(worktree),
            capture_output=True, text=True,
        )
        if commit.returncode != 0:
            detail = (commit.stderr or commit.stdout).strip()
            print(f"    [spec] git commit failed/no-op (non-fatal): {detail}")
            return False

        push = run_command(
            ["git", "push"], cwd=str(worktree),
            capture_output=True, text=True,
        )
        if push.returncode != 0:
            # Committed locally; the open LLD PR updates on the next push.
            print(f"    [spec] commit OK, push failed (non-fatal): {push.stderr.strip()}")
            return True

        print(f"    [spec] implementation spec committed to the LLD PR (issue #{issue_number})")
        return True
    except OSError as e:
        print(f"    [spec] spec mirror failed (non-fatal): {e}")
        return False


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

        # create_implementation_spec_graph already returns CompiledStateGraph
        # (see implementation_spec/graph.py:273 + line 370 `return graph.compile()`).
        # Calling .compile() again raises AttributeError. Use the returned
        # graph directly. Requirements + testing graph factories return the
        # uncompiled StateGraph and still need .compile() — those stages are
        # unchanged.
        app = create_spec_graph()
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
            # Closes #1625: the spec is a permanent artifact paired with the LLD;
            # ride it on the LLD PR so it lands on target main (ADR 0221). The
            # working-tree copy stays for the impl stage to read; the terminal
            # cleanup removes it after the LLD PR merges.
            _ride_spec_on_lld_pr(
                spec_path=spec_path,
                target_repo=state.get("target_repo", ""),
                issue_number=issue_number,
            )
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
                transient=_classify_halt_transience(sub_result),
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
    assemblyzero_root = state.get("assemblyzero_root", "")
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
        # Closes #1504: testing workflow writes files to repo_root. Plumb
        # the worktree path here so generated implementation + tests land
        # on the issue-{N} branch. original_repo_root stays as target_repo
        # so load_lld.py's fallback (Issue #380) can find the LLD that
        # lives on target_repo's main.
        sub_result = app.invoke({
            "issue_number": issue_number,
            "spec_path": spec_path,
            "worktree_path": str(worktree_path),
            "repo_root": str(worktree_path),
            "original_repo_root": target_repo,
            # Issue #1627: suppress the AZ-internal 907/908 c/p docs when building
            # an external repo (target differs from the AssemblyZero root).
            "skip_cp_docs": bool(assemblyzero_root) and target_repo != assemblyzero_root,
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
                transient=_classify_halt_transience(sub_result),
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
