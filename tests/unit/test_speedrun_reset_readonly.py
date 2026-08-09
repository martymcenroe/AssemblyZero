"""Reset deletions survive the ReadOnly attribute (#2162).

Measured live 2026-08-09 mid-roll: the pipeline's own freshly created
lineage directory carried the Windows ReadOnly attribute, and the reset's
plain rmtree died on it with WinError 5, leaving the next attempt to draw
over a predecessor's lineage. These pin the clear-and-retry handler at both
deletion sites.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import speedrun_reset as reset  # noqa: E402


def _protect(path: Path) -> None:
    """Make `path` refuse plain deletion, the way today's incident did."""
    if sys.platform == "win32":
        subprocess.run(
            ["attrib", "+R", str(path)], capture_output=True, check=True
        )
    else:
        # POSIX: a write-protected PARENT refuses deletion of its entries.
        path.chmod(0o555)


def _lineage_tree(tmp_path: Path) -> Path:
    repo = tmp_path / "proj"
    d = repo / "docs" / "lineage" / "active" / "1-lld"
    d.mkdir(parents=True)
    (d / "001-issue.md").write_text("lineage\n", encoding="utf-8")
    inner = d / "phase"
    inner.mkdir()
    (inner / "002-draft.md").write_text("draft\n", encoding="utf-8")
    return repo


class TestClearingRmtree:
    def test_a_readonly_tree_is_fully_removed(self, tmp_path):
        repo = _lineage_tree(tmp_path)
        target = repo / "docs" / "lineage" / "active" / "1-lld"
        _protect(target)
        _protect(target / "phase")

        reset._rmtree_clearing_readonly(target)

        assert not target.exists()

    def test_a_plain_tree_is_removed_without_ceremony(self, tmp_path):
        repo = _lineage_tree(tmp_path)
        target = repo / "docs" / "lineage" / "active" / "1-lld"

        reset._rmtree_clearing_readonly(target)

        assert not target.exists()


class TestLineageDeletion:
    def test_todays_incident_replayed(self, tmp_path, capsys):
        """A ReadOnly lineage dir left by a prior attempt deletes cleanly,
        with no WARNING line."""
        repo = _lineage_tree(tmp_path)
        target = repo / "docs" / "lineage" / "active" / "1-lld"
        _protect(target)
        _protect(target / "phase")

        count = reset.delete_lineage_dirs(repo, 1)

        out = capsys.readouterr().out
        assert count == 1
        assert not target.exists()
        assert "WARNING" not in out
        assert "Deleted lineage dir" in out

    def test_only_the_issues_dirs_are_touched(self, tmp_path):
        repo = _lineage_tree(tmp_path)
        other = repo / "docs" / "lineage" / "active" / "41-lld"
        other.mkdir()
        (other / "keep.md").write_text("other issue\n", encoding="utf-8")

        reset.delete_lineage_dirs(repo, 1)

        assert other.exists(), "issue 41's lineage is not issue 1's to delete"
