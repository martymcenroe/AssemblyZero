"""Discrimination coverage under standard 0034 (#3585).

Named for its ledger line in docs/audits/0908-loud-failure-sweep-ledger.md
(base ``79e18ad1``), for
``assemblyzero/workflows/requirements/discrimination_check.py``. With no
Acceptance Criteria section nothing is judged, and the report is no longer
``ok``: only its disclosure used to say NOT CHECKED.
"""
from __future__ import annotations

from assemblyzero.workflows.requirements.discrimination_check import (
    check_discrimination,
)


def test_278_no_acceptance_criteria_section_is_not_ok():
    report = check_discrimination("# Feature\n\nJust prose, no criteria.\n")
    assert report.criteria_section_found is False
    assert report.ok is False
    assert "NOT CHECKED" in report.disclosure()


def test_a_section_with_nothing_wrong_is_ok():
    """Kept: a judged document with no finding passes."""
    body = (
        "## Acceptance Criteria\n\n"
        "- [ ] A1. `--size 40` renders a dial of radius `16`\n"
    )
    assert check_discrimination(body).ok is True
