#!/usr/bin/env python3
"""Audit: every site that breaks the loud-failure standard (ADR 0236, standard 0034).

The scanner lives in ``assemblyzero.core.loud_failure_check`` so the unit test
``tests/unit/test_loud_failure_check.py`` runs the same code this prints.

Usage
-----
    poetry run python tools/audit_loud_failure.py               # every finding
    poetry run python tools/audit_loud_failure.py --check       # CI mode
    poetry run python tools/audit_loud_failure.py --write-baseline

``--check`` exits 1 when a finding is not in the baseline (a new site), or a
baseline entry no longer exists (the baseline must shrink with the fix).

``--write-baseline`` rewrites the baseline from the tree, and refuses when the
tree holds a finding the current baseline does not: the baseline only shrinks.
Every entry names #3581, the sweep that empties it.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from assemblyzero.core.loud_failure_check import as_baseline, scan

BASELINE_PATH = REPO_ROOT / "tests" / "fixtures" / "loud_failure_baseline.json"
SWEEP_ISSUE = 3581


def tracked_sources() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "--", "assemblyzero/*.py", "tools/*.py"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout
    return [line for line in out.splitlines() if line]


def load_baseline() -> dict:
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write-baseline", action="store_true")
    args = parser.parse_args()

    findings = scan(REPO_ROOT, tracked_sources())
    keys = {f.key for f in findings}

    if args.write_baseline:
        if BASELINE_PATH.exists():
            added = sorted(keys - set(load_baseline()["entries"]))
            if added:
                sys.stderr.write(
                    "REFUSED: the baseline only shrinks; these sites are new and must be fixed:\n  "
                    + "\n  ".join(added) + "\n"
                )
                return 1
        BASELINE_PATH.write_text(
            json.dumps(as_baseline(findings, SWEEP_ISSUE), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"Baseline written: {len(findings)} site(s), each naming #{SWEEP_ISSUE}.")
        return 0

    if args.check:
        baseline = set(load_baseline()["entries"])
        new = sorted(keys - baseline)
        gone = sorted(baseline - keys)
        for key in new:
            sys.stderr.write(f"NEW (fix it; ADR 0236): {key}\n")
        for key in gone:
            sys.stderr.write(f"FIXED but still in the baseline (shrink it): {key}\n")
        if new or gone:
            sys.stderr.write(f"FAIL -- {len(new)} new, {len(gone)} stale\n")
            return 1
        print(f"PASS -- {len(findings)} site(s), all in the baseline (#{SWEEP_ISSUE})")
        return 0

    by_kind: dict[str, int] = {}
    for f in findings:
        by_kind[f.kind] = by_kind.get(f.kind, 0) + 1
        print(f"{f.path}:{f.line}  {f.kind}  {f.detail}")
    print(f"\n{len(findings)} site(s): {by_kind}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
