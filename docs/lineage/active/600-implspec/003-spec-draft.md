# Implementation Spec: AST-Based Import Sentinel

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #600 |
| LLD | `docs/lld/active/600-ast-based-import-sentinel.md` |
| Generated | 2026-03-05 |
| Status | APPROVED |

## 1. Overview

**Objective:** Enhance mechanical validation to strictly catch missing imports, undefined variables, and star imports using AST analysis before execution.

**Success Criteria:** The AST sentinel correctly parses nested scopes, builtins, comprehensions, and walrus operators, explicitly fails the validation gate (`exit 1`) via `sys.stderr` upon detecting unresolved symbols or star imports, and correctly respects `# sentinel: disable-line` directives.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `assemblyzero/utils/ast_sentinel.py` | Add | Core AST parsing logic and visitor for scope, global/nonlocal, and import tracking. |
| 2 | `tests/unit/test_ast_sentinel.py` | Add | Unit tests for AST Sentinel logic, covering scopes, comprehensions, and ignores. |
| 3 | `assemblyzero/workflows/requirements/nodes/validate_mechanical.py` | Modify | Integrate the new AST Sentinel check to scan repo files and strictly exit 1 on failure. |

**Implementation Order Rationale:** The core AST logic (`ast_sentinel.py`) has no internal dependencies and can be built and tested first. Once verified via `test_ast_sentinel.py`, it can be safely integrated into the mechanical validation node.

## 3. Current State (for Modify/Delete files)

### 3.1 `assemblyzero/workflows/requirements/nodes/validate_mechanical.py`

**Relevant excerpt** (lines 145-149):

```python
def validate_lld_mechanical(state: Dict[str, Any]) -> Dict[str, Any]:
    """Mechanical validation of LLD content.

Issue #277: Validates LLD structure and paths without LLM calls."""
    ...
```

**What changes:** Inject a call to the new AST sentinel right at the beginning of the `validate_lld_mechanical` function. If the `repo_root` is present and valid, the sentinel will scan the repository's `.py` files and immediately exit with code 1 if AST violations are found.

## 4. Data Structures

### 4.1 `SentinelError`

**Definition:**

```python
from dataclasses import dataclass

@dataclass
class SentinelError:
    file: str
    name: str
    line: int
    message: str
```

**Concrete Example:**

```json
{
    "file": "assemblyzero/utils/ast_sentinel.py",
    "name": "json",
    "line": 42,
    "message": "Symbol 'json' used on line 42 but not imported."
}
```

## 5. Function Specifications

### 5.1 `check_repo_with_sentinel()`

**File:** `assemblyzero/utils/ast_sentinel.py`

**Signature:**

```python
def check_repo_with_sentinel(repo_root: Path) -> None:
    """Recursively checks all .py files in the repo for lingering symbols."""
    ...
```

**Input Example:**

```python
repo_root = Path("/c/Users/mcwiz/Projects/TARGET_REPO")
```

**Output Example:**
*Returns `None`. If errors are found, it calls `sys.exit(1)` and prints to `sys.stderr`.*

**Edge Cases:**
- `repo_root` does not exist -> returns silently.
- Directory contains no `.py` files -> returns silently.

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
   - `__init__`: `self.scopes = [set(dir(builtins))]`, `self.errors = []`, `self.current_file = ""`
   - Scope Management: `push_scope(is_comprehension=False)`, `pop_scope()`, `add_symbol(name)`. Maintain internal tracking of whether the current scope is a comprehension scope.
   - Lookup Logic: `is_defined(name)` must explicitly iterate through `reversed(self.scopes)` to check if the symbol exists in any active scope.
   - `visit_Import` / `visit_ImportFrom`: Add names to `self.scopes[-1]`. **Crucial:** If `*` in names, append a `SentinelError` to `self.errors` with the message `"Star imports are not allowed: line {node.lineno}."` (Do not call `sys.exit` here).
   - `visit_If`: If `test` is `ast.Name` (`id == "TYPE_CHECKING"`) or `ast.Attribute` (`attr == "TYPE_CHECKING"`), process the body in the same scope so type hint imports are registered.
   - `visit_FunctionDef`, `visit_AsyncFunctionDef`: Add function name to current scope, `push_scope()`, add arguments to new scope, `generic_visit()`, `pop_scope()`.
   - `visit_ClassDef`: Visit `node.bases` and `node.keywords` in the current scope first. Add the class name to the current scope. Then `push_scope()`, `generic_visit()` the body, and `pop_scope()`. (Do not attempt to add `args`).
   - `visit_Lambda`: `push_scope()`, add args, `generic_visit()`, `pop_scope()`.
   - Comprehensions (`ListComp`, `DictComp`, `SetComp`, `GeneratorExp`): `push_scope(is_comprehension=True)`, visit generators (to register target variables), visit element, `pop_scope()`.
   - `visit_NamedExpr` (Walrus): Add `node.target.id` to the nearest enclosing function or global scope (bypassing any intermediate comprehension scopes), then `generic_visit()`.
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
- Use `pytest` and temporary files to test `run_sentinel_on_file`.
- Write functions for each test mapped in Section 9.
- Use `pytest.raises(SystemExit)` to test strict exit behavior for star imports via `check_repo_with_sentinel`.
- Mock or capture `sys.stderr` to verify exact error message formatting.

### 6.3 `assemblyzero/workflows/requirements/nodes/validate_mechanical.py` (Modify)

## 7. Pattern References

### 7.1 Repository Traversal & Checking

## 8. Dependencies & Imports

## 9. Test Mapping

## 10. Implementation Notes

### 10.1 Abstract Syntax Tree (AST) Nuances

### 10.2 Logging Convention

### 10.3 Error Filtering