#!/usr/bin/env python3
"""Replay the preserved disaster museum against the current machinery (#2572).

A model or prompt change ships blind against exactly the failure modes the
fleet paid to discover. Each case here cost a run to find and a session to
fix; this replays them before the next change, not after the next kill.

    poetry run python tools/golden_disasters.py --tier deterministic
    poetry run python tools/golden_disasters.py --tier live

Deterministic tier: free, no network, runs in CI. The preserved BAD artifact
through the REAL machinery.

Live tier: spends tokens, operator-invoked. Run before adopting a model
change, the way FORBIDDEN_MODELS gates ids -- this gates behaviour. It is
registered but carries no cases yet, and says so rather than reporting a
vacuous pass.

Exit codes: 0 when every case in the tier survived; 1 when any regressed or
could not run. The deterministic tier is a gate, so it exits non-zero --
unlike the read-only reporters, whose empty state is a fact rather than a
failure.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

# #2367: before anything prints. Preserved drafts quote model output verbatim.
from assemblyzero.core.utf8_console import install as _install_utf8_console  # noqa: E402

_install_utf8_console()

from assemblyzero.speedrun.golden_disasters import (  # noqa: E402
    CASES,
    DETERMINISTIC,
    LIVE,
    fixture_digest,
    render_report,
    run_tier,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Replay preserved kills against the current machinery."
    )
    parser.add_argument(
        "--tier", default=DETERMINISTIC, choices=(DETERMINISTIC, LIVE),
        help="deterministic (free, CI) or live (spends tokens)",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="list the corpus with provenance and fixture digests, run nothing",
    )
    args = parser.parse_args(argv)

    if args.list:
        for case in CASES.values():
            try:
                digest = fixture_digest(case, REPO_ROOT)
            except OSError:
                digest = "MISSING"
            print(f"{case.slug}  [{case.tier}]  fixtures {digest}")
            print(f"    {case.title}")
            print(f"    guards:     {case.guards}")
            print(f"    provenance: {case.provenance}")
        return 0

    results = run_tier(args.tier, REPO_ROOT)
    print(render_report(results, args.tier), end="", flush=True)

    if args.tier == LIVE and not results:
        # Not a pass. A tier with no cases has measured nothing, and
        # reporting 0 exit here would let "the live tier is green" be said
        # about a tier that never ran anything.
        print(
            "The live tier carries no cases yet (see #2598). Nothing was "
            "measured, so this is not a pass.",
            flush=True,
        )
        return 1

    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
