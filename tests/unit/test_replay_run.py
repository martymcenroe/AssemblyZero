"""The replay runner, and the one thing it must never do (#2724).

The launch gate is that the recorded runs replay past the walls that killed
them, so the runner's verdict is load-bearing: a wrong `passed` here would clear
a launch the evidence does not support. `TestDivergenceNeverPasses` is that
acceptance, and the rest of this file exists to make its inputs trustworthy --
a synthesised edit script that does not actually carry draft N to draft N+1
would produce divergence findings that are the runner's fault rather than the
recording's.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from assemblyzero.speedrun.replay import (
    AUDIT_DIR_FMT,
    CALLER_EDITOR,
    CALLER_EDITOR_RETRY,
    KIND_LLD,
    KIND_SPEC,
    RETRY_MARK,
    VERDICT_DIVERGED,
    VERDICT_EARLIER,
    VERDICT_LATER,
    VERDICT_OTHER_GATE,
    VERDICT_PASSED,
    VERDICT_SAME_GATE,
    AuditDir,
    ReplayResult,
    audit_dirs_for_run,
    build_spec_rules,
    classify,
    discover_audit_dirs,
    parse_audit_stamp,
    parse_verdict_file,
    render_table,
    responses_in,
    synthesize_edit_script,
    verdict_to_json,
)
from assemblyzero.workflows.implementation_spec.nodes.edit_script import (
    apply_edit_blocks,
    parse_edit_blocks,
)


def _stamp(text: str) -> datetime:
    return datetime.strptime(text, AUDIT_DIR_FMT).replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# The acceptance: a divergence is never a pass
# ---------------------------------------------------------------------------


class TestDivergenceNeverPasses:
    """#2724's third acceptance criterion, as a test rather than a promise.

    Once a code change alters a prompt, the recorded response is no longer the
    response the model would give. Everything after that point is the runner's
    invention, and the one invention that does real damage is `passed`, because
    it is what a launch decision reads.
    """

    def test_a_divergence_beats_a_clean_finish(self):
        assert classify(
            recorded_cause="spec.review_cap",
            recorded_progress=9,
            replay_cause="",
            replay_progress=9,
            divergence="the recording could not answer call 7",
            finished=True,
        ) == VERDICT_DIVERGED

    def test_a_divergence_beats_getting_further(self):
        assert classify(
            recorded_cause="spec.review_cap",
            recorded_progress=3,
            replay_cause="spec.review_cap",
            replay_progress=99,
            divergence="the recording could not answer call 7",
            finished=False,
        ) == VERDICT_DIVERGED

    def test_only_a_finish_with_no_cause_is_a_pass(self):
        assert classify(
            recorded_cause="spec.review_cap",
            recorded_progress=9,
            replay_cause="",
            replay_progress=9,
            divergence="",
            finished=True,
        ) == VERDICT_PASSED

    def test_a_finish_that_still_named_a_cause_is_not_a_pass(self):
        """`finished` reads a spec path on the state, and a halt path can leave
        one behind. The cause is what decides."""
        assert classify(
            recorded_cause="spec.review_cap",
            recorded_progress=9,
            replay_cause="spec.review_cap",
            replay_progress=9,
            divergence="",
            finished=True,
        ) == VERDICT_SAME_GATE


class TestClassifyMeasuresDistanceFirst:
    def test_further_in_is_later_whatever_ended_it(self):
        assert classify(
            recorded_cause="spec.review_cap", recorded_progress=3,
            replay_cause="spec.completeness_cap", replay_progress=6,
            divergence="", finished=False,
        ) == VERDICT_LATER

    def test_less_far_is_earlier(self):
        assert classify(
            recorded_cause="spec.review_cap", recorded_progress=9,
            replay_cause="spec.edit_script_rejected", replay_progress=3,
            divergence="", finished=False,
        ) == VERDICT_EARLIER

    def test_same_distance_other_gate_is_named_as_such(self):
        """Softening one gate so a different one kills at the same round is not
        progress, and calling it `same_gate` would hide that."""
        assert classify(
            recorded_cause="spec.review_cap", recorded_progress=4,
            replay_cause="spec.completeness_cap", replay_progress=4,
            divergence="", finished=False,
        ) == VERDICT_OTHER_GATE


# ---------------------------------------------------------------------------
# The synthesised edit script has to actually carry the draft
# ---------------------------------------------------------------------------


class TestSynthesizeEditScript:
    """A revision round asks for edit blocks, not a document. If the blocks this
    module derives do not apply, every replay diverges at round 2 and the
    finding is the runner's rather than the recording's."""

    def _carry(self, before: str, after: str) -> str:
        script = synthesize_edit_script(before, after)
        assert script, "no script was produced"
        blocks = parse_edit_blocks(script)
        assert blocks, "the produced script does not parse as edit blocks"
        patched, failures = apply_edit_blocks(before, blocks)
        assert failures == [], f"blocks did not apply: {failures}"
        return patched

    def test_a_replacement_lands_exactly(self):
        before = "# Spec\n\nalpha\nbeta\ngamma\n"
        after = "# Spec\n\nalpha\nBETA\ngamma\n"
        assert self._carry(before, after) == after

    def test_an_insertion_borrows_a_neighbour_to_anchor_on(self):
        """A pure insertion has no text of its own to put in SEARCH, so the
        anchor must widen before the first uniqueness test rather than after."""
        before = "one\ntwo\nthree\n"
        after = "one\ntwo\nINSERTED\nthree\n"
        assert self._carry(before, after) == after

    def test_a_deletion_lands(self):
        before = "one\ntwo\nthree\nfour\n"
        after = "one\nthree\nfour\n"
        assert self._carry(before, after) == after

    def test_a_repeated_line_is_disambiguated_by_widening(self):
        """`apply_edit_blocks` refuses an anchor that matches twice, so a change
        to one of several identical lines must widen until it is unique."""
        before = "x\nsame\ny\nsame\nz\n"
        after = "x\nsame\ny\nCHANGED\nz\n"
        assert self._carry(before, after) == after

    def test_a_change_to_the_last_line_keeps_the_trailing_newline(self):
        """The blocks are joined from `splitlines()`, which drops the final
        newline; `apply_edit_blocks` replaces a substring of the original, so
        the newline survives. Pinned because losing it would make every
        subsequent round's anchors miss by one byte."""
        before = "alpha\nomega\n"
        after = "alpha\nOMEGA\n"
        assert self._carry(before, after) == after

    def test_several_separate_hunks_all_land(self):
        before = "\n".join(f"line{n}" for n in range(20))
        after = before.replace("line3", "LINE3").replace("line17", "LINE17")
        assert self._carry(before, after) == after

    def test_no_change_produces_no_script(self):
        assert synthesize_edit_script("same\n", "same\n") == ""

    def test_an_unanchorable_change_returns_empty_rather_than_a_bad_block(self):
        """A document that is one repeated line has no unique anchor anywhere.
        Returning a block that cannot apply would be worse than saying so: the
        caller degrades to a whole document and counts it."""
        before = "dup\n" * 6
        after = "dup\n" * 5 + "other\n"
        script = synthesize_edit_script(before, after)
        if script:
            blocks = parse_edit_blocks(script)
            _, failures = apply_edit_blocks(before, blocks)
            assert failures == [], "a produced script must apply"


# ---------------------------------------------------------------------------
# Re-encoding the persisted verdict
# ---------------------------------------------------------------------------


VERDICT_FILE = """\
Verdict: REVISE

Rationale: The spec fails the Assertion Traceability check and contains
tests whose inputs cannot distinguish correct from incorrect behaviour.

## Feedback Items
- Assertion Traceability Violation: `assert snapshot.conpty_count == 2`
- Section 10.1 carries a pointer, not test functions
"""


class TestVerdictReEncoding:
    """The reviewer is called with a schema and Standard 0028 left no regex
    fallback, so the persisted markdown handed back verbatim would be read as an
    infrastructure failure the recording never had."""

    def test_the_three_schema_fields_round_trip(self):
        parsed = parse_verdict_file(VERDICT_FILE)
        assert parsed["verdict"] == "REVISE"
        assert parsed["rationale"].startswith("The spec fails")
        assert "distinguish correct from incorrect" in parsed["rationale"]
        assert len(parsed["feedback_items"]) == 2
        assert parsed["feedback_items"][1].endswith("not test functions")

    def test_the_rationale_stops_at_the_feedback_heading(self):
        assert "Feedback Items" not in parse_verdict_file(VERDICT_FILE)["rationale"]

    def test_the_json_parses_under_the_real_contract(self):
        from assemblyzero.core.verdict_schema import parse_structured_review_spec

        result = parse_structured_review_spec(verdict_to_json(VERDICT_FILE))
        assert result["verdict"] == "REVISE"
        assert len(result["feedback_items"]) == 2

    def test_a_verdict_with_no_feedback_items_is_still_valid(self):
        text = "Verdict: APPROVED\n\nRationale: It is ready.\n"
        from assemblyzero.core.verdict_schema import parse_structured_review_spec

        result = parse_structured_review_spec(verdict_to_json(text))
        assert result["verdict"] == "APPROVED"
        assert result["feedback_items"] == []


# ---------------------------------------------------------------------------
# Finding the recording
# ---------------------------------------------------------------------------


class TestDiscovery:
    def test_a_reset_lineage_is_found(self, tmp_path):
        """Runs 10 and 11 of boostgauge #4 exist ONLY under reset-artifacts,
        because `speedrun_reset` moved them there. A discovery that only looked
        where the pipeline writes would find nothing for the two runs the
        launch gate is actually about."""
        moved = (
            tmp_path / "data" / "speedrun" / "reset-artifacts" / "issue-4"
            / "lineage" / "4-implspec-20260903T002044Z" / "2026-09-02T23-44-44Z"
        )
        moved.mkdir(parents=True)
        (moved / "001-spec-draft.md").write_text("d", encoding="utf-8")
        found = discover_audit_dirs(tmp_path, 4)
        assert [d.kind for d in found] == [KIND_SPEC]
        assert found[0].file_count == 1

    def test_a_directory_that_is_not_a_run_stamp_is_skipped(self):
        assert parse_audit_stamp("issue-brief.md") is None
        assert parse_audit_stamp("4-implspec") is None
        assert parse_audit_stamp("2026-09-02T23-44-44Z") is not None

    def test_another_issues_lineage_is_not_picked_up(self, tmp_path):
        other = (
            tmp_path / "docs" / "lineage" / "done" / "41-implspec"
            / "2026-09-02T23-44-44Z"
        )
        other.mkdir(parents=True)
        (other / "001-spec-draft.md").write_text("d", encoding="utf-8")
        assert discover_audit_dirs(tmp_path, 4) == []


class TestAssociatingDirectoriesWithRuns:
    def test_duplicate_copies_are_broken_by_file_count_and_recorded(self):
        """A reset copies a lineage directory, so run 11's spec lineage exists
        twice under the same name -- once with 26 files and once with 4. Taking
        the 4-file copy would replay a truncated recording and report a
        divergence that is the copy's fault."""
        stamp = _stamp("2026-09-02T23-44-44Z")
        dirs = [
            AuditDir(KIND_SPEC, stamp, __import__("pathlib").Path("a"), 4),
            AuditDir(KIND_SPEC, stamp, __import__("pathlib").Path("b"), 26),
        ]
        chosen, notes = audit_dirs_for_run(
            dirs, _stamp("2026-09-02T23-39-43Z"), _stamp("2026-09-03T00-23-46Z")
        )
        assert chosen[KIND_SPEC].file_count == 26
        assert any("most files" in n for n in notes)

    def test_two_different_directories_in_one_window_is_ambiguity_not_a_guess(self):
        dirs = [
            AuditDir(KIND_SPEC, _stamp("2026-09-02T23-44-44Z"),
                     __import__("pathlib").Path("a"), 26),
            AuditDir(KIND_SPEC, _stamp("2026-09-02T23-50-00Z"),
                     __import__("pathlib").Path("b"), 26),
        ]
        chosen, notes = audit_dirs_for_run(
            dirs, _stamp("2026-09-02T23-39-43Z"), _stamp("2026-09-03T00-23-46Z")
        )
        assert KIND_SPEC not in chosen
        assert any("cannot be told apart" in n for n in notes)

    def test_a_directory_outside_the_window_belongs_to_another_run(self):
        dirs = [
            AuditDir(KIND_LLD, _stamp("2026-09-02T21-31-44Z"),
                     __import__("pathlib").Path("a"), 4),
        ]
        chosen, _ = audit_dirs_for_run(
            dirs, _stamp("2026-09-02T23-39-43Z"), _stamp("2026-09-03T00-23-46Z")
        )
        assert chosen == {}


# ---------------------------------------------------------------------------
# The rules
# ---------------------------------------------------------------------------


def _spec_dir(tmp_path, drafts: list[str], verdicts: list[str]):
    """A lineage directory in the numbering the pipeline actually writes."""
    d = tmp_path / "2026-09-02T23-44-44Z"
    d.mkdir()
    number = 1
    for index, draft in enumerate(drafts):
        (d / f"{number:03d}-spec-draft.md").write_text(draft, encoding="utf-8")
        number += 1
        (d / f"{number:03d}-hallucination-check.json").write_text(
            "{}", encoding="utf-8"
        )
        number += 1
        if index < len(verdicts):
            (d / f"{number:03d}-readiness-verdict.md").write_text(
                verdicts[index], encoding="utf-8"
            )
            number += 1
    return d


class TestSpecRules:
    def test_hallucination_checks_are_not_scripted(self, tmp_path):
        """They are deterministic telemetry, not an LLM call. Scripting them
        would put a rule in the set that no call can ever match."""
        d = _spec_dir(tmp_path, ["a\nb\n", "a\nC\n"], [VERDICT_FILE])
        assert any(r.suffix == "hallucination-check" for r in responses_in(d))
        rules, _ = build_spec_rules(d)
        assert all("hallucination" not in r.stage for r in rules)

    def test_the_drafter_is_scripted_once_because_2569_removed_the_fallback(
        self, tmp_path
    ):
        """A revision is edit blocks or it is a halt. A drafter rule for round 2
        would be a rule nothing can reach, which reads as coverage that is not
        there."""
        d = _spec_dir(tmp_path, ["a\nb\n", "a\nC\n", "a\nD\n"], [VERDICT_FILE])
        rules, _ = build_spec_rules(d)
        drafter = [r for r in rules if r.stage == "spec-drafter"]
        assert len(drafter) == 1
        assert drafter[0].on_call == 1

    def test_a_retry_of_one_round_is_answered_with_a_divergence(self, tmp_path):
        """The recording holds ONE outcome per round because the original script
        applied. Handing a retry the next round's script would silently replay a
        different run; refusing it names the divergence where it happens."""
        d = _spec_dir(tmp_path, ["a\nb\n", "a\nC\n"], [VERDICT_FILE])
        rules, _ = build_spec_rules(d)
        retry = [r for r in rules if r.stage == CALLER_EDITOR_RETRY]
        assert len(retry) == 1
        assert retry[0].fail_with
        assert "divergence" in retry[0].fail_with.lower()

    def test_a_first_attempt_and_a_retry_never_match_the_same_rule(self, tmp_path):
        """`ScriptedProvider` fails a call matching two stages, so these two
        patterns must be mutually exclusive or every revision round is an error
        rather than a replay."""
        d = _spec_dir(tmp_path, ["a\nb\n", "a\nC\n"], [VERDICT_FILE])
        rules, _ = build_spec_rules(d)
        editor = [r for r in rules if r.stage == CALLER_EDITOR]
        retry = [r for r in rules if r.stage == CALLER_EDITOR_RETRY]
        fresh = "You are revising an Implementation Spec."
        again = f"You are revising.\n\n## {RETRY_MARK}\n\nblock 1 failed"
        system = "You are a precision patch engine."
        assert [r.matches(system, fresh) for r in editor] == [True] * len(editor)
        assert [r.matches(system, again) for r in editor] == [False] * len(editor)
        assert retry[0].matches(system, again) is True
        assert retry[0].matches(system, fresh) is False

    def test_the_reconstruction_is_counted_not_asserted(self, tmp_path):
        d = _spec_dir(tmp_path, ["a\nb\n", "a\nC\n", "a\nD\n"], [VERDICT_FILE])
        _, recon = build_spec_rules(d)
        assert recon.drafts == 3
        assert recon.verdicts == 1
        assert recon.edit_scripts + recon.edit_script_degraded == 2
        assert recon.notes, "the report must be able to state its own fidelity"


# ---------------------------------------------------------------------------
# The table a PR carries
# ---------------------------------------------------------------------------


class TestRenderTable:
    def test_every_verdict_shown_is_defined_under_the_table(self):
        """The table travels into PR bodies read by people who will not open a
        doc to find out what `other_gate` means."""
        results = [
            ReplayResult(
                tag="run-issue4-183941", stage=KIND_SPEC,
                recorded_cause="spec.review_cap", recorded_progress=9,
                divergence="call 8 unmatched", replay_progress=3,
                verdict=VERDICT_DIVERGED,
            ),
        ]
        table = render_table(results)
        assert "run-issue4-183941" in table
        assert "diverged at round 3" in table
        assert "**diverged**" in table
        assert "- **diverged** —" in table
        assert "same_gate" not in table, "unused verdicts must not be explained"

    def test_a_pass_says_it_finished_rather_than_naming_a_gate(self):
        results = [
            ReplayResult(
                tag="r", stage=KIND_SPEC, recorded_cause="spec.review_cap",
                recorded_progress=9, replay_progress=9, verdict=VERDICT_PASSED,
            ),
        ]
        assert "finished the stage" in render_table(results)


@pytest.mark.parametrize(
    "bad", ["", "not a stamp", "4-implspec", "issue-brief.md", "done"]
)
def test_a_name_that_is_not_a_stamp_is_walked_past(bad):
    assert parse_audit_stamp(bad) is None


def test_a_stamp_shaped_name_that_is_not_a_real_instant_is_loud():
    """`make_run_id()` cannot produce month 13. Returning None here would let
    something that is not the pipeline name run directories and have the replay
    quietly ignore them, which is how a run gets matched to the wrong
    recording."""
    with pytest.raises(ValueError):
        parse_audit_stamp("2026-13-45T99-99-99Z")
