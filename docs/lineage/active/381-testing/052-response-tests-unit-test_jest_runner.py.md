

```python
"""Unit tests for JestRunner.

Issue #381: Tests T160, T170, T190, T230 from LLD Section 10.0.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    TestFramework,
)
from assemblyzero.workflows.testing.runner_registry import get_framework_config
from assemblyzero.workflows.testing.runners.jest_runner import JestRunner


@pytest.fixture
def jest_runner():
    """Create a JestRunner with mocked npx availability."""
    with patch("shutil.which", return_value="/usr/bin/npx"):
        config = get_framework_config(TestFramework.JEST)
        return JestRunner(config, project_root="/tmp/test_project")


@pytest.fixture
def vitest_runner():
    """Create a JestRunner for Vitest with mocked npx availability."""
    with patch("shutil.which", return_value="/usr/bin/npx"):
        config = get_framework_config(TestFramework.VITEST)
        return JestRunner(config, project_root="/tmp/test_project")


class TestJestRunnerValidation:
    """Tests for JestRunner.validate_test_file()."""

    def test_t160_valid_test_ts(self, jest_runner):
        """T160: JestRunner.validate_test_file accepts valid .test.ts."""
        content = """describe('utils', () => {
  it('formats date correctly', () => {
    expect(formatDate(new Date())).toBeDefined();
  });
});
"""
        errors = jest_runner.validate_test_file("tests/utils.test.ts", content)
        assert errors == []

    def test_t170_no_describe_it(self, jest_runner):
        """T170: JestRunner.validate_test_file rejects no describe/it."""
        content = """const x = 5;
console.log(x);
"""
        errors = jest_runner.validate_test_file("tests/utils.test.ts", content)
        assert any("No test structure" in e for e in errors)

    def test_test_function_accepted(self, jest_runner):
        """Accept test() function style (without describe)."""
        content = """test('works', () => {
  expect(true).toBe(true);
});
"""
        errors = jest_runner.validate_test_file("tests/simple.test.ts", content)
        assert errors == []

    def test_empty_file(self, jest_runner):
        """Reject empty file."""
        errors = jest_runner.validate_test_file("tests/empty.test.ts", "")
        assert any("Empty test file" in e for e in errors)


class TestJestRunnerParseResults:
    """Tests for JestRunner.parse_results()."""

    def test_t190_parse_json_report(self, jest_runner):
        """T190: JestRunner.parse_results handles JSON report."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "jest_json_report.json"
        with open(fixture_path) as f:
            raw_output = f.read()

        result = jest_runner.parse_results(raw_output, exit_code=1)
        assert result["passed"] == 8
        assert result["failed"] == 2
        assert result["skipped"] == 1
        assert result["total"] == 11
        assert result["coverage_type"] == CoverageType.LINE
        assert result["framework"] == TestFramework.JEST
        assert result["exit_code"] == 1

    def test_parse_all_passing(self, jest_runner):
        """Parse all-passing Jest report."""
        report = {
            "success": True,
            "numPassedTests": 5,
            "numFailedTests": 0,
            "numPendingTests": 0,
            "numTotalTests": 5,
        }
        result = jest_runner.parse_results(json.dumps(report), exit_code=0)
        assert result["passed"] == 5
        assert result["failed"] == 0
        assert result["total"] == 5

    def test_parse_invalid_json(self, jest_runner):
        """Fallback when JSON is invalid."""
        result = jest_runner.parse_results("not json", exit_code=1)
        assert result["failed"] >= 1

    def test_parse_with_coverage_map(self, jest_runner):
        """Parse report with coverage data."""
        report = {
            "success": True,
            "numPassedTests": 3,
            "numFailedTests": 0,
            "numPendingTests": 0,
            "numTotalTests": 3,
            "coverageMap": {
                "src/utils.ts": {
                    "statementMap": {"0": {}, "1": {}, "2": {}, "3": {}},
                    "s": {"0": 1, "1": 1, "2": 0, "3": 1},
                }
            },
        }
        result = jest_runner.parse_results(json.dumps(report), exit_code=0)
        assert result["coverage_percent"] == 75.0  # 3/4 statements covered


class TestJestRunnerRunTests:
    """Tests for JestRunner.run_tests()."""

    @patch.object(JestRunner, "_run_subprocess")
    def test_t230_invokes_correct_command(self, mock_subprocess, jest_runner):
        """T230: JestRunner.run_tests invokes correct command."""
        mock_subprocess.return_value = ('{"success":true,"numPassedTests":1,"numFailedTests":0,"numPendingTests":0,"numTotalTests":1}', 0)
        jest_runner.run_tests(test_paths=["tests/utils.test.ts"])

        args, _ = mock_subprocess.call_args
        command = args[0]
        assert "npx" in command
        assert "jest" in command
        assert "--json" in command
        assert "tests/utils.test.ts" in command

    @patch.object(JestRunner, "_run_subprocess")
    def test_vitest_invokes_correct_command(self, mock_subprocess, vitest_runner):
        """Vitest runner uses vitest run --reporter=json."""
        mock_subprocess.return_value = ('{"success":true,"numPassedTests":1,"numFailedTests":0,"numPendingTests":0,"numTotalTests":1}', 0)
        vitest_runner.run_tests()

        args, _ = mock_subprocess.call_args
        command = args[0]
        assert "npx" in command
        assert "vitest" in command
        assert "run" in command
        assert "--reporter=json" in command


class TestJestRunnerEnvironment:
    """Tests for JestRunner environment checks."""

    def test_missing_npx(self):
        """Runner raises EnvironmentError if npx not found."""
        with patch("shutil.which", return_value=None):
            config = get_framework_config(TestFramework.JEST)
            with pytest.raises(EnvironmentError, match="npx not found"):
                JestRunner(config, "/tmp/test")


class TestJestRunnerScaffold:
    """Tests for JestRunner.get_scaffold_imports()."""

    def test_jest_imports(self, jest_runner):
        """Returns correct Jest import."""
        imports = jest_runner.get_scaffold_imports()
        assert "@jest/globals" in imports

    def test_vitest_imports(self, vitest_runner):
        """Returns correct Vitest import."""
        imports = vitest_runner.get_scaffold_imports()
        assert "vitest" in imports
```
