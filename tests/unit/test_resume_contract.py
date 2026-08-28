"""A halt writes what its resume needs, and the resume verifies it (#2570).

The observed worlds as fixtures: the swept-LLD world (the input the loader
resolves deleted between halt and resume — #2551's incident) refuses
naming the path; the stale-counter world (the snapshot the resume seeds
from not the one the halt wrote — #2514's class) refuses naming the
snapshot. A fresh run has no contract and passes silently; verification
consumes the contract so a completed lifecycle leaves none behind.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import assemblyzero.core.resume_contract as rc
import assemblyzero.core.state_persistence as sp
from assemblyzero.core.halt_node import create_halt_node


@pytest.fixture
def store(tmp_path, monkeypatch):
    """A throwaway contract/snapshot store standing in for STATE_DIR."""
    directory = tmp_path / "state"
    directory.mkdir()
    monkeypatch.setattr(rc, "STATE_DIR", directory)
    monkeypatch.setattr(sp, "STATE_DIR", directory)
    return directory


def _world(tmp_path) -> dict:
    lld = tmp_path / "docs" / "lld" / "active" / "LLD-331.md"
    lld.parent.mkdir(parents=True)
    lld.write_text("## 3. Requirements\n\n1. Render the face.\n",
                   encoding="utf-8")
    spec = tmp_path / "spec.md"
    spec.write_text("# Spec\n", encoding="utf-8")
    return {
        "issue_number": 331,
        "original_lld_path": str(lld),
        "lld_path": str(spec),
        "review_iteration": 3,
        "max_iterations": 3,
        "pinning_events": ["[PINNING] refused: x"],
        "checks_shown_to_drafter": ["criteria_have_tests"],
        "audit_dir": "",
    }


class TestBuildAndVerify:
    def test_the_contract_records_inputs_hashed_and_counters(self, tmp_path):
        contract = rc.build_resume_contract(_world(tmp_path), "testing")
        keys = {entry["key"] for entry in contract["inputs"]}
        assert keys == {"original_lld_path", "lld_path"}
        assert all(entry["sha256"] for entry in contract["inputs"])
        assert contract["counters"]["review_iteration"] == 3
        assert contract["counters"]["pinning_events_count"] == 1
        assert contract["issue"] == 331

    def test_an_unchanged_world_verifies_clean(self, tmp_path):
        contract = rc.build_resume_contract(_world(tmp_path), "testing")
        assert rc.verify_resume_contract(contract) == []

    def test_the_swept_lld_world_refuses_naming_the_path(self, tmp_path):
        state = _world(tmp_path)
        contract = rc.build_resume_contract(state, "testing")
        Path(state["original_lld_path"]).unlink()
        mismatches = rc.verify_resume_contract(contract)
        assert len(mismatches) == 1
        assert "original_lld_path" in mismatches[0]
        assert "LLD-331.md" in mismatches[0]
        assert "now missing" in mismatches[0]

    def test_a_changed_input_names_both_hashes(self, tmp_path):
        state = _world(tmp_path)
        contract = rc.build_resume_contract(state, "testing")
        Path(state["original_lld_path"]).write_text(
            "## 3. Requirements\n\n1. Render something else.\n",
            encoding="utf-8",
        )
        mismatches = rc.verify_resume_contract(contract)
        assert len(mismatches) == 1
        assert "hashed" in mismatches[0] and "now" in mismatches[0]

    def test_an_input_absent_at_halt_may_appear(self, tmp_path):
        state = _world(tmp_path)
        missing = tmp_path / "spec-late.md"
        state["spec_path"] = str(missing)
        contract = rc.build_resume_contract(state, "testing")
        missing.write_text("appeared later\n", encoding="utf-8")
        assert rc.verify_resume_contract(contract) == []

    def test_the_stale_counter_world_refuses_naming_the_snapshot(
        self, tmp_path
    ):
        state = _world(tmp_path)
        snapshot = tmp_path / "testing-331.json"
        snapshot.write_text(json.dumps({"review_iteration": 3}),
                            encoding="utf-8")
        contract = rc.build_resume_contract(
            state, "testing", state_snapshot=snapshot
        )
        snapshot.write_text(json.dumps({"review_iteration": 9}),
                            encoding="utf-8")
        mismatches = rc.verify_resume_contract(contract)
        assert len(mismatches) == 1
        assert "state_snapshot" in mismatches[0]
        assert "counters a resume seeds from" in mismatches[0]


class TestCheckAndConsume:
    def test_no_contract_is_a_silent_pass(self, store, capsys):
        assert rc.check_and_consume("testing", 331) is True
        assert capsys.readouterr().out == ""

    def test_an_intact_contract_verifies_and_is_consumed(
        self, store, tmp_path, capsys
    ):
        contract = rc.build_resume_contract(_world(tmp_path), "testing")
        path = rc.save_resume_contract(contract)
        assert rc.check_and_consume("testing", 331) is True
        out = capsys.readouterr().out
        assert "resume contract verified: 2 input(s)" in out
        assert not path.exists(), "verification consumes the contract"

    def test_a_changed_world_refuses_before_any_token(
        self, store, tmp_path, capsys
    ):
        state = _world(tmp_path)
        path = rc.save_resume_contract(
            rc.build_resume_contract(state, "testing")
        )
        Path(state["original_lld_path"]).unlink()
        assert rc.check_and_consume("testing", 331) is False
        out = capsys.readouterr().out
        assert "refusing before any token is spent" in out
        assert "LLD-331.md" in out
        assert "--accept-changed-inputs" in out
        assert path.exists(), "a refused contract is kept for the next try"

    def test_the_override_is_loud_and_consumes(self, store, tmp_path, capsys):
        state = _world(tmp_path)
        path = rc.save_resume_contract(
            rc.build_resume_contract(state, "testing")
        )
        Path(state["original_lld_path"]).unlink()
        assert rc.check_and_consume(
            "testing", 331, accept_changed=True
        ) is True
        out = capsys.readouterr().out
        assert "ACCEPTED" in out
        assert "LLD-331.md" in out
        assert not path.exists()


class TestTheHaltWritesTheContract:
    def test_halt_writes_the_manifest_beside_the_plan_and_into_lineage(
        self, store, tmp_path, capsys
    ):
        state = _world(tmp_path)
        audit_dir = tmp_path / "lineage"
        audit_dir.mkdir()
        state["audit_dir"] = str(audit_dir)
        state["error_message"] = "Iteration cap: 3 revision(s) ended"

        halt = create_halt_node("testing")
        result = halt(state)
        capsys.readouterr()

        assert result["workflow_status"] == "halted"
        contract = rc.load_resume_contract("testing", 331)
        assert contract is not None
        assert len(contract["inputs"]) == 2
        assert contract["state_snapshot"]["sha256"]
        lineage_copy = audit_dir / "resume-contract-testing-331.json"
        assert lineage_copy.exists(), "the lineage carries the manifest"

    def test_a_contract_write_failure_never_masks_the_halt(
        self, store, tmp_path, monkeypatch, capsys
    ):
        state = _world(tmp_path)
        state["error_message"] = "some halt"
        monkeypatch.setattr(
            rc, "build_resume_contract",
            lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")),
        )
        halt = create_halt_node("testing")
        result = halt(state)
        out = capsys.readouterr().out
        assert result["workflow_status"] == "halted"
        assert "resume contract not written" in out
