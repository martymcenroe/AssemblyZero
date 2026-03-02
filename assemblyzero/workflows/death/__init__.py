"""DEATH as Age Transition — the Hourglass Protocol.

Issue #535: Implements documentation reconciliation via age meter,
drift scoring, and the hourglass state machine.
"""

from __future__ import annotations

from assemblyzero.workflows.death.hourglass import (
    create_hourglass_graph,
    run_death,
    should_death_arrive,
)
from assemblyzero.workflows.death.skill import (
    invoke_death_skill,
    parse_death_args,
    format_report_output,
)

__all__ = [
    "create_hourglass_graph",
    "run_death",
    "should_death_arrive",
    "invoke_death_skill",
    "parse_death_args",
    "format_report_output",
]