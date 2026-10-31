"""testing/nodes/cleanup_helpers.py under standard 0034 (#3585, the #3581 sweep).

A `git worktree list` that failed read as "no branch", any `git branch -d`
failure whose stderr began "error: branch" read as "already deleted", a
lineage artifact that could not be read dropped its iteration, and a coverage
figure that did not parse was recorded as 0.0%. Each now raises with its
cause. The two rows the sweep found compliant are pinned: an absent worktree
and an absent active lineage directory are documented answers the caller
checks for. Line numbers in the test names are ledger 0908's, at its base
``79e18ad1``.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from assemblyzero.workflows.testing.nodes import cleanup_helpers as ch


def _done(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(args=["git"], returncode=returncode, stdout=stdout, stderr=stderr)


class TestWorktreeAndBranch:
    def test_101_kept_an_absent_worktree_is_false(self, tmp_path):
        """Won't do (compliant as found): absent is the documented False, and
        N9 reads it as already removed."""
        assert ch.remove_worktree(tmp_path / "gone") is False

    def test_144_a_failed_worktree_list_raises(self, monkeypatch, capsys):
        monkeypatch.setattr(ch, "run_command", lambda *a, **k: _done(
            128, stderr="fatal: not a git repository"))

        with pytest.raises(subprocess.CalledProcessError) as raised:
            ch.get_worktree_branch("/work/tree")

        assert raised.value.returncode == 128
        assert "not a git repository" in raised.value.stderr
        assert "ERROR" in capsys.readouterr().err

    def test_144_kept_a_worktree_not_listed_has_no_branch(self, monkeypatch):
        monkeypatch.setattr(ch, "run_command", lambda *a, **k: _done(
            0, stdout="worktree /other\nbranch refs/heads/main\n"))

        assert ch.get_worktree_branch("/work/tree") is None

    def test_193_a_branch_delete_refused_for_another_reason_raises(self, monkeypatch):
        """git's own words for a branch checked out elsewhere start
        "error: branch" too; that is not "already deleted"."""
        def refusing(*a, **k):
            raise subprocess.CalledProcessError(
                1, a[0], stderr="error: branch 'issue-7' is checked out at '/work/tree'",
            )

        monkeypatch.setattr(ch, "run_command", refusing)

        with pytest.raises(subprocess.CalledProcessError):
            ch.delete_local_branch("issue-7")

    def test_193_kept_git_saying_not_found_is_false(self, monkeypatch):
        def not_found(*a, **k):
            raise subprocess.CalledProcessError(1, a[0], stderr="error: branch 'issue-7' not found.")

        monkeypatch.setattr(ch, "run_command", not_found)

        assert ch.delete_local_branch("issue-7") is False

    def test_193_another_branchs_not_found_is_not_this_ones(self, monkeypatch):
        def other(*a, **k):
            raise subprocess.CalledProcessError(1, a[0], stderr="error: branch 'issue-70' not found.")

        monkeypatch.setattr(ch, "run_command", other)

        with pytest.raises(subprocess.CalledProcessError):
            ch.delete_local_branch("issue-7")


class TestLineage:
    def test_221_kept_no_active_lineage_dir_is_none(self, tmp_path):
        """Won't do (compliant as found): None is documented, and N9 checks
        the directory exists before it archives."""
        assert ch.archive_lineage(tmp_path, 42) is None

    def test_277_an_artifact_that_cannot_be_read_raises(self, tmp_path, monkeypatch, capsys):
        lineage = tmp_path / "42-testing"
        lineage.mkdir()
        good = lineage / "005-green-phase.txt"
        good.write_text("Coverage: 80.0%\n", encoding="utf-8")
        bad = lineage / "009-green-phase.txt"
        bad.write_text("Coverage: 90.0%\n", encoding="utf-8")
        real = Path.read_text

        def read_text(self, *a, **k):
            if self == bad:
                raise PermissionError(13, "Permission denied", str(self))
            return real(self, *a, **k)

        monkeypatch.setattr(Path, "read_text", read_text)

        with pytest.raises(RuntimeError, match="Permission denied") as raised:
            ch.extract_iteration_data(lineage)

        assert type(raised.value).__name__ == "LineageReadError"
        assert str(bad) in str(raised.value)
        assert "ERROR" in capsys.readouterr().err

    def test_288_a_coverage_figure_that_does_not_parse_raises(self, tmp_path):
        lineage = tmp_path / "42-testing"
        lineage.mkdir()
        bad = lineage / "005-green-phase.txt"
        bad.write_text("Coverage: 8.0.1%\n", encoding="utf-8")

        with pytest.raises(RuntimeError, match="8.0.1") as raised:
            ch.extract_iteration_data(lineage)

        assert type(raised.value).__name__ == "LineageReadError"
        assert str(bad) in str(raised.value)

    def test_288_kept_a_figure_reads_as_its_number(self, tmp_path):
        lineage = tmp_path / "42-testing"
        lineage.mkdir()
        (lineage / "005-green-phase.txt").write_text("Coverage: 87.5%\n", encoding="utf-8")

        assert [s.coverage_pct for s in ch.extract_iteration_data(lineage)] == [87.5]
