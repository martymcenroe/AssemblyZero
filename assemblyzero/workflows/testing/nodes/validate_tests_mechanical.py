"""Mechanical validation of generated tests.

Issue #335: Validates that generated tests are real executable tests,
not stubs with `assert False` placeholders.

Issue #502: Hash-based stagnation detection for scaffold loop.

This node runs after scaffold_tests and before verify_red to catch
stub tests early and route back for regeneration.
"""

import ast
import hashlib
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Literal

from assemblyzero.core import alert
from assemblyzero.workflows.testing.audit import gate_log
from assemblyzero.workflows.testing.framework_detector import TestFramework
from assemblyzero.workflows.testing.framework_ownership import (
    RunFramework,
    TestFileOwnershipError,
    owner_of,
    run_frameworks,
)
from assemblyzero.workflows.testing.runner_registry import get_runner

logger = logging.getLogger(__name__)

#: How many times the scaffolder may fail validation before the run stops
#: trying to generate its way out.
MAX_SCAFFOLD_ATTEMPTS = 3

#: #2337 defined this token, and #2331 moved it here. The orchestrator's
#: transience classifier keys off it, so a halt carrying it is not retried.
#: It lives in this module because `verify_phases` already imports from here
#: and the reverse import would be a cycle; `verify_phases` re-exports it, so
#: every existing import keeps working.
DETERMINISTIC_FAILURE = "DETERMINISTIC FAILURE"


# =============================================================================
# Stub Pattern Detection
# =============================================================================

# Patterns that indicate a stub test
STUB_PATTERNS = [
    re.compile(r'assert\s+False', re.IGNORECASE),
    re.compile(r'raise\s+NotImplementedError', re.IGNORECASE),
    re.compile(r'TDD\s*(?:RED|:)', re.IGNORECASE),
    re.compile(r'Implementation\s+pending', re.IGNORECASE),
    re.compile(r'not\s+implemented', re.IGNORECASE),
    re.compile(r'#\s*TODO:\s*implement', re.IGNORECASE),
    re.compile(r'#\s*stub', re.IGNORECASE),
]


def detect_stub_patterns(test_content: str) -> list[str]:
    """Find stub test patterns that indicate placeholder tests.

    Issue #335: Detects common stub patterns like `assert False`,
    `raise NotImplementedError`, "TDD RED", etc.

    Args:
        test_content: The generated test file content.

    Returns:
        List of error messages describing detected stub patterns.
    """
    errors = []

    lines = test_content.split('\n')
    for i, line in enumerate(lines, 1):
        for pattern in STUB_PATTERNS:
            if pattern.search(line):
                # Get a clean snippet of the line
                snippet = line.strip()[:60]
                errors.append(
                    f"Line {i}: Stub pattern detected: '{snippet}'"
                )
                break  # Only report first pattern match per line

    return errors


def count_stub_tests(test_content: str) -> tuple[int, int, list[str]]:
    """Count test functions whose BODY can never pass. (#2317)

    Returns (total_tests, stub_tests, stub_names).

    A stub here is a test whose body does nothing but fail: an unconditional
    `assert False`, a bare `raise NotImplementedError`, or nothing at all
    beyond a docstring, comments and `pass`. Such a function is not a weak
    test -- it is a test no implementation can satisfy, so a suite made
    entirely of them cannot converge no matter what the coder writes.

    Decided on the AST rather than by regex, because the line-based
    STUB_PATTERNS above cannot tell a placeholder body from a genuine test
    that merely mentions one of those strings (a test asserting on the text
    "not implemented", for instance). That imprecision is part of why the
    detection was blanket-disabled by #386 rather than made accurate.

    Text that does not parse counts (0, 0, []): there is no function to
    count, and this is a count, not the parse check. N2.5 hands the same text
    to `validate_test_structure`, which records the syntax error as a
    validation error in the same pass (ledger 0908, lines 101 and 418).
    """
    try:
        tree = ast.parse(test_content)
    except SyntaxError:
        return 0, 0, []

    total = 0
    stub_names: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue
        total += 1

        meaningful = []
        for stmt in node.body:
            # Docstrings and bare constants carry no behaviour.
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
                continue
            if isinstance(stmt, ast.Pass):
                continue
            meaningful.append(stmt)

        if not meaningful:
            stub_names.append(node.name)
            continue

        def _is_dead_end(stmt: ast.stmt) -> bool:
            if isinstance(stmt, ast.Assert):
                test = stmt.test
                return isinstance(test, ast.Constant) and not test.value
            if isinstance(stmt, ast.Raise) and stmt.exc is not None:
                exc = stmt.exc
                name = exc.func if isinstance(exc, ast.Call) else exc
                return isinstance(name, ast.Name) and name.id == "NotImplementedError"
            return False

        if all(_is_dead_end(stmt) for stmt in meaningful):
            stub_names.append(node.name)

    return total, len(stub_names), stub_names


# =============================================================================
# AST Validation
# =============================================================================


#: Calls that fail a test outright. `assert` and `pytest.raises` were the only
#: two forms this checker recognised, and a test that reaches its verdict by
#: calling `pytest.fail` was read as having no assertion at all -- which is how
#: boostgauge's shipped `test_dynamic_256_matches_baseline` was refused (#2737).
#: `unittest`'s vocabulary is here for the same reason: a `TestCase` method
#: asserts through `self.assertEqual`, never through the `assert` keyword.
EXPLICIT_FAILURE_CALLS: frozenset[str] = frozenset({"fail", "xfail"})

#: How far a call is followed out of a test body when looking for the
#: assertion. One level, per the operator's ruling of 2026-09-04: enough for a
#: shared assertion helper, and bounded so the analysis cannot wander.
ASSERTION_FOLLOW_DEPTH = 1


def _is_real_assert(node: ast.AST) -> bool:
    """An `assert` that is not a bare `assert False` (issue #386).

    The TDD scaffold deliberately writes `assert False, 'TDD RED: ...'`, so a
    failing assertion with a message counts; a bare `assert False` does not.
    """
    if not isinstance(node, ast.Assert):
        return False
    if isinstance(node.test, ast.Constant):
        return not (node.test.value is False and node.msg is None)
    return True


def _is_failure_call(node: ast.AST) -> bool:
    """A call that ends the test in a verdict: `pytest.fail`, `self.assertX`."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute):
        if func.attr in EXPLICIT_FAILURE_CALLS:
            return True
        # unittest: self.assertEqual, self.assertRaises, self.failUnless...
        if func.attr.startswith("assert") and isinstance(func.value, ast.Name):
            return True
    if isinstance(func, ast.Name) and func.id in EXPLICIT_FAILURE_CALLS:
        return True
    return False


def _is_raises_block(node: ast.AST) -> bool:
    """`with pytest.raises(...)` -- an assertion written as a context."""
    if not isinstance(node, (ast.With, ast.AsyncWith)):
        return False
    for item in node.items:
        expr = item.context_expr
        if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute):
            if expr.func.attr == "raises":
                return True
    return False


def _module_functions(tree: ast.AST) -> dict[str, ast.AST]:
    """Every function defined in this module, by the name a call would use.

    Methods are keyed by their bare name too, because a call written
    `self._assert_accepted(...)` resolves to a method and the attribute is what
    the caller sees. A duplicate name maps to the first definition; ambiguity
    here can only make the checker more permissive, never less, and a
    permissive assertion check costs a round while a strict one refuses correct
    code (#2737).
    """
    functions: dict[str, ast.AST] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.setdefault(node.name, node)
    return functions


def _called_names(func: ast.AST) -> list[str]:
    """The names of everything ``func`` calls, as a resolver would see them."""
    names: list[str] = []
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        target = node.func
        if isinstance(target, ast.Name):
            names.append(target.id)
        elif isinstance(target, ast.Attribute):
            names.append(target.attr)
    return names


#: Test-framework roots whose names are never "the code under test" (#2754).
#: A closed, enumerable set, as §28a asks of any list a decision reads: every
#: member is written here, and the stdlib half is the interpreter's own
#: `sys.stdlib_module_names` rather than a list anyone has to maintain.
FRAMEWORK_MODULE_ROOTS: frozenset[str] = frozenset({
    "pytest", "_pytest", "unittest", "mock", "hypothesis", "freezegun",
})


def _code_under_test_names(tree: ast.AST) -> set[str]:
    """Names this test file imports from the module it TARGETS (#2754).

    Answered the way a resolver would answer it, not by judgement. Three
    conditions, and the third is the one that took a red suite to find.

    Not the standard library, and not a test framework -- `sys.stdlib_module_names`
    and `FRAMEWORK_MODULE_ROOTS`.

    And imported by a DOTTED package path. That is what separates the code
    under test from a test helper, and the separation is structural rather
    than stylistic: the code under test lives in the package being built and
    is imported as `from boostgauge.telltale import Telltale`, while a helper
    sits beside the test file and is imported bare -- `from helpers import
    assert_accepted` -- or relatively. A first cut of this treated every
    first-party import as a target, and it accepted a test whose only call
    was to a `pass`-bodied helper, because the helper's name looked like
    production code.

    Erring bare-is-a-helper errs toward REFUSING, which is the safe direction
    for a gate whose job is to keep hollow suites out. A genuinely flat
    single-module package would be read as a helper and its test refused;
    nothing in the corpus imports that way, and a false refusal costs a round
    while a false acceptance ships a suite that tests nothing.

    `import boostgauge.telltale` binds the ROOT, so `boostgauge` is what a
    call site writes and what goes in the set.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            # A relative import is a sibling: a helper by position.
            if node.level:
                continue
            module = node.module or ""
            if "." not in module:
                continue
            root = module.split(".")[0]
            if root in sys.stdlib_module_names or root in FRAMEWORK_MODULE_ROOTS:
                continue
            names.update(a.asname or a.name for a in node.names)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if "." not in alias.name:
                    continue
                root = alias.name.split(".")[0]
                if root in sys.stdlib_module_names or root in FRAMEWORK_MODULE_ROOTS:
                    continue
                names.add(alias.asname or root)
    return names


def _exercises_code_under_test(
    func: ast.AST,
    targets: set[str],
    functions: dict[str, ast.AST],
    depth: int = 0,
) -> bool:
    """Whether ``func`` calls into the code under test, directly or one down.

    Operator ruling, 2026-09-04 (#2754): a test body that calls into the code
    under test and carries no `assert` is a test whose assertion is "does not
    raise" -- accepted. A body with no such call and no assertion is a stub --
    refused.

    Following one level through a same-module helper matches #2737's reading
    and is what the shipped case needs: boostgauge's
    `test_V4_equal_timestamp_is_accepted` calls `_fed(...)`, and it is `_fed`
    that constructs the `Telltale` the test is about.

    An attribute call counts when the ROOT of its value chain is a target, so
    `sk.render(...)` after `from boostgauge.skins import stingray as sk` is a
    call into the code under test. A method on a local (`t.update(...)`) is
    NOT resolved -- that needs type inference -- which is exactly why
    following the helper is load-bearing rather than a convenience.
    """
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        target = node.func
        if isinstance(target, ast.Name):
            if target.id in targets:
                return True
        elif isinstance(target, ast.Attribute):
            root = target.value
            while isinstance(root, ast.Attribute):
                root = root.value
            if isinstance(root, ast.Name) and root.id in targets:
                return True

    if depth >= ASSERTION_FOLLOW_DEPTH:
        return False

    for name in _called_names(func):
        helper = functions.get(name)
        if helper is None or helper is func:
            continue
        if _exercises_code_under_test(helper, targets, functions, depth + 1):
            return True
    return False


def _carries_an_assertion(
    func: ast.AST,
    functions: dict[str, ast.AST],
    imported_sources: dict[str, ast.AST] | None = None,
    depth: int = 0,
) -> bool:
    """Whether ``func`` asserts, in its own body or one level down.

    Operator ruling, 2026-09-04 (#2737): a test whose assertion lives in a
    helper it calls counts as having an assertion. Resolve a call to a function
    in the same module or an imported one and look there.

    The recursion is bounded by `ASSERTION_FOLLOW_DEPTH`, so the analysis
    terminates on a helper that calls itself and never wanders into the code
    under test. Following further was rejected deliberately: one level covers a
    shared assertion helper, and every level past it makes "this test asserts"
    depend on production code's contents, which is a different claim.
    """
    for node in ast.walk(func):
        if _is_real_assert(node) or _is_raises_block(node) or _is_failure_call(node):
            return True

    if depth >= ASSERTION_FOLLOW_DEPTH:
        return False

    pool = dict(functions)
    if imported_sources:
        # Same-module definitions win: a local helper shadows an import.
        for name, node in imported_sources.items():
            pool.setdefault(name, node)

    for name in _called_names(func):
        helper = pool.get(name)
        if helper is None or helper is func:
            continue
        if _carries_an_assertion(helper, functions, imported_sources, depth + 1):
            return True
    return False


def validate_test_structure(
    test_content: str,
    scenarios: list[dict],
    imported_sources: dict[str, ast.AST] | None = None,
) -> list[str]:
    """AST validation: verify imports, calls, and assertions exist.

    Issue #335: Uses Python AST to verify that tests have proper structure:
    - At least one import statement
    - Each test function has at least one real assertion
    - Assertions aren't just `assert False`

    #2737, operator ruling 2026-09-04: "has an assertion" is answered by
    reading the test body AND one level down into any function it calls, in
    this module or in an imported one. A shared assertion helper is ordinary
    and good practice in exactly the table-driven tests the pipeline is asked
    to write, and reading only the body refused code the operator shipped.

    Args:
        test_content: The generated test file content.
        scenarios: List of test scenario dicts with test_id and test_name.
        imported_sources: Functions this module imports, by the name the call
            site uses, already parsed. Supplied by callers that can reach the
            files on disk; when it is None, only same-module helpers are
            followed and an imported helper's assertion cannot be seen.

    Returns:
        List of error messages for structural issues.
    """
    errors = []

    try:
        tree = ast.parse(test_content)
    except SyntaxError as e:
        errors.append(f"Syntax error in generated tests: {e}")
        return errors

    # Check for imports
    has_import = any(
        isinstance(node, (ast.Import, ast.ImportFrom))
        for node in ast.walk(tree)
    )

    if not has_import:
        errors.append("No import statements found - tests need imports")

    functions = _module_functions(tree)
    #: #2754: what "the code under test" means for this file, computed once.
    #: A name defined in this file is a helper whatever it was imported as,
    #: so it is never a target -- a local definition shadows the import, and
    #: a `pass`-bodied local must not be read as production code.
    targets = _code_under_test_names(tree) - set(functions)

    # Check each test function
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test_'):
            if _carries_an_assertion(node, functions, imported_sources):
                continue

            # #2754, operator ruling 2026-09-04: no assertion, but it calls
            # into the code under test -- the assertion is "does not raise",
            # and boostgauge's shipped `test_V4_equal_timestamp_is_accepted`
            # says so in a trailing comment. A stub is the other case: no
            # assertion AND no call into the code under test, which is what
            # the checks below still refuse.
            if _exercises_code_under_test(node, targets, functions):
                continue

            # Check if function only has pass
            func_has_only_pass = (
                len(node.body) == 1 and
                isinstance(node.body[0], (ast.Pass, ast.Expr)) and
                (isinstance(node.body[0], ast.Pass) or
                 (isinstance(node.body[0], ast.Expr) and
                  isinstance(node.body[0].value, ast.Constant)))
            )

            if func_has_only_pass:
                errors.append(
                    f"Function '{node.name}' has no assertions - only pass/docstring"
                )
            else:
                # Check if any assert exists (even assert False)
                any_assert = any(
                    isinstance(child, ast.Assert)
                    for child in ast.walk(node)
                )
                if not any_assert:
                    errors.append(
                        f"Function '{node.name}' has no assertion the checker can "
                        f"see, in its body or one level down; assert in the body "
                        f"or call a helper that does"
                    )

    return errors


class HelperSourceUnreadable(Exception):
    """A helper file the test imports is beside it and cannot be read or
    parsed (ledger 0908, line 522). Carries the file, the imported name and
    the cause; N2.5 halts on it through `_halt_validation_cannot_run`."""

    def __init__(self, path: Path, name: str, cause: str) -> None:
        super().__init__(
            f"helper file {path}, which the tests import '{name}' from, "
            f"cannot be read or parsed: {cause}"
        )
        self.path = path
        self.name = name
        self.cause = cause


def imported_helper_sources(
    test_content: str, module_dir: Path | str
) -> dict[str, ast.AST]:
    """Functions ``test_content`` imports from files beside it, parsed.

    The "or an imported one" half of #2737's ruling. Only same-directory and
    `conftest` imports are resolved, which is where a test's shared assertion
    helpers actually live; a name imported from the package under test is
    deliberately NOT followed, because production code's `raise` is not the
    test's assertion.

    Two answers are empty by contract, not by failure. A helper matters only
    to a test function, which is all `validate_test_structure` checks, so text
    with no test function `count_stub_tests` can read has nothing to follow:
    none were written, or the text does not parse, and every caller hands
    the same text to `validate_test_structure`, which reports the syntax
    error (ledger 0908, line 499). A module with no file beside the test (an
    installed package, the code under test) is not a neighbour, so there is
    nothing to follow either.

    A neighbour that IS there and cannot be read or parsed raises
    `HelperSourceUnreadable` naming the file and the cause (ADR 0236, ledger
    0908 line 522). Dropping it quietly refused a test whose assertion lives
    in that file with a message that never named the file; the test file
    imports it, so the suite cannot run while it is broken either.
    """
    directory = Path(module_dir)
    total_tests, _, _ = count_stub_tests(test_content)
    if not total_tests:
        return {}
    # count_stub_tests read at least one test function, so the text parses.
    tree = ast.parse(test_content)

    wanted: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level >= 0:
            head = node.module.split(".")[0]
            for alias in node.names:
                wanted[alias.asname or alias.name] = head

    found: dict[str, ast.AST] = {}
    for local_name, module_head in wanted.items():
        candidate = directory / f"{module_head}.py"
        if not candidate.is_file():
            continue
        try:
            helper_tree = ast.parse(candidate.read_text(encoding="utf-8", errors="replace"))
        except (OSError, SyntaxError) as e:
            raise HelperSourceUnreadable(
                candidate, local_name, f"{type(e).__name__}: {e}",
            ) from e
        for name, node in _module_functions(helper_tree).items():
            if name == local_name:
                found[local_name] = node
    return found


def validate_scenario_coverage(
    test_content: str,
    scenarios: list[dict],
) -> list[str]:
    """Ensure all LLD scenarios have corresponding test functions.

    Issue #335: Verifies that every test scenario from the LLD
    has a corresponding test function in the generated code.

    Args:
        test_content: The generated test file content.
        scenarios: List of test scenario dicts with test_id and test_name.

    Returns:
        List of error messages for missing test functions. Text that does not
        parse adds none: every scenario would read as missing, burying the one
        real error, which `validate_test_structure` already records for the
        same text (ledger 0908, line 557).
    """
    errors = []

    # Extract function names from test content
    try:
        tree = ast.parse(test_content)
    except SyntaxError:
        return []

    test_functions = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
            test_functions.add(node.name.lower())

    # Check each scenario
    for scenario in scenarios:
        test_name = scenario.get("test_name", "").lower()
        test_id = scenario.get("test_id", "")

        if not test_name:
            continue

        # Normalize test name
        if not test_name.startswith("test_"):
            test_name = f"test_{test_name}"

        if test_name not in test_functions:
            errors.append(
                f"Missing test function for scenario {test_id}: {scenario.get('test_name')}"
            )

    return errors


# =============================================================================
# LangGraph Node
# =============================================================================


def validate_tests_mechanical_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node: Mechanical validation of generated tests.

    Issue #335: Validates generated tests to catch stubs before
    the green phase. Routes back to scaffold for regeneration if
    stubs are detected.

    Args:
        state: Workflow state with generated_tests and parsed_scenarios.

    Returns:
        State updates with validation_result and scaffold_attempts.
    """
    gate_log("[N2.5] Validating generated tests (mechanical)...")

    generated_tests = state.get("generated_tests", "")
    parsed_scenarios = state.get("parsed_scenarios", {})
    scenarios = parsed_scenarios.get("scenarios", [])
    scaffold_attempts = state.get("scaffold_attempts", 0)
    issue = state.get("issue_number")

    # Issue #381: Framework-aware validation branch. #4244: every framework
    # of the run has a scaffold, and each is validated by its own framework's
    # rules: pytest's on `generated_tests` (#789), every other framework's on
    # its files as they are on disk (#3081).
    try:
        frameworks = run_frameworks(state)
    except TestFileOwnershipError as e:
        return _halt_validation_cannot_run("run's", str(e), scaffold_attempts)
    if all(run.framework != TestFramework.PYTEST for run in frameworks):
        return _validate_non_pytest(state, frameworks, scaffold_attempts)
    javascript_errors: list[str] = []
    javascript_text = ""
    if len(frameworks) > 1:
        try:
            javascript_errors, javascript_text = _non_pytest_errors(state, frameworks)
        except _ValidatorUnavailable as e:
            return _halt_validation_cannot_run(e.label, e.cause, scaffold_attempts)

    all_errors = []

    # Issue #386 exempted `assert False, 'TDD RED: ...'` from stub detection,
    # because the TDD scaffold emits such placeholders on purpose and flagging
    # them created a scaffold -> validate -> reject -> scaffold loop.
    #
    # #2317: that exemption was total, so this node could no longer tell a few
    # placeholders among real tests from a suite that is ENTIRELY placeholders.
    # It blessed the second case as "36 real tests" on boostgauge #7, and the
    # implementation stage then spent two iterations against a suite no code
    # could satisfy.
    #
    # The distinction restored here is proportional, not a revert. Individual
    # placeholders remain acceptable -- that is #386's case and it still
    # passes. A wholly hollow suite is always NAMED, and is rejected only when
    # rejecting can actually help.
    #
    # #2331 reconsidered this condition, as that issue's acceptance asked, and
    # kept it. The routing reason IS gone: "escalate" now halts instead of
    # entering implementation with the red phase skipped, so rejecting would
    # change the destination and not merely the path.
    #
    # The condition survives on its other reason, which #2331 does not touch.
    # A scaffold of nothing but `assert False, "TDD RED: ..."` is what the TDD
    # scaffolder is SUPPOSED to emit before any implementation exists, and
    # #386 closed the reject -> scaffold -> reject loop that rejecting it
    # created. That case is wholly hollow by count, so a blanket "hollow is
    # invalid" rule reopens #386 exactly. Two tests pin it, and they are
    # right to.
    #
    # So the split stands on what regeneration can achieve. The spec ships
    # executable Section 10 functions and the scaffold ignored them: fixable,
    # reject and say so. The spec ships none: this is the best the scaffolder
    # can do, name it loudly and let the red phase judge it, which it now
    # does, because nothing skips that phase any more.
    #
    # "Loudly" was a stdout print (ledger 0908, line 676). It is now an ERROR
    # on stderr naming the issue and the placeholders, and an alert: nothing
    # stops here, so the operator hears of it from this node (ADR 0236).
    total_tests, stub_count, stub_names = count_stub_tests(generated_tests)
    hollow = total_tests > 0 and stub_count == total_tests
    spec_has_bodies = bool(
        (state.get("spec_test_suite") or {}).get("functions")
    )
    hollow_description = ""
    if hollow:
        shown = ", ".join(stub_names[:3])
        more = f" (and {stub_count - 3} more)" if stub_count > 3 else ""
        # ASCII only: this string is printed, and per #1493 a non-ASCII
        # character raises UnicodeEncodeError mid-stream on Windows cp1252.
        hollow_description = (
            f"all {total_tests} generated test(s) fail unconditionally "
            f"({shown}{more}) -- no implementation can make this suite green"
        )
        if spec_has_bodies:
            all_errors.append(
                f"{hollow_description}. The spec supplies executable Section "
                f"10 test functions that were not used; regenerate from those."
            )

    # Step 2: Validate structure with AST (imports, test functions exist)
    #
    # #2737: an assertion helper beside the test file counts. The test files
    # are on disk by now, so the directory they sit in is where an imported
    # helper is looked for; when there is no such file the checker falls back
    # to same-module helpers and says nothing, because a module with no file
    # beside the test is not a neighbour. A neighbour that is there and cannot
    # be read or parsed halts the run naming the file (ledger 0908, line 522):
    # the assertion check cannot follow into it, so it cannot run, and the
    # suite that imports it cannot run either.
    test_files_on_disk = [str(p) for p in (state.get("test_files") or [])]
    imported_sources: dict[str, ast.AST] = {}
    if test_files_on_disk:
        try:
            imported_sources = imported_helper_sources(
                generated_tests, Path(test_files_on_disk[0]).parent
            )
        except HelperSourceUnreadable as e:
            return _halt_validation_cannot_run(
                "pytest", f"issue #{issue}: {e}", scaffold_attempts,
            )
    structure_errors = validate_test_structure(
        generated_tests, scenarios, imported_sources
    )
    all_errors.extend(structure_errors)

    # Step 3: Validate scenario coverage
    coverage_errors = validate_scenario_coverage(generated_tests, scenarios)
    all_errors.extend(coverage_errors)

    # #4244: the other frameworks' scaffolds, judged by their own validators.
    all_errors.extend(javascript_errors)

    # Build validation result
    is_valid = len(all_errors) == 0

    if hollow_description and not spec_has_bodies:
        _report_hollow_scaffold(
            state, hollow_description, stub_names, proceeds=is_valid,
        )

    # #2317: `real` now excludes placeholders. It previously could not --
    # stub_count was pinned at 0, so every stub was reported as a real test
    # and the number the operator reads was the opposite of the truth.
    real_test_count = total_tests - stub_count

    validation_result = {
        "is_valid": is_valid,
        "errors": all_errors,
        "warnings": [],
        "stub_count": stub_count,
        "real_test_count": max(0, real_test_count),
    }

    if is_valid:
        # #2317: name the placeholders when there are any. A bare count of
        # "real tests" that silently included every stub is what let the
        # hollow suite through looking healthy.
        if stub_count:
            print(
                f"    Validation PASSED: {real_test_count} real tests "
                f"({stub_count} placeholder(s) among {total_tests})"
            )
        else:
            print(f"    Validation PASSED: {real_test_count} real tests")
    else:
        print(f"    Validation FAILED: {len(all_errors)} errors")
        for error in all_errors[:5]:
            print(f"      - {error}")
        if len(all_errors) > 5:
            print(f"      ... and {len(all_errors) - 5} more")

    # #2767 (operator ruling 2026-09-04): every pass through the scaffolder
    # spends budget, not only the ones that fail validation. A budget that
    # counts only failures is not a budget -- and it was the reason the
    # `N3 -> N2` reroute (#292) had no bound of its own: a regenerated suite
    # that passed validation incremented nothing, so the loop was held up
    # only by LangGraph's default recursion limit, which has no gate key and
    # no halt bundle.
    new_attempts = scaffold_attempts + 1

    # Issue #500: Pass validation errors back so scaffold node can use them
    result_dict: dict[str, Any] = {
        "validation_result": validation_result,
        "scaffold_attempts": new_attempts,
    }
    if not is_valid:
        result_dict["scaffold_validation_errors"] = all_errors
    else:
        result_dict["scaffold_validation_errors"] = []  # Clear on success

    # #2331: name the halt BEFORE the hash is overwritten. `exhausted_reason`
    # compares this attempt against the previous one, and the line below
    # replaces the previous with this one.
    #
    # #2676: the decision is computed HERE, once, and carried in
    # `scaffold_route` — the router must not recompute it, because after this
    # node returns, `previous_scaffold_hash` holds THIS attempt's hash and a
    # recompute compares the attempt against itself: always byte-identical,
    # spuriously exhausted, and the run ended silently as success
    # (run-issue384-044442 merged a PR with an assertion-free stub and no
    # code).
    #
    # #2767: consulted on the VALID path too. A suite that validates and then
    # collects nothing sends the red phase back here, and without this the
    # cap it is supposedly bounded by was never read.
    # #4244: the stagnation hash and the exhaustion check cover every
    # scaffold validated here, not the Python one alone.
    validated_text = generated_tests + javascript_text
    reason = _halt_if_exhausted(
        state, result_dict, validated_text, new_attempts, all_errors,
        is_valid=is_valid,
    )
    if reason:
        result_dict["scaffold_route"] = "escalate"
    else:
        result_dict["scaffold_route"] = "regenerate" if not is_valid else "continue"

    # Issue #502: Store hash for stagnation detection
    if validated_text:
        result_dict["previous_scaffold_hash"] = hashlib.sha256(
            validated_text.encode()
        ).hexdigest()

    return result_dict


def _report_hollow_scaffold(
    state: dict[str, Any],
    description: str,
    stub_names: list[str],
    *,
    proceeds: bool,
) -> None:
    """A suite made only of placeholders, from a spec with no test bodies.

    Ledger 0908, line 676: this was a stdout print. It is an ERROR on stderr
    naming the issue and every placeholder. When the suite otherwise passed
    and goes on to the red phase, nothing stops the run here (#386, #2331),
    so the operator is alerted from this node. When the suite was rejected
    for other errors, the rejection routes it back to the scaffolder or, out
    of attempts, to HALT, which alerts; a second alert here would repeat it.
    """
    issue = state.get("issue_number")
    names = ", ".join(stub_names)
    if proceeds:
        consequence = (
            "the spec supplies no executable test bodies, so re-scaffolding "
            "cannot improve on this; the run proceeds to the red phase "
            "(#2331), and the suite goes green only if the implementation "
            "stage rewrites these tests"
        )
    else:
        consequence = (
            "the suite is also rejected for the validation errors listed "
            "with it, and goes back to the scaffolder"
        )
    print(
        f"ERROR [N2.5] [HOLLOW SCAFFOLD] issue #{issue}: {description}. "
        f"Placeholders: {names}. Consequence: {consequence}.",
        file=sys.stderr,
    )
    if proceeds:
        alert.alert_operator(
            what="the scaffold is placeholders only",
            where=(
                "assemblyzero/workflows/testing/nodes/validate_tests_mechanical.py "
                "validate_tests_mechanical_node (testing workflow, N2.5)"
            ),
            cause=f"{description}; placeholders: {names}",
            consequence=consequence,
            repo=str(state.get("repo_root") or ""),
            issue=issue,
        )


class _ValidatorUnavailable(Exception):
    """A framework's validator cannot be built, so its scaffold cannot be
    judged (#3081). Carries the framework's label and the cause to the halt."""

    def __init__(self, label: str, cause: str) -> None:
        super().__init__(f"{label}: {cause}")
        self.label = label
        self.cause = cause


def _halt_validation_cannot_run(
    label: str, cause: str, scaffold_attempts: int,
) -> dict[str, Any]:
    """N2.5's halt when a scaffold cannot be validated at all (#3081).

    It used to return `is_valid: True` with a warning when the runner could
    not be built: a check that cannot run read as a pass (ledger 0908,
    `validate_tests_mechanical.py:811`). Routed to HALT by
    `route_after_validate`, and HALT alerts the operator.
    """
    message = (
        f"{DETERMINISTIC_FAILURE}: [N2.5] the {label} scaffold cannot be "
        f"validated: {cause}. A validation that cannot run is not a pass, so "
        f"the run stops here (ADR 0236, #3081)."
    )
    print(f"ERROR [N2.5] {message}", file=sys.stderr)
    return {
        "validation_result": {
            "is_valid": False,
            "errors": [message],
            "warnings": [],
            "stub_count": 0,
            "real_test_count": 0,
        },
        "scaffold_attempts": scaffold_attempts + 1,
        "scaffold_route": "escalate",
        "next_node": "end",
        "error_message": message,
    }


def _non_pytest_errors(
    state: dict[str, Any], frameworks: list[RunFramework],
) -> tuple[list[str], str]:
    """Every non-pytest scaffold of the run, read from disk and judged by its
    own framework's validator (#3081, #4244).

    The content judged is the file at the path, never a state key: the
    TypeScript scaffold used to return its content under a key nothing read,
    and every Playwright, Jest and Vitest scaffold was validated as an empty
    string. With several frameworks, each test file goes to the framework
    that owns it (`framework_ownership.owner_of`); pytest's files are judged
    on `generated_tests` by the caller, and a non-pytest framework with no
    file at all is an error, because N2 scaffolds every framework.

    A single-framework run whose state lists no test files is judged on
    `generated_tests` as `<generated>`, as it was: there is no file to read.

    Returns `(errors, the text judged)`. Raises `_ValidatorUnavailable`, which
    halts, when a framework's validator cannot be built, when a test file
    cannot be read, and when no framework of the run owns one: each is a
    check that cannot run, never a file passed over.
    """
    repo_root = state.get("repo_root") or "."
    root = os.path.abspath(repo_root)
    test_files = [str(f) for f in (state.get("test_files") or [])]
    multi = len(frameworks) > 1
    runners: dict[int, Any] = {}
    validated: set[int] = set()
    errors: list[str] = []
    texts: list[str] = []

    def runner_for(index: int):
        if index not in runners:
            run = frameworks[index]
            try:
                runners[index] = get_runner(
                    run.framework, repo_root,
                    working_directory=run.config.get("working_directory"),
                )
            except (ValueError, OSError) as e:
                raise _ValidatorUnavailable(run.label, f"{type(e).__name__}: {e}") from e
        return runners[index]

    if not test_files and not multi:
        generated = state.get("generated_tests", "")
        return runner_for(0).validate_test_file("<generated>", generated), generated

    def owner(path: str) -> int:
        if not multi:
            return 0
        try:
            return owner_of(path, frameworks, root)
        except TestFileOwnershipError as e:
            raise _ValidatorUnavailable("run's", str(e)) from e

    def read(index: int, path: str) -> str:
        absolute = path if os.path.isabs(path) else os.path.join(root, path)
        try:
            return Path(absolute).read_text(encoding="utf-8")
        except OSError as e:
            raise _ValidatorUnavailable(
                frameworks[index].label,
                f"test file {absolute} cannot be read: {type(e).__name__}: {e}",
            ) from e

    for path in test_files:
        index = owner(path)
        if frameworks[index].framework == TestFramework.PYTEST:
            continue
        runner = runner_for(index)
        validated.add(index)
        content = read(index, path)
        texts.append(content)
        errors.extend(runner.validate_test_file(path, content))

    for index, run in enumerate(frameworks):
        if run.framework != TestFramework.PYTEST and index not in validated:
            errors.append(
                f"no {run.label} test file to validate: every framework of the "
                f"run has a scaffold (#4244)"
            )
    return errors, "".join(texts)


def _validate_non_pytest(
    state: dict[str, Any],
    frameworks: list[RunFramework],
    scaffold_attempts: int,
) -> dict[str, Any]:
    """Validate non-pytest test files using framework-specific runner validators.

    Issue #381: Playwright/Jest/Vitest files can't be validated with Python AST.
    Instead, use the runner's validate_test_file() method which checks for
    framework-specific patterns (imports, test blocks, etc.).

    #3081: each file is read from disk (`_non_pytest_errors`), and a
    validator that cannot be built halts instead of passing.
    """
    try:
        all_errors, validated_text = _non_pytest_errors(state, frameworks)
    except _ValidatorUnavailable as e:
        return _halt_validation_cannot_run(e.label, e.cause, scaffold_attempts)

    is_valid = len(all_errors) == 0
    labels = ", ".join(run.label for run in frameworks)

    if is_valid:
        print(f"    [N2.5] {labels} validation PASSED")
    else:
        print(f"    [N2.5] {labels} validation FAILED: {len(all_errors)} errors")
        for error in all_errors[:5]:
            print(f"      - {error}")

    new_attempts = scaffold_attempts + 1  # #2767: every pass spends budget

    result: dict[str, Any] = {
        "validation_result": {
            "is_valid": is_valid,
            "errors": all_errors,
            "warnings": [],
            "stub_count": 0,
            "real_test_count": 0,
        },
        "scaffold_attempts": new_attempts,
        "scaffold_validation_errors": all_errors if not is_valid else [],  # Issue #500
    }
    # #2331: the non-pytest path escalates through the same routing, so it
    # owes the same named halt. Leaving it out would make the defect a
    # property of the framework the run happens to use.
    # #2676: and it owes the same carried route, for the same reason.
    # #2767: and the same budget, consulted on the valid path too.
    # #3081: judged on the text the validators read from disk, which is now
    # also what the stagnation hash (#502) is taken over, as on the pytest path.
    reason = _halt_if_exhausted(
        state, result, validated_text, new_attempts, all_errors,
        is_valid=is_valid,
    )
    if reason:
        result["scaffold_route"] = "escalate"
    else:
        result["scaffold_route"] = "regenerate" if not is_valid else "continue"
    if validated_text:
        result["previous_scaffold_hash"] = hashlib.sha256(
            validated_text.encode()
        ).hexdigest()
    return result


# =============================================================================
# Routing Function
# =============================================================================


def exhausted_reason(
    state: dict[str, Any], generated_tests: str, attempts: int,
    *, is_valid: bool = False,
) -> str:
    """Why mechanical generation is out of moves, or "" while it is not.

    #2331 gave this its own function because two callers need the same answer.
    `should_regenerate` decides the route from it, and the validation node
    writes the halt message from it. When the two computed it separately they
    could disagree, and a route that ends a run whose state says nothing went
    wrong is the silent degradation this issue is about.

    #2767: the threshold differs by path, and the asymmetry is deliberate.

    An INVALID suite AT the cap is definitive -- three scaffolds, none of them
    usable, and a fourth will not be different. That is `>=`, and it is the
    behaviour that shipped.

    A VALID suite at the cap is not. A run whose first two scaffolds failed
    validation and whose third finally passed has produced exactly what was
    asked for, and halting it at the moment it succeeded would make the retry
    budget punish the retry it exists to allow. The valid path therefore stops
    only once the count EXCEEDS the cap: the loop has already been round the
    allowed number of times and is asking for one more.
    """
    if generated_tests:
        current = hashlib.sha256(generated_tests.encode()).hexdigest()
        previous = state.get("previous_scaffold_hash", "")
        if previous and current == previous:
            return (
                "the scaffolder reproduced its previous output byte for byte, "
                "so regenerating again produces the same suite"
            )

    if is_valid:
        if attempts > MAX_SCAFFOLD_ATTEMPTS:
            return (
                f"the scaffolder has produced {attempts} suites, more than "
                f"the limit of {MAX_SCAFFOLD_ATTEMPTS}, and the red phase "
                f"still cannot use one"
            )
        return ""

    if attempts >= MAX_SCAFFOLD_ATTEMPTS:
        return (
            f"the scaffold failed validation {attempts} times, which is the "
            f"limit of {MAX_SCAFFOLD_ATTEMPTS}"
        )

    return ""


def _halt_if_exhausted(
    state: dict[str, Any],
    result: dict[str, Any],
    generated_tests: str,
    attempts: int,
    errors: list[str],
    *,
    is_valid: bool = False,
) -> str:
    """Name the halt in state when regeneration cannot help, per #2331.

    Before this, an unusable suite routed to N4_implement_code and skipped the
    red phase on the way, so a suite the validator had just called unusable
    reached implementation with one fewer check than a suite that passed. The
    run then burned its implementation budget against tests no code could
    satisfy. Now it stops, and says which side is wrong.

    #2676: returns the reason ("" when not exhausted) so the node can carry
    the routing decision it implies — the caller sets `scaffold_route` from
    it, and the router reads the carried route instead of recomputing against
    the by-then-overwritten hash.
    """
    reason = exhausted_reason(state, generated_tests, attempts, is_valid=is_valid)
    if not reason:
        return ""

    if is_valid:
        # #2767: the suite validated. Saying it "cannot be validated" would
        # be false in the artifact a human reads to diagnose the halt -- the
        # budget is what ran out, on a suite that passed every check this
        # node makes and still sent the red phase back here.
        result["error_message"] = (
            f"{DETERMINISTIC_FAILURE}: the scaffold budget is spent and "
            f"{reason}. The suite passed mechanical validation each time and "
            f"the red phase still could not use it, so regenerating again "
            f"asks the same question. Repair the spec's Section 10 test "
            f"functions, then resume."
        )
        result["next_node"] = "end"
        print(f"    [HALT] {result['error_message']}")
        return reason

    shown = "; ".join(errors[:3]) if errors else "no specific error was recorded"
    result["error_message"] = (
        f"{DETERMINISTIC_FAILURE}: the generated test suite cannot be "
        f"validated and {reason}. The tests are the wrong side here, not the "
        f"implementation: {shown}. Repair the spec's Section 10 test "
        f"functions, then resume."
    )
    result["next_node"] = "end"
    print(f"    [HALT] {result['error_message']}")
    return reason


class ScaffoldExhausted(RuntimeError):
    """Mechanical generation is out of moves and state names no halt (ledger
    0908, line 1043). Raised by the router, so the run stops with the reason
    instead of ending at ``end`` as if nothing failed; the entry point that
    runs the graph reports and alerts it."""


def _raise_exhausted(reason: str) -> None:
    message = (
        f"{DETERMINISTIC_FAILURE}: [N2.5] the generated test suite is out of "
        f"regenerations ({reason}), and state carries no error_message for "
        f"HALT to report, so the router stops the run here (ADR 0236). "
        f"Repair the spec's Section 10 test functions, then resume."
    )
    print(f"ERROR [N2.5] {message}", file=sys.stderr)
    raise ScaffoldExhausted(message)


def should_regenerate(state: dict[str, Any]) -> Literal["regenerate", "continue", "escalate"]:
    """Conditional edge: return routing decision based on validation.

    Issue #335: Routes the workflow based on validation results:
    - "regenerate": Validation failed, attempts remain, retry scaffold
    - "continue": Validation passed, proceed to verify_red
    - "escalate": Validation failed and regeneration is exhausted

    Issue #502: Hash-based stagnation detection. If scaffold output is
    identical to the previous attempt, escalate immediately instead of
    wasting another generation cycle.

    #2331: "escalate" no longer means "hand this to Claude". It means
    mechanical generation is out of moves, and the run halts. The condition
    lives in `exhausted_reason` so this function and the node that writes the
    halt message cannot disagree about when it holds.

    "escalate" is returned only when state carries the node's error_message,
    which sends the run to HALT. Out of moves with no recorded reason (the
    legacy fallback, or a carried route whose reason is gone) raises
    `ScaffoldExhausted` instead: `route_after_validate` maps "escalate" to
    `end`, and ending there read as success (ledger 0908, line 1043).

    Args:
        state: Workflow state with validation_result and scaffold_attempts.

    Returns:
        Routing decision string.
    """
    # #2676: the node computed the decision BEFORE it overwrote
    # `previous_scaffold_hash` with this attempt's own hash; recomputing here
    # compares the attempt against itself — always byte-identical — and a
    # first-attempt failure spuriously escalated to a silent end that read as
    # success downstream (run-issue384-044442 merged a PR with an
    # assertion-free stub and no code). Read the carried route.
    carried = state.get("scaffold_route", "")
    if carried in ("continue", "regenerate", "escalate"):
        if carried == "escalate":
            if not (state.get("error_message") or "").strip():
                _raise_exhausted(
                    "the validation node's carried route is escalate and "
                    "state records no reason"
                )
            print("    [EXHAUSTED] per the validation node's carried route; "
                  "the halt is named in error_message")
        elif carried == "regenerate":
            attempts = state.get("scaffold_attempts", 0)
            print(f"    [REGENERATE] Attempt {attempts}/{MAX_SCAFFOLD_ATTEMPTS}, "
                  f"returning to scaffold")
        return carried  # type: ignore[return-value]

    # Fallback for resumed state that predates the carried key. This path
    # keeps the pre-#2676 behaviour, hash-timing wart included — it exists
    # only so an in-flight resume does not crash, and the first fresh pass
    # through the node replaces it.
    validation_result = state.get("validation_result", {})
    is_valid = validation_result.get("is_valid", False)

    if is_valid:
        return "continue"

    reason = exhausted_reason(
        state,
        state.get("generated_tests", ""),
        state.get("scaffold_attempts", 0),
    )
    if reason:
        if not (state.get("error_message") or "").strip():
            # Ledger 0908, line 1043: "escalate" with no error_message
            # routed to `end`, which ended the run as if nothing failed. A
            # router cannot write the reason into state, so it raises it.
            _raise_exhausted(reason)
        print(f"    [EXHAUSTED] {reason}")
        return "escalate"

    attempts = state.get("scaffold_attempts", 0)
    print(f"    [REGENERATE] Attempt {attempts}/{MAX_SCAFFOLD_ATTEMPTS}, returning to scaffold")
    return "regenerate"
