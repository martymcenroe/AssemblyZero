"""prompts.py under standard 0034 (ADR 0236), the #3585 sweep.

The per-file prompt for a Modify carries the file's current contents. A read
that failed used to be passed over, and the model was asked to modify a file
it was never shown. It now is an ERROR line naming the file, and the read
error propagates. The test name carries ledger 0908's line number at its base
``79e18ad1``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from assemblyzero.workflows.testing.nodes.implementation.prompts import (
    build_single_file_prompt,
)


def _loud(err: str, *needles: str) -> bool:
    return any(
        line.startswith("ERROR") and all(n in line for n in needles)
        for line in err.splitlines()
    )


def _prompt(repo: Path) -> str:
    return build_single_file_prompt(
        filepath="src/x.py",
        file_spec={"path": "src/x.py", "change_type": "Modify"},
        lld_content="",
        completed_files=[],
        repo_root=repo,
    )


def test_153_an_unreadable_modify_file_raises(tmp_path, monkeypatch, capsys):
    target = tmp_path / "src" / "x.py"
    target.parent.mkdir()
    target.write_text("x = 1\n", encoding="utf-8")
    real = Path.read_text

    def read_text(self, *args, **kwargs):
        if Path(self) == target:
            raise PermissionError(13, "Permission denied", str(self))
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)

    with pytest.raises(PermissionError):
        _prompt(tmp_path)

    assert _loud(capsys.readouterr().err, "x.py", "could not read")


def test_a_readable_modify_file_is_in_the_prompt(tmp_path):
    """Kept: the current contents reach the model."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "x.py").write_text("x = 1\n", encoding="utf-8")
    assert "x = 1" in _prompt(tmp_path)


def test_a_modify_file_not_on_disk_has_no_contents_section(tmp_path):
    """Kept: N4's pre-flight turns a Modify of a missing file into an Add (#2879)."""
    assert "Existing File Contents" not in _prompt(tmp_path)
