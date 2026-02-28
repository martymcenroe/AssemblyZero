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
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


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

    def print_summary(self) -> None:
        """Print a human-readable summary to stdout."""
        border = "=" * 60
        print(f"\n{border}")
        print(f"  HALT — Workflow stopped")
        print(f"{border}")
        print(f"  Issue:     #{self.issue_number}")
        print(f"  Workflow:  {self.workflow}")
        print(f"  Stage:     {self.stage}")
        print(f"  Error:     {self.error_type}")
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
    recommendation = _build_recommendation(error_type, error_message, workflow)

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


def _build_recommendation(error_type: str, error_message: str, workflow: str) -> str:
    """Generate human-readable advice based on error type."""
    if error_type == "capacity_exhausted":
        return (
            "Transient error: Gemini is overloaded (503/529). "
            "Wait 15 minutes and retry, or try --reviewer gemini:3.1-pro-preview."
        )
    elif error_type == "quota_exhausted":
        return (
            "Transient error: All Gemini credentials are quota-exhausted. "
            "Check ~/.assemblyzero/gemini-rotation-state.json for reset times."
        )
    elif error_type == "stagnation":
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
    else:
        return f"Workflow {workflow} halted: {error_message[:200]}"
