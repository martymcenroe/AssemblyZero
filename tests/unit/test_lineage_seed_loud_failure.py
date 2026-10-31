"""lineage_seed under standard 0034 (#3585).

Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md. A prior run's lineage file
that cannot be read raises ``LineageReadError`` naming it; it used to read as
"", so the run was skipped as non-resumable and its paid work was replaced by
an older seed or a fresh draw, and a verdict dropped from the history blinded
the stagnation check.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from assemblyzero.workflows.implementation_spec import lineage_seed as ls


def _run(root: Path, name: str, *, drafts=("draft one",), verdicts=("Verdict: REVISE\n\nfix `x`",)):
    run = root / name
    run.mkdir(parents=True)
    number = 1
    for text in drafts:
        (run / f"{number:03d}-spec-draft.md").write_text(text, encoding="utf-8")
        number += 1
    for text in verdicts:
        (run / f"{number:03d}-readiness-verdict.md").write_text(text, encoding="utf-8")
        number += 1
    return run


def _unreadable(monkeypatch, target: Path) -> None:
    real = Path.read_text

    def read_text(self, *args, **kwargs):
        if self == target:
            raise PermissionError(13, "Permission denied", str(self))
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)


def test_102_an_unreadable_draft_raises(tmp_path, monkeypatch):
    root = tmp_path / "1-implspec"
    _run(root, "2026-10-29T10-00-00Z", drafts=("old draft",))
    newer = _run(root, "2026-10-30T10-00-00Z", drafts=("new draft",))
    draft = next(newer.glob(ls.DRAFT_GLOB))
    _unreadable(monkeypatch, draft)

    with pytest.raises(ls.LineageReadError) as caught:
        ls.seed_from_lineage(root)
    assert str(draft) in str(caught.value)
    assert "PermissionError" in str(caught.value)


def test_102_an_unreadable_newest_verdict_raises(tmp_path, monkeypatch):
    root = tmp_path / "1-implspec"
    run = _run(root, "2026-10-30T10-00-00Z")
    verdict = next(run.glob(ls.VERDICT_GLOB))
    _unreadable(monkeypatch, verdict)

    with pytest.raises(ls.LineageReadError, match="PermissionError"):
        ls.seed_from_lineage(root)


def test_140_an_unreadable_earlier_verdict_raises(tmp_path, monkeypatch):
    root = tmp_path / "1-implspec"
    run = _run(root, "2026-10-30T10-00-00Z", verdicts=("Verdict: REVISE\n\none", "Verdict: REVISE\n\ntwo"))
    first = min(run.glob(ls.VERDICT_GLOB))
    _unreadable(monkeypatch, first)

    with pytest.raises(ls.LineageReadError):
        ls.seed_from_lineage(root)


def test_140_an_empty_verdict_raises_rather_than_leaving_the_history(tmp_path):
    root = tmp_path / "1-implspec"
    _run(root, "2026-10-30T10-00-00Z", verdicts=("   \n", "Verdict: REVISE\n\ntwo"))

    with pytest.raises(ls.LineageReadError, match="empty"):
        ls.seed_from_lineage(root)


def test_a_readable_run_seeds_with_every_verdict(tmp_path):
    root = tmp_path / "1-implspec"
    _run(root, "2026-10-30T10-00-00Z", verdicts=("Verdict: REVISE\n\none", "Verdict: REVISE\n\ntwo"))
    seed = ls.seed_from_lineage(root)
    assert seed is not None
    assert seed.rounds_completed == 2


def test_no_prior_run_is_no_seed(tmp_path):
    """Kept: nothing to resume onto is an answer, and the run draws fresh."""
    assert ls.seed_from_lineage(tmp_path / "1-implspec") is None


def test_an_empty_draft_is_still_no_seed(tmp_path):
    """Kept: an empty draft is a failed draw, not paid work to resume."""
    root = tmp_path / "1-implspec"
    _run(root, "2026-10-30T10-00-00Z", drafts=("  \n",))
    assert ls.seed_from_lineage(root) is None
