---
repo: martymcenroe/AssemblyZero
issue: 571
url: https://github.com/martymcenroe/AssemblyZero/issues/571
fetched: 2026-03-04T06:22:05.484330Z
---

# Issue #571: fix: run_implement_from_lld crashes on None node_output during scaffold regeneration loop

## Bug

`tools/run_implement_from_lld.py` line 776 crashes with `AttributeError: 'NoneType' object has no attribute 'get'` when scaffold node returns empty dict during regeneration loop.

## Reproduction

Observed on Hermes issue #283 TDD workflow. Sequence:

1. **N2** scaffolds test file (147 lines of placeholder assertions)
2. **N2.5** validates → rejects as "empty test file"
3. Regeneration loop routes back to **N2**
4. **N2** sees existing file → `return {}` (skip-on-resume guard, `scaffold_tests.py:871-874`)
5. LangGraph streams event with `node_output = None` (or empty)
6. **Line 776**: `node_output.get("error_message", "")` → crash

## Root Cause

Two issues:

1. **Immediate crash**: Line 776 doesn't guard against `None` node output
2. **Dead loop**: Skip-on-resume guard in scaffold node prevents regeneration from working. When validation fails and routes back to scaffold, the stale file still exists, so scaffold skips. The regeneration loop can never produce a new file.

## Fix

1. Guard `node_output` at line 776: `error = (node_output or {}).get("error_message", "")`
2. Scaffold node should delete/overwrite existing files when re-entering via regeneration (not resume). The `scaffold_validation_errors` state key can distinguish regeneration from resume — if validation errors exist, scaffold should regenerate rather than skip.

## Traceback

```
[FATAL] Unexpected error: 'NoneType' object has no attribute 'get'
Traceback (most recent call last):
  File "C:\Users\mcwiz\Projects\AssemblyZero\tools\run_implement_from_lld.py", line 776, in main
    error = node_output.get("error_message", "")
            ^^^^^^^^^^^^^^^
AttributeError: 'NoneType' object has no attribute 'get'
```

## Key Files

| File | Lines | What |
|------|-------|------|
| `tools/run_implement_from_lld.py` | 776 | Crash site — no None guard |
| `assemblyzero/workflows/testing/nodes/scaffold_tests.py` | 871-874 | Skip-on-resume returns `{}` |
| `assemblyzero/workflows/testing/nodes/validate_tests_mechanical.py` | 398-438 | `should_regenerate()` routing |
| `assemblyzero/workflows/testing/graph.py` | 424-433 | Conditional edge back to N2 |