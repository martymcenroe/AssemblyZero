"""Best-of-N drafting under standard 0034 (#3585).

Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md (base ``79e18ad1``), for
``assemblyzero/workflows/requirements/best_of_n.py``. A gate that crashes on a
candidate is a gate that did not judge it, so the candidate could not be
scored: it alerts the operator and raises, where it used to count as one
failure and the candidate could still win. A candidate count that is not a
number raises naming it, where it silently meant one candidate. Every
candidate unusable is still the caller's halt (compliant, pinned).
"""
from __future__ import annotations

import inspect

import pytest

from assemblyzero.workflows.requirements import best_of_n as bon


def _passes(_state):
    return {"validation_errors": [], "test_plan_errors": []}


def _crashes(_state):
    raise RuntimeError("validator bug")


class TestScoring:
    def test_130_a_gate_that_crashes_alerts_and_raises(self, operator_alerts):
        state = {"issue_number": 42, "target_repo": "/repo"}

        with pytest.raises(RuntimeError, match="validator bug"):
            bon.score_candidate(2, "# 42 - Feature\n", state,
                                mechanical=_crashes, test_plan=_passes)
        assert len(operator_alerts) == 1
        alert = operator_alerts[0]
        assert "candidate 2" in alert["what"]
        assert "mechanical" in alert["what"]
        assert "RuntimeError: validator bug" in alert["cause"]
        assert alert["issue"] == 42
        assert alert["repo"] == "/repo"

    def test_a_gate_that_runs_and_finds_failures_scores_them(self, operator_alerts):
        """Kept: failures a gate reports are the score, not a crash."""
        def fails(_state):
            return {"validation_errors": ["Section 2.1 missing"]}

        score = bon.score_candidate(1, "draft", {}, mechanical=fails, test_plan=_passes)
        assert score.failures == {"mechanical": ["Section 2.1 missing"]}
        assert operator_alerts == []

    def test_131_180_no_fail_open_tag_remains(self):
        assert "fail-open" not in inspect.getsource(bon)


class TestSelection:
    def test_156_every_candidate_unusable_is_none_for_the_caller_to_halt(self):
        """Compliant, pinned: generate_draft turns None into error_message,
        which its router sends to HALT."""
        scores = [bon.CandidateScore(index=i, draft="", unusable="empty") for i in (1, 2)]
        assert bon.select_winner(scores) is None


class TestTheCandidateCount:
    @pytest.mark.parametrize("bad", ["three", None, "2.5", object()])
    def test_179_a_count_that_is_not_a_number_raises_naming_it(self, bad):
        with pytest.raises(ValueError, match="draft candidate count") as raised:
            bon.clamp_candidates(bad)
        assert repr(bad) in str(raised.value)

    @pytest.mark.parametrize(("given", "used"), [(3, 3), ("2", 2), (0, 1), (99, 5)])
    def test_a_number_is_still_clamped_to_the_safe_range(self, given, used):
        """Kept: the clamp is the documented wallet guard."""
        assert bon.clamp_candidates(given) == used
