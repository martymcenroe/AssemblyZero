"""The launcher consults settledness, not branch contents (#2609).

The 09:36 line, inverted:

    BASE 'hardening-run-18' already contains #331's work (1 artifact(s))
    -- establishing a fresh attempt

That is settling work being read as contamination. A committed LLD on the arc
branch is where an approved artifact is SUPPOSED to live, so landing it there
was what triggered redrawing it -- and the redraw shed the settled #361
sampling window twice.

The committed-artifact scan reads `docs/lld` only, so every finding it can
produce is an LLD or a spec. #1959's founding case -- a base whose
implementations were already merged and green -- is invisible to this scan and
stays that way; the control below pins it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import speedrun_reset as reset  # noqa: E402
import speedrun_roll as sr  # noqa: E402

from assemblyzero.core import settlement as s  # noqa: E402
from assemblyzero.workflows.requirements.audit import save_settlement  # noqa: E402

ISSUE = 331
BODY = "# Dial\n\n| ID | value |\n|----|-------|\n| S1 | 250 ms |\n"
FINDING = "committed artifact: docs/lld/active/LLD-331.md"


class _Log:
    """The launcher's EventLog surface, captured."""

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
    (tmp_path / "docs" / "lld" / "drafts").mkdir(parents=True)
    (tmp_path / "docs" / "design").mkdir(parents=True)
    (tmp_path / "docs" / "design" / "dial.md").write_text("law\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def lld(repo: Path) -> Path:
    path = repo / "docs" / "lld" / "active" / f"LLD-{ISSUE}.md"
    path.write_text("## 1. Context\n\n| S1 | 250 ms |\n", encoding="utf-8")
    return path


@pytest.fixture
def body_is(monkeypatch):
    def _set(text: str | None):
        monkeypatch.setattr(
            sr, "fetch_issue",
            lambda _repo, _issue: ("title", text) if text is not None
            else (_ for _ in ()).throw(RuntimeError("gh down")),
        )

    return _set


def _settle(repo: Path, lld: Path, body: str = BODY, stage: str = "lld") -> None:
    save_settlement(
        ISSUE, stage,
        s.build_settlement(
            stage, lld, s.collect_inputs(repo, issue_body=body), verdict="APPROVED"
        ),
        repo,
    )


class TestSettledWorkIsNotContamination:
    def test_a_settled_committed_lld_is_preserved(
        self, repo, lld, body_is
    ) -> None:
        _settle(repo, lld)
        body_is(BODY)

        settled, unsettled = sr.partition_by_settledness(repo, ISSUE, [FINDING])

        assert settled == [FINDING]
        assert unsettled == []

    def test_an_unsettled_committed_lld_is_still_contamination(
        self, repo, lld, body_is
    ) -> None:
        """The control. Without it a function that returns everything as
        settled would pass the test above."""
        _settle(repo, lld)
        body_is(BODY.replace("250 ms", "251 ms"))

        settled, unsettled = sr.partition_by_settledness(repo, ISSUE, [FINDING])

        assert settled == []
        assert len(unsettled) == 1
        assert unsettled[0][0] == FINDING
        assert any("when the artifact settled" in r for r in unsettled[0][1])

    def test_no_settlement_record_is_contamination(
        self, repo, lld, body_is
    ) -> None:
        body_is(BODY)
        settled, unsettled = sr.partition_by_settledness(repo, ISSUE, [FINDING])
        assert settled == []
        assert unsettled[0][1] == ["no settlement record"]

    def test_an_unrecognised_artifact_is_never_reprieved(
        self, repo, lld, body_is
    ) -> None:
        _settle(repo, lld)
        body_is(BODY)
        odd = "committed artifact: docs/lld/active/NOTES.md"

        settled, unsettled = sr.partition_by_settledness(repo, ISSUE, [odd])

        assert settled == []
        assert "not a recognised settleable artifact" in unsettled[0][1]

    def test_another_issues_artifact_is_never_reprieved(
        self, repo, lld, body_is
    ) -> None:
        """#1959's shape: a base carrying a DIFFERENT issue's work."""
        _settle(repo, lld)
        body_is(BODY)
        other = "committed artifact: docs/lld/active/LLD-007.md"

        settled, unsettled = sr.partition_by_settledness(repo, ISSUE, [other])

        assert settled == []

    def test_a_failed_issue_read_is_contamination(
        self, repo, lld, body_is
    ) -> None:
        """`gh` down must not settle anything."""
        _settle(repo, lld)
        body_is(None)

        settled, _unsettled = sr.partition_by_settledness(repo, ISSUE, [FINDING])

        assert settled == []

    def test_mixed_findings_split(self, repo, lld, body_is) -> None:
        _settle(repo, lld)
        body_is(BODY)
        odd = "committed artifact: docs/lld/drafts/spec-0331-x.md"

        settled, unsettled = sr.partition_by_settledness(
            repo, ISSUE, [FINDING, odd]
        )

        assert settled == [FINDING]
        assert len(unsettled) == 1


class TestFreshPreservesSettledArtifacts:
    def test_a_settled_artifact_is_named_for_preservation(
        self, repo, lld, body_is
    ) -> None:
        _settle(repo, lld)
        body_is(BODY)
        log = _Log()

        names = sr.settled_artifact_names(repo, ISSUE, log)

        assert names == {f"LLD-{ISSUE}.md"}
        assert "FRESH preserving settled lld" in log.text

    def test_an_unsettled_artifact_is_archived_and_said_so(
        self, repo, lld, body_is
    ) -> None:
        _settle(repo, lld)
        body_is(BODY.replace("250 ms", "251 ms"))
        log = _Log()

        names = sr.settled_artifact_names(repo, ISSUE, log)

        assert names == set()
        assert "FRESH archiving unsettled lld" in log.text
        assert "when the artifact settled" in log.text

    def test_a_hand_edited_artifact_is_archived(self, repo, lld, body_is) -> None:
        _settle(repo, lld)
        lld.write_text("## 1. Context\n\nedited\n", encoding="utf-8")
        body_is(BODY)
        log = _Log()

        assert sr.settled_artifact_names(repo, ISSUE, log) == set()
        assert "is not the file that settled" in log.text

    def test_nothing_settled_names_nothing(self, repo, lld, body_is) -> None:
        body_is(BODY)
        assert sr.settled_artifact_names(repo, ISSUE, _Log()) == set()


class TestResetHonoursPreservation:
    """`relocate_lld_artifacts` is `--fresh`'s archiving step."""

    def test_a_preserved_artifact_survives_the_reset(
        self, repo, lld, capsys
    ) -> None:
        moved = reset.relocate_lld_artifacts(repo, ISSUE, {lld.name})

        assert lld.is_file()
        assert moved == 0
        assert "Preserved (settled)" in capsys.readouterr().out

    def test_an_unpreserved_artifact_is_relocated(self, repo, lld) -> None:
        """The control: preservation must be the exception, not the default."""
        reset.relocate_lld_artifacts(repo, ISSUE, set())

        assert not lld.is_file()
        assert (
            repo / "data" / "speedrun" / "reset-artifacts" / f"issue-{ISSUE}"
            / lld.name
        ).is_file()

    def test_the_default_is_unchanged(self, repo, lld) -> None:
        """No `preserve` argument means exactly the pre-#2609 behaviour."""
        reset.relocate_lld_artifacts(repo, ISSUE)
        assert not lld.is_file()

    def test_preserving_one_does_not_preserve_another(self, repo, lld) -> None:
        spec = repo / "docs" / "lld" / "drafts" / f"spec-{ISSUE:04d}-x.md"
        spec.write_text("spec\n", encoding="utf-8")

        reset.relocate_lld_artifacts(repo, ISSUE, {lld.name})

        assert lld.is_file()
        assert not spec.is_file()


class TestBindingDocPathsAreOneDefinition:
    def test_the_launcher_imports_the_canonical_tuple(self) -> None:
        """Two literals would let `draft_is_stale` and settlement disagree
        about which documents bind, at which point one of them is wrong."""
        assert sr.BINDING_DOC_PATHS is s.BINDING_DOC_PATHS
