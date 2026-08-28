"""Best-of-N drafts judged by the mechanical gates (#2573).

The acceptance fixture is `test_candidate_two_alone_clears_and_wins`: the
issue asks specifically for a case where candidate two alone clears the
gates, because that is the only arrangement that proves selection happens
on SCORE rather than on order.

Registry class 1 applies here — a zero needs a denominator. A candidate the
drafter never produced trips no gate that reads content, so "zero failures"
would make an empty draft the winner. `unusable` is that denominator.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from assemblyzero.workflows.requirements.best_of_n import (  # noqa: E402
    MAX_CANDIDATES,
    SERIAL,
    CandidateScore,
    clamp_candidates,
    render_score_table,
    score_candidate,
    select_winner,
)

DRAFT = "# LLD-1\n\n## 3. Requirements\n\n1. A thing\n"


def _gate(errors_by_call):
    """A fake GATE (not a fake drafter): returns the errors it is told to.

    The real validators are injected in production; here the injection point
    is used to drive scoring deterministically without standing up a
    workflow. The thing under test is the scoring and selection, not the
    validators -- those have their own suites.
    """
    calls = {"n": 0}

    def gate(state):
        calls["n"] += 1
        draft = state.get("current_draft", "")
        return {"validation_errors": list(errors_by_call.get(draft, []))}

    gate.calls = calls
    return gate


def _empty_gate(state):
    return {"validation_errors": []}


class TestScoring:
    def test_a_clean_candidate_clears(self):
        score = score_candidate(
            1, DRAFT, {}, mechanical=_empty_gate, test_plan=_empty_gate
        )
        assert score.clears is True
        assert score.failure_count == 0
        assert score.summary() == "clears every gate"

    def test_failures_are_counted_per_gate(self):
        mech = _gate({DRAFT: ["missing section 3", "bad title"]})
        plan = _gate({DRAFT: ["no REQ coverage"]})
        score = score_candidate(1, DRAFT, {}, mechanical=mech, test_plan=plan)
        assert score.failure_count == 3
        assert len(score.failures["mechanical"]) == 2
        assert len(score.failures["test-plan"]) == 1
        assert score.clears is False

    def test_an_empty_draft_is_unusable_not_perfect(self):
        """A zero needs a denominator: an empty draft trips no gate that
        reads content, so 'no failures' would otherwise make it the winner."""
        score = score_candidate(
            1, "   ", {}, mechanical=_empty_gate, test_plan=_empty_gate
        )
        assert score.unusable
        assert score.clears is False

    def test_a_gate_that_crashes_counts_against_the_candidate(self):
        """A candidate cannot win by breaking a validator."""
        def exploding(state):
            raise RuntimeError("boom")

        score = score_candidate(
            1, DRAFT, {}, mechanical=exploding, test_plan=_empty_gate
        )
        assert score.clears is False
        assert "gate raised RuntimeError" in score.failures["mechanical"][0]

    def test_candidates_are_scored_in_isolation(self):
        """Leaking accumulated validation state between candidates would
        score candidate 3 for candidate 2's failures."""
        seen = []

        def recording(state):
            seen.append(list(state.get("validation_errors") or []))
            return {"validation_errors": ["one"]}

        dirty = {"validation_errors": ["stale from a sibling"], "other": "kept"}
        score_candidate(1, DRAFT, dirty, mechanical=recording, test_plan=recording)
        assert seen == [[], []], "the probe state carried a sibling's errors"
        # The caller's state is not mutated.
        assert dirty["validation_errors"] == ["stale from a sibling"]

    def test_unrelated_state_reaches_the_gates(self):
        """Isolation must not become amnesia: the gates need the rest of the
        state (issue number, target repo) to judge anything."""
        seen = {}

        def recording(state):
            seen.update(state)
            return {"validation_errors": []}

        score_candidate(
            1, DRAFT, {"issue_number": 331, "target_repo": "/x"},
            mechanical=recording, test_plan=_empty_gate,
        )
        assert seen["issue_number"] == 331
        assert seen["current_draft"] == DRAFT


class TestSelection:
    def test_fewest_failures_wins(self):
        scores = [
            CandidateScore(1, "a", {"mechanical": ["x", "y"]}),
            CandidateScore(2, "b", {"mechanical": ["x"]}),
            CandidateScore(3, "c", {"mechanical": ["x", "y", "z"]}),
        ]
        assert select_winner(scores).index == 2

    def test_ties_go_to_the_earlier_candidate(self):
        """Deterministic, and deliberately NOT longest (rewards padding) or
        shortest (rewards elision -- #2559's exact pathology)."""
        scores = [
            CandidateScore(1, "short", {"mechanical": ["x"]}),
            CandidateScore(2, "a much longer draft", {"mechanical": ["y"]}),
        ]
        assert select_winner(scores).index == 1

    def test_an_unusable_candidate_never_wins(self):
        good = CandidateScore(2, "b", {"mechanical": ["x"]})
        bad = CandidateScore(1, "")
        bad.unusable = "drafter failed"
        assert select_winner([bad, good]).index == 2

    def test_all_unusable_returns_none(self):
        """A halt condition for the caller, not something to paper over with
        the least-bad empty draft."""
        scores = []
        for index in (1, 2):
            score = CandidateScore(index, "")
            score.unusable = "drafter failed"
            scores.append(score)
        assert select_winner(scores) is None


class TestTheAcceptanceFixture:
    """The issue's named case: candidate two alone clears the gates."""

    def test_candidate_two_alone_clears_and_wins(self):
        one = "# LLD-1\n\n## 3. Requirements\n\n1. Only a bit\n"
        two = "# LLD-1\n\n## 3. Requirements\n\n1. Complete\n\n## 10.1\n\n(REQ-1)\n"
        three = "# LLD-1\n\n## 3. Requirements\n\n1. Also incomplete\n"

        mech = _gate({
            one: ["Section 10.1 missing"],
            three: ["Section 10.1 missing", "no REQ-N coverage"],
        })
        plan = _gate({
            one: ["no test scenarios"],
            three: ["no test scenarios"],
        })

        scores = [
            score_candidate(index, draft, {}, mechanical=mech, test_plan=plan)
            for index, draft in enumerate((one, two, three), start=1)
        ]

        assert scores[0].failure_count == 2
        assert scores[1].clears is True
        assert scores[2].failure_count == 3

        winner = select_winner(scores)
        assert winner.index == 2
        assert winner.draft == two

        table = render_score_table(scores, winner.index)
        assert "WINNER candidate 2" in table
        assert "clears every gate" in table
        assert "candidate 1: 2 failure(s)" in table
        assert "candidate 3: 3 failure(s)" in table


class TestClamping:
    def test_the_default_is_the_serial_path(self):
        assert clamp_candidates(1) == SERIAL
        assert clamp_candidates(None) == SERIAL
        assert clamp_candidates("nonsense") == SERIAL

    def test_zero_and_negative_fall_back_to_serial(self):
        assert clamp_candidates(0) == SERIAL
        assert clamp_candidates(-5) == SERIAL

    def test_a_typo_cannot_cost_thirty_drafter_calls(self):
        """The flag is one keystroke from 3, and every candidate is a real
        drafter call on a live roll."""
        assert clamp_candidates(30) == MAX_CANDIDATES
        assert clamp_candidates(3) == 3


class TestTheNodeIsOptIn:
    """The serial path must remain byte-identical by default."""

    def test_state_defaults_to_the_serial_path(self):
        from assemblyzero.workflows.requirements.state import (
            create_initial_state,
        )

        state = create_initial_state(
            workflow_type="lld", assemblyzero_root="/a", target_repo="/b",
        )
        assert state["config_draft_candidates"] == SERIAL

    def test_the_flag_reaches_state(self):
        from assemblyzero.workflows.requirements.state import (
            create_initial_state,
        )

        state = create_initial_state(
            workflow_type="lld", assemblyzero_root="/a", target_repo="/b",
            draft_candidates=3,
        )
        assert state["config_draft_candidates"] == 3

    def test_the_cli_declares_the_flag_with_a_serial_default(self):
        import run_requirements_workflow as cli

        parser = cli.build_parser() if hasattr(cli, "build_parser") else None
        if parser is None:
            source = (TOOLS / "run_requirements_workflow.py").read_text(
                encoding="utf-8"
            )
            assert '"--draft-candidates"' in source
            assert "default=1" in source
            return
        args = parser.parse_args(["--issue", "1"])
        assert args.draft_candidates == 1


def test_render_score_table_marks_exactly_one_winner():
    scores = [
        CandidateScore(1, "a", {"mechanical": ["x"]}),
        CandidateScore(2, "b"),
    ]
    table = render_score_table(scores, 2)
    assert table.count("WINNER") == 1


@pytest.mark.parametrize("count", [2, 3, MAX_CANDIDATES])
def test_scoring_is_stable_across_repeat_runs(count):
    """Identical candidates must produce an identical winner every time; a
    roll that picks differently on replay is not replayable."""
    drafts = [f"# LLD-1\n\n## 3. Requirements\n\n{n}. thing\n" for n in range(count)]
    errors = {draft: ["e"] * (index + 1) for index, draft in enumerate(drafts)}
    first = select_winner([
        score_candidate(i, d, {}, mechanical=_gate(errors), test_plan=_empty_gate)
        for i, d in enumerate(drafts, start=1)
    ])
    second = select_winner([
        score_candidate(i, d, {}, mechanical=_gate(errors), test_plan=_empty_gate)
        for i, d in enumerate(drafts, start=1)
    ])
    assert first.index == second.index == 1
