"""The non-discriminating-test class, made unwritable (#2387).

The semantic gate found this class FOUR times across six samples of boostgauge
#2 and #7, at roughly a five-minute model call per round. Rounds went 3, 3, 1,
2, 1, 1 findings and the tail is entirely this class.

Every fixture below is the real text. The pre-repair criteria are reconstructed
from the gate's own verbatim findings and the issue's revision history (the
acceptance asks for exactly that); the post-repair criteria are copied from
boostgauge #2 as it stands today, so "a criterion with per-branch non-default
coverage passes" is tested against text that a human already accepted rather
than against text written to satisfy this checker.
"""

from __future__ import annotations

import pytest

from assemblyzero.workflows.requirements.discrimination_check import (
    check_discrimination,
    has_non_default_case,
    is_absence_only,
    is_default_anchored,
    pins_a_value,
)


def _doc(*criteria: str) -> str:
    lines = ["# Issue", "", "## Acceptance Criteria", ""]
    lines += [f"- [ ] {c}" for c in criteria]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Instance 1 -- boostgauge #308, the U1 tooltip surface
# ---------------------------------------------------------------------------

U1_BEFORE = (
    "U1 — Hovering the gauge shows a tooltip identifying each window, one line "
    "per window in the form '<window label> — <color name>'. The identification "
    "text comes from a pure function that unit tests call directly against the "
    "four expected strings at default config ('1m — cyan', '10m — orange', "
    "'1h — magenta', 'All-time — coral red'); no `tkinter` in tests, per "
    "strategy 0001."
)

U1_AFTER = (
    "U1 — Hovering the gauge shows a tooltip identifying each window, one line "
    "per window in the form '<window label> — <color name>'. The identification "
    "text comes from a pure function that unit tests call directly against the "
    "four expected strings at default config ('1m — cyan', '10m — orange', "
    "'1h — magenta', 'All-time — coral red') AND against a non-default "
    "configuration for EACH configured window, covering every formatter branch "
    "— short at 90 seconds must read '90s — cyan', medium at 900 seconds must "
    "read '15m — orange', long at 7200 seconds must read '2h — magenta' — so a "
    "formatter that hardcodes any window's label fails while the one pure "
    "formatter passes."
)


class TestInstanceOneTooltipSurface:
    """'The U1 test plan checks only the four default-config strings; at those
    exact values a hardcoded implementation and a genuine dynamic formatter
    produce identical output.' -- the gate, boostgauge #308."""

    def test_the_pre_repair_criterion_is_flagged(self):
        report = check_discrimination(_doc(U1_BEFORE))
        assert not report.ok
        assert report.violations[0].where == "U1"
        assert report.violations[0].kind == "non-discriminating"

    def test_the_finding_says_why(self):
        report = check_discrimination(_doc(U1_BEFORE))
        assert "hardcodes the default" in report.violations[0].detail

    def test_the_repaired_criterion_passes(self):
        report = check_discrimination(_doc(U1_AFTER))
        assert report.ok, [str(v) for v in report.violations]


# ---------------------------------------------------------------------------
# Instances 2 and 3 -- the RS menu surface, rounds 5 and 6 on boostgauge #2
# ---------------------------------------------------------------------------

RS_BEFORE = (
    "RS1 — The short-window menu entry, labelled 'Reset 1m' at default config, "
    "calls `reset()` on the short-window instance; the remaining three are "
    "untouched."
)

RS6_AFTER = (
    "RS6 — The menu entry labels come from the same pure formatter as the "
    "tooltip lines, asserted at a non-default value for EVERY configured "
    "window, covering every branch on the menu surface: short at 90 seconds "
    "reads 'Reset 90s', medium at 900 seconds reads 'Reset 15m', long at 7200 "
    "seconds reads 'Reset 2h' — so a hardcoded label for any window fails "
    "where the one formatter passes."
)


class TestInstancesTwoAndThreeMenuSurface:
    """Round 5: 'the RS menu-entry labels were stated as literals and tested
    only at default config — the same coincidence-point escape U1 just closed
    for tooltip lines.' Round 6 extended it to every window."""

    def test_the_pre_repair_menu_criterion_is_flagged(self):
        report = check_discrimination(_doc(RS_BEFORE))
        assert not report.ok
        assert report.violations[0].where == "RS1"

    def test_the_repaired_menu_criterion_passes(self):
        report = check_discrimination(_doc(RS6_AFTER))
        assert report.ok, [str(v) for v in report.violations]

    def test_both_surfaces_are_flagged_when_both_are_bad(self):
        """The class recurred BECAUSE closing it on one surface left the
        other open. The check must not have the same blind spot."""
        report = check_discrimination(_doc(U1_BEFORE, RS_BEFORE))
        assert len(report.violations) == 2
        assert {v.where for v in report.violations} == {"U1", "RS1"}


# ---------------------------------------------------------------------------
# Instance 4 -- boostgauge #300, the absence-only oracle
# ---------------------------------------------------------------------------

S3_BEFORE = (
    "S3 — Size, no reset, `--size` given, not resized, no direct edits: the "
    "file's `size` key remains '300' and the CLI value '500' is not written."
)

S3_AFTER = (
    "S3 — Size, no reset, `--size` given, not resized, no direct edits: the "
    "window opens at '500', while the file's `size` key remains '300' and the "
    "CLI value is not written."
)


class TestInstanceFourAbsenceOnlyOracle:
    """'S3 passes identically under both readings -- it checks only that the
    file's `size` key remains 300 and that 500 is not written, which is equally
    true whether the window displayed 500 or 300.' -- the gate, boostgauge #300."""

    def test_the_absence_only_criterion_is_flagged(self):
        report = check_discrimination(_doc(S3_BEFORE))
        assert not report.ok
        assert report.violations[0].kind == "absence-only-oracle"

    def test_the_finding_says_why(self):
        report = check_discrimination(_doc(S3_BEFORE))
        assert "ignores the input entirely" in report.violations[0].detail

    def test_adding_a_positive_observation_passes(self):
        report = check_discrimination(_doc(S3_AFTER))
        assert report.ok, [str(v) for v in report.violations]


# ---------------------------------------------------------------------------
# All four together -- the acceptance's first item
# ---------------------------------------------------------------------------


class TestAllFourHistoricalInstances:
    def test_every_one_is_flagged_in_a_single_free_pass(self):
        """'A deterministic check would have named all of them in one free
        pass.' Six gate rounds, ~5 minutes of model call each; this is the
        claim, tested."""
        report = check_discrimination(_doc(U1_BEFORE, RS_BEFORE, S3_BEFORE))
        assert len(report.violations) == 3
        kinds = {v.kind for v in report.violations}
        assert kinds == {"non-discriminating", "absence-only-oracle"}

    def test_every_repair_passes(self):
        report = check_discrimination(_doc(U1_AFTER, RS6_AFTER, S3_AFTER))
        assert report.ok, [str(v) for v in report.violations]


# ---------------------------------------------------------------------------
# The vacuous state is disclosed, never silently passed (#2227 ruling)
# ---------------------------------------------------------------------------


class TestTheVacuousStateIsDisclosed:
    def test_no_criteria_section_is_reported_as_not_checked(self):
        report = check_discrimination("# Issue\n\nSome prose.\n")
        assert report.criteria_section_found is False
        assert "NOT CHECKED" in report.disclosure()

    def test_criteria_that_pin_no_values_are_reported_as_nothing_to_check(self):
        report = check_discrimination(
            _doc("W1 — Four instances are constructed from config.")
        )
        assert report.vacuous is True
        assert report.ok is True
        assert "nothing to check" in report.disclosure()

    def test_a_clean_document_says_it_checked_and_found_none(self):
        """'checked and found nothing to check' and 'checked and found none'
        are different facts and must print differently."""
        report = check_discrimination(_doc(U1_AFTER))
        assert report.vacuous is False
        assert report.ok is True
        disclosure = report.disclosure()
        assert "0 finding(s)" in disclosure
        assert "nothing to check" not in disclosure

    def test_the_disclosure_counts_what_it_judged(self):
        report = check_discrimination(_doc(U1_AFTER, RS6_AFTER))
        assert "2 of 2 criterion(s) pin expected values" in report.disclosure()


# ---------------------------------------------------------------------------
# Narrowness -- the check must not cry wolf
# ---------------------------------------------------------------------------


class TestItDoesNotCryWolf:
    """This session already had to retract one audit for reporting seven
    suspects of which zero were real. Each rule fires on positive evidence
    only."""

    def test_a_criterion_with_no_literals_is_out_of_scope(self):
        report = check_discrimination(
            _doc("W2 — Every collector sample reaches all four instances.")
        )
        assert report.ok

    def test_a_criterion_pinning_values_without_a_default_anchor_is_not_flagged(self):
        """No claim that these are default-config values, so there is no
        evidence of a coincidence point. Silence is the honest answer."""
        report = check_discrimination(
            _doc("W1 — Four instances are constructed with windows '60', "
                 "'600', '3600' and `None`.")
        )
        assert report.ok

    def test_a_no_change_assertion_beside_a_positive_one_is_fine(self):
        """No-change assertions are legitimate. Only a criterion made of
        NOTHING else has no oracle."""
        report = check_discrimination(
            _doc("RS1 — The entry calls `reset()` on the short-window "
                 "instance; the remaining three are 'untouched'.")
        )
        assert report.ok

    def test_a_family_is_covered_by_any_of_its_members(self):
        """The false positive that mattered most, pinned.

        Measured against boostgauge #2 as a human left it after seven gate
        rounds: a per-criterion rule flagged RS1, RS2 and RS3 -- each pins only
        its own default-config label -- while RS6, in the same family, carries
        the non-default case for every window on that surface. Three findings,
        all false. Coverage is judged per family for this reason.
        """
        report = check_discrimination(_doc(RS_BEFORE, RS6_AFTER))
        assert report.ok, [str(v) for v in report.violations]

    def test_a_sibling_in_a_DIFFERENT_family_does_not_rescue_it(self):
        """The family rule must not become 'one non-default case anywhere'.
        The class recurred precisely because closing it on the tooltip surface
        left the menu surface open."""
        report = check_discrimination(_doc(U1_BEFORE, RS6_AFTER))
        assert len(report.violations) == 1
        assert report.violations[0].where == "U1"

    def test_a_symbolic_placeholder_counts_as_a_discriminating_case(self):
        """boostgauge #7's L4 states its case as `--size N` rather than a
        number. A placeholder standing for any value is a stronger claim than
        one number, not a weaker one -- a literal-only rule flagged it."""
        report = check_discrimination(_doc(
            "L4 — Launched with `--reset-config` and no `--size`, the window "
            "opens at the default position and default size; launched with "
            "`--reset-config --size N`, it opens at the default position and "
            "size N."
        ))
        assert report.ok, [str(v) for v in report.violations]

    def test_an_absence_only_criterion_with_no_supplied_input_is_fine(self):
        """boostgauge #7's P1 and S1. Nothing was supplied, so there is
        nothing an implementation could be ignoring."""
        report = check_discrimination(_doc(
            "P1 — Position, no reset, not moved, no direct edits: `position` "
            "unchanged",
            "S1 — Size, no reset, no `--size`, not resized, no direct edits: "
            "`size` unchanged",
        ))
        assert report.ok, [str(v) for v in report.violations]

    def test_the_real_repaired_issue_body_is_clean(self):
        """The strongest anti-noise evidence available: boostgauge #2's whole
        Acceptance Criteria section as a human left it after seven gate rounds.
        A checker that fires on this is a checker nobody will keep."""
        report = check_discrimination(_doc(
            "W1 — Four `Telltale` instances are constructed: three with "
            "durations read from `telltale_windows.short`, "
            "`telltale_windows.medium`, `telltale_windows.long` (defaults 60, "
            "600, 3600 seconds), one with window `None` for all-time.",
            "W2 — Every collector sample reaches all four instances via "
            "`Telltale.update(timestamp, value)`.",
            RS6_AFTER,
            U1_AFTER,
        ))
        assert report.ok, [str(v) for v in report.violations]


# ---------------------------------------------------------------------------
# The predicates, directly
# ---------------------------------------------------------------------------


class TestThePredicates:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("reads 'Reset 1m' at default config", True),
            ("at the default config the labels read '1m'", True),
            ("the default config renders exactly '1m'", True),
            ("checked against the 'default-config' strings", True),
            ("reads '90s' when configured to 90 seconds", False),
        ],
    )
    def test_default_anchor_detection(self, text, expected):
        assert is_default_anchored(text) is expected

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("AND against a non-default configuration", True),
            ("short at 90 seconds reads 'Reset 90s'", True),
            ("medium at 900 seconds reads '15m'", True),
            ("adds the discriminating case", True),
            ("only the four default strings", False),
        ],
    )
    def test_non_default_case_detection(self, text, expected):
        assert has_non_default_case(text) is expected

    @pytest.mark.parametrize(
        "text,expected",
        [
            # An input IS supplied and only its non-effect is asserted.
            ("`--size` given: the key remains '300' and '500' is not written", True),
            ("with --size supplied, the file is 'unchanged'", True),
            # A positive observation rescues it.
            ("`--size` given: the window opens at '500', file unchanged", False),
            ("`--size` given: `size` holds the default", False),
            # NOTHING is supplied, so "unchanged" is the whole truth. Flagging
            # these is what a first cut did, on boostgauge #7's P1 and S1.
            ("no reset, not moved, no direct edits: `position` unchanged", False),
            ("no `--size`, not resized: `size` unchanged", False),
            ("the entry calls `reset()`; the rest are untouched", False),
        ],
    )
    def test_absence_only_detection(self, text, expected):
        assert is_absence_only(text) is expected

    def test_pins_a_value_needs_a_literal(self):
        assert pins_a_value("reads '90s'") is True
        assert pins_a_value("reads the configured label") is False
