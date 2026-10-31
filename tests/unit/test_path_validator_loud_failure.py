"""path_validator.py under standard 0034, one test per sweep site (#3585).

`load_context_files` loads the files the operator names with `--context`
into the prompts. A file that failed validation (164) or could not be read
(177) was added to an error list nobody saw at the point of failure, and the
files that did load came back as the context: a partial context. Each
failure is now an ERROR line naming the file and the cause, and when any
file fails no context comes back at all, only the errors; the one caller,
`tools/run_implement_from_lld.py`, refuses to start on any error and its
handler alerts. A file that cannot be statted (65) is a rejection with its
reason, as the ledger found: compliant, and pinned.

Every test works in a temporary directory. Line numbers in the names are
ledger 0908's, at its base `79e18ad1`.
"""
from __future__ import annotations

from pathlib import Path

from assemblyzero.workflows.testing import path_validator as pv


def _good(tmp_path: Path) -> Path:
    good = tmp_path / "good.py"
    good.write_text("# good", encoding="utf-8")
    return good


class TestARejectedFile:
    def test_164_a_rejection_is_loud_and_leaves_no_partial_context(self, tmp_path, capsys):
        content, errors = pv.load_context_files([str(_good(tmp_path)), "missing.py"], tmp_path)

        assert content == ""
        assert len(errors) == 1 and "REJECTED: missing.py" in errors[0]
        err = capsys.readouterr().err
        assert "ERROR" in err and "missing.py" in err

    def test_164_a_secret_file_is_rejected_loudly(self, tmp_path, capsys):
        (tmp_path / ".env").write_text("X=1", encoding="utf-8")

        content, errors = pv.load_context_files([".env"], tmp_path)

        assert content == "" and "Secret file rejected" in errors[0]
        assert "ERROR" in capsys.readouterr().err


class TestAnUnreadableFile:
    def test_177_a_file_that_does_not_decode_is_loud_and_leaves_no_partial_context(
        self, tmp_path, capsys,
    ):
        (tmp_path / "binary.py").write_bytes(b"\xff\xfe\x00 not utf-8")

        content, errors = pv.load_context_files([str(_good(tmp_path)), "binary.py"], tmp_path)

        assert content == ""
        assert len(errors) == 1
        assert "binary.py" in errors[0] and "UnicodeDecodeError" in errors[0]
        assert "ERROR" in capsys.readouterr().err

    def test_177_a_read_that_fails_is_loud(self, tmp_path, monkeypatch, capsys):
        target = _good(tmp_path)
        real_read = Path.read_text

        def read_text(self, *args, **kwargs):
            if self == target.resolve():
                raise PermissionError(13, "Permission denied", str(self))
            return real_read(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", read_text)

        content, errors = pv.load_context_files([str(target)], tmp_path)

        assert content == ""
        assert "PermissionError" in errors[0]
        assert "ERROR" in capsys.readouterr().err


class TestTheStat:
    def test_65_a_file_that_cannot_be_statted_is_a_rejection_with_its_reason(self, tmp_path):
        """Kept (ledger: compliant): (False, reason) is the documented answer,
        and load_context_files turns it into an error the caller refuses."""
        ok, reason = pv.check_file_size(tmp_path / "gone.py")

        assert ok is False
        assert reason.startswith("Cannot stat file:")


class TestKept:
    def test_files_that_all_load_are_the_context_quietly(self, tmp_path, capsys, operator_alerts):
        other = tmp_path / "other.py"
        other.write_text("# other", encoding="utf-8")

        content, errors = pv.load_context_files([str(_good(tmp_path)), "other.py"], tmp_path)

        assert "# good" in content and "# other" in content
        assert errors == []
        assert "ERROR" not in capsys.readouterr().err
        assert operator_alerts == []

    def test_no_files_is_no_context(self, tmp_path):
        assert pv.load_context_files([], tmp_path) == ("", [])
