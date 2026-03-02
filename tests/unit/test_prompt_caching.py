"""Tests for Issue #488: Anthropic prompt caching directives.

Verifies that AnthropicProvider.invoke() sends cache_control directives
on system prompt and user content blocks.
"""

from unittest.mock import MagicMock, patch

import pytest


class TestAnthropicCacheControl:
    """Verify cache_control directives are sent in Anthropic API calls."""

    @patch("assemblyzero.core.llm_provider._load_anthropic_api_key")
    def test_anthropic_sends_cache_control_system(self, mock_load_key):
        """System prompt should be sent as a structured block with cache_control."""
        mock_load_key.return_value = "sk-test-key"

        from assemblyzero.core.llm_provider import AnthropicProvider

        provider = AnthropicProvider(model="haiku")

        # Mock the anthropic client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="response text")]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_response.usage.cache_read_input_tokens = 0
        mock_response.usage.cache_creation_input_tokens = 0
        # Issue #541: mock streaming context manager
        mock_stream = MagicMock()
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=False)
        mock_stream.text_stream = ["response text"]
        mock_stream.get_final_message.return_value = mock_response
        mock_client.messages.stream.return_value = mock_stream
        provider._client = mock_client

        provider.invoke(
            system_prompt="You are a helpful assistant.",
            content="Hello world",
        )

        # Verify the system prompt was sent as structured block
        call_kwargs = mock_client.messages.stream.call_args
        system_arg = call_kwargs.kwargs.get("system") or call_kwargs[1].get("system")

        assert isinstance(system_arg, list), "system should be a list of blocks"
        assert len(system_arg) == 1
        assert system_arg[0]["type"] == "text"
        assert system_arg[0]["text"] == "You are a helpful assistant."
        assert system_arg[0]["cache_control"] == {"type": "ephemeral"}

    @patch("assemblyzero.core.llm_provider._load_anthropic_api_key")
    def test_anthropic_sends_cache_control_content(self, mock_load_key):
        """User content should be sent as a structured block with cache_control."""
        mock_load_key.return_value = "sk-test-key"

        from assemblyzero.core.llm_provider import AnthropicProvider

        provider = AnthropicProvider(model="haiku")

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="response text")]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_response.usage.cache_read_input_tokens = 0
        mock_response.usage.cache_creation_input_tokens = 0
        # Issue #541: mock streaming context manager
        mock_stream = MagicMock()
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=False)
        mock_stream.text_stream = ["response text"]
        mock_stream.get_final_message.return_value = mock_response
        mock_client.messages.stream.return_value = mock_stream
        provider._client = mock_client

        provider.invoke(
            system_prompt="System prompt",
            content="User content here",
        )

        call_kwargs = mock_client.messages.stream.call_args
        messages_arg = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")

        assert len(messages_arg) == 1
        msg = messages_arg[0]
        assert msg["role"] == "user"
        assert isinstance(msg["content"], list), "content should be a list of blocks"
        assert len(msg["content"]) == 1
        assert msg["content"][0]["type"] == "text"
        assert msg["content"][0]["text"] == "User content here"
        assert msg["content"][0]["cache_control"] == {"type": "ephemeral"}

    @patch("assemblyzero.core.llm_provider._load_anthropic_api_key")
    def test_cache_metrics_in_result(self, mock_load_key):
        """Cache read/creation tokens should be captured in LLMCallResult."""
        mock_load_key.return_value = "sk-test-key"

        from assemblyzero.core.llm_provider import AnthropicProvider

        provider = AnthropicProvider(model="haiku")

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="response text")]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_response.usage.cache_read_input_tokens = 800
        mock_response.usage.cache_creation_input_tokens = 200
        # Issue #541: mock streaming context manager
        mock_stream = MagicMock()
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=False)
        mock_stream.text_stream = ["response text"]
        mock_stream.get_final_message.return_value = mock_response
        mock_client.messages.stream.return_value = mock_stream
        provider._client = mock_client

        result = provider.invoke(
            system_prompt="System",
            content="Content",
        )

        assert result.success
        assert result.cache_read_tokens == 800
        assert result.cache_creation_tokens == 200
