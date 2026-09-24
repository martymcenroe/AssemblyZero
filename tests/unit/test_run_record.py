"""Every entry-point run leaves a record (#3503).

The record is judged by what a reader finds on disk after the run, so
these tests read the files, not the object. The crash test is the case
the issue was filed for: a run that dies mid-graph must leave the node,
the exception, and the list of what it created.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from assemblyzero.core.run_record import RunRecord, left_in_place

TAG_RE = re.compile(r"^(lld|impl)-issue\d+-\d{6}$")


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert result.returncode == 0, f"git {' '.join(args)}: {result.stderr}"
    return result


@pytest.fixture
def target_repo(tmp_path: Path) -> Path:
    """A throwaway target with a bare origin, the `test_mock_roll` shape."""
    origin = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "-q", "--bare", "--initial-branch=main", str(origin)],
        capture_output=True, text=True, check=True,
    )
    root = tmp_path / "target"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "Test")
    (root / ".gitignore").write_text("data/\n", encoding="utf-8")
    (root / "README.md").write_text("base\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")
    _git(root, "remote", "add", "origin", str(origin))
    _git(root, "push", "-qu", "origin", "main")
    return root


@pytest.fixture
def restore_streams():
    """A record that is never finished would leave the tee installed."""
    out, err = sys.stdout, sys.stderr
    yield
    sys.stdout, sys.stderr = out, err


class TestStart:
    def test_prints_the_tag_and_log_path_first(self, target_repo, capsys, restore_streams):
        record = RunRecord.start("lld", target_repo, 42, argv=["prog", "--issue", "42"])
        record.finish("success")
        first = capsys.readouterr().out.splitlines()[0]
        assert first == f"[run] {record.tag} -> {record.out_path}"
        assert TAG_RE.match(record.tag)

    def test_creates_both_files_beside_the_rolls(self, target_repo, restore_streams):
        record = RunRecord.start("impl", target_repo, 7, argv=["prog"])
        record.finish("success")
        runs = target_repo / "data" / "speedrun" / "runs"
        assert record.out_path == runs / f"{record.tag}.log"
        assert record.events_path == runs / f"{record.tag}-events.log"
        assert record.out_path.exists() and record.events_path.exists()

    def test_start_records_argv_target_and_head(self, target_repo, restore_streams):
        head = _git(target_repo, "rev-parse", "--short", "HEAD").stdout.strip()
        record = RunRecord.start("lld", target_repo, 42, argv=["prog", "--x"])
        record.finish("success")
        events = record.events_path.read_text(encoding="utf-8")
        assert "start tool=lld issue=42" in events
        assert "argv=prog --x" in events
        assert f"target head={head} branch=main" in events


class TestTee:
    def test_prints_after_start_land_in_the_log(self, target_repo, restore_streams):
        record = RunRecord.start("lld", target_repo, 42, argv=["prog"])
        print("the tool said this")
        print("and this on stderr", file=sys.stderr)
        record.finish("success")
        log = record.out_path.read_text(encoding="utf-8")
        assert "the tool said this" in log
        assert "and this on stderr" in log

    def test_finish_restores_the_streams_and_is_idempotent(self, target_repo, restore_streams):
        out, err = sys.stdout, sys.stderr
        record = RunRecord.start("lld", target_repo, 42, argv=["prog"])
        assert sys.stdout is not out
        record.finish("halt", "first")
        record.finish("halt", "second")
        assert sys.stdout is out and sys.stderr is err
        events = record.events_path.read_text(encoding="utf-8")
        assert events.count("end outcome=") == 1
        assert "error=first" in events and "error=second" not in events


class TestCrash:
    def test_crash_record_names_type_message_node_and_traceback(
        self, target_repo, restore_streams,
    ):
        record = RunRecord.start("impl", target_repo, 42, argv=["prog"])
        record.node("N2_scaffold_tests")
        try:
            raise ValueError("the model returned\nnothing usable")
        except ValueError as exc:
            record.crash(exc)
        record.finish("halt", "boom")
        events = record.events_path.read_text(encoding="utf-8")
        assert "crash type=ValueError message=the model returned nothing usable" in events
        assert "crash last_node=N2_scaffold_tests" in events
        assert "Traceback (most recent call last)" in events
        assert "left in place" in events

    def test_end_marker_is_skipped_for_node_transitions(self, target_repo, restore_streams):
        record = RunRecord.start("impl", target_repo, 42, argv=["prog"])
        record.node("N1_review_test_plan")
        record.node("__end__")
        record.finish("success")
        assert record.last_node == "N1_review_test_plan"


class TestLeftInPlace:
    def test_nothing_on_a_clean_target(self, target_repo):
        assert left_in_place(target_repo, 42) == []

    def test_lists_worktree_branches_and_untracked_files(self, target_repo):
        _git(target_repo, "branch", "42-lld")
        wt = target_repo / "data" / "worktrees" / "42-lld"
        _git(target_repo, "worktree", "add", "-q", str(wt), "42-lld")
        _git(target_repo, "push", "-q", "origin", "42-lld")
        _git(target_repo, "branch", "42-implementation")
        lld = target_repo / "docs" / "lld" / "active" / "LLD-042.md"
        lld.parent.mkdir(parents=True)
        lld.write_text("draft\n", encoding="utf-8")
        (target_repo / "README.md").write_text("changed\n", encoding="utf-8")

        items = left_in_place(target_repo, 42)

        assert any(item.startswith("worktree: ") and item.endswith("[42-lld]") for item in items)
        assert "branch: 42-lld" in items
        assert "branch: 42-implementation" in items
        assert "remote branch: origin/42-lld" in items
        assert "checkout: ?? docs/lld/active/LLD-042.md" in items
        assert "checkout:  M README.md" in items

    def test_another_issues_branch_is_not_listed(self, target_repo):
        _git(target_repo, "branch", "420-lld")
        items = left_in_place(target_repo, 42)
        assert not any("420" in item for item in items)

    def test_never_raises_outside_a_git_repo(self, tmp_path):
        items = left_in_place(tmp_path / "nowhere", 42)
        assert items
        assert all("unknown" in item or "unavailable" in item for item in items)

    def test_finish_prints_the_list_to_the_console(self, target_repo, capsys, restore_streams):
        _git(target_repo, "branch", "42-lld")
        record = RunRecord.start("lld", target_repo, 42, argv=["prog"])
        record.finish("halt", "x")
        out = capsys.readouterr().out
        assert "[run] left in place (1):" in out
        assert "[run]   branch: 42-lld" in out
        assert f"[run] record: {record.events_path}" in out


class TestTheToolsWriteTheRecord:
    """A crash inside either tool leaves the record. This is the case
    #3503 was filed for: the 2026-09-13 crash left nothing but a terminal."""

    def test_lld_runner_records_a_crash_in_the_graph(self, target_repo, restore_streams):
        from tools.run_requirements_workflow import parse_args, run_single_workflow

        args = parse_args([
            "--type", "lld", "--issue", "42", "--mock",
            "--repo", str(target_repo), "--base-branch", "main",
        ])
        with patch(
            "tools.run_requirements_workflow.create_requirements_graph",
            side_effect=RuntimeError("graph exploded"),
        ):
            rc = run_single_workflow(args, target_repo.parent, target_repo)

        assert rc == 1
        runs = target_repo / "data" / "speedrun" / "runs"
        events = list(runs.glob("lld-issue42-*-events.log"))
        assert len(events) == 1
        text = events[0].read_text(encoding="utf-8")
        assert "crash type=RuntimeError message=graph exploded" in text
        assert "end outcome=halt" in text
        assert "left in place" in text
        assert runs.joinpath(events[0].name.replace("-events", "")).exists()

    def test_lld_dry_run_writes_no_record(self, target_repo, restore_streams):
        from tools.run_requirements_workflow import parse_args, run_single_workflow

        args = parse_args([
            "--type", "lld", "--issue", "42", "--dry-run",
            "--repo", str(target_repo), "--base-branch", "main",
        ])
        rc = run_single_workflow(args, target_repo.parent, target_repo)
        assert rc == 0
        assert not (target_repo / "data" / "speedrun" / "runs").exists()

    def test_impl_runner_records_a_crash_and_the_last_node(
        self, target_repo, tmp_path, restore_streams,
    ):
        from tools import run_implement_from_lld as tool

        failing = Mock()
        failing.compile.side_effect = RuntimeError("compile exploded")
        argv = [
            "prog", "--issue", "42", "--repo", str(target_repo), "--no-worktree",
            "--mock", "--auto", "--db-path", str(tmp_path / "ckpt.db"),
        ]
        with patch("sys.argv", argv), patch(
            "assemblyzero.workflows.testing.build_testing_workflow",
            return_value=failing,
        ):
            rc = tool.main()

        assert rc == 1
        runs = target_repo / "data" / "speedrun" / "runs"
        events = list(runs.glob("impl-issue42-*-events.log"))
        assert len(events) == 1
        text = events[0].read_text(encoding="utf-8")
        assert "crash type=RuntimeError message=compile exploded" in text
        assert "crash last_node=unknown" in text
        assert "end outcome=halt" in text
