"""tdd_path_tracking.py under standard 0034, one test per sweep site (#3798).

``cleanup_stale_scaffold`` removes a scaffold test file once the real tests
live elsewhere. A removal that failed was a WARNING, and the stale scaffold
stayed beside the real tests, collected and run with them. It now raises the
removal's own error, which names the file. Line numbers in the names are
ledger 0908's, at its base ``79e18ad1``.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from assemblyzero.core import tdd_path_tracking as tpt

SCAFFOLD = "tests/test_issue_999.py"
UNIT = "tests/unit/test_module.py"


@pytest.fixture
def project(tmp_path, monkeypatch):
    (tmp_path / "tests" / "unit").mkdir(parents=True)
    (tmp_path / SCAFFOLD).touch()
    (tmp_path / UNIT).touch()
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _state() -> dict:
    return {"test_file_path": UNIT, "test_file_history": [SCAFFOLD, UNIT]}


def test_124_a_scaffold_that_cannot_be_removed_raises(project, monkeypatch):
    def refuse(path):
        raise PermissionError(13, "Permission denied", path)

    monkeypatch.setattr(tpt.os, "remove", refuse)

    with pytest.raises(PermissionError) as raised:
        tpt.cleanup_stale_scaffold(_state())
    assert raised.value.filename == SCAFFOLD
    assert (project / SCAFFOLD).exists()


def test_a_removable_scaffold_is_removed_quietly(project, caplog):
    """Kept: the cleanup that works logs at INFO and removes the file."""
    tpt.cleanup_stale_scaffold(_state())

    assert not (project / SCAFFOLD).exists()
    assert (project / UNIT).exists()
    assert not [r for r in caplog.records if r.levelname in ("WARNING", "ERROR")]


def test_an_already_absent_scaffold_is_not_a_failure(project):
    """Kept: a scaffold already gone has nothing to remove."""
    os.remove(project / SCAFFOLD)
    tpt.cleanup_stale_scaffold(_state())
    assert (project / UNIT).exists()
    assert not Path(project / SCAFFOLD).exists()
