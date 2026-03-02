"""Unified exception hierarchy for API call sites.

Issue #542: Every API-calling module had its own ad-hoc error handling — 4
different retry implementations, string-matching for billing errors, and bare
``except Exception`` catch-alls that swallowed real bugs.  This module provides
a single, typed exception hierarchy so callers can catch errors by *category*
(retryable vs. fatal) instead of pattern-matching error messages.

Classifier functions translate provider-native exceptions into the hierarchy:
- ``classify_anthropic_error``  — Anthropic SDK exceptions
- ``classify_http_status``      — generic HTTP status codes
- ``classify_subprocess_error`` — subprocess failures (timeout, not-found)
"""

from __future__ import annotations

import subprocess
from typing import Optional


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class APIError(Exception):
    """Base for all API-related errors.

    Attributes:
        status_code: HTTP status code (None for non-HTTP errors).
        retryable: Whether the caller should retry this request.
        provider: Provider name that raised the error (e.g. "anthropic").
        retry_after: Seconds to wait before retry (from Retry-After header).
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        retryable: bool = False,
        provider: str = "",
        retry_after: Optional[float] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable
        self.provider = provider
        self.retry_after = retry_after


class RateLimitError(APIError):
    """429 Too Many Requests.  Retryable — honour ``retry_after``."""

    def __init__(
        self,
        message: str,
        *,
        provider: str = "",
        retry_after: Optional[float] = None,
    ):
        super().__init__(
            message,
            status_code=429,
            retryable=True,
            provider=provider,
            retry_after=retry_after,
        )


class AuthenticationError(APIError):
    """401 / 403.  Not retryable — bad key or no permission."""

    def __init__(self, message: str, *, provider: str = "", status_code: int = 401):
        super().__init__(
            message,
            status_code=status_code,
            retryable=False,
            provider=provider,
        )


class BillingError(APIError):
    """402 or 400 with billing message.  Not retryable — pay your bill."""

    def __init__(self, message: str, *, provider: str = ""):
        super().__init__(
            message,
            status_code=402,
            retryable=False,
            provider=provider,
        )


class ServerError(APIError):
    """5xx.  Retryable — transient server-side issue."""

    def __init__(self, message: str, *, provider: str = "", status_code: int = 500):
        super().__init__(
            message,
            status_code=status_code,
            retryable=True,
            provider=provider,
        )


class CapacityError(ServerError):
    """503 / 529 overloaded.  Retryable."""

    def __init__(self, message: str, *, provider: str = "", status_code: int = 503):
        super().__init__(message, provider=provider, status_code=status_code)


class TimeoutError_(APIError):
    """Request timed out.  Retryable (max 1 retry)."""

    def __init__(self, message: str, *, provider: str = ""):
        super().__init__(
            message,
            status_code=None,
            retryable=True,
            provider=provider,
        )


class NotFoundError(APIError):
    """404.  Not retryable."""

    def __init__(self, message: str, *, provider: str = ""):
        super().__init__(
            message,
            status_code=404,
            retryable=False,
            provider=provider,
        )


class CLINotFoundError(APIError):
    """FileNotFoundError on subprocess exec.  Not retryable — binary missing."""

    def __init__(self, message: str, *, provider: str = ""):
        super().__init__(
            message,
            status_code=None,
            retryable=False,
            provider=provider,
        )


# ---------------------------------------------------------------------------
# Classifier: Anthropic SDK
# ---------------------------------------------------------------------------


def classify_anthropic_error(exc: Exception) -> APIError:
    """Translate an Anthropic SDK exception into the unified hierarchy.

    Import ``anthropic`` lazily so this module has no hard dependency on the SDK.

    Args:
        exc: An exception raised by the ``anthropic`` package.

    Returns:
        The appropriate ``APIError`` subclass wrapping the original exception.
    """
    import anthropic

    msg = str(exc)

    # Billing — the SDK raises BadRequestError with a billing message
    if _is_billing_message(msg):
        return BillingError(msg, provider="anthropic")

    if isinstance(exc, anthropic.RateLimitError):
        retry_after = _extract_retry_after(exc)
        return RateLimitError(msg, provider="anthropic", retry_after=retry_after)

    if isinstance(exc, anthropic.AuthenticationError):
        return AuthenticationError(msg, provider="anthropic")

    if isinstance(exc, anthropic.PermissionDeniedError):
        return AuthenticationError(msg, provider="anthropic", status_code=403)

    if isinstance(exc, anthropic.NotFoundError):
        return NotFoundError(msg, provider="anthropic")

    if isinstance(exc, anthropic.APITimeoutError):
        return TimeoutError_(msg, provider="anthropic")

    if isinstance(exc, anthropic.InternalServerError):
        status = getattr(exc, "status_code", 500)
        if status in (503, 529):
            return CapacityError(msg, provider="anthropic", status_code=status)
        return ServerError(msg, provider="anthropic", status_code=status)

    if isinstance(exc, anthropic.APIStatusError):
        status = getattr(exc, "status_code", None)
        if status and 500 <= status < 600:
            return ServerError(msg, provider="anthropic", status_code=status)
        return APIError(msg, status_code=status, retryable=False, provider="anthropic")

    # Fallback: unknown anthropic error — not retryable by default
    return APIError(msg, retryable=False, provider="anthropic")


# ---------------------------------------------------------------------------
# Classifier: HTTP status codes (generic)
# ---------------------------------------------------------------------------


def classify_http_status(status_code: int, body: str = "") -> APIError:
    """Map an HTTP status code to the appropriate exception.

    Args:
        status_code: HTTP status code.
        body: Response body text for message extraction.

    Returns:
        The appropriate ``APIError`` subclass.
    """
    msg = body or f"HTTP {status_code}"

    if status_code == 429:
        return RateLimitError(msg)

    if status_code in (401, 403):
        return AuthenticationError(msg, status_code=status_code)

    if status_code == 402 or (status_code == 400 and _is_billing_message(body)):
        return BillingError(msg)

    if status_code == 404:
        return NotFoundError(msg)

    if status_code in (503, 529):
        return CapacityError(msg, status_code=status_code)

    if 500 <= status_code < 600:
        return ServerError(msg, status_code=status_code)

    return APIError(msg, status_code=status_code, retryable=False)


# ---------------------------------------------------------------------------
# Classifier: Subprocess errors
# ---------------------------------------------------------------------------


def classify_subprocess_error(
    exc: Exception,
    cli_name: str = "subprocess",
) -> APIError:
    """Translate a subprocess exception into the unified hierarchy.

    Args:
        exc: A ``subprocess.TimeoutExpired`` or ``FileNotFoundError``.
        cli_name: Friendly name for error messages (e.g. "claude", "gemini").

    Returns:
        The appropriate ``APIError`` subclass.
    """
    if isinstance(exc, subprocess.TimeoutExpired):
        timeout = exc.timeout
        return TimeoutError_(
            f"{cli_name} timed out after {timeout}s",
            provider=cli_name,
        )

    if isinstance(exc, FileNotFoundError):
        return CLINotFoundError(
            f"{cli_name} executable not found: {exc}",
            provider=cli_name,
        )

    return APIError(str(exc), retryable=False, provider=cli_name)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BILLING_PATTERNS = (
    "credit balance is too low",
    "insufficient_quota",
    "billing",
    "account has been disabled",
)


def _is_billing_message(msg: str) -> bool:
    """Return True if the message indicates a billing/quota problem."""
    lower = msg.lower()
    return any(p in lower for p in _BILLING_PATTERNS)


def _extract_retry_after(exc: Exception) -> Optional[float]:
    """Extract Retry-After seconds from an Anthropic rate-limit response."""
    headers = getattr(exc, "response", None)
    if headers is not None:
        headers = getattr(headers, "headers", {})
        val = headers.get("retry-after")
        if val:
            try:
                return float(val)
            except (ValueError, TypeError):
                pass
    return None
