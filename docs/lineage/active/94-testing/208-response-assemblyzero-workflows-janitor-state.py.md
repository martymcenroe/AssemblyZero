```python
"""State definitions for the Janitor workflow.

Issue #94: Lu-Tze: The Janitor
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, TypedDict


# --- Type aliases ---
Severity = Literal["info", "warning", "critical"]
ProbeScope = Literal["links", "worktrees", "harvest", "todo"]


@dataclass
class Finding:
    """A single issue discovered by a probe."""

    probe: ProbeScope
    category: str
    message: str
    severity: Severity
    fixable: bool
    file_path: str | None = None
    line_number: int | None = None
    fix_data: dict | None = None


@dataclass
class ProbeResult:
    """Structured result from a single probe execution."""

    probe: ProbeScope
    status: Literal["ok", "findings", "error"]
    findings: list[Finding] = field(default_factory=list)
    error_message: str | None = None


@dataclass
class FixAction:
    """Record of a fix that was applied (or would be applied in dry-run)."""

    category: str
    description: str
    files_modified: list[str]
    commit_message: str
    applied: bool


class JanitorState(TypedDict):
    """LangGraph state for the janitor workflow."""

    # Configuration (set at graph entry)
    repo_root: str
    scope: list[ProbeScope]
    auto_fix: bool
    dry_run: bool
    silent: bool
    create_pr: bool
    reporter_type: Literal["github", "local"]

    # Probe results (populated by N0_Sweeper)
    probe_results: list[ProbeResult]
    all_findings: list[Finding]

    # Fix results (populated by N1_Fixer)
    fix_actions: list[FixAction]
    unfixable_findings: list[Finding]

    # Reporter results (populated by N2_Reporter)
    report_url: str | None
    exit_code: int
```
