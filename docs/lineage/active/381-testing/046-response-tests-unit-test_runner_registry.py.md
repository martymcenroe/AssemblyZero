

```python
"""Unit tests for runner registry.

Issue #381: Tests T080-T110 from LLD Section 10.0.
"""

import pytest
from unittest.mock import patch

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    TestFramework,
)
from assemblyzero.workflows.testing.runner_registry import (
    get_framework_config,
    get_runner,
)
from assemblyzero.workflows.testing.runners.base_runner import BaseTestRunner
from assemblyzero.workflows.testing.runners.pytest_runner import PytestRunner
from assemblyzero.workflows.testing.runners.playwright_runner import PlaywrightRunner
from assemblyzero.workflows.testing.runners.jest_runner import JestRunner


class TestGetFrameworkConfig:
    """Tests for get_framework_config()."""

    def test_t080_playwright_config(self):
        """T080: get_framework_config returns correct config for PLAYWRIGHT."""
        config = get_framework_config(TestFramework.PLAYWRIGHT)
        assert config["framework"] == TestFramework.PLAYWRIGHT
        assert config["test_runner_command"] == "npx playwright test"
        assert config["test_file_pattern"] == "*.spec.ts"
        assert config["test_file_extension"] == ".spec.ts"
        assert config["coverage_type"] == CoverageType.SCENARIO
        assert config["coverage_target"] == 1.0

    def test_t090_pytest_config(self):
        """T090: get_framework_config returns correct config for PYTEST."""
        config = get_framework_config(TestFramework.PYTEST)
        assert config["framework"] == TestFramework.PYTEST
        assert config["test_runner_command"] == "pytest"
        assert config["test_file_pattern"] == "test_*.py"
        assert config["test_file_extension"] == ".py"
        assert config["coverage_type"] == CoverageType.LINE
        assert config["coverage_target"] == 0.95

    def test_jest_config(self):
        """get_framework_config returns correct config for JEST."""
        config = get_framework_config(TestFramework.JEST)
        assert config["framework"] == TestFramework.JEST
        assert config["test_runner_command"] == "npx jest"
        assert config["test_file_pattern"] == "*.test.ts"
        assert config["coverage_type"] == CoverageType.LINE

    def test_vitest_config(self):
        """get_framework_config returns correct config for VITEST."""
        config = get_framework_config(TestFramework.VITEST)
        assert config["framework"] == TestFramework.VITEST
        assert config["test_runner_command"] == "npx vitest run"

    def test_config_is_copy(self):
        """Returned config should be a copy (not mutable registry)."""
        config1 = get_framework_config(TestFramework.PYTEST)
        config2 = get_framework_config(TestFramework.PYTEST)
        config1["coverage_target"] = 0.5
        assert config2["coverage_target"] == 0.95  # Unaffected


class TestGetRunner:
    """Tests for get_runner()."""

    def test_t100_pytest_runner(self):
        """T100: get_runner returns PytestRunner for PYTEST."""
        runner = get_runner(TestFramework.PYTEST)
        assert isinstance(runner, PytestRunner)
        assert isinstance(runner, BaseTestRunner)

    @patch("shutil.which", return_value="/usr/bin/npx")
    def test_t110_playwright_runner(self, mock_which):
        """T110: get_runner returns PlaywrightRunner for PLAYWRIGHT."""
        runner = get_runner(TestFramework.PLAYWRIGHT)
        assert isinstance(runner, PlaywrightRunner)
        assert isinstance(runner, BaseTestRunner)

    @patch("shutil.which", return_value="/usr/bin/npx")
    def test_jest_runner(self, mock_which):
        """get_runner returns JestRunner for JEST."""
        runner = get_runner(TestFramework.JEST)
        assert isinstance(runner, JestRunner)

    @patch("shutil.which", return_value="/usr/bin/npx")
    def test_vitest_runner(self, mock_which):
        """get_runner returns JestRunner for VITEST (shared runner)."""
        runner = get_runner(TestFramework.VITEST)
        assert isinstance(runner, JestRunner)
```
