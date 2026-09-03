"""Every cap keeps the work, and the report can count that (#2725).

Under the routing policy a spending limit becomes the only thing allowed to end
a run on the model's own path. A cap that fires and leaves no draft, no list of
what was still being asked for, and no way back in has turned a limit into a
loss.

Two halves here, and the measurement that separated them is worth stating
because the issue was filed on the other reading. The caps DO write their
bundle: counted on boostgauge 2026-09-03, every cap-ended run since 2026-08-28
left one, 6 of 6, and the four that did not are all dated on or before the day
`build_halt_evidence` landed. What was wrong was the counting -- the report
scanned `docs/lineage` alone and found 8 of the 39 bundles in the repo -- and
what the bundle held: no gate key, no outstanding items, no resume line.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from assemblyzero.core.halt_evidence import (
    build_halt_evidence,
    gate_key_for,
    outstanding_items,
    render_halt_evidence_md,
    write_halt_evidence,
)
from assemblyzero.core.halt_node import _halt_bundle_dirname
from assemblyzero.speedrun.factory_report import (
    HALT_BUNDLE_SUBDIRS,
    RunLogFacts,
    attribute_bundles,
    halt_bundle_roots,
)

#: The three assertions run-issue4-183941's ninth review round was still
#: demanding when the hard ceiling stopped it. Nothing in that run's bundle
#: named them, which is the shape #2725's acceptance calls out.
RUN_11_FEEDBACK = "\n".join([
    "The spec's test mapping still disagrees with the LLD in three places.",
    "- test_req_090_live_process_count must assert within 1, not exactly",
    "- test_req_110_live_conpty_count must assert within 1, not exactly",
    "- test_req_130_live_handle_count must assert within 1%, not exactly",
])


def _cap_state(**kwargs) -> dict:
    base = {
        "issue_number": 4,
        "repo_root": "",
        "audit_dir": "",
        "review_iteration": 9,
        "max_iterations": 3,
        "review_feedback": RUN_11_FEEDBACK,
    }
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# The acceptance: run 11's shape names its three outstanding assertions
# ---------------------------------------------------------------------------


class TestTheCeilingBundleNamesWhatWasOutstanding:
    def test_the_three_assertions_are_in_the_bundle(self):
        evidence = build_halt_evidence(
            _cap_state(), "implementation_spec",
            stage="N5_review_iter9",
            error_message=(
                "Iteration cap: 3 review rounds ended REVISE, so the run "
                "stopped rather than spend another round on the same objection."
            ),
        )
        assert len(evidence["outstanding"]) == 3
        assert all("within 1" in item for item in evidence["outstanding"])

    def test_the_bundle_names_the_gate_that_fired(self):
        evidence = build_halt_evidence(
            _cap_state(), "implementation_spec", stage="N5_review_iter9",
            error_message=(
                "Iteration cap: 3 review rounds ended REVISE, so the run "
                "stopped rather than spend another round on the same objection."
            ),
        )
        assert evidence["gate_key"] == "spec.review_cap"

    def test_the_bundle_carries_a_way_back_in(self):
        evidence = build_halt_evidence(
            _cap_state(), "implementation_spec", stage="N5_review_iter9",
            error_message="Iteration cap: 3 review rounds ended REVISE",
        )
        assert evidence["resume_command"]
        assert "4" in evidence["resume_command"]

    def test_the_document_puts_all_three_above_the_inventory(self, tmp_path):
        """A reader arriving at a cap needs the gate, the outstanding work and
        the resume line before a table of file hashes."""
        evidence = build_halt_evidence(
            _cap_state(), "implementation_spec", stage="N5_review_iter9",
            error_message="Iteration cap: 3 review rounds ended REVISE",
        )
        rendered = render_halt_evidence_md(evidence)
        assert "Still outstanding when the run stopped (3)" in rendered
        assert "## Resume" in rendered
        assert "Gate: `spec.review_cap`" in rendered
        _, md_path = write_halt_evidence(evidence, tmp_path)
        assert "within 1%" in md_path.read_text(encoding="utf-8")


class TestOutstandingItems:
    def test_a_bulleted_verdict_becomes_one_item_per_bullet(self):
        assert len(outstanding_items(_cap_state())) == 3

    def test_an_unbulleted_verdict_is_kept_whole_rather_than_dropped(self):
        state = _cap_state(review_feedback="The spec is not implementable yet.")
        assert outstanding_items(state) == ["The spec is not implementable yet."]

    def test_the_history_is_used_when_the_last_round_left_nothing(self):
        """A cap can fire on a round whose feedback never landed on the state,
        and an empty list would read as 'nothing was outstanding'."""
        state = _cap_state(
            review_feedback="",
            review_feedback_history=["- earlier round", "- last round"],
        )
        assert outstanding_items(state) == ["last round"]

    def test_no_feedback_at_all_is_an_empty_list_not_an_invention(self):
        state = _cap_state(review_feedback="", review_feedback_history=[])
        assert outstanding_items(state) == []

    def test_completeness_issues_are_not_folded_in(self):
        """Two different judges with two different remedies. The mechanical
        validator's findings already have their own field, and merging them
        would make a review cap look like a validation failure."""
        state = _cap_state(
            review_feedback="", review_feedback_history=[],
            completeness_issues=["section 10.1 is a pointer, not tests"],
        )
        evidence = build_halt_evidence(
            state, "implementation_spec", stage="N5", error_message="cap"
        )
        assert evidence["outstanding"] == []
        assert evidence["events"]["completeness_issues"] == [
            "section 10.1 is a pointer, not tests"
        ]


class TestGateKey:
    @pytest.mark.parametrize(
        "message,expected",
        [
            ("Iteration cap: 3 review rounds ended REVISE", "spec.review_cap"),
            (
                "Coverage stagnant: 72.0% -> 70.0% (< 1% improvement). "
                "Halting to prevent token waste.",
                "impl.stagnation.coverage",
            ),
            ("", ""),
        ],
    )
    def test_the_classifier_is_the_bridge_until_the_sites_are_tagged(
        self, message, expected
    ):
        assert gate_key_for(message) == expected

    def test_a_tagged_site_beats_the_classifier(self):
        """#2719's `halted()` appends the key. Where it is present it is
        authoritative, so a retagged site stops depending on prose."""
        from assemblyzero.core.gate_registry import halted

        assert gate_key_for(
            halted("spec.review_ceiling", "Iteration cap: 3 review rounds")
        ) == "spec.review_ceiling"


# ---------------------------------------------------------------------------
# Every cap path reaches the writer
# ---------------------------------------------------------------------------


class TestEveryGraphRoutesItsCapsToTheWriter:
    """The bundle is written by `create_halt_node`, so the claim "every cap
    writes a bundle" reduces to "every graph's terminal node is that one".
    Pinned as a structure rather than a behaviour because a fourth graph, or a
    graph that grew its own halt node, would otherwise pass silently.
    """

    @pytest.mark.parametrize(
        "module,name",
        [
            ("assemblyzero.workflows.requirements.graph", "lld"),
            ("assemblyzero.workflows.implementation_spec.graph", "spec"),
            ("assemblyzero.workflows.testing.graph", "impl"),
            ("assemblyzero.workflows.orchestrator.graph", "orchestrator"),
        ],
    )
    def test_the_graph_builds_its_terminal_node_with_create_halt_node(
        self, module, name
    ):
        import importlib
        from pathlib import Path

        source = Path(
            importlib.import_module(module).__file__
        ).read_text(encoding="utf-8")
        assert "create_halt_node(" in source, (
            f"the {name} graph no longer builds its terminal node with "
            f"create_halt_node, so its caps may write no evidence bundle"
        )


class TestTheSharedCopyIsScopedToOneHalt:
    """`write_halt_evidence` writes fixed filenames, and the state directory is
    global across every repo the fleet has rolled. Measured 2026-09-03: 39
    bundles in boostgauge, exactly 1 in the state directory -- every halt of
    every repo had been overwriting the same file."""

    def test_two_workflows_of_one_run_do_not_collide(self, monkeypatch):
        monkeypatch.setenv("SPEEDRUN_RUN_TAG", "run-issue4-183941")
        state = {"issue_number": 4}
        assert _halt_bundle_dirname("implementation_spec", state) != (
            _halt_bundle_dirname("orchestrator", state)
        )

    def test_two_runs_of_one_workflow_do_not_collide(self, monkeypatch):
        state = {"issue_number": 4}
        monkeypatch.setenv("SPEEDRUN_RUN_TAG", "run-issue4-183941")
        first = _halt_bundle_dirname("implementation_spec", state)
        monkeypatch.setenv("SPEEDRUN_RUN_TAG", "run-issue4-192453")
        assert _halt_bundle_dirname("implementation_spec", state) != first

    def test_two_issues_do_not_collide(self, monkeypatch):
        monkeypatch.setenv("SPEEDRUN_RUN_TAG", "run-issue4-183941")
        assert _halt_bundle_dirname(
            "implementation_spec", {"issue_number": 4}
        ) != _halt_bundle_dirname(
            "implementation_spec", {"issue_number": 331}
        )

    def test_outside_a_roll_the_slot_is_named_rather_than_invented(
        self, monkeypatch
    ):
        monkeypatch.delenv("SPEEDRUN_RUN_TAG", raising=False)
        assert _halt_bundle_dirname("testing", {"issue_number": 7}) == (
            "halt-testing-7-norun"
        )

    def test_a_workflow_name_with_separators_cannot_escape_the_directory(
        self, monkeypatch
    ):
        monkeypatch.delenv("SPEEDRUN_RUN_TAG", raising=False)
        name = _halt_bundle_dirname("../../etc", {"issue_number": 1})
        assert "/" not in name and "\\" not in name and ".." not in name


# ---------------------------------------------------------------------------
# The report can find and attribute the bundles
# ---------------------------------------------------------------------------


class TestDiscoveryLooksWhereBundlesActuallyLand:
    def test_the_two_directories_a_reset_moves_them_to_are_searched(self):
        """`docs/lineage` is where the halt writes; the other two are where the
        bundle is MOVED. Scanning only the first found 8 of 39 on boostgauge."""
        assert ("docs", "lineage") in HALT_BUNDLE_SUBDIRS
        assert ("data", "speedrun", "reset-artifacts") in HALT_BUNDLE_SUBDIRS
        assert ("data", "speedrun", "archives") in HALT_BUNDLE_SUBDIRS

    def test_the_roots_are_under_the_repo(self, tmp_path):
        roots = halt_bundle_roots(tmp_path)
        assert len(roots) == len(HALT_BUNDLE_SUBDIRS)
        assert all(str(r).startswith(str(tmp_path)) for r in roots)


def _run(tag: str, issue: int, start: datetime, minutes: int) -> RunLogFacts:
    return RunLogFacts(
        run_id=tag, issue=issue, path="", mtime=start.strftime("%Y-%m-%d %H:%M:%S"),
        started=start, ended=start + timedelta(minutes=minutes),
    )


def _bundle(issue: int, when: datetime) -> dict:
    return {"issue": issue, "halted_at": when.isoformat()}


BASE = datetime(2026, 9, 2, 23, 0, tzinfo=timezone.utc)


class TestAttribution:
    def test_a_bundle_lands_against_the_run_that_was_running(self):
        runs = [_run("run-issue4-a", 4, BASE, 20)]
        per_run, unplaced = attribute_bundles(
            [_bundle(4, BASE + timedelta(minutes=5))], runs
        )
        assert per_run == {"run-issue4-a": 1}
        assert unplaced == 0

    def test_another_issues_run_does_not_claim_it(self):
        """Rolls of different issues run concurrently and their log windows
        overlap freely, so time alone attributes a halt to the wrong run. On
        boostgauge, matching on time alone left 31 of 39 bundles ambiguous."""
        runs = [
            _run("run-issue331-a", 331, BASE, 60),
            _run("run-issue4-a", 4, BASE + timedelta(minutes=10), 20),
        ]
        per_run, unplaced = attribute_bundles(
            [_bundle(4, BASE + timedelta(minutes=15))], runs
        )
        assert per_run == {"run-issue4-a": 1}
        assert unplaced == 0

    def test_two_runs_of_one_issue_overlapping_leaves_it_unplaced(self):
        """Putting a real halt against the wrong run's name is worse than
        admitting the join is ambiguous."""
        runs = [
            _run("run-issue4-a", 4, BASE, 60),
            _run("run-issue4-b", 4, BASE + timedelta(minutes=5), 30),
        ]
        per_run, unplaced = attribute_bundles(
            [_bundle(4, BASE + timedelta(minutes=10))], runs
        )
        assert per_run == {}
        assert unplaced == 1

    def test_a_bundle_with_no_issue_is_counted_not_dropped(self):
        per_run, unplaced = attribute_bundles(
            [{"halted_at": BASE.isoformat()}], [_run("run-issue4-a", 4, BASE, 20)]
        )
        assert per_run == {}
        assert unplaced == 1

    def test_a_bundle_with_an_unreadable_stamp_is_counted_not_dropped(self):
        per_run, unplaced = attribute_bundles(
            [{"issue": 4, "halted_at": "not a time"}],
            [_run("run-issue4-a", 4, BASE, 20)],
        )
        assert per_run == {}
        assert unplaced == 1

    def test_a_naive_stamp_is_read_as_utc_rather_than_refused(self):
        naive = (BASE + timedelta(minutes=5)).replace(tzinfo=None)
        per_run, unplaced = attribute_bundles(
            [{"issue": 4, "halted_at": naive.isoformat()}],
            [_run("run-issue4-a", 4, BASE, 20)],
        )
        assert per_run == {"run-issue4-a": 1}
        assert unplaced == 0

    def test_a_run_that_could_not_be_dated_takes_part_in_no_join(self):
        runs = [RunLogFacts(run_id="r", issue=4, path="", mtime="")]
        per_run, unplaced = attribute_bundles([_bundle(4, BASE)], runs)
        assert per_run == {}
        assert unplaced == 1
