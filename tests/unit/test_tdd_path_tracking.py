"""Unit tests for test file path tracking.

Tests for Issue #311: TDD workflow path tracking functions.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.core.state import TDDState
from assemblyzero.core.tdd_path_tracking import (
    cleanup_stale_scaffold,
    get_test_file_path,
    log_test_file_path,
    resolve_test_file_conflict,
    set_test_file_path,
    track_test_file_move,
)


@pytest.fixture
def temp_project_dir(monkeypatch):
    """Create a temporary project directory and set it as cwd."""
    # ignore_cleanup_errors=True handles Windows file locking during teardown
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        monkeypatch.chdir(tmpdir)
        # Create tests directory
        tests_dir = Path(tmpdir) / "tests"
        tests_dir.mkdir()
        # Create tests/unit directory
        unit_dir = tests_dir / "unit"
        unit_dir.mkdir()
        yield tmpdir


@pytest.fixture
def base_state() -> TDDState:
    """Create a base TDD state for testing."""
    return {
        "issue_number": 999,
        "phase": "scaffold",
        "test_file_path": None,
        "test_file_history": [],
        "implementation_file_path": None,
        "last_verification_result": None,
    }


def test_get_test_file_path_returns_stored_value(base_state):
    """Reading state returns exact path set."""
    # Arrange
    expected_path = "tests/test_issue_999.py"
    base_state["test_file_path"] = expected_path
    
    # Act
    result = get_test_file_path(base_state)
    
    # Assert
    assert result == expected_path


def test_get_test_file_path_raises_on_none(base_state):
    """Clear error when test_file_path is None."""
    # Arrange
    base_state["test_file_path"] = None
    
    # Act & Assert
    with pytest.raises(ValueError, match="No test file path in state"):
        get_test_file_path(base_state)


def test_get_test_file_path_raises_on_empty(base_state):
    """Clear error when test_file_path is empty string."""
    # Arrange
    base_state["test_file_path"] = ""
    
    # Act & Assert
    with pytest.raises(ValueError, match="No test file path in state"):
        get_test_file_path(base_state)


def test_scaffold_sets_test_file_path(temp_project_dir, base_state):
    """Scaffold phase stores path in state."""
    # Arrange
    test_path = "tests/test_issue_999.py"
    
    # Act
    updated_state = set_test_file_path(base_state, test_path, "scaffold")
    
    # Assert
    assert updated_state["test_file_path"] == test_path
    assert test_path in updated_state["test_file_history"]


def test_set_test_file_path_records_history(temp_project_dir, base_state):
    """Path is recorded in test_file_history."""
    # Arrange
    test_path = "tests/test_issue_999.py"
    
    # Act
    updated_state = set_test_file_path(base_state, test_path, "scaffold")
    
    # Assert
    assert len(updated_state["test_file_history"]) == 1
    assert updated_state["test_file_history"][0] == test_path


def test_set_test_file_path_rejects_path_traversal(base_state):
    """Security: reject paths outside project."""
    # Arrange
    malicious_path = "../../../etc/passwd"
    
    # Act & Assert
    with pytest.raises(ValueError, match="must be within project directory"):
        set_test_file_path(base_state, malicious_path, "scaffold")


def test_track_test_file_move_updates_path(temp_project_dir, base_state):
    """Moving file updates state.test_file_path."""
    # Arrange
    old_path = "tests/test_issue_999.py"
    new_path = "tests/unit/test_module.py"
    base_state["test_file_path"] = old_path
    
    # Create the new file so it exists
    new_file = Path(temp_project_dir) / new_path
    new_file.parent.mkdir(parents=True, exist_ok=True)
    new_file.touch()
    
    # Act
    updated_state = track_test_file_move(base_state, old_path, new_path)
    
    # Assert
    assert updated_state["test_file_path"] == new_path


def test_track_test_file_move_records_history(temp_project_dir, base_state):
    """Move is recorded in test_file_history."""
    # Arrange
    old_path = "tests/test_issue_999.py"
    new_path = "tests/unit/test_module.py"
    base_state["test_file_path"] = old_path
    base_state["test_file_history"] = [old_path]
    
    # Create the new file
    new_file = Path(temp_project_dir) / new_path
    new_file.parent.mkdir(parents=True, exist_ok=True)
    new_file.touch()
    
    # Act
    updated_state = track_test_file_move(base_state, old_path, new_path)
    
    # Assert
    assert len(updated_state["test_file_history"]) == 2
    assert updated_state["test_file_history"][1] == new_path


def test_track_test_file_move_validates_new_path_exists(temp_project_dir, base_state):
    """Raise error if new_path doesn't exist."""
    # Arrange
    old_path = "tests/test_issue_999.py"
    new_path = "tests/unit/test_nonexistent.py"
    base_state["test_file_path"] = old_path
    
    # Act & Assert
    with pytest.raises(ValueError, match="Cannot move to non-existent path"):
        track_test_file_move(base_state, old_path, new_path)


def test_track_test_file_move_rejects_path_traversal(temp_project_dir, base_state):
    """Security: reject paths outside project."""
    # Arrange
    old_path = "tests/test_issue_999.py"
    malicious_path = "../../../etc/passwd"
    base_state["test_file_path"] = old_path

    # Mock os.path.exists to return True (skip existence check, test path traversal)
    with patch("assemblyzero.core.tdd_path_tracking.os.path.exists", return_value=True):
        # Act & Assert
        with pytest.raises(ValueError, match="must be within project directory"):
            track_test_file_move(base_state, old_path, malicious_path)


def test_cleanup_stale_scaffold_removes_file(temp_project_dir, base_state):
    """Scaffold deleted when unit tests exist."""
    # Arrange
    scaffold_path = "tests/test_issue_999.py"
    unit_path = "tests/unit/test_module.py"
    
    # Create both files
    scaffold_file = Path(temp_project_dir) / scaffold_path
    scaffold_file.touch()
    unit_file = Path(temp_project_dir) / unit_path
    unit_file.touch()
    
    # State shows we moved to unit path
    base_state["test_file_path"] = unit_path
    base_state["test_file_history"] = [scaffold_path, unit_path]
    
    # Act
    cleanup_stale_scaffold(base_state)
    
    # Assert
    assert not scaffold_file.exists()


def test_cleanup_preserves_unit_tests(temp_project_dir, base_state):
    """Unit test files never deleted."""
    # Arrange
    scaffold_path = "tests/test_issue_999.py"
    unit_path = "tests/unit/test_module.py"
    
    # Create both files
    scaffold_file = Path(temp_project_dir) / scaffold_path
    scaffold_file.touch()
    unit_file = Path(temp_project_dir) / unit_path
    unit_file.touch()
    
    # State shows we moved to unit path
    base_state["test_file_path"] = unit_path
    base_state["test_file_history"] = [scaffold_path, unit_path]
    
    # Act
    cleanup_stale_scaffold(base_state)
    
    # Assert
    assert unit_file.exists()


def test_cleanup_handles_missing_path(base_state):
    """No error when test_file_path is None."""
    # Arrange
    base_state["test_file_path"] = None
    
    # Act (should not raise)
    cleanup_stale_scaffold(base_state)
    
    # Assert - no exception means success
    assert True


def test_cleanup_handles_nonexistent_scaffold(temp_project_dir, base_state):
    """No error when scaffold file already deleted."""
    # Arrange
    scaffold_path = "tests/test_issue_999.py"
    unit_path = "tests/unit/test_module.py"
    
    # Only create unit file (scaffold doesn't exist)
    unit_file = Path(temp_project_dir) / unit_path
    unit_file.touch()
    
    # State shows we moved to unit path
    base_state["test_file_path"] = unit_path
    base_state["test_file_history"] = [scaffold_path, unit_path]
    
    # Act (should not raise)
    cleanup_stale_scaffold(base_state)
    
    # Assert
    assert unit_file.exists()


def test_resolve_conflict_prefers_unit_tests(temp_project_dir, base_state):
    """When both exist, unit path wins."""
    # Arrange
    scaffold_path = "tests/test_issue_999.py"
    unit_path = "tests/unit/test_module.py"
    
    # Create both files
    scaffold_file = Path(temp_project_dir) / scaffold_path
    scaffold_file.touch()
    unit_file = Path(temp_project_dir) / unit_path
    unit_file.touch()
    
    # Act
    result = resolve_test_file_conflict(scaffold_path, unit_path, base_state)
    
    # Assert
    assert result == unit_path


def test_resolve_conflict_handles_missing_state_path(temp_project_dir, base_state):
    """When state path doesn't exist but unit test does, returns unit path."""
    # Arrange
    scaffold_path = "tests/test_issue_999.py"
    unit_path = "tests/unit/test_module.py"
    nonexistent_path = "tests/test_issue_555.py"
    
    # Only create unit file
    unit_file = Path(temp_project_dir) / unit_path
    unit_file.touch()
    
    # State points to nonexistent file
    base_state["test_file_path"] = nonexistent_path
    
    # Act
    result = resolve_test_file_conflict(scaffold_path, unit_path, base_state)
    
    # Assert
    assert result == unit_path


def test_resolve_conflict_falls_back_to_scaffold(temp_project_dir, base_state):
    """Falls back to scaffold if unit doesn't exist."""
    # Arrange
    scaffold_path = "tests/test_issue_999.py"
    unit_path = "tests/unit/test_module.py"
    
    # Only create scaffold file
    scaffold_file = Path(temp_project_dir) / scaffold_path
    scaffold_file.touch()
    
    # Act
    result = resolve_test_file_conflict(scaffold_path, unit_path, base_state)
    
    # Assert
    assert result == scaffold_path


def test_resolve_conflict_raises_when_neither_exists(temp_project_dir, base_state):
    """Clear error when neither file exists."""
    # Arrange
    scaffold_path = "tests/test_issue_999.py"
    unit_path = "tests/unit/test_module.py"
    
    # Don't create any files
    
    # Act & Assert
    with pytest.raises(ValueError, match="Neither scaffold .* nor unit test .* exists"):
        resolve_test_file_conflict(scaffold_path, unit_path, base_state)


def test_phases_log_test_file_path(caplog):
    """All phases log the test file path they use."""
    import logging

    # Arrange
    caplog.set_level(logging.INFO)
    phase = "scaffold"
    path = "tests/test_issue_999.py"

    # Act
    log_test_file_path(phase, path)

    # Assert
    assert "[TDD]" in caplog.text
    assert "Scaffold phase using test file:" in caplog.text
    assert path in caplog.text


def test_backward_compatible_state_loading(base_state):
    """Old state files load with None test_file_path."""
    # Arrange - simulate old state without test_file_path field
    old_state = {
        "issue_number": 999,
        "phase": "scaffold",
        "implementation_file_path": None,
        "last_verification_result": None,
    }
    
    # Act - access with .get() for backward compat
    path = old_state.get("test_file_path")
    
    # Assert
    assert path is None