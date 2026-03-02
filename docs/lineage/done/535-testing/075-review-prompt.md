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

# Test Plan for Issue #535

## Requirements to Cover

- REQ-T010: compute_issue_weight()
- REQ-T020: compute_issue_weight()
- REQ-T030: compute_issue_weight()
- REQ-T040: compute_issue_weight()
- REQ-T050: compute_age_meter()
- REQ-T060: check_meter_threshold()
- REQ-T070: check_meter_threshold()
- REQ-T080: save/load_age_meter_state()
- REQ-T090: scan_readme_claims()
- REQ-T100: scan_readme_claims()
- REQ-T110: scan_inventory_accuracy()
- REQ-T120: scan_inventory_accuracy()
- REQ-T130: compute_drift_score()
- REQ-T140: check_critical_drift()
- REQ-T150: walk_the_field()
- REQ-T160: harvest()
- REQ-T170: run_death()
- REQ-T180: _route_after_harvest()
- REQ-T190: _route_after_harvest()
- REQ-T200: _node_rest()
- REQ-T210: _node_rest()
- REQ-T220: run_drift_probe()
- REQ-T230: should_death_arrive()
- REQ-T240: should_death_arrive()
- REQ-T250: should_death_arrive()
- REQ-T260: AgeMeterState
- REQ-T270: DriftFinding
- REQ-T280: parse_death_args()
- REQ-T290: parse_death_args()
- REQ-T300: parse_death_args()
- REQ-T310: parse_death_args()
- REQ-T320: parse_death_args()
- REQ-T330: invoke_death_skill()
- REQ-T340: invoke_death_skill()
- REQ-T350: format_report_output()
- REQ-T360: generate_adr()
- REQ-T370: generate_adr()
- REQ-T380: generate_adr()
- REQ-T390: generate_adr()

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

### test_id
- **Type:** unit
- **Requirement:** 
- **Description:** Tests Function | File | Input | Expected Output
- **Mock needed:** False
- **Assertions:** 

### test_t010
- **Type:** unit
- **Requirement:** 
- **Description:** `compute_issue_weight()` | `test_age_meter.py` | `labels=["bug"], title="Fix broken link"` | `(1, "bug")`
- **Mock needed:** False
- **Assertions:** 

### test_t020
- **Type:** unit
- **Requirement:** 
- **Description:** `compute_issue_weight()` | `test_age_meter.py` | `labels=["architecture"], title="Redesign plugin system"` | `(10, "architecture")`
- **Mock needed:** False
- **Assertions:** 

### test_t030
- **Type:** unit
- **Requirement:** 
- **Description:** `compute_issue_weight()` | `test_age_meter.py` | `labels=["question"], title="How do I run tests?"` | `(2, "default")`
- **Mock needed:** False
- **Assertions:** 

### test_t040
- **Type:** unit
- **Requirement:** 
- **Description:** `compute_issue_weight()` | `test_age_meter.py` | `labels=["bug", "architecture"], title="Breaking core change"` | `(10, "architecture")`
- **Mock needed:** False
- **Assertions:** 

### test_t050
- **Type:** unit
- **Requirement:** 
- **Description:** `compute_age_meter()` | `test_age_meter.py` | existing score=20 + persona issue | `score=25`
- **Mock needed:** False
- **Assertions:** 

### test_t060
- **Type:** unit
- **Requirement:** 
- **Description:** `check_meter_threshold()` | `test_age_meter.py` | `score=49, threshold=50` | `False`
- **Mock needed:** False
- **Assertions:** 

### test_t070
- **Type:** unit
- **Requirement:** 
- **Description:** `check_meter_threshold()` | `test_age_meter.py` | `score=50, threshold=50` | `True`
- **Mock needed:** False
- **Assertions:** 

### test_t080
- **Type:** unit
- **Requirement:** 
- **Description:** `save/load_age_meter_state()` | `test_age_meter.py` | AgeMeterState with score=47 | Identical after round-trip
- **Mock needed:** False
- **Assertions:** 

### test_t090
- **Type:** unit
- **Requirement:** 
- **Description:** `scan_readme_claims()` | `test_drift_scorer.py` | README "12 agents" vs 36 files | DriftFinding(count_mismatch)
- **Mock needed:** False
- **Assertions:** 

### test_t100
- **Type:** unit
- **Requirement:** 
- **Description:** `scan_readme_claims()` | `test_drift_scorer.py` | README "36 agents" vs 36 files | No findings
- **Mock needed:** False
- **Assertions:** 

### test_t110
- **Type:** unit
- **Requirement:** 
- **Description:** `scan_inventory_accuracy()` | `test_drift_scorer.py` | Missing file in inventory | DriftFinding(stale_reference)
- **Mock needed:** False
- **Assertions:** 

### test_t120
- **Type:** unit
- **Requirement:** 
- **Description:** `scan_inventory_accuracy()` | `test_drift_scorer.py` | File exists in inventory | No findings
- **Mock needed:** False
- **Assertions:** 

### test_t130
- **Type:** unit
- **Requirement:** 
- **Description:** `compute_drift_score()` | `test_drift_scorer.py` | 2 critical + 1 major + 3 minor | `28.0`
- **Mock needed:** False
- **Assertions:** 

### test_t140
- **Type:** unit
- **Requirement:** 
- **Description:** `check_critical_drift()` | `test_drift_scorer.py` | `score=30.0` | `True`
- **Mock needed:** False
- **Assertions:** 

### test_t150
- **Type:** unit
- **Requirement:** 
- **Description:** `walk_the_field()` | `test_reconciler.py` | count_mismatch finding | update_count action
- **Mock needed:** False
- **Assertions:** 

### test_t160
- **Type:** unit
- **Requirement:** 
- **Description:** `harvest()` | `test_reconciler.py` | `dry_run=True` | No file writes
- **Mock needed:** False
- **Assertions:** 

### test_t170
- **Type:** unit
- **Requirement:** 
- **Description:** `run_death()` | `test_hourglass.py` | `mode="report"` | Report completes
- **Mock needed:** False
- **Assertions:** 

### test_t180
- **Type:** unit
- **Requirement:** 
- **Description:** `_route_after_harvest()` | `test_hourglass.py` | `confirmed=True, mode="reaper"` | `"archive"`
- **Mock needed:** False
- **Assertions:** 

### test_t190
- **Type:** unit
- **Requirement:** 
- **Description:** `_route_after_harvest()` | `test_hourglass.py` | `confirmed=False, mode="reaper"` | `"complete"`
- **Mock needed:** False
- **Assertions:** 

### test_t200
- **Type:** unit
- **Requirement:** 
- **Description:** `_node_rest()` | `test_hourglass.py` | age_number=3 | age_number=4, score=0
- **Mock needed:** False
- **Assertions:** 

### test_t210
- **Type:** unit
- **Requirement:** 
- **Description:** `_node_rest()` | `test_hourglass.py` | Mock history file | Entry appended
- **Mock needed:** True
- **Assertions:** 

### test_t220
- **Type:** unit
- **Requirement:** 
- **Description:** `run_drift_probe()` | `test_skill.py` | Mock codebase | Dict with required keys
- **Mock needed:** True
- **Assertions:** 

### test_t230
- **Type:** unit
- **Requirement:** 
- **Description:** `should_death_arrive()` | `test_hourglass.py` | Low meter + low drift | `(False, _, _)`
- **Mock needed:** False
- **Assertions:** 

### test_t240
- **Type:** unit
- **Requirement:** 
- **Description:** `should_death_arrive()` | `test_hourglass.py` | High meter | `(True, "meter", _)`
- **Mock needed:** False
- **Assertions:** 

### test_t250
- **Type:** unit
- **Requirement:** 
- **Description:** `should_death_arrive()` | `test_hourglass.py` | High drift | `(True, "critical_drift", _)`
- **Mock needed:** False
- **Assertions:** 

### test_t260
- **Type:** unit
- **Requirement:** 
- **Description:** `AgeMeterState` | `test_models.py` | Valid dict | Fields accessible
- **Mock needed:** False
- **Assertions:** 

### test_t270
- **Type:** unit
- **Requirement:** 
- **Description:** `DriftFinding` | `test_models.py` | All categories | All accepted
- **Mock needed:** False
- **Assertions:** 

### test_t280
- **Type:** unit
- **Requirement:** 
- **Description:** `parse_death_args()` | `test_skill.py` | `["report"]` | `("report", False)`
- **Mock needed:** False
- **Assertions:** 

### test_t290
- **Type:** unit
- **Requirement:** 
- **Description:** `parse_death_args()` | `test_skill.py` | `["reaper"]` | `("reaper", False)`
- **Mock needed:** False
- **Assertions:** 

### test_t300
- **Type:** unit
- **Requirement:** 
- **Description:** `parse_death_args()` | `test_skill.py` | `["reaper", "--force"]` | `("reaper", True)`
- **Mock needed:** False
- **Assertions:** 

### test_t310
- **Type:** unit
- **Requirement:** 
- **Description:** `parse_death_args()` | `test_skill.py` | `["invalid"]` | `ValueError`
- **Mock needed:** False
- **Assertions:** 

### test_t320
- **Type:** unit
- **Requirement:** 
- **Description:** `parse_death_args()` | `test_skill.py` | `[]` | `("report", False)`
- **Mock needed:** False
- **Assertions:** 

### test_t330
- **Type:** unit
- **Requirement:** 
- **Description:** `invoke_death_skill()` | `test_skill.py` | `["report"]` | Report returned
- **Mock needed:** False
- **Assertions:** 

### test_t340
- **Type:** unit
- **Requirement:** 
- **Description:** `invoke_death_skill()` | `test_skill.py` | `["reaper"]` no force | `PermissionError`
- **Mock needed:** False
- **Assertions:** 

### test_t350
- **Type:** unit
- **Requirement:** 
- **Description:** `format_report_output()` | `test_skill.py` | Full report | Markdown with sections
- **Mock needed:** False
- **Assertions:** 

### test_t360
- **Type:** unit
- **Requirement:** 
- **Description:** `generate_adr()` | `test_reconciler.py` | architecture_drift finding | ADR content string
- **Mock needed:** False
- **Assertions:** 

### test_t370
- **Type:** unit
- **Requirement:** 
- **Description:** `generate_adr()` | `test_reconciler.py` | count_mismatch finding | `None`
- **Mock needed:** False
- **Assertions:** 

### test_t380
- **Type:** unit
- **Requirement:** 
- **Description:** `generate_adr()` | `test_reconciler.py` | `dry_run=False` | File created
- **Mock needed:** False
- **Assertions:** 

### test_t390
- **Type:** unit
- **Requirement:** 
- **Description:** `generate_adr()` | `test_reconciler.py` | `dry_run=True` | Content, no file
- **Mock needed:** False
- **Assertions:** 

## Original Test Plan Section

| Test ID | Tests Function | File | Input | Expected Output |
|---------|---------------|------|-------|-----------------|
| T010 | `compute_issue_weight()` | `test_age_meter.py` | `labels=["bug"], title="Fix broken link"` | `(1, "bug")` |
| T020 | `compute_issue_weight()` | `test_age_meter.py` | `labels=["architecture"], title="Redesign plugin system"` | `(10, "architecture")` |
| T030 | `compute_issue_weight()` | `test_age_meter.py` | `labels=["question"], title="How do I run tests?"` | `(2, "default")` |
| T040 | `compute_issue_weight()` | `test_age_meter.py` | `labels=["bug", "architecture"], title="Breaking core change"` | `(10, "architecture")` |
| T050 | `compute_age_meter()` | `test_age_meter.py` | existing score=20 + persona issue | `score=25` |
| T060 | `check_meter_threshold()` | `test_age_meter.py` | `score=49, threshold=50` | `False` |
| T070 | `check_meter_threshold()` | `test_age_meter.py` | `score=50, threshold=50` | `True` |
| T080 | `save/load_age_meter_state()` | `test_age_meter.py` | AgeMeterState with score=47 | Identical after round-trip |
| T090 | `scan_readme_claims()` | `test_drift_scorer.py` | README "12 agents" vs 36 files | DriftFinding(count_mismatch) |
| T100 | `scan_readme_claims()` | `test_drift_scorer.py` | README "36 agents" vs 36 files | No findings |
| T110 | `scan_inventory_accuracy()` | `test_drift_scorer.py` | Missing file in inventory | DriftFinding(stale_reference) |
| T120 | `scan_inventory_accuracy()` | `test_drift_scorer.py` | File exists in inventory | No findings |
| T130 | `compute_drift_score()` | `test_drift_scorer.py` | 2 critical + 1 major + 3 minor | `28.0` |
| T140 | `check_critical_drift()` | `test_drift_scorer.py` | `score=30.0` | `True` |
| T150 | `walk_the_field()` | `test_reconciler.py` | count_mismatch finding | update_count action |
| T160 | `harvest()` | `test_reconciler.py` | `dry_run=True` | No file writes |
| T170 | `run_death()` | `test_hourglass.py` | `mode="report"` | Report completes |
| T180 | `_route_after_harvest()` | `test_hourglass.py` | `confirmed=True, mode="reaper"` | `"archive"` |
| T190 | `_route_after_harvest()` | `test_hourglass.py` | `confirmed=False, mode="reaper"` | `"complete"` |
| T200 | `_node_rest()` | `test_hourglass.py` | age_number=3 | age_number=4, score=0 |
| T210 | `_node_rest()` | `test_hourglass.py` | Mock history file | Entry appended |
| T220 | `run_drift_probe()` | `test_skill.py` | Mock codebase | Dict with required keys |
| T230 | `should_death_arrive()` | `test_hourglass.py` | Low meter + low drift | `(False, _, _)` |
| T240 | `should_death_arrive()` | `test_hourglass.py` | High meter | `(True, "meter", _)` |
| T250 | `should_death_arrive()` | `test_hourglass.py` | High drift | `(True, "critical_drift", _)` |
| T260 | `AgeMeterState` | `test_models.py` | Valid dict | Fields accessible |
| T270 | `DriftFinding` | `test_models.py` | All categories | All accepted |
| T280 | `parse_death_args()` | `test_skill.py` | `["report"]` | `("report", False)` |
| T290 | `parse_death_args()` | `test_skill.py` | `["reaper"]` | `("reaper", False)` |
| T300 | `parse_death_args()` | `test_skill.py` | `["reaper", "--force"]` | `("reaper", True)` |
| T310 | `parse_death_args()` | `test_skill.py` | `["invalid"]` | `ValueError` |
| T320 | `parse_death_args()` | `test_skill.py` | `[]` | `("report", False)` |
| T330 | `invoke_death_skill()` | `test_skill.py` | `["report"]` | Report returned |
| T340 | `invoke_death_skill()` | `test_skill.py` | `["reaper"]` no force | `PermissionError` |
| T350 | `format_report_output()` | `test_skill.py` | Full report | Markdown with sections |
| T360 | `generate_adr()` | `test_reconciler.py` | architecture_drift finding | ADR content string |
| T370 | `generate_adr()` | `test_reconciler.py` | count_mismatch finding | `None` |
| T380 | `generate_adr()` | `test_reconciler.py` | `dry_run=False` | File created |
| T390 | `generate_adr()` | `test_reconciler.py` | `dry_run=True` | Content, no file |
