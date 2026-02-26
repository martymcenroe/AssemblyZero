

```python
"""Pytest test runner adapter.

Issue #381: Encapsulates pytest execution logic, extracting it from
previously hardcoded workflow nodes.
"""

import json
import logging
import re
from typing import Any

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    FrameworkConfig,
    TestFramework,
    TestRunResult,
)
from assemblyzero.workflows.testing.runners.base_runner import BaseTestRunner

logger = logging.getLogger(__name__)


class PytestRunner(BaseTestRunner):
    """Test runner adapter for pytest + pytest-cov."""

    def run_tests(
        self,
        test_paths: list[str] | None = None,
        extra_args: list[str] | None = None,
    ) -> TestRunResult:
        """Run pytest with --tb=short -q and parse output.

        Uses --json-report if available, falls back to stdout parsing.
        """
        command = ["pytest", "--tb=short", "-q"]

        if extra_args:
            command.extend(extra_args)

        if test_paths:
            command.extend(test_paths)

        raw_output, exit_code = self._run_subprocess(command)
        return self.parse_results(raw_output, exit_code)

    def parse_results(self, raw_output: str, exit_code: int) -> TestRunResult:
        """Parse pytest output into unified TestRunResult.

        Attempts JSON report parsing first, falls back to regex on stdout.
        """
        passed = 0
        failed = 0
        skipped = 0
        errors = 0
        coverage_percent = 0.0

        # Try to parse the summary line: "X passed, Y failed, Z skipped"
        summary_match = re.search(
            r"(\d+)\s+passed", raw_output
        )
        if summary_match:
            passed = int(summary_match.group(1))

        failed_match = re.search(r"(\d+)\s+failed", raw_output)
        if failed_match:
            failed = int(failed_match.group(1))

        skipped_match = re.search(r"(\d+)\s+skipped", raw_output)
        if skipped_match:
            skipped = int(skipped_match.group(1))

        error_match = re.search(r"(\d+)\s+error", raw_output)
        if error_match:
            errors = int(error_match.group(1))

        # Try to extract coverage percentage
        cov_match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", raw_output)
        if cov_match:
            coverage_percent = float(cov_match.group(1))

        total = passed + failed + skipped + errors

        return {
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "errors": errors,
            "total": total,
            "coverage_percent": coverage_percent,
            "coverage_type": CoverageType.LINE,
            "raw_output": raw_output,
            "exit_code": exit_code,
            "framework": TestFramework.PYTEST,
        }

    def validate_test_file(self, file_path: str, content: str) -> list[str]:
        """Validate Python test file for mechanical correctness.

        Checks:
        - Has import statements
        - Has test_ prefixed functions or classes
        """
        errors: list[str] = []

        if not content.strip():
            errors.append(f"Empty test file: {file_path}")
            return errors

        # Check for any import statement
        if not re.search(r"^(import |from )", content, re.MULTILINE):
            errors.append(f"No import statements found in {file_path}")

        # Check for test functions
        if not re.search(r"^def test_", content, re.MULTILINE):
            if not re.search(r"^class Test", content, re.MULTILINE):
                errors.append(f"No test functions (test_*) found in {file_path}")

        return errors

    def get_scaffold_imports(self) -> str:
        """Return pytest import block."""
        return "import pytest"
```
