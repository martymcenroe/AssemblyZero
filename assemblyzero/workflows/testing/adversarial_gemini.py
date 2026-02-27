"""Wrapper module for Gemini adversarial invocation logic.

Issue #352: Multi-Model Adversarial Testing Node (Gemini vs Claude)

Encapsulates adversarial-specific invocation (system prompt, no-mock constraint,
timeout handling) while delegating actual API communication to the existing
provider infrastructure.
"""

import logging
from typing import Any

from assemblyzero.workflows.testing.adversarial_prompts import (
    build_adversarial_analysis_prompt,
    build_adversarial_system_prompt,
)
from assemblyzero.workflows.testing.knowledge.adversarial_patterns import (
    get_adversarial_patterns,
)

logger = logging.getLogger(__name__)


class GeminiQuotaExhaustedError(Exception):
    """Raised when Gemini API quota is exhausted (HTTP 429)."""

    pass


class GeminiModelDowngradeError(Exception):
    """Raised when Gemini silently downgrades from Pro to Flash."""

    pass


class GeminiTimeoutError(Exception):
    """Raised when Gemini API response exceeds timeout."""

    pass


class AdversarialGeminiClient:
    """Wrapper around the project's existing GeminiProvider for adversarial test generation.

    This module encapsulates the adversarial-specific invocation logic
    (system prompt, no-mock constraint, timeout handling) while delegating
    actual Gemini API communication to the existing provider infrastructure.
    """

    def __init__(self, provider: Any | None = None) -> None:
        """Initialize with an optional GeminiProvider instance.

        If provider is None, attempts to instantiate the default provider
        from assemblyzero.utils (auto-discovered at runtime).

        Args:
            provider: An object with a method to invoke Gemini. If None,
                      auto-discovers from assemblyzero.utils.
        """
        if provider is not None:
            self._provider = provider
        else:
            self._provider = self._discover_provider()

    def _discover_provider(self) -> Any:
        """Auto-discover and instantiate the Gemini provider from assemblyzero.utils.

        Searches for common provider class names in the utils package.

        Returns:
            An instantiated Gemini provider.

        Raises:
            ImportError: If no suitable Gemini provider found.
        """
        # Try known provider locations in order of likelihood
        provider_attempts = [
            ("assemblyzero.utils.gemini_provider", "GeminiProvider"),
            ("assemblyzero.utils.gemini", "GeminiProvider"),
            ("assemblyzero.utils.gemini_client", "GeminiClient"),
            ("assemblyzero.utils.providers", "GeminiProvider"),
        ]

        for module_path, class_name in provider_attempts:
            try:
                import importlib

                mod = importlib.import_module(module_path)
                cls = getattr(mod, class_name)
                logger.info(
                    "Discovered Gemini provider: %s.%s", module_path, class_name
                )
                return cls()
            except (ImportError, AttributeError):
                continue

        # Fallback: try google.genai directly
        try:
            from google import genai

            logger.info("Using google.genai directly as Gemini provider")
            return genai.Client()
        except ImportError:
            pass

        raise ImportError(
            "No Gemini provider found. Ensure google-genai or "
            "langchain-google-genai is installed and a provider class "
            "exists in assemblyzero.utils."
        )

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
        except TimeoutError as e:
            raise GeminiTimeoutError(
                f"Gemini API response exceeded {timeout}s timeout"
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

        This method abstracts over different provider APIs (google.genai,
        langchain-google-genai, etc.).

        Returns:
            Tuple of (raw_response_text, response_metadata_dict).
        """
        provider = self._provider

        # Strategy 1: google.genai Client
        if hasattr(provider, "models") and hasattr(
            getattr(provider, "models", None), "generate_content"
        ):
            response = provider.models.generate_content(
                model="gemini-2.5-pro-preview-05-06",
                contents=user_prompt,
                config={
                    "system_instruction": system_prompt,
                    "response_mime_type": "application/json",
                    "timeout": timeout,
                },
            )
            text = response.text if hasattr(response, "text") else str(response)
            metadata: dict[str, Any] = {}
            if hasattr(response, "model"):
                metadata["model"] = response.model
            elif hasattr(response, "candidates") and response.candidates:
                metadata["model"] = getattr(
                    response, "model_version", "gemini-2.5-pro-preview-05-06"
                )
            else:
                metadata["model"] = "gemini-2.5-pro-preview-05-06"
            return text, metadata

        # Strategy 2: LangChain-style provider with invoke()
        if hasattr(provider, "invoke"):
            from langchain_core.messages import HumanMessage, SystemMessage

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
            response = provider.invoke(messages)
            text = response.content if hasattr(response, "content") else str(response)
            metadata = getattr(response, "response_metadata", {})
            return text, metadata

        # Strategy 3: Generic callable
        if callable(provider):
            result = provider(system_prompt=system_prompt, user_prompt=user_prompt)
            if isinstance(result, tuple):
                return result[0], result[1]
            return str(result), {"model": "unknown"}

        raise TypeError(
            f"Unsupported Gemini provider type: {type(provider).__name__}. "
            "Provider must have 'models.generate_content', 'invoke', or be callable."
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