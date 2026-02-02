# Extracted Test Plan

## Scenarios

### test_005
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Verify code passes linting | Unit | Changed files | No lint errors | flake8/ruff returns exit 0

### test_010
- Type: unit
- Requirement: 
- Mock needed: True
- Description: Verify encoding param on load_input subprocess | Unit | Mock subprocess.run | Called with encoding='utf-8' | Assert call includes encoding='utf-8'

### test_020
- Type: unit
- Requirement: 
- Mock needed: True
- Description: Verify encoding param on finalize subprocess | Unit | Mock subprocess.run | Called with encoding='utf-8' | Assert call includes encoding='utf-8'

### test_030
- Type: unit
- Requirement: 
- Mock needed: True
- Description: Parse issue with box-drawing chars | Unit | Mock JSON with Unicode | Parsed correctly | No UnicodeDecodeError, content preserved

### test_040
- Type: unit
- Requirement: 
- Mock needed: True
- Description: Parse issue with emojis | Unit | Mock JSON with emojis | Parsed correctly | Content preserved

### test_050
- Type: unit
- Requirement: 
- Mock needed: True
- Description: Parse ASCII-only issue (regression) | Unit | Mock JSON ASCII only | Parsed correctly | No behavior change

### test_060
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Handle malformed UTF-8 gracefully | Unit | Invalid byte sequence | Graceful error or replacement | No crash, clear error message

### test_070
- Type: integration
- Requirement: 
- Mock needed: False
- Description: Windows CI validation | Integration | CI on Windows runner | Workflow completes | Exit code 0

