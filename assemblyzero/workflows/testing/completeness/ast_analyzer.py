"""Layer 1 AST-based analysis functions for implementation completeness.

Issue #147: Implementation Completeness Gate (Anti-Stub Detection)

Provides deterministic, fast AST-based checks that detect semantically
incomplete implementations:
- Dead CLI flags (argparse add_argument with no usage)
- Empty conditional branches (if/elif/else with only pass/return None)
- Docstring-only functions (functions with docstring + pass/return None)
- Trivial assertions in tests (sole assertion is 'is not None' or similar)
- Unused imports (imports not referenced in function bodies)

These checks form Layer 1 of the two-layer completeness gate. Layer 2
(Gemini semantic review) only runs if Layer 1 passes, for cost control.
"""

from __future__ import annotations

import ast
import logging
import time
from enum import Enum
from pathlib import Path
from typing import Literal, TypedDict

logger = logging.getLogger(__name__)


# =============================================================================
# Data Structures
# =============================================================================


class CompletenessCategory(Enum):
    """Categories of completeness issues for type safety."""

    DEAD_CLI_FLAG = "dead_cli_flag"
    EMPTY_BRANCH = "empty_branch"
    DOCSTRING_ONLY = "docstring_only"
    TRIVIAL_ASSERTION = "trivial_assertion"
    UNUSED_IMPORT = "unused_import"


class CompletenessIssue(TypedDict):
    """Single completeness issue detected by analysis."""

    category: CompletenessCategory
    file_path: str
    line_number: int
    description: str
    severity: Literal["ERROR", "WARNING"]


class CompletenessResult(TypedDict):
    """Result of completeness analysis."""

    verdict: Literal["PASS", "WARN", "BLOCK"]
    issues: list[CompletenessIssue]
    ast_analysis_ms: int
    gemini_review_ms: int | None


# =============================================================================
# Helper Functions
# =============================================================================


def _is_trivial_body(body: list[ast.stmt]) -> bool:
    """Check if a function/branch body is trivial (pass, return None, or ellipsis).

    A body is trivial if it contains only:
    - A docstring (string constant expression)
    - pass statements
    - return None / bare return statements
    - Ellipsis (...)

    Args:
        body: List of AST statement nodes.

    Returns:
        True if the body is trivial.
    """
    for stmt in body:
        # Skip docstrings (string constant expressions)
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
            if isinstance(stmt.value.value, str):
                continue
            # Ellipsis literal
            if stmt.value.value is ...:
                continue

        # pass statement
        if isinstance(stmt, ast.Pass):
            continue

        # return None or bare return
        if isinstance(stmt, ast.Return):
            if stmt.value is None:
                continue
            if isinstance(stmt.value, ast.Constant) and stmt.value.value is None:
                continue

        # If we get here, the statement is non-trivial
        return False

    return True


def _has_docstring(body: list[ast.stmt]) -> bool:
    """Check if a function body starts with a docstring.

    Args:
        body: List of AST statement nodes.

    Returns:
        True if the first statement is a string constant (docstring).
    """
    if not body:
        return False
    first = body[0]
    return (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    )


def _collect_name_references(node: ast.AST) -> set[str]:
    """Collect all Name references within an AST subtree.

    Args:
        node: AST node to walk.

    Returns:
        Set of referenced name strings.
    """
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.add(child.id)
        elif isinstance(child, ast.Attribute):
            # Collect the root name of attribute chains (e.g., os.path -> os)
            attr_node = child
            while isinstance(attr_node, ast.Attribute):
                attr_node = attr_node.value
            if isinstance(attr_node, ast.Name):
                names.add(attr_node.id)
    return names


def _extract_argparse_flag_names(call_node: ast.Call) -> list[str]:
    """Extract flag names from an argparse add_argument call.

    Handles patterns like:
    - parser.add_argument('--foo')
    - parser.add_argument('-f', '--foo')
    - parser.add_argument('positional')

    Args:
        call_node: AST Call node for add_argument.

    Returns:
        List of flag/argument names (without -- prefix), or empty if not parseable.
    """
    names = []
    for arg in call_node.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            flag = arg.value.lstrip("-").replace("-", "_")
            if flag:
                names.append(flag)
    # Also check 'dest' keyword
    for kw in call_node.keywords:
        if kw.arg == "dest" and isinstance(kw.value, ast.Constant):
            if isinstance(kw.value.value, str):
                return [kw.value.value]
    return names


# =============================================================================
# Analysis Functions
# =============================================================================


def analyze_dead_cli_flags(
    source_code: str, file_path: str
) -> list[CompletenessIssue]:
    """Detect argparse add_argument calls with no corresponding usage.

    Issue #147, Requirement 2: Detects dead CLI flags where argparse
    arguments are defined but never referenced in the rest of the code.

    Args:
        source_code: Python source code to analyze.
        file_path: Path to the source file (for issue reporting).

    Returns:
        List of CompletenessIssue for each unused argparse argument.
    """
    issues: list[CompletenessIssue] = []

    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return issues

    # Phase 1: Find all add_argument calls and their flag names
    declared_flags: list[tuple[str, int]] = []  # (flag_name, line_number)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        # Match pattern: *.add_argument(...)
        if isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument":
            flag_names = _extract_argparse_flag_names(node)
            for flag_name in flag_names:
                declared_flags.append((flag_name, node.lineno))

    if not declared_flags:
        return issues

    # Phase 2: Collect all name/attribute references in function bodies
    # (excluding the add_argument calls themselves)
    all_references: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body_refs = _collect_name_references(node)
            all_references.update(body_refs)
        # Also check module-level attribute access (e.g., args.foo)
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name):
                all_references.add(node.attr)

    # Also scan raw source for string references to flag names
    # (handles cases like getattr(args, 'flag_name'))
    source_lower = source_code.lower()

    for flag_name, line_no in declared_flags:
        # Check if flag name appears as an attribute access or reference
        # beyond the add_argument declaration itself
        flag_referenced = False

        # Check attribute references (args.flag_name)
        if flag_name in all_references:
            flag_referenced = True

        # Check string references (getattr(args, 'flag_name'))
        if not flag_referenced:
            # Count occurrences - if more than just the declaration, it's used
            occurrences = source_lower.count(flag_name.lower())
            if occurrences > 1:
                flag_referenced = True

        if not flag_referenced:
            issues.append(
                CompletenessIssue(
                    category=CompletenessCategory.DEAD_CLI_FLAG,
                    file_path=file_path,
                    line_number=line_no,
                    description=(
                        f"CLI flag '{flag_name}' is defined via add_argument "
                        f"but never referenced in code"
                    ),
                    severity="ERROR",
                )
            )

    return issues


def analyze_empty_branches(
    source_code: str, file_path: str
) -> list[CompletenessIssue]:
    """Detect if/elif/else branches with only pass, return None, or trivial bodies.

    Issue #147, Requirement 3: Detects conditional branches that contain
    only trivial statements, indicating unfinished implementation.

    Args:
        source_code: Python source code to analyze.
        file_path: Path to the source file (for issue reporting).

    Returns:
        List of CompletenessIssue for each empty branch.
    """
    issues: list[CompletenessIssue] = []

    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return issues

    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue

        # Check the if body
        if _is_trivial_body(node.body):
            issues.append(
                CompletenessIssue(
                    category=CompletenessCategory.EMPTY_BRANCH,
                    file_path=file_path,
                    line_number=node.lineno,
                    description=(
                        f"Empty 'if' branch at line {node.lineno} — body contains "
                        f"only pass/return None"
                    ),
                    severity="WARNING",
                )
            )

        # Check elif/else branches (stored in node.orelse)
        if node.orelse:
            # If orelse is a single If node, it's an elif — we'll catch it
            # when we walk to that If node. Only check non-If orelse (else blocks).
            if not (len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If)):
                if _is_trivial_body(node.orelse):
                    # else block line number: use the first statement in orelse
                    else_line = node.orelse[0].lineno if node.orelse else node.lineno
                    issues.append(
                        CompletenessIssue(
                            category=CompletenessCategory.EMPTY_BRANCH,
                            file_path=file_path,
                            line_number=else_line,
                            description=(
                                f"Empty 'else' branch at line {else_line} — body "
                                f"contains only pass/return None"
                            ),
                            severity="WARNING",
                        )
                    )

    return issues


def _has_abstractmethod_decorator(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Check if a function has the @abstractmethod decorator.

    Handles both bare ``@abstractmethod`` and qualified ``@abc.abstractmethod``.

    Args:
        node: AST function definition node.

    Returns:
        True if the function is decorated with @abstractmethod.
    """
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Name) and decorator.id == "abstractmethod":
            return True
        if isinstance(decorator, ast.Attribute) and decorator.attr == "abstractmethod":
            return True
    return False


def analyze_docstring_only_functions(
    source_code: str, file_path: str
) -> list[CompletenessIssue]:
    """Detect functions with docstring + pass/return None only.

    Issue #147, Requirement 4: Detects functions that have a docstring
    but no real implementation — just pass, return None, or ellipsis.
    Issue #477: Skip @abstractmethod functions (trivial body is intentional).

    Args:
        source_code: Python source code to analyze.
        file_path: Path to the source file (for issue reporting).

    Returns:
        List of CompletenessIssue for each docstring-only function.
    """
    issues: list[CompletenessIssue] = []

    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return issues

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        # Skip test functions — they're checked by analyze_trivial_assertions
        if node.name.startswith("test_"):
            continue

        # Skip dunder methods that legitimately have trivial bodies
        # (e.g., __init__ with just pass in abstract classes)
        if node.name.startswith("__") and node.name.endswith("__"):
            continue

        # Issue #477: Skip @abstractmethod — trivial body is intentional
        if _has_abstractmethod_decorator(node):
            continue

        # Must have a docstring to qualify as "docstring-only"
        if not _has_docstring(node.body):
            continue

        # Check if body is trivial (docstring + pass/return None)
        if _is_trivial_body(node.body):
            issues.append(
                CompletenessIssue(
                    category=CompletenessCategory.DOCSTRING_ONLY,
                    file_path=file_path,
                    line_number=node.lineno,
                    description=(
                        f"Function '{node.name}' at line {node.lineno} has a "
                        f"docstring but no real implementation (only pass/return None)"
                    ),
                    severity="ERROR",
                )
            )

    return issues


def analyze_trivial_assertions(
    source_code: str, file_path: str
) -> list[CompletenessIssue]:
    """Detect test functions where sole assertion is 'is not None' or similar.

    Issue #147, Requirement 5: Detects test functions that technically
    pass but have assertions so trivial they verify nothing meaningful.

    Trivial assertion patterns:
    - assert x is not None
    - assert result is not None
    - assert True
    - assert 1

    Args:
        source_code: Python source code to analyze.
        file_path: Path to the source file (for issue reporting).

    Returns:
        List of CompletenessIssue for each test with trivial assertions.
    """
    issues: list[CompletenessIssue] = []

    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return issues

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        # Only check test functions
        if not node.name.startswith("test_"):
            continue

        # Collect all assertions in this function
        assertions: list[ast.Assert] = []
        has_pytest_raises = False

        for child in ast.walk(node):
            if isinstance(child, ast.Assert):
                assertions.append(child)
            # pytest.raises counts as a real assertion
            if isinstance(child, ast.With):
                for item in child.items:
                    if isinstance(item.context_expr, ast.Call):
                        call = item.context_expr
                        if isinstance(call.func, ast.Attribute):
                            if call.func.attr == "raises":
                                has_pytest_raises = True

        if has_pytest_raises:
            continue

        if not assertions:
            continue

        # Check if ALL assertions are trivial
        all_trivial = True
        for assertion in assertions:
            if not _is_trivial_assertion(assertion):
                all_trivial = False
                break

        if all_trivial:
            issues.append(
                CompletenessIssue(
                    category=CompletenessCategory.TRIVIAL_ASSERTION,
                    file_path=file_path,
                    line_number=node.lineno,
                    description=(
                        f"Test '{node.name}' at line {node.lineno} has only "
                        f"trivial assertions (e.g., 'is not None', 'assert True')"
                    ),
                    severity="WARNING",
                )
            )

    return issues


def _is_trivial_assertion(assertion: ast.Assert) -> bool:
    """Check if an assertion is trivial.

    Trivial patterns:
    - assert True
    - assert <constant truthy>
    - assert x is not None
    - assert result is not None

    Args:
        assertion: AST Assert node to check.

    Returns:
        True if the assertion is trivial.
    """
    test = assertion.test

    # assert True / assert 1 / assert "string"
    if isinstance(test, ast.Constant):
        return bool(test.value)  # Only trivial if the constant is truthy

    # assert x is not None  ->  Compare(left=Name, ops=[IsNot], comparators=[Constant(None)])
    if isinstance(test, ast.Compare):
        if len(test.ops) == 1 and len(test.comparators) == 1:
            op = test.ops[0]
            comparator = test.comparators[0]
            if isinstance(op, ast.IsNot) and isinstance(comparator, ast.Constant):
                if comparator.value is None:
                    return True

    # assert not None  ->  UnaryOp(op=Not, operand=Constant(None))
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        if isinstance(test.operand, ast.Constant) and test.operand.value is None:
            return True

    return False


def analyze_unused_imports(
    source_code: str, file_path: str
) -> list[CompletenessIssue]:
    """Detect imports with no usage in function bodies.

    Issue #147, Requirement 6: Detects import statements where the
    imported name is never referenced in the module, indicating
    incomplete implementation that imported dependencies but never
    used them.

    Args:
        source_code: Python source code to analyze.
        file_path: Path to the source file (for issue reporting).

    Returns:
        List of CompletenessIssue for each unused import.
    """
    issues: list[CompletenessIssue] = []

    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return issues

    # Phase 1: Collect all imported names and their line numbers
    imported_names: list[tuple[str, int]] = []  # (name, line_number)

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name
                # For dotted imports (import os.path), use the first component
                name = name.split(".")[0]
                imported_names.append((name, node.lineno))

        elif isinstance(node, ast.ImportFrom):
            # Skip __future__ imports
            if node.module and node.module == "__future__":
                continue
            # Skip wildcard imports
            if node.names and any(alias.name == "*" for alias in node.names):
                continue
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name
                imported_names.append((name, node.lineno))

    if not imported_names:
        return issues

    # Phase 2: Collect all name references in the module (excluding import statements)
    all_references: set[str] = set()

    for node in ast.walk(tree):
        # Skip import nodes themselves
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue

        if isinstance(node, ast.Name):
            all_references.add(node.id)
        elif isinstance(node, ast.Attribute):
            # Collect root name of attribute chains
            attr_node = node
            while isinstance(attr_node, ast.Attribute):
                attr_node = attr_node.value
            if isinstance(attr_node, ast.Name):
                all_references.add(attr_node.id)

    # Also check decorators and type annotations as string references
    # (handles TYPE_CHECKING imports used only in annotations)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            # String annotations may reference imported names
            for imp_name, _ in imported_names:
                if imp_name in node.value:
                    all_references.add(imp_name)

    # Phase 3: Find unused imports
    for imp_name, line_no in imported_names:
        if imp_name not in all_references:
            issues.append(
                CompletenessIssue(
                    category=CompletenessCategory.UNUSED_IMPORT,
                    file_path=file_path,
                    line_number=line_no,
                    description=(
                        f"Import '{imp_name}' at line {line_no} is never used "
                        f"in the module"
                    ),
                    severity="WARNING",
                )
            )

    return issues


# =============================================================================
# Aggregate Analysis
# =============================================================================


def run_ast_analysis(
    files: list[Path],
    max_file_size_bytes: int = 1_000_000,
) -> CompletenessResult:
    """Run all AST checks on provided files.

    Issue #147: Orchestrates all Layer 1 AST-based checks across a set
    of implementation files. Skips files exceeding max_file_size_bytes
    to prevent memory spikes on large generated files.

    Files whose names start with 'test_' are analyzed for trivial
    assertions. All other files are analyzed for dead CLI flags, empty
    branches, docstring-only functions, and unused imports.

    Args:
        files: List of Python file paths to analyze.
        max_file_size_bytes: Skip files larger than this (default 1MB).

    Returns:
        CompletenessResult with verdict, issues, and timing.
    """
    start_ms = time.monotonic_ns() // 1_000_000
    all_issues: list[CompletenessIssue] = []

    for file_path in files:
        # Skip non-Python files
        if file_path.suffix != ".py":
            continue

        # Skip files exceeding size limit
        try:
            file_size = file_path.stat().st_size
        except OSError as e:
            logger.warning("Cannot stat file %s: %s", file_path, e)
            continue

        if file_size > max_file_size_bytes:
            logger.warning(
                "Skipping file %s (%d bytes) — exceeds max_file_size_bytes (%d)",
                file_path,
                file_size,
                max_file_size_bytes,
            )
            continue

        # Read source code
        try:
            source_code = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            logger.warning("Cannot read file %s: %s", file_path, e)
            continue

        # Skip empty files
        if not source_code.strip():
            continue

        # Verify it parses before running checks
        try:
            ast.parse(source_code)
        except SyntaxError as e:
            logger.warning("Syntax error in %s: %s — skipping AST analysis", file_path, e)
            continue

        file_str = str(file_path)
        is_test_file = file_path.name.startswith("test_")

        if is_test_file:
            # Test files: check for trivial assertions
            all_issues.extend(analyze_trivial_assertions(source_code, file_str))
        else:
            # Implementation files: check for all other patterns
            all_issues.extend(analyze_dead_cli_flags(source_code, file_str))
            all_issues.extend(analyze_empty_branches(source_code, file_str))
            all_issues.extend(analyze_docstring_only_functions(source_code, file_str))
            all_issues.extend(analyze_unused_imports(source_code, file_str))

    end_ms = time.monotonic_ns() // 1_000_000
    elapsed_ms = end_ms - start_ms

    # Determine verdict based on issues
    verdict = _determine_verdict(all_issues)

    return CompletenessResult(
        verdict=verdict,
        issues=all_issues,
        ast_analysis_ms=elapsed_ms,
        gemini_review_ms=None,
    )


def _determine_verdict(
    issues: list[CompletenessIssue],
) -> Literal["PASS", "WARN", "BLOCK"]:
    """Determine the overall verdict from a list of issues.

    - BLOCK: Any ERROR-severity issue exists
    - WARN: Only WARNING-severity issues exist
    - PASS: No issues at all

    Args:
        issues: List of completeness issues.

    Returns:
        Verdict string.
    """
    if not issues:
        return "PASS"

    has_error = any(issue["severity"] == "ERROR" for issue in issues)
    if has_error:
        return "BLOCK"

    return "WARN"