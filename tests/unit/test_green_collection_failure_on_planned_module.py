"""A collection failure on a symbol the plan owns goes to the implementer (#2893).

boostgauge #4, `run-issue4-012341` (2026-09-06 01:23), the first run with
#2888's named red-phase import. N2 emitted `from boostgauge.collector import
Band, CollectorThread, ProcessRow, WindowsCollector, _psutil_cmdline,
make_collector, normalize`; N4 wrote all five files; N5 ran:

    [N5] Results: 0 passed, 0 failed | Coverage: 0.0% | Exit: 2
    HALT -- Green phase stopped: pytest test execution interrupted (exit code 2).
    Imports that no longer resolve: boostgauge.collector._psutil_cmdline no longer exists

collector.py does not provide `_psutil_cmdline` (the implementation put it in
collectors/windows.py, as LLD-004 s2.6 says, and never re-exported it). The
named import fails at collection, pytest exits 2 without running the other
three files' 25 tests, and the #2035 branch ends the workflow. But this is
not #2035's regression -- a phase deleting a symbol an earlier phase
published -- it is a symbol of a file in files_to_modify, the loop's own
deliverable, with the module, the symbol and the path in pytest's message.
#2851's attribution hands exactly that to collector.py, and the edit script
adds the re-export. "No longer exists" described a symbol that never had.

Two changes, both tested here: the exit-2 branch routes to N4 when every
broken import is a planned file's, and the green phase runs pytest with
--continue-on-collection-errors so one uncollectable file does not silence
the rest.
"""

from __future__ import annotations

from unittest.mock import patch

from assemblyzero.workflows.testing.nodes import verify_phases
from assemblyzero.workflows.testing.nodes.implementation.edit_script_fix import (
    is_attributed,
)
from assemblyzero.workflows.testing.nodes.verify_phases import (
    collection_failures_the_plan_owns,
    plan_owned_collection_summary,
    run_pytest,
    verify_green_phase,
)

# What pytest printed on run 30, in its own shape.
RUN_30_OUTPUT = """\
==================== ERRORS ====================
____________ ERROR collecting tests/test_issue_4.py ____________
ImportError while importing test module 'C:\\Users\\mcwiz\\Projects\\boostgauge\\data\\worktrees\\4\\tests\\test_issue_4.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests\\test_issue_4.py:12: in <module>
    from boostgauge.collector import Band, CollectorThread, ProcessRow, WindowsCollector, _psutil_cmdline, make_collector, normalize  # noqa: F401
E   ImportError: cannot import name '_psutil_cmdline' from 'boostgauge.collector' (C:\\Users\\mcwiz\\Projects\\boostgauge\\data\\worktrees\\4\\src\\boostgauge\\collector.py)
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!
"""

# #2035's live case: a phase deleted symbols an EARLIER phase published.
REGRESSION_OUTPUT = """\
____________ ERROR collecting tests/unit/test_gauge.py ____________
tests/unit/test_gauge.py:13: in <module>
    from boostgauge.gauge import render
E   ImportError: cannot import name 'render' from 'boostgauge.gauge'
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!
"""

RUN_30_PLAN = [
    {"path": "src/boostgauge/collector.py", "change_type": "Add"},
    {"path": "src/boostgauge/collectors/windows.py", "change_type": "Add"},
    {"path": "tests/unit/test_collector.py", "change_type": "Add"},
    {"path": "tests/integration/test_windows_sweep_crosscheck.py", "change_type": "Add"},
    {"path": "tests/benchmark/test_sweep_cost.py", "change_type": "Add"},
]


def _exit_2(output: str) -> dict:
    return {
        "returncode": 2, "stdout": output, "stderr": "",
        "parsed": {"passed": 0, "failed": 0, "errors": 1, "coverage": 0},
    }


def _state(tmp_path, plan, **overrides) -> dict:
    state = {
        "repo_root": str(tmp_path),
        "issue_number": 4,
        "audit_dir": "",
        "test_files": ["tests/test_issue_4.py"],
        "implementation_files": [],
        "files_to_modify": plan,
        "coverage_target": 95,
        "iteration_count": 0,
        "max_iterations": 5,
        "skip_e2e": True,
    }
    state.update(overrides)
    return state


# =============================================================================
# Ownership
# =============================================================================


class TestOwnership:
    def test_run_30s_failure_is_owned_by_collector_py(self):
        owned, all_owned = collection_failures_the_plan_owns(RUN_30_OUTPUT, RUN_30_PLAN)

        assert owned == [("boostgauge.collector._psutil_cmdline", "src/boostgauge/collector.py")]
        assert all_owned is True

    def test_a_symbol_of_an_unplanned_module_is_not_owned(self):
        owned, all_owned = collection_failures_the_plan_owns(REGRESSION_OUTPUT, RUN_30_PLAN)

        assert owned == []
        assert all_owned is False

    def test_a_planned_module_that_was_never_written_is_owned(self):
        out = "E   ModuleNotFoundError: No module named 'boostgauge.collectors.windows'\n"

        owned, all_owned = collection_failures_the_plan_owns(out, RUN_30_PLAN)

        assert owned == [("boostgauge.collectors.windows", "src/boostgauge/collectors/windows.py")]
        assert all_owned is True

    def test_one_owned_and_one_not_is_not_all_owned(self):
        owned, all_owned = collection_failures_the_plan_owns(
            RUN_30_OUTPUT + REGRESSION_OUTPUT, RUN_30_PLAN,
        )

        assert [item for item, _ in owned] == ["boostgauge.collector._psutil_cmdline"]
        assert all_owned is False

    def test_the_parent_package_is_not_owned_by_a_child_file(self):
        """`boostgauge` failing to import is not collector.py's to repair."""
        out = "E   ModuleNotFoundError: No module named 'boostgauge'\n"

        assert collection_failures_the_plan_owns(out, RUN_30_PLAN) == ([], False)

    def test_no_failures_is_nothing_owned(self):
        assert collection_failures_the_plan_owns("3 passed", RUN_30_PLAN) == ([], False)

    def test_no_plan_owns_nothing(self):
        assert collection_failures_the_plan_owns(RUN_30_OUTPUT, []) == ([], False)


# =============================================================================
# The route
# =============================================================================


class TestTheRoute:
    def test_run_30_now_goes_to_the_implementer(self, tmp_path, capsys):
        with patch.object(verify_phases, "run_pytest", return_value=_exit_2(RUN_30_OUTPUT)):
            result = verify_green_phase(_state(tmp_path, RUN_30_PLAN))

        assert result["next_node"] == "N4_implement_code"
        assert result["iteration_count"] == 1
        assert result["error_message"] == ""
        assert (
            "[N5] collection failed on a symbol the plan owns: "
            "boostgauge.collector._psutil_cmdline -- handing it to the implementer (#2893)"
        ) in capsys.readouterr().out

    def test_the_summary_names_the_module_the_symbol_and_the_path(self, tmp_path):
        with patch.object(verify_phases, "run_pytest", return_value=_exit_2(RUN_30_OUTPUT)):
            result = verify_green_phase(_state(tmp_path, RUN_30_PLAN))

        summary = result["test_failure_summary"]
        assert "tests/test_issue_4.py imports `_psutil_cmdline` from boostgauge.collector (src/boostgauge/collector.py)" in summary
        assert "Provide `_psutil_cmdline` in src/boostgauge/collector.py" in summary
        assert "cannot import name '_psutil_cmdline' from 'boostgauge.collector'" in summary
        assert "do not edit it" in summary

    def test_the_summary_attributes_to_collector_py_and_to_nothing_else(self, tmp_path):
        """#2851 attributes per block; the summary is one block naming one file."""
        summary = plan_owned_collection_summary(
            [("boostgauge.collector._psutil_cmdline", "src/boostgauge/collector.py")],
            RUN_30_OUTPUT,
        )

        assert is_attributed(summary, "src/boostgauge/collector.py")
        assert not is_attributed(summary, "src/boostgauge/collectors/windows.py")
        assert not is_attributed(summary, "tests/unit/test_collector.py")
        assert not is_attributed(summary, "tests/benchmark/test_sweep_cost.py")

    def test_a_never_written_module_says_write_it(self):
        summary = plan_owned_collection_summary(
            [("boostgauge.collectors.windows", "src/boostgauge/collectors/windows.py")],
            "E   ModuleNotFoundError: No module named 'boostgauge.collectors.windows'\n",
        )

        assert "Write src/boostgauge/collectors/windows.py as the plan says" in summary

    def test_a_regression_outside_the_plan_still_halts_as_2035(self, tmp_path, capsys):
        with patch.object(verify_phases, "run_pytest", return_value=_exit_2(REGRESSION_OUTPUT)):
            result = verify_green_phase(_state(tmp_path, RUN_30_PLAN))

        assert result["next_node"] == "end"
        assert "boostgauge.gauge.render" in result["error_message"]
        assert "no longer resolve" in result["error_message"]
        assert "#2893" not in capsys.readouterr().out

    def test_a_mixed_failure_still_halts(self, tmp_path):
        with patch.object(
            verify_phases, "run_pytest",
            return_value=_exit_2(RUN_30_OUTPUT + REGRESSION_OUTPUT),
        ):
            result = verify_green_phase(_state(tmp_path, RUN_30_PLAN))

        assert result["next_node"] == "end"

    def test_without_a_plan_the_halt_is_unchanged(self, tmp_path):
        with patch.object(verify_phases, "run_pytest", return_value=_exit_2(RUN_30_OUTPUT)):
            result = verify_green_phase(_state(tmp_path, []))

        assert result["next_node"] == "end"
        assert "boostgauge.collector._psutil_cmdline" in result["error_message"]

    def test_an_internal_error_is_never_routed(self, tmp_path):
        """Exit 3 is pytest's own crash; only exit 2 is a collection failure."""
        crashed = dict(_exit_2(RUN_30_OUTPUT), returncode=3)
        with patch.object(verify_phases, "run_pytest", return_value=crashed):
            result = verify_green_phase(_state(tmp_path, RUN_30_PLAN))

        assert result["next_node"] == "end"


# =============================================================================
# The suite keeps running past one broken file
# =============================================================================


class TestContinueOnCollectionErrors:
    def _completed(self):
        import subprocess
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="1 passed", stderr="")

    def test_run_pytest_passes_the_flag_when_asked(self):
        seen: list[list[str]] = []

        def record(cmd, **kwargs):
            seen.append(list(cmd))
            return self._completed()

        with patch.object(verify_phases, "run_command", record):
            run_pytest(["tests/test_a.py"], continue_on_collection_errors=True)
            run_pytest(["tests/test_a.py"])

        assert "--continue-on-collection-errors" in seen[0]
        assert "--continue-on-collection-errors" not in seen[1], (
            "the red phase keeps pytest's default: a collection error IS its signal"
        )

    def test_the_green_phase_asks_for_it(self, tmp_path):
        with patch.object(
            verify_phases, "run_pytest", return_value=_exit_2(RUN_30_OUTPUT),
        ) as mock_pytest:
            verify_green_phase(_state(tmp_path, RUN_30_PLAN))

        assert mock_pytest.call_args.kwargs.get("continue_on_collection_errors") is True


# What pytest printed on run 31 (`run-issue4-013300`), once the flag let the
# other three files run: 25 passed, one file uncollectable, exit 1. The short
# summary names the file and nothing else; the cause is in the ERRORS section
# that the traceback extractor never reads.
RUN_31_OUTPUT = """\
tests/unit/test_collector.py::test_req_6_cmdline_access_denied_handled PASSED
tests/benchmark/test_sweep_cost.py::test_full_collect_tick_is_under_one_percent_of_a_core PASSED
==================== ERRORS ====================
____________ ERROR collecting tests/test_issue_4.py ____________
ImportError while importing test module 'C:\\Users\\mcwiz\\Projects\\boostgauge\\data\\worktrees\\4\\tests\\test_issue_4.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests\\test_issue_4.py:12: in <module>
    from boostgauge.collector import Band, CollectorThread, ProcessRow, WindowsCollector, _psutil_cmdline, make_collector, normalize  # noqa: F401
E   ImportError: cannot import name '_psutil_cmdline' from 'boostgauge.collector' (C:\\Users\\mcwiz\\Projects\\boostgauge\\data\\worktrees\\4\\src\\boostgauge\\collector.py)
---------- coverage: platform win32, python 3.14.7-final-0 ----------
Name                                   Stmts   Miss  Cover   Missing
--------------------------------------------------------------------
src\\boostgauge\\collector.py               82      6    93%   56-58, 63, 96, 106
src\\boostgauge\\collectors\\windows.py     119     11    91%   86, 153-158, 165-166, 198-199
--------------------------------------------------------------------
TOTAL                                    201     17    91%
FAIL Required test coverage of 95% not reached. Total coverage: 91.54%
==================== short test summary info ====================
ERROR tests/test_issue_4.py
==================== 25 passed, 1 error in 0.64s ====================
"""


class TestExitOneWithAnUncollectableFile:
    """The flag's other half: the run that reached N4 with nothing to go on."""

    def _exit_1(self) -> dict:
        return {
            "returncode": 1, "stdout": RUN_31_OUTPUT, "stderr": "",
            "parsed": {"passed": 25, "failed": 0, "errors": 1, "coverage": 91.0},
        }

    def test_the_repair_task_leads_the_failure_summary(self, tmp_path, capsys):
        with patch.object(verify_phases, "run_pytest", return_value=self._exit_1()):
            result = verify_green_phase(_state(tmp_path, RUN_30_PLAN))

        assert result["next_node"] == "N4_implement_code"
        summary = result["test_failure_summary"]
        assert summary.startswith("Collection failed on a symbol this plan owns (#2893)")
        assert "Provide `_psutil_cmdline` in src/boostgauge/collector.py" in summary
        assert "cannot import name '_psutil_cmdline' from 'boostgauge.collector'" in summary
        assert (
            "[N5] collection failed on a symbol the plan owns: "
            "boostgauge.collector._psutil_cmdline -- carried in the repair task (#2893)"
        ) in capsys.readouterr().out

    def test_the_task_attributes_to_collector_py_alone(self, tmp_path):
        with patch.object(verify_phases, "run_pytest", return_value=self._exit_1()):
            result = verify_green_phase(_state(tmp_path, RUN_30_PLAN))

        summary = result["test_failure_summary"]
        assert is_attributed(summary, "src/boostgauge/collector.py")
        assert not is_attributed(summary, "src/boostgauge/collectors/windows.py")
        assert not is_attributed(summary, "tests/benchmark/test_sweep_cost.py")

    def test_the_short_summary_still_follows(self, tmp_path):
        """The task is prefixed; nothing #498 collected is lost."""
        with patch.object(verify_phases, "run_pytest", return_value=self._exit_1()):
            result = verify_green_phase(_state(tmp_path, RUN_30_PLAN))

        assert "ERROR tests/test_issue_4.py" in result["test_failure_summary"]

    def test_an_unowned_collection_error_adds_no_task(self, tmp_path, capsys):
        unowned = dict(self._exit_1(), stdout=RUN_31_OUTPUT.replace(
            "from 'boostgauge.collector'", "from 'boostgauge.gauge'",
        ))
        with patch.object(verify_phases, "run_pytest", return_value=unowned):
            result = verify_green_phase(_state(tmp_path, RUN_30_PLAN))

        assert "#2893" not in result["test_failure_summary"]
        assert "#2893" not in capsys.readouterr().out
