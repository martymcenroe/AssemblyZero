"""Stage execution logic for each sub-workflow.

Issue #305: End-to-End Orchestration Workflow (Issue → Code)

Each stage function:
1. Checks if the stage should be skipped (existing artifact)
2. Executes the relevant sub-workflow
3. Returns updated OrchestrationState with stage result
"""

from __future__ import annotations

from assemblyzero.utils.git import GitBranchError, current_branch
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
from assemblyzero.core.llm_provider import get_provider

import logging

_stages_logger = logging.getLogger(__name__)


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
        # #1939: no recovery plan, but some sub-workflow guards halt with a
        # bare error_message. A stagnation halt is deterministic given the
        # worktree the retry will resume ("Skipped (already exists)" replayed
        # attempt 1 verbatim on 2026-07-30) — retrying it burns full stage
        # attempts to re-measure the number the guard already reported.
        message = str(sub_result.get("error_message", "")).lower()
        if any(m in message for m in ("stagnant", "stagnation")):
            return False
        return None
    try:
        plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # Halt occurred but plan unreadable. Conservatively non-transient —
        # the operator's resume hint is still the right recovery path.
        return False
    return bool(plan.get("is_transient", False))


def _synthesize_brief_summary(title: str, body: str) -> str:
    """Closes #1530: generate a concise 2-4 sentence summary from an issue
    title and body using the codebase's ClaudeCLIProvider (haiku model for
    speed; subscription/OAuth, never API key).

    Returns the summary text on success, or an empty string on any failure
    (timeout, model error, empty response). Callers must treat an empty
    return as "fall back to raw passthrough."
    """
    system_prompt = (
        "You are a technical writer summarising GitHub issues for an engineering workflow. "
        "Write 2-4 sentences: what the issue asks for, why it matters, and the rough scope "
        "(e.g. single function, new module, config change). "
        "Do not repeat the title. Write in plain English, no markdown headings, no bullet points."
    )
    content = f"Title: {title}\n\nBody:\n{body}"

    try:
        provider = get_provider("claude:haiku")
        result = provider.invoke(
            system_prompt=system_prompt,
            content=content,
            timeout_seconds=60,
        )
    except Exception as exc:
        _stages_logger.warning(
            "brief summary synthesis failed (provider error): %s — falling back to raw passthrough",
            exc,
        )
        return ""

    if not result.success or not result.response or not result.response.strip():
        _stages_logger.warning(
            "brief summary synthesis returned empty/failure (error=%s) — falling back to raw passthrough",
            result.error_message,
        )
        return ""

    return result.response.strip()


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

    # Closes #1530: prepend a concise auto-generated summary so the brief
    # starts with substance rather than raw issue text.  If synthesis fails
    # (timeout, model error, empty response) we fall back silently to the
    # original title+body passthrough — orchestration must never halt here.
    summary = _synthesize_brief_summary(issue_title, issue_body)
    if summary:
        brief_content = (
            f"# {issue_title}\n\n"
            f"## Summary\n{summary}\n\n"
            f"## Issue detail\n{issue_body}\n"
        )
    else:
        # Fallback: raw passthrough (preserves pre-#1530 behaviour)
        _stages_logger.info(
            "issue #%s brief synthesis: using raw passthrough (summary generation failed or returned empty)",
            issue_number,
        )
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

    # Closes #1770: `orchestrate --issue N` means the issue ALREADY EXISTS,
    # so triage's product — a brief distilled from the issue — is exactly
    # what the synthesizer above just produced (#1508 fetch + #1530
    # summary). The previous code invoked the issue-AUTHORING workflow
    # here, which (a) filed a duplicate GitHub issue per attempt via its
    # finalize (`gh issue create`, no existing-issue guard) and (b) then
    # failed on `sub_result['issue_brief_path']`, a key no code path sets —
    # triage could never pass without a pre-existing skip artifact.
    # Persist the synthesized brief to the canonical skip-artifact location
    # so resume/re-runs skip via detect_existing_artifacts, and pass.
    canonical_brief = (
        Path(state.get("target_repo", "."))
        / "docs" / "lineage" / str(issue_number) / "issue-brief.md"
    )
    artifact_path = brief_file
    try:
        canonical_brief.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(brief_file, canonical_brief)
        artifact_path = str(canonical_brief)
    except OSError as exc:
        # Non-fatal: the temp brief still serves this run; only the
        # skip-on-rerun convenience is lost.
        _stages_logger.warning(
            "Triage: could not persist brief to %s: %s", canonical_brief, exc
        )

    result = _make_stage_result(
        status="passed",
        artifact_path=artifact_path,
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
            # #1755: the LLD PR targets the integration branch captured at
            # pipeline start (attempt-branch model), not a hardcoded main.
            "base_branch": state.get("base_branch", ""),
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
        # #1531: capture the LLD PR URL so the terminal cleanup stage can merge it
        # (landing the LLD + spec on target main per ADR 0221).
        lld_pr_url = sub_result.get("final_lld_pr_url", "")
        if lld_pr_url:
            state["lld_pr_url"] = lld_pr_url
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
        from assemblyzero.workflows.requirements.audit import make_run_id

        lld_path = state.get("lld_path", "")
        target_repo = state.get("target_repo", "")
        # #1440: Plumb orchestrator config into the sub-workflow state.
        config = state.get("config", {})
        stage_cfg = config.get("stages", {}).get("spec", {})
        gate_enabled = bool(config.get("gates", {}).get("spec", False))

        # Closes #2250: the spec workflow persists drafts and verdicts only when
        # the caller hands it an audit_dir -- it is the one sub-workflow that
        # does not provision its own (requirements does it in load_input,
        # testing in load_lld). The standalone runner sets it; this stage did
        # not, so every orchestrated spec run -- which is every speedrun roll --
        # ended leaving nothing on disk to diagnose. run-issue7-082047 burned
        # three revision iterations and died at the cap; none of its four drafts
        # survives.
        #
        # Run-scoped for the same reason the LLD lineage is (#1467): generate_spec
        # recovers a draft by globbing *-spec-draft.md out of this directory, so
        # an unscoped dir would let a previous roll's draft be recovered into a
        # fresh run and skip the LLM call outright.
        # Lineage is diagnostic scaffolding, so provisioning it must never be
        # the reason a spec stage fails: an unwritable target repo would
        # otherwise be swallowed by the except below and read as a spec
        # failure. On any OSError this degrades to the old behaviour -- no
        # lineage -- and says so, rather than taking the run down with it.
        audit_dir_str = ""
        # is_dir() and not merely truthy: with no repo there, mkdir(parents=True)
        # would conjure the whole tree out of nothing at a path that is not a
        # checkout -- which on Windows means a fake target quietly materialises
        # a real directory off the drive root.
        if target_repo and Path(target_repo).is_dir():
            spec_lineage = (
                Path(target_repo)
                / "docs" / "lineage" / "active"
                / f"{issue_number}-implspec"
            )
            # make_run_id() is second-resolution and shared with the LLD
            # lineage, so two attempts inside one second would land in the same
            # directory -- the exact collision the scoping exists to prevent.
            # Claim the dir with exist_ok=False so the winner is decided by the
            # filesystem rather than by a check that can go stale.
            run_id = make_run_id()
            try:
                for attempt in range(100):
                    candidate = spec_lineage / (
                        run_id if attempt == 0 else f"{run_id}-{attempt}"
                    )
                    try:
                        candidate.mkdir(parents=True, exist_ok=False)
                        audit_dir_str = str(candidate)
                        break
                    except FileExistsError:
                        continue
            except OSError as exc:
                _stages_logger.warning(
                    "Spec stage: could not create lineage dir under %s: %s. "
                    "The stage will run, but its drafts and verdicts will not "
                    "be persisted (#2250).",
                    spec_lineage, exc,
                )

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
            "repo_root": target_repo,
            "assemblyzero_root": state.get("assemblyzero_root", ""),
            # #2250: without this the spec workflow's writes are all no-ops.
            "audit_dir": audit_dir_str,
            # #2033: the tree the implementation will actually be built on. The
            # checkout is on the default branch and mid-arc has none of the arc.
            "base_branch": state.get("base_branch", ""),
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


_MISSING_ROOT_PACKAGE = "the current project could not be installed"


def _provision_worktree_env(worktree_path: Path) -> subprocess.CompletedProcess:
    """Install the target worktree's dependencies, tolerating a not-yet-built package.

    #1904 provisions the worktree so tests run in the TARGET's environment
    rather than AssemblyZero's -- phase 3 of the boostgauge campaign passed on
    AssemblyZero's Pillow and phase 4 died on the target's psutil. That finding
    is about DEPENDENCIES; installing the project's own package is incidental.

    #1994: provisioning runs BEFORE the implementation stage writes any code, so
    on a base that predates the work -- exactly what an idempotent roll requires
    (#1959, #1968, #1986) -- the project package does not exist yet and poetry
    refuses with "No file/folder found for package <name>". The first roll of
    any arc therefore failed to provision.

    So: try the full install, and retry with --no-root ONLY when the failure was
    the absent root package. Where the package does exist it is still installed,
    because that is what makes `import <pkg>` resolve the way the target repo
    expects; dropping it unconditionally would trade a loud failure for a subtle
    one.
    """
    result = run_command(
        ["poetry", "install"],
        cwd=str(worktree_path), check=False, capture_output=True, text=True,
    )
    if result.returncode == 0:
        return result

    combined = f"{result.stdout or ''}\n{result.stderr or ''}".lower()
    if _MISSING_ROOT_PACKAGE not in combined:
        return result

    print(
        "    [ENV] project package not present yet (base predates the code); "
        "retrying with --no-root"
    )
    return run_command(
        ["poetry", "install", "--no-root"],
        cwd=str(worktree_path), check=False, capture_output=True, text=True,
    )


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
            # #1960: name the base explicitly. `worktree add -b X <path>` with
            # no commit-ish branches from whatever the target repo happens to
            # be checked out on, so the content a roll starts from was decided
            # by ambient state — the same trap #1852/#1903 closed for
            # hand-driven branching. base_branch is already resolved upstream
            # (graph.py: the flag, else the target's current branch), so the
            # default behaviour is unchanged; what changes is that passing
            # --base-branch now controls the roll's CONTENT as well as the PR
            # target, and the resolved base is printed rather than implied.
            base_branch = state.get("base_branch", "")
            if base_branch and target_repo:
                # #2011: the pipeline merges on ORIGIN but cuts the worktree from
                # the LOCAL ref, so each phase was built from a base that had not
                # received the previous phase's merge. `fetch origin b:b` is
                # atomic and fast-forward-only, and REFUSES if the branch is
                # checked out anywhere -- which is the correct failure, and why
                # the main checkout must stay on the default branch (#2012).
                sync = run_command(
                    ["git", "-C", target_repo, "fetch", "origin",
                     f"{base_branch}:{base_branch}"],
                    check=False, capture_output=True, text=True,
                )
                if sync.returncode == 0:
                    print(f"    Base synced from origin/{base_branch}")
                else:
                    detail = (sync.stderr or "").strip()[:200]
                    print(f"    [WARN] could not sync {base_branch}: {detail}")
            if not base_branch:
                # current_branch raises GitBranchError on detached HEAD by
                # design (it must not silently fall back to main), and OSError
                # when the path is not a directory git can run in. Resolving the
                # base is an improvement here, not a new failure mode, so a repo
                # it cannot answer for keeps the previous ambient-HEAD behaviour
                # rather than failing the stage.
                try:
                    base_branch = current_branch(target_repo or ".")
                except (GitBranchError, OSError) as err:
                    print(f"    [WARN] base branch unresolved: {err}")
            if base_branch:
                add_cmd.append(base_branch)
                print(f"    Worktree base: {base_branch}")
            else:
                print(
                    "    [WARN] could not resolve a base branch; worktree "
                    "will be carved from the target repo's current HEAD"
                )
            run_command(
                add_cmd,
                check=True,
                capture_output=True,
                text=True,
            )
            # #1780: set upstream at creation so checkpoint pushes work.
            # Without it every [CP:*] push fails until the pr stage's
            # --set-upstream, losing the crash-resilience checkpoints
            # exist for. Non-fatal (offline runs stay possible).
            push_result = run_command(
                ["git", "-C", str(worktree_path), "push", "-u", "origin", branch_name],
                check=False,
                capture_output=True,
                text=True,
            )
            if push_result.returncode != 0:
                print(
                    f"    [WARN] could not push {branch_name} upstream: "
                    f"{(push_result.stderr or '').strip()[:200]}"
                )

            # #1904: provision the worktree's environment. Without this,
            # `poetry run` silently falls through to PATH for missing
            # commands and every test executes in AssemblyZero's venv —
            # phase 3 of the boostgauge campaign passed on AZ's Pillow,
            # phase 4 died on the target's psutil. A failed install is a
            # failed stage, not a warning: tests in the wrong environment
            # are worse than no tests.
            if (worktree_path / "pyproject.toml").is_file():
                print("    [ENV] poetry install (target worktree)...")
                install_result = _provision_worktree_env(worktree_path)
                if install_result.returncode != 0:
                    detail = (
                        (install_result.stderr or "").strip()
                        or (install_result.stdout or "").strip()
                        or "no output"
                    )
                    # #1993: every OTHER exit from this function returns
                    # update_stage_result(...). This one returned a bare stage
                    # result, so `state` -- and with it `issue_number` -- was
                    # gone by the time graph.py persisted it, and the run died
                    # with `KeyError: 'issue_number'` from save_orchestration_state.
                    # The path that exists to REPORT a provisioning failure was
                    # destroying the report and hiding its own cause.
                    return update_stage_result(
                        state,
                        stage,
                        _make_stage_result(
                            status="failed",
                            error_message=(
                                f"Worktree environment provisioning failed "
                                f"(poetry install exit "
                                f"{install_result.returncode}): {detail[:400]}"
                            ),
                            duration_seconds=time.monotonic() - start_time,
                            attempts=1,
                        ),
                    )
                print("    [ENV] worktree environment ready")

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
            # #1941: RESUMED lets the runner reuse a prior attempt's files;
            # REGENERATED forbids it. Absent on a first attempt, which reuses
            # nothing because there is nothing to reuse.
            "retry_mode": state.get("retry_mode", ""),
        })

        error_msg = sub_result.get("error_message", "")
        # #1779: the completeness gate's verdict must survive to the stage
        # result. The gate's stagnation halt routes the sub-workflow to END
        # without setting error_message — run 6 shipped a PR of BLOCKED,
        # untested code under a 'completed successfully' banner. A BLOCK
        # verdict IS a failure: no PR is opened from unverified code; the
        # work-in-progress stays on the pushed branch and in the
        # implementation report for a resume.
        if not error_msg and sub_result.get("completeness_verdict") == "BLOCK":
            issues = sub_result.get("completeness_issues", [])
            issue_lines = "; ".join(
                str(i.get("message", i)) if isinstance(i, dict) else str(i)
                for i in issues[:5]
            )
            error_msg = (
                "Completeness gate BLOCK — implementation halted with "
                f"unresolved issues: {issue_lines or 'see implementation report'}"
            )
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
        # #1873: stderr alone is empty when the git child dies before it can
        # write (the machine-pressure spawn failures of #1872), which left
        # the run record saying only "Git worktree error: ". Carry the
        # command, the exit code, and both streams so a blank-stderr death
        # is still diagnosable from the log.
        detail = (exc.stderr or "").strip() or (exc.stdout or "").strip() or "no output"
        result = _make_stage_result(
            status="failed",
            error_message=(
                f"Git worktree error (exit {exc.returncode}): {detail[:400]} "
                f"[cmd: {' '.join(str(a) for a in exc.cmd) if isinstance(exc.cmd, (list, tuple)) else exc.cmd}]"
            ),
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
        # #1755 attempt-branch model: the PR base is the integration branch
        # captured at pipeline start. Older persisted states predate the
        # key — detect from the target repo then (its checkout is still on
        # the integration branch). Never silently fall back to main.
        base_branch = state.get("base_branch", "")
        if not base_branch:
            base_branch = current_branch(state.get("target_repo", "."))
        pr_result = run_command(
            [
                "gh", "pr", "create",
                "--title", pr_title,
                "--body", pr_body,
                "--base", base_branch,
                "--head", branch,
            ],
            check=True,
            capture_output=True,
            text=True,
            cwd=worktree_path,
        )

        pr_url = pr_result.stdout.strip()
        # #2011: the impl PR was created and then abandoned -- nothing merged it,
        # so the attempt branch received the design and never the code. Record it
        # so the cleanup stage can land it alongside the LLD PR.
        state["impl_pr_url"] = pr_url
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


def _merge_pr(pr_url: str, timeout_s: int, notes: list[str], label: str = "LLD") -> bool:
    """Poll a PR until mergeable, then squash-merge it. Returns True iff merged.

    Closes #1531 for the LLD PR (landing LLD + spec per ADR 0221). #2011 applies
    the same discipline to the IMPLEMENTATION PR, which nothing merged: the arc
    could not accumulate, and every previous "pipeline-built" arc had a human
    merging six impl PRs by hand.

    Bounded by ``timeout_s``; on timeout the PR is left open and reported. No
    ``--admin``, no force -- a PR that will not merge cleanly is a finding.
    """
    deadline = time.monotonic() + max(0, timeout_s)
    last = ""
    while True:
        view = run_command(
            ["gh", "pr", "view", pr_url, "--json", "state,mergeStateStatus",
             "--jq", "[.state, .mergeStateStatus] | @tsv"],
            capture_output=True, text=True,
        )
        if view.returncode == 0:
            cols = (view.stdout or "").strip().split("\t")
            pr_state = cols[0] if cols and cols[0] else ""
            last = cols[1] if len(cols) > 1 else last
            if pr_state == "MERGED":
                return True
            if last == "CLEAN":
                merge = run_command(
                    ["gh", "pr", "merge", pr_url, "--squash"],
                    capture_output=True, text=True,
                )
                if merge.returncode == 0:
                    return True
                notes.append(f"{label} PR merge attempt failed: {(merge.stderr or '').strip()[:160]}")
        else:
            notes.append(f"{label} PR view failed: {(view.stderr or '').strip()[:160]}")
        if time.monotonic() >= deadline:
            notes.append(
                f"{label} PR not merged within {timeout_s}s (last merge-state="
                f"{last or '?'})"
            )
            return False
        time.sleep(15)


def _delete_landed_working_copies(target_repo: str, issue_number: int, notes: list[str]) -> None:
    """Closes #1624. Delete the LLD + spec working-tree copies from the target after
    they have landed on main via the merged LLD PR. Scoped to the LLD and spec
    artifacts only — never ``lld-status.json`` or anything else.
    """
    base = Path(target_repo)
    patterns = [
        f"docs/lld/active/LLD-{issue_number:03d}.md",
        f"docs/lld/active/LLD-{issue_number:03d}-*.md",
        f"docs/lld/active/LLD-{issue_number}.md",
        f"docs/lld/active/LLD-{issue_number}-*.md",
        f"docs/lld/drafts/spec-{issue_number:04d}.md",
        f"docs/lld/drafts/spec-{issue_number:04d}-*.md",
        f"docs/lld/drafts/spec-{issue_number}.md",
        f"docs/lld/drafts/spec-{issue_number}-*.md",
    ]
    matched = set()
    for pat in patterns:
        matched.update(base.glob(pat))
    removed = []
    for p in sorted(matched):
        try:
            if p.is_file():
                p.unlink()
                removed.append(str(p.relative_to(base)))
        except OSError as e:
            notes.append(f"could not delete {p}: {e}")
    if removed:
        notes.append(f"removed landed working-tree copies: {', '.join(removed)}")


def _remove_orchestrator_worktrees(
    target_repo: str, issue_number: int, lld_merged: bool, notes: list[str],
) -> None:
    """Closes #1628. Remove the LLD and impl worktrees the orchestrator created,
    reusing cleanup_helpers (plain ``git worktree remove``, no ``--force``; ``git
    branch -d``, never ``-D``). The impl branch is left intact (its PR is merged by
    the normal review flow); a squash-merged LLD branch that ``-d`` refuses is left
    for ``/cleanup``'s ADR-0217 graft. Worktree-removal failures (dirty worktree)
    are logged as residue, never force-removed.
    """
    from assemblyzero.workflows.requirements.git_operations import lld_worktree_path_for
    from assemblyzero.workflows.testing.nodes.cleanup_helpers import (
        delete_local_branch,
        get_worktree_branch,
        remove_worktree,
    )

    def _remove_with_retry(path, attempts: int = 5, base_delay_s: float = 2.0) -> None:
        # #1781/#1783: Windows file locks from just-finished child processes
        # (Claude CLI implementer sessions, pytest) outlive a flat 3x2s retry
        # — run 7 proved the identical command succeeds minutes later.
        # Exponential backoff: 2s, 4s, 8s, 16s between 5 attempts (~30s
        # total). Never escalate to --force; persistent locks still report
        # honest residue.
        last_exc: Exception | None = None
        for i in range(attempts):
            try:
                remove_worktree(path)
                return
            except Exception as e:  # noqa: BLE001 — re-raised after retries
                last_exc = e
                if i < attempts - 1:
                    time.sleep(base_delay_s * (2 ** i))
        assert last_exc is not None
        raise last_exc

    if target_repo:
        lld_wt = lld_worktree_path_for(target_repo, issue_number)
        if Path(lld_wt).is_dir():
            branch = None
            try:
                branch = get_worktree_branch(lld_wt)
            except Exception:
                branch = None
            try:
                _remove_with_retry(lld_wt)
                notes.append(f"removed LLD worktree {lld_wt}")
                if lld_merged and branch:
                    try:
                        delete_local_branch(branch)
                    except Exception as e:
                        notes.append(f"LLD branch -d left for /cleanup (squash orphan): {e}")
            except Exception as e:
                notes.append(f"LLD worktree not removed (residue left, no --force): {e}")

    impl_wt = worktree_path_for(issue_number, target_repo or None)
    if Path(impl_wt).is_dir():
        try:
            _remove_with_retry(impl_wt)
            notes.append(f"removed impl worktree {impl_wt}")
        except Exception as e:
            notes.append(f"impl worktree not removed (residue left, no --force): {e}")


def run_cleanup_stage(state: OrchestrationState) -> OrchestrationState:
    """Terminal stage (#1531 + #1624 + #1628): merge the LLD PR (landing LLD + spec
    on target main), delete the now-redundant LLD/spec working-tree copies, and
    remove the LLD + impl worktrees.

    Best-effort housekeeping: always returns ``passed`` so a cleanup hiccup never
    fails an otherwise-successful run. Residue is logged and deferred to manual
    ``/cleanup``.
    """
    stage = "cleanup"
    issue_number = state["issue_number"]
    start_time = time.monotonic()

    target_repo = state.get("target_repo", "")
    lld_pr_url = state.get("lld_pr_url", "")
    config = state.get("config", {})
    merge_timeout = config.get("cleanup_merge_timeout_s", 600)
    notes: list[str] = []

    lld_merged = False
    if lld_pr_url:
        lld_merged = _merge_pr(lld_pr_url, merge_timeout, notes, label="LLD")
    else:
        notes.append("no LLD PR URL in state — skipping LLD merge")

    # #2011: land the IMPLEMENTATION PR. This is the step that was missing
    # entirely; without it the attempt branch never receives the code and the
    # next phase of an arc builds against a base that has never seen this one.
    # LLD first, matching the order every previous arc landed in.
    # #2019: decide against what the run actually produced, not against one
    # optional key. `pr_url` is the pr stage's own artifact and a declared
    # field, so when impl_pr_url is missing it still says whether there IS an
    # implementation PR. Treating "no URL" as "nothing to land" is what let a
    # dropped key report green while the arc failed to accumulate.
    impl_pr_url = state.get("impl_pr_url", "")
    pr_stage = state.get("stage_results", {}).get("pr", {})
    pr_stage_produced = pr_stage.get("status") == "passed" and state.get("pr_url", "")
    if not impl_pr_url and pr_stage_produced:
        impl_pr_url = state.get("pr_url", "")
        notes.append(
            f"implementation PR URL was missing from state; recovered the pr "
            f"stage's own artifact ({impl_pr_url})"
        )

    impl_merged = False
    if impl_pr_url:
        impl_merged = _merge_pr(impl_pr_url, merge_timeout, notes, label="impl")
    elif pr_stage_produced:
        # Unreachable via the recovery above, but a pr stage that passed and
        # left nothing landable is a fault, never a quiet pass.
        notes.append("the pr stage passed but no implementation PR can be found")
    else:
        notes.append("the pr stage produced no implementation PR — nothing to land")

    # #1624: only delete the working-tree copies once the content is safely on main.
    if lld_merged and target_repo:
        _delete_landed_working_copies(target_repo, issue_number, notes)

    # #1628: remove the worktrees (LLD branch -d attempted only if its PR merged).
    _remove_orchestrator_worktrees(target_repo, issue_number, lld_merged, notes)

    for note in notes:
        print(f"    [cleanup] {note}")

    # #2011: this stage was documented as best-effort and ALWAYS returned passed,
    # which is the wrong contract for a step the next phase depends on. A cleanup
    # hiccup still passes; an unlanded implementation does not -- that is the run
    # not having landed, and reporting it green is how the gap stayed invisible.
    # #2019: a run whose pr stage produced an implementation PR has landed only
    # when that PR is merged. Only a run that produced none may pass unlanded.
    landed = impl_merged or not (impl_pr_url or pr_stage_produced)
    result = _make_stage_result(
        status="passed" if landed else "failed",
        error_message=(
            "" if landed else
            f"implementation PR was not merged into the attempt branch "
            f"({impl_pr_url or 'URL missing from state'}); the arc cannot "
            f"accumulate without it"
        ),
        artifact_path=impl_pr_url if impl_merged else (lld_pr_url if lld_merged else ""),
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
    "cleanup": run_cleanup_stage,
}
