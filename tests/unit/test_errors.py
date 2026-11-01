"""Unit tests for assemblyzero.core.errors — exception hierarchy + classifiers.

Issue #542: Unified error handling.
"""

import subprocess

from assemblyzero.core.errors import (
    APIError,
    AuthenticationError,
    BillingError,
    CLINotFoundError,
    CapacityError,
    NotFoundError,
    RateLimitError,
    ServerError,
    TimeoutError_,
    classify_http_status,
    classify_subprocess_error,
)


class TestExceptionHierarchy:
    """Test exception attributes and inheritance."""

    def test_billing_error_not_retryable(self):
        err = BillingError("credit balance is too low", provider="anthropic")
        assert err.retryable is False
        assert err.status_code == 402
        assert err.provider == "anthropic"
        assert isinstance(err, APIError)

    def test_rate_limit_retryable(self):
        err = RateLimitError("too many requests", provider="anthropic", retry_after=5.0)
        assert err.retryable is True
        assert err.status_code == 429
        assert err.retry_after == 5.0

    def test_auth_error_not_retryable(self):
        err = AuthenticationError("bad key", provider="anthropic")
        assert err.retryable is False
        assert err.status_code == 401

    def test_server_error_retryable(self):
        err = ServerError("internal error", provider="anthropic")
        assert err.retryable is True
        assert err.status_code == 500

    def test_capacity_error_is_server_error(self):
        err = CapacityError("overloaded", status_code=529)
        assert isinstance(err, ServerError)
        assert err.retryable is True
        assert err.status_code == 529

    def test_timeout_retryable(self):
        err = TimeoutError_("timed out")
        assert err.retryable is True
        assert err.status_code is None

    def test_not_found_not_retryable(self):
        err = NotFoundError("no such model")
        assert err.retryable is False
        assert err.status_code == 404

    def test_cli_not_found_not_retryable(self):
        err = CLINotFoundError("claude not found")
        assert err.retryable is False


class TestClassifyHttpStatus:
    """Test classify_http_status."""

    def test_429(self):
        result = classify_http_status(429, "rate limited")
        assert isinstance(result, RateLimitError)

    def test_401(self):
        result = classify_http_status(401, "unauthorized")
        assert isinstance(result, AuthenticationError)

    def test_402(self):
        result = classify_http_status(402, "payment required")
        assert isinstance(result, BillingError)

    def test_404(self):
        result = classify_http_status(404, "not found")
        assert isinstance(result, NotFoundError)

    def test_503(self):
        result = classify_http_status(503, "service unavailable")
        assert isinstance(result, CapacityError)

    def test_500(self):
        result = classify_http_status(500, "server error")
        assert isinstance(result, ServerError)

    def test_400_billing(self):
        result = classify_http_status(400, "Your credit balance is too low")
        assert isinstance(result, BillingError)

    def test_400_other(self):
        result = classify_http_status(400, "bad request")
        assert isinstance(result, APIError)
        assert result.retryable is False


class TestClassifySubprocessError:
    """Test classify_subprocess_error."""

    def test_timeout_expired(self):
        exc = subprocess.TimeoutExpired(cmd="claude", timeout=30)
        result = classify_subprocess_error(exc, "claude")
        assert isinstance(result, TimeoutError_)
        assert "30" in str(result)

    def test_file_not_found(self):
        exc = FileNotFoundError("No such file: 'gemini'")
        result = classify_subprocess_error(exc, "gemini")
        assert isinstance(result, CLINotFoundError)
        assert result.retryable is False

    def test_other_error(self):
        exc = OSError("permission denied")
        result = classify_subprocess_error(exc, "test")
        assert isinstance(result, APIError)
