"""Abstract base class for framework-specific test runners.

Issue #381: Defines the interface all test runners must implement.
"""

import json
import logging
import subprocess
from abc import ABC, abstractmethod
from typing import Any

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    FrameworkConfig,
    TestFramework,
    TestRunResult,
)

logger = logging.getLogger(__name__)

# Default subprocess timeout in seconds
DEFAULT_TIMEOUT = 300


class BaseTestRunner(ABC):
    """Abstract base class for framework-specific test runners."""

    def __init__(self, config: FrameworkConfig, project_root: str) -> None:
        """Initialize with framework config and project root path."""
        self.config = config
        self.project_root = project_root

    @abstractmethod
    def run_tests(
        self,
        test_paths: list[str] | None = None,
        extra_args: list[str] | None = None,
    ) -> TestRunResult:
        """Execute tests and return unified results."""
        raise NotImplementedError

    @abstractmethod
    def parse_results(self, raw_output: str, exit_code: int) -> TestRunResult:
        """Parse runner-specific output into unified TestRunResult."""
        raise NotImplementedError

    @abstractmethod
    def validate_test_file(self, file_path: str, content: str) -> list[str]:
        """Validate a test file for mechanical correctness.

        Returns list of validation error messages (empty = valid).
        """
        raise NotImplementedError

    @abstractmethod
    def get_scaffold_imports(self) -> str:
        """Return the import block for scaffolded test files."""
        raise NotImplementedError

    def compute_scenario_coverage(
        self, result: TestRunResult, total_scenarios: int
    ) -> float:
        """Compute scenario-based coverage: passed / total_scenarios.

        Returns 0.0 if total_scenarios is 0 to prevent ZeroDivisionError.
        """
        if total_scenarios == 0:
            logger.warning("total_scenarios is 0; returning 0.0 coverage")
            return 0.0
        return result["passed"] / total_scenarios

    def _run_subprocess(
        self,
        command: list[str],
        timeout: int = DEFAULT_TIMEOUT,
        cwd: str | None = None,
    ) -> tuple[str, int]:
        """Run a subprocess command and return (stdout, exit_code).

        Handles timeout and other subprocess errors gracefully.
        """
        working_dir = cwd or self.project_root
        if self.config.get("working_directory"):
            import os
            working_dir = os.path.join(working_dir, self.config["working_directory"])

        logger.info("Running command: %s in %s", " ".join(command), working_dir)

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=working_dir,
            )
            output = result.stdout
            if result.stderr:
                output += "\n" + result.stderr
            return output, result.returncode
        except subprocess.TimeoutExpired:
            logger.error("Command timed out after %ds: %s", timeout, " ".join(command))
            return f"Command timed out after {timeout}s", -1
        except FileNotFoundError as e:
            logger.error("Command not found: %s", e)
            return f"Command not found: {e}", -1
        except OSError as e:
            logger.error("OS error running command: %s", e)
            return f"OS error: {e}", -1