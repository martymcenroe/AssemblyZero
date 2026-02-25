"""Tests for Issue #447: File-type-aware prompt building and extraction in N4.

Tests that extract_code_block, build_system_prompt, and build_single_file_prompt
correctly handle non-Python files.
"""

import pytest
from pathlib import Path

from assemblyzero.workflows.testing.nodes.implement_code import (
    extract_code_block,
    build_system_prompt,
    build_single_file_prompt,
)


class TestExtractCodeBlock:
    """Tests for file-type-aware code block extraction."""

    def test_extract_python_block_for_py(self):
        response = '```python\nprint("hi")\n\ndef main():\n    pass\n```'
        result = extract_code_block(response, file_path="foo.py")
        assert result is not None
        assert 'print("hi")' in result

    def test_extract_markdown_block_for_md(self):
        response = "```markdown\n# Title\n\nSome content here with enough text to pass.\n```"
        result = extract_code_block(response, file_path="test.md")
        assert result is not None
        assert "# Title" in result

    def test_extract_yaml_block_for_yaml(self):
        response = "```yaml\nname: test\nversion: 1.0\nconfig:\n  key: value\n  other: stuff\n```"
        result = extract_code_block(response, file_path="config.yaml")
        assert result is not None
        assert "name: test" in result

    def test_fallback_to_any_block(self):
        # .md file but response has untagged block
        response = "```\n# Some markdown content\n\nWith enough lines here to pass the threshold check.\n```"
        result = extract_code_block(response, file_path="readme.md")
        assert result is not None
        assert "# Some markdown" in result

    def test_no_fenced_block_returns_none(self):
        response = "I implemented the changes. Here is what I did..."
        result = extract_code_block(response, file_path="foo.py")
        assert result is None

    def test_empty_file_path_backward_compat(self):
        response = '```python\ndef hello():\n    return "world"\n\n# More code\n```'
        result = extract_code_block(response, file_path="")
        assert result is not None
        assert "hello" in result

    def test_no_file_path_backward_compat(self):
        response = '```python\ndef hello():\n    return "world"\n\n# More code\n```'
        result = extract_code_block(response)
        assert result is not None

    def test_prefers_matching_tag(self):
        # Response has both python and markdown blocks
        response = (
            '```python\nprint("wrong")\nsome python code here for length\n```\n\n'
            '```markdown\n# Correct Content\n\nThis is the right markdown block.\n```'
        )
        result = extract_code_block(response, file_path="readme.md")
        assert result is not None
        assert "# Correct Content" in result


class TestBuildSystemPrompt:
    """Tests for file-type-aware system prompt."""

    def test_python_includes_python(self):
        prompt = build_system_prompt("foo.py")
        assert "python" in prompt.lower()

    def test_markdown_includes_markdown(self):
        prompt = build_system_prompt("test.md")
        assert "markdown" in prompt.lower()

    def test_yaml_includes_yaml(self):
        prompt = build_system_prompt("config.yaml")
        assert "yaml" in prompt.lower()

    def test_unknown_uses_generic(self):
        prompt = build_system_prompt("data.xyz")
        assert "fenced code block" in prompt.lower()
        # Should NOT contain a specific language
        assert "python" not in prompt.lower()


class TestBuildSingleFilePromptFileType:
    """Tests for file-type-aware prompt framing."""

    def _build(self, filepath: str) -> str:
        return build_single_file_prompt(
            filepath=filepath,
            file_spec={"change_type": "Add", "description": "test"},
            lld_content="# Test LLD",
            completed_files=[],
            repo_root=Path("/tmp/fake"),
        )

    def test_python_code_framing(self):
        prompt = self._build("src/module.py")
        # Should use python code block in output format
        assert "```python" in prompt

    def test_markdown_content_framing(self):
        prompt = self._build("docs/readme.md")
        # Should use markdown code block
        assert "```markdown" in prompt
        assert "Markdown content" in prompt

    def test_yaml_content_framing(self):
        prompt = self._build("config/settings.yaml")
        assert "```yaml" in prompt

    def test_unknown_generic_framing(self):
        prompt = self._build("data/file.xyz")
        # Generic block with no language tag
        assert "```\n" in prompt
