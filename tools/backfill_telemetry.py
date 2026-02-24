#!/usr/bin/env python3
"""One-time backfill of historical logs into telemetry DynamoDB table.

Parses:
- ~/.unleashed-usage.log → session.start events
- unleashed/logs/friction-*.jsonl → approval.permission events
- AssemblyZero/logs/active/*.jsonl → workflow.* events

Usage:
    poetry run python tools/backfill_telemetry.py
    poetry run python tools/backfill_telemetry.py --dry-run  # preview only
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from assemblyzero.telemetry.emitter import _build_event, _get_dynamo_client


def parse_usage_log(path: Path) -> list[dict]:
    """Parse ~/.unleashed-usage.log → session.start events."""
    events = []
    if not path.exists():
        print(f"  Skipped: {path} not found")
        return events

    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 4:
                continue

            ts_str, _mode, cwd, version = parts[0], parts[1], parts[2], parts[3]
            repo = os.path.basename(cwd) if cwd else "unknown"

            event = _build_event("session.start", repo=repo, metadata={
                "version": version,
                "source": "backfill:usage-log",
            })
            # Override timestamp with historical one
            try:
                dt = datetime.fromisoformat(ts_str)
                event["timestamp"] = dt.astimezone(timezone.utc).isoformat()
                event["sk"] = f"EVENT#{event['timestamp']}#{uuid.uuid4().hex[:12]}"
                event["gsi1sk"] = event["timestamp"]
                event["gsi2sk"] = event["timestamp"]
                date_str = dt.strftime("%Y-%m-%d")
                event["gsi3pk"] = f"DATE#{date_str}"
                event["gsi3sk"] = f"REPO#{repo}#EVENT#{event['timestamp']}"
                event["ttl"] = int(dt.timestamp()) + (90 * 86400)
            except Exception:
                continue

            events.append(event)

    print(f"  Parsed {len(events)} session.start events from usage log")
    return events


def parse_friction_logs(logs_dir: Path) -> list[dict]:
    """Parse unleashed/logs/friction-*.jsonl → approval.permission events."""
    events = []
    if not logs_dir.exists():
        print(f"  Skipped: {logs_dir} not found")
        return events

    for jsonl_file in sorted(logs_dir.glob("friction-*.jsonl")):
        with open(jsonl_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                event = _build_event("approval.permission", metadata={
                    "event_type": record.get("type", "permission_prompt"),
                    "pattern_matched": record.get("pattern_matched", ""),
                    "prompt_number": record.get("prompt_number", 0),
                    "elapsed_s": record.get("elapsed_s", 0),
                    "source": "backfill:friction-log",
                })

                ts_str = record.get("ts", "")
                if ts_str:
                    try:
                        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        event["timestamp"] = dt.isoformat()
                        event["sk"] = f"EVENT#{event['timestamp']}#{uuid.uuid4().hex[:12]}"
                        event["gsi1sk"] = event["timestamp"]
                        event["gsi2sk"] = event["timestamp"]
                        date_str = dt.strftime("%Y-%m-%d")
                        event["gsi3pk"] = f"DATE#{date_str}"
                        event["gsi3sk"] = f"REPO#unknown#EVENT#{event['timestamp']}"
                        event["ttl"] = int(dt.timestamp()) + (90 * 86400)
                    except Exception:
                        pass

                # Actor is always claude for unleashed sessions
                event["actor"] = "claude"
                event["gsi1pk"] = "ACTOR#claude"
                events.append(event)

    print(f"  Parsed {len(events)} approval.permission events from {len(list(logs_dir.glob('friction-*.jsonl')))} friction files")
    return events


def parse_workflow_logs(active_dir: Path) -> list[dict]:
    """Parse AssemblyZero/logs/active/*.jsonl → workflow.* events."""
    events = []
    if not active_dir.exists():
        print(f"  Skipped: {active_dir} not found")
        return events

    for jsonl_file in sorted(active_dir.glob("*.jsonl")):
        with open(jsonl_file, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                verdict = record.get("verdict", "")
                if verdict in ("APPROVED", "DRAFTED"):
                    event_type = "workflow.complete"
                elif verdict == "BLOCK":
                    event_type = "workflow.error"
                else:
                    event_type = "workflow.complete"

                event = _build_event(event_type, repo="AssemblyZero", metadata={
                    "node": record.get("node", ""),
                    "model": record.get("model", ""),
                    "issue_id": record.get("issue_id", 0),
                    "verdict": verdict,
                    "duration_ms": record.get("duration_ms", 0),
                    "source": "backfill:workflow-log",
                })

                ts_str = record.get("timestamp", "")
                if ts_str:
                    try:
                        dt = datetime.fromisoformat(ts_str)
                        event["timestamp"] = dt.isoformat()
                        event["sk"] = f"EVENT#{event['timestamp']}#{uuid.uuid4().hex[:12]}"
                        event["gsi1sk"] = event["timestamp"]
                        event["gsi2sk"] = event["timestamp"]
                        date_str = dt.strftime("%Y-%m-%d")
                        event["gsi3pk"] = f"DATE#{date_str}"
                        event["gsi3sk"] = f"REPO#AssemblyZero#EVENT#{event['timestamp']}"
                        event["ttl"] = int(dt.timestamp()) + (90 * 86400)
                    except Exception:
                        pass

                events.append(event)

    print(f"  Parsed {len(events)} workflow events from {len(list(active_dir.glob('*.jsonl')))} active files")
    return events


def main():
    parser = argparse.ArgumentParser(description="Backfill historical logs into telemetry DynamoDB")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, don't write to DynamoDB")
    args = parser.parse_args()

    print("Backfill: Parsing historical logs...")

    all_events: list[dict] = []

    # 1. Usage log → session.start
    print("\n1. Usage log (session.start):")
    all_events.extend(parse_usage_log(Path.home() / ".unleashed-usage.log"))

    # 2. Friction logs → approval.permission
    print("\n2. Friction logs (approval.permission):")
    unleashed_logs = Path.home() / "Projects" / "unleashed" / "logs"
    all_events.extend(parse_friction_logs(unleashed_logs))

    # 3. Workflow logs → workflow.*
    print("\n3. Workflow logs (workflow.*):")
    active_dir = Path.home() / "Projects" / "AssemblyZero" / "logs" / "active"
    all_events.extend(parse_workflow_logs(active_dir))

    print(f"\nTotal events to backfill: {len(all_events)}")

    if args.dry_run:
        print("\n[DRY RUN] Would write to DynamoDB. Sample events:")
        for event in all_events[:3]:
            print(f"  {event['event_type']} @ {event['timestamp'][:19]} repo={event['repo']}")
        return

    # Write to DynamoDB
    client = _get_dynamo_client()
    if client is None:
        print("ERROR: Could not initialize DynamoDB client")
        sys.exit(1)

    written = 0
    errors = 0
    for event in all_events:
        try:
            client.put_item(Item=event)
            written += 1
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"  Error writing event: {e}")

    print(f"\nBackfill complete: {written} written, {errors} errors")


if __name__ == "__main__":
    main()
