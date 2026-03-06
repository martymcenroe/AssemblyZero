# Implementation Spec: Fix: Implement Missing `tools/mine_quality_patterns.py` Audit Script

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #612 |
| LLD | `docs/lld/active/612-mine-quality-patterns.md` |
| Generated | 2026-03-06 |
| Status | DRAFT |

## 1. Overview

Implement `tools/mine_quality_patterns.py`, a standalone weekly telemetry audit script that queries the SQLite telemetry database for recurring failure patterns across three event types (`quality.gate_rejected`, `retry.strike_one`, `workflow.halt_and_plan`). The script surfaces top-N patterns by frequency, prints a human-readable report, optionally writes JSON, and exits with structured exit codes for CI/cron integration.

**Objective:** Deliver the missing audit script required by Issue #588's acceptance criteria but omitted from PR #596.

**Success Criteria:** Script executable via `poetry run python tools/mine_quality_patterns.py`, queries all three event types, groups into patterns, supports all five CLI flags, exits 0/1/2 appropriately, and has ≥95% test coverage.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `tests/tools/__init__.py` | Add | Empty init file to make `tests/tools/` a Python package |
| 2 | `tools/mine_quality_patterns.py` | Add | Main audit script with all functions |
| 3 | `tests/tools/test_mine_quality_patterns.py` | Add | Full unit test suite with in-memory SQLite |

**Implementation Order Rationale:** The `__init__.py` must exist first so pytest can discover the test package. The main script is implemented second so tests (third) can import and validate it. Tests are written to match the TDD plan from the LLD — in practice, both script and tests are delivered together.

## 3. Current State (for Modify/Delete files)

*No files are being modified or deleted. All three files are new additions. This section is not applicable.*

## 4. Data Structures

### 4.1 TelemetryEvent

**Definition:**

```python
class TelemetryEvent(TypedDict):
    event_type: str
    timestamp: str
    workflow_id: str
    node: str
    detail: str
    thread_id: str
```

**Concrete Example:**

```json
{
    "event_type": "quality.gate_rejected",
    "timestamp": "2026-03-04T14:22:31Z",
    "workflow_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "node": "code_review_gate",
    "detail": "{\"reason\": \"Type hints missing on 3 functions\", \"agent\": \"reviewer-01\", \"file\": \"assemblyzero/workflows/impl/nodes/validate.py\"}",
    "thread_id": "thread-9f8e7d6c-5b4a-3210-fedc-ba0987654321"
}
```

### 4.2 PatternSummary

**Definition:**

```python
class PatternSummary(TypedDict):
    event_type: str
    pattern_key: str
    node: str
    reason: str
    count: int
    first_seen: str
    last_seen: str
    example_workflow_ids: list[str]
```

**Concrete Example:**

```json
{
    "event_type": "quality.gate_rejected",
    "pattern_key": "quality.gate_rejected|code_review_gate|Type hints missing on 3 functions",
    "node": "code_review_gate",
    "reason": "Type hints missing on 3 functions",
    "count": 7,
    "first_seen": "2026-02-28T09:15:00Z",
    "last_seen": "2026-03-05T16:42:00Z",
    "example_workflow_ids": [
        "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "b2c3d4e5-f6a7-8901-bcde-f12345678901",
        "c3d4e5f6-a7b8-9012-cdef-123456789012"
    ]
}
```

### 4.3 AuditReport

**Definition:**

```python
class AuditReport(TypedDict):
    generated_at: str
    look_back_days: int
    event_counts: dict[str, int]
    top_patterns: list[PatternSummary]
    threshold_triggered: bool
```

**Concrete Example:**

```json
{
    "generated_at": "2026-03-06T10:00:00Z",
    "look_back_days": 7,
    "event_counts": {
        "quality.gate_rejected": 12,
        "retry.strike_one": 5,
        "workflow.halt_and_plan": 2
    },
    "top_patterns": [
        {
            "event_type": "quality.gate_rejected",
            "pattern_key": "quality.gate_rejected|code_review_gate|Type hints missing on 3 functions",
            "node": "code_review_gate",
            "reason": "Type hints missing on 3 functions",
            "count": 7,
            "first_seen": "2026-02-28T09:15:00Z",
            "last_seen": "2026-03-05T16:42:00Z",
            "example_workflow_ids": [
                "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "b2c3d4e5-f6a7-8901-bcde-f12345678901",
                "c3d4e5f6-a7b8-9012-cdef-123456789012"
            ]
        }
    ],
    "threshold_triggered": true
}
```

## 5. Function Specifications

### 5.1 `parse_args()`

**File:** `tools/mine_quality_patterns.py`

**Signature:**

```python
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the quality pattern mining script."""
    ...
```

**Input Example:**

```python
argv = ["--days", "14", "--threshold", "5", "--top-n", "20", "--db-path", "/tmp/test.db", "--output-json", "report.json"]
```

**Output Example:**

```python
Namespace(days=14, threshold=5, top_n=20, db_path="/tmp/test.db", output_json="report.json")
```

**Input Example (defaults):**

```python
argv = []
```

**Output Example (defaults):**

```python
Namespace(days=7, threshold=3, top_n=10, db_path="data/telemetry.db", output_json=None)
```

**Edge Cases:**
- `argv=None` -> uses `sys.argv[1:]` (standard argparse behavior)
- Invalid `--days foo` -> argparse raises `SystemExit(2)` with error message (argparse built-in)

### 5.2 `load_telemetry_events()`

**File:** `tools/mine_quality_patterns.py`

**Signature:**

```python
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
    ...
```

**Input Example:**

```python
db_path = "data/telemetry.db"
event_types = ["quality.gate_rejected", "retry.strike_one", "workflow.halt_and_plan"]
since_iso = "2026-02-27T10:00:00Z"
```

**Output Example:**

```python
[
    {
        "event_type": "quality.gate_rejected",
        "timestamp": "2026-03-04T14:22:31Z",
        "workflow_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "node": "code_review_gate",
        "detail": '{"reason": "Type hints missing on 3 functions"}',
        "thread_id": "thread-9f8e7d6c-5b4a-3210-fedc-ba0987654321",
    },
    {
        "event_type": "retry.strike_one",
        "timestamp": "2026-03-03T11:05:00Z",
        "workflow_id": "d4e5f6a7-b8c9-0123-defg-456789012345",
        "node": "implementation_node",
        "detail": '{"reason": "Lint failure on first attempt", "retry_count": 1}',
        "thread_id": "thread-abc12345-def6-7890-1234-567890abcdef",
    },
]
```

**Edge Cases:**
- `db_path` does not exist -> raises `FileNotFoundError(f"No telemetry database found at {db_path}")`
- DB exists but table `telemetry_events` missing -> raises `sqlite3.OperationalError` (caught by caller)
- Table exists but column names differ from expected -> raises `KeyError("Schema mismatch: expected columns {expected}, got {actual}")`
- No matching rows -> returns empty `[]`
- Corrupt DB -> `sqlite3.DatabaseError` propagates

### 5.3 `extract_pattern_key()`

**File:** `tools/mine_quality_patterns.py`

**Signature:**

```python
def extract_pattern_key(event: TelemetryEvent) -> str:
    """Derive a stable grouping key from event node + top-level detail fields.

    Parses detail JSON; uses 'reason' field if present.
    Falls back to detail[:64] if JSON is malformed or 'reason' key missing.
    Returns a string like 'event_type|node|reason'.
    """
    ...
```

**Input Example (valid JSON with reason):**

```python
event = {
    "event_type": "quality.gate_rejected",
    "timestamp": "2026-03-04T14:22:31Z",
    "workflow_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "node": "code_review_gate",
    "detail": '{"reason": "Type hints missing on 3 functions", "agent": "reviewer-01"}',
    "thread_id": "thread-9f8e7d6c-5b4a-3210-fedc-ba0987654321",
}
```

**Output Example:**

```python
"quality.gate_rejected|code_review_gate|Type hints missing on 3 functions"
```

**Input Example (malformed JSON):**

```python
event = {
    "event_type": "retry.strike_one",
    "timestamp": "2026-03-03T11:05:00Z",
    "workflow_id": "d4e5f6a7-b8c9-0123-defg-456789012345",
    "node": "implementation_node",
    "detail": "not-valid-json-but-useful-context-information-about-the-failure",
    "thread_id": "thread-abc12345-def6-7890-1234-567890abcdef",
}
```

**Output Example:**

```python
"retry.strike_one|implementation_node|not-valid-json-but-useful-context-information-about-the-failu"
```

(Note: `detail[:64]` truncation)

**Input Example (valid JSON but no reason key):**

```python
event = {
    "event_type": "workflow.halt_and_plan",
    "timestamp": "2026-03-01T08:00:00Z",
    "workflow_id": "e5f6a7b8-c9d0-1234-efgh-567890123456",
    "node": "planning_node",
    "detail": '{"error_code": 42, "context": "budget exceeded"}',
    "thread_id": "thread-zzz00000-aaa1-2222-3333-444455556666",
}
```

**Output Example:**

```python
"workflow.halt_and_plan|planning_node|{\"error_code\": 42, \"context\": \"budget exceeded\"}"
```

(Falls back to `detail[:64]`)

**Edge Cases:**
- Empty `detail` -> key ends with `|` (empty fallback)
- `detail` longer than 64 chars without valid JSON -> truncated at 64 chars
- Same input always produces identical output (deterministic)

### 5.4 `mine_patterns()`

**File:** `tools/mine_quality_patterns.py`

**Signature:**

```python
def mine_patterns(
    events: list[TelemetryEvent],
    top_n: int = 10,
) -> list[PatternSummary]:
    """Aggregate events by (event_type, pattern_key).

    Returns top_n patterns sorted by count descending.
    """
    ...
```

**Input Example:**

```python
events = [
    {"event_type": "quality.gate_rejected", "timestamp": "2026-03-04T14:22:31Z", "workflow_id": "aaa-111", "node": "code_review_gate", "detail": '{"reason": "Missing type hints"}', "thread_id": "t1"},
    {"event_type": "quality.gate_rejected", "timestamp": "2026-03-04T15:00:00Z", "workflow_id": "bbb-222", "node": "code_review_gate", "detail": '{"reason": "Missing type hints"}', "thread_id": "t2"},
    {"event_type": "quality.gate_rejected", "timestamp": "2026-03-05T09:00:00Z", "workflow_id": "ccc-333", "node": "code_review_gate", "detail": '{"reason": "Missing type hints"}', "thread_id": "t3"},
    {"event_type": "retry.strike_one", "timestamp": "2026-03-03T11:05:00Z", "workflow_id": "ddd-444", "node": "impl_node", "detail": '{"reason": "Lint failure"}', "thread_id": "t4"},
]
top_n = 10
```

**Output Example:**

```python
[
    {
        "event_type": "quality.gate_rejected",
        "pattern_key": "quality.gate_rejected|code_review_gate|Missing type hints",
        "node": "code_review_gate",
        "reason": "Missing type hints",
        "count": 3,
        "first_seen": "2026-03-04T14:22:31Z",
        "last_seen": "2026-03-05T09:00:00Z",
        "example_workflow_ids": ["aaa-111", "bbb-222", "ccc-333"],
    },
    {
        "event_type": "retry.strike_one",
        "pattern_key": "retry.strike_one|impl_node|Lint failure",
        "node": "impl_node",
        "reason": "Lint failure",
        "count": 1,
        "first_seen": "2026-03-03T11:05:00Z",
        "last_seen": "2026-03-03T11:05:00Z",
        "example_workflow_ids": ["ddd-444"],
    },
]
```

**Edge Cases:**
- Empty `events` -> returns `[]`
- More distinct patterns than `top_n` -> returns exactly `top_n` entries
- `example_workflow_ids` capped at 3 IDs per pattern

### 5.5 `build_report()`

**File:** `tools/mine_quality_patterns.py`

**Signature:**

```python
def build_report(
    events: list[TelemetryEvent],
    look_back_days: int,
    alert_threshold: int,
    top_n: int,
) -> AuditReport:
    """Orchestrate pattern mining and wrap results into AuditReport.

    Sets threshold_triggered=True if any pattern count >= alert_threshold.
    """
    ...
```

**Input Example:**

```python
events = [...]  # 5 events, 3 of which share the same pattern
look_back_days = 7
alert_threshold = 3
top_n = 10
```

**Output Example (threshold triggered):**

```python
{
    "generated_at": "2026-03-06T10:00:00Z",
    "look_back_days": 7,
    "event_counts": {"quality.gate_rejected": 4, "retry.strike_one": 1},
    "top_patterns": [...],  # list of PatternSummary
    "threshold_triggered": True,
}
```

**Input Example (below threshold):**

```python
events = [...]  # 2 events, each unique pattern
look_back_days = 7
alert_threshold = 3
top_n = 10
```

**Output Example (no trigger):**

```python
{
    "generated_at": "2026-03-06T10:00:00Z",
    "look_back_days": 7,
    "event_counts": {"quality.gate_rejected": 1, "retry.strike_one": 1},
    "top_patterns": [...],
    "threshold_triggered": False,
}
```

**Edge Cases:**
- Empty events -> `event_counts` is `{}`, `top_patterns` is `[]`, `threshold_triggered` is `False`
- `alert_threshold=1` and any event exists -> `threshold_triggered=True`

### 5.6 `format_console_report()`

**File:** `tools/mine_quality_patterns.py`

**Signature:**

```python
def format_console_report(report: AuditReport) -> str:
    """Render AuditReport as a human-readable plain-text summary for stdout."""
    ...
```

**Input Example:**

```python
report = {
    "generated_at": "2026-03-06T10:00:00Z",
    "look_back_days": 7,
    "event_counts": {"quality.gate_rejected": 12, "retry.strike_one": 5},
    "top_patterns": [
        {
            "event_type": "quality.gate_rejected",
            "pattern_key": "quality.gate_rejected|code_review_gate|Missing type hints",
            "node": "code_review_gate",
            "reason": "Missing type hints",
            "count": 7,
            "first_seen": "2026-02-28T09:15:00Z",
            "last_seen": "2026-03-05T16:42:00Z",
            "example_workflow_ids": ["aaa-111", "bbb-222", "ccc-333"],
        }
    ],
    "threshold_triggered": True,
}
```

**Output Example:**

```
=== Quality Pattern Audit Report ===
Generated: 2026-03-06T10:00:00Z
Look-back: 7 days

--- Event Counts ---
  quality.gate_rejected: 12
  retry.strike_one: 5

--- Top Patterns ---
  #1  [quality.gate_rejected] node=code_review_gate  count=7
      Reason: Missing type hints
      First seen: 2026-02-28T09:15:00Z  Last seen: 2026-03-05T16:42:00Z
      Examples: aaa-111, bbb-222, ccc-333
```

**Edge Cases:**
- No patterns -> `"--- Top Patterns ---\n  (none)\n"`
- Empty `event_counts` -> `"--- Event Counts ---\n  (none)\n"`

### 5.7 `write_json_report()`

**File:** `tools/mine_quality_patterns.py`

**Signature:**

```python
def write_json_report(report: AuditReport, output_path: str) -> None:
    """Serialize AuditReport to JSON at output_path using orjson.

    Creates parent directories if needed.
    Raises PermissionError if write fails.
    """
    ...
```

**Input Example:**

```python
report = {"generated_at": "2026-03-06T10:00:00Z", "look_back_days": 7, ...}
output_path = "data/audit/quality-patterns-2026-03-06.json"
```

**Output:** File written at `data/audit/quality-patterns-2026-03-06.json` containing pretty-printed JSON.

**Edge Cases:**
- Parent directory doesn't exist -> created via `pathlib.Path(output_path).parent.mkdir(parents=True, exist_ok=True)`
- Permission denied -> `PermissionError` propagates

### 5.8 `main()`

**File:** `tools/mine_quality_patterns.py`

**Signature:**

```python
def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns 0 on success, 1 on missing DB, 2 on threshold breach.

    Exit code 2 signals CI/cron that a human should review the patterns.
    Accepts argv parameter for testability; defaults to sys.argv if None.
    """
    ...
```

**Input Example (clean run):**

```python
argv = ["--db-path", "data/telemetry.db", "--days", "7", "--threshold", "3"]
# (DB exists, events found, no pattern >= 3)
```

**Output Example:** Returns `0`, prints console report to stdout.

**Input Example (missing DB):**

```python
argv = ["--db-path", "/nonexistent/path.db"]
```

**Output Example:** Returns `1`, prints `"No telemetry database found at /nonexistent/path.db"` to stderr.

**Input Example (threshold breach):**

```python
argv = ["--db-path", "data/telemetry.db", "--threshold", "3"]
# (DB exists, a pattern has count=5)
```

**Output Example:** Returns `2`, prints console report and `"[WARN] ALERT: One or more patterns exceed threshold (3 occurrences)"`.

**Edge Cases:**
- No events in window -> returns `0`, prints "No telemetry events in the last {days} days."
- `sqlite3.DatabaseError` on corrupt DB -> returns `1`, prints descriptive error

## 6. Change Instructions

### 6.1 `tests/tools/__init__.py` (Add)

**Complete file contents:**

```python
```

(Empty file — just needs to exist so pytest discovers the package.)

### 6.2 `tools/mine_quality_patterns.py` (Add)

**Complete file contents:**

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
from typing import Any, TypedDict

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

### 6.3 `tests/tools/test_mine_quality_patterns.py` (Add)

**Complete file contents:**

```python
"""Unit tests for tools/mine_quality_patterns.py.

Issue #612: Tests for the weekly telemetry audit script.
All tests use in-memory SQLite — no external services required.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest import mock

import orjson
import pytest

# Add tools/ to sys.path so we can import the script as a module
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools"))

import mine_quality_patterns  # noqa: E402


# --- Fixtures ---


def _create_telemetry_db(
    db_path: str | None = None,
    events: list[dict] | None = None,
) -> str:
    """Create a SQLite telemetry DB (file or :memory:) with the expected schema.

    Returns the db_path (for file-based) or the connection (for :memory:).
    """
    conn = sqlite3.connect(db_path or ":memory:")
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
    return db_path  # type: ignore[return-value]


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
        """T100: load_telemetry_events opens DB with PRAGMA query_only = ON."""
        # Load events to confirm reading works
        events = mine_quality_patterns.load_telemetry_events(
            db_path,
            mine_quality_patterns.WATCHED_EVENT_TYPES,
            "2026-01-01T00:00:00Z",
        )
        assert len(events) > 0

        # Verify that the function's connection setup uses query_only
        # We test this by patching sqlite3.connect to capture the connection
        original_connect = sqlite3.connect

        class _CapturedConnection:
            """Wrapper that captures the connection for post-test inspection."""
            conn: sqlite3.Connection | None = None

        captured = _CapturedConnection()

        def capturing_connect(*args, **kwargs):
            conn = original_connect(*args, **kwargs)
            captured.conn = conn
            original_conn_execute = conn.execute

            pragma_calls: list[str] = []

            def tracking_execute(sql, *a, **kw):
                pragma_calls.append(sql)
                return original_conn_execute(sql, *a, **kw)

            conn.execute = tracking_execute  # type: ignore[assignment]
            conn._pragma_calls = pragma_calls  # type: ignore[attr-defined]
            return conn

        with mock.patch("mine_quality_patterns.sqlite3.connect", capturing_connect):
            mine_quality_patterns.load_telemetry_events(
                db_path,
                mine_quality_patterns.WATCHED_EVENT_TYPES,
                "2026-01-01T00:00:00Z",
            )

        assert captured.conn is not None
        # Verify PRAGMA query_only was called
        assert any("query_only" in call for call in captured.conn._pragma_calls)  # type: ignore[attr-defined]

    def test_write_attempt_raises_error(self, db_path: str) -> None:
        """T130 (mapped to LLD T100): Write on read-only connection raises error."""
        # Simulate what happens if we try to write through a read-only connection
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
```

## 7. Pattern References

### 7.1 Existing CLI Tool Pattern

**File:** `tools/run_audit.py` (lines 1-60)

This is an existing CLI tool in the `tools/` directory that follows the project's pattern for standalone scripts. The new `mine_quality_patterns.py` should follow the same conventions:
- Module docstring at top with usage examples
- `argparse` for CLI argument parsing
- `main()` function as entry point
- `if __name__ == "__main__":` guard at bottom
- Exit codes for different outcomes

**Relevance:** Same directory, same execution model (`poetry run python tools/...`), same audience (developers running audits).

### 7.2 Existing Test Pattern

**File:** `tests/e2e/test_issue_workflow_mock.py` (lines 1-80)

Existing test file that shows the project's testing conventions:
- pytest fixtures for setup
- Class-based test organization
- Descriptive docstrings on test methods
- Use of `tmp_path` for file operations

**Relevance:** Same testing framework and conventions that `tests/tools/test_mine_quality_patterns.py` must follow.

### 7.3 Existing Test Package Init Pattern

**File:** `tests/e2e/__init__.py`

Existing empty `__init__.py` that makes a test subdirectory a Python package. The new `tests/tools/__init__.py` follows this exact pattern.

**Relevance:** Confirms the convention of having empty `__init__.py` files in test subdirectories.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from __future__ import annotations` | stdlib | `mine_quality_patterns.py`, `test_mine_quality_patterns.py` |
| `import argparse` | stdlib | `mine_quality_patterns.py` |
| `import json` | stdlib | `mine_quality_patterns.py`, `test_mine_quality_patterns.py` |
| `import sqlite3` | stdlib | `mine_quality_patterns.py`, `test_mine_quality_patterns.py` |
| `import sys` | stdlib | `mine_quality_patterns.py`, `test_mine_quality_patterns.py` |
| `from collections import defaultdict` | stdlib | `mine_quality_patterns.py` |
| `from datetime import datetime, timedelta, timezone` | stdlib | `mine_quality_patterns.py` |
| `from pathlib import Path` | stdlib | `mine_quality_patterns.py`, `test_mine_quality_patterns.py` |
| `from typing import Any, TypedDict` | stdlib | `mine_quality_patterns.py` |
| `import orjson` | `orjson >= 3.11.7` (pyproject.toml) | `mine_quality_patterns.py`, `test_mine_quality_patterns.py` |
| `import pytest` | `pytest` (dev dependency) | `test_mine_quality_patterns.py` |
| `from unittest import mock` | stdlib | `test_mine_quality_patterns.py` |
| `import tempfile` | stdlib | `test_mine_quality_patterns.py` |

**New Dependencies:** None. All imports resolve to stdlib or packages already declared in `pyproject.toml`.

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | Module import | `import mine_quality_patterns` | All 8 public functions exist as attributes |
| T020 | `load_telemetry_events()` | DB with all 3 event types, since="2026-01-01" | Set of returned event_types == 3 expected types |
| T030 | `mine_patterns()` | 3 same-pattern + 1 different events, top_n=10 | `patterns[0]["count"]==3`, `patterns[1]["count"]==1` |
| T040 | `mine_patterns()` | 5 distinct patterns, top_n=3 | `len(patterns)==3` |
| T050 | `parse_args()` | All 5 flags explicitly set | Namespace fields match supplied values |
| T060 | `parse_args()` | Empty argv | `days=7, threshold=3, top_n=10, db_path="data/telemetry.db", output_json=None` |
| T070 | `main()` | Valid DB, threshold=100 | Returns `0` |
| T080 | `main()` | Nonexistent DB path | Returns `1` |
| T090 | `main()` | Valid DB, threshold=2 (3 events share pattern) | Returns `2` |
| T100 | `format_console_report()` | Report with `event_counts={"quality.gate_rejected": 12}` | `"quality.gate_rejected"` and `"12"` in output |
| T110 | `format_console_report()` | Report with 2 patterns with distinct nodes | Both node names in output |
| T120 | `write_json_report()` | Report dict -> tmp file -> `orjson.loads` | All 5 AuditReport keys present in parsed dict |
| T130 | `load_telemetry_events()` (PRAGMA) / write attempt | Connection with query_only=ON + INSERT | `sqlite3.OperationalError` raised |
| T140 | `main()` | Empty DB (schema but no rows) | Returns `0`, stdout contains "No telemetry events" |
| T150 | `load_telemetry_events()` | `db_path="/tmp/nonexistent.db"` | Raises `FileNotFoundError` |
| T160 | `build_report()` | 5 same-pattern events, threshold=3 | `threshold_triggered is True` |
| T170 | `build_report()` | 2 distinct events, threshold=3 | `threshold_triggered is False` |

Additional tests beyond LLD minimum:

| Test | Tests Function | Input | Expected Output |
|------|---------------|-------|-----------------|
| - | `extract_pattern_key()` stability | Same event twice | Identical string keys |
| - | `extract_pattern_key()` malformed JSON | `detail="not-json"` | Key uses `detail[:64]` |
| - | `extract_pattern_key()` no reason key | Valid JSON without "reason" | Key uses `detail[:64]` |
| - | `extract_pattern_key()` long detail | 200-char non-JSON string | Reason part is 64 chars |
| - | `extract_pattern_key()` empty detail | `detail=""` | Key ends with `\|` |
| - | `mine_patterns()` empty | `[]` | `[]` |
| - | `mine_patterns()` first/last seen | 2 events same pattern, different timestamps | Correct min/max |
| - | `mine_patterns()` example_ids capped | 5 events same pattern | `len(example_workflow_ids)==3` |
| - | `build_report()` empty events | `[]` | `threshold_triggered=False`, empty counts/patterns |
| - | `format_console_report()` empty | No patterns | `"(none)"` in output |
| - | `write_json_report()` mkdir | Nested nonexistent dirs | File created, dirs created |
| - | `main()` with --output-json | Valid DB, output path | File exists, valid JSON |
| - | WATCHED_EVENT_TYPES constant | — | Exactly 3 entries, correct values |

## 11. Implementation Notes

### 11.1 Error Handling Convention

All errors are handled with explicit exit codes:
- `FileNotFoundError` -> print to stderr, return 1
- `sqlite3.DatabaseError` -> print to stderr, return 1
- Threshold breach -> print warning to stdout, return 2
- Clean run -> return 0

The `main()` function catches exceptions and converts them to exit codes. Inner functions (`load_telemetry_events`, `extract_pattern_key`) raise or handle locally.

### 11.2 Logging Convention

This script uses `print()` for all output — no logging framework. Console output goes to stdout; error messages go to stderr via `print(..., file=sys.stderr)`. This keeps the script standalone without requiring logging configuration.

### 11.3 Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| `WATCHED_EVENT_TYPES` | `["quality.gate_rejected", "retry.strike_one", "workflow.halt_and_plan"]` | The three events specified in Issue #588 |
| `EXPECTED_COLUMNS` | `{"event_type", "timestamp", "workflow_id", "node", "detail", "thread_id"}` | Schema validation against telemetry table |
| `MAX_EXAMPLE_WORKFLOW_IDS` | `3` | Cap example IDs per pattern to keep output concise |

### 11.4 Import Strategy for Tests

The test file uses `sys.path.insert(0, ...)` to add `tools/` to the Python path, enabling `import mine_quality_patterns` without the script being an installed package. This mirrors how `tools/` scripts are run: they are standalone and not part of the `assemblyzero` package.

### 11.5 SQLite Query Construction

The `load_telemetry_events` function uses parameterized queries (`?` placeholders) for all dynamic values. The `IN` clause uses `",".join("?" for _ in event_types)` to generate the correct number of placeholders. No string interpolation of user input into SQL.

### 11.6 `main()` Testability

The `main()` function accepts an optional `argv` parameter to enable testing without patching `sys.argv`. When `argv=None`, argparse falls back to `sys.argv[1:]` by default. This pattern is used in several existing `tools/` scripts.

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3) — N/A, all files are Add
- [x] Every data structure has a concrete JSON/YAML example (Section 4)
- [x] Every function has input/output examples with realistic values (Section 5)
- [x] Change instructions are diff-level specific (Section 6) — complete file contents provided for all Add files
- [x] Pattern references include file:line and are verified to exist (Section 7)
- [x] All imports are listed and verified (Section 8)
- [x] Test mapping covers all LLD test scenarios (Section 10)

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #612 |
| Verdict | DRAFT |
| Date | 2026-03-06 |
| Iterations | 0 |
| Finalized | — |