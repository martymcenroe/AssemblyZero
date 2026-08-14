"""Recovery plan generation for halted workflows.

Issue #486: Halt-and-Plan pattern — self-babysitting workflows.

When a workflow halts (pre-flight failure, capacity exhaustion, stagnation,
budget exceeded), this module generates a structured recovery plan that:
1. Captures what went wrong and where
2. Classifies the error as transient or permanent
3. Saves full state for later resumption
4. Provides actionable advice and CLI resume commands
"""

import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


# Error types classified as transient (will resolve on their own)
TRANSIENT_ERROR_TYPES = frozenset({"capacity_exhausted", "quota_exhausted"})

# Workflow name → CLI tool for resume commands
RESUME_COMMANDS = {
    "requirements": "tools/run_requirements_workflow.py",
    "implementation_spec": "tools/run_implementation_spec_workflow.py",
    "testing": "tools/run_tdd_workflow.py",
    "orchestrator": "tools/run_orchestrator.py",
}


@dataclass
class RecoveryPlan:
    """Structured recovery plan — the output of every halt."""

    issue_number: int
    workflow: str
    stage: str
    error_type: str
    error_message: str
    is_transient: bool
    state_path: str
    cost_spent_usd: float
    cost_budget_usd: float
    halted_at: str
    resume_command: str
    earliest_retry: str
    recommendation: str

    def save(self, directory: Path) -> Path:
        """Save recovery plan as JSON to the specified directory.

        Args:
            directory: Target directory (created if needed).

        Returns:
            Path to the saved JSON file.
        """
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        filename = f"recovery-{self.issue_number}-{self.workflow}.json"
        plan_path = directory / filename
        with open(plan_path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)
        return plan_path

    #: How much of the reason the halt block shows before pointing at the plan.
    ERROR_LINE_LIMIT = 400

    def _error_line(self) -> str:
        """The real reason, first line first, bounded so the block stays a block.

        Falls back to the classification only when there is genuinely no
        message -- and says so in words, because a bare "unknown" is what
        #2299 was filed about.
        """
        message = (self.error_message or "").strip()
        if not message:
            return f"(no reason recorded; classified as '{self.error_type}')"
        head = message.splitlines()[0].strip()
        if len(head) > self.ERROR_LINE_LIMIT:
            head = head[: self.ERROR_LINE_LIMIT].rstrip() + "..."
        return head

    def print_summary(self) -> None:
        """Print a human-readable summary to stdout."""
        border = "=" * 60
        print(f"\n{border}")
        print(f"  HALT — Workflow stopped")
        print(f"{border}")
        print(f"  Issue:     #{self.issue_number}")
        print(f"  Workflow:  {self.workflow}")
        print(f"  Stage:     {self.stage}")
        # #2299: this line printed `error_type` -- the CLASSIFIER's bucket --
        # under a label that reads as the error itself. `classify_error`
        # returns "unknown" for anything it has no bucket for, and an
        # iteration-cap message is exactly that, so every cap halt announced
        # "Error: unknown" while the real reason sat two lines below in the
        # recommendation. The message was never missing; the field was showing
        # a different quantity than its label promised.
        print(f"  Error:     {self._error_line()}")
        print(f"  Class:     {self.error_type}")
        print(f"  Transient: {'Yes' if self.is_transient else 'No'}")
        if self.cost_spent_usd > 0:
            print(f"  Cost:      ${self.cost_spent_usd:.2f} / ${self.cost_budget_usd:.2f}")
        print(f"  Halted at: {self.halted_at}")
        if self.earliest_retry:
            print(f"  Retry at:  {self.earliest_retry}")
        print(f"\n  {self.recommendation}")
        print(f"\n  Resume: {self.resume_command}")
        print(f"{border}\n")


def generate_recovery_plan(
    issue_number: int,
    workflow: str,
    stage: str,
    error_type: str,
    error_message: str,
    state: dict,
    cost_spent_usd: float = 0.0,
    cost_budget_usd: float = 0.0,
    state_path: str = "",
) -> RecoveryPlan:
    """Smart factory — infers is_transient, builds resume_command, writes recommendation.

    Args:
        issue_number: The issue being processed.
        workflow: Workflow name (requirements, implementation_spec, testing, orchestrator).
        stage: Node name where the halt occurred.
        error_type: Classified error type string.
        error_message: Raw error message.
        state: Current workflow state dict (for context).
        cost_spent_usd: How much has been spent so far.
        cost_budget_usd: Total budget for this run.

    Returns:
        Populated RecoveryPlan ready to save/print.
    """
    is_transient = error_type in TRANSIENT_ERROR_TYPES
    halted_at = datetime.now(timezone.utc).isoformat()

    # Build resume command
    tool = RESUME_COMMANDS.get(workflow, f"tools/run_{workflow}_workflow.py")
    resume_command = (
        f"poetry run python {tool} --issue {issue_number}"
    )

    # Earliest retry for transient errors
    earliest_retry = ""
    if is_transient:
        if error_type == "capacity_exhausted":
            retry_at = datetime.now(timezone.utc) + timedelta(minutes=15)
        else:
            retry_at = datetime.now(timezone.utc) + timedelta(hours=1)
        earliest_retry = retry_at.isoformat()

    # Generate recommendation
    recommendation = _build_recommendation(
        error_type, error_message, workflow, state,
    )

    return RecoveryPlan(
        issue_number=issue_number,
        workflow=workflow,
        stage=stage,
        error_type=error_type,
        error_message=error_message,
        is_transient=is_transient,
        state_path=state_path,
        cost_spent_usd=cost_spent_usd,
        cost_budget_usd=cost_budget_usd,
        halted_at=halted_at,
        resume_command=resume_command,
        earliest_retry=earliest_retry,
        recommendation=recommendation,
    )


def _never_passed(error_message: str) -> bool:
    """True when the halt message reports 0 tests passing out of N (#2321).

    Mechanically derived from the message the stagnation guard already
    writes, so this needs no new plumbing and cannot disagree with the
    number the operator is reading two lines above it.
    """
    match = re.search(r"\b0\s*/\s*(\d+)\s+passed", error_message)
    return bool(match) and int(match.group(1)) > 0


def _build_recommendation(
    error_type: str,
    error_message: str,
    workflow: str,
    state: dict[str, Any] | None = None,
) -> str:
    """Generate human-readable advice based on error type."""
    if error_type == "capacity_exhausted":
        return (
            "Transient error: Gemini is overloaded (503/529). "
            "Wait 15 minutes and retry, or try --reviewer claude:opus."
        )
    elif error_type == "quota_exhausted":
        return (
            "Transient error: All Gemini credentials are quota-exhausted. "
            "Check ~/.assemblyzero/gemini-rotation-state.json for reset times."
        )
    elif error_type == "stagnation":
        # #2321: this is the pipeline's last word before a human picks the run
        # up, and it used to aim at the two most expensive artifacts to
        # regenerate. On boostgauge #7 the LLD (282s) and spec (699s) were both
        # correct -- the spec's own tests pass against the implementation the
        # run discarded -- while the broken artifact was the 2s generated test
        # file, which the message never mentioned. Acting on it as written
        # would have burned another 16 minutes regenerating good documents.
        #
        # When no test has EVER passed, the suite is the first suspect: a suite
        # that cannot pass makes the loop unable to converge whatever the
        # implementation does. A partial-pass stagnation is a genuinely
        # different situation and keeps the original advice.
        if _never_passed(error_message):
            test_file = ""
            for candidate in (state or {}).get("test_files", []) or []:
                test_file = str(candidate)
                break
            where = f" Inspect {test_file}." if test_file else ""
            return (
                "Non-transient: no test has passed in any iteration. When the "
                "pass count never leaves zero, suspect the GENERATED TEST FILE "
                "before the LLD or spec — a suite that cannot pass makes the "
                f"implementation loop unable to converge.{where} Check whether "
                "its tests have real bodies, or are placeholders that fail "
                "unconditionally."
            )
        return (
            "Non-transient: Two consecutive iterations with same blocking issues. "
            "The LLD or spec likely needs manual editing before retry."
        )
    elif error_type == "budget":
        return (
            "Non-transient: Cost budget exceeded. "
            "Increase --budget or review why iterations are costly."
        )
    elif error_type == "auth":
        return (
            "Non-transient: Authentication failed. "
            "Check your Gemini credentials in ~/.assemblyzero/gemini-credentials.json."
        )
    elif error_type == "requirements_conflict":
        return (
            "Non-transient: the ISSUE's requirements contradict each other — "
            "no spec can satisfy both readings, so re-rolling burns tokens on "
            "an unwinnable draft (#1899/#1900). Read the named conflict in the "
            "error message, rule on the correct reading, edit the issue's "
            "acceptance criteria to say it, then re-run."
        )
    else:
        return f"Workflow {workflow} halted: {error_message[:200]}"
