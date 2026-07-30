"""Capacity storms get escalating stage-retry delays (#1909).

The 2026-07-29 phase-4 run proved classification and stage retry both
worked — and the run still died, because three attempts with flat 10s
delays span ~2 minutes while real provider storms (Gemini 503, Anthropic
529) run for several. Attempt N against a capacity-class failure now
sleeps capacity_retry_delays[N-1] (last entry repeats); every other
transient failure keeps retry_delay_seconds.
"""

from unittest.mock import patch

from assemblyzero.core.errors import is_capacity_message
from assemblyzero.workflows.orchestrator.config import (
    get_default_config,
    validate_config,
)
from assemblyzero.workflows.orchestrator.state import create_initial_state


class TestCapacityMessageDetection:
    """The shared marker set recognizes real capacity failures, not noise."""

    def test_live_incident_message_is_capacity(self):
        msg = (
            "Drafter failed: All credentials failed:\n"
            "  - oauth-primary: Capacity exhausted after 3 retries (503/529)"
        )
        assert is_capacity_message(msg) is True

    def test_anthropic_overloaded_is_capacity(self):
        assert is_capacity_message("API error: overloaded_error (529)") is True

    def test_bare_503_is_capacity(self):
        assert is_capacity_message("upstream returned status 503") is True

    def test_ordinary_failure_is_not_capacity(self):
        assert is_capacity_message("Failed to read LLD: file not found") is False

    def test_auth_failure_is_not_capacity(self):
        assert is_capacity_message("Invalid API key for oauth-primary") is False


class TestCapacityRetryConfig:
    def test_default_schedule_is_escalating(self):
        config = get_default_config()
        assert config["capacity_retry_delays"] == [10, 60, 300]

    def test_default_config_validates(self):
        assert validate_config(get_default_config()) == []

    def test_non_list_schedule_rejected(self):
        config = get_default_config()
        config["capacity_retry_delays"] = 60
        assert any("capacity_retry_delays" in e for e in validate_config(config))

    def test_empty_schedule_rejected(self):
        config = get_default_config()
        config["capacity_retry_delays"] = []
        assert any("capacity_retry_delays" in e for e in validate_config(config))

    def test_negative_entry_rejected(self):
        config = get_default_config()
        config["capacity_retry_delays"] = [10, -5]
        assert any("capacity_retry_delays" in e for e in validate_config(config))


class TestCapacityEscalatedStageRetry:
    """_run_stage_node sleeps the escalating schedule for capacity failures."""

    def _make_state(self):
        config = get_default_config()
        state = create_initial_state(305, config)
        state["current_stage"] = "triage"
        return state

    def _failed_runner(self, error_message):
        def fake_runner(s):
            new_state = dict(s)
            new_state["stage_results"] = {
                "triage": {
                    "status": "failed",
                    "error_message": error_message,
                    "duration_seconds": 0.0,
                    "attempts": 1,
                    "transient": True,
                }
            }
            return new_state

        return fake_runner

    def test_capacity_failure_sleeps_escalating_schedule(self):
        from assemblyzero.workflows.orchestrator import graph as graph_mod

        runner = self._failed_runner(
            "All credentials failed:\n  - oauth-primary: Capacity exhausted "
            "after 3 retries (503/529)"
        )
        with patch.dict(graph_mod.STAGE_RUNNERS, {"triage": runner}, clear=False), \
             patch("assemblyzero.workflows.orchestrator.graph.save_orchestration_state"), \
             patch("assemblyzero.workflows.orchestrator.graph.time.sleep") as sleeper:
            result = graph_mod._run_stage_node(self._make_state())

        assert [c.args[0] for c in sleeper.call_args_list] == [10, 60]
        assert result["stage_results"]["triage"]["status"] == "failed"

    def test_non_capacity_transient_keeps_flat_delay(self):
        from assemblyzero.workflows.orchestrator import graph as graph_mod

        runner = self._failed_runner("gh CLI flake: connection reset")
        with patch.dict(graph_mod.STAGE_RUNNERS, {"triage": runner}, clear=False), \
             patch("assemblyzero.workflows.orchestrator.graph.save_orchestration_state"), \
             patch("assemblyzero.workflows.orchestrator.graph.time.sleep") as sleeper:
            graph_mod._run_stage_node(self._make_state())

        assert [c.args[0] for c in sleeper.call_args_list] == [10, 10]

    def test_schedule_last_entry_repeats_when_attempts_exceed_it(self):
        from assemblyzero.workflows.orchestrator import graph as graph_mod

        state = self._make_state()
        state["config"] = dict(state["config"])
        state["config"]["max_stage_retries"] = 4
        state["config"]["capacity_retry_delays"] = [10, 60]

        runner = self._failed_runner("Capacity exhausted (503)")
        with patch.dict(graph_mod.STAGE_RUNNERS, {"triage": runner}, clear=False), \
             patch("assemblyzero.workflows.orchestrator.graph.save_orchestration_state"), \
             patch("assemblyzero.workflows.orchestrator.graph.time.sleep") as sleeper:
            graph_mod._run_stage_node(state)

        assert [c.args[0] for c in sleeper.call_args_list] == [10, 60, 60]

    def test_non_transient_capacity_lookalike_still_skips_retry(self):
        """transient=False wins over a capacity-looking message — the
        escalation only widens delays, it never revives a dead retry."""
        from assemblyzero.workflows.orchestrator import graph as graph_mod

        def runner(s):
            new_state = dict(s)
            new_state["stage_results"] = {
                "triage": {
                    "status": "failed",
                    "error_message": "spec references 503 in acceptance text",
                    "duration_seconds": 0.0,
                    "attempts": 1,
                    "transient": False,
                }
            }
            return new_state

        with patch.dict(graph_mod.STAGE_RUNNERS, {"triage": runner}, clear=False), \
             patch("assemblyzero.workflows.orchestrator.graph.save_orchestration_state"), \
             patch("assemblyzero.workflows.orchestrator.graph.time.sleep") as sleeper:
            graph_mod._run_stage_node(self._make_state())

        assert sleeper.call_args_list == []
