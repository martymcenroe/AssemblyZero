"""The requirements human gates (N2, N4) under standard 0034 (#3585).

Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md (lines at 79e18ad1). When N4
decides on its own (gate disabled, or auto mode) it decides on ``lld_status``
alone: APPROVED finalizes, BLOCKED revises, and anything else halts. The word
"APPROVED" appearing somewhere in the verdict text, as in "NOT APPROVED", no
longer finalizes. Its revise loop is capped by ``max_iterations`` on
``verdict_count``; it used to run until GraphRecursionError. A human at the
prompt still decides for himself.
"""
from __future__ import annotations

import importlib

import pytest

from assemblyzero.workflows.requirements.graph import route_from_human_gate_verdict

hg = importlib.import_module("assemblyzero.workflows.requirements.nodes.human_gate")

DISABLED = {"config_gates_verdict": False}
AUTO = {"config_gates_verdict": True, "config_auto_mode": True}


def _state(mode: dict, **overrides) -> dict:
    state = {"iteration_count": 1, "verdict_count": 1, "max_iterations": 3,
             "current_verdict": "", **mode}
    state.update(overrides)
    return state


def _halts(out: dict) -> bool:
    return bool(out.get("error_message")) and route_from_human_gate_verdict(out) == "HALT"


@pytest.mark.parametrize("mode", [DISABLED, AUTO], ids=["disabled", "auto"])
class TestAutomaticVerdictGate:
    def test_168_and_186_not_approved_in_the_text_does_not_finalize(self, mode):
        state = _state(mode, lld_status="BLOCKED", current_verdict="NOT APPROVED: the cache is unbounded")

        out = hg.human_gate_verdict(state)

        assert out["next_node"] == "N1_generate_draft"
        assert out["error_message"] == ""

    @pytest.mark.parametrize("status", ["PENDING", "", "REVISE", "approved"])
    def test_168_and_186_an_unrecognised_status_halts_naming_it(self, mode, status, capsys):
        state = _state(mode, lld_status=status, current_verdict="Verdict: APPROVED")

        out = hg.human_gate_verdict(state)

        assert _halts(out)
        assert repr(status) in out["error_message"]
        assert "ERROR" in capsys.readouterr().err

    def test_179_the_revise_loop_stops_at_the_cap(self, mode, capsys):
        state = _state(mode, lld_status="BLOCKED", verdict_count=3, max_iterations=3)

        out = hg.human_gate_verdict(state)

        assert _halts(out)
        assert "3" in out["error_message"]
        assert "ERROR" in capsys.readouterr().err

    def test_kept_blocked_under_the_cap_revises(self, mode):
        out = hg.human_gate_verdict(_state(mode, lld_status="BLOCKED", verdict_count=2))
        assert out["next_node"] == "N1_generate_draft"
        assert out["error_message"] == ""

    def test_kept_approved_finalizes(self, mode):
        out = hg.human_gate_verdict(_state(mode, lld_status="APPROVED", verdict_count=3))
        assert out["next_node"] == "N5_finalize"
        assert out["error_message"] == ""


def test_kept_a_human_who_chooses_revise_is_not_capped(monkeypatch):
    """Human priority: the cap bounds the gate's own decisions, not his."""
    monkeypatch.setattr(hg, "_prompt_verdict_gate", lambda status: "R")
    state = _state({"config_gates_verdict": True}, lld_status="BLOCKED", verdict_count=9)

    out = hg.human_gate_verdict(state)

    assert out["next_node"] == "N1_generate_draft"
    assert out["error_message"] == ""
