"""A Jest, Vitest or Playwright suite that collects zero tests is a collection
failure, never a coverage shortfall (#3085).

#2546 refused that reading on the pytest path: zero collected is not a pass
and not a coverage gap; the first time it is a named repair task, the second
time it halts. `_verify_green_non_pytest` had no such guard, so a suite that
collected nothing (0 passed, 0 failed, 0 errors) fell through to the coverage
branch, read 0.0 % against the target, and sent the implementer to add
coverage to a suite that cannot load.

The guard is now one helper both branches call, so there is nowhere for the
two to disagree.
"""

from __future__ import annotations

import inspect
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    TestFramework,
)
from assemblyzero.workflows.testing.nodes import verify_phases
from assemblyzero.workflows.testing.nodes.verify_phases import _verify_green_non_pytest

pytestmark = pytest.mark.usefixtures("coverage_as_reported")  # #4436: routing, not measuring

VERIFY = "assemblyzero.workflows.testing.nodes.verify_phases"
VITEST = {"framework": "vitest", "coverage_type": "line", "working_directory": "web"}

#: What Vitest prints when its config cannot load: nothing collected.
COLLECTION_OUTPUT = (
    "failed to load config from web/vitest.config.ts\n"
    "Error: Cannot find module '@vitejs/plugin-react'\n"
)


def _empty_run() -> dict:
    return {
        "passed": 0, "failed": 0, "skipped": 0, "errors": 0, "total": 0,
        "coverage_percent": 0.0, "coverage_type": CoverageType.LINE,
        "raw_output": COLLECTION_OUTPUT, "exit_code": 1,
        "framework": TestFramework.VITEST,
    }


def _state(tmp_path, **overrides) -> dict:
    state = {
        "test_files": [str(tmp_path / "web" / "tests" / "a.test.ts")],
        "repo_root": str(tmp_path), "issue_number": 3085,
        "coverage_target": 90, "iteration_count": 0, "max_iterations": 5,
        "total_scenarios": 3, "audit_dir": "", "file_counter": 0,
        "framework_config": VITEST,
    }
    state.update(overrides)
    return state


def _green(state) -> dict:
    runner = MagicMock()
    runner.run_tests.return_value = _empty_run()
    with patch(f"{VERIFY}.get_runner", return_value=runner):
        return _verify_green_non_pytest(state, VITEST, TestFramework.VITEST)


class TestZeroCollectedIsACollectionFailure:
    def test_the_first_zero_is_a_named_repair_not_a_coverage_gap(self, tmp_path, capsys):
        result = _green(_state(tmp_path))
        printed = capsys.readouterr().out

        assert result["next_node"] == "N4_implement_code"
        assert result["zero_collected_strikes"] == 1
        assert result["error_message"] == ""
        assert "vitest collected 0 tests" in result["test_failure_summary"]
        assert "Cannot find module" in result["test_failure_summary"], (
            "the collection error travels as the repair task"
        )
        assert "collection is broken" in printed
        assert "Coverage" not in result["test_failure_summary"]

    def test_the_second_zero_halts_naming_the_error(self, tmp_path):
        result = _green(_state(tmp_path, zero_collected_strikes=1, iteration_count=1))

        assert result["next_node"] == "end"
        assert "vitest collected 0 tests on 2 iterations" in result["error_message"]
        assert "Cannot find module" in result["error_message"]
        assert "coverage 0.0%" not in result["error_message"], (
            "never the coverage shortfall the fall-through used to report"
        )

    def test_at_the_iteration_cap_it_is_still_a_collection_failure(self, tmp_path):
        """The coverage branch's cap message was `coverage 0.0% < target 90%`."""
        result = _green(_state(tmp_path, iteration_count=4))
        assert "coverage 0.0%" not in (result["error_message"] + result.get("test_failure_summary", ""))
        assert result["zero_collected_strikes"] == 1


def test_both_branches_call_the_one_guard():
    """#3085: the guard is a property of a test run, so both green branches
    call the same helper and neither keeps a copy."""
    for branch in (verify_phases._verify_green_pytest_single, _verify_green_non_pytest):
        source = inspect.getsource(branch)
        assert "_zero_collected_route(" in source, branch.__name__
        assert "zero_collected_strikes" not in source, (
            f"{branch.__name__} keeps its own copy of the strike counting"
        )
