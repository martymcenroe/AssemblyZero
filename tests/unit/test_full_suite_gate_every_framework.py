"""The full-suite regression gate runs for every framework, and
`full_suite_validated` always carries a measured value (#3087).

#842's gate lived in the pytest green phase alone. `_verify_green_non_pytest`
graded a Jest, Vitest or Playwright run on the files it had just written and
went to E2E and finalisation without anything running the rest of the suite,
and never wrote `full_suite_validated`. A suite that collected nothing read
as clean on the pytest side too, which is a pass that cannot be told from a
skip.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    TestFramework,
)
from assemblyzero.workflows.testing.nodes.verify_phases import (
    _verify_green_non_pytest,
    verify_green_phase,
)

VERIFY = "assemblyzero.workflows.testing.nodes.verify_phases"
VITEST = {"framework": "vitest", "coverage_type": "line", "working_directory": "web"}


def _result(passed: int, failed: int = 0, errors: int = 0, coverage: float = 95.0,
            output: str = "") -> dict:
    return {
        "passed": passed, "failed": failed, "skipped": 0, "errors": errors,
        "total": passed + failed + errors, "coverage_percent": coverage,
        "coverage_type": CoverageType.LINE,
        "raw_output": output or f"{passed} passed, {failed} failed",
        "exit_code": 1 if (failed or errors) else 0,
        "framework": TestFramework.VITEST,
    }


def _runner(targeted: dict, full: dict) -> MagicMock:
    """A runner whose whole-suite call (no test paths) answers `full`."""
    runner = MagicMock()
    runner.run_tests.side_effect = (
        lambda test_paths=None, extra_args=None: full if not test_paths else targeted
    )
    return runner


def _state(tmp_path, **overrides) -> dict:
    state = {
        "test_files": [str(tmp_path / "web" / "tests" / "a.test.ts")],
        "repo_root": str(tmp_path),
        "issue_number": 3087,
        "coverage_target": 90,
        "iteration_count": 0,
        "max_iterations": 5,
        "total_scenarios": 3,
        "audit_dir": "",
        "file_counter": 0,
        "framework_config": VITEST,
    }
    state.update(overrides)
    return state


class TestTheGateRunsForVitest:
    def test_a_green_vitest_run_runs_the_whole_suite_and_records_it(self, tmp_path):
        runner = _runner(_result(3), _result(40))
        with patch(f"{VERIFY}.get_runner", return_value=runner):
            result = _verify_green_non_pytest(_state(tmp_path), VITEST, TestFramework.VITEST)

        calls = [c.kwargs.get("test_paths") for c in runner.run_tests.call_args_list]
        assert None in calls, "the whole suite ran, with no test paths"
        assert result["full_suite_validated"] is True
        assert result["full_suite_regressions"] == []
        assert result["next_node"] == "N6_e2e_validation"

    def test_skip_e2e_still_runs_the_gate(self, tmp_path):
        runner = _runner(_result(3), _result(40))
        with patch(f"{VERIFY}.get_runner", return_value=runner):
            result = _verify_green_non_pytest(
                _state(tmp_path, skip_e2e=True), VITEST, TestFramework.VITEST,
            )
        assert result["next_node"] == "N7_finalize"
        assert result["full_suite_validated"] is True

    def test_a_regression_outside_the_targeted_files_routes_to_n4(self, tmp_path):
        runner = _runner(_result(3), _result(38, failed=2, output="FAIL tests/old.test.ts"))
        with patch(f"{VERIFY}.get_runner", return_value=runner):
            result = _verify_green_non_pytest(_state(tmp_path), VITEST, TestFramework.VITEST)

        assert result["full_suite_validated"] is False
        assert result["next_node"] == "N4_implement_code"
        assert result["error_message"] == ""
        assert "tests/old.test.ts" in result["test_failure_summary"]
        assert result["full_suite_repair_passes"] == 1

    def test_a_whole_suite_that_collects_nothing_halts(self, tmp_path):
        runner = _runner(_result(3), _result(0))
        with patch(f"{VERIFY}.get_runner", return_value=runner):
            result = _verify_green_non_pytest(_state(tmp_path), VITEST, TestFramework.VITEST)

        assert result["full_suite_validated"] is False
        assert "collected 0 tests" in result["error_message"]
        assert "vitest (web)" in result["error_message"]

    def test_an_already_validated_suite_is_not_run_again(self, tmp_path):
        runner = _runner(_result(3), _result(40))
        with patch(f"{VERIFY}.get_runner", return_value=runner):
            result = _verify_green_non_pytest(
                _state(tmp_path, full_suite_validated=True), VITEST, TestFramework.VITEST,
            )
        calls = [c.kwargs.get("test_paths") for c in runner.run_tests.call_args_list]
        assert None not in calls
        assert result["full_suite_validated"] is True


class TestThePytestGateCannotPassOnNothing:
    def test_a_pytest_whole_suite_that_collects_nothing_halts(self, tmp_path):
        test_file = tmp_path / "tests" / "test_x.py"
        test_file.parent.mkdir()
        test_file.write_text("def test_x():\n    assert True\n", encoding="utf-8")

        def fake_run_pytest(test_files, **kwargs):
            passed = 0 if not test_files else 1
            return {
                "returncode": 5 if not test_files else 0,
                "stdout": "no tests ran" if not test_files else "1 passed",
                "stderr": "",
                "parsed": {"passed": passed, "failed": 0, "errors": 0, "coverage": 100.0},
            }

        state = {
            "repo_root": str(tmp_path), "issue_number": 3087, "audit_dir": "",
            "test_files": [str(test_file)], "implementation_files": [],
            "files_to_modify": [], "coverage_target": 90, "iteration_count": 0,
            "framework_config": {"framework": "pytest"},
        }
        with patch(f"{VERIFY}.run_pytest", side_effect=fake_run_pytest):
            result = verify_green_phase(state)

        assert result["full_suite_validated"] is False
        assert "collected 0 tests" in result["error_message"]
        assert "pytest" in result["error_message"]


@pytest.mark.parametrize("cause", [OSError("npx not found on PATH"),
                                   ValueError("Unsupported framework")])
def test_a_gate_whose_runner_cannot_start_halts(tmp_path, cause):
    runner = _runner(_result(3), _result(40))
    calls = {"n": 0}

    def get_runner(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] > 1:
            raise cause
        return runner

    with patch(f"{VERIFY}.get_runner", side_effect=get_runner):
        result = _verify_green_non_pytest(_state(tmp_path), VITEST, TestFramework.VITEST)

    assert result["full_suite_validated"] is False
    assert "cannot run" in result["error_message"]
    assert str(cause) in result["error_message"]
