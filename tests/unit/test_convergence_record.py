"""The record the graph writes for itself, and the report reading it (#2721).

The report learned to say how each run ended by parsing a prose log. This is the
replacement: rows the graph wrote at the moment it knew. The two acceptance
criteria from the issue are `TestTheRollWritesItsOwnRecord` (a roll produces a
terminal record for a passed roll and for a halted one) and
`TestTheReportPrefersTheRecord` (given both, the record wins and the source is
stated).

The rest of this file exists so those two can be trusted. A record store that
silently drops a corrupt line, or a furthest-reached reading that compares a
node ordinal to a stage ordinal, would produce convergence numbers that look
measured and are not.
"""
from __future__ import annotations

import json

import pytest

from assemblyzero.speedrun.convergence import (
    EVENT_NODE_ENTER,
    EVENT_RUN_TERMINAL,
    EVENT_STAGE_ENTER,
    KEY_FINALIZE,
    OUTCOME_FAILED,
    OUTCOME_PASSED,
    SOURCE_BANNER,
    SOURCE_RECORD,
    current_run_tag,
    furthest_by_run,
    read_records,
    record_node_enter,
    record_stage_enter,
    record_terminal,
    records_path,
    terminals_by_run,
)
from assemblyzero.speedrun.factory_report import (
    RunLogFacts,
    apply_records,
    source_counts,
)

TAG = "run-issue4-183941"


@pytest.fixture
def tagged(monkeypatch):
    monkeypatch.setenv("SPEEDRUN_RUN_TAG", TAG)
    return TAG


# ---------------------------------------------------------------------------
# Acceptance 1: a roll writes its own terminal record
# ---------------------------------------------------------------------------


class TestTheRollWritesItsOwnRecord:
    def test_a_halted_roll_records_the_gate_that_ended_it(self, tmp_path, tagged):
        record_stage_enter(tmp_path, "lld", 2, 7)
        record_node_enter(tmp_path, "lld", "N1_generate_draft", 4, 11)
        record_stage_enter(tmp_path, "spec", 4, 7)
        record_terminal(
            tmp_path,
            outcome=OUTCOME_FAILED,
            furthest_stage="spec",
            gate_key="spec.review_cap",
        )
        records, unreadable = read_records(tmp_path)
        assert unreadable == 0
        terminal = terminals_by_run(records)[TAG]
        assert terminal["outcome"] == OUTCOME_FAILED
        assert terminal["gate_key"] == "spec.review_cap"
        assert terminal["furthest_stage"] == "spec"

    def test_a_passed_roll_records_finalize_rather_than_a_gate(
        self, tmp_path, tagged
    ):
        record_stage_enter(tmp_path, "cleanup", 7, 7)
        record_terminal(
            tmp_path,
            outcome=OUTCOME_PASSED,
            furthest_stage="cleanup",
            gate_key=KEY_FINALIZE,
        )
        terminal = terminals_by_run(read_records(tmp_path)[0])[TAG]
        assert terminal["outcome"] == OUTCOME_PASSED
        assert terminal["gate_key"] == KEY_FINALIZE

    def test_every_event_kind_lands_in_one_store(self, tmp_path, tagged):
        record_stage_enter(tmp_path, "lld", 2, 7)
        record_node_enter(tmp_path, "lld", "N1", 4, 11)
        record_terminal(
            tmp_path, outcome=OUTCOME_PASSED, furthest_stage="lld"
        )
        records, _ = read_records(tmp_path)
        assert [r["event"] for r in records] == [
            EVENT_STAGE_ENTER, EVENT_NODE_ENTER, EVENT_RUN_TERMINAL,
        ]
        assert records_path(tmp_path).name == "run-records.jsonl"
        assert records_path(tmp_path).parent.name == "telemetry"


# ---------------------------------------------------------------------------
# Acceptance 2: the report prefers the record and says so
# ---------------------------------------------------------------------------


def _banner_facts(**kwargs) -> RunLogFacts:
    base = dict(
        run_id=TAG, issue=4, path="", mtime="2026-09-02 18:39:41",
        outcome="failed", failed_stage="spec", furthest_stage="spec",
        cause="spec.review_cap",
    )
    base.update(kwargs)
    return RunLogFacts(**base)


class TestTheReportPrefersTheRecord:
    def test_the_record_overrides_the_banner_parse(self, tmp_path, tagged):
        record_terminal(
            tmp_path,
            outcome=OUTCOME_FAILED,
            furthest_stage="impl",
            gate_key="impl.stagnation.coverage",
        )
        [run] = apply_records([_banner_facts()], tmp_path)
        assert run.cause == "impl.stagnation.coverage"
        assert run.failed_stage == "impl"
        assert run.source == SOURCE_RECORD

    def test_a_run_with_no_record_keeps_the_banner_and_says_so(
        self, tmp_path, tagged
    ):
        """The two sources are never mixed into one number without saying which
        is which -- that is the whole point of carrying the field."""
        record_terminal(
            tmp_path, outcome=OUTCOME_PASSED, furthest_stage="cleanup"
        )
        older = _banner_facts(run_id="run-issue4-010710")
        runs = apply_records([_banner_facts(), older], tmp_path)
        assert [r.source for r in runs] == [SOURCE_RECORD, SOURCE_BANNER]
        assert source_counts(runs) == {SOURCE_RECORD: 1, SOURCE_BANNER: 1}

    def test_no_records_at_all_leaves_every_run_on_the_banner(self, tmp_path):
        runs = apply_records([_banner_facts()], tmp_path)
        assert runs[0].source == SOURCE_BANNER
        assert runs[0].cause == "spec.review_cap"

    def test_entries_without_a_terminal_still_say_how_far_it_got(
        self, tmp_path, tagged
    ):
        """This is the case the banner parse cannot describe at all: 19 of
        boostgauge's 180 runs died mid-call and printed no banner. The entries
        are written as the run advances, so they survive it."""
        record_stage_enter(tmp_path, "impl", 5, 7)
        [run] = apply_records(
            [_banner_facts(outcome="killed", furthest_stage="", cause="killed")],
            tmp_path,
        )
        assert run.furthest_stage == "impl"
        assert run.source == SOURCE_RECORD
        assert run.outcome == "killed", (
            "no terminal record means no claim about the outcome -- inventing "
            "one here is exactly the failure this record exists to prevent"
        )


# ---------------------------------------------------------------------------
# Reading the store
# ---------------------------------------------------------------------------


class TestReadingIsCounted:
    def test_a_corrupt_line_is_counted_rather_than_dropped(self, tmp_path, tagged):
        record_stage_enter(tmp_path, "lld", 2, 7)
        with records_path(tmp_path).open("a", encoding="utf-8") as fh:
            fh.write("{not json\n")
            fh.write(json.dumps({"event": "something.else"}) + "\n")
        records, unreadable = read_records(tmp_path)
        assert len(records) == 1
        assert unreadable == 2, (
            "a reader that reports a count while silently dropping lines is "
            "stating a number it did not count"
        )

    def test_a_missing_store_is_empty_not_an_error(self, tmp_path):
        assert read_records(tmp_path) == ([], 0)

    def test_an_untagged_record_is_dropped_rather_than_merged(
        self, tmp_path, monkeypatch
    ):
        """Several untagged runs under one blank key would read as one run."""
        monkeypatch.delenv("SPEEDRUN_RUN_TAG", raising=False)
        record_terminal(tmp_path, outcome=OUTCOME_PASSED, furthest_stage="lld")
        records, _ = read_records(tmp_path)
        assert len(records) == 1
        assert terminals_by_run(records) == {}

    def test_the_tag_is_read_from_the_launcher_and_never_invented(
        self, monkeypatch
    ):
        monkeypatch.delenv("SPEEDRUN_RUN_TAG", raising=False)
        assert current_run_tag() == ""
        monkeypatch.setenv("SPEEDRUN_RUN_TAG", "  run-issue7-080837  ")
        assert current_run_tag() == "run-issue7-080837"

    def test_a_resume_appends_and_the_later_terminal_wins(self, tmp_path, tagged):
        record_terminal(
            tmp_path, outcome=OUTCOME_FAILED, furthest_stage="spec",
            gate_key="spec.review_cap",
        )
        record_terminal(
            tmp_path, outcome=OUTCOME_PASSED, furthest_stage="cleanup",
            gate_key=KEY_FINALIZE,
        )
        terminal = terminals_by_run(read_records(tmp_path)[0])[TAG]
        assert terminal["outcome"] == OUTCOME_PASSED


class TestFurthestReached:
    def test_a_later_stage_beats_an_earlier_stages_node(self, tmp_path, tagged):
        """A stage ordinal and a node ordinal are different scales. Comparing
        them would let node 11 of the LLD outrank stage 5, and every run that
        reached implementation would sort below one that never left drafting."""
        record_stage_enter(tmp_path, "lld", 2, 7)
        record_node_enter(tmp_path, "lld", "N11_finalize", 11, 11)
        record_stage_enter(tmp_path, "impl", 5, 7)
        records, _ = read_records(tmp_path)
        assert furthest_by_run(records)[TAG] == ("impl", "")

    def test_the_node_reported_is_the_furthest_within_the_furthest_stage(
        self, tmp_path, tagged
    ):
        record_stage_enter(tmp_path, "spec", 4, 7)
        record_node_enter(tmp_path, "spec", "N2_generate_spec", 5, 10)
        record_node_enter(tmp_path, "spec", "N5_review_spec", 8, 10)
        record_node_enter(tmp_path, "spec", "N2_generate_spec", 5, 10)
        records, _ = read_records(tmp_path)
        assert furthest_by_run(records)[TAG] == ("spec", "N5_review_spec")

    def test_two_runs_do_not_bleed_into_each_other(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SPEEDRUN_RUN_TAG", "run-a")
        record_stage_enter(tmp_path, "impl", 5, 7)
        monkeypatch.setenv("SPEEDRUN_RUN_TAG", "run-b")
        record_stage_enter(tmp_path, "lld", 2, 7)
        records, _ = read_records(tmp_path)
        furthest = furthest_by_run(records)
        assert furthest["run-a"] == ("impl", "")
        assert furthest["run-b"] == ("lld", "")


# ---------------------------------------------------------------------------
# The wrap that emits the node entries
# ---------------------------------------------------------------------------


class TestNarrationRecordsEveryNode:
    """`narrated()` is already the one place every sub-workflow node announces
    itself, so wrapping the record there means a graph cannot grow a node that
    forgets to record."""

    ATLAS = {"N2_generate_spec": {"ordinal": 5, "title": "draft", "goal": "g"}}

    def test_entering_a_node_records_it(self, tmp_path, tagged, capsys):
        from assemblyzero.workflows.narration import narrated

        wrapped = narrated(
            "N2_generate_spec", lambda s: {"ok": True}, self.ATLAS, 10,
            stage="spec",
        )
        assert wrapped({"repo_root": str(tmp_path)}) == {"ok": True}
        capsys.readouterr()
        records, _ = read_records(tmp_path)
        assert [r["event"] for r in records] == [EVENT_NODE_ENTER]
        assert records[0]["node"] == "N2_generate_spec"
        assert records[0]["ordinal"] == 5
        assert records[0]["stage"] == "spec"

    def test_a_node_still_runs_when_the_record_cannot_be_written(
        self, tmp_path, tagged, capsys
    ):
        """A diagnostic that can take a roll down is worse than a missing one."""
        from assemblyzero.workflows.narration import narrated

        wrapped = narrated(
            "N2_generate_spec", lambda s: {"ok": True}, self.ATLAS, 10,
            stage="spec",
        )
        assert wrapped({"repo_root": "\0not a path"}) == {"ok": True}
        capsys.readouterr()

    def test_a_wrap_with_no_stage_narrates_but_does_not_record(
        self, tmp_path, tagged, capsys
    ):
        from assemblyzero.workflows.narration import narrated

        wrapped = narrated(
            "N2_generate_spec", lambda s: {"ok": True}, self.ATLAS, 10
        )
        wrapped({"repo_root": str(tmp_path)})
        assert "NODE" in capsys.readouterr().out
        assert read_records(tmp_path) == ([], 0)

    def test_a_state_with_no_repo_root_records_nothing_rather_than_guessing(
        self, tmp_path, tagged, capsys
    ):
        from assemblyzero.workflows.narration import narrated

        wrapped = narrated(
            "N2_generate_spec", lambda s: {"ok": True}, self.ATLAS, 10,
            stage="spec",
        )
        wrapped({})
        capsys.readouterr()
        assert read_records(tmp_path) == ([], 0)


class TestTheGraphsPassTheirStage:
    """Pinned because a missing `stage=` is silent: the graph narrates exactly
    as before and simply records nothing, which is invisible until a report
    reads a source it does not have."""

    def test_both_narrating_graphs_name_themselves(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        spec = (
            root / "assemblyzero" / "workflows" / "implementation_spec"
            / "graph.py"
        ).read_text(encoding="utf-8")
        lld = (
            root / "assemblyzero" / "workflows" / "requirements" / "graph.py"
        ).read_text(encoding="utf-8")
        assert 'narrated(name, fn, ATLAS, TOTAL_STEPS, stage="spec")' in spec
        assert 'narrated(name, fn, ATLAS, TOTAL_STEPS, stage="lld")' in lld


class TestTheOrchestratorTerminal:
    def test_a_passed_run_reports_the_last_stage_that_ran(self):
        """`current_stage` is `done` on a success, which is a graph node and not
        a pipeline stage. Recording it would sort every passed run below every
        failed one."""
        from assemblyzero.workflows.orchestrator.graph import (
            _furthest_recorded_stage,
        )

        assert _furthest_recorded_stage(
            {"triage": {}, "lld": {}, "spec": {}, "impl": {}}
        ) == "impl"
        assert _furthest_recorded_stage({}) == ""

    def test_the_gate_key_reads_the_tag_first_and_the_classifier_second(self):
        from assemblyzero.core.gate_registry import halted
        from assemblyzero.workflows.orchestrator.graph import _terminal_gate_key

        tagged_message = halted("spec.review_cap", "Iteration cap: 3 rounds")
        assert _terminal_gate_key(tagged_message) == "spec.review_cap"
        assert _terminal_gate_key(
            "Coverage stagnant: 72.0% -> 70.0% (< 1% improvement)."
        ) == "impl.stagnation.coverage"
        assert _terminal_gate_key("") == KEY_FINALIZE
