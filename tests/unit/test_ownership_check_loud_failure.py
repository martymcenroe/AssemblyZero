"""The ADR 0228 ownership check under standard 0034 (#3585).

Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md (base ``79e18ad1``), for
``assemblyzero/workflows/requirements/ownership_check.py``. An owner row with
no group tag, in a table whose other rows carry one, is now a table-form
violation; the criteria asserting its keys used to be skipped as "already
reported" when nothing had reported them. No variable table, and a table whose
owners are all named in prose, leave the per-criterion clauses unrun: the form
verdict is NOT CHECKED, a failing verdict, where it read PASS.
"""
from __future__ import annotations

from assemblyzero.workflows.requirements import form_check as fc

REQUIREMENTS = (
    "## Requirements\n\n"
    "- WHILE the app is running the app shall re-read the config file.\n\n"
)

CRITERIA = (
    "## Acceptance Criteria\n\n"
    "- [ ] R1. The app re-reads `thresholds` during the session\n"
    "- [ ] E1. Quitting writes `theme` back to the config file\n"
)


def _body(table: str) -> str:
    return "# Config persistence\n\n" + REQUIREMENTS + table + CRITERIA


TAGGED = (
    "## Variables\n\n"
    "| Variable | Extension | Owner |\n"
    "|---|---|---|\n"
    "| `thresholds` | every key under `thresholds` | `R` (the live re-read criteria) |\n"
    "| `theme` | the `theme` key | `E` (the exit-write criteria) |\n\n"
)

ONE_UNTAGGED = TAGGED.replace("`E` (the exit-write criteria)", "the exit-write criteria")

ALL_PROSE = ONE_UNTAGGED.replace("`R` (the live re-read criteria)", "the live re-read criteria")


def test_459_an_untagged_owner_row_in_a_joinable_table_is_a_violation():
    report = fc.check_form(_body(ONE_UNTAGGED))
    found = [str(v) for v in report.violations if v.kind == "ownership-table"]
    assert any("theme" in v and "group" in v for v in found), found


def test_a_fully_tagged_table_reports_no_table_violation():
    """Kept: the clean case the check must be able to pass."""
    report = fc.check_form(_body(TAGGED))
    assert [v for v in report.violations if v.kind == "ownership-table"] == []
    assert report.ownership.ran


def test_611_no_variable_table_is_not_checked_and_fails():
    report = fc.check_form(_body(""))
    assert not report.ownership.table_found
    assert any("no variable table" in part for part in report.not_checked)
    text = fc.render_report(report, "#7")
    assert "RESULT: NOT CHECKED" in text
    assert "RESULT: PASS" not in text


def test_627_owners_named_in_prose_is_not_checked_and_fails():
    report = fc.check_form(_body(ALL_PROSE))
    assert report.ownership.table_found and not report.ownership.joinable
    assert any("named in prose" in part for part in report.not_checked)
    text = fc.render_report(report, "#7")
    assert "RESULT: NOT CHECKED" in text
    assert "RESULT: PASS" not in text
