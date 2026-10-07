"""An unsettled design artifact on the base is redrawn, not a new arc (#3762).

boostgauge #421 (2026-10-07): an LLD on `hardening-run-20` that no longer
verified (run 50's accidental landings; later, #2's clarifying body edits) made
the roll establish a new attempt branch, which would have abandoned the seed
carrying #7, #41, #4 and #332. It was cleared by hand three times
(boostgauge #479, #486, #489).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import speedrun_roll as sr

LLD = "committed artifact: docs/lld/active/LLD-002.md"
OTHER = "committed artifact: src/boostgauge/telltale_group.py"


@pytest.fixture
def base_check(monkeypatch, tmp_path):
    """ensure_base with the gate's findings and their settledness chosen by the test."""
    calls = {"new_attempt": 0}

    def run(findings, unsettled_reason="issue_body: hashed abc then, def now"):
        monkeypatch.setattr(sr, "resolve_attempt_branch", lambda r: "arc")
        monkeypatch.setattr(sr, "base_is_structurally_sound", lambda r, b: [])
        monkeypatch.setattr(sr.gate, "check_repo", lambda r, issues, b: list(findings))
        monkeypatch.setattr(
            sr, "partition_by_settledness",
            lambda r, i, committed: ([], [(c, [unsettled_reason]) for c in committed]),
        )
        monkeypatch.setattr(sr, "record_heal", lambda *a, **k: None)

        def new_attempt(repo, log):
            calls["new_attempt"] += 1
            return "arc-2"

        monkeypatch.setattr(sr, "establish_new_attempt", new_attempt)
        log = sr.EventLog(tmp_path / "events.log")
        base = sr.ensure_base(tmp_path, 2, log)
        return base, (tmp_path / "events.log").read_text(encoding="utf-8"), calls

    return run


def test_an_unsettled_lld_keeps_the_base(base_check):
    base, events, calls = base_check([LLD])

    assert base == "arc"
    assert calls["new_attempt"] == 0
    assert "BASE keeping 'arc': unsettled design artifact(s) will be redrawn" in events
    assert "establishing a fresh attempt" not in events


def test_an_unsettled_non_design_artifact_still_replaces_the_base(base_check):
    base, events, calls = base_check([OTHER])

    assert base == "arc-2"
    assert calls["new_attempt"] == 1
    assert "establishing a fresh attempt" in events
