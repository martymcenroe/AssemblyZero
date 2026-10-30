"""Settlement under standard 0034 (#3795).

Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md. Settlement still resolves every
doubt toward "unsettled", which drafts; what changes is that a failure says
so. An input that exists and cannot be read alerts, a binding doc outside the
repo raises, and an artifact that cannot be hashed is never settled.
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from assemblyzero.core import settlement as s


def _unreadable(monkeypatch, target: Path) -> None:
    real = Path.read_bytes

    def read_bytes(self):
        if self == target:
            raise PermissionError(13, "Permission denied", str(self))
        return real(self)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)


class TestSha256Path:
    def test_111_an_unreadable_input_alerts_and_unsettles(
        self, tmp_path, monkeypatch, operator_alerts
    ):
        doc = tmp_path / "dial.md"
        doc.write_text("the dial\n", encoding="utf-8")
        record = {
            "settlement_version": s.SETTLEMENT_VERSION,
            "inputs": [s.input_from_file("binding:dial.md", doc).as_dict()],
        }
        _unreadable(monkeypatch, doc)

        assert s.sha256_path(doc) is None
        assert len(operator_alerts) == 1
        assert str(doc) in operator_alerts[0]["what"]
        assert "PermissionError" in operator_alerts[0]["cause"]
        mismatches = s.verify(record, [s.input_from_file("binding:dial.md", doc)])
        assert mismatches and "cannot be read now" in mismatches[0]

    def test_111_a_directory_where_a_file_was_alerts(self, tmp_path, operator_alerts):
        folder = tmp_path / "dial.md"
        folder.mkdir()

        assert s.sha256_path(folder) is None
        assert len(operator_alerts) == 1
        assert "IsADirectoryError" in operator_alerts[0]["cause"]

    def test_an_absent_input_is_quiet_and_unsettles(self, tmp_path, operator_alerts):
        """Kept: a landed LLD's working copy is deleted on merge, so absence is
        an answer, not a failure."""
        assert s.sha256_path(tmp_path / "gone.md") is None
        assert operator_alerts == []

    def test_112_and_177_no_fail_open_tag_remains(self):
        for function in (s.sha256_path, s._rel_posix):
            assert "fail-open" not in inspect.getsource(function)


class TestBindingKeys:
    def test_176_a_binding_doc_outside_the_repo_raises(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        outside = tmp_path / "elsewhere.md"
        outside.write_text("not in the repo\n", encoding="utf-8")

        with pytest.raises(ValueError, match="outside the repo root"):
            s.binding_inputs(repo, ("../elsewhere.md",))

    def test_a_binding_doc_inside_the_repo_keeps_its_relative_key(self, tmp_path):
        design = tmp_path / "docs" / "design"
        design.mkdir(parents=True)
        (design / "dial.md").write_text("the dial\n", encoding="utf-8")

        [only] = s.binding_inputs(tmp_path, ("docs/design",))
        assert only.key == "binding:docs/design/dial.md"
        assert only.sha256 == s.sha256_text("the dial\n")


class TestBuildSettlement:
    def test_259_settling_an_absent_artifact_raises(self, tmp_path):
        missing = tmp_path / "LLD-042.md"

        with pytest.raises(FileNotFoundError, match="LLD-042.md"):
            s.build_settlement("lld", missing, [], verdict="APPROVED")

    def test_259_settling_an_unreadable_artifact_raises(self, tmp_path, monkeypatch):
        lld = tmp_path / "LLD-042.md"
        lld.write_text("# LLD\n", encoding="utf-8")
        _unreadable(monkeypatch, lld)

        with pytest.raises(PermissionError):
            s.build_settlement("lld", lld, [], verdict="APPROVED")

    def test_a_readable_artifact_settles_with_its_hash(self, tmp_path):
        lld = tmp_path / "LLD-042.md"
        lld.write_text("# LLD\r\n", encoding="utf-8")

        record = s.build_settlement("lld", lld, [], verdict="APPROVED")
        assert record["artifact_sha256"] == s.sha256_text("# LLD\n")
        assert s.artifact_matches(record, lld)
