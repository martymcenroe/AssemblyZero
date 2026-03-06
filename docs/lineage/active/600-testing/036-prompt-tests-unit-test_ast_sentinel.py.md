# Implementation Request: tests/unit/test_ast_sentinel.py

## Task

Write the complete contents of `tests/unit/test_ast_sentinel.py`.

Change type: Add
Description: Unit tests for AST Sentinel logic.

## LLD Specification

# Implementation Spec: 0600 - AST-Based Import Sentinel

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #600 |
| LLD | `docs/lld/active/LLD-600.md` |
| Generated | 2026-03-05 |
| Status | APPROVED |

## 1. Overview
Enhance mechanical validation to strictly catch "Lingering Symbols" (missing imports or undefined variables) before execution using AST analysis.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `assemblyzero/utils/ast_sentinel.py` | Add | Core AST parsing logic and visitor. |
| 2 | `tests/unit/test_ast_sentinel.py` | Add | Unit tests for AST Sentinel logic. |
| 3 | `assemblyzero/workflows/requirements/nodes/validate_mechanical.py` | Modify | Integrate the new AST Sentinel check. |

## 3. Current State (for Modify/Delete files)

### 3.1 assemblyzero/workflows/requirements/nodes/validate_mechanical.py
```python
def validate_mechanical(state: RequirementsWorkflowState) -> dict:
    # ... existing validation logic ...
    return {"validation_errors": errors}
```

## 4. Technical Strategy
1. **ast_sentinel.py:** Implement `SymbolSentinel` using `ast.NodeVisitor`.
   - Maintain a `scope_stack` (list of sets) to track definitions.
   - `visit_Import`/`visit_ImportFrom`: Register aliases in the current scope. Reject `*`.
   - `visit_FunctionDef`/`visit_ClassDef`: Push new scope, register args/name, pop on exit.
   - `visit_Name(ctx=ast.Load)`: Check if name exists in any scope in the stack or `builtins`.
2. **Integration:** Update `validate_mechanical.py` to call `ast_sentinel.analyze_file(path)`.

## 5. Requirements Mapping (from LLD)
- REQ-1: Parse using `ast.parse` and `NodeVisitor`.
- REQ-2: Detect `ast.Load` without corresponding definition.
- REQ-3: State specific error: "Symbol '{name}' used on line {line} but not imported."
- REQ-4: Strictly fail gate (`exit 1`) on un-ignored errors.
- REQ-5: Recursive stack-based scope tracking (nested scopes, comprehensions, walrus).
- REQ-6: Ban star imports explicitly.
- REQ-7: Support `if TYPE_CHECKING:` blocks.
- REQ-8: Support `# sentinel: disable-line`.

## 10. Verification & Testing

### 10.1 Test Scenarios
| ID | Scenario | Input | Expected | Pass Criteria |
|----|----------|-------|----------|---------------|
| 010 | Happy path valid AST Analysis (REQ-1) | `import os; os.path.join()` | No errors | No errors emitted |
| 020 | Missing import verified (REQ-2) | `json.dumps({})` | `SentinelError` | Error for 'json' |
| 030 | Feedback to stderr (REQ-3) | `json.dumps({})` | Error in stderr | Exact string in stderr |
| 040 | Mechanical validation fail (REQ-4) | Bad file | `sys.exit(1)` | Exit code 1 |
| 050 | Local scope resilience (REQ-5) | `def foo(a): b = a; return b` | No errors | Args/locals recognized |
| 060 | Comprehensions (REQ-5) | `[x for x in y]` | No errors | 'x' isolated |
| 070 | Walrus Operators (REQ-5) | `if (n := len(a)) > 1: print(n)` | No errors | 'n' recognized |
| 080 | Star imports banned (REQ-6) | `from typing import *` | "Star imports are not allowed" | REQ-6 failure |
| 090 | Global/Nonlocal tracking (REQ-5) | `global x; x = 1` | No errors | No false positives |
| 100 | TYPE_CHECKING support (REQ-7) | `if TYPE_CHECKING: from x import y` | No errors | 'y' registered |
| 110 | Ignore comments (REQ-8) | `var # sentinel: disable-line` | No errors | Symbol ignored |

**Final Status:** APPROVED (Manually Patched)


## Required File Paths (from LLD - do not deviate)

The following paths are specified in the LLD. Write ONLY to these paths:


Any files written to other paths will be rejected.

## Repository Structure

The actual directory layout of this repository:

```
tests/
  accessibility/
  adversarial/
  benchmark/
  compliance/
  contract/
  e2e/
  fixtures/
    death/
    issue_workflow/
    janitor/
      mock_repo/
    lld_tracking/
    metrics/
    mock_lineage/
    mock_repo/
      src/
    rag/
    scout/
    scraper/
    spelunking/
    verdict_analyzer/
  harness/
  integration/
  security/
  tools/
  unit/
    test_death/
    test_gate/
    test_janitor/
    test_rag/
    test_spelunking/
  visual/
  __init__.py
  conftest.py
  test_assemblyzero_config.py
  test_audit.py
  test_audit_sharding.py
  test_credentials.py
  test_designer.py
  test_gemini_client.py
  test_gemini_credentials_v2.py
  test_integration_workflow.py
  ... and 14 more files
assemblyzero/
  core/
    validation/
  graphs/
  hooks/
  metrics/
  nodes/
  rag/
  spelunking/
  telemetry/
  utils/
  workflows/
    death/
    implementation_spec/
      nodes/
    issue/
      nodes/
    janitor/
      probes/
    lld/
    orchestrator/
    parallel/
    requirements/
      nodes/
      parsers/
    scout/
    testing/
      completeness/
      knowledge/
      nodes/
      runners/
      templates/
  __init__.py
  tracing.py
dashboard/
  src/
    client/
      components/
      pages/
  package.json
  tsconfig.client.json
  tsconfig.json
  tsconfig.worker.json
  wrangler.toml
data/
  hourglass/
  unleashed/
```

Use these real paths — do NOT invent paths that don't exist.

## Tests That Must Pass

```python
# From C:\Users\mcwiz\Projects\AssemblyZero-600\tests\test_issue_600.py
"""Test file for Issue #600.

Generated by AssemblyZero TDD Testing Workflow.
Tests will fail with ImportError until implementation exists (TDD RED phase).
"""

import pytest

# TDD: This import fails until implementation exists (RED phase)
# Once implemented, tests can run (GREEN phase)
from assemblyzero.utils.ast_sentinel import *  # noqa: F401, F403


# Unit Tests
# -----------

def test_010():
    """
    Happy path valid AST Analysis (REQ-1) | `import os; os.path.join()` |
    No errors | No errors emitted
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_010 works correctly
    assert False, 'TDD RED: test_010 not implemented'


def test_020():
    """
    Missing import verified (REQ-2) | `json.dumps({})` | `SentinelError`
    | Error for 'json'
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_020 works correctly
    assert False, 'TDD RED: test_020 not implemented'


def test_030():
    """
    Feedback to stderr (REQ-3) | `json.dumps({})` | Error in stderr |
    Exact string in stderr
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_030 works correctly
    assert False, 'TDD RED: test_030 not implemented'


def test_040():
    """
    Mechanical validation fail (REQ-4) | Bad file | `sys.exit(1)` | Exit
    code 1
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_040 works correctly
    assert False, 'TDD RED: test_040 not implemented'


def test_050():
    """
    Local scope resilience (REQ-5) | `def foo(a): b = a; return b` | No
    errors | Args/locals recognized
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_050 works correctly
    assert False, 'TDD RED: test_050 not implemented'


def test_060():
    """
    Comprehensions (REQ-5) | `[x for x in y]` | No errors | 'x' isolated
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_060 works correctly
    assert False, 'TDD RED: test_060 not implemented'


def test_070():
    """
    Walrus Operators (REQ-5) | `if (n := len(a)) > 1: print(n)` | No
    errors | 'n' recognized
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_070 works correctly
    assert False, 'TDD RED: test_070 not implemented'


def test_080():
    """
    Star imports banned (REQ-6) | `from typing import *` | "Star imports
    are not allowed" | REQ-6 failure
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_080 works correctly
    assert False, 'TDD RED: test_080 not implemented'


def test_090():
    """
    Global/Nonlocal tracking (REQ-5) | `global x; x = 1` | No errors | No
    false positives
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_090 works correctly
    assert False, 'TDD RED: test_090 not implemented'


def test_100():
    """
    TYPE_CHECKING support (REQ-7) | `if TYPE_CHECKING: from x import y` |
    No errors | 'y' registered
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_100 works correctly
    assert False, 'TDD RED: test_100 not implemented'


def test_110():
    """
    Ignore comments (REQ-8) | `var # sentinel: disable-line` | No errors
    | Symbol ignored
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_110 works correctly
    assert False, 'TDD RED: test_110 not implemented'




```

## Previously Implemented Files

These files have already been implemented. Use them for imports and references:

### assemblyzero/utils/ast_sentinel.py (full)

```python
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
```

## Output Format

Output ONLY the file contents. No explanations, no markdown headers, just the Python code.

```python
# Your Python code here
```

IMPORTANT:
- Output the COMPLETE file contents
- Do NOT output a summary or description
- Do NOT say "I've implemented..."
- Just output the Python code in a single fenced code block
