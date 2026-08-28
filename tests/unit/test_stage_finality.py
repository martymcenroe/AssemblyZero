"""Stage finality: settled until the inputs change (#2609).

The observed history as fixture, inverted. boostgauge #331 took 20 launches in
12 days and had its LLD drawn from scratch seven times while `lld-status.json`
said `"status": "approved"` the whole while -- because that record had no
reader and no input hashes. These tests pin both halves: a settled artifact is
reused with zero drafter spend, and a one-character edit to the source's
decision table unsettles it by name.

Every reuse test has a control asserting the inverse, because a settledness
check that never unsettles and one that always settles are indistinguishable
from a test that only ever asserts reuse.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from assemblyzero.core import settlement as s
from assemblyzero.workflows.requirements.audit import (
    load_settlement,
    save_settlement,
    settled_stages,
    unsettle,
)

ISSUE = 331

SOURCE_TABLE = """\
| ID | Decision | Binding value |
|----|----------|---------------|
| S1 | sampling window | 250 ms |
| S7 | redline colour | #AA0F19 |
| S9 | needle tip | 0.82 r |
"""

ISSUE_BODY = f"""\
# The dial must sample on a fixed window

## Pass criteria

{SOURCE_TABLE}
"""


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A target repo shaped like a real one: docs tree, binding docs, data/."""
    (tmp_path / "docs" / "lld" / "active").mkdir(parents=True)
    (tmp_path / "docs" / "lld" / "drafts").mkdir(parents=True)
    (tmp_path / "docs" / "design").mkdir(parents=True)
    (tmp_path / "docs" / "design" / "dial.md").write_text(
        "The dial's law.\n", encoding="utf-8"
    )
    (tmp_path / "CLAUDE.md").write_text("Repo rules.\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def lld(repo: Path) -> Path:
    path = repo / "docs" / "lld" / "active" / f"LLD-{ISSUE:03d}.md"
    path.write_text(f"## 3. Requirements\n\n{SOURCE_TABLE}", encoding="utf-8")
    return path


def _inputs(repo: Path, body: str = ISSUE_BODY, upstream: Path | None = None):
    return s.collect_inputs(repo, issue_body=body, upstream_artifact=upstream)


def _settle(repo: Path, lld: Path, body: str = ISSUE_BODY) -> dict:
    record = s.build_settlement("lld", lld, _inputs(repo, body), verdict="APPROVED")
    save_settlement(ISSUE, "lld", record, repo)
    return record


# ---------------------------------------------------------------------------
# The invariant: settled until the inputs change
# ---------------------------------------------------------------------------


class TestSettledUntilInputsChange:
    def test_unchanged_inputs_stay_settled(self, repo: Path, lld: Path) -> None:
        record = _settle(repo, lld)
        assert s.verify(record, _inputs(repo)) == []

    def test_one_character_edit_to_the_table_unsettles(
        self, repo: Path, lld: Path
    ) -> None:
        """The acceptance case: 250 ms -> 251 ms, and the redraw cites it."""
        record = _settle(repo, lld)
        edited = ISSUE_BODY.replace("250 ms", "251 ms")
        assert edited != ISSUE_BODY  # the fixture really did change

        mismatches = s.verify(record, _inputs(repo, edited))

        assert len(mismatches) == 1
        assert mismatches[0].startswith("issue_body:")
        assert "when the artifact settled" in mismatches[0]

    def test_a_binding_doc_edit_unsettles(self, repo: Path, lld: Path) -> None:
        record = _settle(repo, lld)
        (repo / "docs" / "design" / "dial.md").write_text(
            "The dial's law, amended.\n", encoding="utf-8"
        )
        mismatches = s.verify(record, _inputs(repo))
        assert [m for m in mismatches if m.startswith("binding:docs/design/dial.md")]

    def test_a_new_binding_doc_unsettles(self, repo: Path, lld: Path) -> None:
        """A gained input changes the derivation even though nothing was edited."""
        record = _settle(repo, lld)
        (repo / "docs" / "design" / "colour.md").write_text("New law.\n", encoding="utf-8")
        mismatches = s.verify(record, _inputs(repo))
        assert any("a new input" in m for m in mismatches), mismatches

    def test_a_removed_binding_doc_unsettles(self, repo: Path, lld: Path) -> None:
        record = _settle(repo, lld)
        (repo / "docs" / "design" / "dial.md").unlink()
        mismatches = s.verify(record, _inputs(repo))
        assert any("is gone" in m for m in mismatches), mismatches

    def test_an_unreadable_issue_body_unsettles(self, repo: Path, lld: Path) -> None:
        """A failed `gh` read must never read as 'nothing changed'."""
        record = _settle(repo, lld)
        mismatches = s.verify(record, _inputs(repo, body=None))
        assert any(m.startswith("issue_body:") for m in mismatches), mismatches

    def test_no_record_is_not_settled(self, repo: Path) -> None:
        assert s.verify(None, _inputs(repo)) == [
            "no settlement record exists for this stage"
        ]

    def test_a_future_version_is_not_settled(self, repo: Path, lld: Path) -> None:
        record = _settle(repo, lld)
        record["settlement_version"] = s.SETTLEMENT_VERSION + 1
        assert s.verify(record, _inputs(repo)) != []


class TestTheArtifactItselfMustMatch:
    def test_the_settled_artifact_matches(self, repo: Path, lld: Path) -> None:
        record = _settle(repo, lld)
        assert s.artifact_matches(record, lld)

    def test_a_hand_edited_artifact_does_not_match(
        self, repo: Path, lld: Path
    ) -> None:
        """Reusing an edited file would present an unreviewed edit as gated."""
        record = _settle(repo, lld)
        lld.write_text(lld.read_text(encoding="utf-8") + "\nhand edit\n",
                       encoding="utf-8")
        assert not s.artifact_matches(record, lld)

    def test_a_missing_artifact_does_not_match(self, repo: Path, lld: Path) -> None:
        record = _settle(repo, lld)
        lld.unlink()
        assert not s.artifact_matches(record, lld)


# ---------------------------------------------------------------------------
# #2615: content, not timestamps
# ---------------------------------------------------------------------------


class TestContentNotTimestamps:
    """A comment bumps an issue's `updatedAt` and changes no binding text.

    The measured evidence is on #2615: #2540's `updatedAt` equalled its last
    comment's `createdAt` to the second, and #2611 with zero comments had
    `updatedAt == createdAt`. A timestamp check unsettles on the campaign's own
    method of posting a diagnosis before fixing. Hashing the body cannot.
    """

    def test_a_body_that_did_not_change_stays_settled(
        self, repo: Path, lld: Path
    ) -> None:
        record = _settle(repo, lld)
        # Same text, re-fetched later. A timestamp check would call this stale.
        assert s.verify(record, _inputs(repo, ISSUE_BODY)) == []

    def test_whitespace_only_line_ending_change_stays_settled(
        self, repo: Path, lld: Path
    ) -> None:
        """LF from `gh`, CRLF from a Windows checkout -- the same document."""
        record = _settle(repo, lld)
        crlf = ISSUE_BODY.replace("\n", "\r\n")
        assert crlf != ISSUE_BODY
        assert s.verify(record, _inputs(repo, crlf)) == []


# ---------------------------------------------------------------------------
# The store: durable, and it keeps what it already carried
# ---------------------------------------------------------------------------


class TestTheStore:
    def test_settlement_round_trips(self, repo: Path, lld: Path) -> None:
        written = _settle(repo, lld)
        assert load_settlement(ISSUE, "lld", repo) == written

    def test_no_settlement_reads_as_none(self, repo: Path) -> None:
        assert load_settlement(ISSUE, "lld", repo) is None

    def test_settling_preserves_the_approval_fields(
        self, repo: Path, lld: Path
    ) -> None:
        """The cache's existing content is what a human reads; a settlement
        write is a read-modify-write, never a replacement."""
        from assemblyzero.workflows.requirements.audit import update_lld_status

        update_lld_status(
            ISSUE, str(lld),
            {"has_gemini_review": True, "final_verdict": "APPROVED",
             "last_review_date": "2026-08-28T14:42:38Z", "review_count": 1},
            repo,
        )
        _settle(repo, lld)

        from assemblyzero.workflows.requirements.audit import load_lld_tracking

        entry = load_lld_tracking(repo)["issues"][str(ISSUE)]
        assert entry["status"] == "approved"
        assert entry["final_verdict"] == "APPROVED"
        assert entry["review_count"] == 1
        assert "settlement" in entry

    def test_two_stages_settle_independently(self, repo: Path, lld: Path) -> None:
        spec = repo / "docs" / "lld" / "drafts" / f"spec-{ISSUE:04d}-x.md"
        spec.write_text("spec\n", encoding="utf-8")
        _settle(repo, lld)
        save_settlement(
            ISSUE, "spec",
            s.build_settlement("spec", spec, _inputs(repo, upstream=lld)),
            repo,
        )
        assert settled_stages(ISSUE, repo) == ["lld", "spec"]

    def test_unsettle_removes_only_its_stage(self, repo: Path, lld: Path) -> None:
        spec = repo / "docs" / "lld" / "drafts" / f"spec-{ISSUE:04d}-x.md"
        spec.write_text("spec\n", encoding="utf-8")
        _settle(repo, lld)
        save_settlement(
            ISSUE, "spec", s.build_settlement("spec", spec, _inputs(repo)), repo
        )
        assert unsettle(ISSUE, "spec", repo) is True
        assert settled_stages(ISSUE, repo) == ["lld"]

    def test_unsettle_reports_when_nothing_was_there(self, repo: Path) -> None:
        assert unsettle(ISSUE, "lld", repo) is False

    def test_regenerating_the_lld_unsettles_the_whole_chain(
        self, repo: Path, lld: Path
    ) -> None:
        """#279's reset rewrites the entry, which drops both stages.

        Regenerating an LLD must unsettle the spec derived from it -- the
        downstream-chain rule. This asserts the behaviour rather than the
        mechanism, so a future rewrite of the reset cannot silently lose it.
        """
        from assemblyzero.workflows.requirements.audit import (
            _reset_lld_status_entry,
        )

        _settle(repo, lld)
        save_settlement(
            ISSUE, "spec", s.build_settlement("spec", lld, _inputs(repo)), repo
        )
        assert settled_stages(ISSUE, repo) == ["lld", "spec"]

        _reset_lld_status_entry(ISSUE, repo)

        assert settled_stages(ISSUE, repo) == []


# ---------------------------------------------------------------------------
# The upstream chain (#2611's ruling, structurally)
# ---------------------------------------------------------------------------


class TestUpstreamChain:
    def test_spec_derives_from_the_lld_not_the_issue(self) -> None:
        assert s.UPSTREAM_OF["spec"] == "lld"

    def test_lld_derives_from_the_source(self) -> None:
        assert s.UPSTREAM_OF["lld"] is None

    def test_editing_the_lld_unsettles_the_spec(self, repo: Path, lld: Path) -> None:
        spec = repo / "docs" / "lld" / "drafts" / f"spec-{ISSUE:04d}-x.md"
        spec.write_text("spec\n", encoding="utf-8")
        record = s.build_settlement("spec", spec, _inputs(repo, upstream=lld))

        lld.write_text("## 3. Requirements\n\n(gutted)\n", encoding="utf-8")

        mismatches = s.verify(record, _inputs(repo, upstream=lld))
        assert any(m.startswith("upstream:artifact") for m in mismatches), mismatches

    def test_an_untouched_lld_leaves_the_spec_settled(
        self, repo: Path, lld: Path
    ) -> None:
        spec = repo / "docs" / "lld" / "drafts" / f"spec-{ISSUE:04d}-x.md"
        spec.write_text("spec\n", encoding="utf-8")
        record = s.build_settlement("spec", spec, _inputs(repo, upstream=lld))
        assert s.verify(record, _inputs(repo, upstream=lld)) == []


# ---------------------------------------------------------------------------
# Artifact path -> stage, the launcher's half
# ---------------------------------------------------------------------------


class TestStageOfArtifactPath:
    @pytest.mark.parametrize(
        "path,expected",
        [
            ("docs/lld/active/LLD-331.md", "lld"),
            ("docs/lld/active/LLD-007.md", None),  # a different issue
            ("docs/lld/drafts/spec-0331-implementation-readiness.md", "spec"),
            ("docs\\lld\\active\\LLD-331.md", "lld"),  # windows separators
            ("docs/lld/active/README.md", None),
        ],
    )
    def test_maps_paths_the_clean_check_emits(
        self, path: str, expected: str | None
    ) -> None:
        assert s.stage_of_artifact_path(path, ISSUE) == expected

    def test_padded_and_unpadded_lld_both_map(self) -> None:
        assert s.stage_of_artifact_path("docs/lld/active/LLD-007.md", 7) == "lld"
        assert s.stage_of_artifact_path("docs/lld/active/LLD-7.md", 7) == "lld"


# ---------------------------------------------------------------------------
# Line-ending normalisation, stated as its own guarantee
# ---------------------------------------------------------------------------


class TestNormalisation:
    def test_crlf_and_lf_hash_the_same(self) -> None:
        assert s.sha256_text("a\r\nb\r\n") == s.sha256_text("a\nb\n")

    def test_lone_cr_normalises_too(self) -> None:
        assert s.sha256_text("a\rb") == s.sha256_text("a\nb")

    def test_different_content_still_differs(self) -> None:
        """The control: normalisation must not flatten real differences."""
        assert s.sha256_text("a\nb\n") != s.sha256_text("a\nc\n")

    def test_a_file_and_its_text_agree(self, tmp_path: Path) -> None:
        path = tmp_path / "x.md"
        path.write_bytes(b"line one\r\nline two\r\n")
        assert s.sha256_path(path) == s.sha256_text("line one\nline two\n")

    def test_an_unreadable_file_hashes_as_none(self, tmp_path: Path) -> None:
        assert s.sha256_path(tmp_path / "does-not-exist.md") is None


# ---------------------------------------------------------------------------
# Evidence the reused stage prints
# ---------------------------------------------------------------------------


class TestEvidence:
    def test_evidence_names_every_input(self, repo: Path, lld: Path) -> None:
        record = _settle(repo, lld)
        lines = s.evidence_lines(record, _inputs(repo))
        body = "\n".join(lines)
        assert "issue_body" in body
        assert "binding:docs/design/dial.md" in body
        assert "binding:CLAUDE.md" in body

    def test_evidence_leads_with_the_settlement_and_artifact(
        self, repo: Path, lld: Path
    ) -> None:
        record = _settle(repo, lld)
        first = s.evidence_lines(record, _inputs(repo))[0]
        assert "settled" in first
        assert "APPROVED" in first
        assert str(record["artifact_sha256"])[:12] in first


class TestBindingInputsAreStable:
    def test_order_does_not_depend_on_the_filesystem(self, repo: Path) -> None:
        first = [i.key for i in s.binding_inputs(repo, s.BINDING_DOC_PATHS)]
        for name in ("z.md", "a.md", "m.md"):
            (repo / "docs" / "design" / name).write_text("x\n", encoding="utf-8")
        second = [i.key for i in s.binding_inputs(repo, s.BINDING_DOC_PATHS)]
        assert second == sorted(second)
        assert set(first).issubset(set(second))

    def test_a_missing_doc_root_is_not_an_error(self, tmp_path: Path) -> None:
        assert s.binding_inputs(tmp_path, ("docs/design",)) == []
