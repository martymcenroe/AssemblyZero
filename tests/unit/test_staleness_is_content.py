"""Staleness is decided by content, and by ONE fingerprint (#2615).

`draft_is_stale` (#2206) used to compare the issue's `updatedAt` against the
draft time. **GitHub bumps `updatedAt` when a comment is posted**, so the probe
fired on events that changed nothing about the derivation -- and the campaign's
standing method is to post a sharpened diagnosis to the issue before fixing.
Following the method invalidated every persisted draft it touched.

Two things are pinned here, and the second matters as much as the first:

1. **Content decides.** A comment does not unsettle; a one-character body edit
   does. Each with the control that makes it mean something.
2. **One fingerprint.** `draft_is_stale` and `should_skip_stage` ask the same
   question, so they must ask it of the same function over the same inputs.
   Two parsers of one question is the #1698 failure class, and it is precisely
   how these two would have drifted -- the settlement path hashing content
   while the resume path read clocks was that drift, already realised.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import speedrun_roll as sr  # noqa: E402

from assemblyzero.core import settlement as s  # noqa: E402
from assemblyzero.workflows.orchestrator import stages  # noqa: E402
from assemblyzero.workflows.orchestrator.state import OrchestrationState  # noqa: E402
from assemblyzero.workflows.requirements.audit import save_settlement  # noqa: E402

ISSUE = 331

TABLE = "| ID | Binding value |\n|----|---------------|\n| S1 | 250 ms |\n"
BODY = f"# Dial\n\n## Pass criteria\n\n{TABLE}"


class _Log:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def write(self, line: str) -> None:
        self.lines.append(line)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "docs" / "lld" / "active").mkdir(parents=True)
    (tmp_path / "docs" / "design").mkdir(parents=True)
    (tmp_path / "docs" / "design" / "dial.md").write_text("law\n", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("rules\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def lld(repo: Path) -> Path:
    path = repo / "docs" / "lld" / "active" / f"LLD-{ISSUE}.md"
    path.write_text(f"## 1. Context\n\n## 3. Requirements\n\n{TABLE}", encoding="utf-8")
    return path


@pytest.fixture
def settled(repo: Path, lld: Path):
    def _settle(body: str = BODY) -> dict:
        record = s.build_settlement(
            "lld", lld, s.collect_inputs(repo, issue_body=body), verdict="APPROVED"
        )
        save_settlement(ISSUE, "lld", record, repo)
        return record

    return _settle


@pytest.fixture
def resume_sees(monkeypatch):
    """What `gh` returns to the RESUME path."""

    def _set(body: str | None):
        def _fetch(_repo, _issue):
            if body is None:
                raise RuntimeError("gh unavailable")
            return ("title", body)

        monkeypatch.setattr(sr, "fetch_issue", _fetch)

    return _set


@pytest.fixture
def stage_sees(monkeypatch):
    """What `gh` returns to the STAGE-ENTRY path."""

    def _set(body: str | None):
        monkeypatch.setattr(stages, "fetch_issue_body", lambda _r, _i: body)

    return _set


# ---------------------------------------------------------------------------
# Content decides
# ---------------------------------------------------------------------------


class TestContentDecides:
    def test_a_comment_does_not_unsettle(self, repo, settled, resume_sees) -> None:
        """The acceptance. A comment leaves the body byte-identical -- which
        is exactly the state this fixture reproduces -- while bumping
        `updatedAt`, the field the old check read."""
        settled()
        resume_sees(BODY)

        assert sr.draft_is_stale(repo, ISSUE, _Log()) is False

    def test_a_one_character_body_edit_unsettles(
        self, repo, settled, resume_sees
    ) -> None:
        """The control. Without it, a check that never unsettles would pass
        the test above."""
        settled()
        resume_sees(BODY.replace("250 ms", "251 ms"))

        assert sr.draft_is_stale(repo, ISSUE, _Log()) is True

    def test_a_binding_doc_edit_unsettles(self, repo, settled, resume_sees) -> None:
        settled()
        resume_sees(BODY)
        (repo / "docs" / "design" / "dial.md").write_text("amended\n", encoding="utf-8")

        assert sr.draft_is_stale(repo, ISSUE, _Log()) is True

    def test_an_unrelated_file_does_not_unsettle(
        self, repo, settled, resume_sees
    ) -> None:
        """Only the binding paths are law."""
        settled()
        resume_sees(BODY)
        (repo / "README.md").write_text("changed\n", encoding="utf-8")

        assert sr.draft_is_stale(repo, ISSUE, _Log()) is False

    def test_whitespace_only_line_endings_do_not_unsettle(
        self, repo, settled, resume_sees
    ) -> None:
        """LF from `gh`, CRLF from a Windows checkout: the same document."""
        settled()
        resume_sees(BODY.replace("\n", "\r\n"))

        assert sr.draft_is_stale(repo, ISSUE, _Log()) is False


class TestUnknowableIsStale:
    def test_no_settlement_record_is_stale(self, repo, resume_sees) -> None:
        resume_sees(BODY)
        assert sr.draft_is_stale(repo, ISSUE, _Log()) is True

    def test_an_unreadable_issue_is_stale(self, repo, settled, resume_sees) -> None:
        settled()
        resume_sees(None)
        assert sr.draft_is_stale(repo, ISSUE, _Log()) is True

    def test_the_decline_says_why(self, repo, settled, resume_sees) -> None:
        settled()
        resume_sees(BODY.replace("250 ms", "251 ms"))
        log = _Log()

        sr.draft_is_stale(repo, ISSUE, log)

        assert "a binding input changed" in log.text
        assert "issue_body" in log.text

    def test_the_missing_record_decline_says_why(self, repo, resume_sees) -> None:
        resume_sees(BODY)
        log = _Log()

        sr.draft_is_stale(repo, ISSUE, log)

        assert "no settlement record" in log.text


# ---------------------------------------------------------------------------
# One fingerprint -- the #1698 guard
# ---------------------------------------------------------------------------


class TestOneFingerprint:
    """The two paths must not be able to disagree.

    They already did: settlement hashed content while the resume path read
    `updatedAt`, so the same question got two answers on the same state. These
    tests fail if a future edit reintroduces a second notion of "did the inputs
    change".
    """

    def test_both_paths_agree_a_comment_changes_nothing(
        self, repo, lld, settled, resume_sees, stage_sees
    ) -> None:
        settled()
        resume_sees(BODY)
        stage_sees(BODY)

        resume_stale = sr.draft_is_stale(repo, ISSUE, _Log())
        skip, _ = stages.should_skip_stage(
            OrchestrationState(
                issue_number=ISSUE, target_repo=str(repo), config={}
            ),
            "lld",
            {"triage": None, "lld": str(lld), "spec": None,
             "impl": None, "pr": None},
        )

        assert resume_stale is False
        assert skip is True, "settled for one path and not the other is drift"

    def test_both_paths_agree_a_body_edit_changes_everything(
        self, repo, lld, settled, resume_sees, stage_sees
    ) -> None:
        """The control, on the same pair: agreement on 'no' is worth nothing
        without agreement on 'yes'."""
        settled()
        edited = BODY.replace("250 ms", "251 ms")
        resume_sees(edited)
        stage_sees(edited)

        resume_stale = sr.draft_is_stale(repo, ISSUE, _Log())
        skip, _ = stages.should_skip_stage(
            OrchestrationState(
                issue_number=ISSUE, target_repo=str(repo), config={}
            ),
            "lld",
            {"triage": None, "lld": str(lld), "spec": None,
             "impl": None, "pr": None},
        )

        assert resume_stale is True
        assert skip is False

    def test_the_resume_path_builds_inputs_with_the_shared_collector(
        self, repo, settled, resume_sees, monkeypatch
    ) -> None:
        """Structural: the resume path must go through `collect_inputs`, not
        assemble its own list. A second assembler is how the fingerprints
        drift even when both sides hash."""
        settled()
        resume_sees(BODY)
        seen: list[str] = []
        real = s.collect_inputs

        def _spy(*args, **kwargs):
            seen.append("called")
            return real(*args, **kwargs)

        monkeypatch.setattr(s, "collect_inputs", _spy)

        sr.draft_is_stale(repo, ISSUE, _Log())

        assert seen, "draft_is_stale did not use settlement.collect_inputs"

    def test_the_resume_path_verdicts_through_settlement_verify(
        self, repo, settled, resume_sees, monkeypatch
    ) -> None:
        settled()
        resume_sees(BODY)
        seen: list[str] = []
        real = s.verify

        def _spy(*args, **kwargs):
            seen.append("called")
            return real(*args, **kwargs)

        monkeypatch.setattr(s, "verify", _spy)

        sr.draft_is_stale(repo, ISSUE, _Log())

        assert seen, "draft_is_stale did not use settlement.verify"

    def test_one_definition_of_the_binding_paths(self) -> None:
        assert sr.BINDING_DOC_PATHS is s.BINDING_DOC_PATHS


class TestTheTimestampProbeIsGone:
    """Dead mechanisms get removed, not left beside the live one."""

    def test_the_source_no_longer_reads_updated_at(self) -> None:
        """The CODE forms, not the word.

        The docstrings deliberately explain what `updatedAt` did and why it
        was wrong, so a bare substring search would forbid recording the
        lesson. What must not come back is the argv that asks GitHub for the
        field.
        """
        source = (TOOLS / "speedrun_roll.py").read_text(encoding="utf-8")
        for code_form in ('"updatedAt"', "'updatedAt'", ".updatedAt"):
            assert code_form not in source, (
                f"{code_form} is the #2615 defect's code form; reading that "
                f"field again reintroduces unsettling on comments"
            )

    def test_the_iso_parser_went_with_it(self) -> None:
        """`_iso_to_epoch` existed only for the timestamp comparisons."""
        source = (TOOLS / "speedrun_roll.py").read_text(encoding="utf-8")
        assert "_iso_to_epoch" not in source
