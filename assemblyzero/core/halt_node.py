"""Generic HALT node factory for LangGraph workflows.

Issue #486: Halt-and-Plan pattern — self-babysitting workflows.

Creates a LangGraph-compatible node that:
1. Saves full workflow state to disk
2. Classifies the error from state["error_message"]
3. Generates a structured recovery plan
4. Prints a human-readable summary
5. Returns paths for downstream consumption

#2197: a halt that reports "Error: unknown" is the one thing this node must
never do -- it exists to make a stop legible. A router's state writes are
discarded at the graph boundary (#2018), so a halt reached by routing alone
arrived here with an empty error_message and printed exactly that. Nodes now
record the reason where they know it, and `describe_halt_from_state` below
synthesizes one from the state when they do not, so no path can print "unknown"
again.

The fallback is deliberately scoped to HALT. A finalize repair (#2233) leaves
error_message empty ON PURPOSE -- an in-flight repair is not a failure -- and
routes to the drafter, never here, so that emptiness is untouched.
"""

from pathlib import Path

from assemblyzero.core.errors import (
    AuthenticationError,
    CapacityError,
    RateLimitError,
    classify_http_status,
    is_capacity_message,
)
from assemblyzero.core.recovery_plan import generate_recovery_plan
from assemblyzero.core.state_persistence import STATE_DIR, save_state_snapshot


def classify_error(error_message: str) -> str:
    """Classify error type from the error_message string.

    Issue #546: Delegates to errors.py for HTTP-related classifications,
    preserving domain-specific patterns (stagnation, budget, preflight)
    that have no HTTP equivalent.

    Args:
        error_message: The error message from the workflow state.

    Returns:
        Classified error type string.
    """
    msg_lower = error_message.lower()

    # Domain-specific classifications first (no HTTP equivalent)
    # #1899/#1900: a contradiction in the ISSUE's own requirements. Nothing
    # transient about it — no retry, revise cycle, or regenerated spec can
    # satisfy two criteria that specify different outcomes for the same
    # situation. The fix is an operator ruling on the issue text.
    if "requirements conflict" in msg_lower:
        return "requirements_conflict"
    # #2474: the gate could not RUN. Checked before the capacity and auth
    # patterns below because the reason text quotes the transport failure
    # verbatim ("All credentials failed ... 503/529"), and classifying on that
    # would produce "wait 15 minutes and retry the run" — advice that skips the
    # part the operator has to know, which is that requirements were never
    # checked. Transient or not is the second question here, not the first.
    if "requirements unverified" in msg_lower:
        return "requirements_unverified"
    # #1939: 'stagnant' is what the live guards actually print
    # ("[STAGNANT] Coverage stagnant: 87.0% -> 86.0%") — the old
    # 'stagnation'-only pattern never matched a real halt message.
    if any(p in msg_lower for p in ("stagnation", "stagnant", "same issues", "same blocking", "two consecutive")):
        return "stagnation"
    # #1944: the bare token 'budget' false-matched the CLIENT's wall-clock
    # wall ('call budget of 600s exhausted') — a pure capacity storm halted
    # as a non-transient cost problem telling the operator to raise
    # --budget. Cost halts all carry '[BUDGET]' or 'cost budget'; match
    # those, and let capacity-flavored budget-wall messages fall through to
    # the capacity classifier below.
    if any(p in msg_lower for p in ("[budget]", "cost budget")):
        return "budget"
    if "preflight" in msg_lower:
        if "unavailable" in msg_lower or "exhausted" in msg_lower:
            return "quota_exhausted"
        return "preflight"

    # Try to extract an HTTP status code and delegate to errors.py
    import re
    status_match = re.search(r'\bstatus[=: ]*(\d{3})\b', msg_lower)
    if status_match:
        status_code = int(status_match.group(1))
        classified = classify_http_status(status_code, error_message)
        if isinstance(classified, CapacityError):
            return "capacity_exhausted"
        if isinstance(classified, RateLimitError):
            return "quota_exhausted"
        if isinstance(classified, AuthenticationError):
            return "auth"

    # Fallback: pattern matching for messages without status codes.
    # #1909: markers live in errors.CAPACITY_MESSAGE_MARKERS so the halt
    # classifier and the orchestrator's escalating retry agree on what
    # "capacity" looks like.
    if is_capacity_message(error_message):
        return "capacity_exhausted"
    if any(p in msg_lower for p in ("quota exhausted", "429", "all credentials exhausted")):
        return "quota_exhausted"
    # #1773: the bare substring "auth" false-matched credential NAMES like
    # "oauth-primary" — a prompt-size rejection was halted as 'Check your
    # Gemini credentials'. Match specific auth-failure phrases only.
    if any(p in msg_lower for p in (
        "authentication failed", "authentication error", "invalid api key",
        "api_key_invalid", "permission_denied", "unauthenticated", "unauthorized",
    )):
        return "auth"

    return "unknown"


def describe_iteration_cap(
    max_iterations: int, verdict: str, feedback: str = "", limit: int = 300
) -> str:
    """The message an iteration-cap halt should have carried (#2197).

    Names the cap, what the last round said, and the first line of the reason,
    so the operator reads a verdict instead of scrolling a transcript.
    """
    rounds = "round" if max_iterations == 1 else "rounds"
    reason = (feedback or "").strip().splitlines()
    head = reason[0].strip() if reason else ""
    if len(head) > limit:
        head = head[:limit].rstrip() + "..."

    message = (
        f"Iteration cap: {max_iterations} review {rounds} ended {verdict}, "
        "so the run stopped rather than spend another round on the same "
        "objection."
    )
    return f"{message} Last feedback: {head}" if head else message


def describe_halt_from_state(state: dict, workflow_name: str) -> str:
    """A best-effort reason when a halt arrived with no error_message (#2197).

    Reports what the state SAYS rather than re-deciding why routing halted: a
    synthesized message that disagreed with the real reason would be worse than
    the blank it replaces. Every branch names the field it read.
    """
    verdict = state.get("review_verdict") or state.get("lld_status") or ""
    iteration = state.get("review_iteration") or state.get("iteration_count") or 0
    cap = state.get("max_iterations", 0)

    if verdict and cap and iteration >= cap:
        return describe_iteration_cap(
            cap, verdict,
            state.get("review_feedback") or state.get("current_verdict") or "",
        )

    issues = state.get("completeness_issues") or state.get("validation_errors") or []
    if issues:
        listed = "; ".join(str(i) for i in list(issues)[:3])
        return (
            f"Halted with {len(issues)} unresolved check(s) after "
            f"{iteration} round(s): {listed}"
        )

    if verdict:
        return (
            f"Halted after {iteration} round(s) with verdict {verdict} and no "
            "recorded reason; see the state snapshot for the full transcript."
        )

    return (
        f"The {workflow_name} workflow halted without recording a reason. "
        "The state snapshot beside this plan holds everything it knew."
    )


def create_halt_node(workflow_name: str):
    """Factory: returns a LangGraph-compatible node function.

    Args:
        workflow_name: The workflow this halt node belongs to
                       (requirements, implementation_spec, testing, orchestrator).

    Returns:
        A function(state: dict) -> dict suitable for graph.add_node("HALT", ...).
    """

    def halt_with_plan(state: dict) -> dict:
        """HALT node — saves state, generates recovery plan, prints summary.

        Args:
            state: The current LangGraph workflow state dict.

        Returns:
            Dict with recovery_plan_path and state_snapshot_path keys.
        """
        issue_number = state.get("issue_number", 0)
        # #2197: "Unknown error" was the default AND the common case, because a
        # halt reached by routing alone carries nothing. Synthesize from state
        # rather than print a word that tells the operator nothing.
        error_message = (state.get("error_message") or "").strip()
        if not error_message:
            error_message = describe_halt_from_state(state, workflow_name)
        cost_budget = state.get("cost_budget_usd", 0.0)

        # 1. Classify the error
        error_type = classify_error(error_message)

        # 2. Determine which stage halted (from state context)
        stage = _infer_stage(state, workflow_name)

        # 3. Save full state to disk
        state_path = save_state_snapshot(
            workflow_name, issue_number, state, trigger="halt"
        )

        # 4. Generate recovery plan
        plan = generate_recovery_plan(
            issue_number=issue_number,
            workflow=workflow_name,
            stage=stage,
            error_type=error_type,
            error_message=error_message,
            state=state,
            cost_budget_usd=cost_budget,
        )
        plan.state_path = str(state_path)

        # 5. Save plan to same directory as state
        plan_path = plan.save(state_path.parent)

        # 5b. #2570: the halt writes the resume contract — every input the
        # resume will need, hashed, plus the counters and the snapshot it
        # seeds from. The resume verifies this FIRST and refuses by name
        # on any mismatch. Written beside the plan, and copied into the
        # run's audit dir when there is one, so the lineage carries the
        # manifest. Best-effort: a contract that cannot be written must
        # never mask the halt it describes.
        try:
            from assemblyzero.core.resume_contract import (
                build_resume_contract,
                save_resume_contract,
            )

            contract = build_resume_contract(
                state, workflow_name, state_snapshot=state_path
            )
            save_resume_contract(contract)
            audit_dir_str = str(state.get("audit_dir", "") or "")
            if audit_dir_str and Path(audit_dir_str).is_dir():
                save_resume_contract(contract, Path(audit_dir_str))
            print(
                f"  resume contract written: "
                f"{len(contract['inputs'])} input(s) (#2570)"
            )
        except Exception as exc:  # noqa: BLE001
            # fail-open: the contract is the resume's protection, not the
            # halt's -- a halt that cannot write it still halts, loudly,
            # and the resume simply has no contract to verify.
            print(f"  [WARN] resume contract not written: {exc}")

        # 6. Print human-readable summary
        plan.print_summary()

        return {
            "recovery_plan_path": str(plan_path),
            "state_snapshot_path": str(state_path),
            # #2297: an explicit terminal verdict every caller can read. A
            # halted workflow used to be distinguishable from a successful one
            # only by inspecting artifacts, and after #2250 made drafts persist
            # a cap-halt left the same evidence a success does.
            "workflow_status": "halted",
            # Carry the synthesized reason out of the halt as well, so a caller
            # that only reads error_message sees what the block printed rather
            # than the empty string routing left behind (#2299).
            "error_message": error_message,
        }

    return halt_with_plan


def _infer_stage(state: dict, workflow_name: str) -> str:
    """Infer which stage the workflow was in when it halted."""
    # Use review_iteration or iteration_count as hints
    if "review_iteration" in state:
        iteration = state.get("review_iteration", 0)
        if iteration > 0:
            return f"N5_review_iter{iteration}"
        return "N2_generate"
    elif "iteration_count" in state:
        iteration = state.get("iteration_count", 0)
        if state.get("current_verdict"):
            return f"N3_review_iter{iteration}"
        if state.get("current_draft"):
            return f"N1_draft_iter{iteration}"
        return f"N0_load"
    elif "next_node" in state:
        return state.get("next_node", "unknown")
    else:
        return f"{workflow_name}_unknown"
