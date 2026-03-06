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
   - `push_scope()`, `pop_scope()`, `add_symbol(name)`, `is_defined(name)`.
   - `visit_Import` / `visit_ImportFrom`: Add names to `self.scopes[-1]`. **Crucial:** If `*` in names, print `"Star imports are not allowed: line {node.lineno}."` to `sys.stderr` and `sys.exit(1)`.
   - `visit_If`: If `test` is `ast.Name` and `id == "TYPE_CHECKING"`, process body in the same scope so type hint imports are registered.
   - `visit_FunctionDef`, `visit_AsyncFunctionDef`, `visit_ClassDef`: Add name to current scope, `push_scope()`, add arguments, `generic_visit()`, `pop_scope()`.
   - `visit_Lambda`: `push_scope()`, add args, `generic_visit()`, `pop_scope()`.
   - Comprehensions (`ListComp`, `DictComp`, etc.): `push_scope()`, visit generators (to register target variables), visit element, `pop_scope()`.
   - `visit_NamedExpr` (Walrus): `add_symbol(node.target.id)`, `generic_visit()`.
   - `visit_Global`, `visit_Nonlocal`: Add `node.names` to current scope (prevents false positives).
   - `visit_Name`: If `isinstance(node.ctx, ast.Store)`, `add_symbol(node.id)`. If `isinstance(node.ctx, ast.Load)` and not `is_defined(node.id)`, append `SentinelError(self.current_file, node.id, node.lineno)`.
4. Define `run_sentinel_on_file(file_path: Path) -> list[SentinelError]`:
   - Read lines. Parse `ast.parse(source)`.
   - Run visitor.
   - Filter errors: `if "# sentinel: disable-line" not in lines[err.line - 1]: filtered.append(err)`
5. Define `check_repo_with_sentinel(repo_root: Path) -> None`:
   - Glob `**/*.py` (ignoring `.venv` or `.git`).
   - Run on each file.
   - If any errors exist: print each to `sys.stderr` using the exact format `"Symbol '{name}' used on line {line} but not imported."`, then `sys.exit(1)`.

### 6.2 `tests/unit/test_ast_sentinel.py` (Add)

**Action:** Create the test module.

**Key Requirements for Implementation:**
- Use `pytest` and temporary files to test `run_sentinel_on_file`.
- Write functions for each test mapped in Section 9.
- Use `pytest.raises(SystemExit)` to test strict exit behavior for star imports.
- Mock or capture `sys.stderr` to verify exact error message formatting.

### 6.3 `assemblyzero/workflows/requirements/nodes/validate_mechanical.py` (Modify)

**Change 1:** Add the call to the sentinel in the main validation function.

```diff
 def validate_lld_mechanical(state: Dict[str, Any]) -> Dict[str, Any]:
     """Mechanical validation of LLD content.
 
 Issue #277: Validates LLD structure and paths without LLM calls."""
+    
+    # Issue #600: AST-Based Import Sentinel check
+    repo_root_str = state.get("repo_root")
+    if repo_root_str:
+        from assemblyzero.utils.ast_sentinel import check_repo_with_sentinel
+        check_repo_with_sentinel(Path(repo_root_str))
+
     ...
```

## 7. Pattern References

### 7.1 Repository Traversal & Checking

**File:** `assemblyzero/workflows/implementation_spec/nodes/analyze_codebase.py:1-50`

```python
def find_python_files(repo_root: Path) -> list[Path]:
    """Recursively find all Python files, skipping common ignores."""
    ignore_dirs = {".git", ".venv", "venv", "__pycache__", "node_modules"}
    return [
        p for p in repo_root.rglob("*.py")
        if not any(part in ignore_dirs for part in p.parts)
    ]
```

**Relevance:** Use this exact traversal logic inside `check_repo_with_sentinel()` to ensure `.venv` and `__pycache__` directories are safely skipped, preventing false positives from third-party libraries.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import ast` | stdlib | `ast_sentinel.py` |
| `import sys` | stdlib | `ast_sentinel.py` |
| `import builtins` | stdlib | `ast_sentinel.py` |
| `from pathlib import Path` | stdlib | `ast_sentinel.py`, `validate_mechanical.py` |
| `from dataclasses import dataclass` | stdlib | `ast_sentinel.py` |
| `from typing import Any, Dict` | stdlib | `ast_sentinel.py` |

**New Dependencies:** None (uses standard library `ast`).

## 9. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `run_sentinel_on_file()` | File with `import os; os.path.join("a")` | `[]` |
| T020 | `run_sentinel_on_file()` | File with `json.dumps({})` but no import | `[SentinelError]` targeting line 1 |
| T030 | `run_sentinel_on_file()` | File using `print`, `len`, `Exception` | `[]` (builtins properly scoped) |
| T040 | `run_sentinel_on_file()` | File with `def foo(a): b = a; return b` | `[]` (args and locals properly scoped) |
| T050 | `check_repo_with_sentinel()` | Repo with missing imports | `sys.exit(1)` and writes to `sys.stderr` |
| T060 | `run_sentinel_on_file()` | File with `[x for x in y]` | `[]` (comprehension target `x` is local) |
| T070 | `run_sentinel_on_file()` | File with `if (n := len(a)) > 1: print(n)` | `[]` (walrus operator `n` recognized) |
| T080 | `run_sentinel_on_file()` | File with `from typing import *` | Calls `sys.exit(1)`, prints "Star imports are not allowed: line X." |
| T090 | `run_sentinel_on_file()` | File with `def f(): global x; x = 1` | `[]` (`global`/`nonlocal` scopes tracked) |
| T100 | `run_sentinel_on_file()` | File with `if TYPE_CHECKING: import foo` | `[]` (resolves `foo` for rest of module) |
| T110 | `run_sentinel_on_file()` | `bad_var # sentinel: disable-line` | `[]` (error is filtered out) |

## 10. Implementation Notes

### 10.1 Abstract Syntax Tree (AST) Nuances
- **Builtins:** Initialize the base scope index 0 with `set(dir(builtins))`. This ensures standard functions like `print`, `len`, and `ValueError` are recognized globally out-of-the-box.
- **NodeVisitor State:** `ast.NodeVisitor` traverses recursively. You MUST implement `push_scope()` before traversing children (via `self.generic_visit(node)`) and `pop_scope()` after, for nodes that create new scopes (`FunctionDef`, `ClassDef`, `Lambda`, `ListComp`, `SetComp`, `DictComp`, `GeneratorExp`).
- **Comprehensions:** The target variables defined in `node.generators` (e.g., the `x` in `[x for x in y]`) must be added to the comprehension's scope BEFORE traversing `node.elt` or `node.value`.

### 10.2 Logging Convention
- **Mechanical Validation Gate:** To cleanly integrate with CI/CD and the overarching workflow gate, do **not** use the standard `logging` library for the failure emissions here. Errors MUST be explicitly printed to `sys.stderr` exactly as specified: `print(f"Symbol '{err.name}' used on line {err.line} but not imported.", file=sys.stderr)`.

### 10.3 Error Filtering
- The `# sentinel: disable-line` directive is a substring match. Since `ast` drops comments during parsing, you must read the file into a list of strings (`lines = file.read_text().splitlines()`) and verify the exact line string at index `err.line - 1`. If the substring exists, the `SentinelError` must be silently dropped.