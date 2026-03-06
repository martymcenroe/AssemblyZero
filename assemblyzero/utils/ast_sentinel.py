"""AST-based Import Sentinel for detecting lingering symbols.

Issue #600: Detect missing imports and undefined variables before execution
using static AST analysis.

Provides:
- SymbolSentinel: AST NodeVisitor that tracks scopes and detects undefined names.
- SentinelError: Structured error for undefined symbol usage.
- analyze_source: Analyze a source string for undefined symbols.
- analyze_file: Analyze a file path for undefined symbols.
"""

from __future__ import annotations

import ast
import builtins
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

# Built-in names that are always available.
BUILTIN_NAMES: frozenset[str] = frozenset(dir(builtins))

# Common implicit globals that don't require imports.
IMPLICIT_GLOBALS: frozenset[str] = frozenset({
    "__name__",
    "__file__",
    "__doc__",
    "__package__",
    "__spec__",
    "__loader__",
    "__builtins__",
    "__all__",
    "__annotations__",
    "__cached__",
    "__path__",
    "TYPE_CHECKING",
})

# Sentinel disable comment pattern.
DISABLE_COMMENT = "sentinel: disable-line"


@dataclass
class SentinelError:
    """A single undefined-symbol error found by the sentinel."""

    name: str
    line: int
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass
class SentinelResult:
    """Result of analyzing a source file."""

    errors: list[SentinelError] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def format_errors(self) -> str:
        """Format all errors for stderr output."""
        return "\n".join(str(e) for e in self.errors)


class SymbolSentinel(ast.NodeVisitor):
    """AST visitor that tracks symbol definitions across scopes.

    Maintains a scope stack to detect uses of undefined names.
    Handles imports, function/class defs, comprehensions, walrus
    operators, global/nonlocal statements, and TYPE_CHECKING blocks.
    """

    def __init__(self, source_lines: list[str] | None = None) -> None:
        # Stack of scopes; each scope is a set of defined names.
        self.scope_stack: list[set[str]] = [set()]
        self.errors: list[SentinelError] = []
        self.source_lines: list[str] = source_lines or []
        # Track names declared global/nonlocal in current scope.
        self._global_names: set[str] = set()
        self._nonlocal_names: set[str] = set()
        # Track if we're inside a TYPE_CHECKING block.
        self._in_type_checking: bool = False

    # -- Scope helpers --

    def _current_scope(self) -> set[str]:
        return self.scope_stack[-1]

    def _define(self, name: str) -> None:
        """Register a name in the current scope."""
        self._current_scope().add(name)

    def _is_defined(self, name: str) -> bool:
        """Check if a name is defined in any enclosing scope, builtins, or implicit globals."""
        if name in BUILTIN_NAMES or name in IMPLICIT_GLOBALS:
            return True
        for scope in reversed(self.scope_stack):
            if name in scope:
                return True
        return False

    def _push_scope(self) -> None:
        self.scope_stack.append(set())

    def _pop_scope(self) -> None:
        if len(self.scope_stack) > 1:
            self.scope_stack.pop()

    def _is_disabled(self, line: int) -> bool:
        """Check if a line has a sentinel: disable-line comment."""
        if not self.source_lines or line < 1 or line > len(self.source_lines):
            return False
        return DISABLE_COMMENT in self.source_lines[line - 1]

    # -- Import visitors --

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name == "*":
                self.errors.append(SentinelError(
                    name="*",
                    line=node.lineno,
                    message=f"Star imports are not allowed (line {node.lineno}).",
                ))
                continue
            # Use alias if provided, otherwise top-level module name.
            name = alias.asname if alias.asname else alias.name.split(".")[0]
            self._define(name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.names and any(alias.name == "*" for alias in node.names):
            self.errors.append(SentinelError(
                name="*",
                line=node.lineno,
                message=f"Star imports are not allowed (line {node.lineno}).",
            ))
            return
        for alias in node.names:
            name = alias.asname if alias.asname else alias.name
            self._define(name)
        self.generic_visit(node)

    # -- Definition visitors --

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        # The function name is defined in the enclosing scope.
        self._define(node.name)
        self._visit_function_body(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        print('DEBUG: VISITING ASYNC FN')
        self._define(node.name)
        self._visit_function_body(node)

    def _visit_function_body(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """Push scope, register args, visit body, pop scope."""
        # Visit decorator list in current scope first.
        for decorator in node.decorator_list:
            self.visit(decorator)

        # Visit default argument values in current scope.
        for default in node.args.defaults:
            self.visit(default)
        for default in node.args.kw_defaults:
            if default is not None:
                self.visit(default)
        # Visit annotations in current scope.
        for arg in node.args.args + node.args.posonlyargs + node.args.kwonlyargs:
            if arg.annotation:
                self.visit(arg.annotation)
        if node.args.vararg and node.args.vararg.annotation:
            self.visit(node.args.vararg.annotation)
        if node.args.kwarg and node.args.kwarg.annotation:
            self.visit(node.args.kwarg.annotation)
        if node.returns:
            self.visit(node.returns)

        saved_globals = self._global_names
        saved_nonlocals = self._nonlocal_names
        self._global_names = set()
        self._nonlocal_names = set()

        self._push_scope()

        # Register all argument names.
        for arg in node.args.args + node.args.posonlyargs + node.args.kwonlyargs:
            self._define(arg.arg)
        if node.args.vararg:
            self._define(node.args.vararg.arg)
        if node.args.kwarg:
            self._define(node.args.kwarg.arg)

        # Visit body.
        for child in node.body:
            self.visit(child)

        self._pop_scope()
        self._global_names = saved_globals
        self._nonlocal_names = saved_nonlocals

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._define(node.name)
        # Visit decorators and bases in current scope.
        for decorator in node.decorator_list:
            self.visit(decorator)
        for base in node.bases:
            self.visit(base)
        for keyword in node.keywords:
            self.visit(keyword.value)

        self._push_scope()
        for child in node.body:
            self.visit(child)
        self._pop_scope()

    # -- Comprehension visitors --

    def _visit_comprehension(self, node: ast.ListComp | ast.SetComp | ast.GeneratorExp | ast.DictComp) -> None:
        """Handle comprehensions with their own scope."""
        self._push_scope()

        generators = node.generators
        for i, generator in enumerate(generators):
            # The first iterable is evaluated in the outer scope.
            if i == 0:
                self._pop_scope()
                self.visit(generator.iter)
                self._push_scope()
            else:
                self.visit(generator.iter)

            # Target defines in comprehension scope.
            self._visit_target(generator.target)

            for if_clause in generator.ifs:
                self.visit(if_clause)

        # Visit the element expression(s).
        if isinstance(node, ast.DictComp):
            self.visit(node.key)
            self.visit(node.value)
        else:
            self.visit(node.elt)

        self._pop_scope()

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._visit_comprehension(node)

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self._visit_comprehension(node)

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._visit_comprehension(node)

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._visit_comprehension(node)

    # -- Assignment visitors --

    def _visit_target(self, target: ast.AST) -> None:
        """Register names from assignment targets (handles tuples, stars, etc.)."""
        if isinstance(target, ast.Name):
            self._define(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for elt in target.elts:
                self._visit_target(elt)
        elif isinstance(target, ast.Starred):
            self._visit_target(target.value)

    def visit_Assign(self, node: ast.Assign) -> None:
        # Visit value first (RHS).
        self.visit(node.value)
        # Then define targets.
        for target in node.targets:
            self._visit_target(target)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value:
            self.visit(node.value)
        self.visit(node.annotation)
        if node.target:
            self._visit_target(node.target)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self.visit(node.value)
        self.visit(node.target)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        """Walrus operator := defines in enclosing scope."""
        self.visit(node.value)
        self._define(node.target.id)

    # -- Global/Nonlocal --

    def visit_Global(self, node: ast.Global) -> None:
        for name in node.names:
            self._global_names.add(name)
            self._define(name)
            # Also define in module scope.
            self.scope_stack[0].add(name)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        for name in node.names:
            self._nonlocal_names.add(name)
            self._define(name)

    # -- For loops --

    def visit_For(self, node: ast.For) -> None:
        self.visit(node.iter)
        self._visit_target(node.target)
        for child in node.body:
            self.visit(child)
        for child in node.orelse:
            self.visit(child)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self.visit(node.iter)
        self._visit_target(node.target)
        for child in node.body:
            self.visit(child)
        for child in node.orelse:
            self.visit(child)

    # -- With statement --

    def visit_With(self, node: ast.With) -> None:
        for item in node.items:
            self.visit(item.context_expr)
            if item.optional_vars:
                self._visit_target(item.optional_vars)
        for child in node.body:
            self.visit(child)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        for item in node.items:
            self.visit(item.context_expr)
            if item.optional_vars:
                self._visit_target(item.optional_vars)
        for child in node.body:
            self.visit(child)

    # -- Exception handling --

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type:
            self.visit(node.type)
        if node.name:
            self._define(node.name)
        for child in node.body:
            self.visit(child)

    # -- TYPE_CHECKING support --

    def visit_If(self, node: ast.If) -> None:
        """Handle if TYPE_CHECKING blocks."""
        is_type_checking = self._is_type_checking_guard(node.test)

        if is_type_checking:
            old = self._in_type_checking
            self._in_type_checking = True
            for child in node.body:
                self.visit(child)
            self._in_type_checking = old
        else:
            self.visit(node.test)
            for child in node.body:
                self.visit(child)

        for child in node.orelse:
            self.visit(child)

    def _is_type_checking_guard(self, test: ast.AST) -> bool:
        """Check if a test node is `TYPE_CHECKING`."""
        if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
            return True
        if isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING":
            return True
        return False

    # -- Name usage (the core check) --

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Store):
            self._define(node.id)
            return
        if isinstance(node.ctx, ast.Del):
            return

        # ast.Load — check if defined.
        if not self._is_defined(node.id):
            if not self._is_disabled(node.lineno):
                self.errors.append(SentinelError(
                    name=node.id,
                    line=node.lineno,
                    message=f"Symbol '{node.id}' used on line {node.lineno} but not imported.",
                ))

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Visit attribute access — only check the root object."""
        self.visit(node.value)

    # -- Match statement (Python 3.10+) --

    def visit_Match(self, node: ast.Match) -> None:
        self.visit(node.subject)
        for case in node.cases:
            self._push_scope()
            if case.pattern:
                self._visit_pattern(case.pattern)
            if case.guard:
                self.visit(case.guard)
            for child in case.body:
                self.visit(child)
            self._pop_scope()

    def _visit_pattern(self, pattern: ast.AST) -> None:
        """Register names from match patterns."""
        if isinstance(pattern, ast.MatchAs):
            if pattern.pattern:
                self._visit_pattern(pattern.pattern)
            if pattern.name:
                self._define(pattern.name)
        elif isinstance(pattern, ast.MatchMapping):
            for key in pattern.keys:
                self.visit(key)
            for p in pattern.patterns:
                self._visit_pattern(p)
            if pattern.rest:
                self._define(pattern.rest)
        elif isinstance(pattern, ast.MatchSequence):
            for p in pattern.patterns:
                self._visit_pattern(p)
        elif isinstance(pattern, ast.MatchStar):
            if pattern.name:
                self._define(pattern.name)
        elif isinstance(pattern, ast.MatchClass):
            self.visit(pattern.cls)
            for p in pattern.patterns:
                self._visit_pattern(p)
            for p in pattern.kwd_patterns:
                self._visit_pattern(p)
        elif isinstance(pattern, ast.MatchOr):
            for p in pattern.patterns:
                self._visit_pattern(p)
        elif isinstance(pattern, ast.MatchValue):
            self.visit(pattern.value)


def analyze_source(source: str, filename: str = "<string>") -> SentinelResult:
    """Analyze a source string for undefined symbols.

    Args:
        source: Python source code to analyze.
        filename: Filename for error messages.

    Returns:
        SentinelResult with any errors found.
    """
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as e:
        return SentinelResult(errors=[SentinelError(
            name="<syntax>",
            line=e.lineno or 0,
            message=f"Syntax error in {filename}: {e}",
        )])

    source_lines = source.splitlines()
    visitor = SymbolSentinel(source_lines=source_lines)
    visitor.visit(tree)

    return SentinelResult(errors=visitor.errors)


def analyze_file(path: str | Path) -> SentinelResult:
    """Analyze a file for undefined symbols.

    Args:
        path: Path to a Python source file.

    Returns:
        SentinelResult with any errors found.
    """
    path = Path(path)
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return SentinelResult(errors=[SentinelError(
            name="<io>",
            line=0,
            message=f"Cannot read {path}: {e}",
        )])

    return analyze_source(source, filename=str(path))


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: analyze files and report errors to stderr.

    Returns 1 if any errors found, 0 otherwise.
    """
    import argparse

    parser = argparse.ArgumentParser(description="AST-based Import Sentinel")
    parser.add_argument("files", nargs="+", help="Python files to analyze")
    args = parser.parse_args(argv)

    has_errors = False
    for filepath in args.files:
        result = analyze_file(filepath)
        if not result.ok:
            has_errors = True
            print(result.format_errors(), file=sys.stderr)

    return 1 if has_errors else 0


if __name__ == "__main__":
    sys.exit(main())