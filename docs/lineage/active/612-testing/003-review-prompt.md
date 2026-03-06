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

# Test Plan for Issue #612

## Requirements to Cover

- REQ-T010: Module import
- REQ-T020: load_telemetry_events()
- REQ-T030: mine_patterns()
- REQ-T040: mine_patterns()
- REQ-T050: parse_args()
- REQ-T060: parse_args()
- REQ-T070: main()
- REQ-T080: main()
- REQ-T090: main()
- REQ-T100: format_console_report()
- REQ-T110: format_console_report()
- REQ-T120: write_json_report()
- REQ-T130: test_write_attempt_raises_error()
- REQ-T140: main()
- REQ-T150: load_telemetry_events()
- REQ-T160: build_report()
- REQ-T170: build_report()

## Detected Test Types

- browser
- e2e
- integration
- mobile
- performance
- security
- terminal
- unit

## Required Tools

- appium
- bandit
- click.testing
- detox
- docker-compose
- locust
- pexpect
- playwright
- pytest
- pytest-benchmark
- safety
- selenium

## Mock Guidance

**Browser/UI Tests:** Real browser required, mock backend APIs for isolation
**End-to-End Tests:** Minimal mocking - test against real (sandboxed) systems
**Integration Tests:** Use test doubles for external services, real DB where possible
**Mobile App Tests:** Use emulators/simulators, mock backend services
**Performance Tests:** Test against representative data volumes
**Security Tests:** Never use real credentials, test edge cases thoroughly
**Terminal/CLI Tests:** Use CliRunner or capture stdout/stderr
**Unit Tests:** Mock external dependencies (APIs, DB, filesystem)

## Coverage Target

95%

## Test Scenarios

### test_t010
- **Type:** unit
- **Requirement:** 
- **Description:** Module import | `import mine_quality_patterns` | All 8 public functions exist as attributes
- **Mock needed:** False
- **Assertions:** 

### test_t020
- **Type:** unit
- **Requirement:** 
- **Description:** `load_telemetry_events()` | DB with all 3 event types, since="2026-01-01" | Set of returned event_types == 3 expected types
- **Mock needed:** False
- **Assertions:** 

### test_t030
- **Type:** unit
- **Requirement:** 
- **Description:** `mine_patterns()` | 3 same-pattern + 1 different events, top_n=10 | `patterns[0]["count"]==3`, `patterns[1]["count"]==1`
- **Mock needed:** False
- **Assertions:** 

### test_t040
- **Type:** unit
- **Requirement:** 
- **Description:** `mine_patterns()` | 5 distinct patterns, top_n=3 | `len(patterns)==3`
- **Mock needed:** False
- **Assertions:** 

### test_t050
- **Type:** unit
- **Requirement:** 
- **Description:** `parse_args()` | All 5 flags explicitly set | Namespace fields match supplied values
- **Mock needed:** False
- **Assertions:** 

### test_t060
- **Type:** unit
- **Requirement:** 
- **Description:** `parse_args()` | Empty argv | `days=7, threshold=3, top_n=10, db_path="data/telemetry.db", output_json=None`
- **Mock needed:** False
- **Assertions:** 

### test_t070
- **Type:** unit
- **Requirement:** 
- **Description:** `main()` | Valid DB, threshold=100 | Returns `0`
- **Mock needed:** False
- **Assertions:** 

### test_t080
- **Type:** unit
- **Requirement:** 
- **Description:** `main()` | Nonexistent DB path | Returns `1`
- **Mock needed:** False
- **Assertions:** 

### test_t090
- **Type:** unit
- **Requirement:** 
- **Description:** `main()` | Valid DB, threshold=2 (3 events share pattern) | Returns `2`
- **Mock needed:** False
- **Assertions:** 

### test_t100
- **Type:** unit
- **Requirement:** 
- **Description:** `format_console_report()` | Report with `event_counts={"quality.gate_rejected": 12}` | `"quality.gate_rejected"` and `"12"` in output
- **Mock needed:** False
- **Assertions:** 

### test_t110
- **Type:** unit
- **Requirement:** 
- **Description:** `format_console_report()` | Report with 2 patterns with distinct nodes | Both node names in output
- **Mock needed:** False
- **Assertions:** 

### test_t120
- **Type:** unit
- **Requirement:** 
- **Description:** `write_json_report()` | Report dict -> tmp file -> `orjson.loads` | All 5 AuditReport keys present in parsed dict
- **Mock needed:** False
- **Assertions:** 

### test_t130
- **Type:** unit
- **Requirement:** 
- **Description:** `test_write_attempt_raises_error()` | `sqlite3.connect(db_path)` with `PRAGMA query_only = ON`, then `INSERT INTO telemetry_events VALUES (...)` | `sqlite3.OperationalError` raised
- **Mock needed:** False
- **Assertions:** 

### test_t140
- **Type:** unit
- **Requirement:** 
- **Description:** `main()` | Empty DB (schema but no rows) | Returns `0`, stdout contains "No telemetry events"
- **Mock needed:** False
- **Assertions:** 

### test_t150
- **Type:** unit
- **Requirement:** 
- **Description:** `load_telemetry_events()` | `db_path="/tmp/nonexistent.db"` | Raises `FileNotFoundError`
- **Mock needed:** False
- **Assertions:** 

### test_t160
- **Type:** unit
- **Requirement:** 
- **Description:** `build_report()` | 5 same-pattern events, threshold=3 | `threshold_triggered is True`
- **Mock needed:** False
- **Assertions:** 

### test_t170
- **Type:** unit
- **Requirement:** 
- **Description:** `build_report()` | 2 distinct events, threshold=3 | `threshold_triggered is False`
- **Mock needed:** False
- **Assertions:** 

## Original Test Plan Section

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | Module import | `import mine_quality_patterns` | All 8 public functions exist as attributes |
| T020 | `load_telemetry_events()` | DB with all 3 event types, since="2026-01-01" | Set of returned event_types == 3 expected types |
| T030 | `mine_patterns()` | 3 same-pattern + 1 different events, top_n=10 | `patterns[0]["count"]==3`, `patterns[1]["count"]==1` |
| T040 | `mine_patterns()` | 5 distinct patterns, top_n=3 | `len(patterns)==3` |
| T050 | `parse_args()` | All 5 flags explicitly set | Namespace fields match supplied values |
| T060 | `parse_args()` | Empty argv | `days=7, threshold=3, top_n=10, db_path="data/telemetry.db", output_json=None` |
| T070 | `main()` | Valid DB, threshold=100 | Returns `0` |
| T080 | `main()` | Nonexistent DB path | Returns `1` |
| T090 | `main()` | Valid DB, threshold=2 (3 events share pattern) | Returns `2` |
| T100 | `format_console_report()` | Report with `event_counts={"quality.gate_rejected": 12}` | `"quality.gate_rejected"` and `"12"` in output |
| T110 | `format_console_report()` | Report with 2 patterns with distinct nodes | Both node names in output |
| T120 | `write_json_report()` | Report dict -> tmp file -> `orjson.loads` | All 5 AuditReport keys present in parsed dict |
| T130 | `test_write_attempt_raises_error()` | `sqlite3.connect(db_path)` with `PRAGMA query_only = ON`, then `INSERT INTO telemetry_events VALUES (...)` | `sqlite3.OperationalError` raised |
| T140 | `main()` | Empty DB (schema but no rows) | Returns `0`, stdout contains "No telemetry events" |
| T150 | `load_telemetry_events()` | `db_path="/tmp/nonexistent.db"` | Raises `FileNotFoundError` |
| T160 | `build_report()` | 5 same-pattern events, threshold=3 | `threshold_triggered is True` |
| T170 | `build_report()` | 2 distinct events, threshold=3 | `threshold_triggered is False` |

Additional tests beyond LLD minimum:

| Test | Tests Function | Input | Expected Output |
|------|---------------|-------|-----------------|
| - | `extract_pattern_key()` stability | Same event twice | Identical string keys |
| - | `extract_pattern_key()` malformed JSON | `detail="not-json"` | Key uses `detail[:64]` |
| - | `extract_pattern_key()` no reason key | Valid JSON without "reason" | Key uses `detail[:64]` |
| - | `extract_pattern_key()` long detail | 200-char non-JSON string | Reason part is 64 chars |
| - | `extract_pattern_key()` empty detail | `detail=""` | Key ends with `\|` |
| - | `mine_patterns()` empty | `[]` | `[]` |
| - | `mine_patterns()` first/last seen | 2 events same pattern, different timestamps | Correct min/max |
| - | `mine_patterns()` example_ids capped | 5 events same pattern | `len(example_workflow_ids)==3` |
| - | `build_report()` empty events | `[]` | `threshold_triggered=False`, empty counts/patterns |
| - | `format_console_report()` empty | No patterns | `"(none)"` in output |
| - | `write_json_report()` mkdir | Nested nonexistent dirs | File created, dirs created |
| - | `main()` with --output-json | Valid DB, output path | File exists, valid JSON |
| - | WATCHED_EVENT_TYPES constant | — | Exactly 3 entries, correct values |
