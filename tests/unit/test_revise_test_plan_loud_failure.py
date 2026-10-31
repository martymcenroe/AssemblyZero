"""revise_test_plan.py (N1.5) under standard 0034, one test per sweep site.

Ledger 0908 found N1.5's four failures compliant: each records a reason
that ``route_after_revision`` sends to HALT, which alerts. They are pinned
here, and each now also writes an ERROR line on stderr where it happens. No
test makes a model call: the provider and the retry wrapper are stand-ins.
Line numbers in the names are ledger 0908's, at its base ``79e18ad1``.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from assemblyzero.workflows.testing.graph import route_after_revision
from assemblyzero.workflows.testing.nodes.revise_test_plan import (
    MAX_REVISION_CYCLES,
    revise_test_plan,
)

TWO_ROWS = (
    "| ID | Scenario | Type | Requirements |\n|---|---|---|---|\n"
    "| T001 | adds | unit | REQ-1 |\n| T002 | subtracts | unit | REQ-2 |\n"
)
ONE_ROW = (
    "| ID | Scenario | Type | Requirements |\n|---|---|---|---|\n"
    "| T001 | adds | unit | REQ-1 |\n"
)


def _state(**overrides) -> dict:
    state = {
        "requirements": ["REQ-1: add", "REQ-2: subtract"],
        "lld_content": "# LLD\n\nadd and subtract",
        "gemini_feedback": "REQ-2 has no scenario",
        "test_plan_revision_count": 0,
        "config_reviewer": "gemini:3.8-flash-high",
    }
    state.update(overrides)
    return state


def _result(response: str, *, success: bool = True, error: str | None = None):
    result = MagicMock()
    result.success = success
    result.response = response
    result.error_message = error
    return result


@pytest.fixture
def revisor(monkeypatch):
    """Stand-ins for the provider and the retry wrapper. Set ``.returns``."""
    box = MagicMock()
    box.returns = _result(TWO_ROWS)
    monkeypatch.setattr(
        "assemblyzero.core.llm_provider.get_provider", lambda *a, **k: MagicMock()
    )
    monkeypatch.setattr(
        "assemblyzero.utils.retry.with_retry", lambda fn, policy=None, **k: box.returns
    )
    return box


def _halts(state: dict, result: dict) -> bool:
    return route_after_revision({**state, **result}) == "HALT"


def test_226_no_requirements_halts(revisor, capsys):
    state = _state(requirements=[])
    result = revise_test_plan(state)

    assert result["error_message"].startswith("Test plan revision blocked: no requirements")
    assert _halts(state, result)
    assert "ERROR [N1.5]" in capsys.readouterr().err


def test_246_an_invalid_revisor_spec_halts(revisor, capsys, monkeypatch):
    def refuse(state, seat):
        raise ValueError("unknown provider: nonsense")

    monkeypatch.setattr("assemblyzero.core.seats.resolve", refuse)
    state = _state()
    result = revise_test_plan(state)

    assert result["error_message"] == (
        "Test plan revision: invalid revisor spec: unknown provider: nonsense"
    )
    assert _halts(state, result)
    assert "ERROR [N1.5]" in capsys.readouterr().err


def test_266_a_failed_revision_call_halts(revisor, capsys):
    revisor.returns = _result("", success=False, error="agy exited 1: quota")
    state = _state()
    result = revise_test_plan(state)

    assert result["error_message"] == "Test plan revision LLM call failed: agy exited 1: quota"
    assert _halts(state, result)
    assert "ERROR [N1.5]" in capsys.readouterr().err


def test_307_a_short_plan_at_the_cap_halts_on_the_budget(revisor, capsys):
    revisor.returns = _result(ONE_ROW)
    state = _state(test_plan_revision_count=MAX_REVISION_CYCLES - 1)
    result = revise_test_plan(state)

    assert result["error_message"].startswith("Test plan revision budget spent")
    assert "1/2" in result["error_message"]
    assert _halts(state, result)
    assert "ERROR [N1.5]" in capsys.readouterr().err


def test_a_short_plan_under_the_cap_asks_again_without_a_reason(revisor, capsys):
    """Kept (#2775): under the cap the loop runs, so no reason is recorded."""
    revisor.returns = _result(ONE_ROW)
    state = _state()
    result = revise_test_plan(state)

    assert result["error_message"] == ""
    assert route_after_revision({**state, **result}) == "N1_review_test_plan"
    assert "ERROR" not in capsys.readouterr().err


def test_a_complete_revision_clears_the_block(revisor):
    """Kept: a revision covering every requirement goes back to N1."""
    state = _state()
    result = revise_test_plan(state)

    assert result["test_plan_status"] == "PENDING"
    assert len(result["test_scenarios"]) == 2
    assert route_after_revision({**state, **result}) == "N1_review_test_plan"
