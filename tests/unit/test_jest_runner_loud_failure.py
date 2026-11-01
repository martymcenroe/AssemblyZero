"""jest_runner.py under standard 0034, one test per sweep site (#3585).

The Jest/Vitest runner turns a run of `npx jest` or `npx vitest` into the
counts the red and green phases judge. Every way it could not read a run used
to come back as an invented result: a run with no JSON report, or one whose
report did not parse, was a "fallback" whose counts read zero failures when
the exit code was 0, and an unreadable package.json was passed over, so the
typecheck it might have named was never run. Each of those now prints an
ERROR line and raises `RunnerError` naming the project, the exit code and the
head of the output; the run stops, and the node or the entry point that ends
it alerts the operator. A typecheck that fails is still a failing run, as it
was: that is a real answer, not a missing one.

`shutil.which` answers for `npx` and `_run_subprocess` is stood in for:
nothing real is run. Line numbers in the names are ledger 0908's, at its
base `79e18ad1`.
"""
from __future__ import annotations

import inspect
import json

import pytest

from assemblyzero.workflows.testing.framework_detector import TestFramework
from assemblyzero.workflows.testing.runner_registry import get_framework_config
from assemblyzero.workflows.testing.runners import jest_runner

REPORT = json.dumps({
    "numPassedTests": 2, "numFailedTests": 1, "numPendingTests": 0, "numTotalTests": 3,
})


def _runner(monkeypatch, framework: TestFramework, root) -> jest_runner.JestRunner:
    monkeypatch.setattr(jest_runner.shutil, "which", lambda name: "/usr/bin/npx")
    return jest_runner.JestRunner(get_framework_config(framework), str(root))


def _stand_in(monkeypatch, runner, *returns):
    """`_run_subprocess` answers each call with the next (stdout, stderr,
    code), and records the commands it was given."""
    calls: list[list[str]] = []
    queue = list(returns)

    def run(command, timeout=300, cwd=None):
        calls.append(list(command))
        return queue.pop(0)

    monkeypatch.setattr(runner, "_run_subprocess", run)
    return calls


def _runner_error(excinfo) -> None:
    assert type(excinfo.value).__name__ == "RunnerError", (
        f"expected RunnerError, got {type(excinfo.value).__name__}: {excinfo.value}"
    )


class TestNpxMissing:
    def test_33_npx_missing_is_an_error_line_naming_the_project(
        self, monkeypatch, tmp_path, capsys,
    ):
        monkeypatch.setattr(jest_runner.shutil, "which", lambda name: None)
        config = get_framework_config(TestFramework.JEST)

        with pytest.raises(EnvironmentError, match="npx not found"):
            jest_runner.JestRunner(config, str(tmp_path))

        err = capsys.readouterr().err
        assert "ERROR" in err
        assert "npx not found" in err
        assert str(tmp_path) in err


class TestPackageJson:
    def test_57_an_unparseable_package_json_raises_naming_the_file(
        self, monkeypatch, tmp_path, capsys,
    ):
        (tmp_path / "package.json").write_text("{not json", encoding="utf-8")
        runner = _runner(monkeypatch, TestFramework.VITEST, tmp_path)
        calls = _stand_in(monkeypatch, runner, (REPORT, "", 1))

        with pytest.raises(Exception) as excinfo:
            runner.run_tests()

        _runner_error(excinfo)
        assert "package.json" in str(excinfo.value)
        assert str(tmp_path) in str(excinfo.value)
        assert calls == [], "no suite runs when its typecheck cannot be decided"
        assert "ERROR" in capsys.readouterr().err

    def test_57_a_package_json_that_is_not_an_object_raises(self, monkeypatch, tmp_path):
        (tmp_path / "package.json").write_text("[1, 2]", encoding="utf-8")
        runner = _runner(monkeypatch, TestFramework.VITEST, tmp_path)
        _stand_in(monkeypatch, runner, (REPORT, "", 1))

        with pytest.raises(Exception) as excinfo:
            runner.run_tests()

        _runner_error(excinfo)
        assert "package.json" in str(excinfo.value)

    def test_58_the_package_json_tag_is_gone(self):
        assert "fail-open" not in inspect.getsource(jest_runner)

    def test_no_package_json_means_no_typecheck_script_and_is_quiet(
        self, monkeypatch, tmp_path, operator_alerts, capsys,
    ):
        """Kept: a project with no package.json declares no typecheck
        script; with no tsconfig.json either, no typecheck runs."""
        runner = _runner(monkeypatch, TestFramework.VITEST, tmp_path)
        calls = _stand_in(monkeypatch, runner, (REPORT, "", 1))

        result = runner.run_tests()

        assert len(calls) == 1
        assert calls[0][:4] == ["npx", "vitest", "run", "--reporter=json"]
        assert (result["passed"], result["failed"]) == (2, 1)
        assert operator_alerts == []
        assert "ERROR" not in capsys.readouterr().err


class TestTypecheck:
    def test_72_a_failing_typecheck_is_a_failing_run_not_an_error(
        self, monkeypatch, tmp_path, operator_alerts,
    ):
        """Kept (ledger: compliant): a typecheck that exits non-zero is the
        run's answer -- the code does not compile -- and comes back as a
        failing result, never raised and never alerted."""
        (tmp_path / "tsconfig.json").write_text("{}", encoding="utf-8")
        runner = _runner(monkeypatch, TestFramework.VITEST, tmp_path)
        calls = _stand_in(monkeypatch, runner, ("src/a.ts: TS2322", "", 2))

        result = runner.run_tests()

        assert calls == [["npx", "tsc", "--noEmit"]]
        assert result["passed"] == 0
        assert result["failed"] == 1
        assert result["errors"] == 1
        assert result["exit_code"] == 2
        assert "TS2322" in result["raw_output"]
        assert operator_alerts == []


class TestTheReport:
    def test_110_no_json_report_raises_with_exit_code_and_output(
        self, monkeypatch, tmp_path, capsys,
    ):
        runner = _runner(monkeypatch, TestFramework.JEST, tmp_path)

        with pytest.raises(Exception) as excinfo:
            runner.parse_results("Error: Cannot find module 'ts-jest'", 1, "npm ERR! code 1")

        _runner_error(excinfo)
        message = str(excinfo.value)
        assert "no Jest/Vitest JSON report" in message
        assert "exit 1" in message
        assert "Cannot find module 'ts-jest'" in message
        assert "npm ERR!" in message
        assert "ERROR" in capsys.readouterr().err

    def test_110_a_run_that_writes_no_report_raises_from_run_tests(
        self, monkeypatch, tmp_path,
    ):
        runner = _runner(monkeypatch, TestFramework.JEST, tmp_path)
        _stand_in(monkeypatch, runner, ("", "jest: command crashed", 1))

        with pytest.raises(Exception) as excinfo:
            runner.run_tests(test_paths=["a.test.ts"])

        _runner_error(excinfo)

    def test_124_a_report_that_does_not_parse_raises(self, monkeypatch, tmp_path, capsys):
        runner = _runner(monkeypatch, TestFramework.VITEST, tmp_path)
        broken = '{"numPassedTests": 3, "numFailedTests": }'

        with pytest.raises(Exception) as excinfo:
            runner.parse_results(broken, 1)

        _runner_error(excinfo)
        assert "does not parse" in str(excinfo.value)
        assert "exit 1" in str(excinfo.value)
        assert isinstance(excinfo.value.__cause__, ValueError)
        assert "ERROR" in capsys.readouterr().err

    def test_169_no_report_at_exit_zero_is_never_a_clean_result(self, monkeypatch, tmp_path):
        """The fallback read failed=0 and errors=0 at exit 0: a run nobody
        could read looked like one where nothing failed."""
        runner = _runner(monkeypatch, TestFramework.JEST, tmp_path)

        with pytest.raises(Exception) as excinfo:
            runner.parse_results("Done in 0.4s", 0)

        _runner_error(excinfo)
        assert "exit 0" in str(excinfo.value)

    def test_169_no_result_the_runner_invents_reads_as_not_failing(self):
        """The only result the runner builds without a report is a failed
        typecheck's, and it is always a failure."""
        assert not hasattr(jest_runner.JestRunner, "_fallback_result")

    def test_a_report_on_stdout_is_read(self, monkeypatch, tmp_path, operator_alerts):
        """Kept: a readable report is the run's result, quietly."""
        runner = _runner(monkeypatch, TestFramework.JEST, tmp_path)

        result = runner.parse_results(REPORT, 1, "npm WARN something")

        assert (result["passed"], result["failed"], result["total"]) == (2, 1, 3)
        assert operator_alerts == []
