"""pytest_runner.py under standard 0034, one test per sweep site (#3585).

The pytest runner never read pytest's exit code: a run that was interrupted
or stopped at collection (2), hit an internal error (3), was given a bad
command line (4) or collected nothing (5) came back as counts read off its
output, which for most of those is zero of everything -- a run that tested
nothing, read as one where nothing failed. Those codes now raise
`RunnerError` naming the code, what pytest means by it and the head of the
output, after an ERROR line. A run with no coverage table read 0% coverage;
it now reads None, not measured, as the Jest runner does (#4246).

`_run_subprocess` is stood in for: nothing real is run. Line numbers in the
names are ledger 0908's, at its base `79e18ad1`.
"""
from __future__ import annotations

import pytest

from assemblyzero.workflows.testing.framework_detector import TestFramework
from assemblyzero.workflows.testing.runner_registry import get_framework_config
from assemblyzero.workflows.testing.runners.pytest_runner import PytestRunner


def _runner(tmp_path) -> PytestRunner:
    return PytestRunner(get_framework_config(TestFramework.PYTEST), str(tmp_path))


def _assert_runner_error(excinfo, *needles: str) -> None:
    assert type(excinfo.value).__name__ == "RunnerError", (
        f"expected RunnerError, got {type(excinfo.value).__name__}: {excinfo.value}"
    )
    for needle in needles:
        assert needle in str(excinfo.value)


class TestTheExitCode:
    @pytest.mark.parametrize(("code", "meaning"), [
        (2, "interrupted"),
        (3, "internal error"),
        (4, "usage error"),
        (5, "no tests collected"),
    ])
    def test_45_a_run_pytest_did_not_finish_raises(self, tmp_path, monkeypatch, capsys, code, meaning):
        runner = _runner(tmp_path)
        monkeypatch.setattr(
            runner, "_run_subprocess",
            lambda command, timeout=300, cwd=None: ("", "INTERNALERROR> boom", code),
        )

        with pytest.raises(Exception) as excinfo:
            runner.run_tests(test_paths=["tests/test_a.py"])

        _assert_runner_error(excinfo, f"exit {code}", meaning, "INTERNALERROR> boom", str(tmp_path))
        assert "ERROR" in capsys.readouterr().err

    def test_45_a_collection_error_is_not_read_as_counts(self, tmp_path):
        output = (
            "ERROR tests/test_a.py - ModuleNotFoundError: No module named 'x'\n"
            "Interrupted: 1 error during collection\n"
        )
        with pytest.raises(Exception) as excinfo:
            _runner(tmp_path).parse_results(output, 2)

        _assert_runner_error(excinfo, "exit 2", "No module named 'x'")

    @pytest.mark.parametrize("code", [0, 1])
    def test_a_run_that_finished_is_read(self, tmp_path, operator_alerts, code):
        """Kept: exit 0 (all passed) and 1 (some failed) are runs, read
        quietly from the summary line."""
        result = _runner(tmp_path).parse_results("3 passed, 1 failed in 0.2s", code)

        assert (result["passed"], result["failed"], result["exit_code"]) == (3, 1, code)
        assert operator_alerts == []


class TestCoverage:
    def test_57_no_coverage_table_is_not_measured(self, tmp_path):
        result = _runner(tmp_path).parse_results("5 passed in 0.5s", 0)

        assert result["coverage_percent"] is None

    def test_a_coverage_table_is_read(self, tmp_path):
        """Kept: a run that printed pytest-cov's TOTAL row reports it."""
        result = _runner(tmp_path).parse_results(
            "5 passed in 0.5s\nTOTAL    150     12    92%\n", 0,
        )

        assert result["coverage_percent"] == 92.0
