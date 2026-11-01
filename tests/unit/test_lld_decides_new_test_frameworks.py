"""The LLD's test files choose the run's frameworks; the gate runs them all (#4437).

On a target with pytest at its root and Vitest in `web/`, an LLD naming one
Python test was still given both frameworks, so N2.5 refused the run for want
of a Vitest file, and a real run would have written a TypeScript test for a
change with no TypeScript in it. The reverse was worse and silent: an LLD naming
only Vitest paths never ran pytest at the full-suite gate, so a change that
broke the other side landed unseen.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.workflows.testing.framework_detector import (
    TestFramework,
    framework_source,
    frameworks_named_by_lld,
    named_test_files,
    resolve_framework,
    resolve_framework_dirs,
)
from assemblyzero.workflows.testing.nodes import verify_phases
from assemblyzero.workflows.testing.nodes.load_lld import (
    _framework_configs,
    _gate_only_configs,
    _log_frameworks,
)
from assemblyzero.workflows.testing.nodes.verify_phases import verify_green_phase

pytestmark = pytest.mark.usefixtures("coverage_as_reported")  # #4436: routing, not measuring

PYTHON_ONLY = "## Tests\n\n| `tests/unit/test_x.py` | Add |\n"
VITEST_ONLY = "## Tests\n\n| `web/tests/x.test.ts` | Add |\n"
BOTH = PYTHON_ONLY + VITEST_ONLY
NO_TEST_FILE = "## Plan\n\nChange `src/app.py` and keep the behaviour.\n"


@pytest.fixture
def target(tmp_path: Path) -> Path:
    """pytest at the root and Vitest in web/, as a git worktree is."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_existing.py").write_text("def test_it():\n    pass\n", encoding="utf-8")
    web = tmp_path / "web"
    web.mkdir()
    (web / "vitest.config.ts").write_text("export default {}\n", encoding="utf-8")
    (web / "package.json").write_text(
        json.dumps({"devDependencies": {"vitest": "^2.1.0"}}), encoding="utf-8"
    )
    return tmp_path


class TestTheTestFilesDecide:
    def test_t1_an_lld_naming_only_python_tests_is_a_pytest_run(self, target):
        assert resolve_framework_dirs(PYTHON_ONLY, str(target)) == {TestFramework.PYTEST: "."}
        assert resolve_framework(PYTHON_ONLY, str(target)) == [TestFramework.PYTEST]

    def test_t2_an_lld_naming_only_vitest_paths_is_a_vitest_run(self, target):
        assert resolve_framework_dirs(VITEST_ONLY, str(target)) == {TestFramework.VITEST: "web"}

    def test_t4_an_lld_naming_no_test_file_gets_every_project_framework(self, target):
        assert resolve_framework_dirs(NO_TEST_FILE, str(target)) == {
            TestFramework.PYTEST: ".",
            TestFramework.VITEST: "web",
        }

    def test_an_lld_naming_both_kinds_gets_both(self, target):
        assert set(resolve_framework_dirs(BOTH, str(target))) == {
            TestFramework.PYTEST, TestFramework.VITEST,
        }

    def test_the_other_style_of_python_test_name_counts(self, target):
        lld = "| `tests/app_test.py` | Add |\n"

        assert resolve_framework_dirs(lld, str(target)) == {TestFramework.PYTEST: "."}

    def test_prose_about_the_other_side_adds_no_framework(self, target):
        lld = PYTHON_ONLY + "\nThe Vitest suite in web/ must keep passing.\n"

        assert set(frameworks_named_by_lld(lld, str(target))) == {TestFramework.PYTEST}

    def test_prose_about_pytest_adds_no_framework_to_a_vitest_lld(self, target):
        lld = VITEST_ONLY + "\nThe pytest suite must keep passing.\n"

        assert set(frameworks_named_by_lld(lld, str(target))) == {TestFramework.VITEST}

    def test_a_declared_runner_still_stands_with_no_test_file(self, target):
        lld = "Test Framework: Vitest\n\nChange the page.\n"

        assert resolve_framework_dirs(lld, str(target)) == {TestFramework.VITEST: "web"}

    def test_a_glob_names_no_file(self):
        assert named_test_files("All of `tests/test_*.py` and `web/**/*.test.ts`.") == []


class TestN25AsksForTheRunsFrameworksOnly:
    def test_t1_a_python_only_lld_asks_for_no_vitest_file(self, target):
        configs = _framework_configs(PYTHON_ONLY, str(target))

        assert [str(c["framework"].value) for c in configs] == ["pytest"]
        assert len(configs) == 1, "one framework, so N2.5 wants one scaffold"


class TestTheGateListsWhatTheRunDoesNot:
    def test_t3_a_python_only_lld_leaves_vitest_to_the_gate(self, target):
        configs = _framework_configs(PYTHON_ONLY, str(target))

        gate_only = _gate_only_configs(configs, str(target))

        assert [(c["framework"].value, c["working_directory"]) for c in gate_only] == [
            ("vitest", "web")
        ]

    def test_t3_a_vitest_only_lld_leaves_pytest_to_the_gate(self, target):
        configs = _framework_configs(VITEST_ONLY, str(target))

        gate_only = _gate_only_configs(configs, str(target))

        assert [(c["framework"].value, c["working_directory"]) for c in gate_only] == [
            ("pytest", None)
        ]

    def test_a_run_of_every_framework_leaves_nothing(self, target):
        configs = _framework_configs(BOTH, str(target))

        assert _gate_only_configs(configs, str(target)) == []

    def test_the_declared_target_governs_a_gate_only_framework_too(self, target):
        configs = _framework_configs(PYTHON_ONLY, str(target), 80)

        gate_only = _gate_only_configs(configs, str(target), 80)

        assert gate_only[0]["coverage_target_percent"] == 80


class TestR3TheLogSaysWhich:
    def test_it_names_the_test_files(self, target):
        assert "tests/unit/test_x.py" in framework_source(PYTHON_ONLY, str(target))

    def test_it_says_when_the_project_decided(self, target):
        assert "every framework the project has" in framework_source(NO_TEST_FILE, str(target))

    def test_it_says_when_a_declaration_decided(self, target):
        assert framework_source("Test Framework: Vitest\n", str(target)) == (
            "the LLD names the runner"
        )

    def test_each_phase_is_named(self, target, capsys):
        configs = _framework_configs(PYTHON_ONLY, str(target))
        gate_only = _gate_only_configs(configs, str(target))

        _log_frameworks(PYTHON_ONLY, str(target), configs, gate_only)

        out = capsys.readouterr().out
        assert "scaffold, red and green: {'pytest': '.'}" in out
        assert "full-suite gate: {'pytest': '.', 'vitest': 'web'}" in out


def _state(target: Path, test_file: str, run: dict, gate_only: dict) -> dict:
    return {
        "test_files": [str(target / test_file)],
        "implementation_files": [],
        "repo_root": str(target),
        "issue_number": 4437,
        "coverage_target": 90,
        "iteration_count": 0,
        "max_iterations": 5,
        "total_scenarios": 3,
        "audit_dir": "",
        "file_counter": 0,
        "framework_config": run,
        "framework_configs": [run],
        "gate_only_framework_configs": [gate_only],
    }


PYTEST = {"framework": "pytest", "working_directory": None}
VITEST = {"framework": "vitest", "working_directory": "web"}


def _suite(passed: int, failed: int = 0) -> dict:
    return {
        "passed": passed, "failed": failed, "skipped": 0, "errors": 0,
        "total": passed + failed, "coverage_percent": 95.0, "coverage_type": "line",
        "raw_output": f"{passed} passed, {failed} failed",
        "exit_code": 1 if failed else 0, "framework": TestFramework.VITEST,
    }


def _green(**extra) -> dict:
    return {
        "green_phase_output": "ok", "pytest_exit_code": 0, "coverage_achieved": 95.0,
        "coverage_judged": True, "file_counter": 1, "full_suite_validated": True,
        "next_node": "N6_e2e_validation", "test_run_result": {"passed": 1, "total": 1},
        **extra,
    }


class TestT3TheGateRunsTheFrameworkTheLldDidNotName:
    def _run_python_only(self, target, vitest_suite):
        runner = MagicMock()
        runner.run_tests.return_value = vitest_suite
        with (
            patch.object(verify_phases, "_verify_green_pytest_single", return_value=_green()),
            patch.object(verify_phases, "get_runner", return_value=runner),
        ):
            result = verify_green_phase(
                _state(target, "tests/unit/test_x.py", PYTEST, VITEST)
            )
        return result, runner

    def test_a_python_only_run_runs_the_whole_vitest_suite(self, target):
        result, runner = self._run_python_only(target, _suite(40))

        assert runner.run_tests.call_args.kwargs.get("test_paths") is None
        assert result["full_suite_validated"] is True
        assert result["next_node"] == "N6_e2e_validation"

    def test_a_vitest_failure_fails_a_python_only_run(self, target):
        result, _ = self._run_python_only(target, _suite(39, failed=1))

        assert result["full_suite_validated"] is False
        assert result["next_node"] == "N4_implement_code"

    def _run_vitest_only(self, target, pytest_suite):
        run_pytest = MagicMock(return_value=pytest_suite)
        with (
            patch.object(verify_phases, "_verify_green_non_pytest", return_value=_green()),
            patch.object(verify_phases, "run_pytest", run_pytest),
            patch.object(verify_phases, "get_runner", return_value=MagicMock()),
        ):
            result = verify_green_phase(
                _state(target, "web/tests/x.test.ts", VITEST, PYTEST)
            )
        return result, run_pytest

    def test_a_vitest_only_run_runs_the_whole_pytest_suite(self, target):
        suite = {
            "stdout": "12 passed", "stderr": "", "returncode": 0,
            "parsed": {"passed": 12, "failed": 0, "errors": 0},
        }

        result, run_pytest = self._run_vitest_only(target, suite)

        run_pytest.assert_called_once()
        assert run_pytest.call_args.args[0] == []
        assert result["full_suite_validated"] is True

    def test_a_pytest_failure_fails_a_vitest_only_run(self, target):
        suite = {
            "stdout": "FAILED tests/test_existing.py::test_it\n1 failed, 11 passed",
            "stderr": "", "returncode": 1,
            "parsed": {"passed": 11, "failed": 1, "errors": 0},
        }

        result, _ = self._run_vitest_only(target, suite)

        assert result["full_suite_validated"] is False
        assert result["next_node"] == "N4_implement_code"

    def test_a_framework_that_cannot_start_halts_before_any_suite_runs(self, target):
        runner = MagicMock()
        runner.require_dependencies.side_effect = ValueError("no @vitest/coverage-v8")
        single = MagicMock()
        with (
            patch.object(verify_phases, "_verify_green_pytest_single", single),
            patch.object(verify_phases, "get_runner", return_value=runner),
        ):
            result = verify_green_phase(
                _state(target, "tests/unit/test_x.py", PYTEST, VITEST)
            )

        assert "vitest (web) cannot run" in result["error_message"]
        single.assert_not_called()

    def test_a_checkpoint_from_before_this_has_no_gate_only_framework(self, target):
        state = _state(target, "tests/unit/test_x.py", PYTEST, VITEST)
        del state["gate_only_framework_configs"]

        with (
            patch.object(verify_phases, "_verify_green_pytest_single", return_value=_green()),
            patch.object(verify_phases, "get_runner") as get_runner,
        ):
            result = verify_green_phase(state)

        get_runner.assert_not_called()
        assert result["next_node"] == "N6_e2e_validation"
