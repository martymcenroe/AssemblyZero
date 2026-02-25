"""Tests for Issue #447: File type detection utility.

Tests the file extension → language tag / content descriptor mapping.
"""

import pytest

from assemblyzero.utils.file_type import (
    get_file_type_info,
    get_language_tag,
    get_content_descriptor,
    FILE_TYPE_REGISTRY,
)


class TestGetFileTypeInfo:
    """Tests for get_file_type_info()."""

    def test_python_file(self):
        info = get_file_type_info("assemblyzero/nodes/foo.py")
        assert info["language_tag"] == "python"
        assert info["content_descriptor"] == "Python code"
        assert info["is_code"] is True

    def test_markdown_file(self):
        info = get_file_type_info(".claude/commands/test-gaps.md")
        assert info["language_tag"] == "markdown"
        assert info["content_descriptor"] == "Markdown content"
        assert info["is_code"] is False

    def test_yaml_file(self):
        info = get_file_type_info("config/settings.yaml")
        assert info["language_tag"] == "yaml"
        assert info["is_code"] is False

    def test_yml_alias(self):
        info = get_file_type_info(".github/workflows/ci.yml")
        assert info["language_tag"] == "yaml"

    def test_json_file(self):
        info = get_file_type_info("package.json")
        assert info["language_tag"] == "json"
        assert info["is_code"] is False

    def test_toml_file(self):
        info = get_file_type_info("pyproject.toml")
        assert info["language_tag"] == "toml"

    def test_shell_script(self):
        info = get_file_type_info("scripts/deploy.sh")
        assert info["language_tag"] == "bash"
        assert info["is_code"] is True

    def test_javascript(self):
        info = get_file_type_info("src/index.js")
        assert info["language_tag"] == "javascript"
        assert info["is_code"] is True

    def test_typescript(self):
        info = get_file_type_info("src/app.ts")
        assert info["language_tag"] == "typescript"
        assert info["is_code"] is True

    def test_unknown_extension(self):
        info = get_file_type_info("data/something.xyz")
        assert info["language_tag"] == ""
        assert info["content_descriptor"] == "file content"
        assert info["is_code"] is False

    def test_extensionless_file(self):
        info = get_file_type_info("Makefile")
        assert info["language_tag"] == ""
        assert info["is_code"] is False

    def test_case_insensitive(self):
        info = get_file_type_info("README.MD")
        assert info["language_tag"] == "markdown"


class TestGetLanguageTag:
    """Tests for get_language_tag()."""

    def test_python(self):
        assert get_language_tag("foo.py") == "python"

    def test_markdown(self):
        assert get_language_tag("foo.md") == "markdown"

    def test_unknown(self):
        assert get_language_tag("foo.xyz") == ""


class TestGetContentDescriptor:
    """Tests for get_content_descriptor()."""

    def test_python(self):
        assert get_content_descriptor("foo.py") == "Python code"

    def test_markdown(self):
        assert get_content_descriptor("foo.md") == "Markdown content"

    def test_unknown(self):
        assert get_content_descriptor("foo.xyz") == "file content"


class TestNoExternalDeps:
    """REQ-6: file_type.py uses only stdlib imports."""

    def test_only_stdlib_imports(self):
        import importlib
        import inspect
        mod = importlib.import_module("assemblyzero.utils.file_type")
        source = inspect.getsource(mod)
        # Should not import any third-party packages
        assert "import requests" not in source
        assert "import anthropic" not in source
        assert "import langchain" not in source
