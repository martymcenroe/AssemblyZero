# Test Plan Review Prompt

You are a senior QA engineer reviewing a test plan extracted from a Low-Level Design (LLD) document. Your goal is to ensure the test plan provides adequate coverage and uses real, executable tests.

## Pre-Validated (Do NOT Re-Check)

**Issue #495:** The following have been confirmed by automated mechanical gates before this review. Do not re-check these — focus on semantic test quality instead.

- **Test plan section exists** with named scenarios: VERIFIED
- **Requirement coverage** ≥ 95%: VERIFIED
- **No vague assertions**: VERIFIED — no "verify it works" patterns detected
- **No human delegation**: VERIFIED — no "manual verification" keywords found

## Review Criteria

### 1. Test Type Appropriateness

Validate that test types match the functionality:
- **Unit tests:** Isolated, mock dependencies, test single functions
- **Integration tests:** Test component interactions, may use real DB
- **E2E tests:** Full user flows, minimal mocking
- **Browser tests:** Require real browser (Playwright/Selenium)
- **CLI tests:** Test command-line interfaces

**WARNING (not blocking) if:** Test types seem mismatched

### 5. Edge Cases

Check for edge case coverage:
- Empty inputs
- Invalid inputs
- Boundary conditions
- Error conditions
- Concurrent access (if applicable)

**WARNING (not blocking) if:** Edge cases seem missing

## Output Format

Provide your verdict in this exact format:

```markdown
## Test Type Review

| Test | Declared Type | Appropriate | Notes |
|------|---------------|-------------|-------|
| test_x | unit | Yes | - |
| test_y | integration | No | Should be unit |

## Edge Cases

- [ ] Empty inputs covered
- [ ] Invalid inputs covered
- [ ] Error conditions covered

## Semantic Issues

{Any issues found with test logic, mock strategy, or test design}

## Verdict

[x] **APPROVED** - Test plan is ready for implementation

OR

[x] **BLOCKED** - Test plan needs revision

## Required Changes (if BLOCKED)

1. [Specific, actionable change needed]
2. [Specific, actionable change needed]
```

## Important Notes

- Coverage, assertion quality, and human delegation are pre-validated — focus on semantic quality
- Provide specific, actionable feedback
- Reference specific tests and requirements by name


---

# Test Plan for Issue #838

## Requirements to Cover

- REQ-1: `WorkspaceContext` is a frozen dataclass with `assemblyzero_root: Path` and `target_repo: Path` fields, plus `docs_dir`, `lld_active_dir`, `reports_dir`, and `target_name` computed properties.
- REQ-2: `make_workspace_context()` accepts `str | Path` arguments, resolves them to absolute paths, validates existence, and raises `ValueError` with a descriptive message if either path does not exist.
- REQ-3: All workflow nodes that previously accepted `assemblyzero_root` and/or `target_repo` as function parameters now read from `state["workspace_ctx"]` instead.
- REQ-4: `WorkspaceContext` is constructed exactly once per workflow run, at the orchestrator entry point.
- REQ-5: All existing tests continue to pass (no regressions).
- REQ-6: New unit tests achieve ≥95% line coverage of `workspace_context.py`.
- REQ-7: `WorkspaceContext` is importable as `from assemblyzero.core import WorkspaceContext`.
- REQ-8: `assemblyzero/core/state.py` contains `workspace_ctx: WorkspaceContext` in the shared `WorkflowState` TypedDict.

## Detected Test Types

- browser
- e2e
- integration
- mobile
- security
- terminal
- unit

## Required Tools

- appium
- bandit
- click.testing
- detox
- docker-compose
- pexpect
- playwright
- pytest
- safety
- selenium

## Mock Guidance

**Browser/UI Tests:** Real browser required, mock backend APIs for isolation
**End-to-End Tests:** Minimal mocking - test against real (sandboxed) systems
**Integration Tests:** Use test doubles for external services, real DB where possible
**Mobile App Tests:** Use emulators/simulators, mock backend services
**Security Tests:** Never use real credentials, test edge cases thoroughly
**Terminal/CLI Tests:** Use CliRunner or capture stdout/stderr
**Unit Tests:** Mock external dependencies (APIs, DB, filesystem)

## Coverage Target

95%

## Test Scenarios

### test_id
- **Type:** unit
- **Requirement:** 
- **Description:** Test Description | Expected Behavior | Status
- **Mock needed:** False
- **Assertions:** 

### test_t010
- **Type:** unit
- **Requirement:** 
- **Description:** Construct `WorkspaceContext` with valid absolute paths | Instance created; fields equal resolved paths | RED
- **Mock needed:** False
- **Assertions:** 

### test_t020
- **Type:** unit
- **Requirement:** 
- **Description:** Construct via `make_workspace_context` with string args | Paths resolved to `Path`; instance returned | RED
- **Mock needed:** False
- **Assertions:** 

### test_t030
- **Type:** unit
- **Requirement:** 
- **Description:** `make_workspace_context` with non-existent `assemblyzero_root` | Raises `ValueError` with path in message | RED
- **Mock needed:** False
- **Assertions:** 

### test_t040
- **Type:** unit
- **Requirement:** 
- **Description:** `make_workspace_context` with non-existent `target_repo` | Raises `ValueError` with path in message | RED
- **Mock needed:** False
- **Assertions:** 

### test_t050
- **Type:** unit
- **Requirement:** 
- **Description:** `frozen=True` — mutation raises `FrozenInstanceError` | Assignment to field raises exception | RED
- **Mock needed:** False
- **Assertions:** 

### test_t060
- **Type:** unit
- **Requirement:** 
- **Description:** `docs_dir` property returns `assemblyzero_root / "docs"` | Correct `Path` returned | RED
- **Mock needed:** False
- **Assertions:** 

### test_t070
- **Type:** unit
- **Requirement:** 
- **Description:** `lld_active_dir` returns `docs_dir / "lld" / "active"` | Correct `Path` returned | RED
- **Mock needed:** False
- **Assertions:** 

### test_t080
- **Type:** unit
- **Requirement:** 
- **Description:** `reports_dir` returns `docs_dir / "reports"` | Correct `Path` returned | RED
- **Mock needed:** False
- **Assertions:** 

### test_t090
- **Type:** unit
- **Requirement:** 
- **Description:** `target_name` returns `target_repo.name` | String basename returned | RED
- **Mock needed:** False
- **Assertions:** 

### test_t100
- **Type:** unit
- **Requirement:** 
- **Description:** `WorkspaceContext` importable from `assemblyzero.core` | No import error | RED
- **Mock needed:** False
- **Assertions:** 

### test_t110
- **Type:** unit
- **Requirement:** 
- **Description:** Node receives `workspace_ctx` from state, not direct args | Node reads `state["workspace_ctx"]`; no `TypeError` | RED
- **Mock needed:** False
- **Assertions:** 

### test_t120
- **Type:** unit
- **Requirement:** 
- **Description:** `WorkflowState` TypedDict in `state.py` declares `workspace_ctx` field | `get_type_hints(WorkflowState)["workspace_ctx"]` is `WorkspaceContext` | RED
- **Mock needed:** False
- **Assertions:** 

### test_t130
- **Type:** unit
- **Requirement:** 
- **Description:** `build_initial_state` calls `make_workspace_context` exactly once | Mock spy confirms single call; `state["workspace_ctx"]` is the returned instance | RED
- **Mock needed:** True
- **Assertions:** 

### test_t140
- **Type:** unit
- **Requirement:** 
- **Description:** Full test suite passes with no regressions | `pytest` exits zero; no previously-passing tests fail | RED
- **Mock needed:** False
- **Assertions:** 

### test_t150
- **Type:** unit
- **Requirement:** 
- **Description:** Coverage report shows ≥95% for `workspace_context.py` | RED
- **Mock needed:** False
- **Assertions:** 

### test_010
- **Type:** unit
- **Requirement:** 
- **Description:** Happy path — valid absolute paths (REQ-1) | Auto | Two existing `tmp_path` dirs | `WorkspaceContext` instance | Fields equal inputs
- **Mock needed:** False
- **Assertions:** 

### test_020
- **Type:** unit
- **Requirement:** 
- **Description:** String inputs to factory (REQ-2) | Auto | Two str paths to existing dirs | `WorkspaceContext` | `isinstance(ctx.assemblyzero_root, Path)`
- **Mock needed:** False
- **Assertions:** 

### test_030
- **Type:** unit
- **Requirement:** 
- **Description:** Missing `assemblyzero_root` (REQ-2) | Auto | Non-existent root path | `ValueError` | Message contains path string
- **Mock needed:** False
- **Assertions:** 

### test_040
- **Type:** unit
- **Requirement:** 
- **Description:** Missing `target_repo` (REQ-2) | Auto | Non-existent target path | `ValueError` | Message contains path string
- **Mock needed:** False
- **Assertions:** 

### test_050
- **Type:** unit
- **Requirement:** 
- **Description:** Frozen immutability (REQ-1) | Auto | Valid `WorkspaceContext`, attempt field set | `FrozenInstanceError` | Exception raised
- **Mock needed:** False
- **Assertions:** 

### test_060
- **Type:** unit
- **Requirement:** 
- **Description:** `docs_dir` property (REQ-1) | Auto | Valid ctx | `assemblyzero_root / "docs"` | Path equality
- **Mock needed:** False
- **Assertions:** 

### test_070
- **Type:** unit
- **Requirement:** 
- **Description:** `lld_active_dir` property (REQ-1) | Auto | Valid ctx | `docs_dir / "lld" / "active"` | Path equality
- **Mock needed:** False
- **Assertions:** 

### test_080
- **Type:** unit
- **Requirement:** 
- **Description:** `reports_dir` property (REQ-1) | Auto | Valid ctx | `docs_dir / "reports"` | Path equality
- **Mock needed:** False
- **Assertions:** 

### test_090
- **Type:** unit
- **Requirement:** 
- **Description:** `target_name` property (REQ-1) | Auto | ctx with `target_repo = Path("/x/my-repo")` | `"my-repo"` | String equality
- **Mock needed:** False
- **Assertions:** 

### test_100
- **Type:** unit
- **Requirement:** 
- **Description:** Public import (REQ-7) | Auto | `from assemblyzero.core import WorkspaceContext` | No exception | Import succeeds
- **Mock needed:** False
- **Assertions:** 

### test_110
- **Type:** unit
- **Requirement:** 
- **Description:** Node reads ctx from state (REQ-3) | Auto | State dict with `workspace_ctx` key | Node accesses correct paths | No `KeyError`; correct paths used
- **Mock needed:** False
- **Assertions:** 

### test_120
- **Type:** unit
- **Requirement:** 
- **Description:** `WorkflowState` TypedDict declares `workspace_ctx` field (REQ-8) | Auto | `get_type_hints(WorkflowState)` | Key `"workspace_ctx"` maps to `WorkspaceContext` | Type hint present and correct
- **Mock needed:** False
- **Assertions:** 

### test_130
- **Type:** unit
- **Requirement:** 
- **Description:** `build_initial_state` constructs `WorkspaceContext` exactly once (REQ-4) | Auto | Valid root + repo strings; mock spy on `make_workspace_context` | `state["workspace_ctx"]` is the mocked return value;
- **Mock needed:** True
- **Assertions:** 

### test_140
- **Type:** unit
- **Requirement:** 
- **Description:** Full test suite passes with no regressions (REQ-5) | Auto | Entire `tests/` directory | All previously-passing tests still pass | `pytest` exit code 0; no new failures
- **Mock needed:** False
- **Assertions:** 

### test_150
- **Type:** unit
- **Requirement:** 
- **Description:** Coverage ≥95% on `workspace_context.py` (REQ-6) | Auto | `pytest --cov=assemblyzero.core.workspace_context` | Coverage report line% ≥ 95
- **Mock needed:** False
- **Assertions:** 

## Original Test Plan Section

*Ref: [0005-testing-strategy-and-protocols.md](0005-testing-strategy-and-protocols.md)*

**Testing Philosophy:** Strive for 100% automated test coverage. Manual tests are a last resort for scenarios that genuinely cannot be automated.

### 10.0 Test Plan (TDD - Complete Before Implementation)

**TDD Requirement:** Tests MUST be written and failing BEFORE implementation begins.

| Test ID | Test Description | Expected Behavior | Status |
|---------|------------------|-------------------|--------|
| T010 | Construct `WorkspaceContext` with valid absolute paths | Instance created; fields equal resolved paths | RED |
| T020 | Construct via `make_workspace_context` with string args | Paths resolved to `Path`; instance returned | RED |
| T030 | `make_workspace_context` with non-existent `assemblyzero_root` | Raises `ValueError` with path in message | RED |
| T040 | `make_workspace_context` with non-existent `target_repo` | Raises `ValueError` with path in message | RED |
| T050 | `frozen=True` — mutation raises `FrozenInstanceError` | Assignment to field raises exception | RED |
| T060 | `docs_dir` property returns `assemblyzero_root / "docs"` | Correct `Path` returned | RED |
| T070 | `lld_active_dir` returns `docs_dir / "lld" / "active"` | Correct `Path` returned | RED |
| T080 | `reports_dir` returns `docs_dir / "reports"` | Correct `Path` returned | RED |
| T090 | `target_name` returns `target_repo.name` | String basename returned | RED |
| T100 | `WorkspaceContext` importable from `assemblyzero.core` | No import error | RED |
| T110 | Node receives `workspace_ctx` from state, not direct args | Node reads `state["workspace_ctx"]`; no `TypeError` | RED |
| T120 | `WorkflowState` TypedDict in `state.py` declares `workspace_ctx` field | `get_type_hints(WorkflowState)["workspace_ctx"]` is `WorkspaceContext` | RED |
| T130 | `build_initial_state` calls `make_workspace_context` exactly once | Mock spy confirms single call; `state["workspace_ctx"]` is the returned instance | RED |
| T140 | Full test suite passes with no regressions | `pytest` exits zero; no previously-passing tests fail | RED |
| T150 | Coverage report shows ≥95% for `workspace_context.py` | `--cov` report line coverage ≥ 95% | RED |

**Coverage Target:** ≥95% for all new code

**TDD Checklist:**
- [ ] All tests written before implementation
- [ ] Tests currently RED (failing)
- [ ] Test IDs match scenario IDs in 10.1
- [ ] Test file created at: `tests/unit/test_workspace_context.py`

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | Happy path — valid absolute paths (REQ-1) | Auto | Two existing `tmp_path` dirs | `WorkspaceContext` instance | Fields equal inputs |
| 020 | String inputs to factory (REQ-2) | Auto | Two str paths to existing dirs | `WorkspaceContext` | `isinstance(ctx.assemblyzero_root, Path)` |
| 030 | Missing `assemblyzero_root` (REQ-2) | Auto | Non-existent root path | `ValueError` | Message contains path string |
| 040 | Missing `target_repo` (REQ-2) | Auto | Non-existent target path | `ValueError` | Message contains path string |
| 050 | Frozen immutability (REQ-1) | Auto | Valid `WorkspaceContext`, attempt field set | `FrozenInstanceError` | Exception raised |
| 060 | `docs_dir` property (REQ-1) | Auto | Valid ctx | `assemblyzero_root / "docs"` | Path equality |
| 070 | `lld_active_dir` property (REQ-1) | Auto | Valid ctx | `docs_dir / "lld" / "active"` | Path equality |
| 080 | `reports_dir` property (REQ-1) | Auto | Valid ctx | `docs_dir / "reports"` | Path equality |
| 090 | `target_name` property (REQ-1) | Auto | ctx with `target_repo = Path("/x/my-repo")` | `"my-repo"` | String equality |
| 100 | Public import (REQ-7) | Auto | `from assemblyzero.core import WorkspaceContext` | No exception | Import succeeds |
| 110 | Node reads ctx from state (REQ-3) | Auto | State dict with `workspace_ctx` key | Node accesses correct paths | No `KeyError`; correct paths used |
| 120 | `WorkflowState` TypedDict declares `workspace_ctx` field (REQ-8) | Auto | `get_type_hints(WorkflowState)` | Key `"workspace_ctx"` maps to `WorkspaceContext` | Type hint present and correct |
| 130 | `build_initial_state` constructs `WorkspaceContext` exactly once (REQ-4) | Auto | Valid root + repo strings; mock spy on `make_workspace_context` | `state["workspace_ctx"]` is the mocked return value; spy call count == 1 | `mock.assert_called_once()` passes |
| 140 | Full test suite passes with no regressions (REQ-5) | Auto | Entire `tests/` directory | All previously-passing tests still pass | `pytest` exit code 0; no new failures |
| 150 | Coverage ≥95% on `workspace_context.py` (REQ-6) | Auto | `pytest --cov=assemblyzero.core.workspace_context` | Coverage report line% ≥ 95 | `--cov-fail-under=95` passes |

### 10.2 Test Commands

```bash

# Run all new unit tests
poetry run pytest tests/unit/test_workspace_context.py tests/unit/test_gate/test_gate_workspace_context.py -v

# Run full test suite (no regressions — covers REQ-5)
poetry run pytest -v

# Coverage report for new module (covers REQ-6)
poetry run pytest tests/unit/test_workspace_context.py \
    --cov=assemblyzero.core.workspace_context \
    --cov-report=term-missing \
    --cov-fail-under=95
```

### 10.3 Manual Tests (Only If Unavoidable)

N/A - All scenarios automated.
