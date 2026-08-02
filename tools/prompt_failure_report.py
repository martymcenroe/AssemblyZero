#!/usr/bin/env python3
"""Count drafter validation failures by fingerprint, model and week (#2074).

Each failure used to print to a run log, the retry re-rolled, and the failure
mode evaporated -- while the prompts producing the failure rate stayed static.
This reads the records and turns them into a rate.

    poetry run python tools/prompt_failure_report.py --repo /c/.../boostgauge
    poetry run python tools/prompt_failure_report.py --repo <path> --since 2026-08-01
    poetry run python tools/prompt_failure_report.py --repo <path> --group-by model

Output is deterministic: identical input produces byte-identical output, so a
report can be diffed across days to see what changed rather than re-read.

Exit codes: 0 always, including "nothing recorded" -- an empty telemetry file
is a fact about the pipeline, not an error in this tool.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from assemblyzero.speedrun.prompt_telemetry import (  # noqa: E402
    read_failures,
    render_report,
    telemetry_path,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Count drafter validation failures by fingerprint, model and week."
    )
    parser.add_argument("--repo", required=True, help="repository whose telemetry to read")
    parser.add_argument("--since", default="", help="local date or timestamp lower bound, e.g. 2026-08-01")
    parser.add_argument(
        "--group-by", default="fingerprint",
        choices=("fingerprint", "model", "week"),
        help="primary grouping for the summary table",
    )
    args = parser.parse_args(argv)

    repo = Path(args.repo)
    rows = read_failures(repo, since=args.since)

    if not rows and not telemetry_path(repo).exists():
        print(f"No telemetry file at {telemetry_path(repo)}", flush=True)
        return 0

    print(render_report(rows, args.group_by), end="", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
