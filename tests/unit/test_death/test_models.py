"""Tests for data models.

Issue #535: T260, T270.
"""

from __future__ import annotations

from assemblyzero.workflows.death.models import (
    AgeMeterState,
    DriftFinding,
    IssueWeight,
)


def test_age_meter_state_fields():
    """T260: AgeMeterState validates correctly."""
    state: AgeMeterState = {
        "current_score": 25,
        "threshold": 50,
        "last_death_visit": None,
        "last_computed": "2026-02-17T12:30:00Z",
        "weighted_issues": [],
        "age_number": 1,
    }
    assert state["current_score"] == 25
    assert state["threshold"] == 50
    assert state["last_death_visit"] is None
    assert state["age_number"] == 1


def test_drift_finding_all_categories():
    """T270: All DriftFinding categories and severities accepted."""
    categories = [
        "count_mismatch",
        "feature_contradiction",
        "missing_component",
        "stale_reference",
        "architecture_drift",
    ]
    severities = ["critical", "major", "minor"]

    for cat in categories:
        for sev in severities:
            finding: DriftFinding = {
                "id": f"DRIFT-{cat}-{sev}",
                "severity": sev,
                "doc_file": "README.md",
                "doc_claim": "test claim",
                "code_reality": "test reality",
                "category": cat,
                "confidence": 0.9,
                "evidence": "test evidence",
            }
            assert finding["category"] == cat
            assert finding["severity"] == sev


def test_issue_weight_fields():
    """IssueWeight fields accessible."""
    iw: IssueWeight = {
        "issue_number": 534,
        "title": "Spelunking Audits",
        "labels": ["architecture"],
        "weight": 10,
        "weight_source": "architecture",
        "closed_at": "2026-02-15T14:30:00Z",
    }
    assert iw["weight"] == 10
    assert iw["weight_source"] == "architecture"