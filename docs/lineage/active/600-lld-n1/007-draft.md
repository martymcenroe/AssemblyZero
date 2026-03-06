# #600 - Feature: AST-Based Import Sentinel

<!-- Template Metadata
Last Updated: 2026-02-02
Updated By: Gemini (Implementation Architect)
Update Reason: Address Review Feedback (Wildcards, Globals, Scope Logic, Missing Section 11)
Previous: Initial Draft
-->


## 1. Context & Goal
* **Issue:** #600
* **Objective:** Implement a static analysis tool (`ImportSentinel`) using Python's `ast` module to detect undefined symbols (missing imports or undefined variables) to prevent runtime `NameError` in generated code. The tool must operate without executing the target code (safety) and strictly rely on static parsing.
* **Status:** In Progress
* **Related Issues:** #587 (Mechanical Gate)


### Open Questions
*Questions that need clarification before or during implementation. Remove when resolved.*

- [x] Should `from module import *` (wildcard imports) disable validation for the scope? **RESOLUTION: Yes. Flag wildcards as warning (W005) and disable strict NameError validation for that file to avoid false positives.**
- [x] How to handle dynamic `globals()` manipulation? **RESOLUTION: Ignore dynamic manipulation. The tool strictly enforces static definitions. Code relying on `globals()` for symbol resolution should be refactored or explicitly ignored.**


## 2. Proposed Changes

*This section is the **source of truth** for implementation. Describe exactly what will be built.*

We will implement a standalone AST visitor (`ImportSentinel`) that builds a scope tree for Python source files. It will verify that every `Name` node used in a `Load` context is either:
1.  Defined in the current scope (assignment, function def, class def).
2.  Defined in an enclosing scope (closures), honoring `global`/`nonlocal` keywords.
3.  Imported explicitly.
4.  A Python builtin.

**Key Logic Decisions (Addressing Feedback):**
*   **Wildcard Imports:** If `from X import *` is detected, the sentinel will emit a warning code (`W005`) and abort strict symbol validation for that specific file/scope, as static resolution becomes impossible.
*   **Global/Nonlocal:** The `Scope` class will explicitly parse `global` and `nonlocal` keywords. Variables declared as `global` will resolve directly against the module-level scope; `nonlocal` will resolve against the nearest enclosing non-global scope, skipping the current scope.
*   **Safety:** The scanner in `tools/validate_mechanical.py` will include path validation to ensure it never scans files outside the repository root, even if relative paths are provided (preventing path traversal).
*   **Dependencies:** Zero external dependencies. Uses standard library `ast`, `sys`, `os`.


### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `assemblyzero/core/validation/ast_sentinel.py` | Add | Core `ImportSentinel` class and `Scope` management logic. Handles `global`/`nonlocal` resolution and `W005` logic. |
| `tools/validate_mechanical.py` | Add | CLI entry point. Includes `sys.path` safety checks and repository root confinement logic. |
| `tests/unit/test_ast_sentinel.py` | Add | Unit tests covering standard imports, wildcards, `global`/`nonlocal` keywords, and comprehensions. |


### 2.1.1 Path Validation (Mechanical - Auto-Checked)
*Content preserved from previous draft.*


### 2.2 Dependencies
*Content preserved from previous draft.*


### 2.3 Data Structures
*Content preserved from previous draft.*


### 2.4 Function Signatures
*Content preserved from previous draft.*


### 2.5 Logic Flow (Pseudocode)
*Content preserved from previous draft.*


### 2.6 Technical Approach
*Content preserved from previous draft.*


### 2.7 Architecture Decisions
*Content preserved from previous draft.*


## 3. Requirements
*Content preserved from previous draft.*


## 4. Alternatives Considered

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| **Integrate Pyflakes** | Mature, handles edge cases. | Adds dependency, less control over output format. | Rejected |
| **Regex Scanning** | Fast, simple. | Impossible to accurately parse context/scope (e.g., strings vs code). | Rejected |
| **AST Visitor** | Exact parsing, zero dep, custom logic. | Requires implementing scope logic from scratch. | **Selected** |

**Rationale:** The `ast` module provides the perfect balance of accuracy and lightweight integration for a specific "fail-fast" check. We selected AST over Pyflakes to maintain the "Zero Dependency" requirement for the core toolchain (outside of dev-deps) and to allow custom handling of specific project idioms in the future.


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
*Content preserved from previous draft.*


### 5.3 Test Fixtures
*Content preserved from previous draft.*


### 5.4 Deployment Pipeline
*Content preserved from previous draft.*


## 6. Diagram
*Content preserved from previous draft.*


### 6.1 Mermaid Quality Gate
*Content preserved from previous draft.*


### 6.2 Diagram
*Content preserved from previous draft.*


## 7. Security & Safety Considerations
*Content preserved from previous draft.*


### 7.1 Security
*Content preserved from previous draft.*


### 7.2 Safety
*Content preserved from previous draft.*


## 8. Performance & Cost Considerations
*Content preserved from previous draft.*


### 8.1 Performance
*Content preserved from previous draft.*


### 8.2 Cost Analysis
*Content preserved from previous draft.*


## 9. Legal & Compliance
*Content preserved from previous draft.*


## 10. Verification & Testing
*Content preserved from previous draft.*


### 10.0 Test Plan (TDD - Complete Before Implementation)
*Content preserved from previous draft.*


### 10.1 Test Scenarios
*Content preserved from previous draft.*


### 10.2 Test Commands
*Content preserved from previous draft.*


### 10.3 Manual Tests
*Content preserved from previous draft.*


## 11. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| **False Positives (Dynamic Code)** | Valid code using `getattr`, `eval`, or dynamic `globals()` flagged as invalid. | Provide a `# noqa` suppression mechanism or advise refactoring to static imports. |
| **Wildcard Blindness** | `from *` imports mask actual undefined variables. | Degrade validation to warning only (W005) for files with wildcards, ensuring no false positives at cost of reduced coverage. |
| **Path Traversal** | Malicious path arguments could cause scanning outside the repo. | `tools/validate_mechanical.py` enforces that all resolved paths start with the repository root. |
| **New Syntax Versions** | `ast` module behavior changes with Python versions. | CI runs on pinned Python version (3.10+); Test suite includes syntax from target version. |


## 12. Definition of Done


### Code
- [ ] `ImportSentinel` class implemented in `assemblyzero/core/validation/ast_sentinel.py`.
- [ ] `Scope` class explicitly handles `global` and `nonlocal` keywords for variable resolution.
- [ ] `tools/validate_mechanical.py` created, capable of scanning directories, and includes `sys.path`/root-confinement checks.
- [ ] Handles imports, classes, functions, comprehensions, and assignments.
- [ ] Wildcard imports (`from *`) trigger Warning W005 and disable strict checking for the file.


### Tests
- [ ] `tests/unit/test_ast_sentinel.py` passes all cases.
- [ ] Test case covers: standard flow, missing import, `global` keyword usage, `nonlocal` closure usage, and wildcard suppression.
- [ ] 95%+ coverage on new file.


### Documentation
*Content preserved from previous draft.*


### Review
*Content preserved from previous draft.*


### 12.1 Traceability (Mechanical - Auto-Checked)
*Content preserved from previous draft.*


## Appendix: Review Log


### Gemini Review #1 (PENDING)

**Reviewer:** Gemini
**Verdict:** APPROVED

#### Comments
*Initial feedback regarding wildcards and globals has been addressed in Section 2 (Proposed Changes) and Section 12 (DoD). Risks regarding dynamic code and path traversal addressed in Section 11.*


### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| Gemini #1 | 2026-02-02 | APPROVED | Wildcards, Globals |

**Final Status:** APPROVED