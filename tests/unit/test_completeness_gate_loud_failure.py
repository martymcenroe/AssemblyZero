"""completeness_gate.py (N4b) under standard 0034, the one open sweep site.

Ledger 0908 found line 119 compliant: zero requirements is a BLOCK whose
error_message routes to HALT, which alerts. It is pinned here, and the
refusal is now an ERROR line on stderr rather than a stdout print. The gate's
other rows were fixed in #3811 and are tested in test_completeness_gate_halts.py.
Line numbers in the names are ledger 0908's, at its base ``79e18ad1``.
"""
from __future__ import annotations

from pathlib import Path

from assemblyzero.workflows.testing.nodes.completeness_gate import (
    completeness_gate,
    route_after_completeness_gate,
)


def _state(tmp_path: Path, **overrides) -> dict:
    (tmp_path / "impl.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    state = {
        "repo_root": str(tmp_path),
        "issue_number": 119,
        "implementation_files": [str(tmp_path / "impl.py")],
        "test_files": [],
        "requirements": [],
        "requirements_empty_reason": "requirements unreadable: no LLD found",
        "iteration_count": 0,
    }
    state.update(overrides)
    return state


def test_119_zero_requirements_halts_with_an_error_on_stderr(tmp_path, capsys):
    state = _state(tmp_path)
    result = completeness_gate(state)

    assert result["completeness_verdict"] == "BLOCK"
    assert "zero requirements" in result["error_message"]
    assert "requirements unreadable" in result["error_message"]
    assert route_after_completeness_gate({**state, **result}) == "HALT"
    err = capsys.readouterr().err
    assert "ERROR [N4b]" in err and "zero requirements" in err


def test_119_zero_requirements_with_no_recorded_reason_still_halts(tmp_path):
    state = _state(tmp_path, requirements_empty_reason="")
    result = completeness_gate(state)

    assert "no recorded reason" in result["error_message"]
    assert route_after_completeness_gate({**state, **result}) == "HALT"
