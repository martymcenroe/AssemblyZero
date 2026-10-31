"""The requirements step budget under standard 0034 (#3585).

Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md (base ``79e18ad1``), for
``assemblyzero/workflows/requirements/step_budget.py``. A cap that is not a
number raises naming it, where it silently became 3. A spent step budget is an
ERROR line and an alert, since the HALT node never runs on that path; the
returned ``error_message`` still makes the run exit 1.
"""
from __future__ import annotations

import logging

import pytest

from assemblyzero.workflows.requirements import step_budget


@pytest.mark.parametrize("bad", ["three", None, "1.5"])
def test_83_a_cap_that_is_not_a_number_raises(bad):
    with pytest.raises(ValueError, match="max_iterations") as raised:
        step_budget.recursion_limit(max_iterations=bad, max_finalize_repairs=0)
    assert repr(bad) in str(raised.value)


def test_a_numeric_cap_still_sizes_the_budget():
    """Kept: the derived budget the module exists for."""
    assert step_budget.recursion_limit(3, 0) == step_budget.recursion_limit("3", 0)


def test_159_a_spent_budget_is_loud_and_alerts(operator_alerts, caplog):
    from langgraph.errors import GraphRecursionError

    class _Spends:
        def stream(self, state, config, stream_mode):
            yield {"verdict_count": 4, "issue_number": 42, "target_repo": "/repo"}
            raise GraphRecursionError("recursion limit reached")

    with caplog.at_level(logging.ERROR, logger=step_budget.__name__):
        result = step_budget.invoke_with_budget(
            _Spends(), {"issue_number": 42}, stage="lld", max_iterations=3,
        )
    assert result["error_message"].startswith("BLOCKED: the lld stage ran out")
    assert any(r.levelno == logging.ERROR for r in caplog.records)
    assert len(operator_alerts) == 1
    assert operator_alerts[0]["issue"] == 42
    assert operator_alerts[0]["repo"] == "/repo"
    assert "graph step" in operator_alerts[0]["what"]


def test_a_run_that_fits_its_budget_alerts_nobody(operator_alerts):
    class _Fits:
        def stream(self, state, config, stream_mode):
            yield {"issue_number": 42, "error_message": ""}

    result = step_budget.invoke_with_budget(_Fits(), {}, stage="lld")
    assert not result.get("error_message")
    assert operator_alerts == []
