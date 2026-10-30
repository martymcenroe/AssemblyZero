"""retry.py under standard 0034, one test per sweep site (#3789).

``with_retry`` already raised every failure to its caller; what it did not do
is say so where the operator looks. A non-retryable error and a timeout that
was already retried went to stdout, and running out of attempts said nothing.
Each is now an ERROR line on stderr, naming the call, the error and the
attempts, and the error is still raised. Line numbers in the names are ledger
0908's, at its base ``79e18ad1``.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from assemblyzero.core.errors import AuthenticationError, ServerError, TimeoutError_
from assemblyzero.core.retry import RetryConfig, with_retry


def _always(exc: Exception):
    def call_the_api():
        raise exc

    return call_the_api


class TestEveryGivingUpIsLoud:
    def test_66_a_non_retryable_error_is_an_error_line_on_stderr(self, capsys):
        with pytest.raises(AuthenticationError):
            with_retry(_always(AuthenticationError("bad key")))

        out, err = capsys.readouterr()
        assert "ERROR [RETRY]" in err
        assert "AuthenticationError: bad key" in err
        assert "call_the_api" in err
        assert "bad key" not in out

    @patch("assemblyzero.core.retry.time.sleep")
    def test_73_a_timeout_already_retried_is_an_error_line_on_stderr(self, _sleep, capsys):
        with pytest.raises(TimeoutError_):
            with_retry(_always(TimeoutError_("timed out")), RetryConfig(max_retries=5))

        out, err = capsys.readouterr()
        assert "ERROR [RETRY]" in err
        assert "already retried once" in err
        assert "TimeoutError_: timed out" in err
        assert "giving up" not in out

    @patch("assemblyzero.core.retry.time.sleep")
    def test_95_running_out_of_attempts_is_an_error_line_on_stderr(self, _sleep, capsys):
        with pytest.raises(ServerError, match="always fails"):
            with_retry(_always(ServerError("always fails")), RetryConfig(max_retries=3))

        err = capsys.readouterr().err
        assert "ERROR [RETRY]" in err
        assert "4 attempts" in err
        assert "ServerError: always fails" in err

    @patch("assemblyzero.core.retry.time.sleep")
    def test_a_retry_that_recovers_writes_no_error_line(self, _sleep, capsys):
        """Kept: a transient failure that the next attempt gets past is not a
        failure of the call."""
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] == 1:
                raise ServerError("blip")
            return "ok"

        assert with_retry(flaky, RetryConfig(max_retries=3)) == "ok"
        assert "ERROR" not in capsys.readouterr().err
