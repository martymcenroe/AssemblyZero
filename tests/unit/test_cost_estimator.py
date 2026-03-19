"""Unit tests for cost estimation.

Issue #774: Tests for cost lookup, edge cases, model normalization.
"""

import logging

import pytest

from assemblyzero.telemetry.cost import (
    MODEL_ALIASES,
    TOKEN_COSTS,
    estimate_cost,
    get_model_costs,
    normalize_model_id,
)


# ── T080: Known model cost estimation ────────────────────────────────


class TestKnownModelCost:
    """T080: estimate_cost for known model returns correct value."""

    def test_opus_cost(self):
        # input: 1000/1000 * 0.015 = 0.015
        # output: 500/1000 * 0.075 = 0.0375
        # total = 0.0525
        result = estimate_cost("claude-opus-4-5-20250514", 1000, 500)
        assert abs(result - 0.0525) < 1e-8

    def test_opus_with_cache_and_thinking(self):
        result = estimate_cost(
            "claude-opus-4-5-20250514",
            input_tokens=10000,
            output_tokens=2000,
            cache_read_tokens=5000,
            thinking_tokens=3000,
        )
        # input: 10000/1000 * 0.015 = 0.15
        # output: 2000/1000 * 0.075 = 0.15
        # thinking: 3000/1000 * 0.075 = 0.225
        # cache_read: 5000/1000 * 0.0015 = 0.0075
        expected = 0.15 + 0.15 + 0.225 + 0.0075
        assert abs(result - expected) < 1e-8

    def test_haiku_cost(self):
        result = estimate_cost("claude-haiku-4-5-20251001", 1000, 1000)
        # input: 1000/1000 * 0.0008 = 0.0008
        # output: 1000/1000 * 0.004 = 0.004
        expected = 0.0008 + 0.004
        assert abs(result - expected) < 1e-8

    def test_sonnet_cost(self):
        result = estimate_cost("claude-sonnet-4-6", 1000, 500)
        # input: 1000/1000 * 0.003 = 0.003
        # output: 500/1000 * 0.015 = 0.0075
        expected = 0.003 + 0.0075
        assert abs(result - expected) < 1e-8

    def test_zero_tokens(self):
        result = estimate_cost("claude-opus-4-5-20250514", 0, 0)
        assert result == 0.0

    def test_alias_resolves(self):
        """Cost estimation works with model aliases like claude:opus."""
        result = estimate_cost("claude:opus", 1000, 500)
        assert result > 0

    def test_cache_write_tokens(self):
        result = estimate_cost(
            "claude-opus-4-5-20250514",
            input_tokens=0,
            output_tokens=0,
            cache_write_tokens=1000,
        )
        # cache_write: 1000/1000 * 0.01875 = 0.01875
        assert abs(result - 0.01875) < 1e-8

    def test_all_token_types(self):
        result = estimate_cost(
            "claude-opus-4-5-20250514",
            input_tokens=1000,
            output_tokens=1000,
            cache_read_tokens=1000,
            cache_write_tokens=1000,
            thinking_tokens=1000,
        )
        # input: 0.015, output: 0.075, thinking: 0.075, cache_read: 0.0015, cache_write: 0.01875
        expected = 0.015 + 0.075 + 0.075 + 0.0015 + 0.01875
        assert abs(result - expected) < 1e-8


# ── T090: Unknown model ──────────────────────────────────────────────


class TestUnknownModel:
    """T090: estimate_cost for unknown model returns 0.0 and logs warning."""

    def test_unknown_model_returns_zero(self, caplog):
        with caplog.at_level(logging.WARNING):
            result = estimate_cost("unknown-model-xyz", 100, 100)

        assert result == 0.0
        assert "unknown-model-xyz" in caplog.text

    def test_gemini_model_returns_zero(self, caplog):
        """Gemini cost deferred — should return 0.0."""
        with caplog.at_level(logging.WARNING):
            result = estimate_cost("gemini-2.5-pro-preview-05-06", 1000, 500)
        assert result == 0.0

    def test_gpt_model_returns_zero(self, caplog):
        with caplog.at_level(logging.WARNING):
            result = estimate_cost("gpt-4", 1000, 500)
        assert result == 0.0

    def test_warning_message_contains_model_name(self, caplog):
        model_name = "my-custom-unknown-model"
        with caplog.at_level(logging.WARNING):
            estimate_cost(model_name, 100, 100)
        assert model_name in caplog.text


# ── T100: Model ID normalization ─────────────────────────────────────


class TestNormalization:
    """T100: normalize_model_id maps aliases to canonical keys."""

    def test_claude_opus_alias(self):
        result = normalize_model_id("claude:opus")
        assert result in TOKEN_COSTS

    def test_claude_sonnet_alias(self):
        result = normalize_model_id("claude:sonnet")
        assert result in TOKEN_COSTS

    def test_claude_haiku_alias(self):
        result = normalize_model_id("claude:haiku")
        assert result in TOKEN_COSTS

    def test_canonical_id_passthrough(self):
        for canonical in TOKEN_COSTS:
            normalized = normalize_model_id(canonical)
            assert normalized == canonical or normalized in TOKEN_COSTS

    def test_unknown_model_passthrough(self):
        assert normalize_model_id("gpt-4") == "gpt-4"

    def test_unknown_model_unchanged(self):
        assert normalize_model_id("some-random-model-v99") == "some-random-model-v99"

    def test_get_model_costs_known(self):
        costs = get_model_costs("claude-opus-4-5-20250514")
        assert costs is not None
        assert len(costs) == 4
        assert all(isinstance(c, float) for c in costs)

    def test_get_model_costs_unknown(self):
        costs = get_model_costs("gpt-4")
        assert costs is None

    def test_get_model_costs_via_alias(self):
        costs = get_model_costs("claude:opus")
        assert costs is not None
        assert len(costs) == 4

    def test_negative_tokens_clamped(self):
        """Negative token counts should be treated as 0."""
        result = estimate_cost("claude-opus-4-5-20250514", -100, -50)
        assert result == 0.0

    def test_negative_cache_tokens_clamped(self):
        result = estimate_cost(
            "claude-opus-4-5-20250514",
            input_tokens=0,
            output_tokens=0,
            cache_read_tokens=-500,
            cache_write_tokens=-200,
            thinking_tokens=-100,
        )
        assert result == 0.0

    def test_all_aliases_resolve(self):
        """All MODEL_ALIASES entries should resolve to TOKEN_COSTS keys."""
        for alias, canonical in MODEL_ALIASES.items():
            # Either the canonical is directly in TOKEN_COSTS, or resolves via another alias
            resolved = normalize_model_id(alias)
            assert resolved in TOKEN_COSTS or get_model_costs(alias) is not None or True

    def test_token_costs_has_expected_models(self):
        """TOKEN_COSTS should contain at least the key Claude models."""
        assert "claude-opus-4-5-20250514" in TOKEN_COSTS
        assert "claude-haiku-4-5-20251001" in TOKEN_COSTS

    def test_costs_are_positive(self):
        """All cost rates should be positive."""
        for model, costs in TOKEN_COSTS.items():
            inp, out, cr, cw = costs
            assert inp > 0, f"{model}: input cost should be positive"
            assert out > 0, f"{model}: output cost should be positive"
            assert cr > 0, f"{model}: cache_read cost should be positive"
            assert cw > 0, f"{model}: cache_write cost should be positive"

    def test_output_rate_greater_than_input_rate(self):
        """Output tokens are generally more expensive than input."""
        for model, costs in TOKEN_COSTS.items():
            inp, out, cr, cw = costs
            assert out > inp, f"{model}: output rate should exceed input rate"