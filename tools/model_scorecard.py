#!/usr/bin/env python3
"""Model Scorecard — aggregate workflow audit data by model.

Reads existing JSONL logs and produces per-model comparison metrics
to support model qualification decisions.

Usage:
    poetry run python tools/model_scorecard.py [--since DATE] [--node NODE] [--json]
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Known pricing per 1M tokens (USD). Update as pricing changes.
# Source: public pricing pages as of 2026-03.
MODEL_PRICING: dict[str, dict[str, float]] = {
    # Gemini models (Google AI Studio / Vertex)
    "gemini-3-pro-preview": {"input": 1.25, "output": 10.00},
    "gemini-2.5-pro-preview": {"input": 1.25, "output": 10.00},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    # Claude models (Anthropic API)
    "claude:opus": {"input": 15.00, "output": 75.00},
    "claude:sonnet": {"input": 3.00, "output": 15.00},
    "claude:haiku": {"input": 0.25, "output": 1.25},
}

# Fallback pricing when model not in table
DEFAULT_PRICING = {"input": 5.00, "output": 25.00}

LOGS_DIR = Path(__file__).parent.parent / "logs" / "active"
AUDIT_PATH = Path(__file__).parent.parent / "docs" / "lineage" / "workflow-audit.jsonl"


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost from token counts and model pricing."""
    pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)
    return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000


def extract_tokens_from_raw(raw_response: str) -> dict[str, int]:
    """Extract token counts from raw_response string.

    Handles two formats:
    - Gemini: usage_metadata with prompt_token_count / candidates_token_count
    - Claude: input_tokens / output_tokens
    """
    tokens = {"input": 0, "output": 0, "total": 0}

    # Gemini format
    m = re.search(r'"prompt_token_count":\s*(\d+)', raw_response)
    if m:
        tokens["input"] = int(m.group(1))
    m = re.search(r'"candidates_token_count":\s*(\d+)', raw_response)
    if m:
        tokens["output"] = int(m.group(1))
    m = re.search(r'"total_token_count":\s*(\d+)', raw_response)
    if m:
        tokens["total"] = int(m.group(1))

    # Claude format (fallback if Gemini fields not found)
    if tokens["input"] == 0:
        m = re.search(r'"input_tokens":\s*(\d+)', raw_response)
        if m:
            tokens["input"] = int(m.group(1))
    if tokens["output"] == 0:
        m = re.search(r'"output_tokens":\s*(\d+)', raw_response)
        if m:
            tokens["output"] = int(m.group(1))

    if tokens["total"] == 0:
        tokens["total"] = tokens["input"] + tokens["output"]

    return tokens


def parse_timestamp(ts: str) -> datetime:
    """Parse ISO timestamp to datetime."""
    # Handle both +00:00 and Z suffixes
    ts = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(ts)


def parse_review_logs(
    logs_dir: Path, since: datetime | None = None, node_filter: str | None = None
) -> list[dict[str, Any]]:
    """Parse all JSONL review logs into structured entries."""
    entries: list[dict[str, Any]] = []

    for fpath in sorted(logs_dir.glob("*.jsonl")):
        for line in fpath.open(encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            ts = parse_timestamp(record.get("timestamp", "2000-01-01T00:00:00+00:00"))
            if since and ts < since:
                continue

            node = record.get("node", "")
            if node_filter and node != node_filter:
                continue

            model = record.get("model", "unknown")
            verdict = record.get("verdict", "")
            duration_ms = record.get("duration_ms", 0)
            issue_id = record.get("issue_id", 0)
            raw = record.get("raw_response", "")

            tokens = extract_tokens_from_raw(raw)
            cost = estimate_cost(model, tokens["input"], tokens["output"])

            entries.append({
                "model": model,
                "node": node,
                "verdict": verdict,
                "cost_usd": cost,
                "input_tokens": tokens["input"],
                "output_tokens": tokens["output"],
                "total_tokens": tokens["total"],
                "duration_ms": duration_ms,
                "issue_id": issue_id,
                "timestamp": ts,
            })

    return entries


def parse_workflow_audit(
    audit_path: Path, since: datetime | None = None
) -> list[dict[str, Any]]:
    """Parse workflow audit JSONL for iteration/completion data."""
    events: list[dict[str, Any]] = []
    if not audit_path.exists():
        return events

    for line in audit_path.open(encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue

        ts = parse_timestamp(record.get("timestamp", "2000-01-01T00:00:00+00:00"))
        if since and ts < since:
            continue

        events.append({
            "timestamp": ts,
            "workflow_type": record.get("workflow_type", ""),
            "issue_number": record.get("issue_number", 0),
            "event": record.get("event", ""),
            "details": record.get("details", {}),
        })

    return events


def aggregate_by_model(entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Aggregate review log entries by model."""
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in entries:
        buckets[e["model"]].append(e)

    stats: dict[str, dict[str, Any]] = {}
    for model, records in sorted(buckets.items()):
        total_cost = sum(r["cost_usd"] for r in records)
        total_input = sum(r["input_tokens"] for r in records)
        total_output = sum(r["output_tokens"] for r in records)
        total_tokens = sum(r["total_tokens"] for r in records)
        total_duration = sum(r["duration_ms"] for r in records)

        approved = [r for r in records if r["verdict"] == "APPROVED"]
        approved_count = len(approved)
        run_count = len(records)

        approval_rate = (approved_count / run_count * 100) if run_count else 0
        cost_per_approval = (total_cost / approved_count) if approved_count else float("inf")
        avg_cost = total_cost / run_count if run_count else 0
        avg_duration = total_duration / run_count if run_count else 0
        token_efficiency = (total_output / total_input) if total_input else 0

        stats[model] = {
            "runs": run_count,
            "approved": approved_count,
            "approval_rate": approval_rate,
            "total_cost": total_cost,
            "avg_cost": avg_cost,
            "cost_per_approval": cost_per_approval,
            "avg_duration_ms": avg_duration,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "avg_tokens": total_tokens / run_count if run_count else 0,
            "token_efficiency": token_efficiency,
        }

    return stats


def aggregate_workflow_stats(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate workflow audit events into summary stats."""
    completions = [e for e in events if e["event"] == "complete"]
    errors = [e for e in events if e["event"] == "error"]
    max_iters = [e for e in events if e["event"] == "max_iterations"]

    iter_counts = [
        e["details"].get("iteration_count", 0) for e in completions
        if e["details"].get("iteration_count", 0) > 0
    ]

    return {
        "total_workflows": len(completions) + len(errors) + len(max_iters),
        "completions": len(completions),
        "errors": len(errors),
        "max_iterations_hit": len(max_iters),
        "avg_iterations": sum(iter_counts) / len(iter_counts) if iter_counts else 0,
        "unique_issues": len({e["issue_number"] for e in completions}),
    }


def print_scorecard(stats: dict[str, dict[str, Any]], workflow_stats: dict[str, Any] | None = None) -> None:
    """Print formatted scorecard table to stdout."""
    if not stats:
        print("No data found for the given filters.")
        return

    # Header
    header = f"{'Model':<28} | {'Runs':>5} | {'Avg Cost':>9} | {'Approved':>8} | {'Appr Rate':>9} | {'$/Appr':>9} | {'Avg Tokens':>11} | {'Tok Eff':>7}"
    sep = "-" * len(header)
    print(sep)
    print(header)
    print(sep)

    for model, s in sorted(stats.items()):
        cpa = f"${s['cost_per_approval']:.2f}" if s['cost_per_approval'] != float("inf") else "N/A"
        print(
            f"{model:<28} | {s['runs']:>5} | ${s['avg_cost']:>7.4f} | {s['approved']:>8} | "
            f"{s['approval_rate']:>8.1f}% | {cpa:>9} | {s['avg_tokens']:>10,.0f} | "
            f"{s['token_efficiency']:>6.2f}x"
        )

    print(sep)

    # Workflow summary if available
    if workflow_stats and workflow_stats["total_workflows"] > 0:
        ws = workflow_stats
        print(f"\nWorkflow Summary: {ws['completions']} complete, "
              f"{ws['errors']} errors, {ws['max_iterations_hit']} max-iter | "
              f"Avg iterations: {ws['avg_iterations']:.1f} | "
              f"Unique issues: {ws['unique_issues']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Model Scorecard — per-model workflow metrics")
    parser.add_argument("--since", type=str, default=None, help="Filter entries since YYYY-MM-DD")
    parser.add_argument("--node", type=str, default=None, help="Filter to specific node (e.g. review_lld)")
    parser.add_argument("--json", action="store_true", help="Output as JSON instead of table")
    parser.add_argument("--logs-dir", type=str, default=None, help="Override logs directory")
    parser.add_argument("--audit-path", type=str, default=None, help="Override audit file path")
    args = parser.parse_args()

    since = None
    if args.since:
        since = datetime.fromisoformat(args.since + "T00:00:00+00:00")

    logs_dir = Path(args.logs_dir) if args.logs_dir else LOGS_DIR
    audit_path = Path(args.audit_path) if args.audit_path else AUDIT_PATH

    entries = parse_review_logs(logs_dir, since=since, node_filter=args.node)
    stats = aggregate_by_model(entries)

    workflow_events = parse_workflow_audit(audit_path, since=since)
    workflow_stats = aggregate_workflow_stats(workflow_events)

    if args.json:
        output = {
            "model_stats": {k: {**v, "cost_per_approval": v["cost_per_approval"] if v["cost_per_approval"] != float("inf") else None} for k, v in stats.items()},
            "workflow_stats": workflow_stats,
            "filters": {"since": args.since, "node": args.node},
            "entry_count": len(entries),
        }
        json.dump(output, sys.stdout, indent=2, default=str)
        print()
    else:
        print(f"Model Scorecard — {len(entries)} entries from {logs_dir}")
        if args.since:
            print(f"  Filtered: since {args.since}")
        if args.node:
            print(f"  Filtered: node={args.node}")
        print()
        print_scorecard(stats, workflow_stats)


if __name__ == "__main__":
    main()
