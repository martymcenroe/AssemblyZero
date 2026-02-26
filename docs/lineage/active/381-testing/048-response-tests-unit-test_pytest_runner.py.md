

```python
"""Unit tests for PytestRunner.

Issue #381: Tests T120, T130, T200, T240 from LLD Section 10.0.
"""

from unittest.mock import patch, MagicMock

import pytest

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    TestFramework,
)
from assemblyzero.workflows.testing.runner_registry import get_framework_config
from assemblyzero.workflows.testing.runners.pytest_runner import PytestRunner


@pytest.fixture
def pytest_runner():
    """Create a PytestRunner with default config."""
    config = get_framework_config(TestFramework.PYTEST)
    return PytestRunner(config, project_root="/tmp/test_project")


class TestPytestRunnerValidation:
    """Tests for PytestRunner.validate_test_file()."""

    def test_t120_valid_python_test(self, pytest_runner):
        """T120: PytestRunner.validate_test_file accepts valid Python test."""
        content = """import pytest
from mymodule import my_function

def test_my_function():
    assert my_function(42) == 84
"""
        errors = pytest_runner.validate_test_file("tests/test_example.py", content)
        assert errors == []

    def test_t130_missing_imports(self, pytest_runner):
        """T130: PytestRunner.validate_test_file rejects missing imports."""
        content = """def test_something():
    assert True
"""
        errors = pytest_runner.validate_test_file("tests/test_bad.py", content)
        assert any("No import statements" in e for e in errors)

    def test_missing_test_functions(self, pytest_runner):
        """Reject file with no test_ functions."""
        content = """import pytest

def helper():
    return 42
"""
        errors = pytest_runner.validate_test_file("tests/test_bad.py", content)
        assert any("No test functions" in e for e in errors)

    def test_empty_file(self, pytest_runner):
        """Reject empty test file."""
        errors = pytest_runner.validate_test_file("tests/test_empty.py", "")
        assert any("Empty test file" in e for e in errors)

    def test_class_based_tests_accepted(self, pytest_runner):
        """Accept class-based test style (class TestXxx)."""
        content = """import pytest

class TestMyFeature:
    def test_something(self):
        assert True
"""
        errors = pytest_runner.validate_test_file("tests/test_class.py", content)
        assert errors == []


class TestPytestRunnerParseResults:
    """Tests for PytestRunner.parse_results()."""

    def test_t200_parse_pytest_output(self, pytest_runner):
        """T200: PytestRunner.parse_results handles pytest output."""
        output = """tests/test_example.py ..F.s
============ 3 passed, 1 failed, 1 skipped in 0.25s ============
TOTAL    150     12    92%
"""
        result = pytest_runner.parse_results(output, exit_code=1)
        assert result["passed"] == 3
        assert result["failed"] == 1
        assert result["skipped"] == 1
        assert result["total"] == 5
        assert result["coverage_percent"] == 92.0
        assert result["coverage_type"] == CoverageType.LINE
        assert result["framework"] == TestFramework.PYTEST
        assert result["exit_code"] == 1

    def test_parse_all_passing(self, pytest_runner):
        """Parse all-passing output."""
        output = "10 passed in 1.5s"
        result = pytest_runner.parse_results(output, exit_code=0)
        assert result["passed"] == 10
        assert result["failed"] == 0
        assert result["exit_code"] == 0

    def test_parse_no_coverage(self, pytest_runner):
        """Parse output without coverage info."""
        output = "5 passed in 0.5s"
        result = pytest_runner.parse_results(output, exit_code=0)
        assert result["coverage_percent"] == 0.0


class TestPytestRunnerRunTests:
    """Tests for PytestRunner.run_tests()."""

    @patch.object(PytestRunner, "_run_subprocess")
    def test_t240_invokes_correct_command(self, mock_subprocess, pytest_runner):
        """T240: PytestRunner.run_tests invokes correct command."""
        mock_subprocess.return_value = ("5 passed in 0.5s", 0)
        pytest_runner.run_tests(test_paths=["tests/test_example.py"])

        args, kwargs = mock_subprocess.call_args
        command = args[0]
        assert "pytest" in command
        assert "--tb=short" in command
        assert "-q" in command
        assert "tests/test_example.py" in command

    @patch.object(PytestRunner, "_run_subprocess")
    def test_extra_args_passed(self, mock_subprocess, pytest_runner):
        """Extra args are appended to the command."""
        mock_subprocess.return_value = ("5 passed", 0)
        pytest_runner.run_tests(extra_args=["--cov=mymodule"])

        args, _ = mock_subprocess.call_args
        command = args[0]
        assert "--cov=mymodule" in command


class TestPytestRunnerScaffold:
    """Tests for PytestRunner.get_scaffold_imports()."""

    def test_scaffold_imports(self, pytest_runner):
        """Returns correct pytest import."""
        assert pytest_runner.get_scaffold_imports() == "import pytest"
```
