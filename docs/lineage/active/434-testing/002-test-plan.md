# Extracted Test Plan

## Scenarios

### test_t010
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `strip_ansi_codes()` | `"\033[32mGreen\033[0m"` | `"Green"`

### test_t020
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `strip_ansi_codes()` | `"\033[1m\033[31mBold Red\033[0m"` | `"Bold Red"`

### test_t030
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `strip_ansi_codes()` | `"plain text"` | `"plain text"`

### test_t040
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `strip_ansi_codes()` | `""` | `""`

### test_t050
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `strip_ansi_codes()` | `"\033[2J\033[HText"` | `"Text"`

### test_t060
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `parse_token_count()` | `"1234"` | `1234`

### test_t070
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `parse_token_count()` | `"1,234,567"` | `1234567`

### test_t080
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `parse_token_count()` | `" 500 "` | `500`

### test_t090
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `parse_token_count()` | `"0"` | `0`

### test_t100
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `parse_token_count()` | `"abc"` | Raises `ValueError`

### test_t110
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `parse_cost_value()` | `"$0.0042"` | `0.0042`

### test_t120
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `parse_cost_value()` | `"0.0042"` | `0.0042`

### test_t130
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `parse_cost_value()` | `"$0.00"` | `0.0`

### test_t140
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `parse_cost_value()` | `" $1.23 "` | `1.23`

### test_t150
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `parse_cost_value()` | `"free"` | Raises `ValueError`

### test_t160
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `extract_usage_line()` | `CLEAN_USAGE_LINE` fixture | `UsageRecord` with `session_id="abc123"`, `input_tokens=15234`, etc.

### test_t170
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `extract_usage_line()` | `ANSI_USAGE_LINE` fixture | Same `UsageRecord` as T160

### test_t180
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `extract_usage_line()` | `"Starting session..."` | `None`

### test_t190
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `extract_usage_line()` | `"abc123  claude-sonnet"` | `None`

### test_t200
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `extract_model_name()` | `"model: claude-sonnet-4-20250514"` | `"claude-sonnet-4-20250514"`

### test_t210
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `extract_model_name()` | `"model: claude-opus-4-20250514"` | `"claude-opus-4-20250514"`

### test_t220
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `extract_model_name()` | `"model: claude-haiku-3-20250514"` | `"claude-haiku-3-20250514"`

### test_t230
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `extract_model_name()` | `"no model info here"` | `None`

### test_t240
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `extract_model_name()` | Two model strings in one text | `"claude-sonnet-4-20250514"` (first match)

### test_t250
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `parse_usage_block()` | `FULL_USAGE_BLOCK` fixture | List of 2 `UsageRecord`s

### test_t260
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `parse_usage_block()` | `MIXED_BLOCK` fixture | List of 2 records (skips non-matching)

### test_t270
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `parse_usage_block()` | `""` | `[]`

### test_t280
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `parse_usage_block()` | `ANSI_FULL_BLOCK` fixture | List of 2 records (same as clean)

### test_t290
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `parse_usage_block()` | Single clean usage line | List of 1 record

### test_t300
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `parse_usage_data()` | `golden_input.txt` content | Matches `golden_output.txt` (excluding volatile `timestamp` field)

### test_t310
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Module import | `importlib.util.spec_from_file_location` + `exec_module` | No stdout output

### test_t320
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `strip_ansi_codes()` | `ANSI_USAGE_LINE` fixture | `ANSI_USAGE_LINE_EXPECTED_CLEAN`

### test_t330
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `parse_usage_block()` | `FULL_USAGE_BLOCK` fixture | `FULL_USAGE_BLOCK_EXPECTED` all fields match

### test_t340
- Type: unit
- Requirement: 
- Mock needed: False
- Description: All parsing functions | Various inputs with socket blocked | Zero `socket.connect` calls

### test_t350
- Type: unit
- Requirement: 
- Mock needed: False
- Description: All parsing functions | >10k char adversarial strings | Completes < 100ms, correct result

