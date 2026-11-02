# 101 - Feature: Mechanic: Stale Observations (Frozen Screen During Actual Settlement)

## 1. Context & Goal
* **Issue:** #101
* **Objective:** Introduce an optional `grid.observation_outage[]` mechanic where player-facing observation telemetry freezes on configured turns with `stale: true` while settlement arithmetic strictly evaluates against ground-truth actuals.
* **Status:** Approved (gemini-3.8-flash-high, 2026-11-02)

### Open Questions
None.

## 2. Proposed Changes

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `src/target/compiler.py` | Modify | Add schema validation and compilation support for `grid.observation_outage` in scenario packs. |
| `src/target/outage.py` | Add | Implement observation outage data structures, turn outage detection, and field freezing transformation logic. |
| `tests/unit/test_observation_outage.py` | Add | Unit and contract tests for observation outage compilation, telemetry freezing, settlement isolation, and replay determinism. |

### 2.1.1 Path Validation (Mechanical - Auto-Checked)

Mechanical validation automatically checks:
- All "Modify" files must exist in repository
- All "Add" files must have existing parent directories

### 2.2 Dependencies

No new external dependencies required.

### 2.4 Function Signatures

```python
def validate_observation_outages(outages: Optional[List[dict[str, Any]]], total_turns: int) -> None:
    """Validate observation outage configuration against pack constraints."""
    ...


def resolve_turn_observation(actuals: ActualTurnData, outages: Optional[List[ObservationOutageConfig]], tracker: OutageStateTracker) -> Observation:
    """Transform actual turn state into player observation, freezing configured fields if in outage."""
    ...


def calculate_settlement(actuals: ActualTurnData, dispatched_mw: float) -> dict[str, float]:
    """Calculate turn settlement strictly against actuals, ignoring observation frozen state."""
    ...
```

### 2.6 Technical Approach

* **Module:** `src/target/outage.py` and `src/target/compiler.py`
* **Pattern:** Presentation Decorator / Pipeline Filter pattern.

## 3. Requirements

1. The scenario pack schema and compiler MUST accept an optional `grid.observation_outage` list containing objects with `turns_active` and `frozen_fields`.
2. The compiler MUST validate that `turns_active` contains integer turn indices within `[0, total_turns - 1]` and `frozen_fields` contains only recognized fields (`price_usd_per_mwh`, `system_status`, `forecast`).
3. Scenario packs omitting `grid.observation_outage` MUST compile and generate observations that are bit-identical to legacy scenarios without the feature.
4. The runtime engine MUST evaluate each turn index against `turns_active` to detect active telemetry outages.
5. On turns matching an active outage, the observation generator MUST set `stale: true` and substitute values for all specified `frozen_fields` with the last observed non-stale values.
6. On active outage turns, fields not listed in `frozen_fields` MUST display current actual values without alteration.
7. On turns where no outage is active, the observation generator MUST set `stale: false` and update all cached values with current actuals.
8. Settlement calculations MUST compute energy costs, penalties, and reliability metrics strictly against actual grid conditions regardless of observation stale status.
9. Deterministic replay verification MUST produce identical financial and reliability scores from identical player actions regardless of observation freezing.
10. The observation generator MUST include scenario-configured `notice_md` markdown notices during outage turns when present, or omit `notice_md` for silent failure scenarios.

## 10. Verification & Testing

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | Valid outage pack schema compilation (REQ-1) | Auto | Pack config with `grid.observation_outage` | Valid compiled pack object | Outage config preserved in output |
| 020 | Schema validation rejects invalid fields or bounds (REQ-2) | Auto | Outage config with negative turn or unknown field | `ValueError` raised | Exception caught and message verified |
| 030 | Absent outage config bit-identical baseline (REQ-3) | Auto | Pack without `observation_outage` | Identical serialized JSON to baseline | Byte-for-byte equality |
| 040 | Active turn detection during episode step (REQ-4) | Auto | Turn 12 with active turns `[12, 13, 14]` | Outage config returned | Config matches active definition |
| 050 | Telemetry freezing for price and system status (REQ-5) | Auto | Turn 12 actual price=$200, frozen at turn 11 price=$50 | Obs price=$50, `stale=True` | Frozen value matches turn 11 |
| 060 | Unfrozen forecast updates while price is frozen (REQ-6) | Auto | Outage with `frozen_fields=["price_usd_per_mwh"]` | Obs price frozen, forecast reflects actuals | Partial field freeze verified |
| 070 | Recovery after outage turn clears stale flag (REQ-7) | Auto | Turn 15 following outage ending at turn 14 | Obs price=actual turn 15 price, `stale=False` | Telemetry restored to actuals |
| 080 | Settlement uses actual prices during freeze (REQ-8) | Auto | Player dispatches 100MW at frozen price=$50, actual=$200 | Settlement cost = $20,000 (100 * 200) | Settlement strictly matches actual price |
| 090 | Replay determinism score equality (REQ-9) | Auto | Identical player actions replayed on frozen scenario | Stored score matches replay score exactly | Score delta == 0.0 |
| 100 | Notice markdown propagation and silent outage (REQ-10) | Auto | Pack with `notice_md` vs pack with `notice_md: None` | `notice_md` populated or None accordingly | Matches scenario specification |

## 11. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Settlement arithmetic reading presentation Observation instead of ActualTurnData | High | Low | Enforce strict type isolation in `calculate_settlement`, accepting only `ActualTurnData`. |
| Outage configuration schema regression breaking legacy packs | High | Low | Validate optionality in `validate_observation_outages`. |

## 12. Definition of Done

### Code
- [ ] Implementation complete and linted (`src/target/compiler.py`, `src/target/outage.py`)

### Tests
- [ ] All test scenarios pass (`tests/unit/test_observation_outage.py`)
