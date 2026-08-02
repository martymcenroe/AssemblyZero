"""Parse a campaign's run logs into a timing table (#2085).

Spec: boostgauge `docs/design/0003-campaign-timing-dashboard.md`, which is
normative. This module is the parsing and classification half; the chart lives
in `tools/campaign_timing_dashboard.py`.

The question it answers: where did the campaign's wall-clock actually go --
how much was the pipeline working, and how much was a human or agent repairing
the pipeline between failed runs.

## Conventions that are easy to get wrong

**Local US Central everywhere; no UTC anywhere.** The events logs are already
local wall-clock (`2026-07-31 10:20:40 START issue=#7 ...`). Normalizing through
UTC would shift every run five or six hours and silently move the late-evening
ones onto the wrong day -- which is exactly the bucketing the chart is about.
Timestamps are parsed naive and stay naive.

**Bucket strictly by run START date.** A run that starts 23:50 and exits 01:20
counts entirely on the start date, and fix-gaps attribute to the *failed run's*
start date, not to the date the repair happened. This is THE convention in the
spec; it is what makes a bar mean "the work begun on this day".

**A gap is only fix time with evidence.** More than 120 seconds AND at least one
AssemblyZero commit landing on origin/main inside the window. A long gap with no
commit is unattributed idle: excluded from the bars but totaled in a footnote, so
exclusions are visible rather than silent.
"""

from __future__ import annotations

import csv
import io
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

RUNS_REL = Path("data/speedrun/runs")
ANALYSIS_REL = Path("data/speedrun/analysis")
CSV_NAME = "runs.csv"
CHART_NAME = "campaign-timing.png"

EVENTS_SUFFIX = "-events.log"
HEARTBEAT_SUFFIX = "-heartbeat.log"

#: Spec §3.5: at day scale a sub-two-minute gap is self-heal/redraw noise.
AUTOMATION_OVERHEAD_SECONDS = 120

_TS = r"(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"
_RE_START = re.compile(rf"^{_TS} START issue=#(?P<issue>\d+)")
_RE_EXIT = re.compile(rf"^{_TS} EXIT rc=(?P<rc>-?\d+)")
_RE_ANY_TS = re.compile(rf"^{_TS}")
_TS_FMT = "%Y-%m-%d %H:%M:%S"

CSV_COLUMNS = (
    "start_local", "issue", "outcome", "run_seconds",
    "fix_seconds_attributed", "source",
)


@dataclass
class Run:
    """One `START` line in an events log: one roll of one issue."""

    tag: str
    issue: int
    start: datetime
    end: datetime | None
    outcome: str          # success | failed | killed
    source: str           # events | heartbeat
    fix_seconds: float = 0.0

    @property
    def run_seconds(self) -> float:
        return (self.end - self.start).total_seconds() if self.end else 0.0

    @property
    def start_date(self) -> str:
        return self.start.strftime("%Y-%m-%d")

    @property
    def succeeded(self) -> bool:
        return self.outcome == "success"


def _last_timestamp(path: Path) -> datetime | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    stamp = None
    for line in text.splitlines():
        match = _RE_ANY_TS.match(line)
        if match:
            stamp = match.group("ts")
    return datetime.strptime(stamp, _TS_FMT) if stamp else None


def parse_events_log(path: Path) -> Run | None:
    """One run from its events log. None when the log has no START line.

    A run with no `EXIT` was killed uncatchably; the last heartbeat is its time
    of death. That fallback is why a killed run still contributes real run time
    instead of being dropped or counted as zero.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    tag = path.name[: -len(EVENTS_SUFFIX)]
    start = end = None
    issue = 0
    outcome = "killed"

    for line in text.splitlines():
        began = _RE_START.match(line)
        if began and start is None:
            start = datetime.strptime(began.group("ts"), _TS_FMT)
            issue = int(began.group("issue"))
            continue
        exited = _RE_EXIT.match(line)
        if exited:
            end = datetime.strptime(exited.group("ts"), _TS_FMT)
            outcome = "success" if int(exited.group("rc")) == 0 else "failed"

    if start is None:
        return None

    source = "events"
    if end is None:
        beat = _last_timestamp(path.with_name(f"{tag}{HEARTBEAT_SUFFIX}"))
        if beat is not None and beat >= start:
            end, source = beat, "heartbeat"
        else:
            # No exit and no usable heartbeat: the run's duration is genuinely
            # unknown. Recorded at zero seconds and tagged killed rather than
            # guessed -- an invented duration would land in the CSV as fact.
            end, source = start, "unknown"
        outcome = "killed"

    return Run(tag=tag, issue=issue, start=start, end=end, outcome=outcome, source=source)


def load_runs(repo_root: Path | str) -> list[Run]:
    """Every parseable run under the target repo, ordered by start time."""
    runs_dir = Path(repo_root) / RUNS_REL
    if not runs_dir.is_dir():
        return []
    runs = []
    for path in sorted(runs_dir.glob(f"*{EVENTS_SUFFIX}")):
        run = parse_events_log(path)
        if run is not None:
            runs.append(run)
    return sorted(runs, key=lambda r: (r.start, r.tag))


# ---------------------------------------------------------------------------
# Gap classification
# ---------------------------------------------------------------------------


def az_commits_between(
    az_root: Path | str, start: datetime, end: datetime, runner=None
) -> int:
    """AssemblyZero commits on origin/main inside a local-time window.

    `--since`/`--until` are handed local wall-clock strings deliberately: git
    interprets them in the machine's zone, which is the same zone the logs are
    written in. Converting to UTC first would shift the window off the gap.
    """
    runner = runner or (
        lambda args: subprocess.run(
            args, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
    )
    result = runner([
        "git", "-C", str(az_root), "log", "origin/main",
        f"--since={start.strftime(_TS_FMT)}",
        f"--until={end.strftime(_TS_FMT)}",
        "--format=%H",
    ])
    if getattr(result, "returncode", 1) != 0:
        return 0
    return len([line for line in (result.stdout or "").splitlines() if line.strip()])


@dataclass
class GapReport:
    fix_seconds: float = 0.0
    idle_seconds: float = 0.0
    overhead_seconds: float = 0.0


def classify_gaps(
    runs: list[Run], az_root: Path | str, *, commit_counter=az_commits_between
) -> GapReport:
    """Attribute post-failure gaps. Mutates each run's `fix_seconds`.

    Applies to every run that did not succeed -- failed and killed alike. A
    killed run is not a success, and the repair that followed it is the same
    kind of work as one that follows a nonzero exit.
    """
    report = GapReport()
    ordered = sorted(runs, key=lambda r: (r.start, r.tag))

    for index, run in enumerate(ordered):
        run.fix_seconds = 0.0
        if run.succeeded:
            continue
        if index + 1 >= len(ordered):
            # Spec §3.5: the last run of the dataset has no following start.
            continue

        terminal = run.end or run.start
        following = ordered[index + 1].start
        gap = (following - terminal).total_seconds()
        if gap <= 0:
            continue

        if gap <= AUTOMATION_OVERHEAD_SECONDS:
            report.overhead_seconds += gap
            continue

        if commit_counter(az_root, terminal, following) >= 1:
            run.fix_seconds = gap
            report.fix_seconds += gap
        else:
            report.idle_seconds += gap

    return report


# ---------------------------------------------------------------------------
# Aggregation and output
# ---------------------------------------------------------------------------


@dataclass
class DayTotals:
    date: str
    run_hours: float
    fix_hours: float
    run_count: int
    reconstructed: bool = False


def by_day(runs: list[Run], reconstructed_dates: set[str] | None = None) -> list[DayTotals]:
    """Per local START date, ordered oldest first."""
    reconstructed = reconstructed_dates or set()
    buckets: dict[str, list[Run]] = {}
    for run in runs:
        buckets.setdefault(run.start_date, []).append(run)

    return [
        DayTotals(
            date=date,
            run_hours=sum(r.run_seconds for r in day) / 3600.0,
            fix_hours=sum(r.fix_seconds for r in day) / 3600.0,
            run_count=len(day),
            reconstructed=date in reconstructed,
        )
        for date, day in sorted(buckets.items())
    ]


def render_csv(runs: list[Run]) -> str:
    """Deterministic CSV text: same inputs produce the same bytes.

    Rows sorted by start then tag, `\\n` line endings written explicitly, and
    seconds formatted to a fixed precision -- float repr would otherwise vary the
    bytes without the numbers changing.
    """
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for run in sorted(runs, key=lambda r: (r.start, r.tag)):
        writer.writerow([
            run.start.strftime(_TS_FMT),
            run.issue,
            run.outcome,
            f"{run.run_seconds:.1f}",
            f"{run.fix_seconds:.1f}",
            run.source,
        ])
    return buffer.getvalue()


def analysis_dir(repo_root: Path | str) -> Path:
    return Path(repo_root) / ANALYSIS_REL


def write_csv(repo_root: Path | str, runs: list[Run]) -> Path:
    """The ONLY filesystem write this module performs, and it is inside
    `<target>/data/speedrun/analysis/` by construction."""
    out = analysis_dir(repo_root)
    out.mkdir(parents=True, exist_ok=True)
    path = out / CSV_NAME
    path.write_text(render_csv(runs), encoding="utf-8", newline="")
    return path


# ---------------------------------------------------------------------------
# Ledger-era reconstruction (optional scope)
# ---------------------------------------------------------------------------


def parse_ledger_durations(comment_bodies: list[str]) -> list[tuple[str, float]]:
    """(date, seconds) pairs recoverable from campaign-ledger comments.

    Deliberately conservative: it reads `NNNs` durations that appear next to an
    explicit date, and nothing else. A looser parser would invent bars for the
    pre-instrumentation era, and a wrong bar is worse than an absent one.
    """
    found: list[tuple[str, float]] = []
    date_re = re.compile(r"(\d{4}-\d{2}-\d{2})")
    dur_re = re.compile(r"\b(\d{2,5})s\b")
    for body in comment_bodies or []:
        for line in (body or "").splitlines():
            date_match = date_re.search(line)
            if not date_match:
                continue
            for dur in dur_re.findall(line):
                found.append((date_match.group(1), float(dur)))
    return found
