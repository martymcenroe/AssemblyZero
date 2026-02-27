"""Unit tests for assemblyzero/core/state_persistence.py.

Issue #486: Halt-and-Plan pattern — self-babysitting workflows.

Tests cover:
- save_state_snapshot: saves workflow state to JSON
- load_state_snapshot: loads most recent state snapshot
- Round-trip: save then load preserves data
- Edge cases: missing file, corrupt JSON
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.core.state_persistence import (
    save_state_snapshot,
    load_state_snapshot,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def state_dir(tmp_path: Path) -> Path:
    """Temporary state directory for isolation."""
    return tmp_path / "workflow_state"


@pytest.fixture
def sample_state() -> dict:
    """A representative workflow state dict."""
    return {
        "issue_number": 102,
        "spec_draft": "# Implementation Spec\n\n...",
        "review_iteration": 2,
        "error_message": "Gemini 503",
        "cost_budget_usd": 10.0,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: save_state_snapshot
# ═══════════════════════════════════════════════════════════════════════════════


class TestSaveStateSnapshot:
    """Tests for save_state_snapshot()."""

    def test_save_creates_file(self, state_dir: Path, sample_state: dict) -> None:
        """Saving state creates a JSON file on disk."""
        with patch("assemblyzero.core.state_persistence.STATE_DIR", state_dir):
            path = save_state_snapshot("implementation_spec", 102, sample_state)
        assert path.exists()
        assert path.suffix == ".json"

    def test_save_creates_directory(self, state_dir: Path) -> None:
        """Saving state creates the directory if it doesn't exist."""
        assert not state_dir.exists()
        with patch("assemblyzero.core.state_persistence.STATE_DIR", state_dir):
            save_state_snapshot("requirements", 1, {"key": "value"})
        assert state_dir.exists()

    def test_save_valid_json(self, state_dir: Path, sample_state: dict) -> None:
        """Saved file contains valid JSON."""
        with patch("assemblyzero.core.state_persistence.STATE_DIR", state_dir):
            path = save_state_snapshot("implementation_spec", 102, sample_state)
        content = path.read_text(encoding="utf-8")
        data = json.loads(content)
        assert isinstance(data, dict)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: load_state_snapshot
# ═══════════════════════════════════════════════════════════════════════════════


class TestLoadStateSnapshot:
    """Tests for load_state_snapshot()."""

    def test_load_missing_returns_none(self, state_dir: Path) -> None:
        """Loading from non-existent path returns None."""
        with patch("assemblyzero.core.state_persistence.STATE_DIR", state_dir):
            result = load_state_snapshot("requirements", 999)
        assert result is None

    def test_load_corrupt_json_returns_none(self, state_dir: Path) -> None:
        """Loading corrupt JSON returns None (graceful degradation)."""
        state_dir.mkdir(parents=True, exist_ok=True)
        corrupt_path = state_dir / "implementation_spec-42.json"
        corrupt_path.write_text("NOT VALID JSON {{{", encoding="utf-8")
        with patch("assemblyzero.core.state_persistence.STATE_DIR", state_dir):
            result = load_state_snapshot("implementation_spec", 42)
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Round-trip
# ═══════════════════════════════════════════════════════════════════════════════


class TestRoundTrip:
    """Tests for save/load round-trip correctness."""

    def test_save_load_roundtrip(self, state_dir: Path, sample_state: dict) -> None:
        """Saving then loading preserves all state fields."""
        with patch("assemblyzero.core.state_persistence.STATE_DIR", state_dir):
            save_state_snapshot("implementation_spec", 102, sample_state)
            loaded = load_state_snapshot("implementation_spec", 102)

        assert loaded is not None
        assert loaded["issue_number"] == 102
        assert loaded["spec_draft"] == "# Implementation Spec\n\n..."
        assert loaded["review_iteration"] == 2
        assert loaded["error_message"] == "Gemini 503"

    def test_overwrite_on_rerun(self, state_dir: Path) -> None:
        """Saving twice for the same workflow/issue overwrites the first."""
        with patch("assemblyzero.core.state_persistence.STATE_DIR", state_dir):
            save_state_snapshot("requirements", 50, {"version": 1})
            save_state_snapshot("requirements", 50, {"version": 2})
            loaded = load_state_snapshot("requirements", 50)

        assert loaded is not None
        assert loaded["version"] == 2
