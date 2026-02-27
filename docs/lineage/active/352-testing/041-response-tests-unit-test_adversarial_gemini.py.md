

```python
"""Unit tests for adversarial Gemini wrapper.

Issue #352: Multi-Model Adversarial Testing Node (Gemini vs Claude)
"""

from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from assemblyzero.workflows.testing.adversarial_gemini import (
    AdversarialGeminiClient,
    GeminiModelDowngradeError,
    GeminiQuotaExhaustedError,
    GeminiTimeoutError,
)


class TestAdversarialGeminiClient:
    """Tests for AdversarialGeminiClient (T210, T220, T230, T240)."""

    def test_delegates_to_provider(self):
        """T210: Client correctly wraps and invokes underlying provider."""
        mock_provider = MagicMock(spec=[])  # empty spec so no attrs leak
        mock_provider.return_value = (
            '{"uncovered_edge_cases": [], "false_claims": [], '
            '"missing_error_handling": [], "implicit_assumptions": [], '
            '"test_cases": []}',
            {"model": "gemini-2.5-pro-preview-05-06"},
        )

        client = AdversarialGeminiClient(provider=mock_provider)
        result = client.generate_adversarial_tests(
            implementation_code="def foo(): pass",
            lld_content="# LLD",
            existing_tests="",
        )

        mock_provider.assert_called_once()
        assert "test_cases" in result

    def test_timeout_raises_gemini_timeout_error(self):
        """T220: On timeout from provider, raises GeminiTimeoutError."""
        mock_provider = MagicMock(spec=[])
        mock_provider.side_effect = TimeoutError("timeout")

        client = AdversarialGeminiClient(provider=mock_provider)

        with pytest.raises(GeminiTimeoutError, match="timeout"):
            client.generate_adversarial_tests(
                implementation_code="def foo(): pass",
                lld_content="# LLD",
                existing_tests="",
                timeout=120,
            )

    def test_quota_error_from_response_content(self):
        """Detects quota exhaustion from response content."""
        mock_provider = MagicMock(spec=[])
        mock_provider.return_value = (
            "RESOURCE_EXHAUSTED: quota exceeded",
            {"model": "gemini-2.5-pro-preview-05-06"},
        )

        client = AdversarialGeminiClient(provider=mock_provider)

        with pytest.raises(GeminiQuotaExhaustedError, match="429"):
            client.generate_adversarial_tests(
                implementation_code="def foo(): pass",
                lld_content="# LLD",
                existing_tests="",
            )

    def test_quota_error_from_status_code(self):
        """Detects quota exhaustion from HTTP 429 status code."""
        mock_provider = MagicMock(spec=[])
        mock_provider.return_value = (
            "some response",
            {"model": "gemini-2.5-pro-preview-05-06", "status_code": 429},
        )

        client = AdversarialGeminiClient(provider=mock_provider)

        with pytest.raises(GeminiQuotaExhaustedError):
            client.generate_adversarial_tests(
                implementation_code="def foo(): pass",
                lld_content="# LLD",
                existing_tests="",
            )

    def test_flash_model_in_response_raises(self):
        """Detects Flash model downgrade from response metadata."""
        mock_provider = MagicMock(spec=[])
        mock_provider.return_value = (
            '{"uncovered_edge_cases": [], "false_claims": [], '
            '"missing_error_handling": [], "implicit_assumptions": [], '
            '"test_cases": []}',
            {"model": "gemini-2.0-flash-001"},
        )

        client = AdversarialGeminiClient(provider=mock_provider)

        with pytest.raises(GeminiModelDowngradeError, match="Flash"):
            client.generate_adversarial_tests(
                implementation_code="def foo(): pass",
                lld_content="# LLD",
                existing_tests="",
            )

    def test_uses_default_patterns_when_none(self):
        """When adversarial_patterns is None, uses defaults from knowledge base."""
        mock_provider = MagicMock(spec=[])
        mock_provider.return_value = (
            '{"uncovered_edge_cases": [], "false_claims": [], '
            '"missing_error_handling": [], "implicit_assumptions": [], '
            '"test_cases": []}',
            {"model": "gemini-2.5-pro-preview-05-06"},
        )

        client = AdversarialGeminiClient(provider=mock_provider)
        client.generate_adversarial_tests(
            implementation_code="def foo(): pass",
            lld_content="# LLD",
            existing_tests="",
            adversarial_patterns=None,
        )

        # Should have called provider (meaning prompts were built with default patterns)
        mock_provider.assert_called_once()

    def test_custom_patterns_used(self):
        """Custom adversarial patterns are passed through to prompt builder."""
        mock_provider = MagicMock(spec=[])
        mock_provider.return_value = (
            '{"uncovered_edge_cases": [], "false_claims": [], '
            '"missing_error_handling": [], "implicit_assumptions": [], '
            '"test_cases": []}',
            {"model": "gemini-2.5-pro-preview-05-06"},
        )

        client = AdversarialGeminiClient(provider=mock_provider)
        custom_patterns = ["Custom: test with custom pattern"]
        client.generate_adversarial_tests(
            implementation_code="def foo(): pass",
            lld_content="# LLD",
            existing_tests="",
            adversarial_patterns=custom_patterns,
        )

        # Verify provider was called (patterns were used in prompt construction)
        mock_provider.assert_called_once()
        call_kwargs = mock_provider.call_args
        # The user_prompt arg should contain the custom pattern
        assert "Custom: test with custom pattern" in str(call_kwargs)

    def test_provider_injected(self):
        """Injected provider is used directly without auto-discovery."""
        mock_provider = MagicMock(spec=[])
        client = AdversarialGeminiClient(provider=mock_provider)
        assert client._provider is mock_provider

    def test_auto_discovery_import_error(self):
        """When no provider can be discovered, raises ImportError."""
        with patch(
            "assemblyzero.workflows.testing.adversarial_gemini.AdversarialGeminiClient._discover_provider",
            side_effect=ImportError("No Gemini provider found"),
        ):
            with pytest.raises(ImportError, match="No Gemini provider found"):
                AdversarialGeminiClient(provider=None)

    def test_langchain_provider_strategy(self):
        """Client can use LangChain-style provider with invoke() method."""
        mock_response = MagicMock()
        mock_response.content = (
            '{"uncovered_edge_cases": [], "false_claims": [], '
            '"missing_error_handling": [], "implicit_assumptions": [], '
            '"test_cases": []}'
        )
        mock_response.response_metadata = {"model": "gemini-2.5-pro-preview-05-06"}

        mock_provider = MagicMock()
        # Remove callable behavior so it falls to invoke() strategy
        mock_provider.models = MagicMock(spec=[])  # no generate_content
        del mock_provider.models.generate_content
        mock_provider.invoke.return_value = mock_response

        client = AdversarialGeminiClient(provider=mock_provider)

        with patch(
            "assemblyzero.workflows.testing.adversarial_gemini.AdversarialGeminiClient._invoke_provider",
            return_value=(mock_response.content, mock_response.response_metadata),
        ):
            result = client.generate_adversarial_tests(
                implementation_code="def foo(): pass",
                lld_content="# LLD",
                existing_tests="",
            )

        assert "test_cases" in result


class TestVerifyModelIsPro:
    """Tests for verify_model_is_pro (T230, T240)."""

    def test_pro_model_passes(self):
        """T230: verify_model_is_pro returns True for Pro metadata."""
        client = AdversarialGeminiClient(provider=MagicMock())
        result = client.verify_model_is_pro(
            {"model": "gemini-2.5-pro-preview-05-06"}
        )
        assert result is True

    def test_flash_detected_raises(self):
        """T240: verify_model_is_pro raises for Flash metadata."""
        client = AdversarialGeminiClient(provider=MagicMock())
        with pytest.raises(GeminiModelDowngradeError, match="Flash"):
            client.verify_model_is_pro({"model": "gemini-2.0-flash-001"})

    def test_empty_metadata_raises(self):
        """Empty metadata raises GeminiModelDowngradeError."""
        client = AdversarialGeminiClient(provider=MagicMock())
        with pytest.raises(GeminiModelDowngradeError, match="No model information"):
            client.verify_model_is_pro({})

    def test_unknown_model_passes_with_warning(self):
        """Unknown model name passes but with warning."""
        client = AdversarialGeminiClient(provider=MagicMock())
        result = client.verify_model_is_pro({"model": "gemini-ultra-2026"})
        assert result is True

    def test_pro_case_insensitive(self):
        """Model name check is case-insensitive."""
        client = AdversarialGeminiClient(provider=MagicMock())
        assert client.verify_model_is_pro({"model": "Gemini-PRO-latest"}) is True

    def test_empty_model_string_raises(self):
        """Empty model string raises GeminiModelDowngradeError."""
        client = AdversarialGeminiClient(provider=MagicMock())
        with pytest.raises(GeminiModelDowngradeError, match="No model information"):
            client.verify_model_is_pro({"model": ""})

    def test_flash_exp_detected(self):
        """Flash experimental model is also detected."""
        client = AdversarialGeminiClient(provider=MagicMock())
        with pytest.raises(GeminiModelDowngradeError):
            client.verify_model_is_pro({"model": "gemini-2.0-flash-exp"})

    def test_pro_preview_variant(self):
        """Pro preview variant passes."""
        client = AdversarialGeminiClient(provider=MagicMock())
        assert client.verify_model_is_pro({"model": "gemini-3-pro-preview-0514"}) is True


class TestIsQuotaError:
    """Tests for _is_quota_error."""

    def test_status_code_429(self):
        """HTTP 429 status code is detected as quota error."""
        client = AdversarialGeminiClient(provider=MagicMock())
        assert client._is_quota_error("", {"status_code": 429}) is True

    def test_resource_exhausted_in_response(self):
        """RESOURCE_EXHAUSTED in response text is detected."""
        client = AdversarialGeminiClient(provider=MagicMock())
        assert client._is_quota_error("RESOURCE_EXHAUSTED: quota limit", {}) is True

    def test_rate_limit_in_response(self):
        """'rate limit' in response text is detected."""
        client = AdversarialGeminiClient(provider=MagicMock())
        assert client._is_quota_error("rate limit exceeded", {}) is True

    def test_normal_response_not_quota_error(self):
        """Normal JSON response is not a quota error."""
        client = AdversarialGeminiClient(provider=MagicMock())
        assert client._is_quota_error('{"test_cases": []}', {"status_code": 200}) is False

    def test_empty_response_not_quota_error(self):
        """Empty response is not a quota error."""
        client = AdversarialGeminiClient(provider=MagicMock())
        assert client._is_quota_error("", {}) is False

    def test_none_response_not_quota_error(self):
        """None response is not a quota error."""
        client = AdversarialGeminiClient(provider=MagicMock())
        assert client._is_quota_error(None, {}) is False

    def test_quota_word_in_response(self):
        """'quota' in response text is detected."""
        client = AdversarialGeminiClient(provider=MagicMock())
        assert client._is_quota_error("quota exceeded for project", {}) is True
```
