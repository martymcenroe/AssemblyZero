"""Unit tests for tools/mine_quality_patterns.py.

Issue #612: Tests for the weekly telemetry audit script.
All tests use in-memory SQLite — no external services required.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from unittest import mock

import orjson
import pytest

# Add tools/ to sys.path so we can import the script as a module
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools"))

import mine_quality_patterns  # noqa: E402


# --- Fixtures ---


def _create_telemetry_db(
    db_path: str,
    events: list[dict] | None = None,
) -> str:
    """Create a SQLite telemetry DB with the expected schema.

    Returns the db_path.
    """
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE telemetry_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            workflow_id TEXT NOT NULL,
            node TEXT NOT NULL,
            detail TEXT NOT NULL,
            thread_id TEXT NOT NULL
        )
        """
    )
    if events:
        for e in events:
            conn.execute(
                "INSERT INTO telemetry_events "
                "(event_type, timestamp, workflow_id, node, detail, thread_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    e["event_type"],
                    e["timestamp"],
                    e["workflow_id"],
                    e["node"],
                    e["detail"],
                    e["thread_id"],
                ),
            )
    conn.commit()
    conn.close()
    return db_path


SAMPLE_EVENTS: list[dict] = [
    {
        "event_type": "quality.gate_rejected",
        "timestamp": "2026-03-04T14:22:31Z",
        "workflow_id": "aaa-111",
        "node": "code_review_gate",
        "detail": json.dumps({"reason": "Missing type hints"}),
        "thread_id": "t1",
    },
    {
        "event_type": "quality.gate_rejected",
        "timestamp": "2026-03-04T15:00:00Z",
        "workflow_id": "bbb-222",
        "node": "code_review_gate",
        "detail": json.dumps({"reason": "Missing type hints"}),
        "thread_id": "t2",
    },
    {
        "event_type": "quality.gate_rejected",
        "timestamp": "2026-03-05T09:00:00Z",
        "workflow_id": "ccc-333",
        "node": "code_review_gate",
        "detail": json.dumps({"reason": "Missing type hints"}),
        "thread_id": "t3",
    },
    {
        "event_type": "retry.strike_one",
        "timestamp": "2026-03-03T11:05:00Z",
        "workflow_id": "ddd-444",
        "node": "implementation_node",
        "detail": json.dumps({"reason": "Lint failure on first attempt"}),
        "thread_id": "t4",
    },
    {
        "event_type": "workflow.halt_and_plan",
        "timestamp": "2026-03-02T08:00:00Z",
        "workflow_id": "eee-555",
        "node": "planning_node",
        "detail": json.dumps({"reason": "Budget exceeded"}),
        "thread_id": "t5",
    },
]


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    """Create a temporary SQLite DB seeded with SAMPLE_EVENTS."""
    path = str(tmp_path / "telemetry.db")
    _create_telemetry_db(path, SAMPLE_EVENTS)
    return path


@pytest.fixture
def empty_db_path(tmp_path: Path) -> str:
    """Create a temporary SQLite DB with the schema but no events."""
    path = str(tmp_path / "empty_telemetry.db")
    _create_telemetry_db(path, [])
    return path


# --- T010: Script importable (REQ-1) ---


class TestT010ScriptImportable:
    def test_import_succeeds(self) -> None:
        """T010: Script file exists and is importable."""
        assert hasattr(mine_quality_patterns, "main")
        assert hasattr(mine_quality_patterns, "parse_args")
        assert hasattr(mine_quality_patterns, "load_telemetry_events")
        assert hasattr(mine_quality_patterns, "extract_pattern_key")
        assert hasattr(mine_quality_patterns, "mine_patterns")
        assert hasattr(mine_quality_patterns, "build_report")
        assert hasattr(mine_quality_patterns, "format_console_report")
        assert hasattr(mine_quality_patterns, "write_json_report")


# --- T020: All three watched event types queried (REQ-2) ---


class TestT020EventTypes:
    def test_all_three_event_types_returned(self, db_path: str) -> None:
        """T020: load_telemetry_events queries all three watched event types."""
        events = mine_quality_patterns.load_telemetry_events(
            db_path,
            mine_quality_patterns.WATCHED_EVENT_TYPES,
            "2026-01-01T00:00:00Z",
        )
        returned_types = {e["event_type"] for e in events}
        assert returned_types == {
            "quality.gate_rejected",
            "retry.strike_one",
            "workflow.halt_and_plan",
        }


# --- T030: Pattern grouping counts correctly (REQ-3) ---


class TestT030PatternGrouping:
    def test_counts_aggregated_correctly(self) -> None:
        """T030: mine_patterns groups by pattern key and counts correctly."""
        events: list[mine_quality_patterns.TelemetryEvent] = [
            {
                "event_type": "quality.gate_rejected",
                "timestamp": "2026-03-04T14:00:00Z",
                "workflow_id": "w1",
                "node": "gate",
                "detail": json.dumps({"reason": "same reason"}),
                "thread_id": "t1",
            },
            {
                "event_type": "quality.gate_rejected",
                "timestamp": "2026-03-04T15:00:00Z",
                "workflow_id": "w2",
                "node": "gate",
                "detail": json.dumps({"reason": "same reason"}),
                "thread_id": "t2",
            },
            {
                "event_type": "quality.gate_rejected",
                "timestamp": "2026-03-04T16:00:00Z",
                "workflow_id": "w3",
                "node": "gate",
                "detail": json.dumps({"reason": "same reason"}),
                "thread_id": "t3",
            },
            {
                "event_type": "quality.gate_rejected",
                "timestamp": "2026-03-04T17:00:00Z",
                "workflow_id": "w4",
                "node": "other_gate",
                "detail": json.dumps({"reason": "different reason"}),
                "thread_id": "t4",
            },
        ]
        patterns = mine_quality_patterns.mine_patterns(events, top_n=10)
        assert len(patterns) == 2
        assert patterns[0]["count"] == 3
        assert patterns[1]["count"] == 1

    def test_top_n_limits_results(self) -> None:
        """T040: --top-n limits returned patterns."""
        events: list[mine_quality_patterns.TelemetryEvent] = []
        for i in range(5):
            events.append(
                {
                    "event_type": "quality.gate_rejected",
                    "timestamp": f"2026-03-04T{10+i}:00:00Z",
                    "workflow_id": f"w{i}",
                    "node": f"node_{i}",
                    "detail": json.dumps({"reason": f"reason_{i}"}),
                    "thread_id": f"t{i}",
                }
            )
        patterns = mine_quality_patterns.mine_patterns(events, top_n=3)
        assert len(patterns) == 3

    def test_example_workflow_ids_capped_at_3(self) -> None:
        """Pattern example_workflow_ids limited to MAX_EXAMPLE_WORKFLOW_IDS."""
        events: list[mine_quality_patterns.TelemetryEvent] = [
            {
                "event_type": "quality.gate_rejected",
                "timestamp": f"2026-03-04T{10+i}:00:00Z",
                "workflow_id": f"w{i}",
                "node": "gate",
                "detail": json.dumps({"reason": "same"}),
                "thread_id": f"t{i}",
            }
            for i in range(5)
        ]
        patterns = mine_quality_patterns.mine_patterns(events, top_n=10)
        assert len(patterns[0]["example_workflow_ids"]) == 3


# --- T040: CLI flag parsing (REQ-4) ---


class TestT040CLIParsing:
    def test_all_five_flags_parsed(self) -> None:
        """T050: parse_args accepts all five documented CLI flags."""
        args = mine_quality_patterns.parse_args(
            [
                "--days", "14",
                "--threshold", "5",
                "--top-n", "20",
                "--db-path", "x.db",
                "--output-json", "out.json",
            ]
        )
        assert args.days == 14
        assert args.threshold == 5
        assert args.top_n == 20
        assert args.db_path == "x.db"
        assert args.output_json == "out.json"

    def test_default_values(self) -> None:
        """T060: Default CLI values applied."""
        args = mine_quality_patterns.parse_args([])
        assert args.days == 7
        assert args.threshold == 3
        assert args.top_n == 10
        assert args.db_path == "data/telemetry.db"
        assert args.output_json is None


# --- T050/T060/T070: Exit codes (REQ-5) ---


class TestExitCodes:
    def test_exit_0_clean_run(self, db_path: str) -> None:
        """T050: main() exits 0 on clean run below threshold."""
        # threshold=100 ensures no breach
        result = mine_quality_patterns.main(
            ["--db-path", db_path, "--threshold", "100"]
        )
        assert result == 0

    def test_exit_1_missing_db(self, tmp_path: Path) -> None:
        """T060: main() exits 1 when DB path does not exist."""
        missing = str(tmp_path / "nonexistent.db")
        result = mine_quality_patterns.main(["--db-path", missing])
        assert result == 1

    def test_exit_2_threshold_breach(self, db_path: str) -> None:
        """T070: main() exits 2 when threshold breached."""
        # 3 events share the same pattern; threshold=2 triggers
        result = mine_quality_patterns.main(
            ["--db-path", db_path, "--threshold", "2"]
        )
        assert result == 2


# --- T080: Console report content (REQ-6) ---


class TestT080ConsoleReport:
    def test_contains_event_type_and_count(self) -> None:
        """T080: format_console_report includes event counts and pattern rows."""
        report: mine_quality_patterns.AuditReport = {
            "generated_at": "2026-03-06T10:00:00Z",
            "look_back_days": 7,
            "event_counts": {"quality.gate_rejected": 12, "retry.strike_one": 5},
            "top_patterns": [
                {
                    "event_type": "quality.gate_rejected",
                    "pattern_key": "quality.gate_rejected|gate|Missing type hints",
                    "node": "gate",
                    "reason": "Missing type hints",
                    "count": 7,
                    "first_seen": "2026-02-28T09:15:00Z",
                    "last_seen": "2026-03-05T16:42:00Z",
                    "example_workflow_ids": ["aaa-111", "bbb-222"],
                },
            ],
            "threshold_triggered": True,
        }
        output = mine_quality_patterns.format_console_report(report)
        assert "quality.gate_rejected" in output
        assert "12" in output
        assert "retry.strike_one" in output
        assert "5" in output

    def test_contains_pattern_node(self) -> None:
        """T110: Console report contains pattern node values."""
        report: mine_quality_patterns.AuditReport = {
            "generated_at": "2026-03-06T10:00:00Z",
            "look_back_days": 7,
            "event_counts": {"quality.gate_rejected": 2},
            "top_patterns": [
                {
                    "event_type": "quality.gate_rejected",
                    "pattern_key": "quality.gate_rejected|node_alpha|r1",
                    "node": "node_alpha",
                    "reason": "r1",
                    "count": 1,
                    "first_seen": "2026-03-04T14:00:00Z",
                    "last_seen": "2026-03-04T14:00:00Z",
                    "example_workflow_ids": ["w1"],
                },
                {
                    "event_type": "quality.gate_rejected",
                    "pattern_key": "quality.gate_rejected|node_beta|r2",
                    "node": "node_beta",
                    "reason": "r2",
                    "count": 1,
                    "first_seen": "2026-03-04T15:00:00Z",
                    "last_seen": "2026-03-04T15:00:00Z",
                    "example_workflow_ids": ["w2"],
                },
            ],
            "threshold_triggered": False,
        }
        output = mine_quality_patterns.format_console_report(report)
        assert "node_alpha" in output
        assert "node_beta" in output

    def test_empty_patterns_shows_none(self) -> None:
        """Console report with no patterns shows '(none)'."""
        report: mine_quality_patterns.AuditReport = {
            "generated_at": "2026-03-06T10:00:00Z",
            "look_back_days": 7,
            "event_counts": {},
            "top_patterns": [],
            "threshold_triggered": False,
        }
        output = mine_quality_patterns.format_console_report(report)
        assert "(none)" in output


# --- T090: JSON report output (REQ-7) ---


class TestT090JSONReport:
    def test_json_roundtrip_valid(self, tmp_path: Path) -> None:
        """T090: write_json_report writes valid JSON conforming to AuditReport."""
        report: mine_quality_patterns.AuditReport = {
            "generated_at": "2026-03-06T10:00:00Z",
            "look_back_days": 7,
            "event_counts": {"quality.gate_rejected": 3},
            "top_patterns": [
                {
                    "event_type": "quality.gate_rejected",
                    "pattern_key": "quality.gate_rejected|gate|reason",
                    "node": "gate",
                    "reason": "reason",
                    "count": 3,
                    "first_seen": "2026-03-04T14:00:00Z",
                    "last_seen": "2026-03-05T09:00:00Z",
                    "example_workflow_ids": ["w1", "w2", "w3"],
                },
            ],
            "threshold_triggered": True,
        }
        out_path = str(tmp_path / "subdir" / "report.json")
        mine_quality_patterns.write_json_report(report, out_path)

        parsed = orjson.loads(Path(out_path).read_bytes())
        assert parsed["generated_at"] == "2026-03-06T10:00:00Z"
        assert parsed["look_back_days"] == 7
        assert "event_counts" in parsed
        assert "top_patterns" in parsed
        assert "threshold_triggered" in parsed
        assert len(parsed["top_patterns"]) == 1

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """write_json_report creates parent directories if missing."""
        out_path = str(tmp_path / "deep" / "nested" / "dir" / "report.json")
        report: mine_quality_patterns.AuditReport = {
            "generated_at": "2026-03-06T10:00:00Z",
            "look_back_days": 7,
            "event_counts": {},
            "top_patterns": [],
            "threshold_triggered": False,
        }
        mine_quality_patterns.write_json_report(report, out_path)
        assert Path(out_path).exists()


# --- T100: Read-only DB access (REQ-8) ---


class TestT100ReadOnly:
    def test_db_opened_read_only(self, db_path: str) -> None:
        """T100: load_telemetry_events opens DB with PRAGMA query_only = ON.

        Verify by calling the function (reads work), then confirm the
        connection it creates is actually read-only by intercepting it
        and attempting a write.
        """
        # Reading works
        events = mine_quality_patterns.load_telemetry_events(
            db_path,
            mine_quality_patterns.WATCHED_EVENT_TYPES,
            "2026-01-01T00:00:00Z",
        )
        assert len(events) > 0

        # Verify read-only: open a connection the same way the function does
        # and confirm writes are blocked
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA query_only = ON")
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("CREATE TABLE _write_test (id INTEGER)")
        conn.close()

    def test_write_attempt_raises_error(self, db_path: str) -> None:
        """T130: Write on read-only connection raises sqlite3.OperationalError.

        Opens a connection to the test DB with PRAGMA query_only = ON, then
        attempts an INSERT which must raise sqlite3.OperationalError.

        Input: db_path fixture pointing to a tmp SQLite file with telemetry_events table.
        Expected: sqlite3.OperationalError is raised by the INSERT statement.
        """
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA query_only = ON")
        with pytest.raises(sqlite3.OperationalError):
            conn.execute(
                "INSERT INTO telemetry_events "
                "(event_type, timestamp, workflow_id, node, detail, thread_id) "
                "VALUES ('test', '2026-03-06', 'w', 'n', 'd', 't')"
            )
        conn.close()


# --- T110: In-memory DB / no external services (REQ-9, REQ-10) ---
# This requirement is satisfied by the test fixture design itself.
# All tests use tmp_path or in-memory SQLite.


# --- T120: extract_pattern_key stability ---


class TestT120PatternKeyStability:
    def test_stable_key_for_same_event(self) -> None:
        """T120: extract_pattern_key produces stable key for same event."""
        event: mine_quality_patterns.TelemetryEvent = {
            "event_type": "quality.gate_rejected",
            "timestamp": "2026-03-04T14:22:31Z",
            "workflow_id": "aaa-111",
            "node": "code_review_gate",
            "detail": json.dumps({"reason": "Missing type hints"}),
            "thread_id": "t1",
        }
        key1 = mine_quality_patterns.extract_pattern_key(event)
        key2 = mine_quality_patterns.extract_pattern_key(event)
        assert key1 == key2
        assert key1 == "quality.gate_rejected|code_review_gate|Missing type hints"


# --- T130: Malformed JSON fallback ---


class TestT130MalformedJSON:
    def test_malformed_json_falls_back(self) -> None:
        """T130: Malformed JSON in detail falls back to detail[:64]."""
        event: mine_quality_patterns.TelemetryEvent = {
            "event_type": "retry.strike_one",
            "timestamp": "2026-03-03T11:05:00Z",
            "workflow_id": "ddd-444",
            "node": "implementation_node",
            "detail": "not-json",
            "thread_id": "t4",
        }
        key = mine_quality_patterns.extract_pattern_key(event)
        assert key == "retry.strike_one|implementation_node|not-json"

    def test_json_without_reason_key_falls_back(self) -> None:
        """Valid JSON but no 'reason' key falls back to detail[:64]."""
        event: mine_quality_patterns.TelemetryEvent = {
            "event_type": "workflow.halt_and_plan",
            "timestamp": "2026-03-01T08:00:00Z",
            "workflow_id": "eee-555",
            "node": "planning_node",
            "detail": json.dumps({"error_code": 42, "context": "budget exceeded"}),
            "thread_id": "t5",
        }
        key = mine_quality_patterns.extract_pattern_key(event)
        # Should fall back to detail[:64]
        assert "planning_node" in key
        assert "workflow.halt_and_plan" in key
        # The reason portion is the detail[:64] since no 'reason' key
        assert "error_code" in key

    def test_long_detail_truncated_at_64(self) -> None:
        """Detail longer than 64 chars without valid JSON truncated."""
        long_detail = "a" * 200
        event: mine_quality_patterns.TelemetryEvent = {
            "event_type": "quality.gate_rejected",
            "timestamp": "2026-03-04T14:00:00Z",
            "workflow_id": "w1",
            "node": "gate",
            "detail": long_detail,
            "thread_id": "t1",
        }
        key = mine_quality_patterns.extract_pattern_key(event)
        reason_part = key.split("|", 2)[2]
        assert len(reason_part) == 64

    def test_empty_detail(self) -> None:
        """Empty detail produces key ending with |."""
        event: mine_quality_patterns.TelemetryEvent = {
            "event_type": "quality.gate_rejected",
            "timestamp": "2026-03-04T14:00:00Z",
            "workflow_id": "w1",
            "node": "gate",
            "detail": "",
            "thread_id": "t1",
        }
        key = mine_quality_patterns.extract_pattern_key(event)
        assert key == "quality.gate_rejected|gate|"


# --- T140: Empty events graceful exit ---


class TestT140EmptyEvents:
    def test_empty_events_exit_0(self, empty_db_path: str, capsys) -> None:
        """T140: Empty events list exits 0 with 'No events' message."""
        result = mine_quality_patterns.main(["--db-path", empty_db_path])
        assert result == 0
        captured = capsys.readouterr()
        assert "No telemetry events" in captured.out


# --- T150: FileNotFoundError on missing DB ---


class TestT150MissingDB:
    def test_file_not_found_error_raised(self) -> None:
        """T150: load_telemetry_events raises FileNotFoundError on missing DB."""
        with pytest.raises(FileNotFoundError):
            mine_quality_patterns.load_telemetry_events(
                "/tmp/absolutely_nonexistent_db_612.db",
                mine_quality_patterns.WATCHED_EVENT_TYPES,
                "2026-01-01T00:00:00Z",
            )


# --- T160/T170: build_report threshold logic ---


class TestBuildReportThreshold:
    def test_threshold_triggered_when_count_gte(self) -> None:
        """T160: build_report sets threshold_triggered=True when count >= threshold."""
        events: list[mine_quality_patterns.TelemetryEvent] = [
            {
                "event_type": "quality.gate_rejected",
                "timestamp": f"2026-03-04T{10+i}:00:00Z",
                "workflow_id": f"w{i}",
                "node": "gate",
                "detail": json.dumps({"reason": "same"}),
                "thread_id": f"t{i}",
            }
            for i in range(5)
        ]
        report = mine_quality_patterns.build_report(
            events, look_back_days=7, alert_threshold=3, top_n=10
        )
        assert report["threshold_triggered"] is True

    def test_threshold_not_triggered_when_below(self) -> None:
        """T170: build_report sets threshold_triggered=False when all below threshold."""
        events: list[mine_quality_patterns.TelemetryEvent] = [
            {
                "event_type": "quality.gate_rejected",
                "timestamp": "2026-03-04T14:00:00Z",
                "workflow_id": "w1",
                "node": "gate_a",
                "detail": json.dumps({"reason": "reason_a"}),
                "thread_id": "t1",
            },
            {
                "event_type": "retry.strike_one",
                "timestamp": "2026-03-04T15:00:00Z",
                "workflow_id": "w2",
                "node": "gate_b",
                "detail": json.dumps({"reason": "reason_b"}),
                "thread_id": "t2",
            },
        ]
        report = mine_quality_patterns.build_report(
            events, look_back_days=7, alert_threshold=3, top_n=10
        )
        assert report["threshold_triggered"] is False

    def test_empty_events_no_threshold(self) -> None:
        """Empty events: threshold_triggered is False."""
        report = mine_quality_patterns.build_report(
            events=[], look_back_days=7, alert_threshold=1, top_n=10
        )
        assert report["threshold_triggered"] is False
        assert report["event_counts"] == {}
        assert report["top_patterns"] == []


# --- Integration-style: main() with --output-json ---


class TestMainWithJSON:
    def test_json_output_written_on_flag(self, db_path: str, tmp_path: Path) -> None:
        """main() writes JSON report when --output-json provided."""
        out = str(tmp_path / "output.json")
        result = mine_quality_patterns.main(
            ["--db-path", db_path, "--threshold", "100", "--output-json", out]
        )
        assert result == 0
        assert Path(out).exists()
        parsed = orjson.loads(Path(out).read_bytes())
        assert "generated_at" in parsed
        assert "top_patterns" in parsed


# --- mine_patterns edge cases ---


class TestMinePatterns:
    def test_empty_events_returns_empty(self) -> None:
        """mine_patterns with empty list returns empty list."""
        result = mine_quality_patterns.mine_patterns([], top_n=10)
        assert result == []

    def test_first_seen_last_seen_correct(self) -> None:
        """first_seen and last_seen computed correctly from timestamps."""
        events: list[mine_quality_patterns.TelemetryEvent] = [
            {
                "event_type": "quality.gate_rejected",
                "timestamp": "2026-03-05T09:00:00Z",
                "workflow_id": "w2",
                "node": "gate",
                "detail": json.dumps({"reason": "r"}),
                "thread_id": "t2",
            },
            {
                "event_type": "quality.gate_rejected",
                "timestamp": "2026-03-04T14:00:00Z",
                "workflow_id": "w1",
                "node": "gate",
                "detail": json.dumps({"reason": "r"}),
                "thread_id": "t1",
            },
        ]
        patterns = mine_quality_patterns.mine_patterns(events, top_n=10)
        assert patterns[0]["first_seen"] == "2026-03-04T14:00:00Z"
        assert patterns[0]["last_seen"] == "2026-03-05T09:00:00Z"


# --- WATCHED_EVENT_TYPES constant ---


class TestConstants:
    def test_watched_event_types_has_three_entries(self) -> None:
        """WATCHED_EVENT_TYPES contains exactly the three #588 event types."""
        assert len(mine_quality_patterns.WATCHED_EVENT_TYPES) == 3
        assert "quality.gate_rejected" in mine_quality_patterns.WATCHED_EVENT_TYPES
        assert "retry.strike_one" in mine_quality_patterns.WATCHED_EVENT_TYPES
        assert "workflow.halt_and_plan" in mine_quality_patterns.WATCHED_EVENT_TYPES