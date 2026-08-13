"""Unit tests for adversarial Gemini wrapper.

Issue #352: Multi-Model Adversarial Testing Node (Gemini vs Claude)
"""

from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from pydantic import BaseModel, ValidationError as PydanticValidationError

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

        with pytest.raises(GeminiModelDowngradeError, match="flash"):
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
        with pytest.raises(GeminiModelDowngradeError, match="flash"):
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


# ---------------------------------------------------------------------------
# The request we build must be one the SDK accepts (#2281)
# ---------------------------------------------------------------------------

_VALID_RESPONSE = (
    '{"uncovered_edge_cases": [], "false_claims": [], '
    '"missing_error_handling": [], "implicit_assumptions": [], "test_cases": []}'
)


def _capturing_genai_provider() -> tuple[MagicMock, dict]:
    """A stand-in for a google.genai Client that records the kwargs it is given.

    Shaped to take strategy 1 in `_invoke_provider` (`provider.models.generate_content`),
    which is the path a real google.genai Client takes.
    """
    captured: dict = {}

    def generate_content(*, model, contents, config):
        captured["model"] = model
        captured["contents"] = contents
        captured["config"] = config
        response = MagicMock()
        response.text = _VALID_RESPONSE
        response.model = "gemini-2.5-pro"
        return response

    provider = MagicMock()
    provider.models.generate_content = generate_content
    return provider, captured


def _invoke(provider, **kwargs) -> str:
    return AdversarialGeminiClient(provider=provider).generate_adversarial_tests(
        implementation_code="def foo(): pass",
        lld_content="# LLD",
        existing_tests="",
        **kwargs,
    )


class TestGenerateContentConfigIsAcceptedBySdk:
    """The config dict this module builds is validated by the real SDK type.

    Before #2281 the call site put `timeout` inside the config dict.
    `GenerateContentConfig` forbids extra fields, so every adversarial
    invocation raised a pydantic ValidationError locally, before any request
    was sent. The integration test could not catch it -- it skips on the very
    exception the defect raises -- so this offline check is the one that must.
    """

    def test_config_validates_against_the_real_sdk_type(self):
        from google.genai.types import GenerateContentConfig

        provider, captured = _capturing_genai_provider()
        _invoke(provider, timeout=120)

        # Must not raise. This is the whole defect: the dict below was rejected.
        GenerateContentConfig(**captured["config"])

    def test_timeout_is_not_passed_as_a_config_field(self):
        provider, captured = _capturing_genai_provider()
        _invoke(provider, timeout=120)

        assert "timeout" not in captured["config"], (
            "`timeout` is not a GenerateContentConfig field and the model forbids "
            "extras -- putting it back here breaks every adversarial call (#2281)."
        )

    def test_timeout_reaches_http_options_in_milliseconds(self):
        provider, captured = _capturing_genai_provider()
        _invoke(provider, timeout=120)

        assert captured["config"]["http_options"]["timeout"] == 120_000

    def test_sdk_still_documents_http_options_timeout_in_milliseconds(self):
        """Pin the UNIT, not just the field.

        A version bump that redefined `http_options.timeout` as seconds would
        turn our 120-second budget into 120000 seconds, or a 120ms one if the
        conversion were dropped. Neither would fail any other test here, and
        both would present as a Gemini problem rather than ours.
        """
        from google.genai.types import HttpOptions

        description = (HttpOptions.model_fields["timeout"].description or "").lower()
        assert "millisecond" in description, (
            f"google-genai no longer documents http_options.timeout in "
            f"milliseconds (got: {description!r}). The `* 1000` conversion in "
            f"adversarial_gemini.py must be re-derived before this ships."
        )


class TestClientSideErrorsAreNotReportedAsOutages:
    """A local validation error is our bug, and must not read as a Gemini outage.

    Before #2282 any non-rate-limit exception became a GeminiTimeoutError with
    `status=None`. Both consumers treat a timeout as "Gemini was unavailable":
    the integration test skips and the adversarial node records a benign skip
    reason and proceeds. That false all-clear is what hid #2281.
    """

    @staticmethod
    def _real_validation_error() -> PydanticValidationError:
        class _Forbidding(BaseModel):
            model_config = {"extra": "forbid"}
            a: int

        try:
            _Forbidding(a=1, b=2)
        except PydanticValidationError as exc:
            return exc
        raise AssertionError("expected a ValidationError from the probe model")

    def test_validation_error_propagates_unconverted(self):
        provider = MagicMock(spec=[])
        provider.side_effect = self._real_validation_error()

        with pytest.raises(PydanticValidationError):
            _invoke(provider, timeout=120)

    def test_validation_error_is_not_a_timeout_or_quota_error(self):
        provider = MagicMock(spec=[])
        provider.side_effect = self._real_validation_error()

        with pytest.raises(Exception) as excinfo:
            _invoke(provider, timeout=120)

        assert not isinstance(excinfo.value, GeminiTimeoutError), (
            "a locally-raised validation error was renamed to a timeout -- the "
            "misclassification that made a broken call site look like an outage"
        )
        assert not isinstance(excinfo.value, GeminiQuotaExhaustedError)

    def test_genuine_transport_errors_still_classify_as_before(self):
        """The narrowing must not swallow the behaviour #546 built."""
        provider = MagicMock(spec=[])
        provider.side_effect = RuntimeError("503 backend unavailable")

        with pytest.raises(GeminiTimeoutError):
            _invoke(provider, timeout=120)