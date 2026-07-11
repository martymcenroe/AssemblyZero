"""Unit tests for tools/pat_smoke_test.py's pure verdict (#1745)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from pat_smoke_test import evaluate  # noqa: E402


def test_happy_path_all_pass():
    ok, lines = evaluate(200, "martymcenroe", "repo, workflow",
                         "2026-10-09 05:00:00 UTC")
    assert ok
    assert sum(1 for line in lines if line.startswith("PASS")) == 4


def test_bad_status_fails_fast_with_encrypt_hint():
    ok, lines = evaluate(401, "", "", "")
    assert not ok
    assert len(lines) == 1
    assert "re-check the encrypt step" in lines[0]


def test_wrong_login_fails():
    ok, lines = evaluate(200, "somebody-else", "repo", "")
    assert not ok
    assert any("wrong token" in line for line in lines)


def test_missing_repo_scope_fails():
    ok, lines = evaluate(200, "martymcenroe", "gist, read:org", "")
    assert not ok
    assert any("repo (full)" in line for line in lines)


def test_scope_match_is_exact_token_not_substring():
    # "repo:status" alone must NOT satisfy the full-repo requirement.
    ok, lines = evaluate(200, "martymcenroe", "repo:status", "")
    assert not ok


def test_non_expiring_token_notes_not_fails():
    ok, lines = evaluate(200, "martymcenroe", "repo", "")
    assert ok
    assert any(line.startswith("NOTE") for line in lines)
