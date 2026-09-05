"""Infrastructure a run walked away from is counted (#2810).

`factory_report`'s cause table answers one question: what killed this run.
An infrastructure failure a run SURVIVES therefore leaves no trace anywhere
— and a run can spend its entire retry allowance on one, recover, and die
later of something unrelated.

`run-issue41-184913` is the exhibit. Three of three edit-script attempts
failed with `drafter call failed: All credentials failed via agy`; the run
continued, drew a fresh revision, and died two hundred lines later for a
different reason. The report attributed it correctly and said nothing about
the budget that had already been spent before the work began.

**Deliberately not a cause row.** Putting a non-death in the deaths table
would move a distribution nobody decided to move, so this is its own
section and `test_no_cause_of_death_count_moves` pins that.
"""

from __future__ import annotations

from assemblyzero.speedrun.factory_report import (
    SURVIVED_UNCLASSIFIED,
    RunLogFacts,
    _survived_index,
    classify_survived,
)

CREDENTIALS = "drafter call failed: All credentials failed via agy (Antigravity CLI"


def _facts(run_id: str, events) -> RunLogFacts:
    return RunLogFacts(
        run_id=run_id, issue=41, path=f"{run_id}.log", mtime="x",
        survived_events=list(events),
    )


class TestClassification:
    def test_a_credentials_failure_is_infrastructure(self):
        assert classify_survived(CREDENTIALS) == "infra.drafter_unreachable"

    def test_an_unknown_reason_is_named_not_absorbed(self):
        """The cause table's own rule: never the nearest bucket."""
        assert classify_survived("something nobody has seen") == (
            SURVIVED_UNCLASSIFIED
        )

    def test_an_empty_reason_is_still_classified_rather_than_dropped(self):
        assert classify_survived("") == SURVIVED_UNCLASSIFIED


class TestTheIndex:
    def test_it_groups_by_key_and_names_the_run_and_the_attempt(self):
        index = _survived_index([
            _facts("run-a", [("infra.drafter_unreachable", CREDENTIALS, 1, 3)]),
            _facts("run-b", [
                ("infra.drafter_unreachable", CREDENTIALS, 1, 3),
                ("infra.drafter_unreachable", CREDENTIALS, 2, 3),
            ]),
        ])
        assert list(index) == ["infra.drafter_unreachable"]
        entries = index["infra.drafter_unreachable"]
        assert len(entries) == 3
        assert entries[0].startswith("run-a: attempt 1/3 -- ")
        assert any("run-b: attempt 2/3" in e for e in entries)

    def test_a_run_that_survived_nothing_contributes_nothing(self):
        assert _survived_index([_facts("clean", [])]) == {}

    def test_the_whole_allowance_being_spent_is_visible(self):
        """The finding this exists for: 3 of 3, and the run lived.

        A reader sizing that cap needs to see its most expensive customer,
        and no cause row will ever show it.
        """
        index = _survived_index([
            _facts("run-issue41-184913", [
                ("infra.drafter_unreachable", CREDENTIALS, n, 3)
                for n in (1, 2, 3)
            ]),
        ])
        entries = index["infra.drafter_unreachable"]
        assert len(entries) == 3
        assert entries[-1].endswith(CREDENTIALS)
        assert "attempt 3/3" in entries[-1]


class TestItStaysOutOfTheDeathsTable:
    def test_survived_events_are_not_a_cause_and_have_no_row(self):
        """A survived event must never acquire a `Cause` row: the cause
        table is about deaths, and this run did not die of it."""
        from assemblyzero.speedrun.factory_report import CAUSE_TABLE

        keys = {c.key for c in CAUSE_TABLE}
        assert "infra.drafter_unreachable" not in keys
        assert SURVIVED_UNCLASSIFIED not in keys

    def test_the_parser_field_defaults_empty(self):
        """So a log with no such line is indistinguishable from before."""
        assert RunLogFacts(
            run_id="x", issue=None, path="x", mtime="x",
        ).survived_events == []
