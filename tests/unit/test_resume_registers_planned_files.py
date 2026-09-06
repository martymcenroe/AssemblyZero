"""A resumed run's red phase registers the plan's files it finds (#2897).

boostgauge #4, `run-issue4-020617` (2026-09-06 02:06), resumed from run 32's
preserved worktree -- the 38-of-38 tree, 91 % over collector.py and
collectors/windows.py:

    [N3] 13 test(s) pass, and files this run's prior attempt wrote are present in the worktree.
    [N5] Derived coverage module from LLD files_to_modify: boostgauge.collector
    [N5] Results: 13 passed, 0 failed | Coverage: 83.0%
    [N5] all 13 test(s) pass; coverage 83.0% < 95% target -- this is a test gap, routing to test additions
    [N4c] 83.0% vs 95% target; targeting uncovered lines in 1 file(s)

Thirteen tests is the scaffold alone. The plan's three test files -- 25 tests,
on disk and passing on the previous run -- were never in the measurement, and
the coverage was of one module. N2 sets `test_files` to the scaffold; N4 grows
it and sets `implementation_files`; the #2337/#2542 branch of N3 routes to N5
without N4. Runs 29-32 hid the gap because their scaffold failed to collect on
entry, which sent N3 through N4 first.

The red phase now registers what it found, the way N4 would have, before it
routes on.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.core.retry_mode import RESUMED
from assemblyzero.workflows.testing.nodes import verify_phases
from assemblyzero.workflows.testing.nodes.verify_phases import (
    _is_test_path,
    _register_prior_attempt_files,
    verify_red_phase,
)

RUN_33_PLAN = [
    {"path": "src/boostgauge/collector.py", "change_type": "Add"},
    {"path": "src/boostgauge/collectors/windows.py", "change_type": "Add"},
    {"path": "tests/unit/test_collector.py", "change_type": "Add"},
    {"path": "tests/integration/test_windows_sweep_crosscheck.py", "change_type": "Add"},
    {"path": "tests/benchmark/test_sweep_cost.py", "change_type": "Add"},
]


@pytest.fixture
def worktree(tmp_path: Path) -> Path:
    """Run 32's preserved tree: the scaffold plus all five planned files."""
    for spec in RUN_33_PLAN:
        path = tmp_path / spec["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# prior attempt\n", encoding="utf-8")
    (tmp_path / "tests" / "test_issue_4.py").write_text("# scaffold\n", encoding="utf-8")
    return tmp_path


def _state(worktree: Path, **overrides) -> dict:
    state = {
        "repo_root": str(worktree),
        "issue_number": 4,
        "audit_dir": "",
        "test_files": [str(worktree / "tests" / "test_issue_4.py")],
        "implementation_files": [],
        "files_to_modify": [dict(s) for s in RUN_33_PLAN],
        "spec_test_suite": {"functions": [{"name": "test_req_1", "source": "def test_req_1(): pass"}]},
        "retry_mode": RESUMED,
        "iteration_count": 0,
        "coverage_target": 95,
    }
    state.update(overrides)
    return state


def _red_result(passed: int, failed: int, errors: int = 0) -> dict:
    return {
        "returncode": 1 if failed or errors else 0,
        "stdout": f"{passed} passed, {failed} failed, {errors} errors",
        "stderr": "",
        "parsed": {"passed": passed, "failed": failed, "errors": errors, "coverage": 0.0},
    }


class TestRun33:
    def test_the_plans_files_are_registered_on_the_resume_route(self, worktree, capsys):
        with patch.object(verify_phases, "run_pytest", return_value=_red_result(13, 0)):
            result = verify_red_phase(_state(worktree))

        assert result["next_node"] == "N5_verify_green"
        assert [Path(p).name for p in result["test_files"]] == [
            "test_issue_4.py", "test_collector.py",
            "test_windows_sweep_crosscheck.py", "test_sweep_cost.py",
        ]
        assert [Path(p).name for p in result["implementation_files"]] == [
            "collector.py", "windows.py",
        ]
        assert (
            "[N3] registered the prior attempt's 3 test file(s) and 2 source "
            "file(s) from the plan, as N4 would have (#2897)"
        ) in capsys.readouterr().out

    def test_the_scaffold_stays_first_as_the_contract(self, worktree):
        """#2709: the spec's suite runs first; the plan's tests follow."""
        with patch.object(verify_phases, "run_pytest", return_value=_red_result(13, 0)):
            result = verify_red_phase(_state(worktree))

        assert result["test_files"][0].endswith("test_issue_4.py")
        assert (worktree / "tests" / "test_issue_4.py").exists()

    def test_registered_paths_are_absolute_like_n4s(self, worktree):
        with patch.object(verify_phases, "run_pytest", return_value=_red_result(13, 0)):
            result = verify_red_phase(_state(worktree))

        for p in result["test_files"] + result["implementation_files"]:
            assert Path(p).is_absolute()
            assert Path(p).is_file()

    def test_a_first_attempt_with_passing_tests_is_still_fatal(self, worktree):
        """#2337 unchanged: no retry_mode and no iteration means green-at-red."""
        with patch.object(verify_phases, "run_pytest", return_value=_red_result(13, 0)):
            result = verify_red_phase(_state(worktree, retry_mode=""))

        assert result["next_node"] != "N5_verify_green"
        assert "test_files" not in result
        assert result.get("error_message")

    def test_a_red_that_fails_as_it_should_registers_nothing(self, worktree):
        """All failing is the ordinary red; N4 will run and register as before."""
        with patch.object(verify_phases, "run_pytest", return_value=_red_result(0, 13)):
            result = verify_red_phase(_state(worktree))

        assert "test_files" not in result
        assert "implementation_files" not in result


class TestTheHelper:
    def test_only_planned_files_present_on_disk_count(self, worktree):
        (worktree / "src" / "boostgauge" / "collectors" / "windows.py").unlink()

        updates = _register_prior_attempt_files(_state(worktree))

        assert [Path(p).name for p in updates["implementation_files"]] == ["collector.py"]

    def test_nothing_present_registers_nothing(self, tmp_path):
        assert _register_prior_attempt_files(_state(tmp_path)) == {}

    def test_already_registered_sources_are_not_duplicated(self, worktree):
        state = _state(worktree, implementation_files=[str(worktree / "src" / "boostgauge" / "collector.py")])

        updates = _register_prior_attempt_files(state)

        assert [Path(p).name for p in updates["implementation_files"]] == ["collector.py", "windows.py"]

    def test_the_suffix_filter_is_the_frameworks(self, worktree):
        (worktree / "src" / "boostgauge" / "app.ts").write_text("", encoding="utf-8")
        state = _state(worktree, files_to_modify=[{"path": "src/boostgauge/app.ts", "change_type": "Add"}])

        assert _register_prior_attempt_files(state) == {}
        assert [Path(p).name for p in _register_prior_attempt_files(state, (".ts",))["implementation_files"]] == ["app.ts"]

    @pytest.mark.parametrize("path, expected", [
        ("tests/unit/test_collector.py", True),
        ("tests/benchmark/test_sweep_cost.py", True),
        ("src/boostgauge/collector.py", False),
        ("src/boostgauge/collectors/windows.py", False),
        ("tests/conftest.py", False),
        ("src/app/__tests__/app.test.ts", True),
        ("src/app/app.spec.ts", True),
        ("C:\\repo\\tests\\unit\\test_x.py", True),
    ])
    def test_which_paths_are_tests(self, path, expected):
        assert _is_test_path(path) is expected
