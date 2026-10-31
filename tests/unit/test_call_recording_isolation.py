"""No test inherits an armed call recorder (#4163).

The recorder's context is a module global. A test that left it armed made
every later model call in the process write to ``audit/calls.jsonl`` under
pytest's working directory, the checkout, where the file was even tracked.
``tests/conftest.py``'s ``call_recording_disarmed`` resets it around every
test. These two run in file order: the first arms it, the second checks the
reset reached it.
"""
from __future__ import annotations

from pathlib import Path

from assemblyzero.core import call_recording

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_1_a_test_may_arm_the_recorder(tmp_path):
    call_recording.set_context("lld", "N1b_validate_test_plan", str(tmp_path))
    assert call_recording.recording_is_armed()


def test_2_the_next_test_finds_it_disarmed():
    assert not call_recording.recording_is_armed()
    assert call_recording.current_context().audit_dir == ""


def test_the_committed_artifact_is_gone_and_ignored():
    assert not (REPO_ROOT / "audit" / "calls.jsonl").exists()
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "/audit/" in gitignore.splitlines()
