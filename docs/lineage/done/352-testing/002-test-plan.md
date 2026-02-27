# Extracted Test Plan

## Scenarios

### test_id
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Tests Function | File | Input | Expected Output

### test_t010
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `run_adversarial_node()` | `test_adversarial_node.py` | State with impl+LLD, mocked Gemini returning valid JSON | `verdict="pass"`, `test_count > 0`

### test_t020
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `run_adversarial_node()` | `test_adversarial_node.py` | State + `GeminiQuotaExhaustedError` | `verdict="error"`, `skipped_reason` contains "quota"

### test_t030
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `run_adversarial_node()` | `test_adversarial_node.py` | State + `GeminiModelDowngradeError` | `verdict="error"`, `skipped_reason` contains "Flash"

### test_t040
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `run_adversarial_node()` | `test_adversarial_node.py` | State with `implementation_files={}` | `verdict="error"`, `skipped_reason` contains "No implementation"

### test_t050
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `_parse_gemini_response()` | `test_adversarial_node.py` | Valid JSON string with all categories | `AdversarialAnalysis` with all fields

### test_t060
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `_parse_gemini_response()` | `test_adversarial_node.py` | `"{broken"` | `ValueError` with "Malformed JSON"

### test_t070
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `write_adversarial_tests()` | `test_adversarial_writer.py` | 3 boundary + 2 contract cases | 2 files created

### test_t080
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `write_adversarial_tests()` | `test_adversarial_writer.py` | `issue_id=352`, `category="injection"` | File named `test_352_injection.py`

### test_t090
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `_render_test_file()` | `test_adversarial_writer.py` | Single test case | `compile()` succeeds

### test_t100
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `_check_no_mocks()` | `test_adversarial_validator.py` | `"from unittest.mock import patch"` | 1+ mock violation

### test_t110
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `_check_no_mocks()` | `test_adversarial_validator.py` | `"m = MagicMock()"` | 1+ mock violation

### test_t120
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `_check_no_mocks()` | `test_adversarial_validator.py` | `"@patch('module.func')"` | 1+ mock violation

### test_t130
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `_check_no_mocks()` | `test_adversarial_validator.py` | `"def test_x(monkeypatch):"` | 1+ mock violation

### test_t140
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `validate_adversarial_tests()` | `test_adversarial_validator.py` | Clean test file | `valid=True`, empty violations

### test_t150
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `_check_assertions()` | `test_adversarial_validator.py` | `"def test_x(): pass"` | 1 warning

### test_t160
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `_check_syntax()` | `test_adversarial_validator.py` | `"def test_x(:\n  pass"` | 1 error

### test_t170
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `build_adversarial_analysis_prompt()` | `test_adversarial_prompts.py` | impl+LLD+tests+patterns | Prompt contains all sections

### test_t180
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `build_adversarial_system_prompt()` | `test_adversarial_prompts.py` | N/A | Prompt contains "NEVER" and "mock"

### test_t190
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `_collect_context()` | `test_adversarial_node.py` | 200KB impl + 100KB LLD | Total ≤ ~65KB

### test_t200
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `AdversarialGeminiClient.generate_adversarial_tests()` | `test_adversarial_integration.py` | Real impl+LLD, real API | Valid JSON, parseable

### test_t210
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `AdversarialGeminiClient.generate_adversarial_tests()` | `test_adversarial_gemini.py` | Mock provider, valid inputs | Provider called correctly

### test_t220
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `AdversarialGeminiClient.generate_adversarial_tests()` | `test_adversarial_gemini.py` | Provider raises timeout | `GeminiTimeoutError` raised

### test_t230
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `verify_model_is_pro()` | `test_adversarial_gemini.py` | `{"model": "gemini-2.5-pro-preview"}` | Returns `True`

### test_t240
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `verify_model_is_pro()` | `test_adversarial_gemini.py` | `{"model": "gemini-2.0-flash-001"}` | Raises `GeminiModelDowngradeError`

### test_t250
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `validate_adversarial_tests()` | `test_adversarial_validator.py` | File with mock import | `valid=False`, mock_violations populated

### test_t260
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `_parse_gemini_response()` | `test_adversarial_node.py` | JSON with all 4 categories | All 4 category lists present

### test_t270
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `_parse_gemini_response()` | `test_adversarial_node.py` | JSON missing `false_claims` | `ValueError` mentioning "false_claims"

### test_t280
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `_render_test_file()` | `test_adversarial_writer.py` | Single test case | First line is `# ADVERSARIAL TEST FILE`

### test_t290
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `_render_test_file()` | `test_adversarial_writer.py` | `issue_id=352`, category="injection" | Header contains "Issue: #352" and "Category: injection"

