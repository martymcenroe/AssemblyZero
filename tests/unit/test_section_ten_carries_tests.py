"""Section 10 must actually hold the test functions (#2741).

#1870 established Section 10.1 as where executable test functions live and
#2316 made the scaffolder emit them verbatim. Nothing checked they were there.

Run 12 of boostgauge #4 (`run-issue4-192453`) put its functions in Section 6 and
left Section 10.1 as one sentence pointing at them. Section 10 is where the
checks look, so `spec_test_functions_have_assertions` (#2706) and
`spec_test_fixtures_resolvable` (#2707) both reported NOT APPLICABLE and the
contract mechanism (#2709) never engaged. Three pieces of machinery, all landed
within a day of that run, all silent, all printing green.

The fixture below is that draft's Section 10.1 verbatim.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from assemblyzero.workflows.implementation_spec.check_classification import (
    FACT,
    CLASSIFICATIONS,
    is_proxy,
)
from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
    check_section_ten_carries_test_functions,
    check_spec_test_functions_have_assertions,
)
from assemblyzero.workflows.implementation_spec.revision_pinning import (
    demands_additions,
    named_line_ranges,
)

CHECK = "section_ten_carries_test_functions"

#: `run-issue4-192453`, 016-spec-draft.md, Section 10.1 verbatim. The sentence
#: that made two gates go quiet.
RUN_12_POINTER = (
    "See `tests/unit/test_collector.py`, "
    "`tests/integration/test_windows_collector.py`, and "
    "`tests/benchmark/test_windows_sweep.py` in Section 6 for exactly 1 "
    "function per requirement criterion mapped from the LLD, strictly "
    "fulfilling the coverage requirements."
)

HEAD = textwrap.dedent("""\
    # Implementation Spec: the collector

    ## 1. Overview

    Implements REQ-1.

    ## 6. Change Instructions

    Write `src/collector.py`.
    """)

TAIL = textwrap.dedent("""\

    ## 11. Implementation Notes

    Nothing further.
    """)

TABLE = textwrap.dedent("""\
    | Test ID | Tests Function | Expected |
    |---|---|---|
    | 010 | `test_req_010` | passes |
    """)

FUNCTIONS = textwrap.dedent("""\
    ```python
    import pytest

    def test_req_010_collector_reads():
        assert collector.read() == 1
    ```
    """)


def spec(section_ten: str, head: str = HEAD) -> str:
    return f"{head}\n## 10. Test Mapping\n\n### 10.1 Per-criterion test functions\n\n{section_ten}\n{TAIL}"


class TestTheArtifactThatShowedTheProblem:
    def test_the_run_12_shape_is_refused(self):
        result = check_section_ten_carries_test_functions(spec(RUN_12_POINTER))
        assert result["passed"] is False
        assert result["check_name"] == CHECK

    def test_the_two_checks_it_silenced_still_report_not_applicable(self):
        """The control, and the reason this check had to exist. #2706's check
        is not wrong to abstain -- it has nothing to read. It just cannot be
        the thing that notices why."""
        old = check_spec_test_functions_have_assertions(spec(RUN_12_POINTER))
        assert old["passed"] is True
        assert "not applicable" in old["details"].lower()

    def test_the_complaint_says_what_it_found_instead(self):
        details = check_section_ten_carries_test_functions(
            spec(TABLE + "\n" + RUN_12_POINTER)
        )["details"]
        assert "a table of scenarios" in details
        assert "a pointer to test files or another section" in details

    def test_a_section_holding_the_functions_passes(self):
        result = check_section_ten_carries_test_functions(spec(FUNCTIONS))
        assert result["passed"] is True
        assert "1 executable test function" in result["details"]


class TestNotApplicableStaysPossibleAndVisible:
    def test_no_section_ten_means_the_check_did_not_run(self):
        """A spec with no test section is `criteria_have_tests`'s finding. This
        one says it did not run rather than inventing a pass -- losing that
        distinction is exactly what run 12 did."""
        result = check_section_ten_carries_test_functions(HEAD + TAIL)
        assert result["passed"] is True
        assert "did not run" in result["details"]

    def test_the_did_not_run_case_is_counted_as_not_applicable(self):
        """The node counts a check as not-applicable by looking for that phrase
        in its details (#1870), so the wording is load-bearing: without it the
        summary would read this as a verified pass."""
        result = check_section_ten_carries_test_functions(HEAD + TAIL)
        assert "not applicable" in result["details"].lower() or "did not run" in (
            result["details"].lower()
        )


class TestTheComplaintCanBeActedOn:
    def test_it_cites_the_section_span_so_pinning_can_unlock_it(self):
        """#2686: a demand to ADD has no existing line to name, and a complaint
        that addressed only its heading left the insertion point locked -- the
        drafter wrote the demanded edit three times and pinning refused it three
        times. The citation has to span the region the edit goes in."""
        draft = spec(RUN_12_POINTER)
        details = check_section_ten_carries_test_functions(draft)["details"]
        ranges = named_line_ranges([details])
        assert ranges, "the complaint names no line range at all"
        start, end = ranges[0]
        assert end > start, "a one-line citation addresses the heading only"

        lines = draft.splitlines()
        cited = "\n".join(lines[start - 1:end])
        assert "## 10." in cited, "the citation must cover the section heading"
        assert "10.1" in cited, "and the subsection the functions belong in"

    def test_asking_for_new_content_is_recognised_as_an_addition_demand(self):
        """#2560 and #2740: pinning refuses an edit that adds content unless the
        complaint is recognised as demanding an addition. A draft with no test
        function anywhere is asking for new content."""
        details = check_section_ten_carries_test_functions(
            spec(RUN_12_POINTER)
        )["details"]
        assert "Add the block inside that subsection" in details
        assert demands_additions([details]) is True

    def test_asking_for_a_move_does_not_read_as_a_demand_for_new_tests(self):
        """When the functions exist elsewhere in the draft, the fix is a move.
        Saying "add" there would ask the drafter to write tests it has already
        written, which is how a complaint makes a draft worse."""
        draft = spec(RUN_12_POINTER, head=HEAD + "\n" + FUNCTIONS)
        details = check_section_ten_carries_test_functions(draft)["details"]
        assert "Move them into Section 10" in details
        assert "Add the block inside that subsection" not in details
        assert demands_additions([details]) is False


class TestItIsAReviseCheckByConstruction:
    def test_it_is_declared_a_fact_and_keeps_its_authority(self):
        """An unclassified check would fail the exhaustiveness lint; a check
        classified as a proxy would be demoted to advisory whenever the
        reviewer is engaged, which is precisely when run 12 was passing."""
        assert CHECK in CLASSIFICATIONS
        assert CLASSIFICATIONS[CHECK].kind == FACT
        assert is_proxy(CHECK) is False

    def test_it_adds_no_halt_site(self):
        """The ratchet forbids a new halting gate (#2720). A failing
        completeness check routes the draft back to the drafter, bounded by the
        review iteration cap; it returns a CompletenessCheck and raises
        nothing, so the walker finds no new site."""
        from assemblyzero.core.gate_registry import renumberings, scan_halt_sites

        root = Path(__file__).resolve().parents[2]
        sites, _coverage = scan_halt_sites(root)
        moved, fresh, ghosts = renumberings(sites)
        assert (moved, fresh, ghosts) == ([], [], [])


BOOSTGAUGE = Path("C:/Users/mcwiz/Projects/boostgauge/docs/lineage")


@pytest.mark.skipif(
    not BOOSTGAUGE.is_dir(),
    reason="the recorded lineage lives in the target repo, not in this one",
)
class TestAgainstEveryRecordedDraft:
    """Measured across the whole corpus, not only the exhibit.

    90 unique spec drafts survive in boostgauge's lineage. The check refuses 12
    of them, and those 12 are two runs: `run-issue4-192453` (six drafts) and one
    run of issue #331 (six drafts). Both left Section 10 holding a table and a
    pointer. Every other draft carries its functions and passes.
    """

    def _drafts(self) -> list[Path]:
        seen: dict[str, Path] = {}
        for path in sorted(BOOSTGAUGE.rglob("*-spec-draft.md")):
            seen.setdefault(str(path.resolve()), path)
        return list(seen.values())

    def test_it_refuses_only_the_two_runs_that_moved_their_tests(self):
        refused = [
            path for path in self._drafts()
            if not check_section_ten_carries_test_functions(
                path.read_text(encoding="utf-8", errors="replace")
            )["passed"]
        ]
        runs = sorted({path.parent.name for path in refused})
        assert len(refused) == 12, [str(p) for p in refused]
        assert len(runs) == 2, runs

    def test_every_other_draft_passes(self):
        drafts = self._drafts()
        passing = [
            path for path in drafts
            if check_section_ten_carries_test_functions(
                path.read_text(encoding="utf-8", errors="replace")
            )["passed"]
        ]
        assert len(drafts) - len(passing) == 12
        assert len(passing) == 78
