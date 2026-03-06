# #600 - Feature: AST-Based Import Sentinel

<!-- Template Metadata
Last Updated: 2026-02-02
Updated By: Issue #600 implementation
Update Reason: Initial LLD for Import Sentinel
Previous: N/A
-->

## 1. Context & Goal
* **Issue:** #600
* **Objective:** Implement a static analysis tool using Python's `ast` module to detect undefined symbols (missing imports or undefined variables) to prevent runtime `NameError` in generated code.
* **Status:** Draft
* **Related Issues:** #587 (Mechanical Gate)

### Open Questions
*Questions that need clarification before or during implementation. Remove when resolved.*

- [ ] Should `from module import *` (wildcard imports) disable validation for the scope? (Proposed: Flag wildcards as a separate high-severity warning and skip validation for that file to avoid false positives).
- [ ] How to handle dynamic `globals()` manipulation? (Proposed: Ignore dynamic manipulation; strictly enforce static definitions).

## 2. Proposed Changes

*This section is the **source of truth** for implementation. Describe exactly what will be built.*

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `assemblyzero/core/validation/ast_sentinel.py` | Add | Core logic for AST traversal and scope tracking. |
| `tools/validate_mechanical.py` | Add | CLI entry point to run the sentinel check against the repository or specific files. |
| `tests/unit/test_ast_sentinel.py` | Add | Unit tests for various scope and import scenarios. |

### 2.1.1 Path Validation (Mechanical - Auto-Checked)

*Issue #277: Before human or Gemini review, paths are verified programmatically.*

Mechanical validation automatically checks:
- All "Modify" files must exist in repository
- All "Delete" files must exist in repository
- All "Add" files must have existing parent directories
- No placeholder prefixes (`src/`, `lib/`, `app/`) unless directory exists

**If validation fails, the LLD is BLOCKED before reaching review.**

### 2.2 Dependencies

*New packages, APIs, or services required.*

None. Uses Python standard library `ast` and `builtins`.

### 2.3 Data Structures

```python
from typing import TypedDict, Set, Optional, List

class SentinelError(TypedDict):
    line: int
    column: int
    symbol: str
    message: str
    code: str  # e.g., "E001" (Undefined), "W001" (Wildcard)

class Scope:
    def __init__(self, parent: Optional['Scope'] = None, is_class: bool = False):
        self.parent = parent
        self.defined_names: Set[str] = set()
        self.is_class = is_class

    def define(self, name: str):
        self.defined_names.add(name)

    def is_defined(self, name: str) -> bool:
        if name in self.defined_names:
            return True
        # In class scope, we don't recurse up for bare names during definition checks
        # normally, but for read access, Python looks up (LEGB).
        # Exception: Class bodies don't see class variable names being defined *as* they are used
        # in the same block for some constructs, but generally LEGB applies.
        if self.parent:
            return self.parent.is_defined(name)
        return False
```

### 2.4 Function Signatures

```python

# assemblyzero/core/validation/ast_sentinel.py

import ast

class ImportSentinel(ast.NodeVisitor):
    def __init__(self):
        self.errors: List[SentinelError] = []
        self.current_scope: Scope = Scope()
        self._init_builtins()

    def _init_builtins(self):
        """Populate root scope with dir(__builtins__)."""
        ...

    def check_source(self, content: str, filename: str) -> List[SentinelError]:
        """Parses and checks a single file content."""
        ...

    def visit_Import(self, node: ast.Import):
        """Register imported modules in current scope."""
        ...

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Register imported names in current scope."""
        ...

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Handle function scope, arguments, and decorators."""
        ...

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Handle async function scope."""
        ...

    def visit_ClassDef(self, node: ast.ClassDef):
        """Handle class scope."""
        ...

    def visit_Lambda(self, node: ast.Lambda):
        """Handle lambda scope."""
        ...

    def visit_ListComp(self, node: ast.ListComp):
        """Handle list comprehension scope."""
        ...

    def visit_Name(self, node: ast.Name):
        """Check if Loaded name exists in scope; Register Stored name."""
        ...

    def visit_Global(self, node: ast.Global):
        """Handle global keyword declarations."""
        ...

    def visit_Nonlocal(self, node: ast.Nonlocal):
        """Handle nonlocal keyword declarations."""
        ...
```

### 2.5 Logic Flow (Pseudocode)

```
1. Initialize ImportSentinel with standard Python builtins.
2. Read source code from file.
3. Parse source code into AST (ast.parse).
   - If SyntaxError: Catch, report as Critical Error, abort file.
4. Traverse AST (NodeVisitor):
   - Scope Management:
     - Root is Global Scope (pre-filled with builtins).
     - Enter Scope (Function/Class/Lambda/Comprehension): Push new Scope object to stack.
     - Exit Scope: Pop from stack.
   - Registration (Store Context):
     - `x = 1`, `import x`, `def x`, `class x`: Add 'x' to `current_scope.defined_names`.
     - Function Arguments: Add to the *new* function scope.
   - Validation (Load Context):
     - `y = x`: Check if 'x' is in `current_scope` (recursive lookup).
     - If not found: Append Error "Symbol 'x' used but not defined".
   - Special Handling:
     - `global x`: Mark 'x' as belonging to Root scope, not local.
     - `nonlocal x`: Verify 'x' exists in parent (non-global) scopes.
5. Return list of errors.
```

### 2.6 Technical Approach

*   **Module:** `assemblyzero/core/validation/ast_sentinel.py`
*   **Pattern:** Visitor Pattern (`ast.NodeVisitor`) with Scope Stack.
*   **Key Decisions:**
    *   **Custom AST Visitor:** Selected over Pylint/Pyflakes to ensure zero dependencies and extreme speed for the mechanical gate. We specifically target `NameError` which is a subset of what linters do.
    *   **Scope Stack:** Explicit stack management is required to handle Python's LEGB (Local, Enclosing, Global, Built-in) rule correctly.
    *   **Comprehensions:** In Python 3, list/set/dict comprehensions and generator expressions create their own scope. The visitor must handle this to prevent leaking loop variables (unlike Python 2 list comps).

### 2.7 Architecture Decisions

| Decision | Options Considered | Choice | Rationale |
|----------|-------------------|--------|-----------|
| **Analysis Engine** | `pylint`, `pyflakes`, `ast` | `ast` | Lightweight, zero-dep, specific to the "NameError" goal without configuration overhead. |
| **Scope Handling** | Flat list vs. Stack | Stack | Python has nested scopes (LEGB rule); a stack is required to correctly identify shadowing and visibility. |
| **Error Reporting** | Throw Exception vs Accumulate | Accumulate | We want to report all missing imports in a file at once, not stop at the first one. |

**Architectural Constraints:**
- Must run fast (< 100ms per file) to be part of the pre-run mechanical gate.
- No new external pip dependencies (standard library only).

## 3. Requirements

1.  **Detection:** Must identify `NameError` candidates (variables used but not defined/imported).
2.  **Accuracy:** Must support standard Python scoping (LEGB), including function arguments, list comprehensions, and exception handlers (`except Exception as e`).
3.  **Built-ins:** Must respect Python 3.10+ built-ins.
4.  **Feedback:** Error messages must include line number and specific symbol name.
5.  **Integration:** Must be callable via CLI (`tools/validate_mechanical.py`).

## 4. Alternatives Considered

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| **Integrate Pyflakes** | Mature, handles edge cases. | Adds dependency, less control over output format. | Rejected |
| **Regex Scanning** | Fast, simple. | Impossible to accurately parse context/scope (e.g., strings vs code). | Rejected |
| **AST Visitor** | Exact parsing, zero dep, custom logic. | Requires implementing scope logic from scratch. | **Selected** |

**Rationale:** The `ast` module provides the perfect balance of accuracy and lightweight integration for a specific "fail-fast" check.

## 5. Data & Fixtures

### 5.1 Data Sources

| Attribute | Value |
|-----------|-------|
| Source | Python source files in the repo |
| Format | `.py` text content |
| Size | Kilobytes per file |
| Refresh | Real-time on execution |
| Copyright/License | N/A |

### 5.2 Data Pipeline

```
File System ──read──► String ──ast.parse──► AST ──SentinelVisitor──► List[Errors] ──► CLI Output
```

### 5.3 Test Fixtures

| Fixture | Source | Notes |
|---------|--------|-------|
| `valid_complex_scope.py` | Hardcoded string | Nested functions, classes, comprehensions, valid usage. |
| `missing_import.py` | Hardcoded string | Uses `os.path` without importing `os`. |
| `undefined_var.py` | Hardcoded string | Uses `x` without assignment. |
| `scope_shadowing.py` | Hardcoded string | Defines `x` in func, checks it's not seen globally. |
| `wildcard_import.py` | Hardcoded string | `from x import *` usage. |

### 5.4 Deployment Pipeline

Code is deployed as part of the `assemblyzero-tools` package. The sentinel runs locally during the "Mechanical Gate" phase of the workflow via `tools/validate_mechanical.py`.

## 6. Diagram

### 6.1 Mermaid Quality Gate

- [x] **Simplicity:** Similar components collapsed
- [x] **No touching:** All elements have visual separation
- [x] **No hidden lines:** All arrows fully visible
- [x] **Readable:** Labels not truncated, flow direction clear
- [x] **Auto-inspected:** Agent rendered via mermaid.ink and viewed

**Auto-Inspection Results:**
```
- Touching elements: [ ] None / [x] None
- Hidden lines: [ ] None / [x] None
- Label readability: [ ] Pass / [x] Pass
- Flow clarity: [ ] Clear / [x] Clear
```

### 6.2 Diagram

```mermaid
sequenceDiagram
    participant User
    participant CLI as validate_mechanical.py
    participant S as ImportSentinel
    participant A as AST Module
    participant V as NodeVisitor

    User->>CLI: Run Validation
    CLI->>CLI: Scan Directory (.py)
    loop For Each File
        CLI->>S: check_source(content)
        S->>S: Init Builtins
        S->>A: parse(content)
        A-->>S: Root Node
        S->>V: visit(Root)

        loop AST Traversal
            V->>V: Push Scope (if block)
            V->>V: Register Defs (Store)
            V->>V: Check Usage (Load)
            alt Symbol Missing
                V-->>S: Record Error
            end
            V->>V: Pop Scope (exit block)
        end

        S-->>CLI: Return Errors
    end

    alt Errors Found
        CLI-->>User: Exit 1 (Report)
    else No Errors
        CLI-->>User: Exit 0
    end
```

## 7. Security & Safety Considerations

### 7.1 Security

| Concern | Mitigation | Status |
|---------|------------|--------|
| Malicious Code Execution | AST analysis is static; it does not execute the code, so no risk of side effects from malicious files during scan. | Addressed |
| DoS via Deep Nesting | Python `ast` has recursion limits. We rely on Python's parser limits. | Addressed |

### 7.2 Safety

| Concern | Mitigation | Status |
|---------|------------|--------|
| False Positives (Blocking valid code) | "Fail Open" on dynamic constructs (e.g., `eval`, `globals()['x'] = 1`). We only strictly block on static `Name` usage that is definitely missing. Support `# type: ignore` or similar if needed (future). | Addressed |

**Fail Mode:** Fail Closed - If the code contains syntax errors or undefined symbols, the gate prevents execution to save tokens/time.

**Recovery Strategy:** User must fix the import or definition in the source file.

## 8. Performance & Cost Considerations

### 8.1 Performance

| Metric | Budget | Approach |
|--------|--------|----------|
| Latency | < 100ms/file | Single-pass AST traversal is extremely fast (compiled C underneath). |
| Memory | < 50MB | AST nodes are lightweight for typical file sizes. |

**Bottlenecks:** Scanning very large files (10k+ LOC) might take longer, but this is rare in this codebase.

### 8.2 Cost Analysis

| Resource | Unit Cost | Estimated Usage | Monthly Cost |
|----------|-----------|-----------------|--------------|
| CPU | Negligible | Local execution | $0 |

**Cost Controls:**
- Saves money by preventing LLM/Agent execution on code that would immediately crash with `NameError` (token savings).

**Worst-Case Scenario:** Sentinel crashes on valid code -> User bypasses mechanical gate or fixes the parser bug.

## 9. Legal & Compliance

| Concern | Applies? | Mitigation |
|---------|----------|------------|
| PII/Personal Data | No | Logic analyzes code structure, not data values. |
| Third-Party Licenses | No | No new dependencies. |

**Data Classification:** Internal (Source Code).

**Compliance Checklist:**
- [x] No PII stored
- [x] No external dependencies
- [x] Standard Library use only

## 10. Verification & Testing

**Testing Philosophy:** 100% unit test coverage for the AST logic to ensure no false positives.

### 10.0 Test Plan (TDD - Complete Before Implementation)

**TDD Requirement:** Tests MUST be written and failing BEFORE implementation begins.

| Test ID | Test Description | Expected Behavior | Status |
|---------|------------------|-------------------|--------|
| T010 | Basic undefined variable | Return error with line number | RED |
| T020 | Valid import usage | Return 0 errors | RED |
| T030 | Function argument scope | Argument is visible in body, not outside | RED |
| T040 | Class method `self` | `self` is defined in method scope | RED |
| T050 | Built-in function (`len`) | Return 0 errors | RED |
| T060 | Star import | Return Warning or Error | RED |
| T070 | List comprehension (Py3) | Iteration variable not leaked to outer scope | RED |
| T080 | Lambda argument | Arg visible in lambda body | RED |
| T090 | Global keyword | Modifies variable visibility | RED |

**Coverage Target:** ≥95% for `ast_sentinel.py`.

**TDD Checklist:**
- [ ] All tests written before implementation
- [ ] Tests currently RED (failing)
- [ ] Test IDs match scenario IDs in 10.1
- [ ] Test file created at: `tests/unit/test_ast_sentinel.py`

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | Use of undefined `x` | Auto | `print(x)` | Error: 'x' undefined | Error list has 1 entry |
| 020 | Import `os` and use | Auto | `import os; os.path.join()` | No Errors | Error list empty |
| 030 | Local var shadowing | Auto | `x=1; def f(): x=2; return x` | No Errors | Error list empty |
| 040 | Missing import inside func | Auto | `def f(): return math.pi` | Error: 'math' undefined | Error list has 1 entry |
| 050 | List Comp Scope (Py3) | Auto | `[i for i in range(10)]; print(i)` | Error: 'i' undefined (if global) | Error list has 1 entry |
| 060 | Exception Handler | Auto | `try: pass; except Exception as e: print(e)` | No Errors | Error list empty |

### 10.2 Test Commands

```bash

# Run unit tests
poetry run pytest tests/unit/test_ast_sentinel.py -v
```

### 10.3 Manual Tests

N/A - All scenarios automated.

## 11. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| False Positives on Magic | Med | Low | Allow `# type: ignore` or similar suppression, or explicitly whitelist dynamic names if needed. |
| Complex Scope (Decorators) | Low | Med | Ensure visitor handles `decorator_list` in function definitions correctly (decorators run in enclosing scope). |
| Generator Expressions | Low | Low | Ensure `GeneratorExp` creates a new scope similar to comprehensions. |

## 12. Definition of Done

### Code
- [ ] `ImportSentinel` class implemented in `assemblyzero/core/validation/ast_sentinel.py`.
- [ ] `tools/validate_mechanical.py` created and capable of scanning directories.
- [ ] Handles imports, classes, functions, comprehensions, and assignments.

### Tests
- [ ] `tests/unit/test_ast_sentinel.py` passes all cases.
- [ ] 95%+ coverage on new file.

### Documentation
- [ ] Docstrings on all Visitor methods.
- [ ] LLD updated with any scope edge case decisions.

### Review
- [ ] Code review completed.

### 12.1 Traceability (Mechanical - Auto-Checked)

- `assemblyzero/core/validation/ast_sentinel.py` (Section 2.1)
- `tools/validate_mechanical.py` (Section 2.1)
- `tests/unit/test_ast_sentinel.py` (Section 2.1)
- `ImportSentinel` (Section 2.4)
- Risks handled by scope logic.

---

## Appendix: Review Log

### Gemini Review #1 (PENDING)

**Reviewer:** Gemini
**Verdict:** PENDING

#### Comments
*Waiting for submission.*

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| Gemini #1 | (auto) | PENDING | - |

**Final Status:** PENDING