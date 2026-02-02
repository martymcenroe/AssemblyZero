# Issue #160: fix: Human gates in requirements workflow don't actually gate

## Problem

The `--gates draft,verdict` configuration in the requirements workflow doesn't actually stop for human input. The gates are configured but the workflow runs straight through as if `--gates none` was specified.

**Reproduction:**
```bash
poetry run python tools/run_requirements_workflow.py --type lld --issue 83
# Note: no --gates flag, should default to draft,verdict
```

**Expected:** Workflow pauses at draft gate and verdict gate for human approval

**Actual:**
```
Gates:    draft,verdict      <-- Config shows gates ON
...
[N2] Human gate (draft)...
    Proceeding to review     <-- Just proceeds, no stop!
...
[N4] Human gate (verdict: APPROVED)...
                             <-- Same - no actual gate
```

## Impact

- Human review gates are ineffective
- Workflows run fully automated even when gates are configured
- Users think they have oversight but don't

## Likely Cause

The human gate node probably checks for a condition that's always true, or the gate logic was stubbed out and never implemented.

## Affected Code

- `agentos/workflows/requirements/nodes/human_gate.py` (likely)
- Gate configuration in `agentos/workflows/requirements/config.py`

## Labels
bug, workflow