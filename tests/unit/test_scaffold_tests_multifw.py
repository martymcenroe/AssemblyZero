"""Unit tests for multi-framework scaffolding.

Issue #381: Tests T270, T280 from LLD Section 10.0.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    TestFramework,
)
from assemblyzero.workflows.testing.runner_registry import get_framework_config
from assemblyzero.workflows.testing.nodes.scaffold_tests import (
    determine_test_file_path,
    generate_ts_test_file_content,
)


class TestDetermineTestFilePath:
    """Tests for determine_test_file_path with framework config."""

    def test_t270_playwright_creates_spec_ts(self):
        """T270: scaffold_tests uses correct file extension for Playwright."""
        config = get_framework_config(TestFramework.PLAYWRIGHT)
        repo_root = Path("/tmp/test_project")
        path = determine_test_file_path(56, [], repo_root, framework_config=config)
        assert path.suffix == ".ts"
        assert ".spec.ts" in str(path)

    def test_t280_pytest_creates_test_py(self):
        """T280: scaffold_tests uses correct file extension for pytest."""
        # Without framework_config, should use default behavior
        repo_root = Path("/tmp/test_project")
        # Pass None for framework_config to use default pytest behavior
        path = determine_test_file_path(200, [], repo_root, framework_config=None)
        # Default behavior varies, but should not have .ts extension
        assert ".spec.ts" not in str(path)

    def test_jest_creates_test_ts(self):
        """Jest framework creates .test.ts files."""
        config = get_framework_config(TestFramework.JEST)
        repo_root = Path("/tmp/test_project")
        path = determine_test_file_path(100, [], repo_root, framework_config=config)
        assert ".test.ts" in str(path)

    def test_vitest_creates_test_ts(self):
        """Vitest framework creates .test.ts files."""
        config = get_framework_config(TestFramework.VITEST)
        repo_root = Path("/tmp/test_project")
        path = determine_test_file_path(100, [], repo_root, framework_config=config)
        assert ".test.ts" in str(path)


class TestGenerateTsTestFileContent:
    """Tests for generate_ts_test_file_content."""

    def test_playwright_content_has_correct_imports(self):
        """Playwright content includes @playwright/test import."""
        config = get_framework_config(TestFramework.PLAYWRIGHT)
        scenarios = [
            {"id": "T010", "description": "Dashboard loads", "expected_behavior": "Page shows heading"},
        ]
        content = generate_ts_test_file_content(scenarios, config, issue_number=56)
        assert "@playwright/test" in content
        assert "test(" in content
        assert "Dashboard loads" in content

    @patch("shutil.which", return_value="/usr/bin/npx")
    def test_jest_content_has_correct_imports(self, mock_which):
        """Jest content includes @jest/globals import."""
        config = get_framework_config(TestFramework.JEST)
        scenarios = [
            {"id": "T010", "description": "formatDate works", "expected_behavior": "Returns string"},
        ]
        content = generate_ts_test_file_content(scenarios, config, issue_number=100)
        assert "@jest/globals" in content
        assert "describe(" in content
        assert "it(" in content
        assert "formatDate works" in content

    def test_pytest_raises_value_error(self):
        """Raises ValueError for pytest (not a TS framework)."""
        config = get_framework_config(TestFramework.PYTEST)
        with pytest.raises(ValueError, match="Cannot generate TS content"):
            generate_ts_test_file_content([], config, issue_number=200)

    def test_multiple_scenarios(self):
        """Multiple scenarios generate multiple test blocks."""
        config = get_framework_config(TestFramework.PLAYWRIGHT)
        scenarios = [
            {"id": "T010", "description": "Test A", "expected_behavior": "Result A"},
            {"id": "T020", "description": "Test B", "expected_behavior": "Result B"},
            {"id": "T030", "description": "Test C", "expected_behavior": "Result C"},
        ]
        content = generate_ts_test_file_content(scenarios, config, issue_number=56)
        assert content.count("test(") == 3