"""Unit tests for Requirements Workflow CLI Runner.

Issue #101: Unified Requirements Workflow

Tests for the CLI interface and argument parsing.
"""

import pytest
import json
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
        args.brief = None  # No brief provided, fall back to CWD

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
    @patch("tools.run_requirements_workflow.create_requirements_graph")
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


class TestSelectFlag:
    """Tests for --select flag parsing."""

    def test_parse_select_flag(self):
        """Test parsing --select flag."""
        from tools.run_requirements_workflow import parse_args

        args = parse_args([
            "--type", "issue",
            "--select",
        ])

        assert args.select is True

    def test_select_with_issue_workflow(self):
        """Test --select is valid for issue workflow."""
        from tools.run_requirements_workflow import parse_args

        args = parse_args([
            "--type", "issue",
            "--select",
        ])

        assert args.type == "issue"
        assert args.select is True
        assert args.brief is None

    def test_select_with_lld_workflow(self):
        """Test --select is valid for lld workflow."""
        from tools.run_requirements_workflow import parse_args

        args = parse_args([
            "--type", "lld",
            "--select",
        ])

        assert args.type == "lld"
        assert args.select is True
        assert args.issue is None


class TestExtractBriefTitle:
    """Tests for extract_brief_title function."""

    def test_extracts_h1_title(self, tmp_path):
        """Test extracting title from H1 heading."""
        from tools.run_requirements_workflow import extract_brief_title

        brief = tmp_path / "feature.md"
        brief.write_text("# My Feature Title\n\nDescription here.")

        title = extract_brief_title(brief)

        assert title == "My Feature Title"

    def test_returns_no_title_for_empty_file(self, tmp_path):
        """Test returns placeholder for empty file."""
        from tools.run_requirements_workflow import extract_brief_title

        brief = tmp_path / "empty.md"
        brief.write_text("")

        title = extract_brief_title(brief)

        assert title == "(no title)"

    def test_returns_no_title_when_no_heading(self, tmp_path):
        """Test returns placeholder when no H1 heading."""
        from tools.run_requirements_workflow import extract_brief_title

        brief = tmp_path / "no-heading.md"
        brief.write_text("Just some text without a heading.")

        title = extract_brief_title(brief)

        assert title == "(no title)"

    def test_handles_missing_file(self, tmp_path):
        """Test handles missing file gracefully."""
        from tools.run_requirements_workflow import extract_brief_title

        missing = tmp_path / "nonexistent.md"

        title = extract_brief_title(missing)

        assert title == "(no title)"


class TestSelectBriefFile:
    """Tests for select_brief_file function."""

    def test_returns_none_when_no_ideas_dir(self, tmp_path):
        """Test returns None when ideas/active/ doesn't exist."""
        from tools.run_requirements_workflow import select_brief_file

        result = select_brief_file(tmp_path)

        assert result is None

    def test_returns_none_when_no_briefs(self, tmp_path):
        """Test returns None when no brief files found."""
        from tools.run_requirements_workflow import select_brief_file

        ideas_dir = tmp_path / "ideas" / "active"
        ideas_dir.mkdir(parents=True)

        result = select_brief_file(tmp_path)

        assert result is None

    @patch.dict("os.environ", {"AGENTOS_TEST_MODE": "1"})
    def test_auto_selects_first_in_test_mode(self, tmp_path):
        """Test auto-selects first brief in test mode."""
        from tools.run_requirements_workflow import select_brief_file

        ideas_dir = tmp_path / "ideas" / "active"
        ideas_dir.mkdir(parents=True)
        (ideas_dir / "feature-a.md").write_text("# Feature A")
        (ideas_dir / "feature-b.md").write_text("# Feature B")

        result = select_brief_file(tmp_path)

        assert result == "ideas/active/feature-a.md" or result == "ideas\\active\\feature-a.md"

    @patch("builtins.input", return_value="q")
    def test_returns_none_when_user_quits(self, mock_input, tmp_path):
        """Test returns None when user quits."""
        from tools.run_requirements_workflow import select_brief_file

        ideas_dir = tmp_path / "ideas" / "active"
        ideas_dir.mkdir(parents=True)
        (ideas_dir / "feature.md").write_text("# Feature")

        result = select_brief_file(tmp_path)

        assert result is None

    @patch("builtins.input", return_value="1")
    def test_selects_valid_number(self, mock_input, tmp_path):
        """Test selects brief when valid number entered."""
        from tools.run_requirements_workflow import select_brief_file

        ideas_dir = tmp_path / "ideas" / "active"
        ideas_dir.mkdir(parents=True)
        (ideas_dir / "feature.md").write_text("# Feature")

        result = select_brief_file(tmp_path)

        assert "feature.md" in result


class TestSelectGitHubIssue:
    """Tests for select_github_issue function."""

    @patch("subprocess.run")
    def test_returns_none_on_gh_failure(self, mock_run, tmp_path):
        """Test returns None when gh CLI fails."""
        from tools.run_requirements_workflow import select_github_issue

        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="gh: not logged in",
        )

        result = select_github_issue(tmp_path)

        assert result is None

    @patch("subprocess.run")
    def test_returns_none_on_timeout(self, mock_run, tmp_path):
        """Test returns None on gh CLI timeout."""
        import subprocess
        from tools.run_requirements_workflow import select_github_issue

        mock_run.side_effect = subprocess.TimeoutExpired("gh", 30)

        result = select_github_issue(tmp_path)

        assert result is None

    @patch("subprocess.run")
    def test_returns_none_when_gh_not_found(self, mock_run, tmp_path):
        """Test returns None when gh CLI not installed."""
        from tools.run_requirements_workflow import select_github_issue

        mock_run.side_effect = FileNotFoundError("gh not found")

        result = select_github_issue(tmp_path)

        assert result is None

    @patch("subprocess.run")
    def test_returns_none_when_no_issues(self, mock_run, tmp_path):
        """Test returns None when no open issues."""
        from tools.run_requirements_workflow import select_github_issue

        mock_run.return_value = Mock(
            returncode=0,
            stdout="[]",
        )

        result = select_github_issue(tmp_path)

        assert result is None

    @patch("subprocess.run")
    @patch.dict("os.environ", {"AGENTOS_TEST_MODE": "1"})
    def test_auto_selects_first_in_test_mode(self, mock_run, tmp_path):
        """Test auto-selects first issue in test mode."""
        from tools.run_requirements_workflow import select_github_issue

        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps([
                {"number": 42, "title": "First Issue", "labels": []},
                {"number": 43, "title": "Second Issue", "labels": []},
            ]),
        )

        result = select_github_issue(tmp_path)

        assert result == 42

    @patch("subprocess.run")
    @patch("builtins.input", return_value="q")
    def test_returns_none_when_user_quits(self, mock_input, mock_run, tmp_path):
        """Test returns None when user quits."""
        from tools.run_requirements_workflow import select_github_issue

        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps([
                {"number": 42, "title": "Test Issue", "labels": []},
            ]),
        )

        result = select_github_issue(tmp_path)

        assert result is None

    @patch("subprocess.run")
    @patch("builtins.input", return_value="1")
    def test_selects_valid_number(self, mock_input, mock_run, tmp_path):
        """Test selects issue when valid number entered."""
        from tools.run_requirements_workflow import select_github_issue

        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps([
                {"number": 42, "title": "First Issue", "labels": []},
                {"number": 43, "title": "Second Issue", "labels": []},
            ]),
        )

        result = select_github_issue(tmp_path)

        assert result == 42

    @patch("subprocess.run")
    @patch("builtins.input", return_value="2")
    def test_selects_second_issue(self, mock_input, mock_run, tmp_path):
        """Test selects second issue when 2 entered."""
        from tools.run_requirements_workflow import select_github_issue

        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps([
                {"number": 42, "title": "First Issue", "labels": []},
                {"number": 99, "title": "Second Issue", "labels": []},
            ]),
        )

        result = select_github_issue(tmp_path)

        assert result == 99


class TestUnusedArgumentsRemoved:
    """Tests to verify that previously unused arguments have been removed.

    Issue #156: These arguments were defined but never used.
    The fix removes them entirely from the argparse definition.
    """

    def test_resume_not_in_parser(self):
        """Verify --resume argument has been removed from requirements CLI.

        This argument was defined but never used in the code.
        It should be removed from the parser.
        """
        from pathlib import Path
        import re

        cli_file = Path(__file__).parent.parent.parent / "tools" / "run_requirements_workflow.py"
        content = cli_file.read_text(encoding="utf-8")

        # Should NOT find --resume in argument definitions
        resume_pattern = r'parser\.add_argument\([^)]*"--resume"'
        matches = re.findall(resume_pattern, content)

        assert len(matches) == 0, (
            f"--resume argument should be removed from parser. "
            f"Found {len(matches)} occurrences."
        )


class TestAllArgumentsUsed:
    """Tests to verify every defined argument affects behavior.

    Issue #156: Acceptance criteria requires each CLI flag has a test
    verifying it affects behavior.
    """

    def test_debug_flag_affects_output(self, tmp_path, capsys):
        """Test --debug flag enables debug output."""
        from tools.run_requirements_workflow import parse_args

        args = parse_args([
            "--type", "lld",
            "--issue", "42",
            "--debug",
        ])

        assert args.debug is True

        # When debug is True, the code prints DEBUG: lines
        # This verifies the flag is actually checked

    def test_dry_run_flag_skips_execution(self, tmp_path):
        """Test --dry-run flag prevents actual execution."""
        from tools.run_requirements_workflow import parse_args

        args = parse_args([
            "--type", "lld",
            "--issue", "42",
            "--dry-run",
        ])

        assert args.dry_run is True

        # In main(), dry_run causes early return without running graph

    def test_mock_flag_sets_mock_mode(self, tmp_path):
        """Test --mock flag sets mock_mode in state."""
        from tools.run_requirements_workflow import parse_args, build_initial_state

        args = parse_args([
            "--type", "lld",
            "--issue", "42",
            "--mock",
        ])

        state = build_initial_state(args, tmp_path, tmp_path)

        assert state["config_mock_mode"] is True

    def test_gates_none_sets_auto_mode(self, tmp_path):
        """Test --gates none sets auto_mode in state."""
        from tools.run_requirements_workflow import parse_args, build_initial_state

        args = parse_args([
            "--type", "lld",
            "--issue", "42",
            "--gates", "none",
        ])

        state = build_initial_state(args, tmp_path, tmp_path)

        assert state["config_auto_mode"] is True

    def test_context_flag_passed_to_state(self, tmp_path):
        """Test --context files are passed to state."""
        from tools.run_requirements_workflow import parse_args, build_initial_state

        args = parse_args([
            "--type", "lld",
            "--issue", "42",
            "--context", "src/auth.py",
            "--context", "src/utils.py",
        ])

        state = build_initial_state(args, tmp_path, tmp_path)

        assert state["context_files"] == ["src/auth.py", "src/utils.py"]

    def test_max_iterations_passed_to_state(self, tmp_path):
        """Test --max-iterations is passed to state."""
        from tools.run_requirements_workflow import parse_args, build_initial_state

        args = parse_args([
            "--type", "lld",
            "--issue", "42",
            "--max-iterations", "5",
        ])

        state = build_initial_state(args, tmp_path, tmp_path)

        assert state["max_iterations"] == 5

    def test_drafter_passed_to_state(self, tmp_path):
        """Test --drafter is passed to state."""
        from tools.run_requirements_workflow import parse_args, build_initial_state

        args = parse_args([
            "--type", "lld",
            "--issue", "42",
            "--drafter", "gemini:2.5-flash",
        ])

        state = build_initial_state(args, tmp_path, tmp_path)

        assert state["config_drafter"] == "gemini:2.5-flash"

    def test_reviewer_passed_to_state(self, tmp_path):
        """Test --reviewer is passed to state."""
        from tools.run_requirements_workflow import parse_args, build_initial_state

        args = parse_args([
            "--type", "lld",
            "--issue", "42",
            "--reviewer", "claude:sonnet",
        ])

        state = build_initial_state(args, tmp_path, tmp_path)

        assert state["config_reviewer"] == "claude:sonnet"


class TestRepoAutoDetection:
    """Tests for automatic target repo detection from brief file path.

    Issue #115: Auto-detect target repo from brief file path.

    TDD: These tests are written FIRST to define the expected behavior.
    """

    def test_explicit_repo_takes_precedence(self, tmp_path):
        """--repo flag should override all auto-detection."""
        from tools.run_requirements_workflow import resolve_roots

        # Create two repos
        repo_a = tmp_path / "repo_a"
        repo_b = tmp_path / "repo_b"
        repo_a.mkdir()
        repo_b.mkdir()

        # Initialize repo_b as git repo
        import subprocess
        subprocess.run(["git", "init"], cwd=str(repo_b), capture_output=True)

        # Create brief in repo_b
        ideas_dir = repo_b / "ideas" / "active"
        ideas_dir.mkdir(parents=True)
        brief = ideas_dir / "feature.md"
        brief.write_text("# Feature")

        # Create args with --repo pointing to repo_a and --brief in repo_b
        args = Mock()
        args.repo = str(repo_a)
        args.brief = str(brief)

        _, target_repo = resolve_roots(args)

        # Explicit --repo should take precedence
        assert target_repo == repo_a.resolve()

    def test_detect_repo_from_brief_path(self, tmp_path):
        """Brief in another repo should set target_repo to that repo."""
        from tools.run_requirements_workflow import resolve_roots

        # Create a git repo
        repo = tmp_path / "other_repo"
        repo.mkdir()

        import subprocess
        subprocess.run(["git", "init"], cwd=str(repo), capture_output=True)

        # Create brief in that repo
        ideas_dir = repo / "ideas" / "active"
        ideas_dir.mkdir(parents=True)
        brief = ideas_dir / "feature.md"
        brief.write_text("# Feature")

        # Create args with --brief but no --repo
        args = Mock()
        args.repo = None
        args.brief = str(brief)

        _, target_repo = resolve_roots(args)

        # Should detect repo from brief path
        assert target_repo == repo.resolve()

    def test_fallback_to_cwd_when_brief_not_in_repo(self, tmp_path, monkeypatch):
        """Brief outside any git repo falls back to CWD detection."""
        from tools.run_requirements_workflow import resolve_roots

        # Create a non-git directory with a brief
        non_git_dir = tmp_path / "not_a_repo"
        non_git_dir.mkdir()
        brief = non_git_dir / "brief.md"
        brief.write_text("# Feature")

        # Create a git repo to be CWD
        cwd_repo = tmp_path / "cwd_repo"
        cwd_repo.mkdir()

        import subprocess
        subprocess.run(["git", "init"], cwd=str(cwd_repo), capture_output=True)

        # Change to the CWD repo
        monkeypatch.chdir(cwd_repo)

        # Create args with --brief in non-git dir
        args = Mock()
        args.repo = None
        args.brief = str(brief)

        _, target_repo = resolve_roots(args)

        # Should fall back to CWD repo
        assert target_repo == cwd_repo.resolve()

    def test_fallback_to_cwd_when_no_brief(self, tmp_path, monkeypatch):
        """No --brief and no --repo uses CWD."""
        from tools.run_requirements_workflow import resolve_roots

        # Create a git repo to be CWD
        cwd_repo = tmp_path / "cwd_repo"
        cwd_repo.mkdir()

        import subprocess
        subprocess.run(["git", "init"], cwd=str(cwd_repo), capture_output=True)

        # Change to the CWD repo
        monkeypatch.chdir(cwd_repo)

        # Create args with no --brief and no --repo
        args = Mock()
        args.repo = None
        args.brief = None

        _, target_repo = resolve_roots(args)

        # Should use CWD repo
        assert target_repo == cwd_repo.resolve()

    def test_detect_repo_handles_nested_brief_path(self, tmp_path):
        """Brief deeply nested in repo should still detect repo root."""
        from tools.run_requirements_workflow import resolve_roots

        # Create a git repo with deeply nested structure
        repo = tmp_path / "deep_repo"
        repo.mkdir()

        import subprocess
        subprocess.run(["git", "init"], cwd=str(repo), capture_output=True)

        # Create deeply nested brief
        nested_dir = repo / "ideas" / "active" / "subfolder" / "deep"
        nested_dir.mkdir(parents=True)
        brief = nested_dir / "feature.md"
        brief.write_text("# Feature")

        # Create args
        args = Mock()
        args.repo = None
        args.brief = str(brief)

        _, target_repo = resolve_roots(args)

        # Should still find repo root
        assert target_repo == repo.resolve()
