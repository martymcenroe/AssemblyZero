"""#2670: the red-phase guard gains Modify-awareness.

run-issue379-015229 halted in six seconds: 8 real tests, 3 passing at a
first-attempt red entry, and the #2542 guard read "the implementation existed
before this stage entered" as fatal. On a Modify issue that is the plan's own
declared state — boostgauge #379 modifies `stingray.py` on an arc that ships
it, and the passing three are conjunction partners and regression guards the
green phase already holds to staying green.

The sanctioned reading is narrow: every planned .py is change_type Modify AND
present on disk, and at least one test still fails (the red signal). An Add in
the plan, a missing change_type, or all-green at entry each keep the fatal
halt — the #2337/#2542 later-attempt paths are untouched.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.workflows.testing.nodes.verify_phases import (
    _base_ships_the_implementation,
    verify_red_phase,
)


@pytest.fixture()
def worktree(tmp_path: Path) -> Path:
    """A pristine Modify-issue worktree: the base ships the module."""
    src = tmp_path / "src" / "boostgauge" / "skins"
    src.mkdir(parents=True)
    (src / "stingray.py").write_text(
        "def render_face(size):\n    return None\n", encoding="utf-8"
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_issue_379.py").write_text(
        "def test_placeholder():\n    assert True\n", encoding="utf-8"
    )
    return tmp_path


def _state(worktree: Path, **overrides: object) -> dict:
    state = {
        "repo_root": str(worktree),
        "issue_number": 379,
        "audit_dir": str(worktree),
        "file_counter": 1,
        "test_files": [str(worktree / "tests" / "test_issue_379.py")],
        "files_to_modify": [
            {"path": "src/boostgauge/skins/stingray.py", "change_type": "Modify"},
        ],
        # first attempt: the paths #2337/#2542 sanction must all decline
        "retry_mode": "",
        "iteration_count": 0,
    }
    state.update(overrides)
    return state


def _pytest_result(passed: int, failed: int) -> dict:
    return {
        "returncode": 0 if failed == 0 else 1,
        "stdout": f"{passed} passed, {failed} failed",
        "stderr": "",
        "parsed": {
            "passed": passed, "failed": failed, "errors": 0, "coverage": 0,
        },
    }


# ------------------------------------------------- the helper's truth table


def test_all_modify_and_present_is_base_shipped(worktree: Path) -> None:
    assert _base_ships_the_implementation(_state(worktree)) is True


def test_an_add_in_the_plan_is_not(worktree: Path) -> None:
    state = _state(worktree, files_to_modify=[
        {"path": "src/boostgauge/skins/stingray.py", "change_type": "Modify"},
        {"path": "src/boostgauge/skins/telltale.py", "change_type": "Add"},
    ])
    assert _base_ships_the_implementation(state) is False


def test_a_missing_change_type_is_never_forgiven(worktree: Path) -> None:
    """The #2337 fixture shape — path only — must not be read as Modify."""
    state = _state(worktree, files_to_modify=[
        {"path": "src/boostgauge/skins/stingray.py"},
    ])
    assert _base_ships_the_implementation(state) is False


def test_a_planned_file_absent_from_disk_is_not(worktree: Path) -> None:
    state = _state(worktree, files_to_modify=[
        {"path": "src/boostgauge/skins/missing.py", "change_type": "Modify"},
    ])
    assert _base_ships_the_implementation(state) is False


def test_an_empty_plan_explains_nothing(worktree: Path) -> None:
    assert _base_ships_the_implementation(
        _state(worktree, files_to_modify=[])
    ) is False


# ------------------------------------------------- the node's behaviour


@patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
def test_the_379_shape_proceeds_to_implement(
    mock_pytest, worktree: Path,
) -> None:
    """3 base-satisfied guards pass, 5 failures drive the implementation."""
    mock_pytest.return_value = _pytest_result(passed=3, failed=5)

    result = verify_red_phase(_state(worktree))

    assert result["next_node"] == "N4_implement_code"
    assert result["error_message"] == ""


@patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
def test_an_add_in_the_plan_keeps_the_fatal_halt(
    mock_pytest, worktree: Path,
) -> None:
    mock_pytest.return_value = _pytest_result(passed=3, failed=5)

    state = _state(worktree, files_to_modify=[
        {"path": "src/boostgauge/skins/stingray.py", "change_type": "Add"},
    ])
    result = verify_red_phase(state)

    assert result["next_node"] == "END"
    assert "passed unexpectedly" in result["error_message"]


@patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
def test_all_green_at_entry_stays_fatal_even_on_modify(
    mock_pytest, worktree: Path,
) -> None:
    """No failing test means nothing drives the change — vacuous tests or
    nothing to implement, and proceeding would ship the former."""
    mock_pytest.return_value = _pytest_result(passed=8, failed=0)

    result = verify_red_phase(_state(worktree))

    assert result["next_node"] == "END"
    assert "passed unexpectedly" in result["error_message"]
