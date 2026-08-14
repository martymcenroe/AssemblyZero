"""#2338: a stage that dies should end at its best measured state.

`run-issue7-192332` logged "best iteration so far: 23 passing at 78.0% —
snapshotted 3 file(s)", and thirteen seconds later ended holding a test file
that could not be collected. The snapshot sat unused.

`_hill_climb` (#2050) is a within-loop ratchet -- a worse iteration restores
the best files so the next revision starts from there -- and it works. What
no path did was consult it on TERMINAL failure, which is exactly when the
worktree stops being scratch space and becomes what a resume picks up and
what the operator inspects.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.workflows.testing.nodes.verify_phases import (
    restore_best_on_failure,
    verify_green_phase,
)


@pytest.fixture()
def snapshotted(tmp_path: Path) -> tuple[Path, Path, dict]:
    """A worktree whose live file is broken and whose snapshot is good."""
    live = tmp_path / "tests" / "test_issue_7.py"
    live.parent.mkdir(parents=True)
    live.write_text(
        "from pkg.config import does_not_exist\n", encoding="utf-8",
    )

    snap = tmp_path / "audit" / "best-iteration" / "00-test_issue_7.py"
    snap.parent.mkdir(parents=True)
    snap.write_text("def test_real():\n    assert True\n", encoding="utf-8")

    best = {
        "passed": 23,
        "coverage": 78.0,
        "green_failures": [],
        "files": {str(live): str(snap)},
    }
    return live, snap, best


def test_the_worktree_ends_holding_the_best_state(snapshotted) -> None:
    live, _snap, best = snapshotted

    described = restore_best_on_failure({"best_iteration": best})

    assert "23 passing at 78.0% coverage" == described
    assert "does_not_exist" not in live.read_text(encoding="utf-8"), (
        "the broken file must not survive the restore"
    )
    assert "def test_real" in live.read_text(encoding="utf-8")


def test_nothing_to_restore_is_silent() -> None:
    assert restore_best_on_failure({}) == ""
    assert restore_best_on_failure({"best_iteration": None}) == ""
    assert restore_best_on_failure({"best_iteration": {"files": {}}}) == ""


def test_a_missing_snapshot_file_is_not_a_restore(tmp_path: Path) -> None:
    """A manifest pointing at nothing must not claim success."""
    live = tmp_path / "t.py"
    live.write_text("broken\n", encoding="utf-8")
    best = {"passed": 1, "coverage": 1.0,
            "files": {str(live): str(tmp_path / "gone.py")}}

    assert restore_best_on_failure({"best_iteration": best}) == ""
    assert live.read_text(encoding="utf-8") == "broken\n"


def test_restore_trouble_never_raises(tmp_path: Path) -> None:
    """Restoration must never mask the failure the operator needs to read."""
    best = {"passed": 1, "coverage": 1.0,
            "files": {str(tmp_path / "nope" / "x.py"): str(tmp_path / "s.py")}}
    (tmp_path / "s.py").write_text("ok\n", encoding="utf-8")

    assert restore_best_on_failure({"best_iteration": best}) == ""


@patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
def test_collection_death_restores_and_says_so(
    mock_pytest, snapshotted, tmp_path: Path,
) -> None:
    """The live path: exit 2 after a good snapshot."""
    live, _snap, best = snapshotted
    mock_pytest.return_value = {
        "returncode": 2,
        "stdout": "ImportError: cannot import name 'does_not_exist'",
        "stderr": "",
        "parsed": {"passed": 0, "failed": 0, "errors": 0, "coverage": 0},
    }

    result = verify_green_phase({
        "repo_root": str(tmp_path),
        "issue_number": 7,
        "audit_dir": str(tmp_path / "audit"),
        "file_counter": 1,
        "test_files": [str(live)],
        "implementation_files": [],
        "coverage_target": 95,
        "iteration_count": 1,
        "max_iterations": 5,
        "best_iteration": best,
    })

    assert result["next_node"] == "end"
    message = result["error_message"]
    assert "23 passing at 78.0% coverage" in message, (
        "the operator should be told what the worktree now holds"
    )
    # The original diagnosis must survive alongside it.
    assert "exit code 2" in message.lower()
    assert "def test_real" in live.read_text(encoding="utf-8")
