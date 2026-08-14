"""#2337: green-at-red is only fatal when nothing has been implemented yet.

`run-issue7-192332` died at N5 on attempt 1. Attempts 2 and 3 then scaffolded
23 tests, found the implementation attempt 1 had written, went green at the
red phase, and ended the stage -- about two seconds of work each, twelve
seconds apart. Nothing had changed between them, so nothing could have.

Two defects:
  - green-at-red was fatal unconditionally, even when the implementation
    legitimately existed (a retry, or a resume into a worktree with prior
    work), and
  - the failure was retried, though it is deterministic on an unchanged
    worktree -- the #2298 rule with a new cause.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.workflows.orchestrator.stages import _is_non_transient_halt
from assemblyzero.workflows.testing.graph import route_after_red
from assemblyzero.workflows.testing.nodes.verify_phases import (
    DETERMINISTIC_FAILURE,
    _implementation_already_exists,
    verify_red_phase,
)


@pytest.fixture()
def worktree(tmp_path: Path) -> Path:
    src = tmp_path / "src" / "boostgauge"
    src.mkdir(parents=True)
    (src / "config.py").write_text("def get_default_config():\n    return {}\n",
                                   encoding="utf-8")
    (src / "app.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    # The node checks the test file exists before running pytest, so the
    # fixture has to be a plausible worktree rather than just source files.
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_issue_7.py").write_text(
        "def test_placeholder():\n    assert True\n", encoding="utf-8",
    )
    return tmp_path


def _state(worktree: Path, **overrides: object) -> dict:
    state = {
        "repo_root": str(worktree),
        "issue_number": 7,
        "audit_dir": str(worktree),
        "file_counter": 1,
        "test_files": [str(worktree / "tests" / "test_issue_7.py")],
        "files_to_modify": [
            {"path": "src/boostgauge/config.py"},
            {"path": "src/boostgauge/app.py"},
        ],
        "retry_mode": "REGENERATED",
        "iteration_count": 0,
    }
    state.update(overrides)
    return state


# ------------------------------------------------- detecting prior work


def test_a_retry_with_files_present_is_recognised(worktree: Path) -> None:
    assert _implementation_already_exists(_state(worktree)) is True


def test_a_first_attempt_is_not(worktree: Path) -> None:
    """The pre-existing-implementation guard still applies on attempt 1."""
    state = _state(worktree, retry_mode="", iteration_count=0)
    assert _implementation_already_exists(state) is False


def test_a_retry_whose_files_were_cleared_is_not(tmp_path: Path) -> None:
    """Files genuinely absent -> the red phase is meaningful again."""
    assert _implementation_already_exists(_state(tmp_path)) is False


def test_a_resume_counts_as_a_later_attempt(worktree: Path) -> None:
    state = _state(worktree, retry_mode="", iteration_count=2)
    assert _implementation_already_exists(state) is True


def test_partial_implementation_is_not_enough(worktree: Path) -> None:
    """One of two files present is not a surviving implementation."""
    (worktree / "src" / "boostgauge" / "app.py").unlink()
    assert _implementation_already_exists(_state(worktree)) is False


def test_no_declared_targets_is_not_enough(worktree: Path) -> None:
    assert _implementation_already_exists(
        _state(worktree, files_to_modify=[])
    ) is False


# ------------------------------------------------- the node's behaviour


def _pytest_result(passed: int) -> dict:
    return {
        "returncode": 0,
        "stdout": f"{passed} passed",
        "stderr": "",
        "parsed": {"passed": passed, "failed": 0, "errors": 0, "coverage": 0},
    }


@patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
def test_retry_with_surviving_implementation_proceeds(
    mock_pytest, worktree: Path,
) -> None:
    """The live case: 23 pass, implementation is there, so verify it."""
    mock_pytest.return_value = _pytest_result(23)

    result = verify_red_phase(_state(worktree))

    assert result["next_node"] == "N5_verify_green"
    assert result["error_message"] == ""


@patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
def test_first_attempt_green_at_red_still_ends_the_stage(
    mock_pytest, worktree: Path,
) -> None:
    """Tests that pass before any code exists are not testing anything."""
    mock_pytest.return_value = _pytest_result(23)

    result = verify_red_phase(_state(worktree, retry_mode="", iteration_count=0))

    assert result["next_node"] == "END"
    assert "passed unexpectedly" in result["error_message"]


@patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
def test_that_failure_is_marked_deterministic(
    mock_pytest, worktree: Path,
) -> None:
    """#2298's rule: a failure a re-run cannot change is not retried."""
    mock_pytest.return_value = _pytest_result(23)

    result = verify_red_phase(_state(worktree, retry_mode="", iteration_count=0))

    assert DETERMINISTIC_FAILURE in result["error_message"]
    assert _is_non_transient_halt(
        {"error_message": result["error_message"]}
    ) is False, "a deterministic failure must not be retried"


# ------------------------------------------------- routing


def test_route_accepts_the_verify_destination() -> None:
    assert route_after_red(
        {"error_message": "", "next_node": "N5_verify_green"}
    ) == "N5_verify_green"


@pytest.mark.parametrize("next_node,expected", [
    ("N4_implement_code", "N4_implement_code"),
    ("N2_scaffold_tests", "N2_scaffold_tests"),
    ("END", "end"),
])
def test_existing_routes_are_unchanged(next_node: str, expected: str) -> None:
    assert route_after_red(
        {"error_message": "", "next_node": next_node}
    ) == expected


def test_an_error_still_ends_regardless() -> None:
    assert route_after_red(
        {"error_message": "boom", "next_node": "N5_verify_green"}
    ) == "end"
