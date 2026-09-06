"""An edit block with an empty section is a block, a marker is never written
into a file (#2918); the green state is the best state (#2919); and a
full-suite regression found at the cap gets a repair pass (#2920).

boostgauge #4, `run-issue4-141929` (2026-09-06 14:19). The full-suite check
had just handed N4 the circular import's cause (#2914). windows.py's model
call answered with three blocks, the first a deletion:

    <<<<<<< SEARCH
    from boostgauge.collector import (
        ...
    )
    =======
    >>>>>>> REPLACE

The regex parser required a newline on both sides of each section's text,
so the empty REPLACE did not match at its own closing marker and the lazy
`(.*?)` ran on to the NEXT block's closing marker. Two blocks were "applied",
the log said `100% of the prior file preserved byte-identical`, and line 13
of windows.py read `>>>>>>> REPLACE`:

    E     File ".../src/boostgauge/collectors/windows.py", line 13
    E       >>>>>>> REPLACE
    E   SyntaxError: invalid syntax
    [N5] Results: 0 passed, 1 failed | Coverage: 47.0%
    [N5] iteration regressed (0 passing at 47.0% vs best 38 at 90.0%) — restored 6 file(s)

And the restore went to 38 at 90 %, from before the coverage stage, because
the green-passed path -- 48 tests at 97 % a minute earlier -- had never
snapshotted.
"""

from __future__ import annotations

from pathlib import Path

from assemblyzero.workflows.implementation_spec.nodes.edit_script import (
    apply_edit_blocks,
    parse_edit_blocks,
)
from assemblyzero.workflows.testing.nodes.implementation.edit_script_fix import (
    apply_code_edit_script,
)

# windows.py as run 42 had it, reduced to the lines the response touches.
WINDOWS_PY = '''\
from __future__ import annotations

import ctypes

from boostgauge.collector import (
    DataCollector,
    SystemSnapshot,
    Thresholds,
    composite,
)


class WindowsCollector(DataCollector):
    def collect(self):
        return SystemSnapshot(
            driver=driver,
            composite_value=composite_value,
        )
'''

# The model's answer, verbatim in shape: a deletion, a one-line change, and
# an append.
RUN_42_RESPONSE = '''\
<<<<<<< SEARCH
from boostgauge.collector import (
    DataCollector,
    SystemSnapshot,
    Thresholds,
    composite,
)
=======
>>>>>>> REPLACE

<<<<<<< SEARCH
class WindowsCollector(DataCollector):
=======
class WindowsCollector(object):
>>>>>>> REPLACE

<<<<<<< SEARCH
            driver=driver,
            composite_value=composite_value,
        )
=======
            driver=driver,
            composite_value=composite_value,
        )


from boostgauge.collector import (  # noqa: E402
    DataCollector,
    SystemSnapshot,
    Thresholds,
    composite,
)
WindowsCollector.__bases__ = (DataCollector,)
>>>>>>> REPLACE
'''


class TestRun42sResponse:
    def test_three_blocks_the_first_a_deletion(self):
        blocks = parse_edit_blocks(RUN_42_RESPONSE)

        assert len(blocks) == 3
        assert blocks[0][0].startswith("from boostgauge.collector import (")
        assert blocks[0][1] == ""
        assert blocks[1] == ("class WindowsCollector(DataCollector):", "class WindowsCollector(object):")

    def test_no_section_carries_a_marker(self):
        for search, replace in parse_edit_blocks(RUN_42_RESPONSE):
            for marker in ("<<<<<<< SEARCH", "=======", ">>>>>>> REPLACE"):
                assert marker not in search
                assert marker not in replace

    def test_applied_the_file_holds_no_marker_and_the_import_is_gone_from_the_top(self):
        patched, failures = apply_edit_blocks(WINDOWS_PY, parse_edit_blocks(RUN_42_RESPONSE))

        assert failures == []
        assert ">>>>>>>" not in patched and "<<<<<<<" not in patched and "=======" not in patched
        assert patched.index("class WindowsCollector(object):") < patched.index("from boostgauge.collector import (")
        assert "WindowsCollector.__bases__ = (DataCollector,)" in patched

    def test_the_implementers_wrapper_reports_three_edits(self):
        outcome = apply_code_edit_script(RUN_42_RESPONSE, WINDOWS_PY)

        assert outcome.ok
        assert outcome.blocks == 3
        assert ">>>>>>> REPLACE" not in outcome.code


class TestTheParserOnEdges:
    def test_an_empty_search_section_parses(self):
        assert parse_edit_blocks("<<<<<<< SEARCH\n=======\nnew\n>>>>>>> REPLACE") == [("", "new")]

    def test_both_sections_empty_parse(self):
        assert parse_edit_blocks("<<<<<<< SEARCH\n=======\n>>>>>>> REPLACE") == [("", "")]

    def test_trailing_whitespace_on_markers_is_tolerated(self):
        assert parse_edit_blocks("<<<<<<< SEARCH  \na\n=======\t\nb\n>>>>>>> REPLACE \n") == [("a", "b")]

    def test_crlf_markers_are_tolerated(self):
        assert parse_edit_blocks("<<<<<<< SEARCH\r\na\r\n=======\r\nb\r\n>>>>>>> REPLACE\r\n") == [("a", "b")]

    def test_a_block_opened_inside_a_block_is_malformed(self):
        nested = "<<<<<<< SEARCH\na\n<<<<<<< SEARCH\nb\n=======\nc\n>>>>>>> REPLACE\n"

        assert parse_edit_blocks(nested) == []

    def test_an_unterminated_block_is_dropped_and_the_complete_ones_kept(self):
        text = "<<<<<<< SEARCH\na\n=======\nb\n>>>>>>> REPLACE\n<<<<<<< SEARCH\nc\n=======\nd\n"

        assert parse_edit_blocks(text) == [("a", "b")]

    def test_a_whole_response_fence_is_unwrapped(self):
        fenced = "```\n<<<<<<< SEARCH\na\n=======\n>>>>>>> REPLACE\n```"

        assert parse_edit_blocks(fenced) == [("a", "")]

    def test_a_separator_inside_text_that_is_not_seven_equals_is_content(self):
        text = "<<<<<<< SEARCH\n========\n=======\nx\n>>>>>>> REPLACE"

        assert parse_edit_blocks(text) == [("========", "x")]


class TestTheApplierRefusesMarkers:
    def test_a_marker_in_a_replacement_is_a_failure_not_a_write(self):
        patched, failures = apply_edit_blocks(
            "a\nb\n", [("a", ">>>>>>> REPLACE\n\n<<<<<<< SEARCH\nb")],
        )

        assert failures == ["block 1: an edit marker inside a section; the response is malformed"]
        assert ">>>>>>>" not in patched

    def test_a_marker_in_a_search_is_a_failure(self):
        _, failures = apply_edit_blocks("a\n", [("=======", "x")])

        assert len(failures) == 1 and "malformed" in failures[0]

    def test_the_implementers_wrapper_falls_back_on_a_malformed_block(self):
        outcome = apply_code_edit_script(
            "<<<<<<< SEARCH\na\n=======\n>>>>>>> REPLACE\n<<<<<<< SEARCH\nb\n=======\nc", "a\nb\n",
        )
        # Only the first block is complete; it deletes `a`. Nothing malformed
        # reaches the applier, and the unterminated tail is not an edit.
        assert outcome.ok and outcome.code == "\nb\n"


class TestTheGreenStateIsTheBest:
    def test_the_verifier_snapshots_before_the_full_suite_check(self):
        source = (
            Path(__file__).resolve().parents[2]
            / "assemblyzero" / "workflows" / "testing" / "nodes" / "verify_phases.py"
        ).read_text(encoding="utf-8")
        passed = source.index('print(f"    [N5] Green phase PASSED: {passed_count} tests')
        snapshot = source.index("_hill_climb(state, repo_root, passed_count, coverage_achieved,", passed)
        full_suite = source.index("Running full test suite regression check", passed)
        assert passed < snapshot < full_suite

    def test_every_return_after_green_carries_the_snapshot(self):
        source = (
            Path(__file__).resolve().parents[2]
            / "assemblyzero" / "workflows" / "testing" / "nodes" / "verify_phases.py"
        ).read_text(encoding="utf-8")
        start = source.index('print(f"    [N5] Green phase PASSED: {passed_count} tests')
        end = source.index("def _resolve_framework_enum(")
        tail = source[start:end]

        assert tail.count("**green_updates,") == 3
        assert tail.count('"next_node": "N4_implement_code"') == 1
        assert tail.count('"next_node": "N6_e2e_validation"') == 1
        assert tail.count('"next_node": "N7_finalize"') == 1


class TestAFullSuiteRegressionAtTheCapGetsARepairPass:
    """#2920: run 42 went green on iteration 4 of 5; the full-suite route
    made it 5/5 and the router stopped the loop, the stage failed, and the
    orchestrator regenerated the scaffold from a green tree."""

    def test_run_42s_shape_is_granted_a_pass(self, capsys):
        from assemblyzero.workflows.testing.nodes.verify_phases import _full_suite_repair_grace

        assert _full_suite_repair_grace({}, iteration_count=4, max_iterations=5) == 6
        assert "repair pass 1 of 2 granted, cap now 6 (#2920)" in capsys.readouterr().out

    def test_below_the_cap_nothing_changes(self):
        from assemblyzero.workflows.testing.nodes.verify_phases import _full_suite_repair_grace

        assert _full_suite_repair_grace({}, iteration_count=2, max_iterations=5) is None

    def test_the_second_pass_is_the_last(self, capsys):
        from assemblyzero.workflows.testing.nodes.verify_phases import _full_suite_repair_grace

        assert _full_suite_repair_grace({"full_suite_repair_passes": 1}, 5, 6) == 7
        assert _full_suite_repair_grace({"full_suite_repair_passes": 2}, 6, 7) is None
        assert "the cap holds (#2920)" in capsys.readouterr().out

    def test_the_route_writes_the_cap_and_the_count_into_state(self):
        from assemblyzero.workflows.testing.state import TestingWorkflowState
        source = (
            Path(__file__).resolve().parents[2]
            / "assemblyzero" / "workflows" / "testing" / "nodes" / "verify_phases.py"
        ).read_text(encoding="utf-8")
        start = source.index("collection_cause = collection_error_blocks(full_output)")
        routed = source.index('"next_node": "N4_implement_code"', start)
        block = source[start:routed]

        assert "_full_suite_repair_grace(state, iteration_count, max_iterations)" in block
        assert '"full_suite_repair_passes": repair_passes + 1' in block
        assert '"max_iterations": repair_cap if repair_cap is not None else max_iterations' in block
        assert "full_suite_repair_passes" in TestingWorkflowState.__annotations__
