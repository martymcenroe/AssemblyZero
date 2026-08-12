"""Rank drafter failure fingerprints by what they actually cost (#2075).

#2074 counts validation failures. Counting alone ranks a cheap failure that
happens often above an expensive one that happens rarely, which is the wrong
order to fix things in. This joins the counts to roll durations so the ranking
is by cost:

    cost = occurrences x mean wasted roll seconds

## Unknown is not zero

A fingerprint with no duration data is ranked by occurrence count and flagged
`duration-unknown`. It is never costed at zero -- that would sort the most
expensive unmeasured failure to the bottom of the list, which is precisely the
failure this tool exists to surface. Unknown-duration entries sort after
costed ones at equal standing, but they are never dropped.

## The join

Telemetry records carry `run_id`, the events-log basename (`run-issue2-133746`).
The timing dashboard's `runs.csv` carries `start_local` and `issue`. The tag
encodes both -- issue number and HHMMSS -- so the join parses the tag and
matches the row whose issue and start time agree. No new column is needed on
either side, and a tag that matches nothing yields unknown duration rather than
a silent drop.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path

TELEMETRY_REL = Path("data/speedrun/telemetry/prompt-failures.jsonl")
RUNS_CSV_REL = Path("data/speedrun/analysis/runs.csv")

_RE_TAG = re.compile(r"run-?\w*?-?issue(?P<issue>\d+)-(?P<hhmmss>\d{6})")

UNKNOWN_DURATION = "duration-unknown"


@dataclass
class Ranked:
    fingerprint: str
    occurrences: int
    mean_wasted_seconds: float | None
    cost: float | None
    flags: tuple[str, ...] = ()
    models: tuple[str, ...] = ()

    @property
    def duration_known(self) -> bool:
        return self.mean_wasted_seconds is not None


def load_telemetry(repo_root: Path | str) -> list[dict]:
    path = Path(repo_root) / TELEMETRY_REL
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return []
    rows = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def load_durations(repo_root: Path | str) -> dict[tuple[int, str], float]:
    """(issue, HHMMSS) -> run seconds, from the timing dashboard's runs.csv."""
    path = Path(repo_root) / RUNS_CSV_REL
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}

    durations: dict[tuple[int, str], float] = {}
    for row in csv.DictReader(text.splitlines()):
        try:
            issue = int(row["issue"])
            seconds = float(row["run_seconds"])
            hhmmss = row["start_local"].split(" ")[1].replace(":", "")
        except (KeyError, ValueError, IndexError):
            continue
        durations[(issue, hhmmss)] = seconds
    return durations


def duration_for(run_id: str, durations: dict[tuple[int, str], float]) -> float | None:
    match = _RE_TAG.search(run_id or "")
    if not match:
        return None
    key = (int(match.group("issue")), match.group("hhmmss"))
    return durations.get(key)


def rank(rows: list[dict], durations: dict[tuple[int, str], float]) -> list[Ranked]:
    """Fingerprints ordered by cost, then by occurrences, then by name.

    The tie-breaks are what make the output byte-identical for identical input;
    sorting on cost alone leaves equal-cost entries in dict order.
    """
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        fingerprint = row.get("fingerprint") or "unknown"
        grouped.setdefault(fingerprint, []).append(row)

    ranked: list[Ranked] = []
    for fingerprint, entries in grouped.items():
        # #2198: a record that measured its own cost is authoritative for
        # itself; the run table is the fallback for records that did not.
        # Existing rows carry no `duration_seconds`, so they resolve exactly as
        # before -- through the run_id lookup.
        seconds = [
            d for d in (
                e.get("duration_seconds")
                if e.get("duration_seconds") is not None
                else duration_for(e.get("run_id", ""), durations)
                for e in entries
            )
            if d is not None
        ]
        models = tuple(sorted({e.get("drafter_model") or "unknown" for e in entries}))
        occurrences = len(entries)

        if seconds:
            mean = sum(seconds) / len(seconds)
            ranked.append(
                Ranked(fingerprint, occurrences, mean, occurrences * mean, (), models)
            )
        else:
            ranked.append(
                Ranked(fingerprint, occurrences, None, None, (UNKNOWN_DURATION,), models)
            )

    # Costed entries first by cost; unknown-duration entries after, ordered by
    # occurrences. Never dropped, never costed at zero.
    return sorted(
        ranked,
        key=lambda r: (
            0 if r.duration_known else 1,
            -(r.cost if r.cost is not None else 0.0),
            -r.occurrences,
            r.fingerprint,
        ),
    )


def render(ranked: list[Ranked]) -> str:
    """Deterministic text table. Identical input yields identical bytes."""
    if not ranked:
        return "No validation failures recorded — nothing to rank.\n"

    width = max(len(r.fingerprint) for r in ranked)
    lines = [
        f"{'fingerprint'.ljust(width)}  {'count':>5}  {'mean_s':>8}  {'cost_s':>10}  flags",
        f"{'-' * width}  {'-' * 5}  {'-' * 8}  {'-' * 10}  -----",
    ]
    for entry in ranked:
        mean = f"{entry.mean_wasted_seconds:.1f}" if entry.duration_known else "-"
        cost = f"{entry.cost:.1f}" if entry.duration_known else "-"
        lines.append(
            f"{entry.fingerprint.ljust(width)}  {entry.occurrences:>5}  "
            f"{mean:>8}  {cost:>10}  {','.join(entry.flags)}"
        )
    return "\n".join(lines) + "\n"
