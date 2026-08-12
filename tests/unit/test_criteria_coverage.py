"""Every LLD pass criterion must have a test in the spec (Closes #2239).

The spec stage had no mechanical criterion-to-test check; the judgment lived
only in the adversarial reviewer, so a miss cost a full REVISE round and
detection was bounded by the iteration cap. run-issue7-082047 (boostgauge,
2026-08-12) spent three iterations and still died at the cap with "completely
omits 12 required state matrix tests" among the reasons.

The fixtures here are real artifacts, not invented ones:

* ``LLD-007.md`` -- verbatim from boostgauge PR #285 at ``f8018447``. Twenty-two
  requirements over twenty-three scenario rows, twelve of them decision-table
  rows (REQ-9..REQ-20).
* ``spec-0007-reconstruction.md`` -- a **documented reconstruction**, authored
  for this test under the operator's 2026-08-12 ruling. The real failing spec
  does not exist: orchestrated runs never persisted their drafts (#2250). The
  file states its own provenance in its first paragraph.
* ``LLD-041.md`` / ``spec-0041.md`` -- verbatim from merged boostgauge PR #214,
  a historically green run, used to pin that full coverage passes unchanged.
* ``LLD-001.md`` / ``spec-0001.md`` -- verbatim from merged boostgauge PR #220.
  See ``TestAGreenRunThatWasNotActuallyCovered`` -- measuring this pair is how
  the check found that a green run shipped with four criteria untested.
"""

from pathlib import Path

import pytest

from assemblyzero.workflows.implementation_spec.criteria_coverage import (
    MODE_EXACT,
    MODE_OUTCOME,
    criteria_coverage,
    format_report,
    lld_criteria,
    spec_tests,
)
from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
    check_criteria_have_tests,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "criteria_coverage"

#: The twelve decision-table rows of LLD-007: position matrix + size matrix.
MATRIX_ROWS = [f"REQ-{n}" for n in range(9, 21)]


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# The regression the issue names
# ---------------------------------------------------------------------------


class TestTheOmittedMatrixTests:
    """LLD-007 against a spec missing exactly the twelve row tests."""

    @pytest.fixture
    def report(self):
        return criteria_coverage(
            _fixture("spec-0007-reconstruction.md"), _fixture("LLD-007.md")
        )

    def test_all_twelve_row_criteria_are_reported_missing(self, report):
        assert sorted(c.key for c in report.missing) == sorted(MATRIX_ROWS), (
            "the check must name every omitted row criterion, not a sample. The "
            "whole point is that one revision can address the full set instead "
            "of paying a REVISE round per miss."
        )

    def test_nothing_else_is_reported_missing(self, report):
        """A check that fired on a spec thin everywhere would prove nothing
        about the row omission."""
        assert len(report.missing) == 12

    def test_the_check_fails(self, report):
        assert not report.ok

    def test_every_missing_criterion_is_named_in_the_report_text(self, report):
        text = format_report(report)
        for key in MATRIX_ROWS:
            assert key in text, f"{key} is missing from the drafter-facing report"

    def test_the_report_names_the_join_mode(self, report):
        """#2239: the weaker mode must never be mistaken for the stronger."""
        assert report.join_mode == MODE_EXACT
        assert "exact" in format_report(report)

    def test_the_report_carries_the_scenario_text(self, report):
        """A bare ID list would make the drafter go read the LLD; the point is
        to hand it what to write."""
        text = format_report(report)
        assert "Pos matrix" in text
        assert "Size matrix" in text

    def test_the_measured_requirement_count_is_twenty_two(self):
        """The 2026-08-12 correction on the issue: twenty-two, not twenty-one."""
        keys = {c.key for c in lld_criteria(_fixture("LLD-007.md"))}
        assert len(keys) == 22, f"expected 22 distinct requirements, got {len(keys)}"


# ---------------------------------------------------------------------------
# A historically green run must still pass
# ---------------------------------------------------------------------------


class TestAGreenRunPassesUnchanged:
    """boostgauge PR #214: LLD-041 and its final spec, merged and green."""

    def test_full_coverage_passes(self):
        report = criteria_coverage(_fixture("spec-0041.md"), _fixture("LLD-041.md"))

        assert report.ok, (
            "a merged, historically green spec must not be failed by this check. "
            f"Reported missing: {[c.key for c in report.missing]}"
        )
        assert report.join_mode == MODE_EXACT
        assert report.covered == len(report.criteria)

    def test_it_really_had_criteria_and_tests_to_check(self):
        """A pass proves nothing if either side was empty."""
        assert len(lld_criteria(_fixture("LLD-041.md"))) == 12
        assert len(spec_tests(_fixture("spec-0041.md"))) == 13


class TestAGreenRunThatWasNotActuallyCovered:
    """boostgauge PR #220, merged green, is NOT full coverage.

    #2239 named PRs #220 and #214 as green-run specs carrying REQ tags, on the
    premise that both would pass unchanged. Measured, #214 does and #220 does
    not: LLD-001 tags all twelve of its scenario rows, and spec-0001's eleven
    tests cite only eight of them. REQ-6 (wordmark), REQ-7 (telltales behind the
    main needle), REQ-10 (omit a telltale when None) and REQ-11 (needle over
    redline) have no test. All twelve rows are type "Auto", so no exemption
    applies.

    That is the defect this issue exists to catch, shipped in a green run and
    undetected -- a second exhibit for the thesis rather than a counterexample
    to it. Pinned here so the finding survives, and so the day someone adds the
    four tests this test says plainly what changed.
    """

    def test_exactly_the_four_visual_criteria_are_uncovered(self):
        report = criteria_coverage(_fixture("spec-0001.md"), _fixture("LLD-001.md"))

        assert sorted(c.key for c in report.missing) == ["REQ-10", "REQ-11", "REQ-6", "REQ-7"]

    def test_the_other_eight_are_covered(self):
        report = criteria_coverage(_fixture("spec-0001.md"), _fixture("LLD-001.md"))
        assert report.covered == len(report.criteria) - 4


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


class TestCriterionExtraction:
    def test_scenario_rows_become_criteria(self):
        criteria = lld_criteria(_fixture("LLD-007.md"))
        assert len(criteria) == 23, (
            "twenty-three scenario rows over twenty-two requirements -- REQ-4 "
            "has two rows, 040 and 041"
        )

    def test_row_ids_are_carried_for_the_report(self):
        by_key = {c.key: c for c in lld_criteria(_fixture("LLD-007.md"))}
        assert by_key["REQ-9"].row_id == "090"

    def test_non_scenario_tables_are_left_alone(self):
        """An LLD's Alternatives Considered table is a table, not criteria."""
        lld = (
            "## 4. Alternatives Considered\n\n"
            "| Option | Pros | Cons | Decision |\n"
            "|---|---|---|---|\n"
            "| In-memory diffing | Simple | Overwrites edits | **Rejected** |\n"
        )
        assert lld_criteria(lld) == []

    def test_an_lld_with_no_table_is_not_applicable(self):
        report = criteria_coverage("```python\ndef test_x(): pass\n```", "# LLD\n\nProse only.\n")
        assert not report.ran
        assert "not applicable" in format_report(report).lower()


class TestSpecTestExtraction:
    def test_tests_are_found_inside_fences(self):
        names = [n for n, _ in spec_tests(_fixture("spec-0041.md"))]
        assert "test_t010_initialization_validation" in names

    def test_prose_outside_a_fence_is_not_coverage(self):
        """spec-0041's closing paragraph says its assertions "trace to
        requirements REQ-1 through REQ-7". That sentence names no test, and a
        checker that counted it would call an empty spec fully covered."""
        spec = (
            "All test assertions trace to requirements REQ-1 through REQ-7.\n"
            "\n```python\ndef test_only(self):\n    \"\"\"REQ-1: something.\"\"\"\n```\n"
        )
        tagged = spec_tests(spec)
        assert len(tagged) == 1
        assert "REQ-7" not in tagged[0][1]

    def test_a_docstring_stays_with_its_own_test(self):
        spec = (
            "```python\n"
            "def test_one():\n    \"\"\"REQ-1: first.\"\"\"\n    pass\n\n"
            "def test_two():\n    \"\"\"REQ-2: second.\"\"\"\n    pass\n"
            "```\n"
        )
        blocks = dict(spec_tests(spec))
        assert "REQ-1" in blocks["test_one"] and "REQ-2" not in blocks["test_one"]
        assert "REQ-2" in blocks["test_two"] and "REQ-1" not in blocks["test_two"]


# ---------------------------------------------------------------------------
# The fallback mode
# ---------------------------------------------------------------------------


class TestCountAndOutcomeFallback:
    """Used when there are no IDs to join on. #2239 requires the mode be named,
    and requires matching rather than greedy assignment."""

    UNTAGGED_LLD = (
        "### 10.1 Test Scenarios\n\n"
        "| ID | Scenario | Type | Pass Criteria |\n"
        "|---|---|---|---|\n"
        "| 010 | Size no reset not resized | Auto | size unchanged |\n"
        "| 020 | Size no reset size given | Auto | size unchanged; the CLI value is not written |\n"
    )

    def test_the_mode_is_named(self):
        spec = (
            "```python\n"
            "def test_a():\n    \"\"\"size unchanged.\"\"\"\n\n"
            "def test_b():\n    \"\"\"size unchanged; the CLI value is not written.\"\"\"\n"
            "```\n"
        )
        report = criteria_coverage(spec, self.UNTAGGED_LLD)
        assert report.join_mode == MODE_OUTCOME
        assert "count and outcome" in format_report(report)

    def test_matching_is_not_greedy(self):
        """'size unchanged' is a substring of 'size unchanged; the CLI value is
        not written'. Assigning in row order would consume the only test row 020
        could use and report a gap that is not there -- the exact hazard
        _max_matching exists for."""
        spec = (
            "```python\n"
            "def test_b():\n    \"\"\"size unchanged; the CLI value is not written.\"\"\"\n\n"
            "def test_a():\n    \"\"\"size unchanged.\"\"\"\n"
            "```\n"
        )
        report = criteria_coverage(spec, self.UNTAGGED_LLD)
        assert report.ok, f"false gap reported: {[c.row_id for c in report.missing]}"

    def test_a_genuine_gap_is_still_caught(self):
        spec = "```python\ndef test_a():\n    \"\"\"size unchanged.\"\"\"\n```\n"
        report = criteria_coverage(spec, self.UNTAGGED_LLD)
        assert len(report.missing) == 1


# ---------------------------------------------------------------------------
# Wiring into the node
# ---------------------------------------------------------------------------


class TestTheCompletenessCheck:
    def test_the_check_fails_the_reconstruction(self):
        check = check_criteria_have_tests(
            _fixture("spec-0007-reconstruction.md"), _fixture("LLD-007.md")
        )
        assert check["check_name"] == "criteria_have_tests"
        assert not check["passed"]
        for key in MATRIX_ROWS:
            assert key in check["details"]

    def test_the_check_passes_the_green_run(self):
        check = check_criteria_have_tests(
            _fixture("spec-0041.md"), _fixture("LLD-041.md")
        )
        assert check["passed"]

    def test_an_absent_lld_is_not_applicable_rather_than_a_failure(self):
        """#1870's convention: nothing to check is not evidence, but it is also
        not a failure -- a spec must not be blocked because the LLD did not
        reach this node."""
        check = check_criteria_have_tests("```python\ndef test_x(): pass\n```", "")
        assert check["passed"]
        assert "not applicable" in check["details"].lower()

    def test_the_node_runs_the_check(self):
        """The check must actually be wired in, not merely defined -- a check
        nothing calls is the quietest way for this to regress."""
        import inspect

        from assemblyzero.workflows.implementation_spec.nodes import (
            validate_completeness as node,
        )

        source = inspect.getsource(node)
        assert "check_criteria_have_tests(" in source, (
            "validate_completeness defines the check but never calls it"
        )
        assert "lld_content" in source, (
            "the check is called without the LLD, so it can only ever report "
            "'not applicable'"
        )
