"""Data models for the Hourglass Protocol.

Issue #535: TypedDict definitions for age meter, drift, and reconciliation.
"""

from __future__ import annotations

from typing import Literal, TypedDict


class IssueWeight(TypedDict):
    """Weight assignment for a single closed issue."""

    issue_number: int
    title: str
    labels: list[str]
    weight: int
    weight_source: str
    closed_at: str


class AgeMeterState(TypedDict):
    """Persistent state of the age meter between sessions."""

    current_score: int
    threshold: int
    last_death_visit: str | None
    last_computed: str
    weighted_issues: list[IssueWeight]
    age_number: int


class DriftFinding(TypedDict):
    """A single factual inaccuracy found by drift analysis."""

    id: str
    severity: Literal["critical", "major", "minor"]
    doc_file: str
    doc_claim: str
    code_reality: str
    category: Literal[
        "count_mismatch",
        "feature_contradiction",
        "missing_component",
        "stale_reference",
        "architecture_drift",
    ]
    confidence: float
    evidence: str


class DriftReport(TypedDict):
    """Aggregated drift analysis results."""

    findings: list[DriftFinding]
    total_score: float
    critical_count: int
    major_count: int
    minor_count: int
    scanned_docs: list[str]
    scanned_code_paths: list[str]
    timestamp: str


class ReconciliationAction(TypedDict):
    """A single action to reconcile documentation with reality."""

    target_file: str
    action_type: Literal[
        "update_count",
        "update_description",
        "add_section",
        "remove_section",
        "archive",
        "create_adr",
    ]
    description: str
    old_content: str | None
    new_content: str | None
    drift_finding_id: str


class ReconciliationReport(TypedDict):
    """Full reconciliation report — output of DEATH's walk."""

    age_number: int
    trigger: Literal["meter", "summon", "critical_drift"]
    trigger_details: str
    drift_report: DriftReport
    actions: list[ReconciliationAction]
    mode: Literal["report", "reaper"]
    timestamp: str
    summary: str


class HourglassState(TypedDict):
    """LangGraph state for the Hourglass workflow."""

    trigger: Literal["meter", "summon", "critical_drift"]
    mode: Literal["report", "reaper"]
    codebase_root: str
    age_meter: AgeMeterState
    drift_report: DriftReport | None
    reconciliation_report: ReconciliationReport | None
    step: Literal[
        "init",
        "walk_field",
        "harvest",
        "archive",
        "chronicle",
        "rest",
        "complete",
    ]
    errors: list[str]
    confirmed: bool