"""Spec-stage convergence failures must reach the 0025 loop (Closes #2198).

The prompt-failure telemetry recorded only drafter-side validation failures. A
spec sub-workflow that burned its whole iteration budget on reviewer REVISE
verdicts and halted left no record at all.

Measured on boostgauge `run-issue1-124144` (2026-08-10): 685 seconds of spec
drafting and three Gemini review rounds, every one REVISE for the same objection
class, halt at the cap. `prompt_revision_rank.py` for that repo showed 24
fingerprints and every one was `lld:*` -- the spec stage's most expensive
failure mode was invisible to the loop that exists to fix exactly that.

Standard 0025 can only fix what it can rank, so the record has to carry a
fingerprint that repeats across runs and the cost that makes it worth ranking.
"""

import json
from unittest.mock import patch

import pytest

from assemblyzero.speedrun.prompt_telemetry import (
    fingerprint,
    rankable_detail,
    read_failures,
    record_failure,
    telemetry_path,
)
from assemblyzero.workflows.orchestrator.stages import (
    _record_spec_convergence_failure,
)

# The objection class that recurred three times in run-issue1-124144.
FEEDBACK = (
    "The spec invents pixel geometry the requirements never pin down.\n"
    "\n"
    "Specifically, the needle length of 120px appears in no requirement, and\n"
    "the test asserts it as though it were specified."
)


class TestTheRecordIsEmitted:
    def test_a_capped_revise_is_recorded(self, tmp_path):
        _record_spec_convergence_failure(
            str(tmp_path), 1,
            {"review_verdict": "REVISE", "review_feedback": FEEDBACK},
            685.0, {"drafter": "claude-opus-5"},
        )

        rows = read_failures(tmp_path)
        assert len(rows) == 1, (
            "the spec stage's most expensive failure mode left no record; the "
            "0025 loop cannot rank what it never sees"
        )
        assert rows[0]["stage"] == "spec"
        assert rows[0]["check"] == "reviewer-revise"

    def test_the_cost_is_carried(self, tmp_path):
        """Ranking without cost cannot tell an expensive failure from a cheap
        one, and this one costs eleven minutes."""
        _record_spec_convergence_failure(
            str(tmp_path), 1,
            {"review_verdict": "REVISE", "review_feedback": FEEDBACK},
            685.0, {},
        )
        assert read_failures(tmp_path)[0]["duration_seconds"] == 685.0

    def test_the_fingerprint_is_spec_land(self, tmp_path):
        """Every fingerprint in the boostgauge table was lld:*. This is the
        first one that is not."""
        _record_spec_convergence_failure(
            str(tmp_path), 1,
            {"review_verdict": "REVISE", "review_feedback": FEEDBACK},
            685.0, {},
        )
        assert read_failures(tmp_path)[0]["fingerprint"].startswith(
            "spec:reviewer-revise:"
        )

    def test_the_issue_and_model_travel(self, tmp_path):
        _record_spec_convergence_failure(
            str(tmp_path), 7,
            {"review_verdict": "REVISE", "review_feedback": FEEDBACK},
            10.0, {"drafter": "claude-opus-5"},
        )
        row = read_failures(tmp_path)[0]
        assert row["issue"] == 7
        assert row["drafter_model"] == "claude-opus-5"


class TestWhatIsNotRecorded:
    def test_an_approved_stage_records_nothing(self, tmp_path):
        _record_spec_convergence_failure(
            str(tmp_path), 1,
            {"review_verdict": "APPROVED", "review_feedback": ""},
            10.0, {},
        )
        assert read_failures(tmp_path) == []

    def test_a_blocked_verdict_records_nothing_here(self, tmp_path):
        """BLOCKED is a requirements conflict -- it files a must-resolve
        question (#2192) and is a different failure class from a drafter whose
        prompt keeps producing the same objection."""
        _record_spec_convergence_failure(
            str(tmp_path), 1,
            {"review_verdict": "BLOCKED", "review_feedback": "conflict"},
            10.0, {},
        )
        assert read_failures(tmp_path) == []

    def test_no_feedback_records_nothing(self, tmp_path):
        """A record whose detail is empty fingerprints to nothing rankable."""
        _record_spec_convergence_failure(
            str(tmp_path), 1,
            {"review_verdict": "REVISE", "review_feedback": ""},
            10.0, {},
        )
        assert read_failures(tmp_path) == []

    def test_telemetry_never_breaks_the_stage(self, tmp_path, caplog):
        """The module's own rule: telemetry that can break the thing it
        measures is worse than no telemetry."""
        with patch(
            "assemblyzero.speedrun.prompt_telemetry.record_failure",
            side_effect=RuntimeError("disk gone"),
        ):
            _record_spec_convergence_failure(
                str(tmp_path), 1,
                {"review_verdict": "REVISE", "review_feedback": FEEDBACK},
                10.0, {},
            )  # must not raise


class TestTheFingerprintIsRankable:
    """A fingerprint that never repeats cannot be ranked, and ranking is the
    whole point of the 0025 loop."""

    def test_the_same_objection_two_runs_running_shares_a_fingerprint(self, tmp_path):
        second = FEEDBACK.replace("120px", "140px")  # a later paragraph differs

        for feedback in (FEEDBACK, second):
            _record_spec_convergence_failure(
                str(tmp_path), 1,
                {"review_verdict": "REVISE", "review_feedback": feedback},
                10.0, {},
            )

        rows = read_failures(tmp_path)
        assert len(rows) == 2
        assert rows[0]["fingerprint"] == rows[1]["fingerprint"], (
            "two runs blocked by the same objection must land in one bucket, "
            "or the rate this exists to measure is always one"
        )

    def test_a_different_objection_gets_a_different_fingerprint(self, tmp_path):
        for feedback in (FEEDBACK, "The spec omits the error path entirely."):
            _record_spec_convergence_failure(
                str(tmp_path), 1,
                {"review_verdict": "REVISE", "review_feedback": feedback},
                10.0, {},
            )
        rows = read_failures(tmp_path)
        assert rows[0]["fingerprint"] != rows[1]["fingerprint"]

    def test_the_detail_is_bounded(self):
        assert len(rankable_detail("x" * 900)) <= 160

    def test_leading_list_markers_are_stripped(self):
        assert rankable_detail("- The spec invents geometry.") == (
            "The spec invents geometry."
        )

    def test_blank_leading_lines_are_skipped(self):
        assert rankable_detail("\n\n  \nReal finding.") == "Real finding."

    def test_it_uses_the_same_normalization_as_the_mechanical_fingerprints(self):
        detail = rankable_detail(FEEDBACK)
        assert fingerprint("spec", "reviewer-revise", detail) == (
            "spec:reviewer-revise:"
            "the-spec-invents-pixel-geometry-the-requirements-never-pin-down"
        )


class TestTheSchemaStaysBackwardCompatible:
    def test_a_row_written_without_a_duration_still_reads(self, tmp_path):
        """#2075 reads this file. Existing rows predate the field."""
        path = telemetry_path(tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({
                "ts_local": "2026-08-01 13:37:46", "repo": "r", "issue": 2,
                "stage": "lld", "check": "mechanical",
                "fingerprint": "lld:mechanical:section-2-1-table-malformed",
                "draft_number": 1, "drafter_model": "", "run_id": "",
                "detail_raw": "Section 2.1 table malformed",
            }) + "\n",
            encoding="utf-8",
        )

        rows = read_failures(tmp_path)
        assert len(rows) == 1
        assert rows[0].get("duration_seconds") is None

    def test_existing_callers_need_no_duration(self, tmp_path):
        record = record_failure(
            tmp_path, stage="lld", check="mechanical",
            detail="Section 2.1 table malformed",
        )
        assert record is not None
        assert record.duration_seconds is None


class TestTheRankerCostsIt:
    """A duration nothing reads is dead weight. #2198's point is that the
    ranking table governs spec prompts as it governs lld ones, and ranking is
    by cost."""

    def test_a_record_with_its_own_duration_is_costed(self):
        from assemblyzero.speedrun.prompt_ranking import rank

        ranked = rank(
            [
                {"fingerprint": "spec:reviewer-revise:x", "run_id": "",
                 "duration_seconds": 685.0},
                {"fingerprint": "spec:reviewer-revise:x", "run_id": "",
                 "duration_seconds": 685.0},
            ],
            durations={},
        )

        assert ranked[0].duration_known, (
            "the record measured its own cost; flagging it duration-unknown "
            "would rank the stage's most expensive failure below a cheap one"
        )
        assert ranked[0].cost == pytest.approx(1370.0)

    def test_rows_without_one_still_use_the_run_table(self):
        """Every historical lld record resolves exactly as before."""
        from assemblyzero.speedrun.prompt_ranking import rank

        ranked = rank(
            [{"fingerprint": "lld:mechanical:x", "run_id": "run-issue2-133746"}],
            durations={(2, "133746"): 86.1},
        )

        assert ranked[0].duration_known
        assert ranked[0].mean_wasted_seconds == pytest.approx(86.1)

    def test_an_unknown_duration_is_still_never_costed_at_zero(self):
        from assemblyzero.speedrun.prompt_ranking import rank

        ranked = rank([{"fingerprint": "spec:x:y", "run_id": ""}], durations={})
        assert not ranked[0].duration_known
        assert ranked[0].cost is None


@pytest.mark.parametrize("verdict", ["REVISE", "revise"])
def test_only_the_exact_verdict_records(tmp_path, verdict):
    """The state field is set from a structured schema, so it is exact. A
    case-insensitive match here would record on values the graph never emits."""
    _record_spec_convergence_failure(
        str(tmp_path), 1,
        {"review_verdict": verdict, "review_feedback": FEEDBACK}, 10.0, {},
    )
    assert len(read_failures(tmp_path)) == (1 if verdict == "REVISE" else 0)
