# Implementation Spec: AST-Based Import Sentinel

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #600 |
| LLD | `docs/lld/active/600-ast-based-import-sentinel.md` |
| Generated | 2026-03-05 |
| Status | APPROVED |

## 1. Overview

**Objective:** Enhance mechanical validation to strictly catch "Lingering Symbols" (missing imports or undefined variables) before execution using AST analysis.

**Success Criteria:** The AST sentinel correctly parses nested scopes, builtins, comprehensions, and walrus operators, explicitly fails the validation gate (`exit 1`) via `sys.stderr` upon detecting unresolved symbols or star imports, and correctly respects `# sentinel: disable-line` directives.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `assemblyzero/utils/ast_sentinel.py` | Add | Core AST parsing logic and visitor for scope, global/nonlocal, and import tracking. |
| 2 | `tests/unit/test_ast_sentinel.py` | Add | Unit tests for AST Sentinel logic, covering scopes, comprehensions, and ignores. |
| 3 | `assemblyzero/workflows/requirements/nodes/validate_mechanical.py` | Modify | Integrate the new AST Sentinel check to scan repo files and strictly exit 1 on failure. |

**Implementation Order Rationale:** The core AST logic (`ast_sentinel.py`) has no internal dependencies and can be built and tested first. Once verified via `test_ast_sentinel.py` (which maps perfectly to LLD test scenarios), it can be safely integrated into the mechanical validation node.

## 3. Current State (for Modify/Delete files)

### [UNCHANGED] 3.1 `assemblyzero/workflows/requirements/nodes/validate_mechanical.py`

## [UNCHANGED] 4. Data Structures

### [UNCHANGED] 4.1 `SentinelError`

## [UNCHANGED] 5. Function Specifications

### [UNCHANGED] 5.1 `check_repo_with_sentinel()`

### 5.2 `run_sentinel_on_file()`

**File:** `assemblyzero/utils/ast_sentinel.py`

**Signature:**

```python
def run_sentinel_on_file(file_path: Path) -> list[SentinelError]:
    """Parses a single file and returns a list of AST violations."""
    ...
```

**Input Example:**

```python
file_path = Path("/c/Users/mcwiz/Projects/TARGET_REPO/src/main.py")
```

**Output Example:**

```python
[
    SentinelError(
        file="src/main.py",
        name="requests",
        line=10,
        message="Symbol 'requests' used on line 10 but not imported."
    )
]
```

**Edge Cases:**
- File contains valid syntax but missing import -> Returns list with `SentinelError`.
- File contains a star import -> Returns list with a `SentinelError` specifying "Star imports are not allowed...".
- File contains `SyntaxError` -> Caught and ignored (delegated to syntactical linters), returns `[]`.
- File contains `# sentinel: disable-line` on the exact line with the missing symbol -> Returns `[]`.

## 6. Change Instructions

### 6.1 `assemblyzero/utils/ast_sentinel.py` (Add)

**Action:** Create the core AST analysis module.

**Key Requirements for Implementation:**
1. Import `ast`, `sys`, `builtins`.
2. Define `SentinelError` dataclass.
3. Define `ImportSentinelVisitor(ast.NodeVisitor)` with stack-based scope tracking:
   - `__init__`: `self.scopes = [{'symbols': set(dir(builtins)), 'is_comp': False, 'is_func': False}]`, `self.errors = []`, `self.current_file = ""`
   - Scope Management: `push_scope(is_comprehension=False, is_function=False)`, `pop_scope()`, `add_symbol(name)`. Maintain internal tracking of whether the scope is a comprehension or function scope.
   - Lookup Logic: `is_defined(name)` must explicitly iterate through `reversed(self.scopes)` to check if the symbol exists in the `'symbols'` set of any active scope.
   - `visit_Import` / `visit_ImportFrom`: Add names to `self.scopes[-1]['symbols']`. **Crucial:** If `*` in names, append a `SentinelError` to `self.errors` with the message `"Star imports are not allowed: line {node.lineno}."` (Do not call `sys.exit` here).
   - `visit_If`: If `test` is `ast.Name` (`id == "TYPE_CHECKING"`) or `ast.Attribute` (`attr == "TYPE_CHECKING"`), process the body in the same scope so type hint imports are registered.
   - `visit_FunctionDef`, `visit_AsyncFunctionDef`: 
     1. Visit `node.decorator_list` and default arguments (`node.args.defaults`, `node.args.kw_defaults`) in the **current** scope.
     2. Add the function name (`node.name`) to the **current** scope.
     3. `push_scope(is_function=True)`.
     4. Add function arguments (`args`, `posonlyargs`, `kwonlyargs`, `vararg`, `kwarg`) to the **new** scope.
     5. Iterate over and visit `node.body` manually. Do NOT call `self.generic_visit(node)`.
     6. `pop_scope()`.
   - `visit_ClassDef`: 
     1. Visit `node.decorator_list`, `node.bases`, and `node.keywords` in the **current** scope.
     2. Add the class name (`node.name`) to the **current** scope. 
     3. `push_scope()`.
     4. Iterate over and visit `node.body` manually. Do NOT call `self.generic_visit(node)`.
     5. `pop_scope()`.
   - `visit_Lambda`: 
     1. Visit `node.args.defaults` and `node.args.kw_defaults` in the **current** scope.
     2. `push_scope(is_function=True)`.
     3. Add lambda arguments to the **new** scope.
     4. Visit `node.body`.
     5. `pop_scope()`.
   - Comprehensions (`ListComp`, `DictComp`, `SetComp`, `GeneratorExp`): `push_scope(is_comprehension=True)`, visit generators (to register target variables), visit element, `pop_scope()`.
   - `visit_NamedExpr` (Walrus): Add `node.target.id` to the nearest enclosing function scope. To do this, iterate backwards through `self.scopes`. Skip any scope where `is_comp` is `True`. If you find a scope where `is_func` is `True`, add the symbol there. If no function scope is found, add the symbol to the module-level scope (index 1 of `self.scopes`, as index 0 is builtins). Finally, visit `node.value`.
   - `visit_Global`, `visit_Nonlocal`: Add `node.names` to the current scope (prevents false positives).
   - `visit_Name`: If `isinstance(node.ctx, ast.Store)`, `add_symbol(node.id)`. If `isinstance(node.ctx, ast.Load)` and not `is_defined(node.id)`, append `SentinelError(self.current_file, node.id, node.lineno, f"Symbol '{node.id}' used on line {node.lineno} but not imported.")`.
4. Define `run_sentinel_on_file(file_path: Path) -> list[SentinelError]`:
   - Read lines. Parse `ast.parse(source)`.
   - Run visitor.
   - Filter errors: `if "# sentinel: disable-line" not in lines[err.line - 1]: filtered.append(err)`
5. Define `check_repo_with_sentinel(repo_root: Path) -> None`:
   - Glob `**/*.py` (ignoring `.venv` or `.git`).
   - Run on each file.
   - If any errors exist: print each to `sys.stderr` using the exact format from `err.message` (e.g., `"Symbol '{name}' used on line {line} but not imported."` or the star import message), then call `sys.exit(1)`.

### 6.2 `tests/unit/test_ast_sentinel.py` (Add)

**Action:** Create the test module.

**Key Requirements for Implementation:**
- Import `pytest`, `sys`, and `run_sentinel_on_file`, `check_repo_with_sentinel` from `assemblyzero.utils.ast_sentinel`.
- Use `pytest` and temporary files to test `run_sentinel_on_file`.
- Write functions for strictly every single test mapped in Section 9 (T010 - T110).
- Use `pytest.raises(SystemExit)` to test strict exit behavior for mechanical validation (T040).
- Mock or capture `sys.stderr` via `capsys.readouterr()` to verify exact error message formatting matches expectations in T030.

### 6.3 `assemblyzero/workflows/requirements/nodes/validate_mechanical.py` (Modify)

**Action:** Inject the AST Sentinel invocation immediately inside the LLD mechanical validation function.

**Instructions:**
1. Import `check_repo_with_sentinel` and `Path`.
2. Inside `validate_lld_mechanical`, before any existing validation logic, extract `repo_root` from the state.
3. If the path exists, invoke `check_repo_with_sentinel`.

**Target Code Changes:**

```python
# Add to imports
from pathlib import Path
from assemblyzero.utils.ast_sentinel import check_repo_with_sentinel

# Modify validate_lld_mechanical
def validate_lld_mechanical(state: Dict[str, Any]) -> Dict[str, Any]:
    """Mechanical validation of LLD content.

Issue #277: Validates LLD structure and paths without LLM calls."""
    repo_root = state.get("repo_root")
    if repo_root:
        check_repo_with_sentinel(Path(repo_root))
        
    # ... existing validation logic ...
```

## [UNCHANGED] 7. Pattern References

### 7.1 Repository Traversal & Checking

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import ast` | stdlib | `assemblyzero/utils/ast_sentinel.py` |
| `import sys` | stdlib | `assemblyzero/utils/ast_sentinel.py` |
| `import builtins` | stdlib | `assemblyzero/utils/ast_sentinel.py` |
| `from dataclasses import dataclass` | stdlib | `assemblyzero/utils/ast_sentinel.py` |
| `from pathlib import Path` | stdlib | `assemblyzero/utils/ast_sentinel.py`, `validate_mechanical.py` |
| `from typing import Any, Dict` | stdlib | `validate_mechanical.py` |
| `import pytest` | external | `tests/unit/test_ast_sentinel.py` |

**New Dependencies:** None (uses standard library `ast` and existing test framework).

## 9. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `run_sentinel_on_file()` | Valid source with `import os; os.path.join()` | `[]` |
| T020 | `run_sentinel_on_file()` | Source `json.dumps({})` (missing import) | `[SentinelError]` targeting 'json' |
| T030 | `check_repo_with_sentinel()` | Source with missing import | `sys.stderr` contains exact "Symbol '...' used on line X but not imported." |
| T040 | `validate_lld_mechanical()` | Dummy state dict with valid `repo_root` containing bad Python code | Raises `SystemExit` (1) |
| T050 | `run_sentinel_on_file()` | Nested local code `def foo(a): b = a; return b` | `[]` (Arguments and nested variables resolve natively) |
| T060 | `run_sentinel_on_file()` | Comprehensions `[x for x in y]` / `{k:v for k,v in z.items()}` | `[]` (Assuming `y` and `z` are imported or defined globally) |
| T070 | `run_sentinel_on_file()` | Source with walrus `if (n := len(a)) > 1: print(n)` | `[]` (Variable `n` correctly assigned locally) |
| T080 | `run_sentinel_on_file()` | Source with `from typing import *` | `[SentinelError]` with message "Star imports are not allowed: line X." |
| T090 | `run_sentinel_on_file()` | Source containing `global x` or `nonlocal y` | `[]` |
| T100 | `run_sentinel_on_file()` | `if TYPE_CHECKING: import typing` | `[]` (Type hinting scopes register globally) |
| T110 | `run_sentinel_on_file()` | `undefined_var # sentinel: disable-line` | `[]` (Specific line ignored correctly) |

## 10. Implementation Notes

### 10.1 Abstract Syntax Tree (AST) Nuances

- **Data Structure for Scope Tracking:** Instead of a flat list, implement the scope stack dynamically using a list of dictionaries (`list[dict]`). Example: `[{'symbols': set(dir(builtins)), 'is_comp': False, 'is_func': False}]`. Index 0 is always builtins. Index 1 represents the module-level global scope. This unambiguous dict mapping avoids confusion and clearly marks which scopes are list comprehensions and which are enclosing functions.
- **Walrus Operators (`:=`):** According to Python 3.8+ language semantics, a walrus operator inside a comprehension binds the variable to the enclosing function scope (or global scope if not inside a function). It *never* binds to the comprehension scope itself. Thus, `visit_NamedExpr` must explicitly scan backwards through the stack, ignore `is_comp=True` layers, and assign the target `id` to the first `is_func=True` layer it finds, falling back to module scope (index 1) if no function exists.
- **`TYPE_CHECKING` Flow:** AST parsing statically reads files, meaning standard `if TYPE_CHECKING:` branches would normally evaluate conditionally. Ensure your `visit_If` checks explicitly for `TYPE_CHECKING` and traverses its body strictly sequentially, effectively treating it as executed code so its imports register for the rest of the module file.

### 10.2 Logging Convention

### [UNCHANGED] 10.3 Error Filtering