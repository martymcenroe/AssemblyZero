"""playwright_runner.py under standard 0034, one test per sweep site (#3585).

A Playwright run with no JSON report, or whose report did not parse, came
back with a WARNING as a fabricated result: one failure and one error when the
exit code was not 0, and zero of everything when it was, which a phase reads
as a run where nothing failed. Each now raises `RunnerError` after an ERROR
line, naming the project, the exit code and the head of the output. A report
whose suites are not the shape Playwright writes raises the same way.

`shutil.which` answers for `npx` and `_run_subprocess` is stood in for:
nothing real is run. Line numbers in the names are ledger 0908's, at its
base `79e18ad1`.
"""
from __future__ import annotations

import json

import pytest

from assemblyzero.workflows.testing.framework_detector import TestFramework
from assemblyzero.workflows.testing.runner_registry import get_framework_config
from assemblyzero.workflows.testing.runners import playwright_runner

REPORT = json.dumps({"suites": [{"specs": [{"tests": [
    {"results": [{"status": "passed"}]},
    {"results": [{"status": "failed"}]},
]}]}]})


def _runner(monkeypatch, root) -> playwright_runner.PlaywrightRunner:
    monkeypatch.setattr(playwright_runner.shutil, "which", lambda name: "/usr/bin/npx")
    return playwright_runner.PlaywrightRunner(
        get_framework_config(TestFramework.PLAYWRIGHT), str(root),
    )


def _assert_runner_error(excinfo, *needles: str) -> None:
    assert type(excinfo.value).__name__ == "RunnerError", (
        f"expected RunnerError, got {type(excinfo.value).__name__}: {excinfo.value}"
    )
    for needle in needles:
        assert needle in str(excinfo.value)


class TestNoReport:
    def test_91_no_json_report_raises_with_exit_code_and_output(
        self, monkeypatch, tmp_path, capsys,
    ):
        runner = _runner(monkeypatch, tmp_path)

        with pytest.raises(Exception) as excinfo:
            runner.parse_results("Error: browserType.launch: Executable doesn't exist", 1, "npx: warn")

        _assert_runner_error(
            excinfo, "no Playwright JSON report", "exit 1",
            "Executable doesn't exist", "npx: warn", str(tmp_path),
        )
        assert "ERROR" in capsys.readouterr().err

    def test_91_no_report_at_exit_zero_is_never_a_clean_result(self, monkeypatch, tmp_path):
        """The fallback read zero failures and zero errors at exit 0."""
        runner = _runner(monkeypatch, tmp_path)

        with pytest.raises(Exception) as excinfo:
            runner.parse_results("", 0)

        _assert_runner_error(excinfo, "exit 0")

    def test_91_a_run_that_writes_no_report_raises_from_run_tests(self, monkeypatch, tmp_path):
        runner = _runner(monkeypatch, tmp_path)
        monkeypatch.setattr(
            runner, "_run_subprocess",
            lambda command, timeout=300, cwd=None: ("", "crashed", 1),
        )

        with pytest.raises(Exception) as excinfo:
            runner.run_tests(test_paths=["e2e/a.spec.ts"])

        _assert_runner_error(excinfo)


class TestBrokenReport:
    def test_104_a_report_that_does_not_parse_raises(self, monkeypatch, tmp_path, capsys):
        runner = _runner(monkeypatch, tmp_path)

        with pytest.raises(Exception) as excinfo:
            runner.parse_results('{"suites": [{"specs": []},, {}]}', 1)

        _assert_runner_error(excinfo, "does not parse", "exit 1")
        assert isinstance(excinfo.value.__cause__, ValueError)
        assert "ERROR" in capsys.readouterr().err

    @pytest.mark.parametrize("report", [
        {"suites": "not a list"},
        {"suites": [{"specs": [{"tests": [{"results": ["passed"]}]}]}]},
        {"suites": [{"specs": 3}]},
    ])
    def test_104_a_report_of_the_wrong_shape_raises(self, monkeypatch, tmp_path, report):
        runner = _runner(monkeypatch, tmp_path)

        with pytest.raises(Exception) as excinfo:
            runner.parse_results(json.dumps(report), 1)

        _assert_runner_error(excinfo, "not the shape")

    def test_a_report_is_read(self, monkeypatch, tmp_path, operator_alerts):
        """Kept: a readable report is the run's result, quietly."""
        result = _runner(monkeypatch, tmp_path).parse_results(REPORT, 1, "npm WARN x")

        assert (result["passed"], result["failed"], result["total"]) == (1, 1, 2)
        assert operator_alerts == []

    def test_no_result_is_invented(self):
        assert not hasattr(playwright_runner.PlaywrightRunner, "_fallback_result")
