"""resume_contract.py under standard 0034, one test per sweep site (#3788).

The contract exists so a resume never runs against a world nobody checked.
Each site below used to let it: an unreadable file hashed as absent, a
corrupt contract read as no contract, and a refusal reached only the console.
Line numbers in the names are ledger 0908's, at its base ``79e18ad1``.
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from assemblyzero.core import resume_contract as rc


def _unreadable(monkeypatch, target: Path) -> None:
    real = Path.read_bytes

    def read_bytes(self):
        if self == target:
            raise PermissionError("permission denied")
        return real(self)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)


def _halt_with_input(tmp_path: Path) -> tuple[Path, Path]:
    lld = tmp_path / "LLD-042.md"
    lld.write_text("# LLD\n", encoding="utf-8")
    contract = rc.build_resume_contract({"issue_number": 42, "repo_root": str(tmp_path), "lld_path": str(lld)}, "testing")
    rc.save_resume_contract(contract, tmp_path)
    return lld, rc.contract_path("testing", 42, tmp_path)


class TestHashing:
    def test_53_an_unreadable_file_raises_with_its_cause(self, tmp_path, monkeypatch):
        target = tmp_path / "LLD-042.md"
        target.write_text("x", encoding="utf-8")
        _unreadable(monkeypatch, target)
        with pytest.raises(PermissionError):
            rc._sha256_file(target)

    def test_53_an_absent_file_is_still_absent(self, tmp_path):
        assert rc._sha256_file(tmp_path / "nothing.md") is None

    def test_54_the_withdrawn_tag_is_gone(self):
        assert "fail-open" not in inspect.getsource(rc._sha256_file)

    def test_148_an_unreadable_input_is_not_reported_as_missing(
        self, tmp_path, monkeypatch,
    ):
        lld, _ = _halt_with_input(tmp_path)
        contract = rc.load_resume_contract("testing", 42, tmp_path)
        _unreadable(monkeypatch, lld)
        with pytest.raises(PermissionError):
            rc.verify_resume_contract(contract)

    def test_148_an_unreadable_input_refuses_the_resume_with_its_cause(
        self, tmp_path, monkeypatch, operator_alerts,
    ):
        lld, _ = _halt_with_input(tmp_path)
        _unreadable(monkeypatch, lld)
        assert rc.check_and_consume("testing", 42, repo_root=tmp_path, directory=tmp_path, log=lambda m: None) is False
        assert len(operator_alerts) == 1
        assert "PermissionError" in operator_alerts[0]["cause"]


class TestTheContractItself:
    def test_126_a_corrupt_contract_raises(self, tmp_path):
        rc.contract_path("testing", 42, tmp_path).write_text("{not json", encoding="utf-8")
        with pytest.raises(rc.ResumeContractUnreadable, match="exists but cannot be read"):
            rc.load_resume_contract("testing", 42, tmp_path)

    def test_126_a_corrupt_contract_refuses_the_resume_and_alerts(self, tmp_path, operator_alerts):
        rc.contract_path("testing", 42, tmp_path).write_text("{not json", encoding="utf-8")
        assert rc.check_and_consume("testing", 42, repo_root=tmp_path, directory=tmp_path, log=lambda m: None) is False
        assert len(operator_alerts) == 1
        assert "cannot be verified" in operator_alerts[0]["what"]
        assert "JSONDecodeError" in operator_alerts[0]["cause"]

    def test_127_the_withdrawn_tag_is_gone(self):
        assert "fail-open" not in inspect.getsource(rc.load_resume_contract)

    def test_no_contract_is_still_a_silent_pass(self, tmp_path, operator_alerts):
        assert rc.check_and_consume("testing", 42, repo_root=tmp_path, directory=tmp_path, log=lambda m: None) is True
        assert operator_alerts == []


class TestTheVerdict:
    def test_196_a_changed_world_refuses_and_alerts(self, tmp_path, operator_alerts):
        lld, _ = _halt_with_input(tmp_path)
        lld.write_text("# LLD, edited after the halt\n", encoding="utf-8")
        assert rc.check_and_consume("testing", 42, repo_root=tmp_path, directory=tmp_path, log=lambda m: None) is False
        assert len(operator_alerts) == 1
        assert "world changed" in operator_alerts[0]["what"]
        assert "LLD-042.md" in operator_alerts[0]["cause"]

    def test_an_intact_world_is_quiet_and_consumes_the_contract(self, tmp_path, operator_alerts):
        _, path = _halt_with_input(tmp_path)
        assert rc.check_and_consume("testing", 42, repo_root=tmp_path, directory=tmp_path, log=lambda m: None) is True
        assert operator_alerts == []
        assert not path.exists()

    def test_223_a_contract_that_cannot_be_deleted_alerts_and_the_resume_proceeds(
        self, tmp_path, monkeypatch, operator_alerts,
    ):
        _, path = _halt_with_input(tmp_path)
        real_unlink = Path.unlink

        def unlink(self, *args, **kwargs):
            if self == path:
                raise PermissionError("read-only directory")
            return real_unlink(self, *args, **kwargs)

        monkeypatch.setattr(Path, "unlink", unlink)
        assert rc.check_and_consume("testing", 42, repo_root=tmp_path, directory=tmp_path, log=lambda m: None) is True
        assert len(operator_alerts) == 1
        assert "could not be deleted" in operator_alerts[0]["what"]

    def test_224_the_withdrawn_tag_is_gone(self):
        assert "fail-open" not in inspect.getsource(rc.check_and_consume)

    def test_the_contract_written_is_json(self, tmp_path):
        _, path = _halt_with_input(tmp_path)
        assert json.loads(path.read_text(encoding="utf-8"))["workflow"] == "testing"
