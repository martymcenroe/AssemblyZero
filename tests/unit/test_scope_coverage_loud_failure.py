"""Scope coverage under standard 0034 (#3585).

Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md (base ``79e18ad1``), for
``assemblyzero/workflows/requirements/scope_coverage.py``. A vacuous report (no
scope elements, or no criteria table) is no longer ``ok``. Refusing the launch
on it is a won't-do: the operator's 2026-08-12 ruling keeps an unconverted
prose issue from ever refusing, and no issue in the fleet declares a scope
alias yet; ``form_gate`` prints the NOT CHECKED disclosure, pinned below. A
declared alias whose row IDs the table does not carry is now a violation; the
element used to count as disposed.
"""
from __future__ import annotations

from assemblyzero.workflows.requirements import form_gate
from assemblyzero.workflows.requirements.scope_coverage import check_scope_coverage

TITLE = "feat: static face -- bezel, dial, ticks"

TABLE = (
    "| ID | Element | Binding value | Assertion method |\n"
    "|---|---|---|---|\n"
    "| S1 | Dial | flat `#0A0A0C` | classification at 3 points |\n"
    "| S3 | Ticks | `#FFFFFF`, 11 total | stroke predicate |\n"
)


def test_467_a_vacuous_report_is_not_ok():
    report = check_scope_coverage("fix: a typo", "Some prose with no table.\n")
    assert report.vacuous
    assert report.ok is False
    assert "NOT CHECKED" in report.disclosure()


def test_467_a_vacuous_scope_still_does_not_refuse_the_launch(tmp_path, operator_alerts):
    """WON'T DO, pinned: report-only, per the operator's 2026-08-12 ruling."""
    def fetch(_r, _i):
        return ("fix: a typo", "Some prose with no table.\n")

    text, refuse = form_gate.check_form_at_preflight(tmp_path, [7], fetch)
    assert refuse is False
    assert "scope coverage: NOT CHECKED" in text
    assert operator_alerts == []


def test_476_an_alias_naming_a_row_the_table_lacks_is_a_violation():
    body = TABLE + "\n<!-- scope-alias: bezel -> S9 -->\n"
    report = check_scope_coverage(TITLE, body)
    dangling = [v for v in report.violations if v.kind == "scope-alias-unknown-row"]
    assert dangling, report.violations
    assert "S9" in str(dangling[0])
    assert "bezel" not in report.aliased


def test_an_alias_naming_existing_rows_disposes_the_element():
    """Kept: an alias the table can honour."""
    body = TABLE + "\n<!-- scope-alias: bezel -> S1, S3 -->\n"
    report = check_scope_coverage(TITLE, body)
    assert report.aliased.get("bezel") == "S1, S3"
    assert [v for v in report.violations if v.kind == "scope-alias-unknown-row"] == []
