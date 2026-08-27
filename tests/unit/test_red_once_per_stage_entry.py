"""Red is a property of stage entry, not of every attempt (#2542).

run-issue331-230544 — the first #331 run to pass lld, the operator-approved
visual gate, AND the spec stage — died 3 seconds into the impl stage's second
attempt: attempt 1 verified red against the clean worktree, implemented 2 of
its 3 planned files, and died on the third's LLM call; attempt 2 re-demanded
red against the worktree attempt 1 had just implemented into, found 8 tests
passing, and killed the run for the crime of its own progress.

The law now: the red verification is recorded at stage entry (the
``red-verified.json`` marker in the worktree-scoped audit dir); attempt
restarts consult the marker or the run's own surviving writes and resume the
implement-iterate loop against the current failure set; and a genuinely
pre-existing implementation at stage entry — no marker, no prior-attempt
writes — still halts, with a message that says which case it is.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.workflows.testing.nodes.verify_phases import (
    DETERMINISTIC_FAILURE,
    RED_MARKER_NAME,
    _implementation_already_exists,
    read_red_marker,
    verify_red_phase,
    write_red_marker,
)


@pytest.fixture()
def worktree(tmp_path: Path) -> Path:
    """The observed shape: 2 of 3 planned files written, the third missing."""
    skins = tmp_path / "src" / "boostgauge" / "skins"
    skins.mkdir(parents=True)
    (skins / "stingray.py").write_text(
        "def render_face(size):\n    return None\n", encoding="utf-8"
    )
    visual = tmp_path / "tests" / "visual"
    visual.mkdir(parents=True)
    (visual / "conftest.py").write_text("import pytest\n", encoding="utf-8")
    # tests/visual/test_stingray.py deliberately ABSENT — attempt 1's final
    # LLM call errored before writing it.
    tests = tmp_path / "tests"
    (tests / "test_issue_331.py").write_text(
        "def test_placeholder():\n    assert True\n", encoding="utf-8",
    )
    return tmp_path


def _state(worktree: Path, **overrides: object) -> dict:
    state = {
        "repo_root": str(worktree),
        "issue_number": 331,
        "audit_dir": str(worktree),
        "file_counter": 1,
        "test_files": [str(worktree / "tests" / "test_issue_331.py")],
        "files_to_modify": [
            {"path": "src/boostgauge/skins/stingray.py"},
            {"path": "tests/visual/conftest.py"},
            {"path": "tests/visual/test_stingray.py"},
        ],
        "retry_mode": "REGENERATED",
        "iteration_count": 0,
    }
    state.update(overrides)
    return state


def _pytest_result(passed: int, failed: int = 0) -> dict:
    return {
        "returncode": 1 if failed else 0,
        "stdout": f"{passed} passed, {failed} failed",
        "stderr": "",
        "parsed": {"passed": passed, "failed": failed, "errors": 0,
                   "coverage": 0},
    }


class TestTheObservedCase:
    """The acceptance's equivalent fixture: attempt 2 against the run's own
    partial implementation resumes against 5 failing tests — never
    re-demands red."""

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_attempt_two_resumes_the_loop_against_the_failure_set(
        self, mock_pytest, worktree: Path,
    ) -> None:
        mock_pytest.return_value = _pytest_result(passed=8, failed=5)

        result = verify_red_phase(_state(worktree))

        assert result["next_node"] == "N5_verify_green"
        assert result["error_message"] == ""

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_the_message_carries_the_current_failure_count(
        self, mock_pytest, worktree: Path, capsys,
    ) -> None:
        """Ask 4: the 5 named failures are the work; the resume names them
        rather than discarding them for a ceremony re-check."""
        mock_pytest.return_value = _pytest_result(passed=8, failed=5)

        verify_red_phase(_state(worktree))
        printed = capsys.readouterr().out
        assert "5 current failure(s)" in printed
        assert "resuming the implement-iterate loop" in printed.lower()

    def test_partial_writes_are_this_runs_own_work(self, worktree: Path) -> None:
        """2 of 3 planned files present + a later attempt = the run's own
        surviving implementation, per the run log's file-write record."""
        assert _implementation_already_exists(_state(worktree)) is True


class TestTheMarker:
    def test_a_valid_red_writes_the_stage_entry_marker(
        self, worktree: Path,
    ) -> None:
        with patch(
            "assemblyzero.workflows.testing.nodes.verify_phases.run_pytest"
        ) as mock_pytest:
            mock_pytest.return_value = _pytest_result(passed=0, failed=13)
            result = verify_red_phase(
                _state(worktree, retry_mode="", iteration_count=0)
            )
        assert result["next_node"] == "N4_implement_code"
        marker = json.loads(
            (worktree / RED_MARKER_NAME).read_text(encoding="utf-8")
        )
        assert marker["failing"] == 13
        assert marker["issue"] == 331

    def test_the_marker_alone_recognises_a_later_attempt(
        self, tmp_path: Path,
    ) -> None:
        """Even with every planned file cleared, the stage entry's verified
        red says passing tests are the loop's state, not an anomaly."""
        write_red_marker(
            _state(tmp_path, files_to_modify=[]), failing=13, exit_code=2,
        )
        state = _state(tmp_path, files_to_modify=[])
        assert _implementation_already_exists(state) is True

    def test_a_first_attempt_never_consults_the_marker(
        self, worktree: Path,
    ) -> None:
        """A stale marker cannot suppress a genuine entry's red demand: the
        marker is only read on a later attempt."""
        write_red_marker(_state(worktree), failing=13, exit_code=2)
        state = _state(worktree, retry_mode="", iteration_count=0)
        assert _implementation_already_exists(state) is False

    def test_a_corrupt_marker_abstains(self, worktree: Path) -> None:
        (worktree / RED_MARKER_NAME).write_text("{not json", encoding="utf-8")
        assert read_red_marker(_state(worktree)) is None
        # The file evidence still carries the later-attempt case.
        assert _implementation_already_exists(_state(worktree)) is True


class TestGenuinePreExistingStillHalts:
    """The guard's founding case is preserved: implementation present at
    STAGE ENTRY, with no marker and no prior-attempt writes, halts."""

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_first_attempt_green_at_red_halts_deterministically(
        self, mock_pytest, worktree: Path,
    ) -> None:
        mock_pytest.return_value = _pytest_result(passed=8)

        result = verify_red_phase(
            _state(worktree, retry_mode="", iteration_count=0)
        )

        assert result["next_node"] == "END"
        assert DETERMINISTIC_FAILURE in result["error_message"]

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_the_halt_message_says_before_this_stage_entered(
        self, mock_pytest, worktree: Path,
    ) -> None:
        """Ask 3: the anomaly halt and the loop-state resume are different
        sentences."""
        mock_pytest.return_value = _pytest_result(passed=8)

        result = verify_red_phase(
            _state(worktree, retry_mode="", iteration_count=0)
        )

        assert "before this stage entered" in result["error_message"]
        assert "re-demand" not in result["error_message"]
