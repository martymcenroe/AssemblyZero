"""Unit tests for Requirements Workflow CLI Runner.

Issue #101: Unified Requirements Workflow

Tests for the CLI interface and argument parsing.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock


class TestArgumentParsing:
    """Tests for CLI argument parsing."""

    def test_parse_issue_workflow_args(self):
        """Test parsing issue workflow arguments."""
        from tools.run_requirements_workflow import parse_args

        args = parse_args([
            "--type", "issue",
            "--brief", "ideas/active/my-feature.md",
        ])

        assert args.type == "issue"
        assert args.brief == "ideas/active/my-feature.md"

    def test_parse_lld_workflow_args(self):
        """Test parsing LLD workflow arguments."""
        from tools.run_requirements_workflow import parse_args

        args = parse_args([
            "--type", "lld",
            "--issue", "42",
        ])

        assert args.type == "lld"
        assert args.issue == 42

    def test_parse_drafter_reviewer(self):
        """Test parsing drafter and reviewer specifications."""
        from tools.run_requirements_workflow import parse_args

        args = parse_args([
            "--type", "lld",
            "--issue", "42",
            "--drafter", "gemini:2.5-flash",
            "--reviewer", "claude:sonnet",
        ])

        assert args.drafter == "gemini:2.5-flash"
        assert args.reviewer == "claude:sonnet"

    def test_parse_gates_both(self):
        """Test parsing gates with both enabled."""
        from tools.run_requirements_workflow import parse_args

        args = parse_args([
            "--type", "lld",
            "--issue", "42",
            "--gates", "draft,verdict",
        ])

        assert args.gates == "draft,verdict"

    def test_parse_gates_draft_only(self):
        """Test parsing gates with draft only."""
        from tools.run_requirements_workflow import parse_args

        args = parse_args([
            "--type", "lld",
            "--issue", "42",
            "--gates", "draft",
        ])

        assert args.gates == "draft"

    def test_parse_gates_none(self):
        """Test parsing gates with none."""
        from tools.run_requirements_workflow import parse_args

        args = parse_args([
            "--type", "lld",
            "--issue", "42",
            "--gates", "none",
        ])

        assert args.gates == "none"

    def test_parse_mock_mode(self):
        """Test parsing mock mode flag."""
        from tools.run_requirements_workflow import parse_args

        args = parse_args([
            "--type", "lld",
            "--issue", "42",
            "--mock",
        ])

        assert args.mock is True

    def test_parse_repo(self):
        """Test parsing target repo path."""
        from tools.run_requirements_workflow import parse_args

        args = parse_args([
            "--type", "lld",
            "--issue", "42",
            "--repo", "/path/to/repo",
        ])

        assert args.repo == "/path/to/repo"

    def test_parse_context_files(self):
        """Test parsing context files."""
        from tools.run_requirements_workflow import parse_args

        args = parse_args([
            "--type", "lld",
            "--issue", "42",
            "--context", "src/auth.py",
            "--context", "docs/security.md",
        ])

        assert args.context == ["src/auth.py", "docs/security.md"]

    def test_parse_max_iterations(self):
        """Test parsing max iterations."""
        from tools.run_requirements_workflow import parse_args

        args = parse_args([
            "--type", "lld",
            "--issue", "42",
            "--max-iterations", "10",
        ])

        assert args.max_iterations == 10

    def test_default_values(self):
        """Test default argument values."""
        from tools.run_requirements_workflow import parse_args

        args = parse_args([
            "--type", "lld",
            "--issue", "42",
        ])

        assert args.drafter == "claude:opus-4.5"
        assert args.reviewer == "gemini:3-pro-preview"
        assert args.gates == "draft,verdict"
        assert args.mock is False
        assert args.max_iterations == 20


class TestResolveRoots:
    """Tests for path resolution."""

    def test_resolve_roots_with_explicit_repo(self, tmp_path):
        """Test resolving roots with explicit repo path."""
        from tools.run_requirements_workflow import resolve_roots

        # Create mock args
        args = Mock()
        args.repo = str(tmp_path)

        agentos_root, target_repo = resolve_roots(args)

        # target_repo should be the explicit path
        assert target_repo == tmp_path.resolve()

    @patch("subprocess.run")
    def test_resolve_roots_with_git_detection(self, mock_run, tmp_path):
        """Test resolving roots with git detection."""
        from tools.run_requirements_workflow import resolve_roots

        mock_run.return_value = Mock(
            returncode=0,
            stdout=str(tmp_path) + "\n",
        )

        args = Mock()
        args.repo = None

        agentos_root, target_repo = resolve_roots(args)

        # target_repo should be detected from git
        assert target_repo == tmp_path


class TestBuildInitialState:
    """Tests for building initial state."""

    def test_build_issue_state(self, tmp_path):
        """Test building state for issue workflow."""
        from tools.run_requirements_workflow import build_initial_state

        args = Mock()
        args.type = "issue"
        args.brief = "ideas/active/feature.md"
        args.drafter = "claude:opus-4.5"
        args.reviewer = "gemini:3-pro-preview"
        args.gates = "draft,verdict"
        args.mock = False
        args.max_iterations = 20
        args.context = None

        state = build_initial_state(
            args,
            agentos_root=tmp_path,
            target_repo=tmp_path,
        )

        assert state["workflow_type"] == "issue"
        assert state["brief_file"] == "ideas/active/feature.md"
        assert state["config_drafter"] == "claude:opus-4.5"
        assert state["config_gates_draft"] is True
        assert state["config_gates_verdict"] is True

    def test_build_lld_state(self, tmp_path):
        """Test building state for LLD workflow."""
        from tools.run_requirements_workflow import build_initial_state

        args = Mock()
        args.type = "lld"
        args.issue = 42
        args.drafter = "gemini:2.5-flash"
        args.reviewer = "claude:sonnet"
        args.gates = "none"
        args.mock = True
        args.max_iterations = 10
        args.context = ["src/auth.py"]

        state = build_initial_state(
            args,
            agentos_root=tmp_path,
            target_repo=tmp_path,
        )

        assert state["workflow_type"] == "lld"
        assert state["issue_number"] == 42
        assert state["config_drafter"] == "gemini:2.5-flash"
        assert state["config_gates_draft"] is False
        assert state["config_gates_verdict"] is False
        assert state["config_mock_mode"] is True
        assert state["context_files"] == ["src/auth.py"]


class TestMainFunction:
    """Tests for main function."""

    @patch("tools.run_requirements_workflow.resolve_roots")
    @patch("tools.run_requirements_workflow.create_governance_graph")
    def test_main_creates_and_runs_graph(self, mock_graph, mock_roots, tmp_path):
        """Test that main creates and runs the graph."""
        from tools.run_requirements_workflow import main

        mock_roots.return_value = (tmp_path, tmp_path)

        # Create mock compiled graph
        mock_compiled = Mock()
        mock_compiled.invoke.return_value = {
            "error_message": "",
            "issue_url": "https://github.com/test/repo/issues/123",
        }
        mock_graph.return_value.compile.return_value = mock_compiled

        # Create brief file
        brief = tmp_path / "brief.md"
        brief.write_text("# Feature Brief")

        # Run main with arguments
        with patch("sys.argv", ["prog", "--type", "issue", "--brief", str(brief), "--mock"]):
            result = main()

        # Verify graph was created and invoked
        mock_graph.assert_called_once()
        mock_compiled.invoke.assert_called_once()
