

```python
"""Jest/Vitest test runner adapter.

Issue #381: Handles Jest and Vitest execution via npx,
JSON report parsing, and TypeScript test file validation.
"""

import json
import logging
import re
import shutil

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    FrameworkConfig,
    TestFramework,
    TestRunResult,
)
from assemblyzero.workflows.testing.runners.base_runner import BaseTestRunner

logger = logging.getLogger(__name__)


class JestRunner(BaseTestRunner):
    """Test runner adapter for Jest / Vitest."""

    def __init__(self, config: FrameworkConfig, project_root: str) -> None:
        """Initialize and verify node/npx availability.

        Raises EnvironmentError if 'npx' is not found on PATH.
        """
        super().__init__(config, project_root)
        if not shutil.which("npx"):
            raise EnvironmentError(
                "npx not found on PATH. Jest/Vitest tests require Node.js >= 18. "
                "Install Node.js from https://nodejs.org/ and ensure npx is available."
            )
        self._is_vitest = config["framework"] == TestFramework.VITEST

    def run_tests(
        self,
        test_paths: list[str] | None = None,
        extra_args: list[str] | None = None,
    ) -> TestRunResult:
        """Run 'npx jest --json' or 'npx vitest run --reporter=json'."""
        if self._is_vitest:
            command = ["npx", "vitest", "run", "--reporter=json"]
        else:
            command = ["npx", "jest", "--json"]

        if extra_args:
            command.extend(extra_args)

        if test_paths:
            command.extend(test_paths)

        raw_output, exit_code = self._run_subprocess(command)
        return self.parse_results(raw_output, exit_code)

    def parse_results(self, raw_output: str, exit_code: int) -> TestRunResult:
        """Parse Jest/Vitest JSON output into unified TestRunResult.

        Jest JSON format:
        {
            "success": bool,
            "numPassedTests": int,
            "numFailedTests": int,
            "numPendingTests": int,
            "numTotalTests": int,
            "coverageMap": {...} (optional)
        }
        """
        passed = 0
        failed = 0
        skipped = 0
        errors = 0
        coverage_percent = 0.0

        try:
            # Jest may output non-JSON before the JSON blob
            json_start = raw_output.find("{")
            if json_start == -1:
                logger.warning("No JSON found in Jest/Vitest output")
                return self._fallback_result(raw_output, exit_code)

            json_str = raw_output[json_start:]
            report = json.loads(json_str)

            passed = report.get("numPassedTests", 0)
            failed = report.get("numFailedTests", 0)
            skipped = report.get("numPendingTests", 0)

            # Extract coverage if available
            if "coverageMap" in report and report["coverageMap"]:
                coverage_percent = self._extract_coverage(report["coverageMap"])

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("Failed to parse Jest/Vitest JSON output: %s", e)
            return self._fallback_result(raw_output, exit_code)

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
            "framework": self.config["framework"],
        }

    def _extract_coverage(self, coverage_map: dict) -> float:
        """Extract overall line coverage percentage from Jest coverageMap.

        Averages line coverage across all files.
        """
        if not coverage_map:
            return 0.0

        total_statements = 0
        covered_statements = 0

        for _file_path, file_coverage in coverage_map.items():
            statement_map = file_coverage.get("statementMap", {})
            s_counts = file_coverage.get("s", {})
            total_statements += len(statement_map)
            covered_statements += sum(1 for count in s_counts.values() if count > 0)

        if total_statements == 0:
            return 0.0

        return (covered_statements / total_statements) * 100.0

    def _fallback_result(self, raw_output: str, exit_code: int) -> TestRunResult:
        """Create a fallback result when JSON parsing fails."""
        return {
            "passed": 0,
            "failed": 1 if exit_code != 0 else 0,
            "skipped": 0,
            "errors": 1 if exit_code != 0 else 0,
            "total": 1,
            "coverage_percent": 0.0,
            "coverage_type": CoverageType.LINE,
            "raw_output": raw_output,
            "exit_code": exit_code,
            "framework": self.config["framework"],
        }

    def validate_test_file(self, file_path: str, content: str) -> list[str]:
        """Validate .test.ts file for Jest/Vitest correctness.

        Checks:
        - Has describe/it/test blocks
        - Has expect() assertions
        """
        errors: list[str] = []

        if not content.strip():
            errors.append(f"Empty test file: {file_path}")
            return errors

        has_describe = bool(re.search(r"\bdescribe\s*\(", content))
        has_it = bool(re.search(r"\bit\s*\(", content))
        has_test = bool(re.search(r"\btest\s*\(", content))

        if not (has_describe or has_it or has_test):
            errors.append(f"No test structure (describe/it/test) found in {file_path}")

        return errors

    def get_scaffold_imports(self) -> str:
        """Return jest or vitest import block."""
        if self._is_vitest:
            return "import { describe, it, expect } from 'vitest';"
        return "import { describe, it, expect } from '@jest/globals';"
```
