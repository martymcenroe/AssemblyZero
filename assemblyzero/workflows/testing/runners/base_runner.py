"""Abstract base class for framework-specific test runners.

Issue #381: Defines the interface all test runners must implement.
"""

from assemblyzero.utils.shell import run_command
import json
import logging
import os
import subprocess
import sys
from abc import ABC, abstractmethod

from assemblyzero.workflows.testing.coverage_report import CoverageReportError, FileLines
from assemblyzero.workflows.testing.framework_detector import (
    FrameworkConfig,
    TestRunResult,
)

logger = logging.getLogger(__name__)

# Default subprocess timeout in seconds
DEFAULT_TIMEOUT = 300


class RunnerError(RuntimeError):
    """A test run whose outcome cannot be read (ADR 0236, #3585).

    The run's report is missing or broken, or the project's own files do not
    say how to run it. Raised, never turned into counts: a result no report
    backs reads as a pass or a red the run never produced. The message names
    the project, the exit code and the head of the output. The node or the
    entry point that the raise reaches ends the run and alerts the operator.
    """


def loud(message: str) -> None:
    """One ERROR line on stderr and in the log (ADR 0236 property 1)."""
    logger.error("[RUNNER] %s", message)
    print(f"ERROR [RUNNER] {message}", file=sys.stderr, flush=True)


#: How much of a run's output a RunnerError carries: enough to name the
#: cause, short enough for one alert.
OUTPUT_HEAD_CHARS = 600


def output_head(text: str) -> str:
    """The start of a run's output, for an error message."""
    text = text.strip()
    if len(text) <= OUTPUT_HEAD_CHARS:
        return text
    return text[:OUTPUT_HEAD_CHARS] + " ..."


def combined_output(stdout: str, stderr: str) -> str:
    """Both streams, stdout first, as a reader of the run's output sees them."""
    return stdout + ("\n" + stderr if stderr else "")


def _object_end(text: str, start: int) -> int:
    """The index of the `}` that closes the `{` at `start`, reading JSON
    strings as strings; -1 when it never closes."""
    depth = 0
    in_string = escaped = False
    for index in range(start, len(text)):
        character = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
        elif character == '"':
            in_string = True
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return index
    return -1


def first_json_object(text: str, required_key: str) -> dict | None:
    """The first JSON object in `text` whose top level carries `required_key`
    (#3065).

    Each `{` is matched to the `}` that closes it, so text after the report
    (npx's warnings, when the streams were joined) cannot reach the parse,
    and a brace in a log line ahead of it (`Using config {rootDir: web}`) is
    passed over: an object is decoded only when it opens as JSON does and
    names the key. A JSON log line that is not the report is passed over
    whole, so nothing nested inside it is mistaken for the report.

    None when no object in `text` carries the key: there is no report. An
    object that carries the key and does not parse raises ValueError -- that
    is the report, broken.
    """
    marker = f'"{required_key}"'
    index = text.find("{")
    while index != -1:
        end = _object_end(text, index)
        if end == -1:
            index = text.find("{", index + 1)
            continue
        span = text[index:end + 1]
        if span[1:].lstrip()[:1] in ('"', "}") and marker in span:
            try:
                value = json.loads(span)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"the JSON object carrying {marker} does not parse: {e}"
                ) from e
            if isinstance(value, dict) and required_key in value:
                return value
        index = text.find("{", end + 1)
    return None


class BaseTestRunner(ABC):
    """Abstract base class for framework-specific test runners."""

    def __init__(self, config: FrameworkConfig, project_root: str) -> None:
        """Initialize with framework config and project root path."""
        self.config = config
        self.project_root = project_root

    @property
    def framework_name(self) -> str:
        """The framework's name for a message: the enum's value, or the
        string a checkpoint-safe config carries."""
        framework = self.config.get("framework")
        return getattr(framework, "value", str(framework))

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
        searched: list[str] = []
        for current in self._node_search_dirs():
            searched.append(current)
            bin_dir = os.path.join(current, "node_modules", ".bin")
            if (
                os.path.isfile(os.path.join(bin_dir, binary))
                or os.path.isfile(os.path.join(bin_dir, f"{binary}.cmd"))
                or os.path.isfile(os.path.join(current, ".pnp.cjs"))
            ):
                return
        raise OSError(
            f"{binary} cannot run in {self.project_dir}: no "
            f"node_modules/.bin/{binary} in {', '.join(searched)}. Install the "
            f"project's dependencies there (npm ci) before the run"
        )

    def _node_search_dirs(self) -> list[str]:
        """The project directory and each directory above it up to the
        project root: where Node resolves a package from."""
        root = os.path.abspath(self.project_root)
        current = os.path.abspath(self.project_dir)
        dirs: list[str] = []
        while True:
            dirs.append(current)
            parent = os.path.dirname(current)
            if current == root or parent == current or not (
                parent == root or parent.startswith(root + os.sep)
            ):
                return dirs
            current = parent

    def _require_one_node_module(self, names: tuple[str, ...], purpose: str) -> None:
        """Raise OSError unless one of the packages `names` is installed in
        `node_modules` in the project directory or above it, or a Yarn
        Plug'n'Play `.pnp.cjs` stands in for node_modules (#4246)."""
        searched: list[str] = []
        for current in self._node_search_dirs():
            searched.append(current)
            if os.path.isfile(os.path.join(current, ".pnp.cjs")) or any(
                os.path.isdir(os.path.join(current, "node_modules", *name.split("/")))
                for name in names
            ):
                return
        raise OSError(
            f"{self.config['framework'].value} cannot {purpose} in "
            f"{self.project_dir}: neither {' nor '.join(names)} is installed in "
            f"node_modules in {', '.join(searched)}. Install one (for example "
            f"npm i -D {names[0]}) before the run"
        )

    @abstractmethod
    def run_tests(
        self,
        test_paths: list[str] | None = None,
        extra_args: list[str] | None = None,
        *,
        measure_coverage: bool = False,
        coverage_include: list[str] | None = None,
    ) -> TestRunResult:
        """Execute tests and return unified results.

        `measure_coverage` (#4246) asks a runner that measures line coverage
        to do so and to report it in `coverage_percent`; a runner whose
        coverage is measured elsewhere (pytest's, by `run_pytest`) or is
        scenario coverage (Playwright's) ignores it.

        `coverage_include` (#4436) names files, relative to `project_dir`,
        the report must cover whether or not a test loads them, so a file no
        test reaches reads as measured at zero; a runner that does not
        measure line coverage here ignores it."""
        raise NotImplementedError

    def read_line_coverage(self) -> dict[str, FileLines]:
        """The run's per-line coverage, by repository path (#4436). A runner
        with no such report raises CoverageReportError: the green phase asks
        this only of a framework it judges by lines."""
        raise CoverageReportError(
            f"{self.framework_name} in {self.project_dir} writes no per-line "
            f"coverage report"
        )

    @abstractmethod
    def parse_results(
        self, raw_output: str, exit_code: int, stderr: str = "",
    ) -> TestRunResult:
        """Parse runner-specific output into unified TestRunResult.

        `raw_output` is the stream the runner parses, and `stderr` the other
        one, kept for the reader (#3065)."""
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

        Raises ValueError after an ERROR line when there are no scenarios
        (ADR 0236): with nothing to divide by, coverage is unmeasured, and the
        0.0 it used to return read as a measured 0%.
        """
        if total_scenarios <= 0:
            message = (
                f"{self.framework_name} scenario coverage in "
                f"{self.project_dir} cannot be computed: the run has no scenarios "
                f"(total_scenarios is {total_scenarios}) to divide "
                f"{result.get('passed')} passed by"
            )
            loud(message)
            raise ValueError(message)
        return result["passed"] / total_scenarios

    def _run_subprocess(
        self,
        command: list[str],
        timeout: int = DEFAULT_TIMEOUT,
        cwd: str | None = None,
    ) -> tuple[str, str, int]:
        """Run a subprocess command and return (stdout, stderr, exit_code).

        #3065: the streams come back apart, so a runner that asked for a
        machine-readable report on stdout parses stdout alone; `npx` writes
        to stderr as a matter of routine, and a warning appended after the
        report broke every JSON parse. A runner that reads human output
        joins them (`combined_output`).

        A command that ran comes back with its exit code, whatever it is. A
        timeout, a missing command or an OS error raises RunnerError naming
        the framework, the command, the directory and the cause, after an
        ERROR line (ADR 0236). They used to come back as exit code -1 with
        the cause in place of stderr, which the runners parsed as a run, so a
        suite that never started read as one that failed.
        """
        working_dir = cwd or self.project_root
        if self.config.get("working_directory"):
            working_dir = os.path.join(working_dir, self.config["working_directory"])

        shown = " ".join(command)
        logger.info("Running command: %s in %s", shown, working_dir)

        try:
            result = run_command(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=working_dir,
            )
        except subprocess.TimeoutExpired as e:
            raise self._could_not_run(shown, working_dir, f"timed out after {timeout}s") from e
        except FileNotFoundError as e:
            raise self._could_not_run(shown, working_dir, f"command not found: {e}") from e
        except OSError as e:
            raise self._could_not_run(
                shown, working_dir, f"OS error: {type(e).__name__}: {e}",
            ) from e
        return result.stdout or "", result.stderr or "", result.returncode

    def _could_not_run(self, command: str, working_dir: str, cause: str) -> RunnerError:
        """The RunnerError for a test command that did not run to an exit
        code, after its ERROR line."""
        message = (
            f"{self.framework_name} could not run `{command}` in "
            f"{working_dir}: {cause}. The run's outcome is unknown"
        )
        loud(message)
        return RunnerError(message)
