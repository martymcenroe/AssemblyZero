"""Tests for Claude CLI retry/backoff handling.

Issue #138: Add retry/backoff handling for Claude CLI invocations.
"""

import subprocess
from unittest.mock import MagicMock, patch

import pytest


class TestClaudeRetryBackoff:
    """Tests for Claude CLI retry/backoff handling."""

    def test_successful_call_no_retry(self):
        """Successful Claude call should not retry."""
        from assemblyzero.core.claude_client import invoke_claude

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Hello, world!"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = invoke_claude("Say hello", "/tmp")

        assert result == "Hello, world!"
        assert mock_run.call_count == 1

    def test_retry_on_rate_limit_429(self):
        """Should retry with backoff on 429 rate limit."""
        from assemblyzero.core.claude_client import invoke_claude

        # Create mock results: fail twice with 429, then succeed
        fail_result = MagicMock()
        fail_result.returncode = 1
        fail_result.stdout = ""
        fail_result.stderr = "Error: 429 Too Many Requests"

        success_result = MagicMock()
        success_result.returncode = 0
        success_result.stdout = "Success after retries"
        success_result.stderr = ""

        with patch("subprocess.run", side_effect=[fail_result, fail_result, success_result]) as mock_run:
            with patch("time.sleep") as mock_sleep:
                result = invoke_claude("Test prompt", "/tmp", max_retries=5)

        assert result == "Success after retries"
        assert mock_run.call_count == 3
        assert mock_sleep.call_count == 2  # Two waits before third attempt

    def test_retry_on_rate_limit_text(self):
        """Should retry when stderr contains 'rate limit' text."""
        from assemblyzero.core.claude_client import invoke_claude

        fail_result = MagicMock()
        fail_result.returncode = 1
        fail_result.stdout = ""
        fail_result.stderr = "Rate limit exceeded, please try again later"

        success_result = MagicMock()
        success_result.returncode = 0
        success_result.stdout = "Success"
        success_result.stderr = ""

        with patch("subprocess.run", side_effect=[fail_result, success_result]) as mock_run:
            with patch("time.sleep"):
                result = invoke_claude("Test prompt", "/tmp")

        assert result == "Success"
        assert mock_run.call_count == 2

    def test_max_retries_exceeded(self):
        """Should raise after max retries."""
        from assemblyzero.core.claude_client import ClaudeRateLimitError, invoke_claude

        fail_result = MagicMock()
        fail_result.returncode = 1
        fail_result.stdout = ""
        fail_result.stderr = "Error: 429 Too Many Requests"

        with patch("subprocess.run", return_value=fail_result) as mock_run:
            with patch("time.sleep"):
                with pytest.raises(ClaudeRateLimitError):
                    invoke_claude("Test prompt", "/tmp", max_retries=3)

        assert mock_run.call_count == 3

    def test_no_retry_on_other_errors(self):
        """Non-rate-limit errors should not retry."""
        from assemblyzero.core.claude_client import ClaudeClientError, invoke_claude

        fail_result = MagicMock()
        fail_result.returncode = 1
        fail_result.stdout = ""
        fail_result.stderr = "Error: Invalid API key"

        with patch("subprocess.run", return_value=fail_result) as mock_run:
            with pytest.raises(ClaudeClientError) as exc_info:
                invoke_claude("Test prompt", "/tmp")

        assert mock_run.call_count == 1
        assert "Invalid API key" in str(exc_info.value)

    def test_exponential_backoff_timing(self):
        """Backoff should be exponential: ~1s, ~2s, ~4s, ~8s..."""
        from assemblyzero.core.claude_client import invoke_claude

        fail_result = MagicMock()
        fail_result.returncode = 1
        fail_result.stdout = ""
        fail_result.stderr = "Error: 429 Too Many Requests"

        success_result = MagicMock()
        success_result.returncode = 0
        success_result.stdout = "Success"
        success_result.stderr = ""

        # Fail 4 times, then succeed
        side_effects = [fail_result] * 4 + [success_result]

        sleep_delays = []

        def capture_sleep(delay):
            sleep_delays.append(delay)

        with patch("subprocess.run", side_effect=side_effects):
            with patch("time.sleep", side_effect=capture_sleep):
                invoke_claude("Test prompt", "/tmp", max_retries=5)

        # Should have 4 delays (before attempts 2, 3, 4, 5)
        assert len(sleep_delays) == 4

        # Verify exponential pattern (allowing for jitter of ±20%)
        # Expected base delays: 1, 2, 4, 8 seconds
        expected_bases = [1.0, 2.0, 4.0, 8.0]
        for i, (actual, expected) in enumerate(zip(sleep_delays, expected_bases)):
            min_delay = expected * 0.8  # -20% jitter
            max_delay = expected * 1.2  # +20% jitter
            assert min_delay <= actual <= max_delay, (
                f"Delay {i} was {actual}, expected {expected} ±20%"
            )

    def test_jitter_applied_to_backoff(self):
        """Backoff should include jitter so delays vary."""
        from assemblyzero.core.claude_client import _calculate_backoff

        # Generate many backoff values for the same attempt
        delays = [_calculate_backoff(0) for _ in range(100)]

        # With ±20% jitter on base 1.0, we expect range ~[0.8, 1.2]
        # Not all values should be exactly the same
        unique_delays = set(delays)
        assert len(unique_delays) > 1, "Jitter should cause variation in delays"

        # All delays should be within expected range
        for delay in delays:
            assert 0.8 <= delay <= 1.2, f"Delay {delay} outside expected jitter range"

    def test_timeout_does_not_retry(self):
        """Timeout errors should not retry."""
        from assemblyzero.core.claude_client import ClaudeClientError, invoke_claude

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("claude", 300)) as mock_run:
            with pytest.raises(ClaudeClientError) as exc_info:
                invoke_claude("Test prompt", "/tmp", timeout=300)

        assert mock_run.call_count == 1
        assert "timed out" in str(exc_info.value)

    def test_max_delay_cap(self):
        """Backoff delay should be capped at MAX_DELAY."""
        from assemblyzero.core.claude_client import MAX_DELAY, _calculate_backoff

        # At attempt 10, base delay would be 2^10 = 1024 seconds
        # But should be capped at MAX_DELAY (60 seconds)
        delay = _calculate_backoff(10)
        assert delay <= MAX_DELAY * 1.2, f"Delay {delay} exceeds MAX_DELAY cap"

    def test_working_dir_parameter(self):
        """Working directory should be passed to subprocess."""
        from assemblyzero.core.claude_client import invoke_claude

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Response"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            invoke_claude("Test prompt", "/my/working/dir")

        # Verify cwd was passed
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs.get("cwd") == "/my/working/dir"

    def test_too_many_requests_text(self):
        """Should retry when stderr contains 'too many requests' text."""
        from assemblyzero.core.claude_client import invoke_claude

        fail_result = MagicMock()
        fail_result.returncode = 1
        fail_result.stdout = ""
        fail_result.stderr = "Error: Too many requests, slow down"

        success_result = MagicMock()
        success_result.returncode = 0
        success_result.stdout = "Success"
        success_result.stderr = ""

        with patch("subprocess.run", side_effect=[fail_result, success_result]) as mock_run:
            with patch("time.sleep"):
                result = invoke_claude("Test prompt", "/tmp")

        assert result == "Success"
        assert mock_run.call_count == 2
