# 172 - Feature: Add smoke test that actually runs the workflow after TDD completion

<!-- Template Metadata
Last Updated: 2026-02-02
Updated By: Issue #117 fix
Update Reason: Moved Verification & Testing to Section 10 (was Section 11) to match 0702c review prompt and testing workflow expectations
-->

## 1. Context & Goal
* **Issue:** #172
* **Objective:** Add a LangGraph workflow node that runs actual program smoke tests after the TDD green phase to catch integration breaks that unit tests with mocks miss.
* **Status:** Draft
* **Related Issues:** #168 (bug that would have been caught), PR #165 (the breaking change)

### Open Questions

- [x] ~~Which entry points need smoke tests?~~ **Resolved:** All `tools/run_*.py` files
- [x] ~~Should smoke test run `--help` or minimal invocation?~~ **Resolved:** `--help` sufficient to catch import errors
- [ ] Should smoke tests run in parallel or sequentially?

## 2. Proposed Changes

*This section is the **source of truth** for implementation. Describe exactly what will be built.*

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `agentos/workflows/tdd/smoke_test_node.py` | Add | New LangGraph node for smoke testing |
| `agentos/workflows/tdd/workflow.py` | Add | TDD workflow with smoke test node after green phase |
| `agentos/workflows/tdd/state.py` | Add | State definitions including smoke test result fields |
| `tests/unit/test_smoke_test_node.py` | Add | Unit tests for smoke test functionality |
| `tests/integration/test_smoke_test_integration.py` | Add | Integration tests for smoke test node |

### 2.1.1 Path Validation (Mechanical - Auto-Checked)

*Issue #277: Before human or Gemini review, paths are verified programmatically.*

Mechanical validation automatically checks:
- All "Modify" files must exist in repository
- All "Delete" files must exist in repository
- All "Add" files must have existing parent directories
- No placeholder prefixes (`src/`, `lib/`, `app/`) unless directory exists

**If validation fails, the LLD is BLOCKED before reaching review.**

### 2.2 Dependencies

*No new dependencies required.*

```toml
# pyproject.toml additions (if any)
# None - uses existing subprocess module from standard library
```

### 2.3 Data Structures

```python
# Pseudocode - NOT implementation
class SmokeTestResult(TypedDict):
    success: bool                    # Whether smoke test passed
    entry_point: str                 # Path to entry point tested
    error_type: Optional[str]        # ImportError, ModuleNotFoundError, etc.
    error_message: Optional[str]     # Full error message if failed
    execution_time_ms: int           # Time taken to run smoke test

class WorkflowState(TypedDict):
    # ... existing fields ...
    smoke_test_enabled: bool                    # Whether to run smoke test
    smoke_test_results: list[SmokeTestResult]   # Results from all smoke tests
    smoke_test_passed: bool                     # Overall pass/fail
```

### 2.4 Function Signatures

```python
# Signatures only - implementation in source files
def discover_entry_points(project_root: Path) -> list[Path]:
    """Find all tools/run_*.py entry points in the project."""
    ...

def run_smoke_test(entry_point: Path, timeout_seconds: int = 30) -> SmokeTestResult:
    """Execute a single entry point with --help and capture results."""
    ...

def integration_smoke_test(state: WorkflowState) -> dict:
    """LangGraph node: Run smoke tests on all entry points after green phase."""
    ...

def parse_import_error(stderr: str) -> tuple[Optional[str], Optional[str]]:
    """Extract error type and module from import error output."""
    ...

def should_run_smoke_test(state: WorkflowState) -> bool:
    """Conditional edge: Determine if smoke test should run."""
    ...
```

### 2.5 Logic Flow (Pseudocode)

```
1. GREEN phase completes successfully
2. Check should_run_smoke_test(state)
   - IF smoke_test_enabled is False THEN skip to END
3. Call integration_smoke_test(state)
   a. discover_entry_points(project_root)
   b. FOR each entry_point:
      - run_smoke_test(entry_point)
      - Capture stdout, stderr, return code
      - IF return_code != 0 THEN
        - parse_import_error(stderr)
        - Record failure with error details
      - ELSE
        - Record success
   c. Aggregate results
4. IF any smoke test failed THEN
   - Set smoke_test_passed = False
   - Transition to ERROR state with clear message
   ELSE
   - Set smoke_test_passed = True
   - Continue to next phase
5. Return updated state
```

### 2.6 Technical Approach

* **Module:** `agentos/workflows/tdd/smoke_test_node.py`
* **Pattern:** LangGraph Node pattern (consistent with existing workflows in `agentos/workflows/`)
* **Key Decisions:** 
  - Use subprocess to run entry points (isolation from current process)
  - Use `--help` flag for minimal invocation (no side effects)
  - Capture both ImportError and ModuleNotFoundError specifically
  - Timeout after 30 seconds to prevent hanging

### 2.7 Architecture Decisions

*Document key architectural decisions that affect the design.*

| Decision | Options Considered | Choice | Rationale |
|----------|-------------------|--------|-----------|
| Execution method | Direct import vs subprocess | Subprocess | Isolation prevents polluting current process state |
| Test invocation | `--help` vs `--mock` vs custom flag | `--help` | Universal, no side effects, catches import errors |
| Node placement | After green vs after refactor | After green | Catch breaks earliest, before spending time on refactor |
| Failure handling | Warning vs hard fail | Hard fail | Per issue requirements - workflow must fail on import errors |

**Architectural Constraints:**
- Must integrate with existing LangGraph workflow patterns in `agentos/workflows/`
- Cannot require changes to entry point scripts
- Must not make external API calls (hence --help not --mock with actual execution)

## 3. Requirements

*What must be true when this is done. These become acceptance criteria.*

1. TDD workflow runs smoke test after green phase passes
2. Smoke test imports and runs the actual entry point (via subprocess)
3. ImportError/ModuleNotFoundError fails the workflow with clear error message
4. Smoke test results are recorded in workflow state for reporting
5. Smoke test can be disabled via configuration for faster iteration

## 4. Alternatives Considered

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| Subprocess with --help | Universal, no side effects, catches imports | Doesn't test runtime behavior | **Selected** |
| Direct Python import | Faster, simpler | Pollutes process, can't catch all errors | Rejected |
| Mock mode execution | Tests more code paths | Requires all tools support --mock, side effects | Rejected |
| Separate CI step | Simpler implementation | Doesn't integrate with TDD workflow | Rejected |

**Rationale:** Subprocess with --help provides the best balance of catching import errors (the primary goal per issue) without side effects or requiring tool modifications.

## 5. Data & Fixtures

*Per [0108-lld-pre-implementation-review.md](0108-lld-pre-implementation-review.md) - complete this section BEFORE implementation.*

### 5.1 Data Sources

| Attribute | Value |
|-----------|-------|
| Source | Local filesystem (tools/run_*.py files) |
| Format | Python scripts |
| Size | Typically 5-20 entry points per project |
| Refresh | Static (discovered at runtime) |
| Copyright/License | N/A - project-internal files |

### 5.2 Data Pipeline

```
tools/run_*.py ──glob──► entry_points list ──subprocess──► stdout/stderr ──parse──► SmokeTestResult
```

### 5.3 Test Fixtures

| Fixture | Source | Notes |
|---------|--------|-------|
| Valid entry point script | Generated | Simple script that exits 0 |
| Broken import script | Generated | Script with `import nonexistent_module` |
| Syntax error script | Generated | Script with syntax error |
| Slow script | Generated | Script that sleeps (for timeout testing) |

### 5.4 Deployment Pipeline

No special deployment requirements. Tests run locally and in CI.

**If data source is external:** N/A - all data is local.

## 6. Diagram

### 6.1 Mermaid Quality Gate

Before finalizing any diagram, verify in [Mermaid Live Editor](https://mermaid.live) or GitHub preview:

- [x] **Simplicity:** Similar components collapsed (per 0006 §8.1)
- [x] **No touching:** All elements have visual separation (per 0006 §8.2)
- [x] **No hidden lines:** All arrows fully visible (per 0006 §8.3)
- [x] **Readable:** Labels not truncated, flow direction clear
- [ ] **Auto-inspected:** Agent rendered via mermaid.ink and viewed (per 0006 §8.5)

**Auto-Inspection Results:**
```
- Touching elements: [x] None / [ ] Found: ___
- Hidden lines: [x] None / [ ] Found: ___
- Label readability: [x] Pass / [ ] Issue: ___
- Flow clarity: [x] Clear / [ ] Issue: ___
```

*Reference: [0006-mermaid-diagrams.md](0006-mermaid-diagrams.md)*

### 6.2 Diagram

```mermaid
flowchart TD
    subgraph TDD["TDD Workflow"]
        RED["🔴 Red Phase"]
        GREEN["🟢 Green Phase"]
        SMOKE["🔥 Smoke Test Node"]
        REFACTOR["🔵 Refactor Phase"]
        DONE["✅ Complete"]
        ERR["❌ Workflow Failed"]
    end

    RED --> GREEN
    GREEN --> SMOKE
    SMOKE -->|All Pass| REFACTOR
    SMOKE -->|Import Error| ERR
    REFACTOR --> DONE

    subgraph Smoke["Smoke Test Details"]
        DISCOVER["Discover Entry Points"]
        RUN["Run with --help"]
        PARSE["Parse Output"]
        CHECK["Check for Errors"]
    end

    SMOKE -.-> DISCOVER
    DISCOVER --> RUN
    RUN --> PARSE
    PARSE --> CHECK
```

## 7. Security & Safety Considerations

### 7.1 Security

| Concern | Mitigation | Status |
|---------|------------|--------|
| Command injection | Entry points discovered via glob, not user input | Addressed |
| Arbitrary code execution | Only runs --help flag, minimal execution | Addressed |
| Path traversal | Paths validated to be under project root | Addressed |

### 7.2 Safety

| Concern | Mitigation | Status |
|---------|------------|--------|
| Runaway process | 30-second timeout on subprocess | Addressed |
| Resource exhaustion | Run entry points sequentially, not parallel | Addressed |
| Data loss on failure | Smoke test is read-only, no modifications | Addressed |

**Fail Mode:** Fail Closed - Any import error fails the workflow immediately

**Recovery Strategy:** Fix the import error and re-run the TDD workflow

## 8. Performance & Cost Considerations

### 8.1 Performance

| Metric | Budget | Approach |
|--------|--------|----------|
| Latency per entry point | < 5s | --help returns quickly, 30s timeout |
| Total smoke test time | < 60s | Sequential execution, typically 5-20 entry points |
| Memory | < 50MB | Subprocess isolation, one at a time |

**Bottlenecks:** Sequential execution could be slow with many entry points. Future optimization: parallel execution with resource limits.

### 8.2 Cost Analysis

| Resource | Unit Cost | Estimated Usage | Monthly Cost |
|----------|-----------|-----------------|--------------|
| Compute (local) | $0 | N/A | $0 |
| CI minutes | ~$0.008/min | ~1 min per workflow | < $1 |

**Cost Controls:**
- [x] No external API calls
- [x] Timeout prevents runaway execution
- [x] Can be disabled for faster iteration

**Worst-Case Scenario:** 100 entry points × 30s timeout = 50 minutes. Mitigation: timeout would kill the process, and this scenario is unrealistic.

## 9. Legal & Compliance

| Concern | Applies? | Mitigation |
|---------|----------|------------|
| PII/Personal Data | No | Smoke test only runs --help |
| Third-Party Licenses | No | No new dependencies |
| Terms of Service | No | No external APIs |
| Data Retention | No | No data persisted |
| Export Controls | No | Standard Python tooling |

**Data Classification:** Internal

**Compliance Checklist:**
- [x] No PII stored without consent
- [x] All third-party licenses compatible with project license
- [x] External API usage compliant with provider ToS
- [x] Data retention policy documented

## 10. Verification & Testing

*Ref: [0005-testing-strategy-and-protocols.md](0005-testing-strategy-and-protocols.md)*

**Testing Philosophy:** 100% automated test coverage for all new code.

### 10.0 Test Plan (TDD - Complete Before Implementation)

**TDD Requirement:** Tests MUST be written and failing BEFORE implementation begins.

| Test ID | Test Description | Expected Behavior | Status |
|---------|------------------|-------------------|--------|
| T010 | test_discover_entry_points_finds_run_scripts | Returns list of tools/run_*.py paths | RED |
| T020 | test_run_smoke_test_success | Returns success=True for valid script | RED |
| T030 | test_run_smoke_test_import_error | Returns success=False with error details | RED |
| T040 | test_run_smoke_test_timeout | Returns failure after timeout | RED |
| T050 | test_integration_smoke_test_all_pass | Updates state with passed=True | RED |
| T060 | test_integration_smoke_test_one_fails | Updates state with passed=False | RED |
| T070 | test_parse_import_error_extracts_module | Parses ModuleNotFoundError correctly | RED |
| T080 | test_workflow_integration_smoke_after_green | Smoke test runs after green phase | RED |

**Coverage Target:** ≥95% for all new code

**TDD Checklist:**
- [ ] All tests written before implementation
- [ ] Tests currently RED (failing)
- [ ] Test IDs match scenario IDs in 10.1
- [ ] Test file created at: `tests/unit/test_smoke_test_node.py`

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | Discover valid entry points | Auto | Project with tools/run_*.py | List of paths | All paths returned |
| 020 | Smoke test passes for valid script | Auto | Script that exits 0 | SmokeTestResult(success=True) | No errors |
| 030 | Smoke test catches ImportError | Auto | Script with bad import | SmokeTestResult(success=False, error_type="ImportError") | Error captured |
| 040 | Smoke test catches ModuleNotFoundError | Auto | Script with missing module | SmokeTestResult(success=False, error_type="ModuleNotFoundError") | Error captured |
| 050 | Smoke test times out | Auto | Script that sleeps 60s | SmokeTestResult(success=False) | Timeout after 30s |
| 060 | Workflow continues on all pass | Auto | State with passing results | smoke_test_passed=True | Workflow proceeds |
| 070 | Workflow fails on any failure | Auto | State with one failure | smoke_test_passed=False | Workflow errors |
| 080 | Error message shows failed import | Auto | ImportError for 'foo' | Message contains 'foo' | Clear error message |

### 10.2 Test Commands

```bash
# Run all automated tests for smoke test module
poetry run pytest tests/unit/test_smoke_test_node.py -v

# Run integration tests
poetry run pytest tests/integration/test_smoke_test_integration.py -v

# Run with coverage
poetry run pytest tests/unit/test_smoke_test_node.py --cov=agentos/workflows/tdd/smoke_test_node --cov-report=term-missing
```

### 10.3 Manual Tests (Only If Unavoidable)

N/A - All scenarios automated.

## 11. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Entry points have side effects with --help | Med | Low | Review entry points, ensure --help is idempotent |
| False positives from unrelated errors | Med | Low | Only catch ImportError/ModuleNotFoundError specifically |
| Slow smoke tests delay TDD cycle | Low | Med | Add skip flag, optimize later with parallel execution |
| Missing entry points in discovery | Med | Low | Use consistent naming convention, document requirements |

## 12. Definition of Done

### Code
- [ ] Implementation complete and linted
- [ ] Code comments reference this LLD

### Tests
- [ ] All test scenarios pass (T010-T080)
- [ ] Test coverage ≥95%

### Documentation
- [ ] LLD updated with any deviations
- [ ] Implementation Report (0103) completed
- [ ] Test Report (0113) completed if applicable

### Review
- [ ] Code review completed
- [ ] User approval before closing issue

### 12.1 Traceability (Mechanical - Auto-Checked)

*Issue #277: Cross-references are verified programmatically.*

Mechanical validation automatically checks:
- Every file mentioned in this section must appear in Section 2.1
- Every risk mitigation in Section 11 should have a corresponding function in Section 2.4 (warning if not)

**If files are missing from Section 2.1, the LLD is BLOCKED.**

---

## Appendix: Review Log

*Track all review feedback with timestamps and implementation status.*

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| - | - | - | - |

**Final Status:** PENDING