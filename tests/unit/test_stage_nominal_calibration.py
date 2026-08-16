"""The SLOW label must not fire on healthy runs (#2410).

    [STAGE] lld running 300s (nominal ~75s) - SLOW, 3x nominal

printed on run-issue1-114223 while the stage completed normally: its three
prior LLD passes on that repo took 380.1s and 409.0s. Every ordinary LLD run
crossed the threshold.

The fleet's doctrine is no false alarms, because a check that cries wolf trains
the operator to ignore it. The SLOW label exists to distinguish a hang from
patience, and a label that fires on every healthy run erases that distinction
exactly where it was needed -- the #2405 storm was first noticed through these
labels, so their credibility is operationally real.

The cause was the STATISTIC, not the derivation. #2323 correctly replaced a
hand-typed table with a derived one; the median it chose describes "typical"
only when the distribution has one mode, and this one does not.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from assemblyzero.core.stage_watchdog import (
    MIN_SAMPLES_FOR_NOMINAL,
    SLOW_RATIO,
    STAGE_NOMINAL_SECONDS,
    STALLED_RATIO,
    StageWatchdog,
)

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import derive_stage_nominals as derive  # noqa: E402

#: The corpus as measured 2026-08-15, from
#: `derive_stage_nominals.py --runs <boostgauge>/data/speedrun/runs`.
#: Held here so the calibration claim is checkable without the corpus on disk.
CORPUS = {
    #        n    p50      p75      p90      max
    "lld": (74, 79.9, 332.9, 409.0, 741.1),
    "spec": (56, 89.0, 154.2, 406.7, 699.0),
    "impl": (22, 484.6, 1400.7, 2122.2, 2711.2),
    "pr": (21, 2.5, 2.9, 3.2, 4.3),
    "cleanup": (21, 81.9, 82.4, 82.7, 84.2),
}


class TestTheMeasuredFalseAlarm:
    """run-issue1-114223's LLD timing, replayed. The issue's first acceptance."""

    @pytest.mark.parametrize("elapsed", [300, 360, 409, 741])
    def test_a_healthy_lld_run_earns_no_label(self, elapsed):
        line = StageWatchdog("lld").status_line(elapsed)
        assert "SLOW" not in line, line
        assert "STALLED" not in line, line

    def test_the_old_nominal_would_have_labelled_it(self):
        """Pins WHY: at the previous median-derived 75.7s, 300s was 3.9x and
        earned SLOW. Without this the test above could pass for any reason."""
        line = StageWatchdog("lld", nominal_seconds=75.7).status_line(300)
        assert "SLOW" in line

    def test_the_line_still_reports_the_elapsed_time(self):
        """Quieter verdict, same information. The operator still sees the
        stage running; only the JUDGEMENT is withheld."""
        assert "running 300s" in StageWatchdog("lld").status_line(300)


class TestAGenuineHangIsStillCaught:
    """The issue's second acceptance: five times the recorded nominal still
    earns a label."""

    @pytest.mark.parametrize("stage", sorted(STAGE_NOMINAL_SECONDS))
    def test_five_times_nominal_is_slow(self, stage):
        nominal = STAGE_NOMINAL_SECONDS[stage]
        line = StageWatchdog(stage).status_line(nominal * 5)
        assert "SLOW" in line or "STALLED" in line, line

    @pytest.mark.parametrize("stage", sorted(STAGE_NOMINAL_SECONDS))
    def test_six_times_nominal_is_stalled(self, stage):
        nominal = STAGE_NOMINAL_SECONDS[stage]
        assert "STALLED" in StageWatchdog(stage).status_line(nominal * STALLED_RATIO)

    def test_the_17_minute_hang_class_is_still_caught(self):
        """#1886's founding case: a stage stalling far past anything it has
        ever taken must still be labelled."""
        line = StageWatchdog("lld").status_line(3600)
        assert "STALLED" in line


class TestNoFalseAlarmAcrossTheWholeCorpus:
    """The doctrine, asserted rather than hoped for.

    Every stage's WORST recorded healthy run must earn no label. This is the
    property that failed before: lld's max healthy run was 741.1s against a
    75.7s nominal -- 9.8x, deep into STALLED.
    """

    @pytest.mark.parametrize("stage", sorted(CORPUS))
    def test_the_slowest_healthy_run_earns_no_label(self, stage):
        _n, _p50, _p75, _p90, worst = CORPUS[stage]
        line = StageWatchdog(stage).status_line(worst)
        assert "SLOW" not in line, line
        assert "STALLED" not in line, line

    @pytest.mark.parametrize("stage", sorted(CORPUS))
    def test_the_old_median_nominal_would_have_cried_wolf_somewhere(self, stage):
        """Not every stage was miscalibrated -- this records which were, so
        the fix is not credited with more than it did."""
        _n, p50, _p75, _p90, worst = CORPUS[stage]
        cried = (worst / p50) >= SLOW_RATIO
        expected = stage in {"lld", "spec", "impl"}
        assert cried is expected, (
            f"{stage}: worst/{p50} = {worst / p50:.1f}x"
        )


class TestTheUnderSampledStageGetsNoVerdict:
    """'A nominal the fleet cannot yet compute honestly should say so rather
    than guess low.'"""

    def test_triage_is_omitted_rather_than_guessed(self):
        """It had no passing samples in the corpus and carried a hand-guessed
        20.0, which would have called a 61-second triage STALLED."""
        assert "triage" not in STAGE_NOMINAL_SECONDS

    def test_a_stage_with_no_nominal_reports_elapsed_without_a_verdict(self):
        line = StageWatchdog("triage").status_line(600)
        assert "running 600s" in line
        assert "SLOW" not in line
        assert "STALLED" not in line
        assert "nominal" not in line

    def test_an_unknown_stage_behaves_the_same_way(self):
        line = StageWatchdog("brand-new-stage").status_line(9999)
        assert "running 9999s" in line
        assert "SLOW" not in line

    def test_every_shipped_nominal_has_enough_samples_behind_it(self):
        for stage in STAGE_NOMINAL_SECONDS:
            assert CORPUS[stage][0] >= MIN_SAMPLES_FOR_NOMINAL, stage

    def test_the_floor_agrees_with_the_derivation_tool(self):
        """Two constants, one meaning. Pinned so they cannot drift."""
        assert MIN_SAMPLES_FOR_NOMINAL == derive.MIN_SAMPLES_FOR_NOMINAL


class TestTheTableMatchesItsDerivation:
    def test_the_tool_emits_the_p90(self):
        assert derive.NOMINAL_PERCENTILE == 0.90

    @pytest.mark.parametrize("stage", sorted(STAGE_NOMINAL_SECONDS))
    def test_each_shipped_value_is_the_corpus_p90(self, stage):
        """The table is a transcription of a measurement. If it stops matching,
        someone hand-edited it -- which is what #2323 was filed about."""
        assert STAGE_NOMINAL_SECONDS[stage] == pytest.approx(CORPUS[stage][3])

    def test_the_percentile_helper_is_the_one_that_produced_them(self):
        values = sorted(v for v in [1.0, 2.0, 3.0, 4.0, 10.0])
        assert derive.percentile(values, 0.90) == 10.0
        assert derive.percentile(values, 0.50) == 3.0

    def test_an_under_sampled_stage_is_omitted_by_the_tool(self, tmp_path, capsys):
        runs = tmp_path / "runs"
        runs.mkdir()
        (runs / "run-1.log").write_text(
            "lld       passed     100.0s  /tmp/a\n"
            "lld       passed     200.0s  /tmp/b\n",
            encoding="utf-8",
        )
        derive.main(["--runs", str(runs)])
        out = capsys.readouterr().out
        assert "only 2 passing sample(s)" in out
        # The COMMENTED form carries the name too, so the check must be for an
        # emitted entry -- an indented, uncommented `"lld":`.
        emitted = out.split("STAGE_NOMINAL_SECONDS")[-1]
        assert '\n    "lld":' not in emitted, emitted
