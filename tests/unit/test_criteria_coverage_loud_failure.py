"""criteria_coverage under standard 0034 (#3585).

Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md. A criterion the check cannot
read is a failure, never a row quietly left out of the count, and a check that
cannot run is never ``ok``: its caller used to pass the gate on it.
"""
from __future__ import annotations

import pytest

from assemblyzero.workflows.implementation_spec import criteria_coverage as cc

HEADER = "### 10.1 Test Scenarios\n\n| ID | Scenario | Type | Pass Criteria |\n|---|---|---|---|\n"
SPEC = "```python\ndef test_one():\n    \"\"\"REQ-1: covered.\"\"\"\n```\n"


class TestRowsAreNeverDropped:
    def test_171_a_row_with_the_wrong_cell_count_raises(self):
        lld = HEADER + "| 010 | REQ-1 one | Auto | ok |\n| 020 | REQ-2 two | Auto |\n"
        with pytest.raises(cc.CriteriaTableError) as caught:
            cc.lld_criteria(lld)
        message = str(caught.value)
        assert "020" in message and "3 cell(s)" in message and "4" in message

    def test_180_a_row_with_no_tag_and_no_id_raises(self):
        lld = HEADER + "| 010 | REQ-1 one | Auto | ok |\n|  | a scenario nobody can name | Auto | ok |\n"
        with pytest.raises(cc.CriteriaTableError, match="a scenario nobody can name"):
            cc.lld_criteria(lld)

    def test_a_blank_row_is_not_a_criterion(self):
        """Kept: a row with no content at all states nothing to cover."""
        lld = HEADER + "| 010 | REQ-1 one | Auto | ok |\n|  |  |  |  |\n"
        assert [c.key for c in cc.lld_criteria(lld)] == ["REQ-1"]

    def test_criteria_coverage_raises_on_a_malformed_row(self):
        lld = HEADER + "| 010 | REQ-1 one | Auto |\n"
        with pytest.raises(cc.CriteriaTableError):
            cc.criteria_coverage(SPEC, lld)


class TestACheckThatCannotRunIsNotOk:
    def test_222_an_lld_with_no_criteria_table_is_not_ok(self):
        report = cc.criteria_coverage(SPEC, "# LLD\n\nProse only.\n")
        assert report.ran is False
        assert report.ok is False
        assert "cannot be checked" in cc.format_report(report)

    def test_237_untagged_criteria_are_not_ok(self):
        lld = HEADER + "| 010 | one | Auto | ok |\n"
        report = cc.criteria_coverage(SPEC, lld)
        assert report.ran is False
        assert report.ok is False
        assert "REQ tag" in cc.format_report(report)

    def test_full_tagged_coverage_is_ok(self):
        lld = HEADER + "| 010 | REQ-1 one | Auto | ok |\n"
        report = cc.criteria_coverage(SPEC, lld)
        assert report.ran is True and report.ok is True

    def test_a_miss_is_not_ok(self):
        lld = HEADER + "| 010 | REQ-1 one | Auto | ok |\n| 020 | REQ-2 two | Auto | ok |\n"
        report = cc.criteria_coverage(SPEC, lld)
        assert report.ran is True and report.ok is False
        assert [c.key for c in report.missing] == ["REQ-2"]
