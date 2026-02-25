# Extracted Test Plan

## Scenarios

### test_t010
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `detect_cascade_risk()` | `"Great, issue #42 is fixed! Should I continue with issue #43?"` | `detected=True, risk_level>=MEDIUM`

### test_t020
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `detect_cascade_risk()` | `"Done! What's next?\n1. Yes, start issue #44\n2. No, stop here"` | `risk_level=CRITICAL, action=block_and_alert`

### test_t030
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `detect_cascade_risk()`, `is_permission_prompt()` | `"Allow bash command: git push origin main? (y/n)"` | `detected=False, action=allow`

### test_t040
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `detect_cascade_risk()` | `"I've completed the refactor. Now let me also update the tests..."` | `detected=True, risk_level>=MEDIUM`

### test_t050
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `detect_cascade_risk()` | `"While I'm at it, I could also fix the related CSS issue..."` | `detected=True, risk_level>=MEDIUM`

### test_t060
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `detect_cascade_risk()` | `""` and `None` | `detected=False, risk_level=NONE`

### test_t070
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `load_user_patterns()`, `load_default_patterns()` | Corrupt JSON file | Empty user patterns, 15+ defaults, no crash

### test_t080
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `detect_cascade_risk()` | `"a"*10000 + " Should I " + "b"*10000` | Completes in <100ms

### test_t090
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `log_cascade_event()` | Valid CascadeEvent | JSONL file with all fields

### test_t100
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `merge_patterns()` | Default CP-001 + user CP-001 | User regex used

### test_t110
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `detect_cascade_risk()` | `"Should I format this differently?"` | `action=allow`

### test_t120
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `detect_cascade_risk()` | Single-category vs multi-category text | Multi score > single score

### test_t130
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `format_block_message()` | HIGH risk result | Contains "cascade", risk level, pattern IDs

### test_t140
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `get_cascade_stats()` | Log with 5 events (3 blocked, 2 allowed) | `{total_checks: 5, detections: 3, blocks: 3, allowed: 2}`

### test_t150
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `main()` via subprocess | JSON hook input with cascade/clean text | exit(2) for cascade, exit(0) for clean

### test_t160
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `handle_cascade_detection()` | MEDIUM risk result | Returns `False`

### test_t170
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `create_cascade_event()` | HIGH risk result | All 8 CascadeEvent fields present

### test_t180
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `load_user_patterns()` | Valid JSON with 2 patterns | Returns 2 patterns

### test_t190
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `merge_patterns()` | Default CP-001 regex A + user CP-001 regex B | Merged CP-001 has regex B

### test_t200
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `detect_cascade_risk()` | 2000-char text, 100 runs | Average <5ms

### test_t210
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `detect_cascade_risk()` | 10000-char text, 100 runs | Average <5ms

### test_t260
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `validate_claude_md_cascade_rule()` | `CLAUDE.md` | `rule_present=True`

### test_t270
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `validate_claude_md_cascade_rule()` | `CLAUDE.md` | `contains_open_ended=True, forbids_numbered_options=True`

### test_t280
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `validate_claude_md_cascade_rule()` | `CLAUDE.md` | `section_correct=True`

