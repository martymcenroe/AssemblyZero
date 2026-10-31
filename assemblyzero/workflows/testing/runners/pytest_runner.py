"""Pytest test runner adapter.

Issue #381: Encapsulates pytest execution logic, extracting it from
previously hardcoded workflow nodes.
"""

import logging
import re

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    TestFramework,
    TestRunResult,
)
from assemblyzero.workflows.testing.runners.base_runner import (
    BaseTestRunner,
    RunnerError,
    combined_output,
    loud,
    output_head,
)

logger = logging.getLogger(__name__)

#: pytest's exit codes for a run that finished: 0, every test passed; 1,
#: some failed. Every other code is a run whose tests were not all run and
#: judged, so its counts are not the suite's (ADR 0236).
FINISHED_EXIT_CODES: frozenset[int] = frozenset({0, 1})

#: What pytest means by each exit code that is not a finished run. Closed:
#: pytest's `ExitCode` enum, 2 to 5.
UNFINISHED_EXIT_CODES: dict[int, str] = {
    2: "interrupted, or stopped by errors during collection",
    3: "internal error",
    4: "usage error",
    5: "no tests collected",
}


class PytestRunner(BaseTestRunner):
    """Test runner adapter for pytest + pytest-cov."""

    def run_tests(
        self,
        test_paths: list[str] | None = None,
        extra_args: list[str] | None = None,
        *,
        measure_coverage: bool = False,
    ) -> TestRunResult:
        """Run pytest with --tb=short -q and parse output.

        Reads the counts from pytest's summary line; an exit code other than
        0 or 1 raises RunnerError (`parse_results`).
        `measure_coverage` is accepted and ignored (#4246): the green phase
        measures pytest's coverage through `run_pytest`, with pytest-cov.
        """
        # #1904: bare "pytest" resolved from the ORCHESTRATOR's PATH — AZ's
        # venv, not the target repo's. Phase 3 of the boostgauge campaign
        # passed only because AZ happens to carry Pillow; phase 4 died on
        # psutil, which only the target declares. poetry run + cwd at the
        # (provisioned — see stages.py) worktree resolves the real env.
        command = ["poetry", "run", "pytest", "--tb=short", "-q"]

        if extra_args:
            command.extend(extra_args)

        if test_paths:
            command.extend(test_paths)

        # #3065: pytest's output is for people, and its summary can be on
        # either stream, so it reads both, joined as they always were.
        stdout, stderr, exit_code = self._run_subprocess(command)
        return self.parse_results(combined_output(stdout, stderr), exit_code)

    def parse_results(
        self, raw_output: str, exit_code: int, stderr: str = "",
    ) -> TestRunResult:
        """Parse pytest output into unified TestRunResult.

        Reads the counts from pytest's summary line. `stderr`, when given
        separately, is read with `raw_output` (#3065).

        ADR 0236: an exit code other than 0 or 1 raises RunnerError after an
        ERROR line, naming the code, what pytest means by it and the head of
        the output. Such a run did not run and judge its tests, and its
        counts, mostly zero, read as a run where nothing failed.

        `coverage_percent` is pytest-cov's TOTAL percentage when the output
        carries the table, and None when it does not: a run not asked to
        measure coverage prints none, and None is "not measured" (#4246),
        where it used to read 0%.
        """
        raw_output = combined_output(raw_output, stderr)
        if exit_code not in FINISHED_EXIT_CODES:
            meaning = UNFINISHED_EXIT_CODES.get(exit_code, "not an exit code pytest defines")
            message = (
                f"pytest in {self.project_dir} ended with exit {exit_code} "
                f"({meaning}), so its tests were not all run and judged and its "
                f"counts are not the suite's. Output: {output_head(raw_output)}"
            )
            loud(message)
            raise RunnerError(message)
        passed = 0
        failed = 0
        skipped = 0
        errors = 0
        coverage_percent: float | None = None

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