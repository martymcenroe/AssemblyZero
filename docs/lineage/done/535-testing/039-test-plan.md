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
- Description: `compute_issue_weight()` | `test_age_meter.py` | `labels=["bug"], title="Fix broken link"` | `(1, "bug")`

### test_t020
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `compute_issue_weight()` | `test_age_meter.py` | `labels=["architecture"], title="Redesign plugin system"` | `(10, "architecture")`

### test_t030
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `compute_issue_weight()` | `test_age_meter.py` | `labels=["question"], title="How do I run tests?"` | `(2, "default")`

### test_t040
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `compute_issue_weight()` | `test_age_meter.py` | `labels=["bug", "architecture"], title="Breaking core change"` | `(10, "architecture")`

### test_t050
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `compute_age_meter()` | `test_age_meter.py` | existing score=20 + persona issue | `score=25`

### test_t060
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `check_meter_threshold()` | `test_age_meter.py` | `score=49, threshold=50` | `False`

### test_t070
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `check_meter_threshold()` | `test_age_meter.py` | `score=50, threshold=50` | `True`

### test_t080
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `save/load_age_meter_state()` | `test_age_meter.py` | AgeMeterState with score=47 | Identical after round-trip

### test_t090
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `scan_readme_claims()` | `test_drift_scorer.py` | README "12 agents" vs 36 files | DriftFinding(count_mismatch)

### test_t100
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `scan_readme_claims()` | `test_drift_scorer.py` | README "36 agents" vs 36 files | No findings

### test_t110
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `scan_inventory_accuracy()` | `test_drift_scorer.py` | Missing file in inventory | DriftFinding(stale_reference)

### test_t120
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `scan_inventory_accuracy()` | `test_drift_scorer.py` | File exists in inventory | No findings

### test_t130
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `compute_drift_score()` | `test_drift_scorer.py` | 2 critical + 1 major + 3 minor | `28.0`

### test_t140
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `check_critical_drift()` | `test_drift_scorer.py` | `score=30.0` | `True`

### test_t150
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `walk_the_field()` | `test_reconciler.py` | count_mismatch finding | update_count action

### test_t160
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `harvest()` | `test_reconciler.py` | `dry_run=True` | No file writes

### test_t170
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `run_death()` | `test_hourglass.py` | `mode="report"` | Report completes

### test_t180
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `_route_after_harvest()` | `test_hourglass.py` | `confirmed=True, mode="reaper"` | `"archive"`

### test_t190
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `_route_after_harvest()` | `test_hourglass.py` | `confirmed=False, mode="reaper"` | `"complete"`

### test_t200
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `_node_rest()` | `test_hourglass.py` | age_number=3 | age_number=4, score=0

### test_t210
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `_node_rest()` | `test_hourglass.py` | Mock history file | Entry appended

### test_t220
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `run_drift_probe()` | `test_skill.py` | Mock codebase | Dict with required keys

### test_t230
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `should_death_arrive()` | `test_hourglass.py` | Low meter + low drift | `(False, _, _)`

### test_t240
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `should_death_arrive()` | `test_hourglass.py` | High meter | `(True, "meter", _)`

### test_t250
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `should_death_arrive()` | `test_hourglass.py` | High drift | `(True, "critical_drift", _)`

### test_t260
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `AgeMeterState` | `test_models.py` | Valid dict | Fields accessible

### test_t270
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `DriftFinding` | `test_models.py` | All categories | All accepted

### test_t280
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `parse_death_args()` | `test_skill.py` | `["report"]` | `("report", False)`

### test_t290
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `parse_death_args()` | `test_skill.py` | `["reaper"]` | `("reaper", False)`

### test_t300
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `parse_death_args()` | `test_skill.py` | `["reaper", "--force"]` | `("reaper", True)`

### test_t310
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `parse_death_args()` | `test_skill.py` | `["invalid"]` | `ValueError`

### test_t320
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `parse_death_args()` | `test_skill.py` | `[]` | `("report", False)`

### test_t330
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `invoke_death_skill()` | `test_skill.py` | `["report"]` | Report returned

### test_t340
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `invoke_death_skill()` | `test_skill.py` | `["reaper"]` no force | `PermissionError`

### test_t350
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `format_report_output()` | `test_skill.py` | Full report | Markdown with sections

### test_t360
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `generate_adr()` | `test_reconciler.py` | architecture_drift finding | ADR content string

### test_t370
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `generate_adr()` | `test_reconciler.py` | count_mismatch finding | `None`

### test_t380
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `generate_adr()` | `test_reconciler.py` | `dry_run=False` | File created

### test_t390
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `generate_adr()` | `test_reconciler.py` | `dry_run=True` | Content, no file

