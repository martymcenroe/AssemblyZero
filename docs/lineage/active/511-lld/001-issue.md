---
repo: martymcenroe/AssemblyZero
issue: 511
url: https://github.com/martymcenroe/AssemblyZero/issues/511
fetched: 2026-02-28T18:57:20.617906Z
---

# Issue #511: enhancement: persist per-node LLM cost through audit trail, telemetry, and dashboard

## Problem

AssemblyZero computes per-LLM-call cost perfectly — every provider populates `cost_usd`, `input_tokens`, `output_tokens` in `LLMCallResult`, and `log_llm_call()` prints cumulative cost to stdout. Budget enforcement works via `--budget` flag.

But **none of this is persisted**. Cost is printed to stdout during execution and then lost. There is no persistent record of what any past workflow run cost, let alone a per-node breakdown within a run. The entire storage and display chain is missing.

### Current state of the chain

| Layer | Status | What exists |
|-------|--------|-------------|
| Per-call cost calculation | ✅ Done | `LLMCallResult.cost_usd`, token counts, cache tokens |
| Cumulative session tracking | ✅ Done | `get_cumulative_cost()`, budget checks in nodes |
| Stdout logging | ✅ Done | `[LLM] provider=claude cost=$0.04 cumulative=$0.12` |
| Audit trail files | ❌ No cost fields | `filed.json`, `test-report.json` have iterations/coverage only |
| `workflow-audit.jsonl` | ❌ No cost fields | Events log iterations/verdicts/coverage, not cost |
| `.implement-status-*.json` | ❌ No cost fields | Logs status/error only |
| Telemetry (`emit()` to DynamoDB) | ❌ No cost data | Tracks tool duration only |
| DynamoDB schema | ❌ No cost columns | GSIs on actor/user/date, no cost field |
| Dashboard | ❌ No cost view | No cost visualization exists |

### Impact

- Cannot answer "what did the last 10 workflow runs cost?"
- Cannot identify which nodes are the most expensive (suspected: generate_draft revision loops, review iterations)
- Cannot track cost trends over time
- Cannot validate that optimizations (#488-#492, #508, #509) actually reduced spend
- Budget enforcement works reactively (stops after exceeding) but there's no historical data to set informed budgets

## Proposed approach — 4 layers

### Layer 1: Per-node cost capture in workflow nodes

Each node that calls an LLM should record its cost delta:

```python
# Pattern for every LLM-calling node:
cost_before = get_cumulative_cost()
result = provider.invoke(...)
cost_after = get_cumulative_cost()
node_cost = cost_after - cost_before

# Include in return dict
return {
    ...,
    "node_cost_usd": node_cost,
    "node_input_tokens": result.input_tokens,
    "node_output_tokens": result.output_tokens,
}
```

Affected nodes (all LLM-calling):
- `generate_draft.py` (Requirements — Claude)
- `review.py` (Requirements — Gemini)
- `generate_spec.py` (Impl Spec — Claude)
- `review_spec.py` (Impl Spec — Gemini)
- `review_test_plan.py` (Testing — Gemini)
- `implement_code.py` (Testing — Claude)
- `adversarial_node.py` (Testing — Gemini)
- `gap_analyst_node` (Scout — Gemini)

### Layer 2: Persist cost in audit trail and status files

**`workflow-audit.jsonl`** — add cost fields to completion events:
```json
{
  "timestamp": "...",
  "workflow_type": "requirements",
  "issue_number": 506,
  "event": "workflow_complete",
  "details": {
    "total_cost_usd": 0.47,
    "cost_by_node": {
      "generate_draft": 0.28,
      "review": 0.12,
      "generate_draft_revision": 0.07
    },
    "total_input_tokens": 45000,
    "total_output_tokens": 12000,
    "iterations": 3
  }
}
```

**Final status files** (`filed.json`, `test-report.json`, `.implement-status-*.json`) — add:
```json
{
  "total_cost_usd": 0.47,
  "cost_by_node": {"generate_draft": 0.28, "review": 0.12},
  "total_tokens": 57000
}
```

### Layer 3: Emit cost to telemetry (DynamoDB)

Add cost fields to `tool.complete` telemetry events:
```python
emit("tool.complete", {
    "tool": "run_requirements_workflow",
    "duration_ms": 42000,
    "cost_usd": 0.47,           # NEW
    "input_tokens": 45000,       # NEW
    "output_tokens": 12000,      # NEW
    "cost_by_node": {...},       # NEW (optional — may be too large for DynamoDB item)
})
```

DynamoDB schema change: no new GSI needed — cost fields are queryable via existing date/repo GSIs.

### Layer 4: Dashboard cost visualization

Add a "Cost" tab to the telemetry dashboard showing:
- **Cost per run** — bar chart, last N runs, colored by workflow type
- **Cost by node** — stacked bar or treemap showing which nodes consume most
- **Cost trend** — line chart over time (daily/weekly aggregation)
- **Cost per issue** — table: issue number, workflow type, total cost, iterations
- **Budget utilization** — how close runs get to the `--budget` limit

## Node cost tracking design consideration

The cumulative cost tracker (`_cumulative_cost_usd`) is a module-level global. For per-node cost, the cleanest approach is the delta pattern (cost_after - cost_before) rather than resetting the global per-node. This preserves the existing budget-check behavior while adding per-node visibility.

An alternative: a cost context manager similar to `track_tool()` in telemetry:
```python
with track_cost("generate_draft") as cost:
    result = provider.invoke(...)
# cost.usd, cost.input_tokens, cost.output_tokens available
```

The LLD should evaluate both approaches.

## Depends On

- Independent of #494 (JSON migration) — cost tracking is orthogonal to output format
- Independent of #508 (prompt-size awareness) — but cost data would help calibrate size limits
- Independent of #509 (mechanical pre-flight gates) — but cost data would measure their savings

## Acceptance Criteria

- [ ] Every LLM-calling node records its cost delta in returned state
- [ ] `workflow-audit.jsonl` completion events include `total_cost_usd` and `cost_by_node`
- [ ] Final status files (`filed.json`, `test-report.json`) include cost totals
- [ ] Telemetry `tool.complete` events include cost fields
- [ ] Dashboard displays cost-per-run for last N runs
- [ ] Dashboard displays cost-by-node breakdown
- [ ] Can answer "what did the last 10 workflow runs cost?" from persisted data
- [ ] Historical runs before this change show `null` cost (graceful degradation)
- [ ] Unit tests for cost delta capture
- [ ] No regression in existing workflow behavior