"""Tests for scout workflow budget module.

Tests for: assemblyzero/workflows/scout/budget.py
Target coverage: >95%
"""

from unittest.mock import patch

import pytest

from assemblyzero.workflows.scout.budget import (
    SAFETY_BUFFER,
    adaptive_truncate,
    check_and_update_budget,
    estimate_tokens,
)


class TestEstimateTokens:
    """Tests for estimate_tokens function."""

    def test_estimate_simple_text(self):
        """Test token estimation for simple text."""
        result = estimate_tokens("Hello, world!")
        assert result > 0
        # tiktoken should give reasonable estimate (3-5 tokens)
        assert result < 10

    def test_estimate_empty_string(self):
        """Test token estimation for empty string."""
        result = estimate_tokens("")
        assert result == 0

    def test_estimate_long_text(self):
        """Test token estimation for longer text."""
        text = "This is a longer piece of text that should have more tokens. " * 10
        result = estimate_tokens(text)
        # Should scale with text length
        assert result > 50

    def test_estimate_with_special_characters(self):
        """Test token estimation with special characters."""
        text = "Hello! @#$%^&*() 日本語 emoji: 🎉"
        result = estimate_tokens(text)
        assert result > 0

    def test_fallback_on_encoding_error(self):
        """Test fallback estimation when tiktoken fails."""
        # Mock tiktoken to raise an exception
        with patch("assemblyzero.workflows.scout.budget.tiktoken.get_encoding") as mock_enc:
            mock_enc.side_effect = Exception("Encoding error")
            text = "x" * 100
            result = estimate_tokens(text)

        # Fallback: len(text) // 4 = 100 // 4 = 25
        assert result == 25


class TestCheckAndUpdateBudget:
    """Tests for check_and_update_budget function."""

    def test_within_budget(self):
        """Test when new text is within budget."""
        current_usage = 100
        new_text = "Hello"
        limit = 1000

        new_usage, is_within = check_and_update_budget(current_usage, new_text, limit)

        assert is_within is True
        assert new_usage > current_usage

    def test_exceeds_budget(self):
        """Test when new text exceeds budget."""
        current_usage = 900
        new_text = "x" * 1000  # Lots of text
        limit = 1000

        new_usage, is_within = check_and_update_budget(current_usage, new_text, limit)

        assert is_within is False
        assert new_usage > limit

    def test_exactly_at_limit(self):
        """Test when usage is exactly at limit."""
        current_usage = 1000
        new_text = ""
        limit = 1000

        new_usage, is_within = check_and_update_budget(current_usage, new_text, limit)

        # Empty text adds 0 tokens
        assert is_within is True
        assert new_usage == current_usage

    def test_safety_buffer_applied(self):
        """Test that safety buffer is applied."""
        current_usage = 0
        new_text = "test"
        limit = 10000

        new_usage, _ = check_and_update_budget(current_usage, new_text, limit)

        # The buffered tokens should be greater than raw estimate
        raw_estimate = estimate_tokens(new_text)
        assert new_usage == int(raw_estimate * SAFETY_BUFFER)

    def test_zero_current_usage(self):
        """Test starting from zero usage."""
        new_usage, is_within = check_and_update_budget(0, "Hello", 1000)

        assert new_usage > 0
        assert is_within is True


class TestAdaptiveTruncate:
    """Tests for adaptive_truncate function."""

    def test_truncate_half(self):
        """Test truncation to 50%."""
        text = "0123456789"
        result = adaptive_truncate(text, reduction_factor=0.5)

        assert len(result) == 5
        assert result == "01234"

    def test_truncate_quarter(self):
        """Test truncation to 25%."""
        text = "0123456789ABCDEF"
        result = adaptive_truncate(text, reduction_factor=0.25)

        assert len(result) == 4
        assert result == "0123"

    def test_truncate_empty_string(self):
        """Test truncation of empty string."""
        result = adaptive_truncate("", reduction_factor=0.5)
        assert result == ""

    def test_truncate_preserves_beginning(self):
        """Test that truncation preserves the beginning of text."""
        text = "Important beginning... less important end"
        result = adaptive_truncate(text, reduction_factor=0.5)

        assert result.startswith("Important")
        assert "end" not in result

    def test_invalid_reduction_factor_zero(self):
        """Test that reduction_factor=0 raises error."""
        with pytest.raises(ValueError) as exc_info:
            adaptive_truncate("test", reduction_factor=0)
        assert "between 0 and 1" in str(exc_info.value)

    def test_invalid_reduction_factor_one(self):
        """Test that reduction_factor=1 raises error."""
        with pytest.raises(ValueError) as exc_info:
            adaptive_truncate("test", reduction_factor=1)
        assert "between 0 and 1" in str(exc_info.value)

    def test_invalid_reduction_factor_negative(self):
        """Test that negative reduction_factor raises error."""
        with pytest.raises(ValueError) as exc_info:
            adaptive_truncate("test", reduction_factor=-0.5)
        assert "between 0 and 1" in str(exc_info.value)

    def test_invalid_reduction_factor_greater_than_one(self):
        """Test that reduction_factor > 1 raises error."""
        with pytest.raises(ValueError) as exc_info:
            adaptive_truncate("test", reduction_factor=1.5)
        assert "between 0 and 1" in str(exc_info.value)

    def test_small_reduction_factor(self):
        """Test very small reduction factor."""
        text = "0123456789"
        result = adaptive_truncate(text, reduction_factor=0.1)

        assert len(result) == 1
        assert result == "0"


class TestSafetyBuffer:
    """Tests for SAFETY_BUFFER constant."""

    def test_safety_buffer_value(self):
        """Test that safety buffer has correct value."""
        assert SAFETY_BUFFER == 1.2

    def test_safety_buffer_is_greater_than_one(self):
        """Test that safety buffer increases token count."""
        assert SAFETY_BUFFER > 1.0
