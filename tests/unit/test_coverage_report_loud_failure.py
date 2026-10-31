"""coverage_report.py under standard 0034, one test per sweep site (#3585).

Both ledger rows for this module are compliant, and stay as they are. A
report with no TOTAL row (137) and a report whose table leaves out the
target (143) are each a reading in the state ABSENT, with no percentage and
a failure message naming what was sought and what the report held. That is
the module's documented contract (#2637). Since #4436 the gate reads the
per-line report, so this reading supplies coverage's own reason to N5's halt
when that report is missing. These tests pin the contract.

Line numbers in the names are ledger 0908's, at its base `79e18ad1`.
"""
from __future__ import annotations

import pytest

from assemblyzero.workflows.testing import coverage_report as cr

TABLE = (
    "Name                 Stmts   Miss  Cover   Missing\n"
    "--------------------------------------------------\n"
    "src/pkg/other.py        10      2    80%   3-4\n"
    "--------------------------------------------------\n"
    "TOTAL                   10      2    80%\n"
)


class TestNoTotalRow:
    def test_137_no_total_row_is_absent_with_no_percentage(self):
        reading = cr.read_coverage(
            "CoverageWarning: Module pkg.mod was never imported\n"
            "CoverageWarning: No data was collected\n",
            "pkg.mod",
        )

        assert reading.state == cr.ABSENT
        assert reading.measured is False
        assert reading.percent is None
        assert reading.reasons == ["was never imported", "No data was collected"]

    def test_137_its_message_names_the_target_and_says_it_is_a_failure(self):
        message = cr.read_coverage("", "pkg.mod").failure_message()

        assert message.startswith("COVERAGE MEASUREMENT FAILED")
        assert "`pkg.mod`" in message
        assert "no files at all" in message

    def test_137_an_absent_percentage_cannot_be_read_as_a_number(self):
        """None, not 0.0: a caller that forgets the state fails loudly."""
        reading = cr.read_coverage("", "pkg.mod")
        with pytest.raises(TypeError):
            reading.percent < 95  # noqa: B015 - the comparison is the test


class TestTheTargetIsNotInTheReport:
    def test_143_a_table_without_the_target_is_absent(self):
        reading = cr.read_coverage(TABLE, "pkg.mod")

        assert reading.state == cr.ABSENT
        assert reading.percent is None
        assert reading.files == ["src/pkg/other.py"]

    def test_143_its_message_names_what_the_report_covers(self):
        message = cr.read_coverage(TABLE, "pkg.mod").failure_message()

        assert "`pkg.mod`" in message
        assert "src/pkg/other.py" in message
        assert "not a test gap" in message


class TestMeasured:
    def test_a_table_with_the_target_is_measured(self):
        reading = cr.read_coverage(TABLE, "pkg.other")

        assert reading.measured
        assert reading.percent == 80.0
        assert reading.uncovered == {"src/pkg/other.py": ["3-4"]}
