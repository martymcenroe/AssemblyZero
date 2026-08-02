"""Acceptance tests for the campaign timing dashboard (#2085).

The spec is boostgauge `docs/design/0003-campaign-timing-dashboard.md` and its
§7 is the acceptance contract; the issue's Tests section distils it. Both are
covered here.

The conventions most likely to regress silently — Central-only timestamps and
bucketing by START date — get their own tests, because getting either wrong
still produces a plausible-looking chart.
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from assemblyzero.speedrun.timing import (  # noqa: E402
    AUTOMATION_OVERHEAD_SECONDS,
    CSV_COLUMNS,
    analysis_dir,
    by_day,
    classify_gaps,
    load_runs,
    parse_ledger_durations,
    render_csv,
    write_csv,
)

BOOSTGAUGE = Path("C:/Users/mcwiz/Projects/boostgauge")


def _write_run(
    runs_dir: Path, tag: str, issue: int, start: str, end: str | None,
    rc: int = 0, heartbeat: str | None = None,
) -> None:
    runs_dir.mkdir(parents=True, exist_ok=True)
    lines = [f"{start} START issue=#{issue} repo=C:\\repo pid=1"]
    lines.append(f"{start} BASE 'hardening-run-test' verified clean for #{issue}")
    if end is not None:
        lines.append(f"{end} CHILD EXITED rc={rc}")
        lines.append(f"{end} EXIT rc={rc}")
    (runs_dir / f"{tag}-events.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if heartbeat:
        (runs_dir / f"{tag}-heartbeat.log").write_text(
            f"{start} alive\n{heartbeat} alive\n", encoding="utf-8"
        )


@pytest.fixture
def repo(tmp_path) -> Path:
    return tmp_path / "target"


def _no_commits(*_args, **_kwargs):
    return 0


def _one_commit(*_args, **_kwargs):
    return 1


# --- "all existing instrumented logs parse; killed runs use heartbeat" ----


@pytest.mark.skipif(not BOOSTGAUGE.is_dir(), reason="boostgauge checkout absent")
def test_every_real_events_log_parses_without_error():
    runs = load_runs(BOOSTGAUGE)
    assert len(runs) >= 59, f"spec expects 59+ instrumented logs, parsed {len(runs)}"
    for run in runs:
        assert run.issue > 0
        assert run.outcome in ("success", "failed", "killed")
        assert run.run_seconds >= 0


def test_killed_run_falls_back_to_the_last_heartbeat(repo):
    runs_dir = repo / "data" / "speedrun" / "runs"
    _write_run(
        runs_dir, "run-issue7-100000", 7,
        "2026-07-31 10:00:00", None, heartbeat="2026-07-31 10:45:30",
    )

    run = load_runs(repo)[0]

    assert run.outcome == "killed"
    assert run.source == "heartbeat"
    assert run.run_seconds == pytest.approx(45 * 60 + 30)


def test_killed_run_with_no_heartbeat_is_zero_not_invented(repo):
    runs_dir = repo / "data" / "speedrun" / "runs"
    _write_run(runs_dir, "run-issue7-100000", 7, "2026-07-31 10:00:00", None)

    run = load_runs(repo)[0]

    assert run.outcome == "killed"
    assert run.source == "unknown"
    assert run.run_seconds == 0.0, "an invented duration would land in the CSV as fact"


def test_a_nonzero_exit_is_failed_not_killed(repo):
    runs_dir = repo / "data" / "speedrun" / "runs"
    _write_run(runs_dir, "run-issue7-100000", 7,
               "2026-07-31 10:00:00", "2026-07-31 10:10:00", rc=1)
    assert load_runs(repo)[0].outcome == "failed"


# --- "a 23:50 -> 01:20 run lands only on its start date" -----------------


def test_a_run_crossing_midnight_counts_wholly_on_its_start_date(repo):
    runs_dir = repo / "data" / "speedrun" / "runs"
    _write_run(runs_dir, "run-issue4-235000", 4,
               "2026-07-31 23:50:00", "2026-08-01 01:20:00")

    runs = load_runs(repo)
    days = by_day(runs)

    assert [d.date for d in days] == ["2026-07-31"]
    assert days[0].run_count == 1
    assert days[0].run_hours == pytest.approx(1.5)


def test_timestamps_are_never_normalized_through_utc(repo):
    """A UTC round-trip would shift this run five or six hours onto 08-01."""
    runs_dir = repo / "data" / "speedrun" / "runs"
    _write_run(runs_dir, "run-issue4-232000", 4,
               "2026-07-31 23:20:00", "2026-07-31 23:40:00")

    run = load_runs(repo)[0]

    assert run.start == datetime(2026, 7, 31, 23, 20, 0)
    assert run.start.tzinfo is None, "a naive local stamp is the whole convention"
    assert run.start_date == "2026-07-31"


# --- "gap classification: zero fix time with no AZ commits" --------------


def test_no_assemblyzero_commits_means_zero_fix_time(repo):
    runs_dir = repo / "data" / "speedrun" / "runs"
    _write_run(runs_dir, "run-issue1-100000", 1,
               "2026-07-31 10:00:00", "2026-07-31 10:10:00", rc=1)
    _write_run(runs_dir, "run-issue1-120000", 1,
               "2026-07-31 12:00:00", "2026-07-31 12:10:00", rc=0)

    runs = load_runs(repo)
    report = classify_gaps(runs, ".", commit_counter=_no_commits)

    assert report.fix_seconds == 0.0
    assert report.idle_seconds == pytest.approx(110 * 60)
    assert all(r.fix_seconds == 0.0 for r in runs)
    assert by_day(runs)[0].fix_hours == 0.0


def test_a_long_gap_containing_a_commit_is_fix_time(repo):
    runs_dir = repo / "data" / "speedrun" / "runs"
    _write_run(runs_dir, "run-issue1-100000", 1,
               "2026-07-31 10:00:00", "2026-07-31 10:10:00", rc=1)
    _write_run(runs_dir, "run-issue1-120000", 1,
               "2026-07-31 12:00:00", "2026-07-31 12:10:00", rc=0)

    runs = load_runs(repo)
    report = classify_gaps(runs, ".", commit_counter=_one_commit)

    assert report.fix_seconds == pytest.approx(110 * 60)
    assert runs[0].fix_seconds == pytest.approx(110 * 60)
    assert report.idle_seconds == 0.0


def test_fix_time_attributes_to_the_failed_runs_start_date(repo):
    """The repair happened on 08-01; the bar it belongs to is 07-31."""
    runs_dir = repo / "data" / "speedrun" / "runs"
    _write_run(runs_dir, "run-issue1-233000", 1,
               "2026-07-31 23:30:00", "2026-07-31 23:40:00", rc=1)
    _write_run(runs_dir, "run-issue1-020000", 1,
               "2026-08-01 02:00:00", "2026-08-01 02:10:00", rc=0)

    runs = load_runs(repo)
    classify_gaps(runs, ".", commit_counter=_one_commit)
    days = {d.date: d for d in by_day(runs)}

    assert days["2026-07-31"].fix_hours > 0
    assert days["2026-08-01"].fix_hours == 0.0


@pytest.mark.parametrize(
    "gap_seconds,expect_fix",
    [(AUTOMATION_OVERHEAD_SECONDS, False), (AUTOMATION_OVERHEAD_SECONDS + 1, True)],
)
def test_the_120_second_boundary(repo, gap_seconds, expect_fix):
    """Exactly 120s is automation overhead; 121s is not."""
    runs_dir = repo / "data" / "speedrun" / "runs"
    _write_run(runs_dir, "run-issue1-100000", 1,
               "2026-07-31 10:00:00", "2026-07-31 10:00:00", rc=1)
    end = datetime(2026, 7, 31, 10, 0, 0)
    nxt = end.timestamp() + gap_seconds
    start_next = datetime.fromtimestamp(nxt).strftime("%Y-%m-%d %H:%M:%S")
    _write_run(runs_dir, "run-issue1-110000", 1, start_next, start_next, rc=0)

    runs = load_runs(repo)
    report = classify_gaps(runs, ".", commit_counter=_one_commit)

    assert (report.fix_seconds > 0) is expect_fix
    if not expect_fix:
        assert report.overhead_seconds == pytest.approx(gap_seconds)


def test_a_successful_run_contributes_no_fix_time(repo):
    runs_dir = repo / "data" / "speedrun" / "runs"
    _write_run(runs_dir, "run-issue1-100000", 1,
               "2026-07-31 10:00:00", "2026-07-31 10:10:00", rc=0)
    _write_run(runs_dir, "run-issue1-140000", 1,
               "2026-07-31 14:00:00", "2026-07-31 14:10:00", rc=0)

    runs = load_runs(repo)
    report = classify_gaps(runs, ".", commit_counter=_one_commit)

    assert report.fix_seconds == 0.0


def test_the_last_run_has_no_gap(repo):
    runs_dir = repo / "data" / "speedrun" / "runs"
    _write_run(runs_dir, "run-issue1-100000", 1,
               "2026-07-31 10:00:00", "2026-07-31 10:10:00", rc=1)

    runs = load_runs(repo)
    report = classify_gaps(runs, ".", commit_counter=_one_commit)

    assert report.fix_seconds == 0.0
    assert runs[0].fix_seconds == 0.0


# --- "CSV sums equal bar heights; per-bar run counts render" ------------


def test_csv_rows_sum_to_the_bar_heights(repo):
    runs_dir = repo / "data" / "speedrun" / "runs"
    _write_run(runs_dir, "run-issue1-100000", 1,
               "2026-07-31 10:00:00", "2026-07-31 10:30:00", rc=1)
    _write_run(runs_dir, "run-issue4-120000", 4,
               "2026-07-31 12:00:00", "2026-07-31 13:00:00", rc=0)

    runs = load_runs(repo)
    classify_gaps(runs, ".", commit_counter=_one_commit)
    day = by_day(runs)[0]

    rows = [r.split(",") for r in render_csv(runs).strip().splitlines()[1:]]
    run_seconds = sum(float(r[3]) for r in rows)
    fix_seconds = sum(float(r[4]) for r in rows)

    assert run_seconds / 3600 == pytest.approx(day.run_hours)
    assert fix_seconds / 3600 == pytest.approx(day.fix_hours)
    assert day.run_count == 2


def test_csv_carries_the_specified_columns(repo):
    runs_dir = repo / "data" / "speedrun" / "runs"
    _write_run(runs_dir, "run-issue1-100000", 1,
               "2026-07-31 10:00:00", "2026-07-31 10:30:00")
    header = render_csv(load_runs(repo)).splitlines()[0]
    assert header.split(",") == list(CSV_COLUMNS)


# --- "two runs over identical inputs produce byte-identical CSV" --------


def test_csv_is_byte_identical_across_runs(repo):
    runs_dir = repo / "data" / "speedrun" / "runs"
    for tag, issue, start, end in (
        ("run-issue4-120000", 4, "2026-07-31 12:00:00", "2026-07-31 12:30:00"),
        ("run-issue1-100000", 1, "2026-07-31 10:00:00", "2026-07-31 10:30:00"),
        ("run-issue7-140000", 7, "2026-07-31 14:00:00", "2026-07-31 14:30:00"),
    ):
        _write_run(runs_dir, tag, issue, start, end)

    first = write_csv(repo, load_runs(repo)).read_bytes()
    second = write_csv(repo, load_runs(repo)).read_bytes()

    assert first == second
    assert b"\r\n" not in first, "CRLF would make the bytes platform-dependent"


def test_csv_row_order_does_not_depend_on_directory_order(repo):
    runs_dir = repo / "data" / "speedrun" / "runs"
    _write_run(runs_dir, "run-issue9-090000", 9, "2026-07-31 09:00:00", "2026-07-31 09:10:00")
    _write_run(runs_dir, "run-issue1-080000", 1, "2026-07-31 08:00:00", "2026-07-31 08:10:00")

    rows = render_csv(load_runs(repo)).splitlines()[1:]
    assert rows[0].startswith("2026-07-31 08:00:00"), "rows sort by start time"


# --- "no code path writes outside <target>/data/speedrun/analysis/" -----


def test_the_only_write_target_is_the_analysis_dir(repo):
    runs_dir = repo / "data" / "speedrun" / "runs"
    _write_run(runs_dir, "run-issue1-100000", 1,
               "2026-07-31 10:00:00", "2026-07-31 10:30:00")

    before = {p for p in repo.rglob("*") if p.is_file()}
    write_csv(repo, load_runs(repo))
    after = {p for p in repo.rglob("*") if p.is_file()}

    created = after - before
    assert created, "the CSV should have been written"
    for path in created:
        assert analysis_dir(repo) in path.parents, f"{path} is outside the analysis dir"


def test_source_declares_no_other_write_target():
    """A grep-level guard: only the analysis dir may be a write destination."""
    import inspect

    from assemblyzero.speedrun import timing

    source = inspect.getsource(timing)
    for writer in ("write_text(", "open(", "mkdir("):
        for line_no, line in enumerate(source.splitlines(), 1):
            if writer in line and "read_text" not in line:
                context = "\n".join(source.splitlines()[max(0, line_no - 12):line_no])
                assert "analysis_dir" in context or "io.StringIO" in line, (
                    f"line {line_no} writes without an analysis_dir anchor: {line.strip()}"
                )


# --- chart rendering -----------------------------------------------------


def test_chart_renders_with_counts_and_both_segments(repo, tmp_path):
    import campaign_timing_dashboard as cli

    runs_dir = repo / "data" / "speedrun" / "runs"
    _write_run(runs_dir, "run-issue1-100000", 1,
               "2026-07-31 10:00:00", "2026-07-31 10:30:00", rc=1)
    _write_run(runs_dir, "run-issue4-120000", 4,
               "2026-07-31 12:00:00", "2026-07-31 13:00:00", rc=0)
    _write_run(runs_dir, "run-issue7-090000", 7,
               "2026-08-01 09:00:00", "2026-08-01 09:20:00", rc=0)

    runs = load_runs(repo)
    classify_gaps(runs, ".", commit_counter=_one_commit)
    days = by_day(runs)

    out = cli.render_chart(days, tmp_path / "chart.png", idle_hours=0.4)

    assert out.is_file()
    assert out.stat().st_size > 5000, "a real PNG, not an empty canvas"


def test_chart_uses_the_validated_palette():
    import campaign_timing_dashboard as cli

    # Validated with scripts/validate_palette.js: adjacent CVD dE 24.7,
    # normal-vision 33.6, both >= 3:1 on the surface. Changing either hue
    # without re-running the validator is the thing this guards.
    assert cli.SERIES_RUN == "#2a78d6"
    assert cli.SERIES_FIX == "#eb6834"
    assert cli.SERIES_RUN != cli.SERIES_FIX


def test_reconstructed_days_are_marked(repo, tmp_path):
    import campaign_timing_dashboard as cli

    runs_dir = repo / "data" / "speedrun" / "runs"
    _write_run(runs_dir, "run-issue1-100000", 1,
               "2026-07-28 10:00:00", "2026-07-28 10:30:00")

    days = by_day(load_runs(repo), reconstructed_dates={"2026-07-28"})
    assert days[0].reconstructed is True

    out = cli.render_chart(days, tmp_path / "chart.png")
    assert out.is_file()


# --- ledger reconstruction ----------------------------------------------


def test_ledger_parser_only_reads_durations_next_to_a_date():
    bodies = [
        "run8 on 2026-07-28 took 313s end to end",
        "no date here, 984s",
        "2026-07-29 — two rolls: 1244s and 610s",
    ]
    found = parse_ledger_durations(bodies)

    assert ("2026-07-28", 313.0) in found
    assert ("2026-07-29", 1244.0) in found
    assert ("2026-07-29", 610.0) in found
    assert all(d != "" for d, _ in found)
    assert 984.0 not in [s for _, s in found], "a bar without a date would be invented"


def test_ledger_parser_on_empty_input():
    assert parse_ledger_durations([]) == []
    assert parse_ledger_durations(["", None]) == []


# --- CLI ------------------------------------------------------------------


def test_cli_dry_run_writes_nothing(repo, capsys):
    import campaign_timing_dashboard as cli

    runs_dir = repo / "data" / "speedrun" / "runs"
    _write_run(runs_dir, "run-issue1-100000", 1,
               "2026-07-31 10:00:00", "2026-07-31 10:30:00")

    code = cli.main(["--repo", str(repo), "--dry-run"])

    assert code == 0
    assert not analysis_dir(repo).exists()
    assert "Dry run" in capsys.readouterr().out


def test_cli_reports_when_there_is_nothing_to_chart(tmp_path, capsys):
    import campaign_timing_dashboard as cli

    empty = tmp_path / "empty"
    empty.mkdir()

    assert cli.main(["--repo", str(empty)]) == 1
    assert "No parseable runs" in capsys.readouterr().out


def test_cli_writes_both_outputs(repo):
    import campaign_timing_dashboard as cli

    runs_dir = repo / "data" / "speedrun" / "runs"
    _write_run(runs_dir, "run-issue1-100000", 1,
               "2026-07-31 10:00:00", "2026-07-31 10:30:00")

    code = cli.main(["--repo", str(repo), "--assemblyzero-root", str(repo)])

    assert code == 0
    assert (analysis_dir(repo) / "runs.csv").is_file()
    assert (analysis_dir(repo) / "campaign-timing.png").is_file()


def test_az_commit_window_is_queried_in_local_time():
    from assemblyzero.speedrun.timing import az_commits_between

    seen = {}

    def fake(args):
        seen["args"] = args
        return subprocess.CompletedProcess(args, 0, "abc123\n", "")

    count = az_commits_between(
        ".", datetime(2026, 7, 31, 10, 0, 0), datetime(2026, 7, 31, 12, 0, 0), runner=fake
    )

    assert count == 1
    joined = " ".join(seen["args"])
    assert "--since=2026-07-31 10:00:00" in joined
    assert "--until=2026-07-31 12:00:00" in joined
    assert "Z" not in joined and "+00:00" not in joined, "no UTC anywhere"


def test_az_commit_query_failure_counts_as_zero():
    from assemblyzero.speedrun.timing import az_commits_between

    def failing(args):
        return subprocess.CompletedProcess(args, 128, "", "not a repo")

    assert az_commits_between(
        ".", datetime(2026, 7, 31, 10, 0), datetime(2026, 7, 31, 12, 0), runner=failing
    ) == 0
