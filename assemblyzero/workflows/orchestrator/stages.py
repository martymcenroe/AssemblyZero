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
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import NamedTuple

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
from assemblyzero.core.retry_mode import RESUMED
from assemblyzero.core import settlement as settlement_mod

import logging

_stages_logger = logging.getLogger(__name__)

#: Stages a mock run must never enter (#2288). They exist to reach outward --
#: pushing a branch, opening a PR, merging the LLD PR per ADR 0221 -- and none
#: of that has a mock form. The value of a rehearsal is in exercising the graph
#: wiring, not in producing artifacts, and an artifact produced by a rehearsal
#: is worse than none because someone has to work out where it came from.
MOCK_FORBIDDEN_STAGES = ("pr", "cleanup")


def mock_mode(state: OrchestrationState) -> bool:
    """Whether this run is a rehearsal.

    Read from config rather than passed down, because all three sub-workflow
    stages build their sub-state independently and a parameter would have to be
    remembered at each one. It was forgotten at exactly one of them before, and
    that hardcoded ``False`` is what made the spec stage unrehearsable.
    """
    return bool((state.get("config", {}) or {}).get("mock_mode", False))


def fetch_issue_body(target_repo: str, issue_number: int) -> str | None:
    """The rolling issue's body text, or None when it cannot be read.

    Indirected through a module-level function so a test can drive settlement
    without `gh` and without a network. None is a real answer -- it reaches
    `collect_inputs` as an unreadable input and unsettles, which drafts.
    """
    try:
        from assemblyzero.workflows.requirements.precheck import fetch_issue

        _title, body = fetch_issue(Path(target_repo), issue_number)
        return body
    except Exception:
        # fail-open: only in shape -- None unsettles, and unsettled means the
        # stage DRAFTS, which is the pre-#2609 behaviour and the safe
        # direction. A settlement check must never be able to brick a roll.
        return None


def current_inputs(
    state: OrchestrationState, stage: str, existing_artifacts: dict[str, str | None]
) -> list[settlement_mod.SettledInput]:
    """What this stage's derivation currently depends on, hashed (#2609)."""
    target_repo = state.get("target_repo", "") or "."
    issue_number = state["issue_number"]
    upstream_stage = settlement_mod.UPSTREAM_OF.get(stage)
    upstream = existing_artifacts.get(upstream_stage) if upstream_stage else None
    return settlement_mod.collect_inputs(
        target_repo,
        issue_body=fetch_issue_body(target_repo, issue_number),
        upstream_artifact=upstream,
    )


def settlement_status(
    state: OrchestrationState,
    stage: str,
    artifact_path: str,
    existing_artifacts: dict[str, str | None],
) -> tuple[bool, list[str]]:
    """(is_settled, lines). Lines are evidence when settled, mismatches when not.

    A stage with no settlement record is NOT settled, and the caller falls back
    to the pre-#2609 presence check rather than drafting -- an artifact written
    before this feature existed has no record through no fault of its own, and
    treating that as a reason to redraw would regress the very tax #2609 exists
    to remove.
    """
    from assemblyzero.workflows.requirements.audit import load_settlement

    target_repo = Path(state.get("target_repo", "") or ".")
    record = load_settlement(state["issue_number"], stage, target_repo)
    if record is None:
        return (False, ["no settlement record"])

    if not settlement_mod.artifact_matches(record, artifact_path):
        return (False, [
            f"the artifact at {artifact_path} is not the one that settled "
            f"(recorded {str(record.get('artifact_sha256'))[:12]})"
        ])

    inputs = current_inputs(state, stage, existing_artifacts)
    mismatches = settlement_mod.verify(record, inputs)
    if mismatches:
        return (False, mismatches)
    return (True, settlement_mod.evidence_lines(record, inputs))


def should_skip_stage(
    state: OrchestrationState,
    stage: str,
    existing_artifacts: dict[str, str | None],
) -> tuple[bool, str | None]:
    """Determine if a stage should be skipped.

    Returns (should_skip, artifact_path).

    impl and pr stages are never skipped.

    #2609: presence alone used to be the whole test, which failed in both
    directions. An artifact whose source issue had since been edited was reused
    silently, and an artifact whose file cleanup had deleted after its PR merged
    was redrawn even though the ruling it embodied had not changed. Settlement
    decides both: a settled artifact is reused with its hash evidence printed,
    and an input change unsettles it by name.
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
    if not validate_artifact(path, stage):
        return (False, None)

    if stage in settlement_mod.SETTLEABLE_STAGES:
        settled, lines = settlement_status(
            state, stage, artifact_path, existing_artifacts
        )
        if settled:
            print(f"    [{stage}] settled and reused -- no drafter spend")
            for line in lines:
                print(f"    [{stage}] {line}")
            return (True, artifact_path)
        if lines != ["no settlement record"]:
            print(f"    [{stage}] unsettled -- redrawing:")
            for line in lines:
                print(f"    [{stage}]   {line}")
            return (False, None)

    return (True, artifact_path)


def settle_stage(
    state: OrchestrationState, stage: str, artifact_path: str, verdict: str = ""
) -> None:
    """Record ``stage``'s artifact as settled, having just passed its gate.

    Called only on a passed result. Best-effort by design: a settlement that
    cannot be written costs the next launch a redraw, which is the pre-#2609
    behaviour, and must never turn a stage that genuinely passed into a
    failure.
    """
    if stage not in settlement_mod.SETTLEABLE_STAGES or not artifact_path:
        return
    try:
        from assemblyzero.workflows.requirements.audit import save_settlement

        target_repo = Path(state.get("target_repo", "") or ".")
        existing = detect_existing_artifacts(
            state["issue_number"], state.get("target_repo", "")
        )
        record = settlement_mod.build_settlement(
            stage,
            artifact_path,
            current_inputs(state, stage, existing),
            verdict=verdict,
        )
        save_settlement(state["issue_number"], stage, record, target_repo)
        print(
            f"    [{stage}] settled: artifact "
            f"{str(record['artifact_sha256'])[:12]}, "
            f"{len(record['inputs'])} input(s) fingerprinted"
        )
    except Exception as exc:
        # fail-open: a stage that passed its gate stays passed. Losing the
        # record costs one redraw next launch; failing the stage would discard
        # work that was already certified.
        print(f"    [{stage}] settlement not recorded ({exc})")


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
    notes: list[str] | None = None,
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
    if notes:
        # #2608: only when there is something to say. An empty key on every
        # result would put a blank NOTES section under every run record and
        # train the reader to skip the one that matters.
        result["notes"] = list(notes)
    return result


def _declared_fallthroughs(sub_result: dict) -> list[str]:
    """Protections a sub-workflow deliberately sat out, for the run record.

    #2608: run-issue331-093613 passed the spec stage with the #2533
    assertion-manifest protection switched off, and the stage table said
    only "passed". A declared fall-through is survivable by design -- that
    is what makes it declared -- but it must reach the record, or a green
    row means two different things and the reader cannot tell which.
    """
    notes: list[str] = []
    if sub_result.get("assertion_manifest_abstained"):
        reason = sub_result.get("assertion_manifest_absence_reason", "")
        notes.append(
            f"assertion manifest ABSTAINED ({reason}) — the #2533 "
            f"protection did not run for this stage (#2608)"
        )
    return notes


def _unresolved_test_failures(sub_result: dict) -> int:
    """Failing tests the implementation loop ended holding (#2344).

    Reads the last green-phase measurement the sub-workflow recorded. Returns
    0 when the run finished clean, when it never measured, or when the state
    cannot answer -- this must never invent a failure and turn a genuine pass
    into a spurious halt.

    Two keys, because a clean targeted run is not the same as a clean repo:

    - `previous_green_failures` -- the identity set from the last N5. Preferred
      over a parsed count because it is what the loop's own stagnation and
      freeze decisions are made from, so the verdict follows the set the loop
      actually acted on.
    - `full_suite_regressions` -- the #842 full-suite gate. Its return sets
      `previous_green_failures` to `[]` while carrying regression names and an
      empty error_message, so checking only the first would let a regressed
      repo through the same cap-and-report-passed hole this closes.

    Both are reset to empty on every genuine success path, so a passing run
    still reports passed.
    """
    total = 0
    for key in ("previous_green_failures", "full_suite_regressions"):
        value = sub_result.get(key)
        if isinstance(value, (list, tuple, set)):
            total += len(value)
    return total


def _phases_not_run(sub_result: dict) -> str:
    """Which TDD phases produced no output, named in the halt text (#2677).

    "Ended without reaching finalize" says a route was not taken. This says
    what was not DONE, which is the part an operator reading `impl passed
    3.5s` needed and did not get: on run-issue384-044442 the red phase, the
    implementation loop, the green phase and the regression check had all
    never run, and nothing in the stage table showed it.

    Reports only phases with NO recorded output. A phase that ran and failed
    is a different fact and is already named by the checks above.
    """
    phases = (
        ("red phase", "red_phase_output"),
        ("implementation", "implementation_files"),
        ("green phase", "green_phase_output"),
    )
    missing = [label for label, key in phases if not sub_result.get(key)]
    if not missing:
        return "Every phase produced output, so the workflow stopped after them."
    return f"Never ran: {', '.join(missing)}."


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
        # #2298: a missing required input is deterministic — the file an
        # upstream stage should have produced is absent, and running this stage
        # again cannot conjure it. It was retried three times 0.1s apart on the
        # 2026-08-13 roll, each attempt printing a full banner about a failure
        # the operator had already been told about.
        from assemblyzero.workflows.testing.nodes.load_lld import (
            MISSING_REQUIRED_INPUT,
        )

        if MISSING_REQUIRED_INPUT.lower() in message:
            return False
        # #2337: same rule, different cause. Green-at-red on an unchanged
        # worktree is deterministic -- attempts 2 and 3 of run-issue7-192332
        # reproduced attempt 2's outcome exactly, twelve seconds apart.
        from assemblyzero.workflows.testing.nodes.verify_phases import (
            DETERMINISTIC_FAILURE,
        )

        if DETERMINISTIC_FAILURE.lower() in message:
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

        # #2245: this stage passed no config at all, so every orchestrated roll
        # took LangGraph's default of 25 super-steps by accident -- and a run
        # that spent its loops raised GraphRecursionError, which names no stage,
        # no loop and no document. The budget is derived from the loop costs and
        # the caps that bound them; exhausting it now halts with what consumed
        # it.
        from assemblyzero.workflows.requirements.step_budget import invoke_with_budget

        graph = create_requirements_graph()
        app = graph.compile()
        sub_result = invoke_with_budget(app, {
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
            "config_mock_mode": mock_mode(state),
            "previous_draft_path": previous_draft_path,
            "previous_verdict_text": previous_verdict_text,
        }, stage="lld")

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
                # #2609: the artifact passed its gate. Settle it, so the next
                # launch reuses this ruling instead of re-deriving it.
                settle_stage(state, stage, lld_path, review_verdict)
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

    # #2301: ask the TARGET repo whether it wants this path tracked before
    # trying to add it. boostgauge gitignores docs/lineage, so every roll
    # printed "git add failed (non-fatal)" — a failure line for a repo doing
    # exactly what it configured. Whether lineage is tracked differs by repo,
    # and the repo's own ignore rules are the authority; log noise is what
    # buries real failures.
    ignored = run_command(
        ["git", "check-ignore", "-q", str(rel)], cwd=str(worktree),
        capture_output=True, text=True,
    )
    if ignored.returncode == 0:
        print(
            f"    [spec] {rel.as_posix()} is gitignored in this repo — not "
            f"riding it on the LLD PR. The spec stays on the working tree."
        )
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


def _record_spec_convergence_failure(
    target_repo: str,
    issue_number: int,
    sub_result: dict,
    elapsed: float,
    stage_cfg: dict,
) -> None:
    """One telemetry record when the spec stage burns its budget on REVISE.

    Closes #2198. Standard 0025's loop can only fix what it can rank, and it
    ranked nothing from spec land: on boostgauge the failure table held 24
    fingerprints and every one was `lld:*`, while the spec stage's most
    expensive failure mode -- 685 seconds of drafting and three review rounds
    all objecting to the same thing -- left no record at all.

    A REVISE verdict that survives to the end of the sub-workflow IS the
    convergence failure: a REVISE with budget left routes back to the drafter
    and never terminates the run.

    Recorded here rather than in the reviewer node because this is where the
    stage's wall clock exists, which is the cost the ranking needs. Never
    raises -- telemetry that can break the thing it measures is worse than no
    telemetry (the module's own rule).
    """
    if sub_result.get("review_verdict") != "REVISE":
        return

    try:
        from assemblyzero.speedrun.must_resolve import run_context
        from assemblyzero.speedrun.prompt_telemetry import (
            rankable_detail,
            record_failure,
        )

        detail = rankable_detail(
            sub_result.get("review_feedback", "")
            or sub_result.get("error_message", "")
        )
        if not detail:
            return

        run_id, _ = run_context()
        record_failure(
            target_repo or ".",
            stage="spec",
            check="reviewer-revise",
            detail=detail,
            issue=issue_number or None,
            drafter_model=stage_cfg.get("drafter", ""),
            run_id=run_id,
            duration_seconds=round(elapsed, 1),
        )
    except Exception as exc:  # noqa: BLE001 - telemetry never breaks a stage
        _stages_logger.warning("Spec convergence telemetry skipped: %s", exc)


def run_visual_stage(state: OrchestrationState) -> OrchestrationState:
    """The visual gate (#2518): the eyeball artifact before the spec spends.

    Applies only when the TARGET repo declares a visual gate
    (docs/design/visual-gate.json) naming this issue; every other roll skips
    in milliseconds. When it applies: render the contract, serve the picture
    on localhost, halt resumably for the operator's Approve / Reject /
    Modify. The console and the detached launcher log both carry the URL --
    run_gate prints it through this stage's stdout, which the launcher tees.

    Halts are non-transient by construction: every halt here is either the
    operator's own verb (Reject), a ruling contradiction awaiting the
    operator, or an unrenderable contract awaiting a doc fix -- none of which
    a blind retry can answer, and a retry would re-serve the page to nobody.
    """
    stage = "visual"
    issue_number = state["issue_number"]
    start_time = time.monotonic()
    target_repo = Path(state.get("target_repo", ""))

    from assemblyzero.visual_gate.config import gate_applies, load_gate_config

    try:
        gate_config = load_gate_config(target_repo)
    except (ValueError, json.JSONDecodeError) as exc:
        # fail-open: in shape only -- the handler substitutes a FAILED,
        # non-transient stage result naming the broken declaration, which is
        # this pipeline's halt idiom (a raise would crash the graph instead
        # of halting it). A repo that declared a gate and then broke the
        # declaration must not silently roll ungated (#2518; #2475).
        result = _make_stage_result(
            status="failed",
            error_message=(
                f"visual-gate declaration unreadable "
                f"(docs/design/visual-gate.json): {exc}"
            ),
            duration_seconds=time.monotonic() - start_time,
            attempts=1,
            transient=False,
        )
        return update_stage_result(state, stage, result)

    if not gate_applies(gate_config, issue_number):
        result = _make_stage_result(
            status="skipped",
            artifact_path="",
            error_message=(
                "no visual deliverable declared for this issue"
                if gate_config else "repo declares no visual gate"
            ),
            duration_seconds=time.monotonic() - start_time,
            attempts=0,
        )
        return update_stage_result(state, stage, result)

    from assemblyzero.visual_gate.gate import run_gate

    outcome = run_gate(
        target_repo, issue_number, gate_config, mock=mock_mode(state),
    )
    if outcome.status == "approved":
        result = _make_stage_result(
            status="passed",
            artifact_path=outcome.artifact_path,
            duration_seconds=time.monotonic() - start_time,
            attempts=1,
        )
        return update_stage_result(state, stage, result)

    result = _make_stage_result(
        status="failed",
        error_message=f"visual gate halted: {outcome.error}",
        duration_seconds=time.monotonic() - start_time,
        attempts=1,
        transient=False,
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
        # #2382: this stage passed no config at all, so it silently took
        # LangGraph's default of 25 super-steps. A converging review loop may
        # now run past the base cap, and without a derived budget it would hit
        # GraphRecursionError -- an error naming no stage, no loop and no
        # document -- instead of the halt that says which exit fired. Same
        # failure #2245 removed from the requirements graph.
        from assemblyzero.workflows.implementation_spec.spec_step_budget import (
            recursion_limit as spec_recursion_limit,
        )

        spec_max_iterations = int(stage_cfg.get("max_revisions", 3) or 3)

        # #2383: a resume used to restart at iteration 0 with a fresh draft,
        # discarding every round already paid for -- because each run claims a
        # NEW run-scoped lineage dir and generate_spec recovers a draft by
        # globbing the dir it was handed, which is empty. Seed the loop from the
        # last run instead: its final draft, its final verdict's outstanding
        # items, and every verdict it produced so #2382's convergence check is
        # not blind on the resumed round.
        #
        # Keyed on an actual resume. Whether resuming is appropriate was already
        # decided upstream -- resume_plan refuses a resume whose draft predates
        # an issue edit or binding-doc change, and --fresh skips planning
        # entirely; both express themselves as no --resume-from arriving here.
        seed = None
        if state.get("resumed_from") == "spec" and audit_dir_str:
            from assemblyzero.workflows.implementation_spec.lineage_seed import (
                describe as describe_seed,
                seed_from_lineage,
            )

            seed = seed_from_lineage(
                Path(audit_dir_str).parent, exclude=Path(audit_dir_str)
            )
            if seed:
                print(describe_seed(seed))
            else:
                print(
                    "    [spec] resume found no prior draft-and-verdict pair "
                    "in lineage; drawing fresh."
                )

        # #2516: the payload seeds the paid draft, the final verdict's items
        # (so the first regeneration starts from the reviewer's last word),
        # the full cross-grant feedback history for #2382's stagnation check
        # -- and a review counter at ZERO, per the #2514 ruling that each
        # explicit relaunch grants one fresh cap regime. Seeding the prior
        # grant's counter made the first resumed round illegal by
        # construction (iteration 10 > ceiling 9, run-issue331-102255).
        from assemblyzero.workflows.implementation_spec.lineage_seed import (
            resume_payload,
        )

        resumed_payload = resume_payload(seed) if seed else {}

        app = create_spec_graph()
        sub_result = app.invoke({
            **resumed_payload,
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
            # #2288: was a hardcoded False, so the spec stage could not be
            # rehearsed and every change to it was first executed by the roll
            # it was meant to protect.
            "config_mock_mode": mock_mode(state),
            "human_gate_enabled": gate_enabled,
            "max_iterations": spec_max_iterations,
        }, config={"recursion_limit": spec_recursion_limit(spec_max_iterations)})

        spec_path = sub_result.get("spec_path", "")
        # #2297: the stage verdict is the workflow's OWN explicit status, not an
        # inference from an artifact existing. A cap-halted run was recorded as
        # `passed` because generate_spec wrote each draft's audit path into
        # `spec_path` and the file was really there -- so the roll proceeded to
        # impl on a spec that was never finalized, and the true failure was
        # buried five screens up. `halted` is authoritative and refuses the
        # stage even if an artifact is present.
        workflow_status = str(sub_result.get("workflow_status", ""))
        halted = workflow_status == "halted"
        if not halted and spec_path and Path(spec_path).is_file():
            # Closes #1625: the spec is a permanent artifact paired with the LLD;
            # ride it on the LLD PR so it lands on target main (ADR 0221). The
            # working-tree copy stays for the impl stage to read; the terminal
            # cleanup removes it after the LLD PR merges.
            # #2288: the spec is written either way -- that is the part a
            # rehearsal exercises. Riding it onto the LLD PR is a commit and a
            # push, so a mock run stops short of it.
            if mock_mode(state):
                print(
                    f"    [mock] spec written to {spec_path}; not committed "
                    f"and not pushed to the LLD PR."
                )
            else:
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
                notes=_declared_fallthroughs(sub_result),
            )
            # #2609: the spec passed its gate. Its inputs include the upstream
            # settled LLD, so editing the LLD unsettles the spec derived from it.
            settle_stage(state, stage, spec_path)
        else:
            error_msg = sub_result.get("error_message", "")
            if not error_msg:
                error_msg = (
                    "Spec workflow halted before finalizing"
                    if halted
                    else "Spec workflow completed but no artifact produced"
                )
            elapsed = time.monotonic() - start_time
            _record_spec_convergence_failure(
                target_repo, issue_number, sub_result, elapsed, stage_cfg,
            )
            result = _make_stage_result(
                status="failed",
                error_message=error_msg,
                duration_seconds=elapsed,
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


class _LeftoverBranch(NamedTuple):
    """What a pre-existing pipeline branch holds, for #2310's decision.

    `absent` is the ordinary case and is neither reusable nor divergent, so
    the caller falls through to the normal `worktree add -b` path.
    """

    absent: bool
    reusable: bool
    divergent: bool
    unique_commits: int | None

    def describe_unique(self) -> str:
        if self.unique_commits is None:
            return "commits"
        return f"{self.unique_commits} commit(s)"


def _classify_leftover_branch(
    target_repo: str, branch_name: str, base_branch: str,
) -> _LeftoverBranch:
    """Decide whether an existing `branch_name` may be adopted by this roll.

    #2310: `git worktree add -b X` fails with a bare `fatal: a branch named
    'X' already exists` when a previous failed roll left the name standing.
    The measured case was pointer-identical to the base with zero unique
    commits -- a name squatting on the exact SHA the new run wanted, killing
    a roll for nothing. That case is safe to adopt. A branch holding commits
    of its own is NOT this roll's to reuse or delete, and gets a halt naming
    what it holds instead of an exit 255.

    Every git failure here resolves to "not reusable, not divergent", so an
    unreadable repo keeps the previous behaviour rather than inventing a new
    failure mode.
    """
    def _git(*args: str) -> subprocess.CompletedProcess:
        cmd = ["git"]
        if target_repo:
            cmd += ["-C", target_repo]
        return run_command(
            [*cmd, *args], check=False, capture_output=True, text=True,
        )

    absent = _git(
        "show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}",
    ).returncode != 0
    if absent:
        return _LeftoverBranch(True, False, False, None)

    if not base_branch:
        # Nothing to compare against: cannot prove it is safe to adopt, and
        # cannot prove it diverges. Let git speak, as before.
        return _LeftoverBranch(False, False, False, None)

    counted = _git(
        "rev-list", "--count", f"{base_branch}..{branch_name}",
    )
    if counted.returncode != 0:
        return _LeftoverBranch(False, False, False, None)
    try:
        unique = int(counted.stdout.strip())
    except ValueError:
        return _LeftoverBranch(False, False, False, None)

    return _LeftoverBranch(
        absent=False,
        reusable=unique == 0,
        divergent=unique > 0,
        unique_commits=unique,
    )


#: A graveyard branch holding one prior implementation attempt for one issue.
#: Anchored on both ends so `issue-4` never matches `issue-41`'s graves, and
#: so the hand-made names in a long-lived campaign repo -- `graveyard/arc1-issue-4`,
#: `graveyard/run11-roll10-issue-4` -- are not mistaken for the machinery's own
#: (#2845). The stamp is `_disposal_stamp()`'s, which sorts.
_GRAVEYARD_ATTEMPT = re.compile(r"^graveyard/issue-(\d+)-(\d{8}T\d{6}Z)$")


def _recoverable_attempt_branch(
    target_repo: str, issue_number: int, base_branch: str,
) -> tuple[str, int] | None:
    """The newest preserved attempt for #issue worth resuming from, or None.

    #2845: RESTORE removes the implementation worktree on every exit (#2005),
    so `verify_phases._restore_best`'s snapshot of the best iteration dies
    with it. What survives is the attempt branch, renamed under `graveyard/`
    by the #2310 disposal discipline. On boostgauge run 15 that branch held
    the whole 48-of-52-passing implementation -- eight files, 1,356 lines,
    across a post-scaffold and five post-impl checkpoints -- and the resume
    that followed carved a worktree from the base and implemented from zero,
    repaying two and a half hours of paid work for nothing.

    Two conditions, both measured, before an attempt is offered back:

    * `base_branch` is an ANCESTOR of it. That is what proves the attempt was
      cut from the base this run is rolling on. A grave from an earlier phase,
      or from before the base moved, fails the test and is left alone --
      resuming stale work is worse than an honest start from zero, so the
      unprovable case falls through to the ordinary path.
    * it carries commits the base does not. A grave with nothing unique has
      nothing to give back; `dispose_pipeline_branches` should not have made
      one, and if it did, it is not this function's to resurrect.

    Every git failure resolves to None, so an unreadable repo keeps the
    previous behaviour rather than inventing a new one.
    """
    if not base_branch:
        return None

    def _git(*args: str) -> subprocess.CompletedProcess:
        cmd = ["git"]
        if target_repo:
            cmd += ["-C", target_repo]
        return run_command(
            [*cmd, *args], check=False, capture_output=True, text=True,
        )

    listed = _git(
        "branch", "--list", "--format=%(refname:short)",
        f"graveyard/issue-{issue_number}-*",
    )
    if listed.returncode != 0:
        return None

    candidates: list[tuple[str, str]] = []
    for line in listed.stdout.splitlines():
        branch = line.strip()
        match = _GRAVEYARD_ATTEMPT.match(branch)
        # `--list` globs, so `issue-4-*` also matches `issue-41-...`. The
        # captured number is compared, never the glob's word.
        if match and int(match.group(1)) == issue_number:
            candidates.append((match.group(2), branch))

    # Newest disposal first: the stamp is UTC and fixed-width, so it sorts.
    for _stamp, branch in sorted(candidates, reverse=True):
        if _git(
            "merge-base", "--is-ancestor", base_branch, branch,
        ).returncode != 0:
            continue
        counted = _git("rev-list", "--count", f"{base_branch}..{branch}")
        if counted.returncode != 0:
            continue
        try:
            unique = int(counted.stdout.strip())
        except ValueError:
            # fail-open: an unmeasurable candidate is skipped, and a run out
            # of candidates starts the implementation from the base -- which
            # is exactly what every resume did before #2845. The failure
            # direction that matters here is the opposite one: resurrecting a
            # grave whose ancestry could not be established would build on a
            # tree the campaign has moved off, silently. Declining is visible
            # in the log ("No preserved attempt ... is resumable") and costs
            # only the rebuild that was the status quo.
            continue
        if unique > 0:
            return branch, unique
    return None


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
    # #2845: set only when this entry carved the worktree from a preserved
    # attempt. Declared out here because a worktree that already exists skips
    # the creation block entirely and still reaches the sub-workflow invoke.
    recovered_branch = ""

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

            # #2845: a RESUME into the implementation stage starts from the
            # best state the halted attempt reached, not from the base. That
            # state is on the graveyard branch RESTORE preserved; without
            # this, the resume rebuilds from zero and repays the whole stage.
            # Only on a resume -- a fresh draw (`--fresh`, or any first run)
            # must start from the base, which is what `resumed_from` being
            # empty means (#2383 makes that field explicit on both paths).
            if state.get("resumed_from") == "impl":
                recovered = _recoverable_attempt_branch(
                    target_repo, issue_number, base_branch,
                )
                if recovered:
                    recovered_branch, recovered_commits = recovered
                    print(
                        f"    Resuming from preserved attempt "
                        f"{recovered_branch} ({recovered_commits} commit(s) "
                        f"beyond {base_branch})"
                    )
                    # Replaces the base as the worktree's commit-ish. `-b
                    # issue-{N}` still creates the branch, so everything
                    # downstream -- checkpoints, the pr stage's head, the
                    # #2310 disposal -- is unchanged. The base was appended
                    # just above and is the last argument; it is matched
                    # rather than indexed, so a future edit to the argument
                    # order cannot silently retarget the worktree.
                    if add_cmd and add_cmd[-1] == base_branch:
                        add_cmd[-1] = recovered_branch
                    else:
                        add_cmd.append(recovered_branch)
                else:
                    print(
                        f"    No preserved attempt for #{issue_number} is "
                        f"resumable from '{base_branch}'; starting the "
                        f"implementation from the base"
                    )

            # #2310: a previous failed roll can leave `issue-{N}` standing.
            # `worktree add -b` then dies with a bare `fatal: a branch named
            # 'issue-7' already exists` (exit 255), which killed a roll whose
            # spec stage had just passed for the first time in campaign
            # history. Decide from what the leftover actually holds, before
            # git gets the chance to fail uninformatively.
            leftover = _classify_leftover_branch(
                target_repo, branch_name, base_branch,
            )
            if leftover.divergent:
                raise RuntimeError(
                    f"branch '{branch_name}' already exists and carries "
                    f"{leftover.describe_unique()} not on "
                    f"'{base_branch or 'the base'}'. It is not this roll's to "
                    f"reuse or delete. Preserve it under graveyard/ (a rename "
                    f"keeps every commit and frees the name), then relaunch."
                )
            if leftover.reusable:
                # Pointer-identical to the base: nothing to lose by adopting
                # it, and adopting is what keeps the relaunch alive. Rebuild
                # the command in the `worktree add <path> <existing-branch>`
                # form -- `-b` would try to create it again and fail.
                print(
                    f"    Reusing leftover branch '{branch_name}' "
                    f"(pointer-identical to {base_branch or 'the base'})"
                )
                if recovered_branch:
                    # #2845: adopting the leftover means the worktree starts
                    # at the base after all, so the preserved attempt is not
                    # in play. Said out loud rather than dropped in silence:
                    # the run is about to implement from zero and the log
                    # must be the reason it can be told from a recovery.
                    # Disposal (#2310) safe-deletes a zero-unique
                    # `issue-{N}`, so reaching here at all means a previous
                    # RESTORE did not finish.
                    print(
                        f"    [WARN] preserved attempt {recovered_branch} "
                        f"NOT used: '{branch_name}' is still standing from "
                        f"an earlier roll, and adopting it starts from the "
                        f"base. Preserve or free that name to resume from "
                        f"the attempt."
                    )
                    recovered_branch = ""
                add_cmd = ["git"]
                if target_repo:
                    add_cmd += ["-C", target_repo]
                add_cmd += ["worktree", "add", str(worktree_path), branch_name]

            run_command(
                add_cmd,
                check=True,
                capture_output=True,
                text=True,
            )
            # #1780 pushed the branch here to set an upstream, so that
            # checkpoint pushes would work. #2339 removed it, because
            # checkpoints no longer push.
            #
            # The push was the first line of run-issue7-192332 and it was
            # rejected: origin/issue-7 was a stale remote branch from an
            # earlier run, diverged from the new local one. No upstream was
            # set, so all four [[CP:*]] checkpoints then failed the same way
            # and each printed git's four-line set-upstream advice into the
            # run log.
            #
            # The operator's ruling: checkpoints are local crash resilience
            # and do not push. The evidence for it is in that same incident.
            # Every checkpoint commit survived without ever reaching origin,
            # preserved on graveyard/issue-7-20260814T002812Z by the #2310
            # disposal discipline, and that local chain is the only reason
            # the post-mortem had anything to measure.
            #
            # Nothing here needs a remote, so nothing here reconciles one.
            # The pr stage pushes the branch, and that push is the run's
            # product; its own stale-remote reconcile landed in #2349.

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
        # #2790: this stage spent no step budget, so its ceiling was
        # LangGraph's default of 10007 -- ten thousand super-steps, in a stage
        # where a super-step can be a model call, ending on an exception with
        # no gate key. The budget is derived from the stage's own caps.
        from assemblyzero.workflows.testing.step_budget import (
            recursion_limit as impl_recursion_limit,
        )
        from assemblyzero.workflows.testing.state import DEFAULT_MAX_ITERATIONS

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
            #
            # #2845: a worktree carved from a preserved attempt IS a later
            # attempt, and must say so, or the red phase reads the surviving
            # implementation as green-at-red and halts the stage as fatal --
            # `_implementation_already_exists` consults no other signal on a
            # sub-workflow entering fresh, with retry_mode empty and
            # iteration_count zero. The recovery would otherwise turn a
            # from-zero rebuild into a halt, which is worse than the defect
            # it fixes.
            "retry_mode": RESUMED if recovered_branch else state.get("retry_mode", ""),
            # #2344: seed the iteration cap explicitly. Left absent, each
            # reader fell back to its own inline default -- 5 in N5's progress
            # message, 3 in the router's decision -- so the run announced a
            # budget it did not have and a freeze's loop-back was dropped at 3
            # without a word.
            "max_iterations": DEFAULT_MAX_ITERATIONS,
            "config_mock_mode": mock_mode(state),
        }, config={"recursion_limit": impl_recursion_limit(DEFAULT_MAX_ITERATIONS)})

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
        # #2344: a verdict must be MEASURED, not inferred from silence.
        #
        # run-issue7-231606 ended with `31 passed, 1 failed` as its last N5
        # result and recorded impl as PASSED. Nothing lied: N5's freeze branch
        # correctly returned an empty error_message because it was routing to
        # another revision, not failing. The router then hit the iteration cap
        # and returned "end" without a word, so the empty error survived to
        # here and "no error" was read as "tests pass".
        #
        # This is the #2297 verdict-integrity class, and #1779's shape: a
        # stage reporting success without checking the thing it exists to
        # check. The pr stage would have pushed and opened a PR on a branch
        # whose suite fails.
        if not error_msg:
            unresolved = _unresolved_test_failures(sub_result)
            if unresolved:
                error_msg = (
                    f"Implementation stage ended with {unresolved} failing "
                    f"test(s) and no further revision available. The last "
                    f"green-phase measurement did not pass, so the stage did "
                    f"not pass."
                )

        # #2677: COMPLETION MUST BE AS EXPLICIT AS FAILURE.
        #
        # Every check above this line is a negative: it names one way the
        # sub-workflow can end badly while leaving `error_message` empty.
        # #1779 added the BLOCK verdict after one escape and #2344 added
        # unresolved failures after another, and run-issue384-044442 found a
        # third -- the testing workflow stopped at N2.5 on an exhausted
        # scaffolder, said nothing, and the stage recorded `impl passed 3.5s`
        # with the red phase, the implementation loop, the green phase and the
        # regression check all never run. A PR carrying an assertion-free stub
        # and no code was opened and merged from that verdict.
        #
        # Enumerating failures cannot terminate: any new END that forgets to
        # set an error re-creates the class. So the stage asks the workflow to
        # SAY it finished. `workflow_status` is set in exactly one place, N7
        # finalize, which is reached only after the green phase has passed --
        # every other route to END is a failure, a halt, or `scaffold_only`,
        # which the orchestrator never sets. This is #2297's halted-is-
        # authoritative reading in the positive direction.
        if not error_msg and sub_result.get("workflow_status") != "completed":
            error_msg = (
                "Testing workflow ended without reaching N7 finalize, so the "
                "implementation stage did not pass. "
                + _phases_not_run(sub_result)
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


#: #2346: a non-fast-forward rejection cannot change between attempts. Same
#: rule as #2298/#2337, pr-stage edition -- the remote's divergence is not
#: something re-running the push can resolve.
NON_FAST_FORWARD = "non-fast-forward"


def _reconcile_stale_remote_branch(worktree_path, branch: str) -> str:
    """Clear a same-name remote branch out of the push's way (#2346).

    Returns a description of what was done, or '' when nothing was needed.

    Three cases, decided by measurement rather than assumption:

    - the remote branch does not exist -> nothing to do
    - it is an ANCESTOR of what we are about to push -> the push
      fast-forwards, so leave it alone
    - it has DIVERGED -> preserve it under `graveyard/<branch>-<stamp>` on the
      remote and delete the old name, so the push is clean

    Preserve-and-rename, never force-push: the same discipline #2310/#2324
    settled for local branches, which exists because a name in the way is not
    a reason to destroy whatever is standing on it. A remote rename is a push
    of the same commit under a new ref followed by a delete of the old ref, so
    nothing is ever unreachable in between.

    Best-effort by design. Every git failure returns '' and lets the push
    proceed to fail on its own terms -- a reconcile that cannot read the
    remote must not invent a destructive action, and the push's own error is
    a better diagnosis than anything guessed here.
    """
    from datetime import datetime, timezone

    def _git(*args: str):
        return run_command(
            ["git", *args], check=False, capture_output=True, text=True,
            cwd=worktree_path,
        )

    fetched = _git("fetch", "origin", branch)
    if fetched.returncode != 0:
        # No such branch on origin (or the remote is unreachable). Either way
        # there is nothing to reconcile; the push will say so if it matters.
        return ""

    remote_tip = _git("rev-parse", "FETCH_HEAD")
    local_tip = _git("rev-parse", "HEAD")
    if remote_tip.returncode != 0 or local_tip.returncode != 0:
        return ""
    remote_sha = remote_tip.stdout.strip()
    if not remote_sha or remote_sha == local_tip.stdout.strip():
        return ""

    if _git("merge-base", "--is-ancestor", remote_sha, "HEAD").returncode == 0:
        return ""  # fast-forwardable; the ordinary push handles it

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    parked = f"graveyard/{branch}-{stamp}"
    if _git("push", "origin", f"{remote_sha}:refs/heads/{parked}").returncode != 0:
        return ""  # could not preserve it, so do not delete it

    if _git("push", "origin", f":refs/heads/{branch}").returncode != 0:
        return (
            f"stale origin/{branch} preserved as {parked}, but the old name "
            f"could not be removed; the push may still be rejected"
        )
    return (
        f"stale origin/{branch} ({remote_sha[:8]}) had diverged — preserved "
        f"as {parked} and cleared; nothing was force-pushed"
    )


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

        # #2346: a same-name branch left on origin by an earlier run makes this
        # push fail non-fast-forward, and run-issue7-231606 died there on the
        # first pr stage the campaign ever reached. #2310/#2324/#2325 taught
        # RESTORE this discipline for the LOCAL branch; origin never learned
        # it, so leftovers outlive every run and collide with the next.
        reconcile_note = _reconcile_stale_remote_branch(worktree_path, branch)
        if reconcile_note:
            print(f"    {reconcile_note}")

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
        stderr = exc.stderr or ""
        # #2346: a rejected push is deterministic -- the remote's divergence
        # is not something another attempt can resolve. run-issue7-231606
        # spent three attempts on one, ten seconds apart. Reconciliation above
        # should now prevent it; this is the guard for when it cannot (a
        # protected ref, a permissions failure, a race with another push).
        deterministic = NON_FAST_FORWARD in stderr.lower()
        result = _make_stage_result(
            status="failed",
            error_message=f"PR creation error: {stderr}",
            duration_seconds=time.monotonic() - start_time,
            attempts=1,
            transient=False if deterministic else None,
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
    "visual": run_visual_stage,
    "spec": run_spec_stage,
    "impl": run_impl_stage,
    "pr": run_pr_stage,
    "cleanup": run_cleanup_stage,
}
