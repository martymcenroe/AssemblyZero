"""The full-suite check hands N4 a collection error's cause, and a file with
nothing to fix can say so (#2914, #2915).

boostgauge #4, `run-issue4-135112` (2026-09-06 13:51): the first green pass of
the campaign, 47 tests at 97 %, and then the one full-suite check (#842):

    [N5] Full suite: 2 regression(s) detected (0 passed) — routing back to N4
    [N4] failures attributed to 3 of 5 file(s): src/boostgauge/collectors/windows.py,
         tests/benchmark/test_sweep_cost.py, tests/integration/test_windows_sweep_crosscheck.py
    [EDIT-SCRIPT] fell back to full regeneration: no edit blocks in response   (windows.py)

N4 was handed `ERROR tests/integration/test_windows_sweep_crosscheck.py` and
nothing under it. The ERRORS section, reproduced on the run's checkpoint,
named the cause: a circular import closed by `src/boostgauge/collector.py:114`.
"""

from __future__ import annotations

from pathlib import Path

from assemblyzero.workflows.testing.nodes.implementation.edit_script_fix import (
    EditScriptOutcome,
    apply_code_edit_script,
    build_code_edit_script_prompt,
    is_attributed,
)
from assemblyzero.workflows.testing.nodes.verify_phases import collection_error_blocks

# `pytest --co -q` on graveyard/issue-4 at checkpoint 4ff3f98, verbatim but for
# the machine path in the last E line.
RUN_41_FULL_SUITE = """\
=================================== ERRORS ====================================
_____________ ERROR collecting tests/benchmark/test_sweep_cost.py _____________
ImportError while importing test module 'C:\\Users\\mcwiz\\Projects\\boostgauge-run41\\tests\\benchmark\\test_sweep_cost.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests\\benchmark\\test_sweep_cost.py:7: in <module>
    from boostgauge.collectors.windows import WindowsCollector
src\\boostgauge\\collectors\\windows.py:13: in <module>
    from boostgauge.collector import (
src\\boostgauge\\collector.py:114: in <module>
    from boostgauge.collectors.windows import WindowsCollector
E   ImportError: cannot import name 'WindowsCollector' from partially initialized module 'boostgauge.collectors.windows' (most likely due to a circular import) (src/boostgauge/collectors/windows.py)
_____ ERROR collecting tests/integration/test_windows_sweep_crosscheck.py _____
ImportError while importing test module 'C:\\Users\\mcwiz\\Projects\\boostgauge-run41\\tests\\integration\\test_windows_sweep_crosscheck.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests\\integration\\test_windows_sweep_crosscheck.py:6: in <module>
    from boostgauge.collectors.windows import CONSOLE_HOSTS, WindowsCollector
src\\boostgauge\\collectors\\windows.py:13: in <module>
    from boostgauge.collector import (
src\\boostgauge\\collector.py:114: in <module>
    from boostgauge.collectors.windows import WindowsCollector
E   ImportError: cannot import name 'WindowsCollector' from partially initialized module 'boostgauge.collectors.windows' (most likely due to a circular import) (src/boostgauge/collectors/windows.py)
=========================== short test summary info ===========================
ERROR tests/benchmark/test_sweep_cost.py
ERROR tests/integration/test_windows_sweep_crosscheck.py
!!!!!!!!!!!!!!!!!!! Interrupted: 2 errors during collection !!!!!!!!!!!!!!!!!!!
116 tests collected, 2 errors in 0.48s
"""


class TestRun41sCircularImport:
    def test_the_cause_names_the_import_that_closes_the_cycle(self):
        blocks = collection_error_blocks(RUN_41_FULL_SUITE)

        assert "circular import" in blocks
        assert "src/boostgauge/collector.py:114" in blocks
        assert "Move the import at src/boostgauge/collector.py:114" in blocks
        assert "E   ImportError: cannot import name 'WindowsCollector'" in blocks

    def test_two_test_files_tripping_on_one_cause_is_one_block(self):
        blocks = collection_error_blocks(RUN_41_FULL_SUITE)

        assert blocks.count("Collection failed") == 1

    def test_the_importing_test_files_are_not_in_the_block(self):
        blocks = collection_error_blocks(RUN_41_FULL_SUITE)

        assert "test_sweep_cost" not in blocks
        assert "test_windows_sweep_crosscheck" not in blocks

    def test_attribution_reaches_collector_and_not_the_test_files(self):
        blocks = collection_error_blocks(RUN_41_FULL_SUITE)

        assert is_attributed(blocks, "src/boostgauge/collector.py")
        assert not is_attributed(blocks, "tests/benchmark/test_sweep_cost.py")
        assert not is_attributed(blocks, "tests/integration/test_windows_sweep_crosscheck.py")

    def test_the_source_frames_travel_with_their_lines(self):
        blocks = collection_error_blocks(RUN_41_FULL_SUITE)

        assert "src\\boostgauge\\collector.py:114: in <module>" in blocks
        assert "    from boostgauge.collectors.windows import WindowsCollector" in blocks


class TestOtherShapes:
    def test_no_errors_section_is_empty(self):
        assert collection_error_blocks("3 passed in 0.1s\n") == ""
        assert collection_error_blocks("") == ""

    def test_a_plain_import_error_names_the_failing_frame(self):
        output = (
            "=================================== ERRORS ====================================\n"
            "_______________ ERROR collecting tests/unit/test_config.py ________________\n"
            "Traceback:\n"
            "tests\\unit\\test_config.py:3: in <module>\n"
            "    from boostgauge.config import load\n"
            "src\\boostgauge\\config.py:9: in <module>\n"
            "    import tomllib_missing\n"
            "E   ModuleNotFoundError: No module named 'tomllib_missing'\n"
            "=========================== short test summary info ===========================\n"
            "ERROR tests/unit/test_config.py\n"
        )

        blocks = collection_error_blocks(output)

        assert "circular" not in blocks
        assert "the failing import is at src/boostgauge/config.py:9" in blocks
        assert "E   ModuleNotFoundError: No module named 'tomllib_missing'" in blocks
        assert is_attributed(blocks, "src/boostgauge/config.py")

    def test_the_full_suite_path_leads_with_the_cause(self):
        source = (
            Path(__file__).resolve().parents[2]
            / "assemblyzero" / "workflows" / "testing" / "nodes" / "verify_phases.py"
        ).read_text(encoding="utf-8")
        start = source.index("full_result = run_pytest([], repo_root=repo_root)")
        cause = source.index("collection_cause = collection_error_blocks(full_output)", start)
        routed = source.index('"test_failure_summary": regression_summary', start)
        assert cause < routed
        assert "nothing ran -- routing the cause to N4 (#2914)" in source


class TestAFileWithNothingToFixCanSaySo:
    """#2915: run 41's windows.py was named by the circular import and had
    nothing to change; its no-blocks answer regenerated it whole."""

    EXISTING = "import ctypes\n\n\nclass WindowsCollector:\n    pass\n"

    def test_a_no_edit_answer_keeps_the_file_byte_for_byte(self):
        outcome = apply_code_edit_script(
            "NO-EDIT: the circular import is closed in collector.py:114, not here",
            self.EXISTING,
        )

        assert outcome.ok
        assert outcome.code == self.EXISTING
        assert outcome.no_edit == "the circular import is closed in collector.py:114, not here"
        assert outcome.describe() == (
            "[EDIT-SCRIPT] no edits; the model says: the circular import is "
            "closed in collector.py:114, not here (#2915)"
        )

    def test_a_fenced_or_bare_declaration_counts(self):
        for response in ("```\nNO-EDIT: nothing here\n```", "no-edit nothing here", "NO-EDIT:"):
            outcome = apply_code_edit_script(response, self.EXISTING)
            assert outcome.ok and outcome.code == self.EXISTING, response

    def test_a_mention_inside_an_edit_block_is_not_a_declaration(self):
        response = (
            "<<<<<<< SEARCH\n    pass\n=======\n    # NO-EDIT: not really\n    pass\n>>>>>>> REPLACE\n"
        )

        outcome = apply_code_edit_script(response, self.EXISTING)

        assert outcome.no_edit is None
        assert outcome.blocks == 1

    def test_an_empty_answer_still_falls_back(self):
        outcome = apply_code_edit_script("", self.EXISTING)

        assert not outcome.ok
        assert outcome.no_edit is None
        assert "no edit blocks in response" in outcome.describe()

    def test_the_prompt_offers_the_answer(self):
        prompt = build_code_edit_script_prompt("src/x.py", self.EXISTING, "FAILED t::test_a")

        assert "NO-EDIT: <why>" in prompt
        assert "Never rewrite a file to have something to say" in prompt

    def test_the_outcome_type_carries_the_reason(self):
        assert EditScriptOutcome("x", no_edit="why").no_edit == "why"
        assert EditScriptOutcome("x").no_edit is None
