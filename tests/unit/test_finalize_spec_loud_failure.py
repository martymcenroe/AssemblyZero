"""N6 finalize_spec under standard 0034 (#3585).

Every ledger row for this module was settled by #3887 and #3891 (PR #3901):
route_after_finalize sends any error to HALT, and the repo_root, audit_dir and
hand-off guards halt. tests/unit/test_spec_finalize_halts.py pins lines 153,
166, 179, 257 and 271. This file pins the rows it does not reach: the short
draft (137), the temp-file cleanup (219, compliant), a failed write (224) and
a spec absent after the write (234). Each passed before #3585 touched
anything, because nothing here changed.
"""
from __future__ import annotations

from pathlib import Path

from assemblyzero.workflows.implementation_spec.graph import route_after_finalize
from assemblyzero.workflows.implementation_spec.nodes.finalize_spec import (
    SPEC_OUTPUT_DIR,
    finalize_spec,
)

SPEC = "# Implementation Spec\n\n" + ("Content line\n" * 50)


def _state(repo: Path, **overrides) -> dict:
    audit_dir = repo / "docs" / "lineage" / "active" / "7-implspec" / "20261030T000000Z"
    audit_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "issue_number": 7,
        "spec_draft": SPEC,
        "review_verdict": "APPROVED",
        "review_feedback": "",
        "review_iteration": 1,
        "repo_root": str(repo),
        "audit_dir": str(audit_dir),
    }
    state.update(overrides)
    return state


def _halts(result: dict, *fragments: str) -> None:
    assert result["spec_path"] == ""
    for fragment in fragments:
        assert fragment in result["error_message"]
    assert route_after_finalize(result) == "HALT"


def test_137_a_draft_under_the_minimum_halts(tmp_path):
    _halts(finalize_spec(_state(tmp_path, spec_draft="# too short")), "too short")


def test_219_a_failed_temp_write_is_cleaned_up_and_halts(tmp_path, monkeypatch):
    """Compliant, pinned: the temp file is removed and the error re-raised
    into the write handler, which halts."""
    real_write = Path.write_text

    def refuse_temp(self, *args, **kwargs):
        if self.name.startswith(".spec-"):
            raise OSError("disk full")
        return real_write(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", refuse_temp)
    result = finalize_spec(_state(tmp_path))

    _halts(result, "Failed to write spec file", "disk full")
    assert list((tmp_path / SPEC_OUTPUT_DIR).glob(".spec-*")) == []


def test_224_an_output_directory_that_cannot_be_made_halts(tmp_path):
    drafts = tmp_path / SPEC_OUTPUT_DIR
    drafts.parent.mkdir(parents=True)
    drafts.write_text("a file where the drafts directory belongs", encoding="utf-8")

    _halts(finalize_spec(_state(tmp_path)), "Failed to write spec file")


def test_234_a_spec_absent_after_the_write_halts(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "replace", lambda self, target: target)

    _halts(finalize_spec(_state(tmp_path)), "Spec file not created")
