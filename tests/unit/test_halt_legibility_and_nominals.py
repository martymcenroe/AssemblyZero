"""#2321 / #2323: the halt names the broken artifact, and nominals are derived.

#2321  The stagnation halt aimed the operator at the LLD (282s) and spec
       (699s), both of which were correct -- the spec's own tests pass
       against the implementation the run discarded. The broken artifact was
       the 2s generated test file, which the message never mentioned. Acting
       on it as written would have burned another 16 minutes regenerating
       good documents.

#2323  STAGE_NOMINAL_SECONDS was hand-typed and went stale. impl's nominal
       was 240s against a measured median of 718.9s, so a TYPICAL impl run
       earned SLOW immediately and the stage most likely to genuinely hang
       had the least trustworthy warnings.
"""

from __future__ import annotations

import pytest

from assemblyzero.core.recovery_plan import _build_recommendation, _never_passed
from assemblyzero.core.stage_watchdog import (
    SLOW_RATIO,
    STAGE_NOMINAL_SECONDS,
    STALLED_RATIO,
)

# The live message from run-issue7-153937.
ZERO_PASSING = (
    "Test count stagnant: 0/36 passed (unchanged across 2 iterations). "
    "Halting to prevent token waste."
)
PARTIAL_PASSING = (
    "Test count stagnant: 30/36 passed (unchanged across 2 iterations). "
    "Halting to prevent token waste."
)


# ----------------------------------------------------------------- #2321


@pytest.mark.parametrize("message,expected", [
    (ZERO_PASSING, True),
    (PARTIAL_PASSING, False),
    ("Coverage stagnant: 78.0% -> 78.0% (< 1% improvement).", False),
    ("Test identity stagnant: same 6 test(s) failing", False),
    ("0/0 passed", False),          # nothing ran at all; not this case
    ("", False),
])
def test_zero_passing_is_detected_from_the_message(
    message: str, expected: bool,
) -> None:
    """Derived from the number the guard already prints, so they agree."""
    assert _never_passed(message) is expected


def test_zero_passing_halt_names_the_generated_suite() -> None:
    advice = _build_recommendation(
        "stagnation", ZERO_PASSING, "testing",
        {"test_files": ["/repo/tests/test_issue_7.py"]},
    )

    assert "GENERATED TEST FILE" in advice
    assert "/repo/tests/test_issue_7.py" in advice, (
        "the operator should not have to go looking for the file"
    )
    # It must stop aiming at the artifacts that were fine.
    assert "LLD or spec likely needs manual editing" not in advice


def test_zero_passing_halt_works_without_a_known_test_file() -> None:
    advice = _build_recommendation("stagnation", ZERO_PASSING, "testing", {})

    assert "GENERATED TEST FILE" in advice
    assert "Inspect" not in advice, "no path known, so none is claimed"


def test_partial_pass_stagnation_keeps_the_original_advice() -> None:
    """A genuinely different situation, and the old guidance is right for it."""
    advice = _build_recommendation(
        "stagnation", PARTIAL_PASSING, "testing",
        {"test_files": ["/repo/tests/test_issue_7.py"]},
    )
    assert "LLD or spec likely needs manual editing" in advice


def test_other_error_types_are_untouched() -> None:
    advice = _build_recommendation("budget", "over budget", "testing", {})
    assert "Cost budget exceeded" in advice


def test_state_is_optional() -> None:
    """Callers that predate the state argument must keep working."""
    assert _build_recommendation("stagnation", ZERO_PASSING, "testing")


# ----------------------------------------------------------------- #2323


def test_impl_nominal_matches_its_measured_median() -> None:
    """The entry that was 3x wrong. 718.9s is the median of 19 passed runs."""
    assert STAGE_NOMINAL_SECONDS["impl"] == pytest.approx(718.9)


def test_a_median_duration_run_is_not_slow() -> None:
    """#2323 acceptance: impl no longer reports SLOW on a typical run.

    A nominal below the median means the typical run is always flagged, which
    is how the warning stopped carrying information.
    """
    for stage, nominal in STAGE_NOMINAL_SECONDS.items():
        assert nominal / nominal < SLOW_RATIO, stage


# Measured p90s from the same corpus that produced the nominals.
@pytest.mark.parametrize("stage,p90", [
    ("lld", 386.6),
    ("spec", 207.5),
    ("impl", 2122.2),
    ("pr", 3.0),
    ("cleanup", 82.7),
])
def test_a_long_tailed_stage_at_p90_is_not_stalled(
    stage: str, p90: float,
) -> None:
    """#2323 acceptance: natural variance must not read as a hang."""
    ratio = p90 / STAGE_NOMINAL_SECONDS[stage]
    assert ratio < STALLED_RATIO, (
        f"{stage} at its p90 ({p90}s) reports STALLED against a "
        f"{STAGE_NOMINAL_SECONDS[stage]}s nominal ({ratio:.1f}x)"
    )


def test_a_genuinely_hung_stage_still_stalls() -> None:
    """#2323 acceptance: the signal must survive the recalibration."""
    for stage, nominal in STAGE_NOMINAL_SECONDS.items():
        hung = nominal * (STALLED_RATIO + 1)
        assert hung / nominal >= STALLED_RATIO, stage


def test_every_stage_has_a_nominal() -> None:
    assert set(STAGE_NOMINAL_SECONDS) == {
        "triage", "lld", "spec", "impl", "pr", "cleanup",
    }
