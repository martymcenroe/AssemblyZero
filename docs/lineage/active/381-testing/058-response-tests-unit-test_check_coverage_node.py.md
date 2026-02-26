

```python
"""Unit tests for the check_coverage node.

Issue #381: Tests T210, T300, T310, T320 from LLD Section 10.0.
"""

from unittest.mock import patch, MagicMock

import pytest

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    TestFramework,
)
from assemblyzero.workflows.testing.runner_registry import get_framework_config
from assemblyzero.workflows.testing.nodes.check_coverage import check_coverage


class TestScenarioCoverage:
    """Tests for scenario-based coverage (Playwright)."""

    def test_t210_scenario_coverage_math(self):
        """T210: compute_scenario_coverage calculates correctly."""
        # Tested indirectly through check_coverage node
        from assemblyzero.workflows.testing.runners.base_runner import BaseTestRunner
        from assemblyzero.workflows.testing.runners.pytest_runner import PytestRunner

        config = get_framework_config(TestFramework.PYTEST)
        runner = PytestRunner(config, "/tmp")

        # 38/38 = 100%
        result_full = {"passed": 38, "failed": 0}
        assert runner.compute_scenario_coverage(result_full, 38) == 1.0

        # 35/38 ≈ 92.1%
        result_partial = {"passed": 35, "failed": 3}
        cov = runner.compute_scenario_coverage(result_partial, 38)
        assert abs(cov - 0.9210526315789473) < 0.0001

        # 0/0 = 0.0 (no ZeroDivisionError)
        result_empty = {"passed": 0, "failed": 0}
        assert runner.compute_scenario_coverage(result_empty, 0) == 0.0

    @patch("shutil.which", return_value="/usr/bin/npx")
    def test_t300_scenario_coverage_for_e2e(self, mock_which):
        """T300: check_coverage uses scenario coverage for e2e (38/38 = 100%)."""
        config = get_framework_config(TestFramework.PLAYWRIGHT)

        with patch(
            "assemblyzero.workflows.testing.nodes.check_coverage.get_runner"
        ) as mock_get_runner:
            mock_runner = MagicMock()
            mock_runner.compute_scenario_coverage.return_value = 1.0
            mock_get_runner.return_value = mock_runner

            state = {
                "issue_number": 56,
                "test_run_result": {
                    "passed": 38, "failed": 0, "skipped": 0, "errors": 0,
                    "total": 38, "coverage_percent": 0.0,
                    "coverage_type": CoverageType.SCENARIO,
                    "raw_output": "", "exit_code": 0,
                    "framework": TestFramework.PLAYWRIGHT,
                },
                "framework_config": config,
                "total_scenarios": 38,
            }
            result = check_coverage(state)
            assert result["green"] is True
            assert result["iterate_reason"] == ""

    @patch("shutil.which", return_value="/usr/bin/npx")
    def test_scenario_coverage_below_target(self, mock_which):
        """Scenario coverage below target → not green."""
        config = get_framework_config(TestFramework.PLAYWRIGHT)

        with patch(
            "assemblyzero.workflows.testing.nodes.check_coverage.get_runner"
        ) as mock_get_runner:
            mock_runner = MagicMock()
            mock_runner.compute_scenario_coverage.return_value = 0.80
            mock_get_runner.return_value = mock_runner

            state = {
                "issue_number": 56,
                "test_run_result": {
                    "passed": 30, "failed": 0, "skipped": 0, "errors": 0,
                    "total": 30, "coverage_percent": 0.0,
                    "coverage_type": CoverageType.SCENARIO,
                    "raw_output": "", "exit_code": 0,
                    "framework": TestFramework.PLAYWRIGHT,
                },
                "framework_config": config,
                "total_scenarios": 38,
            }
            result = check_coverage(state)
            assert result["green"] is False
            assert "Scenario coverage" in result["iterate_reason"]


class TestLineCoverage:
    """Tests for line-based coverage (pytest, Jest)."""

    def test_t310_line_coverage_for_pytest(self):
        """T310: check_coverage uses line coverage for pytest."""
        config = get_framework_config(TestFramework.PYTEST)
        state = {
            "issue_number": 200,
            "test_run_result": {
                "passed": 15, "failed": 0, "skipped": 0, "errors": 0,
                "total": 15, "coverage_percent": 97.0,
                "coverage_type": CoverageType.LINE,
                "raw_output": "", "exit_code": 0,
                "framework": TestFramework.PYTEST,
            },
            "framework_config": config,
        }
        result = check_coverage(state)
        assert result["green"] is True

    def test_line_coverage_below_target(self):
        """Line coverage below target → not green."""
        config = get_framework_config(TestFramework.PYTEST)
        state = {
            "issue_number": 200,
            "test_run_result": {
                "passed": 15, "failed": 0, "skipped": 0, "errors": 0,
                "total": 15, "coverage_percent": 72.5,
                "coverage_type": CoverageType.LINE,
                "raw_output": "", "exit_code": 0,
                "framework": TestFramework.PYTEST,
            },
            "framework_config": config,
        }
        result = check_coverage(state)
        assert result["green"] is False
        assert "Line coverage 72.5%" in result["iterate_reason"]
        assert "95.0%" in result["iterate_reason"]


class TestNoneCoverage:
    """Tests for coverage_type NONE."""

    def test_t320_none_coverage_skips_check(self):
        """T320: check_coverage with coverage_type NONE skips coverage check."""
        config = get_framework_config(TestFramework.PYTEST)
        config["coverage_type"] = CoverageType.NONE  # Override for test

        state = {
            "issue_number": 300,
            "test_run_result": {
                "passed": 10, "failed": 0, "skipped": 0, "errors": 0,
                "total": 10, "coverage_percent": 0.0,
                "coverage_type": CoverageType.NONE,
                "raw_output": "", "exit_code": 0,
                "framework": TestFramework.PYTEST,
            },
            "framework_config": config,
        }
        result = check_coverage(state)
        assert result["green"] is True


class TestFailureHandling:
    """Tests for test failure detection."""

    def test_failed_tests_not_green(self):
        """Failed tests → not green, regardless of coverage."""
        config = get_framework_config(TestFramework.PYTEST)
        state = {
            "issue_number": 200,
            "test_run_result": {
                "passed": 12, "failed": 3, "skipped": 0, "errors": 0,
                "total": 15, "coverage_percent": 97.0,
                "coverage_type": CoverageType.LINE,
                "raw_output": "", "exit_code": 1,
                "framework": TestFramework.PYTEST,
            },
            "framework_config": config,
        }
        result = check_coverage(state)
        assert result["green"] is False
        assert "3 tests failed" in result["iterate_reason"]

    def test_errors_not_green(self):
        """Test errors → not green."""
        config = get_framework_config(TestFramework.PYTEST)
        state = {
            "issue_number": 200,
            "test_run_result": {
                "passed": 10, "failed": 0, "skipped": 0, "errors": 2,
                "total": 12, "coverage_percent": 90.0,
                "coverage_type": CoverageType.LINE,
                "raw_output": "", "exit_code": 1,
                "framework": TestFramework.PYTEST,
            },
            "framework_config": config,
        }
        result = check_coverage(state)
        assert result["green"] is False
        assert "2 test errors" in result["iterate_reason"]

    def test_no_test_results(self):
        """Missing test results → not green."""
        state = {
            "issue_number": 200,
            "test_run_result": None,
            "framework_config": get_framework_config(TestFramework.PYTEST),
        }
        result = check_coverage(state)
        assert result["green"] is False
        assert "No test results" in result["iterate_reason"]

    def test_zero_scenarios_not_green(self):
        """Zero total scenarios for SCENARIO type → not green."""
        config = get_framework_config(TestFramework.PLAYWRIGHT)

        state = {
            "issue_number": 56,
            "test_run_result": {
                "passed": 0, "failed": 0, "skipped": 0, "errors": 0,
                "total": 0, "coverage_percent": 0.0,
                "coverage_type": CoverageType.SCENARIO,
                "raw_output": "", "exit_code": 0,
                "framework": TestFramework.PLAYWRIGHT,
            },
            "framework_config": config,
            "total_scenarios": 0,
        }
        result = check_coverage(state)
        assert result["green"] is False
        assert "No scenarios" in result["iterate_reason"]

    def test_t340_backward_compat_pytest(self):
        """T340: Standard pytest state works with backward compatibility."""
        config = get_framework_config(TestFramework.PYTEST)
        state = {
            "issue_number": 200,
            "test_run_result": {
                "passed": 20, "failed": 0, "skipped": 0, "errors": 0,
                "total": 20, "coverage_percent": 96.0,
                "coverage_type": CoverageType.LINE,
                "raw_output": "20 passed", "exit_code": 0,
                "framework": TestFramework.PYTEST,
            },
            "framework_config": config,
        }
        result = check_coverage(state)
        assert result["green"] is True
        assert result["iterate_reason"] == ""

    def test_no_framework_config_defaults_to_pytest(self):
        """Missing framework_config defaults to pytest config."""
        state = {
            "issue_number": 200,
            "test_run_result": {
                "passed": 10, "failed": 0, "skipped": 0, "errors": 0,
                "total": 10, "coverage_percent": 96.0,
                "coverage_type": CoverageType.LINE,
                "raw_output": "", "exit_code": 0,
                "framework": TestFramework.PYTEST,
            },
            "framework_config": None,
        }
        result = check_coverage(state)
        assert result["green"] is True
```
