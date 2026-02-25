# Extracted Test Plan

## Scenarios

### test_id
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Tests Phase | Invocation | Expected Output Characteristics

### test_t010_scenario_010
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Backward compat | `/test-gaps` | Layer 1 output only; no Layer 2/3 headings; structure identical to pre-change

### test_t020_scenario_020
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Layer 2 CI analysis | `/test-gaps --layer infra` | CI findings table with at least one check; header shows project type

### test_t030_scenario_030
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Layer 2 skip audit | `/test-gaps --layer infra` | Skip audit table with classifications

### test_t040_scenario_040
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Layer 2 pyramid | `/test-gaps --layer infra` | Pyramid visualization with counts and percentages

### test_t050_scenario_050
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Layer 3 auto-detection | `/test-gaps --layer heuristics` | Header shows detected project type with "(auto)"

### test_t060_scenario_060
- Type: unit
- Requirement: 
- Mock needed: True
- Description: Project type override | `/test-gaps --layer heuristics --project-type api` | Header shows "api (override)"; API checks run

### test_t070_scenario_070
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Report quality | `/test-gaps --layer heuristics` | Report Quality table with scores

### test_t080_scenario_080
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Full output structure | `/test-gaps --full` | All 3 layer headings; Recommended Actions sorted CRITICAL→LOW; Issues to Create with only HIGH+ items

### test_t090_scenario_090
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Cost ceiling | `/test-gaps --full` | Completes within 50 tool calls

### test_t100_scenario_100
- Type: unit
- Requirement: 
- Mock needed: False
- Description: All argument flags | Various | Each flag produces correct routing

### test_t110_scenario_110
- Type: unit
- Requirement: 
- Mock needed: False
- Description: No workflows | `/test-gaps --layer infra` (no .github/workflows/) | "No CI workflows found" message, no error

### test_t120_scenario_120
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Generic fallback | `/test-gaps --layer heuristics` (no markers) | "generic (auto)" in header; "no heuristic checks available" note

