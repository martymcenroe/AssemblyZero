"""errors.py under standard 0034, the one sweep site (#3774).

A rate limit's ``retry-after`` header that is not a number of seconds was
dropped in silence, and the caller backed off on its own schedule with no
word that the provider had asked for something else. The rate limit is still
classified and still raised; the unreadable header is now an ERROR line
naming its value. Line numbers in the names are ledger 0908's, at its base
``79e18ad1``.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from assemblyzero.core.errors import RateLimitError, classify_anthropic_error


def _rate_limit(headers: dict):
    import anthropic

    response = MagicMock()
    response.status_code = 429
    response.headers = headers
    return anthropic.RateLimitError(
        message="Rate limited", response=response,
        body={"error": {"message": "Rate limited"}},
    )


class TestTheRetryAfterHeader:
    def test_365_an_unreadable_retry_after_is_an_error_line(self, capsys):
        result = classify_anthropic_error(_rate_limit({"retry-after": "soon"}))

        assert isinstance(result, RateLimitError)
        assert result.retry_after is None
        err = capsys.readouterr().err
        assert "ERROR" in err
        assert "'soon'" in err
        assert "backoff" in err

    def test_a_numeric_retry_after_is_read_and_quiet(self, capsys):
        """Kept: seconds are the hint, and reading them is not news."""
        result = classify_anthropic_error(_rate_limit({"retry-after": "10"}))

        assert result.retry_after == 10.0
        assert "ERROR" not in capsys.readouterr().err

    def test_no_retry_after_is_no_hint_and_quiet(self, capsys):
        """Kept: a 429 without the header gives no hint, which is an answer."""
        result = classify_anthropic_error(_rate_limit({}))

        assert result.retry_after is None
        assert "ERROR" not in capsys.readouterr().err
