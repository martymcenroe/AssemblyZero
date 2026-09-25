"""Wrapper module for Gemini adversarial invocation logic.

Issue #352: Multi-Model Adversarial Testing Node (Gemini vs Claude)

Encapsulates adversarial-specific invocation (system prompt, no-mock constraint,
model check) while delegating the call to the sanctioned transport:
``get_provider("gemini:3.1-pro")``, which is ``agy`` over stdin per ADR 0220.

#2926: until 2026-09-24 the client "discovered" its provider through four
module names that did not exist, fell through to ``google.genai.Client()``,
and that SDK read a retired ``GEMINI_API_KEY`` from the environment. Google
answered ``API_KEY_INVALID`` on every run since 2026-07-31 and the node
skipped itself each time. There is no discovery and no SDK fallback now: the
provider is the one every other Gemini caller in this repository uses, or one
the caller injects.
"""

import logging
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from assemblyzero.core.errors import (
    RateLimitError,
    TimeoutError_ as TypedTimeoutError,
    classify_gemini_error,
)
from assemblyzero.core.text_sanitizer import strip_emoji

from assemblyzero.workflows.testing.adversarial_prompts import (
    build_adversarial_analysis_prompt,
    build_adversarial_system_prompt,
)
from assemblyzero.workflows.testing.knowledge.adversarial_patterns import (
    get_adversarial_patterns,
)

logger = logging.getLogger(__name__)


# Issue #546: GeminiQuotaExhaustedError and GeminiTimeoutError are now
# aliases for the unified error hierarchy.  Kept as names for backward
# compatibility with existing except-clauses in callers.
GeminiQuotaExhaustedError = RateLimitError
GeminiTimeoutError = TypedTimeoutError


class GeminiModelDowngradeError(Exception):
    """Raised when Gemini silently downgrades from Pro to Flash."""

    pass


class ForbiddenModelError(Exception):
    """Raised when the model this call would REQUEST is not permitted.

    Distinct from GeminiModelDowngradeError, which is about what came back.
    Both checks are needed and neither substitutes for the other: a call can
    request a forbidden model and a call can be answered by one.
    """


#: #2286: the alias, not an identifier. Three call sites previously spelled out
#: `gemini-2.5-pro-preview-05-06` -- a dated preview whose validity was never
#: established, because the call died in local validation before #2281 and at
#: authentication after it. Naming a tier instead means `MODEL_MAP` supersession
#: notes and `FORBIDDEN_MODELS` both reach this path, and a fleet-wide migration
#: cannot miss it.
ADVERSARIAL_MODEL_ALIAS = "3.1-pro"

#: #2926: the spec the node hands to ``get_provider``. Its model half is the
#: alias ``resolve_adversarial_model`` checks against FORBIDDEN_MODELS, so the
#: request that is validated and the request that is sent cannot differ.
ADVERSARIAL_PROVIDER_SPEC = f"gemini:{ADVERSARIAL_MODEL_ALIAS}"


def resolve_adversarial_model() -> str:
    """The model this call will request, resolved and checked.

    Two things the old call site did not do. The alias goes through the same
    map every other Gemini caller uses, so a retired preview remaps rather than
    404s. And the result is checked against FORBIDDEN_MODELS *before* the
    request, where the existing `verify_model_is_pro` only inspects the reply.

    Raises:
        ForbiddenModelError: if the resolved identifier is forbidden.
    """
    from assemblyzero.core.config import FORBIDDEN_MODELS
    from assemblyzero.core.llm_provider import GeminiProvider

    alias = ADVERSARIAL_MODEL_ALIAS.lower()
    model_id = GeminiProvider.MODEL_MAP.get(alias)
    if model_id is None:
        valid = ", ".join(sorted(GeminiProvider.MODEL_MAP))
        raise ForbiddenModelError(
            f"Adversarial model alias {alias!r} is not in the selection map. "
            f"Valid aliases: {valid}"
        )

    # Exact match, then family. FORBIDDEN_MODELS carries both specific ids
    # ("gemini-3-pro") and family names ("gemini-flash", "gemini-lite"), and a
    # family entry is only meaningful as a substring.
    lowered = model_id.lower()
    for forbidden in FORBIDDEN_MODELS:
        entry = forbidden.lower()
        if lowered == entry or entry in lowered:
            raise ForbiddenModelError(
                f"Adversarial alias {alias!r} resolves to {model_id!r}, which "
                f"is forbidden by FORBIDDEN_MODELS entry {forbidden!r}"
            )

    # FORBIDDEN_MODELS does not catch every Flash: its entries are
    # `gemini-flash` and `gemini-2.5-flash`, and neither is a substring of
    # `gemini-3.1-flash-preview`, so a 3.1-line Flash passes the list (#2374).
    # `verify_model_is_pro` right below rejects any "flash" in the RESPONSE, so
    # without this the request gate would be looser than the response gate and
    # this call could ask for a model its own reply check would then refuse.
    # The two ends of one call must agree; the list's gap is #2374's to close.
    for tier in ("flash", "lite"):
        if tier in lowered:
            raise ForbiddenModelError(
                f"Adversarial alias {alias!r} resolves to {model_id!r}, a "
                f"{tier} tier. Governance calls run on Pro; verify_model_is_pro "
                f"would reject this model's own response."
            )
    return model_id


class AdversarialGeminiClient:
    """Wrapper around the project's existing GeminiProvider for adversarial test generation.

    This module encapsulates the adversarial-specific invocation logic
    (system prompt, no-mock constraint, timeout handling) while delegating
    actual Gemini API communication to the existing provider infrastructure.
    """

    def __init__(self, provider: Any | None = None) -> None:
        """Wrap ``provider``, or build the sanctioned one.

        Args:
            provider: An ``LLMProvider`` (the sanctioned shape), or a callable
                ``(system_prompt=..., user_prompt=...) -> (text, metadata)``
                standing in for one in tests. ``None`` builds
                ``get_provider(ADVERSARIAL_PROVIDER_SPEC)`` after
                ``resolve_adversarial_model`` has checked the alias, so a
                forbidden tier is refused before any transport exists.

        Raises:
            ForbiddenModelError: if the alias resolves to a forbidden model.
            ValueError: from ``get_provider`` if the spec cannot be built.
        """
        if provider is not None:
            self._provider = provider
            return
        resolve_adversarial_model()
        from assemblyzero.core.llm_provider import get_provider

        self._provider = get_provider(ADVERSARIAL_PROVIDER_SPEC)

    def verify_model_is_pro(self, response_metadata: dict) -> bool:
        """Check response metadata to confirm Gemini Pro was used.

        Args:
            response_metadata: Dictionary containing model info from the API response.

        Returns:
            True if Pro model confirmed.

        Raises:
            GeminiModelDowngradeError: If Flash model detected or no model info present.
        """
        model_name = response_metadata.get("model", "")

        if not model_name:
            raise GeminiModelDowngradeError(
                "No model information in response metadata"
            )

        model_lower = model_name.lower()

        if "flash" in model_lower:
            raise GeminiModelDowngradeError(
                f"Expected Gemini Pro but received {model_name}"
            )

        if "pro" in model_lower:
            logger.info("Gemini Pro model confirmed: %s", model_name)
            return True

        # Unknown model — warn but don't block
        logger.warning(
            "Unknown Gemini model variant: %s. Proceeding cautiously.", model_name
        )
        return True

    def generate_adversarial_tests(
        self,
        implementation_code: str,
        lld_content: str,
        existing_tests: str,
        adversarial_patterns: list[str] | None = None,
        timeout: int = 120,
    ) -> str:
        """Invoke Gemini Pro for adversarial test generation.

        Builds the adversarial prompt, delegates to the underlying provider,
        and applies model-downgrade detection.

        Args:
            implementation_code: Source code of the implementation under test.
            lld_content: LLD markdown content.
            existing_tests: Existing test code for deduplication.
            adversarial_patterns: Optional list of patterns. Uses defaults if None.
            timeout: Maximum seconds to wait for response.

        Returns:
            Raw JSON string response from Gemini.

        Raises:
            GeminiQuotaExhaustedError: If 429 or quota message detected.
            GeminiModelDowngradeError: If Flash detected instead of Pro.
            GeminiTimeoutError: If response exceeds timeout.
        """
        if adversarial_patterns is None:
            adversarial_patterns = get_adversarial_patterns()

        system_prompt = build_adversarial_system_prompt()
        user_prompt = build_adversarial_analysis_prompt(
            implementation_code=implementation_code,
            lld_content=lld_content,
            existing_tests=existing_tests,
            adversarial_patterns=adversarial_patterns,
        )

        logger.info(
            "Invoking Gemini Pro for adversarial analysis (timeout=%ds)", timeout
        )

        try:
            raw_response, metadata = self._invoke_provider(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                timeout=timeout,
            )
        except (GeminiQuotaExhaustedError, GeminiTimeoutError):
            # #2926: already typed by the sanctioned path, with the transport's
            # own message. Re-wrapping below would rename a reported failure
            # to "exceeded {timeout}s timeout", which is the misreading that
            # hid a dead API key for two months.
            raise
        except TimeoutError as e:
            raise GeminiTimeoutError(
                f"Gemini API response exceeded {timeout}s timeout",
                provider="gemini",
            ) from e
        except TypeError:
            raise  # Unsupported provider type — propagate as-is
        except PydanticValidationError:
            # A validation error is raised locally, before anything is sent, so
            # it can only mean this repo built the request wrong. Classifying it
            # below would rename it to a timeout with `status=None` -- and both
            # consumers treat a timeout as "Gemini was unavailable": the
            # integration test skips, and the adversarial node records a benign
            # skip reason and proceeds. That is a false all-clear, and it hid
            # #2281 (an invalid `timeout` kwarg) through every roll that ran
            # this node. Propagate as-is, like the TypeError above (#2282).
            raise
        except Exception as e:
            # Issue #546: Classify through the typed error hierarchy
            classified = classify_gemini_error(e)
            if isinstance(classified, RateLimitError):
                raise GeminiQuotaExhaustedError(
                    f"Gemini quota exhausted: {e}", provider="gemini",
                ) from e
            raise GeminiTimeoutError(
                f"Gemini API error (status={classified.status_code}): {e}",
                provider="gemini",
            ) from e

        # Check for quota exhaustion in response or exception
        if self._is_quota_error(raw_response, metadata):
            raise GeminiQuotaExhaustedError(
                "Gemini API quota exhausted (HTTP 429)"
            )

        # Verify model is Pro (not silently downgraded to Flash)
        self.verify_model_is_pro(metadata)

        logger.info(
            "Gemini adversarial analysis received (%d chars)", len(raw_response)
        )
        return raw_response

    def _invoke_provider(
        self,
        system_prompt: str,
        user_prompt: str,
        timeout: int,
    ) -> tuple[str, dict]:
        """Invoke the underlying provider and return (response_text, metadata).

        Two shapes, and only two (#2926). The ``google.genai`` and LangChain
        strategies that used to sit here were the failed path: a raw SDK
        constructed around the sanctioned client, reading a key from the
        environment that nothing sanctioned reads.

        Returns:
            Tuple of (raw_response_text, response_metadata_dict).

        Raises:
            GeminiQuotaExhaustedError: the transport reported a rate limit.
            GeminiTimeoutError: the transport reported any other failure. The
                message carries the transport's own error text and status,
                so a credential failure reads as one rather than as a timeout.
        """
        provider = self._provider
        from assemblyzero.core.llm_provider import LLMProvider

        # The sanctioned shape: an LLMProvider, which for a gemini: spec is
        # GeminiClient over agy (ADR 0220), with its own retries and rotation.
        if isinstance(provider, LLMProvider):
            result = provider.invoke(
                system_prompt=system_prompt,
                content=user_prompt,
                timeout_seconds=timeout,
            )
            if not result.success:
                if result.rate_limited:
                    raise GeminiQuotaExhaustedError(
                        f"Gemini quota exhausted: {result.error_message}",
                        provider="gemini",
                    )
                raise GeminiTimeoutError(
                    f"Gemini API error (status={result.status_code}): "
                    f"{result.error_message}",
                    provider="gemini",
                )
            # Issue #527: Strip emojis from Gemini response
            text = strip_emoji(result.response or "")
            return text, {"model": result.model_used}

        # A plain callable, standing in for the transport in tests.
        if callable(provider):
            result = provider(system_prompt=system_prompt, user_prompt=user_prompt)
            if isinstance(result, tuple):
                return result[0], result[1]
            return str(result), {"model": "unknown"}

        raise TypeError(
            f"Unsupported Gemini provider type: {type(provider).__name__}. "
            "Provider must be an LLMProvider or a callable."
        )

    def _is_quota_error(self, response: str | None, metadata: dict) -> bool:
        """Check if the response indicates quota exhaustion.

        Args:
            response: Raw response text.
            metadata: Response metadata.

        Returns:
            True if quota exhaustion detected.
        """
        status = metadata.get("status_code", 0)
        if status == 429:
            return True

        if not response:
            return False

        quota_indicators = [
            "429",
            "quota",
            "rate limit",
            "resource exhausted",
            "resource_exhausted",
        ]

        response_lower = response.lower()
        for indicator in quota_indicators:
            if indicator.lower() in response_lower:
                return True

        return False