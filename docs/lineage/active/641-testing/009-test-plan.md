# Extracted Test Plan

## Scenarios

### test_t010
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `select_model_for_file()` | `file_path="assemblyzero/__init__.py", estimated_line_count=0, is_test_scaffold=False` | `HAIKU_MODEL` (`"claude-3-haiku-20240307"`)

### test_t020
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `select_model_for_file()` | `file_path="tests/conftest.py", estimated_line_count=0, is_test_scaffold=False` | `HAIKU_MODEL`

### test_t030
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `select_model_for_file()` | `file_path="tests/unit/test_foo.py", estimated_line_count=200, is_test_scaffold=True` | `HAIKU_MODEL`

### test_t040
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `select_model_for_file()` | `file_path="assemblyzero/utils/helper.py", estimated_line_count=49, is_test_scaffold=False` | `HAIKU_MODEL`

### test_t050
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `select_model_for_file()` | `file_path="assemblyzero/utils/helper.py", estimated_line_count=50, is_test_scaffold=False` | `CLAUDE_MODEL` (default)

### test_t060
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `select_model_for_file()` | `file_path="assemblyzero/core/engine.py", estimated_line_count=200, is_test_scaffold=False` | `CLAUDE_MODEL`

### test_t070
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `select_model_for_file()` | `file_path="assemblyzero/core/engine.py", estimated_line_count=0, is_test_scaffold=False` | `CLAUDE_MODEL`

### test_t080
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `select_model_for_file()` | `file_path="assemblyzero/workflows/testing/nodes/__init__.py"` | `HAIKU_MODEL`

### test_t090
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `call_claude_for_file()` | Signature inspection: `model` param exists with default `None` | Parameter present

### test_t100
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `call_claude_for_file()` | Signature inspection: `model` default is `None` | Backward-compatible

### test_t110
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `generate_file_with_retry()` | `filepath="tests/__init__.py"`, mocked routing/call | `select_model_for_file` called; model passed to `call_claude_for_file`

### test_t120
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `select_model_for_file()` | `estimated_line_count=-1` | `CLAUDE_MODEL`

### test_t130
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `select_model_for_file()` | `estimated_line_count=1` | `HAIKU_MODEL`

### test_t140
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `select_model_for_file()` | `estimated_line_count=51` | `CLAUDE_MODEL`

### test_t150
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Coverage check | `pytest --cov --cov-fail-under=95` | Exit code 0

### test_t160
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Regression check | `pytest tests/unit/ -m "not integration"` | Exit code 0

