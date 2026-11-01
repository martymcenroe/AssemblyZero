"""Unit tests for assemblyzero.core.retry — with_retry + RetryConfig.

Issue #542: Unified retry contract.
"""

from unittest.mock import patch

import pytest

from assemblyzero.core.errors import (
    BillingError,
    RateLimitError,
    ServerError,
    TimeoutError_,
)
from assemblyzero.core.retry import RetryConfig, with_retry


class TestWithRetry:
    """Test the with_retry function."""

    def test_succeeds_immediately(self):
        """No errors — returns on first call."""
        result = with_retry(lambda: 42)
        assert result == 42

    def test_succeeds_after_transient(self):
        """ServerError on first call, success on second."""
        calls = {"count": 0}

        def fn():
            calls["count"] += 1
            if calls["count"] == 1:
                raise ServerError("temporary glitch")
            return "ok"

        with patch("assemblyzero.core.retry.time.sleep"):
            result = with_retry(fn, RetryConfig(max_retries=3, base_delay=0.01))

        assert result == "ok"
        assert calls["count"] == 2

    def test_halts_on_billing(self):
        """BillingError raises immediately — 0 retries."""
        calls = {"count": 0}

        def fn():
            calls["count"] += 1
            raise BillingError("credit balance is too low")

        with pytest.raises(BillingError, match="credit balance"):
            with_retry(fn, RetryConfig(max_retries=5))

        assert calls["count"] == 1  # Only called once

    def test_halts_on_non_retryable(self):
        """Any non-retryable error raises immediately."""
        from assemblyzero.core.errors import AuthenticationError

        def fn():
            raise AuthenticationError("bad key")

        with pytest.raises(AuthenticationError):
            with_retry(fn)

    @patch("assemblyzero.core.retry.time.sleep")
    def test_respects_retry_after(self, mock_sleep):
        """RateLimitError with retry_after=5 → delay >= 5s."""
        calls = {"count": 0}

        def fn():
            calls["count"] += 1
            if calls["count"] == 1:
                raise RateLimitError("rate limited", retry_after=5.0)
            return "ok"

        result = with_retry(fn, RetryConfig(max_retries=3, base_delay=1.0))
        assert result == "ok"

        # Verify sleep was called with the retry_after value
        mock_sleep.assert_called_once()
        delay = mock_sleep.call_args[0][0]
        assert delay == 5.0

    @patch("assemblyzero.core.retry.time.sleep")
    def test_max_retries_exhausted(self, mock_sleep):
        """Raises after max_retries transient failures."""
        calls = {"count": 0}

        def fn():
            calls["count"] += 1
            raise ServerError("always fails")

        with pytest.raises(ServerError, match="always fails"):
            with_retry(fn, RetryConfig(max_retries=3, base_delay=0.01))

        # 1 initial + 3 retries = 4 calls
        assert calls["count"] == 4

    @patch("assemblyzero.core.retry.time.sleep")
    def test_timeout_max_one_retry(self, mock_sleep):
        """TimeoutError_ gets max 1 retry regardless of config."""
        calls = {"count": 0}

        def fn():
            calls["count"] += 1
            raise TimeoutError_("timed out")

        with pytest.raises(TimeoutError_):
            with_retry(fn, RetryConfig(max_retries=5, base_delay=0.01))

        # 1 initial + 1 retry = 2 calls (not 6)
        assert calls["count"] == 2

    @patch("assemblyzero.core.retry.time.sleep")
    def test_exponential_backoff(self, mock_sleep):
        """Verify delays increase exponentially."""
        calls = {"count": 0}

        def fn():
            calls["count"] += 1
            if calls["count"] <= 3:
                raise ServerError("transient")
            return "ok"

        result = with_retry(fn, RetryConfig(max_retries=3, base_delay=1.0, jitter=0.0))
        assert result == "ok"

        # With jitter=0 and base=1: delays should be 1.0, 2.0, 4.0
        delays = [call[0][0] for call in mock_sleep.call_args_list]
        assert len(delays) == 3
        assert delays[0] == pytest.approx(1.0, abs=0.01)
        assert delays[1] == pytest.approx(2.0, abs=0.01)
        assert delays[2] == pytest.approx(4.0, abs=0.01)
