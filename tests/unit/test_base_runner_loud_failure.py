"""base_runner.py under standard 0034, one test per sweep site (#3585).

Every runner starts its test command through `_run_subprocess`. A command
that timed out, was not found or could not be started came back as exit code
-1 with the cause where stderr would be, and an ERROR line that named neither
the framework nor the directory; the runners then parsed that as a run, so a
suite that never started was read as one that failed. It now raises
`RunnerError` naming the framework, the command, the directory and the cause,
after an ERROR line. Scenario coverage with no scenarios was 0.0 with a
WARNING, read as a measured 0%; it now raises ValueError after an ERROR line.

`base_runner.run_command` is stood in for: nothing real is run. Line numbers
in the names are ledger 0908's, at its base `79e18ad1`.
"""
from __future__ import annotations

import subprocess

import pytest

from assemblyzero.workflows.testing.framework_detector import TestFramework
from assemblyzero.workflows.testing.runner_registry import get_framework_config
from assemblyzero.workflows.testing.runners import base_runner


class _Runner(base_runner.BaseTestRunner):
    """The base class's behaviour, with nothing of its own."""

    def run_tests(self, test_paths=None, extra_args=None, *, measure_coverage=False):
        raise NotImplementedError

    def parse_results(self, raw_output, exit_code, stderr=""):
        raise NotImplementedError

    def validate_test_file(self, file_path, content):
        return []

    def get_scaffold_imports(self):
        return ""


def _runner(tmp_path, framework=TestFramework.PLAYWRIGHT) -> _Runner:
    return _Runner(get_framework_config(framework), str(tmp_path))


def _raising(exc: BaseException):
    def run_command(command, **kwargs):
        raise exc
    return run_command


def _assert_runner_error(excinfo, *needles: str) -> None:
    assert type(excinfo.value).__name__ == "RunnerError", (
        f"expected RunnerError, got {type(excinfo.value).__name__}: {excinfo.value}"
    )
    for needle in needles:
        assert needle in str(excinfo.value)


class TestScenarioCoverage:
    def test_96_no_scenarios_raises_and_is_loud(self, tmp_path, capsys):
        runner = _runner(tmp_path)
        result = {"passed": 3}

        with pytest.raises(ValueError, match="no scenarios"):
            runner.compute_scenario_coverage(result, 0)

        assert "ERROR" in capsys.readouterr().err

    def test_96_a_negative_count_raises(self, tmp_path):
        with pytest.raises(ValueError, match="no scenarios"):
            _runner(tmp_path).compute_scenario_coverage({"passed": 0}, -1)

    def test_scenario_coverage_is_passed_over_total(self, tmp_path, operator_alerts):
        """Kept: with scenarios, coverage is passed / total, quietly."""
        assert _runner(tmp_path).compute_scenario_coverage({"passed": 3}, 4) == 0.75
        assert operator_alerts == []


class TestTheCommand:
    def test_129_a_timeout_raises_naming_the_framework_command_and_directory(
        self, tmp_path, monkeypatch, capsys,
    ):
        monkeypatch.setattr(
            base_runner, "run_command",
            _raising(subprocess.TimeoutExpired(["npx", "playwright", "test"], 300)),
        )

        with pytest.raises(Exception) as excinfo:
            _runner(tmp_path)._run_subprocess(["npx", "playwright", "test"])

        _assert_runner_error(
            excinfo, "playwright", "npx playwright test", str(tmp_path), "timed out after 300s",
        )
        assert isinstance(excinfo.value.__cause__, subprocess.TimeoutExpired)
        err = capsys.readouterr().err
        assert "ERROR" in err and "npx playwright test" in err

    def test_132_a_missing_command_raises(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(
            base_runner, "run_command",
            _raising(FileNotFoundError(2, "No such file or directory", "npx")),
        )

        with pytest.raises(Exception) as excinfo:
            _runner(tmp_path, TestFramework.JEST)._run_subprocess(["npx", "jest", "--json"])

        _assert_runner_error(excinfo, "jest", "npx jest --json", str(tmp_path), "not found")
        assert isinstance(excinfo.value.__cause__, FileNotFoundError)
        assert "ERROR" in capsys.readouterr().err

    def test_135_an_os_error_raises(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(
            base_runner, "run_command", _raising(PermissionError(13, "Permission denied")),
        )

        with pytest.raises(Exception) as excinfo:
            _runner(tmp_path, TestFramework.VITEST)._run_subprocess(["npx", "vitest", "run"])

        _assert_runner_error(excinfo, "vitest", "npx vitest run", "PermissionError")
        assert isinstance(excinfo.value.__cause__, PermissionError)
        assert "ERROR" in capsys.readouterr().err

    def test_a_command_that_ran_returns_its_streams_and_code(
        self, tmp_path, monkeypatch, operator_alerts,
    ):
        """Kept: a command that ran, whatever its exit code, comes back as
        (stdout, stderr, exit code), quietly; the runner reads the code."""
        monkeypatch.setattr(
            base_runner, "run_command",
            lambda command, **kw: subprocess.CompletedProcess(command, 3, "out", "err"),
        )

        assert _runner(tmp_path)._run_subprocess(["npx", "playwright", "test"]) == ("out", "err", 3)
        assert operator_alerts == []
