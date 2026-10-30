"""Jest/Vitest test runner adapter.

Issue #381: Handles Jest and Vitest execution via npx,
JSON report parsing, and TypeScript test file validation.
"""

import json
import logging
import os
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
    CoverageReportError,
    combined_output,
    first_json_object,
)

logger = logging.getLogger(__name__)

#: Where a coverage run's report goes, beneath the framework's project
#: directory (#4246): both runners' default, so a JavaScript project's
#: .gitignore already names it in the common case.
COVERAGE_DIR = "coverage"

#: The istanbul json-summary reporter's file name, for Vitest and Jest alike.
COVERAGE_SUMMARY = "coverage-summary.json"

#: Vitest measures coverage through one of these packages (#4246). Closed:
#: the two providers Vitest ships.
VITEST_COVERAGE_PROVIDERS: tuple[str, ...] = ("@vitest/coverage-v8", "@vitest/coverage-istanbul")


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

    def require_dependencies(self) -> None:
        """The project's own vitest or jest must be installed (#4236), and
        for Vitest a coverage provider, because the green phase measures
        coverage (#4246). Jest's coverage is built in."""
        self._require_node_package("vitest" if self._is_vitest else "jest")
        if self._is_vitest:
            self._require_one_node_module(VITEST_COVERAGE_PROVIDERS, "measure coverage")

    @property
    def coverage_report_path(self) -> str:
        """Where a coverage run writes its istanbul json-summary (#4246)."""
        return os.path.join(self.project_dir, COVERAGE_DIR, COVERAGE_SUMMARY)

    def _coverage_args(self) -> list[str]:
        """Ask for line coverage, as a json-summary in COVERAGE_DIR (#4246).
        These replace the project's own coverage reporters for the run, so
        no text table lands on the stdout the JSON report is read from."""
        if self._is_vitest:
            return [
                "--coverage.enabled=true",
                "--coverage.reporter=json-summary",
                f"--coverage.reportsDirectory={COVERAGE_DIR}",
            ]
        return [
            "--coverage",
            "--coverageReporters=json-summary",
            f"--coverageDirectory={COVERAGE_DIR}",
        ]

    def read_coverage_report(self) -> float:
        """`total.lines.pct` from the run's json-summary (#4246). Raises
        CoverageReportError naming the path when there is no report, it does
        not parse, or it carries no line percentage (istanbul writes
        "Unknown" when nothing was instrumented). Never 0% in place of one."""
        path = self.coverage_report_path
        if not os.path.isfile(path):
            raise CoverageReportError(
                f"no coverage report at {path}: the run's tests passed and it "
                f"wrote none"
            )
        try:
            with open(path, "r", encoding="utf-8") as f:
                summary = json.load(f)
        except (OSError, ValueError) as e:
            raise CoverageReportError(
                f"the coverage report at {path} cannot be read: "
                f"{type(e).__name__}: {e}"
            ) from e
        lines = (summary.get("total") or {}).get("lines") if isinstance(summary, dict) else None
        pct = lines.get("pct") if isinstance(lines, dict) else None
        if isinstance(pct, bool) or not isinstance(pct, (int, float)):
            raise CoverageReportError(
                f"the coverage report at {path} has no line percentage "
                f"(total.lines.pct is {pct!r})"
            )
        return float(pct)

    def run_tests(
        self,
        test_paths: list[str] | None = None,
        extra_args: list[str] | None = None,
        *,
        measure_coverage: bool = False,
    ) -> TestRunResult:
        """Run 'npx jest --json' or 'npx vitest run --reporter=json'.

        #4246: with `measure_coverage`, the run also writes a json-summary to
        `coverage_report_path`, and a report left there by an earlier run is
        removed first, so it is never read as this one's. When every test
        passed, `coverage_percent` is the report's line percentage, and a
        report that cannot be read raises CoverageReportError. While tests
        fail, or when none ran, coverage decides nothing in the green phase,
        and `coverage_percent` is None: not measured. Without
        `measure_coverage` (the red phase, the full-suite gate) it is None
        too, and the argv is as it was.
        """
        test_paths = self._paths_for_runner(test_paths)  # #3707
        if measure_coverage:
            stale = self.coverage_report_path
            if os.path.isfile(stale):
                try:
                    os.remove(stale)
                except OSError as e:
                    raise CoverageReportError(
                        f"an earlier run's coverage report at {stale} cannot "
                        f"be removed, so this run's could not be told from it: "
                        f"{type(e).__name__}: {e}"
                    ) from e
        if self._is_vitest:
            print("Running vitest runner for project:", self.project_dir)
            package_json_path = os.path.join(self.project_dir, "package.json")
            has_typecheck_script = False
            if os.path.exists(package_json_path):
                try:
                    with open(package_json_path, "r") as f:
                        pkg = json.load(f)
                        if "scripts" in pkg and "typecheck" in pkg["scripts"]:
                            has_typecheck_script = True
                except (OSError, json.JSONDecodeError):
                    # fail-open: missing or malformed package.json just means no typecheck script
                    pass
            
            tsconfig_path = os.path.join(self.project_dir, "tsconfig.json")
            
            typecheck_command = None
            if has_typecheck_script:
                typecheck_command = ["npm", "run", "typecheck"]
            elif os.path.exists(tsconfig_path):
                typecheck_command = ["npx", "tsc", "--noEmit"]
                
            if typecheck_command:
                out, err, code = self._run_subprocess(typecheck_command)
                if code != 0:
                    return self._fallback_result(combined_output(out, err), code)

            command = ["npx", "vitest", "run", "--reporter=json"]
        else:
            command = ["npx", "jest", "--json"]

        if measure_coverage:
            command.extend(self._coverage_args())

        if extra_args:
            command.extend(extra_args)

        if test_paths:
            command.extend(test_paths)

        stdout, stderr, exit_code = self._run_subprocess(command)
        result = self.parse_results(stdout, exit_code, stderr)
        if (
            measure_coverage
            and result["passed"] > 0
            and result["failed"] == 0
            and result["errors"] == 0
        ):
            result["coverage_percent"] = self.read_coverage_report()
        return result

    def parse_results(
        self, raw_output: str, exit_code: int, stderr: str = "",
    ) -> TestRunResult:
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

        #3065: the report is read from `raw_output`, the run's stdout, as the
        first JSON object that carries `numPassedTests`, the count it reads
        first; `stderr` (npx's warnings) is kept in the result's `raw_output`
        for the reader and never parsed.

        #4246: `coverage_percent` is None here, not measured. The report's
        `coverageMap` is not read: coverage comes from the json-summary a
        `measure_coverage` run writes (`read_coverage_report`), one source,
        where it used to read 0% whenever the map was absent, which was
        every run, because none asked for coverage.
        """
        passed = 0
        failed = 0
        skipped = 0
        errors = 0
        shown = combined_output(raw_output, stderr)

        try:
            report = first_json_object(raw_output, "numPassedTests")
            if report is None:
                logger.warning("No JSON report found in Jest/Vitest output")
                return self._fallback_result(shown, exit_code)

            passed = report.get("numPassedTests", 0)
            failed = report.get("numFailedTests", 0)
            skipped = report.get("numPendingTests", 0)

        except (ValueError, KeyError, TypeError, AttributeError) as e:
            logger.warning("Failed to parse Jest/Vitest JSON output: %s", e)
            return self._fallback_result(shown, exit_code)

        total = passed + failed + skipped + errors

        return {
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "errors": errors,
            "total": total,
            "coverage_percent": None,  # #4246: not measured here
            "coverage_type": CoverageType.LINE,
            "raw_output": shown,
            "exit_code": exit_code,
            "framework": self.config["framework"],
        }

    def _fallback_result(self, raw_output: str, exit_code: int) -> TestRunResult:
        """Create a fallback result when JSON parsing fails."""
        return {
            "passed": 0,
            "failed": 1 if exit_code != 0 else 0,
            "skipped": 0,
            "errors": 1 if exit_code != 0 else 0,
            "total": 1,
            "coverage_percent": None,  # #4246: nothing was measured
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

        # #3067: the docstring's second check, which the code never made. A
        # file whose tests call the code and assert nothing passes when run,
        # and its coverage is of behaviour nobody checked. `expect` named in
        # the import line is not a call; `expect(` in a test body is. Per
        # file, not per test: counting per test needs a TypeScript parse.
        if not re.search(r"\bexpect\s*\(", content):
            errors.append(f"No expect() assertions found in {file_path}")

        return errors

    def get_scaffold_imports(self) -> str:
        """Return jest or vitest import block."""
        if self._is_vitest:
            return "import { describe, it, expect } from 'vitest';"
        return "import { describe, it, expect } from '@jest/globals';"