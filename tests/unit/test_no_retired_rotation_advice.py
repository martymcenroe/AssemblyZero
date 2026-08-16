"""No operator-facing message sends a human to the retired rotation file (#2441).

The rotation-state file belonged to the API-key credential rotation that the
agy migration retired (#1595/#1605), so on a current machine it is stale or
absent. Two messages still named it, and both are read at the moment something
has already failed -- the worst moment to be sent somewhere useless.

These tests cover the MESSAGES, not the constant. `ROTATION_STATE_FILE` itself
survives because `GeminiClient` and `preflight` still read it, and a file that
is absent reads as "nothing exhausted", which is the harmless answer.
"""
from __future__ import annotations

import pytest

from assemblyzero.core.gemini_client import CredentialPoolExhaustedException
from assemblyzero.core.recovery_plan import _build_recommendation

#: Every branch of the recommendation, plus an unknown type for the else.
ERROR_TYPES = [
    "capacity_exhausted",
    "quota_exhausted",
    "stagnation",
    "budget",
    "auth",
    "requirements_conflict",
    "something_nobody_has_classified_yet",
]

#: The dead file, in the spellings a message could plausibly use.
DEAD_REFERENCES = ("rotation-state", "rotation_state", "gemini-rotation")


@pytest.mark.parametrize("error_type", ERROR_TYPES)
def test_no_recommendation_names_the_retired_rotation_file(error_type):
    advice = _build_recommendation(error_type, "some error", "requirements")
    lowered = advice.lower()
    for dead in DEAD_REFERENCES:
        assert dead not in lowered, (
            f"{error_type} advice sends the operator to a file the agy "
            f"migration retired: {advice!r}"
        )


def test_the_quota_advice_names_something_the_operator_can_do():
    """Naming no file is necessary but not sufficient -- the replacement has to
    be actionable under the transport that actually runs."""
    advice = _build_recommendation("quota_exhausted", "429", "requirements")
    assert "--reviewer claude:opus" in advice, (
        "the reviewer swap is the one action that works while the "
        "subscription is out of quota"
    )
    assert "credentials are quota-exhausted" not in advice, (
        "there are no credentials to rotate under the subscription transport"
    )


def test_the_resume_message_reports_a_reset_when_one_is_known():
    exc = CredentialPoolExhaustedException("dry", earliest_reset="2026-08-16T18:00:00Z")
    assert "2026-08-16T18:00:00Z" in exc.get_resume_message()


def test_the_resume_message_fallback_names_no_retired_file():
    exc = CredentialPoolExhaustedException("dry")
    message = exc.get_resume_message().lower()
    for dead in DEAD_REFERENCES:
        assert dead not in message, (
            f"the no-reset-known fallback still names the retired file: {message!r}"
        )
    assert message.strip(), "saying nothing is not an improvement on saying the wrong thing"
