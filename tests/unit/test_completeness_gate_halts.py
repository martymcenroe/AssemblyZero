"""The completeness gate halts when it cannot check (#3811, #3812, #3823; ADR 0236).

Each path below used to log a warning and carry on, so the gate could return
PASS or WARN on code it never examined. Each now returns verdict BLOCK with an
error_message, and the router sends that to HALT, which alerts the operator.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.workflows.testing.completeness.ast_analyzer import (
    CompletenessGateError,
)
from assemblyzero.workflows.testing.nodes.completeness_gate import (
    completeness_gate,
    route_after_completeness_gate,
)

NODE = "assemblyzero.workflows.testing.nodes.completeness_gate"
PASSING = {"verdict": "PASS", "issues": [], "ast_analysis_ms": 1, "gemini_review_ms": None}


def _state(tmp_path: Path, **overrides) -> dict:
    lld = tmp_path / "LLD-7.md"
    lld.write_text("# LLD\n\n## 3. Requirements\n\n1. impl exists\n")
    impl = tmp_path / "impl.py"
    impl.write_text("x = 1\n")
    state = {
        "repo_root": str(tmp_path),
        "issue_number": 7,
        "original_lld_path": str(lld),
        "implementation_files": [str(impl)],
        "test_files": [],
        "audit_dir": "",
        "iteration_count": 1,
        "requirements": ["REQ-1: impl exists"],
    }
    state.update(overrides)
    return state


def _halts(out: dict, state: dict, *fragments: str) -> None:
    assert out["completeness_verdict"] == "BLOCK"
    for fragment in fragments:
        assert fragment in out["error_message"]
    assert "issue #7" in out["error_message"]
    assert route_after_completeness_gate({**state, **out}) == "HALT"


def test_no_files_to_analyse_halts(tmp_path):
    """It used to pass through with verdict PASS."""
    state = _state(tmp_path, implementation_files=[], test_files=[])
    _halts(completeness_gate(state), state, "no implementation or test files")


def test_a_missing_lld_halts(tmp_path):
    """Layer 2 and the report used to be skipped with a warning."""
    state = _state(tmp_path, original_lld_path=str(tmp_path / "gone.md"))
    _halts(completeness_gate(state), state, "gone.md", "does not exist")


def test_a_file_that_does_not_parse_halts(tmp_path):
    """Layer 1 used to skip it, or fail open to WARN."""
    broken = tmp_path / "broken.py"
    broken.write_text("def broken(:\n")
    state = _state(tmp_path, implementation_files=[str(broken)])
    _halts(completeness_gate(state), state, "Layer 1", "cannot parse", "broken.py")


def test_review_materials_that_cannot_be_prepared_halt(tmp_path):
    """Layer 2 used to be skipped with a warning."""
    state = _state(tmp_path)
    with patch(f"{NODE}.run_ast_analysis", return_value=PASSING), patch(
        f"{NODE}.prepare_review_materials",
        side_effect=CompletenessGateError("cannot read impl.py for the review materials"),
    ):
        out = completeness_gate(state)
    _halts(out, state, "Layer 2", "cannot read impl.py")


def test_a_report_that_cannot_be_written_halts(tmp_path):
    """It used to log, return the path of a file never written, and go on."""
    state = _state(tmp_path)
    with patch(f"{NODE}.run_ast_analysis", return_value=PASSING), patch(
        f"{NODE}.generate_implementation_report",
        side_effect=CompletenessGateError("cannot write the implementation report"),
    ):
        out = completeness_gate(state)
    _halts(out, state, "implementation report")


def test_an_unexpected_error_is_not_swallowed(tmp_path):
    """Only the gate's own failure is turned into a halt; anything else propagates."""
    state = _state(tmp_path)
    with patch(f"{NODE}.run_ast_analysis", side_effect=KeyError("bug")), pytest.raises(KeyError):
        completeness_gate(state)


def test_a_clean_run_still_passes(tmp_path):
    """The control: with everything readable the verdict is PASS and nothing halts."""
    state = _state(tmp_path)
    out = completeness_gate(state)
    assert out["completeness_verdict"] == "PASS"
    assert out["error_message"] == ""
    assert Path(out["implementation_report_path"]).is_file()
    assert route_after_completeness_gate({**state, **out}) == "N4_5_mechanical_hooks"
