"""Unit tests for tools/_gh_retry.py.

Exercises the retry/backoff helper without making real HTTP calls.
Mocks `requests.request` and `time.sleep` so tests are deterministic
and fast.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest import mock

import pytest
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import _gh_retry as gh  # noqa: E402


def _resp(status: int, headers: dict | None = None) -> requests.Response:
    r = requests.Response()
    r.status_code = status
    if headers:
        r.headers.update(headers)
    return r


class TestSuccessPaths:
    def test_success_on_first_try(self):
        with mock.patch("requests.request", return_value=_resp(200)) as m:
            r = gh.request_with_retry("GET", "https://example/x", "pat")
        assert r.status_code == 200
        assert m.call_count == 1

    def test_passes_kwargs_through(self):
        with mock.patch("requests.request", return_value=_resp(200)) as m:
            gh.request_with_retry("PUT", "https://example/x", "pat", json={"k": "v"})
        kwargs = m.call_args.kwargs
        assert kwargs.get("json") == {"k": "v"}

    def test_sets_auth_header(self):
        with mock.patch("requests.request", return_value=_resp(200)) as m:
            gh.request_with_retry("GET", "https://example/x", "secret_pat")
        headers = m.call_args.kwargs.get("headers", {})
        assert headers.get("Authorization") == "Bearer secret_pat"
        assert headers.get("Accept") == "application/vnd.github+json"


class TestPermanent4xx:
    def test_404_returned_without_retry(self):
        with mock.patch("requests.request", return_value=_resp(404)) as m:
            r = gh.request_with_retry("GET", "https://example/x", "pat")
        assert r.status_code == 404
        assert m.call_count == 1

    def test_422_returned_without_retry(self):
        with mock.patch("requests.request", return_value=_resp(422)) as m:
            r = gh.request_with_retry("PUT", "https://example/x", "pat")
        assert r.status_code == 422
        assert m.call_count == 1


class TestServer5xx:
    def test_recovers_after_transient_5xx(self):
        responses = [_resp(502), _resp(503), _resp(200)]
        with mock.patch("requests.request", side_effect=responses) as m, \
             mock.patch.object(time, "sleep"):
            r = gh.request_with_retry("GET", "https://example/x", "pat")
        assert r.status_code == 200
        assert m.call_count == 3

    def test_5xx_exhaustion_raises_http_error(self):
        with mock.patch("requests.request", return_value=_resp(502)), \
             mock.patch.object(time, "sleep"):
            with pytest.raises(requests.HTTPError):
                gh.request_with_retry("GET", "https://example/x", "pat")


class TestSecondaryRateLimit429:
    def test_recovers_after_429(self):
        responses = [_resp(429, {"Retry-After": "5"}), _resp(200)]
        sleep = mock.MagicMock()
        with mock.patch("requests.request", side_effect=responses), \
             mock.patch.object(time, "sleep", sleep):
            r = gh.request_with_retry("GET", "https://example/x", "pat")
        assert r.status_code == 200
        # Honors Retry-After value.
        assert any(call.args == (5,) for call in sleep.call_args_list)

    def test_429_exhaustion_raises_http_error(self):
        with mock.patch(
            "requests.request",
            return_value=_resp(429, {"Retry-After": "1"}),
        ), mock.patch.object(time, "sleep"):
            with pytest.raises(requests.HTTPError):
                gh.request_with_retry("GET", "https://example/x", "pat")


class TestPrimaryRateLimit403:
    def test_recovers_after_primary_rate_limit(self):
        future = int(time.time()) + 5
        responses = [
            _resp(403, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(future)}),
            _resp(200),
        ]
        with mock.patch("requests.request", side_effect=responses), \
             mock.patch.object(time, "sleep"):
            r = gh.request_with_retry("GET", "https://example/x", "pat")
        assert r.status_code == 200

    def test_403_without_rate_limit_header_returned_as_is(self):
        # 403 not flagged as rate-limit (no X-RateLimit-Remaining=0) is permanent
        with mock.patch("requests.request", return_value=_resp(403)) as m:
            r = gh.request_with_retry("GET", "https://example/x", "pat")
        assert r.status_code == 403
        assert m.call_count == 1

    def test_primary_rate_limit_exhaustion_raises_http_error(self):
        future = int(time.time()) + 1
        resp = _resp(403, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(future)})
        with mock.patch("requests.request", return_value=resp), \
             mock.patch.object(time, "sleep"):
            with pytest.raises(requests.HTTPError):
                gh.request_with_retry("GET", "https://example/x", "pat")


class TestNetworkErrors:
    def test_recovers_after_connection_error(self):
        side_effects = [requests.ConnectionError("nope"), _resp(200)]
        with mock.patch("requests.request", side_effect=side_effects), \
             mock.patch.object(time, "sleep"):
            r = gh.request_with_retry("GET", "https://example/x", "pat")
        assert r.status_code == 200

    def test_recovers_after_timeout(self):
        side_effects = [requests.Timeout("slow"), _resp(200)]
        with mock.patch("requests.request", side_effect=side_effects), \
             mock.patch.object(time, "sleep"):
            r = gh.request_with_retry("GET", "https://example/x", "pat")
        assert r.status_code == 200

    def test_connection_error_exhaustion_raises(self):
        with mock.patch(
            "requests.request",
            side_effect=requests.ConnectionError("nope"),
        ), mock.patch.object(time, "sleep"):
            with pytest.raises(requests.ConnectionError):
                gh.request_with_retry("GET", "https://example/x", "pat")

    def test_timeout_exhaustion_raises(self):
        with mock.patch(
            "requests.request",
            side_effect=requests.Timeout("slow"),
        ), mock.patch.object(time, "sleep"):
            with pytest.raises(requests.Timeout):
                gh.request_with_retry("GET", "https://example/x", "pat")


class TestExceptionHierarchy:
    """All raised exceptions must be requests.RequestException so existing
    `except requests.RequestException` handlers in caller tools keep
    catching retry-exhausted failures."""

    def test_http_error_is_request_exception(self):
        with mock.patch("requests.request", return_value=_resp(502)), \
             mock.patch.object(time, "sleep"):
            with pytest.raises(requests.RequestException):
                gh.request_with_retry("GET", "https://example/x", "pat")

    def test_connection_error_is_request_exception(self):
        with mock.patch(
            "requests.request",
            side_effect=requests.ConnectionError("nope"),
        ), mock.patch.object(time, "sleep"):
            with pytest.raises(requests.RequestException):
                gh.request_with_retry("GET", "https://example/x", "pat")
