"""Every orchestrator stage has a runner, and a stage without one fails by name (#4529, #3737).

The integration fixture ``mock_all_stages`` stubbed every runner except
``visual``, the stage #2518 put between lld and spec. ``_run_stage_node``
returned ``{}`` for a stage with no runner, so the state never changed, the
router sent the graph back to the same node, and the run looped until
``GraphRecursionError``, which names no stage.

CI never saw it. Its integration step selects ``-m integration`` and
``tests/integration/test_orchestrator_graph.py`` carried no such marker, so only
a local full run collected the test (#3737). These tests sit in the unit tier,
which CI runs, and since #4756 so does that file, as
``tests/unit/test_orchestrator_graph.py``.
"""

from __future__ import annotations

import pytest

from assemblyzero.workflows.orchestrator import graph as g
from assemblyzero.workflows.orchestrator.stages import STAGE_RUNNERS
from assemblyzero.workflows.orchestrator.state import (
    STAGE_ORDER,
    StageResult,
    update_stage_result,
)


def _passing_runner(stage: str):
    def runner(state):
        return update_stage_result(
            state,
            stage,
            StageResult(
                status="passed",
                artifact_path=f"mock/{stage}",
                error_message="",
                duration_seconds=0.0,
                attempts=1,
            ),
        )

    return runner


def _start_state() -> dict:
    # No target_repo: _record_stage_entry then writes no convergence record.
    return {"current_stage": STAGE_ORDER[0], "config": {}, "stage_results": {}, "target_repo": ""}


def _invoke_with(runners: dict, monkeypatch) -> dict:
    monkeypatch.setattr(g, "STAGE_RUNNERS", runners)
    monkeypatch.setattr(g, "save_orchestration_state", lambda state: None)
    monkeypatch.setattr(g, "check_human_gate", lambda state, stage: True)
    app = g.create_orchestration_graph().compile()
    # Seven stages take nine steps. A limit of 50 makes a returning loop fail in
    # milliseconds as GraphRecursionError, which is not the error asserted below.
    return app.invoke(_start_state(), config={"recursion_limit": 50})


def test_the_runners_and_the_stage_order_name_the_same_stages():
    assert set(STAGE_RUNNERS) == set(STAGE_ORDER), (
        f"stages without a runner: {sorted(set(STAGE_ORDER) - set(STAGE_RUNNERS))}; "
        f"runners for no stage: {sorted(set(STAGE_RUNNERS) - set(STAGE_ORDER))}"
    )


def test_a_stage_with_no_runner_raises_naming_it(monkeypatch):
    monkeypatch.delitem(STAGE_RUNNERS, "visual")
    with pytest.raises(g.MissingStageRunnerError, match="Stage 'visual' has no runner"):
        g._run_stage_node({"current_stage": "visual", "config": {}, "stage_results": {}})


def test_done_still_returns_no_update():
    assert g._run_stage_node({"current_stage": "done"}) == {}


def test_the_graph_stops_on_a_missing_runner_instead_of_looping(monkeypatch):
    """#3737 T2: the looping condition, forced, fails fast with a named reason."""
    runners = {stage: _passing_runner(stage) for stage in STAGE_ORDER if stage != "visual"}
    with pytest.raises(g.MissingStageRunnerError, match="Stage 'visual' has no runner"):
        _invoke_with(runners, monkeypatch)


def test_the_same_graph_reaches_done_with_every_runner(monkeypatch):
    """The falsifier: with the one runner restored, the same graph finishes."""
    final = _invoke_with({stage: _passing_runner(stage) for stage in STAGE_ORDER}, monkeypatch)
    assert final["current_stage"] == "done"
    assert set(final["stage_results"]) == set(STAGE_ORDER)
