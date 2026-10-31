"""The ADR 0226 form check under standard 0034 (#3585).

Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md (base ``79e18ad1``), for
``assemblyzero/workflows/requirements/form_check.py``. With no
``## Requirements`` section the EARS check cannot run, and that is now a
violation, where ``report.ok`` stayed True. A run that examined nothing of a
part of the form renders ``RESULT: NOT CHECKED``, a failing verdict, where it
rendered PASS.
"""
from __future__ import annotations

from assemblyzero.workflows.requirements import form_check as fc

CHECKED = (
    "## Requirements\n\n"
    "- The system shall persist the window size on exit.\n\n"
    "## Variables\n\n"
    "| Variable | Extension | Owner |\n"
    "|---|---|---|\n"
    "| `size` | the `size` key | `E` (the exit-write criteria) |\n\n"
    "## Acceptance Criteria\n\n"
    "- [ ] E1. Quitting writes `size` to the config file\n"
)


def test_388_no_requirements_section_is_not_checked():
    """Fixed by the NOT CHECKED verdict; WON'T DO as a violation, which would
    fail the fleet's one converted issue (boostgauge #7 has no Requirements
    section and is ruled correct)."""
    report = fc.check_form("## Acceptance Criteria\n\n- [ ] A1. it works\n")
    assert report.ears_ran is False
    assert any(part.startswith("EARS") for part in report.not_checked)
    verdict = next(
        line for line in fc.render_report(report, "#7").splitlines()
        if line.startswith("RESULT:")
    )
    assert verdict.startswith("RESULT: NOT CHECKED")
    assert "EARS (no '## Requirements' section)" in verdict


def test_821_a_vacuous_run_renders_not_checked():
    body = CHECKED.split("## Variables")[0] + (
        "## Acceptance Criteria\n\n- [ ] E1. Quitting writes `size`\n"
    )
    report = fc.check_form(body)
    assert report.violations == []
    assert report.not_checked
    text = fc.render_report(report, "#7")
    assert "RESULT: NOT CHECKED" in text
    assert "RESULT: PASS" not in text


def test_a_fully_checked_clean_issue_passes():
    """Kept: a verdict that can still pass."""
    report = fc.check_form(CHECKED)
    assert report.violations == [], report.violations
    assert report.not_checked == []
    assert "RESULT: PASS" in fc.render_report(report, "#7")
