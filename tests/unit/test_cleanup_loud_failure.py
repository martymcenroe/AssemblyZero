"""testing/nodes/cleanup.py (N9) under standard 0034 (#3585, the #3581 sweep).

N9 logged every failure at WARNING and went on to END: a worktree it could
not remove, a PR it could not check, a learning summary it could not write,
a lineage it could not archive. It read three keys no node writes, so every
summary said 0.0% of 0.0% and FAILURE, and a missing repo_root became the
current directory. Each failure now writes an ERROR line and raises
``CleanupError``; N9's edge to END is unconditional (graph.py, batch C), so
the raise is what stops the run, and the entry point's handler alerts.
Line numbers in the test names are ledger 0908's, at its base ``79e18ad1``.
"""
from __future__ import annotations

import importlib
import subprocess
from pathlib import Path

import pytest

#: The package exports the node function under the module's own name, so
#: `from ...nodes import cleanup` would give the function.
n9 = importlib.import_module("assemblyzero.workflows.testing.nodes.cleanup")


def _state(tmp_path: Path, **overrides) -> dict:
    repo = tmp_path / "repo"
    (repo / "docs" / "lineage" / "active" / "42-testing").mkdir(parents=True, exist_ok=True)
    state = {
        "issue_number": 42,
        "repo_root": str(repo),
        "pr_url": "",
        "worktree_path": "",
        "coverage_achieved": 96.5,
        "coverage_target": 95,
        "workflow_status": "completed",
    }
    state.update(overrides)
    return state


def _is_cleanup_error(raised) -> None:
    assert type(raised.value).__name__ == "CleanupError", type(raised.value)


class TestRouting:
    def test_47_no_issue_number_after_n8_raises(self, capsys):
        with pytest.raises(RuntimeError, match="issue_number") as raised:
            n9.route_after_document({"issue_number": 0})

        _is_cleanup_error(raised)
        assert "ERROR" in capsys.readouterr().err

    def test_47_kept_an_issue_number_routes_to_n9(self):
        assert n9.route_after_document({"issue_number": 42}) == "N9_cleanup"


class TestTheState:
    def test_72_the_summary_reads_the_declared_keys(self, tmp_path, monkeypatch):
        seen = {}

        def build(lineage_dir, issue_number, outcome, final_coverage, target_coverage):
            seen.update(outcome=outcome, final=final_coverage, target=target_coverage)
            return _Summary()

        monkeypatch.setattr(n9, "build_learning_summary", build)
        monkeypatch.setattr(n9, "render_learning_summary", lambda data: "# summary\n")

        n9.cleanup(_state(tmp_path))

        assert seen == {"outcome": "SUCCESS", "final": 96.5, "target": 95}

    def test_72_an_absent_declared_key_raises(self, tmp_path):
        state = _state(tmp_path)
        del state["coverage_achieved"]

        with pytest.raises(RuntimeError, match="coverage_achieved") as raised:
            n9.cleanup(state)

        _is_cleanup_error(raised)

    def test_81_no_repo_root_raises_instead_of_using_the_cwd(self, tmp_path):
        with pytest.raises(RuntimeError, match="repo_root") as raised:
            n9.cleanup(_state(tmp_path, repo_root=""))

        _is_cleanup_error(raised)


class _Summary:
    pass


class TestWorktree:
    def test_96_a_worktree_that_cannot_be_removed_raises(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(n9, "check_pr_merged", lambda url: True)
        monkeypatch.setattr(n9, "get_worktree_branch", lambda path: "issue-42")

        def dirty(path):
            raise subprocess.CalledProcessError(
                128, ["git", "worktree", "remove"], stderr="fatal: contains modified files",
            )

        monkeypatch.setattr(n9, "remove_worktree", dirty)

        with pytest.raises(RuntimeError, match="modified files") as raised:
            n9.cleanup(_state(tmp_path, pr_url="https://github.com/o/r/pull/1",
                              worktree_path=str(tmp_path / "wt")))

        _is_cleanup_error(raised)
        assert "ERROR" in capsys.readouterr().err

    def test_103_a_pr_check_that_fails_raises(self, tmp_path, monkeypatch):
        def failing(url):
            raise subprocess.TimeoutExpired(cmd=["gh"], timeout=10)

        monkeypatch.setattr(n9, "check_pr_merged", failing)

        with pytest.raises(RuntimeError, match="TimeoutExpired") as raised:
            n9.cleanup(_state(tmp_path, pr_url="https://github.com/o/r/pull/1"))

        _is_cleanup_error(raised)

    def test_103_kept_a_pr_not_merged_keeps_the_worktree(self, tmp_path, monkeypatch):
        monkeypatch.setattr(n9, "check_pr_merged", lambda url: False)

        result = n9.cleanup(_state(tmp_path, pr_url="https://github.com/o/r/pull/1"))

        assert result["pr_merged"] is False
        assert result["cleanup_skipped_reason"] == "PR not yet merged"


class TestLineage:
    def test_123_a_learning_summary_that_fails_raises(self, tmp_path, monkeypatch):
        def failing(*a, **k):
            raise OSError(28, "No space left on device")

        monkeypatch.setattr(n9, "write_learning_summary", failing)

        with pytest.raises(RuntimeError, match="No space left") as raised:
            n9.cleanup(_state(tmp_path))

        _is_cleanup_error(raised)

    def test_138_an_archive_that_produced_nothing_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(n9, "check_pr_merged", lambda url: True)
        monkeypatch.setattr(n9, "archive_lineage", lambda *a, **k: None)

        with pytest.raises(RuntimeError, match="archiv") as raised:
            n9.cleanup(_state(tmp_path, pr_url="https://github.com/o/r/pull/1"))

        _is_cleanup_error(raised)

    def test_139_an_archive_that_raises_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(n9, "check_pr_merged", lambda url: True)

        def failing(*a, **k):
            raise OSError(13, "Permission denied")

        monkeypatch.setattr(n9, "archive_lineage", failing)

        with pytest.raises(RuntimeError, match="Permission denied") as raised:
            n9.cleanup(_state(tmp_path, pr_url="https://github.com/o/r/pull/1"))

        _is_cleanup_error(raised)

    def test_kept_a_clean_run_writes_the_summary_in_active(self, tmp_path):
        result = n9.cleanup(_state(tmp_path))

        summary = Path(result["learning_summary_path"])
        assert summary.name == "learning-summary.md"
        assert summary.is_file()
        assert "SUCCESS" in summary.read_text(encoding="utf-8")
