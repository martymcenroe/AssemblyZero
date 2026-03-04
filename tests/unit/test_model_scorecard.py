"""Unit tests for tools/model_scorecard.py."""

import json
import pytest
from datetime import datetime, timezone
from pathlib import Path

# Import under test — add tools/ to path since it's not a package
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tools"))
from model_scorecard import (
    extract_tokens_from_raw,
    estimate_cost,
    parse_review_logs,
    parse_workflow_audit,
    aggregate_by_model,
    aggregate_workflow_stats,
    parse_timestamp,
)


class TestExtractTokens:
    """Tests for token extraction from raw_response strings."""

    def test_gemini_format(self):
        raw = (
            'response:\nGenerateContentResponse(\n'
            '  "usage_metadata": {\n'
            '    "prompt_token_count": 3000,\n'
            '    "candidates_token_count": 1500,\n'
            '    "total_token_count": 4500\n'
            '  }\n'
            ')'
        )
        tokens = extract_tokens_from_raw(raw)
        assert tokens["input"] == 3000
        assert tokens["output"] == 1500
        assert tokens["total"] == 4500

    def test_claude_format(self):
        raw = json.dumps({
            "usage": {"input_tokens": 5000, "output_tokens": 2000}
        })
        tokens = extract_tokens_from_raw(raw)
        assert tokens["input"] == 5000
        assert tokens["output"] == 2000
        assert tokens["total"] == 7000

    def test_empty_raw(self):
        tokens = extract_tokens_from_raw("")
        assert tokens["input"] == 0
        assert tokens["output"] == 0
        assert tokens["total"] == 0

    def test_gemini_takes_precedence_over_claude(self):
        """If both formats present, Gemini fields win (they're checked first)."""
        raw = (
            '"prompt_token_count": 100, "candidates_token_count": 50, '
            '"input_tokens": 999, "output_tokens": 888'
        )
        tokens = extract_tokens_from_raw(raw)
        assert tokens["input"] == 100
        assert tokens["output"] == 50


class TestEstimateCost:
    """Tests for cost estimation."""

    def test_known_model(self):
        # gemini-3-pro-preview: $1.25/M input, $10.00/M output
        cost = estimate_cost("gemini-3-pro-preview", 1_000_000, 1_000_000)
        assert cost == pytest.approx(11.25)

    def test_unknown_model_uses_default(self):
        cost = estimate_cost("unknown-model", 1_000_000, 1_000_000)
        # Default: $5/M input, $25/M output
        assert cost == pytest.approx(30.00)

    def test_zero_tokens(self):
        assert estimate_cost("gemini-3-pro-preview", 0, 0) == 0.0

    def test_small_token_count(self):
        # 3000 input, 1500 output for gemini-3-pro
        cost = estimate_cost("gemini-3-pro-preview", 3000, 1500)
        expected = (3000 * 1.25 + 1500 * 10.00) / 1_000_000
        assert cost == pytest.approx(expected)


class TestParseTimestamp:
    def test_iso_with_offset(self):
        ts = parse_timestamp("2026-01-31T21:51:53.432454+00:00")
        assert ts.year == 2026
        assert ts.month == 1
        assert ts.tzinfo is not None

    def test_iso_with_z(self):
        ts = parse_timestamp("2026-02-15T10:00:00Z")
        assert ts.year == 2026
        assert ts.month == 2


class TestParseReviewLogs:
    """Tests for JSONL log parsing."""

    def _write_log(self, tmp_path: Path, entries: list[dict]) -> Path:
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        log_file = logs_dir / "test_session.jsonl"
        with log_file.open("w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
        return logs_dir

    def test_basic_parsing(self, tmp_path):
        logs_dir = self._write_log(tmp_path, [
            {
                "timestamp": "2026-02-01T10:00:00+00:00",
                "node": "review_lld",
                "model": "gemini-3-pro-preview",
                "verdict": "APPROVED",
                "issue_id": 42,
                "duration_ms": 5000,
                "raw_response": '"prompt_token_count": 3000, "candidates_token_count": 800, "total_token_count": 3800',
            }
        ])
        entries = parse_review_logs(logs_dir)
        assert len(entries) == 1
        assert entries[0]["model"] == "gemini-3-pro-preview"
        assert entries[0]["verdict"] == "APPROVED"
        assert entries[0]["input_tokens"] == 3000
        assert entries[0]["output_tokens"] == 800

    def test_since_filter(self, tmp_path):
        logs_dir = self._write_log(tmp_path, [
            {"timestamp": "2026-01-15T10:00:00+00:00", "node": "review_lld",
             "model": "m1", "verdict": "BLOCK", "issue_id": 1, "duration_ms": 100, "raw_response": ""},
            {"timestamp": "2026-02-15T10:00:00+00:00", "node": "review_lld",
             "model": "m1", "verdict": "APPROVED", "issue_id": 2, "duration_ms": 200, "raw_response": ""},
        ])
        since = datetime(2026, 2, 1, tzinfo=timezone.utc)
        entries = parse_review_logs(logs_dir, since=since)
        assert len(entries) == 1
        assert entries[0]["issue_id"] == 2

    def test_node_filter(self, tmp_path):
        logs_dir = self._write_log(tmp_path, [
            {"timestamp": "2026-02-01T10:00:00+00:00", "node": "design_lld",
             "model": "m1", "verdict": "DRAFTED", "issue_id": 1, "duration_ms": 100, "raw_response": ""},
            {"timestamp": "2026-02-01T11:00:00+00:00", "node": "review_lld",
             "model": "m1", "verdict": "APPROVED", "issue_id": 1, "duration_ms": 200, "raw_response": ""},
        ])
        entries = parse_review_logs(logs_dir, node_filter="review_lld")
        assert len(entries) == 1
        assert entries[0]["node"] == "review_lld"

    def test_malformed_json_skipped(self, tmp_path):
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        log_file = logs_dir / "bad.jsonl"
        log_file.write_text("not json\n{bad\n", encoding="utf-8")
        entries = parse_review_logs(logs_dir)
        assert entries == []


class TestAggregateByModel:
    """Tests for model aggregation."""

    def test_single_model(self):
        entries = [
            {"model": "m1", "verdict": "APPROVED", "cost_usd": 0.10,
             "input_tokens": 1000, "output_tokens": 500, "total_tokens": 1500, "duration_ms": 3000},
            {"model": "m1", "verdict": "BLOCK", "cost_usd": 0.10,
             "input_tokens": 1000, "output_tokens": 500, "total_tokens": 1500, "duration_ms": 4000},
        ]
        stats = aggregate_by_model(entries)
        assert "m1" in stats
        assert stats["m1"]["runs"] == 2
        assert stats["m1"]["approved"] == 1
        assert stats["m1"]["approval_rate"] == pytest.approx(50.0)
        assert stats["m1"]["total_cost"] == pytest.approx(0.20)
        assert stats["m1"]["cost_per_approval"] == pytest.approx(0.20)

    def test_multiple_models(self):
        entries = [
            {"model": "m1", "verdict": "APPROVED", "cost_usd": 1.00,
             "input_tokens": 10000, "output_tokens": 5000, "total_tokens": 15000, "duration_ms": 5000},
            {"model": "m2", "verdict": "APPROVED", "cost_usd": 0.30,
             "input_tokens": 12000, "output_tokens": 4000, "total_tokens": 16000, "duration_ms": 3000},
        ]
        stats = aggregate_by_model(entries)
        assert len(stats) == 2
        assert stats["m1"]["cost_per_approval"] == pytest.approx(1.00)
        assert stats["m2"]["cost_per_approval"] == pytest.approx(0.30)

    def test_no_approvals(self):
        entries = [
            {"model": "m1", "verdict": "BLOCK", "cost_usd": 0.50,
             "input_tokens": 1000, "output_tokens": 500, "total_tokens": 1500, "duration_ms": 2000},
        ]
        stats = aggregate_by_model(entries)
        assert stats["m1"]["cost_per_approval"] == float("inf")
        assert stats["m1"]["approval_rate"] == 0.0

    def test_empty_entries(self):
        assert aggregate_by_model([]) == {}

    def test_token_efficiency(self):
        entries = [
            {"model": "m1", "verdict": "APPROVED", "cost_usd": 0.10,
             "input_tokens": 10000, "output_tokens": 4000, "total_tokens": 14000, "duration_ms": 1000},
        ]
        stats = aggregate_by_model(entries)
        assert stats["m1"]["token_efficiency"] == pytest.approx(0.4)


class TestParseWorkflowAudit:
    """Tests for workflow audit parsing."""

    def test_basic_parsing(self, tmp_path):
        audit_file = tmp_path / "audit.jsonl"
        audit_file.write_text(json.dumps({
            "timestamp": "2026-02-01T10:00:00+00:00",
            "workflow_type": "lld",
            "issue_number": 42,
            "event": "complete",
            "details": {"iteration_count": 3, "verdict_count": 2},
        }) + "\n", encoding="utf-8")
        events = parse_workflow_audit(audit_file)
        assert len(events) == 1
        assert events[0]["event"] == "complete"

    def test_missing_file(self, tmp_path):
        events = parse_workflow_audit(tmp_path / "nonexistent.jsonl")
        assert events == []


class TestAggregateWorkflowStats:
    def test_mixed_events(self):
        events = [
            {"event": "complete", "details": {"iteration_count": 3}},
            {"event": "complete", "details": {"iteration_count": 2}},
            {"event": "error", "details": {}},
            {"event": "max_iterations", "details": {"iteration_count": 5}},
            {"event": "complete", "details": {"iteration_count": 0}},  # zero iters excluded from avg
        ]
        # Add required fields
        for i, e in enumerate(events):
            e["issue_number"] = i
            e["workflow_type"] = "lld"
            e["timestamp"] = datetime(2026, 2, 1, tzinfo=timezone.utc)

        stats = aggregate_workflow_stats(events)
        assert stats["completions"] == 3
        assert stats["errors"] == 1
        assert stats["max_iterations_hit"] == 1
        assert stats["avg_iterations"] == pytest.approx(2.5)  # (3+2) / 2 (zero excluded)
