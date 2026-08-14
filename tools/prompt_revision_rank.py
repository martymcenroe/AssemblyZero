#!/usr/bin/env python3
"""Rank drafter failure fingerprints by what they cost (#2075).

Companion to #2074's telemetry. Counting alone ranks a cheap frequent failure
above an expensive rare one; this joins the counts to roll durations from the
timing dashboard's `runs.csv` so the ranking is by cost:

    cost = occurrences x mean wasted roll seconds

    poetry run python tools/prompt_revision_rank.py --repo /c/.../boostgauge

A fingerprint with no duration data is ranked by occurrence count and flagged
`duration-unknown`. It is never costed at zero -- that would sort the most
expensive unmeasured failure to the bottom.

Exit 0 always, including on an empty telemetry file: no failures recorded is a
fact about the pipeline, not an error in this tool.

The procedure this feeds is `docs/standards/0025-prompt-revision-from-telemetry.md`.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# #2367: before anything prints. Ranked rows quote revision prose.
from assemblyzero.core.utf8_console import install as _install_utf8_console  # noqa: E402

_install_utf8_console()

from assemblyzero.speedrun.prompt_ranking import (  # noqa: E402
    RUNS_CSV_REL,
    TELEMETRY_REL,
    load_durations,
    load_telemetry,
    rank,
    render,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Rank drafter failure fingerprints by occurrences x mean wasted roll seconds."
    )
    parser.add_argument("--repo", required=True, help="repository whose telemetry to rank")
    parser.add_argument("--top", type=int, default=0, help="show only the N most expensive")
    args = parser.parse_args(argv)

    repo = Path(args.repo)
    rows = load_telemetry(repo)
    durations = load_durations(repo)

    if not rows:
        print(
            f"No validation failures recorded at {repo / TELEMETRY_REL}.\n"
            f"Telemetry populates from rolls run after it landed; an empty file "
            f"means no roll has hit a validation failure since.",
            flush=True,
        )
        return 0

    if not durations:
        print(
            f"note: no durations at {repo / RUNS_CSV_REL} — every fingerprint will "
            f"be flagged duration-unknown and ranked by count.",
            flush=True,
        )

    ranked = rank(rows, durations)
    if args.top > 0:
        ranked = ranked[: args.top]
    print(render(ranked), end="", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
