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
- Mock needed: False
- Description: `run_pytest()` | `test_parser.py` | `args=["tests/unit/", "-v", "-x"]` | subprocess called with matching args

### test_t020
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `run_pytest()` + `main()` | `test_parser.py`, `test_integration.py` | pytest returns 1 | gate returns 1

### test_t025
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `ensure_verbose_flag()` | `test_parser.py` | `args=["tests/", "--tb=short"]` | `[..., "-v"]` appended

### test_t030
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `parse_skipped_tests()` | `test_parser.py` | inline SKIPPED output | `SkippedTest` with correct fields

### test_t040
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `parse_skipped_tests()` | `test_parser.py` | multiple skipped lines | 3 `SkippedTest` objects

### test_t050
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `detect_critical_tests()` | `test_parser.py` | test with "critical" in name | `is_critical=True`

### test_t060
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `detect_critical_tests()` | `test_parser.py` | test with "security"/"auth" in name | `is_critical=True`

### test_t070
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `find_audit_block()` | `test_auditor.py` | stdout containing audit block | `AuditBlock` with `source="stdout"`

### test_t080
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `find_audit_block()` | `test_auditor.py` | `.skip-audit.md` file | `AuditBlock` with `source="file"`

### test_t090
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `match_test_to_audit()` | `test_auditor.py` | exact and glob patterns | `True`/`False` matches

### test_t100
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `main()` | `test_integration.py` | skips, no audit | exit code 1

### test_t110
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `validate_audit()` + `main()` | `test_auditor.py`, `test_integration.py` | test not in audit | unaudited list populated, exit 1

### test_t120
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `validate_audit()` + `main()` | `test_auditor.py`, `test_integration.py` | critical + UNVERIFIED | unverified list populated, exit 1

### test_t130
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `validate_audit()` + `main()` | `test_auditor.py`, `test_integration.py` | all audited | `([], [])`, exit 0

### test_t140
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `main()` | `test_integration.py` | WARNING logged, exit 0

### test_t150
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `main()` | `test_integration.py` | no skipped tests | pytest exit code returned

### test_t160
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `main()` | `test_integration.py` | all flags passed through

