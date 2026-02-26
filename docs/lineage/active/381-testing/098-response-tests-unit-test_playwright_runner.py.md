

```python
"""Unit tests for PlaywrightRunner.

Issue #381: Tests T140, T150, T180, T220, T250 from LLD Section 10.0.
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    TestFramework,
)
from assemblyzero.workflows.testing.runner_registry import get_framework_config
from assemblyzero.workflows.testing.runners.playwright_runner import PlaywrightRunner


@pytest.fixture
def playwright_runner():
    """Create a PlaywrightRunner with mocked npx availability."""
    with patch("shutil.which", return_value="/usr/bin/npx"):
        config = get_framework_config(TestFramework.PLAYWRIGHT)
        return PlaywrightRunner(config, project_root="/tmp/test_project")


class TestPlaywrightRunnerValidation:
    """Tests for PlaywrightRunner.validate_test_file()."""

    def test_t140_valid_spec_ts(self, playwright_runner):
        """T140: PlaywrightRunner.validate_test_file accepts valid .spec.ts."""
        content = """import { test, expect } from '@playwright/test';

test('loads dashboard', async ({ page }) => {
  await page.goto('/dashboard');
  await expect(page.locator('h1')).toHaveText('Dashboard');
});
"""
        errors = playwright_runner.validate_test_file("tests/dashboard.spec.ts", content)
        assert errors == []

    def test_t150_missing_playwright_import(self, playwright_runner):
        """T150: PlaywrightRunner.validate_test_file rejects missing imports."""
        content = """test('loads dashboard', async ({ page }) => {
  await page.goto('/dashboard');
});
"""
        errors = playwright_runner.validate_test_file("tests/dashboard.spec.ts", content)
        assert any("@playwright/test" in e for e in errors)

    def test_missing_test_calls(self, playwright_runner):
        """Reject file with no test() calls."""
        content = """import { test, expect } from '@playwright/test';

const x = 5;
console.log(x);
"""
        errors = playwright_runner.validate_test_file("tests/bad.spec.ts", content)
        assert any("No test() calls" in e for e in errors)

    def test_empty_file(self, playwright_runner):
        """Reject empty file."""
        errors = playwright_runner.validate_test_file("tests/empty.spec.ts", "")
        assert any("Empty test file" in e for e in errors)


class TestPlaywrightRunnerParseResults:
    """Tests for PlaywrightRunner.parse_results()."""

    def test_t180_parse_json_report(self, playwright_runner):
        """T180: PlaywrightRunner.parse_results handles JSON report."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "playwright_json_report.json"
        with open(fixture_path) as f:
            raw_output = f.read()

        result = playwright_runner.parse_results(raw_output, exit_code=1)
        assert result["passed"] == 2
        assert result["failed"] == 1
        assert result["skipped"] == 1
        assert result["total"] == 4
        assert result["coverage_type"] == CoverageType.SCENARIO
        assert result["framework"] == TestFramework.PLAYWRIGHT
        assert result["exit_code"] == 1

    def test_parse_all_passing(self, playwright_runner):
        """Parse all-passing Playwright report."""
        report = {
            "config": {},
            "suites": [{
                "title": "Tests",
                "specs": [
                    {"title": "t1", "tests": [{"results": [{"status": "passed"}]}]},
                    {"title": "t2", "tests": [{"results": [{"status": "passed"}]}]},
                ],
                "suites": [],
            }],
        }
        result = playwright_runner.parse_results(json.dumps(report), exit_code=0)
        assert result["passed"] == 2
        assert result["failed"] == 0
        assert result["total"] == 2

    def test_parse_invalid_json(self, playwright_runner):
        """Fallback when JSON is invalid."""
        result = playwright_runner.parse_results("not json at all", exit_code=1)
        assert result["failed"] >= 1
        assert result["errors"] >= 1

    def test_parse_nested_suites(self, playwright_runner):
        """Parse nested suite structure."""
        report = {
            "config": {},
            "suites": [{
                "title": "Root",
                "specs": [],
                "suites": [{
                    "title": "Nested",
                    "specs": [
                        {"title": "t1", "tests": [{"results": [{"status": "passed"}]}]},
                    ],
                    "suites": [],
                }],
            }],
        }
        result = playwright_runner.parse_results(json.dumps(report), exit_code=0)
        assert result["passed"] == 1
        assert result["total"] == 1


class TestPlaywrightRunnerRunTests:
    """Tests for PlaywrightRunner.run_tests()."""

    @patch.object(PlaywrightRunner, "_run_subprocess")
    def test_t220_invokes_correct_command(self, mock_subprocess, playwright_runner):
        """T220: PlaywrightRunner.run_tests invokes correct command."""
        mock_subprocess.return_value = ('{"config":{},"suites":[]}', 0)
        playwright_runner.run_tests(test_paths=["tests/dashboard.spec.ts"])

        args, _ = mock_subprocess.call_args
        command = args[0]
        assert "npx" in command
        assert "playwright" in command
        assert "test" in command
        assert "--reporter=json" in command
        assert "tests/dashboard.spec.ts" in command


class TestPlaywrightRunnerEnvironment:
    """Tests for PlaywrightRunner environment checks."""

    def test_t250_missing_npx(self):
        """T250: Runner raises EnvironmentError if npx not found."""
        with patch("shutil.which", return_value=None):
            config = get_framework_config(TestFramework.PLAYWRIGHT)
            with pytest.raises(EnvironmentError, match="npx not found"):
                PlaywrightRunner(config, "/tmp/test")


class TestPlaywrightRunnerScaffold:
    """Tests for PlaywrightRunner.get_scaffold_imports()."""

    def test_scaffold_imports(self, playwright_runner):
        """Returns correct Playwright import."""
        imports = playwright_runner.get_scaffold_imports()
        assert "@playwright/test" in imports
        assert "test" in imports
        assert "expect" in imports
```
