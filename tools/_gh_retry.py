"""Shared retry helper for in-process classic-PAT GitHub API calls.

Companion to `tools/_pat_session.py`. Where `_pat_session` decides
*how* the PAT is sourced (ADR-0216), this module decides *how* the
HTTP call wrapping the PAT-bearing request handles transient failures.

Single function: `_request_with_retry`. Exponential backoff on
ConnectionError/Timeout/5xx, primary rate limit (403 +
X-RateLimit-Remaining=0, X-RateLimit-Reset honored), secondary rate
limit (429, Retry-After honored). Permanent 4xx responses (404, 422,
etc.) are returned as-is for the caller to inspect.

On retry exhaustion, raises rather than silently returning a failed
response. This is the loud-failure variant; the silent-return form
(used previously in `new_repo_setup.py` and `deploy_cerberus_secrets.py`)
let permanent transient failures masquerade as flow control. (#1052)

Existing callers wrap calls in `try / except requests.RequestException`
and check `resp.status_code < 300` on the way out. The exceptions
raised by this module — `requests.ConnectionError`, `requests.Timeout`,
`requests.HTTPError` — are all subclasses of `RequestException`, so
the existing handlers continue to catch them.

Usage:

    from _gh_retry import request_with_retry

    with classic_pat_session() as pat:
        try:
            r = request_with_retry(
                "PUT", f"{_GH_API}/repos/{owner}/{repo}/...", pat,
                json=body,
            )
        except requests.RequestException:
            # network or retry-exhausted failure
            return False
        return r.status_code < 300
"""
from __future__ import annotations

import time
from typing import Any

import requests

_HTTP_TIMEOUT_S = 30
_MAX_RETRIES = 4
_INITIAL_BACKOFF_S = 1.0


def _gh_headers(pat: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def request_with_retry(
    method: str,
    url: str,
    pat: str,
    **kwargs: Any,
) -> requests.Response:
    """HTTP request with exponential backoff on transient errors.

    Retries: ConnectionError, Timeout, HTTP 5xx, HTTP 429 (Retry-After
    honored), HTTP 403 with X-RateLimit-Remaining=0 (X-RateLimit-Reset
    honored).

    Returns: the response object on success or on permanent 4xx (caller
    decides what to do with non-retried 4xx like 404, 422).

    Raises (on retry exhaustion):
    - `requests.ConnectionError` or `requests.Timeout` — last
      network-level exception when retries are exhausted on transport
      errors.
    - `requests.HTTPError` — when retries are exhausted on a retried
      HTTP status (5xx, 429, or 403 rate-limit). Subclass of
      RequestException so callers' existing `except RequestException`
      handlers catch it.
    """
    backoff = _INITIAL_BACKOFF_S
    for attempt in range(_MAX_RETRIES + 1):
        try:
            r = requests.request(
                method, url, headers=_gh_headers(pat),
                timeout=_HTTP_TIMEOUT_S, **kwargs,
            )
        except (requests.ConnectionError, requests.Timeout) as e:
            if attempt < _MAX_RETRIES:
                print(f"    network error ({type(e).__name__}); retry in {backoff}s")
                time.sleep(backoff)
                backoff *= 2
                continue
            raise

        # Secondary rate limit (429 + Retry-After)
        if r.status_code == 429:
            if attempt < _MAX_RETRIES:
                retry_after = int(r.headers.get("Retry-After", "30"))
                print(f"    HTTP 429; sleeping {retry_after}s per Retry-After")
                time.sleep(retry_after)
                continue
            r.raise_for_status()  # exhausted -> HTTPError

        # Primary rate limit (403 + X-RateLimit-Remaining=0)
        if r.status_code == 403 and r.headers.get("X-RateLimit-Remaining") == "0":
            if attempt < _MAX_RETRIES:
                reset = int(r.headers.get("X-RateLimit-Reset", "0"))
                wait = max(reset - int(time.time()), 30)
                print(f"    primary rate limit hit; sleeping {wait}s until reset")
                time.sleep(wait)
                continue
            r.raise_for_status()  # exhausted -> HTTPError

        # Server-side transient (5xx)
        if 500 <= r.status_code < 600:
            if attempt < _MAX_RETRIES:
                print(f"    HTTP {r.status_code}; retry in {backoff}s")
                time.sleep(backoff)
                backoff *= 2
                continue
            r.raise_for_status()  # exhausted -> HTTPError

        # Success or permanent 4xx (non-retried) — return as-is
        return r

    # Defensive: the loop body always either continues, returns, or raises.
    # If somehow we fall through, raise on the last response.
    r.raise_for_status()
    return r
