#!/usr/bin/env python3
"""Aggregate data/speedrun/run-log.jsonl into a readable table (#1076).

Reads the run log and prints two sections:

  1. Per-attempt timeline (one row per attempt, chronological).
  2. Summary by failure mode (counts and percentages).

Usage:

    poetry run python tools/speedrun_summarize.py \\
        --repo /c/Users/mcwiz/Projects/boostgauge

    # Filter to a single issue:
    poetry run python tools/speedrun_summarize.py \\
        --repo /c/Users/mcwiz/Projects/boostgauge --issue 35

The output is plain text suitable for between-attempt review or for
pasting into a session log. Designed to be useful with `tail -1` style
single-take inspection too — even a fresh, mostly-empty log produces
useful output.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

# Make assemblyzero/ importable when run from the repo root.
_TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(_TOOLS.parent))

from assemblyzero.utils.speedrun import RunLogger  # noqa: E402


def _format_seconds(s: float) -> str:
    """Format seconds as MM:SS for human readability."""
    if s is None:
        return "?"
    minutes, seconds = divmod(int(s), 60)
    return f"{minutes:02d}:{seconds:02d}"


def print_timeline(entries: list[dict]) -> None:
    """Print a per-attempt table."""
    if not entries:
        print("\nNo attempts logged yet.")
        return
    print("\n## Timeline\n")
    headers = ("attempt", "issue", "outcome", "failure", "duration", "started_at")
    rows = [
        (
            str(e.get("attempt", "?")),
            str(e.get("issue", "?")),
            e.get("outcome", "?"),
            e.get("failure_mode") or "-",
            _format_seconds(e.get("total_seconds")),
            e.get("started_at", "?"),
        )
        for e in entries
    ]
    widths = [
        max(len(h), max((len(r[i]) for r in rows), default=0))
        for i, h in enumerate(headers)
    ]
    fmt = " | ".join(f"{{:<{w}}}" for w in widths)
    print(fmt.format(*headers))
    print(" | ".join("-" * w for w in widths))
    for row in rows:
        print(fmt.format(*row))


def print_failure_summary(entries: list[dict]) -> None:
    """Print a counts-by-failure-mode table."""
    if not entries:
        return
    print("\n## Summary by outcome\n")
    outcome_counts = Counter(e.get("outcome", "unknown") for e in entries)
    total = sum(outcome_counts.values())
    for outcome, count in outcome_counts.most_common():
        pct = 100.0 * count / total
        print(f"  {outcome:<8} {count:>3}  ({pct:5.1f}%)")

    failures = [e for e in entries if e.get("outcome") != "success"]
    if not failures:
        return
    print("\n## Summary by failure mode (non-success only)\n")
    fail_counts = Counter(e.get("failure_mode") or "unknown" for e in failures)
    total_fail = sum(fail_counts.values())
    for mode, count in fail_counts.most_common():
        pct = 100.0 * count / total_fail
        print(f"  {mode:<28} {count:>3}  ({pct:5.1f}%)")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Summarize data/speedrun/run-log.jsonl",
    )
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument(
        "--issue", type=int, default=None,
        help="Filter to a single issue number",
    )
    args = parser.parse_args()

    repo_root = args.repo.resolve()
    if not repo_root.exists():
        print(f"ERROR: repo path does not exist: {repo_root}")
        return 1

    runlogger = RunLogger(repo_root)
    entries = runlogger.read_all()

    if args.issue is not None:
        entries = [e for e in entries if e.get("issue") == args.issue]

    print(f"# Speed-run summary — {repo_root.name}")
    if args.issue:
        print(f"Issue filter: #{args.issue}")
    print(f"Log: {runlogger.log_path}")
    print(f"Total attempts: {len(entries)}")

    print_timeline(entries)
    print_failure_summary(entries)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
