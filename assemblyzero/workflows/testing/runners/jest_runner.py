"""Jest/Vitest test runner adapter.

Issue #381: Handles Jest and Vitest execution via npx,
JSON report parsing, and TypeScript test file validation.
"""

import json
import logging
import os
import re
import shutil
import tempfile
from pathlib import Path

from assemblyzero.workflows.testing.coverage_report import (
    FileLines,
    read_istanbul_report,
)
from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    FrameworkConfig,
    TestFramework,
    TestRunResult,
)
from assemblyzero.workflows.testing.runners.base_runner import (
    BaseTestRunner,
    CoverageReportError,
    RunnerError,
    combined_output,
    first_json_object,
    loud,
    output_head,
)

logger = logging.getLogger(__name__)

#: Where a coverage run's report goes, beneath the framework's project
#: directory (#4246): both runners' default. A JavaScript project's .gitignore
#: names it in the common case, and not always (the target #4436 measured does
#: not), so a run's reports are removed once read, or a checkpoint's `git add
#: -A` would commit them into the run's branch and its PR.
COVERAGE_DIR = "coverage"

#: The istanbul json-summary reporter's file name, for Vitest and Jest alike.
COVERAGE_SUMMARY = "coverage-summary.json"

#: The istanbul json reporter's file name: the per-line data the green phase
#: judges a run's changed lines by, which a json-summary does not carry (#4436).
COVERAGE_LINES = "coverage-final.json"

#: Vitest measures coverage through one of these packages (#4246). Closed:
#: the two providers Vitest ships.
VITEST_COVERAGE_PROVIDERS: tuple[str, ...] = ("@vitest/coverage-v8", "@vitest/coverage-istanbul")

#: Vitest's four threshold metrics, each set to 0 on a coverage run (#4436):
#: a project's own whole-file `coverage.thresholds` would otherwise end the
#: run non-zero on a number that decides nothing. Closed: the four it checks.
VITEST_THRESHOLDS: tuple[str, ...] = ("lines", "functions", "branches", "statements")

#: What a Vitest or Jest coverage glob reads as syntax and a file name may
#: hold, as in a `[id].tsx` route. Closed: glob grouping characters.
_GLOB_GROUPING = "()[]{}"


def _glob_literal(path: str) -> str:
    """`path` as a glob that matches that one file."""
    return "".join(f"\\{c}" if c in _GLOB_GROUPING else c for c in path)


class JestRunner(BaseTestRunner):
    """Test runner adapter for Jest / Vitest."""

    def __init__(self, config: FrameworkConfig, project_root: str) -> None:
        """Initialize and verify node/npx availability.

        Raises EnvironmentError if 'npx' is not found on PATH, after an ERROR
        line naming the project (ADR 0236). Every caller turns it into a halt,
        which alerts the operator.
        """
        super().__init__(config, project_root)
        if not shutil.which("npx"):
            message = (
                f"npx not found on PATH, so {config['framework'].value} cannot run "
                f"in {self.project_dir}. Jest/Vitest tests require Node.js >= 18. "
                "Install Node.js from https://nodejs.org/ and ensure npx is available."
            )
            loud(message)
            raise EnvironmentError(message)
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

    @property
    def line_coverage_report_path(self) -> str:
        """Where a coverage run writes its per-line report (#4436)."""
        return os.path.join(self.project_dir, COVERAGE_DIR, COVERAGE_LINES)

    def _coverage_args(self, include: list[str] | None = None) -> list[str]:
        """Ask for line coverage, as a json-summary and a per-line report in
        COVERAGE_DIR (#4246, #4436). These replace the project's own coverage
        reporters for the run, so no text table lands on the stdout the JSON
        report is read from.

        `include` names files, relative to the project, the report must cover
        even if no test loads them; both runners then report such a file at
        zero rather than leave it out. The project's own whole-file
        thresholds are switched off: a threshold that fails decides the run
        on a number that must decide nothing (#4436).

        Jest's array flags take every word after them that is not a flag, so
        `--coverageDirectory`, which is not one, comes last, ahead of the
        test paths.
        """
        files = [_glob_literal(path) for path in include or []]
        if self._is_vitest:
            return [
                "--coverage.enabled=true",
                "--coverage.reporter=json-summary",
                "--coverage.reporter=json",
                f"--coverage.reportsDirectory={COVERAGE_DIR}",
                *(f"--coverage.thresholds.{metric}=0" for metric in VITEST_THRESHOLDS),
                *(f"--coverage.include={path}" for path in files),
            ]
        return [
            "--coverage",
            "--coverageReporters=json-summary",
            "--coverageReporters=json",
            *(f"--collectCoverageFrom={path}" for path in files),
            "--coverageThreshold={}",
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

    def read_line_coverage(self) -> dict[str, FileLines]:
        """Every line of every file the run's report covers, by repository
        path (#4436). Raises CoverageReportError naming the path when the
        report is missing or cannot be read. The last read of a run, so the
        reports leave the project here."""
        lines = read_istanbul_report(
            self.line_coverage_report_path, self.project_root, self.project_dir,
        )
        self._discard_reports()
        return lines

    def _discard_reports(self) -> None:
        """Take a run's reports out of the project (#4436; see COVERAGE_DIR).
        Before a run this is also what stops an earlier run's report being
        read as this one's (#4246)."""
        for report in (self.coverage_report_path, self.line_coverage_report_path):
            if not os.path.isfile(report):
                continue
            try:
                os.remove(report)
            except OSError as e:
                raise CoverageReportError(
                    f"the coverage report at {report} cannot be removed, so a "
                    f"later run's could not be told from it and a checkpoint "
                    f"would commit it: {type(e).__name__}: {e}"
                ) from e

    def _has_typecheck_script(self) -> bool:
        """Whether the project's package.json declares a `typecheck` script.

        No package.json is a project that declares none: False, quietly. A
        package.json that cannot be read, does not parse, or is not an object
        with an object of scripts raises RunnerError naming it, after an
        ERROR line (ADR 0236): it used to be passed over as "no script", so
        a project whose typecheck it named was tested without one.
        """
        path = os.path.join(self.project_dir, "package.json")
        if not os.path.exists(path):
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                pkg = json.load(f)
        except (OSError, ValueError) as e:
            message = (
                f"the package.json at {path} cannot be read, so whether the "
                f"project declares a typecheck script is unknown and its tests "
                f"are not run: {type(e).__name__}: {e}"
            )
            loud(message)
            raise RunnerError(message) from e
        scripts = pkg.get("scripts", {}) if isinstance(pkg, dict) else None
        if not isinstance(scripts, dict):
            message = (
                f"the package.json at {path} is not an object with an object "
                f"of scripts, so whether the project declares a typecheck "
                f"script is unknown and its tests are not run"
            )
            loud(message)
            raise RunnerError(message)
        return "typecheck" in scripts

    def run_tests(
        self,
        test_paths: list[str] | None = None,
        extra_args: list[str] | None = None,
        *,
        measure_coverage: bool = False,
        coverage_include: list[str] | None = None,
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

        #4436: the run writes its per-line report beside the summary, cleared
        the same way, and `read_line_coverage` reads it and removes both. A
        run whose reports will not be read has them removed here.
        `coverage_include` names files the report must cover (`_coverage_args`).
        """
        test_paths = self._paths_for_runner(test_paths)  # #3707
        if measure_coverage:
            self._discard_reports()
        if self._is_vitest:
            print("Running vitest runner for project:", self.project_dir)
            tsconfig_path = os.path.join(self.project_dir, "tsconfig.json")

            typecheck_command = None
            if self._has_typecheck_script():
                typecheck_command = ["npm", "run", "typecheck"]
            elif os.path.exists(tsconfig_path):
                typecheck_command = ["npx", "tsc", "--noEmit"]

            if typecheck_command:
                out, err, code = self._run_subprocess(typecheck_command)
                if code != 0:
                    return self._typecheck_failed_result(combined_output(out, err), code)

            command = ["npx", "vitest", "run", "--reporter=json"]
        else:
            command = ["npx", "jest", "--json"]

        if measure_coverage:
            command.extend(self._coverage_args(coverage_include))

        if extra_args:
            command.extend(extra_args)

        if test_paths:
            command.extend(test_paths)

        report, stderr, exit_code = self._run_for_report(command)
        result = self.parse_results(report, exit_code, stderr)
        if measure_coverage:
            if result["passed"] > 0 and result["failed"] == 0 and result["errors"] == 0:
                result["coverage_percent"] = self.read_coverage_report()
            else:
                self._discard_reports()  # Jest writes them even when tests fail
        return result

    def _run_for_report(self, command: list[str]) -> tuple[str, str, int]:
        """Run the suite; return (its JSON report, stderr, exit code).

        #4504: Vitest 5's JSON reporter writes `.vitest/json/output.json` in the
        project and prints one line, where earlier versions printed the report.
        So the run names the file, which every version honours, in a folder
        outside the target's tree that goes with the run. A run that wrote
        nothing hands on its stdout, and `parse_results` raises on it naming
        what the run said.
        """
        if not self._is_vitest:
            return self._run_subprocess(command)
        with tempfile.TemporaryDirectory(prefix="az-vitest-") as folder:
            report = Path(folder) / "report.json"
            after_reporter = command.index("--reporter=json") + 1
            stdout, stderr, exit_code = self._run_subprocess(
                [*command[:after_reporter], f"--outputFile={report}", *command[after_reporter:]]
            )
            if report.is_file():
                return report.read_text(encoding="utf-8"), stderr, exit_code
            return stdout, stderr, exit_code

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

        ADR 0236: a run with no report, or whose report does not parse,
        raises RunnerError after an ERROR line, naming the project, the exit
        code and the head of both streams. It used to come back as a
        fallback whose counts read zero failures at exit 0, so a run nobody
        could read was judged as one where nothing failed.
        """
        errors = 0
        shown = combined_output(raw_output, stderr)

        try:
            report = first_json_object(raw_output, "numPassedTests")
        except ValueError as e:
            message = (
                f"the {self.config['framework'].value} JSON report in "
                f"{self.project_dir} (exit {exit_code}) does not parse, so the "
                f"run's outcome is unknown: {e}. Output: {output_head(shown)}"
            )
            loud(message)
            raise RunnerError(message) from e
        if report is None:
            message = (
                f"no Jest/Vitest JSON report in the {self.config['framework'].value} "
                f"run's stdout in {self.project_dir} (exit {exit_code}), so the "
                f"run's outcome is unknown. Output: {output_head(shown)}"
            )
            loud(message)
            raise RunnerError(message)

        passed = report.get("numPassedTests", 0)
        failed = report.get("numFailedTests", 0)
        skipped = report.get("numPendingTests", 0)

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

    def _typecheck_failed_result(self, raw_output: str, exit_code: int) -> TestRunResult:
        """The result of a Vitest run whose typecheck failed: one failure and
        one error, always. The code does not compile, which is the run's
        answer, not a missing one, so it is returned and not raised; the
        phases read it as a failing run. It is the only result this runner
        builds without a report (ADR 0236: the parse-failure fallback, which
        read as not failing at exit 0, is gone)."""
        return {
            "passed": 0,
            "failed": 1,
            "skipped": 0,
            "errors": 1,
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