"""The /death skill entry point — parses arguments and invokes the hourglass.

Issue #535: Skill interface for DEATH as Age Transition.
"""

from __future__ import annotations

import logging
from typing import Literal

from assemblyzero.workflows.death.hourglass import run_death
from assemblyzero.workflows.death.models import ReconciliationReport

logger = logging.getLogger(__name__)

_VALID_MODES = {"report", "reaper"}


def parse_death_args(
    args: list[str],
) -> tuple[Literal["report", "reaper"], bool]:
    """Parse /death skill command arguments.

    Returns (mode, force) tuple.

    Raises:
        ValueError: If arguments are invalid.
    """
    if not args:
        return ("report", False)

    mode = args[0].lower()
    if mode not in _VALID_MODES:
        raise ValueError(
            f"Unknown mode: '{args[0]}'. Expected 'report' or 'reaper'."
        )

    force = False
    if len(args) > 1:
        for flag in args[1:]:
            if flag == "--force":
                force = True
            else:
                raise ValueError(f"Unknown flag: '{flag}'. Expected '--force'.")

    return (mode, force)


def invoke_death_skill(
    args: list[str],
    codebase_root: str,
    repo: str,
    github_token: str | None = None,
) -> ReconciliationReport:
    """Main entry point for /death skill. Trigger is always 'summon'.

    Raises:
        ValueError: If arguments are invalid.
        PermissionError: If reaper mode not confirmed.
    """
    mode, force = parse_death_args(args)

    if mode == "reaper" and not force:
        raise PermissionError(
            "Reaper mode requires confirmation. Use --force to bypass."
        )

    return run_death(
        mode=mode,
        trigger="summon",
        codebase_root=codebase_root,
        repo=repo,
        github_token=github_token,
    )


def format_report_output(
    report: ReconciliationReport,
) -> str:
    """Format ReconciliationReport as human-readable markdown."""
    lines: list[str] = []
    lines.append(f"# DEATH Reconciliation Report — Age {report['age_number']}")
    lines.append("")
    lines.append("> WHAT CAN THE HARVEST HOPE FOR, IF NOT FOR THE CARE OF THE REAPER MAN?")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(report["summary"])
    lines.append("")
    lines.append(f"**Trigger:** {report['trigger']} — {report['trigger_details']}")
    lines.append(f"**Mode:** {report['mode']} ({'read-only' if report['mode'] == 'report' else 'write mode'})")
    lines.append(f"**Timestamp:** {report['timestamp']}")
    lines.append("")

    # Drift findings
    drift = report["drift_report"]
    lines.append("## Drift Findings")
    lines.append("")
    if drift["findings"]:
        lines.append("| ID | Severity | File | Category | Claim | Reality |")
        lines.append("|----|----------|------|----------|-------|---------|")
        for f in drift["findings"]:
            lines.append(
                f"| {f['id']} | {f['severity']} | {f['doc_file']} | {f['category']} | {f['doc_claim'][:40]} | {f['code_reality'][:40]} |"
            )
        lines.append("")
    else:
        lines.append("No drift findings detected.")
        lines.append("")

    lines.append(f"**Drift Score:** {drift['total_score']} / 30.0 (critical threshold)")
    lines.append("")

    # Proposed actions
    lines.append("## Proposed Actions")
    lines.append("")
    if report["actions"]:
        lines.append("| # | File | Action | Description |")
        lines.append("|---|------|--------|-------------|")
        for i, action in enumerate(report["actions"], 1):
            lines.append(
                f"| {i} | {action['target_file']} | {action['action_type']} | {action['description'][:60]} |"
            )
        lines.append("")
    else:
        lines.append("No reconciliation actions needed.")
        lines.append("")

    # Next steps
    lines.append("## Next Steps")
    lines.append("")
    if report["mode"] == "report":
        lines.append("Run `/death reaper` to apply these changes (with confirmation).")
    else:
        lines.append("Changes have been applied. Review and commit.")
    lines.append("")

    return "\n".join(lines)