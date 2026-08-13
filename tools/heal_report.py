#!/usr/bin/env python3
"""Roll up the healing ledger: what the machinery fixed about itself (#2164).

Reads ``data/speedrun/telemetry/heals.jsonl`` (written by record_heal at
every self-heal site), reports per-run and cross-run, and when the same
category+target recurs across enough distinct runs it emits a ready-to-file
issue stub. It NEVER files the issue: the machine asks, the operator rules,
same philosophy as the must-resolve flow (#2072).

Cold start honours standard 0025's rule: an empty ledger says so, with the
denominator, and never fabricates.

Usage:
    poetry run python tools/heal_report.py --repo /c/.../boostgauge
    poetry run python tools/heal_report.py --repo ... --recurrence 3
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from assemblyzero.speedrun.healing import (  # noqa: E402
    heals_path,
    is_per_roll,
    read_heals,
)


def render_report(records: list[dict], recurrence: int) -> str:
    lines: list[str] = []
    lines.append(f"{len(records)} heal record(s).")
    lines.append("")

    by_run: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_run[r.get("run_tag") or "(no run tag)"].append(r)

    lines.append("By run:")
    for run, rs in by_run.items():
        outcomes = defaultdict(int)
        for r in rs:
            outcomes[r.get("outcome", "?")] += 1
        summary = ", ".join(f"{k} {v}" for k, v in sorted(outcomes.items()))
        lines.append(f"  {run}: {len(rs)} heal(s) ({summary})")
        for r in rs:
            if r.get("outcome") != "healed":
                lines.append(
                    f"    ! {r.get('category')}: {r.get('target')} -- "
                    f"{r.get('outcome')}: {r.get('detail', '')[:100]}"
                )
    lines.append("")

    # Cross-run recurrence: the same category+target healed again and again
    # is a defect wearing a bandage.
    #
    # ...unless the target is merely a stable LABEL for an object each roll
    # re-creates, which is the ordinary condition of a hardening campaign that
    # rolls one issue repeatedly (#2269). `is_per_roll` carries that rule and
    # states its evidence; the two tiers are instance-first, category-second.
    # Groups it sets aside are reported below rather than dropped, so the
    # reader can see what was judged and disagree.
    runs_by_key: dict[tuple, set] = defaultdict(set)
    detail_by_key: dict[tuple, str] = {}
    instances_by_key: dict[tuple, list[str]] = defaultdict(list)
    for r in records:
        key = (r.get("category"), r.get("target"))
        runs_by_key[key].add(r.get("run_tag") or r.get("ts"))
        detail_by_key[key] = r.get("detail", "")
        instances_by_key[key].append(r.get("instance", "") or "")

    recurring = [
        (key, runs)
        for key, runs in runs_by_key.items()
        if len(runs) >= recurrence
    ]
    stubs = [
        (key, runs) for key, runs in recurring
        if not is_per_roll(key[0], instances_by_key[key])
    ]
    set_aside = [
        (key, runs) for key, runs in recurring
        if is_per_roll(key[0], instances_by_key[key])
    ]
    if stubs:
        lines.append(
            f"Recurring heals (same category+target across >= {recurrence} "
            "runs) -- ready-to-file issue stubs. Filing is the operator's "
            "call, never automatic:"
        )
        for (category, target), runs in sorted(stubs, key=lambda s: -len(s[1])):
            lines.append("")
            lines.append(
                f"  TITLE: fix: the machinery keeps healing "
                f"'{target}' ({category}) -- {len(runs)} runs"
            )
            lines.append(
                f"  BODY: The healing ledger shows {category} healing "
                f"'{target}' in {len(runs)} distinct runs "
                f"({', '.join(sorted(str(r) for r in runs)[:5])}). A heal "
                "that recurs is a defect with a bandage; find and fix the "
                f"source. Last detail: {detail_by_key[(category, target)][:200]}"
            )
    else:
        lines.append(
            f"No heal recurs across {recurrence}+ runs -- nothing proposes "
            "an issue."
        )

    # Never a silent cap: a group held back is named, with the reason, so the
    # judgement is auditable and a wrong call is visible rather than absent.
    if set_aside:
        lines.append("")
        lines.append(
            f"Set aside as per-roll artifacts (recurred across >= {recurrence} "
            "runs, but each firing addressed a fresh object -- see is_per_roll "
            "in assemblyzero/speedrun/healing.py):"
        )
        for (category, target), runs in sorted(set_aside, key=lambda s: -len(s[1])):
            known = [i for i in instances_by_key[(category, target)] if i]
            basis = (
                f"{len(set(known))} distinct recorded instances"
                if len(known) >= 2
                else f"category '{category}' heals the previous roll's leavings"
            )
            lines.append(
                f"  {category}: '{target}' in {len(runs)} runs -- {basis}"
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Roll up the healing ledger and propose issues for "
                    "recurring heals (#2164)."
    )
    parser.add_argument("--repo", required=True, help="Target repo root path")
    parser.add_argument(
        "--recurrence", type=int, default=3,
        help="Distinct runs before a recurring heal proposes an issue "
             "(default 3)",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.repo).resolve()
    records = read_heals(repo_root)
    if not records:
        print(
            f"No heal records at {heals_path(repo_root)}.\n"
            "Either nothing has needed healing since the ledger landed, or "
            "no roll has run since. An empty ledger is a real answer; during "
            "cold start, grep the events logs by hand (standard 0025's rule: "
            "never fabricate)."
        )
        return 0

    print(render_report(records, max(1, args.recurrence)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
