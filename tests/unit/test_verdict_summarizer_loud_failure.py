"""The verdict summarizer under standard 0034 (#3585).

Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md (base ``79e18ad1``), for
``assemblyzero/workflows/requirements/verdict_summarizer.py``. A JSON verdict
that is malformed, or lacks the ``blocking_issues`` its reader needs, raises
naming what is wrong, where it summarised as "0 issues" or fell back to
reading the JSON as prose. The text status is read from an explicit verdict
line only: "NOT APPROVED" is no longer APPROVED. A history entry with no
verdict line (the review node stores actionable feedback, #506) still reads as
UNKNOWN; raising there would stop every revision, so that half of the ledger's
fix is a won't-do, pinned below.
"""
from __future__ import annotations

import logging

import pytest

from assemblyzero.workflows.requirements import verdict_summarizer as vs

LOGGER = "assemblyzero.workflows.requirements.verdict_summarizer"


class TestJsonBlockingIssues:
    def test_64_a_json_verdict_without_blocking_issues_raises(self):
        with pytest.raises(ValueError, match="blocking_issues"):
            vs.extract_blocking_issues('{"verdict": "BLOCKED"}')

    def test_64_blocking_issues_that_is_not_a_list_raises(self):
        with pytest.raises(ValueError, match="not a list"):
            vs.extract_blocking_issues('{"verdict": "BLOCKED", "blocking_issues": "two"}')

    def test_64_an_item_without_a_description_raises(self):
        with pytest.raises(ValueError, match="description") as raised:
            vs.extract_blocking_issues(
                '{"verdict": "BLOCKED", "blocking_issues": [{"issue": "no rollback"}]}'
            )
        assert "item 0" in str(raised.value)

    def test_66_text_that_starts_like_json_and_is_not_raises(self, caplog):
        malformed = '{invalid json\n- **[BLOCKING]** Fallback issue found'
        with caplog.at_level(logging.ERROR, logger=LOGGER), pytest.raises(
            ValueError, match="not valid JSON"
        ):
            vs.extract_blocking_issues(malformed)
        assert any(r.levelno == logging.ERROR for r in caplog.records)

    def test_a_json_verdict_with_its_issues_is_read(self):
        """Kept: the documented JSON shape."""
        text = '{"verdict": "BLOCKED", "blocking_issues": [{"description": "no rollback"}]}'
        assert vs.extract_blocking_issues(text) == ["no rollback"]


class TestStatus:
    def test_105_a_malformed_json_status_raises(self):
        with pytest.raises(ValueError, match="not valid JSON"):
            vs.summarize_verdict('{"verdict": "BLOCKED", ', iteration=1)

    def test_109_not_approved_is_not_approved(self):
        text = "- The schema section is NOT APPROVED until the keys are named"
        assert vs.summarize_verdict(text, iteration=1).verdict == "UNKNOWN"

    def test_109_the_explicit_verdict_line_decides(self):
        blocked = "## Verdict: BLOCKED\n\n- **[BLOCKING]** previously approved design reverted"
        assert vs.summarize_verdict(blocked, iteration=1).verdict == "BLOCKED"
        approved = "**Verdict:** APPROVED\n\nNothing blocking."
        assert vs.summarize_verdict(approved, iteration=1).verdict == "APPROVED"
        boxed = "Verdict: [x] APPROVED"
        assert vs.summarize_verdict(boxed, iteration=1).verdict == "APPROVED"

    def test_109_feedback_with_no_verdict_line_is_unknown_not_an_error(self):
        """WON'T DO, pinned: the review node stores actionable feedback in the
        history (#506), usually a bullet list with no verdict line. Raising
        here would stop every revision; UNKNOWN is what the entry says."""
        text = "- Section 2.1 omits the cache module\n- The test plan lacks a timeout case"
        summary = vs.summarize_verdict(text, iteration=2, prior_issues=[])
        assert summary.verdict == "UNKNOWN"

    def test_an_empty_entry_is_unknown_and_empty(self):
        """Kept: an empty history entry carries nothing to read."""
        assert vs.summarize_verdict("", iteration=1).verdict == "UNKNOWN"
        assert vs.extract_blocking_issues("") == []
