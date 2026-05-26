"""Unit tests for tools/audit_cerberus_health.py.

Tests the classification function with mock workflow-run shapes. Does NOT
make live gh API calls -- the API boundary is upstream of classify().

Issue: martymcenroe/AssemblyZero#1284
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(_TOOLS))

from audit_cerberus_health import (  # noqa: E402
    HEALTHY,
    NOT_DEPLOYED,
    UNCERTAIN,
    UNKNOWN,
    classify,
    is_dependabot_run,
    parse_iso,
)


def _ts(days_ago: int) -> str:
    """Make an ISO timestamp `days_ago` days before now (UTC)."""
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _run(conclusion: str, days_ago: int, **extra) -> dict:
    """Build a minimal workflow_run dict for tests."""
    run = {
        "name": "Auto Review",
        "conclusion": conclusion,
        "created_at": _ts(days_ago),
        "actor": {"login": "martymcenroe"},
        "head_branch": "feature/some-branch",
    }
    run.update(extra)
    return run


class TestParseIso:
    def test_z_suffix(self):
        dt = parse_iso("2026-05-25T14:00:00Z")
        assert dt is not None
        assert dt.tzinfo is not None

    def test_offset_suffix(self):
        dt = parse_iso("2026-05-25T14:00:00+00:00")
        assert dt is not None

    def test_empty(self):
        assert parse_iso("") is None

    def test_garbage(self):
        assert parse_iso("not a timestamp") is None


class TestIsDependabotRun:
    def test_actor_dependabot(self):
        assert is_dependabot_run({
            "actor": {"login": "dependabot[bot]"},
            "head_branch": "main",
        })

    def test_branch_dependabot(self):
        assert is_dependabot_run({
            "actor": {"login": "martymcenroe"},
            "head_branch": "dependabot/pip/foo-bar",
        })

    def test_normal_branch_normal_actor(self):
        assert not is_dependabot_run({
            "actor": {"login": "martymcenroe"},
            "head_branch": "feature/x",
        })

    def test_missing_fields(self):
        assert not is_dependabot_run({})


class TestClassify:
    def test_healthy_on_success(self):
        runs = [_run("success", 1)]
        status = classify("myrepo", runs, days=30)
        assert status.classification == HEALTHY
        assert "success" in status.detail
        assert status.last_run_ts

    def test_uncertain_on_failure(self):
        runs = [_run("failure", 1)]
        status = classify("myrepo", runs, days=30)
        assert status.classification == UNCERTAIN
        assert "failure" in status.detail.lower()

    def test_uncertain_on_startup_failure(self):
        runs = [_run("startup_failure", 1)]
        status = classify("myrepo", runs, days=30)
        assert status.classification == UNCERTAIN
        assert "mode a" in status.detail.lower()

    def test_unknown_on_no_runs(self):
        status = classify("myrepo", [], days=30)
        assert status.classification == UNKNOWN
        assert "no non-dependabot" in status.detail.lower()

    def test_unknown_when_only_old_runs(self):
        runs = [_run("success", 60)]
        status = classify("myrepo", runs, days=30)
        assert status.classification == UNKNOWN

    def test_unknown_when_only_dependabot_runs(self):
        runs = [_run("success", 1, actor={"login": "dependabot[bot]"})]
        status = classify("myrepo", runs, days=30)
        assert status.classification == UNKNOWN

    def test_picks_most_recent_among_relevant(self):
        # Old failure, recent success -> HEALTHY
        runs = [
            _run("failure", 20),
            _run("success", 1),
            _run("failure", 10),
        ]
        status = classify("myrepo", runs, days=30)
        assert status.classification == HEALTHY

    def test_picks_most_recent_failure(self):
        # Old success, recent failure -> UNCERTAIN
        runs = [
            _run("success", 20),
            _run("failure", 1),
        ]
        status = classify("myrepo", runs, days=30)
        assert status.classification == UNCERTAIN

    def test_ignores_dependabot_runs_in_classification(self):
        # Recent success on dependabot/* shouldn't make a repo HEALTHY
        # (dependabot Auto Review runs are architecturally irrelevant to
        # key health). The non-dependabot history determines the verdict.
        runs = [
            _run("success", 1, head_branch="dependabot/pip/foo"),
            _run("failure", 5),  # the real signal
        ]
        status = classify("myrepo", runs, days=30)
        assert status.classification == UNCERTAIN
        assert "failure" in status.detail.lower()

    def test_days_window_respected(self):
        # 7-day window with a 10-day-old success -> UNKNOWN
        runs = [_run("success", 10)]
        status = classify("myrepo", runs, days=7)
        assert status.classification == UNKNOWN
