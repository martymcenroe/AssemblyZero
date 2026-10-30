"""pr_poll.py under standard 0034, one test per sweep site (#3785).

``poll_verdict`` read any payload it could not classify as "wait": the ``{}``
a failed or unparsed API call leaves, and GitHub's own error object. A poller
then sat out its whole bound on an answer it never had, and ended as a
timeout with the cause gone. A payload that is not a pull request's state now
raises ValueError naming it. A real PR whose ``mergeable_state`` is not yet
computed still waits. Line numbers in the names are ledger 0908's, at its base
``79e18ad1``.
"""
from __future__ import annotations

import pytest

from assemblyzero.core.pr_poll import VERDICT_WAIT, poll_verdict


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"message": "Not Found", "documentation_url": "https://docs.github.com/rest"},
        {"mergeable_state": None, "merged": None, "state": None},
        {"mergeable_state": "clean", "merged": "false", "state": "open"},
        {"mergeable_state": "clean", "merged": False, "state": "draft"},
    ],
)
def test_86_a_payload_that_is_not_a_pr_state_raises(payload):
    with pytest.raises(ValueError, match="not a pull request's state") as raised:
        poll_verdict(payload)
    assert repr(payload)[:40] in str(raised.value)


def test_86_a_payload_that_is_not_an_object_raises():
    with pytest.raises(ValueError, match="not a pull request's state"):
        poll_verdict(["behind"])  # type: ignore[arg-type]


@pytest.mark.parametrize("mergeable", ["unknown", None, "blocked", "has_hooks", "draft"])
def test_an_open_pr_still_being_computed_waits(mergeable):
    """Kept: GitHub computes mergeable_state lazily, and blocked resolves on
    its own (#1399); those are answers, not failures."""
    assert poll_verdict(
        {"mergeable_state": mergeable, "merged": False, "state": "open"}
    ) == VERDICT_WAIT
