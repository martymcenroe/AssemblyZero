"""Abstract base class for framework-specific test runners.

Issue #381: Defines the interface all test runners must implement.
"""

from assemblyzero.utils.shell import run_command
import logging
import os
import subprocess
from abc import ABC, abstractmethod

from assemblyzero.workflows.testing.framework_detector import (
    FrameworkConfig,
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

    @property
    def project_dir(self) -> str:
        """Where the framework's project lives: the project root, or the
        config's `working_directory` beneath it (#3707)."""
        working_directory = self.config.get("working_directory")
        if working_directory:
            return os.path.join(self.project_root, working_directory)
        return self.project_root

    def _paths_for_runner(self, test_paths: list[str] | None) -> list[str] | None:
        """Test paths as the runner must see them from `project_dir` (#3707).

        The workflow names test files relative to the project root
        (`web/tests/a.test.ts`), or absolutely. A runner started in `web/`
        would not find either, so a path inside `project_dir` is made
        relative to it. A path outside it is passed through unchanged.
        """
        if not test_paths:
            return test_paths
        root = os.path.abspath(self.project_root)
        base = os.path.abspath(self.project_dir)
        out: list[str] = []
        for path in test_paths:
            absolute = os.path.normpath(path if os.path.isabs(path) else os.path.join(root, path))
            if absolute == base or absolute.startswith(base + os.sep):
                out.append(os.path.relpath(absolute, base))
            else:
                out.append(path)
        return out

    def require_dependencies(self) -> None:
        """Raise OSError (EnvironmentError) when this runner's project cannot
        run its tests (#4236). The base runner needs nothing beyond what its
        constructor checked; the JavaScript runners need their packages."""

    def _require_node_package(self, binary: str) -> None:
        """Raise OSError unless `node_modules/.bin/<binary>` exists in
        the project directory or a directory above it up to the project root
        (#4236), or a Yarn Plug'n'Play `.pnp.cjs` stands in for node_modules.

        Node resolves packages upwards, so a workspace that installs at the
        root is installed for `web/` too. Without the package, `npx` fetches
        the runner from the network instead of running the project's own, or
        fails: the run never starts a suite it cannot run.
        """
        root = os.path.abspath(self.project_root)
        current = os.path.abspath(self.project_dir)
        searched: list[str] = []
        while True:
            searched.append(current)
            bin_dir = os.path.join(current, "node_modules", ".bin")
            if (
                os.path.isfile(os.path.join(bin_dir, binary))
                or os.path.isfile(os.path.join(bin_dir, f"{binary}.cmd"))
                or os.path.isfile(os.path.join(current, ".pnp.cjs"))
            ):
                return
            parent = os.path.dirname(current)
            if current == root or parent == current or not (
                parent == root or parent.startswith(root + os.sep)
            ):
                break
            current = parent
        raise OSError(
            f"{binary} cannot run in {self.project_dir}: no "
            f"node_modules/.bin/{binary} in {', '.join(searched)}. Install the "
            f"project's dependencies there (npm ci) before the run"
        )

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
            result = run_command(
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
