"""The spec workflow's N4 human_gate under standard 0034 (#3585).

Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md.
"""
from __future__ import annotations

import importlib
from unittest.mock import patch

from assemblyzero.workflows.implementation_spec.graph import route_after_human_gate

hg = importlib.import_module("assemblyzero.workflows.implementation_spec.nodes.human_gate")


def test_146_reaching_the_gate_while_it_is_disabled_halts():
    """route_after_validation sends here only when the gate is enabled, so
    arriving with it disabled is a misrouted graph. It used to proceed to N5
    as if nothing had happened."""
    result = hg.human_gate({"human_gate_enabled": False, "spec_draft": "# Spec", "issue_number": 42})
    assert "#42" in result["error_message"]
    assert "human_gate_enabled" in result["error_message"]
    assert route_after_human_gate(result) == "HALT"


def test_159_no_draft_at_the_gate_halts():
    """Compliant, pinned."""
    result = hg.human_gate({"human_gate_enabled": True, "spec_draft": "", "issue_number": 42})
    assert result["error_message"]
    assert route_after_human_gate(result) == "HALT"


def test_an_enabled_gate_sends_an_approved_draft_on():
    with patch.object(hg, "_prompt_human_gate", return_value="S"), patch.object(
        hg, "_display_spec_preview",
    ):
        result = hg.human_gate({"human_gate_enabled": True, "spec_draft": "# Spec", "issue_number": 42})
    assert result["error_message"] == ""
    assert route_after_human_gate(result) == "N5_review_spec"
