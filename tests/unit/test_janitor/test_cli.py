"""Tests for janitor CLI argument parsing.

Issue #94: Lu-Tze: The Janitor
Test IDs: T240-T260, T360-T380
"""

import io
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

from tools.run_janitor_workflow import (
    build_initial_state,
    main,
    parse_args,
)


class TestParseArgs:
    """Test CLI argument parsing. T240, T250, T260, T360, T370."""

    def test_defaults(self):
        """T240/T360: parse_args with no args returns correct defaults."""
        args = parse_args([])
        assert args.scope == "all"
        assert args.auto_fix is True
        assert args.dry_run is False
        assert args.silent is False
        assert args.create_pr is False
        assert args.reporter == "github"

    def test_all_flags(self):
        """T250/T370: parse_args handles all flag combinations."""
        args = parse_args([
            "--scope", "links",
            "--dry-run",
            "--silent",
            "--create-pr",
            "--reporter", "local",
        ])
        assert args.scope == "links"
        assert args.dry_run is True
        assert args.silent is True
        assert args.create_pr is True
        assert args.reporter == "local"

    def test_invalid_scope(self):
        """T260/T380: parse_args with invalid scope raises SystemExit."""
        with pytest.raises(SystemExit):
            parse_args(["--scope", "invalid"])

    def test_scope_worktrees(self):
        """parse_args accepts worktrees scope."""
        args = parse_args(["--scope", "worktrees"])
        assert args.scope == "worktrees"

    def test_scope_harvest(self):
        """parse_args accepts harvest scope."""
        args = parse_args(["--scope", "harvest"])
        assert args.scope == "harvest"

    def test_scope_todo(self):
        """parse_args accepts todo scope."""
        args = parse_args(["--scope", "todo"])
        assert args.scope == "todo"

    def test_reporter_local(self):
        """parse_args accepts local reporter."""
        args = parse_args(["--reporter", "local"])
        assert args.reporter == "local"

    def test_auto_fix_false(self):
        """parse_args handles --auto-fix false."""
        args = parse_args(["--auto-fix", "false"])
        assert args.auto_fix is False


class TestBuildInitialState:
    """Test state construction from CLI args. T010, T390."""

    def test_build_initial_state_scope_all(self):
        """T010/T390: build_initial_state converts 'all' scope to full list."""
        args = parse_args(["--reporter", "local"])

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="/home/user/repo\n"
            )
            state = build_initial_state(args)

        assert state["scope"] == ["links", "worktrees", "harvest", "todo"]
        assert state["repo_root"] == "/home/user/repo"
        assert state["reporter_type"] == "local"
        assert state["probe_results"] == []
        assert state["exit_code"] == 0

    def test_build_initial_state_single_scope(self):
        """build_initial_state converts single scope correctly."""
        args = parse_args(["--scope", "links", "--dry-run"])

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="/repo\n"
            )
            state = build_initial_state(args)

        assert state["scope"] == ["links"]
        assert state["dry_run"] is True


class TestMainEntryPoint:
    """Test main() entry point. T270-T350."""

    def test_exit_code_2_not_git_repo(self):
        """T350: main() returns 2 when not in a git repo."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=128, stdout="", stderr="not a git repo")
            code = main(["--silent"])
        assert code == 2

    def test_exit_code_0_clean_run(self):
        """T270: main() returns 0 when no findings."""
        with patch("subprocess.run") as mock_git, patch(
            "tools.run_janitor_workflow.build_janitor_graph"
        ) as mock_graph:
            mock_git.return_value = MagicMock(returncode=0, stdout="/repo\n")
            mock_compiled = MagicMock()
            mock_compiled.invoke.return_value = {
                "repo_root": "/repo",
                "scope": [],
                "auto_fix": True,
                "dry_run": False,
                "silent": True,
                "create_pr": False,
                "reporter_type": "local",
                "probe_results": [],
                "all_findings": [],
                "fix_actions": [],
                "unfixable_findings": [],
                "report_url": None,
                "exit_code": 0,
            }
            mock_graph.return_value = mock_compiled
            code = main(["--silent", "--reporter", "local"])
        assert code == 0

    def test_exit_code_1_unfixable(self):
        """T280: main() returns 1 when unfixable findings remain."""
        with patch("subprocess.run") as mock_git, patch(
            "tools.run_janitor_workflow.build_janitor_graph"
        ) as mock_graph:
            mock_git.return_value = MagicMock(returncode=0, stdout="/repo\n")
            mock_compiled = MagicMock()
            mock_compiled.invoke.return_value = {
                "exit_code": 1,
                "all_findings": [],
                "fix_actions": [],
                "unfixable_findings": [],
                "report_url": None,
            }
            mock_graph.return_value = mock_compiled
            code = main(["--silent", "--reporter", "local"])
        assert code == 1

    def test_silent_no_stdout(self, capsys):
        """T340: main with --silent produces no stdout on clean run."""
        with patch("subprocess.run") as mock_git, patch(
            "tools.run_janitor_workflow.build_janitor_graph"
        ) as mock_graph:
            mock_git.return_value = MagicMock(returncode=0, stdout="/repo\n")
            mock_compiled = MagicMock()
            mock_compiled.invoke.return_value = {
                "exit_code": 0,
                "all_findings": [],
                "fix_actions": [],
                "unfixable_findings": [],
                "report_url": None,
            }
            mock_graph.return_value = mock_compiled
            code = main(["--silent", "--reporter", "local"])

        captured = capsys.readouterr()
        assert captured.out == ""
        assert code == 0

    def test_fatal_exception_returns_2(self):
        """main() returns 2 on unhandled exception."""
        with patch("subprocess.run") as mock_git, patch(
            "tools.run_janitor_workflow.build_janitor_graph"
        ) as mock_graph:
            mock_git.return_value = MagicMock(returncode=0, stdout="/repo\n")
            mock_graph.side_effect = RuntimeError("Graph build failed")
            code = main(["--silent", "--reporter", "local"])
        assert code == 2