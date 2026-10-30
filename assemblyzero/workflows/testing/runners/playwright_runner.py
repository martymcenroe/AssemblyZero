"""Playwright test runner adapter.

Issue #381: Handles Playwright (@playwright/test) execution via npx,
JSON report parsing, and TypeScript test file validation.
"""

import logging
import re
import shutil

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    FrameworkConfig,
    TestFramework,
    TestRunResult,
)
from assemblyzero.workflows.testing.runners.base_runner import (
    BaseTestRunner,
    combined_output,
    first_json_object,
)

logger = logging.getLogger(__name__)


class PlaywrightRunner(BaseTestRunner):
    """Test runner adapter for Playwright (@playwright/test)."""

    def __init__(self, config: FrameworkConfig, project_root: str) -> None:
        """Initialize and verify node/npx availability.

        Raises EnvironmentError if 'npx' is not found on PATH.
        """
        super().__init__(config, project_root)
        if not shutil.which("npx"):
            raise EnvironmentError(
                "npx not found on PATH. Playwright tests require Node.js >= 18. "
                "Install Node.js from https://nodejs.org/ and ensure npx is available."
            )

    def require_dependencies(self) -> None:
        """The project's own Playwright must be installed (#4236)."""
        self._require_node_package("playwright")

    def run_tests(
        self,
        test_paths: list[str] | None = None,
        extra_args: list[str] | None = None,
    ) -> TestRunResult:
        """Run 'npx playwright test' with --reporter=json."""
        command = ["npx", "playwright", "test", "--reporter=json"]

        if extra_args:
            command.extend(extra_args)

        test_paths = self._paths_for_runner(test_paths)  # #3707
        if test_paths:
            command.extend(test_paths)

        stdout, stderr, exit_code = self._run_subprocess(command)
        return self.parse_results(stdout, exit_code, stderr)

    def parse_results(
        self, raw_output: str, exit_code: int, stderr: str = "",
    ) -> TestRunResult:
        """Parse Playwright JSON reporter output into TestRunResult.

        Playwright JSON format has:
        {
            "config": {...},
            "suites": [
                {
                    "title": "Suite Name",
                    "specs": [
                        {
                            "title": "test title",
                            "tests": [
                                {
                                    "results": [
                                        {"status": "passed"|"failed"|"skipped"|"timedOut"}
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        }

        #3065: the report is read from `raw_output`, the run's stdout, as the
        first JSON object that carries `suites`; `stderr` (npx's warnings,
        Playwright's browser-launch notices) is kept in the result's
        `raw_output` for the reader and never parsed.
        """
        passed = 0
        failed = 0
        skipped = 0
        errors = 0
        shown = combined_output(raw_output, stderr)

        try:
            report = first_json_object(raw_output, "suites")
            if report is None:
                logger.warning("No JSON report found in Playwright output; using exit code only")
                return self._fallback_result(shown, exit_code)

            for suite in report.get("suites", []):
                passed_s, failed_s, skipped_s, errors_s = self._count_suite(suite)
                passed += passed_s
                failed += failed_s
                skipped += skipped_s
                errors += errors_s

        except (ValueError, KeyError, TypeError, AttributeError) as e:
            logger.warning("Failed to parse Playwright JSON report: %s", e)
            return self._fallback_result(shown, exit_code)

        total = passed + failed + skipped + errors

        return {
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "errors": errors,
            "total": total,
            "coverage_percent": 0.0,  # Playwright doesn't provide line coverage
            "coverage_type": CoverageType.SCENARIO,
            "raw_output": shown,
            "exit_code": exit_code,
            "framework": TestFramework.PLAYWRIGHT,
        }

    def _count_suite(self, suite: dict) -> tuple[int, int, int, int]:
        """Recursively count test results in a Playwright suite."""
        passed = 0
        failed = 0
        skipped = 0
        errors = 0

        for spec in suite.get("specs", []):
            for test in spec.get("tests", []):
                for result in test.get("results", []):
                    status = result.get("status", "")
                    if status == "passed" or status == "expected":
                        passed += 1
                    elif status == "failed" or status == "unexpected":
                        failed += 1
                    elif status == "skipped":
                        skipped += 1
                    elif status == "timedOut":
                        errors += 1
                    else:
                        # Unknown status
                        errors += 1

        # Recurse into nested suites
        for child_suite in suite.get("suites", []):
            p, f, s, e = self._count_suite(child_suite)
            passed += p
            failed += f
            skipped += s
            errors += e

        return passed, failed, skipped, errors

    def _fallback_result(self, raw_output: str, exit_code: int) -> TestRunResult:
        """Create a fallback result when JSON parsing fails."""
        return {
            "passed": 0,
            "failed": 1 if exit_code != 0 else 0,
            "skipped": 0,
            "errors": 1 if exit_code != 0 else 0,
            "total": 1,
            "coverage_percent": 0.0,
            "coverage_type": CoverageType.SCENARIO,
            "raw_output": raw_output,
            "exit_code": exit_code,
            "framework": TestFramework.PLAYWRIGHT,
        }

    def validate_test_file(self, file_path: str, content: str) -> list[str]:
        """Validate .spec.ts file for Playwright-specific correctness.

        Checks:
        - Has @playwright/test import
        - Has test() calls
        """
        errors: list[str] = []

        if not content.strip():
            errors.append(f"Empty test file: {file_path}")
            return errors

        if "@playwright/test" not in content:
            errors.append(f"Missing '@playwright/test' import in {file_path}")

        if not re.search(r"\btest\s*\(", content):
            errors.append(f"No test() calls found in {file_path}")

        return errors

    def get_scaffold_imports(self) -> str:
        """Return Playwright import block."""
        return "import { test, expect } from '@playwright/test';"