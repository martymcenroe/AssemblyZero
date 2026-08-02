#!/usr/bin/env python3
"""Where did the campaign's wall-clock go? (#2085)

Spec: boostgauge `docs/design/0003-campaign-timing-dashboard.md` (normative).
Delivery of outputs for boostgauge is tracked in boostgauge #218.

One stacked bar per local date: run time (the pipeline working) beneath
diagnose+fix time (a human or agent repairing the pipeline between failed runs),
with the day's run count above each bar.

    poetry run python tools/campaign_timing_dashboard.py --repo /c/.../boostgauge
    poetry run python tools/campaign_timing_dashboard.py --repo <path> --dry-run

Read-only against the target repo except for `data/speedrun/analysis/`, which is
gitignored. Exit 0 on success, 1 when there is nothing to chart.

## Chart decisions (dataviz skill)

Two series is a categorical job -- identity, not magnitude -- so the two fixed
categorical slots are used in order and never cycled. The pair was validated
rather than eyeballed:

    validate_palette.js "#2a78d6,#eb6834" --mode light
    CVD separation  worst adjacent ΔE 24.7 (protan) · tritan 32.7   PASS
    Normal-vision   worst adjacent ΔE 33.6                          PASS
    Contrast        both >= 3:1 vs surface                          PASS

Both series are direct-labeled in the legend and the axis carries units, so
identity is never colour-alone. A 2px surface-coloured gap separates the stacked
segments. Grid and axes are recessive; the value text wears ink colours rather
than the series colour.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from assemblyzero.speedrun.timing import (  # noqa: E402
    CHART_NAME,
    analysis_dir,
    by_day,
    classify_gaps,
    load_runs,
    parse_ledger_durations,
    write_csv,
)

# Categorical slots 1 and 2 from the validated reference palette, light mode.
SERIES_RUN = "#2a78d6"
SERIES_FIX = "#eb6834"
SURFACE = "#fcfcfb"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#8a8880"


def _log(msg: str) -> None:
    print(msg, flush=True)


def _short_date(iso: str) -> str:
    from datetime import datetime

    return datetime.strptime(iso, "%Y-%m-%d").strftime("%b %d").replace(" 0", " ")


def render_chart(days, out_path: Path, *, idle_hours: float = 0.0) -> Path:
    """Stacked bar per local date. Run time bottom, diagnose+fix on top."""
    import matplotlib

    matplotlib.use("Agg")  # no display on a scheduled or headless run
    import matplotlib.pyplot as plt

    labels = [_short_date(d.date) for d in days]
    run_hours = [d.run_hours for d in days]
    fix_hours = [d.fix_hours for d in days]

    width = max(8.0, 0.62 * len(days) + 2.2)
    fig, ax = plt.subplots(figsize=(width, 5.6), dpi=160)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    bars_run = ax.bar(labels, run_hours, color=SERIES_RUN, width=0.68, label="Run time")
    # linewidth in the surface colour is the 2px spacer between stacked fills.
    bars_fix = ax.bar(
        labels, fix_hours, bottom=run_hours, color=SERIES_FIX, width=0.68,
        label="Diagnose + fix time", linewidth=1.6, edgecolor=SURFACE,
    )

    for day, bar_run, bar_fix in zip(days, bars_run, bars_fix):
        if day.reconstructed:
            bar_run.set_hatch("//")
            bar_fix.set_hatch("//")
            bar_run.set_alpha(0.72)
            bar_fix.set_alpha(0.72)

    # Spec §4: the day's run count sits above each bar.
    for label, run_h, fix_h, day in zip(labels, run_hours, fix_hours, days):
        ax.annotate(
            str(day.run_count), xy=(label, run_h + fix_h), xytext=(0, 5),
            textcoords="offset points", ha="center", va="bottom",
            fontsize=9, color=INK_SECONDARY,
        )

    # Headroom for the per-bar counts. Without it the tallest bar's annotation
    # lands in the legend row -- visible only by rendering the thing and looking
    # at it, which is why that is a step and not an optional courtesy.
    tallest = max((r + f for r, f in zip(run_hours, fix_hours)), default=1.0)
    ax.set_ylim(0, tallest * 1.16 if tallest else 1.0)
    ax.margins(x=0.12)

    ax.set_ylabel("Hours", color=INK_SECONDARY, fontsize=10)
    ax.set_title(
        "Campaign wall-clock by day — run time vs diagnose + fix time",
        color=INK_PRIMARY, fontsize=13, pad=26, loc="left",
    )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(INK_MUTED)
        ax.spines[side].set_linewidth(0.8)
    ax.tick_params(colors=INK_SECONDARY, labelsize=9)
    ax.grid(axis="y", color=INK_MUTED, alpha=0.22, linewidth=0.7)
    ax.set_axisbelow(True)
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")

    legend = ax.legend(frameon=False, loc="upper left", fontsize=9, ncols=2,
                       bbox_to_anchor=(0, 1.06))
    for text in legend.get_texts():
        text.set_color(INK_SECONDARY)

    footnotes = ["Bars are bucketed by run START date; a run crossing midnight counts on the day it began."]
    if idle_hours > 0:
        footnotes.append(
            f"Excluded: {idle_hours:.1f}h of unattributed idle "
            f"(gaps over 2 min with no AssemblyZero commit inside)."
        )
    if any(d.reconstructed for d in days):
        footnotes.append("Hatched bars are reconstructed from the campaign ledger, not instrumented logs.")
    fig.text(0.01, 0.005, "\n".join(footnotes), fontsize=7.5, color=INK_MUTED, va="bottom")

    fig.tight_layout(rect=(0, 0.04 + 0.018 * len(footnotes), 1, 1))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, facecolor=SURFACE)
    plt.close(fig)
    return out_path


def _ledger_dates(repo_root: Path, issue: int) -> set[str]:
    """Dates recoverable from the campaign ledger, for hatching."""
    result = subprocess.run(
        ["gh", "issue", "view", str(issue), "--repo", _slug(repo_root),
         "--json", "comments", "--jq", "[.comments[].body]"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        _log(f"  ledger issue #{issue} unreadable; reconstructed era omitted")
        return set()
    try:
        bodies = json.loads(result.stdout or "[]")
    except ValueError:
        return set()
    return {date for date, _ in parse_ledger_durations(bodies)}


def _slug(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "remote", "get-url", "origin"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    url = (result.stdout or "").strip()
    for prefix in ("https://github.com/", "git@github.com:"):
        if url.startswith(prefix):
            path = url[len(prefix):]
            return path[:-4] if path.endswith(".git") else path
    return ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Chart a speedrun campaign's wall-clock by day."
    )
    parser.add_argument("--repo", required=True, help="target repository root")
    parser.add_argument(
        "--assemblyzero-root", default=str(Path(__file__).resolve().parents[1]),
        help="tree whose origin/main commits classify a gap as fix time",
    )
    parser.add_argument("--ledger-issue", type=int, default=0,
                        help="reconstruct the pre-instrumentation era from this issue's comments")
    parser.add_argument("--dry-run", action="store_true", help="report without writing")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    runs = load_runs(repo)
    if not runs:
        _log(f"No parseable runs under {repo / 'data/speedrun/runs'}")
        return 1

    gaps = classify_gaps(runs, args.assemblyzero_root)
    reconstructed = _ledger_dates(repo, args.ledger_issue) if args.ledger_issue else set()
    days = by_day(runs, reconstructed)

    _log(f"runs            {len(runs)}")
    _log(f"days            {len(days)}")
    _log(f"run time        {sum(d.run_hours for d in days):.1f}h")
    _log(f"diagnose+fix    {gaps.fix_seconds / 3600:.1f}h")
    _log(f"excluded idle   {gaps.idle_seconds / 3600:.1f}h")
    _log(f"excluded churn  {gaps.overhead_seconds / 3600:.1f}h (gaps under 2 min)")

    if args.dry_run:
        _log("\nDry run. Nothing written.")
        return 0

    csv_path = write_csv(repo, runs)
    chart_path = render_chart(
        days, analysis_dir(repo) / CHART_NAME, idle_hours=gaps.idle_seconds / 3600
    )
    _log(f"\nwrote {csv_path}")
    _log(f"wrote {chart_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
