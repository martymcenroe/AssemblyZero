"""Gemini failures are final at the provider boundary (#1907).

GeminiClient.invoke() retries per credential, rotates across credentials,
and enforces its own wall-clock budget (#1874). A failure it reports is
post-exhaustion — but LLMCallResult defaulted retryable=True, so the
#1071 with_retry(5) wrapper at call sites like review_test_plan stacked
up to five more full gauntlets (~50 minutes worst case) on a review call
that had already burned every internal recovery. On a recorded take that
is indistinguishable from a hang.

The provider now reports retryable=False on any failure its client
returns, which makes with_retry a pass-through for Gemini — storm-riding
escalates to the stage retry loop (#1909) instead.
"""

from unittest.mock import Mock, patch

from assemblyzero.core.llm_provider import GeminiProvider
from assemblyzero.utils.retry import RetryPolicy, with_retry


def _failed_client_result():
    return Mock(
        success=False,
        response=None,
        raw_response=None,
        error_message=(
            "All credentials failed:\n"
            "  - oauth-primary: Capacity exhausted after 3 retries (503/529)"
        ),
        error_type=None,
        model_verified="gemini-3.1-pro-high",
        duration_ms=28000,
        attempts=3,
        credential_used="oauth-primary",
        rotation_occurred=True,
    )


class TestGeminiFailureIsFinal:
    @patch("assemblyzero.core.llm_provider.GeminiProvider._get_client")
    def test_client_reported_failure_is_not_retryable(self, mock_get_client):
        mock_client = Mock()
        mock_client.invoke.return_value = _failed_client_result()
        mock_get_client.return_value = mock_client

        result = GeminiProvider(model="3.1-pro").invoke(
            system_prompt="review", content="content"
        )

        assert result.success is False
        assert result.retryable is False

    @patch("assemblyzero.core.llm_provider.GeminiProvider._get_client")
    def test_success_keeps_retryable_semantics(self, mock_get_client):
        mock_client = Mock()
        mock_client.invoke.return_value = Mock(
            success=True,
            response="ok",
            raw_response="ok",
            error_message=None,
            error_type=None,
            model_verified="gemini-3.1-pro-high",
            duration_ms=900,
            attempts=1,
            credential_used="oauth-primary",
            rotation_occurred=False,
        )
        mock_get_client.return_value = mock_client

        result = GeminiProvider(model="3.1-pro").invoke(
            system_prompt="review", content="content"
        )

        assert result.success is True
        assert result.retryable is True

    @patch("assemblyzero.core.llm_provider.GeminiProvider._get_client")
    def test_with_retry_runs_the_exhausted_gauntlet_exactly_once(
        self, mock_get_client
    ):
        """The #1907 regression itself: 1 invocation, not 1 + max_retries."""
        mock_client = Mock()
        mock_client.invoke.return_value = _failed_client_result()
        mock_get_client.return_value = mock_client

        provider = GeminiProvider(model="3.1-pro")
        calls = {"n": 0}

        def call_provider():
            calls["n"] += 1
            return provider.invoke(system_prompt="review", content="content")

        result = with_retry(
            call_provider,
            policy=RetryPolicy.default(),
            sleep_fn=lambda s: None,
            description="N1 testing reviewer",
        )

        assert result.success is False
        assert calls["n"] == 1
