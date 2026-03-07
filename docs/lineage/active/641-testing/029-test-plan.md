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
- Description: `select_model_for_file` routes `__init__.py` to Haiku | Returns `HAIKU_MODEL` | RED

### test_t020
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `select_model_for_file` routes `conftest.py` to Haiku | Returns `HAIKU_MODEL` | RED

### test_t030
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `select_model_for_file` routes test scaffold to Haiku | Returns `HAIKU_MODEL` when `is_test_scaffold=True` | RED

### test_t040
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `select_model_for_file` routes 49-line file to Haiku | Returns `HAIKU_MODEL` | RED

### test_t050
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `select_model_for_file` routes 50-line file to Sonnet | Returns default model | RED

### test_t060
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `select_model_for_file` routes unknown-size complex file to Sonnet | Returns default model when `estimated_line_count=0` | RED

### test_t070
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `select_model_for_file` routes deeply nested `__init__.py` to Haiku | Path depth irrelevant; basename match wins | RED

### test_t080
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `call_claude_for_file` uses supplied model when provided | Anthropic client called with correct model string | RED

### test_t090
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `call_claude_for_file` uses default model when `model=None` | Existing behaviour preserved | RED

### test_t100
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `generate_file_with_retry` passes routed model to `call_claude_for_file` | Integration of routing -> call | RED

### test_t110
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Routing decision logged at INFO level with reason | Logger called with file path, model name, and reason | RED

### test_t120
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Negative line count treated as unknown | Returns `DEFAULT_MODEL` when `estimated_line_count=-1` | RED

### test_t130
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Returns `HAIKU_MODEL` for lower boundary | RED

### test_t140
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Returns `DEFAULT_MODEL` just above threshold | RED

### test_t150
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Coverage ≥ 95% on new/modified code | `pytest-cov` report shows ≥ 95% line coverage | RED

### test_t160
- Type: unit
- Requirement: 
- Mock needed: False
- Description: No regressions in existing unit test suite | All pre-existing tests pass after change | RED

### test_010
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `__init__.py` in root (REQ-1) | Auto | `file_path="assemblyzero/__init__.py"`, `estimated_line_count=0`, `is_test_scaffold=False` | `HAIKU_MODEL` | `assert result == HAIKU_MODEL`

### test_020
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `conftest.py` in tests root (REQ-2) | Auto | `file_path="tests/conftest.py"`, `estimated_line_count=0`, `is_test_scaffold=False` | `HAIKU_MODEL` | `assert result == HAIKU_MODEL`

### test_030
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Test scaffold flag overrides line count (REQ-3) | Auto | `file_path="tests/unit/test_foo.py"`, `estimated_line_count=200`, `is_test_scaffold=True` | `HAIKU_MODEL` | Flag overrides line count and filen

### test_040
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Auto | `file_path="assemblyzero/utils/helper.py"`, `estimated_line_count=49`, `is_test_scaffold=False` | `HAIKU_MODEL` | `assert result == HAIKU_MODEL`

### test_050
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Auto | `file_path="assemblyzero/utils/helper.py"`, `estimated_line_count=50`, `is_test_scaffold=False` | `DEFAULT_MODEL` | Exactly 50 lines goes to Sonnet (threshold is `< 50`)

### test_060
- Type: unit
- Requirement: 
- Mock needed: False
- Description: 200-line complex file (REQ-5) | Auto | `file_path="assemblyzero/core/engine.py"`, `estimated_line_count=200`, `is_test_scaffold=False` | `DEFAULT_MODEL` | `assert result == DEFAULT_MODEL`

### test_070
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Unknown size complex file (REQ-5) | Auto | `file_path="assemblyzero/core/engine.py"`, `estimated_line_count=0`, `is_test_scaffold=False` | `DEFAULT_MODEL` | `0` means unknown; don't route to Haiku

### test_080
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Deeply nested `__init__.py` (REQ-1) | Auto | `file_path="assemblyzero/workflows/testing/nodes/__init__.py"` | `HAIKU_MODEL` | Basename match regardless of depth

### test_090
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `call_claude_for_file` explicit model (REQ-7) | Auto | `model="claude-3-haiku-20240307"`, mock client | Anthropic client receives `model="claude-3-haiku-20240307"` | Mock assert called with correct mo

### test_100
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `call_claude_for_file` default model (REQ-7) | Auto | `model=None`, mock client | Anthropic client receives configured default | Backward-compatible path

### test_110
- Type: integration
- Requirement: 
- Mock needed: True
- Description: `generate_file_with_retry` routing integration (REQ-8) | Auto | `file_path="tests/__init__.py"`, mock `call_claude_for_file` | `call_claude_for_file` called with `model=HAIKU_MODEL` | End-to-end routi

### test_120
- Type: unit
- Requirement: 
- Mock needed: True
- Description: Routing log emission includes reason (REQ-9) | Auto | Any routed call, mock logger | `logger.info` called with file path, model name, and reason string | `mock_logger.info.assert_called_once()` and re

### test_130
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Auto | `estimated_line_count=1` | `HAIKU_MODEL` | Lower boundary check

### test_140
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Negative line count treated as unknown (REQ-6) | Auto | `estimated_line_count=-1` | `DEFAULT_MODEL` | Defensive: negative = unknown, no Haiku routing

### test_150
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Coverage ≥ 95% on new/modified code (REQ-10) | Auto | Run `pytest --cov=assemblyzero/workflows/testing/nodes/implement_code --cov-report=term-missing` | Coverage report shows ≥ 95% line coverage | CI 

### test_160
- Type: unit
- Requirement: 
- Mock needed: False
- Description: No regressions in existing unit test suite (REQ-11) | Auto | Run `pytest tests/unit/ -m "not integration and not e2e and not adversarial"` | All pre-existing tests pass | Exit code 0; zero failures, z

