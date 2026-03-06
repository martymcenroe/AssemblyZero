```python
"""Weekly telemetry audit script — mines recurring quality failure patterns.

Issue #612: Implement missing audit script required by #588 acceptance criteria.
Related: #588 (Two-Strikes & Context Pruning), #596 (closed #588 without this script).

Usage:
    poetry run python tools/mine_quality_patterns.py
    poetry run python tools/mine_quality_patterns.py --days 14 --threshold 5
    poetry run python tools/mine_quality_patterns.py --output-json data/audit/report.json

Cron example (weekly, Mondays at 8am):
    0 8 * * 1 cd /path/to/repo && poetry run python tools/mine_quality_patterns.py --days 7

Exit codes:
    0 - Clean run (no threshold breach)
    1 - Database not found or corrupt
    2 - Alert: one or more patterns exceed threshold — human review needed

Performance note:
    At >100k rows, an index on (event_type, timestamp) is recommended:
    CREATE INDEX IF NOT EXISTS idx_telemetry_type_ts ON telemetry_events(event_type, timestamp);
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TypedDict

import orjson

# --- Constants ---

WATCHED_EVENT_TYPES: list[str] = [
    "quality.gate_rejected",
    "retry.strike_one",
    "workflow.halt_and_plan",
]

EXPECTED_COLUMNS: set[str] = {
    "event_type",
    "timestamp",
    "workflow_id",
    "node",
    "detail",
    "thread_id",
}

MAX_EXAMPLE_WORKFLOW_IDS: int = 3


# --- Data Structures ---


class TelemetryEvent(TypedDict):
    event_type: str
    timestamp: str
    workflow_id: str
    node: str
    detail: str
    thread_id: str


class PatternSummary(TypedDict):
    event_type: str
    pattern_key: str
    node: str
    reason: str
    count: int
    first_seen: str
    last_seen: str
    example_workflow_ids: list[str]


class AuditReport(TypedDict):
    generated_at: str
    look_back_days: int
    event_counts: dict[str, int]
    top_patterns: list[PatternSummary]
    threshold_triggered: bool


# --- Functions ---


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments: --db-path, --days, --threshold, --output-json, --top-n."""
    parser = argparse.ArgumentParser(
        description="Mine recurring quality failure patterns from telemetry data.",
        epilog="Exit codes: 0=clean, 1=DB not found, 2=threshold breached",
    )
    parser.add_argument(
        "--db-path",
        default="data/telemetry.db",
        help="Path to the SQLite telemetry database (default: data/telemetry.db)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Look-back window in days (default: 7)",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=3,
        help="Alert if any pattern seen >= N times (default: 3)",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="Number of top patterns to surface (default: 10)",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="Optional path to write JSON report file",
    )
    return parser.parse_args(argv)


def load_telemetry_events(
    db_path: str,
    event_types: list[str],
    since_iso: str,
) -> list[TelemetryEvent]:
    """Query the SQLite telemetry store for matching event types after since_iso.

    Opens connection read-only via PRAGMA query_only = ON.
    Validates expected columns after first fetch; raises KeyError with descriptive
    message listing expected vs. actual columns on schema mismatch.
    Raises FileNotFoundError if db_path does not exist.
    """
    if not Path(db_path).exists():
        raise FileNotFoundError(f"No telemetry database found at {db_path}")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA query_only = ON")
    conn.row_factory = sqlite3.Row

    try:
        placeholders = ",".join("?" for _ in event_types)
        query = (
            f"SELECT event_type, timestamp, workflow_id, node, detail, thread_id "
            f"FROM telemetry_events "
            f"WHERE event_type IN ({placeholders}) "
            f"AND timestamp >= ? "
            f"ORDER BY timestamp ASC"
        )
        params = [*event_types, since_iso]
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()

        if rows:
            actual_columns = set(rows[0].keys())
            if not EXPECTED_COLUMNS.issubset(actual_columns):
                missing = EXPECTED_COLUMNS - actual_columns
                raise KeyError(
                    f"Schema mismatch: expected columns {sorted(EXPECTED_COLUMNS)}, "
                    f"got {sorted(actual_columns)}. Missing: {sorted(missing)}"
                )

        events: list[TelemetryEvent] = []
        for row in rows:
            events.append(
                TelemetryEvent(
                    event_type=row["event_type"],
                    timestamp=row["timestamp"],
                    workflow_id=row["workflow_id"],
                    node=row["node"],
                    detail=row["detail"],
                    thread_id=row["thread_id"],
                )
            )
        return events
    finally:
        conn.close()


def extract_pattern_key(event: TelemetryEvent) -> str:
    """Derive a stable grouping key from event node + top-level detail fields.

    Parses detail JSON; uses 'reason' field if present.
    Falls back to detail[:64] if JSON is malformed or 'reason' key missing.
    Returns a string like 'event_type|node|reason'.
    """
    detail_str = event.get("detail", "") or ""
    reason: str
    try:
        parsed = json.loads(detail_str)
        if isinstance(parsed, dict) and "reason" in parsed:
            reason = str(parsed["reason"])
        else:
            reason = detail_str[:64]
    except (json.JSONDecodeError, TypeError):
        reason = detail_str[:64]

    return f"{event['event_type']}|{event['node']}|{reason}"


def mine_patterns(
    events: list[TelemetryEvent],
    top_n: int = 10,
) -> list[PatternSummary]:
    """Aggregate events by (event_type, pattern_key).

    Returns top_n patterns sorted by count descending.
    """
    if not events:
        return []

    # Group events by pattern key
    groups: dict[str, list[TelemetryEvent]] = defaultdict(list)
    for event in events:
        key = extract_pattern_key(event)
        groups[key].append(event)

    # Build PatternSummary for each group
    summaries: list[PatternSummary] = []
    for pattern_key, group_events in groups.items():
        # Parse pattern_key back to components
        parts = pattern_key.split("|", 2)
        event_type = parts[0] if len(parts) > 0 else ""
        node = parts[1] if len(parts) > 1 else ""
        reason = parts[2] if len(parts) > 2 else ""

        timestamps = [e["timestamp"] for e in group_events]
        workflow_ids = [e["workflow_id"] for e in group_events]

        summaries.append(
            PatternSummary(
                event_type=event_type,
                pattern_key=pattern_key,
                node=node,
                reason=reason,
                count=len(group_events),
                first_seen=min(timestamps),
                last_seen=max(timestamps),
                example_workflow_ids=workflow_ids[:MAX_EXAMPLE_WORKFLOW_IDS],
            )
        )

    # Sort by count descending, then by event_type for stable ordering
    summaries.sort(key=lambda s: (-s["count"], s["event_type"]))
    return summaries[:top_n]


def build_report(
    events: list[TelemetryEvent],
    look_back_days: int,
    alert_threshold: int,
    top_n: int,
) -> AuditReport:
    """Orchestrate pattern mining and wrap results into AuditReport.

    Sets threshold_triggered=True if any pattern count >= alert_threshold.
    """
    patterns = mine_patterns(events, top_n=top_n)

    # Count events per type
    event_counts: dict[str, int] = {}
    for event in events:
        et = event["event_type"]
        event_counts[et] = event_counts.get(et, 0) + 1

    threshold_triggered = any(p["count"] >= alert_threshold for p in patterns)

    return AuditReport(
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        look_back_days=look_back_days,
        event_counts=event_counts,
        top_patterns=patterns,
        threshold_triggered=threshold_triggered,
    )


def format_console_report(report: AuditReport) -> str:
    """Render AuditReport as a human-readable plain-text summary for stdout."""
    lines: list[str] = []
    lines.append("=== Quality Pattern Audit Report ===")
    lines.append(f"Generated: {report['generated_at']}")
    lines.append(f"Look-back: {report['look_back_days']} days")
    lines.append("")

    lines.append("--- Event Counts ---")
    if report["event_counts"]:
        for event_type, count in sorted(report["event_counts"].items()):
            lines.append(f"  {event_type}: {count}")
    else:
        lines.append("  (none)")
    lines.append("")

    lines.append("--- Top Patterns ---")
    if report["top_patterns"]:
        for i, pattern in enumerate(report["top_patterns"], 1):
            lines.append(
                f"  #{i}  [{pattern['event_type']}] "
                f"node={pattern['node']}  count={pattern['count']}"
            )
            lines.append(f"      Reason: {pattern['reason']}")
            lines.append(
                f"      First seen: {pattern['first_seen']}  "
                f"Last seen: {pattern['last_seen']}"
            )
            examples = ", ".join(pattern["example_workflow_ids"])
            lines.append(f"      Examples: {examples}")
    else:
        lines.append("  (none)")
    lines.append("")

    return "\n".join(lines)


def write_json_report(report: AuditReport, output_path: str) -> None:
    """Serialize AuditReport to JSON at output_path using orjson.

    Creates parent directories if needed.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(orjson.dumps(report, option=orjson.OPT_INDENT_2))


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns 0 on success, 1 on missing DB, 2 on threshold breach.

    Exit code 2 signals CI/cron that a human should review the patterns.
    Accepts argv parameter for testability; defaults to sys.argv if None.
    """
    args = parse_args(argv)

    since_dt = datetime.now(timezone.utc) - timedelta(days=args.days)
    since_iso = since_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        events = load_telemetry_events(args.db_path, WATCHED_EVENT_TYPES, since_iso)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except sqlite3.DatabaseError as exc:
        print(f"Database error: {exc}", file=sys.stderr)
        return 1

    if not events:
        print(f"No telemetry events in the last {args.days} days.")
        return 0

    report = build_report(events, args.days, args.threshold, args.top_n)

    console_output = format_console_report(report)
    print(console_output)

    if args.output_json:
        write_json_report(report, args.output_json)
        print(f"JSON report written to {args.output_json}")

    if report["threshold_triggered"]:
        print(
            f"[WARN] ALERT: One or more patterns exceed threshold "
            f"({args.threshold} occurrences)"
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
```
