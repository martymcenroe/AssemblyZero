"""The standalone runners must show a stall while it stalls (Closes #2231).

#1367 asked for intra-stage heartbeat output during long model calls. It
shipped for orchestrator runs as `StageWatchdog` (#1886) and never reached the
standalone runners -- so `tools/run_requirements_workflow.py` and
`tools/run_implement_from_lld.py` emitted nothing during a multi-minute model
call.

Those are the two entry points the babysit protocol and the CLAUDE.md workflow
section actually tell an operator to run, which makes them the surface where
silence is most likely to be misread as a hang. Runbook 0952's doctrine -- a
stage past three times nominal is a fault rather than patience -- needs elapsed
time to be visible to be applied at all.

The wiring is what these pin. The watchdog's own behaviour is covered by
`tests/unit/test_stage_watchdog.py`; this file asserts the runners are under it
and that the observable contract still holds at the boundary.
"""

import ast
import time
from pathlib import Path

import pytest

from assemblyzero.core.stage_watchdog import StageWatchdog

TOOLS = Path(__file__).resolve().parents[2] / "tools"
RUNNERS = {
    "run_requirements_workflow.py": "lld / issue drafting",
    "run_implement_from_lld.py": "implementation",
}


def _source(name: str) -> str:
    return (TOOLS / name).read_text(encoding="utf-8")


def _guards_the_invocation(name: str) -> bool:
    """True when a `with StageWatchdog(...)` encloses the graph invocation.

    Asserted structurally rather than by substring: a runner that imported the
    watchdog and never entered it would pass a grep and emit nothing, which is
    the exact defect.
    """
    tree = ast.parse(_source(name))

    for node in ast.walk(tree):
        if not isinstance(node, ast.With):
            continue
        enters_watchdog = any(
            isinstance(item.context_expr, ast.Call)
            and isinstance(item.context_expr.func, ast.Name)
            and item.context_expr.func.id == "StageWatchdog"
            for item in node.items
        )
        if not enters_watchdog:
            continue
        # Something inside must actually drive the graph.
        for inner in ast.walk(node):
            if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Attribute):
                if inner.func.attr in ("invoke", "stream"):
                    return True
            if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name):
                if inner.func.id == "invoke_with_budget":
                    return True
    return False


@pytest.mark.parametrize("runner", sorted(RUNNERS), ids=lambda r: r)
class TestBothRunnersAreUnderTheWatchdog:
    def test_it_imports_the_watchdog(self, runner):
        assert "stage_watchdog import StageWatchdog" in _source(runner)

    def test_a_watchdog_encloses_the_graph_invocation(self, runner):
        assert _guards_the_invocation(runner), (
            f"{runner} invokes its graph without entering StageWatchdog, so a "
            "multi-minute model call prints nothing and reads as a hang"
        )


class TestTheAuditInspectsSomething:
    """A structural check that matched anything would pass forever."""

    def test_a_runner_without_the_wiring_fails_the_check(self, tmp_path, monkeypatch):
        naked = tmp_path / "tools"
        naked.mkdir()
        (naked / "run_requirements_workflow.py").write_text(
            "app.invoke({'x': 1})\n", encoding="utf-8"
        )
        monkeypatch.setattr(
            "tests.unit.test_standalone_runner_heartbeat.TOOLS", naked
        )
        assert not _guards_the_invocation("run_requirements_workflow.py")

    def test_a_watchdog_around_nothing_does_not_count(self, tmp_path, monkeypatch):
        naked = tmp_path / "tools"
        naked.mkdir()
        (naked / "run_requirements_workflow.py").write_text(
            "with StageWatchdog('lld'):\n    print('hello')\n", encoding="utf-8"
        )
        monkeypatch.setattr(
            "tests.unit.test_standalone_runner_heartbeat.TOOLS", naked
        )
        assert not _guards_the_invocation("run_requirements_workflow.py"), (
            "entering the watchdog around something other than the graph would "
            "satisfy a grep and still emit nothing during the model call"
        )


class TestTheObservableContract:
    """Mirrors test_stage_watchdog.py's lifecycle cases at the boundary the
    runners rely on: a slow stage speaks, a fast one stays quiet."""

    def test_a_slow_stage_prints_a_heartbeat(self, capsys):
        with StageWatchdog("lld", nominal_seconds=1, interval=0.05):
            time.sleep(0.2)
        out = capsys.readouterr().out

        assert "[STAGE] lld running" in out
        assert "s" in out, "elapsed time is the whole point"

    def test_a_fast_stage_stays_quiet(self, capsys):
        with StageWatchdog("lld", interval=5):
            pass
        assert "[STAGE]" not in capsys.readouterr().out

    def test_the_impl_runner_uses_the_impl_nominal(self):
        """A heartbeat with the wrong nominal would mislabel a normal stage as
        stalled, which is the noise the doctrine cannot survive."""
        assert "StageWatchdog(\"impl\")" in _source("run_implement_from_lld.py")

    def test_the_requirements_runner_names_its_stage(self):
        source = _source("run_requirements_workflow.py")
        assert "StageWatchdog(stage_name)" in source or 'StageWatchdog("lld")' in source
