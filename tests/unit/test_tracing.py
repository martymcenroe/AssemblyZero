"""Tests for LangSmith tracing configuration — Issue #120."""

import os
from unittest.mock import patch

from assemblyzero.tracing import configure_langsmith, DEFAULT_PROJECT


class TestConfigureLangsmith:
    """Tests for configure_langsmith()."""

    def test_disabled_without_api_key(self):
        """Tracing disabled when no LANGSMITH_API_KEY."""
        env = dict(os.environ)
        env.pop("LANGSMITH_API_KEY", None)
        with patch.dict(os.environ, env, clear=True):
            result = configure_langsmith()
            assert result is False
            assert os.environ.get("LANGCHAIN_TRACING_V2") == "false"

    def test_enabled_with_api_key(self):
        """Tracing enabled when LANGSMITH_API_KEY is set."""
        with patch.dict(os.environ, {"LANGSMITH_API_KEY": "test-key-123"}):
            result = configure_langsmith()

        assert result is True

    def test_sets_project_name(self):
        """Sets LANGCHAIN_PROJECT to default project name."""
        with patch.dict(os.environ, {"LANGSMITH_API_KEY": "test-key-123"}):
            configure_langsmith()
            assert os.environ.get("LANGCHAIN_PROJECT") == DEFAULT_PROJECT

    def test_custom_project_name(self):
        """Accepts custom project name."""
        with patch.dict(os.environ, {"LANGSMITH_API_KEY": "test-key-123"}):
            configure_langsmith(project_name="custom-project")
            assert os.environ.get("LANGCHAIN_PROJECT") == "custom-project"

    def test_default_project_is_assemblyzero(self):
        """Default project name is 'AssemblyZero'."""
        assert DEFAULT_PROJECT == "AssemblyZero"

    def test_sets_tracing_v2_true(self):
        """Sets LANGCHAIN_TRACING_V2 to 'true' when enabled."""
        with patch.dict(os.environ, {"LANGSMITH_API_KEY": "test-key-123"}):
            configure_langsmith()
            assert os.environ.get("LANGCHAIN_TRACING_V2") == "true"

    def test_empty_api_key_disables(self):
        """Empty string API key counts as missing."""
        with patch.dict(os.environ, {"LANGSMITH_API_KEY": ""}):
            result = configure_langsmith()
        assert result is False
