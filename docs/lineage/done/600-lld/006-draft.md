# 600 - Feature: AST-Based Import Sentinel

<!-- Template Metadata
Last Updated: 2026-02-02
Updated By: Issue #117 fix
Update Reason: Moved Verification & Testing to Section 10 (was Section 11) to match 0702c review prompt and testing workflow expectations
Previous: Added sections based on 80 blocking issues from 164 governance verdicts (2026-02-01)
-->

## 1. Context & Goal
* **Issue:** #600
* **Objective:** Enhance mechanical validation to strictly catch "Lingering Symbols" (missing imports or undefined variables) before execution using AST analysis to block invalid code from wasting LLM tokens.
* **Status:** Draft
* **Related Issues:** #587

## 2. Proposed Changes

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `assemblyzero/core/validation/ast_sentinel.py` | Add | Core AST traversal, scope tracking, and validation logic. |
| `assemblyzero/workflows/requirements/nodes/validate_mechanical.py` | Modify | Integrate the AST sentinel to run on all modified Python files. |
| `tests/unit/test_ast_sentinel.py` | Add | Unit tests for AST symbol validation and edge cases. |

### [UNCHANGED] 2.1.1 Path Validation (Mechanical - Auto-Checked)

### [UNCHANGED] 2.2 Dependencies

### [UNCHANGED] 2.3 Data Structures

### [UNCHANGED] 2.4 Function Signatures

### [UNCHANGED] 2.5 Logic Flow (Pseudocode)

### [UNCHANGED] 2.6 Technical Approach

### 2.7 Architecture Decisions

| Decision | Options Considered | Choice | Rationale |
|----------|-------------------|--------|-----------|
| Parser Engine | Regex, `ast` module, `symtable` module | `ast` module | `ast` provides exact line numbers and node contexts, avoiding the brittleness of regex. |
| Scope Tracking | Flat tracking, Stack-based scoping | Stack-based scoping | Necessary to handle local variables inside functions so we don't falsely flag local variables as missing. |

**Architectural Constraints:**
- Must not introduce significant latency to the mechanical validation gate.
- Must not require downloading external linter binaries.

## 3. Requirements

1. Must parse the target file using `ast.parse` and walk nodes using `ast.NodeVisitor`.
2. Every `ast.Name` node with `ctx=ast.Load()` must correspond to an `ast.Import`, `ast.ImportFrom`, built-in function, or local assignment/definition.
3. Errors must specifically state: "Symbol '{name}' used on line {line} but not imported."
4. Must be invoked directly within `assemblyzero/workflows/requirements/nodes/validate_mechanical.py` and strictly fail the validation gate (exit 1) rather than emitting a warning.
5. Must use fully recursive, stack-based scope tracking to seamlessly handle nested functions, classes, lambdas, all comprehensions (list, set, dict, generator), and Python 3.8+ Walrus operators (`:=`) to minimize false positives.

## 4. Alternatives Considered

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| External Linter (Flake8) | Extremely robust, handles all edge cases | Heavy dependency, output formatting is rigid, overkill for token-saving gate | **Rejected** |
| AST module (`ast`) | Zero dependencies, highly customizable output, fast | Requires manual scope tracking | **Selected** |
| Regex parsing | Simple to write initially | Cannot handle scopes, multi-line imports, or distinguishing strings from code | **Rejected** |

**Rationale:** The `ast` module gives us the precise control needed to format LLM-friendly feedback while keeping the validation gate lightweight and fast.

## 5. Data & Fixtures

### 5.1 Data Sources

| Attribute | Value |
|-----------|-------|
| Source | Local Python source files modified in the active worktree |
| Format | `.py` code |
| Size | Typically < 1000 LOC per file |
| Refresh | Real-time during mechanical validation |
| Copyright/License | N/A |

### [UNCHANGED] 5.2 Data Pipeline

### [UNCHANGED] 5.3 Test Fixtures

### [UNCHANGED] 5.4 Deployment Pipeline

## [UNCHANGED] 6. Diagram

### [UNCHANGED] 6.1 Mermaid Quality Gate

### [UNCHANGED] 6.2 Diagram

## [UNCHANGED] 7. Security & Safety Considerations

### [UNCHANGED] 7.1 Security

### 7.2 Safety

| Concern | Mitigation | Status |
|---------|------------|--------|
| Malformed Python causing crash | Wrap `ast.parse` in a `try/except SyntaxError`. Return clean early exit (syntax errors caught elsewhere). | Addressed |
| False positives blocking valid code | Track scopes strictly. Ensure Python `builtins` are pre-loaded into the base scope. Handle edge case syntax gracefully. | Addressed |

**Fail Mode:** Fail Closed - If undefined variables are detected, the mechanical validation must fail to prevent broken code from proceeding to expensive LLM reviews or testing.
**Recovery Strategy:** The LLM receives the exact line number and symbol name, allowing an immediate targeted fix (e.g., adding the missing import).

## 8. Performance & Cost Considerations

### 8.1 Performance

| Metric | Budget | Approach |
|--------|--------|----------|
| Latency | < 100ms per file | `ast.parse` is written in C and executes in microseconds. Flat AST traversal is computationally trivial. |
| Memory | < 50MB overhead | Memory is limited to the AST tree representation for a single file at a time. |
| API Calls | 0 | Pure local execution. |

**Bottlenecks:** None expected. AST traversal of standard-sized Python files is exceptionally fast.

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
| T050 | Mechanical Gate integration | Gate exits non-zero (`sys.exit(1)`) strictly and prints specific feedback | RED |
| T060 | Comprehension scope tracking | Parses targets in list, dict, set, and generator comprehensions dynamically | RED |
| T070 | Walrus operators (`:=`) | Recognizes named assignment targets dynamically within expression bodies | RED |

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
| 030 | Feedback specifically stated (REQ-3) | Auto | Code with missing import | `[SentinelError]` | Exact string: "Symbol 'json' used on line X but not imported." |
| 040 | Integration with mechanical validation (REQ-4) | Auto | Running gate on bad file | `sys.exit(1)` | Strictly fails the gate check |
| 050 | Local definition nested scope resilience (REQ-5) | Auto | Code with `def foo(a): b = a; return b` | `[]` | Function arguments, nested functions, and lambdas recognized |
| 060 | Comprehensions (REQ-5) | Auto | Code with `[x for x in y]` and `{k:v for k,v in z.items()}` | `[]` | Targets correctly isolated as local within comprehension scope |
| 070 | Walrus Operators (REQ-5) | Auto | Code with `if (n := len(a)) > 1: print(n)` | `[]` | `n` is correctly identified as a local variable |

### 10.2 Test Commands

```bash

# Run the specific tests for the Sentinel
poetry run pytest tests/unit/test_ast_sentinel.py -v

# Run gate integration tests
poetry run pytest tests/unit/test_gate/ -v
```

### [UNCHANGED] 10.3 Manual Tests (Only If Unavoidable)

## [UNCHANGED] 11. Risks & Mitigations

## [UNCHANGED] 12. Definition of Done

### Code
- [ ] Implementation complete and linted
- [ ] Code comments reference this LLD

### Tests
- [ ] All test scenarios pass
- [ ] Test coverage meets threshold (≥95%)

### Documentation
- [ ] LLD updated with any deviations
- [ ] Implementation Report (0103) completed
- [ ] Test Report (0113) completed if applicable

### [UNCHANGED] Review

### [UNCHANGED] 12.1 Traceability (Mechanical - Auto-Checked)

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

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| Orchestrator #1 | (auto) | FEEDBACK | Fixed mechanical path error. Added recursive comprehension tracking, walrus tracking, and strictly failing logic. |

**Final Status:** PENDING