```python
"""Tests for /death skill entry point.

Issue #535: T220, T280–T350.
"""

from __future__ import annotations

import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest

from assemblyzero.workflows.death.skill import (
    format_report_output,
    invoke_death_skill,
    parse_death_args,
)
from assemblyzero.workflows.death.models import ReconciliationReport


def test_parse_report_mode():
    """T280: parse_death_args(["report"]) returns ("report", False).

    Input: args=["report"]
    Expected: ("report", False)
    """
    mode, force = parse_death_args(["report"])
    assert mode == "report"
    assert force is False


def test_parse_reaper_mode():
    """T290: parse_death_args(["reaper"]) returns ("reaper", False).

    Input: args=["reaper"]
    Expected: ("reaper", False)
    """
    mode, force = parse_death_args(["reaper"])
    assert mode == "reaper"
    assert force is False


def test_parse_reaper_force():
    """T300: parse_death_args(["reaper", "--force"]) returns ("reaper", True).

    Input: args=["reaper", "--force"]
    Expected: ("reaper", True)
    """
    mode, force = parse_death_args(["reaper", "--force"])
    assert mode == "reaper"
    assert force is True


def test_parse_invalid_mode():
    """T310: parse_death_args(["invalid"]) raises ValueError.

    Input: args=["invalid"]
    Expected: ValueError with message containing "Unknown mode"
    """
    with pytest.raises(ValueError, match="Unknown mode"):
        parse_death_args(["invalid"])


def test_parse_default_mode():
    """T320: parse_death_args([]) returns ("report", False).

    Input: args=[]
    Expected: ("report", False)
    """
    mode, force = parse_death_args([])
    assert mode == "report"
    assert force is False


@patch("assemblyzero.workflows.death.skill.run_death")
def test_invoke_report_mode(mock_run):
    """T330: invoke_death_skill(["report"], ...) returns report.

    Input: args=["report"], mock codebase
    Expected: ReconciliationReport with mode="report"
    """
    mock_report: ReconciliationReport = {
        "age_number": 3,
        "trigger": "summon",
        "trigger_details": "DEATH summoned via /death command",
        "drift_report": {
            "findings": [],
            "total_score": 0.0,
            "critical_count": 0,
            "major_count": 0,
            "minor_count": 0,
            "scanned_docs": [],
            "scanned_code_paths": [],
            "timestamp": "2026-02-17T12:45:00Z",
        },
        "actions": [],
        "mode": "report",
        "timestamp": "2026-02-17T12:50:00Z",
        "summary": "No findings.",
    }
    mock_run.return_value = mock_report

    result = invoke_death_skill(
        args=["report"],
        codebase_root="/project",
        repo="test/repo",
    )
    assert result["mode"] == "report"
    mock_run.assert_called_once_with(
        mode="report",
        trigger="summon",
        codebase_root="/project",
        repo="test/repo",
        github_token=None,
    )


def test_invoke_reaper_no_force():
    """T340: Reaper without --force raises PermissionError.

    Input: args=["reaper"], no force flag
    Expected: PermissionError
    """
    with pytest.raises(PermissionError, match="Reaper mode requires confirmation"):
        invoke_death_skill(
            args=["reaper"],
            codebase_root="/project",
            repo="test/repo",
        )


def test_format_report_output():
    """T350: format_report_output produces valid markdown.

    Input: ReconciliationReport with 1 finding and 1 action
    Expected: Markdown string containing Summary, Drift Findings, Proposed Actions, Next Steps
    """
    report: ReconciliationReport = {
        "age_number": 3,
        "trigger": "summon",
        "trigger_details": "DEATH summoned via /death command",
        "drift_report": {
            "findings": [
                {
                    "id": "DRIFT-001",
                    "severity": "critical",
                    "doc_file": "README.md",
                    "doc_claim": "12+ agents",
                    "code_reality": "36 agents",
                    "category": "count_mismatch",
                    "confidence": 0.95,
                    "evidence": "glob found 36",
                }
            ],
            "total_score": 10.0,
            "critical_count": 1,
            "major_count": 0,
            "minor_count": 0,
            "scanned_docs": ["README.md"],
            "scanned_code_paths": ["assemblyzero/"],
            "timestamp": "2026-02-17T12:45:00Z",
        },
        "actions": [
            {
                "target_file": "README.md",
                "action_type": "update_count",
                "description": "Update agent count from '12+' to '36'",
                "old_content": "12+",
                "new_content": "36",
                "drift_finding_id": "DRIFT-001",
            }
        ],
        "mode": "report",
        "timestamp": "2026-02-17T12:50:00Z",
        "summary": "DEATH found 1 drift finding (1 critical). 1 reconciliation action proposed.",
    }

    output = format_report_output(report)
    assert "# DEATH Reconciliation Report" in output
    assert "## Summary" in output
    assert "## Drift Findings" in output
    assert "## Proposed Actions" in output
    assert "## Next Steps" in output
    assert "DRIFT-001" in output
    assert "README.md" in output


def test_drift_probe_interface():
    """T220: Drift probe returns ProbeResult with required fields.

    Input: Mock codebase root
    Expected: ProbeResult with probe="drift", status, and findings
    """
    from assemblyzero.workflows.janitor.probes.drift import probe_drift

    with patch("assemblyzero.workflows.janitor.probes.drift.build_drift_report") as mock_report:
        mock_report.return_value = {
            "findings": [
                {
                    "id": "DRIFT-001",
                    "severity": "critical",
                    "doc_file": "README.md",
                    "doc_claim": "test",
                    "code_reality": "test",
                    "category": "count_mismatch",
                    "confidence": 0.9,
                    "evidence": "test",
                }
            ],
            "total_score": 10.0,
            "critical_count": 1,
            "major_count": 0,
            "minor_count": 0,
            "scanned_docs": ["README.md"],
            "scanned_code_paths": ["/project"],
            "timestamp": "2026-02-17T12:45:00Z",
        }

        result = probe_drift("/project")
        assert result.probe == "drift"
        assert result.status in ("ok", "findings", "error")
        assert result.status == "findings"
        assert len(result.findings) == 1
        assert result.findings[0].probe == "drift"
        assert result.findings[0].category == "count_mismatch"


def test_format_report_output_no_findings():
    """format_report_output with no findings produces correct output."""
    report: ReconciliationReport = {
        "age_number": 1,
        "trigger": "summon",
        "trigger_details": "DEATH summoned via /death command",
        "drift_report": {
            "findings": [],
            "total_score": 0.0,
            "critical_count": 0,
            "major_count": 0,
            "minor_count": 0,
            "scanned_docs": [],
            "scanned_code_paths": [],
            "timestamp": "2026-02-17T12:45:00Z",
        },
        "actions": [],
        "mode": "report",
        "timestamp": "2026-02-17T12:50:00Z",
        "summary": "DEATH found 0 drift finding(s) (none). 0 reconciliation action(s) proposed.",
    }

    output = format_report_output(report)
    assert "# DEATH Reconciliation Report — Age 1" in output
    assert "No drift findings detected." in output
    assert "No reconciliation actions needed." in output
    assert "REAPER MAN" in output


def test_parse_unknown_flag():
    """Unknown flag raises ValueError."""
    with pytest.raises(ValueError, match="Unknown flag"):
        parse_death_args(["reaper", "--unknown"])


@patch("assemblyzero.workflows.death.skill.run_death")
def test_invoke_reaper_with_force(mock_run):
    """Reaper with --force invokes run_death without raising."""
    mock_report: ReconciliationReport = {
        "age_number": 3,
        "trigger": "summon",
        "trigger_details": "DEATH summoned via /death command",
        "drift_report": {
            "findings": [],
            "total_score": 0.0,
            "critical_count": 0,
            "major_count": 0,
            "minor_count": 0,
            "scanned_docs": [],
            "scanned_code_paths": [],
            "timestamp": "2026-02-17T12:45:00Z",
        },
        "actions": [],
        "mode": "reaper",
        "timestamp": "2026-02-17T12:50:00Z",
        "summary": "No findings.",
    }
    mock_run.return_value = mock_report

    result = invoke_death_skill(
        args=["reaper", "--force"],
        codebase_root="/project",
        repo="test/repo",
    )
    assert result["mode"] == "reaper"
    mock_run.assert_called_once_with(
        mode="reaper",
        trigger="summon",
        codebase_root="/project",
        repo="test/repo",
        github_token=None,
    )


@patch("assemblyzero.workflows.death.skill.run_death")
def test_invoke_with_github_token(mock_run):
    """invoke_death_skill passes github_token through to run_death."""
    mock_run.return_value = {
        "age_number": 1,
        "trigger": "summon",
        "trigger_details": "test",
        "drift_report": {
            "findings": [],
            "total_score": 0.0,
            "critical_count": 0,
            "major_count": 0,
            "minor_count": 0,
            "scanned_docs": [],
            "scanned_code_paths": [],
            "timestamp": "2026-02-17T12:45:00Z",
        },
        "actions": [],
        "mode": "report",
        "timestamp": "2026-02-17T12:50:00Z",
        "summary": "test",
    }

    invoke_death_skill(
        args=["report"],
        codebase_root="/project",
        repo="test/repo",
        github_token="ghp_test123",
    )
    mock_run.assert_called_once_with(
        mode="report",
        trigger="summon",
        codebase_root="/project",
        repo="test/repo",
        github_token="ghp_test123",
    )


def test_format_report_reaper_mode():
    """format_report_output in reaper mode shows correct next steps."""
    report: ReconciliationReport = {
        "age_number": 2,
        "trigger": "summon",
        "trigger_details": "DEATH summoned via /death command",
        "drift_report": {
            "findings": [],
            "total_score": 0.0,
            "critical_count": 0,
            "major_count": 0,
            "minor_count": 0,
            "scanned_docs": [],
            "scanned_code_paths": [],
            "timestamp": "2026-02-17T12:45:00Z",
        },
        "actions": [],
        "mode": "reaper",
        "timestamp": "2026-02-17T12:50:00Z",
        "summary": "No findings.",
    }

    output = format_report_output(report)
    assert "write mode" in output
    assert "Changes have been applied" in output
```
