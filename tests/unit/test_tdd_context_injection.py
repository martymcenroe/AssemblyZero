"""Tests for TDD context injection (Issue #288) and --issue-only flag (Issue #287).

Tests the --context CLI flag, --issue-only flag, state propagation, and prompt injection.
"""

import pytest
from pathlib import Path

from assemblyzero.workflows.testing.nodes.implement_code import (
    build_single_file_prompt,
)


class TestContextCLIFlag:
    """Test --context flag parsing in the CLI argument parser."""

    def test_context_flag_accepted(self):
        from tools.run_implement_from_lld import create_argument_parser

        parser = create_argument_parser()
        args = parser.parse_args([
            "--issue", "42",
            "--context", "src/core.py",
            "--context", "docs/spec.md",
        ])
        assert args.context == ["src/core.py", "docs/spec.md"]

    def test_context_defaults_to_empty(self):
        from tools.run_implement_from_lld import create_argument_parser

        parser = create_argument_parser()
        args = parser.parse_args(["--issue", "42"])
        assert args.context == []


class TestContextInPrompt:
    """Test that context_content appears in generated prompts."""

    def test_context_injected_into_prompt(self, tmp_path):
        prompt = build_single_file_prompt(
            filepath="src/module.py",
            file_spec={"change_type": "Add", "description": "New module"},
            lld_content="# LLD\nImplement feature X",
            completed_files=[],
            repo_root=tmp_path,
            context_content="# Context: audit.py\n\ndef existing_function(): pass",
        )
        assert "Additional Context" in prompt
        assert "existing_function" in prompt

    def test_no_context_section_when_empty(self, tmp_path):
        prompt = build_single_file_prompt(
            filepath="src/module.py",
            file_spec={"change_type": "Add", "description": "New module"},
            lld_content="# LLD\nImplement feature X",
            completed_files=[],
            repo_root=tmp_path,
            context_content="",
        )
        assert "Additional Context" not in prompt


class TestIssueOnlyCLIFlag:
    """Test --issue-only flag parsing in the CLI argument parser (Issue #287)."""

    def test_issue_only_flag_accepted(self):
        from tools.run_implement_from_lld import create_argument_parser

        parser = create_argument_parser()
        args = parser.parse_args(["--issue", "42", "--issue-only"])
        assert args.issue_only is True

    def test_issue_only_defaults_to_false(self):
        from tools.run_implement_from_lld import create_argument_parser

        parser = create_argument_parser()
        args = parser.parse_args(["--issue", "42"])
        assert args.issue_only is False


class TestIssueOnlyStateField:
    """Test issue_only field in TestingWorkflowState (Issue #287)."""

    def test_state_accepts_issue_only_field(self):
        from assemblyzero.workflows.testing.state import TestingWorkflowState

        annotations = TestingWorkflowState.__annotations__
        assert "issue_only" in annotations


class TestStateContextField:
    """Test context fields in TestingWorkflowState."""

    def test_state_accepts_context_fields(self):
        from assemblyzero.workflows.testing.state import TestingWorkflowState

        # Verify the fields exist in the TypedDict annotations
        annotations = TestingWorkflowState.__annotations__
        assert "context_files" in annotations
        assert "context_content" in annotations
