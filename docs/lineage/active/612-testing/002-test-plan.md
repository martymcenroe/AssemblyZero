# Extracted Test Plan

## Scenarios

### test_t010
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Module import | `import mine_quality_patterns` | All 8 public functions exist as attributes

### test_t020
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `load_telemetry_events()` | DB with all 3 event types, since="2026-01-01" | Set of returned event_types == 3 expected types

### test_t030
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `mine_patterns()` | 3 same-pattern + 1 different events, top_n=10 | `patterns[0]["count"]==3`, `patterns[1]["count"]==1`

### test_t040
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `mine_patterns()` | 5 distinct patterns, top_n=3 | `len(patterns)==3`

### test_t050
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `parse_args()` | All 5 flags explicitly set | Namespace fields match supplied values

### test_t060
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `parse_args()` | Empty argv | `days=7, threshold=3, top_n=10, db_path="data/telemetry.db", output_json=None`

### test_t070
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `main()` | Valid DB, threshold=100 | Returns `0`

### test_t080
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `main()` | Nonexistent DB path | Returns `1`

### test_t090
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `main()` | Valid DB, threshold=2 (3 events share pattern) | Returns `2`

### test_t100
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `format_console_report()` | Report with `event_counts={"quality.gate_rejected": 12}` | `"quality.gate_rejected"` and `"12"` in output

### test_t110
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `format_console_report()` | Report with 2 patterns with distinct nodes | Both node names in output

### test_t120
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `write_json_report()` | Report dict -> tmp file -> `orjson.loads` | All 5 AuditReport keys present in parsed dict

### test_t130
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `test_write_attempt_raises_error()` | `sqlite3.connect(db_path)` with `PRAGMA query_only = ON`, then `INSERT INTO telemetry_events VALUES (...)` | `sqlite3.OperationalError` raised

### test_t140
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `main()` | Empty DB (schema but no rows) | Returns `0`, stdout contains "No telemetry events"

### test_t150
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `load_telemetry_events()` | `db_path="/tmp/nonexistent.db"` | Raises `FileNotFoundError`

### test_t160
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `build_report()` | 5 same-pattern events, threshold=3 | `threshold_triggered is True`

### test_t170
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `build_report()` | 2 distinct events, threshold=3 | `threshold_triggered is False`

