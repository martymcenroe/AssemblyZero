"""Tests for Issue #643: Stable system prompt for LLD caching.

Verifies that:
- build_stable_system_prompt() contains LLD, repo structure, path enforcement
- build_single_file_prompt() no longer contains LLD content
- call_claude_for_file() passes system= kwarg when system_prompt provided
- Two different files produce identical system prompts
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.workflows.testing.nodes.implementation.prompts import (
    build_single_file_prompt,
    build_stable_system_prompt,
)


# ---------------------------------------------------------------------------
# build_stable_system_prompt tests
# ---------------------------------------------------------------------------


class TestBuildStableSystemPrompt:
    """Verify stable system prompt contains all expected stable content."""

    def test_contains_lld_content(self):
        lld = "## Section 2.1\nFiles to modify:\n- foo.py"
        result = build_stable_system_prompt(lld_content=lld)
        assert lld in result

    def test_contains_repo_structure(self):
        repo_tree = "src/\n  foo.py\n  bar.py"
        result = build_stable_system_prompt(
            lld_content="lld", repo_structure=repo_tree
        )
        assert repo_tree in result
        assert "Repository Structure" in result

    def test_contains_path_enforcement(self):
        path_section = "## Allowed Paths\n- src/foo.py"
        result = build_stable_system_prompt(
            lld_content="lld", path_enforcement_section=path_section
        )
        assert path_section in result

    def test_contains_test_content(self):
        tests = "def test_foo():\n    assert True"
        result = build_stable_system_prompt(
            lld_content="lld", test_content=tests
        )
        assert tests in result
        assert "Tests That Must Pass" in result

    def test_contains_context_content(self):
        ctx = "This module handles authentication."
        result = build_stable_system_prompt(
            lld_content="lld", context_content=ctx
        )
        assert ctx in result
        assert "Additional Context" in result

    def test_omits_empty_sections(self):
        result = build_stable_system_prompt(lld_content="lld")
        assert "Repository Structure" not in result
        assert "Additional Context" not in result
        assert "Tests That Must Pass" not in result

    def test_identical_across_files(self):
        """Two different files must produce the same stable system prompt."""
        kwargs = dict(
            lld_content="## Files\n- a.py\n- b.py",
            repo_structure="src/\n  a.py\n  b.py",
            path_enforcement_section="## Allowed\n- a.py\n- b.py",
            test_content="def test_a(): pass",
            context_content="context here",
        )
        prompt_a = build_stable_system_prompt(**kwargs)
        prompt_b = build_stable_system_prompt(**kwargs)
        assert prompt_a == prompt_b


# ---------------------------------------------------------------------------
# build_single_file_prompt no longer contains LLD
# ---------------------------------------------------------------------------


class TestSingleFilePromptExcludesStableContent:
    """Verify per-file prompt does not duplicate stable system content."""

    def test_no_lld_in_user_prompt(self):
        """LLD content should NOT appear in the per-file user prompt."""
        lld = "This is the LLD specification for issue 643."
        prompt = build_single_file_prompt(
            filepath="src/foo.py",
            file_spec={"path": "src/foo.py", "change_type": "Add", "description": "foo"},
            lld_content=lld,
            completed_files=[],
            repo_root=Path("/tmp/fake"),
        )
        assert lld not in prompt

    def test_no_repo_structure_in_user_prompt(self):
        repo_tree = "src/\n  foo.py"
        prompt = build_single_file_prompt(
            filepath="src/foo.py",
            file_spec={"path": "src/foo.py", "change_type": "Add", "description": "foo"},
            lld_content="lld",
            completed_files=[],
            repo_root=Path("/tmp/fake"),
            repo_structure=repo_tree,
        )
        assert "Repository Structure" not in prompt

    def test_no_test_content_in_user_prompt(self):
        tests = "def test_something(): pass"
        prompt = build_single_file_prompt(
            filepath="src/foo.py",
            file_spec={"path": "src/foo.py", "change_type": "Add", "description": "foo"},
            lld_content="lld",
            completed_files=[],
            repo_root=Path("/tmp/fake"),
            test_content=tests,
        )
        assert "Tests That Must Pass" not in prompt

    def test_still_contains_per_file_content(self):
        """Per-file content like filepath, change type, output format must remain."""
        prompt = build_single_file_prompt(
            filepath="src/foo.py",
            file_spec={"path": "src/foo.py", "change_type": "Add", "description": "A new module"},
            lld_content="lld",
            completed_files=[],
            repo_root=Path("/tmp/fake"),
        )
        assert "src/foo.py" in prompt
        assert "Add" in prompt
        assert "Output Format" in prompt

    def test_completed_files_still_in_user_prompt(self):
        prompt = build_single_file_prompt(
            filepath="src/bar.py",
            file_spec={"path": "src/bar.py", "change_type": "Add", "description": "bar"},
            lld_content="lld",
            completed_files=[("src/foo.py", "def foo(): pass")],
            repo_root=Path("/tmp/fake"),
        )
        assert "Previously Implemented" in prompt
        assert "src/foo.py" in prompt

    def test_error_context_still_in_user_prompt(self):
        prompt = build_single_file_prompt(
            filepath="src/bar.py",
            file_spec={"path": "src/bar.py", "change_type": "Add", "description": "bar"},
            lld_content="lld",
            completed_files=[],
            repo_root=Path("/tmp/fake"),
            previous_error="NameError: name 'x' is not defined",
        )
        assert "Previous Attempt Failed" in prompt
        assert "NameError" in prompt


# ---------------------------------------------------------------------------
# call_claude_for_file passes system_prompt through
# ---------------------------------------------------------------------------


class TestCallClaudeSystemPrompt:
    """Verify system_prompt parameter is passed through to provider.

    Issue #783: Tests updated to mock get_provider instead of SDK/CLI internals.
    """

    def test_provider_receives_system_prompt(self):
        """When system_prompt is provided, provider.invoke() receives it."""
        from assemblyzero.core.llm_provider import LLMCallResult

        mock_provider = MagicMock()
        mock_provider.invoke.return_value = LLMCallResult(
            success=True,
            response="```python\nprint('hi')\n```",
            raw_response="```python\nprint('hi')\n```",
            error_message=None,
            provider="claude",
            model_used="opus",
            duration_ms=1000,
            attempts=1,
        )

        with patch(
            "assemblyzero.workflows.testing.nodes.implementation.claude_client.get_provider",
            return_value=mock_provider,
        ):
            from assemblyzero.workflows.testing.nodes.implementation.claude_client import (
                call_claude_for_file,
            )

            stable_prompt = "You are a file generator.\n## LLD\nSome LLD content here."
            call_claude_for_file(
                prompt="# Implement foo.py",
                file_path="foo.py",
                system_prompt=stable_prompt,
            )

            call_kwargs = mock_provider.invoke.call_args
            assert call_kwargs.kwargs["system_prompt"] == stable_prompt

    def test_fallback_system_prompt_when_none_provided(self):
        """When system_prompt is empty, build_system_prompt fallback is used."""
        from assemblyzero.core.llm_provider import LLMCallResult

        mock_provider = MagicMock()
        mock_provider.invoke.return_value = LLMCallResult(
            success=True,
            response="```python\nprint('hi')\n```",
            raw_response="```python\nprint('hi')\n```",
            error_message=None,
            provider="claude",
            model_used="opus",
            duration_ms=1000,
            attempts=1,
        )

        with patch(
            "assemblyzero.workflows.testing.nodes.implementation.claude_client.get_provider",
            return_value=mock_provider,
        ):
            from assemblyzero.workflows.testing.nodes.implementation.claude_client import (
                call_claude_for_file,
            )

            call_claude_for_file(prompt="# Implement foo.py", file_path="foo.py")

            call_kwargs = mock_provider.invoke.call_args
            system_val = call_kwargs.kwargs["system_prompt"]
            # Should be the default build_system_prompt output
            assert "file generator" in system_val.lower()

    def test_provider_receives_custom_system_prompt(self):
        """Custom system_prompt passes through verbatim to provider."""
        from assemblyzero.core.llm_provider import LLMCallResult

        mock_provider = MagicMock()
        mock_provider.invoke.return_value = LLMCallResult(
            success=True,
            response="code",
            raw_response="code",
            error_message=None,
            provider="claude",
            model_used="opus",
            duration_ms=500,
            attempts=1,
        )

        with patch(
            "assemblyzero.workflows.testing.nodes.implementation.claude_client.get_provider",
            return_value=mock_provider,
        ):
            from assemblyzero.workflows.testing.nodes.implementation.claude_client import (
                call_claude_for_file,
            )

            stable = "Stable system prompt with LLD"
            call_claude_for_file(
                prompt="# Implement foo.py",
                file_path="foo.py",
                system_prompt=stable,
            )

            call_kwargs = mock_provider.invoke.call_args
            assert call_kwargs.kwargs["system_prompt"] == stable
