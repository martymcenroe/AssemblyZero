#!/usr/bin/env python
"""Derive STAGE_NOMINAL_SECONDS from observed run records (#2323).

The table in `assemblyzero/core/stage_watchdog.py` was hand-typed from the
boostgauge hardening campaign of 2026-07-28/29 and went stale as the campaign
ran on. Re-measured 2026-08-13, three of six entries no longer described the
stage they named -- impl's nominal was 3x BELOW its own median, so the stage
most likely to genuinely hang was the one whose warnings fired on nearly every
healthy run.

A hand-typed table goes stale silently. This script is the answer to that: the
numbers are derived, the derivation is runnable, and re-deriving is a command
rather than an afternoon.

Usage:
    poetry run python tools/derive_stage_nominals.py \\
        --runs /c/Users/mcwiz/Projects/boostgauge/data/speedrun/runs

Prints a table of percentiles and the Python literal to paste into
stage_watchdog.py. Read-only: it never edits the table itself, because a
nominal is a judgement about what "normal" means and that belongs to a human.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

#: Summary rows look like: `spec      passed     699.0s  C:\\path\\to\\artifact`
_ROW = re.compile(
    r"^(triage|lld|spec|impl|pr|cleanup)\s+(passed|failed)\s+([\d.]+)s",
)

#: The nominal is the p90 of passing runs. Not the mean (one 2711s outlier
#: drags it), not the minimum (every run then looks slow), and -- corrected in
#: #2410 -- not the median either.
#:
#: The median was chosen on the reasoning that "the point is to describe
#: typical, and the ratios above it express the tail". That holds for a
#: unimodal distribution. This one is not unimodal, which the earlier
#: derivation had no reason to check:
#:
#:     stage    n     p50     p75     p90     max
#:     lld     74    79.9   332.9   409.0   741.1
#:
#: LLD passes cluster near 60s AND near 400s, with genuine passing runs at
#: both ends -- verified against the corpus: no `skipped` verdict exists, and
#: the fast mode is 50-80s of real passes, not near-zero stubs. A single-point
#: median therefore sits inside the fast mode and describes neither. Measured
#: consequence on run-issue1-114223: `lld running 300s (nominal ~75s) - SLOW,
#: 3x nominal`, on a stage whose three prior passes on that repo took 380.1s,
#: 409.0s and similar. Every ordinary LLD run crossed the SLOW threshold.
#:
#: The label answers "is this longer than this stage plausibly takes?", not
#: "is this longer than typical?". p90 answers the first. Across the whole
#: corpus, 3x p90 sits above every recorded healthy run for every stage, so the
#: no-false-alarms doctrine holds by measurement rather than by hope --
#: `tests/unit/test_stage_watchdog.py` asserts exactly that.
NOMINAL_PERCENTILE = 0.90

#: Below this many passing samples, a stage gets no nominal at all and the
#: watchdog reports elapsed time without a verdict. A nominal the fleet cannot
#: yet compute honestly should say so rather than guess low -- guessing low is
#: what #2410 was filed about.
MIN_SAMPLES_FOR_NOMINAL = 5


def collect(runs_dir: Path) -> dict[str, list[float]]:
    """Durations of PASSED stages, per stage, across every run log."""
    samples: dict[str, list[float]] = {}
    for log in sorted(runs_dir.glob("run-*.log")):
        try:
            text = log.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            match = _ROW.match(line.strip())
            if not match:
                continue
            stage, verdict, seconds = match.groups()
            # Failed stages stopped early; their duration says nothing about
            # how long the stage takes when it works.
            if verdict != "passed":
                continue
            samples.setdefault(stage, []).append(float(seconds))
    return {k: sorted(v) for k, v in samples.items()}


def percentile(values: list[float], fraction: float) -> float:
    """Nearest-rank percentile. Deterministic, and no numpy dependency."""
    if not values:
        return 0.0
    index = max(0, min(len(values) - 1, round(fraction * (len(values) - 1))))
    return values[index]


def main(argv: list[str] | None = None) -> int:
    # `argv` is threaded so a test can drive the real entry point rather than a
    # re-expression of it (#2410, and the #2264 lesson about tests that agree
    # only with themselves).
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runs", required=True, type=Path,
        help="directory holding run-*.log summary logs",
    )
    args = parser.parse_args(argv)

    if not args.runs.is_dir():
        print(f"not a directory: {args.runs}")
        return 2

    samples = collect(args.runs)
    if not samples:
        print(f"no passed-stage rows found under {args.runs}")
        return 1

    print(f"{'stage':<9} {'n':>4} {'p50':>9} {'p75':>9} {'p90':>9} {'max':>9}")
    for stage in ("triage", "lld", "spec", "impl", "pr", "cleanup"):
        values = samples.get(stage, [])
        if not values:
            print(f"{stage:<9} {0:>4}   (no passed samples — keep current)")
            continue
        print(
            f"{stage:<9} {len(values):>4} "
            f"{percentile(values, 0.50):>9.1f} {percentile(values, 0.75):>9.1f} "
            f"{percentile(values, 0.90):>9.1f} {max(values):>9.1f}"
        )

    print("\nSTAGE_NOMINAL_SECONDS: dict[str, float] = {")
    for stage in ("triage", "lld", "spec", "impl", "pr", "cleanup"):
        values = samples.get(stage, [])
        if not values:
            print(f'    # "{stage}": no passed samples in this corpus')
            continue
        if len(values) < MIN_SAMPLES_FOR_NOMINAL:
            print(
                f'    # "{stage}": only {len(values)} passing sample(s), below '
                f"the {MIN_SAMPLES_FOR_NOMINAL} needed — omitted so the "
                f"watchdog reports elapsed without a verdict"
            )
            continue
        print(f'    "{stage}": {percentile(values, NOMINAL_PERCENTILE):.1f},')
    print("}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
