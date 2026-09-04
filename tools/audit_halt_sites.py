#!/usr/bin/env python3
"""Audit: every site that can end a run, against the gate registry (#2719).

The walker and the registry live in ``assemblyzero.core.gate_registry`` so the
CI gate in ``tests/unit/test_gate_registry.py`` runs the same code this prints.

Usage
-----
    poetry run python tools/audit_halt_sites.py              # per-gate report
    poetry run python tools/audit_halt_sites.py --tsv        # one row per site
    poetry run python tools/audit_halt_sites.py --unregistered
    poetry run python tools/audit_halt_sites.py --check      # CI mode

``--check`` exits 1 on any walked site no registry row names, or any registry
site the walker cannot find. It is what the unit test calls.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from assemblyzero.core.utf8_console import install as _install_utf8_console  # noqa: E402

_install_utf8_console()

from assemblyzero.core.gate_registry import (  # noqa: E402
    ACTION_HALT,
    GATE_REGISTRY,
    JUDGES_MODEL_OUTPUT,
    HaltSite,
    WalkCoverage,
    halt_counts,
    renumberings,
    scan_halt_sites,
    site_to_gate,
    unregistered,
)

BASELINE_PATH = REPO_ROOT / "tests" / "fixtures" / "gate_registry_baseline.json"


def model_output_halt_rows() -> int:
    """Gates that judge the drafter's output and end the run. The maze."""
    return sum(
        1 for g in GATE_REGISTRY
        if g.action == ACTION_HALT and g.judges == JUDGES_MODEL_OUTPUT
    )


def write_baseline(sites: list[HaltSite], coverage: WalkCoverage,
                   path: Path = BASELINE_PATH) -> dict:
    """Freeze today's halt-row counts so CI can refuse tomorrow's rise (#2720).

    The counts ride with what they were measured against, so a reader can
    see the denominator without re-running anything. Lower it by hand when
    a gate stops halting; raise it only in a PR that names an operator
    ruling.
    """
    payload = {
        "_comment": (
            "The ratchet (#2720). tests/unit/test_gate_registry.py fails when "
            "halt_rows_per_stage rises above this, and when "
            "model_output_halt_rows differs from it in EITHER direction "
            "(#2759). A row that stops halting, or that leaves the "
            "model-output category, lowers the number in the same PR -- so "
            "the denominator is never stale. Raise either only with an "
            "operator ruling named in the row's created_by or justified_by, "
            "in the same PR."
        ),
        "measured_against": {
            "files_scanned": coverage.files_scanned,
            "halt_sites": len(sites),
            "gates": len(GATE_REGISTRY),
        },
        "halt_rows_per_stage": halt_counts(),
        "model_output_halt_rows": model_output_halt_rows(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def render_tsv(sites: list[HaltSite]) -> str:
    known = site_to_gate()
    rows = ["site\tline\tgate\thead"]
    for site in sites:
        rows.append(
            f"{site.key}\t{site.line}\t{known.get(site.key, '-')}\t"
            f"{site.head[:100]!r}"
        )
    return "\n".join(rows)


def render_report(sites: list[HaltSite], coverage: WalkCoverage) -> str:
    moved, fresh, ghosts = renumberings(sites)
    by_gate: dict[str, int] = defaultdict(int)
    known = site_to_gate()
    for site in sites:
        if site.key in known:
            by_gate[known[site.key]] += 1

    lines = [
        "=" * 78,
        "HALT-SITE AUDIT (#2719)",
        "=" * 78,
        "",
        "Coverage -- counted, not estimated:",
        f"  Files scanned:      {coverage.files_scanned}",
        f"  Functions scanned:  {coverage.functions_scanned}",
        f"  Halt sites found:   {len(sites)}",
        f"  Files that would NOT parse: {len(coverage.files_unparseable)}",
        "",
        f"Registry: {len(GATE_REGISTRY)} gate(s); halt-action rows per stage: "
        + ", ".join(f"{s} {n}" for s, n in halt_counts().items()),
        f"  Renumbered sites (a sibling was retired above them): {len(moved)}",
        f"  Unregistered sites (no row names them): {len(fresh)}",
        f"  Phantom sites (row names, walker cannot find): {len(ghosts)}",
        "",
        f"{'gate':<44} {'stage':<12} {'judges':<18} {'action':<7} sites",
        "-" * 78,
    ]
    for gate in sorted(GATE_REGISTRY, key=lambda g: (g.stage, g.key)):
        lines.append(
            f"{gate.key:<44} {gate.stage:<12} {gate.judges:<18} "
            f"{gate.action:<7} {by_gate.get(gate.key, 0)}"
            + ("  (decided in " + gate.decided_in + ")" if gate.decided_in else "")
        )
    if moved:
        lines += ["", "RENUMBERED -- the same return, at a new index (#2738):"]
        for rename in moved:
            lines.append(f"  {rename.describe()}")
            lines.append(f"    {rename.named}")
            lines.append(f"    -> {rename.found}")
    if fresh:
        lines += ["", "UNREGISTERED -- every one must name a row:"]
        for site in fresh:
            lines.append(f"  {site.key}  line {site.line}  {site.head[:70]!r}")
    if ghosts:
        lines += ["", "PHANTOM -- the row names a site the walker cannot find:"]
        for gate_key, site in ghosts:
            lines.append(f"  {gate_key}: {site}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--tsv", action="store_true", help="one row per site")
    parser.add_argument("--unregistered", action="store_true",
                        help="only sites no registry row names")
    parser.add_argument("--check", action="store_true",
                        help="exit 1 on any unregistered or phantom site")
    parser.add_argument("--write-baseline", action="store_true",
                        help="freeze today's halt-row counts for the ratchet")
    args = parser.parse_args(argv)

    sites, coverage = scan_halt_sites(args.root)

    if args.write_baseline:
        payload = write_baseline(sites, coverage)
        print(
            f"Baseline written: halt rows {payload['halt_rows_per_stage']}, "
            f"model-output halt rows {payload['model_output_halt_rows']}"
        )
        print(f"  {BASELINE_PATH.relative_to(REPO_ROOT)}")
        return 0

    if args.check:
        # #2738: separate a renumbering from a real finding BEFORE printing.
        # A site index is positional, so retiring one halt site shifts every
        # later site of the same kind in the same function -- and the two-way
        # check then reports the neighbours while saying nothing about the gate
        # that moved. In #2723 it named four gates that had not been touched.
        moved, fresh, ghosts = renumberings(sites)
        if not fresh and not ghosts and not moved:
            print(
                f"PASS -- {coverage.files_scanned} files, {len(sites)} halt "
                f"sites, every one registered; {len(GATE_REGISTRY)} gates, "
                f"halt rows: {halt_counts()}"
            )
            return 0
        parts = []
        if moved:
            parts.append(f"{len(moved)} renumbered site(s)")
        if fresh:
            parts.append(f"{len(fresh)} unregistered site(s)")
        if ghosts:
            parts.append(f"{len(ghosts)} phantom(s)")
        print(f"FAIL -- {', '.join(parts)}")
        if moved:
            print()
            print("RENUMBERED -- the same return, at a new index. A sibling was")
            print("retired above it; remap the row rather than hunting a new gate:")
            for rename in moved:
                print(f"  {rename.describe()}")
                print(f"    {rename.named}")
                print(f"    -> {rename.found}")
        for site in fresh:
            print(f"  unregistered: {site.key}  line {site.line}  {site.head[:70]!r}")
        for gate_key, site in ghosts:
            print(f"  phantom: {gate_key} names {site}")
        print()
        if fresh or ghosts:
            print("Add the site to a GATE_REGISTRY row (or a new row with its issue")
            print("and the run that justified it); a halt-action row also moves the")
            print("ratchet baseline. Remove a stale site key from its row.")
        return 1

    if args.unregistered:
        print(render_tsv(unregistered(sites)))
        return 0
    if args.tsv:
        print(render_tsv(sites))
        return 0
    print(render_report(sites, coverage))
    return 0


if __name__ == "__main__":
    sys.exit(main())
