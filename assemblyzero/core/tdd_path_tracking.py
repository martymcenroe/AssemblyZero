"""Test file path tracking functions for TDD workflow.

This module provides functions to track and manage test file paths
across TDD phases (scaffold, red, green, refactor).

Fixes Issue #311: Ensures all phases use consistent test file paths.
"""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from assemblyzero.core.state import TDDState

logger = logging.getLogger(__name__)


def get_test_file_path(state: TDDState) -> str:
    """Get the canonical test file path from state.
    
    Args:
        state: Current TDD state
        
    Returns:
        The test file path stored in state
        
    Raises:
        ValueError: If test_file_path is None or empty
    """
    path = state.get("test_file_path")
    if not path:
        raise ValueError("No test file path in state")
    return path


def set_test_file_path(state: TDDState, path: str, phase: str) -> TDDState:
    """Set the test file path, recording the phase that set it.
    
    Args:
        state: Current TDD state
        path: Path to the test file
        phase: Phase setting the path ("scaffold", "red", "green", "refactor")
        
    Returns:
        Updated state with path set and history recorded
    """
    # Validate path is within project (security: prevent path traversal)
    abs_path = os.path.abspath(path)
    if not abs_path.startswith(os.getcwd()):
        raise ValueError(f"Test file path must be within project directory: {path}")
    
    # Update state
    state["test_file_path"] = path
    
    # Record in history
    history = state.get("test_file_history", [])
    history.append(path)
    state["test_file_history"] = history
    
    log_test_file_path(phase, path)
    
    return state


def track_test_file_move(state: TDDState, old_path: str, new_path: str) -> TDDState:
    """Record when a test file is moved to a new location.
    
    Args:
        state: Current TDD state
        old_path: Previous path
        new_path: New path
        
    Returns:
        Updated state with new path and move recorded
        
    Raises:
        ValueError: If new_path doesn't exist
    """
    # Validate new path exists before updating state
    if not os.path.exists(new_path):
        raise ValueError(f"Cannot move to non-existent path: {new_path}")
    
    # Validate path is within project (security: prevent path traversal)
    abs_path = os.path.abspath(new_path)
    if not abs_path.startswith(os.getcwd()):
        raise ValueError(f"Test file path must be within project directory: {new_path}")
    
    # Update path
    state["test_file_path"] = new_path
    
    # Record in history
    history = state.get("test_file_history", [])
    history.append(new_path)
    state["test_file_history"] = history
    
    logger.info(f"Test file moved: {old_path} -> {new_path}")
    
    return state


def cleanup_stale_scaffold(state: TDDState) -> None:
    """Remove scaffold test file if real tests exist elsewhere.
    
    Only deletes files matching the scaffold pattern: tests/test_issue_N.py
    Never deletes unit test files.
    
    Args:
        state: Current TDD state
    """
    # Get current test path
    current_path = state.get("test_file_path")
    if not current_path:
        return
    
    # Check history for scaffold files
    history = state.get("test_file_history", [])
    for old_path in history:
        # Only cleanup scaffold pattern files (safety: prevent deleting real tests)
        if _is_scaffold_file(old_path) and old_path != current_path:
            if os.path.exists(old_path):
                try:
                    os.remove(old_path)
                    logger.info(f"Cleaned up stale scaffold file: {old_path}")
                except OSError as e:
                    logger.warning(f"Failed to cleanup scaffold file {old_path}: {e}")


def resolve_test_file_conflict(
    scaffold_path: str, 
    unit_path: str,
    state: TDDState
) -> str:
    """Determine which test file is authoritative when both exist.
    
    Handles edge case where state.test_file_path points to non-existent
    file but valid unit test exists in tests/unit/.
    
    Args:
        scaffold_path: Path to scaffold test file (tests/test_issue_N.py)
        unit_path: Path to unit test file (tests/unit/test_*.py)
        state: Current TDD state
        
    Returns:
        The authoritative test file path (prefers unit tests)
    """
    # Edge case: state path doesn't exist but unit test does
    state_path = state.get("test_file_path")
    if state_path and not os.path.exists(state_path) and os.path.exists(unit_path):
        logger.info(f"State path {state_path} doesn't exist, using unit test: {unit_path}")
        return unit_path
    
    # Prefer unit tests over scaffold
    if os.path.exists(unit_path):
        return unit_path
    
    # Fall back to scaffold if it exists
    if os.path.exists(scaffold_path):
        return scaffold_path
    
    # If neither exists, raise error
    raise ValueError(f"Neither scaffold ({scaffold_path}) nor unit test ({unit_path}) exists")


def log_test_file_path(phase: str, path: str) -> None:
    """Log the test file path being used by a phase.
    
    Ensures R6 compliance: All phases log which test file path they are using.
    
    Args:
        phase: TDD phase name ("scaffold", "red", "green", "refactor", "verification")
        path: Test file path being used
    """
    logger.info(f"[TDD] {phase.capitalize()} phase using test file: {path}")


def _is_scaffold_file(path: str) -> bool:
    """Check if a path matches the scaffold file pattern.
    
    Scaffold pattern: tests/test_issue_N.py
    
    Args:
        path: Path to check
        
    Returns:
        True if path matches scaffold pattern
    """
    p = Path(path)
    # Must be in tests/ directory and match test_issue_*.py pattern
    return (
        p.parent.name == "tests" and 
        p.name.startswith("test_issue_") and 
        p.suffix == ".py"
    )