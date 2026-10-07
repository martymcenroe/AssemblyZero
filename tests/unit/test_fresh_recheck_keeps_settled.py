"""The post-reset recheck honours settledness, as the first check does (#3758).

boostgauge #2 run-issue2-033833 (2026-10-07): the first base check preserved the
settled LLD on `hardening-run-20`, `--fresh` reset the issue preserving it on
purpose, and the recheck then counted the same LLD as a finding the reset
could not clear, and aborted.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import speedrun_roll as sr

LLD = "committed artifact: docs/lld/active/LLD-002.md"
SPEC = "untracked artifact: docs/lld/drafts/spec-0002-implementation-readiness.md"


@pytest.fixture
def roll(monkeypatch, tmp_path):
    """ensure_base(fresh=True) with every collaborator stubbed; the gate's two
    answers and the recheck's settledness are the test's to choose."""
    calls: dict = {"refused": None}

    def run(*, recheck_settled: bool):
        answers = iter([[LLD, SPEC], [LLD]])
        partitions = iter([True, recheck_settled])

        def partition(repo, issue, committed):
            if next(partitions):
                return list(committed), []
            return [], [(c, ["settlement does not verify"]) for c in committed]

        def refuse(repo, base, issue, debris, log):
            calls["refused"] = list(debris)

        monkeypatch.setattr(sr, "resolve_attempt_branch", lambda r: "arc")
        monkeypatch.setattr(sr, "base_is_structurally_sound", lambda r, b: [])
        monkeypatch.setattr(sr.gate, "check_repo", lambda r, issues, b: next(answers))
        monkeypatch.setattr(sr, "partition_by_settledness", partition)
        monkeypatch.setattr(sr, "record_heal", lambda *a, **k: None)
        monkeypatch.setattr(sr, "find_checkpoint", lambda r, i: None)
        monkeypatch.setattr(sr, "settled_artifact_names", lambda r, i, log: {"LLD-002.md"})
        monkeypatch.setattr(sr.reset, "_gh_repo", lambda r: "o/r")
        monkeypatch.setattr(sr.reset, "reset_one_issue", lambda *a, **k: None)
        monkeypatch.setattr(sr, "replace_or_refuse", refuse)

        log = sr.EventLog(tmp_path / "events.log")
        base = sr.ensure_base(tmp_path, 2, log, True)
        return base, (tmp_path / "events.log").read_text(encoding="utf-8"), calls

    return run


def test_a_settled_artifact_the_reset_kept_is_not_a_finding(roll):
    base, events, calls = roll(recheck_settled=True)

    assert base == "arc"
    assert calls["refused"] is None
    assert f"BASE settled, preserved after reset: {LLD}" in events
    assert "still dirty after reset" not in events


def test_an_unsettled_artifact_after_the_reset_still_counts(roll):
    base, events, calls = roll(recheck_settled=False)

    assert base is None
    assert calls["refused"] == [LLD]
    assert "still dirty after reset" in events
