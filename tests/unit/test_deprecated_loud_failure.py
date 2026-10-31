"""deprecated.py under standard 0034 (ADR 0236), the #3585 sweep.

The batch-mode helpers have no caller in a run, only in tests, but they keep
the standard while they exist: a read that fails is an ERROR line naming the
file and the read error propagates; a code block with no path is refused
rather than given an invented name; an entry with no path or no content is
refused before anything is written. Test names carry ledger 0908's line
numbers at its base ``79e18ad1``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from assemblyzero.workflows.testing.nodes.implementation import deprecated


@pytest.fixture
def unreadable(monkeypatch):
    """Make named paths raise PermissionError on read, on every platform."""
    blocked: set[str] = set()
    real = Path.read_text

    def read_text(self, *args, **kwargs):
        if str(Path(self).resolve()) in blocked:
            raise PermissionError(13, "Permission denied", str(self))
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)
    return lambda path: blocked.add(str(Path(path).resolve()))


def _loud(err: str, *needles: str) -> bool:
    return any(
        line.startswith("ERROR") and all(n in line for n in needles)
        for line in err.splitlines()
    )


class TestBuildImplementationPrompt:
    def test_58_an_unreadable_test_file_raises(self, tmp_path, unreadable, capsys):
        test_file = tmp_path / "tests" / "test_x.py"
        test_file.parent.mkdir()
        test_file.write_text("def test_x():\n    pass\n", encoding="utf-8")
        unreadable(test_file)

        with pytest.raises(PermissionError):
            deprecated.build_implementation_prompt(
                {"repo_root": str(tmp_path), "test_files": [str(test_file)]}
            )

        assert _loud(capsys.readouterr().err, "test_x.py", "could not read")

    def test_87_an_unreadable_modify_file_raises(self, tmp_path, unreadable, capsys):
        target = tmp_path / "src" / "x.py"
        target.parent.mkdir()
        target.write_text("x = 1\n", encoding="utf-8")
        unreadable(target)

        with pytest.raises(PermissionError):
            deprecated.build_implementation_prompt({
                "repo_root": str(tmp_path),
                "files_to_modify": [{"path": "src/x.py", "change_type": "Modify"}],
            })

        assert _loud(capsys.readouterr().err, "x.py", "could not read")

    def test_readable_files_reach_the_prompt(self, tmp_path):
        """Kept: the prompt carries the tests and the Modify file."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "x.py").write_text("x = 1\n", encoding="utf-8")
        prompt = deprecated.build_implementation_prompt({
            "repo_root": str(tmp_path),
            "files_to_modify": [{"path": "src/x.py", "change_type": "Modify"}],
        })
        assert "x = 1" in prompt


class TestParseImplementationResponse:
    def test_190_a_code_block_with_no_path_is_refused(self, capsys):
        response = "```python\ndef f():\n    return 1\n```"

        with pytest.raises(ValueError, match="no file path"):
            deprecated.parse_implementation_response(response)

        assert _loud(capsys.readouterr().err, "no file path")

    def test_a_block_that_names_its_path_is_kept(self):
        """Kept: a path comment on the first line names the file."""
        files = deprecated.parse_implementation_response(
            "```python\n# src/x.py\ndef f():\n    return 1\n```"
        )
        assert files == [{"path": "src/x.py", "content": "def f():\n    return 1"}]


class TestWriteImplementationFiles:
    def test_218_an_entry_with_no_content_is_refused_before_any_write(self, tmp_path, capsys):
        files = [
            {"path": "src/a.py", "content": "a = 1\n"},
            {"path": "src/b.py", "content": ""},
        ]

        with pytest.raises(ValueError, match="src/b.py"):
            deprecated.write_implementation_files(files, tmp_path)

        assert not (tmp_path / "src" / "a.py").exists()
        assert _loud(capsys.readouterr().err, "src/b.py", "no content")

    def test_218_an_entry_with_no_path_is_refused(self, tmp_path, capsys):
        with pytest.raises(ValueError, match="no path"):
            deprecated.write_implementation_files([{"path": "", "content": "x = 1\n"}], tmp_path)

        assert _loud(capsys.readouterr().err, "no path")

    def test_a_protected_test_file_is_still_skipped(self, tmp_path):
        """Kept: tests are protected by design; skipping one is not a failure."""
        written = deprecated.write_implementation_files(
            [{"path": "tests/test_a.py", "content": "x = 1\n"}], tmp_path,
        )
        assert written == []
