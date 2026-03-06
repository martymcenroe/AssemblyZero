# 600 - Feature: AST-Based Import Sentinel

<!-- Template Metadata
Last Updated: 2026-02-02
Updated By: Issue #117 fix
Update Reason: Moved Verification & Testing to Section 10 (was Section 11) to match 0702c review prompt and testing workflow expectations
Previous: Added sections based on 80 blocking issues from 164 governance verdicts (2026-02-01)
-->

## 1. Context & Goal
* **Issue:** #600
* **Objective:** Enhance mechanical validation to strictly catch "Lingering Symbols" (missing imports or undefined variables) before execution using AST analysis. It must explicitly fail the mechanical gate (exit 1) via `sys.stderr`, robustly handle nested scopes, `global`/`nonlocal` declarations, type-checking blocks, explicitly ban star imports, and support a line-level bypass mechanism.
* **Status:** Draft
* **Related Issues:** #587

## 2. Proposed Changes

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `assemblyzero/workflows/requirements/nodes/validate_mechanical.py` | Modify | Integrate the new AST Sentinel check and exit 1 strictly on failure. |
| `assemblyzero/utils/ast_sentinel.py` | Add | Core AST parsing logic and visitor for scope, global/nonlocal, and import tracking. |
| `tests/unit/test_ast_sentinel.py` | Add | Unit tests for AST Sentinel logic, including scopes, comprehensions, and star imports. |

### [UNCHANGED] 2.2 Dependencies

### [UNCHANGED] 2.3 Data Structures

### [UNCHANGED] 2.4 Function Signatures

### [UNCHANGED] 2.5 Logic Flow (Pseudocode)

### [UNCHANGED] 2.6 Technical Approach

### 2.7 Architecture Decisions

| Decision | Options Considered | Choice | Rationale |
|----------|-------------------|--------|-----------|
| Parser Engine | Regex, `ast` module, `symtable` module | `ast` module | `ast` provides exact line numbers and node contexts, avoiding the brittleness of regex. |
| Scope Tracking | Flat tracking, Stack-based scoping | Stack-based scoping | Necessary to handle local variables inside nested scopes (functions, comprehensions, and walrus operators) so we don't falsely flag local variables as missing. |

**Architectural Constraints:**
- Must not introduce significant latency to the mechanical validation gate.
- Must not require downloading external linter binaries.

## 3. Requirements

1. Must parse the target file using `ast.parse` and walk nodes using `ast.NodeVisitor`.
2. Every `ast.Name` node with `ctx=ast.Load()` must correspond to an `ast.Import`, `ast.ImportFrom`, built-in function, or local assignment/definition.
3. Errors must specifically state: "Symbol '{name}' used on line {line} but not imported." and be printed directly to `sys.stderr` for clean CI/CD capture.
4. Must be invoked directly within `assemblyzero/workflows/requirements/nodes/validate_mechanical.py` and strictly fail the validation gate (`sys.exit(1)`) if any un-ignored errors are found.
5. Must use fully recursive, stack-based scope tracking to seamlessly handle nested functions, classes, lambdas, comprehensions (list, set, dict, generator), Walrus operators (`:=`), and dynamically respect `global` and `nonlocal` declarations to minimize false positives.
6. **Star Imports:** Must explicitly ban star imports (e.g., `from typing import *`). If an `ast.ImportFrom` contains a `*` alias, the sentinel must immediately fail the gate with a specific error: "Star imports are not allowed: line {line}."
7. **Type Hinting Scopes:** Must gracefully handle imports defined within `if TYPE_CHECKING:` blocks, registering them as valid symbols for the rest of the module to support Python type annotations.
8. **Bypass Mechanism:** Must support `# sentinel: disable-line` comments. If a line containing an undefined symbol also contains this exact comment substring, the error for that specific line must be suppressed.

## 4. Alternatives Considered

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| External Linter (Flake8) | Extremely robust, handles all edge cases | Heavy dependency, output formatting is rigid, overkill for token-saving gate | **Rejected** |
| AST module (`ast`) | Zero dependencies, highly customizable output, fast | Requires manual scope tracking | **Selected** |
| Regex parsing | Simple to write initially | Cannot handle scopes, multi-line imports, or distinguishing strings from code | **Rejected** |

**Rationale:** The `ast` module gives us the precise control needed to format LLM-friendly feedback while keeping the validation gate lightweight and fast.

## [UNCHANGED] 5. Data & Fixtures

### [UNCHANGED] 5.1 Data Sources

### [UNCHANGED] 5.2 Data Pipeline

### [UNCHANGED] 5.3 Test Fixtures

### [UNCHANGED] 5.4 Deployment Pipeline

## [UNCHANGED] 6. Diagram

### [UNCHANGED] 6.1 Mermaid Quality Gate

### [UNCHANGED] 6.2 Diagram

## [UNCHANGED] 7. Security & Safety Considerations

### [UNCHANGED] 7.1 Security

### [UNCHANGED] 7.2 Safety

## [UNCHANGED] 8. Performance & Cost Considerations

### [UNCHANGED] 8.1 Performance

### [UNCHANGED] 8.2 Cost Analysis

## 9. Legal & Compliance

| Concern | Applies? | Mitigation |
|---------|----------|------------|
| PII/Personal Data | No | AST parsing operates only on structural source code locally. |
| Third-Party Licenses | No | Uses only Python standard library `ast`. |
| Terms of Service | No | Runs entirely locally. |
| Data Retention | N/A | No data stored; transient parsing. |
| Export Controls | N/A | Internal tool extension. |

**Data Classification:** Internal (Source Code)

**Compliance Checklist:**
- [x] No PII stored without consent
- [x] All third-party licenses compatible with project license
- [x] External API usage compliant with provider ToS
- [x] Data retention policy documented

## 10. Verification & Testing

### 10.0 Test Plan (TDD - Complete Before Implementation)

| Test ID | Test Description | Expected Behavior | Status |
|---------|------------------|-------------------|--------|
| T010 | Valid code with imports | Returns empty error list | RED |
| T020 | Code with missing import | Returns `SentinelError` with correct line number | RED |
| T030 | Code using Python builtins | Ignores `print`, `len`, `Exception`, returns empty list | RED |
| T040 | Complex scope (locals) | Recognizes locally assigned variables recursively, returns empty list | RED |
| T050 | Mechanical Gate integration | Gate exits non-zero (`sys.exit(1)`) strictly and prints specific feedback to `sys.stderr` | RED |
| T060 | Comprehension scope tracking | Parses targets in list, dict, set, and generator comprehensions dynamically | RED |
| T070 | Walrus operators (`:=`) | Recognizes named assignment targets dynamically within expression bodies | RED |
| T080 | Star import rejection | Fails validation with specific "Star imports are not allowed" message | RED |
| T090 | Global and Nonlocal | Respects `global` and `nonlocal` scope declarations, preventing false positives | RED |
| T100 | TYPE_CHECKING scope | Recognizes symbols imported under `if TYPE_CHECKING:` blocks | RED |
| T110 | Disable line comment | Ignores missing symbols on lines containing `# sentinel: disable-line` | RED |

**Coverage Target:** ≥95% for all new code in `ast_sentinel.py`.

**TDD Checklist:**
- [ ] All tests written before implementation
- [ ] Tests currently RED (failing)
- [ ] Test IDs match scenario IDs in 10.1
- [ ] Test file created at: `tests/unit/test_ast_sentinel.py`

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | Happy path valid AST Analysis (REQ-1) | Auto | Code with `import os; os.path.join()` | `[]` | No errors emitted |
| 020 | Missing import verified (REQ-2) | Auto | Code with `json.dumps({})` but no import | `[SentinelError]` | Errors emitted correctly |
| 030 | Feedback specifically stated to stderr (REQ-3) | Auto | Code with missing import | `sys.stderr` output | Exact string: "Symbol 'json' used on line X but not imported." in stderr |
| 040 | Integration with mechanical validation (REQ-4) | Auto | Running gate on bad file | `sys.exit(1)` | Strictly fails the gate check |
| 050 | Local definition nested scope resilience (REQ-5) | Auto | Code with `def foo(a): b = a; return b` | `[]` | Function arguments, nested functions, and lambdas recognized |
| 060 | Comprehensions (REQ-5) | Auto | Code with `[x for x in y]` and `{k:v for k,v in z.items()}` | `[]` | Targets correctly isolated as local within comprehension scope |
| 070 | Walrus Operators (REQ-5) | Auto | Code with `if (n := len(a)) > 1: print(n)` | `[]` | `n` is correctly identified as a local variable |
| 080 | Star imports banned (REQ-6) | Auto | Code with `from typing import *` | `[SentinelError]` | Gate fails explicitly citing star import restriction |
| 090 | Global/Nonlocal tracking (REQ-5) | Auto | Code declaring `global x` or `nonlocal y` | `[]` | Variables are correctly resolved without false positives |
| 100 | TYPE_CHECKING support (REQ-7) | Auto | Code importing under `if TYPE_CHECKING:` | `[]` | Type hints using these imports do not flag as missing |
| 110 | Ignore comments (REQ-8) | Auto | `undefined_var # sentinel: disable-line` | `[]` | No error emitted for `undefined_var` on that specific line |

### 10.2 Test Commands

```bash

# Run the specific tests for the Sentinel
poetry run pytest tests/unit/test_ast_sentinel.py -v

# Run gate integration tests
poetry run pytest tests/unit/test_gate/ -v
```

### 10.3 Manual Tests (Only If Unavoidable)

N/A - All scenarios automated.

## 11. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| False positives blocking valid code | High | Medium | Implement robust, fully recursive AST scope tracking handling comprehensions, lambdas, `global`/`nonlocal` keywords, and Python 3.8+ Walrus operators. Ensure Python `builtins` are properly loaded. |
| Star imports obfuscate symbols (`from x import *`) | High | High | Explicitly ban star imports at the AST level (fail gate if `*` is used), as a single-pass static analyzer cannot reliably resolve them. |
| `TYPE_CHECKING` blocks causing false positives | Medium | High | Add explicit logic in the AST visitor to treat imports inside `if TYPE_CHECKING:` (or similar type-hinting conditionals) as globally available within the module. |
| Dynamic resolution (`getattr`, `locals()`) flags as missing | Medium | Medium | Implement a fallback ignore mechanism (`# sentinel: disable-line`) to allow developers to bypass the sentinel for highly dynamic, un-analyzable lines. |
| Parser fails on valid syntax | Medium | Low | Wrap parsing in `try/except SyntaxError` and handle gracefully, delegating the catch to existing syntactical validation tools. |
| Performance overhead on large files | Low | Low | Use the built-in C-based `ast` module which operates in microseconds. Process each file in isolation. |

## 12. Definition of Done

### Code
- [ ] Implementation complete and linted
- [ ] Code comments reference this LLD
- [ ] AST traversal cleanly handles fully recursive scopes, `global`, and `nonlocal` declarations
- [ ] Star imports explicitly trigger validation failures
- [ ] `TYPE_CHECKING` blocks are parsed and imports registered
- [ ] `# sentinel: disable-line` logic successfully filters errors

### Tests
- [ ] All test scenarios pass (including Star Imports, TYPE_CHECKING, Global/Nonlocal, and Disable Comments)
- [ ] Test coverage meets threshold (≥95%)
- [ ] Errors are verified to print to `sys.stderr`

### Documentation
- [ ] LLD updated with any deviations
- [ ] Implementation Report (0103) completed
- [ ] Test Report (0113) completed if applicable

### [UNCHANGED] 12.1 Traceability

## Appendix: Review Log

### Orchestrator Review #1 (FEEDBACK)

**Reviewer:** Automated Validation
**Verdict:** FEEDBACK

#### Comments

| ID | Comment | Implemented? |
|----|---------|--------------|
| R1.1 | "File marked Modify but does not exist: assemblyzero/core/validation/validate_mechanical.py. Did you mean: `assemblyzero/workflows/requirements/nodes/validate_mechanical.py`?" | YES - Updated path in Section 2.1 |
| R1.2 | [BLOCKING] Missing test coverage for list comprehensions (REQ-5). Scenario 050's input only tests nested function scope. | YES - Added T060 / Test Scenario 060. |
| R1.3 | Sentinel MUST fail the validation strictly (exit 1), not just emit a warning. | YES - Addressed in 3. Requirements (REQ-4). |
| R1.4 | Scope tracking must be fully recursive and stack-based for all nested items. | YES - Updated REQ-5 and Test Scenarios. |
| R1.5 | Consider adding a specific test scenario for Python 3.8+ Walrus operators (:=). | YES - Added T070 / Test Scenario 070. |

### Orchestrator Review #2 (FEEDBACK)

**Reviewer:** Automated Validation
**Verdict:** FEEDBACK

#### Comments

| ID | Comment | Implemented? |
|----|---------|--------------|
| R2.1 | [BLOCKING] A single-file AST pass cannot statically resolve star imports. Must explicitly ban star imports. | YES - Added REQ-6, T080, and updated Risks. |
| R2.2 | [BLOCKING] No scope tracking for 'global' and 'nonlocal' statements. Bypass flat tracking. | YES - Updated REQ-5, added T090, and Test Scenario 090. |
| R2.3 | [HIGH] Type hinting scopes (`if TYPE_CHECKING:`) require special handling to prevent false positives. | YES - Added REQ-7, T100, and Test Scenario 100. |
| R2.4 | [SUGGESTION] Ensure 'sys.exit(1)' failure emits specifically to 'sys.stderr'. | YES - Updated REQ-3, REQ-4, and Test Scenario 030. |
| R2.5 | [SUGGESTION] Consider an ignore-comment fallback (`# sentinel: disable-line`) for dynamic edge cases. | YES - Added REQ-8, T110, and Test Scenario 110. |