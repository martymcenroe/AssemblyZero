"""Vitest and Jest measure the coverage the green phase judges, and a
non-pytest coverage shortfall goes to test additions, never to the coder
(#4246).

`jest_runner.py` ran Vitest without coverage, and Jest too, so the green
phase read 0% on every run and no JavaScript suite could meet its target. The
green run now asks for an istanbul `json-summary` report in the framework's
own `coverage/` directory and reads `total.lines.pct` from it. A run whose
tests all pass and whose report cannot be read is a measurement failure that
names the report path; it is never 0%.

The shortfall route went to `N4_implement_code`, where pytest's goes to
`N4c_augment_tests` (#2327). It goes to N4c for every framework. N4c writes
and vets pytest tests only, so a gap in a JavaScript suite halts there,
naming the framework, and the graph now routes N4c's error to HALT instead of
straight back to N5 (ledger 0908, `graph.py:732`, `augment_tests.py:551`).

`base_runner.run_command` stands in for npx and writes the report a real
coverage run would; `shutil.which` answers for `npx`. Nothing real runs.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.workflows.testing.framework_detector import TestFramework
from assemblyzero.workflows.testing.graph import (
    build_testing_workflow,
    route_after_green,
)
from assemblyzero.workflows.testing.nodes.augment_tests import (
    augment_tests_for_coverage,
    coverage_target_file,
)
from assemblyzero.workflows.testing.nodes.verify_phases import _verify_green_non_pytest
from assemblyzero.workflows.testing.runner_registry import get_runner
from assemblyzero.workflows.testing.runners import base_runner, jest_runner

VITEST_WEB = {"framework": "vitest", "coverage_type": "line", "working_directory": "web"}


def _web(root: Path, *, provider: str | None = "coverage-v8") -> Path:
    web = root / "web"
    (web / "tests").mkdir(parents=True)
    (web / "package.json").write_text(
        json.dumps({"scripts": {"test": "vitest run"}}), encoding="utf-8"
    )
    (web / "node_modules" / ".bin").mkdir(parents=True)
    (web / "node_modules" / ".bin" / "vitest").write_text("", encoding="utf-8")
    if provider:
        (web / "node_modules" / "@vitest" / provider).mkdir(parents=True)
        (web / "node_modules" / "@vitest" / provider / "package.json").write_text(
            "{}", encoding="utf-8"
        )
    return root


def _report(passed: int, failed: int = 0) -> str:
    return json.dumps({"numPassedTests": passed, "numFailedTests": failed,
                       "numPendingTests": 0, "numTotalTests": passed + failed})


class _Npx:
    """Stands in for `npx`: answers a report and, for a coverage run, writes
    the json-summary a real one would, in the directory the run named."""

    def __init__(self, *, passed: int, failed: int = 0, pct: object = 85,
                 write_summary: bool = True) -> None:
        self.calls: list[list[str]] = []
        self.passed, self.failed, self.pct = passed, failed, pct
        self.write_summary = write_summary

    def __call__(self, command, **kwargs):
        self.calls.append(list(command))
        cwd = Path(kwargs["cwd"])
        coverage = any(a.startswith("--coverage") for a in command)
        if coverage and self.write_summary:
            (cwd / "coverage").mkdir(exist_ok=True)
            (cwd / "coverage" / "coverage-summary.json").write_text(json.dumps({
                "total": {"lines": {"total": 20, "covered": 17, "skipped": 0,
                                    "pct": self.pct}},
            }), encoding="utf-8")
        return subprocess.CompletedProcess(
            args=command, returncode=1 if self.failed else 0,
            stdout=_report(self.passed, self.failed), stderr="",
        )


def _vitest(root: Path):
    with patch.object(jest_runner.shutil, "which", return_value="/usr/bin/npx"):
        return get_runner(TestFramework.VITEST, str(root), working_directory="web")


def _green_state(root: Path, **overrides) -> dict:
    state = {
        "test_files": [str(root / "web" / "tests" / "a.test.ts")],
        "repo_root": str(root),
        "issue_number": 4246,
        "coverage_target": 90,
        "iteration_count": 0,
        "max_iterations": 5,
        "total_scenarios": 3,
        "audit_dir": "",
        "file_counter": 0,
        "framework_config": VITEST_WEB,
        "framework_configs": [VITEST_WEB],
    }
    state.update(overrides)
    return state


def _green(root: Path, npx: _Npx, **overrides) -> dict:
    with patch.object(base_runner, "run_command", side_effect=npx), \
         patch.object(jest_runner.shutil, "which", return_value="/usr/bin/npx"):
        return _verify_green_non_pytest(
            _green_state(root, **overrides), VITEST_WEB, TestFramework.VITEST
        )


# ---------------------------------------------------------------------------
# T1 (R1): coverage is asked for and read
# ---------------------------------------------------------------------------


def test_t1_the_vitest_argv_asks_for_coverage_and_85_is_read_as_85(tmp_path):
    root = _web(tmp_path)
    npx = _Npx(passed=3, pct=85)
    runner = _vitest(root)
    with patch.object(base_runner, "run_command", side_effect=npx):
        result = runner.run_tests(test_paths=["web/tests/a.test.ts"], measure_coverage=True)

    command = npx.calls[-1]
    assert command[:4] == ["npx", "vitest", "run", "--reporter=json"]
    assert "--coverage.enabled=true" in command
    assert "--coverage.reporter=json-summary" in command
    assert result["coverage_percent"] == 85.0


def test_t1_jest_asks_for_coverage_too(tmp_path):
    root = _web(tmp_path, provider=None)
    npx = _Npx(passed=2, pct=72.5)
    with patch.object(jest_runner.shutil, "which", return_value="/usr/bin/npx"):
        runner = get_runner(TestFramework.JEST, str(root), working_directory="web")
    with patch.object(base_runner, "run_command", side_effect=npx):
        result = runner.run_tests(test_paths=["web/tests/a.test.ts"], measure_coverage=True)

    assert "--coverage" in npx.calls[-1]
    assert "--coverageReporters=json-summary" in npx.calls[-1]
    assert result["coverage_percent"] == 72.5


def test_t1_a_run_that_does_not_ask_for_coverage_carries_no_coverage_flag(tmp_path):
    """The red phase and the full-suite gate measure nothing, and their argv
    stays as it was."""
    root = _web(tmp_path)
    npx = _Npx(passed=3)
    runner = _vitest(root)
    with patch.object(base_runner, "run_command", side_effect=npx):
        result = runner.run_tests(test_paths=None)

    assert npx.calls[-1] == ["npx", "vitest", "run", "--reporter=json"]
    assert result["coverage_percent"] is None, "not measured, and never 0%"


# ---------------------------------------------------------------------------
# T2 (R1): a report that cannot be read is a failure naming its path
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("npx", [
    _Npx(passed=3, write_summary=False),
    _Npx(passed=3, pct="Unknown"),
], ids=["no-report", "no-percentage"])
def test_t2_an_unreadable_report_on_a_passing_run_raises_naming_the_path(npx, tmp_path):
    root = _web(tmp_path)
    runner = _vitest(root)
    with patch.object(base_runner, "run_command", side_effect=npx), \
         pytest.raises(base_runner.CoverageReportError) as raised:
        runner.run_tests(test_paths=["web/tests/a.test.ts"], measure_coverage=True)

    assert str(root / "web" / "coverage" / "coverage-summary.json") in str(raised.value)


def test_t2_a_stale_report_from_an_earlier_run_is_never_read(tmp_path):
    root = _web(tmp_path)
    stale = root / "web" / "coverage" / "coverage-summary.json"
    stale.parent.mkdir()
    stale.write_text(json.dumps({"total": {"lines": {"pct": 99}}}), encoding="utf-8")
    runner = _vitest(root)
    with patch.object(base_runner, "run_command",
                      side_effect=_Npx(passed=3, write_summary=False)), \
         pytest.raises(base_runner.CoverageReportError):
        runner.run_tests(test_paths=["web/tests/a.test.ts"], measure_coverage=True)


def test_t2_the_green_phase_halts_naming_the_report(tmp_path, capsys):
    root = _web(tmp_path)
    result = _green(root, _Npx(passed=3, write_summary=False))

    message = result["error_message"]
    assert "COVERAGE MEASUREMENT FAILED" in message
    assert str(root / "web" / "coverage" / "coverage-summary.json") in message
    assert route_after_green({**_green_state(root), **result}) == "HALT"
    assert "ERROR" in capsys.readouterr().err


def test_t2_a_failing_run_needs_no_report(tmp_path):
    """Coverage decides nothing while tests fail, so its absence is no failure."""
    root = _web(tmp_path)
    result = _green(root, _Npx(passed=1, failed=2, write_summary=False))

    assert result["error_message"] == ""
    assert result["next_node"] == "N4_implement_code"


def test_the_vitest_preflight_requires_a_coverage_provider(tmp_path):
    root = _web(tmp_path, provider=None)
    runner = _vitest(root)
    with pytest.raises(OSError) as raised:
        runner.require_dependencies()
    assert "@vitest/coverage-v8" in str(raised.value)
    assert str(root / "web") in str(raised.value)


@pytest.mark.parametrize("provider", ["coverage-v8", "coverage-istanbul"])
def test_either_vitest_coverage_provider_is_enough(provider, tmp_path):
    root = _web(tmp_path, provider=provider)
    _vitest(root).require_dependencies()


# ---------------------------------------------------------------------------
# T3 (R2): a shortfall goes to N4c, and N4c halts on a gap it cannot fill
# ---------------------------------------------------------------------------


def test_t3_a_vitest_coverage_shortfall_routes_to_n4c(tmp_path):
    root = _web(tmp_path)
    result = _green(root, _Npx(passed=3, pct=50))

    assert result["error_message"] == ""
    assert result["next_node"] == "N4c_augment_tests"
    assert result["coverage_achieved"] == 50.0
    assert result["coverage_gap_framework"] == "vitest"
    assert result["iteration_count"] == 1


def test_t3_n4c_halts_on_a_gap_in_a_javascript_suite(tmp_path, capsys):
    from assemblyzero.workflows.testing.graph import route_after_augment

    state = {
        "repo_root": str(tmp_path),
        "issue_number": 4246,
        "test_files": [str(tmp_path / "web" / "tests" / "a.test.ts")],
        "coverage_achieved": 50.0,
        "coverage_target": 90,
        "coverage_gap_framework": "vitest",
        "green_phase_output": _report(3),
    }
    result = augment_tests_for_coverage(state)

    assert "vitest" in result["error_message"]
    assert "pytest" in result["error_message"], "says what N4c can do"
    assert route_after_augment({**state, **result}) == "HALT"
    assert "ERROR" in capsys.readouterr().err


def test_t3_the_graph_routes_n4c_through_its_router(tmp_path):
    from assemblyzero.workflows.testing.graph import route_after_augment

    workflow = build_testing_workflow()
    assert ("N4c_augment_tests", "N5_verify_green") not in workflow.edges
    assert "N4c_augment_tests" in workflow.branches
    assert route_after_augment({"error_message": ""}) == "N5_verify_green"
    assert route_after_augment({"error_message": "x"}) == "HALT"


def test_n4c_extends_a_python_test_file_in_a_two_framework_run(tmp_path):
    """The first plan-owned test file may be a .test.ts; N4c appends pytest
    functions, so it extends a Python file."""
    ts = str(tmp_path / "web" / "tests" / "replay.test.ts")
    py = str(tmp_path / "tests" / "test_engine.py")
    assert coverage_target_file([ts, py], tmp_path, 7) == Path(py)
