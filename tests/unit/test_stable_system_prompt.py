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
    """Verify system_prompt parameter is passed to SDK."""

    @patch("assemblyzero.workflows.testing.nodes.implementation.claude_client._find_claude_cli")
    def test_sdk_receives_system_kwarg_with_cache_control(self, mock_cli):
        """When system_prompt is provided, SDK stream() gets structured system block with cache_control."""
        mock_cli.return_value = None  # Force SDK path

        mock_final_msg = MagicMock()
        mock_final_msg.usage.cache_read_input_tokens = 0
        mock_final_msg.usage.cache_creation_input_tokens = 100

        mock_stream = MagicMock()
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=False)
        mock_stream.text_stream = ["```python\nprint('hi')\n```"]
        mock_stream.get_final_message.return_value = mock_final_msg

        mock_anthropic = MagicMock()
        mock_client = MagicMock()
        mock_client.messages.stream.return_value = mock_stream
        mock_anthropic.Anthropic.return_value = mock_client

        import sys
        with patch.dict(sys.modules, {"anthropic": mock_anthropic, "httpx": MagicMock()}):
            from assemblyzero.workflows.testing.nodes.implementation.claude_client import (
                call_claude_for_file,
            )

            stable_prompt = "You are a file generator.\n## LLD\nSome LLD content here."
            call_claude_for_file(
                prompt="# Implement foo.py",
                file_path="foo.py",
                system_prompt=stable_prompt,
            )

            call_kwargs = mock_client.messages.stream.call_args
            system_val = call_kwargs.kwargs["system"]
            # Issue #625: Must be structured block list with cache_control
            assert isinstance(system_val, list)
            assert len(system_val) == 1
            assert system_val[0]["type"] == "text"
            assert system_val[0]["text"] == stable_prompt
            assert system_val[0]["cache_control"] == {"type": "ephemeral"}

    @patch("assemblyzero.workflows.testing.nodes.implementation.claude_client._find_claude_cli")
    def test_sdk_no_system_prompt_still_works(self, mock_cli):
        """When system_prompt is empty, SDK uses build_system_prompt fallback with cache_control."""
        mock_cli.return_value = None

        mock_final_msg = MagicMock()
        mock_final_msg.usage.cache_read_input_tokens = 0
        mock_final_msg.usage.cache_creation_input_tokens = 0

        mock_stream = MagicMock()
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=False)
        mock_stream.text_stream = ["```python\nprint('hi')\n```"]
        mock_stream.get_final_message.return_value = mock_final_msg

        mock_anthropic = MagicMock()
        mock_client = MagicMock()
        mock_client.messages.stream.return_value = mock_stream
        mock_anthropic.Anthropic.return_value = mock_client

        import sys
        with patch.dict(sys.modules, {"anthropic": mock_anthropic, "httpx": MagicMock()}):
            from assemblyzero.workflows.testing.nodes.implementation.claude_client import (
                call_claude_for_file,
            )

            call_claude_for_file(prompt="# Implement foo.py", file_path="foo.py")

            call_kwargs = mock_client.messages.stream.call_args
            system_val = call_kwargs.kwargs["system"]
            # Should be structured block list even for fallback
            assert isinstance(system_val, list)
            assert system_val[0]["cache_control"] == {"type": "ephemeral"}
            assert "file generator" in system_val[0]["text"].lower()

    @patch("assemblyzero.workflows.testing.nodes.implementation.claude_client._find_claude_cli")
    @patch("assemblyzero.workflows.testing.nodes.implementation.claude_client.run_command")
    def test_cli_receives_system_prompt(self, mock_run, mock_cli):
        """CLI path should use the provided system_prompt."""
        mock_cli.return_value = "/usr/bin/claude"
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "```python\nprint('hi')\n```"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        from assemblyzero.workflows.testing.nodes.implementation.claude_client import (
            call_claude_for_file,
        )

        stable = "Stable system prompt with LLD"
        call_claude_for_file(
            prompt="# Implement foo.py",
            file_path="foo.py",
            system_prompt=stable,
        )

        cmd_args = mock_run.call_args[0][0]
        # Find --system-prompt flag and its value
        idx = cmd_args.index("--system-prompt")
        assert cmd_args[idx + 1] == stable


# ---------------------------------------------------------------------------
# Issue #625: Cache metric logging
# ---------------------------------------------------------------------------


class TestCacheMetricLogging:
    """Verify cache metrics are logged when present."""

    @patch("assemblyzero.workflows.testing.nodes.implementation.claude_client._find_claude_cli")
    def test_cache_log_printed_when_nonzero(self, mock_cli, capsys):
        """[CACHE] log line should appear when cache_read or cache_create > 0."""
        mock_cli.return_value = None

        mock_final_msg = MagicMock()
        mock_final_msg.usage.cache_read_input_tokens = 5000
        mock_final_msg.usage.cache_creation_input_tokens = 0

        mock_stream = MagicMock()
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=False)
        mock_stream.text_stream = ["```python\nprint('hi')\n```"]
        mock_stream.get_final_message.return_value = mock_final_msg

        mock_anthropic = MagicMock()
        mock_client = MagicMock()
        mock_client.messages.stream.return_value = mock_stream
        mock_anthropic.Anthropic.return_value = mock_client

        import sys
        with patch.dict(sys.modules, {"anthropic": mock_anthropic, "httpx": MagicMock()}):
            from assemblyzero.workflows.testing.nodes.implementation.claude_client import (
                call_claude_for_file,
            )
            call_claude_for_file(prompt="# foo", file_path="foo.py", system_prompt="stable")

        captured = capsys.readouterr()
        assert "[CACHE] read=5000 create=0" in captured.out

    @patch("assemblyzero.workflows.testing.nodes.implementation.claude_client._find_claude_cli")
    def test_cache_log_not_printed_when_zero(self, mock_cli, capsys):
        """No [CACHE] log when both cache metrics are 0."""
        mock_cli.return_value = None

        mock_final_msg = MagicMock()
        mock_final_msg.usage.cache_read_input_tokens = 0
        mock_final_msg.usage.cache_creation_input_tokens = 0

        mock_stream = MagicMock()
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=False)
        mock_stream.text_stream = ["```python\nprint('hi')\n```"]
        mock_stream.get_final_message.return_value = mock_final_msg

        mock_anthropic = MagicMock()
        mock_client = MagicMock()
        mock_client.messages.stream.return_value = mock_stream
        mock_anthropic.Anthropic.return_value = mock_client

        import sys
        with patch.dict(sys.modules, {"anthropic": mock_anthropic, "httpx": MagicMock()}):
            from assemblyzero.workflows.testing.nodes.implementation.claude_client import (
                call_claude_for_file,
            )
            call_claude_for_file(prompt="# foo", file_path="foo.py", system_prompt="stable")

        captured = capsys.readouterr()
        assert "[CACHE]" not in captured.out
