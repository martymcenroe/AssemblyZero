"""An unpriced model's cost is None, never a free 0.0 (ADR 0236, #3585).

``estimate_cost`` returned 0.0 for a model with no entry in the table, with a
WARNING, so the call record of an unpriced model read exactly like a call that
cost nothing. It now returns None, which the record field
(``LLMOutputMetadata.cost_usd_estimate: Optional[float]``) already allows and a
sum cannot mistake for zero. This is the ledger's second option, "return None
that callers must handle"; the one caller, ``InstrumentedCall``, stores the
value as given.

One test per ledger site, named for the line the ledger gives at ``79e18ad1``.
"""

from __future__ import annotations

import pytest

from assemblyzero.telemetry.cost import estimate_cost


@pytest.mark.parametrize("model", ["unknown-model-xyz", "gemini-2.5-pro-preview-05-06"])
def test_73_an_unpriced_model_has_no_cost_rather_than_zero(model, operator_alerts):
    assert estimate_cost(model, 1000, 500) is None


def test_73_a_sum_cannot_take_an_unpriced_cost_as_zero(operator_alerts):
    with pytest.raises(TypeError):
        sum([0.5, estimate_cost("unknown-model-xyz", 1, 1)])  # type: ignore[list-item]


def test_a_priced_model_still_costs(operator_alerts):
    assert abs(estimate_cost("claude-opus-4-5-20250514", 1000, 500) - 0.0525) < 1e-8


def test_a_priced_model_with_no_tokens_costs_zero(operator_alerts):
    """Zero is still a real answer, for a priced model that used nothing."""
    assert estimate_cost("claude-haiku-4-5-20251001", 0, 0) == 0.0


def test_the_instrumented_record_carries_none(operator_alerts):
    from assemblyzero.telemetry.instrumentation import InstrumentedCall

    written = []

    class _Store:
        def write(self, record):
            written.append(record)

    with InstrumentedCall(_Store(), {"model_requested": "unknown-model-xyz"}) as call:
        call.record_outputs({"model_used": "unknown-model-xyz", "input_tokens": 5})

    assert written[0]["outputs"]["cost_usd_estimate"] is None
