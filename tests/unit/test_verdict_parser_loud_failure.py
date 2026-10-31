"""The requirements verdict parser under standard 0034 (#3585).

Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md (base ``79e18ad1``), for
``assemblyzero/workflows/requirements/parsers/verdict_parser.py``. An empty
verdict and a verdict whose status cannot be read raise, where they read as
UNKNOWN and the approved draft silently kept its unresolved open questions.
"""
from __future__ import annotations

import pytest

from assemblyzero.workflows.requirements.parsers import verdict_parser


def test_76_an_empty_verdict_raises():
    with pytest.raises(ValueError, match="empty"):
        verdict_parser.parse_verdict("")


def test_135_a_status_that_cannot_be_read_raises():
    with pytest.raises(ValueError, match="status") as raised:
        verdict_parser.parse_verdict("The reviewer had some thoughts about section 4.")
    assert "section 4" in str(raised.value)


def test_a_readable_status_is_returned():
    """Kept: the audit-trail form the review node writes."""
    approved = verdict_parser.parse_verdict("Verdict: APPROVED\n\nRationale: ok\n")
    assert approved.verdict_status == "APPROVED"
    assert verdict_parser.parse_verdict("Verdict: REVISE\n").verdict_status == "BLOCKED"
