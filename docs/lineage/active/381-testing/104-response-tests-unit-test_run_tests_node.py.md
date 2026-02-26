

```python
"""Unit tests for the run_tests node.

Issue #381: Tests T290, T260 from LLD Section 10.0.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    TestFramework,
    TestRunResult,
)
from assemblyzero.workflows.testing.runner_registry import get_framework_config
from assemblyzero.workflows.testing.nodes.run_tests import run_tests


@pytest.fixture
def valid_playwright_test_file(tmp_path):
    """Create a valid Playwright test file."""
    test_file = tmp_path / "tests" / "dashboard.spec.ts"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text(
        "import { test, expect } from '@playwright/test';\n"
        "test('works', async ({ page }) => {\n"
        "  await expect(page).toBeTruthy();\n"
        "});\n"
    )
    return str(test_file)


@pytest.fixture
def valid_pytest_file(tmp_path):
    """Create a valid pytest file."""
    test_file = tmp_path / "tests" / "test_example.py"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text(
        "import pytest\n\n"
        "def test_example():\n"
        "    assert True\n"
    )
    return str(test_file)


class TestRunTestsNode:
    """Tests for run_tests() node function."""

    def test_no_test_files(self):
        """Returns error when no test files in state."""
        state = {"issue_number": 100, "test_files": [], "framework_config": None}
        result = run_tests(state)
        assert result["error_message"] == "No test files to run"

    def test_default_pytest_when_no_config(self, valid_pytest_file):
        """Falls back to pytest config when framework_config missing."""
        with patch(
            "assemblyzero.workflows.testing.nodes.run_tests.get_runner"
        ) as mock_get_runner:
            mock_runner = MagicMock()
            mock_runner.validate_test_file.return_value = []
            mock_runner.run_tests.return_value = {
                "passed": 1, "failed": 0, "skipped": 0, "errors": 0,
                "total": 1, "coverage_percent": 100.0,
                "coverage_type": CoverageType.LINE,
                "raw_output": "1 passed", "exit_code": 0,
                "framework": TestFramework.PYTEST,
            }
            mock_get_runner.return_value = mock_runner

            state = {
                "issue_number": 200,
                "test_files": [valid_pytest_file],
                "framework_config": None,
                "repo_root": "/tmp",
            }
            result = run_tests(state)
            assert result["error_message"] == ""
            assert result["test_run_result"]["passed"] == 1

    @patch("shutil.which", return_value="/usr/bin/npx")
    def test_t290_playwright_validation(self, mock_which, valid_playwright_test_file):
        """T290: run_tests delegates to runner.validate_test_file for Playwright."""
        with patch(
            "assemblyzero.workflows.testing.nodes.run_tests.get_runner"
        ) as mock_get_runner:
            mock_runner = MagicMock()
            mock_runner.validate_test_file.return_value = []
            mock_runner.run_tests.return_value = {
                "passed": 1, "failed": 0, "skipped": 0, "errors": 0,
                "total": 1, "coverage_percent": 0.0,
                "coverage_type": CoverageType.SCENARIO,
                "raw_output": "{}", "exit_code": 0,
                "framework": TestFramework.PLAYWRIGHT,
            }
            mock_get_runner.return_value = mock_runner

            config = get_framework_config(TestFramework.PLAYWRIGHT)
            state = {
                "issue_number": 56,
                "test_files": [valid_playwright_test_file],
                "framework_config": config,
                "repo_root": "/tmp",
            }
            result = run_tests(state)

            # Verify validate_test_file was called with the right file
            mock_runner.validate_test_file.assert_called_once()
            call_args = mock_runner.validate_test_file.call_args
            assert "dashboard.spec.ts" in call_args[0][0]

    def test_validation_errors_stop_execution(self, tmp_path):
        """When validation fails, tests are not run."""
        bad_file = tmp_path / "tests" / "bad.spec.ts"
        bad_file.parent.mkdir(parents=True, exist_ok=True)
        bad_file.write_text("// no playwright import\n")

        with patch(
            "assemblyzero.workflows.testing.nodes.run_tests.get_runner"
        ) as mock_get_runner:
            mock_runner = MagicMock()
            mock_runner.validate_test_file.return_value = [
                "Missing '@playwright/test' import"
            ]
            mock_get_runner.return_value = mock_runner

            config = get_framework_config(TestFramework.PLAYWRIGHT)
            state = {
                "issue_number": 56,
                "test_files": [str(bad_file)],
                "framework_config": config,
                "repo_root": str(tmp_path),
            }
            result = run_tests(state)

            assert result["test_run_result"] is None
            assert len(result["validation_errors"]) > 0
            assert "validation failed" in result["error_message"]
            # run_tests should NOT have been called
            mock_runner.run_tests.assert_not_called()

    def test_environment_error_handled(self):
        """EnvironmentError (missing npx) is handled gracefully."""
        with patch(
            "assemblyzero.workflows.testing.nodes.run_tests.get_runner",
            side_effect=EnvironmentError("npx not found on PATH"),
        ):
            config = get_framework_config(TestFramework.PLAYWRIGHT)
            state = {
                "issue_number": 56,
                "test_files": ["tests/test.spec.ts"],
                "framework_config": config,
                "repo_root": "/tmp",
            }
            result = run_tests(state)
            assert "npx not found" in result["error_message"]

    def test_t260_subprocess_timeout_handled(self, valid_pytest_file):
        """T260: Subprocess timeout handled gracefully."""
        with patch(
            "assemblyzero.workflows.testing.nodes.run_tests.get_runner"
        ) as mock_get_runner:
            mock_runner = MagicMock()
            mock_runner.validate_test_file.return_value = []
            mock_runner.run_tests.return_value = {
                "passed": 0, "failed": 0, "skipped": 0, "errors": 1,
                "total": 1, "coverage_percent": 0.0,
                "coverage_type": CoverageType.LINE,
                "raw_output": "Command timed out after 300s",
                "exit_code": -1,
                "framework": TestFramework.PYTEST,
            }
            mock_get_runner.return_value = mock_runner

            state = {
                "issue_number": 200,
                "test_files": [valid_pytest_file],
                "framework_config": get_framework_config(TestFramework.PYTEST),
                "repo_root": "/tmp",
            }
            result = run_tests(state)
            assert result["test_run_result"]["exit_code"] == -1
            assert "timed out" in result["test_run_result"]["raw_output"]

    def test_unreadable_test_file(self, tmp_path):
        """Non-existent test file produces validation error."""
        with patch(
            "assemblyzero.workflows.testing.nodes.run_tests.get_runner"
        ) as mock_get_runner:
            mock_runner = MagicMock()
            mock_get_runner.return_value = mock_runner

            config = get_framework_config(TestFramework.PYTEST)
            state = {
                "issue_number": 200,
                "test_files": [str(tmp_path / "nonexistent_test.py")],
                "framework_config": config,
                "repo_root": str(tmp_path),
            }
            result = run_tests(state)
            assert result["test_run_result"] is None
            assert len(result["validation_errors"]) > 0
            assert "Cannot read test file" in result["validation_errors"][0]

    def test_runner_exception_handled(self, valid_pytest_file):
        """Generic exception during test execution is handled."""
        with patch(
            "assemblyzero.workflows.testing.nodes.run_tests.get_runner"
        ) as mock_get_runner:
            mock_runner = MagicMock()
            mock_runner.validate_test_file.return_value = []
            mock_runner.run_tests.side_effect = RuntimeError("Unexpected crash")
            mock_get_runner.return_value = mock_runner

            state = {
                "issue_number": 200,
                "test_files": [valid_pytest_file],
                "framework_config": get_framework_config(TestFramework.PYTEST),
                "repo_root": "/tmp",
            }
            result = run_tests(state)
            assert result["test_run_result"] is None
            assert "Test execution failed" in result["error_message"]
            assert "Unexpected crash" in result["error_message"]

    def test_multiple_test_files(self, tmp_path):
        """Multiple test files are all validated and passed to runner."""
        test_file_1 = tmp_path / "tests" / "test_a.py"
        test_file_2 = tmp_path / "tests" / "test_b.py"
        test_file_1.parent.mkdir(parents=True, exist_ok=True)
        test_file_1.write_text("import pytest\n\ndef test_a():\n    assert True\n")
        test_file_2.write_text("import pytest\n\ndef test_b():\n    assert True\n")

        with patch(
            "assemblyzero.workflows.testing.nodes.run_tests.get_runner"
        ) as mock_get_runner:
            mock_runner = MagicMock()
            mock_runner.validate_test_file.return_value = []
            mock_runner.run_tests.return_value = {
                "passed": 2, "failed": 0, "skipped": 0, "errors": 0,
                "total": 2, "coverage_percent": 95.0,
                "coverage_type": CoverageType.LINE,
                "raw_output": "2 passed", "exit_code": 0,
                "framework": TestFramework.PYTEST,
            }
            mock_get_runner.return_value = mock_runner

            state = {
                "issue_number": 200,
                "test_files": [str(test_file_1), str(test_file_2)],
                "framework_config": get_framework_config(TestFramework.PYTEST),
                "repo_root": str(tmp_path),
            }
            result = run_tests(state)
            assert result["error_message"] == ""
            assert result["test_run_result"]["passed"] == 2
            assert mock_runner.validate_test_file.call_count == 2
            mock_runner.run_tests.assert_called_once_with(
                test_paths=[str(test_file_1), str(test_file_2)]
            )

    @patch("shutil.which", return_value="/usr/bin/npx")
    def test_t330_full_chain_mocked(self, mock_which, valid_playwright_test_file):
        """T330: Full chain — run_tests produces result consumed by check_coverage."""
        from assemblyzero.workflows.testing.nodes.check_coverage import check_coverage

        with patch(
            "assemblyzero.workflows.testing.nodes.run_tests.get_runner"
        ) as mock_run_get_runner:
            mock_runner = MagicMock()
            mock_runner.validate_test_file.return_value = []
            mock_runner.run_tests.return_value = {
                "passed": 38, "failed": 0, "skipped": 0, "errors": 0,
                "total": 38, "coverage_percent": 0.0,
                "coverage_type": CoverageType.SCENARIO,
                "raw_output": "{}", "exit_code": 0,
                "framework": TestFramework.PLAYWRIGHT,
            }
            mock_run_get_runner.return_value = mock_runner

            config = get_framework_config(TestFramework.PLAYWRIGHT)
            state = {
                "issue_number": 56,
                "test_files": [valid_playwright_test_file],
                "framework_config": config,
                "repo_root": "/tmp",
            }
            run_result = run_tests(state)

            assert run_result["error_message"] == ""
            assert run_result["test_run_result"]["passed"] == 38

        # Now feed into check_coverage
        with patch(
            "assemblyzero.workflows.testing.nodes.check_coverage.get_runner"
        ) as mock_cov_get_runner:
            mock_cov_runner = MagicMock()
            mock_cov_runner.compute_scenario_coverage.return_value = 1.0
            mock_cov_get_runner.return_value = mock_cov_runner

            coverage_state = {
                "issue_number": 56,
                "test_run_result": run_result["test_run_result"],
                "framework_config": config,
                "total_scenarios": 38,
            }
            cov_result = check_coverage(coverage_state)
            assert cov_result["green"] is True
            assert cov_result["iterate_reason"] == ""
```
