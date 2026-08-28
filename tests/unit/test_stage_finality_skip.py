"""Stage entry reuses a settled artifact and redraws an unsettled one (#2609).

The acceptance, driven through the real `should_skip_stage`: a settled LLD with
matching hashes is reused with the hash evidence printed and zero drafter spend,
and a one-character edit to the source's decision table unsettles it with the
redraw citing the mismatch.

`should_skip_stage` returning True IS the zero-spend guarantee -- the drafter
lives behind it, and `run_lld_stage` returns a `skipped` result without ever
building the requirements graph. The control below pins the inverse so a check
that always skips cannot pass this file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from assemblyzero.core import settlement as s
from assemblyzero.workflows.orchestrator import stages
from assemblyzero.workflows.orchestrator.state import OrchestrationState
from assemblyzero.workflows.requirements.audit import save_settlement

ISSUE = 331

TABLE = """\
| ID | Decision | Binding value |
|----|----------|---------------|
| S1 | sampling window | 250 ms |
"""

BODY = f"# Dial\n\n## Pass criteria\n\n{TABLE}"

LLD_TEXT = f"""\
## 1. Context

The dial samples on a fixed window.

## 3. Requirements

{TABLE}
"""


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "docs" / "lld" / "active").mkdir(parents=True)
    (tmp_path / "docs" / "design").mkdir(parents=True)
    (tmp_path / "docs" / "design" / "dial.md").write_text("law\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def lld(repo: Path) -> Path:
    path = repo / "docs" / "lld" / "active" / f"LLD-{ISSUE}.md"
    path.write_text(LLD_TEXT, encoding="utf-8")
    return path


@pytest.fixture
def state(repo: Path) -> OrchestrationState:
    return OrchestrationState(
        issue_number=ISSUE, target_repo=str(repo), config={}
    )


@pytest.fixture
def body_is(monkeypatch):
    """Drive the issue body without `gh` and without a network."""

    def _set(text: str | None):
        monkeypatch.setattr(
            stages, "fetch_issue_body", lambda _repo, _issue: text
        )

    return _set


def _existing(repo: Path, lld: Path) -> dict[str, str | None]:
    return {"triage": None, "lld": str(lld), "spec": None, "impl": None, "pr": None}


def _settle(repo: Path, lld: Path, body: str = BODY) -> None:
    record = s.build_settlement(
        "lld", lld,
        s.collect_inputs(repo, issue_body=body),
        verdict="APPROVED",
    )
    save_settlement(ISSUE, "lld", record, repo)


class TestSettledIsReused:
    def test_a_settled_lld_is_reused(
        self, repo, lld, state, body_is, capsys
    ) -> None:
        _settle(repo, lld)
        body_is(BODY)

        skip, path = stages.should_skip_stage(state, "lld", _existing(repo, lld))

        assert skip is True
        assert path == str(lld)

    def test_the_reuse_prints_hash_evidence(
        self, repo, lld, state, body_is, capsys
    ) -> None:
        """'settled-and-reused with the hash evidence' is the acceptance's
        wording; an operator must be able to see WHY it was reused."""
        _settle(repo, lld)
        body_is(BODY)

        stages.should_skip_stage(state, "lld", _existing(repo, lld))

        out = capsys.readouterr().out
        assert "settled and reused -- no drafter spend" in out
        assert "issue_body" in out
        assert "binding:docs/design/dial.md" in out


class TestAnInputChangeRedraws:
    def test_a_one_character_edit_unsettles(
        self, repo, lld, state, body_is, capsys
    ) -> None:
        _settle(repo, lld)
        body_is(BODY.replace("250 ms", "251 ms"))

        skip, path = stages.should_skip_stage(state, "lld", _existing(repo, lld))

        assert skip is False
        assert path is None

    def test_the_redraw_cites_the_mismatch(
        self, repo, lld, state, body_is, capsys
    ) -> None:
        _settle(repo, lld)
        body_is(BODY.replace("250 ms", "251 ms"))

        stages.should_skip_stage(state, "lld", _existing(repo, lld))

        out = capsys.readouterr().out
        assert "unsettled -- redrawing" in out
        assert "issue_body" in out
        assert "when the artifact settled" in out

    def test_a_binding_doc_edit_unsettles(self, repo, lld, state, body_is) -> None:
        _settle(repo, lld)
        (repo / "docs" / "design" / "dial.md").write_text("amended\n", encoding="utf-8")
        body_is(BODY)

        skip, _ = stages.should_skip_stage(state, "lld", _existing(repo, lld))

        assert skip is False

    def test_a_hand_edited_lld_unsettles(self, repo, lld, state, body_is) -> None:
        _settle(repo, lld)
        lld.write_text(LLD_TEXT + "\nhand edit\n", encoding="utf-8")
        body_is(BODY)

        skip, _ = stages.should_skip_stage(state, "lld", _existing(repo, lld))

        assert skip is False

    def test_a_failed_issue_read_unsettles(self, repo, lld, state, body_is) -> None:
        """`gh` down must draft, never settle on an unread input."""
        _settle(repo, lld)
        body_is(None)

        skip, _ = stages.should_skip_stage(state, "lld", _existing(repo, lld))

        assert skip is False


class TestNonRegression:
    """An artifact with no settlement record keeps the pre-#2609 behaviour.

    Records are written from the first passed stage onward. Treating their
    absence as a reason to redraw would impose the exact tax #2609 removes on
    every artifact that predates it.
    """

    def test_no_record_still_skips_on_presence(
        self, repo, lld, state, body_is
    ) -> None:
        body_is(BODY)
        skip, path = stages.should_skip_stage(state, "lld", _existing(repo, lld))
        assert skip is True
        assert path == str(lld)

    def test_no_record_does_not_claim_to_be_settled(
        self, repo, lld, state, body_is, capsys
    ) -> None:
        body_is(BODY)
        stages.should_skip_stage(state, "lld", _existing(repo, lld))
        assert "settled and reused" not in capsys.readouterr().out

    def test_an_invalid_artifact_is_never_skipped(
        self, repo, lld, state, body_is
    ) -> None:
        """The control: a file missing '## 1. Context' fails validation, and
        settlement must not be able to wave it through."""
        _settle(repo, lld)
        lld.write_text("not an LLD\n", encoding="utf-8")
        _settle(repo, lld)  # settle the broken file, so only validation objects
        body_is(BODY)

        skip, _ = stages.should_skip_stage(state, "lld", _existing(repo, lld))

        assert skip is False

    def test_a_missing_artifact_is_never_skipped(self, repo, state, body_is) -> None:
        body_is(BODY)
        empty = {"triage": None, "lld": None, "spec": None, "impl": None, "pr": None}
        assert stages.should_skip_stage(state, "lld", empty) == (False, None)

    def test_impl_and_pr_are_never_skipped(self, repo, lld, state) -> None:
        for stage in ("impl", "pr"):
            assert stages.should_skip_stage(
                state, stage, _existing(repo, lld)
            ) == (False, None)

    def test_skip_existing_lld_false_still_wins(self, repo, lld, body_is) -> None:
        """A settled artifact does not override an explicit config refusal."""
        _settle(repo, lld)
        body_is(BODY)
        state = OrchestrationState(
            issue_number=ISSUE, target_repo=str(repo),
            config={"skip_existing_lld": False},
        )
        assert stages.should_skip_stage(
            state, "lld", _existing(repo, lld)
        ) == (False, None)


class TestSettleStage:
    def test_a_passed_stage_settles(self, repo, lld, state, body_is, capsys) -> None:
        body_is(BODY)

        stages.settle_stage(state, "lld", str(lld), "APPROVED")

        from assemblyzero.workflows.requirements.audit import load_settlement

        record = load_settlement(ISSUE, "lld", repo)
        assert record is not None
        assert record["verdict"] == "APPROVED"
        assert record["artifact_sha256"] == s.sha256_path(lld)

    def test_settling_then_checking_reuses(
        self, repo, lld, state, body_is
    ) -> None:
        """End to end: settle on pass, reuse on the next launch."""
        body_is(BODY)
        stages.settle_stage(state, "lld", str(lld), "APPROVED")

        skip, _ = stages.should_skip_stage(state, "lld", _existing(repo, lld))

        assert skip is True

    def test_a_stage_that_cannot_settle_is_a_no_op(self, repo, state) -> None:
        stages.settle_stage(state, "impl", "", "")  # must not raise

    def test_settlement_failure_never_fails_the_stage(
        self, repo, lld, state, monkeypatch, capsys
    ) -> None:
        """A stage that passed its gate stays passed."""
        def boom(*_a, **_k):
            raise OSError("disk full")

        monkeypatch.setattr(
            "assemblyzero.workflows.requirements.audit.save_settlement", boom
        )
        stages.settle_stage(state, "lld", str(lld), "APPROVED")  # must not raise
        assert "settlement not recorded" in capsys.readouterr().out
