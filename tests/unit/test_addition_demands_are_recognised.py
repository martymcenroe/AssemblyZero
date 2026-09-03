"""Every complaint that asks for new content must be recognised as asking (#2740).

The pinning enforcement refuses a revision that adds content the round did not
demand. `demands_additions` decides what counts as a demand, from a closed list
of phrasings enumerated BY HAND from the checks' own strings. That hand copy is
the defect surface: a check whose wording was never fed back into the list emits
a complaint the drafter is told to satisfy and the enforcement then refuses --
a complaint that can be made and never satisfied.

It has happened twice. #2591: `check_modify_files_have_excerpts` demanded a
fenced excerpt and nothing recognised it. #2740: `check_error_path_coverage`'s
two branches are worded differently, the exception branch says "owes each a
test" and was covered, and the platform branch says "no test varies the
platform" and was not.

So this file does not test the list. It renders each check's REAL complaint from
the check's own code and asserts the pattern matches it. A new check, or a
reworded one, fails here rather than deadlocking a live run.
"""
from __future__ import annotations

import pytest

from assemblyzero.workflows.implementation_spec.criteria_coverage import (
    Criterion,
    CoverageReport,
)
from assemblyzero.workflows.implementation_spec.criteria_coverage import (
    format_report as format_criteria,
)
from assemblyzero.workflows.implementation_spec.error_path_coverage import (
    ErrorPathReport,
)
from assemblyzero.workflows.implementation_spec.error_path_coverage import (
    format_report as format_error_paths,
)
from assemblyzero.workflows.implementation_spec.revision_pinning import (
    demands_additions,
)


#: One row of an LLD pass-criteria table, in the shape `lld_criteria` produces.
_CRITERION = Criterion(
    key="REQ-1", row_id="1", scenario="the gauge reads zero at rest",
    outcome="needle sits on 0", tagged=True,
)


class TestErrorPathCoverage:
    """Both branches, because they are worded differently and only one of them
    was recognised until #2740."""

    def test_an_untested_exception_is_recognised_as_demanding_a_test(self):
        report = ErrorPathReport(
            ran=True, raised={"ValueError": 1}, asserted=set(),
            untested=["ValueError"], test_count=3,
        )
        complaint = format_error_paths(report)
        assert "owes each a test" in complaint
        assert demands_additions([complaint]) is True

    def test_a_platform_gap_is_recognised_as_demanding_a_test(self):
        """#2740. This was the hole: the drafter is told to add a test that
        varies the platform, adds one, and the addition is refused because
        nothing recognised the demand."""
        report = ErrorPathReport(
            ran=True, platform_branches=2, platform_tested=False, test_count=3,
        )
        complaint = format_error_paths(report)
        assert "no test varies the platform" in complaint
        assert demands_additions([complaint]) is True

    def test_both_gaps_at_once_are_recognised(self):
        report = ErrorPathReport(
            ran=True, raised={"OSError": 2}, untested=["OSError"],
            platform_branches=1, platform_tested=False, test_count=4,
        )
        assert demands_additions([format_error_paths(report)]) is True

    def test_a_clean_report_demands_nothing(self):
        """The control. Without it the three above would pass on a pattern that
        matched every string, which would unlock every revision."""
        report = ErrorPathReport(
            ran=True, raised={"ValueError": 1}, asserted={"ValueError"},
            platform_branches=1, platform_tested=True, test_count=3,
        )
        complaint = format_error_paths(report)
        assert "Every error path" in complaint
        assert demands_additions([complaint]) is False

    def test_a_check_that_did_not_run_demands_nothing(self):
        report = ErrorPathReport(ran=False, reason="the spec has no code fences")
        assert demands_additions([format_error_paths(report)]) is False


class TestCriteriaCoverage:
    def test_an_uncovered_criterion_is_recognised_as_demanding_a_test(self):
        report = CoverageReport(
            ran=True, join_mode="id",
            criteria=[_CRITERION],
            missing=[_CRITERION],
            test_count=2,
        )
        complaint = format_criteria(report)
        assert demands_additions([complaint]) is True

    def test_full_coverage_demands_nothing(self):
        report = CoverageReport(
            ran=True, join_mode="id",
            criteria=[_CRITERION],
            missing=[], test_count=2,
        )
        assert demands_additions([format_criteria(report)]) is False


class TestTheOtherPhrasingsStillMatch:
    """The three fenced-artifact demands from #2591, kept as literals because
    their checks live inside `validate_completeness.py` and are not separately
    renderable. If one of those is reworded this file will not catch it -- which
    is why the two renderable checks above are driven from their own code, and
    why a check that grows a renderer should be moved up there."""

    @pytest.mark.parametrize(
        "complaint",
        [
            "Section 2.1 lists `src/x.py` as Modify and the spec MUST include "
            "a code block excerpting it.",
            "Section 7 defines a data structure and MUST have at least one "
            "JSON/YAML/Python example.",
            "Section 8.2 documents a function and MUST have at least one "
            "example of its input and output.",
            "Section 9.1 has no example. Add the block inside that subsection.",
        ],
    )
    def test_each_fenced_demand_is_recognised(self, complaint):
        assert demands_additions([complaint]) is True


class TestTheGateStaysNarrow:
    """`demands_additions` unlocks a revision that would otherwise be refused,
    so a pattern that matched ordinary prose would unlock everything."""

    @pytest.mark.parametrize(
        "complaint",
        [
            "The spec's test mapping table is missing a column.",
            "Untagged code fence at lines 5-8 (```): tag it ```python.",
            "Section 10.1 is a pointer to Section 6 rather than test functions.",
            "REQUIREMENTS CONFLICT: two criteria specify different outcomes.",
            "",
        ],
    )
    def test_a_complaint_about_existing_content_demands_nothing(self, complaint):
        assert demands_additions([complaint]) is False

    def test_no_issues_at_all_demands_nothing(self):
        assert demands_additions([]) is False
        assert demands_additions(None) is False
