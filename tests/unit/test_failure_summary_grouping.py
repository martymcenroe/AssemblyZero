"""N4's failure feedback must carry every distinct cause, not the first 16 lines (#2058).

Three consecutive runs of boostgauge #2 rewrote all 7 files and landed on an
identical pass count. The revision was blind: with 100+ failures at ~120 chars
per summary line, the 2000-char cap fed N4 the first ~16 lines and cut the
rest. 41 tests failing on one TypeError are ONE fact -- grouping says so in one
line and leaves budget for every other distinct cause.
"""

from assemblyzero.workflows.testing.nodes.verify_phases import (
    _build_failure_summary,
)


def _output(lines):
    return (
        "===== short test summary info =====\n"
        + "\n".join(lines)
        + "\n==================================\n"
    )


class TestGrouping:
    def test_one_cause_many_tests_is_one_line(self):
        """The live shape: 41 tests, one TypeError."""
        lines = [
            f"FAILED tests/unit/test_m.py::test_{i} - TypeError: Telltale.__init__() "
            f"got an unexpected keyword argument 'window_seconds'"
            for i in range(41)
        ]
        summary = _build_failure_summary(_output(lines))

        assert "41 test(s):" in summary
        assert summary.count("window_seconds") == 1
        assert "and 38 more" in summary

    def test_every_distinct_cause_survives_a_large_suite(self):
        """The defect: causes past the old cap were invisible to the revision."""
        lines = []
        for c in range(20):
            for i in range(5):
                lines.append(
                    f"FAILED tests/unit/test_x.py::test_c{c}_{i} - "
                    f"AssertionError: distinct cause number {c} was violated"
                )
        summary = _build_failure_summary(_output(lines))

        for c in range(20):
            assert f"distinct cause number {c}" in summary, (
                f"cause {c} fell off the feedback; the revision is blind to it"
            )

    def test_biggest_group_leads(self):
        lines = [
            "FAILED tests/a.py::t1 - RareError: once",
            "FAILED tests/a.py::t2 - CommonError: lots",
            "FAILED tests/a.py::t3 - CommonError: lots",
        ]
        summary = _build_failure_summary(_output(lines))
        assert summary.index("CommonError") < summary.index("RareError")

    def test_lines_without_a_reason_are_kept_verbatim(self):
        lines = ["FAILED tests/a.py::t1", "ERROR tests/b.py"]
        summary = _build_failure_summary(_output(lines))
        assert "tests/a.py::t1" in summary
        assert "ERROR tests/b.py" in summary

    def test_no_failures_is_still_empty(self):
        assert _build_failure_summary("all good\n") == ""
