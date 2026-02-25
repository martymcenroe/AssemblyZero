"""Tests for enriched .implement-status-{issue}.json — event timeline and state data."""

from __future__ import annotations

import json
from pathlib import Path

from tools.run_implement_from_lld import _write_status_file


def _read_status(tmp_path: Path, issue: int) -> dict:
    """Helper: read and parse the status file."""
    status_file = tmp_path / f".implement-status-{issue}.json"
    return json.loads(status_file.read_text(encoding="utf-8"))


class TestBasicStatusFile:
    """Verify basic fields are always present."""

    def test_basic_status_file_structure(self, tmp_path):
        """Status file has issue, status, timestamp, repo."""
        _write_status_file(tmp_path, 100, "SUCCESS")

        data = _read_status(tmp_path, 100)
        assert data["issue"] == 100
        assert data["status"] == "SUCCESS"
        assert "timestamp" in data
        assert data["repo"] == str(tmp_path)

    def test_failed_status_includes_error(self, tmp_path):
        """Error field present when error string is provided."""
        _write_status_file(tmp_path, 101, "FAILED", "Coverage stagnant: 9.0% -> 9.0%")

        data = _read_status(tmp_path, 101)
        assert data["status"] == "FAILED"
        assert data["error"] == "Coverage stagnant: 9.0% -> 9.0%"


class TestStateEnrichment:
    """Verify state dict enriches the status file."""

    def test_state_enrichment_adds_iteration_data(self, tmp_path):
        """Iteration, coverage, and file lists extracted from state."""
        state = {
            "iteration_count": 3,
            "max_iterations": 5,
            "coverage_achieved": 45.0,
            "coverage_target": 95,
            "previous_coverage": 30.0,
            "test_files": ["tests/unit/test_foo.py"],
            "implementation_files": ["src/foo.py", "src/bar.py"],
        }
        _write_status_file(tmp_path, 200, "FAILED", "Low coverage", state=state)

        data = _read_status(tmp_path, 200)
        assert data["iterations"] == 3
        assert data["max_iterations"] == 5
        assert data["coverage_achieved"] == 45.0
        assert data["coverage_target"] == 95
        assert data["previous_coverage"] == 30.0
        assert data["test_files"] == ["tests/unit/test_foo.py"]
        assert data["implementation_files"] == ["src/foo.py", "src/bar.py"]

    def test_state_enrichment_adds_token_budget(self, tmp_path):
        """Token usage and budget included when estimated_tokens_used is set."""
        state = {
            "estimated_tokens_used": 45000,
            "token_budget": 200000,
        }
        _write_status_file(tmp_path, 201, "FAILED", "Token limit", state=state)

        data = _read_status(tmp_path, 201)
        assert data["tokens_used"] == 45000
        assert data["token_budget"] == 200000

    def test_no_token_fields_when_not_estimated(self, tmp_path):
        """Token fields omitted when estimated_tokens_used is absent."""
        state = {"iteration_count": 1}
        _write_status_file(tmp_path, 202, "SUCCESS", state=state)

        data = _read_status(tmp_path, 202)
        assert "tokens_used" not in data
        assert "token_budget" not in data


class TestEventTimeline:
    """Verify event timeline from audit JSONL."""

    def _write_audit(self, repo_root: Path, entries: list[dict]) -> None:
        """Helper: write JSONL audit file."""
        lineage_dir = repo_root / "docs" / "lineage"
        lineage_dir.mkdir(parents=True, exist_ok=True)
        lines = [json.dumps(e) for e in entries]
        (lineage_dir / "workflow-audit.jsonl").write_text(
            "\n".join(lines), encoding="utf-8"
        )

    def test_event_timeline_from_audit_trail(self, tmp_path):
        """Events matching issue number appear in status file."""
        self._write_audit(tmp_path, [
            {
                "timestamp": "2026-02-25T20:25:57Z",
                "event": "start",
                "issue_number": 300,
                "details": {"scenario_count": 25},
            },
            {
                "timestamp": "2026-02-25T20:26:25Z",
                "event": "test_plan_reviewed",
                "issue_number": 300,
                "details": {"status": "APPROVED"},
            },
        ])

        _write_status_file(tmp_path, 300, "SUCCESS", state={"iteration_count": 1})

        data = _read_status(tmp_path, 300)
        assert "events" in data
        assert len(data["events"]) == 2
        assert data["events"][0]["event"] == "start"
        assert data["events"][0]["time"] == "2026-02-25T20:25:57Z"
        assert data["events"][0]["details"]["scenario_count"] == 25
        assert data["events"][1]["event"] == "test_plan_reviewed"

    def test_event_timeline_filters_by_issue(self, tmp_path):
        """Only events for the matching issue are included."""
        self._write_audit(tmp_path, [
            {
                "timestamp": "2026-02-25T20:00:00Z",
                "event": "start",
                "issue_number": 301,
                "details": {},
            },
            {
                "timestamp": "2026-02-25T20:01:00Z",
                "event": "start",
                "issue_number": 302,
                "details": {},
            },
            {
                "timestamp": "2026-02-25T20:02:00Z",
                "event": "implementation_generated",
                "issue_number": 301,
                "details": {"iteration": 0},
            },
        ])

        _write_status_file(tmp_path, 301, "SUCCESS", state={"iteration_count": 1})

        data = _read_status(tmp_path, 301)
        assert len(data["events"]) == 2
        assert all(e["event"] != "start" or e["time"] != "2026-02-25T20:01:00Z"
                    for e in data["events"])

    def test_missing_audit_file_no_crash(self, tmp_path):
        """No crash when audit JSONL doesn't exist; no events key."""
        _write_status_file(tmp_path, 303, "SUCCESS", state={"iteration_count": 1})

        data = _read_status(tmp_path, 303)
        assert "events" not in data


class TestBackwardCompatibility:
    """Ensure old callers (state=None) still work."""

    def test_backward_compatible_no_state(self, tmp_path):
        """Without state, only basic 4-5 fields present."""
        _write_status_file(tmp_path, 400, "FAILED", "some error")

        data = _read_status(tmp_path, 400)
        assert set(data.keys()) == {"issue", "status", "timestamp", "repo", "error"}

    def test_backward_compatible_success_no_state(self, tmp_path):
        """Success without state has exactly 4 fields."""
        _write_status_file(tmp_path, 401, "SUCCESS")

        data = _read_status(tmp_path, 401)
        assert set(data.keys()) == {"issue", "status", "timestamp", "repo"}
