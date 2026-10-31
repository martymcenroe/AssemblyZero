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
    RunnerError,
    combined_output,
    first_json_object,
    loud,
    output_head,
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
        *,
        measure_coverage: bool = False,
        coverage_include: list[str] | None = None,
    ) -> TestRunResult:
        """Run 'npx playwright test' with --reporter=json.

        `measure_coverage` and `coverage_include` are accepted and ignored
        (#4246, #4436): Playwright's coverage is scenario coverage, computed
        from the result by the green phase, not measured by the run."""
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

        ADR 0236: a run with no report, a report that does not parse, or a
        report whose suites are not the shape above raises RunnerError after
        an ERROR line, naming the project, the exit code and the head of both
        streams. Each used to come back as a fabricated result that read zero
        failures at exit 0.
        """
        passed = 0
        failed = 0
        skipped = 0
        errors = 0
        shown = combined_output(raw_output, stderr)

        try:
            report = first_json_object(raw_output, "suites")
        except ValueError as e:
            raise self._unreadable(f"its JSON report does not parse: {e}", exit_code, shown) from e
        if report is None:
            raise self._unreadable("no Playwright JSON report in its stdout", exit_code, shown)

        suites = report["suites"]
        if not isinstance(suites, list):
            raise self._unreadable(
                f"its JSON report is not the shape Playwright writes: suites is "
                f"a {type(suites).__name__}, not a list",
                exit_code, shown,
            )
        try:
            for suite in suites:
                passed_s, failed_s, skipped_s, errors_s = self._count_suite(suite)
                passed += passed_s
                failed += failed_s
                skipped += skipped_s
                errors += errors_s
        except (TypeError, AttributeError) as e:
            raise self._unreadable(
                f"its JSON report is not the shape Playwright writes: "
                f"{type(e).__name__}: {e}",
                exit_code, shown,
            ) from e

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

    def _unreadable(self, cause: str, exit_code: int, shown: str) -> RunnerError:
        """The RunnerError for a run whose outcome cannot be read, after its
        ERROR line (ADR 0236). It replaces the fallback result, which read
        zero failures and zero errors at exit 0."""
        message = (
            f"the Playwright run in {self.project_dir} (exit {exit_code}) cannot "
            f"be read, so its outcome is unknown: {cause}. Output: {output_head(shown)}"
        )
        loud(message)
        return RunnerError(message)

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