"""Unit tests for adversarial Gemini wrapper.

Issue #352: Multi-Model Adversarial Testing Node (Gemini vs Claude)
"""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel, ValidationError as PydanticValidationError

from assemblyzero.core.llm_provider import LLMCallResult, LLMProvider
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
# The sanctioned transport, and nothing else (#2926)
# ---------------------------------------------------------------------------

_VALID_RESPONSE = (
    '{"uncovered_edge_cases": [], "false_claims": [], '
    '"missing_error_handling": [], "implicit_assumptions": [], "test_cases": []}'
)


def _invoke(provider, **kwargs) -> str:
    return AdversarialGeminiClient(provider=provider).generate_adversarial_tests(
        implementation_code="def foo(): pass",
        lld_content="# LLD",
        existing_tests="",
        **kwargs,
    )


class _FakeTransport(LLMProvider):
    """An LLMProvider that answers with a canned LLMCallResult and records
    the call: the shape GeminiProvider over agy has, without the network."""

    def __init__(self, result: LLMCallResult) -> None:
        self._result = result
        self.calls: list[dict] = []

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model(self) -> str:
        return "3.1-pro"

    def invoke(
        self,
        system_prompt: str,
        content: str,
        timeout_seconds: int = 300,
        response_schema: dict | None = None,
        json_schema: dict | None = None,
    ) -> LLMCallResult:
        self.calls.append({
            "system_prompt": system_prompt,
            "content": content,
            "timeout_seconds": timeout_seconds,
        })
        return self._result


def _result(**overrides) -> LLMCallResult:
    base = dict(
        success=True,
        response=_VALID_RESPONSE,
        raw_response=_VALID_RESPONSE,
        error_message=None,
        provider="gemini",
        model_used="gemini-3.1-pro-high",
        duration_ms=1,
        attempts=1,
    )
    base.update(overrides)
    return LLMCallResult(**base)


class TestTheSanctionedTransport:
    """#2926. The client used to discover its provider through four module
    names that did not exist and fall through to google.genai.Client(), which
    read a retired GEMINI_API_KEY from the environment. Google answered
    API_KEY_INVALID on every run from 2026-07-31 to 2026-09-24, the error was
    renamed to a timeout, and the node skipped itself each time."""

    def test_the_default_provider_comes_from_get_provider_with_the_gemini_spec(self):
        with patch("assemblyzero.core.llm_provider.get_provider") as factory:
            factory.return_value = _FakeTransport(_result())
            client = AdversarialGeminiClient()

        # #3563: with no spec given, the `impl.adversarial` seat of the
        # built-in default profile, which is Gemini.
        factory.assert_called_once_with("gemini:3.1-pro", effort=None)
        assert client._provider is factory.return_value

    def test_a_forbidden_alias_is_refused_before_any_transport_is_built(self):
        from assemblyzero.workflows.testing import adversarial_gemini as ag

        with patch("assemblyzero.core.llm_provider.get_provider") as factory:
            with pytest.raises(ag.ForbiddenModelError):
                AdversarialGeminiClient(spec="gemini:flash")

        factory.assert_not_called()

    def test_an_llm_provider_is_invoked_with_the_prompts_and_the_timeout(self):
        transport = _FakeTransport(_result())

        text = _invoke(transport, timeout=120)

        assert len(transport.calls) == 1
        call = transport.calls[0]
        assert call["timeout_seconds"] == 120
        assert "adversarial" in call["system_prompt"].lower()
        assert "def foo(): pass" in call["content"]
        assert "test_cases" in text

    def test_the_reply_metadata_carries_the_model_the_transport_used(self):
        transport = _FakeTransport(_result(model_used="gemini-3.1-pro-high"))
        client = AdversarialGeminiClient(provider=transport)

        _, metadata = client._invoke_provider("sys", "user", 120)

        assert metadata == {"model": "gemini-3.1-pro-high"}

    def test_a_reported_failure_carries_the_transport_message_not_a_timeout(self):
        """#2926's first requirement: a credential failure is reported as one.
        The message is the transport's own, with its status, and is not
        renamed to "exceeded 120s timeout" on the way out."""
        transport = _FakeTransport(_result(
            success=False,
            response=None,
            error_message="API key not valid. Please pass a valid API key.",
            status_code=400,
        ))

        with pytest.raises(GeminiTimeoutError) as excinfo:
            _invoke(transport, timeout=120)

        message = str(excinfo.value)
        assert "API key not valid" in message
        assert "status=400" in message
        assert "exceeded 120s timeout" not in message

    def test_a_rate_limit_is_a_quota_error(self):
        transport = _FakeTransport(_result(
            success=False,
            response=None,
            error_message="429 RESOURCE_EXHAUSTED",
            rate_limited=True,
            status_code=429,
        ))

        with pytest.raises(GeminiQuotaExhaustedError):
            _invoke(transport, timeout=120)

    def test_no_discovery_and_no_sdk_import_remain(self):
        """The failed path's names are gone from the module, not merely
        unreachable: no discovery method, and no import of the SDK, of
        importlib, of langchain, or of the utils package that never held a
        provider."""
        import ast
        from pathlib import Path

        import assemblyzero.workflows.testing.adversarial_gemini as ag

        assert not hasattr(AdversarialGeminiClient, "_discover_provider")

        imported: set[str] = set()
        for node in ast.walk(ast.parse(Path(ag.__file__).read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                imported |= {alias.name for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
        banned = {
            name for name in imported
            if name.split(".")[0] in {"google", "importlib", "langchain_core"}
            or name.startswith("assemblyzero.utils")
        }
        assert banned == set(), banned


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

class TestTheRequestedModelIsChosenNotSpelled:
    """#2286: three call sites spelled out `gemini-2.5-pro-preview-05-06`.

    That identifier's validity was never established -- before #2281 the call
    died in local validation, after it the request was rejected at
    authentication (#2285), so Google never resolved it once. A dated preview
    is exactly the kind of identifier that gets retired, and this call site
    consulted neither the alias map that would have remapped it nor the
    forbidden list that would have caught a bad tier.
    """

    def test_the_alias_is_in_the_selection_map(self):
        """#3563: the alias is the model half of the default profile's
        `impl.adversarial` seat."""
        from assemblyzero.core.llm_provider import GeminiProvider
        from assemblyzero.core.seats import default_profile, seat_in

        spec = seat_in(default_profile(), "impl.adversarial").spec
        provider, _, alias = spec.partition(":")
        assert provider == "gemini"
        assert alias in GeminiProvider.MODEL_MAP, (
            "the alias must resolve through the map, or supersession notes and "
            "fleet migrations cannot reach this call"
        )

    def test_it_resolves_to_a_pro_identifier(self):
        from assemblyzero.workflows.testing.adversarial_gemini import (
            resolve_adversarial_model,
        )

        model_id = resolve_adversarial_model()
        assert "pro" in model_id
        assert "flash" not in model_id
        assert "preview" not in model_id, (
            "a path that fails open should not run on a dated preview"
        )

    def test_the_requested_model_is_not_forbidden(self):
        """The check #2286 asked for: the REQUEST is validated, where
        verify_model_is_pro only ever inspected the reply."""
        from assemblyzero.core.config import FORBIDDEN_MODELS
        from assemblyzero.workflows.testing.adversarial_gemini import (
            resolve_adversarial_model,
        )

        assert resolve_adversarial_model() not in FORBIDDEN_MODELS

    @pytest.mark.parametrize("alias", ["flash", "2.5-flash", "3.1-flash-preview"])
    def test_a_forbidden_tier_is_refused_before_any_request(self, alias):
        """Including 3.1-flash-preview, which FORBIDDEN_MODELS does not catch
        (#2374) but which verify_model_is_pro would reject in the response.
        The two ends of one call have to agree."""
        from assemblyzero.workflows.testing import adversarial_gemini as ag

        with pytest.raises(ag.ForbiddenModelError):
            ag.resolve_adversarial_model(f"gemini:{alias}")

    def test_an_unknown_alias_is_refused_rather_than_passed_through(self):
        from assemblyzero.workflows.testing import adversarial_gemini as ag

        with pytest.raises(ag.ForbiddenModelError):
            ag.resolve_adversarial_model("gemini:gemini-9.9-imaginary")

    def test_a_forbidden_model_under_another_provider_is_refused(self):
        """#3563: a profile may put any provider in this seat; FORBIDDEN_MODELS
        still applies."""
        from assemblyzero.workflows.testing import adversarial_gemini as ag

        with pytest.raises(ag.ForbiddenModelError):
            ag.resolve_adversarial_model("mock:gemini-3-pro")

    def test_the_dated_preview_is_gone_from_every_call_site(self):
        """It appeared three times: the model argument and two metadata
        fallbacks. Changing only the first would have left the fallbacks
        reporting a model that was never requested."""
        from pathlib import Path

        import assemblyzero.workflows.testing.adversarial_gemini as ag

        source = Path(ag.__file__).read_text(encoding="utf-8")
        code = [
            line
            for line in source.splitlines()
            if not line.lstrip().startswith("#")
        ]
        assert not [line for line in code if "gemini-2.5-pro-preview" in line]

    def test_the_spec_sent_is_the_alias_that_was_checked(self):
        """#2926: the model half of the provider spec is the alias
        resolve_adversarial_model validates, so what is checked and what is
        requested cannot drift apart. #3563: the spec the client is given is
        the one both checked and built."""
        from assemblyzero.workflows.testing import adversarial_gemini as ag

        with patch.object(
            ag, "resolve_adversarial_model", wraps=ag.resolve_adversarial_model
        ) as checked, patch("assemblyzero.core.llm_provider.get_provider") as factory:
            factory.return_value = _FakeTransport(_result())
            ag.AdversarialGeminiClient(spec="gemini:3.1-pro-high", effort="max")

        checked.assert_called_once_with("gemini:3.1-pro-high")
        factory.assert_called_once_with("gemini:3.1-pro-high", effort="max")
