"""Tests for edit-script LLD revision and its section guard (#2200).

The regression these hold shut is measured, not hypothetical. Fixtures
`boostgauge-7-003-draft.md` and `boostgauge-7-005-draft.md` are the real
drafts from `run-issue7-182028`: 003 carried all twelve numbered sections
through mechanical and test-plan validation at 425 lines, and 005, revising it
in response to a REVISE verdict, came back at 267 lines with sections 3, 10,
11 and 12 replaced by the literal heading `## [UNCHANGED] 3. Requirements`.

The binding property is structural, not statistical: on a revision the model
is never asked to redraw the document, so content it does not name in a SEARCH
block cannot change. These tests assert that no path through the node can
regenerate an LLD, that the guard refuses a lossy patch before anything is
saved, and that removing the guard is what lets 005 through.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from importlib import import_module

from assemblyzero.core.llm_provider import LLMCallResult
from assemblyzero.workflows.requirements.nodes.lld_revision import (
    build_lld_edit_prompt,
    removed_required_sections,
    section_numbers,
)

# The nodes package re-exports the generate_draft FUNCTION under the same name
# as its module, so a plain `from ... import generate_draft` binds the function.
gd = import_module("assemblyzero.workflows.requirements.nodes.generate_draft")

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "lld_revision"
TEMPLATE_PATH = ROOT / "docs" / "templates" / "0102-feature-lld-template.md"


@pytest.fixture(scope="module")
def draft_003() -> str:
    return (FIXTURES / "boostgauge-7-003-draft.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def draft_005() -> str:
    return (FIXTURES / "boostgauge-7-005-draft.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def template() -> str:
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def _result(response: str) -> LLMCallResult:
    return LLMCallResult(
        success=True,
        response=response,
        raw_response=response,
        error_message=None,
        provider="fake",
        model_used="fake-model",
        duration_ms=1,
        attempts=1,
    )


def _edit_block(search: str, replace: str) -> str:
    return f"<<<<<<< SEARCH\n{search}\n=======\n{replace}\n>>>>>>> REPLACE"


class _Recorder:
    """A drafter that records every call and replays canned responses."""

    def __init__(self, *responses: str) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    def invoke(self, **kwargs) -> LLMCallResult:
        self.calls.append(kwargs)
        if not self._responses:
            raise AssertionError(
                "drafter invoked more times than the test supplied responses; "
                "a revision must make exactly one call and never fall back"
            )
        return _result(self._responses.pop(0))


@pytest.fixture
def lld_state(tmp_path, draft_003):
    """A revision state: an existing draft plus a reviewer verdict."""
    audit = tmp_path / "audit"
    audit.mkdir()
    return {
        "workflow_type": "lld",
        "assemblyzero_root": str(ROOT),
        "target_repo": str(tmp_path / "repo"),
        "audit_dir": str(audit),
        "config_mock_mode": False,
        "config_drafter": "fake:model",
        "issue_number": 7,
        "issue_title": "config persistence",
        "issue_body": "the issue body",
        "current_draft": draft_003,
        "verdict_history": ["REVISE: section 5 needs the fixture path spelled out"],
        "draft_count": 2,
        "iteration_count": 2,
    }


def _run(monkeypatch, state, drafter):
    monkeypatch.setattr(gd, "get_provider", lambda spec, *a, **k: drafter)
    return gd.generate_draft(state)


# ---------------------------------------------------------------------------
# The regression fixture (acceptance 5)
# ---------------------------------------------------------------------------


class TestBoostgaugeRegression:
    def test_003_carries_all_twelve_sections(self, draft_003):
        top_level = {s for s in section_numbers(draft_003) if "." not in s}
        assert top_level == {str(n) for n in range(1, 13)}

    def test_005_lost_four_of_them(self, draft_005):
        top_level = {s for s in section_numbers(draft_005) if "." not in s}
        assert top_level == {"1", "2", "4", "5", "6", "7", "8", "9"}

    def test_the_unchanged_marker_is_not_a_section(self, draft_005):
        """005's sections were not deleted; their bodies became a marker.

        `## [UNCHANGED] 3. Requirements` is what shipped. Mechanical
        validation agreed it was absent -- it flagged 11 and 12 as Critical
        because `"## 11"` no longer appeared -- so the guard must read it the
        same way.
        """
        assert "## [UNCHANGED] 3. Requirements" in draft_005
        assert "3" not in section_numbers(draft_005)

    def test_the_guard_names_every_lost_section(self, draft_003, draft_005, template):
        removed = removed_required_sections(draft_003, draft_005, template)

        # The four the operator counted, and nothing else, at the top level.
        assert [s for s in removed if "." not in s] == ["3", "10", "11", "12"]
        # Subsections went with them: 003 carried 35 template sections and
        # 005 kept 19, so the guard names all 16 it would have to lose.
        assert len(removed) == 16
        assert removed[0] == "2.1.1"

    def test_a_revision_of_003_cannot_produce_005(
        self, monkeypatch, lld_state, draft_005, tmp_path
    ):
        """The whole point, end to end.

        The drafter here behaves exactly as the one that produced 005: it
        returns a complete replacement document. Under the edit-script
        contract that response carries no edit blocks, so it is not a
        revision at all and nothing is saved.
        """
        drafter = _Recorder(draft_005)

        out = _run(monkeypatch, lld_state, drafter)

        assert "current_draft" not in out
        assert out["error_message"].startswith("[EDIT-SCRIPT]")
        assert "no well-formed SEARCH/REPLACE blocks" in out["error_message"]
        assert list((tmp_path / "audit").iterdir()) == []

    def test_edits_that_would_strip_a_section_are_refused_before_saving(
        self, monkeypatch, lld_state, draft_003, tmp_path
    ):
        """Even named as edits, removing section 11 does not get saved."""
        section_11 = "## 11. Risks & Mitigations"
        assert section_11 in draft_003
        drafter = _Recorder(
            _edit_block(section_11, "## [UNCHANGED] 11. Risks & Mitigations")
        )

        out = _run(monkeypatch, lld_state, drafter)

        assert "current_draft" not in out
        assert "template-required section(s) 11" in out["error_message"]
        assert list((tmp_path / "audit").iterdir()) == []


# ---------------------------------------------------------------------------
# Preservation (acceptance 1)
# ---------------------------------------------------------------------------


class TestPreservation:
    def test_everything_outside_the_named_span_is_byte_identical(
        self, monkeypatch, lld_state, draft_003
    ):
        search = "## 4. Alternatives Considered"
        replace = "## 4. Alternatives Considered\n\nAdded by the revision."
        drafter = _Recorder(_edit_block(search, replace))

        out = _run(monkeypatch, lld_state, drafter)

        revised = out["current_draft"]
        assert revised == draft_003.replace(search, replace, 1)
        # Line-for-line: only the named span differs.
        before = draft_003.splitlines()
        after = revised.splitlines()
        assert before[: before.index(search)] == after[: after.index(search)]

    def test_the_revision_is_the_prior_draft_plus_the_edits(
        self, monkeypatch, lld_state, draft_003
    ):
        drafter = _Recorder(
            _edit_block("## 9. Legal & Compliance", "## 9. Legal & Compliance\n\nNone.")
        )

        out = _run(monkeypatch, lld_state, drafter)

        assert section_numbers(out["current_draft"]) == section_numbers(draft_003)
        assert len(out["current_draft"]) > len(draft_003)

    def test_multiple_edits_all_apply(self, monkeypatch, lld_state):
        drafter = _Recorder(
            _edit_block("## 5. Data & Fixtures", "## 5. Data & Fixtures\n\nOne.")
            + "\n"
            + _edit_block("## 6. Diagram", "## 6. Diagram\n\nTwo.")
        )

        out = _run(monkeypatch, lld_state, drafter)

        assert "One." in out["current_draft"]
        assert "Two." in out["current_draft"]


# ---------------------------------------------------------------------------
# No redraw, ever (the design constraint)
# ---------------------------------------------------------------------------


class TestNeverRedraws:
    def test_the_revision_asks_for_edit_blocks_not_a_document(
        self, monkeypatch, lld_state
    ):
        drafter = _Recorder(_edit_block("## 6. Diagram", "## 6. Diagram\n\nx"))

        _run(monkeypatch, lld_state, drafter)

        content = drafter.calls[0]["content"]
        assert "<<<<<<< SEARCH" in content
        assert "Do NOT rewrite it" in content
        assert "precision patch engine" in drafter.calls[0]["system_prompt"]

    def test_a_failed_revision_makes_exactly_one_model_call(
        self, monkeypatch, lld_state, draft_005
    ):
        """_Recorder raises if invoked twice, which a fallback would do."""
        drafter = _Recorder(draft_005)

        out = _run(monkeypatch, lld_state, drafter)

        assert len(drafter.calls) == 1
        assert out["error_message"]

    def test_the_revision_prompt_carries_no_preservation_pleading(self):
        """Asking the generator to police its own drift is the defect.

        The old prompt said "PRESERVE sections that weren't flagged" and
        "Keep ALL template sections intact", and 005 shipped anyway.
        """
        prompt = build_lld_edit_prompt("# doc\n\n## 1. A\n", "## FEEDBACK\n\nfix it")

        lowered = prompt.lower()
        assert "preserve" not in lowered
        assert "byte-identical" not in lowered
        assert "intact" not in lowered

    def test_unmatched_search_halts_rather_than_redrawing(
        self, monkeypatch, lld_state
    ):
        drafter = _Recorder(_edit_block("text that is not in the draft", "x"))

        out = _run(monkeypatch, lld_state, drafter)

        assert "current_draft" not in out
        assert "SEARCH text not found" in out["error_message"]
        assert len(drafter.calls) == 1

    def test_ambiguous_search_halts(self, monkeypatch, lld_state, draft_003):
        repeated = "| Risk | Impact |"
        state = dict(lld_state)
        state["current_draft"] = f"## 1. A\n\n{repeated}\n\n{repeated}\n"
        drafter = _Recorder(_edit_block(repeated, "changed"))

        out = _run(monkeypatch, state, drafter)

        assert "SEARCH text ambiguous" in out["error_message"]

    def test_a_no_op_edit_halts(self, monkeypatch, lld_state):
        heading = "## 6. Diagram"
        drafter = _Recorder(_edit_block(heading, heading))

        out = _run(monkeypatch, lld_state, drafter)

        assert "changed nothing" in out["error_message"]

    def test_the_halt_message_says_the_prior_draft_survived(
        self, monkeypatch, lld_state, draft_005
    ):
        out = _run(monkeypatch, lld_state, _Recorder(draft_005))

        assert "prior draft is unchanged" in out["error_message"]
        assert "no full-regeneration fallback" in out["error_message"]


# ---------------------------------------------------------------------------
# The guard is what stops it (acceptance 4)
# ---------------------------------------------------------------------------


class TestGuardMutation:
    def test_removing_the_guard_lets_the_lossy_revision_through(
        self, monkeypatch, lld_state, draft_003
    ):
        """Mutation: neuter the guard and the section loss is saved.

        Without this, a passing suite cannot distinguish "the guard fires"
        from "nothing ever reached the guard".
        """
        section_11 = "## 11. Risks & Mitigations"
        blocks = _edit_block(section_11, "## [UNCHANGED] 11. Risks & Mitigations")

        guarded = _run(monkeypatch, dict(lld_state), _Recorder(blocks))
        assert "current_draft" not in guarded

        monkeypatch.setattr(gd, "removed_required_sections", lambda *a, **k: [])
        unguarded = _run(monkeypatch, dict(lld_state), _Recorder(blocks))

        assert "current_draft" in unguarded
        assert "11" not in section_numbers(unguarded["current_draft"])

    def test_the_guard_ignores_sections_the_prior_draft_never_had(self, template):
        prior = "## 1. Context & Goal\n\nx\n"
        revised = "## 1. Context & Goal\n\ny\n"

        assert removed_required_sections(prior, revised, template) == []

    def test_the_guard_ignores_sections_the_template_does_not_require(
        self, template
    ):
        prior = "## 1. Context & Goal\n\nx\n\n## 99. Scratch\n\nnotes\n"
        revised = "## 1. Context & Goal\n\nx\n"

        assert removed_required_sections(prior, revised, template) == []

    def test_the_guard_runs_before_the_draft_is_saved(
        self, monkeypatch, lld_state, tmp_path
    ):
        saved = MagicMock()
        monkeypatch.setattr(gd, "save_audit_file", saved)
        drafter = _Recorder(
            _edit_block("## 12. Definition of Done", "## [UNCHANGED] 12. DoD")
        )

        _run(monkeypatch, lld_state, drafter)

        saved.assert_not_called()


# ---------------------------------------------------------------------------
# The preservation log line (acceptance 3)
# ---------------------------------------------------------------------------


class TestPreservationLogLine:
    def test_it_matches_the_spec_stage_line(self, monkeypatch, lld_state, capsys):
        drafter = _Recorder(_edit_block("## 6. Diagram", "## 6. Diagram\n\nx"))

        _run(monkeypatch, lld_state, drafter)

        out = capsys.readouterr().out
        assert "[EDIT-SCRIPT] Applied 1 edit(s);" in out
        assert "of prior draft preserved byte-identical" in out

    def test_a_large_rewrite_would_show_a_low_percentage(
        self, monkeypatch, lld_state, capsys
    ):
        """The line is the narration's tell that a rewrite happened.

        A single edit block may legally replace most of a section's body. The
        percentage is what makes that visible the moment it happens, instead
        of after a validator notices the document shrank.
        """
        body = "\n".join(f"line {n}" for n in range(100))
        state = dict(lld_state)
        state["current_draft"] = f"## 1. Context & Goal\n\n{body}\n"
        drafter = _Recorder(_edit_block(body, "gutted"))

        _run(monkeypatch, state, drafter)

        out = capsys.readouterr().out
        assert "[EDIT-SCRIPT] Applied 1 edit(s);" in out
        percent = int(out.split("edit(s); ")[1].split("%")[0])
        assert percent < 10


# ---------------------------------------------------------------------------
# Scope: what the port must not disturb
# ---------------------------------------------------------------------------


class TestScope:
    def test_an_initial_lld_draft_still_generates_a_document(
        self, monkeypatch, lld_state
    ):
        state = dict(lld_state)
        state["current_draft"] = ""
        state["verdict_history"] = []
        document = "# LLD-007\n\n## 1. Context & Goal\n\nfresh\n"
        drafter = _Recorder(document)

        out = _run(monkeypatch, state, drafter)

        assert out["current_draft"] == document
        assert "<<<<<<< SEARCH" not in drafter.calls[0]["content"]

    def test_mock_mode_keeps_the_classic_path(self, monkeypatch, lld_state):
        state = dict(lld_state)
        state["config_mock_mode"] = True
        document = "# LLD-007\n\n## 1. Context & Goal\n\nmocked\n"
        drafter = _Recorder(document)

        out = _run(monkeypatch, state, drafter)

        assert out["current_draft"] == document

    def test_the_issue_workflow_is_untouched(self, monkeypatch, lld_state):
        state = dict(lld_state)
        state["workflow_type"] = "issue"
        state["brief_content"] = "a brief"
        document = "# feat: a thing\n\n## Summary\n\nprose\n"
        drafter = _Recorder(document)

        out = _run(monkeypatch, state, drafter)

        assert out["current_draft"] == document
        assert "<<<<<<< SEARCH" not in drafter.calls[0]["content"]


# ---------------------------------------------------------------------------
# Section parsing
# ---------------------------------------------------------------------------


class TestSectionNumbers:
    @pytest.mark.parametrize(
        "heading,expected",
        [
            ("## 1. Context & Goal", {"1"}),
            ("### 2.1 Files Changed", {"2.1"}),
            ("### 2.1.1 Path Validation", {"2.1.1"}),
            ("## 12. Definition of Done", {"12"}),
            ("## [UNCHANGED] 3. Requirements", set()),
            ("## Appendix: Review Log", set()),
            ("Some prose mentioning ## 4. not at line start", set()),
        ],
    )
    def test_headings(self, heading, expected):
        assert section_numbers(heading + "\n") == expected

    def test_ordering_is_numeric_not_lexical(self, template):
        prior = "\n".join(
            f"## {n}. S{n}" for n in (2, 3, 9, 10, 11, 12)
        )
        removed = removed_required_sections(prior, "## 2. S2", template)

        assert removed == ["3", "9", "10", "11", "12"]


# ---------------------------------------------------------------------------
# The extracted context builder
# ---------------------------------------------------------------------------


class TestRevisionContext:
    def test_both_paths_are_fed_the_same_feedback(self, lld_state, template):
        context = gd.build_revision_context(lld_state)
        classic = gd._build_prompt(lld_state, template, "lld")
        edit = build_lld_edit_prompt(lld_state["current_draft"], context)

        assert "section 5 needs the fixture path spelled out" in context
        assert context.strip() in edit
        assert "section 5 needs the fixture path spelled out" in classic

    def test_a_prior_run_verdict_still_reaches_the_edit_path(
        self, monkeypatch, lld_state
    ):
        """#1443 context rides in the system prompt the edit path replaces.

        On a resumed stage the prior attempt's verdict must not vanish just
        because the revision is now expressed as edits.
        """
        state = dict(lld_state)
        state["previous_verdict_text"] = "prior run said: section 7 is thin"
        drafter = _Recorder(_edit_block("## 6. Diagram", "## 6. Diagram\n\nx"))

        _run(monkeypatch, state, drafter)

        assert "prior run said: section 7 is thin" in drafter.calls[0]["content"]

    def test_mechanical_errors_come_first(self, lld_state):
        state = dict(lld_state)
        state["validation_errors"] = ["Critical: Section 11 missing from LLD"]

        context = gd.build_revision_context(state)

        assert context.startswith("## MECHANICAL VALIDATION ERRORS")
        assert "Section 11 missing" in context

    def test_no_feedback_yields_an_empty_context(self, tmp_path):
        assert gd.build_revision_context({"current_draft": "# doc\n"}) == ""
