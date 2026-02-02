# Issue #128: fix: add progress output to requirements workflow

## Problem

The requirements workflow (`run_requirements_workflow.py`) is silent while running. Users see:

```
Starting workflow...

```

And then nothing until it completes (or fails). No indication of progress.

Compare to the testing workflow which prints:
```
[N0] Loading LLD for issue #78...
[N1] Reviewing test plan...
    Scenarios: 9
    Requirements: 30
    Verdict: APPROVED
[N2] Scaffolding tests...
```

## Proposed Fix

Add print statements to each node in `agentos/workflows/requirements/nodes/`:

| Node | Output |
|------|--------|
| `load_input.py` | `[N0] Loading input...` + issue/brief details |
| `generate_draft.py` | `[N1] Generating draft...` + drafter model |
| `review.py` | `[N2] Reviewing draft...` + verdict |
| `human_gate.py` | `[N3] Human gate...` + decision |
| `finalize.py` | `[N4] Finalizing...` + output path |

## Files to Update

- `agentos/workflows/requirements/nodes/load_input.py`
- `agentos/workflows/requirements/nodes/generate_draft.py`
- `agentos/workflows/requirements/nodes/review.py`
- `agentos/workflows/requirements/nodes/human_gate.py`
- `agentos/workflows/requirements/nodes/finalize.py`

## Acceptance Criteria

- [ ] Each node prints its name and key info when starting
- [ ] Review node prints verdict (APPROVED/BLOCKED)
- [ ] Human gate prints decision (approve/reject/feedback)
- [ ] Finalize prints output file path
- [ ] Output matches testing workflow style (`[N#] Action...`)