"""review_progress under standard 0034 (#3585).

Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md.
"""
from __future__ import annotations

import pytest

from assemblyzero.workflows.implementation_spec import review_progress as rp


@pytest.mark.parametrize("bad", ["three", None, "", object()])
def test_73_a_max_iterations_that_is_not_an_integer_raises(bad):
    """It used to stand in a base cap of 3, so a misconfigured run reviewed
    to a ceiling nobody set."""
    with pytest.raises(ValueError, match="max_iterations"):
        rp.hard_ceiling(bad)


@pytest.mark.parametrize("value, ceiling", [(3, 9), ("4", 12), (0, 0)])
def test_an_integer_max_iterations_sets_the_ceiling(value, ceiling):
    """Kept: an int, or a string of one, is three times the base."""
    assert rp.hard_ceiling(value) == ceiling


def test_157_revise_with_empty_feedback_stops():
    """Compliant, pinned: review_spec turns this into an error_message."""
    decision = rp.decide(
        review_iteration=0, max_iterations=3, current_feedback="", prior_feedbacks=[],
    )
    assert decision.should_continue is False
    assert decision.exit_name == rp.EXIT_EMPTY
