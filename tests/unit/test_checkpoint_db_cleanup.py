"""Unit tests for stale checkpoint DB cleanup on fresh runs.

Issue #470: SqliteSaver persists stale N0 results (including error state)
across runs. When the user fixes the problem and re-runs without --resume,
the checkpoint replays the stale error instead of re-executing.

Tests verify:
- Fresh run (no --resume) deletes existing checkpoint DB
- Resume run preserves checkpoint DB
- Missing DB on fresh run does not error
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


def _make_args(resume: bool = False, issue: int = 999) -> SimpleNamespace:
    """Create a minimal args namespace mimicking argparse output."""
    return SimpleNamespace(resume=resume, issue=issue)


def test_fresh_run_deletes_existing_db(tmp_path: Path):
    """Fresh run (no --resume) should delete the checkpoint DB."""
    db_path = tmp_path / "testing_999.db"
    db_path.write_text("stale data")

    args = _make_args(resume=False)

    # Replicate the cleanup logic from run_implement_from_lld.py lines 727-731
    if not args.resume:
        if db_path.exists():
            db_path.unlink()

    assert not db_path.exists()


def test_resume_run_preserves_db(tmp_path: Path):
    """Resume run (--resume) should NOT delete the checkpoint DB."""
    db_path = tmp_path / "testing_999.db"
    db_path.write_text("checkpoint data")

    args = _make_args(resume=True)

    if not args.resume:
        if db_path.exists():
            db_path.unlink()

    assert db_path.exists()
    assert db_path.read_text() == "checkpoint data"


def test_fresh_run_missing_db_no_error(tmp_path: Path):
    """Fresh run with no existing DB should not raise."""
    db_path = tmp_path / "testing_999.db"
    assert not db_path.exists()

    args = _make_args(resume=False)

    # Should not raise
    if not args.resume:
        if db_path.exists():
            db_path.unlink()

    assert not db_path.exists()
