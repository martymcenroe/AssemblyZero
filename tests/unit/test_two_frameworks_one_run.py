"""One run tests a target with a pytest suite at its root and a Vitest suite
in `web/`, both of them, each in its own directory (#4236).

#3677 added `framework_configs` to the state and a loop over it in the red
and green phases, and nothing ever wrote it: all three N0 load sites resolved
every framework and kept the first. So a target with a Python suite at the
root and a Vitest suite in `web/` ran pytest alone and reported green with a
whole suite unexercised.

These tests drive the real load sites and the real phases. The subprocess
layer is stood in for: `run_pytest` for pytest, `base_runner.run_command`
for Vitest, and `shutil.which` so the Vitest runner sees an `npx`. Nothing
real is installed or run.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.workflows.testing.graph import route_after_green, route_after_load
from assemblyzero.workflows.testing.nodes.load_lld import (
    _load_from_issue,
    _mock_load_lld,
    load_lld,
)
from assemblyzero.workflows.testing.nodes.verify_phases import (
    verify_green_phase,
    verify_red_phase,
)
from assemblyzero.workflows.testing.runners import base_runner, jest_runner

#: The module itself: `nodes/__init__` exports the `load_lld` function under
#: the same name, so `from ...nodes import load_lld` would give the function.
load_lld_module = importlib.import_module("assemblyzero.workflows.testing.nodes.load_lld")

VERIFY = "assemblyzero.workflows.testing.nodes.verify_phases"

#: A spec that names no framework, so the project's own files decide.
#: #3585: N0 halts on a spec that names no files to implement, so it names one
#: source file, which places no test runner.
NEUTRAL_SPEC = """# 7 - Engine replay

**Status:** APPROVED

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/engine.py` | Add | The replay engine |

## 3. Requirements

1. REQ-1: The engine replays a recorded session.

## 10. Test Plan

### test_replay_round_trip
Verify that a recorded session replays to the same final state.
Requirement: REQ-1
"""


def _mixed_target(root: Path, *, node_modules: bool = True) -> Path:
    """A Python suite at the root and a Vitest suite in web/."""
    (root / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\ntestpaths = [\"tests\"]\n", encoding="utf-8"
    )
    (root / "tests").mkdir()
    (root / "tests" / "test_engine.py").write_text(
        "def test_engine():\n    assert True\n", encoding="utf-8"
    )
    web = root / "web"
    (web / "tests").mkdir(parents=True)
    (web / "package.json").write_text(
        json.dumps({
            "scripts": {"test": "vitest run"},
            "devDependencies": {"vitest": "^2.1.0"},
        }),
        encoding="utf-8",
    )
    (web / "vitest.config.ts").write_text("export default {}\n", encoding="utf-8")
    (web / "tests" / "engine.test.ts").write_text(
        "import { it, expect } from 'vitest';\nit('runs', () => expect(1).toBe(1));\n",
        encoding="utf-8",
    )
    if node_modules:
        (web / "node_modules" / ".bin").mkdir(parents=True)
        (web / "node_modules" / ".bin" / "vitest").write_text("", encoding="utf-8")
        # #4246: the green run measures coverage, so the provider is installed.
        (web / "node_modules" / "@vitest" / "coverage-v8").mkdir(parents=True)
    return root


def _framework(config: dict) -> str:
    fw = config["framework"]
    return getattr(fw, "value", fw)


def _placement(configs: list[dict]) -> tuple[tuple[str, str | None], ...]:
    return tuple((_framework(c), c.get("working_directory")) for c in configs)


class _Proc:
    def __init__(self, stdout: str, returncode: int) -> None:
        self.stdout, self.stderr, self.returncode = stdout, "", returncode


def _vitest_report(passed: int, failed: int) -> str:
    """Jest-compatible JSON. Coverage is not in it: since #4246 the runner
    reads the json-summary a coverage run writes (`_Recorder.run_command`)."""
    return json.dumps({
        "numPassedTests": passed,
        "numFailedTests": failed,
        "numPendingTests": 0,
        "numTotalTests": passed + failed,
    })


class _Recorder:
    """Stands in for both runners and records what each was asked to run."""

    def __init__(self, *, pytest_passed: int, pytest_failed: int,
                 vitest_passed: int, vitest_failed: int) -> None:
        self.pytest_calls: list[list[str]] = []
        self.vitest_calls: list[tuple[list[str], str]] = []
        self._pytest = (pytest_passed, pytest_failed)
        self._vitest = (vitest_passed, vitest_failed)

    def run_pytest(self, test_files, **kwargs):
        self.pytest_calls.append(list(test_files))
        passed, failed = self._pytest
        return {
            "returncode": 1 if failed else 0,
            "stdout": f"{passed} passed, {failed} failed",
            "stderr": "",
            "parsed": {"passed": passed, "failed": failed, "errors": 0,
                       "coverage": 100.0},
        }

    def run_command(self, command, **kwargs):
        self.vitest_calls.append((list(command), str(kwargs.get("cwd"))))
        passed, failed = self._vitest
        if any(arg.startswith("--coverage") for arg in command):
            # #4246: a coverage run writes its json-summary (100 % here).
            report = Path(kwargs["cwd"]) / "coverage" / "coverage-summary.json"
            report.parent.mkdir(exist_ok=True)
            report.write_text(json.dumps({"total": {"lines": {"pct": 100}}}), encoding="utf-8")
        return _Proc(_vitest_report(passed, failed), 1 if failed else 0)


def _patched(recorder: _Recorder):
    return (
        patch(f"{VERIFY}.run_pytest", side_effect=recorder.run_pytest),
        patch.object(base_runner, "run_command", side_effect=recorder.run_command),
        patch.object(jest_runner.shutil, "which", return_value="/usr/bin/npx"),
    )


def _run_state(root: Path, test_files: list[Path], **overrides) -> dict:
    """The state N0's mock load site writes for this target, plus the files."""
    loaded = _mock_load_lld({"issue_number": 7, "repo_root": str(root)})
    state = {
        **loaded,
        "issue_number": 7,
        "repo_root": str(root),
        "test_files": [str(p) for p in test_files],
        "implementation_files": [],
        "files_to_modify": [],
        "coverage_target": 90,
        "iteration_count": 0,
        "max_iterations": 5,
        "audit_dir": "",
    }
    state.update(overrides)
    return state


# ---------------------------------------------------------------------------
# T1 (R1): every load site writes both configs
# ---------------------------------------------------------------------------


class TestEveryLoadSiteWritesEveryFramework:
    EXPECTED = (("pytest", None), ("vitest", "web"))

    def test_the_mock_load_site(self, tmp_path):
        root = _mixed_target(tmp_path)
        result = _mock_load_lld({"issue_number": 7, "repo_root": str(root)})
        assert _placement(result["framework_configs"]) == self.EXPECTED
        assert _framework(result["framework_config"]) == "pytest"

    def test_the_spec_load_site(self, tmp_path):
        root = _mixed_target(tmp_path)
        spec = root / "spec-7.md"
        spec.write_text(NEUTRAL_SPEC, encoding="utf-8")
        result = load_lld({
            "issue_number": 7, "repo_root": str(root), "lld_path": str(spec),
        })
        assert result.get("error_message", "") == ""
        assert _placement(result["framework_configs"]) == self.EXPECTED

    def test_the_issue_only_load_site(self, tmp_path):
        root = _mixed_target(tmp_path)
        # #3585: issue-only mode halts on a body with no test plan or no files
        # to implement; the spec's sections serve as the body.
        body = NEUTRAL_SPEC.split("## 2. Files to Implement", 1)[1]
        issue = json.dumps({
            "title": "Engine replay", "body": "## 2. Files to Implement" + body,
        })
        with patch.object(load_lld_module, "run_command",
                          return_value=_Proc(issue, 0)):
            result = _load_from_issue({}, 7, root)
        assert result.get("error_message", "") == ""
        assert _placement(result["framework_configs"]) == self.EXPECTED

    def test_the_configs_are_checkpoint_safe(self, tmp_path):
        """Strings, not enums (#3708), in every entry."""
        root = _mixed_target(tmp_path)
        result = _mock_load_lld({"issue_number": 7, "repo_root": str(root)})
        for config in result["framework_configs"]:
            assert isinstance(config["framework"], str)
            assert isinstance(config["coverage_type"], str)


# ---------------------------------------------------------------------------
# T2 (R2): each phase runs each framework, in its own directory, on its files
# ---------------------------------------------------------------------------


class TestEachPhaseRunsEveryFramework:
    def test_a_failing_vitest_test_fails_the_green_phase_while_pytest_passes(self, tmp_path):
        root = _mixed_target(tmp_path)
        py_test = root / "tests" / "test_engine.py"
        ts_test = root / "web" / "tests" / "engine.test.ts"
        recorder = _Recorder(pytest_passed=1, pytest_failed=0,
                             vitest_passed=0, vitest_failed=1)
        state = _run_state(root, [py_test, ts_test])

        p1, p2, p3 = _patched(recorder)
        with p1, p2, p3:
            result = verify_green_phase(state)

        assert result["error_message"] == ""
        assert result["next_node"] == "N4_implement_code", (
            "the Vitest failure sends the run back to implementation"
        )
        assert recorder.pytest_calls[0] == [str(py_test)], (
            "pytest is given the Python test alone, never the .test.ts file"
        )
        targeted = [c for c in recorder.vitest_calls if "tests/engine.test.ts" in c[0]]
        assert targeted, "the Vitest test ran"
        command, cwd = targeted[0]
        assert command[:4] == ["npx", "vitest", "run", "--reporter=json"]
        assert Path(cwd) == root / "web", "Vitest runs in web/, never at the root"

    def test_both_frameworks_pass_and_the_run_goes_on(self, tmp_path):
        root = _mixed_target(tmp_path)
        recorder = _Recorder(pytest_passed=1, pytest_failed=0,
                             vitest_passed=1, vitest_failed=0)
        state = _run_state(
            root, [root / "tests" / "test_engine.py",
                   root / "web" / "tests" / "engine.test.ts"],
        )
        p1, p2, p3 = _patched(recorder)
        with p1, p2, p3:
            result = verify_green_phase(state)

        assert result["error_message"] == ""
        assert result["next_node"] == "N6_e2e_validation"
        assert result["full_suite_validated"] is True
        assert "=== Framework: pytest ===" in result["green_phase_output"]
        assert "=== Framework: vitest (web) ===" in result["green_phase_output"]

    def test_the_red_phase_runs_both_frameworks_on_their_own_files(self, tmp_path):
        root = _mixed_target(tmp_path)
        py_test = root / "tests" / "test_engine.py"
        ts_test = root / "web" / "tests" / "engine.test.ts"
        recorder = _Recorder(pytest_passed=0, pytest_failed=1,
                             vitest_passed=0, vitest_failed=1)
        state = _run_state(root, [py_test, ts_test])

        p1, p2, p3 = _patched(recorder)
        with p1, p2, p3:
            result = verify_red_phase(state)

        assert result["error_message"] == ""
        assert result["next_node"] == "N4_implement_code"
        assert recorder.pytest_calls == [[str(py_test)]]
        assert len(recorder.vitest_calls) == 1
        command, cwd = recorder.vitest_calls[0]
        assert command[-1] == "tests/engine.test.ts"
        assert Path(cwd) == root / "web"

    def test_a_vitest_test_that_passes_at_red_fails_the_red_phase(self, tmp_path):
        """Each leg judges its own tests: pytest's red does not cover for Vitest."""
        root = _mixed_target(tmp_path)
        recorder = _Recorder(pytest_passed=0, pytest_failed=1,
                             vitest_passed=1, vitest_failed=0)
        state = _run_state(
            root, [root / "tests" / "test_engine.py",
                   root / "web" / "tests" / "engine.test.ts"],
        )
        p1, p2, p3 = _patched(recorder)
        with p1, p2, p3:
            result = verify_red_phase(state)

        assert "passed unexpectedly" in result["error_message"]

    def test_the_full_suite_gate_runs_a_framework_with_no_test_in_this_run(self, tmp_path):
        """A Python-only change still runs the whole Vitest suite at the gate."""
        root = _mixed_target(tmp_path)
        recorder = _Recorder(pytest_passed=1, pytest_failed=0,
                             vitest_passed=4, vitest_failed=0)
        state = _run_state(root, [root / "tests" / "test_engine.py"])

        p1, p2, p3 = _patched(recorder)
        with p1, p2, p3:
            result = verify_green_phase(state)

        assert result["error_message"] == ""
        assert result["full_suite_validated"] is True
        assert [] in recorder.pytest_calls, "pytest's whole suite ran"
        assert recorder.vitest_calls, "Vitest's whole suite ran"
        command, cwd = recorder.vitest_calls[-1]
        assert command == ["npx", "vitest", "run", "--reporter=json"], (
            "the whole suite: no test paths"
        )
        assert Path(cwd) == root / "web"

    def test_a_vitest_regression_outside_the_run_fails_the_gate(self, tmp_path):
        root = _mixed_target(tmp_path)
        recorder = _Recorder(pytest_passed=1, pytest_failed=0,
                             vitest_passed=3, vitest_failed=1)
        state = _run_state(root, [root / "tests" / "test_engine.py"])

        p1, p2, p3 = _patched(recorder)
        with p1, p2, p3:
            result = verify_green_phase(state)

        assert result["full_suite_validated"] is False
        assert result["next_node"] == "N4_implement_code"

    def test_a_test_file_no_framework_owns_halts(self, tmp_path):
        """A .test.ts file outside web/ would be run by nothing: that halts."""
        root = _mixed_target(tmp_path)
        stray = root / "tests" / "issue_7.test.ts"
        stray.write_text("", encoding="utf-8")
        recorder = _Recorder(pytest_passed=0, pytest_failed=1,
                             vitest_passed=0, vitest_failed=1)
        state = _run_state(root, [root / "tests" / "test_engine.py", stray])

        p1, p2, p3 = _patched(recorder)
        with p1, p2, p3:
            result = verify_red_phase(state)

        assert "issue_7.test.ts" in result["error_message"]
        assert "belongs to no framework" in result["error_message"]
        assert recorder.pytest_calls == [] and recorder.vitest_calls == [], (
            "nothing runs once the run cannot say who runs every file"
        )


# ---------------------------------------------------------------------------
# T3 (R3): a framework that cannot run fails its phase with an alert
# ---------------------------------------------------------------------------


class TestAFrameworkThatCannotRunHalts:
    def test_missing_node_modules_fails_the_green_phase(self, tmp_path, capsys):
        root = _mixed_target(tmp_path, node_modules=False)
        recorder = _Recorder(pytest_passed=1, pytest_failed=0,
                             vitest_passed=1, vitest_failed=0)
        state = _run_state(
            root, [root / "tests" / "test_engine.py",
                   root / "web" / "tests" / "engine.test.ts"],
        )
        p1, p2, p3 = _patched(recorder)
        with p1, p2, p3:
            result = verify_green_phase(state)

        message = result["error_message"]
        assert "vitest" in message and "node_modules" in message
        assert str(root / "web") in message
        assert recorder.vitest_calls == [], "npx is never started without the runner installed"
        assert recorder.pytest_calls == [], "the phase stops before either suite runs"
        assert route_after_green({**state, **result}) == "HALT", (
            "HALT is where the operator is alerted (#3724)"
        )
        assert "ERROR" in capsys.readouterr().out

    def test_missing_node_modules_fails_the_red_phase(self, tmp_path):
        root = _mixed_target(tmp_path, node_modules=False)
        recorder = _Recorder(pytest_passed=0, pytest_failed=1,
                             vitest_passed=0, vitest_failed=1)
        state = _run_state(root, [root / "tests" / "test_engine.py"])
        p1, p2, p3 = _patched(recorder)
        with p1, p2, p3:
            result = verify_red_phase(state)

        assert "node_modules" in result["error_message"]
        assert recorder.vitest_calls == []

    def test_a_hoisted_node_modules_above_web_is_enough(self, tmp_path):
        """npm workspaces install at the root; Node resolves upwards."""
        root = _mixed_target(tmp_path, node_modules=False)
        (root / "node_modules" / ".bin").mkdir(parents=True)
        (root / "node_modules" / ".bin" / "vitest").write_text("", encoding="utf-8")
        (root / "node_modules" / "@vitest" / "coverage-v8").mkdir(parents=True)
        recorder = _Recorder(pytest_passed=1, pytest_failed=0,
                             vitest_passed=1, vitest_failed=0)
        state = _run_state(
            root, [root / "tests" / "test_engine.py",
                   root / "web" / "tests" / "engine.test.ts"],
        )
        p1, p2, p3 = _patched(recorder)
        with p1, p2, p3:
            result = verify_green_phase(state)

        assert result["error_message"] == ""

    def test_a_load_site_that_cannot_resolve_halts(self, tmp_path):
        """A package.json that cannot be read stops N0 through HALT; it used
        to raise out of the node."""
        root = _mixed_target(tmp_path)
        (root / "web" / "package.json").write_text("{not json", encoding="utf-8")
        result = _mock_load_lld({"issue_number": 7, "repo_root": str(root)})
        assert "package.json could not be read" in result["error_message"]
        assert route_after_load(result) == "HALT"


@pytest.mark.parametrize("phase", [verify_red_phase, verify_green_phase])
def test_a_run_with_one_framework_is_unchanged(phase, tmp_path):
    """A pytest-only target keeps the single-framework path: every test file
    goes to pytest, as before."""
    (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
    test_file = tmp_path / "tests" / "test_x.py"
    test_file.parent.mkdir()
    test_file.write_text("def test_x():\n    assert True\n", encoding="utf-8")
    loaded = _mock_load_lld({"issue_number": 7, "repo_root": str(tmp_path)})
    assert _placement(loaded["framework_configs"]) == (("pytest", None),)
    recorder = _Recorder(pytest_passed=0, pytest_failed=1,
                         vitest_passed=0, vitest_failed=0)
    state = _run_state(tmp_path, [test_file])
    p1, p2, p3 = _patched(recorder)
    with p1, p2, p3:
        phase(state)
    assert recorder.pytest_calls[0] == [str(test_file)]
    assert recorder.vitest_calls == []
