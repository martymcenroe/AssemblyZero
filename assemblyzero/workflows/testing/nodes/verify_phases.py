"""N3 and N5: Verify Red/Green Phase nodes for TDD Testing Workflow.

N3 (verify_red_phase): Verify all tests fail before implementation
N5 (verify_green_phase): Verify all tests pass with coverage target

Issue #292: Added pytest exit code routing. Exit codes 4/5 (syntax/collection
errors) route back to N2_scaffold_tests instead of endlessly looping through
N4_implement_code. Exit codes 2/3 (interrupt/internal error) stop the workflow.
"""

from assemblyzero.utils.shell import run_command
import re
import subprocess
from pathlib import Path
from typing import Any

from assemblyzero.workflows.testing.audit import (
    gate_log,
    get_repo_root,
    log_workflow_execution,
    next_file_number,
    parse_pytest_output,
    save_audit_file,
)
from assemblyzero.workflows.testing.circuit_breaker import check_circuit_breaker
from assemblyzero.workflows.testing.nodes.e2e_validation import _extract_failed_test_names
from assemblyzero.workflows.testing.exit_code_router import (
    EXIT_INTERRUPTED,
    EXIT_INTERNALERROR,
    EXIT_USAGEERROR,
    EXIT_NOTESTSCOLLECTED,
    describe_exit_code,
    describe_run_outcome,
    route_by_exit_code,
)
from assemblyzero.workflows.testing.framework_detector import CoverageType, TestFramework
from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
    count_stub_tests,
)
from assemblyzero.workflows.testing.runner_registry import get_runner
from assemblyzero.workflows.testing.state import TestingWorkflowState


# Timeout for pytest execution
PYTEST_TIMEOUT_SECONDS = 300

# Issue #498: Max chars for failure summary fed back to N4
# #2058: was 2000 -- roughly the first 16 lines of a 100-failure suite. With
# root-cause grouping in _build_failure_summary, 12000 comfortably holds every
# DISTINCT cause of even a large generated test plan.
MAX_FAILURE_SUMMARY_CHARS = 12000

# #2319: pytest truncates each `short test summary info` line to the terminal
# width. Captured through a pipe there is no terminal, so it assumes 80 columns
# and the ` - AssertionError: ...` half is cut off -- leaving the reviser a list
# of test names with no reason attached. Measured on boostgauge #7: identical
# command, identical config; at 80 columns every reason is gone, at 200 every
# reason is present. 200 clears a worktree-length path plus a typical assertion
# message without making pytest's separator rules absurdly wide.
#
# Where this bites, and why CI disagrees: pytest skips the trim entirely when
# it believes it is on CI (`_pytest/terminal.py`: `running_on_ci() or
# config.option.verbose >= 2`, keyed off CI / BUILD_NUMBER). GitHub Actions
# sets CI=true, so the defect does NOT reproduce there -- and the speedrun runs
# on the operator's workstation, where nothing sets it. The one environment
# that would have shown a green suite is the one the pipeline never runs in.
PYTEST_OUTPUT_COLUMNS = "200"

# #2320: how many distinct failure tracebacks to carry back. Tracebacks are the
# only part of pytest's output that states WHY a test failed in full -- they are
# not width-truncated -- and they were being captured and discarded.
MAX_TRACEBACK_BLOCKS = 8

# Issue #562: Critical skip keywords (aligned with tools/test-gate.py)
_CRITICAL_SKIP_KEYWORDS = ["security", "auth", "payment", "critical"]

# Regex for verbose pytest skip lines: "test_name SKIPPED"
_SKIP_PATTERN = re.compile(r"([\w/\\.\-]+::[\w\[\]\-]+)\s+SKIPPED")


def _validate_skip_audit(output: str) -> dict[str, Any]:
    """Post-run validation of skipped tests (Issue #562).

    Parses pytest verbose output for SKIPPED tests, checks for critical
    keywords. Returns audit info for state tracking and logging.

    Args:
        output: Combined stdout+stderr from pytest.

    Returns:
        Dict with skip_count, critical_count, critical_tests, gate_passed.
    """
    skipped_names = _SKIP_PATTERN.findall(output)
    if not skipped_names:
        return {
            "skip_count": 0,
            "critical_count": 0,
            "critical_tests": [],
            "gate_passed": True,
        }

    critical = []
    for name in skipped_names:
        name_lower = name.lower()
        if any(kw in name_lower for kw in _CRITICAL_SKIP_KEYWORDS):
            critical.append(name)

    return {
        "skip_count": len(skipped_names),
        "critical_count": len(critical),
        "critical_tests": critical,
        "gate_passed": len(critical) == 0,
    }


def _build_failure_summary(output: str) -> str:
    """Extract a concise failure summary from pytest output.

    Issue #498: Instead of feeding N4 the entire pytest output, extract
    only the "short test summary info" section which contains test names
    and one-line error messages. This tells N4 exactly what to fix.

    Args:
        output: Combined stdout + stderr from pytest.

    Returns:
        Concise failure summary, truncated to MAX_FAILURE_SUMMARY_CHARS.
        Empty string if no failures found.
    """
    import re

    lines = output.split("\n")
    summary_lines: list[str] = []

    # Extract "short test summary info" section
    in_summary = False
    for line in lines:
        if "short test summary info" in line:
            in_summary = True
            continue
        if in_summary:
            # Section ends at the next separator line (====)
            if line.startswith("=" * 10):
                # Capture the final summary (e.g., "2 failed, 1 passed in 0.15s")
                summary_lines.append(line.strip("= \n"))
                break
            if line.strip():
                summary_lines.append(line.strip())

    if not summary_lines:
        # Fallback: extract FAILED lines from anywhere in output
        for line in lines:
            if re.match(r"FAILED\s+", line):
                summary_lines.append(line.strip())

    if not summary_lines:
        return ""

    # #2058: group by root cause before spending the budget. Three consecutive
    # runs of boostgauge #2 rewrote all 7 files and landed on an identical pass
    # count -- N4 was revising against the first ~16 of 100+ failure lines the
    # 2000-char cap let through, blind to the rest. 41 tests failing on one
    # TypeError are ONE fact; grouping says so in one line and leaves budget
    # for every other distinct cause.
    grouped: dict[str, list[str]] = {}
    ungrouped: list[str] = []
    for line in summary_lines:
        m = re.match(r"FAILED\s+(\S+?)(?:\s+-\s+(.*))?$", line)
        if m and m.group(2):
            grouped.setdefault(m.group(2).strip(), []).append(m.group(1))
        else:
            ungrouped.append(line)

    if grouped:
        blocks: list[str] = []
        for reason, tests in sorted(
            grouped.items(), key=lambda kv: len(kv[1]), reverse=True
        ):
            shown = ", ".join(tests[:3])
            more = f" (and {len(tests) - 3} more)" if len(tests) > 3 else ""
            blocks.append(f"{len(tests)} test(s): {reason}\n    e.g. {shown}{more}")
        blocks.extend(ungrouped)
        result = "\n".join(blocks)
    else:
        result = "\n".join(summary_lines)

    # #2320: the short summary says WHICH tests failed. The tracebacks say WHY,
    # and run_pytest already asks for them with --tb=short. Reading only the
    # summary section threw the diagnosis away: on boostgauge #7 the discarded
    # block held `assert False` on the source line, which identified the tests
    # as unconditional stubs. The reviser instead saw 36 bare names and made a
    # six-line cosmetic edit, because nothing it was shown was actionable.
    tracebacks = _extract_traceback_blocks(output)
    if tracebacks:
        result = f"{result}\n\nFailure detail (source line and error):\n{tracebacks}"

    if len(result) > MAX_FAILURE_SUMMARY_CHARS:
        result = result[:MAX_FAILURE_SUMMARY_CHARS] + "\n... (truncated)"
    return result


def _extract_traceback_blocks(output: str) -> str:
    """Pull distinct failure tracebacks out of pytest's FAILURES section.

    #2320: returns the failing source line and the `E ...` error lines for up
    to MAX_TRACEBACK_BLOCKS DISTINCT failures. Blocks whose error lines are
    identical are collapsed with a count, because N tests failing on one cause
    is one fact and repeating it N times only spends the budget.

    Unlike the short-summary line, traceback content is not truncated to the
    terminal width, so this is informative regardless of #2319's environment
    fix -- the two repairs are independent on purpose.
    """
    import re

    failures_match = re.search(
        r"^=+ FAILURES =+$(.*?)(?=^=+ (?:short test summary|warnings summary|"
        r"ERRORS|[\w ]*coverage)|\Z)",
        output,
        re.MULTILINE | re.DOTALL,
    )
    if not failures_match:
        return ""

    section = failures_match.group(1)
    # Blocks are introduced by a centred `____ test_name ____` rule.
    parts = re.split(r"^_+ (.+?) _+$", section, flags=re.MULTILINE)
    if len(parts) < 3:
        return ""

    seen: dict[str, dict[str, Any]] = {}
    # parts alternates: [preamble, name, body, name, body, ...]
    for i in range(1, len(parts) - 1, 2):
        name = parts[i].strip()
        body = parts[i + 1]

        error_lines = [
            line.rstrip() for line in body.splitlines()
            if line.startswith("E ")
        ]
        if not error_lines:
            continue

        # The last non-E, non-blank line before the errors is the source line
        # that raised -- the single most useful line in the block.
        source_line = ""
        for line in body.splitlines():
            if line.startswith("E "):
                break
            if line.strip():
                source_line = line.strip()

        signature = "\n".join(error_lines)
        if signature in seen:
            seen[signature]["tests"].append(name)
            continue
        seen[signature] = {
            "tests": [name],
            "source": source_line,
            "errors": error_lines,
        }

    if not seen:
        return ""

    blocks: list[str] = []
    for entry in list(seen.values())[:MAX_TRACEBACK_BLOCKS]:
        tests = entry["tests"]
        header = tests[0]
        if len(tests) > 1:
            header = f"{tests[0]} (and {len(tests) - 1} more with the same error)"
        lines = [header]
        if entry["source"]:
            lines.append(f"    {entry['source']}")
        lines.extend(f"    {e}" for e in entry["errors"])
        blocks.append("\n".join(lines))

    if len(seen) > MAX_TRACEBACK_BLOCKS:
        blocks.append(
            f"... {len(seen) - MAX_TRACEBACK_BLOCKS} further distinct "
            f"failure cause(s) not shown"
        )
    return "\n\n".join(blocks)


def _classify_import_errors(
    output: str, expected_module_paths: list[str]
) -> tuple[int, int, list[str]]:
    """Classify ImportErrors in pytest output as expected or unexpected.

    Issue #842: In TDD red phase, ImportError on the module-under-test is
    expected (it doesn't exist yet). But ImportError on other modules means
    the generated code has hallucinated imports (e.g., assemblyzero.core.metrics).

    Args:
        output: Combined stdout + stderr from pytest.
        expected_module_paths: File paths of modules being implemented
            (e.g., ["assemblyzero/utils/foo.py"]). Converted to dotted
            module names for matching.

    Returns:
        Tuple of (expected_count, unexpected_count, unexpected_module_names).
    """
    # Convert file paths to dotted module names for matching
    # e.g., "assemblyzero/utils/foo.py" -> "assemblyzero.utils.foo"
    # Closes #1492: also strip common source-root prefixes so src-layout
    # repos (src/chiron/provenance.py -> chiron.provenance per Python
    # import resolution) match the names pytest actually reports.
    # Aligned with #1477's source-root list in implementation_spec.
    _SOURCE_ROOT_DOTTED = ("src.", "lib.", "source.", "python.", "apps.")
    expected_dotted: set[str] = set()
    for path in expected_module_paths:
        dotted = path.replace("/", ".").replace("\\", ".")
        if dotted.endswith(".py"):
            dotted = dotted[:-3]
        # Add raw form (flat-layout repos)
        expected_dotted.add(dotted)
        # Also add the source-root-stripped form (src-layout, lib-layout, etc.)
        for prefix in _SOURCE_ROOT_DOTTED:
            if dotted.startswith(prefix):
                expected_dotted.add(dotted[len(prefix):])
        # And each parent package of every form recorded so far so that
        # "from assemblyzero.utils import foo" matches as expected.
        for form in list(expected_dotted):
            parts = form.split(".")
            for i in range(1, len(parts)):
                expected_dotted.add(".".join(parts[:i]))

    # Parse ModuleNotFoundError / ImportError from pytest output
    # Patterns: "ModuleNotFoundError: No module named 'X'"
    #           "ImportError: cannot import name 'Y' from 'X'"
    import_error_pattern = re.compile(
        r"(?:ModuleNotFoundError|ImportError):\s*(?:No module named\s+['\"]([^'\"]+)['\"]"
        r"|cannot import name\s+['\"]?\w+['\"]?\s+from\s+['\"]([^'\"]+)['\"])"
    )

    expected_count = 0
    unexpected_count = 0
    unexpected_modules: list[str] = []
    seen_modules: set[str] = set()

    for match in import_error_pattern.finditer(output):
        module_name = match.group(1) or match.group(2)
        if not module_name or module_name in seen_modules:
            continue
        seen_modules.add(module_name)

        # Check if this module is one we expect to be missing
        is_expected = any(
            module_name == exp or module_name.startswith(exp + ".")
            or exp.startswith(module_name + ".")
            for exp in expected_dotted
        )

        if is_expected:
            expected_count += 1
        else:
            unexpected_count += 1
            unexpected_modules.append(module_name)

    return expected_count, unexpected_count, unexpected_modules


# Closes #1502: src-layout repos store importable packages under a
# source-root prefix dir which is NOT itself a package. The earlier
# is_package check only looked at top_level/__init__.py; for src-layout
# that returned False and the function fell back to file-path form,
# which pytest-cov measured as 0.0% (it expects module names or
# discoverable directories, not file paths inside a nested layout).
# Mirrors #1477's source-root list.
_COV_SOURCE_ROOT_PREFIXES: tuple[str, ...] = (
    "src", "lib", "source", "python", "apps",
)


def _is_python_package_dir(d: Path) -> bool:
    """True if `d` is a Python package — regular (`__init__.py`) or PEP 420
    namespace (directory with `.py` files but no `__init__.py`)."""
    try:
        if not d.is_dir():
            return False
        if (d / "__init__.py").exists():
            return True
        return any(f.suffix == ".py" for f in d.iterdir() if f.is_file())
    except (OSError, PermissionError):
        return False


def _path_to_cov_target(rel_path: str | Path, repo_root: Path | None) -> str:
    """Convert a relative file path to the correct --cov target.

    For Python packages (top-level dir has ``__init__.py``), returns dotted
    module format (e.g., ``assemblyzero.utils.file_type``).
    For src-layout packages (``src/<pkg>/...``), strips the source-root
    prefix and returns the dotted module form (Closes #1502). The nested
    package may be a regular or PEP 420 namespace package (Closes #1506).
    For standalone scripts (no ``__init__.py``, e.g., ``tools/``), returns
    the file path so pytest-cov measures the right file.
    """
    rel = Path(rel_path)
    top_level = rel.parts[0] if rel.parts else None

    # Flat-layout package: repo_root/<top>/__init__.py exists.
    is_flat_package = bool(
        top_level
        and repo_root
        and (repo_root / top_level / "__init__.py").exists()
    )

    # src-layout package: top_level is a source-root prefix and the
    # immediately-nested dir is a package. Accept BOTH regular packages
    # (have __init__.py) and PEP 420 namespace packages (no __init__.py
    # but the dir contains .py files). Without this, namespace-package
    # src-layouts fall through to file-path form and pytest-cov reports
    # 0% coverage (Closes #1506).
    is_src_layout_package = bool(
        top_level
        and top_level in _COV_SOURCE_ROOT_PREFIXES
        and len(rel.parts) > 1
        and repo_root is not None
        and _is_python_package_dir(repo_root / top_level / rel.parts[1])
    )

    rel_str = str(rel)
    if rel_str.endswith(".py"):
        rel_str = rel_str[:-3]

    if is_flat_package or is_src_layout_package:
        module = rel_str.replace("/", ".").replace("\\", ".")
        # Strip a known source-root prefix (Issue #387 / #1502).
        for prefix in _COV_SOURCE_ROOT_PREFIXES:
            if module.startswith(prefix + "."):
                module = module[len(prefix) + 1:]
                break
        return module

    # Return as a file path — pytest-cov accepts paths for non-package code
    return str(rel).replace("\\", "/")


def _pytest_env() -> dict[str, str]:
    """Environment for a captured pytest run (#2319).

    Sets COLUMNS so pytest does not truncate its short-summary lines to the
    80-column default it assumes when stdout is a pipe. Without this the
    ` - AssertionError: ...` half of every FAILED line is cut, the reviser
    receives test names with no reasons, and the #2058 root-cause grouping
    cannot fire because its regex needs the reason it never receives.

    Inherits the rest of the environment unchanged -- the venv, PATH and any
    repo-specific variables the run needs are all still required.
    """
    import os

    env = os.environ.copy()
    env["COLUMNS"] = PYTEST_OUTPUT_COLUMNS
    return env


def run_pytest(
    test_files: list[str],
    coverage_module: str | None = None,
    coverage_target: int | None = None,
    repo_root: Path | None = None,
) -> dict:
    """Run pytest on the specified test files.

    Args:
        test_files: List of test file paths.
        coverage_module: Module to measure coverage for.
        coverage_target: Coverage threshold percentage.
        repo_root: Repository root for running pytest.

    Returns:
        Dict with returncode, stdout, stderr, and parsed results.
    """
    # Issue #268: Use poetry run to ensure correct virtualenv with dependencies
    cmd = ["poetry", "run", "pytest", "-v", "--tb=short"]
    cmd.extend(test_files)

    # Issue #789: Only add --cov flags if pytest-cov is installed.
    # Without it, pytest returns exit code 4 ("unrecognized arguments")
    # which the workflow misclassifies as "collection/syntax error" and loops.
    if coverage_module:
        try:
            import pytest_cov  # noqa: F401
            cmd.extend([f"--cov={coverage_module}", "--cov-report=term-missing"])
            if coverage_target:
                cmd.append(f"--cov-fail-under={coverage_target}")
        except ImportError:
            print("    [WARN] pytest-cov not installed — skipping coverage measurement")

    try:
        result = run_command(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=PYTEST_TIMEOUT_SECONDS,
            cwd=str(repo_root) if repo_root else None,
            env=_pytest_env(),
        )

        parsed = parse_pytest_output(result.stdout + result.stderr)

        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "parsed": parsed,
        }

    except subprocess.TimeoutExpired:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": "Pytest execution timed out",
            "parsed": {"passed": 0, "failed": 0, "errors": 1, "coverage": 0},
        }
    except FileNotFoundError:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": "pytest not found. Is it installed?",
            "parsed": {"passed": 0, "failed": 0, "errors": 1, "coverage": 0},
        }


def _describe_hollow_suite(state: TestingWorkflowState) -> str:
    """Describe a scaffold that cannot pass, or '' when it might (#2322).

    The red phase's job is to confirm the tests fail for the RIGHT reason.
    An ImportError says only that the module under test is missing; every
    test body is still unexecuted, so a suite made entirely of unconditional
    failures is indistinguishable from a healthy red phase at that moment.

    Reads the scaffold's source rather than its behaviour, which is what
    makes the distinction available at all while the implementation does not
    yet exist. Anything it cannot parse or find returns '' -- an unreadable
    suite is not evidence of a hollow one, and this must never invent a
    failure.
    """
    source = state.get("generated_tests", "") or ""
    if not source:
        for path in state.get("test_files", []) or []:
            try:
                source += Path(path).read_text(encoding="utf-8") + "\n"
            except OSError:
                continue
    if not source.strip():
        return ""

    total, stubs, names = count_stub_tests(source)
    if total == 0 or stubs != total:
        return ""

    shown = ", ".join(names[:3])
    more = f" (and {stubs - 3} more)" if stubs > 3 else ""
    # ASCII only: printed to a Windows console, where #1493 showed a non-ASCII
    # character raises UnicodeEncodeError mid-stream.
    return (
        f"all {total} test(s) fail unconditionally ({shown}{more}) -- no "
        f"implementation can make this suite green"
    )


def verify_red_phase(state: TestingWorkflowState) -> dict[str, Any]:
    """N3: Verify all tests fail (TDD red phase).

    The red phase confirms that:
    1. All tests are syntactically valid and runnable
    2. All tests fail (no pre-existing implementation)
    3. Failures are the expected "TDD: Implementation pending" assertions

    Args:
        state: Current workflow state.

    Returns:
        State updates with red phase results.
    """
    gate_log("[N3] Verifying red phase (all tests should fail)...")

    # Check for mock mode
    if state.get("mock_mode"):
        return _mock_verify_red_phase(state)

    # Issue #381: Framework-aware red phase
    framework_config = state.get("framework_config")
    if framework_config:
        fw_enum = _resolve_framework_enum(framework_config)
        if fw_enum and fw_enum != TestFramework.PYTEST:
            return _verify_red_non_pytest(state, framework_config, fw_enum)

    # Get data from state
    test_files = state.get("test_files", [])
    repo_root_str = state.get("repo_root", "")
    repo_root = Path(repo_root_str) if repo_root_str else get_repo_root()

    # --------------------------------------------------------------------------
    # GUARD: Validate test files exist
    # --------------------------------------------------------------------------
    if not test_files:
        print("    [GUARD] BLOCKED: No test files to run")
        return {"error_message": "GUARD: No test files generated"}

    for tf in test_files:
        if not Path(tf).exists():
            print(f"    [GUARD] BLOCKED: Test file not found: {tf}")
            return {"error_message": f"GUARD: Test file not found: {tf}"}
    # --------------------------------------------------------------------------

    print(f"    Running pytest on {len(test_files)} test file(s)...")

    # Run pytest
    result = run_pytest(test_files, repo_root=repo_root)
    exit_code = result["returncode"]
    output = result["stdout"] + "\n" + result["stderr"]
    parsed = result["parsed"]

    print(f"    Results: {parsed.get('passed', 0)} passed, {parsed.get('failed', 0)} failed")
    print(f"    Exit code: {exit_code} ({describe_exit_code(exit_code)})")

    # Save output to audit trail
    audit_dir_str = state.get("audit_dir", "")
    audit_dir = Path(audit_dir_str) if audit_dir_str else None
    if audit_dir and audit_dir.exists():
        file_num = next_file_number(audit_dir)
        save_audit_file(audit_dir, file_num, "red-phase.txt", output)
    else:
        file_num = state.get("file_counter", 0)

    # Issue #292: Check exit code FIRST for routing decisions
    # Exit codes 4 (syntax/collection error) and 5 (no tests collected) mean
    # the scaffold itself is broken — route back to N2 to regenerate.
    # Exit codes 2 (interrupted) and 3 (internal error) stop the workflow.
    if exit_code in (EXIT_USAGEERROR, EXIT_NOTESTSCOLLECTED):
        reason = describe_exit_code(exit_code)
        print(f"    [EXIT CODE {exit_code}] {reason} — routing to re-scaffold")

        log_workflow_execution(
            target_repo=repo_root,
            issue_number=state.get("issue_number", 0),
            workflow_type="testing",
            event="red_phase_scaffold_error",
            details={"exit_code": exit_code, "reason": reason},
        )

        return {
            "red_phase_output": output,
            "file_counter": file_num,
            "pytest_exit_code": exit_code,
            "next_node": "N2_scaffold_tests",
            "error_message": "",
        }

    if exit_code == EXIT_INTERRUPTED:
        # Closes #1492: exit 2 is documented as "interrupted by user", but
        # pytest also returns 2 when collection fails because of
        # ImportError on a module that doesn't exist yet — i.e. the
        # expected red signal at the start of TDD. Classify the output
        # first; route to N4_implement_code if the missing module is one
        # the spec said it would Add. Only END on genuine interruption.
        files_to_modify_for_red = state.get("files_to_modify", [])
        expected_modules_for_red = [
            f["path"] for f in files_to_modify_for_red
            if f.get("path", "").endswith(".py")
        ]
        exp_count_red, unexp_count_red, _ = _classify_import_errors(
            output, expected_modules_for_red
        )
        if exp_count_red > 0 and unexp_count_red == 0:
            # #2322: an ImportError proves the module is ABSENT. It does not
            # prove the tests discriminate. Collection died before a single
            # body ran, so a suite of unconditional `assert False` stubs
            # produces exactly this signal -- and on boostgauge #7 it did,
            # which is how a suite no implementation could pass reached the
            # implementation stage and spent two iterations there.
            #
            # The bodies are visible statically even while the module is
            # missing, so the check that collection cannot make is made here.
            hollow = _describe_hollow_suite(state)
            if hollow:
                print(
                    f"    [EXIT CODE {exit_code}] ImportError on expected "
                    f"module(s), but the suite cannot pass either: {hollow}"
                )
                # Re-scaffold only where it can produce something better --
                # since #2316 that means the spec ships executable Section 10
                # functions the scaffold did not use. Otherwise a reroute just
                # regenerates the same stubs, so the finding is stated and the
                # run continues rather than circling.
                if (state.get("spec_test_suite") or {}).get("functions"):
                    print(
                        "    the spec supplies executable test functions "
                        "-> routing to re-scaffold, not to implementation"
                    )
                    return {
                        "red_phase_output": output,
                        "file_counter": file_num,
                        "pytest_exit_code": exit_code,
                        "next_node": "N2_scaffold_tests",
                        "scaffold_validation_errors": [hollow],
                        "error_message": "",
                    }
                print(
                    "    the spec supplies no test bodies, so re-scaffolding "
                    "cannot improve on this -- continuing, but the "
                    "implementation loop cannot converge against these tests"
                )
            print(
                f"    [EXIT CODE {exit_code}] ImportError on expected module(s) "
                f"-> valid red signal, routing to implementation"
            )
            return {
                "red_phase_output": output,
                "file_counter": file_num,
                "pytest_exit_code": exit_code,
                "next_node": "N4_implement_code",
                "error_message": "",
            }
        # Fall through to the generic interrupted handler below.

    if exit_code in (EXIT_INTERRUPTED, EXIT_INTERNALERROR):
        reason = describe_exit_code(exit_code)
        # Closes #1493: ASCII-only print, no Unicode arrows. Windows cp1252
        # otherwise raises UnicodeEncodeError mid-stream.
        print(f"    [EXIT CODE {exit_code}] {reason} -- stopping workflow")

        return {
            "red_phase_output": output,
            "file_counter": file_num,
            "pytest_exit_code": exit_code,
            "next_node": "end",
            "error_message": f"Red phase stopped: pytest {reason} (exit code {exit_code})",
        }

    # Analyze pass/fail counts (exit codes 0 and 1)
    passed_count = parsed.get("passed", 0)
    failed_count = parsed.get("failed", 0)
    error_count = parsed.get("errors", 0)

    # Issue #842: Classify import errors — expected (module-under-test) vs
    # unexpected (hallucinated imports like assemblyzero.core.metrics).
    files_to_modify = state.get("files_to_modify", [])
    expected_modules = [f["path"] for f in files_to_modify if f.get("path", "").endswith(".py")]
    expected_import_count, unexpected_import_count, unexpected_modules = _classify_import_errors(
        output, expected_modules
    )

    if unexpected_import_count > 0:
        # Issue #842: Unexpected ImportErrors are code defects, not valid red.
        # Route back to N4 with specific feedback about broken imports.
        bad_modules_str = ", ".join(unexpected_modules[:5])
        error_msg = (
            f"Red phase detected {unexpected_import_count} unexpected ImportError(s): "
            f"{bad_modules_str}. These modules do not exist in the codebase. "
            f"Fix the imports in the generated code."
        )
        print(f"    [GUARD] {error_msg}")

        log_workflow_execution(
            target_repo=repo_root,
            issue_number=state.get("issue_number", 0),
            workflow_type="testing",
            event="red_phase_unexpected_imports",
            details={
                "unexpected_modules": unexpected_modules,
                "expected_import_count": expected_import_count,
            },
        )

        return {
            "red_phase_output": output,
            "file_counter": file_num,
            "pytest_exit_code": exit_code,
            "error_message": error_msg,
            "next_node": "N4_implement_code",
        }

    # Issue #263: Expected import errors are valid RED phase behavior.
    # With import-based TDD scaffolding, ImportError on the module-under-test
    # means "module doesn't exist yet" which is exactly what RED should catch.
    total_red = failed_count + error_count

    # Red phase success = ALL tests fail or error (none pass)
    if passed_count > 0:
        print(f"    [GUARD] WARNING: {passed_count} tests passed unexpectedly!")
        print("    This may indicate pre-existing implementation.")

        log_workflow_execution(
            target_repo=repo_root,
            issue_number=state.get("issue_number", 0),
            workflow_type="testing",
            event="red_phase_unexpected_pass",
            details={"passed": passed_count, "failed": failed_count, "errors": error_count},
        )

        return {
            "red_phase_output": output,
            "file_counter": file_num,
            "pytest_exit_code": exit_code,
            "error_message": f"Red phase failed: {passed_count} tests passed unexpectedly. "
                           "Tests should fail before implementation.",
            "next_node": "END",
        }

    if total_red == 0:
        print("    [GUARD] WARNING: No tests ran!")

        return {
            "red_phase_output": output,
            "file_counter": file_num,
            "pytest_exit_code": exit_code,
            "error_message": "Red phase failed: No tests were collected/run",
            "next_node": "END",
        }

    # Success: all tests failed or errored as expected
    if expected_import_count > 0:
        print(f"    Red phase PASSED: {expected_import_count} expected import errors (module doesn't exist yet)")
    if failed_count > 0:
        print(f"    Red phase PASSED: {failed_count} tests failed as expected")

    log_workflow_execution(
        target_repo=repo_root,
        issue_number=state.get("issue_number", 0),
        workflow_type="testing",
        event="red_phase_complete",
        details={"failed": failed_count, "errors": error_count, "exit_code": exit_code},
    )

    return {
        "red_phase_output": output,
        "file_counter": file_num,
        "pytest_exit_code": exit_code,
        "next_node": "N4_implement_code",
        "error_message": "",
    }


COVERAGE_IMPROVEMENT_THRESHOLD = 1.0


def _hill_climb(
    state, repo_root, passed_count, coverage_achieved, current_green_failures,
    updates,
) -> None:
    """Never revise from a state worse than the best one seen (#2050).

    boostgauge #2 oscillated 36% -> 99% (39/41 passing) -> 36% (7/15) and
    halted holding the WORST state it had produced: iteration 2 was one
    revision from done and iteration 3 threw it away. The loop was a random
    walk over drafter variance with no memory of its best result.

    After each measurement: a new best snapshots the implementation and test
    files; a worse iteration restores the best files to the worktree before N4
    revises again and carries the BEST metrics as previous_*, so the stagnation
    guards compare against the best rather than the latest roll of the dice.
    A worse iteration then costs one revision instead of the run.

    Mutates `updates` in place. Best-effort: snapshot or restore trouble is
    reported and never fails the node.
    """
    import shutil

    impl_files = state.get("implementation_files", []) or []
    test_files = state.get("test_files", []) or []
    tracked = [f for f in (*impl_files, *test_files) if f]
    if not tracked:
        return

    best = state.get("best_iteration") or None
    score = (passed_count, coverage_achieved)
    best_score = (
        (best.get("passed", -1), best.get("coverage", -1.0)) if best else None
    )

    if best_score is None or score > best_score:
        snap_root = Path(state.get("audit_dir") or Path(repo_root) / ".az-best-iteration")
        snap_dir = snap_root / "best-iteration"
        manifest: dict[str, str] = {}
        try:
            if snap_dir.exists():
                shutil.rmtree(snap_dir)
            snap_dir.mkdir(parents=True, exist_ok=True)
            for idx, file_str in enumerate(tracked):
                src = Path(file_str)
                if src.is_file():
                    dst = snap_dir / f"{idx:02d}-{src.name}"
                    shutil.copy2(src, dst)
                    manifest[str(src)] = str(dst)
        except OSError as exc:
            print(f"    [N5] best-iteration snapshot failed (non-fatal): {exc}")
            return
        updates["best_iteration"] = {
            "passed": passed_count,
            "coverage": coverage_achieved,
            "green_failures": list(current_green_failures or []),
            "files": manifest,
        }
        print(
            f"    [N5] best iteration so far: {passed_count} passing at "
            f"{coverage_achieved:.1f}% — snapshotted {len(manifest)} file(s)"
        )
        return

    if score < best_score:
        restored = 0
        for src_str, snap_str in (best.get("files") or {}).items():
            try:
                if Path(snap_str).is_file():
                    shutil.copy2(snap_str, src_str)
                    restored += 1
            except OSError as exc:
                print(f"    [N5] could not restore {src_str} (non-fatal): {exc}")
        updates["previous_passed"] = best.get("passed", passed_count)
        updates["previous_coverage"] = best.get("coverage", coverage_achieved)
        updates["previous_green_failures"] = best.get("green_failures", [])
        print(
            f"    [N5] iteration regressed ({passed_count} passing at "
            f"{coverage_achieved:.1f}% vs best {best.get('passed')} at "
            f"{best.get('coverage'):.1f}%) — restored {restored} file(s) from "
            f"the best iteration; revising from there instead"
        )


def _snapshot_untracked(repo_root) -> set[str] | None:
    """Untracked paths right now, or None when git cannot say (#2048)."""
    # -uall: without it git collapses an untracked directory to "dir/" and the
    # files inside never appear -- exactly where generated baselines land
    # (tests/visual/baselines/ is born whole during the run).
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "-uall"],
            cwd=str(repo_root), capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
    except OSError:
        # Nonexistent cwd, git missing -- could not measure, so measure nothing.
        return None
    if result.returncode != 0:
        return None
    return {
        line[3:].strip().strip('"')
        for line in result.stdout.splitlines()
        if line.startswith("??")
    }


def _remove_test_run_droppings(repo_root, before: set[str] | None) -> None:
    """Delete untracked files a pytest run just created (#2048).

    Scope is exact: only paths untracked NOW that were not untracked BEFORE the
    run started. Implementation files are written by N4 before pytest ever
    runs, so they are in the before-set; anything newer was created by the test
    execution itself -- generated baselines, caches, stray outputs -- and
    carrying it into the next iteration makes iterations judge each other. The
    poisoning case: a generated visual test saved its baseline in iteration 1
    and every later iteration failed against it, unwinnable by revision.

    None for `before` means the snapshot failed; delete nothing rather than
    guess ("could not measure" is not "nothing was there" -- #2028's rule).
    """
    if before is None:
        return
    after = _snapshot_untracked(repo_root)
    if after is None:
        return
    from pathlib import Path as _Path

    for rel in sorted(after - before):
        target = _Path(repo_root) / rel
        try:
            if target.is_file():
                target.unlink()
                print(f"    [N5] removed test-run dropping: {rel}")
        except OSError as exc:
            print(f"    [N5] could not remove test-run dropping {rel}: {exc}")

# "cannot import name 'render' from 'boostgauge.gauge'" — the shape pytest
# prints when a phase removed something an earlier phase published.
_MISSING_NAME_RE = re.compile(
    r"cannot import name ['\"](?P<name>[\w.]+)['\"] from ['\"](?P<module>[\w.]+)['\"]"
)
_MISSING_MODULE_RE = re.compile(
    r"No module named ['\"](?P<module>[\w.]+)['\"]"
)
_COLLECT_ERROR_RE = re.compile(r"ERROR collecting (?P<path>\S+)")


def describe_collection_failures(output: str, limit: int = 3) -> str:
    """Name what failed to import, from pytest's own output (#2035).

    Exit 2 is usually a collection failure, and pytest has already said which
    import broke. That was discarded, so a phase deleting a symbol an earlier
    phase published surfaced as "pytest test execution interrupted" with
    Error: unknown -- and diagnosing one took a manual worktree from a
    checkpoint commit plus a re-run by hand.

    Deliberately reports the symbol and its module rather than the traceback:
    "cannot import name render from boostgauge.gauge" is the whole diagnosis,
    and the phase that published `render` is then obvious.
    """
    if not output:
        return ""

    parts: list[str] = []
    seen: set[str] = set()

    for match in _MISSING_NAME_RE.finditer(output):
        item = f"{match.group('module')}.{match.group('name')} no longer exists"
        if item not in seen:
            seen.add(item)
            parts.append(item)
    for match in _MISSING_MODULE_RE.finditer(output):
        item = f"module {match.group('module')} not found"
        if item not in seen:
            seen.add(item)
            parts.append(item)

    if not parts:
        files = [m.group("path") for m in _COLLECT_ERROR_RE.finditer(output)]
        unique = list(dict.fromkeys(files))
        if unique:
            return f"Collection failed in: {', '.join(unique[:limit])}"
        return ""

    shown = "; ".join(parts[:limit])
    if len(parts) > limit:
        shown += f" (and {len(parts) - limit} more)"
    return f"Imports that no longer resolve: {shown}"


def coverage_has_stagnated(
    coverage_achieved: float,
    previous_coverage: float,
    passed_count: int,
    previous_passed: int,
    current_green_failures: list[str],
    previous_green_failures: list[str],
) -> bool:
    """Whether this iteration earned another one (#2029, #2030).

    ONE decision, called from both branches of verify_green_phase. They carried
    near-identical copies of this check, and #2023 repaired only the branch
    whose symptom had been seen -- so the twin halted a plainly improving run on
    the very next live arc: 20 -> 22 passing, 3 -> 1 failing, 97.0% -> 98.0%,
    reported as stagnant. A duplicated guard is how a fix lands on one side
    only, so there is now nowhere for the two to disagree.

    Two things count that the old condition missed.

    Test outcomes are progress (#2029). The point of another iteration is that
    the last one moved something, and in the tests-failing branch the two guards
    immediately above compute exactly this and then it was thrown away.

    An improvement of exactly the threshold MEETS the threshold (#2030). The old
    `<= previous + 1.0` halted on a 1.0 point gain while printing
    "< 1% improvement", so the code and its own message described different
    rules.
    """
    if previous_coverage < 0:
        return False  # first iteration has nothing to compare against

    if coverage_achieved - previous_coverage >= COVERAGE_IMPROVEMENT_THRESHOLD:
        return False

    tests_improved = (
        (previous_passed >= 0 and passed_count > previous_passed)
        or (
            bool(previous_green_failures)
            and len(current_green_failures) < len(previous_green_failures)
        )
    )
    if tests_improved:
        print(
            f"    [N5] Coverage {previous_coverage:.1f}% -> {coverage_achieved:.1f}%, "
            f"but tests improved ({previous_passed} -> {passed_count} passing) — "
            f"continuing rather than halting."
        )
        return False

    return True


def verify_green_phase(state: TestingWorkflowState) -> dict[str, Any]:
    """N5: Verify all tests pass with coverage target.

    The green phase confirms that:
    1. All tests pass
    2. Coverage meets target (default 90%)

    Args:
        state: Current workflow state.

    Returns:
        State updates with green phase results.
    """
    gate_log("[N5] Verifying green phase (all tests should pass)...")

    # Check for mock mode
    if state.get("mock_mode"):
        return _mock_verify_green_phase(state)

    # Issue #381: Framework-aware green phase
    framework_config = state.get("framework_config")
    if framework_config:
        fw_enum = _resolve_framework_enum(framework_config)
        if fw_enum and fw_enum != TestFramework.PYTEST:
            return _verify_green_non_pytest(state, framework_config, fw_enum)

    # Get data from state
    test_files = state.get("test_files", [])
    coverage_target = state.get("coverage_target", 90)
    repo_root_str = state.get("repo_root", "")
    repo_root = Path(repo_root_str) if repo_root_str else get_repo_root()
    iteration_count = state.get("iteration_count", 0)

    print(f"    Running pytest with coverage target: {coverage_target}%")

    # Determine coverage module from implementation files
    # Filter out test files - we want to measure coverage of implementation, not tests
    impl_files = state.get("implementation_files", [])
    coverage_module = None

    if impl_files:
        # Find first non-test, non-init, Python implementation file for coverage
        for impl_path in impl_files:
            # Skip test files (in tests/ directory)
            path_parts = Path(impl_path).parts
            if any(part.lower() in ("tests", "test") for part in path_parts):
                continue
            # Issue #265: Skip __init__.py - pytest-cov doesn't work with it
            if impl_path.endswith("__init__.py"):
                continue
            # Skip non-Python files (.gitkeep, .json, .yml, etc.)
            if not impl_path.endswith(".py"):
                print(f"    [N5] Skipping non-Python file for coverage: {impl_path}")
                continue
            rel_path = Path(impl_path).relative_to(repo_root) if repo_root else Path(impl_path)
            # Issue #474: Use helper that handles both packages and standalone scripts
            coverage_module = _path_to_cov_target(rel_path, repo_root)
            break

    # Issue #462: When all impl files are test files (test-only issues),
    # fall back to files_to_modify from LLD to find the source module
    if not coverage_module:
        files_to_modify = state.get("files_to_modify", [])
        for file_info in files_to_modify:
            fpath = file_info.get("path", "")
            if "test" in fpath.lower():
                continue
            if fpath.endswith("__init__.py"):
                continue
            if not fpath.endswith(".py"):
                continue
            # Issue #474: Use helper that handles both packages and standalone scripts
            coverage_module = _path_to_cov_target(fpath, repo_root)
            print(f"    [N5] Derived coverage module from LLD files_to_modify: {coverage_module}")
            break

    # Issue #462 fallback 2: reverse-map test file name to source module
    # e.g., tests/unit/test_circuit_breaker.py → find circuit_breaker.py in repo
    if not coverage_module and test_files:
        for tf in test_files:
            tf_name = Path(tf).name  # e.g., test_circuit_breaker.py
            if tf_name.startswith("test_"):
                src_name = tf_name[5:]  # e.g., circuit_breaker.py
                # Search for matching source file in repo
                matches = list(repo_root.rglob(src_name)) if repo_root else []
                # Filter to .py files not in tests/ directories
                for match in matches:
                    match_parts = match.relative_to(repo_root).parts
                    if any(p.lower() in ("tests", "test") for p in match_parts):
                        continue
                    # Issue #474: Use helper that handles both packages and standalone scripts
                    rel_path = match.relative_to(repo_root)
                    coverage_module = _path_to_cov_target(rel_path, repo_root)
                    print(f"    [N5] Derived coverage module from test filename: {coverage_module}")
                    break
                if coverage_module:
                    break

    # Issue #474: Last resort — infer from any available file paths before
    # falling back to a hardcoded default.  Previous versions always fell
    # back to "assemblyzero", which measured 0% for tools/ targets.
    if not coverage_module:
        # Try ALL files (including non-.py) to at least get the right directory
        all_candidate_paths = [
            p for p in impl_files
            if not any(part.lower() in ("tests", "test") for part in Path(p).parts)
        ]
        if not all_candidate_paths:
            all_candidate_paths = [
                fi.get("path", "")
                for fi in state.get("files_to_modify", [])
                if fi.get("path") and "test" not in fi["path"].lower()
            ]
        if all_candidate_paths:
            rel = Path(all_candidate_paths[0])
            if repo_root:
                try:
                    rel = rel.relative_to(repo_root)
                except ValueError:
                    pass
            # Use the top-level directory as coverage scope
            coverage_module = str(rel.parts[0]).replace("\\", "/") if rel.parts else "assemblyzero"
            print(f"    [N5] Fallback: inferred coverage scope from file paths: {coverage_module}")
        else:
            coverage_module = "assemblyzero"
            print(f"    [N5] Fallback: no file paths available, defaulting to: {coverage_module}")

    print(f"    Coverage module: {coverage_module}")

    result = run_pytest(
        test_files,
        coverage_module=coverage_module,
        coverage_target=coverage_target,
        repo_root=repo_root,
    )
    exit_code = result["returncode"]
    output = result["stdout"] + "\n" + result["stderr"]
    parsed = result["parsed"]

    print(f"    [N5] Results: {parsed.get('passed', 0)} passed, {parsed.get('failed', 0)} failed | "
          f"Coverage: {parsed.get('coverage', 0):.1f}% | Exit: {exit_code} "
          f"({describe_run_outcome(exit_code, parsed.get('failed'))})")

    # Save output to audit trail
    audit_dir_str = state.get("audit_dir", "")
    audit_dir = Path(audit_dir_str) if audit_dir_str else None
    if audit_dir and audit_dir.exists():
        file_num = next_file_number(audit_dir)
        save_audit_file(audit_dir, file_num, "green-phase.txt", output)
    else:
        file_num = state.get("file_counter", 0)

    # Issue #292: Check exit code FIRST for routing decisions
    # Exit codes 4/5 mean scaffold is broken — not an implementation problem.
    # Route back to N2 to regenerate tests instead of looping through N4.
    if exit_code in (EXIT_USAGEERROR, EXIT_NOTESTSCOLLECTED):
        reason = describe_exit_code(exit_code)
        print(f"    [EXIT CODE {exit_code}] {reason} — routing to re-scaffold")

        log_workflow_execution(
            target_repo=repo_root,
            issue_number=state.get("issue_number", 0),
            workflow_type="testing",
            event="green_phase_scaffold_error",
            details={"exit_code": exit_code, "reason": reason, "iteration": iteration_count},
        )

        return {
            "green_phase_output": output,
            "coverage_achieved": 0,
            "file_counter": file_num,
            "pytest_exit_code": exit_code,
            "iteration_count": iteration_count + 1,
            "next_node": "N2_scaffold_tests",
            "error_message": "",
        }

    if exit_code in (EXIT_INTERRUPTED, EXIT_INTERNALERROR):
        reason = describe_exit_code(exit_code)
        print(f"    [EXIT CODE {exit_code}] {reason} — stopping workflow")

        # #2035: exit 2 is usually a COLLECTION failure, and pytest has already
        # said exactly which import broke. That detail was discarded, so a phase
        # that deleted a symbol an earlier phase published surfaced as
        # "pytest test execution interrupted" with Error: unknown -- diagnosing
        # one took a manual worktree from a checkpoint commit and a re-run by
        # hand. Everything below was in the output all along.
        broken = describe_collection_failures(output)
        detail = f" {broken}" if broken else ""
        if broken:
            print(f"    [EXIT CODE {exit_code}] {broken}")

        return {
            "green_phase_output": output,
            "coverage_achieved": 0,
            "file_counter": file_num,
            "pytest_exit_code": exit_code,
            "iteration_count": iteration_count,
            "next_node": "end",
            "error_message": (
                f"Green phase stopped: pytest {reason} "
                f"(exit code {exit_code}).{detail}"
            ),
        }

    # Analyze results (exit codes 0 and 1)
    passed_count = parsed.get("passed", 0)
    failed_count = parsed.get("failed", 0)
    error_count = parsed.get("errors", 0)
    coverage_achieved = parsed.get("coverage", 0)

    # Stagnation detection: coverage must improve by >=1% each iteration
    previous_coverage = state.get("previous_coverage", -1.0)
    max_iterations = state.get("max_iterations", 5)

    # Issue #498: Build concise failure summary for N4 feedback
    failure_summary = _build_failure_summary(output)

    # Issue #501: Extract failed test names for identity-based stagnation
    current_green_failures = _extract_failed_test_names(output)

    # Check for failures
    if failed_count > 0 or error_count > 0:
        # Check if we've exhausted iterations
        if iteration_count + 1 >= max_iterations:
            print(f"    [ERROR] Max iterations ({max_iterations}) reached with {failed_count} failures")
            error_msg = f"Green phase failed after {max_iterations} iterations: {failed_count} tests still failing"
            return {
                "green_phase_output": output,
                "coverage_achieved": coverage_achieved,
                "previous_coverage": coverage_achieved,
                "previous_passed": passed_count,
                "previous_green_failures": current_green_failures,
                "test_failure_summary": failure_summary,
                "file_counter": file_num,
                "pytest_exit_code": exit_code,
                "iteration_count": iteration_count + 1,
                "next_node": "end",
                "error_message": error_msg,
            }

        # Stagnation check: if passed count unchanged from previous iteration, halt.
        # Catches 0/N->0/N loops (e.g., circular imports, total import failures).
        #
        # #2062: two strikes for ZERO passing (the #457 import-death loop this
        # guard was built for), three for a nonzero plateau. Five boostgauge #2
        # runs halted on the SECOND identical count with three iterations
        # unspent -- and the first of those seconds was judged while the
        # revision was starving on a 2000-char feedback window (#2058). With
        # full-cause feedback now flowing, one identical count is one revision
        # that did not move the needle, not proof no revision can.
        previous_passed = state.get("previous_passed", -1)
        plateau_strikes = state.get("count_plateau_strikes", 0)
        if previous_passed >= 0 and passed_count == previous_passed:
            plateau_strikes += 1
        else:
            plateau_strikes = 0
        strikes_needed = 1 if passed_count == 0 else 2
        if previous_passed >= 0 and passed_count == previous_passed and (
            plateau_strikes >= strikes_needed
        ):
            stagnant_msg = (
                f"Test count stagnant: {passed_count}/{passed_count + failed_count} passed "
                f"(unchanged across {plateau_strikes + 1} iterations). "
                f"Halting to prevent token waste."
            )
            print(f"    [STAGNANT] {stagnant_msg}")
            return {
                "green_phase_output": output,
                "coverage_achieved": coverage_achieved,
                "previous_coverage": coverage_achieved,
                "previous_passed": passed_count,
                "previous_green_failures": current_green_failures,
                "test_failure_summary": failure_summary,
                "file_counter": file_num,
                "pytest_exit_code": exit_code,
                "iteration_count": iteration_count + 1,
                "next_node": "end",
                "error_message": stagnant_msg,
            }

        # Issue #501: Identity-based stagnation — same tests failing across iterations.
        # Catches cases where pass count fluctuates but the SAME tests keep failing.
        #
        # #2064: a repeated failing set is a FIXED POINT, not just fatigue. Both
        # tests and impl are regenerated from the same spec that causes their
        # disagreement, so a deterministic drafter reproduces the exact failure
        # set — six boostgauge #2 runs repeated their counts to the digit. The
        # first repeat now breaks the symmetry instead of halting: the tests
        # become a frozen contract (the passing ones prove they can run) and N4
        # rewrites ONLY the implementation to satisfy them. Halt on the third
        # identical set, when the symmetry-break has had its chance.
        previous_green_failures = state.get("previous_green_failures", [])
        identity_stagnant = (
            bool(current_green_failures)
            and bool(previous_green_failures)
            and current_green_failures == sorted(previous_green_failures)
        )
        identity_strikes = state.get("identity_plateau_strikes", 0)
        if identity_stagnant:
            identity_strikes += 1
        else:
            identity_strikes = 0
        if identity_stagnant and identity_strikes >= 2:
            stagnant_msg = (
                f"Test identity stagnant: same {len(current_green_failures)} test(s) failing "
                f"across {identity_strikes + 1} iterations (tests were frozen for the "
                f"retry). Halting to prevent token waste."
            )
            print(f"    [STAGNANT] {stagnant_msg}")
            return {
                "green_phase_output": output,
                "coverage_achieved": coverage_achieved,
                "previous_coverage": coverage_achieved,
                "previous_passed": passed_count,
                "previous_green_failures": current_green_failures,
                "test_failure_summary": failure_summary,
                "file_counter": file_num,
                "pytest_exit_code": exit_code,
                "iteration_count": iteration_count + 1,
                "next_node": "end",
                "error_message": stagnant_msg,
            }
        if identity_stagnant:
            # #2066: the armed break LOOPS BACK HERE, before any further guard.
            # The first version printed this and fell through -- the coverage
            # guard then saw the same flat numbers and halted the run before
            # the frozen iteration ever executed. A break that never runs is
            # the old halt with extra words. If the frozen attempt also fails
            # to move anything, the NEXT pass halts through the normal guards,
            # which is the break having had its chance.
            print(
                f"    [N5] same {len(current_green_failures)} test(s) failing again — "
                f"freezing tests as the contract; next revision rewrites only the "
                f"implementation (strike {identity_strikes})"
            )
            return {
                "green_phase_output": output,
                "coverage_achieved": coverage_achieved,
                "previous_coverage": coverage_achieved,
                "previous_passed": passed_count,
                "previous_green_failures": current_green_failures,
                "test_failure_summary": failure_summary,
                "file_counter": file_num,
                "pytest_exit_code": exit_code,
                "iteration_count": iteration_count + 1,
                "next_node": "N4_implement_code",
                "error_message": "",
                "count_plateau_strikes": plateau_strikes,
                "identity_plateau_strikes": identity_strikes,
                "freeze_tests": True,
            }

        # Stagnation check: one shared decision, see coverage_has_stagnated.
        # Skip when passed_count == 0: coverage is vacuously 100% with no passing
        # tests, so the metric is meaningless. The test-count check above handles that case.
        if passed_count > 0 and coverage_has_stagnated(
            coverage_achieved, previous_coverage, passed_count, previous_passed,
            current_green_failures, previous_green_failures,
        ):
            stagnant_msg = (
                f"Coverage stagnant: {previous_coverage:.1f}% -> {coverage_achieved:.1f}% "
                f"(< 1% improvement). Halting to prevent token waste."
            )
            print(f"    [STAGNANT] {stagnant_msg}")
            return {
                "green_phase_output": output,
                "coverage_achieved": coverage_achieved,
                "previous_coverage": coverage_achieved,
                "previous_passed": passed_count,
                "previous_green_failures": current_green_failures,
                "test_failure_summary": failure_summary,
                "file_counter": file_num,
                "pytest_exit_code": exit_code,
                "iteration_count": iteration_count + 1,
                "next_node": "end",
                "error_message": stagnant_msg,
            }

        # Circuit breaker check before looping
        should_trip, trip_reason = check_circuit_breaker(state)
        if should_trip:
            print(f"    {trip_reason}")
            return {
                "green_phase_output": output,
                "coverage_achieved": coverage_achieved,
                "previous_coverage": coverage_achieved,
                "previous_passed": passed_count,
                "previous_green_failures": current_green_failures,
                "test_failure_summary": failure_summary,
                "file_counter": file_num,
                "pytest_exit_code": exit_code,
                "iteration_count": iteration_count + 1,
                "next_node": "end",
                "error_message": trip_reason,
            }

        print(f"    [N5] Iteration {iteration_count + 1}/{max_iterations} | "
              f"Tests: {passed_count}/{passed_count + failed_count} passed | "
              f"Coverage: {coverage_achieved:.1f}% (was {previous_coverage:.1f}%) | "
              f"Target: {coverage_target}%")

        log_workflow_execution(
            target_repo=repo_root,
            issue_number=state.get("issue_number", 0),
            workflow_type="testing",
            event="green_phase_failed",
            details={
                "passed": passed_count,
                "failed": failed_count,
                "errors": error_count,
                "iteration": iteration_count,
            },
        )

        # Loop back to implementation with failure feedback
        updates = {
            "green_phase_output": output,
            "coverage_achieved": coverage_achieved,
            "previous_coverage": coverage_achieved,
            "previous_passed": passed_count,
            "previous_green_failures": current_green_failures,
            "test_failure_summary": failure_summary,
            "file_counter": file_num,
            "pytest_exit_code": exit_code,
            "iteration_count": iteration_count + 1,
            "next_node": "N4_implement_code",
            "error_message": "",
            "count_plateau_strikes": plateau_strikes,
            "identity_plateau_strikes": identity_strikes,
            "freeze_tests": identity_stagnant,
        }
        _hill_climb(state, repo_root, passed_count, coverage_achieved,
                    current_green_failures, updates)
        return updates

    # Check coverage
    if coverage_achieved < coverage_target:
        # Check if we've exhausted iterations
        if iteration_count + 1 >= max_iterations:
            print(f"    [ERROR] Max iterations ({max_iterations}) reached with {coverage_achieved:.1f}% coverage")
            return {
                "green_phase_output": output,
                "coverage_achieved": coverage_achieved,
                "previous_coverage": coverage_achieved,
                "previous_passed": passed_count,
                "previous_green_failures": current_green_failures,
                "test_failure_summary": failure_summary,
                "file_counter": file_num,
                "pytest_exit_code": exit_code,
                "iteration_count": iteration_count + 1,
                "next_node": "end",
                "error_message": f"Green phase failed after {max_iterations} iterations: coverage {coverage_achieved:.1f}% < target {coverage_target}%",
            }

        # Stagnation check: one shared decision, see coverage_has_stagnated.
        previous_passed = state.get("previous_passed", -1)
        previous_green_failures = state.get("previous_green_failures", [])
        if coverage_has_stagnated(
            coverage_achieved, previous_coverage, passed_count, previous_passed,
            current_green_failures, previous_green_failures,
        ):
            stagnant_msg = (
                f"Coverage stagnant: {previous_coverage:.1f}% -> {coverage_achieved:.1f}% "
                f"(< 1% improvement). Halting to prevent token waste."
            )
            print(f"    [STAGNANT] {stagnant_msg}")
            return {
                "green_phase_output": output,
                "coverage_achieved": coverage_achieved,
                "previous_coverage": coverage_achieved,
                "previous_passed": passed_count,
                "previous_green_failures": current_green_failures,
                "test_failure_summary": failure_summary,
                "file_counter": file_num,
                "pytest_exit_code": exit_code,
                "iteration_count": iteration_count + 1,
                "next_node": "end",
                "error_message": stagnant_msg,
            }

        # Circuit breaker check before looping
        should_trip, trip_reason = check_circuit_breaker(state)
        if should_trip:
            print(f"    {trip_reason}")
            return {
                "green_phase_output": output,
                "coverage_achieved": coverage_achieved,
                "previous_coverage": coverage_achieved,
                "previous_passed": passed_count,
                "previous_green_failures": current_green_failures,
                "test_failure_summary": failure_summary,
                "file_counter": file_num,
                "pytest_exit_code": exit_code,
                "iteration_count": iteration_count + 1,
                "next_node": "end",
                "error_message": trip_reason,
            }

        print(f"    [N5] Iteration {iteration_count + 1}/{max_iterations} | "
              f"Tests: {passed_count}/{passed_count + failed_count} passed | "
              f"Coverage: {coverage_achieved:.1f}% (was {previous_coverage:.1f}%) | "
              f"Target: {coverage_target}%")

        log_workflow_execution(
            target_repo=repo_root,
            issue_number=state.get("issue_number", 0),
            workflow_type="testing",
            event="green_phase_low_coverage",
            details={
                "coverage": coverage_achieved,
                "target": coverage_target,
                "iteration": iteration_count,
            },
        )

        # Loop back to implementation for more coverage
        updates = {
            "green_phase_output": output,
            "coverage_achieved": coverage_achieved,
            "previous_coverage": coverage_achieved,
            "previous_passed": passed_count,
            "previous_green_failures": current_green_failures,
            "test_failure_summary": failure_summary,
            "file_counter": file_num,
            "pytest_exit_code": exit_code,
            "iteration_count": iteration_count + 1,
            "next_node": "N4_implement_code",
            "error_message": "",
            # All tests pass here; a count plateau is a failing-branch concept.
            "count_plateau_strikes": 0,
            "identity_plateau_strikes": 0,
            "freeze_tests": False,
        }
        _hill_climb(state, repo_root, passed_count, coverage_achieved,
                    current_green_failures, updates)
        return updates

    # Success: all tests pass and coverage meets target
    print(f"    [N5] Green phase PASSED: {passed_count} tests, {coverage_achieved:.1f}% coverage")

    # --------------------------------------------------------------------------
    # Issue #842: Full suite regression gate — run ONCE after new tests pass.
    # Catches regressions in existing 4000+ tests that the targeted test run misses.
    # --------------------------------------------------------------------------
    if not state.get("full_suite_validated", False):
        print("    [N5] Running full test suite regression check...")
        # #2048: iterations must be independent. boostgauge #2's generated
        # visual test wrote its baseline PNG on first run; the revise loop then
        # changed the renderer, and every later iteration failed RMS-diff
        # against the stale baseline forever -- "2 regressions" became "same 4
        # failing, stagnant" without the model having any way to win. Files a
        # test RUN creates are droppings, not implementation: N4 writes its
        # files before pytest starts, so anything new afterwards was made by
        # the run itself and is removed before the next iteration judges.
        droppings_before = _snapshot_untracked(repo_root)
        full_result = run_pytest([], repo_root=repo_root)
        _remove_test_run_droppings(repo_root, droppings_before)
        full_parsed = full_result["parsed"]
        full_failed = full_parsed.get("failed", 0)
        full_errors = full_parsed.get("errors", 0)
        full_passed = full_parsed.get("passed", 0)

        if full_failed > 0 or full_errors > 0:
            full_output = full_result["stdout"] + "\n" + full_result["stderr"]
            regression_summary = _build_failure_summary(full_output)
            regression_names = _extract_failed_test_names(full_output)

            # Check for stagnation: same regressions across 2 iterations → halt
            previous_regressions = state.get("full_suite_regressions", [])
            if previous_regressions and sorted(regression_names) == sorted(previous_regressions):
                # #2048: name them. "same 4 test(s)" sent the diagnosis to a
                # manual worktree + full-suite re-run; the names were in hand.
                named = ", ".join(regression_names[:4])
                if len(regression_names) > 4:
                    named += f" (and {len(regression_names) - 4} more)"
                stagnant_msg = (
                    f"Full suite regression stagnant: same {len(regression_names)} test(s) "
                    f"failing across iterations: {named}. Halting."
                )
                print(f"    [STAGNANT] {stagnant_msg}")
                return {
                    "green_phase_output": output,
                    "coverage_achieved": coverage_achieved,
                    "previous_coverage": coverage_achieved,
                    "previous_passed": passed_count,
                    "previous_green_failures": [],
                    "test_failure_summary": regression_summary,
                    "full_suite_validated": False,
                    "full_suite_regressions": regression_names,
                    "file_counter": file_num,
                    "pytest_exit_code": exit_code,
                    "iteration_count": iteration_count + 1,
                    "next_node": "end",
                    "error_message": stagnant_msg,
                }

            print(f"    [N5] Full suite: {full_failed + full_errors} regression(s) detected "
                  f"({full_passed} passed) — routing back to N4")

            log_workflow_execution(
                target_repo=repo_root,
                issue_number=state.get("issue_number", 0),
                workflow_type="testing",
                event="full_suite_regression",
                details={
                    "full_passed": full_passed,
                    "full_failed": full_failed,
                    "full_errors": full_errors,
                    "regression_names": regression_names[:10],
                },
            )

            return {
                "green_phase_output": output,
                "coverage_achieved": coverage_achieved,
                "previous_coverage": coverage_achieved,
                "previous_passed": passed_count,
                "previous_green_failures": [],
                "test_failure_summary": regression_summary,
                "full_suite_validated": False,
                "full_suite_regressions": regression_names,
                "file_counter": file_num,
                "pytest_exit_code": exit_code,
                "iteration_count": iteration_count + 1,
                "next_node": "N4_implement_code",
                "error_message": "",
            }

        print(f"    [N5] Full suite: {full_passed} tests passed — no regressions")
    # --------------------------------------------------------------------------

    # --------------------------------------------------------------------------
    # Issue #562: Skip audit gate — validate skipped tests post-run
    # --------------------------------------------------------------------------
    skipped_count = parsed.get("skipped", 0)
    skip_audit = _validate_skip_audit(output)
    if skip_audit["skip_count"] > 0:
        if skip_audit["critical_count"] > 0:
            print(f"    [SKIP-GATE] WARNING: {skip_audit['critical_count']} critical skipped test(s): "
                  f"{', '.join(skip_audit['critical_tests'])}")
        else:
            print(f"    [SKIP-GATE] {skip_audit['skip_count']} skipped test(s) (none critical)")

        log_workflow_execution(
            target_repo=repo_root,
            issue_number=state.get("issue_number", 0),
            workflow_type="testing",
            event="skip_audit",
            details={
                "skip_count": skip_audit["skip_count"],
                "critical_count": skip_audit["critical_count"],
                "critical_tests": skip_audit["critical_tests"],
                "gate_passed": skip_audit["gate_passed"],
            },
        )
    # --------------------------------------------------------------------------

    log_workflow_execution(
        target_repo=repo_root,
        issue_number=state.get("issue_number", 0),
        workflow_type="testing",
        event="green_phase_complete",
        details={
            "passed": passed_count,
            "coverage": coverage_achieved,
            "iterations": iteration_count,
            "skipped": skipped_count,
        },
    )

    # Check if E2E should be skipped
    if state.get("skip_e2e"):
        return {
            "green_phase_output": output,
            "coverage_achieved": coverage_achieved,
            "previous_coverage": coverage_achieved,
            "previous_passed": passed_count,
            "previous_green_failures": [],
            "test_failure_summary": "",
            "full_suite_validated": True,
            "full_suite_regressions": [],
            "file_counter": file_num,
            "pytest_exit_code": exit_code,
            "skip_audit": skip_audit,
            "next_node": "N7_finalize",  # Skip E2E
            "error_message": "",
        }

    return {
        "green_phase_output": output,
        "coverage_achieved": coverage_achieved,
        "previous_coverage": coverage_achieved,
        "previous_passed": passed_count,
        "previous_green_failures": [],
        "test_failure_summary": "",
        "full_suite_validated": True,
        "full_suite_regressions": [],
        "file_counter": file_num,
        "pytest_exit_code": exit_code,
        "skip_audit": skip_audit,
        "next_node": "N6_e2e_validation",
        "error_message": "",
    }


def _resolve_framework_enum(framework_config: dict) -> TestFramework | None:
    """Extract TestFramework enum from framework_config dict.

    The framework field may be a TestFramework enum or its string value
    (after serialization through LangGraph state).
    """
    fw = framework_config.get("framework")
    if isinstance(fw, TestFramework):
        return fw
    if isinstance(fw, str):
        try:
            return TestFramework(fw)
        except ValueError:
            return None
    return None


def _verify_red_non_pytest(
    state: TestingWorkflowState,
    framework_config: dict,
    framework: TestFramework,
) -> dict[str, Any]:
    """Red phase verification for non-pytest frameworks (Playwright/Jest/Vitest).

    Issue #381: Uses the runner registry to execute tests. In red phase,
    ALL tests should fail (none should pass).
    """
    test_files = state.get("test_files", [])
    repo_root_str = state.get("repo_root", "")
    repo_root = Path(repo_root_str) if repo_root_str else get_repo_root()

    if not test_files:
        print("    [GUARD] BLOCKED: No test files to run")
        return {"error_message": "GUARD: No test files generated"}

    print(f"    Running {framework.value} on {len(test_files)} test file(s)...")

    try:
        runner = get_runner(framework, str(repo_root))
    except (ValueError, EnvironmentError) as e:
        return {"error_message": f"Runner unavailable for {framework.value}: {e}"}

    result = runner.run_tests(test_paths=test_files)

    output = result["raw_output"]
    passed = result["passed"]
    failed = result["failed"]
    errors = result["errors"]
    exit_code = result["exit_code"]

    print(f"    Results: {passed} passed, {failed} failed, {errors} errors")
    print(f"    Exit code: {exit_code}")

    # Save output to audit trail
    audit_dir_str = state.get("audit_dir", "")
    audit_dir = Path(audit_dir_str) if audit_dir_str else None
    if audit_dir and audit_dir.exists():
        file_num = next_file_number(audit_dir)
        save_audit_file(audit_dir, file_num, "red-phase.txt", output)
    else:
        file_num = state.get("file_counter", 0)

    # Red phase: ALL tests must fail
    if passed > 0:
        print(f"    [GUARD] WARNING: {passed} tests passed unexpectedly!")
        return {
            "red_phase_output": output,
            "file_counter": file_num,
            "test_run_result": dict(result),
            "error_message": f"Red phase failed: {passed} tests passed unexpectedly.",
            "next_node": "END",
        }

    total_red = failed + errors
    if total_red == 0:
        print("    [GUARD] WARNING: No tests ran!")
        return {
            "red_phase_output": output,
            "file_counter": file_num,
            "test_run_result": dict(result),
            "error_message": "Red phase failed: No tests were collected/run",
            "next_node": "END",
        }

    print(f"    Red phase PASSED: {total_red} tests failed as expected ({framework.value})")

    log_workflow_execution(
        target_repo=repo_root,
        issue_number=state.get("issue_number", 0),
        workflow_type="testing",
        event="red_phase_complete",
        details={
            "failed": failed,
            "errors": errors,
            "exit_code": exit_code,
            "framework": framework.value,
        },
    )

    return {
        "red_phase_output": output,
        "file_counter": file_num,
        "test_run_result": dict(result),
        "next_node": "N4_implement_code",
        "error_message": "",
    }


def _verify_green_non_pytest(
    state: TestingWorkflowState,
    framework_config: dict,
    framework: TestFramework,
) -> dict[str, Any]:
    """Green phase verification for non-pytest frameworks (Playwright/Jest/Vitest).

    Issue #381: Uses the runner registry to execute tests. Handles both
    line-based coverage (Jest/Vitest) and scenario-based coverage (Playwright).
    Preserves stagnation detection and circuit breaker logic.
    """
    test_files = state.get("test_files", [])
    coverage_target = state.get("coverage_target", 90)
    repo_root_str = state.get("repo_root", "")
    repo_root = Path(repo_root_str) if repo_root_str else get_repo_root()
    iteration_count = state.get("iteration_count", 0)
    max_iterations = state.get("max_iterations", 5)
    total_scenarios = state.get("total_scenarios", 0)

    print(f"    Running {framework.value} with coverage target: {coverage_target}%")

    try:
        runner = get_runner(framework, str(repo_root))
    except (ValueError, EnvironmentError) as e:
        return {"error_message": f"Runner unavailable for {framework.value}: {e}"}

    result = runner.run_tests(test_paths=test_files)

    output = result["raw_output"]
    passed = result["passed"]
    failed = result["failed"]
    errors = result["errors"]
    exit_code = result["exit_code"]

    # Compute coverage based on coverage_type
    coverage_type = framework_config.get("coverage_type")
    if isinstance(coverage_type, str):
        try:
            coverage_type = CoverageType(coverage_type)
        except ValueError:
            coverage_type = CoverageType.LINE

    if coverage_type == CoverageType.SCENARIO:
        # Playwright: coverage = passed / total_scenarios
        coverage_achieved = runner.compute_scenario_coverage(result, total_scenarios) * 100.0
    else:
        # Jest/Vitest: line coverage from runner output
        coverage_achieved = result.get("coverage_percent", 0.0)

    print(f"    [N5] Results: {passed} passed, {failed} failed | "
          f"Coverage: {coverage_achieved:.1f}% | Exit: {exit_code} ({framework.value})")

    # Save output to audit trail
    audit_dir_str = state.get("audit_dir", "")
    audit_dir = Path(audit_dir_str) if audit_dir_str else None
    if audit_dir and audit_dir.exists():
        file_num = next_file_number(audit_dir)
        save_audit_file(audit_dir, file_num, "green-phase.txt", output)
    else:
        file_num = state.get("file_counter", 0)

    # Stagnation detection
    previous_coverage = state.get("previous_coverage", -1.0)
    previous_passed = state.get("previous_passed", -1)

    if failed > 0 or errors > 0:
        if iteration_count + 1 >= max_iterations:
            error_msg = (
                f"Green phase failed after {max_iterations} iterations: "
                f"{failed} tests still failing ({framework.value})"
            )
            print(f"    [ERROR] {error_msg}")
            return {
                "green_phase_output": output,
                "coverage_achieved": coverage_achieved,
                "previous_coverage": coverage_achieved,
                "previous_passed": passed,
                "file_counter": file_num,
                "test_run_result": dict(result),
                "iteration_count": iteration_count + 1,
                "next_node": "end",
                "error_message": error_msg,
            }

        # Stagnation: passed count unchanged
        if previous_passed >= 0 and passed == previous_passed:
            stagnant_msg = (
                f"Test count stagnant: {passed}/{passed + failed} passed "
                f"(unchanged from previous iteration). Halting."
            )
            print(f"    [STAGNANT] {stagnant_msg}")
            return {
                "green_phase_output": output,
                "coverage_achieved": coverage_achieved,
                "previous_coverage": coverage_achieved,
                "previous_passed": passed,
                "file_counter": file_num,
                "test_run_result": dict(result),
                "iteration_count": iteration_count + 1,
                "next_node": "end",
                "error_message": stagnant_msg,
            }

        # Circuit breaker
        should_trip, trip_reason = check_circuit_breaker(state)
        if should_trip:
            print(f"    {trip_reason}")
            return {
                "green_phase_output": output,
                "coverage_achieved": coverage_achieved,
                "previous_coverage": coverage_achieved,
                "previous_passed": passed,
                "file_counter": file_num,
                "test_run_result": dict(result),
                "iteration_count": iteration_count + 1,
                "next_node": "end",
                "error_message": trip_reason,
            }

        print(f"    [N5] Iteration {iteration_count + 1}/{max_iterations} | "
              f"Tests: {passed}/{passed + failed} passed | "
              f"Coverage: {coverage_achieved:.1f}% | Target: {coverage_target}%")

        return {
            "green_phase_output": output,
            "coverage_achieved": coverage_achieved,
            "previous_coverage": coverage_achieved,
            "previous_passed": passed,
            "file_counter": file_num,
            "test_run_result": dict(result),
            "iteration_count": iteration_count + 1,
            "next_node": "N4_implement_code",
            "error_message": "",
        }

    # All tests pass — check coverage
    if coverage_achieved < coverage_target:
        if iteration_count + 1 >= max_iterations:
            error_msg = (
                f"Green phase failed after {max_iterations} iterations: "
                f"coverage {coverage_achieved:.1f}% < target {coverage_target}%"
            )
            return {
                "green_phase_output": output,
                "coverage_achieved": coverage_achieved,
                "previous_coverage": coverage_achieved,
                "previous_passed": passed,
                "file_counter": file_num,
                "test_run_result": dict(result),
                "iteration_count": iteration_count + 1,
                "next_node": "end",
                "error_message": error_msg,
            }

        # Stagnation on coverage
        if previous_coverage >= 0 and coverage_achieved <= previous_coverage + 1.0:
            stagnant_msg = (
                f"Coverage stagnant: {previous_coverage:.1f}% -> {coverage_achieved:.1f}% "
                f"(< 1% improvement). Halting."
            )
            print(f"    [STAGNANT] {stagnant_msg}")
            return {
                "green_phase_output": output,
                "coverage_achieved": coverage_achieved,
                "previous_coverage": coverage_achieved,
                "previous_passed": passed,
                "file_counter": file_num,
                "test_run_result": dict(result),
                "iteration_count": iteration_count + 1,
                "next_node": "end",
                "error_message": stagnant_msg,
            }

        # Circuit breaker
        should_trip, trip_reason = check_circuit_breaker(state)
        if should_trip:
            print(f"    {trip_reason}")
            return {
                "green_phase_output": output,
                "coverage_achieved": coverage_achieved,
                "previous_coverage": coverage_achieved,
                "previous_passed": passed,
                "file_counter": file_num,
                "test_run_result": dict(result),
                "iteration_count": iteration_count + 1,
                "next_node": "end",
                "error_message": trip_reason,
            }

        return {
            "green_phase_output": output,
            "coverage_achieved": coverage_achieved,
            "previous_coverage": coverage_achieved,
            "previous_passed": passed,
            "file_counter": file_num,
            "test_run_result": dict(result),
            "iteration_count": iteration_count + 1,
            "next_node": "N4_implement_code",
            "error_message": "",
        }

    # Success
    print(f"    [N5] Green phase PASSED: {passed} tests, "
          f"{coverage_achieved:.1f}% coverage ({framework.value})")

    log_workflow_execution(
        target_repo=repo_root,
        issue_number=state.get("issue_number", 0),
        workflow_type="testing",
        event="green_phase_complete",
        details={
            "passed": passed,
            "coverage": coverage_achieved,
            "iterations": iteration_count,
            "framework": framework.value,
        },
    )

    if state.get("skip_e2e"):
        return {
            "green_phase_output": output,
            "coverage_achieved": coverage_achieved,
            "previous_coverage": coverage_achieved,
            "previous_passed": passed,
            "file_counter": file_num,
            "test_run_result": dict(result),
            "next_node": "N7_finalize",
            "error_message": "",
        }

    return {
        "green_phase_output": output,
        "coverage_achieved": coverage_achieved,
        "previous_coverage": coverage_achieved,
        "previous_passed": passed,
        "file_counter": file_num,
        "test_run_result": dict(result),
        "next_node": "N6_e2e_validation",
        "error_message": "",
    }


def _mock_verify_red_phase(state: TestingWorkflowState) -> dict[str, Any]:
    """Mock implementation for testing."""
    audit_dir_str = state.get("audit_dir", "")
    audit_dir = Path(audit_dir_str) if audit_dir_str else None

    mock_output = """============================= test session starts ==============================
collected 3 items

tests/test_issue_42.py::test_login_success FAILED
tests/test_issue_42.py::test_login_failure FAILED
tests/test_issue_42.py::test_input_validation FAILED

=========================== short test summary info ============================
FAILED tests/test_issue_42.py::test_login_success - AssertionError: TDD: Implementation pending
FAILED tests/test_issue_42.py::test_login_failure - AssertionError: TDD: Implementation pending
FAILED tests/test_issue_42.py::test_input_validation - AssertionError: TDD: Implementation pending
============================== 3 failed in 0.12s ===============================
"""

    if audit_dir and audit_dir.exists():
        file_num = next_file_number(audit_dir)
        save_audit_file(audit_dir, file_num, "red-phase.txt", mock_output)
    else:
        file_num = state.get("file_counter", 0)

    print("    [MOCK] Red phase: 3 tests failed as expected")

    return {
        "red_phase_output": mock_output,
        "file_counter": file_num,
        "next_node": "N4_implement_code",
        "error_message": "",
    }


def _mock_verify_green_phase(state: TestingWorkflowState) -> dict[str, Any]:
    """Mock implementation for testing."""
    audit_dir_str = state.get("audit_dir", "")
    audit_dir = Path(audit_dir_str) if audit_dir_str else None
    iteration_count = state.get("iteration_count", 0)
    coverage_target = state.get("coverage_target", 90)

    # First iteration: fail, second: pass
    if iteration_count <= 1:
        mock_output = """============================= test session starts ==============================
collected 3 items

tests/test_issue_42.py::test_login_success PASSED
tests/test_issue_42.py::test_login_failure FAILED
tests/test_issue_42.py::test_input_validation PASSED

=========================== short test summary info ============================
FAILED tests/test_issue_42.py::test_login_failure - AssertionError
============================== 1 failed, 2 passed in 0.15s =====================
"""
        coverage_achieved = 75.0
        next_node = "N4_implement_code"
    else:
        mock_output = f"""============================= test session starts ==============================
collected 3 items

tests/test_issue_42.py::test_login_success PASSED
tests/test_issue_42.py::test_login_failure PASSED
tests/test_issue_42.py::test_input_validation PASSED

---------- coverage: platform linux, python 3.11.0 ----------
Name                      Stmts   Miss  Cover
---------------------------------------------
assemblyzero/__init__.py          10      0   100%
assemblyzero/module.py            50      5    90%
---------------------------------------------
TOTAL                        60      5    92%

============================== 3 passed in 0.18s ===============================
"""
        coverage_achieved = 92.0
        next_node = "N7_finalize" if state.get("skip_e2e") else "N6_e2e_validation"

    if audit_dir and audit_dir.exists():
        file_num = next_file_number(audit_dir)
        save_audit_file(audit_dir, file_num, "green-phase.txt", mock_output)
    else:
        file_num = state.get("file_counter", 0)

    print(f"    [MOCK] Green phase: coverage {coverage_achieved}%")

    return {
        "green_phase_output": mock_output,
        "coverage_achieved": coverage_achieved,
        "file_counter": file_num,
        "iteration_count": iteration_count + 1 if next_node == "N4_implement_code" else iteration_count,
        "next_node": next_node,
        "error_message": "",
    }
