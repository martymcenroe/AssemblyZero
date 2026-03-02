"""Tests for age meter computation.

Issue #535: T010–T080.
"""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from assemblyzero.workflows.death.age_meter import (
    check_meter_threshold,
    compute_age_meter,
    compute_issue_weight,
    load_age_meter_state,
    save_age_meter_state,
)
from assemblyzero.workflows.death.models import AgeMeterState


def test_bug_label_weight():
    """T010: Bug label returns weight=1.

    Input: labels=["bug"], title="Fix broken link"
    Expected: (1, "bug")
    """
    weight, source = compute_issue_weight(labels=["bug"], title="Fix broken link")
    assert weight == 1
    assert source == "bug"


def test_architecture_label_weight():
    """T020: Architecture label returns weight=10.

    Input: labels=["architecture"], title="Redesign plugin system"
    Expected: (10, "architecture")
    """
    weight, source = compute_issue_weight(
        labels=["architecture"], title="Redesign plugin system"
    )
    assert weight == 10
    assert source == "architecture"


def test_no_matching_labels_default():
    """T030: No matching label falls back to default weight=2.

    Input: labels=["question"], title="How do I run tests?"
    Expected: (2, "default")
    """
    weight, source = compute_issue_weight(
        labels=["question"], title="How do I run tests?"
    )
    assert weight == 2
    assert source == "default"


def test_multiple_labels_highest_wins():
    """T040: Multiple labels selects highest weight.

    Input: labels=["bug", "architecture"], title="Breaking core change"
    Expected: (10, "architecture")
    """
    weight, source = compute_issue_weight(
        labels=["bug", "architecture"], title="Breaking core change"
    )
    assert weight == 10
    assert source == "architecture"


def test_empty_labels_default():
    """T030 variant: Empty labels list falls back to default.

    Input: labels=[], title="Unlabeled issue"
    Expected: (2, "default")
    """
    weight, source = compute_issue_weight(labels=[], title="Unlabeled issue")
    assert weight == 2
    assert source == "default"


def test_incremental_meter_computation():
    """T050: Incremental meter adds new issues to existing score.

    Input: current_score=20 + issues with persona(5) label
    Expected: current_score=25
    """
    current_state: AgeMeterState = {
        "current_score": 20,
        "threshold": 50,
        "last_death_visit": None,
        "last_computed": "2026-02-01T00:00:00Z",
        "weighted_issues": [],
        "age_number": 3,
    }
    issues = [
        {
            "number": 520,
            "title": "New persona: Spelunker",
            "labels": ["persona"],
            "closed_at": "2026-02-01T11:00:00Z",
            "body": None,
        }
    ]
    result = compute_age_meter(issues, current_state)
    assert result["current_score"] == 25  # 20 + 5


def test_meter_threshold_below():
    """T060: Below threshold returns False.

    Input: score=49, threshold=50
    Expected: False
    """
    state: AgeMeterState = {
        "current_score": 49,
        "threshold": 50,
        "last_death_visit": None,
        "last_computed": "2026-02-17T12:30:00Z",
        "weighted_issues": [],
        "age_number": 1,
    }
    assert check_meter_threshold(state) is False


def test_meter_threshold_at():
    """T070: At threshold returns True.

    Input: score=50, threshold=50
    Expected: True
    """
    state: AgeMeterState = {
        "current_score": 50,
        "threshold": 50,
        "last_death_visit": None,
        "last_computed": "2026-02-17T12:30:00Z",
        "weighted_issues": [],
        "age_number": 1,
    }
    assert check_meter_threshold(state) is True


def test_state_persistence_roundtrip():
    """T080: Save -> load returns identical state.

    Input: AgeMeterState with score=47
    Expected: Loaded state matches saved state
    """
    state: AgeMeterState = {
        "current_score": 47,
        "threshold": 50,
        "last_death_visit": "2026-01-10T09:00:00Z",
        "last_computed": "2026-02-17T12:30:00Z",
        "weighted_issues": [
            {
                "issue_number": 500,
                "title": "Add RAG pipeline",
                "labels": ["rag"],
                "weight": 8,
                "weight_source": "rag",
                "closed_at": "2026-01-15T10:00:00Z",
            }
        ],
        "age_number": 3,
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "age_meter.json")
        save_age_meter_state(state, path)
        loaded = load_age_meter_state(path)
        assert loaded == state


def test_load_nonexistent_state():
    """Load returns None when file doesn't exist."""
    result = load_age_meter_state("/nonexistent/path/age_meter.json")
    assert result is None