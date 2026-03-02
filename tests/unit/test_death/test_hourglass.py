"""Tests for hourglass state machine.

Issue #535: T170–T210, T230–T250.
"""

from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.workflows.death.hourglass import (
    _node_rest,
    _route_after_harvest,
    run_death,
    should_death_arrive,
)
from assemblyzero.workflows.death.models import AgeMeterState, HourglassState


def _make_state(**overrides) -> HourglassState:
    """Helper to create test HourglassState."""
    base: HourglassState = {
        "trigger": "summon",
        "mode": "report",
        "codebase_root": "/tmp/test",
        "age_meter": {
            "current_score": 25,
            "threshold": 50,
            "last_death_visit": None,
            "last_computed": "2026-02-17T12:30:00Z",
            "weighted_issues": [],
            "age_number": 3,
        },
        "drift_report": None,
        "reconciliation_report": None,
        "step": "init",
        "errors": [],
        "confirmed": False,
    }
    base.update(overrides)
    return base


@patch("assemblyzero.workflows.death.hourglass.build_drift_report")
@patch("assemblyzero.workflows.death.hourglass.load_age_meter_state")
@patch("assemblyzero.workflows.death.hourglass.save_age_meter_state")
def test_report_flow_completes(mock_save, mock_load, mock_drift):
    """T170: Report mode completes full flow.

    Input: mode="report"
    Expected: Report completes without error
    """
    mock_load.return_value = {
        "current_score": 10,
        "threshold": 50,
        "last_death_visit": None,
        "last_computed": "2026-02-17T12:30:00Z",
        "weighted_issues": [],
        "age_number": 1,
    }
    mock_drift.return_value = {
        "findings": [],
        "total_score": 0.0,
        "critical_count": 0,
        "major_count": 0,
        "minor_count": 0,
        "scanned_docs": [],
        "scanned_code_paths": [],
        "timestamp": "2026-02-17T12:45:00Z",
    }

    report = run_death(
        mode="report",
        trigger="summon",
        codebase_root="/tmp/fake",
        repo="test/repo",
    )
    assert report is not None
    assert report["mode"] == "report"


def test_route_after_harvest_report_mode():
    """T180 variant: Report mode routes to 'archive'.

    Input: mode="report", confirmed=False
    Expected: "archive"
    """
    state = _make_state(mode="report", confirmed=False)
    assert _route_after_harvest(state) == "archive"


def test_route_after_harvest_reaper_confirmed():
    """T180: Reaper confirmed routes to 'archive'.

    Input: mode="reaper", confirmed=True
    Expected: "archive"
    """
    state = _make_state(mode="reaper", confirmed=True)
    assert _route_after_harvest(state) == "archive"


def test_route_after_harvest_reaper_declined():
    """T190: Reaper declined routes to 'complete'.

    Input: mode="reaper", confirmed=False
    Expected: "complete"
    """
    state = _make_state(mode="reaper", confirmed=False)
    assert _route_after_harvest(state) == "complete"


@patch("assemblyzero.workflows.death.hourglass.save_age_meter_state")
@patch("assemblyzero.workflows.death.hourglass.HISTORY_PATH")
def test_node_rest_resets_meter(mock_history_path, mock_save):
    """T200: Rest node resets score to 0 and increments age.

    Input: age_number=3, current_score=55
    Expected: age_number=4, current_score=0
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        history_path = os.path.join(tmpdir, "history.json")
        with open(history_path, "w") as f:
            json.dump([], f)
        mock_history_path.__str__ = lambda s: history_path
        # Patch the module-level HISTORY_PATH
        with patch("assemblyzero.workflows.death.hourglass.HISTORY_PATH", history_path):
            state = _make_state(
                step="rest",
                age_meter={
                    "current_score": 55,
                    "threshold": 50,
                    "last_death_visit": None,
                    "last_computed": "2026-02-17T12:30:00Z",
                    "weighted_issues": [],
                    "age_number": 3,
                },
                reconciliation_report={
                    "age_number": 3,
                    "trigger": "summon",
                    "trigger_details": "test",
                    "drift_report": {"findings": [], "total_score": 0, "critical_count": 0, "major_count": 0, "minor_count": 0, "scanned_docs": [], "scanned_code_paths": [], "timestamp": "2026-02-17T12:45:00Z"},
                    "actions": [],
                    "mode": "report",
                    "timestamp": "2026-02-17T12:50:00Z",
                    "summary": "test",
                },
            )
            result = _node_rest(state)
            assert result["age_meter"]["current_score"] == 0
            assert result["age_meter"]["age_number"] == 4


@patch("assemblyzero.workflows.death.hourglass.save_age_meter_state")
def test_node_rest_appends_history(mock_save):
    """T210: Rest node appends entry to history.json.

    Input: Mock history file with 0 entries
    Expected: History file has 1 entry after rest
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        history_path = os.path.join(tmpdir, "history.json")
        with open(history_path, "w") as f:
            json.dump([], f)

        with patch("assemblyzero.workflows.death.hourglass.HISTORY_PATH", history_path):
            state = _make_state(
                step="rest",
                reconciliation_report={
                    "age_number": 3,
                    "trigger": "summon",
                    "trigger_details": "test",
                    "drift_report": {"findings": [], "total_score": 0, "critical_count": 0, "major_count": 0, "minor_count": 0, "scanned_docs": [], "scanned_code_paths": [], "timestamp": "2026-02-17T12:45:00Z"},
                    "actions": [],
                    "mode": "report",
                    "timestamp": "2026-02-17T12:50:00Z",
                    "summary": "test",
                },
            )
            _node_rest(state)

            with open(history_path) as f:
                history = json.load(f)
            assert len(history) == 1
            assert history[0]["age_number"] == 3


@patch("assemblyzero.workflows.death.hourglass.build_drift_report")
@patch("assemblyzero.workflows.death.hourglass.load_age_meter_state")
@patch("assemblyzero.workflows.death.hourglass.fetch_closed_issues_since")
@patch("assemblyzero.workflows.death.hourglass.save_age_meter_state")
@patch("assemblyzero.workflows.death.hourglass.compute_age_meter")
def test_should_death_arrive_no_triggers(mock_compute, mock_save, mock_fetch, mock_load, mock_drift):
    """T230: No triggers active returns (False, ...).

    Input: Low meter (score=10/50), low drift (score=5.0/30.0)
    Expected: (False, "", "No triggers active...")
    """
    mock_drift.return_value = {
        "findings": [],
        "total_score": 5.0,
        "critical_count": 0,
        "major_count": 1,
        "minor_count": 0,
        "scanned_docs": [],
        "scanned_code_paths": [],
        "timestamp": "2026-02-17T12:45:00Z",
    }
    mock_load.return_value = {
        "current_score": 10,
        "threshold": 50,
        "last_death_visit": None,
        "last_computed": "2026-02-17T12:30:00Z",
        "weighted_issues": [],
        "age_number": 1,
    }
    mock_fetch.return_value = []
    mock_compute.return_value = {
        "current_score": 10,
        "threshold": 50,
        "last_death_visit": None,
        "last_computed": "2026-02-17T12:30:00Z",
        "weighted_issues": [],
        "age_number": 1,
    }

    should, trigger, details = should_death_arrive("/project", "test/repo", "fake-token")
    assert should is False


@patch("assemblyzero.workflows.death.hourglass.build_drift_report")
@patch("assemblyzero.workflows.death.hourglass.load_age_meter_state")
@patch("assemblyzero.workflows.death.hourglass.fetch_closed_issues_since")
@patch("assemblyzero.workflows.death.hourglass.save_age_meter_state")
@patch("assemblyzero.workflows.death.hourglass.compute_age_meter")
def test_should_death_arrive_meter_trigger(mock_compute, mock_save, mock_fetch, mock_load, mock_drift):
    """T240: High meter triggers DEATH.

    Input: age_meter score=55/50, drift score=5.0/30.0
    Expected: (True, "meter", "...")
    """
    mock_drift.return_value = {
        "findings": [],
        "total_score": 5.0,
        "critical_count": 0,
        "major_count": 0,
        "minor_count": 0,
        "scanned_docs": [],
        "scanned_code_paths": [],
        "timestamp": "2026-02-17T12:45:00Z",
    }
    mock_load.return_value = {
        "current_score": 55,
        "threshold": 50,
        "last_death_visit": None,
        "last_computed": "2026-02-17T12:30:00Z",
        "weighted_issues": [],
        "age_number": 1,
    }
    mock_fetch.return_value = []
    mock_compute.return_value = {
        "current_score": 55,
        "threshold": 50,
        "last_death_visit": None,
        "last_computed": "2026-02-17T12:30:00Z",
        "weighted_issues": [],
        "age_number": 1,
    }

    should, trigger, details = should_death_arrive("/project", "test/repo", "fake-token")
    assert should is True
    assert trigger == "meter"


@patch("assemblyzero.workflows.death.hourglass.build_drift_report")
def test_should_death_arrive_critical_drift(mock_drift):
    """T250: High drift triggers DEATH.

    Input: age_meter score=10/50, drift score=35.0/30.0
    Expected: (True, "critical_drift", "...")
    """
    mock_drift.return_value = {
        "findings": [],
        "total_score": 35.0,
        "critical_count": 3,
        "major_count": 1,
        "minor_count": 0,
        "scanned_docs": [],
        "scanned_code_paths": [],
        "timestamp": "2026-02-17T12:45:00Z",
    }

    should, trigger, details = should_death_arrive("/project", "test/repo", "fake-token")
    assert should is True
    assert trigger == "critical_drift"