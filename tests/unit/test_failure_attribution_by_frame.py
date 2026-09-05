"""A file's fix prompt carries the failures that file owns (#2851).

`run-issue4-120049`, green-loop iteration 1, six files. Every file's edit-script
prompt carried all four failures under "Fix ALL the failures listed below."
The one file that owned three of the fixes took 168 s; the files that could
not do what they were told took 2,022 s, 1,594 s and 1,968 s -- 100k tokens
of deliberation each, for 1.7 KB patches.

Attribution (`failures_for_file`) existed and never matched, for two reasons
that compound:

* `_extract_traceback_blocks` kept "the last non-blank line before the E
  lines" as the source line. On Python 3.11+ that line is the caret underline
  (`    ^^^^^^^`), not the code. And it never kept the FRAME line --
  `src\\boostgauge\\collector.py:116: in _is_unleashed_session` -- which is the
  only line in the block that names the file that raised.
* `failures_for_file` filtered line by line against forward-slash tokens, and
  Windows frames carry backslashes.

The fixtures below are pytest's real output from that run, trimmed. The tests
run the real summariser over it and the real attribution over the summary,
so the claim "collector.py owns test_req_4 and windows.py owns nothing here"
is measured on the shape that failed, not on a shape invented to pass.
"""

from unittest.mock import patch

import pytest

from assemblyzero.workflows.testing.nodes import verify_phases
from assemblyzero.workflows.testing.nodes.implementation import edit_script_fix
from assemblyzero.workflows.testing.nodes.implementation.edit_script_fix import (
    build_code_edit_script_prompt,
    failures_for_file,
    is_attributed,
)

# pytest --tb=short, Python 3.14, Windows paths. Verbatim from
# docs/lineage/active/4-testing/007-green-phase.txt of run-issue4-120049,
# trimmed to two failures and the summary.
PYTEST_OUTPUT = """\
============================= test session starts =============================
collected 12 items

tests/test_issue_4.py::test_req_4 FAILED                                 [ 33%]
tests/test_issue_4.py::test_req_7 FAILED                                 [ 58%]

================================== FAILURES ===================================
__________________________________ test_req_4 __________________________________
tests\\test_issue_4.py:71: in test_req_4
    assert collector._is_unleashed_session("python.exe", 12345)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
src\\boostgauge\\collector.py:116: in _is_unleashed_session
    return "unleashed" in name or "unleashed" in cmdline_str
                                  ^^^^^^^^^^^^^^^^^^^^^^^^^^
E   TypeError: argument of type 'int' is not a container or iterable
__________________________________ test_req_7 __________________________________
tests\\test_issue_4.py:100: in test_req_7
    assert len(calls) == 1
E   assert 0 == 1
E    +  where 0 = len([])
=========================== short test summary info ===========================
FAILED tests/test_issue_4.py::test_req_4 - TypeError: argument of type 'int' is not a container or iterable
FAILED tests/test_issue_4.py::test_req_7 - assert 0 == 1
========================= 2 failed, 10 passed in 5.85s =========================
"""


@pytest.fixture
def summary():
    return verify_phases._build_failure_summary(PYTEST_OUTPUT)


class TestTheSummaryCarriesTheFrame:
    def test_the_innermost_frame_is_kept_with_forward_slashes(self, summary):
        assert "src/boostgauge/collector.py:116: in _is_unleashed_session" in summary

    def test_the_source_line_is_code_not_carets(self, summary):
        assert 'return "unleashed" in name or "unleashed" in cmdline_str' in summary
        for line in summary.splitlines():
            stripped = line.strip()
            assert not (stripped and set(stripped) <= {"^"}), (
                f"a caret underline survived as a 'source line': {line!r}"
            )

    def test_a_frame_less_block_still_keeps_its_source_line(self, summary):
        """test_req_7 raises in the test itself; the test frame is its
        innermost frame and the assertion is its source line."""
        assert "tests/test_issue_4.py:100: in test_req_7" in summary
        assert "assert len(calls) == 1" in summary

    def test_the_error_lines_are_unchanged(self, summary):
        assert "E   TypeError: argument of type 'int' is not a container or iterable" in summary
        assert "E    +  where 0 = len([])" in summary


class TestAttributionOnTheRealShape:
    def test_the_implementation_file_that_raised_is_attributed(self, summary):
        assert is_attributed(summary, "src/boostgauge/collector.py")

    def test_a_file_no_failure_names_is_not(self, summary):
        assert not is_attributed(summary, "src/boostgauge/collectors/windows.py")
        assert not is_attributed(summary, "tests/integration/test_windows_collector.py")
        assert not is_attributed(summary, "tests/benchmark/test_windows_collector_bench.py")

    def test_the_scoped_corpus_keeps_whole_blocks(self, summary):
        scoped = failures_for_file(summary, "src/boostgauge/collector.py")
        # The frame, its source line and its error travel together.
        assert "src/boostgauge/collector.py:116: in _is_unleashed_session" in scoped
        assert 'return "unleashed" in name' in scoped
        assert "E   TypeError" in scoped
        # And the failure this file does not own is gone.
        assert "test_req_7" not in scoped

    def test_the_test_file_owning_a_failure_is_attributed(self, summary):
        """test_req_7 raises inside tests/test_issue_4.py; the stem token
        `test_issue_4` names it, so a plan that lists that file gets it."""
        assert is_attributed(summary, "tests/test_issue_4.py")

    def test_an_unattributable_corpus_is_still_passed_through_whole(self):
        corpus = "1 test(s): AssertionError\n    e.g. tests/test_x.py::test_y"
        assert failures_for_file(corpus, "src/boostgauge/collector.py") == corpus
        assert not is_attributed(corpus, "src/boostgauge/collector.py")

    def test_windows_backslashes_in_the_corpus_match_forward_slash_tokens(self):
        corpus = (
            "test_a\n"
            "    src\\pkg\\mod.py:3: in f\n"
            "    raise ValueError\n"
            "    E   ValueError"
        )
        assert is_attributed(corpus, "src/pkg/mod.py")


class TestThePromptNoLongerOrdersEverythingFixed:
    def test_the_rule_is_scoped_to_this_files_failures(self):
        prompt = build_code_edit_script_prompt("src/x.py", "x = 1\n", "E   boom")
        assert "Fix ALL the failures" not in prompt
        assert "that this file is responsible for" in prompt


class TestTheLoopLeavesUnattributedFilesAlone:
    """The consequence: with the corpus naming collector.py, windows.py is
    not called at all. Driven through `implement_code` with the model calls
    stubbed, so what is asserted is the decision, not the model."""

    def _run(self, tmp_path, summary, capsys):
        from assemblyzero.workflows.testing.nodes.implementation import orchestrator

        (tmp_path / "src" / "boostgauge" / "collectors").mkdir(parents=True)
        big = "# " + ("x" * 900) + "\n"  # over MIN_BYTES_FOR_EDIT_SCRIPT
        (tmp_path / "src" / "boostgauge" / "collector.py").write_text(big, encoding="utf-8")
        (tmp_path / "src" / "boostgauge" / "collectors" / "windows.py").write_text(big, encoding="utf-8")

        called: list[str] = []

        def fake_edit(filepath, **kwargs):
            called.append(filepath)
            return edit_script_fix.EditScriptOutcome(
                kwargs["existing_content"], failures=[]
            )

        state = {
            "repo_root": str(tmp_path),
            "lld_content": "## 2.1 Files\n",
            "files_to_modify": [
                {"path": "src/boostgauge/collector.py", "change_type": "Modify"},
                {"path": "src/boostgauge/collectors/windows.py", "change_type": "Modify"},
            ],
            "test_files": ["tests/test_issue_4.py"],
            "iteration_count": 1,
            "test_failure_summary": summary,
            "audit_dir": str(tmp_path / "audit"),
        }
        with patch.object(orchestrator, "try_edit_script_fix", fake_edit), \
             patch.object(orchestrator, "generate_file_with_retry",
                          side_effect=AssertionError("full regeneration must not run")), \
             patch.object(orchestrator, "validate_files_to_modify", return_value=[]), \
             patch.object(orchestrator, "record_iteration_cost", return_value=0), \
             patch.object(orchestrator, "get_cumulative_cost", return_value=0.0):
            try:
                orchestrator.implement_code(state)
            except Exception:
                # Later bookkeeping in the node is not under test; the per-file
                # decisions have been made and recorded by the time it runs.
                pass
        return called, capsys.readouterr().out

    def test_only_the_attributed_file_is_sent_for_a_fix(self, tmp_path, summary, capsys):
        called, out = self._run(tmp_path, summary, capsys)

        assert called == ["src/boostgauge/collector.py"], called
        assert "no failure attributed to src/boostgauge/collectors/windows.py" in out
        assert "failures attributed to 1 of 2 file(s)" in out
