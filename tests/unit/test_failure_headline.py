"""The headline names the failure CLASS, and the roster is counted (#2553).

During a live 503 storm on 2026-08-27 (`run-issue331-092913.log`) the surface
read:

    [LLM] provider=gemini model=3.1-pro duration=600.3s ERROR=All credentials
    failed via agy (Antigravity CLI):
      - oauth-primary: call budget of 600s exhausted riding 503/529 capacity
        storms retryable=false

The operator's reading was the obvious one: something is wrong with our
credentials. Nothing was. The credential connected on every attempt and the
model had no capacity -- a Google-side `MODEL_CAPACITY_EXHAUSTED`.

Two things had changed under the wording. #1605 removed API-key credentials,
so the roster loader appends only `type == "oauth"` entries, and the deployed
roster holds exactly one. "All credentials failed" was plural phrasing over a
denominator of one, naming the wrong failure class, at the moment an operator
is deciding whether their auth is broken.

**The riskiest part of this change is not the wording, it is what downstream
matches on it.** `TestTheClassificationIsUnchanged` is the load-bearing half:
the halt classifier and the capacity/quota split must land exactly where they
landed before.
"""

from __future__ import annotations

import pytest

from assemblyzero.core.errors import is_capacity_message
from assemblyzero.core.gemini_client import (
    GeminiErrorType,
    failure_headline,
    roster_phrase,
)
from assemblyzero.core.halt_node import classify_error

#: The per-credential detail line from the observed run, verbatim. It was the
#: accurate part and is kept.
OBSERVED_DETAIL = (
    "oauth-primary: call budget of 600s exhausted riding 503/529 "
    "capacity storms retryable=false"
)


def observed_message(names: list[str] | None = None) -> str:
    return (
        failure_headline(
            GeminiErrorType.CAPACITY_EXHAUSTED, names or ["oauth-primary"]
        )
        + "\n  - "
        + OBSERVED_DETAIL
    )


class TestItLeadsWithTheFailureClass:
    def test_a_capacity_storm_says_capacity(self) -> None:
        headline = failure_headline(
            GeminiErrorType.CAPACITY_EXHAUSTED, ["oauth-primary"]
        )

        assert headline.lower().startswith("provider capacity exhausted")

    def test_a_capacity_storm_never_says_credentials_failed(self) -> None:
        """The exact phrase the operator misread."""
        headline = failure_headline(
            GeminiErrorType.CAPACITY_EXHAUSTED, ["oauth-primary"]
        )

        assert "credentials failed" not in headline.lower()
        assert "all credentials" not in headline.lower()

    def test_it_says_outright_that_credentials_are_not_the_problem(
        self,
    ) -> None:
        for error_type in (
            GeminiErrorType.CAPACITY_EXHAUSTED,
            GeminiErrorType.QUOTA_EXHAUSTED,
        ):
            headline = failure_headline(error_type, ["oauth-primary"])
            assert "not a credential problem" in headline, error_type

    def test_quota_says_quota(self) -> None:
        headline = failure_headline(
            GeminiErrorType.QUOTA_EXHAUSTED, ["oauth-primary"]
        )

        assert headline.lower().startswith("quota exhausted")

    def test_an_unclassified_failure_claims_no_class(self) -> None:
        """Naming a class we did not establish would be the same defect."""
        headline = failure_headline(GeminiErrorType.UNKNOWN, ["oauth-primary"])

        assert "capacity" not in headline.lower()
        assert "quota" not in headline.lower()
        assert "credential problem" not in headline.lower()


class TestItCountsRatherThanPluralizing:
    def test_one_credential_is_named_not_pluralized(self) -> None:
        assert roster_phrase(["oauth-primary"]) == "oauth-primary"

    def test_the_headline_names_it(self) -> None:
        headline = failure_headline(
            GeminiErrorType.CAPACITY_EXHAUSTED, ["oauth-primary"]
        )

        assert "oauth-primary" in headline
        assert "all 1" not in headline.lower()

    @pytest.mark.parametrize("count", [2, 3, 4])
    def test_several_credentials_are_counted(self, count: int) -> None:
        names = [f"oauth-{n}" for n in range(count)]

        assert roster_phrase(names) == f"all {count} credentials"

    def test_an_empty_roster_says_so(self) -> None:
        assert roster_phrase([]) == "no credentials"


class TestTheClassificationIsUnchanged:
    """The load-bearing half. A reword that moves a halt verdict is a bug.

    `halt_node.classify_error` keys on `CAPACITY_MESSAGE_MARKERS` and on
    specific auth phrases, never on the old headline -- but that is a claim
    about today's classifier, and claims about code get asserted.
    """

    def test_the_observed_storm_still_classifies_as_capacity(self) -> None:
        assert classify_error(observed_message()) == "capacity_exhausted"

    def test_the_capacity_marker_survives_in_the_headline_alone(self) -> None:
        """Not leaning on the detail line to carry the signal."""
        headline = failure_headline(
            GeminiErrorType.CAPACITY_EXHAUSTED, ["oauth-primary"]
        )

        assert is_capacity_message(headline)

    def test_quota_still_classifies_as_quota(self) -> None:
        message = (
            failure_headline(GeminiErrorType.QUOTA_EXHAUSTED, ["oauth-primary"])
            + "\n  - oauth-primary: Quota exhausted"
        )

        assert classify_error(message) == "quota_exhausted"

    @pytest.mark.parametrize(
        "error_type",
        [
            GeminiErrorType.CAPACITY_EXHAUSTED,
            GeminiErrorType.QUOTA_EXHAUSTED,
            GeminiErrorType.UNKNOWN,
        ],
    )
    def test_no_headline_carries_an_auth_phrase(
        self, error_type: GeminiErrorType
    ) -> None:
        """A capacity storm must never be halted as 'check your credentials'.

        These are `classify_error`'s auth patterns, read from the classifier
        rather than restated from memory.
        """
        headline = failure_headline(error_type, ["oauth-primary"]).lower()

        for phrase in (
            "authentication failed", "authentication error", "invalid api key",
            "api_key_invalid", "permission_denied", "unauthenticated",
            "unauthorized",
        ):
            assert phrase not in headline, phrase

    def test_a_genuine_auth_failure_still_says_auth(self) -> None:
        """The reword must not make auth unreachable."""
        message = (
            failure_headline(GeminiErrorType.UNKNOWN, ["oauth-primary"])
            + "\n  - oauth-primary: authentication failed"
        )

        assert classify_error(message) == "auth"


class TestTheDetailLinesAreKept:
    def test_the_accurate_part_survives_verbatim(self) -> None:
        assert OBSERVED_DETAIL in observed_message()

    def test_the_whole_message_reads_as_an_outage(self) -> None:
        """The acceptance, stated as the operator's own question."""
        message = observed_message()

        assert "capacity" in message.lower()
        assert "503/529" in message
        assert "credentials failed" not in message.lower()
