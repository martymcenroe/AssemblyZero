"""The requirements test-plan validation node (N1b) under standard 0034 (#3585).

Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md (lines at 79e18ad1). A failing
draft is preserved in the run's lineage or the run stops: an unset audit_dir
halts, and a write that fails alerts the operator and raises. A telemetry
record that cannot be made alerts and raises, where it printed "skipped".
"""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from assemblyzero.workflows.requirements.graph import route_after_validate_test_plan

vt = importlib.import_module("assemblyzero.workflows.requirements.nodes.validate_test_plan")

LLD_FAILING = """\
# 999 - Feature: Failing

## 3. Requirements

1. Requirement A
2. Requirement B
3. Requirement C

## 10. Verification & Testing

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | Test for Requirement 1 | Auto | Input | Output | Pass |
"""


def _state(tmp_path: Path, **overrides) -> dict:
    audit = tmp_path / "audit"
    audit.mkdir(exist_ok=True)
    state = {
        "workflow_type": "lld", "target_repo": str(tmp_path), "issue_number": 999,
        "current_draft": LLD_FAILING, "test_plan_validation_attempts": 0,
        "iteration_count": 0, "max_iterations": 20, "audit_dir": str(audit),
        "error_message": "",
    }
    state.update(overrides)
    return state


def test_139_a_telemetry_record_that_cannot_be_made_alerts_and_raises(
    tmp_path, monkeypatch, operator_alerts
):
    def broken():
        raise RuntimeError("run context unreadable")

    monkeypatch.setattr("assemblyzero.speedrun.must_resolve.run_context", broken)
    with pytest.raises(RuntimeError, match="run context unreadable"):
        vt.validate_test_plan_node(_state(tmp_path))

    assert len(operator_alerts) == 1
    assert "run context unreadable" in operator_alerts[0]["cause"]


@pytest.mark.parametrize("audit_dir", ["", None])
def test_154_no_audit_dir_halts_instead_of_losing_the_failing_draft(tmp_path, capsys, audit_dir):
    state = _state(tmp_path, audit_dir=audit_dir)

    out = vt.validate_test_plan_node(state)

    assert out["error_message"]
    assert route_after_validate_test_plan({**state, **out}) == "HALT"
    assert "audit_dir" in out["error_message"]
    assert "ERROR" in capsys.readouterr().err


def test_163_a_failing_draft_that_cannot_be_written_alerts_and_raises(
    tmp_path, monkeypatch, operator_alerts
):
    real_write = Path.write_text

    def write_text(self, *args, **kwargs):
        if self.name.startswith("failed-draft-iter"):
            raise OSError(28, "No space left on device", str(self))
        return real_write(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", write_text)
    with pytest.raises(OSError, match="No space left on device"):
        vt.validate_test_plan_node(_state(tmp_path))

    assert len(operator_alerts) == 1
    assert "failed-draft-iter1.md" in operator_alerts[0]["what"]


def test_kept_a_failing_draft_is_preserved_and_loops_back(tmp_path):
    state = _state(tmp_path)

    out = vt.validate_test_plan_node(state)

    assert out["error_message"] == ""
    assert route_after_validate_test_plan({**state, **out}) == "N1_generate_draft"
    assert (Path(state["audit_dir"]) / "failed-draft-iter1.md").is_file()
