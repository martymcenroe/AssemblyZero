# Extracted Test Plan

## Scenarios

### test_id
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Test Description | Expected Behavior | Status

### test_t010
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Construct `WorkspaceContext` with valid absolute paths | Instance created; fields equal resolved paths | RED

### test_t020
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Construct via `make_workspace_context` with string args | Paths resolved to `Path`; instance returned | RED

### test_t030
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `make_workspace_context` with non-existent `assemblyzero_root` | Raises `ValueError` with path in message | RED

### test_t040
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `make_workspace_context` with non-existent `target_repo` | Raises `ValueError` with path in message | RED

### test_t050
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `frozen=True` — mutation raises `FrozenInstanceError` | Assignment to field raises exception | RED

### test_t060
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `docs_dir` property returns `assemblyzero_root / "docs"` | Correct `Path` returned | RED

### test_t070
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `lld_active_dir` returns `docs_dir / "lld" / "active"` | Correct `Path` returned | RED

### test_t080
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `reports_dir` returns `docs_dir / "reports"` | Correct `Path` returned | RED

### test_t090
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `target_name` returns `target_repo.name` | String basename returned | RED

### test_t100
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `WorkspaceContext` importable from `assemblyzero.core` | No import error | RED

### test_t110
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Node receives `workspace_ctx` from state, not direct args | Node reads `state["workspace_ctx"]`; no `TypeError` | RED

### test_t120
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `WorkflowState` TypedDict in `state.py` declares `workspace_ctx` field | `get_type_hints(WorkflowState)["workspace_ctx"]` is `WorkspaceContext` | RED

### test_t130
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `build_initial_state` calls `make_workspace_context` exactly once | Mock spy confirms single call; `state["workspace_ctx"]` is the returned instance | RED

### test_t140
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Full test suite passes with no regressions | `pytest` exits zero; no previously-passing tests fail | RED

### test_t150
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Coverage report shows ≥95% for `workspace_context.py` | RED

### test_010
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Happy path — valid absolute paths (REQ-1) | Auto | Two existing `tmp_path` dirs | `WorkspaceContext` instance | Fields equal inputs

### test_020
- Type: unit
- Requirement: 
- Mock needed: False
- Description: String inputs to factory (REQ-2) | Auto | Two str paths to existing dirs | `WorkspaceContext` | `isinstance(ctx.assemblyzero_root, Path)`

### test_030
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Missing `assemblyzero_root` (REQ-2) | Auto | Non-existent root path | `ValueError` | Message contains path string

### test_040
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Missing `target_repo` (REQ-2) | Auto | Non-existent target path | `ValueError` | Message contains path string

### test_050
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Frozen immutability (REQ-1) | Auto | Valid `WorkspaceContext`, attempt field set | `FrozenInstanceError` | Exception raised

### test_060
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `docs_dir` property (REQ-1) | Auto | Valid ctx | `assemblyzero_root / "docs"` | Path equality

### test_070
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `lld_active_dir` property (REQ-1) | Auto | Valid ctx | `docs_dir / "lld" / "active"` | Path equality

### test_080
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `reports_dir` property (REQ-1) | Auto | Valid ctx | `docs_dir / "reports"` | Path equality

### test_090
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `target_name` property (REQ-1) | Auto | ctx with `target_repo = Path("/x/my-repo")` | `"my-repo"` | String equality

### test_100
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Public import (REQ-7) | Auto | `from assemblyzero.core import WorkspaceContext` | No exception | Import succeeds

### test_110
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Node reads ctx from state (REQ-3) | Auto | State dict with `workspace_ctx` key | Node accesses correct paths | No `KeyError`; correct paths used

### test_120
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `WorkflowState` TypedDict declares `workspace_ctx` field (REQ-8) | Auto | `get_type_hints(WorkflowState)` | Key `"workspace_ctx"` maps to `WorkspaceContext` | Type hint present and correct

### test_130
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `build_initial_state` constructs `WorkspaceContext` exactly once (REQ-4) | Auto | Valid root + repo strings; mock spy on `make_workspace_context` | `state["workspace_ctx"]` is the mocked return value;

### test_140
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Full test suite passes with no regressions (REQ-5) | Auto | Entire `tests/` directory | All previously-passing tests still pass | `pytest` exit code 0; no new failures

### test_150
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Coverage ≥95% on `workspace_context.py` (REQ-6) | Auto | `pytest --cov=assemblyzero.core.workspace_context` | Coverage report line% ≥ 95

