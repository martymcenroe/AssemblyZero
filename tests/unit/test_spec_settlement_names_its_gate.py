"""A spec settlement fingerprints the gate that approved it (#3756).

boostgauge #2 run-issue2-024542 settled a spec the completeness gate later
learned to refuse (#3754, #3755). Without the gate among the inputs, `--fresh`
would preserve that spec and the new checks would never see it.
"""

from __future__ import annotations

from assemblyzero.core import settlement as s
from assemblyzero.workflows.implementation_spec import check_classification as cc

BODY = "The renderer shall draw four telltales."


def _keys(inputs):
    return {i.key for i in inputs}


def test_the_spec_stage_carries_the_gate(tmp_path):
    assert "gate:spec-completeness" in _keys(s.collect_inputs(tmp_path, issue_body=BODY, stage="spec"))


def test_other_stages_and_no_stage_do_not(tmp_path):
    assert "gate:spec-completeness" not in _keys(s.collect_inputs(tmp_path, issue_body=BODY, stage="lld"))
    assert "gate:spec-completeness" not in _keys(s.collect_inputs(tmp_path, issue_body=BODY))


def test_a_new_check_changes_the_gate_input(monkeypatch):
    before = s.gate_input("spec").sha256
    monkeypatch.setitem(cc.CLASSIFICATIONS, "a_check_added_later", cc.CLASSIFICATIONS["import_targets_exist"])
    assert s.gate_input("spec").sha256 != before


def test_a_spec_settled_by_the_old_gate_no_longer_verifies(tmp_path):
    spec = tmp_path / "spec.md"
    spec.write_text("# Spec\n", encoding="utf-8")
    old = s.build_settlement("spec", spec, s.collect_inputs(tmp_path, issue_body=BODY), verdict="APPROVED")
    mismatches = s.verify(old, s.collect_inputs(tmp_path, issue_body=BODY, stage="spec"))
    assert any("gate:spec-completeness" in m for m in mismatches), mismatches


def test_a_spec_settled_by_the_current_gate_verifies(tmp_path):
    spec = tmp_path / "spec.md"
    spec.write_text("# Spec\n", encoding="utf-8")
    inputs = s.collect_inputs(tmp_path, issue_body=BODY, stage="spec")
    record = s.build_settlement("spec", spec, inputs, verdict="APPROVED")
    assert s.verify(record, s.collect_inputs(tmp_path, issue_body=BODY, stage="spec")) == []


def test_an_lld_settlement_is_unaffected(tmp_path):
    lld = tmp_path / "LLD-002.md"
    lld.write_text("# LLD\n", encoding="utf-8")
    record = s.build_settlement("lld", lld, s.collect_inputs(tmp_path, issue_body=BODY), verdict="APPROVED")
    assert s.verify(record, s.collect_inputs(tmp_path, issue_body=BODY, stage="lld")) == []
